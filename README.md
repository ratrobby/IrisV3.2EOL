# AL1342 / AL2205 / LCM300 Interface

This repository provides a minimal set of Python modules for reading an LCM300 load
cell through an AL2205 IO-Link hub connected to an AL1342 IO master.

## Contents

```
IO_master.py               # Modbus communication with the AL1342
AL2205_Hub.py              # Access analog values from the AL2205 hub
LoadCell_LCM300.py         # Convert analog values to force readings
test_read_five_load_cells.py # Command line utility to read up to five load cells
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
from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300

io = IO_master()                          # Defaults to IP 192.168.100.1
hub = AL2205Hub(io, port_number=1)        # Hub connected to port 1
cell = LoadCellLCM300(hub, x1_index=0)    # Load cell on channel X1.0

print(cell.read_force("N"))              # Read force in newtons
```

To read up to five load cells from the command line:

```
python test_read_five_load_cells.py 192.168.100.1
```

## License

This project is licensed under the [MIT License](LICENSE).
