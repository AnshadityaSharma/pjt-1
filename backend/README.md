# Rover backend

FastAPI control, planning, safety, sensors and telemetry service for the survey
rover. See the repository README and `../docs/` for operation and wiring.

Laptop simulation and tests: `pip install -e ".[dev]"`, then `python -m pytest`.
On Raspberry Pi 5, run `../deploy/install_pi.sh` or install `.[pi]`.
GPIO uses gpiozero with an explicit lgpio factory; Raspberry Pi OS packages
`python3-gpiozero` and `python3-lgpio` can be used with a virtualenv created with
`--system-site-packages`. Hardware libraries are optional for simulation.
