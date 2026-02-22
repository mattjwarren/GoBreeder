from __future__ import annotations

import json
from pathlib import Path

import pytest

from GoBreeder.gui.models.deployment import DeploymentModel
from GoBreeder.gui.models.population_library import (
    PopulationLibrary,
    PopulationLibraryError,
    PopulationRecord,
    _count_genomes,
)
from GoBreeder.gui.models.run_state import RunState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_library(tmp_path: Path) -> PopulationLibrary:
    lib_dir = tmp_path / "lib"
    registry = tmp_path / "registry.json"
    return PopulationLibrary(library_dir=lib_dir, registry_path=registry)


def make_deployment(tmp_path: Path, running: bool = False) -> DeploymentModel:
    dep_dir = tmp_path / "deployments" / "my_dep"
    breed_dir = dep_dir / "breed"
    breed_dir.mkdir(parents=True, exist_ok=True)
    return DeploymentModel(
        name="my_dep",
        deployment_dir=dep_dir,
        run_state=RunState.RUNNING if running else RunState.IDLE,
    )


# ---------------------------------------------------------------------------
# _count_genomes
# ---------------------------------------------------------------------------

def test_count_genomes_counts_non_comment_non_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "pop.pop"
    p.write_text("# comment\n\n[1, 2, 3]\n[4, 5]\n", encoding="utf-8")
    assert _count_genomes(p) == 2


def test_count_genomes_returns_zero_on_missing_file(tmp_path: Path) -> None:
    assert _count_genomes(tmp_path / "missing.pop") == 0


# ---------------------------------------------------------------------------
# PopulationRecord serialisation
# ---------------------------------------------------------------------------

def test_population_record_model_dump_json_converts_path(tmp_path: Path) -> None:
    rec = PopulationRecord(name="test", file_path=tmp_path / "test.pop")
    data = rec.model_dump(mode="json")
    assert isinstance(data["file_path"], str)


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

def test_add_creates_file_and_record(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("alpha")
    assert rec.name == "alpha"
    assert rec.file_path.exists()
    assert len(lib.list_all()) == 1


def test_add_raises_on_duplicate_name(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add("alpha")
    with pytest.raises(PopulationLibraryError, match="already exists"):
        lib.add("alpha")


def test_add_copies_source_file(tmp_path: Path) -> None:
    src = tmp_path / "source.pop"
    src.write_text("[1, 2]\n[3, 4]\n", encoding="utf-8")
    lib = make_library(tmp_path)
    rec = lib.add("beta", source_path=src)
    assert rec.file_path.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
    assert rec.genome_count == 2


def test_add_empty_population_creates_comment_file(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("empty")
    content = rec.file_path.read_text(encoding="utf-8")
    assert content.startswith("#")
    assert rec.genome_count == 0


# ---------------------------------------------------------------------------
# add_from_dna_list()
# ---------------------------------------------------------------------------

def test_add_from_dna_list_writes_correct_content(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    reprs = ["[1, 2, 3]", "[4, 5]", "[6]"]
    rec = lib.add_from_dna_list("my_pop", reprs)
    lines = rec.file_path.read_text(encoding="utf-8").splitlines()
    assert lines == reprs
    assert rec.genome_count == 3


def test_add_from_dna_list_raises_on_duplicate(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add_from_dna_list("pop", ["[1]"])
    with pytest.raises(PopulationLibraryError):
        lib.add_from_dna_list("pop", ["[2]"])


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

def test_delete_removes_file_and_record(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("to_delete")
    assert rec.file_path.exists()
    lib.delete(rec)
    assert not rec.file_path.exists()
    assert len(lib.list_all()) == 0


def test_delete_tolerates_missing_file(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("ghost")
    rec.file_path.unlink()  # simulate missing file
    # Should not raise
    lib.delete(rec)
    assert len(lib.list_all()) == 0


# ---------------------------------------------------------------------------
# rename()
# ---------------------------------------------------------------------------

def test_rename_moves_file_and_updates_record(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("old_name")
    updated = lib.rename(rec, "new_name")
    assert updated.name == "new_name"
    assert updated.file_path.name == "new_name.pop"
    assert updated.file_path.exists()
    assert not rec.file_path.exists()
    records = lib.list_all()
    assert len(records) == 1
    assert records[0].name == "new_name"


def test_rename_raises_on_duplicate_name(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add("first")
    rec = lib.add("second")
    with pytest.raises(PopulationLibraryError):
        lib.rename(rec, "first")


# ---------------------------------------------------------------------------
# inject_into_deployment()
# ---------------------------------------------------------------------------

def test_inject_into_deployment_copies_file(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add_from_dna_list("inject_pop", ["[10, 20]"])
    dep = make_deployment(tmp_path)
    lib.inject_into_deployment(rec, dep)
    target = dep.population_file_path()
    assert target.exists()
    assert "[10, 20]" in target.read_text(encoding="utf-8")


def test_inject_raises_when_deployment_running(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add_from_dna_list("running_pop", ["[1]"])
    dep = make_deployment(tmp_path, running=True)
    with pytest.raises(PopulationLibraryError, match="running"):
        lib.inject_into_deployment(rec, dep)


def test_inject_raises_when_file_missing(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    rec = lib.add("no_file")
    rec.file_path.unlink()  # remove the file
    dep = make_deployment(tmp_path)
    with pytest.raises(PopulationLibraryError, match="not found"):
        lib.inject_into_deployment(rec, dep)


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------

def test_list_all_returns_all_records(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add("a")
    lib.add("b")
    lib.add("c")
    names = [r.name for r in lib.list_all()]
    assert sorted(names) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_save_and_reload(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add("persist_me")
    lib._save()

    # Load into a fresh instance bypassing __init__
    lib2 = make_library(tmp_path)
    lib2._load()
    names = [r.name for r in lib2.list_all()]
    assert "persist_me" in names


def test_persistence_registry_json_is_valid(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib.add_from_dna_list("check", ["[1, 2]"])
    lib._save()
    raw = json.loads(lib._registry_path.read_text())
    assert isinstance(raw, list)
    assert raw[0]["name"] == "check"
    assert isinstance(raw[0]["file_path"], str)


def test_load_tolerates_corrupt_registry(tmp_path: Path) -> None:
    lib = make_library(tmp_path)
    lib._registry_path.parent.mkdir(parents=True, exist_ok=True)
    lib._registry_path.write_text("not valid json", encoding="utf-8")
    lib._load()  # should not raise
    assert lib.list_all() == []
