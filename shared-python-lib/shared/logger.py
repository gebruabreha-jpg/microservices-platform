import json
from datetime import datetime


def get_logger(name):
    return {"name": name, "timestamp": datetime.utcnow().isoformat()}


def log_event(logger, level, message, **kwargs):
    entry = {
        "level": level,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "service": logger.get("name", "unknown"),
    }
    entry.update(kwargs)
    print(json.dumps(entry))
    return entry