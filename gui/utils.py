import os
import json


def load_config(path="config/Test_Cell_Config.json"):
    with open(path) as f:
        return json.load(f)


def save_config(data, path="config/Test_Cell_Config.json"):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
