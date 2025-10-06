# Keithley 2612 Controller

A PyQt6 desktop application for configuring a Keithley 2612 SourceMeter over GPIB. It offers resource discovery, channel selection, safe voltage sourcing, and compliance monitoring, with a simulator for development away from the lab.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m keithley2612
```

Select `sim://2612` while developing without hardware; switch to your `GPIB0::<address>::INSTR` resource on the lab PC and run `scripts/smoke_check.py` to confirm connectivity. Use `scripts/panel_feedback_check.py` to verify front-panel beeps and voltage display mirror the hardware workflow.

## Tests

```bash
pytest
```
