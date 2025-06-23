import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util
import inspect
import os
import datetime


class RunnerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Test Runner")

        ttk.Label(master, text="Test Name:").pack(anchor="w", padx=5, pady=2)
        self.test_name_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.test_name_var).pack(fill="x", padx=5)

        ttk.Label(master, text="Test Setup:").pack(anchor="w", padx=5, pady=(10, 2))
        self.setup_box = tk.Text(master, height=6, width=50)
        self.setup_box.pack(fill="both", padx=5, pady=5)

        self.run_button = ttk.Button(
            master, text="Run Test Loop", command=self.run_tests
        )
        self.run_button.pack(pady=10)

        self.devices = self._load_devices()
        self.setup_methods, self.command_methods = self._discover_methods()
        self._display_setup()

    def _load_devices(self):
        devices = []
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "Test_Cell_1_Devices.py"
        )
        if not os.path.exists(path):
            return devices
        spec = importlib.util.spec_from_file_location("Test_Cell_1_Devices", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            for obj in module.__dict__.values():
                if not inspect.isclass(obj) and hasattr(obj, "__class__"):
                    devices.append(obj)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load devices:\n{e}")
        return devices

    def _discover_methods(self):
        setup = []
        commands = []
        for dev in self.devices:
            for name, meth in inspect.getmembers(dev, predicate=inspect.ismethod):
                if getattr(meth, "_is_test_setup", False):
                    setup.append((dev, meth))
                if getattr(meth, "_is_test_command", False):
                    commands.append((dev, meth))
        return setup, commands

    def _display_setup(self):
        lines = [
            f"{dev.__class__.__name__}.{meth.__name__}"
            for dev, meth in self.setup_methods
        ]
        self.setup_box.delete("1.0", tk.END)
        self.setup_box.insert(tk.END, "\n".join(lines))

    def run_tests(self):
        test_name = self.test_name_var.get().strip() or "untitled"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("logs", exist_ok=True)
        log_path = os.path.join("logs", f"{test_name}_{ts}.log")

        with open(log_path, "w") as f:
            f.write(f"Test Name: {test_name}\n")
            f.write(f"Timestamp: {ts}\n\n")
            f.write("Test Setup:\n")
            for dev, meth in self.setup_methods:
                f.write(f"  {dev.__class__.__name__}.{meth.__name__}\n")
                try:
                    result = meth()
                    f.write(f"    result: {result}\n")
                except Exception as e:
                    f.write(f"    error: {e}\n")
            f.write("\nTest Loop:\n")
            for i in range(3):
                f.write(f"Iteration {i+1}\n")
                for dev, meth in self.command_methods:
                    try:
                        result = meth()
                        f.write(
                            f"  {dev.__class__.__name__}.{meth.__name__}: {result}\n"
                        )
                    except TypeError:
                        f.write(
                            f"  {dev.__class__.__name__}.{meth.__name__}: missing parameters\n"
                        )
                    except Exception as e:
                        f.write(
                            f"  {dev.__class__.__name__}.{meth.__name__}: ERROR {e}\n"
                        )
        messagebox.showinfo("Completed", f"Log saved to {log_path}")


def launch():
    root = tk.Tk()
    RunnerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
