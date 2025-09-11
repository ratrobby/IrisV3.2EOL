# AL1342 / AL2205 / LCM300 Interface

This repository provides a minimal set of Python modules for reading an LCM300 load
cell through an AL2205 IO-Link hub connected to an AL1342 IO master.

## Contents

```
devices/                   # Hardware interface modules
  IO_master.py             # Modbus communication with the AL1342
  AL2205_Hub.py            # Access analog values from the AL2205 hub
  LoadCell_LCM300.py       # Convert analog values to force readings
  PressureSensor_PQ3834.py # PQ3834 pressure sensor helper
  FlowPressure_SD9500.py   # SD9500 flow/pressure sensor helper
  FlowSensor_SD6020.py     # SD6020 flow sensor helper
Iris_EOL_Fixture.py        # Convenience functions for common tasks
Sample_Test_Script.py      # Example script exercising the fixture
```

## Installation

Install the required dependency:

```
pip install pyModbusTCP
```

## Example
By default, `IO_master` uses the AL1342's IP address `192.168.100.1`. The
example below assumes the AL2205 hub is connected to port 1 and the load cell
is on channel X1.0.

```python
from devices.IO_master import IO_master
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300

io = IO_master()                          # Defaults to IP 192.168.100.1
hub = AL2205Hub(io, port_number=1)        # Hub connected to port 1
cell = LoadCellLCM300(hub, x1_index=0)    # Load cell on channel X1.0

print(cell.read_force())                  # Read force in newtons (default)
print(cell.read_force("lbf"))             # Read force in pounds-force
```

## License

This project is licensed under the [MIT License](LICENSE).
