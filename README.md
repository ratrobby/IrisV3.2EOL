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

`gui/ConfigureTestCell.py` presents a minimal GUI used to configure a test cell. The tool allows entering the AL1342 IP address, mapping devices to IO‑Link ports and saving the configuration to `config/Test_Cell_Config.json`. After saving, the TestWizard placeholder GUI is launched.

Saving the configuration also generates `config/Test_Cell_1_Devices.py`. This
file contains an `IO_master` instance and device objects created for every
selected port, using names from the instance map. Test scripts can import this
module to work directly with the configured devices.

`gui/TestWizard.py` remains a simple placeholder for future test execution tools.

To calibrate any connected `PositionSensorSDATMHS_M160` devices with a GUI run:

```bash
python -m gui.sensor_calibration_psg
```
