import sys, os, shutil
from pathlib import Path
import pytest

from simnexus.graph_actions import WorkFlow, WorkArea
from simnexus.simulation_iterator import SimulationIterator, JobIndex
from simnexus.actions import MathEvaluation
from simnexus.errors import SimNexusError, DataNotFoundError

def test_work_area_custom_path():
    print("Testing WorkArea with custom path...")
    wf = WorkFlow("TestWF")
    wf.add_action(MathEvaluation("calc", "2 * x"))
    
    custom_path = Path("custom_work_area")
    if custom_path.exists():
        shutil.rmtree(custom_path)
        
    wa = WorkArea(wf, work_area_path=str(custom_path))
    params = {'x': 5}
    
    try:
        res = wa.solve(params)
        assert res['calc'] == 10
        assert custom_path.exists()
    finally:
        wa.rm_rundir()

@pytest.mark.parametrize("path_template", [
    "/tmp/simnexus_WA_test",
    "~/tmp/simnexus_WA_test",
    "$HOME/tmp/simnexus_WA_test"
])
def test_simulation_iterator_special_paths(path_template):
    print(f"Testing SimulationIterator with path: {path_template}")
    wf = WorkFlow("TestWF_Special")
    wf.add_action(MathEvaluation("calc", "x + 1"))
    
    # We need to resolve the path for verification in the test
    resolved_path = Path(os.path.expandvars(os.path.expanduser(path_template)))
    
    if resolved_path.exists():
        shutil.rmtree(resolved_path)
        
    sim_iter = SimulationIterator(wf, work_area_path=path_template, clean_start=True)
    
    try:
        # Run iteration
        params = {'x': 100}
        res = sim_iter.solve(params) 
        
        # Verify
        assert res['calc'] == 101
        assert sim_iter.work_area_path == resolved_path
        assert resolved_path.exists()
        assert (resolved_path / "job_0").exists()
        
    finally:
        sim_iter.rm_rundir()
        # Clean up the ~/tmp or $HOME/tmp if we created it
        if resolved_path.exists():
            shutil.rmtree(resolved_path)


# ----------------------------------------------------------------------
# job index: retrieving past results and grouping runs

def _study_iterator( path, **kwargs ):
    """A fresh iterator pointed at the same results directory. Used to
    check that results can be retrieved by code that did not run them."""
    wf = WorkFlow("Study")
    wf.add_action(MathEvaluation("energy", "K * T"))
    return SimulationIterator(wf, work_area_path=str(path), **kwargs)


@pytest.fixture
def study_path(tmp_path):
    return tmp_path / "study"


def test_simulation_iterator_still_importable_from_graph_actions():
    """SimulationIterator moved to its own module; workflows import it
    from graph_actions and must keep working."""
    from simnexus.graph_actions import SimulationIterator as FromGraphActions
    assert FromGraphActions is SimulationIterator


def test_index_records_variables_and_groups(study_path):
    itr = _study_iterator(study_path, groups='baseline')
    itr.collect_for_varrange({'K': [0.2, 0.3], 'T': [75]})

    # a new iterator reads the index written by the run
    reader = _study_iterator(study_path)
    recs = reader.job_index().records
    assert [r['job'] for r in recs] == ['job_0', 'job_1']
    assert recs[0]['variables'] == {'K': 0.2, 'T': 75}
    assert recs[0]['groups'] == ['baseline']
    assert all(r['state'] == 'done' for r in recs)


def test_results_for_returns_stored_outputs(study_path):
    itr = _study_iterator(study_path)
    itr.collect_for_varrange({'K': [0.2, 0.3], 'T': [75]})

    reader = _study_iterator(study_path)
    assert reader.results_for({'K': 0.2, 'T': 75})['energy'] == pytest.approx(15.0)
    # a partial, unambiguous match is accepted
    assert reader.results_for({'K': 0.3})['energy'] == pytest.approx(22.5)
    assert reader.find_job(where={'K': 0.3}).name == 'job_1'

    with pytest.raises(DataNotFoundError):
        reader.results_for({'K': 9.9, 'T': 75})
    # T=75 holds for both jobs: ambiguous rather than silently wrong
    with pytest.raises(DataNotFoundError):
        reader.results_for({'T': 75})


