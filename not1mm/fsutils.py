#!/usr/bin/env python3

"""
fsutils.py: Filesystem utilities for not1mm.
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
_app_paths = AppDataPaths(name="not1mm")
_app_paths.setup()

DATA_PATH = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
DATA_PATH += "/not1mm"
USER_DATA_PATH = Path(DATA_PATH)
LOG_FILE = USER_DATA_PATH / "application.log"
_CONFIG_PATH = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
_CONFIG_PATH += "/not1mm"
CONFIG_PATH = Path(_CONFIG_PATH)
CONFIG_FILE = CONFIG_PATH / "not1mm.json"

CONTEST_PLUGIN_PATH = MODULE_PATH / 'contest'

if platform.system() not in ["Windows", "Darwin"]:
    try:
        os.mkdir(CONFIG_PATH)
    except FileExistsError:
        ...
    try:
        os.mkdir(USER_DATA_PATH)
    except FileExistsError:
        ...

if platform.system() in ["Windows", "Darwin"]:
    LOG_FILE = _app_paths.get_log_file_path(name="appplication.log")
    _DATA_PATH = Path(_app_paths.app_data_path)
    USER_DATA_PATH = _DATA_PATH
    CONFIG_PATH = USER_DATA_PATH
    CONFIG_FILE = CONFIG_PATH / "not1mm.json"

DARK_STYLESHEET = ""


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
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "rt", encoding="utf-8") as file_descriptor:
            return json.loads(file_descriptor.read())


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
