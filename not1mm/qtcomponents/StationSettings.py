"""Edit Settings Dialog"""
import datetime
import logging
import typing

from PyQt6 import QtWidgets, uic, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QMessageBox, QAbstractItemView

from not1mm import fsutils
from not1mm.lib import event as appevent
from not1mm.lib.bigcty import BigCty
from not1mm.lib.ham_utility import gridtolatlon
from not1mm.model import Station

logger = logging.getLogger(__name__)


class StationSettings(QtWidgets.QDialog):
    """Edit Station Settings"""

    table_station: QTableWidget
    button_close: QPushButton
    select_station: QComboBox

    station: Station = None

    bigcty = BigCty(fsutils.APP_DATA_PATH / "cty.json")

    def __init__(self, app_data_path, parent=None):
        super(StationSettings, self).__init__(parent)
        uic.loadUi(app_data_path / 'StationSettings.ui', self)
        self.settings = fsutils.read_settings()

        self.button_close.clicked.connect(self.close)
        self.table_station.verticalHeader().setSectionsMovable(True)
        self.table_station.verticalHeader().sectionMoved.connect(self.row_order_update)
        self.button_save.clicked.connect(self.save_station_table)
        self.button_delete.clicked.connect(self.delete_station)
        self.button_new.clicked.connect(self.new_station)
        self.select_station.currentIndexChanged.connect(self.edit_station)

        self.table_station.itemChanged.connect(self.item_edit)
        self.table_station.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.populate_select()

        if not self.station:
            # first run, new station
            s = Station()
            s.station_name = 'My Base Station'
            s.callsign = "K6GTE"
            self.populate_station_table(s)

    def populate_select(self):
        self.select_station.clear()
        active_station_id = self.settings.get("active_station_id", None)
        found_active = False
        for station in Station.select().where(Station.deleted != True).order_by(Station.id.desc()):
            name = station.station_name
            if active_station_id == station.id:
                name = f"[ACTIVE] {name}"
                self.station = station
                found_active = True
            self.select_station.addItem(name, station)
            if active_station_id == station.id:
                self.select_station.setCurrentIndex(self.select_station.count()-1)
        if not found_active and 'active_station_id' in self.settings:
            # make sure settings doesn't get out of sync with db
            del self.settings['active_station_id']

    def get_fields(self):
        """return ordered list of station model fields"""
        # TODO load station field order from settings
        field_columns = list(Station._meta.sorted_field_names)
        for i in ['id', 'deleted']:
            field_columns.remove(i)
        return field_columns

    def row_order_update(self):
        # TODO persist and load the station row order from settings
        pass

    def populate_station_table(self, station: Station):
        self.station = station
        field_columns = self.get_fields()
        self.table_station.clear()
        self.table_station.setRowCount(len(field_columns))
        self.table_station.setColumnCount(1)
        self.table_station.setVerticalHeaderLabels(field_columns)

        for i, name in enumerate(field_columns):
            value = getattr(station, name)
            item = QTableWidgetItem(str(value) if value else None)
            item.setFlags(Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
            if name == 'gridsquare':
                item.setToolTip("This 4-8 character maidenhead grid square will set other location based station properties.")

            self.table_station.setItem(i, 0, item)

    def item_edit(self, item: QTableWidgetItem):
        fields = self.get_fields()
        field = fields[item.row()]
        if field == Station.gridsquare.name:
            self.grid_change(item.text())
        if field == Station.callsign.name:
            self.call_change(item.text())

    def grid_change(self, grid):
        """Populated the Lat and Lon fields when the gridsquare changes"""
        if grid:
            lat, lon = gridtolatlon(grid)
            self.set_if_empty(Station.latitude.name, round(lat, 4))
            self.set_if_empty(Station.longitude.name, round(lon, 4))


    def call_change(self, call):
        """Populate zones"""
        if call:
            results = self.bigcty.find_call_match(call)
            if results:
                self.set_if_empty(Station.cq_zone.name, results.get("cq", ""))
                self.set_if_empty(Station.itu_zone.name, results.get("itu", ""))
                self.set_if_empty(Station.country.name, results.get("entity", ""))
                self.set_if_empty(Station.continent.name, results.get("continent", ""))
                self.set_if_empty(Station.dxcc.name, results.get("dxcc", ""))

    def set_if_empty(self, field_name, value):
        item = self.table_station.item(self.get_fields().index(field_name), 0)
        if item and not item.text():
            item.setText(str(value))

    def closeEvent(self, event: typing.Optional[QtGui.QCloseEvent]) -> None:
        if not self.settings.get('active_station_id', None):
            event.ignore()
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Station Settings Required")
            dlg.setText("You must define a station to continue. The basic information required is station"
                        " callsign and the station's name. A 6 character grid square is also useful.")
            dlg.exec()

    def save_station_table(self):
        for row, field in enumerate(self.get_fields()):
            value = self.table_station.item(row, 0).text()
            if field == 'callsign':
                value = value.upper()
            setattr(self.station, field, value or None) # empty strings become null

        self.station.save()
        self.settings['active_station_id'] = self.station.id
        fsutils.write_settings({'active_station_id': self.station.id})
        appevent.emit(appevent.StationActivated(self.station))
        self.populate_select()
        # If there is no active contest, close this dialog to enable less confusing on-boarding flow.
        # The main window will open the contest edit window.
        if not self.settings.get('active_contest_id', None):
            self.close()

    def delete_station(self):
        active_station_id = self.settings.get("active_station_id", None)
        if active_station_id == self.select_station.currentData().id:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Station Settings")
            dlg.setText(
                "Cannot delete the currently ACTIVE Station. Select and Save a different station first.")
            dlg.exec()
        else:
            station = self.select_station.currentData()
            result = QMessageBox.question(self, "Delete Station",
                                       f"Are you sure you want to delete station {station.station_name}?",
                                       )
            if result == QMessageBox.StandardButton.Yes:
                station.deleted = True
                station.save()
                self.populate_select()

    def edit_station(self, index):
        if index == -1:
            self.table_station.clear()
        else:
            self.populate_station_table(self.select_station.itemData(index))

    def new_station(self):
        s = Station()
        s.station_name = f"New Station {datetime.datetime.now().isoformat(timespec='seconds')}"
        s.callsign = 'VE9AA'
        s.save()
        self.select_station.addItem(s.station_name, s)
        self.select_station.setCurrentIndex(self.select_station.count()-1)
