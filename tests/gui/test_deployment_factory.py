from __future__ import annotations

from pathlib import Path

import pytest

from GoBreeder.gui.models.deployment_factory import (
    DeploymentError,
    DeploymentFactory,
    _REFRESHABLE_CODE_FILES,
)
from GoBreeder.gui.models.run_state import RunState

REPO_ROOT = Path(__file__).parent.parent.parent  # tests/gui/ -> tests/ -> repo root


class TestDeploymentFactory:
    def test_creates_breed_dir(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert model.breed_dir.is_dir()

    def test_config_py_has_correct_basepath(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        config_text = (model.breed_dir / "config.py").read_text()
        # The factory writes basepath using repr(), so backslashes are escaped in the source.
        # Double each backslash to match how they appear inside the repr'd string literal.
        expected = str(model.breed_dir).replace("\\", "\\\\")
        assert expected in config_text

    def test_current_population_exists(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert model.population_file_path().exists()

    def test_model_name_matches_input(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="my_breeder", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert model.name == "my_breeder"

    def test_model_run_state_is_idle(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert model.run_state == RunState.IDLE

    def test_model_deployment_dir_matches(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert model.deployment_dir == tmp_path / "test_deploy"

    def test_source_python_files_copied(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        # Check a few key files from the source breed/ directory
        for fname in ("board_info.py", "breeder.py", "data_structures.py"):
            src = REPO_ROOT / "GoBreeder" / "breed" / fname
            if src.exists():
                assert (model.breed_dir / fname).exists(), f"{fname} was not copied"

    def test_gogui_dir_present_in_deployment(self, tmp_path: Path) -> None:
        """gogui-v1.6.0-bin must be present alongside breed/ for two_gtp_command."""
        gogui_src = REPO_ROOT / "GoBreeder" / "gogui-v1.6.0-bin"
        if not gogui_src.exists():
            pytest.skip("gogui-v1.6.0-bin not present in repo")
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        gogui_dst = model.deployment_dir / "gogui-v1.6.0-bin"
        assert gogui_dst.exists(), "gogui-v1.6.0-bin missing from deployment directory"

    def test_raises_if_directory_already_exists(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        # Pre-create the target directory
        (tmp_path / "existing").mkdir()
        with pytest.raises(DeploymentError, match="already exists"):
            factory.create(name="existing", parent_dir=tmp_path, repo_root=REPO_ROOT)

    def test_config_py_is_valid_python(self, tmp_path: Path) -> None:
        """Verify the generated config.py can be compiled without syntax errors."""
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        config_text = (model.breed_dir / "config.py").read_text()
        # compile() raises SyntaxError if invalid
        compile(config_text, "config.py", "exec")

    def test_returns_deployment_model(self, tmp_path: Path) -> None:
        from GoBreeder.gui.models.deployment import DeploymentModel

        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        assert isinstance(model, DeploymentModel)

    # --- refresh_code tests ---

    def test_refresh_code_updates_code_files(self, tmp_path: Path) -> None:
        """refresh_code() should overwrite code files with the latest source."""
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        # Corrupt a code file
        target = model.breed_dir / "breeder.py"
        target.write_text("# corrupted")
        updated = factory.refresh_code(model, repo_root=REPO_ROOT)
        assert "breeder.py" in updated
        # File content should now differ from "# corrupted"
        assert target.read_text() != "# corrupted"

    def test_refresh_code_does_not_touch_population_file(self, tmp_path: Path) -> None:
        """refresh_code() must never overwrite the population state file."""
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        pop_file = model.population_file_path()
        sentinel = "# sentinel population data\n"
        pop_file.write_text(sentinel)
        factory.refresh_code(model, repo_root=REPO_ROOT)
        assert pop_file.read_text() == sentinel, "population file was overwritten"

    def test_refresh_code_does_not_touch_config(self, tmp_path: Path) -> None:
        """refresh_code() must not overwrite the deployment-specific config.py."""
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        config_file = model.breed_dir / "config.py"
        original_config = config_file.read_text()
        factory.refresh_code(model, repo_root=REPO_ROOT)
        assert config_file.read_text() == original_config, "config.py was overwritten"

    def test_refresh_code_returns_list_of_updated_files(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        updated = factory.refresh_code(model, repo_root=REPO_ROOT)
        assert isinstance(updated, list)
        assert len(updated) > 0

    def test_refresh_code_raises_if_breed_dir_missing(self, tmp_path: Path) -> None:
        factory = DeploymentFactory()
        model = factory.create(name="test_deploy", parent_dir=tmp_path, repo_root=REPO_ROOT)
        import shutil
        shutil.rmtree(model.breed_dir)
        with pytest.raises(DeploymentError, match="not found"):
            factory.refresh_code(model, repo_root=REPO_ROOT)

    def test_refreshable_files_excludes_current_population(self) -> None:
        assert "current_population.py" not in _REFRESHABLE_CODE_FILES
