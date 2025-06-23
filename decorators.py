# Decorators used by the GUI library to categorize device methods

def test_setup(func):
    """Mark a method as part of a device's test setup procedure."""
    func._is_test_setup = True
    return func


def test_command(func):
    """Mark a method as a command executed during a test."""
    func._is_test_command = True
    return func


def device_class(cls):
    """Mark a class as representing a test device."""
    cls._is_device_class = True
    return cls
