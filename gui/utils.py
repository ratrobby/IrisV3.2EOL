import os
import json


def load_config(path="config/Test_Cell_Config.json"):
    with open(path) as f:
        return json.load(f)


def save_config(data, path="config/Test_Cell_Config.json"):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


    """Generate a device setup script from a configuration dict.

    Parameters
    ----------
    cfg : dict
        Configuration as returned by ``gather_config()``.

    """
    import inspect
    import importlib
    from .TestWizard import build_instance_map



    instance_map = cfg.get("device_names")
    if not instance_map:
        instance_map = build_instance_map(cfg)
    ip_addr = cfg.get("ip_address", "192.168.XXX.XXX")

    # Collect all selected device modules
    modules = set()
    for section in ("al1342", "al2205"):
        for dev in cfg.get(section, {}).values():
            if dev and str(dev) != "Empty":
                modules.add(dev)

    # Map module name -> device class name
    classes = {}
    for mod_name in sorted(modules):
        try:
            mod = importlib.import_module(f"devices.{mod_name}")
        except Exception:
            continue
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if getattr(obj, "_is_device_class", False):
                classes[mod_name] = name
                break

    lines = [
        "import sys",
        "import os",
        "sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), \"..\")))",
        "",
        "from IO_master import IO_master",
    ]

    for mod_name in sorted(classes):
        cls_name = classes[mod_name]
        lines.append(f"from devices.{mod_name} import {cls_name}")

    lines.append("")
    lines.append(f"master = IO_master(\"{ip_addr}\")")

    hub_vars = {}

    # AL1342 devices (direct IO_master connection)
    for port in sorted(cfg.get("al1342", {})):
        dev_name = cfg["al1342"][port]
        if dev_name == "Empty":
            continue
        cls_name = classes.get(dev_name)
        inst_name = instance_map["al1342"][port]
        port_num = int(port.replace("X0", ""))
        lines.append(
            f"{inst_name} = {cls_name}(master, port_number={port_num})"
        )
        if dev_name == "AL2205_Hub":
            hub_vars[port] = inst_name

    hub_var = next(iter(hub_vars.values()), None)

    # AL2205 devices connected to the hub
    if hub_var:
        for port in sorted(cfg.get("al2205", {})):
            dev_name = cfg["al2205"][port]
            if dev_name == "Empty":
                continue
            cls_name = classes.get(dev_name)
            inst_name = instance_map["al2205"][port]
            index = int(port.split(".")[-1])
            lines.append(
                f"{inst_name} = {cls_name}({hub_var}, x1_index={index})"
            )

    lines.append("")
    lines.append("# Example generated mappings")
    for port in sorted(cfg.get("al1342", {})):
        dev_name = cfg["al1342"][port]
        if dev_name == "Empty":
            continue
        inst = instance_map["al1342"][port]
        lines.append(f"# AL1342 Port {port}: {inst} ({dev_name})")

    for port in sorted(cfg.get("al2205", {})):
        dev_name = cfg["al2205"][port]
        if dev_name == "Empty":
            continue
        inst = instance_map["al2205"][port]
        lines.append(f"# AL2205 {port}: {inst} ({dev_name})")

    script = "\n".join(lines) + "\n"
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(script)
    return script

