try:
    from scipy.interpolate import interp1d
except Exception:  # pragma: no cover - optional SciPy dependency
    def interp1d(x, y):
        """Minimal linear interpolation fallback if SciPy is unavailable."""

        x_vals = list(x)
        y_vals = list(y)

        def _interp(v):
            if v <= x_vals[0]:
                return y_vals[0]
            if v >= x_vals[-1]:
                return y_vals[-1]
            for i in range(1, len(x_vals)):
                if v <= x_vals[i]:
                    x0, x1 = x_vals[i - 1], x_vals[i]
                    y0, y1 = y_vals[i - 1], y_vals[i]
                    return y0 + (y1 - y0) * (v - x0) / (x1 - x0)
            return y_vals[-1]

        return _interp
import os
import sys
import time

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import setup_command, test_command, device_class

@device_class
class PressureRegulatorITV1050:

    @classmethod
    def setup_instructions(cls):
        return [
            {
                "title": "set_pressure(target_psi)",
                "content": (
                    "Use: Sets ITV-1050 to target pressure value\n"
                    "Inputs:\n"
                    "    - target_psi: Pressure value in psi\n"
                    "Example:\n"
                    "    - set_pressure(25) - Sets ITV-1050 to 25psi"
                ),
            }
        ]
    @classmethod
    def test_instructions(cls):
        return cls.setup_instructions()
    def __init__(self, io_master, port_number, default_tolerance=1.0, default_timeout=10):
        self.io_master = io_master
        self.port = port_number
        self.command_register = io_master.id_write_register(port_number)
        self.feedback_register = io_master.id_read_register(port_number)
        self.min_psi = 15.0
        self.max_psi = 115.0

        # Build interpolation function converting psi -> raw command
        self.command_correction = self._build_correction_curve()

        # Default values for public method
        self.default_tolerance = default_tolerance
        self.default_timeout = default_timeout

    def _build_correction_curve(self):
        """Return interpolation from pressure to raw command value."""
        try:
            return interp1d(
                [self.min_psi, self.max_psi],
                [0, 65535],
            )
        except Exception:
            x0, x1 = self.min_psi, self.max_psi
            y0, y1 = 0, 65535

            def _linear(v):
                if v <= x0:
                    return y0
                if v >= x1:
                    return y1
                return y0 + (y1 - y0) * (v - x0) / (x1 - x0)

            return _linear

    def _write_pressure(self, target_psi):
        """Write corrected raw value for the desired pressure."""
        psi = min(max(target_psi, self.min_psi), self.max_psi)
        raw = int(self.command_correction(psi))
        self.io_master.write_register(self.command_register, raw)
        return raw

    def _read_feedback_psi(self):
        """Read raw feedback value and convert to psi."""
        raw = self.io_master.read_register(self.feedback_register)
        psi = ((raw / 65535) * (self.max_psi - self.min_psi)) + self.min_psi
        return psi, raw


    def set_pressure(self, target_psi):
        """
        Set the regulator to the target pressure and wait until it's within default tolerance.

        Parameters:
        - target_psi: desired output pressure

        Returns:
        - True if pressure reached within tolerance, else False
        """
        tolerance = self.default_tolerance
        timeout = self.default_timeout

        self._write_pressure(target_psi)
        start_time = time.time()

        while time.time() - start_time < timeout:
            feedback_psi, raw = self._read_feedback_psi()
            error = abs(feedback_psi - target_psi)
            print(f"📈 Feedback: {feedback_psi:.2f} psi (raw: {raw}) | Error: {error:.2f}")
            if error <= tolerance:
                print(f"✅ Within tolerance: {feedback_psi:.2f} psi")
                return True
            time.sleep(0.2)

        print("❌ Did not reach target within timeout")
        return False
