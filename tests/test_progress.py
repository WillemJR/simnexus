import os

import json
import tempfile
import time
from pathlib import Path

import pytest

from simnexus.actions import WorkAction
from simnexus.args import STATUS_PATH
from simnexus.errors import SimNexusError, AsyncActionError
from simnexus.graph_actions import WorkFlow, DirectedGraph, WorkArea, SimulationIterator
from simnexus import progress


class PlusOne(WorkAction):
    def solve(self, val_dict=None):
        return (val_dict.get(self.name, 0) if val_dict else 0) + 1


class Failing(WorkAction):
    def solve(self, val_dict=None):
        raise RuntimeError('boom')


class _in_tmp_dir:
    """Run a test body in a fresh temporary directory."""
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root = Path.cwd()
        os.chdir(self._tmp.name)
        return Path(self._tmp.name)
    def __exit__(self, *exc):
        os.chdir(self._root)
        self._tmp.cleanup()


def _read_status(path=STATUS_PATH):
    return json.loads(Path(path).read_text())


def test_workflow_writes_status():
    with _in_tmp_dir():
        wf = WorkFlow('WF', actions=[PlusOne('a'), PlusOne('b')])
        wf.solve({})

        st = _read_status()
        assert st['name'] == 'WF'
        assert st['state'] == 'done'
        assert st['pid'] == os.getpid()
        assert st['actions']['a']['state'] == 'done'
        assert st['actions']['b']['state'] == 'done'
        assert progress.is_alive(st)   # just written


def test_failed_action_is_reported():
    with _in_tmp_dir():
        wf = WorkFlow('WF', actions=[PlusOne('a'), Failing('bad'), PlusOne('c')])
        with pytest.raises(RuntimeError):
            wf.solve({})

        st = _read_status()
        assert st['state'] == 'failed'
        assert st['actions']['a']['state'] == 'done'
        assert st['actions']['bad']['state'] == 'failed'
        assert st['actions']['c']['state'] == 'pending'


def test_nested_graph_does_not_clobber_owner():
    with _in_tmp_dir():
        inner = WorkFlow('Inner', actions=[PlusOne('deep')])
        outer = WorkFlow('Outer', actions=[PlusOne('a'), inner])
        outer.solve({})

        # one file, owned by the outer graph; the inner graph reports its
        # own actions through the owner's reporter (names stay unique)
        st = _read_status()
        assert st['name'] == 'Outer'
        assert st['actions']['Inner']['state'] == 'done'
        assert st['actions']['deep']['state'] == 'done'


def test_workarea_status_in_work_area_dir():
    with _in_tmp_dir():
        wf = WorkFlow('WFArea', actions=[PlusOne('a')])
        area = WorkArea(wf)
        area.solve({})
        st = _read_status(Path('WFArea') / STATUS_PATH)
        assert st['name'] == 'WFArea' and st['state'] == 'done'


def test_iterator_root_and_job_status():
    with _in_tmp_dir():
        wf = WorkFlow('It', actions=[PlusOne('a')])
        itr = SimulationIterator(wf)
        itr.solve({})
        itr.solve({})

        root = _read_status(Path('It') / STATUS_PATH)
        assert root['name'] == 'It_Iter'
        assert root['state'] == 'idle'
        assert root['jobs_done'] == 2
        assert root['jobs_total'] is None   # bare solve(): total unknown
        assert root['current_job'] == 'job_1'

        for job in ('job_0', 'job_1'):
            st = _read_status(Path('It') / job / STATUS_PATH)
            assert st['state'] == 'done'
            assert st['actions']['a']['state'] == 'done'


def test_iterator_collect_sets_totals_and_done():
    with _in_tmp_dir():
        wf = WorkFlow('Coll', actions=[PlusOne('a')])
        itr = SimulationIterator(wf)
        itr.collect_for_varrange({'V1': [1, 2, 3]})

        root = _read_status(Path('Coll') / STATUS_PATH)
        assert root['jobs_total'] == 3
        assert root['jobs_done'] == 3
        assert root['state'] == 'done'


def test_status_watcher_polls_changes():
    with _in_tmp_dir() as tmp:
        watcher = progress.StatusWatcher(Path(tmp) / STATUS_PATH)
        assert watcher.poll() is None   # no file yet: no news, no error

        rep = progress.StatusReporter('W', directory=tmp)
        rep.start(actions=['a'])
        st = watcher.poll()
        assert st is not None and st['state'] == 'running'
        assert watcher.poll() is None   # unchanged

        time.sleep(0.02)                # ensure a new mtime
        rep.action_state('a', 'done')
        rep.finish('done')
        st = watcher.poll()
        assert st is not None and st['state'] == 'done'
        assert watcher.last is st