def test_jobs_carry_several_groups_and_can_be_retagged(study_path):
    itr = _study_iterator(study_path, groups='baseline')
    itr.collect_for_varrange({'K': [0.2, 0.3], 'T': [75]})

    reader = _study_iterator(study_path)
    reader.add_groups(['screened', 'converged'], where={'K': 0.2})
    assert reader.groups_of('job_0') == ['baseline', 'screened', 'converged']
    assert reader.group_names() == ['baseline', 'converged', 'screened']

    assert [p.name for p in reader.find_jobs(groups='baseline')] == ['job_0', 'job_1']
    assert [p.name for p in reader.find_jobs(groups='converged')] == ['job_0']
    # any-of versus all-of
    assert len(reader.find_jobs(groups=['converged', 'baseline'])) == 2
    assert len(reader.find_jobs(groups=['converged', 'baseline'],
                                match_all_groups=True)) == 1

    reader.remove_groups('converged', jobs=['job_0'])
    assert reader.find_jobs(groups='converged') == []


def test_collect_reads_a_group_from_disk(study_path):
    itr = _study_iterator(study_path)
    itr.collect_for_varrange({'K': [0.2, 0.3], 'T': [75]}, groups='sweep_a')
    itr2 = _study_iterator(study_path, reuse_existing=True)
    itr2.collect_for_varrange({'K': [0.5], 'T': [75]}, groups='sweep_b')

    reader = _study_iterator(study_path)
    pars, out = reader.collect(groups='sweep_a')
    assert list(pars['K']) == pytest.approx([0.2, 0.3])
    assert out['energy'] == pytest.approx([15.0, 22.5])

    pars, out = reader.collect(groups='sweep_b')
    assert list(pars['K']) == pytest.approx([0.5])
    assert out['energy'] == pytest.approx([37.5])

    with pytest.raises(DataNotFoundError):
        reader.collect(groups='never_used')


def test_reuse_existing_skips_completed_design_points(study_path):
    itr = _study_iterator(study_path, groups='first')
    itr.collect_for_varrange({'K': [0.2], 'T': [75]})

    itr2 = _study_iterator(study_path, reuse_existing=True, groups='second')
    pars, out = itr2.collect_for_varrange({'K': [0.2, 0.5], 'T': [75]})

    assert itr2.reused_jobs == ['job_0']            # K=0.2 came off disk
    assert out['energy'] == pytest.approx([15.0, 37.5])
    # only the new design point created a directory, numbered after job_0
    jobs = sorted(p.name for p in study_path.iterdir()
                  if p.is_dir() and p.name.startswith('job_'))
    assert jobs == ['job_0', 'job_1']
    # the reused job now belongs to both studies
    assert itr2.groups_of('job_0') == ['first', 'second']


def test_existing_results_directory_still_refused_by_default(study_path):
    _study_iterator(study_path).solve({'K': 0.2, 'T': 75})
    with pytest.raises(SimNexusError):
        _study_iterator(study_path).solve({'K': 0.2, 'T': 75})


def test_index_rebuilds_from_job_directories(study_path):
    itr = _study_iterator(study_path)
    itr.collect_for_varrange({'K': [0.2, 0.3], 'T': [75]})

    # an index written before this feature existed / deleted by hand
    (study_path / 'jobs_index.json').unlink()

    reader = _study_iterator(study_path)
    recs = reader.job_index().records
    assert [r['job'] for r in recs] == ['job_0', 'job_1']
    assert recs[1]['variables'] == {'K': 0.3, 'T': 75}
    assert reader.results_for({'K': 0.3, 'T': 75})['energy'] == pytest.approx(22.5)


def test_failed_job_is_not_reused(study_path):
    wf = WorkFlow("Study")
    wf.add_action(MathEvaluation("energy", "K * missing_name"))
    itr = SimulationIterator(wf, work_area_path=str(study_path))
    with pytest.raises(SimNexusError):
        itr.solve({'K': 0.2})

    rec = itr.job_index().find(state=None)[0]
    assert rec['state'] == 'failed'
    assert rec['variables'] == {'K': 0.2}
    # retrieval only offers completed jobs
    assert itr.find_jobs(where={'K': 0.2}) == []
    with pytest.raises(DataNotFoundError):
        itr.results_for({'K': 0.2})


if __name__ == "__main__":
    # If run directly, just run some examples
    pytest.main([__file__])
