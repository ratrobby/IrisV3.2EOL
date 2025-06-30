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

## License

This project is licensed under the [MIT License](LICENSE).
