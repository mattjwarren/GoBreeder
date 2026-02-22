# Phase 5 & 6 Progress: Archive Management UI + Population Library

## Date: 2026-02-22

## What Was Done

### Phase 6: Population Library Model (`GoBreeder/gui/models/population_library.py`)

- `PopulationRecord(BaseModel)` — name, file_path, genome_count, created_at, modified_at, notes
- `PopulationLibrary(QObject)` — persistent library stored in `~/.gobreeder/`
  - `add(name, source_path?)` — creates or copies a population file
  - `add_from_dna_list(name, dna_reprs)` — writes repr strings directly
  - `delete(record)` — removes file and registry entry
  - `rename(record, new_name)` — moves file and updates record
  - `inject_into_deployment(record, deployment)` — copies pop file into deployment; raises if RUNNING
  - `list_all()` — returns all records
  - Persistence via JSON registry at `~/.gobreeder/library.json`
  - `library_changed = Signal()` emitted on every mutation

### Phase 5: Archive Browser (`GoBreeder/gui/panels/archive_manager_panel.py`)

- `ArchiveBrowserWidget(QWidget)`:
  - Left: archive list with Add/Remove buttons; QTreeWidget of archive contents; pop-file-only filter toggle
  - Middle: genome table (Index/Length/Fitness/Preview); View in VM Inspector / Add to Selection buttons
  - Right: export selection list; Remove/Clear All/Save as Population File/Import to Library buttons
  - Signals: `view_genome_requested(list)`, `import_to_library_requested(list)`
- `ArchiveManagerPanel(QWidget)`:
  - QTabWidget containing `ArchiveBrowserWidget` + `PopulationLibraryPanel`
  - Routes `view_genome_requested` → `vm_inspector_panel.load_dna()`
  - Routes `import_to_library_requested` → `PopulationLibraryPanel.import_from_selection()`

### Phase 6: Population Library Panel (`GoBreeder/gui/panels/population_library_panel.py`)

- `PopulationLibraryPanel(QWidget)`:
  - Left: QListWidget of records with toolbar (New, Import from File, Delete, Rename, Import from Archive Selection)
  - Right: detail pane (name, path, genome count, notes editor, genome preview table)
  - Action buttons: Inject into Deployment, Open in VM Inspector
  - `open_in_inspector_requested = Signal(list)`
  - `import_from_selection(dna_reprs)` — called from archive browser

### Integration Updates

- `GoBreeder/gui/main_window.py` — replaced placeholder tab with `ArchiveManagerPanel`; creates `PopulationLibrary(parent=self)`; passes library to `DeploymentPanel`
- `GoBreeder/gui/panels/deployment_panel.py` — added `library: PopulationLibrary | None = None` param; added "Inject Population from Library…" button; `_on_inject_population()` method

## Design Decisions

- `PopulationLibrary` stores files in `~/.gobreeder/populations/` with `.pop` extension; registry in `~/.gobreeder/library.json`
- Library dir / registry path are constructor params to enable clean unit testing with `tmp_path`
- Archive browser uses `ArchiveReader.list_files()` to build directory tree; `read_population_from_archive()` to load genomes on tree node click
- `ArchiveBrowserWidget` uses a path → `ArchiveEntry` tree built from `internal_path` strings, splitting on `/`

## Tests

- `tests/gui/test_population_library.py` — 20 tests covering all CRUD operations, error cases, and persistence

## Metrics

- 270 total tests, all passing
- 0 ruff errors, 0 mypy errors
