"""Settings Dialog Class"""

import logging
import platform

import serial.tools.list_ports
import sounddevice as sd
from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QComboBox

from qsourcelogger import fsutils

logger = logging.getLogger(__name__)


class Settings(QtWidgets.QDialog):
    """Settings dialog"""
    updated = pyqtSignal(list)
    tabWidget: QTabWidget
    cat_hamlib_dev: QComboBox
    cat_hamlib_rig: QComboBox
    cat_hamlib_baud: QComboBox

    hamlib_available = False

    def __init__(self, app_data_path, pref, parent=None):
        """initialize dialog"""
        super().__init__(parent)
        self.logger = logging.getLogger("settings")
        uic.loadUi(app_data_path / "configuration.ui", self)
        self.buttonBox.accepted.connect(self.save_pref_values)
        self.preference = pref

        if platform.system() != "Windows":
            self.cat_enable_omnirig.setEnabled(False)

        try:
            from ..cat.libhamlib import Hamlib
            if Hamlib:
                Hamlib.rig_load_all_backends()
                self.hamlib_available = True
        except Exception as e:
            logger.error(f"Hamlib not available {e}")

        self.setup()

    def show_tab(self, tab_name):
        self.tabWidget.setCurrentWidget(getattr(self, tab_name))

    def setup(self):
        """setup dialog"""
        for device in sd.query_devices():
            if device.get("max_output_channels"):
                device_id = device['name'] + ", " + sd.query_hostapis(device['hostapi'])['name']
                self.sounddevice.addItem(device_id)

        value = self.preference.get("sounddevice", "default")
        index = self.sounddevice.findText(value)
        if index != -1:
            self.sounddevice.setCurrentIndex(index)

        self.lookup_source_qrz.setChecked(bool(self.preference.get("lookup_source_qrz")))
        self.lookup_source_hamdb.setChecked(bool(self.preference.get("lookup_source_hamdb")))
        self.lookup_source_hamqth.setChecked(bool(self.preference.get("lookup_source_hamqth")))
        self.lookup_user_name_field.setText(self.preference.get("lookup_username"))
        self.lookup_password_field.setText(self.preference.get("lookup_password"))
        self.lookup_populate_name.setChecked(self.preference.get("lookup_populate_name"))
        self.lookup_name_prefer_qso_history_name.setChecked(self.preference.get("lookup_name_prefer_qso_history_name"))
        self.lookup_firstname.setChecked(bool(self.preference.get("lookup_firstname")))
        self.lookup_others.setChecked(bool(self.preference.get("lookup_others")))

        self.cat_enable_flrig.setChecked(bool(self.preference.get("cat_enable_flrig")))
        self.cat_flrig_ip.setText(self.preference.get("cat_flrig_ip"))
        self.cat_flrig_port.setText(str(self.preference.get("cat_flrig_port")))

        self.cat_enable_omnirig.setChecked(bool(self.preference.get("cat_enable_omnirig")))
        self.cat_enable_rigctld.setChecked(bool(self.preference.get("cat_enable_rigctld")))
        self.cat_rigctld_ip.setText(self.preference.get("cat_rigctld_ip"))
        self.cat_rigctld_port.setText(str(self.preference.get("cat_rigctld_port")))
        self.cat_manual_mode.setCurrentText(self.preference.get("cat_manual_mode"))
        self.cat_manual_vfo.setText(str(self.preference.get("cat_manual_vfo")))

        self.cwip_field.setText(str(self.preference.get("cwip", "")))
        self.cwport_field.setText(str(self.preference.get("cwport", "")))
        self.usecwdaemon_radioButton.setChecked(
            bool(self.preference.get("cwtype") == 1)
        )
        self.usepywinkeyer_radioButton.setChecked(
            bool(self.preference.get("cwtype") == 2)
        )

        self.send_n1mm_packets.setChecked(
            bool(self.preference.get("send_n1mm_packets"))
        )
        self.n1mm_station_name.setText(
            str(self.preference.get("n1mm_station_name", ""))
        )
        self.n1mm_operator.setText(str(self.preference.get("n1mm_operator", "")))
        # self.n1mm_ip.setText(str(self.preference.get("n1mm_ip", "")))
        self.n1mm_radioport.setText(str(self.preference.get("n1mm_radioport", "")))
        self.n1mm_contactport.setText(str(self.preference.get("n1mm_contactport", "")))
        self.n1mm_lookupport.setText(str(self.preference.get("n1mm_lookupport", "")))
        self.n1mm_scoreport.setText(str(self.preference.get("n1mm_scoreport", "")))
        self.send_n1mm_radio.setChecked(bool(self.preference.get("send_n1mm_radio")))
        self.send_n1mm_contact.setChecked(
            bool(self.preference.get("send_n1mm_contact"))
        )
        self.send_n1mm_lookup.setChecked(bool(self.preference.get("send_n1mm_lookup")))
        self.send_n1mm_score.setChecked(bool(self.preference.get("send_n1mm_score")))

        self.cluster_server_field.setText(
            str(self.preference.get("cluster_server", "dxc.nc7j.com"))
        )
        self.cluster_port_field.setText(str(self.preference.get("cluster_port", 7373)))
        self.cluster_filter.setText(self.preference.get("cluster_filter", ""))
        value = self.preference.get("cluster_mode", "")
        index = self.cluster_mode.findText(value)
        if index != -1:
            self.cluster_mode.setCurrentIndex(index)
        self.activate_160m.setChecked(bool("160" in self.preference.get("bands", [])))
        self.activate_80m.setChecked(bool("80" in self.preference.get("bands", [])))
        self.activate_40m.setChecked(bool("40" in self.preference.get("bands", [])))
        self.activate_20m.setChecked(bool("20" in self.preference.get("bands", [])))
        self.activate_15m.setChecked(bool("15" in self.preference.get("bands", [])))
        self.activate_10m.setChecked(bool("10" in self.preference.get("bands", [])))
        self.activate_6m.setChecked(bool("6" in self.preference.get("bands", [])))
        self.activate_2m.setChecked(bool("2" in self.preference.get("bands", [])))
        self.activate_1dot25.setChecked(
            bool("1.25" in self.preference.get("bands", []))
        )
        self.activate_70cm.setChecked(bool("70cm" in self.preference.get("bands", [])))
        self.activate_33cm.setChecked(bool("33cm" in self.preference.get("bands", [])))
        self.activate_23cm.setChecked(bool("23cm" in self.preference.get("bands", [])))

        self.interface_checkbox_emacs.setChecked(self.preference.get('interface_emacs', False))
        self.interface_entry_focus_select.setChecked(self.preference.get('interface_entry_focus_select', True))
        self.interface_entry_focus_end.setChecked(not self.preference.get('interface_entry_focus_select', True))

        if self.hamlib_available:
            self.cat_enable_hamlib.setEnabled(True)
            self.cat_enable_hamlib.setChecked(self.preference.get("cat_enable_hamlib", False))
            self.cat_hamlib_baud.setCurrentText(self.preference.get("cat_hamlib_baud", '38400'))

            self.cat_hamlib_dev.clear()
            self.cat_hamlib_dev.addItem('')
            self.cat_hamlib_dev.addItems([x.device for x in serial.tools.list_ports.comports()])
            if self.preference.get("cat_hamlib_dev", None):
                self.cat_hamlib_dev.setCurrentText(self.preference.get("cat_hamlib_dev"))

            from qsourcelogger.cat import libhamlib
            self.cat_hamlib_rig.clear()
            rigs = libhamlib.rig_get_models()
            rigs = list(filter(lambda r: r.get('mfg_name') and r.get('model_name'), rigs))
            rigs.sort(key=lambda r: r['mfg_name'] + '_' + r['model_name'])

            for rig in rigs:
                self.cat_hamlib_rig.addItem(rig['mfg_name'] + ' ' + rig['model_name'], rig['macro_name'])
                if self.preference.get('cat_hamlib_rig', None) == rig['macro_name']:
                    self.cat_hamlib_rig.setCurrentIndex(self.cat_hamlib_rig.count() - 1)

        else:
            self.cat_enable_hamlib.setEnabled(False)

    def save_pref_values(self):
        new_pref = {}
        new_pref["sounddevice"] = self.sounddevice.currentText()
        new_pref["lookup_source_qrz"] = self.lookup_source_qrz.isChecked()
        new_pref["lookup_source_hamdb"] = self.lookup_source_hamdb.isChecked()
        new_pref["lookup_source_hamqth"] = self.lookup_source_hamqth.isChecked()
        new_pref["lookup_username"] = self.lookup_user_name_field.text()
        new_pref["lookup_password"] = self.lookup_password_field.text()
        new_pref["lookup_populate_name"] = self.lookup_populate_name.isChecked()
        new_pref["lookup_name_prefer_qso_history_name"] = self.lookup_name_prefer_qso_history_name.isChecked()
        new_pref["lookup_firstname"] = self.lookup_firstname.isChecked()
        new_pref["lookup_others"] = self.lookup_others.isChecked()

        new_pref["cat_enable_flrig"] = self.cat_enable_flrig.isChecked()
        new_pref["cat_flrig_ip"] = self.cat_flrig_ip.text()
        try:
            new_pref["cat_flrig_port"] = int(self.cat_flrig_port.text())
        except ValueError:
            ...

        new_pref["cat_enable_omnirig"] = self.cat_enable_omnirig.isChecked()

        new_pref["cat_enable_rigctld"] = self.cat_enable_rigctld.isChecked()
        new_pref["cat_rigctld_ip"] = self.cat_rigctld_ip.text()
        try:
            new_pref["cat_rigctld_port"] = int(self.cat_rigctld_port.text())
        except ValueError:
            ...

        new_pref["cat_enable_hamlib"] = self.cat_enable_hamlib.isChecked()
        new_pref["cat_hamlib_dev"] = self.cat_hamlib_dev.currentText()
        new_pref["cat_hamlib_rig"] = self.cat_hamlib_rig.currentData()
        new_pref["cat_hamlib_baud"] = self.cat_hamlib_baud.currentText()

        new_pref["cat_manual_mode"] = self.cat_manual_mode.currentText()
        try:
            new_pref["cat_manual_vfo"] = int(self.cat_manual_vfo.text())
        except ValueError:
            ...

        new_pref["cwip"] = self.cwip_field.text()
        try:
            new_pref["cwport"] = int(self.cwport_field.text())
        except ValueError:
            ...
        new_pref["cwtype"] = 0
        if self.usecwdaemon_radioButton.isChecked():
            new_pref["cwtype"] = 1
        if self.usepywinkeyer_radioButton.isChecked():
            new_pref["cwtype"] = 2

        new_pref["send_n1mm_packets"] = self.send_n1mm_packets.isChecked()

        new_pref["send_n1mm_radio"] = self.send_n1mm_radio.isChecked()
        new_pref["send_n1mm_contact"] = self.send_n1mm_contact.isChecked()
        new_pref["send_n1mm_lookup"] = self.send_n1mm_lookup.isChecked()
        new_pref["send_n1mm_score"] = self.send_n1mm_score.isChecked()

        new_pref["n1mm_station_name"] = self.n1mm_station_name.text()
        new_pref["n1mm_operator"] = self.n1mm_operator.text()
        # new_pref["n1mm_ip"] = self.n1mm_ip.text()
        new_pref["n1mm_radioport"] = self.n1mm_radioport.text()
        new_pref["n1mm_contactport"] = self.n1mm_contactport.text()
        new_pref["n1mm_lookupport"] = self.n1mm_lookupport.text()
        new_pref["n1mm_scoreport"] = self.n1mm_scoreport.text()
        new_pref["cluster_server"] = self.cluster_server_field.text()
        new_pref["cluster_port"] = int(self.cluster_port_field.text())
        new_pref["cluster_filter"] = self.cluster_filter.text()
        new_pref["cluster_mode"] = self.cluster_mode.currentText()
        bandlist = list()
        if self.activate_160m.isChecked():
            bandlist.append("160")
        if self.activate_80m.isChecked():
            bandlist.append("80")
        if self.activate_40m.isChecked():
            bandlist.append("40")
        if self.activate_20m.isChecked():
            bandlist.append("20")
        if self.activate_15m.isChecked():
            bandlist.append("15")
        if self.activate_10m.isChecked():
            bandlist.append("10")
        if self.activate_6m.isChecked():
            bandlist.append("6")
        if self.activate_2m.isChecked():
            bandlist.append("2")
        if self.activate_1dot25.isChecked():
            bandlist.append("1.25")
        if self.activate_70cm.isChecked():
            bandlist.append("70cm")
        if self.activate_33cm.isChecked():
            bandlist.append("33cm")
        if self.activate_23cm.isChecked():
            bandlist.append("23cm")
        new_pref["bands"] = bandlist

        new_pref['interface_emacs'] = self.interface_checkbox_emacs.isChecked()
        new_pref['interface_entry_focus_select'] = self.interface_entry_focus_select.isChecked()

        fsutils.write_settings(new_pref)
        self.updated.emit([])
