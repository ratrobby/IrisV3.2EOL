import threading
from typing import Callable, Any

def start_thread(target: Callable[..., Any], *args, daemon: bool = True, **kwargs) -> threading.Thread:
    """Start ``target`` in a daemon thread and return the ``Thread``."""
    thread = threading.Thread(target=target, args=args, kwargs=kwargs)
    thread.daemon = daemon
    thread.start()
    return thread