def test_run_watcher_follows_current_job():
    with _in_tmp_dir() as tmp:
        wf = WorkFlow('RW', actions=[PlusOne('a')])
        itr = SimulationIterator(wf)
        rw = progress.RunWatcher(Path(tmp) / 'RW')
        assert rw.poll() is None        # nothing yet

        itr.solve({})
        snap = rw.poll()
        assert snap is not None
        assert snap['root']['jobs_done'] == 1
        assert snap['job_name'] == 'job_0'
        assert snap['job']['actions']['a']['state'] == 'done'
        assert rw.poll() is None        # unchanged

        itr.solve({})
        snap = rw.poll()
        assert snap['job_name'] == 'job_1'
        assert snap['job']['state'] == 'done'

        assert 'job 2 of ?' in progress.format_status(snap)


def test_run_watcher_follows_several_jobs_at_once():
    with _in_tmp_dir() as tmp:
        root = Path(tmp) / 'Multi'
        (root / 'job_0').mkdir(parents=True)
        (root / 'job_1').mkdir(parents=True)
        rw = progress.RunWatcher(root)

        rep = progress.StatusReporter('M_Iter', directory=root)
        rep.start(actions=None, jobs_total=4, jobs_done=0,
                  current_job='job_1', current_jobs=['job_0', 'job_1'])
        job0 = progress.StatusReporter('G', directory=root / 'job_0')
        job1 = progress.StatusReporter('G', directory=root / 'job_1')
        job0.start(actions=['a'])
        job1.start(actions=['a'])
        job0.action_state('a', 'running', fraction=0.5, message='time 5 of 10')

        snap = rw.poll()
        assert list(snap['jobs']) == ['job_0', 'job_1']
        assert snap['job_name'] == 'job_0'          # first of them
        assert snap['job'] is snap['jobs']['job_0']

        text = progress.format_status(snap)
        assert 'job 0 of 4' in text
        assert 'job_0 - G: running' in text         # named, so they are told apart
        assert 'job_1 - G: running' in text
        assert '50%   time 5 of 10' in text

        time.sleep(0.02)                            # ensure a new mtime
        job0.finish('done')
        rep.update(jobs_done=1, current_jobs=['job_1'])
        snap = rw.poll()
        assert list(snap['jobs']) == ['job_1']      # job_0 is no longer followed
        assert 'job_0' not in progress.format_status(snap)

        job1.finish('done')
        rep.finish('done')


def test_job_fraction_averages_over_the_actions():
    assert progress.job_fraction(None) == (None, None)
    assert progress.job_fraction({'actions': {}}) == (None, None)

    status = {'actions': {
        'prep':   {'state': 'done'},
        'solver': {'state': 'running', 'fraction': 0.5, 'message': 'time 5 of 10'},
        'read':   {'state': 'pending'}}}
    fraction, message = progress.job_fraction(status)
    assert fraction == pytest.approx(1.5 / 3)      # one done, one half done
    # what it is busy with, and how far that action itself has got -- the
    # fraction above is the job's, which is the smaller number
    assert message == 'solver: time 5 of 10 (50%)'

    # a running action without a fraction still names itself
    status['actions']['solver'] = {'state': 'running'}
    fraction, message = progress.job_fraction(status)
    assert fraction == pytest.approx(1 / 3)
    assert message == 'solver'


def test_is_alive_detects_stale_heartbeat():
    now = time.time()
    assert progress.is_alive({'heartbeat_interval': 5.0, 'updated_at': now})
    assert not progress.is_alive({'heartbeat_interval': 5.0, 'updated_at': now - 60.0})
    assert not progress.is_alive(None)
    assert not progress.is_alive({})


def test_forked_child_writes_sidecar_and_owner_merges():
    import multiprocessing
    with _in_tmp_dir() as tmp:
        rep = progress.StatusReporter('G', directory=tmp)
        rep.start(actions=['solver'])
        rep.action_state('solver', 'running')

        # a forked child (as in an asynch action) reports a fraction
        def child():
            rep.action_state('solver', 'running', fraction=0.4, message='time 0.8 of 2')
        p = multiprocessing.get_context('fork').Process(target=child)
        p.start(); p.join()

        # the child wrote a sidecar, not the status file
        sidecar = Path(tmp) / f'.solver{progress.SIDECAR_SUFFIX}'
        assert sidecar.exists()
        assert _read_status()['actions']['solver']['fraction'] is None

        # the owner's next write folds it in
        rep.update()
        entry = _read_status()['actions']['solver']
        assert entry['fraction'] == 0.4
        assert entry['message'] == 'time 0.8 of 2'
        assert entry['state'] == 'running'   # owner keeps state authority

        # terminal state: sidecar is dropped, fraction cleared by the sweep
        rep.action_state('solver', 'done')
        rep.update()
        assert not sidecar.exists()
        assert _read_status()['actions']['solver']['state'] == 'done'
        rep.finish('done')
        assert not list(Path(tmp).glob('.*' + progress.SIDECAR_SUFFIX))


