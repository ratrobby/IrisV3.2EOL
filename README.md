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

Saving the configuration also generates `config/Test_Cell_1_Devices.py`. This
file contains an `IO_master` instance and device objects created for every
selected port. The object variable names exactly match those listed in the
Test Wizard's **Device Instances** panel so you can reference them directly in
your test code. The Test Wizard automatically imports this module when a test
starts so the objects are available without manual `import` statements.

Custom device instance names are saved with each test rather than written back
to `config/Test_Cell_1_Devices.py`. When device names are updated in the Test
Wizard a copy of this module is written to the selected test folder as
`<TestName>_Script.py`.
The copy includes alias assignments for the customised names along with the
current setup and loop code so the test configuration can be reproduced later.
When a test is started the wizard will import this generated script instead of
`Test_Cell_1_Devices.py` so the customised names are available automatically.

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
