from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field

from GoBreeder.gui.models.run_state import RunState


class DeploymentModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=False)

    name: str
    deployment_dir: Path
    created_at: datetime = Field(default_factory=datetime.now)
    run_state: RunState = RunState.IDLE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def breed_dir(self) -> Path:
        return self.deployment_dir / "breed"

    def population_file_path(self) -> Path:
        return self.breed_dir / "current_population.py"

    def previous_population_file_path(self) -> Path:
        return self.breed_dir / "current_population.py_save"

    def stats_file_path(self) -> Path:
        return self.breed_dir / "current_population.py_save_stats"

    def runlog_path(self) -> Path:
        return self.breed_dir / "runlog.txt"

    def is_running(self) -> bool:
        return self.run_state == RunState.RUNNING

    def model_dump(self, **kwargs) -> dict:  # type: ignore[override]
        """Override to ensure Path fields are serialised as strings by default."""
        data = super().model_dump(**kwargs)
        mode = kwargs.get("mode", "python")
        if mode == "json":
            for key in ("deployment_dir", "breed_dir"):
                if key in data and isinstance(data[key], Path):
                    data[key] = str(data[key])
        return data
