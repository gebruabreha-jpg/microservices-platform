import os
import json
from datetime import datetime


def load_env(path=".env"):
    config = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    return config


def get_env(key, default=None):
    return os.getenv(key, config.get(key, default))


config = load_env()