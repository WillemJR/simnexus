"""
Progress reporting for long-running workflows.

Status is exchanged between the workflow process and consumers (e.g. a GUI
running as a separate process) through small ``status.json`` files written
into the work directories -- the same channel already used for
``iter_variables.json`` and ``actions_output.pkl``. Files are written
atomically (temp file + ``os.replace``), so a reader never sees a
half-written file, and either side can start, stop or crash independently.

Writer side (used internally by ``DirectedGraph`` and
``SimulationIterator``):
    ``StatusReporter`` -- owns the ``status.json`` of one directory, writes
    it on every state change, and keeps a heartbeat timestamp fresh from a
    daemon thread so a reader can tell a slow run from a dead one.

Reader side (for the GUI):
    ``StatusWatcher``  -- cheap mtime-based polling of one status file.
    ``RunWatcher``     -- follows a ``SimulationIterator`` results tree:
                          the root status plus the currently running job.
    ``watch_run()``    -- blocking generator over ``RunWatcher`` for
                          scripts; GUIs with an event loop should call
                          ``RunWatcher.poll()`` from a timer instead.
    ``is_alive()``     -- heartbeat-based liveness check of a status dict.

Status file schema (a graph's file; the iterator's root file has
``jobs_total``/``jobs_done``/``current_job`` instead of ``actions``)::

    {
      "name": "Radioss_WorkFlow",
      "state": "running",              # pending|running|idle|done|failed
      "pid": 12345,
      "heartbeat_interval": 5.0,
      "started_at": 1751871242.1,      # epoch seconds
      "updated_at": 1751880093.7,
      "actions": {
        "jinja_prep": {"state": "done",    "fraction": null, "message": null},
        "rad_solver": {"state": "running", "fraction": null, "message": null}
      }
    }

The ``fraction`` and ``message`` fields are reserved for solver actions
reporting percent-complete (parsed from their stdout files); they stay
``null`` until that is implemented.
"""

import json
import os
import threading
import time
from pathlib import Path

from simnexus.args import STATUS_PATH

import logging
logger = logging.getLogger(__name__)


HEARTBEAT_INTERVAL = 5.0

# suffix of the per-action sidecar files written by forked child processes
# (asynch actions); the owning process merges them into status.json
SIDECAR_SUFFIX = '.progress.json'

# A directory has one owning reporter per process: a graph nested inside
# another graph runs in the same directory and must not clobber the owner's
# file. The nested graph's reporter simply becomes a no-op; the nested graph
# still shows up as a single action in the owner's file.
_owned_paths = set()
_owned_lock = threading.Lock()


def _write_json_atomic( path, data ):
    """Write data as JSON such that a concurrent reader never sees a
    partial file: write to a sibling temp file, then os.replace (atomic
    on POSIX)."""
    tmp = path.with_name( path.name + '.tmp' )
    with open( tmp, 'w' ) as f:
        json.dump( data, f, indent=1 )
    os.replace( tmp, path )


