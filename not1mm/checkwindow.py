#!/usr/bin/env python3
"""
Check Window
"""
# pylint: disable=no-name-in-module, unused-import, no-member, invalid-name, c-extension-no-member
# pylint: disable=logging-fstring-interpolation, line-too-long

import logging
import os
from datetime import datetime, timedelta
from json import loads

import Levenshtein
from PyQt6 import uic
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QGraphicsOpacityEffect

import not1mm.fsutils as fsutils
import not1mm.lib.event as appevent

from not1mm.lib.super_check_partial import SCP
from not1mm.model import QsoLog
from not1mm.model.inmemory import Spot
from not1mm.qtcomponents.DockWidget import DockWidget

logger = logging.getLogger(__name__)


class ScpWorker(QThread):

    def __init__(self, call, scp):
        super().__init__()
        self.call = call
        self.result = None
        self.scp = scp

    def run(self):
        self.result = self.scp.super_check(self.call)
        self.result = filter(lambda x: '#' not in x, self.result)


class CheckWindow(DockWidget):
    """The check window. Shows list or probable stations."""
    dbname = None
    pref = {}

    masterLayout: QVBoxLayout = None
    dxcLayout: QVBoxLayout = None
    qsoLayout: QVBoxLayout = None

    character_remove_color = '#cc3333'
    character_add_color = '#3333cc'

    masterScrollWidget: QWidget = None

    master_debounce_timer = False

    call: str = None

    last_callsign_count_datetime: datetime = None
    callsign_count: int = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        appevent.register(appevent.CallChanged, self.event_call_change)

        self.load_pref()

        logger.debug(uic.widgetPluginPath)
        uic.loadUi(fsutils.APP_DATA_PATH / "checkwindow.ui", self)

        self.scp = SCP(fsutils.APP_DATA_PATH)

    def load_pref(self) -> None:
        """
        Load preference file to get current db filename and sets the initial darkmode state.
        """
        try:
            if os.path.exists(fsutils.CONFIG_FILE):
                with open(
                    fsutils.CONFIG_FILE, "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.pref = loads(file_descriptor.read())
                    logger.info(f"loaded config file from {fsutils.CONFIG_FILE}")
                if self.pref.get("darkmode", None):
                    # red darkmode
                    self.character_remove_color = '#990000'
                    # blue darkmode
                    self.character_add_color = '#000099'
                else:
                    # red light mode
                    self.character_remove_color = '#ff6666'
                    # blue light mode
                    self.character_add_color = '#66ccff'
            else:
                self.pref["current_database"] = "ham.db"

        except IOError as exception:
            logger.critical("Error: %s", exception)

    def event_call_change(self, event: appevent.CallChanged):
        self.call = event.call
        if event.call == "":
            self.clear_lists()
        else:
            if len(self.call) <= 12:
                self.master_list(self.call)
            self.qsolog_list(self.call)
            self.dxc_list(Spot.get_like_calls(event.call))

    def clear_lists(self) -> None:
        self.populate_layout(self.masterLayout, [])
        self.show_count(self.masterLayout, len(self.scp.scp or []))
        self.populate_layout(self.qsoLayout, [])
        self.show_count(self.qsoLayout, self._get_callsign_count())
        self.populate_layout(self.dxcLayout, [])

    def _get_callsign_count(self):
        now = datetime.utcnow()
        if not self.last_callsign_count_datetime or not self.callsign_count \
            or now - self.last_callsign_count_datetime > timedelta(seconds=10):
            self.callsign_count = QsoLog.select(QsoLog.call.distinct()).count()
        self.last_callsign_count_datetime = datetime.utcnow()
        return self.callsign_count

    def show_count(self, layout, count):
        label = QLabel(str(count))
        label.setGraphicsEffect(QGraphicsOpacityEffect())
        label.graphicsEffect().setOpacity(0.5)
        label.setStyleSheet("QLabel {font-size: 10pt; font-family: 'Roboto Mono'; font-style: italic;}")
        layout.addWidget(label)
        layout.addStretch(0)

    def master_list(self, call: str) -> None:
        """
        Get MASTER.SCP matches to call and display in list.

        Parameters
        ----------
        call : str
        Call to get matches for
        """

        # The super check call is what takes up most of the runtime
        self.master_list_thread = ScpWorker(call, self.scp)
        self.master_list_thread.finished.connect(self.master_list_scp_finished)
        self.master_list_thread.start()

    def master_list_scp_finished(self) -> None:
        if self.call != self.master_list_thread.call:
            return
        self.populate_layout(self.masterLayout, self.master_list_thread.result)

    def qsolog_list(self, call: str) -> None:
        """
        Get log matches to call and display in list.

        Parameters
        ----------
        call : str
        Call to get matches for
        """
        result = QsoLog.get_like_calls(call, None)
        self.populate_layout(self.qsoLayout, result)

    def dxc_list(self, spots: list) -> None:
        """
        Get telnet matches to call and display in list.

        Parameters
        ----------
        spots : list
        List of spots to get matches for
        """
        if spots:
            self.populate_layout(self.dxcLayout, filter(lambda x: x, [x.callsign for x in spots]))

    def populate_layout(self, layout, call_list):
        call_items = []

        for call in call_list:
            if call:
                if self.call:
                    label_text = ""
                    diff_score = 0
                    #logger.debug(f'opcodes for {call} {self.call}')
                    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(call, self.call):
                        #logger.debug('{:7}   i[{}:{}] --> j[{}:{}] {!r:>8} --> {!r}'.format(
                        #    tag, i1, i2, j1, j2, call[i1:i2], self.call[j1:j2]))
                        if tag == 'equal':
                            label_text += call[i1:i2]
                            continue
                        elif tag == 'replace':
                            label_text += f"<span style='background-color: {self.character_remove_color};'>{call[i1:i2]}</span>"
                            diff_score += max((i2 - i1), (j2 - j1)) * (max(len(call), len(self.call)) + 1 - min(i1, j1))
                        elif tag == 'insert' or tag == 'delete':
                            label_text += f"<span style='background-color: {self.character_add_color};'>{call[i1:i2]}</span>"
                            diff_score += max((i2 - i1), (j2 - j1)) * (max(len(call), len(self.call)) + 1 - min(i1, j1))
                        #logger.debug(f"new score high is bad {diff_score}")
                    #call_items.append((Levenshtein.hamming(call, self.call), label_text, call))
                    call_items.append((diff_score, label_text, call))

        call_items = sorted(call_items, key=lambda x: x[0])
        for i in reversed(range(layout.count())):
            if layout.itemAt(i).widget():
                layout.itemAt(i).widget().setParent(None)
            else:
                layout.removeItem(layout.itemAt(i))

        for _, label_text, call in call_items:
            label = CallLabel(label_text, call=call)
            label.setStyleSheet("QLabel {/*font-size: 11pt; */letter-spacing: 0.15em; font-family: 'Roboto Mono';}")
            layout.addWidget(label)
        if len(call_items):
            # top aligns
            layout.addStretch(0)

class CallLabel(QLabel):
    call: str = None
    def __init__(self, *args, call=None, ):
        super().__init__(*args)
        self.call = call

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if self.call:
            appevent.emit(appevent.Tune(None, self.call))