def test_asynch_graph_reports_fractions():
    """End-to-end: an asynch graph's action runs in a forked child; its
    FileProgressTail fractions must reach status.json via sidecars."""
    import threading
    from simnexus.progress import FileProgressTail
    from simnexus.util import solver_progress

    class AsyncFakeSolver(WorkAction):
        def solve(self, val_dict=None):
            log = Path(f'{self.name}.stdout')
            tail = FileProgressTail(self._progress_reporter, self.name, log,
                                    solver_progress.radioss_run_time,
                                    t_end=2.0, interval=0.05)
            tail.start()
            try:
                for t in ('0.0000E+00', '1.0000E+00', '2.0000E+00'):
                    with open(log, 'a') as f:
                        f.write(f' NC= 100 T= {t} DT= 1E-06\n')
                    time.sleep(0.3)
            finally:
                tail.stop()
            return 1.0

    saved = progress.HEARTBEAT_INTERVAL
    progress.HEARTBEAT_INTERVAL = 0.1   # merge sidecars quickly for the test
    try:
        with _in_tmp_dir() as tmp:
            g = DirectedGraph('AG', asynch=True)
            g.add_action(AsyncFakeSolver('solver'))

            status = Path(tmp) / STATUS_PATH
            seen = []
            worker = threading.Thread(target=g.solve, args=({},))
            worker.start()
            while worker.is_alive():
                try:
                    entry = json.loads(status.read_text())['actions']['solver']
                    if entry.get('fraction') is not None:
                        seen.append(entry['fraction'])
                except (FileNotFoundError, json.JSONDecodeError, KeyError):
                    pass
                time.sleep(0.05)
            worker.join()

            assert seen, 'no fractions from the asynch child observed'
            assert max(seen) > 0.4
            st = json.loads(status.read_text())
            assert st['state'] == 'done'
            assert st['actions']['solver']['state'] == 'done'
            assert not list(Path(tmp).glob('.*' + progress.SIDECAR_SUFFIX))
    finally:
        progress.HEARTBEAT_INTERVAL = saved


class SlowPlusOne(WorkAction):
    def solve(self, val_dict=None):
        time.sleep(3.0)
        return 1


class HardCrash(WorkAction):
    def solve(self, val_dict=None):
        os._exit(9)   # simulates a segfault/oom-kill: no exception raised


def test_asynch_failed_child_reports_failed():
    with _in_tmp_dir():
        g = DirectedGraph('AF', asynch=True)
        g.add_action(Failing('bad'))
        g.add_action(SlowPlusOne('slow_sibling'))

        with pytest.raises(AsyncActionError) as excinfo:
            g.solve({})
        # the child's exception type, message and traceback are surfaced
        assert 'bad' in str(excinfo.value)
        assert 'RuntimeError: boom' in str(excinfo.value)

        st = _read_status()
        assert st['state'] == 'failed'
        assert st['actions']['bad']['state'] == 'failed'
        assert 'RuntimeError' in st['actions']['bad']['message']
        # the still-running sibling was terminated and marked failed
        assert st['actions']['slow_sibling']['state'] == 'failed'
        assert 'terminated' in st['actions']['slow_sibling']['message']


def test_asynch_crashed_child_reports_failed():
    with _in_tmp_dir():
        g = DirectedGraph('AC', asynch=True)
        g.add_action(HardCrash('crasher'))

        with pytest.raises(AsyncActionError) as excinfo:
            g.solve({})
        assert 'exited with code 9' in str(excinfo.value)
        st = _read_status()
        assert st['state'] == 'failed'
        assert st['actions']['crasher']['state'] == 'failed'


def test_asynch_success_still_works():
    with _in_tmp_dir():
        g = DirectedGraph('AS', asynch=True)
        a = g.add_action(PlusOne('a'))
        b = g.add_action(PlusOne('b'))
        g.add_action(PlusOne('c'), parents=[a, b])
        ret = g.solve({})
        assert ret['c'] == 1
        st = _read_status()
        assert st['state'] == 'done'
        assert all(v['state'] == 'done' for v in st['actions'].values())


def test_atomic_write_leaves_no_temp_file():
    with _in_tmp_dir() as tmp:
        rep = progress.StatusReporter('A', directory=tmp)
        rep.start(actions=['x'])
        rep.finish('done')
        names = [p.name for p in Path(tmp).iterdir()]
        assert STATUS_PATH in names
        assert not any(n.endswith('.tmp') for n in names)


if __name__ == '__main__':
    test_workflow_writes_status()
    test_failed_action_is_reported()
    test_nested_graph_does_not_clobber_owner()
    test_workarea_status_in_work_area_dir()
    test_iterator_root_and_job_status()
    test_iterator_collect_sets_totals_and_done()
    test_status_watcher_polls_changes()
    test_run_watcher_follows_current_job()
    test_is_alive_detects_stale_heartbeat()
    test_atomic_write_leaves_no_temp_file()
    print('all progress tests passed')
