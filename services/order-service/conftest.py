"""Test environment defaults.

The application refuses to start without real credentials (see
``shared.config.require_env``); tests supply throwaway values here so imports
succeed without a live database or broker.
"""

import os

os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")

os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")