class StatusReporter:
    """
    Writes the ``status.json`` of one directory.

    Used by ``DirectedGraph.solve`` (per-action states, in the run
    directory) and ``SimulationIterator.solve`` (job counts, at the results
    root). A write happens on every state change; between changes a daemon
    thread rewrites the file every ``heartbeat_interval`` seconds so
    ``updated_at`` stays fresh while the process is alive.

    Reporting must never break a workflow: write errors are logged and
    swallowed, and a reporter for a directory that is already owned by
    another reporter in this process silently becomes a no-op.

    **Fork safety (asynch actions).** An asynch action runs ``solve()`` in
    a forked child process holding a copy of this reporter. A child never
    touches ``status.json`` (two processes rewriting one file would race)
    and never uses the inherited lock (which may have been copied in a
    locked state): ``action_state`` detects the pid change and writes the
    single entry to a per-action sidecar file
    (``.<action>.progress.json``) instead. The owning process folds
    sidecars into ``status.json`` on every write and every heartbeat, so
    child fractions surface at heartbeat cadence, and deletes them when
    the action reaches a terminal state (or at ``finish``).

    Arguments:
        name (str) : name of the graph/iterator this status describes.
        directory (str|Path) : where ``status.json`` is written. Default
            is the current working directory (resolved immediately, so
            later ``os.chdir`` calls do not move the file).
        heartbeat_interval (float) : seconds between heartbeat writes.
            Default is ``progress.HEARTBEAT_INTERVAL`` (read at call time).
    """

    def __init__( self, name, directory='.', heartbeat_interval=None ):
        if heartbeat_interval is None:
            heartbeat_interval = HEARTBEAT_INTERVAL
        self.path = Path( directory ).resolve() / STATUS_PATH
        self.heartbeat_interval = heartbeat_interval
        self._owner_pid = os.getpid()
        self._lock = threading.Lock()
        self._hb_thread = None
        self._hb_stop = threading.Event()

        with _owned_lock:
            if self.path in _owned_paths:
                self._active = False
            else:
                _owned_paths.add( self.path )
                self._active = True

        self._own_actions = set()   # actions registered via start()

        now = time.time()
        self._status = {
            'name': name,
            'state': 'pending',
            'pid': os.getpid(),
            'heartbeat_interval': heartbeat_interval,
            'started_at': now,
            'updated_at': now,
            'actions': {},
        }

    @property
    def active( self ):
        """False when another reporter in this process owns the directory
        (all reporting methods are then no-ops)."""
        return self._active

    def start( self, actions=None, **fields ):
        """Mark the run as started and begin the heartbeat.

        Arguments:
            actions (list) : names of the actions to report on; all start
                in state 'pending'. Omit for an iterator-level status.
            fields : extra top-level fields (e.g. jobs_total=48).
        """
        if not self._active: return
        if os.getpid() != self._owner_pid: return
        with self._lock:
            self._status['state'] = 'running'
            self._status['started_at'] = time.time()
            if actions is not None:
                self._own_actions = set( actions )
                self._status['actions'] = {
                    a: { 'state': 'pending', 'fraction': None, 'message': None }
                    for a in actions }
            self._status.update( fields )
            self._write()
        self._hb_stop.clear()
        self._hb_thread = threading.Thread( target=self._heartbeat, daemon=True )
        self._hb_thread.start()

    def action_state( self, action, state, fraction=None, message=None ):
        """Set one action's state ('pending'|'running'|'done'|'failed')."""
        if not self._active: return
        if os.getpid() != self._owner_pid:
            # forked child (asynch action): sidecar file, one writer per
            # file, no inherited lock; the owner merges it on its next write
            self._write_sidecar( action, { 'state': state, 'fraction': fraction,
                                           'message': message } )
            return
        with self._lock:
            entry = self._status['actions'].setdefault( action, {} )
            entry['state'] = state
            entry['fraction'] = fraction
            entry['message'] = message
            self._write()

    def update( self, **fields ):
        """Update top-level fields (e.g. state='idle', jobs_done=3)."""
        if not self._active: return
        if os.getpid() != self._owner_pid: return
        with self._lock:
            self._status.update( fields )
            self._write()

    def finish( self, state='done' ):
        """Stop the heartbeat, write the final state and release the
        directory so a later run can own it again."""
        if not self._active: return
        if os.getpid() != self._owner_pid: return
        self._hb_stop.set()
        if self._hb_thread is not None:
            self._hb_thread.join( timeout=2.0 )
            self._hb_thread = None
        with self._lock:
            self._status['state'] = state
            self._write()   # merges any remaining sidecars first
            for part in self.path.parent.glob( '.*' + SIDECAR_SUFFIX ):
                try:
                    part.unlink()
                except OSError:
                    pass
        with _owned_lock:
            _owned_paths.discard( self.path )
        self._active = False

    def _heartbeat( self ):
        while not self._hb_stop.wait( self.heartbeat_interval ):
            with self._lock:
                if not self._write():
                    break   # directory is gone; stop quietly

    def _write_sidecar( self, action, entry ):
        """Write one action's entry to its sidecar file (called in a forked
        child process). Atomic; no lock needed -- one writer per file."""
        part = self.path.parent / f'.{action}{SIDECAR_SUFFIX}'
        data = dict( entry )
        data['action'] = action
        data['updated_at'] = time.time()
        try:
            _write_json_atomic( part, data )
        except OSError as err:
            logger.warning( f'Could not write progress sidecar {part}: {err}' )

    def _merge_sidecars( self ):
        """Fold child-process sidecar files into the actions dict. Caller
        holds self._lock. For actions this reporter tracks, the owner keeps
        authority over the *state* and takes only fraction/message while
        the action is running; a sidecar for a terminal action is deleted.
        Unknown actions (from a graph nested inside an asynch action) are
        adopted wholesale, state included."""
        try:
            parts = list( self.path.parent.glob( '.*' + SIDECAR_SUFFIX ) )
        except OSError:
            return
        for part in parts:
            try:
                data = json.loads( part.read_text() )
                aname = data['action']
            except ( OSError, ValueError, KeyError ):
                continue
            entry = self._status['actions'].get( aname )
            if aname not in self._own_actions:
                # action of a graph nested inside an asynch action: this
                # reporter never sets its state, so the sidecar is
                # authoritative (state included)
                self._status['actions'][aname] = {
                    'state': data.get( 'state', 'running' ),
                    'fraction': data.get( 'fraction' ),
                    'message': data.get( 'message' ) }
            elif entry is not None and entry.get( 'state' ) == 'running':
                entry['fraction'] = data.get( 'fraction' )
                entry['message'] = data.get( 'message' )
            else:
                try:
                    part.unlink()
                except OSError:
                    pass

    def _write( self ):
        """Write the status file. Caller holds self._lock. Returns False on
        failure -- reporting must never break the workflow."""
        self._merge_sidecars()
        self._status['updated_at'] = time.time()
        try:
            _write_json_atomic( self.path, self._status )
            return True
        except OSError as err:
            logger.warning( f'Could not write status file {self.path}: {err}' )
            return False


