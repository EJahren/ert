import os
from pathlib import Path
from textwrap import dedent

from ert._c_wrappers.enkf import ResConfig, EnkfFs
from ert._c_wrappers.enkf.enkf_main import EnKFMain
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def enkf_main(tmp_path):
    (tmp_path / "test.ert").write_text("NUM_REALIZATIONS 1\nJOBNAME name%d")
    os.chdir(tmp_path)
    yield EnKFMain(ResConfig("test.ert"))


def test_load_from_forward_model(enkf_main):

    fs = MagicMock()
    realizations = [True] * 10
    iteration = 0
    num_loaded = 8

    enkf_main.create_ensemble_experiment_run_context = MagicMock()
    enkf_main.loadFromRunContext = MagicMock()
    enkf_main.loadFromRunContext.return_value = num_loaded

    assert enkf_main.loadFromForwardModel(realizations, iteration, fs) == num_loaded

    enkf_main.loadFromRunContext.assert_called()


def test_create_ensemble_experiment_run_context(enkf_main):
    fs = MagicMock()

    enkf_main._create_run_context = MagicMock()

    realizations = [True] * 10
    iteration = 0

    enkf_main.create_ensemble_experiment_run_context(
        active_mask=realizations, source_filesystem=fs, iteration=iteration
    )

    enkf_main._create_run_context.assert_called_with(
        iteration=iteration,
        active_mask=realizations,
        source_filesystem=fs,
        target_fs=None,
    )


def test_create_ensemble_smoother_run_context(enkf_main):
    fs = MagicMock()
    fs2 = MagicMock()

    enkf_main._create_run_context = MagicMock()

    realizations = [True] * 10
    iteration = 0

    enkf_main.create_ensemble_smoother_run_context(
        active_mask=realizations,
        source_filesystem=fs,
        target_filesystem=fs2,
        iteration=iteration,
    )

    enkf_main._create_run_context.assert_called_with(
        iteration=iteration,
        active_mask=realizations,
        source_filesystem=fs,
        target_fs=fs2,
    )


def test_create_run_context(monkeypatch, enkf_main):

    iteration = 0
    ensemble_size = 10

    run_context = enkf_main._create_run_context(
        iteration=iteration, active_mask=[True] * ensemble_size
    )
    assert run_context.sim_fs == enkf_main.getCurrentFileSystem()
    assert run_context.target_fs == enkf_main.getCurrentFileSystem()
    assert run_context.mask == [True] * ensemble_size
    assert run_context.paths == [
        f"{Path().absolute()}/simulations/realization{i}" for i in range(ensemble_size)
    ]
    assert run_context.jobnames == [f"name{i}" for i in range(ensemble_size)]

    substitutions = enkf_main.substituter.get_substitutions(1, iteration)
    assert "<RUNPATH>" in substitutions
    assert substitutions["<ECL_BASE>"] == "name1"
    assert substitutions["<ECLBASE>"] == "name1"
    assert substitutions["<ITER>"] == str(iteration)
    assert substitutions["<IENS>"] == "1"


def test_create_set_geo_id(enkf_main):

    iteration = 1
    realization = 2
    geo_id = "geo_id"

    enkf_main.set_geo_id("geo_id", realization, iteration)

    assert (
        enkf_main.substituter.get_substitutions(realization, iteration)["<GEO_ID>"]
        == geo_id
    )


@pytest.mark.usefixtures("use_tmpdir")
def test_that_current_case_file_is_written():
    config_text = dedent(
        """
        NUM_REALIZATIONS 1
        JOBNAME my_case%d
        """
    )
    Path("config.ert").write_text(config_text)
    res_config = ResConfig("config.ert")
    ert = EnKFMain(res_config)
    new_fs = EnkfFs.createFileSystem("new_fs")
    ert.switchFileSystem(new_fs)
    assert (Path("storage") / "current_case").read_text() == "new_fs"
