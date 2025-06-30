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

`gui/TestLauncher.py` lets you map devices and create or load tests. Enter a test name, configure the mapping and click **Create New Test** to launch the Test Wizard. Test folders are created inside `~/MRLF Tests` by default (or the location specified in the `MRLF_TEST_DIR` environment variable) and any logs or scripts are written there. The launcher replaces the previous `ConfigureTestCell.py` tool.

Calibration values for position sensors are stored in the file specified by the
`MRLF_CALIBRATION_FILE` environment variable. The Test Wizard automatically sets
this variable to `<TestFolder>/sensor_calibrations.json` when a test starts so
each test keeps its own calibration data. If the variable is not set, the
default `config/sensor_calibrations.json` path in the repository root is used.

Each test directory also contains a `<TestName>_Script.py` generated when the
test is created. This script defines the `IO_master` instance and all mapped
device objects. When the Test Wizard starts a test it sets the
`MRLF_TEST_SCRIPT` environment variable to point at this file so calibration
tools can load the same device objects. Custom device instance names are stored
with the test so rerunning the wizard reproduces the exact configuration.

`gui/TestWizard.py` now supports a generic calibration wizard. Any device
implementing a `calibration_steps()` class method will show a **Calibrate…**
button in the Test Wizard setup panel. Clicking the button launches a wizard
that walks through the defined steps.

The standalone PySimpleGUI tool for calibrating all
`PositionSensorSDATMHS_M160` devices is still available:

```bash
python -m gui.sensor_calibration_psg
```

## License

This project is licensed under the [MIT License](LICENSE).
