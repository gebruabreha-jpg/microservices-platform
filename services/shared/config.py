import os
import json
from datetime import datetime


config = {}


def load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()


def get_env(key, default=None):
    return os.getenv(key, config.get(key, default))


def require_env(key):
    """Return an environment value, or raise if it is not configured.

    Use this for credentials and other values that must never fall back to a
    baked-in default - a missing secret should fail loudly at startup, not
    silently connect with a well-known password.
    """
    value = os.getenv(key, config.get(key))
    if value is None or value == "":
        raise RuntimeError(f"Required environment variable {key!r} is not set")
    return value


load_env()