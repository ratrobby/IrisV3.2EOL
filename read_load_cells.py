from IO_master import IO_master
from AL2205_Hub import AL2205Hub
from LoadCell_LCM300 import LoadCellLCM300
import atexit

# Configure IO master and AL2205 hub
io = IO_master("192.168.1.1")
hub = AL2205Hub(io, port_number=1)

# Instantiate five load cells on ports X1.0 to X1.4
cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

# Ensure Modbus client is closed on exit
atexit.register(io.close_client)


def readLC(n):
    """Print the force from load cell ``n`` in newtons.

    Parameters
    ----------
    n : int
        Load cell number (1-5).
    """
    if not 1 <= n <= len(cells):
        raise ValueError("Load cell number must be between 1 and 5")
    force = cells[n - 1].read_force()
    if force is None:
        print(f"LC{n}: N/A")
    else:
        print(f"LC{n}: {force:.2f} N")
