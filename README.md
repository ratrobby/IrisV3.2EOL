# MRLF Repo

This repository contains device classes and GUI tools for the MRLF project. The repository layout is organised as follows:

```
MRLF Repo/
├── devices/         # Device class modules
├── gui/             # GUI applications
├── config/          # JSON configuration files
├── logs/            # Test run logs
├── decorators.py
├── IO_master.py
└── README.md
```



Calibration values for position sensors are stored in the file specified by the
`MRLF_CALIBRATION_FILE` environment variable. The Test Wizard automatically sets
this variable to `<TestFolder>/sensor_calibrations.json` when a test starts so
each test keeps its own calibration data. If the variable is not set, the
default `config/sensor_calibrations.json` path in the repository root is used.

`gui/TestWizard.py` now supports a generic calibration wizard. Any device
implementing a `calibration_steps()` class method will show a **Calibrate…**
button in the Test Wizard setup panel. Clicking the button launches a wizard
that walks through the defined steps.

Loop steps in the Test Wizard can be reordered by dragging rows in the loop
editor.

The standalone PySimpleGUI tool for calibrating all
`PositionSensorSDATMHS_M160` devices is still available:

```bash
python -m gui.sensor_calibration_psg
```

## Python Dependencies

The GUI and device modules rely on a few external packages. Install the core
dependencies with:

```bash
pip install PySimpleGUI pyModbusTCP
```


Some features, such as interpolation in the calibration tools, require the
optional `scipy` package:

```bash
pip install scipy
```

## Utility Commands

Test scripts can use a small helper function to pause between actions:

```python
from commands import Hold

Hold(3)  # wait 3 seconds
```

The `Hold` function is available automatically when running scripts in the Test Wizard.

### Running Sensor Calls in Parallel

The repository includes a ``thread_utils`` module with a convenient
``start_thread`` helper. Device classes also provide ``*_thread`` methods so
reads or monitoring loops can run concurrently:

```python
from thread_utils import start_thread

# Monitor multiple load cells at the same time
LC_1.monitor_force_thread("N", duration=3)
LC_2.monitor_force_thread("N", duration=3)

# Read a position sensor in the background
PS_1.read_position_thread()

# Monitor a position sensor for 2 seconds
PS_1.monitor_position_thread(duration=2)
```

Each helper returns the ``Thread`` object for optional joining or inspection.

The Test Wizard loop builder also includes a **Thread** checkbox for each step.
When checked, the generated script wraps that line with ``start_thread`` so the
command runs in a background thread. This allows sensor monitoring or other
device calls to execute concurrently with subsequent steps.

### Valve Bank Control

When a `ValveBank_SY3000` device is mapped, the Test Wizard setup panel shows an
**Open Valve Controller** button. This opens a small window with toggle buttons
for each valve so they can be switched on and off during setup.

The same controller is provided on the command line and can be launched as:

```bash
python valve_bank_cli.py --ip 192.168.1.250 --device-port 1
```

Commands at the prompt include `on VALVE [DURATION]`, `off VALVE`, `alloff` and `exit`. A duration turns the valve off automatically after the specified seconds while omitting it keeps the valve on until commanded otherwise.

## License

This project is licensed under the [MIT License](LICENSE).
