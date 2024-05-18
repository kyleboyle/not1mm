#!/usr/bin/env python3

# pylint: disable=unused-import, c-extension-no-member, no-member, invalid-name, too-many-lines, no-name-in-module
# pylint: disable=logging-fstring-interpolation, logging-not-lazy, line-too-long, bare-except

# alt cluster hamqth.com 7300

import datetime
import importlib
import logging
import os
import platform
import signal
import sys
import typing
import uuid
from json import loads
from logging.handlers import RotatingFileHandler
from pathlib import Path
from shutil import copyfile
from typing import Optional

import qdarktheme
from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtCore import QDir, Qt, QByteArray, QEvent, QTimer, QUrl
from PyQt6.QtGui import QFontDatabase, QKeyEvent, QCursor, QMouseEvent, QDesktopServices
from PyQt6.QtWidgets import QFileDialog, QLineEdit, QLabel, QHBoxLayout, QMessageBox, QMenu, QPushButton

import qsourcelogger.fsutils as fsutils
from . import model, contest
from .bandmap import BandMapWindow
from .callprofile import ExternalCallProfileWindow
from .cat import AbstractCat
from .cat.RigState import RigState
from .cat.flrig import CatFlrig
from .cat.manual import CatManual
from .cat.omnirig import CatOmnirig
from .cat.rigctld import CatRigctld
from .checkwindow import CheckWindow
from .contest.AbstractContest import ContestFieldNextLine, ContestField, AbstractContest, DupeType
from .lib import event as appevent, flags, hamutils
from .lib.about import About
from .lib.bigcty import BigCty
from .lib.cwinterface import CW
from .lib.edit_macro import EditMacro
from .lib.edit_opon import OpOn
from .lib.event_model import StationActivated, IntermediateQsoUpdate
from .lib.ham_utility import (
    bearing,
    bearing_with_latlon,
    distance,
    distance_with_latlon,
    getband,
    reciprocol,
    fakefreq, gridtolatlon, calculate_wpx_prefix, get_call_base,
)
from .lib.lookup import HamQTH, QRZlookup, ExternalCallLookupService
from .lib.n1mm import N1MM
from .lib.super_check_partial import SCP
from .lib.version import __version__
from .lib.versiontest import VersionTest
from .logwindow import LogWindow
from .mapwindow import WorldMap
from .model import Contest, Station, QsoLog
from .qsoeditwindow import QsoEditWindow
from .qtcomponents.AdifExport import AdifExport
from .qtcomponents.AdifImport import AdifImport
from .qtcomponents.CabrilloExport import CabrilloExport
from .qtcomponents.ContestEdit import ContestEdit
from .qtcomponents.ContestFieldEventFilter import ContestFieldEventFilter
from .qtcomponents.DockWidget import DockWidget
from .qtcomponents.EmacsCursorEventFilter import EmacsCursorEventFilter
from .qtcomponents.QsoEntryField import QsoEntryField
from .qtcomponents.StationSettings import StationSettings
from .qtcomponents.VoiceAudio import VoiceAudio
from .qtcomponents.settings import Settings
from .qtcomponents.spotsend import Spotsend
from .vfo import VfoWindow

qss = """
QFrame#Band_Mode_Frame_CW QLabel, QFrame#Band_Mode_Frame_RTTY QLabel, QFrame#Band_Mode_Frame_SSB QLabel {
    font-size: 11pt;
    font-family: 'Roboto Mono';
}

QFrame#Button_Row1 QPushButton, QFrame#Button_Row2 QPushButton {
    font-size: 11pt;
    font-family: 'Roboto Mono';
}

#MainWindow #centralwidget QFrame QLineEdit {
    font-family: 'Roboto Mono';
    font-size: 26pt;
    border-bottom-width: 2px;
    padding: 0;
}
#MainWindow #centralwidget QFrame QLineEdit#callsign_input {
    text-transform: uppercase;
}

#MainWindow #Band_Mode_Frame_SSB QLabel, #MainWindow #Band_Mode_Frame_RTTY QLabel, #MainWindow #Band_Mode_Frame_CW QLabel {
    border-radius: 4px;
}
"""
logger = logging.getLogger("__main__")

_ESCAPE_DOUBLE_TAP_TIME_MS = 200

