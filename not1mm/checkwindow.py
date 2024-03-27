#!/usr/bin/env python3
"""
Check Window
"""
# pylint: disable=no-name-in-module, unused-import, no-member, invalid-name, c-extension-no-member
# pylint: disable=logging-fstring-interpolation, line-too-long

import logging
import os
import platform
import queue
from json import loads
import difflib

from PyQt6 import uic
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtWidgets import QWidget

import not1mm.fsutils as fsutils
from not1mm.lib.database import DataBase
from not1mm.lib.multicast import Multicast
from not1mm.lib.super_check_partial import SCP
import Levenshtein

logger = logging.getLogger(__name__)


class CheckWindow(QWidget):
    """The check window. Shows list or probable stations."""

    multicast_interface = None
    dbname = None
    pref = {}

    masterLayout: QVBoxLayout = None
    dxcLayout: QVBoxLayout = None
    qsoLayout: QVBoxLayout = None

    character_remove_color = '#cc3333'
    character_add_color = '#3333cc'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_pref()
        self.dbname = fsutils.USER_DATA_PATH / self.pref.get(
            "current_database", "ham.db"
        )
        self.database = DataBase(self.dbname, fsutils.APP_DATA_PATH)
        self.database.current_contest = self.pref.get("contest", 0)
        logger.debug(uic.widgetPluginPath)
        uic.loadUi(fsutils.APP_DATA_PATH / "checkwindow.ui", self)

        self.mscp = SCP(fsutils.APP_DATA_PATH)
        self._udpwatch = None
        self.udp_fifo = queue.Queue()
        self.multicast_interface = Multicast(
            self.pref.get("multicast_group", "239.1.1.1"),
            self.pref.get("multicast_port", 2239),
            self.pref.get("interface_ip", "127.0.0.1"),
        )
        self.multicast_interface.ready_read_connect(self.watch_udp)


    def load_pref(self) -> None:
        """
        Load preference file to get current db filename and sets the initial darkmode state.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        try:
            if os.path.exists(fsutils.CONFIG_FILE):
                with open(
                    fsutils.CONFIG_FILE, "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.pref = loads(file_descriptor.read())
                    logger.info(f"loaded config file from {fsutils.CONFIG_FILE}")
                if self.pref["darkmode"]:
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

    def watch_udp(self):
        """
        Puts UDP datagrams in a FIFO queue.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        while self.multicast_interface.server_udp.hasPendingDatagrams():
            logger.error("Got multicast ")
            json_data = self.multicast_interface.read_datagram_as_json()

            if json_data.get("station", "") != platform.node():
                continue
            if json_data.get("cmd", "") == "UPDATELOG":
                self.clear_lists()
            if json_data.get("cmd", "") == "CALLCHANGED":
                self.call = json_data.get("call", "")
                self.master_list(self.call)
                self.qsolog_list(self.call)
                continue
            if json_data.get("cmd", "") == "CHECKSPOTS":
                spots = json_data.get("spots", [])
                self.dxc_list(spots)
                continue

    def clear_lists(self) -> None:
        self.populate_layout(self.masterLayout, [])
        self.populate_layout(self.qsoLayout, [])
        self.populate_layout(self.dxcLayout, [])

    def master_list(self, call: str) -> None:
        """
        Get MASTER.SCP matches to call and display in list.

        Parameters
        ----------
        call : str
        Call to get matches for

        Returns
        -------
        None
        """
        results: list = self.mscp.super_check(call)
        self.populate_layout(self.masterLayout, filter(lambda x: '#' not in x, results))

    def qsolog_list(self, call: str) -> None:
        """
        Get log matches to call and display in list.

        Parameters
        ----------
        call : str
        Call to get matches for

        Returns
        -------
        None
        """
        result = []
        if call:
            result = self.database.get_like_calls_and_bands(call)
        self.populate_layout(self.qsoLayout, result)

    def dxc_list(self, spots: list) -> None:
        """
        Get telnet matches to call and display in list.

        Parameters
        ----------
        spots : list
        List of spots to get matches for

        Returns
        -------
        None
        """
        if spots:
            self.populate_layout(self.dxcLayout, filter(lambda x: x, [x.get('callsign', None) for x in spots]))

    def populate_layout(self, layout, call_list):
        for i in reversed(range(layout.count())):
            if layout.itemAt(i).widget():
                layout.itemAt(i).widget().setParent(None)
            else:
                layout.removeItem(layout.itemAt(i))
        labels = []
        for call in call_list:
            if call:
                if self.call:
                    label_text = ""
                    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(call, self.call):
                        #logger.debug('{:7}   a[{}:{}] --> b[{}:{}] {!r:>8} --> {!r}'.format(
                        #    tag, i1, i2, j1, j2, call[i1:i2], self.call[j1:j2]))
                        if tag == 'equal':
                            label_text += call[i1:i2]
                            continue
                        elif tag == 'replace':
                            label_text += f"<span style='background-color: {self.character_remove_color};'>{call[i1:i2]}</span>"
                        elif tag == 'insert' or tag == 'delete':
                            label_text += f"<span style='background-color: {self.character_add_color};'>{call[i1:i2]}</span>"
                    labels.append((Levenshtein.hamming(call, self.call), QLabel(label_text)))

        for _, label in sorted(labels, key=lambda x: x[0]):
            label.setStyleSheet("QLabel {letter-spacing: 0.15em; font-family: 'JetBrains Mono';}")
            layout.addWidget(label)
        # top aligns
        layout.addStretch(0)

