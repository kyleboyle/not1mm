#!/usr/bin/env python3
"""
VFO Window
"""
# pylint: disable=no-name-in-module, unused-import, no-member, invalid-name, logging-fstring-interpolation, c-extension-no-member

# 115200 pico default speed
# usb-Raspberry_Pi_Pico_E6612483CB1B242A-if00
# usb-Raspberry_Pi_Pico_W_E6614C311B331139-if00

import logging
import os
from json import loads

import serial
from PyQt6 import QtCore, QtWidgets, uic
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDockWidget

import not1mm.fsutils as fsutils
from not1mm.lib import event
from not1mm.qtcomponents.DockWidget import DockWidget

logger = logging.getLogger(__name__)

class VfoWindow(DockWidget):
    """The VFO window."""

    pref = {}
    old_vfo = ""
    old_pico = ""
    message_shown = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(fsutils.APP_DATA_PATH / "vfo.ui", self)
        self.rig_control = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.getwaiting)
        self.load_pref()
        self.lcdNumber.display(0)
        self.pico = None

        self.setup_serial()
        # app.processEvents()
        self.poll_rig_timer = QtCore.QTimer()
        self.poll_rig_timer.timeout.connect(self.poll_radio)
        self.poll_rig_timer.start(500)

        event.register(event.Tune, self.tune)

    def tune(self, e: event.Tune):

        changefreq = f"F {int(e.freq_hz)}\r"
        try:
            if self.pico:
                self.pico.write(changefreq.encode())
        except OSError:
            logger.critical("Unable to write to serial device.")
        except AttributeError:
            logger.critical("Unable to write to serial device.")


    def load_pref(self) -> None:
        """
        Load preference file.
        Get CAT interface.
        """
        try:
            if os.path.exists(fsutils.CONFIG_FILE):
                with open(
                    fsutils.CONFIG_FILE, "rt", encoding="utf-8"
                ) as file_descriptor:
                    self.pref = loads(file_descriptor.read())
                    logger.info("%s", self.pref)

        except IOError as exception:
            logger.critical("Error: %s", exception)

        if self.pref.get("useflrig", False):
            logger.debug(
                "Using flrig: %s",
                f"{self.pref.get('CAT_ip')} {self.pref.get('CAT_port')}",
            )
            self.rig_control = CAT(
                "flrig",
                self.pref.get("CAT_ip", "127.0.0.1"),
                int(self.pref.get("CAT_port", 12345)),
            )
            self.timer.start(100)
        if self.pref.get("userigctld", False):
            logger.debug(
                "Using rigctld: %s",
                f"{self.pref.get('CAT_ip')} {self.pref.get('CAT_port')}",
            )
            self.rig_control = CAT(
                "rigctld",
                self.pref.get("CAT_ip", "127.0.0.1"),
                int(self.pref.get("CAT_port", 4532)),
            )
            self.timer.start(100)

    def discover_device(self) -> str:
        """
        Poll all serial devices looking for correct one.

        Rummage thru /dev/serial/by-id/ looking for Raspberry Picos
        Ask each if it's a vfoknob.
        Return the device ID if it is, or None if not found.
        """

        devices = None
        data = None
        # app.processEvents()
        try:
            devices = os.listdir("/dev/serial/by-id")
        except FileNotFoundError:
            return None

        for device in devices:
            if "usb-Raspberry_Pi_Pico" in device:
                try:
                    with serial.Serial("/dev/serial/by-id/" + device, 115200) as ser:
                        ser.timeout = 1000
                        ser.write(b"whatareyou\r")
                        data = ser.readline()
                except serial.serialutil.SerialException:
                    return None
                if "vfoknob" in data.decode().strip():
                    return device

    def setup_serial(self) -> None:
        """
        Setup the device returned by discover_device()
        Or display message saying we didn't find one.
        """

        device = self.discover_device()
        if device:
            try:
                self.pico = serial.Serial("/dev/serial/by-id/" + device, 115200)
                self.pico.timeout = 100
                self.lcdNumber.setStyleSheet("QLCDNumber { color: white; }")
            except OSError:
                if self.message_shown is False:
                    self.message_shown = True
                    self.show_message_box(
                        "Unable to locate or open the VFO knob serial device."
                    )
                self.lcdNumber.setStyleSheet("QLCDNumber { color: red; }")
        else:
            if self.message_shown is False:
                self.message_shown = True
                self.show_message_box(
                    "Unable to locate or open the VFO knob serial device."
                )
            self.lcdNumber.setStyleSheet("QLCDNumber { color: red; }")


    def showNumber(self, the_number) -> None:
        """Display vfo value with dots"""
        dvfo = str(the_number)
        if len(dvfo) > 6:
            dnum = f"{dvfo[:len(dvfo)-6]}.{dvfo[-6:-3]}.{dvfo[-3:]}"
            self.lcdNumber.display(dnum)
            # app.processEvents()

    def poll_radio(self) -> None:
        """
        Poll radio via CAT asking for VFO state.
        If it's with in the HAM bands set the vfo knob to match the radio.
        """
        if self.rig_control:
            if self.rig_control.online is False:
                self.rig_control.reinit()
            if self.rig_control.online:
                vfo = self.rig_control.get_vfo()
                try:
                    vfo = int(vfo)
                except ValueError:
                    return
                if vfo < 1700000 or vfo > 60000000:
                    return
                if vfo != self.old_vfo:
                    self.old_vfo = vfo
                    logger.debug(f"{vfo}")
                    self.showNumber(vfo)
                    # self.lcdNumber.display(dnum)
                    # app.processEvents()
                    cmd = f"F {vfo}\r"
                    try:
                        if self.pico:
                            self.pico.write(cmd.encode())
                    except OSError:
                        logger.critical("Unable to write to serial device.")
                    except AttributeError:
                        logger.critical("Unable to write to serial device.")

    def getwaiting(self) -> None:
        """
        Get the USB VFO knob state.
        Set the radio's VFO to match if it has changed.
        """
        try:
            if self.pico:
                self.pico.write(b"f\r")
                while self.pico.in_waiting:
                    result = self.pico.read(self.pico.in_waiting)
                    result = result.decode().strip()
                    if self.old_pico != result:
                        self.old_pico = result
                        if self.rig_control:
                            self.rig_control.set_vfo(result)
                            self.showNumber(result)
                            # self.lcdNumber.display(result)
                            # app.processEvents()
        except OSError:
            logger.critical("Unable to write to serial device.")
        except AttributeError:
            logger.critical("Unable to write to serial device.")
        # app.processEvents()

    def show_message_box(self, message: str) -> None:
        """
        Display an alert box with the supplied message.
        """
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message_box.setText(message)
        message_box.setWindowTitle("Information")
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        _ = message_box.exec()

