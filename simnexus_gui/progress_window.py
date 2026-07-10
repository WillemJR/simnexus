"""
PySide6 widgets for watching simnexus workflow progress.

The two public widgets are designed to be dropped into a larger Qt
application:

* :class:`StatusView` -- a passive renderer of one status dict. It owns no
  timer and does no I/O; call :meth:`StatusView.set_status` from wherever your
  status dicts come from (typically a :class:`simnexus.progress.StatusWatcher`).

* :class:`RunProgressWidget` -- a self-contained watcher: give it a results
  directory and it polls that tree on a ``QTimer`` and keeps a ``StatusView``
  up to date. Embed it as-is, or read it as a worked example of how to wire
  :class:`simnexus.progress.RunWatcher` into an event loop.

All progress data flows through :mod:`simnexus.progress`; this module adds only
the Qt presentation layer.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from simnexus.progress import RunWatcher, is_alive

# How often the widget polls the status files (milliseconds). Polling is cheap:
# StatusWatcher re-reads a file only when its (mtime, inode, size) changes.
DEFAULT_POLL_MS = 500

# state name -> (label text colour, progress-bar chunk colour)
_STATE_COLORS = {
    'pending': ( '#888888', '#b0b0b0' ),
    'running': ( '#1565c0', '#1e88e5' ),
    'idle':    ( '#888888', '#b0b0b0' ),
    'done':    ( '#2e7d32', '#43a047' ),
    'failed':  ( '#c62828', '#e53935' ),
}


def _state_color( state ):
    return _STATE_COLORS.get( state, _STATE_COLORS['pending'] )


class _ActionRow:
    """One action's widgets (name, progress bar, status text) living in a
    shared :class:`QGridLayout`. Kept as an object so rows can be updated in
    place -- rebuilding the layout on every poll would flicker."""

    def __init__( self, grid, row, name ):
        self.name_label = QLabel( name )
        self.name_label.setStyleSheet( 'font-weight: 600;' )

        self.bar = QProgressBar()
        self.bar.setRange( 0, 100 )
        self.bar.setValue( 0 )
        self.bar.setTextVisible( True )
        self.bar.setFixedHeight( 18 )
        self.bar.setSizePolicy( QSizePolicy.Expanding, QSizePolicy.Fixed )

        self.status_label = QLabel()
        self.status_label.setMinimumWidth( 160 )

        grid.addWidget( self.name_label, row, 0 )
        grid.addWidget( self.bar, row, 1 )
        grid.addWidget( self.status_label, row, 2 )

    def update( self, entry ):
        state = entry.get( 'state', 'pending' )
        fraction = entry.get( 'fraction' )
        message = entry.get( 'message' )
        text_color, chunk_color = _state_color( state )

        # Progress bar: an explicit fraction wins; otherwise fall back to the
        # state (done => full, running w/o fraction => busy/indeterminate).
        if fraction is not None:
            self.bar.setRange( 0, 100 )
            self.bar.setValue( int( round( fraction * 100 ) ) )
            self.bar.setFormat( '%p%' )
        elif state == 'done':
            self.bar.setRange( 0, 100 )
            self.bar.setValue( 100 )
            self.bar.setFormat( 'done' )
        elif state == 'running':
            self.bar.setRange( 0, 0 )          # marquee / indeterminate
            self.bar.setFormat( '' )
        elif state == 'failed':
            self.bar.setRange( 0, 100 )
            self.bar.setValue( 100 )
            self.bar.setFormat( 'failed' )
        else:                                  # pending / idle
            self.bar.setRange( 0, 100 )
            self.bar.setValue( 0 )
            self.bar.setFormat( state )

        self.bar.setStyleSheet(
            'QProgressBar { border: 1px solid palette(mid); border-radius: 3px; '
            'text-align: center; }'
            f'QProgressBar::chunk {{ background-color: {chunk_color}; }}' )

        label = state if not message else f'{state} — {message}'
        self.status_label.setText( label )
        self.status_label.setStyleSheet( f'color: {text_color};' )

    def remove( self, grid ):
        for w in ( self.name_label, self.bar, self.status_label ):
            grid.removeWidget( w )
            w.deleteLater()


class StatusView( QWidget ):
    """
    Passive renderer of a single status dict (as produced by
    :class:`simnexus.progress.StatusReporter` / read by
    :class:`simnexus.progress.StatusWatcher`).

    Shows the run name, its state, a liveness ('no heartbeat') warning, and one
    progress row per action. It performs no I/O and owns no timer; drive it by
    calling :meth:`set_status`. Rows are created lazily and reused, so repeated
    updates do not flicker or leak widgets.
    """

    def __init__( self, parent=None ):
        super().__init__( parent )
        self._rows = {}          # action name -> _ActionRow

        outer = QVBoxLayout( self )
        outer.setContentsMargins( 0, 0, 0, 0 )

        header = QHBoxLayout()
        self._name_label = QLabel( '(no status)' )
        self._name_label.setStyleSheet( 'font-size: 14px; font-weight: 700;' )
        self._state_label = QLabel()
        self._alive_label = QLabel()
        self._alive_label.setStyleSheet( 'color: #c62828; font-style: italic;' )
        header.addWidget( self._name_label )
        header.addWidget( self._state_label )
        header.addStretch( 1 )
        header.addWidget( self._alive_label )
        outer.addLayout( header )

        self._grid = QGridLayout()
        self._grid.setColumnStretch( 1, 1 )
        self._grid.setHorizontalSpacing( 12 )
        self._grid.setVerticalSpacing( 6 )
        outer.addLayout( self._grid )
        outer.addStretch( 1 )

    def set_status( self, status ):
        """Render ``status`` (a dict from ``StatusWatcher``), or clear the view
        when it is ``None``."""
        if not status:
            self._name_label.setText( '(no status)' )
            self._state_label.clear()
            self._alive_label.clear()
            self._clear_rows()
            return

        name = status.get( 'name', '?' )
        state = status.get( 'state', '?' )
        self._name_label.setText( name )
        text_color, _ = _state_color( state )
        self._state_label.setText( f'— {state}' )
        self._state_label.setStyleSheet( f'color: {text_color}; font-weight: 600;' )

        # A terminal run needs no heartbeat; only warn for a run that claims to
        # be active but has gone quiet.
        if state in ( 'running', 'idle', 'pending' ) and not is_alive( status ):
            self._alive_label.setText( 'no heartbeat' )
        else:
            self._alive_label.clear()

        self._sync_rows( status.get( 'actions', {} ) )

    def _sync_rows( self, actions ):
        # Drop rows for actions that vanished (unusual, but keeps us honest).
        for stale in [ n for n in self._rows if n not in actions ]:
            self._rows.pop( stale ).remove( self._grid )
        for name, entry in actions.items():
            row = self._rows.get( name )
            if row is None:
                row = _ActionRow( self._grid, len( self._rows ), name )
                self._rows[ name ] = row
            row.update( entry )

    def _clear_rows( self ):
        for row in self._rows.values():
            row.remove( self._grid )
        self._rows.clear()


class RunProgressWidget( QWidget ):
    """
    Self-contained progress window for one workflow results tree.

    Point it at:

    * a :class:`~simnexus.SimulationIterator` results root -- it shows the job
      counter (``job k of n``) and follows the currently running job's actions,
      or
    * any directory holding a graph's ``status.json`` -- it shows that graph's
      actions directly.

    It owns a :class:`QTimer` and a :class:`simnexus.progress.RunWatcher`, so it
    is a genuine drop-in: construct it, add it to a layout, done. Polling starts
    automatically and pauses/resumes with :meth:`stop` / :meth:`start`. The
    :attr:`state_changed` signal fires with the root state string whenever it
    changes, so a host window can react (e.g. update a status bar).

    Arguments:
        results_root (str|Path) : directory to watch. May be set later or
            changed at runtime via :meth:`set_results_root`.
        poll_ms (int) : polling period in milliseconds.
    """

    state_changed = Signal( str )

    def __init__( self, results_root=None, poll_ms=DEFAULT_POLL_MS, parent=None ):
        super().__init__( parent )
        self._watcher = None
        self._last_state = None

        outer = QVBoxLayout( self )

        # Summary line: path + iterator job counter (hidden for a plain graph).
        summary = QHBoxLayout()
        self._path_label = QLabel( '(no directory)' )
        self._path_label.setStyleSheet( 'color: palette(mid);' )
        self._jobs_label = QLabel()
        self._jobs_label.setStyleSheet( 'font-weight: 600;' )
        summary.addWidget( self._path_label, 1 )
        summary.addWidget( self._jobs_label )
        outer.addLayout( summary )

        line = QFrame()
        line.setFrameShape( QFrame.HLine )
        line.setFrameShadow( QFrame.Sunken )
        outer.addWidget( line )

        # The per-job / per-graph action view, in a scroll area so many actions
        # never blow out the window.
        self._status_view = StatusView()
        scroll = QScrollArea()
        scroll.setWidgetResizable( True )
        scroll.setWidget( self._status_view )
        scroll.setFrameShape( QFrame.NoFrame )
        outer.addWidget( scroll, 1 )

        self._timer = QTimer( self )
        self._timer.setInterval( poll_ms )
        self._timer.timeout.connect( self._tick )

        if results_root is not None:
            self.set_results_root( results_root )

    # -- public control ---------------------------------------------------

    def set_results_root( self, results_root ):
        """Watch a different results directory, resetting the view."""
        root = Path( results_root )
        self._watcher = RunWatcher( root )
        self._last_state = None
        self._path_label.setText( str( root ) )
        self._jobs_label.clear()
        self._status_view.set_status( None )
        self._tick()            # paint immediately, don't wait a full period
        self.start()

    def start( self ):
        """(Re)start polling."""
        if self._watcher is not None and not self._timer.isActive():
            self._timer.start()

    def stop( self ):
        """Pause polling (e.g. when the window is hidden)."""
        self._timer.stop()

    def refresh( self ):
        """Force an immediate poll and repaint."""
        self._tick()

    # -- internals --------------------------------------------------------

    def _tick( self ):
        if self._watcher is None:
            return
        snap = self._watcher.poll()
        if snap is None:
            return          # nothing changed since last poll
        self._render( snap )

    def _render( self, snap ):
        root = snap.get( 'root' ) or {}
        is_iterator = ( 'jobs_total' in root ) or ( 'current_job' in root )

        if is_iterator:
            total = root.get( 'jobs_total' )
            total = '?' if total is None else total
            done = root.get( 'jobs_done', '?' )
            state = root.get( 'state', '?' )
            self._jobs_label.setText( f'{root.get("name", "run")}: {state}'
                                      f'   —   job {done} of {total}' )
            # Show the current job's actions (may be None between jobs).
            self._status_view.set_status( snap.get( 'job' ) )
        else:
            # Plain graph directory: the root file *is* the action status.
            self._jobs_label.clear()
            self._status_view.set_status( root or None )

        state = root.get( 'state' )
        if state != self._last_state:
            self._last_state = state
            if state is not None:
                self.state_changed.emit( state )


class MainWindow( QMainWindow ):
    """Minimal standalone shell around :class:`RunProgressWidget`: a directory
    picker, a status bar and the widget. Kept deliberately small to serve as a
    copy-paste starting point for a real application."""

    def __init__( self, results_root=None ):
        super().__init__()
        self.setWindowTitle( 'simnexus — workflow progress' )
        self.resize( 640, 480 )

        central = QWidget()
        layout = QVBoxLayout( central )

        bar = QHBoxLayout()
        open_btn = QPushButton( 'Open results directory…' )
        open_btn.clicked.connect( self._choose_directory )
        bar.addWidget( open_btn )
        bar.addStretch( 1 )
        layout.addLayout( bar )

        self._progress = RunProgressWidget( results_root )
        self._progress.state_changed.connect(
            lambda s: self.statusBar().showMessage( f'state: {s}' ) )
        layout.addWidget( self._progress, 1 )

        self.setCentralWidget( central )
        if results_root is None:
            self.statusBar().showMessage( 'Open a workflow results directory to begin.' )

    def _choose_directory( self ):
        path = QFileDialog.getExistingDirectory( self, 'Select results directory' )
        if path:
            self._progress.set_results_root( path )
            self.statusBar().showMessage( f'watching {path}' )


def main( argv=None ):
    """Entry point for ``python -m simnexus_gui [results_dir]``."""
    import sys
    argv = list( sys.argv if argv is None else argv )
    results_root = argv[1] if len( argv ) > 1 else None

    app = QApplication.instance() or QApplication( argv )
    window = MainWindow( results_root )
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit( main() )
