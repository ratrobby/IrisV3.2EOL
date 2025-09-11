import Iris_EOL_Fixture

if __name__ == "__main__":
    """Read Load Cell (input load cell number)"""
    Iris_EOL_Fixture.readLC(1)

    """Read pressure from the PQ3834 sensor"""
    Iris_EOL_Fixture.readPS()

    """Read flow from the SD9500 sensor"""
    Iris_EOL_Fixture.readVF()

    """Read pressure from the SD9500 sensor"""
    Iris_EOL_Fixture.readVP()

    """Read flow from the SD6020 sensor"""
    Iris_EOL_Fixture.readPF()

    """Open monitoring window"""
    Iris_EOL_Fixture.open_monitor()
