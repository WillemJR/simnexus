"""Running several jobs of one SimulationIterator at the same time."""

import json
import time

import pytest

from simnexus.actions import MathEvaluation, WorkAction
from simnexus.args import JOBS_INDEX_PATH, STATUS_PATH
from simnexus.errors import AsyncActionError, ParameterError
from simnexus.graph_actions import WorkFlow
from simnexus.simulation_iterator import SimulationIterator


class Sleeper(WorkAction):
    """Takes long enough that jobs overlapping is measurable."""
    DELAY = 0.4

    def solve(self, val_dict=None):
        time.sleep(self.DELAY)
        return val_dict.get('x', 0) if val_dict else 0


class FailsOnThree(WorkAction):
    def solve(self, val_dict=None):
        if val_dict and val_dict.get('x') == 3:
            raise RuntimeError('boom')
        return val_dict.get('x', 0) if val_dict else 0


def _iterator(name, max_workers=1, **kwargs):
    wf = WorkFlow(name, actions=[MathEvaluation('calc', 'x * 10')])
    return SimulationIterator(wf, max_workers=max_workers, **kwargs)


def test_max_workers_must_be_at_least_one():
    with pytest.raises(ParameterError):
        _iterator('Bad', max_workers=0)


def test_parallel_sweep_matches_serial(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    _, serial = _iterator('Serial').collect_for_varrange({'x': [1, 2, 3, 4, 5]})
    _, parallel = _iterator('Parallel', max_workers=3).collect_for_varrange(
        {'x': [1, 2, 3, 4, 5]})

    # same results, in the order the design points were given
    assert serial['calc'] == [10, 20, 30, 40, 50]
    assert parallel['calc'] == serial['calc']
    assert parallel['x'] == serial['x']

    # one job directory per design point, each with its own results
    jobs = sorted((tmp_path / 'Parallel').glob('job_*'))
    assert [j.name for j in jobs] == [f'job_{i}' for i in range(5)]
    for i, job in enumerate(jobs):
        assert json.loads((job / 'iter_variables.json').read_text()) == {'x': i + 1}

    index = json.loads((tmp_path / 'Parallel' / JOBS_INDEX_PATH).read_text())
    assert [r['state'] for r in index['jobs']] == ['done'] * 5


def test_parallel_sweep_runs_jobs_at_the_same_time(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    wf = WorkFlow('Slow', actions=[Sleeper('slow')])
    itr = SimulationIterator(wf, max_workers=4)

    start = time.time()
    itr.collect_for_varrange({'x': [1, 2, 3, 4]})
    elapsed = time.time() - start

    # serially this is 4 * DELAY; four at once is one DELAY plus overhead
    assert elapsed < 3 * Sleeper.DELAY
    assert len(list((tmp_path / 'Slow').glob('job_*'))) == 4


def test_parallel_reports_running_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    wf = WorkFlow('Reported', actions=[Sleeper('slow')])
    itr = SimulationIterator(wf, max_workers=2)
    itr.collect_for_varrange({'x': [1, 2]})

    root = json.loads((tmp_path / 'Reported' / STATUS_PATH).read_text())
    assert root['state'] == 'done'
    assert root['jobs_done'] == 2
    assert root['jobs_total'] == 2
    assert root['current_jobs'] == []          # none left running
    assert root['current_job'] == 'job_1'      # last one started

    for job in ('job_0', 'job_1'):
        st = json.loads((tmp_path / 'Reported' / job / STATUS_PATH).read_text())
        assert st['state'] == 'done'
        assert st['actions']['slow']['state'] == 'done'


def test_failing_job_aborts_the_sweep(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    wf = WorkFlow('Failing', actions=[FailsOnThree('maybe')])
    itr = SimulationIterator(wf, max_workers=2)

    with pytest.raises(AsyncActionError) as excinfo:
        itr.collect_for_varrange({'x': [1, 2, 3, 4]})

    assert 'boom' in str(excinfo.value)         # the child's traceback
    assert 'RuntimeError' in str(excinfo.value)

    index = json.loads((tmp_path / 'Failing' / JOBS_INDEX_PATH).read_text())
    states = {r['job']: r['state'] for r in index['jobs']}
    assert states['job_2'] == 'failed'          # x == 3
    assert 'running' not in states.values()     # nothing left dangling

    root = json.loads((tmp_path / 'Failing' / STATUS_PATH).read_text())
    assert root['state'] == 'failed'


def test_progress_bar_reports_the_jobs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    itr = _iterator('Bar', max_workers=2)
    itr.solve_parallel([{'x': 1}, {'x': 2}, {'x': 3}], progress_bar=True)

    err = capsys.readouterr().err
    assert 'Bar_Iter' in err        # the batch bar is labelled with the iterator
    assert '3/3' in err             # and ends on the last job
    assert '  job_0' in err         # each running job gets a bar of its own
    assert '  job_2' in err


def test_progress_bar_can_be_switched_off(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    itr = _iterator('Quiet', max_workers=2)
    itr.solve_parallel([{'x': 1}, {'x': 2}], progress_bar=False)
    assert capsys.readouterr().err == ''

    # the default is quiet too when stderr is not a terminal, as here
    itr.solve_parallel([{'x': 3}])
    assert capsys.readouterr().err == ''


def test_parallel_sweep_reuses_existing_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    _, first = _iterator('Reuse', max_workers=2).collect_for_varrange({'x': [1, 2, 3]})

    itr = _iterator('Reuse', max_workers=2, reuse_existing=True)
    _, again = itr.collect_for_varrange({'x': [1, 2, 3]})

    assert again['calc'] == first['calc']
    assert len(itr.reused_jobs) == 3
    # nothing was run again, so no new job directories
    assert len(list((tmp_path / 'Reuse').glob('job_*'))) == 3
