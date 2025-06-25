import tkinter as tk
from tkinter import ttk, messagebox


class CalibrationWizard:
    """Generic wizard that walks through calibration steps for a device."""

    def __init__(self, device, steps, title=None):
        self.device = device
        self.steps = list(steps)
        self.index = -1

        self.win = tk.Toplevel()
        self.win.title(title or f"{device.__class__.__name__} Calibration")

        self.label = ttk.Label(self.win, text="", wraplength=380)
        self.label.pack(padx=10, pady=10)

        self.body = ttk.Frame(self.win)
        self.body.pack(pady=5)

        self.entry = None
        self.button = ttk.Button(self.win, text="Next", command=self._next)
        self.button.pack(pady=10)

        self._next()

    # ---------------------------------------------------------------
    def _run_action(self, step):
        action = step.get("action")
        if not action:
            return True
        method = getattr(self.device, action, None)
        if not callable(method):
            return True
        if "input" in step:
            if not self.entry:
                return True
            value = self.entry.get()
            if step.get("type", "float") == "float":
                try:
                    value = float(value)
                except ValueError:
                    messagebox.showerror("Input Error", f"Invalid value: {value}")
                    return False
            method(value)
        else:
            method()
        return True

    def _next(self):
        # execute current step before advancing
        if self.index >= 0:
            step = self.steps[self.index]
            if self._run_action(step) is False:
                return
        self.index += 1
        if self.index >= len(self.steps):
            self.win.destroy()
            return
        self._show_step()

    def _show_step(self):
        step = self.steps[self.index]
        if self.entry:
            self.entry.destroy()
            self.entry = None
        self.label.config(text=step.get("prompt", ""))
        if "input" in step:
            default = getattr(self.device, step.get("input"), "")
            self.entry = ttk.Entry(self.body)
            self.entry.insert(0, str(default))
            self.entry.pack()
        btn_text = step.get(
            "button",
            "Finish" if self.index == len(self.steps) - 1 else "Next",
        )
        self.button.config(text=btn_text)
