#!/usr/bin/env python3

"""
fsutils.py: Filesystem utilities for qsourcelogger.
@kyleboyle
"""
import json
import logging

import os
import platform
import sys
import subprocess
from pathlib import Path

from appdata import AppDataPaths

logger = logging.getLogger(__name__)

WORKING_PATH = Path(os.path.dirname(os.path.abspath(__file__)))

MODULE_PATH = WORKING_PATH

APP_DATA_PATH = MODULE_PATH / "data"

CONTEST_PLUGIN_PATH = MODULE_PATH / 'contest'

_app_paths = AppDataPaths(name="qsourcelogger")
_app_paths.setup()
LOG_FILE = _app_paths.get_log_file_path()
_DATA_PATH = Path(_app_paths.app_data_path)
USER_DATA_PATH = _DATA_PATH
CONFIG_PATH = USER_DATA_PATH
CONFIG_FILE = CONFIG_PATH / "qsourcelogger.json"

def openFileWithOS(file):
    """Open a file with the default program for that OS."""
    if sys.platform == "win32":
        os.startfile(file)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", file])
    else:
        subprocess.Popen(["xdg-open", file])
        # os.system(f"xdg-open {fsutils.USER_DATA_PATH / macro_file}")


def read_settings() -> dict:
    if os.path.exists(CONFIG_FILE) and os.path.getsize(CONFIG_FILE) > 0:
        with open(CONFIG_FILE, "rt", encoding="utf-8") as file_descriptor:
            return json.loads(file_descriptor.read())
    else:
        from . import pref_ref
        with open(CONFIG_FILE, "wt", encoding="utf-8") as file_descriptor:
            file_descriptor.write(json.dumps(pref_ref, indent=4))
        return dict(pref_ref)

def write_settings(to_merge: dict) -> None:
    # TODO compare with existing settings and signal diffs
    try:
        settings = None
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "rt", encoding="utf-8") as file_descriptor:
                 settings = json.loads(file_descriptor.read())
        if settings:
            with open(CONFIG_FILE, "wt", encoding="utf-8") as file_descriptor:
                settings.update(to_merge)
                file_descriptor.write(json.dumps(settings, indent=4))
    except IOError as exception:
        logger.exception(f"Error saving preferences document", exception)
