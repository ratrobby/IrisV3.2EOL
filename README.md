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

`gui/ConfigureTestCell.py` presents a minimal GUI used to configure a test cell. The tool allows entering the AL1342 IP address, mapping devices to IO‑Link ports and saving the configuration to `config/Test_Cell_Config.json`. After saving, the TestWizard GUI is launched.

Saving the configuration also generates `config/Test_Cell_1_Devices.py`. This
file contains an `IO_master` instance and device objects created for every
selected port. The object variable names exactly match those listed in the
Test Wizard's **Device Instances** panel so you can reference them directly in
your test code. The Test Wizard automatically imports this module when a test
starts so the objects are available without manual `import` statements.

Custom device instance names are saved with each test rather than written back
to `config/Test_Cell_1_Devices.py`. When device names are updated in the Test
Wizard a copy of this module is written to `user_tests/<TestName>_Script.py`.
The copy includes alias assignments for the customised names along with the
current setup and loop code so the test configuration can be reproduced later.

`gui/TestWizard.py` remains a simple placeholder for future test execution tools.

To calibrate any connected `PositionSensorSDATMHS_M160` devices with a GUI run:

```bash
python -m gui.sensor_calibration_psg
```
