# Repository Guidelines

## Project Structure & Module Organization
- Keep production code in `src/keithley2612/` with submodules for `connection`, `channels`, `automation`, and surface only stable APIs in `__init__.py`.
- Mirror that layout in `tests/` (`tests/test_connection.py` exercises `src/keithley2612/connection.py`).
- Store runnable utilities in `scripts/` (e.g., `scripts/channel_sweep.py`) and place manuals such as `full_manual.md` inside `docs/` with any wiring diagrams or config samples.

## Build, Test, and Development Commands
- Create a virtual environment: `python -m venv .venv` then `source .venv/bin/activate`.
- Install dependencies once `pyproject.toml` exists: `pip install -e .[dev]`.
- Format and lint before committing: `black src tests` then `ruff check src tests`.
- Run the suite locally with `pytest`; use `pytest -k <pattern>` for focused loops and document any hardware a test touched.

## Coding Style & Naming Conventions
- Follow Black defaults (88 columns, double quotes) and keep Ruff warnings at zero; add targeted `# noqa` only when instrument APIs force unusual names.
- Use lowercase snake_case for modules and functions, PascalCase for classes that model SMU concepts, and prefix direct-instrument helpers with `smu_` for quick scanning.
- Keep docstrings short and explicit about expected instrument state or safety limits.

## Testing Guidelines
- Write pure-software tests first and mark hardware-dependent ones `@pytest.mark.hardware`; they should skip by default and require an environment variable to run.
- Stub SMU responses with fixtures under `tests/fixtures/` so command sequences and parsing logic stay verifiable without lab access.
- Target ≥85% coverage for logic layers; attach manual bench notes beside the relevant test file in a lightweight `README.md` when physical validation occurs.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `docs:`) and squash before merging; include scope when touching a specific subsystem (`feat(connection): add VISA retry`).
- Every PR description should link the tracking issue, list the commands executed (`pytest`, `ruff`, live hardware runs), and note whether safety limits changed.
- Request at least one review from someone with recent lab time before merging automation that can drive voltage or current.

## Instrument Safety & Configuration
- Default all scripts to `standby` and require explicit voltage/current limits; guard automated ramps with configurable soft limits.
- Keep VISA addresses, credentials, and lab secrets in `.env` (git-ignored) and document required keys in `docs/config.example.env`.
- Update `docs/automation_playbooks/` with wiring diagrams and emergency shutdown steps whenever a new automation flow lands.

## Development & Lab Workflow
- Core coding happens on a personal macOS laptop without direct SMU access, so rely on simulators and stub transports during development.
- Before merging hardware-facing changes, run the minimal `pyvisa` smoke script on the lab PC to confirm GPIB connectivity and address discovery.
- Follow an iterative loop: implement and unit-test on the laptop → deploy the change set or test script to the lab PC → validate against the instrument → record observations in docs/tests and repeat.
- Use the built-in simulator by choosing `sim://2612` in the GUI or tests when hardware is unavailable; swap to the actual `GPIB0::n::INSTR` address on the lab PC.
- Before lab runs, execute `scripts/smoke_check.py` for connectivity and `scripts/panel_feedback_check.py` to confirm beeper/display behaviour.
