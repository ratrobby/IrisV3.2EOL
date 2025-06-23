from scipy.interpolate import interp1d
import time

# Public API decorator
def public_api(func):
    func._is_public_api = True
    return func

class ITV1050Controller:

    """
    =====================================
    ITV1050Controller - Public Interface
    =====================================

    Purpose:
    --------
    Control an SMC ITV1050 electro-pneumatic regulator via Modbus.

    Constructor:
    ------------
    ITV1050Controller(io_master, port_number)

    Public Method:
    --------------
    - set_pressure(target_psi, tolerance=1.0, timeout=10)

    Notes:
    ------
    - Automatically corrects for nonlinear output using interpolation.
    - Converts desired psi to raw command register value.
    """

    @classmethod
    def instructions(cls):
        return """
Command: ~set_pressure(target_psi)~
    Use: Sets ITV-1050 to target pressure value
    Inputs:
        - target_psi: Pressure value in psi
    Example:
        - set_pressure(25) - Sets ITV-1050 to 25psi
                
            """
    def __init__(self, io_master, port_number, default_tolerance=1.0, default_timeout=10):
        self.io_master = io_master
        self.port = port_number
        self.command_register = io_master.id_write_register(port_number)
        self.feedback_register = io_master.id_read_register(port_number)
        self.min_psi = 15.0
        self.max_psi = 115.0
        self.command_correction = self._build_correction_curve()

        # Default values for public method
        self.default_tolerance = default_tolerance
        self.default_timeout = default_timeout

    ...

    @public_api
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