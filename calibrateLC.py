import argparse
import tkinter as tk
from IO_master import IO_master
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300


class LoadCellMonitor:
    """Tkinter window to display load cell readings."""

    def __init__(self, root, cells, unit):
        self.root = root
        self.cells = cells
        self.unit = unit
        self.labels = []
        label_unit = "N" if unit.lower() == "n" else "lbf"
        for i in range(5):
            label = tk.Label(root, text=f"Load cell {i + 1}: --{label_unit}")
            label.pack()
            self.labels.append(label)
        self.update_values()

    def update_values(self):
        label_unit = "N" if self.unit.lower() == "n" else "lbf"
        for i, cell in enumerate(self.cells, start=1):
            force = cell.read_force(self.unit)
            if force is None:
                text = f"Load cell {i}: N/A"
            else:
                text = f"Load cell {i}: {force:.2f}{label_unit}"
            self.labels[i - 1].config(text=text)
        # update again after 500ms
        self.root.after(500, self.update_values)


def main():
    parser = argparse.ArgumentParser(
        description="Open a window displaying readings from five load cells"
    )
    parser.add_argument("ip", help="IP address of the AL1342 IO master")
    parser.add_argument(
        "--hub-port",
        type=int,
        default=1,
        help="AL1342 port number where the AL2205 hub is connected (1-8)",
    )
    parser.add_argument(
        "--unit",
        choices=["lbf", "N"],
        default="N",
        help="Force units to display",
    )
    args = parser.parse_args()

    io = IO_master(args.ip)
    hub = AL2205Hub(io, port_number=args.hub_port)
    cells = [LoadCellLCM300(hub, x1_index=i) for i in range(5)]

    root = tk.Tk()
    root.title("Load Cell Monitor")

    # create and start monitor
    monitor = LoadCellMonitor(root, cells, args.unit)

    def on_close():
        io.close_client()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
