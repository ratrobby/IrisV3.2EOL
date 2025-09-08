from IO_master import IO_master
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300


def readLC(x=None):
    """Print load cell forces in newtons.

    Parameters
    ----------
    x : int or None
        Load cell number to read (1-5). If ``None``, read all five.
    """
    io = IO_master()
    hub = AL2205Hub(io, port_number=1)
    cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]
    label = "N"

    def _print_cell(idx):
        force = cells[idx].read_force("N")
        if force is None:
            print(f"load cell {idx + 1}: N/A")
        else:
            print(f"load cell {idx + 1}: {force:.2f}{label}")

    if x is None:
        for i in range(5):
            _print_cell(i)
    else:
        if not 1 <= x <= 5:
            raise ValueError("Load cell number must be between 1 and 5")
        _print_cell(x - 1)

    io.close_client()