class MainWindow(QtWidgets.QMainWindow):

    contest: Contest = None
    contest_plugin: AbstractContest = None
    contest_fields: dict[str:QsoEntryField] = {}
    contact: QsoLog = None

    button_cmd_esc: QPushButton
    button_cmd_wipe: QPushButton
    button_cmd_save: QPushButton
    button_cmd_edit: QPushButton
    button_cmd_mark: QPushButton
    button_cmd_spot: QPushButton
    button_cmd_qrz: QPushButton

    pref = None
    station: Station = None
    current_op: str = None
    current_mode = ""
    current_band = ""

    cw = None
    look_up: Optional[ExternalCallLookupService] = None
    run_state = False
    fkeys = {}
    about_dialog = None
    edit_macro_dialog = None
    configuration_dialog = None
    opon_dialog = None

    radio_state: RigState = RigState(error="not connected")
    rig_control: AbstractCat = None
    worked_list = {}
    cw_entry_visible = False
    last_focus = None
    cw_text_previous_value = ""
    radio_icon: QLabel

    qso_row1: QHBoxLayout
    qso_row2: QHBoxLayout
    qso_row3: QHBoxLayout
    callsign_entry: QsoEntryField
    rst_sent_entry: QsoEntryField
    rst_received_entry: QsoEntryField

    """points to the input field that should be focused when the space bar is pressed in the callsign field"""
    callsign_space_to_input: QLineEdit
    space_character_removal_queue = []

    log_window: DockWidget = None
    check_window: DockWidget = None
    bandmap_window: DockWidget = None
    vfo_window: DockWidget = None
    profile_window: DockWidget = None
    qso_edit_window: QsoEditWindow = None
    map_window: WorldMap = None

    n1mm: N1MM = None

    call_change_debounce_timer = False
    dx_entity: QLabel
    flag_label: QLabel

    audio_thread: VoiceAudio = None

    last_escape_datetime: datetime.datetime = None

    bigcty = BigCty(fsutils.APP_DATA_PATH / 'cty.json')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("MainWindow: __init__")

        appevent.register(appevent.GetActiveContest, self.event_get_contest_status)
        appevent.register(appevent.Tune, self.event_tune)
        appevent.register(appevent.ExternalLookupResult, self.event_external_call_lookup)
        appevent.register(appevent.ContestActivated, self.activate_contest)
        appevent.register(appevent.StationActivated, self.activate_station)
        appevent.register(appevent.RadioState, self.event_radio_state)

        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

        data_path = fsutils.APP_DATA_PATH / "main.ui"
        uic.loadUi(data_path, self)

        self.cw_entry.hide()
        self.mscp = SCP(fsutils.APP_DATA_PATH)

        self.dupe_indicator.hide()
        self.cw_speed.valueChanged.connect(self.cwspeed_spinbox_changed)

        self.cw_entry.textChanged.connect(self.handle_cw_text_change)
        self.cw_entry.returnPressed.connect(self.toggle_cw_entry)

        self.actionCW_Macros.triggered.connect(self.cw_macros_state_changed)
        self.actionDark_Mode.triggered.connect(self.dark_mode_state_changed)
        self.actionCommand_Buttons.triggered.connect(self.command_buttons_state_change)
        self.actionLog_Window.triggered.connect(self.launch_log_window)
        self.actionBandmap.triggered.connect(self.launch_bandmap_window)
        self.actionCheck_Window.triggered.connect(self.launch_check_window)
        self.actionExternalProfile_Window.triggered.connect(self.launch_profile_image_window)
        self.actionQsoedit_Window.triggered.connect(self.launch_qso_edit_window)
        self.actionMap_Window.triggered.connect(self.launch_map_window)
        self.actionVFO.triggered.connect(self.launch_vfo)
        self.actionRecalculate_Mults.triggered.connect(self.recalculate_mults)

        self.actionGenerate_Cabrillo.triggered.connect(self.generate_cabrillo)
        self.actionGenerate_ADIF.triggered.connect(self.generate_adif)
        self.actionImport_ADIF.triggered.connect(self.action_import_adif)

        self.actionConfiguration_Settings.triggered.connect(
            self.edit_configuration_settings
        )
        self.actionStationSettings.triggered.connect(self.edit_station_settings)

        self.actionEdit_Current_Contest.triggered.connect(self.edit_contest)

        self.actionNew_Database.triggered.connect(self.prompt_new_database_file)
        self.actionOpen_Database.triggered.connect(self.prompt_open_database_file)

        self.actionEdit_Macros.triggered.connect(self.edit_cw_macros)

        self.actionAbout.triggered.connect(self.show_about_dialog)
        self.actionHotKeys.triggered.connect(self.show_key_help)
        self.actionHelp.triggered.connect(self.show_help_dialog)
        self.actionUpdate_CTY.triggered.connect(self.check_for_new_cty)
        self.actionUpdate_MASTER_SCP.triggered.connect(self.update_masterscp)
        self.actionQuit.triggered.connect(self.quit_app)

        self.pushButton_run.clicked.connect(self.run_button_clicked)
        self.pushButton_sp.clicked.connect(self.sp_button_clicked)
        self.score.setText("0")

        icon_path = fsutils.APP_DATA_PATH

        self.radio_grey = QtGui.QPixmap(str(icon_path / "radio_grey.png"))
        self.radio_red = QtGui.QPixmap(str(icon_path / "radio_red.png"))
        self.radio_green = QtGui.QPixmap(str(icon_path / "radio_green.png"))
        self.radio_ptt = QtGui.QPixmap(str(icon_path / "radio_ptt.png"))
        self.radio_icon.setPixmap(self.radio_grey)

        self.F1.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F1.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F1))
        self.F1.clicked.connect(lambda x: self.process_function_key(self.F1))
        self.F2.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F2.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F2))
        self.F2.clicked.connect(lambda x: self.process_function_key(self.F2))
        self.F3.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F3.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F3))
        self.F3.clicked.connect(lambda x: self.process_function_key(self.F3))
        self.F4.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F4.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F4))
        self.F4.clicked.connect(lambda x: self.process_function_key(self.F4))
        self.F5.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F5.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F5))
        self.F5.clicked.connect(lambda x: self.process_function_key(self.F5))
        self.F6.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F6.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F6))
        self.F6.clicked.connect(lambda x: self.process_function_key(self.F6))
        self.F7.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F7.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F7))
        self.F7.clicked.connect(lambda x: self.process_function_key(self.F7))
        self.F8.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F8.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F8))
        self.F8.clicked.connect(lambda x: self.process_function_key(self.F8))
        self.F9.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F9.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F9))
        self.F9.clicked.connect(lambda x: self.process_function_key(self.F9))
        self.F10.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F10.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F10))
        self.F10.clicked.connect(lambda x: self.process_function_key(self.F10))
        self.F11.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F11.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F11))
        self.F11.clicked.connect(lambda x: self.process_function_key(self.F11))
        self.F12.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.F12.customContextMenuRequested.connect(lambda x: self.edit_macro(self.F12))
        self.F12.clicked.connect(lambda x: self.process_function_key(self.F12))

        self.cw_band_160.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 160, "CW")
        self.cw_band_80.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 80, "CW")
        self.cw_band_40.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 40, "CW")
        self.cw_band_20.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 20, "CW")
        self.cw_band_15.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 15, "CW")
        self.cw_band_10.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 10, "CW")
        self.cw_band_6.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 6, "CW")
        self.cw_band_2.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 2, "CW")
        self.cw_band_125.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 222, "CW")
        self.cw_band_70cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 432, "CW")
        self.cw_band_33cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 902, "CW")
        self.cw_band_23cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 1240, "CW")

        self.ssb_band_160.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 160, "SSB")
        self.ssb_band_80.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 80, "SSB")
        self.ssb_band_40.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 40, "SSB")
        self.ssb_band_20.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 20, "SSB")
        self.ssb_band_15.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 15, "SSB")
        self.ssb_band_10.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 10, "SSB")
        self.ssb_band_6.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 6, "SSB")
        self.ssb_band_2.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 2, "SSB")
        self.ssb_band_125.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 222, "SSB")
        self.ssb_band_70cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 432, "SSB")
        self.ssb_band_33cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 902, "SSB")
        self.ssb_band_23cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 1240, "SSB")

        self.rtty_band_160.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 160, "RTTY")
        self.rtty_band_80.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 80, "RTTY")
        self.rtty_band_40.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 40, "RTTY")
        self.rtty_band_20.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 20, "RTTY")
        self.rtty_band_15.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 15, "RTTY")
        self.rtty_band_10.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 10, "RTTY")
        self.rtty_band_6.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 6, "RTTY")
        self.rtty_band_2.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 2, "RTTY")
        self.rtty_band_125.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 222, "RTTY")
        self.rtty_band_70cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 432, "RTTY")
        self.rtty_band_33cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 902, "RTTY")
        self.rtty_band_23cm.mousePressEvent = lambda x: self.change_to_band_and_mode(x, 1240, "RTTY")

        self.band_indicators_cw = {
            "160": self.cw_band_160,
            "80": self.cw_band_80,
            "40": self.cw_band_40,
            "20": self.cw_band_20,
            "15": self.cw_band_15,
            "10": self.cw_band_10,
            "6": self.cw_band_6,
            "2": self.cw_band_2,
            "1.25": self.cw_band_125,
            "70cm": self.cw_band_70cm,
            "33cm": self.cw_band_33cm,
            "23cm": self.cw_band_23cm,
        }

        self.band_indicators_ssb = {
            "160": self.ssb_band_160,
            "80": self.ssb_band_80,
            "40": self.ssb_band_40,
            "20": self.ssb_band_20,
            "15": self.ssb_band_15,
            "10": self.ssb_band_10,
            "6": self.ssb_band_6,
            "2": self.ssb_band_2,
            "1.25": self.ssb_band_125,
            "70cm": self.ssb_band_70cm,
            "33cm": self.ssb_band_33cm,
            "23cm": self.ssb_band_23cm,
        }

        self.band_indicators_rtty = {
            "160": self.rtty_band_160,
            "80": self.rtty_band_80,
            "40": self.rtty_band_40,
            "20": self.rtty_band_20,
            "15": self.rtty_band_15,
            "10": self.rtty_band_10,
            "6": self.rtty_band_6,
            "2": self.rtty_band_2,
            "1.25": self.rtty_band_125,
            "70cm": self.rtty_band_70cm,
            "33cm": self.rtty_band_33cm,
            "23cm": self.rtty_band_23cm,
        }

        self.all_mode_indicators = {
            "CW": self.band_indicators_cw,
            "SSB": self.band_indicators_ssb,
            "RTTY": self.band_indicators_rtty,
        }

        self.button_cmd_esc.clicked.connect(self.cmd_escape_stop)
        self.button_cmd_wipe.clicked.connect(self.clearinputs, Qt.ConnectionType.QueuedConnection)
        self.button_cmd_edit.clicked.connect(self.launch_qso_edit_window, Qt.ConnectionType.QueuedConnection)
        self.button_cmd_mark.clicked.connect(self.cmd_mark, Qt.ConnectionType.QueuedConnection)
        self.button_cmd_spot.clicked.connect(self.cmd_spot, Qt.ConnectionType.QueuedConnection)
        self.button_cmd_save.clicked.connect(self.save_contact, Qt.ConnectionType.QueuedConnection)
        self.button_cmd_qrz.clicked.connect(self.cmd_qrz, Qt.ConnectionType.QueuedConnection)

        app_icon = QtGui.QIcon()
        app_icon.addFile(str(fsutils.APP_DATA_PATH / "qsource-32.png"), QtCore.QSize(32, 32))
        app_icon.addFile(str(fsutils.APP_DATA_PATH / "qsource-128.png"), QtCore.QSize(128, 128))
        app_icon.addFile(str(fsutils.APP_DATA_PATH / "qsource-512.png"), QtCore.QSize(512, 512))
        self.setWindowIcon(app_icon)

        self.readpreferences()
        db_path = self.pref.get("current_database", fsutils.USER_DATA_PATH / 'qsodefault.db')
        if not self.pref.get("current_database", None):
            self.pref["current_database"] = db_path
            fsutils.write_settings({"current_database": str(db_path)})
        model.persistent.loadPersistantDb(db_path)

        if not DEBUG_ENABLED:
            if VersionTest(__version__).test():
                self.show_message_box(
                    "There is a newer version of qsourcelogger available.\n"
                    "You can udate to the current version by using:\npip install -U qsourcelogger"
                )

        self.callsign_entry = QsoEntryField('callsign', 'Callsign', self.centralwidget)
        self.callsign_entry.input_field.setProperty('field_config', ContestField(name="call", display_label="Callsign"))
        self.rst_sent_entry = QsoEntryField('rst_sent', 'RST Snt', self.centralwidget)
        self.rst_received_entry = QsoEntryField('rst_rcvd', 'Rcv RST', self.centralwidget)
        self.callsign_entry.input_field.setMaxLength(20)
        self.callsign_entry.input_field.textEdited.connect(self.callsign_changed)
        self.callsign_entry.input_field.returnPressed.connect(self.save_contact)
        self.callsign_entry.input_field.editingFinished.connect(self.callsign_editing_finished)
        self.callsign_entry.input_field.focused.connect(self.handle_input_focus, Qt.ConnectionType.QueuedConnection)

        self.rst_sent_entry.input_field.returnPressed.connect(self.save_contact)
        self.rst_sent_entry.input_field.focused.connect(self.handle_input_focus, Qt.ConnectionType.QueuedConnection)
        self.rst_received_entry.input_field.returnPressed.connect(self.save_contact)
        self.rst_received_entry.input_field.focused.connect(self.handle_input_focus, Qt.ConnectionType.QueuedConnection)

        self.rst_sent_entry.input_field.setText("59")
        self.rst_received_entry.input_field.setText("59")

        self.qso_field_event_filter = ContestFieldEventFilter(self.handle_input_change, parent=self)

        for entry in [self.callsign_entry, self.rst_received_entry, self.rst_sent_entry]:
            entry.input_field.installEventFilter(self.qso_field_event_filter)
            if self.pref.get('interface_emacs', False):
                entry.input_field.installEventFilter(EmacsCursorEventFilter(parent=entry.input_field))

        self.read_cw_macros()
        self.open_database()

        self.centralwidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.centralwidget.customContextMenuRequested.connect(self.context_menu)

    def open_database(self):
        station_id = self.pref.get('active_station_id', None)
        if station_id:
            self.station = Station.select().where(Station.id == station_id).get_or_none()
            if self.station is None:
                del self.pref['active_station_id']
                fsutils.write_settings({'active_station_id': None})

        contest_id = self.pref.get('active_contest_id', None)
        if contest_id:
            self.contest = Contest.select().where(Contest.id == contest_id).get_or_none()
            if self.contest is None:
                del self.pref['active_contest_id']
                fsutils.write_settings({'active_contest_id': None})

        if not self.station:
            fsutils.write_settings({"active_station_id": None})
            # the app menu doesn't load if a dialog is opened in the same qt loading thread
            QTimer.singleShot(10, self.edit_station_settings)
        else:
            if not self.contest:
                fsutils.write_settings({"active_contest_id": None})
            appevent.emit(appevent.StationActivated(self.station))
            if self.contest:
                appevent.emit(appevent.ContestActivated(self.contest))

    def context_menu(self):
        cat_name = 'CAT not configured'
        if self.pref.get("cat_enable_flrig", False):
            cat_name = 'flrig'
        if self.pref.get("cat_enable_rigctld", False):
            cat_name = 'rigctld'
        elif self.pref.get("cat_enable_omnirig", False):
            cat_name = 'omnirig'
        elif self.pref.get("cat_enable_hamlib", False):
            cat_name = 'hamlib'

        menu = QMenu(self)
        bands = menu.addAction("Edit Bands")
        radio_parent = menu.addMenu("Active Radio")
        radio_manual = radio_parent.addAction("Manual Radio")
        radio_manual.setCheckable(True)
        radio_cat = radio_parent.addAction(cat_name)

        if cat_name != 'CAT not configured':
            radio_cat.setCheckable(True)
            radio_cat.setChecked(not self.pref.get("cat_enable_manual", False))

        radio_manual.setChecked(self.pref.get("cat_enable_manual", False))
        if self.pref.get("cat_enable_manual", False):
            radio_cat.triggered.connect(self.toggle_manual_rig)
        else:
            radio_manual.triggered.connect(self.toggle_manual_rig)

        bands.triggered.connect(lambda: self.edit_configuration_settings(show_tab='bands_tab'))

        menu.exec(QCursor.pos())

    def toggle_manual_rig(self):
        self.pref['cat_enable_manual'] = not self.pref.get("cat_enable_manual", False)
        fsutils.write_settings({'cat_enable_manual': self.pref['cat_enable_manual']})
        logger.info("removing pins for radio-based fields to reduce likelihood of incorrect entry")
        pinned_fields: dict = self.contest.get_setting("pinned_fields", {})
        if 'freq' in pinned_fields:
            del pinned_fields['freq']
        if 'mode' in pinned_fields:
            del pinned_fields['mode']
        if 'submode' in pinned_fields:
            del pinned_fields['submode']
        self.contest.merge_settings({'pinned_fields': pinned_fields})
        self.setup_rig_control()

    def activate_station(self, event: StationActivated):
        self.station = event.station
        self.current_op = self.station.callsign
        self.make_op_dir()
        if not self.contest:
            # show contest config window
            QTimer.singleShot(10, self.edit_contest)

    def handle_input_focus(self, source: QLineEdit) -> None:
        if (source == self.rst_received_entry.input_field or source == self.rst_sent_entry.input_field) and (source.text() == '59' or source.text() == '599'):
            source.setSelection(1, 1)
        else:
            # behaviour for focusing into an entry field
            if self.pref.get('interface_entry_focus_select', True):
                source.setFocus()
            else:
                source.deselect()
                source.end(False)

        # clear up any spaces that need to be removed as a result of pressing the space bar
        while self.space_character_removal_queue:
            input, text = self.space_character_removal_queue.pop()
            input.setText(text)

    def handle_input_change(self, source: QLineEdit, event: QEvent) -> None:
        """check for "space does tab" fields and if the space bar is pressed then execute a focus to next field"""
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            conf: ContestField = source.property('field_config')
            # the call field has special space behaviour elsewhere
            if conf and conf.name != 'call' and conf and conf.space_tabs:
                # the text currently does not have the space character in it
                self.handle_space_tab(conf.name, source)
        if event.type() == QEvent.Type.FocusOut and self.qso_edit_window and self.contact:
            conf: ContestField = source.property('field_config')
            if conf:
                qso_value = self.contest_fields[conf.name].input_field.text()
                if conf.name == 'call':
                    qso_value = qso_value.strip().upper()
                if getattr(self.contact, conf.name) != qso_value:
                    setattr(self.contact, conf.name, qso_value)
                    self.qso_edit_window.set_qso(self.contact)

    def set_radio_icon(self, state: int) -> None:
        """
        Change CAT icon state

        Parameters
        ----------
        state : int
        The state of the CAT icon. 0 = grey, 1 = red, 2 = green
        """
        displaystate = [self.radio_grey, self.radio_red, self.radio_green, self.radio_ptt]
        try:
            self.radio_icon.setPixmap(displaystate[state])
        except (IndexError, TypeError) as err:
            logger.debug(err)

    def toggle_cw_entry(self) -> None:
        """
        Toggle the CW entry field on and off.
        """

        self.cw_entry_visible = not self.cw_entry_visible
        if self.cw_entry_visible:
            self.last_focus = app.focusWidget()
            self.cw_entry.clear()
            self.cw_entry.show()
            self.cw_entry.setFocus()
            return
        self.cw_entry.hide()
        self.cw_entry.clearFocus()
        if self.last_focus:
            self.last_focus.setFocus()

    def handle_cw_text_change(self) -> None:
        newtext = self.cw_entry.text()
        if len(newtext) < len(self.cw_text_previous_value):
            # self.send_backspace()
            self.cw_text_previous_value = newtext
            return
        if self.cw is not None:
            self.cw.sendcw(newtext[len(self.cw_text_previous_value):])
        self.cw_text_previous_value = newtext

    def change_to_band_and_mode(self, event: QMouseEvent, band: int, mode: str) -> None:
        """
        Gets a sane frequency for the chosen band and mode.
        Then changes to that,

        Parameters
        ----------
        band : int
        mode : str
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.contact.time_on:
                self.show_message_box("QSO in progress! Wipe it or Save it before switching bands.")
            elif mode in ["CW", "SSB", "RTTY"]:
                freq = fakefreq(str(band), mode)
                self.change_freq(freq)
                self.change_mode(mode)
        else:
            super().mousePressEvent(event)

    def quit_app(self) -> None:
        app.quit()

    def show_message_box(self, message: str) -> None:
        """
        Displays a dialog box with a message.
        """

        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message_box.setText(message)
        message_box.setWindowTitle("Information")
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        _ = message_box.exec()

    def show_about_dialog(self) -> None:
        self.about_dialog = About(fsutils.APP_DATA_PATH)
        self.about_dialog.donors.setSource(
            QtCore.QUrl.fromLocalFile(f"{fsutils.APP_DATA_PATH / 'donors.html'}")
        )

        self.about_dialog.open()

    def show_help_dialog(self):
        self.about_dialog = About(fsutils.APP_DATA_PATH)

        self.about_dialog.setWindowTitle("Help")
        self.about_dialog.setGeometry(0, 0, 800, 600)
        self.about_dialog.donors.setSource(
            QtCore.QUrl.fromLocalFile(str(fsutils.APP_DATA_PATH / "qsourcelogger.html"))
        )
        self.about_dialog.open()

    def update_masterscp(self) -> None:
        """
        Tries to update the MASTER.SCP file when the menu item is clicked.

        Displays a dialog advising if it was updated.
        """

        if self.mscp.update_masterscp():
            self.show_message_box("MASTER.SCP file updated.")
            return
        self.show_message_box("MASTER.SCP could not be updated.")

    def edit_configuration_settings(self, show_tab:str = None) -> None:
        """
        Configuration Settings was clicked
        """
        self.callsign_entry.input_field.setFocus()
        self.configuration_dialog = Settings(fsutils.APP_DATA_PATH, self.pref)
        self.configuration_dialog.show()
        if show_tab:
            self.configuration_dialog.show_tab(show_tab)
        self.configuration_dialog.updated.connect(self.readpreferences)

    def prompt_open_database_file(self) -> None:
        current_file = self.pref.get("current_database", None)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Existing Database File",
            os.path.dirname(current_file),
            "Database (*.db)",
            options=QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.DontConfirmOverwrite,
        )
        if filename:
            self.pref["current_database"] = filename
            fsutils.write_settings({"current_database": filename})
            model.loadPersistantDb(filename)
            self.open_database()

    def prompt_new_database_file(self) -> None:
        current_file = self.pref.get("current_database", None)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Create a New Database File",
            str(Path(os.path.dirname(current_file)) / f"qsolog_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.db"),
            "Database (*.db)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if filename:
            if filename[-3:] != ".db":
                filename += ".db"
            filepath = Path(filename)

            if filepath.exists():
                if filepath.is_dir():
                    logger.error("Cannot use a directory as a new db file")
                    return
                elif filepath.exists():
                    # when creating a new db if the chosen file is is exsting, back it up
                    filepath.rename(f"{str(filepath)}_{datetime.datetime.now().strftime('YYYMMDD_hhmm')}_backup")

            self.pref["current_database"] = filename
            fsutils.write_settings({"current_database": filename})
            model.loadPersistantDb(filename)
            self.open_database()

    def edit_contest(self) -> None:
        contest_dialog = ContestEdit(fsutils.APP_DATA_PATH, parent=self)
        contest_dialog.open()

    def activate_contest(self, event: appevent.ContestActivated) -> None:
        self.pref['active_contest_id'] = event.contest.id
        self.contest = event.contest
        self.contest_plugin = contest.contests_by_cabrillo_id[self.contest.fk_contest_meta.cabrillo_name](self.contest)
        self.load_contest()

    def set_blank_qso(self):
        self.contact = QsoLog()
        self.contact.fk_contest = self.contest
        self.contact.fk_station = self.station

        self.contact.station_callsign = self.station.callsign
        self.contact.my_arrl_sect = self.station.arrl_sect

        self.contact.my_antenna = self.station.antenna
        self.contact.my_rig = self.station.rig

        self.contact.my_gridsquare = self.station.gridsquare
        self.contact.my_gridsquare_ext = self.station.gridsquare_ext
        self.contact.my_lat = self.station.latitude
        self.contact.my_lon = self.station.longitude
        self.contact.my_altitude = self.station.altitude
        self.contact.my_cq_zone = self.station.cq_zone
        self.contact.my_dxcc = self.station.dxcc

        self.contact.my_itu_zone = self.station.itu_zone

        self.contact.my_name = self.station.name
        self.contact.my_street = self.station.street1
        if self.station.street2:
            self.contact.my_street += self.station.street2

        self.contact.my_city = self.station.city
        self.contact.my_state = self.station.state
        self.contact.my_postal_code = self.station.postal_code
        self.contact.my_county = self.station.county
        self.contact.my_country = self.station.country

        self.contact.my_iota = self.station.iota
        self.contact.my_iota_island_id = self.station.iota_island_id
        self.contact.my_pota_ref = self.station.pota_ref

        self.contact.my_fists = self.station.fists
        self.contact.my_usaca_counties = self.station.usaca_counties
        self.contact.my_vucc_grids = self.station.vucc_grids
        self.contact.my_wwff_ref = self.station.wwff_ref
        self.contact.my_sota_ref = self.station.sota_ref
        self.contact.my_sig = self.station.sig
        self.contact.my_sig_info = self.station.sig_info

        for field_name, value in self.contest.get_setting("pinned_fields", {}).items():
            setattr(self.contact, field_name, value)

        self.contest_plugin.intermediate_qso_update(self.contact, None)

    def load_contest(self) -> None:
        assert self.contest
        assert self.contest_plugin
        # clear out previous contest
        for layout in [self.qso_row1, self.qso_row2, self.qso_row3]:
            for i in reversed(range(layout.count())):
                widgetToRemove = layout.itemAt(i).widget()
                # remove it from the layout list
                layout.removeWidget(widgetToRemove)
                # remove it from the gui
                widgetToRemove.setParent(None)
                if widgetToRemove not in [self.callsign_entry, self.rst_sent_entry, self.rst_received_entry]:
                    widgetToRemove.deleteLater()

        # merge entry field list from contest plugin with any additional customized fields defined by the user
        qso_fields = list(self.contest_plugin.get_qso_fields())
        is_callspace_space_target_defined = any([x.callsign_space_to_here for x in qso_fields])
        user_tab_order = []
        for user_field in self.contest.get_setting('user_fields', []):
            if user_field['name'] == '[NextLine]':
                qso_fields.append(ContestFieldNextLine())
            else:
                qso_fields.append(ContestField(name=user_field['name'], display_label=user_field['display_label'],
                                               space_tabs=user_field['space_tabs'], stretch_factor=user_field['stretch_factor'],
                                               max_chars=user_field['max_chars'], callsign_space_to_here=not is_callspace_space_target_defined))

                user_tab_order.append(user_field['name'])
                is_callspace_space_target_defined = True

        # define and populate input widgets for contest fields
        # callsign is always first.
        self.qso_row1.addWidget(self.callsign_entry, 4)
        row = self.qso_row1
        self.contest_fields = {'call': self.callsign_entry}
        self.callsign_space_to_input = None

        for f in qso_fields:
            if f.__class__ == ContestFieldNextLine:
                row = self.qso_row2 if row == self.qso_row1 else self.qso_row3
                continue

            field: QsoEntryField
            if f.name == 'rst_sent':
                field = self.rst_sent_entry
            elif f.name == 'rst_rcvd':
                field = self.rst_received_entry
            else:
                field = QsoEntryField(f.name, f.display_label, parent=self.centralwidget)
            row.addWidget(field, f.stretch_factor)
            if f.name not in ['rst_rcvd', 'rst_sent']:
                field.input_field.installEventFilter(self.qso_field_event_filter)
                if self.pref.get('interface_emacs', False):
                    field.input_field.installEventFilter(EmacsCursorEventFilter(parent=field))
                field.input_field.returnPressed.connect(self.save_contact)
                field.input_field.focused.connect(self.handle_input_focus, Qt.ConnectionType.QueuedConnection)

            if f.callsign_space_to_here:
                self.callsign_space_to_input = field.input_field
            field.input_field.setProperty('field_config', f)
            field.input_field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            field.input_field.setMaxLength(f.max_chars)
            self.contest_fields[f.name] = field

        # setup tab order, contests have a change to exclude or skip fields
        tab_order = [x for x in self.contest_plugin.get_tab_order() if x != 'call']
        missing = [x for x in tab_order if x not in self.contest_fields.keys()]
        if missing:
            logger.warning(f"contest plugin defines a tab order for qso fields it does not define: {missing}")
        for x in missing:
            tab_order.remove(x)

        tab_order.insert(0, 'call')
        tab_order.extend(user_tab_order)
        for i in range(1, len(tab_order)):
            current = self.contest_fields[tab_order[i-1]].input_field
            focus_next = self.contest_fields[tab_order[i]].input_field
            current.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            focus_next.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setTabOrder(current, focus_next)

        self.hide_band_mode(self.contest.mode_category)
        if self.contest.mode_category == "CW":
            self.setmode("CW")
            band = getband(str(self.radio_state.vfotx_hz or 0))
            self.set_band_indicator(band)
        elif self.contest.mode_category == "SSB":
            self.setmode("SSB")
            if (self.radio_state.vfotx_hz or 0) > 10000000:
                self.radio_state.mode = "USB"
            else:
                self.radio_state.mode = "LSB"
            band = getband(str(self.radio_state.vfotx_hz or 0))
            self.set_band_indicator(band)

        self.set_window_title()

        if 'CW' in self.contest.mode_category:
            self.cw_speed.show()
        else:
            self.cw_speed.hide()

        self.clearinputs()
        self.callsign_entry.input_field.setFocus()
        if self.qso_edit_window:
            self.qso_edit_window.set_qso(self.contact)

    def check_for_new_cty(self) -> None:
        """
        Checks for a new cty.dat file.
        The following steps are performed:
        - Check if the file exists
        - Check if the file is newer than the one in the data folder
        - If the file is newer, load it and show a message box
        """

        try:
            cty = BigCty(fsutils.APP_DATA_PATH / "cty.json")
            updated = cty.update()
            if updated:
                cty.dump(fsutils.APP_DATA_PATH / "cty.json")
                self.show_message_box("cty file updated.")
                with open(
                        fsutils.APP_DATA_PATH / "cty.json", "rt", encoding="utf-8"
                ) as ctyfile:
                    globals()["CTYFILE"] = loads(ctyfile.read())
            else:
                self.show_message_box("CTY file is up to date.")
        except:
            logger.exception("cty file update")
            self.show_message_box("An Error occured updating file.")

    def hide_band_mode(self, the_mode: str) -> None:
        """
        Hide the unused band and mode frames.
        Show the used band and mode frames.

        Parameters
        ----------
        the_mode : str
        The mode to show.
        """

        logger.debug("%s", f"{the_mode}")
        self.Band_Mode_Frame_CW.hide()
        self.Band_Mode_Frame_SSB.hide()
        self.Band_Mode_Frame_RTTY.hide()
        modes = {
            "CW": (self.Band_Mode_Frame_CW,),
            "SSB": (self.Band_Mode_Frame_SSB,),
            "RTTY": (self.Band_Mode_Frame_RTTY,),
            "PSK": (self.Band_Mode_Frame_RTTY,),
            "SSB+CW": (self.Band_Mode_Frame_CW, self.Band_Mode_Frame_SSB),
            "BOTH": (self.Band_Mode_Frame_CW, self.Band_Mode_Frame_SSB),
            "DIGITAL": (self.Band_Mode_Frame_RTTY,),
            "SSB+CW+DIGITAL": (
                self.Band_Mode_Frame_RTTY,
                self.Band_Mode_Frame_CW,
                self.Band_Mode_Frame_SSB,
            ),
            "FM": (self.Band_Mode_Frame_SSB,),
        }
        frames = modes.get(the_mode)
        if frames:
            for frame in frames:
                frame.show()

    def show_key_help(self) -> None:
        """
        Show help box for hotkeys.
        Provides a list of hotkeys and what they do.
        """

        self.show_message_box(
            "[Esc]\tClears the input fields of any text.\n"
            "[CTRL-Esc]\tStops cwdaemon from sending Morse.\n"
            "[PgUp]\tIncreases the cw sending speed.\n"
            "[PgDown]\tDecreases the cw sending speed.\n"
            "[Arrow-Up] Jump to the next spot above the current VFO cursor\n"
            "\tin the bandmap window (CAT Required).\n"
            "[Arrow-Down] Jump to the next spot below the current\n"
            "\tVFO cursor in the bandmap window (CAT Required).\n"
            "[TAB]\tMove cursor to the right one field.\n"
            "[Shift-Tab]\tMove cursor left One field.\n"
            "[SPACE]\tWhen in the callsign field, will move the input to the\n"
            "\tfirst field needed for the exchange.\n"
            "[Enter]\tSubmits the fields to the log.\n"
            "[F1-F12]\tSend (CW or Voice) macros.\n"
            "[CTRL-G]\tTune to a spot matching partial text in the callsign\n"
            "\tentry field (CAT Required).\n"
            "[CTRL-M]\tMark Callsign to the bandmap window to work later."
            "[CTRL-S]\tSpot Callsign to the cluster.\n"
            "[CTRL-SHIFT-K] Open CW text input field.\n"
        )

    def recalculate_mults(self) -> None:
        """Recalculate Multipliers"""
        self.contest.recalculate_mults(self)
        self.clearinputs()

    def launch_log_window(self) -> None:
        if not self.log_window:
            self.log_window = LogWindow()
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_window)
        self.log_window.show()

    def launch_bandmap_window(self) -> None:
        """Launch the bandmap window"""
        if not self.bandmap_window:
            self.bandmap_window = BandMapWindow()
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.bandmap_window)

        self.bandmap_window.show()

    def launch_check_window(self) -> None:
        """Launch the check window"""
        if not self.check_window:
            self.check_window = CheckWindow()
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.check_window)
        self.check_window.show()

    def launch_profile_image_window(self) -> None:
        if not self.profile_window:
            self.profile_window = ExternalCallProfileWindow()
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.profile_window)
            self.profile_window.closed.connect(self.handle_dock_closed)
        self.profile_window.show()

    def launch_map_window(self) -> None:
        if not self.map_window:
            self.map_window = WorldMap()
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.map_window)
            self.map_window.setFloating(True)
            self.map_window.closed.connect(self.handle_dock_closed)
        self.map_window.show()

    def launch_qso_edit_window(self) -> None:
        if not self.qso_edit_window:
            self.qso_edit_window = QsoEditWindow(None, contest=self.contest)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.qso_edit_window)
            self.qso_edit_window.setFloating(True)
            self.qso_edit_window.closed.connect(self.handle_dock_closed)
            self.qso_edit_window.setWindowTitle("QSO In Progress")
            self.qso_edit_window.model.edited.connect(self.edit_window_data_change)
            self.qso_edit_window.set_qso(self.contact)
        self.qso_edit_window.show()
        self.qso_edit_window.setWindowState(Qt.WindowState.WindowActive)

    def launch_vfo(self) -> None:
        """Launch the VFO window"""
        if not self.vfo_window:
            self.vfo_window = VfoWindow()
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.vfo_window)
        self.vfo_window.show()

    def handle_dock_closed(self, event: typing.Optional[QtGui.QCloseEvent]):
        if event and event.source and event.source == self.profile_window:
            self.removeDockWidget(self.profile_window)
            self.profile_window = None
        if event and event.source and event.source == self.qso_edit_window:
            self.removeDockWidget(self.qso_edit_window)
            self.qso_edit_window = None
        if event and event.source and event.source == self.map_window:
            self.removeDockWidget(self.map_window)
            self.map_window = None

    def clear_band_indicators(self) -> None:
        """
        Clear the indicators.
        """
        for _, indicators in self.all_mode_indicators.items():
            for _, indicator in indicators.items():
                indicator.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
                indicator.setStyleSheet(None)


    def set_band_indicator(self, band: str) -> None:
        """
        Set the band indicator

        Parameters:
        ----------
        band: str
        band to set indicator for
        """
        if band and self.current_mode:
            self.clear_band_indicators()
            indicator = self.all_mode_indicators[self.current_mode].get(band, None)
            if indicator:
                #indicator.setFrameShape(QtWidgets.QFrame.Shape.Box)
                indicator.setStyleSheet("QLabel {color:white; background-color : green;}")

    def closeEvent(self, event) -> None:
        if self.rig_control:
            self.rig_control.close()
        window_state = {
            "window_state": bytes(self.saveState(1).toHex()).decode('ascii'),
            "window_geo": bytes(self.saveGeometry().toHex()).decode('ascii'),
            "window_bandmap_enable": self.bandmap_window and self.bandmap_window.isVisible(),
            "window_check_enable": self.check_window and self.check_window.isVisible(),
            "window_log_enable": self.log_window and self.log_window.isVisible(),
            "window_profile_enable": self.profile_window and self.profile_window.isVisible(),
            "window_qsoedit_enable": self.qso_edit_window and self.qso_edit_window.isVisible(),
            "window_vfo_enable": self.vfo_window and self.vfo_window.isVisible(),
            "window_worldmap_enable": self.map_window and self.map_window.isVisible(),
        }

        fsutils.write_settings(window_state)
        event.accept()

    def cwspeed_spinbox_changed(self) -> None:
        """
        Triggered when value of CW speed in the spinbox changes.
        """
        if self.cw is None:
            return
        if self.cw.servertype == 1:
            self.cw.speed = self.cw_speed.value()
            self.cw.sendcw(f"\x1b2{self.cw.speed}")
        if self.cw.servertype == 2:
            self.cw.set_winkeyer_speed(self.cw_speed.value())

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name

        modifier = event.modifiers()
        if event.key() == Qt.Key.Key_K:
            if self.current_mode == "CW":
                self.toggle_cw_entry()
                return
        if event.key() == Qt.Key.Key_S and modifier == Qt.KeyboardModifier.ControlModifier:
            self.cmd_spot()
            return
        if event.key() == Qt.Key.Key_M and modifier == Qt.KeyboardModifier.ControlModifier:
            self.cmd_mark()
            return
        if event.key() == Qt.Key.Key_G and modifier == Qt.KeyboardModifier.ControlModifier:
            dx = self.callsign_entry.input_field.text()
            if dx:
                appevent.emit(appevent.FindDx(dx))
            return
        if event.key() == Qt.Key.Key_Escape and modifier != Qt.KeyboardModifier.ControlModifier:
            now = datetime.datetime.utcnow()
            if not self.last_escape_datetime or now - self.last_escape_datetime > datetime.timedelta(milliseconds=_ESCAPE_DOUBLE_TAP_TIME_MS):
                # single escape press
                self.cmd_escape_stop()
                self.callsign_entry.input_field.setFocus()
                self.last_escape_datetime = now
            else:
                # escape double tap
                self.clearinputs()
            return
        if event.key() == Qt.Key.Key_Up:
            appevent.emit(appevent.BandmapSpotPrev())
            return
        if event.key() == Qt.Key.Key_Down:
            appevent.emit(appevent.BandmapSpotNext())
            return
        if event.key() == Qt.Key.Key_PageUp and modifier != Qt.KeyboardModifier.ControlModifier:
            if self.cw is not None:
                self.cw.speed += 1
                self.cw_speed.setValue(self.cw.speed)
                if self.cw.servertype == 1:
                    self.cw.sendcw(f"\x1b2{self.cw.speed}")
                if self.cw.servertype == 2:
                    self.cw.set_winkeyer_speed(self.cw_speed.value())
            return
        if event.key() == Qt.Key.Key_PageDown and modifier != Qt.KeyboardModifier.ControlModifier:
            if self.cw is not None:
                self.cw.speed -= 1
                self.cw_speed.setValue(self.cw.speed)
                if self.cw.servertype == 1:
                    self.cw.sendcw(f"\x1b2{self.cw.speed}")
                if self.cw.servertype == 2:
                    self.cw.set_winkeyer_speed(self.cw_speed.value())
            return
        if event.key() == Qt.Key.Key_F1:
            self.process_function_key(self.F1)
        if event.key() == Qt.Key.Key_F2:
            self.process_function_key(self.F2)
        if event.key() == Qt.Key.Key_F3:
            self.process_function_key(self.F3)
        if event.key() == Qt.Key.Key_F4:
            self.process_function_key(self.F4)
        if event.key() == Qt.Key.Key_F5:
            self.process_function_key(self.F5)
        if event.key() == Qt.Key.Key_F6:
            self.process_function_key(self.F6)
        if event.key() == Qt.Key.Key_F7:
            self.process_function_key(self.F7)
        if event.key() == Qt.Key.Key_F8:
            self.process_function_key(self.F8)
        if event.key() == Qt.Key.Key_F9:
            self.process_function_key(self.F9)
        if event.key() == Qt.Key.Key_F10:
            self.process_function_key(self.F10)
        if event.key() == Qt.Key.Key_F11:
            self.process_function_key(self.F11)
        if event.key() == Qt.Key.Key_F12:
            self.process_function_key(self.F12)

    def cmd_spot(self):
        freq = self.radio_state.vfotx_hz
        dx = self.callsign_entry.input_field.text().strip().upper()
        if len(dx) > 3 and freq:
            dialog = Spotsend(self)

            dialog.text_mycall.setText(self.station.callsign)
            dialog.text_dx.setText(self.callsign_entry.input_field.text().upper())
            dialog.text_freq.setText(str(self.radio_state.vforx_hz))
            if 'comment' in self.contest_fields:
                dialog.text_comment.setText(self.contest_fields['comment'].input_field.text())

            dialog.accepted.connect(lambda: appevent.emit(
                appevent.SpotDx(de=dialog.text_mycall.text(),
                                dx=dialog.text_dx.text(),
                                freq_hz=int(dialog.text_freq.text()),
                                comment=dialog.text_comment.text())))
            dialog.open()


    def cmd_mark(self):
        freq = self.radio_state.vfotx_hz
        dx = self.callsign_entry.input_field.text().strip().upper()
        if len(dx) > 2 and freq:
            appevent.emit(appevent.MarkDx(self.station.callsign, dx, freq))

    def cmd_escape_stop(self):
        if self.cw is not None:
            if self.cw.servertype == 1:
                self.cw.sendcw("\x1b4")
                return
        if self.audio_thread:
            self.audio_thread.stop_sound()

    def cmd_qrz(self):
        if len(self.contact.call) > 2:
            url = f'https://www.qrz.com/db/{str(self.contact.call).strip()}'
            QDesktopServices.openUrl(QUrl(url))

    def set_window_title(self) -> None:
        """
        Set window title based on current state.
        """

        vfoa = self.radio_state.vfotx_hz
        if vfoa:
            try:
                vfoa = int(vfoa) / 1000
            except ValueError:
                vfoa = 0.0
        else:
            vfoa = 0.0
        contest_name = ""
        if self.contest:
            contest_name = self.contest.get_display_name()
        line = (
            f"vfoa:{round(vfoa, 2):,g} ".replace(',', '.') +
            f"mode:{self.radio_state.mode} "
            f"OP:{self.current_op} {contest_name} "
            f"- QSOurce v{__version__}"
        )
        self.setWindowTitle(line)

    def clearinputs(self) -> None:
        """
        Clears the text input fields and sets focus to callsign field.
        """

        self.dupe_indicator.hide()
        self.set_blank_qso()
        self.heading_distance.setText("")
        self.dx_entity.setText("")
        self.flag_label.clear()
        if self.contest:
            # TODO multiplier logic unknown
            mults = 0 #self.contest.show_mults(self)
            qsos = QsoLog.select().where(QsoLog.fk_contest == self.contest).count()
            multstring = f"{qsos}/{mults}"
            self.mults.setText(multstring)
            score = self.contest_plugin.calculate_total_points()
            self.score.setText(str(score or '0'))

        for name, field in self.contest_fields.items():
            if name not in ['call', 'rst_sent', 'rst_rcvd']:
                field.input_field.clear()
                # if any values have been pre-filled by the contest plugin, set them in the input fields
                value = getattr(self.contact, name)
                if value:
                    field.input_field.setText(str(value))

        if self.current_mode == "CW":
            self.rst_sent_entry.input_field.setText("599")
            self.rst_received_entry.input_field.setText("599")
        else:
            self.rst_sent_entry.input_field.setText("59")
            self.rst_received_entry.input_field.setText("59")
        self.callsign_entry.input_field.clear()
        self.callsign_entry.input_field.setFocus()

        appevent.emit(appevent.CallChanged(''))
        if self.qso_edit_window:
            self.qso_edit_window.set_qso(self.contact)

    def callsign_editing_finished(self) -> None:
        """
        This signal is invoked after the enter button is pressed so it doesn't conflict with saving a qso.
        This signal is used to handle the "callsign loses focus" event. if the call sign is empty it means the
        qso has been persisted and we can do nothing
        """
        # alt tabbing will trigger this also, not sure if that is correct or not nore how to prevent it
        callsign_value = self.callsign_entry.input_field.text().strip().upper()
        if not callsign_value:
            return
        logger.debug(f'callsign field exit value {callsign_value}')
        self.check_callsign(callsign_value)
        if self.is_dupe_call(callsign_value):
            self.dupe_indicator.show()
        else:
            self.dupe_indicator.hide()
        self.pre_populate_contact()

        self.check_callsign_external(callsign_value)

    def pre_populate_contact(self, notify=True):
        # triggered when callsign of qso is set
        if self.contact.time_on is not None:
            return
        if len(self.callsign_entry.input_field.text()) < 3:
            return

        self.contact.time_on = datetime.datetime.now()

        self.contact.station_callsign = self.contact.fk_station.callsign
        self.contact.call = self.callsign_entry.input_field.text().strip().upper()
        self.contact.freq = self.radio_state.vfotx_hz
        self.contact.band = hamutils.adif.common.convert_freq_to_band((self.contact.freq or 0) / 1000_000)

        # important for dexpediation - split mode - set when radio state indicates split
        if self.radio_state.is_split:
            self.contact.freq_rx = self.radio_state.vforx_hz
            self.contact.band_rx = hamutils.adif.common.convert_freq_to_band((self.contact.freq_rx or 0) / 1000_000)


        self.contact.mode = (self.radio_state.mode or "").upper()
        if self.contact.mode in ['USB', 'LSB']:
            self.contact.submode = self.contact.mode
            self.contact.mode = 'SSB'
        if self.contact.prefix:
            self.contact.wpx_prefix = calculate_wpx_prefix(self.contact.call)
        self.contact.is_run = self.pushButton_run.isChecked()
        self.contact.operator = self.current_op
        self.contact.hostname = platform.node()[:255]
        self.contact.is_original = True

        if self.pref['lookup_name_prefer_qso_history_name']:
            name_from_log = QsoLog.get_name_from_previous_contact(get_call_base(self.contact.call))
            if name_from_log:
                self.contact.name = name_from_log
                if 'name' in self.contest_fields:
                    self.contest_fields['name'].input_field.setText(self.contact.name)

        if notify:
            self.contest_plugin.intermediate_qso_update(self.contact, None)
            appevent.emit(IntermediateQsoUpdate(self.contact))
            if self.qso_edit_window:
                self.qso_edit_window.set_qso(self.contact)

    def save_contact(self) -> None:
        """
        Save contact to database.
        """
        logger.debug("saving contact")
        if self.contest is None:
            self.show_message_box("You have no contest defined.")
            return
        if len(self.callsign_entry.input_field.text()) < 3:
            return
        if not any(char.isdigit() for char in self.callsign_entry.input_field.text()):
            return
        if not any(char.isalpha() for char in self.callsign_entry.input_field.text()):
            return
        self.pre_populate_contact(notify=False)

        self.contact.time_off = datetime.datetime.now()

        for name, field in self.contest_fields.items():
            setattr(self.contact, name, field.input_field.text())

        self.contact.call = self.contact.call.strip().upper()

        self.contact.is_run = self.pushButton_run.isChecked()
        if not self.contact.qso_complete:
            self.contact.qso_complete = 'Y'

        self.contact.contest_id = self.contact.fk_contest.fk_contest_meta.cabrillo_name

        if self.contact.gridsquare and self.station.gridsquare:
            kilometers = distance(self.station.gridsquare, self.contact.gridsquare)
            self.contact.distance = kilometers

        # special comment field features (eg pota/iota/sota references)
        if self.contact.comment:
            source = str(self.contact.comment).strip().lower()
            if source.startswith('pota '):
                pota_ref = source[5:].strip()
                if pota_ref:
                    self.contact.pota_ref = pota_ref
            elif source.startswith('iota '):
                iota_ref = source[5:].strip()
                if iota_ref:
                    self.contact.iota_ref = iota_ref
            elif source.startswith('sota '):
                sota_ref = source[5:].strip()
                if sota_ref:
                    self.contact.sota_ref = sota_ref
            elif source.startswith('wwff '):
                wwff_ref = source[5:].strip()
                if wwff_ref:
                    self.contact.wwff_ref = wwff_ref

        # contest may need to do re calculation or normalization or something
        self.contest_plugin.pre_process_qso_log(self.contact)
        self.contact.points = self.contest_plugin.points_for_qso(self.contact)

        self.contact.id = uuid.uuid4()
        try:
            self.contact.save(force_insert=True)
            self.save_pinned_field_values(self.contact)
            appevent.emit(appevent.QsoAdded(self.contact))
            self.clearinputs()
        except Exception as e:
            logger.exception("error saving qso record")
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Error saving QSO log")
            dlg.setText(str(e))
            dlg.exec()

    def edit_station_settings(self) -> None:
        logger.debug("Station Settings selected")
        station_dialog = StationSettings(fsutils.APP_DATA_PATH, parent=self)
        station_dialog.open()

    def save_pinned_field_values(self, qso: QsoLog):
        if not qso and not qso.id:
            return
        pinned_fields: dict = self.contest.get_setting("pinned_fields", {})
        for field_name in pinned_fields.keys():
            pinned_fields[field_name] = getattr(qso, field_name)
        self.contest.merge_settings({'pinned_fields': pinned_fields})

    def set_dark_mode(self, enabled):
        qdarktheme.setup_theme(theme="dark" if enabled else "light", corner_shape="sharp",
                               additional_qss=qss,
                               custom_colors={
                                   "[light]": {
                                       "foreground": "#141414",
                                       "input.background": "#ffffff",
                                   }
                               }
                               )

        if self.bandmap_window:
            self.bandmap_window.get_settings()
            self.bandmap_window.update()
        if self.log_window:
            QTimer.singleShot(0, self.log_window.load_settings)


    def edit_macro(self, function_key) -> None:
        """
        Show edit macro dialog for function key.

        Parameters
        ----------
        function_key : str
        Function key to edit.
        """

        self.edit_macro_dialog = EditMacro(function_key, fsutils.APP_DATA_PATH)

        self.edit_macro_dialog.accepted.connect(self.edited_macro)
        self.edit_macro_dialog.open()

    def edited_macro(self) -> None:
        """
        Save edited macro to database.
        """

        self.edit_macro_dialog.function_key.setText(
            self.edit_macro_dialog.macro_label.text()
        )
        self.edit_macro_dialog.function_key.setToolTip(
            self.edit_macro_dialog.the_macro.text()
        )
        self.edit_macro_dialog.close()

    def process_macro(self, macro: str) -> str:
        """
        Process CW macro substitutions for contest.

        Parameters
        ----------
        macro : str
        Macro to process.

        Returns
        -------
        str
        Processed macro.
        """

        next_serial = str(self.contact.stx or "1")
        macro = macro.upper()
        macro = macro.replace("#", next_serial)
        macro = macro.replace("{MYCALL}", self.station.callsign)
        macro = macro.replace("{HISCALL}", self.callsign_entry.input_field.text())
        if self.radio_state.mode == "CW":
            macro = macro.replace("{SNT}", self.rst_sent_entry.input_field.text().replace("9", "n"))
        else:
            macro = macro.replace("{SNT}", self.rst_sent_entry.input_field.text())

        for field_name, field in self.contest_fields.items():
            macro.replace(f"{{{field_name}}}", field.input_field.text())

        macro = macro.replace("{EXCH}", self.contact.stx_string or '')

        return macro

    def voice_string(self, the_string: str) -> None:
        self.audio_thread = VoiceAudio(the_string, self.current_op, self.rig_control)
        self.audio_thread.finished.connect(self.audio_finished)
        self.audio_thread.start()

    def audio_finished(self):
        self.audio_thread.deleteLater()
        self.audio_thread = None

    def process_function_key(self, function_key) -> None:
        """
        Called when a function key is clicked.

        Parameters
        ----------
        function_key : QPushButton
        Function key to process.
        """
        logger.debug("Function Key: %s", function_key.text())
        if self.n1mm:
            self.n1mm.radio_info["FunctionKeyCaption"] = function_key.text()
        if self.radio_state.mode in ["LSB", "USB", "SSB"]:
            self.voice_string(self.process_macro(function_key.toolTip()))
            return
        if self.cw:
            self.cw.sendcw(self.process_macro(function_key.toolTip()))

    def run_button_clicked(self) -> None:
        self.run_sp_buttons_clicked(True)

    def sp_button_clicked(self) -> None:
        self.run_sp_buttons_clicked(False)

    def run_sp_buttons_clicked(self, is_run) -> None:
        """
        Handle Run/S&P mode changes.
        """
        self.pushButton_run.setChecked(is_run)
        self.pushButton_sp.setChecked(not is_run)

        self.pref["run_state"] = is_run
        fsutils.write_settings({"run_state": is_run})
        self.read_cw_macros()
        if self.n1mm:
            self.n1mm.set_operator(self.current_op, self.pref.get("run_state", False))

    def readpreferences(self, updated_fields = None) -> None:
        """
        Restore preferences if they exist, otherwise create some sane defaults.
        """
        logger.debug("readpreferences")

        self.pref = fsutils.read_settings()

        if updated_fields is not None and 'contest_fields' in updated_fields:
            self.contest = Contest.get_by_id(self.contest._pk)
            self.load_contest()

        self.look_up = None
        try:
            if self.pref.get("lookup_source_qrz"):
                self.look_up = QRZlookup(self.pref.get("lookup_username"), self.pref.get("lookup_password"))
            elif self.pref.get("lookup_source_hamqth"):
                self.look_up = HamQTH(self.pref.get("lookup_username"), self.pref.get("lookup_password"))
        except Exception:
            logger.exception("Could not initialize external lookup service")

        if self.pref.get("run_state"):
            self.pushButton_run.setChecked(True)
        else:
            self.pushButton_sp.setChecked(True)

        if self.pref.get("command_buttons"):
            self.actionCommand_Buttons.setChecked(True)
        else:
            self.actionCommand_Buttons.setChecked(False)

        if self.pref.get("cw_macros"):
            self.actionCW_Macros.setChecked(True)
        else:
            self.actionCW_Macros.setChecked(False)

        if self.pref.get("bands_modes"):
            self.actionMode_and_Bands.setChecked(True)
        else:
            self.actionMode_and_Bands.setChecked(False)

        if self.pref.get("darkmode"):
            self.actionDark_Mode.setChecked(True)
            self.set_dark_mode(True)
        else:
            self.set_dark_mode(False)
            self.actionDark_Mode.setChecked(False)

        self.setup_rig_control()
        if self.pref.get("cwtype", 0) == 0:
            self.cw = None
        else:
            self.cw = CW(
                int(self.pref.get("cwtype")),
                self.pref.get("cwip"),
                int(self.pref.get("cwport", 6789)),
            )
            self.cw.speed = 20
            if self.cw.servertype == 2:
                self.cw.set_winkeyer_speed(20)

        self.n1mm = None
        if self.pref.get("send_n1mm_packets", False):
            try:
                self.n1mm = N1MM(
                    self.pref.get("n1mm_radioport", "127.0.0.1:12060"),
                    self.pref.get("n1mm_contactport", "127.0.0.1:12061"),
                    self.pref.get("n1mm_lookupport", "127.0.0.1:12060"),
                    self.pref.get("n1mm_scoreport", "127.0.0.1:12060"),
                )
            except ValueError:
                logger.warning("%s", f"{ValueError}")
            self.n1mm.send_radio_packets = self.pref.get("send_n1mm_radio", False)
            self.n1mm.send_contact_packets = self.pref.get("send_n1mm_contact", False)
            self.n1mm.send_lookup_packets = self.pref.get("send_n1mm_lookup", False)
            self.n1mm.send_score_packets = self.pref.get("send_n1mm_score", False)
            self.n1mm.set_station_name(self.pref.get("station_name"))

        self.show_command_buttons()
        self.show_CW_macros()

        # If bands list is empty fill it with HF.
        if self.pref.get("bands", []) == []:
            self.pref["bands"] = ["160", "80", "40", "20", "15", "10"]

        # Hide all the bands and then show only the wanted bands.
        for _indicator in [
            self.band_indicators_cw,
            self.band_indicators_ssb,
            self.band_indicators_rtty,
        ]:
            for _bandind in _indicator.values():
                _bandind.hide()
            for band_to_show in self.pref.get("bands", []):
                if band_to_show in _indicator:
                    _indicator[band_to_show].show()

    def setup_rig_control(self):
        if self.rig_control:
            self.rig_control.close()
        self.rig_control = None

        if self.pref.get('cat_enable_manual', False):
            self.rig_control = CatManual()
        elif self.pref.get("cat_enable_flrig", False):
            logger.debug(f"Using flrig: {self.pref.get('cat_flrig_ip')} {self.pref.get('cat_flrig_port')}")
            self.rig_control = CatFlrig(self.pref.get("cat_flrig_ip", "127.0.0.1"), int(self.pref.get("cat_flrig_port", 12345)))
        elif self.pref.get("cat_enable_rigctld", False):
            logger.debug(f"Using rigctld: {self.pref.get('cat_rigctld_ip')} {self.pref.get('cat_rigctld_port')}")
            self.rig_control = CatRigctld(self.pref.get("cat_rigctld_ip", "127.0.0.1"), int(self.pref.get("cat_rigctld_port", 4532)))

        elif sys.platform == 'windows' and self.pref.get("cat_enable_omnirig", False):
            logger.debug(f"Using omni rig: {self.pref.get('cat_rigctld_ip')} {self.pref.get('cat_rigctld_port')}")
            self.rig_control = CatOmnirig(self.pref.get("cat_omnirig_index", 1))

        if self.rig_control:
            self.rig_control.start_poll_loop()

    def event_tune(self, event: appevent.Tune):
        if event.freq_hz:
            if self.rig_control:
                self.rig_control.set_vfo(event.freq_hz)
        if event.dx and self.callsign_entry.input_field.text().strip() != event.dx:
            self.callsign_entry.input_field.setText(event.dx)
            self.callsign_changed()
            self.pre_populate_contact()
            self.check_callsign_external(event.dx)

        self.callsign_entry.input_field.setFocus()

    def event_get_contest_status(self, event: appevent.GetActiveContest):
        appevent.emit(appevent.GetActiveContestResponse(self.contest, self.current_op))

    def event_external_call_lookup(self, event: appevent.ExternalLookupResult):
        current_call = self.callsign_entry.input_field.text().strip().upper()
        if event.result.call == current_call:
            # Get the grid square and calculate the distance and heading.
            self.contact.gridsquare = event.result.grid
            if self.contact.gridsquare:
                self.contact.lat, self.contact.lon = gridtolatlon(self.contact.gridsquare)

            # auto-fill name from external source
            if (not self.pref.get('lookup_name_prefer_qso_history_name', False) or not self.contact.name) \
                and self.pref.get('lookup_populate_name', None):
                name_field = self.contest_fields.get('name', None)
                if self.pref.get('lookup_populate_name', None):
                    if self.pref.get('lookup_firstname', None):
                        self.contact.name = event.result.first_name.title()
                    else:
                        self.contact.name = event.result.name.title()

            if self.pref.get('lookup_others', None):
                # populate more fields from the external lookup
                # qrz - addr1, addr2, state, county, qslmgr, email, url
                if event.result.source_result.get('url'):
                    self.contact.web = event.result.source_result.get('url')
                if event.result.source_result.get('email'):
                    self.contact.email = event.result.source_result.get('email')
                if event.result.source_result.get('qslmgr'):
                    self.contact.qslvia = event.result.source_result.get('qslmgr')
                if event.result.source_result.get('county'):
                    self.contact.county = event.result.source_result.get('county')
                if event.result.source_result.get('state'):
                    self.contact.state = event.result.source_result.get('state')
                if event.result.source_result.get('addr1'):
                    self.contact.address = event.result.source_result.get('addr1')
                if event.result.source_result.get('addr2'):
                    if self.contact.address:
                        self.contact.address = self.contact.address + ', ' + event.result.source_result.get('addr2')
                    else:
                        self.contact.address = event.result.source_result.get('addr2')

            if self.station.gridsquare:
                heading = bearing(self.station.gridsquare, event.result.grid)
                kilometers = distance(self.station.gridsquare, event.result.grid)
                self.heading_distance.setText(
                    f"{event.result.grid} Hdg {heading}° LP {reciprocol(heading)}° / "
                    f"{int(kilometers * 0.621371)}mi {kilometers}km"
                )
                self.contact.distance = kilometers
                self.sync_entry_fields(['distance'])
            self.contest_plugin.intermediate_qso_update(self.contact, ['gridsquare', 'name', 'distance'])
            self.sync_entry_fields()
            appevent.emit(IntermediateQsoUpdate(self.contact))
            if self.qso_edit_window:
                self.qso_edit_window.set_qso(self.contact)

    def sync_entry_fields(self, fields: Optional[list[str]] = None):
        if not fields:
            fields = list(self.contest_fields.keys())
            fields.remove('call')
            fields.remove('rst_sent')
            fields.remove('rst_rcvd')
        for f in fields:
            if f in self.contest_fields:
                self.contest_fields[f].input_field.setText( getattr(self.contact, f))


    def dark_mode_state_changed(self) -> None:
        self.pref["darkmode"] = self.actionDark_Mode.isChecked()
        fsutils.write_settings({"darkmode": self.actionDark_Mode.isChecked()})
        self.set_dark_mode(self.actionDark_Mode.isChecked())

    def cw_macros_state_changed(self) -> None:
        """
        Menu item to show/hide macro buttons.
        """
        self.pref["cw_macros"] = self.actionCW_Macros.isChecked()
        fsutils.write_settings({"cw_macros": self.actionCW_Macros.isChecked()})
        self.show_CW_macros()

    def show_CW_macros(self) -> None:
        """
        Show/Hide the macro buttons.
        """
        if self.pref.get("cw_macros"):
            self.Button_Row1.show()
            self.Button_Row2.show()
        else:
            self.Button_Row1.hide()
            self.Button_Row2.hide()

    def command_buttons_state_change(self) -> None:
        """
        Menu item to show/hide command buttons
        """
        self.pref["command_buttons"] = self.actionCommand_Buttons.isChecked()
        fsutils.write_settings({"command_buttons": self.actionCommand_Buttons.isChecked()})
        self.show_command_buttons()

    def show_command_buttons(self) -> None:
        """
        Show/Hide the command buttons depending on the preference.
        """

        if self.pref.get("command_buttons"):
            self.widget_cmd.show()
        else:
            self.widget_cmd.hide()

    def is_floatable(self, item: str) -> bool:
        """
        Check to see if string can be a float.

        Parameters
        ----------
        item : str
        The string to test.

        Returns
        -------
        bool
        True if string can be a float, False otherwise.
        """

        if item.isnumeric():
            return True
        try:
            _test = float(item)
        except ValueError:
            return False
        return True

    def callsign_changed(self) -> None:
        """
        Called when text in the callsign field has changed.
        Strip out any spaces and set the text.
        Check if the field contains a command.
        """

        text = self.callsign_entry.input_field.text()
        text = text.upper()
        position = self.callsign_entry.input_field.cursorPosition()
        stripped_text = text.strip().replace(" ", "")

        if " " in text:
            self.callsign_entry.input_field.setText(stripped_text)
            self.callsign_entry.input_field.setCursorPosition(position)
            if stripped_text == "CW":
                self.change_mode(stripped_text)
                return
            if stripped_text == "RTTY":
                self.change_mode(stripped_text)
                return
            if stripped_text == "SSB":
                self.change_mode(stripped_text)
                return
            if stripped_text == "OPON":
                self.get_opon()
                self.clearinputs()
                return
            if stripped_text == "HELP":
                self.show_help_dialog()
                self.clearinputs()
                return
            if stripped_text == "TEST":
                result = self.database.get_calls_and_bands()
                appevent.emit(appevent.WorkedList(result))
                self.clearinputs()
                return

            if self.is_floatable(stripped_text):
                if float(stripped_text) < 1000:
                    self.change_freq(float(stripped_text) * 1000)
                else:
                    self.change_freq(stripped_text)
                return

            self.check_callsign(stripped_text)
            if self.is_dupe_call(stripped_text):
                self.dupe_indicator.show()
            else:
                self.dupe_indicator.hide()
            self.pre_populate_contact()
            self.check_callsign_external(text)
            # space-to-tab
            self.handle_space_tab('call', self.callsign_entry.input_field)
            return

        #  debounce the potentially rapid callsign change activities
        if not self.call_change_debounce_timer:
            self.call_change_debounce_timer = True
            QTimer.singleShot(50, self.handle_call_change_debounce)

    def handle_call_change_debounce(self):
        self.call_change_debounce_timer = False
        if not self.callsign_entry.input_field.text().strip():
            self.clearinputs()
        else:
            appevent.emit(appevent.CallChanged(self.callsign_entry.input_field.text().upper()))
            self.dupe_indicator.hide()
            self.check_callsign(self.callsign_entry.input_field.text().upper())

    def handle_space_tab(self, field_name, field_input):
        if field_name == 'call':
            if self.callsign_space_to_input:
                self.callsign_space_to_input.setFocus()
            else:
                self.focusNextChild()
        else:
            field_input.deselect()
            # the text currently does not contain the space because the keypress event is fired before the change
            self.space_character_removal_queue.append((field_input, field_input.text()))
            self.focusNextChild()

    def change_freq(self, stripped_text: str) -> None:
        """
        Change VFO to given frequency in Khz and set the band indicator.
        Send the new frequency to the rig control.

        Parameters
        ----------
        stripped_text : str
        Stripped of any spaces.

        Returns
        -------
        None
        """

        vfo = float(stripped_text)
        vfo = int(vfo * 1000)
        band = getband(str(vfo))
        self.set_band_indicator(band)
        self.radio_state.vfotx_hz = vfo
        self.set_window_title()
        #self.clearinputs()
        if self.rig_control:
            self.rig_control.set_vfo(vfo)
        else:
            appevent.emit(appevent.RadioState(self.radio_state))

    def change_mode(self, mode: str) -> None:
        """
        Change mode to given mode.
        Send the new mode to the rig control.
        Set the band indicator.
        Set the window title.
        Clear the inputs.
        Read the CW macros.

        Parameters
        ----------
        mode : str
        Mode to change to.

        Returns
        -------
        None
        """

        if mode == "CW":
            self.setmode("CW")
            self.radio_state.mode = "CW"
            if self.rig_control:
                self.rig_control.set_mode("CW")
            band = getband(str(self.radio_state.vfotx_hz))
            self.set_band_indicator(band)
            self.set_window_title()
            self.clearinputs()
            self.read_cw_macros()
            return
        if mode == "RTTY":
            self.setmode("RTTY")
            self.radio_state.mode = "RTTY"
            if self.rig_control:
                self.rig_control.set_mode("RTTY")
            band = getband(str(self.radio_state.vfotx_hz))
            self.set_band_indicator(band)
            self.set_window_title()
            self.clearinputs()
            return
        if mode == "SSB":
            self.setmode("SSB")
            if int(self.radio_state.vfotx_hz) > 10000000:
                self.radio_state.mode = "USB"
            else:
                self.radio_state.mode = "LSB"
            band = getband(str(self.radio_state.vfotx_hz))
            self.set_band_indicator(band)
            self.set_window_title()
            if self.rig_control:
                self.rig_control.set_mode(self.radio_state.mode)
            self.clearinputs()
            self.read_cw_macros()

    def check_callsign(self, callsign) -> None:
        """
        Check callsign as it's being entered in the big_cty index.
        Get DX entity, CQ, ITU and continent.
        Geographic information. Distance and Heading.

        Parameters
        ----------
        callsign : str
        Callsign to check.
        """
        # TODO handle stroke callsigns correctly. stroke suffixes currently work
        result = self.bigcty.find_call_match(callsign)
        logger.debug(f"cty lookup result {result}")
        if result:
            entity = result.get("entity", "")
            if entity == self.contact.country:
                logger.debug(f"aborting cty update, have already populated for {entity}")
                return
            cq = result.get("cq", "")
            itu = result.get("itu", "")
            continent = result.get("continent")
            lat = float(result.get("lat", "0.0"))
            lon = float(result.get("long", "0.0"))
            lon = lon * -1  # cty.dat file inverts longitudes
            primary_pfx = result.get("primary_pfx", "")
            self.contact.country = entity
            self.contact.prefix = primary_pfx
            self.contact.cqz = int(cq)
            self.contact.continent = continent
            self.contact.ituz = itu
            self.contact.dxcc = result.get("dxcc", None)
            self.contact.lat = lat
            self.contact.lon = lon
            self.contest_plugin.intermediate_qso_update(self.contact, None)
            appevent.emit(IntermediateQsoUpdate(self.contact))

            if self.station.gridsquare:
                heading = bearing_with_latlon(self.station.gridsquare, self.contact.lat, self.contact.lon)
                kilometers = distance_with_latlon(
                    self.station.gridsquare, lat, lon
                )

                self.heading_distance.setText(
                    f"Regional Hdg {heading}° LP {reciprocol(heading)}° / "
                    f" {int(kilometers * 0.621371)}mi {kilometers}km"
                )
            else:
                self.heading_distance.setText("Heading/Distance Error: Set your station grid square!")

            self.dx_entity.setText(f"{self.contact.prefix}: {self.contact.continent}/{self.contact.country} cq:{self.contact.cqz} itu:{self.contact.ituz}")
            self.show_flag(self.contact.dxcc)


    def show_flag(self, dxcc):
        if dxcc:
            pixmap = flags.get_pixmap(dxcc, self.dx_entity.frameSize().height())
            self.flag_label.setMaximumHeight(self.dx_entity.frameSize().height())
            if pixmap:
                self.flag_label.setPixmap(pixmap)
        else:
            self.flag_label.clear()


    def check_callsign_external(self, callsign) -> None:
        """starts the process of getting station from external source"""
        callsign = callsign.strip()
        if self.look_up and self.look_up.did_init():
            self.look_up.lookup(callsign)

    def is_dupe_call(self, call: str) -> bool:
        """Checks if a callsign is a dupe on current band/mode."""
        dupe_type = self.contest_plugin.get_dupe_type()
        if not dupe_type:
            return False

        band = hamutils.adif.common.convert_freq_to_band((self.radio_state.vfotx_hz or 0) / 1000_000)
        mode = self.radio_state.mode
        if mode == 'USB' or mode == 'LSB':
            mode = 'SSB'
        logger.debug(f"Call: {call} Band: {band} Mode: {mode} Dupetype: {dupe_type}")

        if dupe_type == DupeType.ONCE:
            return self.contest_plugin.contest_qso_select() \
                .where(QsoLog.call == call).limit(1).get_or_none() is not None
        if dupe_type == DupeType.EACH_BAND:
            return self.contest_plugin.contest_qso_select()\
                .where(QsoLog.call == call).where(QsoLog.band == band).limit(1).get_or_none() is not None
        if dupe_type == DupeType.EACH_BAND_MODE:
            return self.contest_plugin.contest_qso_select() \
                .where(QsoLog.call == call).where(QsoLog.band == band)\
                .where(QsoLog.mode == mode).limit(1).get_or_none() is not None

        return False

    def setmode(self, mode: str) -> None:
        """Call when the mode changes."""

        self.cw_speed.setVisible(False)
        if mode == "CW":
            self.cw_speed.setVisible(True)
            if self.current_mode != "CW":
                self.current_mode = "CW"
                # self.mode.setText("CW")
                self.rst_sent_entry.input_field.setText("599")
                self.rst_received_entry.input_field.setText("599")
                self.read_cw_macros()
            return
        if mode == "SSB":
            if self.current_mode != "SSB":
                self.current_mode = "SSB"
                # self.mode.setText("SSB")
                self.rst_sent_entry.input_field.setText("59")
                self.rst_received_entry.input_field.setText("59")
                self.read_cw_macros()
            return
        if mode == "RTTY":
            if self.current_mode != "RTTY":
                self.current_mode = "RTTY"
                # self.mode.setText("RTTY")
                self.rst_sent_entry.input_field.setText("59")
                self.rst_received_entry.input_field.setText("59")

    def get_opon(self) -> None:
        """
        Ctrl+O Open the OPON dialog.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        self.opon_dialog = OpOn(fsutils.APP_DATA_PATH)

        self.opon_dialog.accepted.connect(self.new_op)
        self.opon_dialog.open()

    def new_op(self) -> None:
        """
        Called when the user clicks the OK button on the OPON dialog.
        Create the new directory and copy the phonetic files.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        if self.opon_dialog.NewOperator.text():
            self.current_op = self.opon_dialog.NewOperator.text().upper()
        self.opon_dialog.close()
        logger.debug("New Op: %s", self.current_op)
        if self.n1mm:
            self.n1mm.set_operator(self.current_op, self.pref.get("run_state", False))
        self.make_op_dir()

    def make_op_dir(self) -> None:
        """
        Create OP directory if it does not exist.
        Copy the phonetic files to the new directory.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        if self.current_op:
            op_path = fsutils.USER_DATA_PATH / 'operator' / self.current_op
            logger.debug("op_path: %s", str(op_path))
            if op_path.is_dir() is False:
                logger.debug("Creating Op Directory: %s", str(op_path))
                op_path.mkdir(parents=True)
            if op_path.is_dir():
                source_path = fsutils.APP_DATA_PATH / "phonetics"
                logger.debug("source_path: %s", str(source_path))
                for child in source_path.iterdir():
                    destination_file = op_path / child.name
                    if destination_file.is_file() is False:
                        logger.debug("Destination: %s", str(destination_file))
                        destination_file.write_bytes(child.read_bytes())

    def edit_cw_macros(self) -> None:
        """
        Calls the default text editor to edit the CW macro file.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.radio_state.mode == "CW":
            macro_file = "cwmacros.txt"
        else:
            macro_file = "ssbmacros.txt"
        if not (fsutils.USER_DATA_PATH / macro_file).exists():
            logger.debug("read_cw_macros: copying default macro file.")
            copyfile(
                fsutils.APP_DATA_PATH / macro_file, fsutils.USER_DATA_PATH / macro_file
            )
        try:
            fsutils.openFileWithOS(fsutils.USER_DATA_PATH / macro_file)
        except:
            logger.exception(
                f"Could not open file {fsutils.USER_DATA_PATH / macro_file}"
            )

    def read_cw_macros(self) -> None:
        """
        Reads in the CW macros, firsts it checks to see if the file exists. If it does not,
        and this has been packaged with pyinstaller it will copy the default file from the
        temp directory this is running from... In theory.
        """

        if self.radio_state.mode == "CW":
            macro_file = "cwmacros.txt"
        else:
            macro_file = "ssbmacros.txt"

        if not (fsutils.USER_DATA_PATH / macro_file).exists():
            logger.debug("read_cw_macros: copying default macro file.")
            copyfile(
                fsutils.APP_DATA_PATH / macro_file, fsutils.USER_DATA_PATH / macro_file
            )
        with open(
            fsutils.USER_DATA_PATH / macro_file, "r", encoding="utf-8"
        ) as file_descriptor:
            for line in file_descriptor:
                try:
                    mode, fkey, buttonname, cwtext = line.split("|")
                    if mode.strip().upper() == "R" and self.pref.get("run_state"):
                        self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                    if mode.strip().upper() != "R" and not self.pref.get("run_state"):
                        self.fkeys[fkey.strip()] = (buttonname.strip(), cwtext.strip())
                except ValueError as err:
                    logger.info("read_cw_macros: %s", err)
        keys = self.fkeys.keys()
        if "F1" in keys:
            self.F1.setText(f"F1: {self.fkeys['F1'][0]}")
            self.F1.setToolTip(self.fkeys["F1"][1])
        if "F2" in keys:
            self.F2.setText(f"F2: {self.fkeys['F2'][0]}")
            self.F2.setToolTip(self.fkeys["F2"][1])
        if "F3" in keys:
            self.F3.setText(f"F3: {self.fkeys['F3'][0]}")
            self.F3.setToolTip(self.fkeys["F3"][1])
        if "F4" in keys:
            self.F4.setText(f"F4: {self.fkeys['F4'][0]}")
            self.F4.setToolTip(self.fkeys["F4"][1])
        if "F5" in keys:
            self.F5.setText(f"F5: {self.fkeys['F5'][0]}")
            self.F5.setToolTip(self.fkeys["F5"][1])
        if "F6" in keys:
            self.F6.setText(f"F6: {self.fkeys['F6'][0]}")
            self.F6.setToolTip(self.fkeys["F6"][1])
        if "F7" in keys:
            self.F7.setText(f"F7: {self.fkeys['F7'][0]}")
            self.F7.setToolTip(self.fkeys["F7"][1])
        if "F8" in keys:
            self.F8.setText(f"F8: {self.fkeys['F8'][0]}")
            self.F8.setToolTip(self.fkeys["F8"][1])
        if "F9" in keys:
            self.F9.setText(f"F9: {self.fkeys['F9'][0]}")
            self.F9.setToolTip(self.fkeys["F9"][1])
        if "F10" in keys:
            self.F10.setText(f"F10: {self.fkeys['F10'][0]}")
            self.F10.setToolTip(self.fkeys["F10"][1])
        if "F11" in keys:
            self.F11.setText(f"F11: {self.fkeys['F11'][0]}")
            self.F11.setToolTip(self.fkeys["F11"][1])
        if "F12" in keys:
            self.F12.setText(f"F12: {self.fkeys['F12'][0]}")
            self.F12.setToolTip(self.fkeys["F12"][1])

    def generate_adif(self) -> None:
        AdifExport(self.contest, parent=self).open()

    def generate_cabrillo(self) -> None:
        CabrilloExport(self.contest, self.contest_plugin, self.station, parent=self).open()

    def action_import_adif(self):
        AdifImport(self.contest, parent=self).show()

    def event_radio_state(self, event: appevent.RadioState):
        self.radio_state = event.state
        self.set_radio_icon(0)
        self.set_radio_icon_tooltip()
        if self.radio_state.error or not self.radio_state.vfotx_hz:
            self.set_radio_icon(1)
        elif self.radio_state.vfotx_hz:
            self.set_radio_icon(2)
            if self.radio_state.mode == "CW" or self.radio_state.mode == 'RTTY':
                self.setmode(self.radio_state.mode)
            if self.radio_state.mode == "LSB" or self.radio_state.mode == "USB" or self.radio_state.mode == 'SSB':
                self.setmode("SSB")
            band = getband(str(self.radio_state.vfotx_hz))
            self.set_band_indicator(band)
            self.set_window_title()
            if self.radio_state.is_ptt:
                self.set_radio_icon(3)

    def set_radio_icon_tooltip(self):
        if self.radio_state.vfotx_hz is None:
            self.radio_icon.setToolTip("Unavailable")
            return
        self.radio_icon.setToolTip(f"<table><tr><td>rig</td><td>{self.radio_state.id}</td></tr>"
                                   f"<tr><td>vfo</td><td>{self.radio_state.vforx_hz:,}</td></tr>"
                                   f"<tr><td>mode</td><td>{self.radio_state.mode}</td></tr>"
                                   f"<tr><td>split tx</td><td>{'N/A' if not self.radio_state.is_split else self.radio_state.vfotx_hz}</td></tr>"
                                   f"<tr><td>bandwidth</td><td>{self.radio_state.bandwidth_hz}</td></tr>"
                                   f"<tr><td>power</td><td>{self.radio_state.power}</td></tr></table>"
                                   )

    def edit_window_data_change(self, qso_before, qso_after, field_name, value):
        # update entry fields with new values from the qso edit window
        if field_name in self.contest_fields:
            # make sure the input field stays in sync with the qso object
            new_value = getattr(self.contact, field_name)
            if self.contest_fields[field_name].input_field.text() != new_value:
                self.contest_fields[field_name].input_field.setText(new_value)


def load_fonts_from_dir(directory: str) -> set:
    """
    Well it loads fonts from a directory...

    Parameters
    ----------
    directory : str
    The directory to load fonts from.

    Returns
    -------
    set
    A set of font families installed in the directory.
    """
    font_families = set()
    for _fi in QDir(directory).entryInfoList(["*.ttf", "*.woff", "*.woff2"]):
        _id = QFontDatabase.addApplicationFont(_fi.absoluteFilePath())
        font_families |= set(QFontDatabase.applicationFontFamilies(_id))
    return font_families


def install_icons() -> None:
    """Install icons"""

    if sys.platform == "linux":
        os.system(
            "xdg-icon-resource install --size 32 --context apps --mode user "
            f"{fsutils.APP_DATA_PATH}/qsource-32.png qsource-logger"
        )
        os.system(
            "xdg-icon-resource install --size 128 --context apps --mode user "
            f"{fsutils.APP_DATA_PATH}/qsource-128.png qsource-logger"
        )
        os.system(
            f"xdg-desktop-menu install {fsutils.APP_DATA_PATH}/qsource-logger.desktop"
        )


def doimp(modname) -> object:
    """
    Imports a module.

    Parameters
    ----------
    modname : str
    The name of the module to import.

    Returns
    -------
    object
    The module object.
    """

    logger.debug("doimp: %s", modname)
    return importlib.import_module(f"qsourcelogger.contest.{modname}")


_window = None
def run() -> None:
    """
    Main Entry
    """
    logger.debug(
        f"Resolved OS file system paths: MODULE_PATH {fsutils.MODULE_PATH}, USER_DATA_PATH {fsutils.USER_DATA_PATH}, CONFIG_PATH {fsutils.CONFIG_PATH}")

    window = MainWindow()

    if window.pref.get("window_bandmap_enable", None):
        window.launch_bandmap_window()
    if window.pref.get("window_check_enable", None):
        window.launch_check_window()
    if window.pref.get("window_log_enable", None):
        window.launch_log_window()
    if window.pref.get("window_profile_enable", None):
        window.launch_profile_image_window()
    if window.pref.get("window_worldmap_enable", None):
        window.launch_map_window()
    if window.pref.get("window_vfo_enable", None):
        window.launch_vfo()
    if window.pref.get("window_qsoedit_enable", None):
        window.launch_qso_edit_window()

    if 'window_state' in window.pref:
        window.restoreState(QByteArray.fromHex(bytes(window.pref["window_state"], 'ascii')), 1)
    if 'window_geo' in window.pref:
        window.restoreGeometry(QByteArray.fromHex(bytes(window.pref["window_geo"], 'ascii')))

    signal.signal(signal.SIGINT, lambda sig, frame: window.close())

    window.show()

    sys.exit(app.exec())


DEBUG_ENABLED = False
if Path("./debug").exists():
    DEBUG_ENABLED = True


logging.basicConfig(
    level=logging.DEBUG if DEBUG_ENABLED else logging.CRITICAL,
    format="[%(asctime)s] %(levelname)s %(name)s - %(funcName)s Line %(lineno)d: %(message)s",
    handlers=[
        RotatingFileHandler(fsutils.LOG_FILE, maxBytes=10490000, backupCount=20),
        logging.StreamHandler(),
    ],
)

logging.getLogger('PyQt6.uic.uiparser').setLevel('INFO')
logging.getLogger('PyQt6.uic.properties').setLevel('INFO')
logging.getLogger('matplotlib.font_manager').setLevel('INFO')
logging.getLogger('peewee').setLevel('INFO')
#os.environ["QT_QPA_PLATFORMTHEME"] = "gnome"
app = QtWidgets.QApplication(sys.argv)
install_icons()
families = load_fonts_from_dir(os.fspath(fsutils.APP_DATA_PATH))
logger.info(f"font families {families}")

if __name__ == "__main__":
    run()
