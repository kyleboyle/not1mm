"""New Contest Dialog"""
import datetime

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QDateTime, QDate, QTime
from PyQt6.QtWidgets import QComboBox, QPlainTextEdit, QDateTimeEdit, QLineEdit, QDialog, QPushButton, QMessageBox

from not1mm import fsutils
from not1mm.lib.event_model import ContestActive
from not1mm.model import Contest, ContestMeta, Station, QsoLog, DeletedQsoLog
from not1mm.contest import contest_plugin_list, contests_by_cabrillo_id

import not1mm.lib.event as appevent

class ContestEdit(QDialog):
    select_contest: QComboBox
    transmitter_category: QComboBox
    band_category: QComboBox
    overlay_category: QComboBox
    soapbox: QPlainTextEdit
    assisted_category: QComboBox
    start_date: QDateTimeEdit
    station_category: QComboBox
    mode_category: QComboBox
    sent_exchange: QLineEdit
    operator_category: QComboBox
    operators: QLineEdit
    power_category: QComboBox
    fk_contest: QComboBox
    fk_station: QComboBox
    button_activate: QPushButton
    button_new: QPushButton
    button_delete: QPushButton
    button_save: QPushButton

    contest: Contest = None  # contest in form

    def __init__(self, app_data_path, parent=None):
        super().__init__(parent)
        self.settings = fsutils.read_settings()
        uic.loadUi(app_data_path / "ContestEdit.ui", self)

        self.button_new.clicked.connect(self.new_contest)
        self.button_save.clicked.connect(self.save_contest)
        self.button_delete.clicked.connect(self.delete_contest)
        self.button_activate.clicked.connect(self.activate_contest)
        self.select_contest.currentIndexChanged.connect(self.edit_contest)

        self.fk_contest.currentIndexChanged.connect(self.contest_meta_changed)

        self.start_date.setCalendarPopup(True)

        self.fk_contest.clear()
        for plugin_class in contest_plugin_list:
            # Populate contest select list based on available contest plugin classes which match the contest meta data base table.
            # future - is the contest meta table necessary? - probably to enforce contest categorization integrity
            cm = ContestMeta.select().where(ContestMeta.cabrillo_name == plugin_class.get_cabrillo_name()).get_or_none()
            if cm:
                self.fk_contest.addItem(cm.display_name, cm)

        for s in Station.select().where(Station.deleted != True):
            self.fk_station.addItem(f"[{s.callsign}] {s.station_name}", s)

        self.clear_form()
        if self.settings.get("active_contest_id", None) is not None:
            # initial view = show the active contest
            c = Contest.select().where(Contest.id == self.settings.get("active_contest_id")).get_or_none()
            self.populate_contest_select(c)
            if c:
                self.populate_form(c)
        else:
            self.populate_contest_select()

    def populate_contest_select(self, select_contest: Contest = None):
        self.select_contest.clear()
        self.select_contest.addItem("", None)
        active_contest_id = self.settings.get("active_contest_id", None)
        found_active = False
        for contest in Contest.select().where(Contest.deleted != True).order_by(Contest.start_date.desc()):
            name = f"{contest.start_date.date()} {contest.fk_contest_meta.display_name}"
            if active_contest_id == contest.id:
                name = f"[ACTIVE] {name}"
                self.contest = contest
                found_active = True
            self.select_contest.addItem(name, contest)
            if select_contest and select_contest.get_id() == contest.get_id():
                self.select_contest.setCurrentIndex(self.select_contest.count() - 1)
        if not found_active and 'active_contest_id' in self.settings:
            # make sure settings doesn't get out of sync with db contents
            del self.settings['active_contest_id']

    def populate_form(self, contest: Contest):

        self.fk_contest.setEnabled(True)
        self.fk_station.setEnabled(True)
        self.assisted_category.setEnabled(True)
        self.band_category.setEnabled(True)
        self.mode_category.setEnabled(True)
        self.operator_category.setEnabled(True)
        self.overlay_category.setEnabled(True)
        self.power_category.setEnabled(True)
        self.station_category.setEnabled(True)
        self.transmitter_category.setEnabled(True)
        self.operators.setEnabled(True)
        self.soapbox.setEnabled(True)
        self.sent_exchange.setEnabled(True)
        self.start_date.setEnabled(True)

        if contest.fk_contest_meta_id:
            self.select_item(self.fk_contest, contest.fk_contest_meta.display_name)

        if contest.fk_station_id:
            self.select_item(self.fk_station, contest.fk_station.station_name)

        self.select_item(self.assisted_category, contest.assisted_category)
        self.select_item(self.band_category, contest.band_category)
        self.select_item(self.mode_category, contest.mode_category)
        self.select_item(self.operator_category, contest.operator_category)
        self.select_item(self.overlay_category, contest.overlay_category)
        self.select_item(self.power_category, contest.power_category)
        self.select_item(self.station_category, contest.station_category)
        self.select_item(self.transmitter_category, contest.transmitter_category)
        # TODO sub_type, time_category

        self.operators.setText(contest.operators)
        self.soapbox.setPlainText(contest.soapbox)
        self.sent_exchange.setText(contest.sent_exchange)
        self.start_date.setDate(contest.start_date.date())
        self.start_date.setTime(contest.start_date.time())

        self.contest = contest
        self.button_delete.setEnabled(self.contest.id is not None)
        self.button_activate.setEnabled(self.settings.get('active_contest_id', None) != self.contest.id)

    def select_item(self, target: QComboBox, text: str) -> None:
        index = target.findText(text)
        if index >= 0:
            target.setCurrentIndex(index)

    def clear_form(self):
        self.contest = None
        self.button_activate.setEnabled(False)
        self.button_delete.setEnabled(False)
        self.fk_contest.setEnabled(False)
        self.fk_contest.setCurrentIndex(0)
        self.fk_station.setEnabled(False)
        self.fk_station.setCurrentIndex(0)
        self.assisted_category.setEnabled(False)
        self.assisted_category.setCurrentIndex(0)
        self.band_category.setEnabled(False)
        self.band_category.setCurrentIndex(0)
        self.mode_category.setEnabled(False)
        self.mode_category.setCurrentIndex(0)
        self.operator_category.setEnabled(False)
        self.operator_category.setCurrentIndex(0)
        self.overlay_category.setEnabled(False)
        self.overlay_category.setCurrentIndex(0)
        self.power_category.setEnabled(False)
        self.power_category.setCurrentIndex(0)
        self.station_category.setEnabled(False)
        self.station_category.setCurrentIndex(0)
        self.transmitter_category.setEnabled(False)
        self.transmitter_category.setCurrentIndex(0)
        self.operators.clear()
        self.operators.setEnabled(False)
        self.soapbox.clear()
        self.soapbox.setEnabled(False)
        self.sent_exchange.clear()
        self.sent_exchange.setEnabled(False)
        self.start_date.clear()
        self.start_date.setDate(QDate(2000, 1, 1))
        self.start_date.setTime(QTime(0, 0, 0))
        self.start_date.setEnabled(False)

    def edit_contest(self, index):
        if index == -1 or not self.select_contest.itemData(index):
            self.clear_form()
        else:
            self.populate_form(self.select_contest.itemData(index))

    def new_contest(self):
        self.clear_form()
        self.select_contest.setCurrentIndex(0)
        c = Contest()
        c.start_date = (datetime.datetime.now() + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        self.populate_form(c)

    def save_contest(self):
        if not self.contest:
            return
        self.contest.fk_contest_meta = self.fk_contest.currentData()
        self.contest.fk_station = self.fk_station.currentData()
        self.contest.assisted_category = self.assisted_category.currentText()
        self.contest.band_category = self.band_category.currentText()
        self.contest.mode_category = self.mode_category.currentText()
        self.contest.operator_category = self.operator_category.currentText()
        self.contest.overlay_category = self.overlay_category.currentText()
        self.contest.power_category = self.power_category.currentText()
        self.contest.station_category = self.station_category.currentText()
        self.contest.transmitter_category = self.transmitter_category.currentText()
        self.contest.operators = self.operators.text()
        self.contest.soapbox = self.soapbox.toPlainText()
        self.contest.sent_exchange = self.sent_exchange.text()
        self.contest.start_date = self.start_date.dateTime().toPyDateTime()

        self.contest.save()
        self.populate_contest_select(self.contest)

    def activate_contest(self):
        if not self.contest:
            return

        if self.settings['active_contest_id'] == self.contest.id:
            return

        self.settings['active_contest_id'] = self.contest.id
        fsutils.write_settings({'active_contest_id': self.contest.id})
        self.populate_contest_select(self.contest)
        appevent.emit(ContestActive(self.contest))

    def delete_contest(self):
        if self.settings['active_contest_id'] == self.contest.id:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Conteset Settings")
            dlg.setText("Cannot delete the currently ACTIVE contest. Activate a different contest first.")
            dlg.exec()
        else:
            qso_count = QsoLog.select().where(QsoLog.fk_contest == self.contest).count()

            result = QMessageBox.question(self, f"Delete Contest with {qso_count} QSO logs",
                                          f"Are you sure you want to delete contest "
                                          f"{self.contest.start_date.date()} - {self.contest.fk_contest_meta.display_name}? "
                                          f"TODO show number of QSOs. "
                                          f"All associated # of QSO logs will also be removed.",
                                          )
            if result == QMessageBox.StandardButton.Yes:
                self.contest.deleted = True
                self.contest.save()
                # foreign keys should still work as the station and contest are not actually removed from the table
                DeletedQsoLog.insert_from(
                    query=QsoLog.select().where(QsoLog.fk_contest == self.contest),
                    fields=list(QsoLog._meta.sorted_field_names))
                QsoLog.delete().where(QsoLog.fk_contest == self.contest)
                self.populate_contest_select()

    def contest_meta_changed(self):
        """if the contest type (meta) is changed and this is a new conteset (not saved yet), then fill in
        default values from the contest plugin
        """
        if self.contest and not self.contest.id:
            plugin = contests_by_cabrillo_id[self.fk_contest.currentData().cabrillo_name]
            values = plugin.get_suggested_contest_setup()

            for name in ['assisted_category', 'band_category', 'operator_category', 'overlay_category', 'power_category', 'station_category', 'transmitter_category']:
                if name in values:
                    self.select_item(getattr(self, name), values[name])
                else:
                    getattr(self, name).setCurrentIndex(0)
            if 'sent_exchange' in values:
                self.sent_exchange.setText(values['sent_exchange'])
            else:
                self.sent_exchange.clear()

            if 'start_date' in values:
                self.start_date.setDate(values['start_date'])
            if 'start_time' in values:
                self.start_date.setTime(values['start_time'])