class FileProgressTail:
    """
    Daemon thread reporting a solver's percent-complete while it runs.

    Solvers print the current simulation time to their (redirected) stdout
    file, and the termination time is known from the input deck. This
    thread polls the tail of that file every ``interval`` seconds, extracts
    the latest time with ``parse_time`` (see
    ``simnexus.util.solver_progress``), and reports
    ``(time - t_start) / (t_end - t_start)`` as the action's ``fraction``.

    Start it right before the blocking ``subprocess.run`` and stop it in a
    ``finally`` (so no 'running' write can land after the graph marks the
    action done)::

        tail = FileProgressTail( self._progress_reporter, self.name,
                                 'run_file.stdout', dyna_run_time, t_end )
        tail.start()
        try:
            subprocess.run( ... )
        finally:
            tail.stop()

    ``start()`` is a no-op when the reporter is missing/inactive or the
    termination time is unknown -- progress reporting must never break a
    solver run, so parse errors are swallowed too.

    Arguments:
        reporter (StatusReporter) : where to report; may be None.
        action_name (str) : the action entry to update.
        path (str|Path) : the solver output file to poll.
        parse_time (callable) : ``text -> float | None``, latest sim time.
        t_end (float) : termination time from the deck; None disables.
        t_start (float) : start time (OpenFOAM restarts), default 0.
        interval (float) : polling period in seconds.
        tail_bytes (int) : how much of the file end to read per poll.
    """

    def __init__( self, reporter, action_name, path, parse_time, t_end,
                  t_start=0.0, interval=2.0, tail_bytes=65536 ):
        self.reporter = reporter
        self.action_name = action_name
        self.path = Path( path )
        self.parse_time = parse_time
        self.t_end = t_end
        self.t_start = t_start
        self.interval = interval
        self.tail_bytes = tail_bytes
        self._thread = None
        self._stop = threading.Event()
        self._last_fraction = None

    def start( self ):
        if self.reporter is None or not self.reporter.active:
            return
        if self.t_end is None or self.t_end <= self.t_start:
            return
        self._stop.clear()
        self._thread = threading.Thread( target=self._loop, daemon=True )
        self._thread.start()

    def stop( self ):
        """Stop polling and wait for the thread, so no further write can
        race with the action's final 'done'/'failed' state."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join( timeout=self.interval + 2.0 )
            self._thread = None

    def _loop( self ):
        while not self._stop.wait( self.interval ):
            self._report_once()

    def _read_tail( self ):
        with open( self.path, 'rb' ) as f:
            f.seek( 0, os.SEEK_END )
            size = f.tell()
            f.seek( max( 0, size - self.tail_bytes ) )
            return f.read().decode( errors='replace' )

    def _report_once( self ):
        try:
            t = self.parse_time( self._read_tail() )
        except OSError:
            return  # file not written yet
        except Exception as err:
            logger.warning( f'Progress parsing failed for {self.path}: {err}' )
            return
        if t is None:
            return
        fraction = ( t - self.t_start ) / ( self.t_end - self.t_start )
        fraction = min( max( fraction, 0.0 ), 1.0 )
        if self._last_fraction is not None and abs( fraction - self._last_fraction ) < 1e-3:
            return
        self._last_fraction = fraction
        self.reporter.action_state( self.action_name, 'running',
                                    fraction=fraction,
                                    message=f'time {t:g} of {self.t_end:g}' )


def is_alive( status, grace=3.0 ):
    """
    True if the process that wrote this status dict appears alive: the file
    was updated within ``grace * heartbeat_interval`` seconds. Use it to
    distinguish a slow run from a dead one; a 'done'/'failed' state is
    final regardless of the heartbeat.
    """
    if not status:
        return False
    hb = status.get( 'heartbeat_interval', HEARTBEAT_INTERVAL )
    return ( time.time() - status.get( 'updated_at', 0.0 ) ) < grace * hb


class StatusWatcher:
    """
    Cheap polling reader of one status file, for a consumer in another
    process. ``poll()`` stats the file and re-reads it only when the mtime
    changed; a missing or (transiently) unparsable file is 'no news', never
    an error. The last successfully parsed status stays available as
    ``.last``.
    """

    def __init__( self, path ):
        self.path = Path( path )
        self.last = None
        self._signature = None

    def poll( self ):
        """Return the parsed status dict if it changed since the last call,
        else None."""
        try:
            st = self.path.stat()
            # mtime alone is not enough: filesystem timestamps have coarse
            # granularity (a kernel tick), so rapid successive writes can
            # share an mtime. os.replace gives the file a new inode on every
            # atomic write, so the inode reliably discriminates.
            signature = ( st.st_mtime_ns, st.st_ino, st.st_size )
            if signature == self._signature:
                return None
            self._signature = signature
            self.last = json.loads( self.path.read_text() )
            return self.last
        except ( FileNotFoundError, json.JSONDecodeError ):
            return None


class RunWatcher:
    """
    Follows a ``SimulationIterator`` results tree: the root ``status.json``
    (job counts) plus the ``status.json`` of the job it points at via
    'current_job'. ``poll()`` is non-blocking -- drive it from a GUI timer.
    """

    def __init__( self, results_root ):
        self.results_root = Path( results_root )
        self._root_watcher = StatusWatcher( self.results_root / STATUS_PATH )
        self._job_watcher = None
        self._job_name = None

    def poll( self ):
        """Return a ``{'root':..., 'job_name':..., 'job':...}`` snapshot if
        anything changed since the last call, else None."""
        changed = self._root_watcher.poll() is not None
        root = self._root_watcher.last

        job_name = root.get( 'current_job' ) if root else None
        if job_name != self._job_name:
            self._job_name = job_name
            self._job_watcher = StatusWatcher(
                self.results_root / job_name / STATUS_PATH ) if job_name else None
            changed = True
        if self._job_watcher is not None and self._job_watcher.poll() is not None:
            changed = True

        if not changed:
            return None
        return { 'root': root,
                 'job_name': self._job_name,
                 'job': self._job_watcher.last if self._job_watcher else None }


def watch_run( results_root, interval=1.0 ):
    """
    Blocking generator yielding ``RunWatcher`` snapshots whenever something
    changed. Convenient for scripts and terminals::

        for snap in watch_run('Radioss_WorkFlow'):
            print(format_status(snap))

    A GUI with an event loop should use ``RunWatcher.poll()`` directly.
    """
    watcher = RunWatcher( results_root )
    while True:
        snap = watcher.poll()
        if snap is not None:
            yield snap
        time.sleep( interval )


def format_status( snapshot ):
    """
    Render a status dict (from ``StatusWatcher``) or a run snapshot (from
    ``RunWatcher``) as short human-readable text.
    """
    if snapshot is None:
        return '(no status)'
    if 'root' in snapshot and 'job' in snapshot:       # RunWatcher snapshot
        root = snapshot['root'] or {}
        total = root.get( 'jobs_total' )
        total = '?' if total is None else total
        lines = [ f"{root.get('name','?')}: {root.get('state','?')}, "
                  f"job {root.get('jobs_done', '?')} of {total}"
                  f"{'' if is_alive(root) else '   (no heartbeat)'}" ]
        if snapshot['job'] is not None:
            job = format_status( snapshot['job'] )
            lines += [ '  ' + l for l in job.splitlines() ]
        return '\n'.join( lines )

    lines = [ f"{snapshot.get('name','?')}: {snapshot.get('state','?')}"
              f"{'' if is_alive(snapshot) else '   (no heartbeat)'}" ]
    for aname, a in snapshot.get( 'actions', {} ).items():
        frac = a.get( 'fraction' )
        frac = f" {frac*100:.0f}%" if frac is not None else ''
        msg = a.get( 'message' )
        msg = f"   {msg}" if msg else ''
        lines.append( f"  {aname}: {a.get('state','?')}{frac}{msg}" )
    return '\n'.join( lines )
