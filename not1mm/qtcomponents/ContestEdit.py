"""New Contest Dialog"""
import datetime
import logging

import typing
from PyQt6 import uic, QtGui, QtWidgets
from PyQt6.QtCore import QDate, QTime, QEvent, QTimer, QModelIndex, QAbstractTableModel, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QComboBox, QPlainTextEdit, QDateTimeEdit, QLineEdit, QDialog, QPushButton, QMessageBox, \
    QTableView, QItemDelegate, QWidget, QAbstractItemView, QTabWidget

from not1mm import fsutils
from not1mm.contest.AbstractContest import ContestField
from not1mm.lib.event_model import ContestActivated
from not1mm.model import Contest, ContestMeta, Station, QsoLog, DeletedQsoLog
from not1mm.contest import contest_plugin_list, contests_by_cabrillo_id, GeneralLogging

import not1mm.lib.event as appevent

logger = logging.getLogger(__name__)


def _show_info_message_box(message: str) -> None:
    message_box = QtWidgets.QMessageBox()
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
    message_box.setText(message)
    message_box.setWindowTitle("Information")
    message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    _ = message_box.exec()


available_fields = ['[NextLine]', 'rst_sent', 'rst_rcvd', 'freq', 'band', 'mode', 'submode', 'name', 'comment',
                    'stx', 'stx_string', 'srx', 'srx_string', 'gridsquare', 'gridsquare_ext', 'qth', 'county',
                    'country', 'continent', 'state', 've_prov', 'dxcc', 'prefix', 'cqz', 'ituz', 'arrl_sect',
                    'wpx_prefix', 'pota_ref', 'wwff_ref', 'iota', 'sota_ref', 'station_callsign', 'distance', 'tx_pwr', 'a_index',
                    'address', 'age', 'altitude', 'ant_path', 'ant_az', 'ant_el', 'freq_rx', 'band_rx', 'check',
                    'class_contest', 'contacted_op', 'darc_dok', 'email', 'eq_call', 'fists', 'fists_cc', 'force_init',
                    'guest_op', 'iota_island_id', 'k_index', 'lat', 'lon', 'max_bursts', 'ms_shower', 'my_altitude',
                    'my_antenna', 'my_ant_az', 'my_ant_el', 'my_arrl_sect', 'my_city', 'my_county', 'my_country',
                    'my_cq_zone', 'my_dxcc', 'my_fists', 'my_gridsquare', 'my_gridsquare_ext', 'my_iota',
                    'my_iota_island_id', 'my_itu_zone', 'my_lat', 'my_lon', 'my_name', 'my_postal_code', 'my_pota_ref',
                    'my_rig', 'my_sig', 'my_sig_info', 'my_sota_ref', 'my_state', 'my_street', 'my_usaca_counties',
                    'my_vucc_grids', 'my_wwff_ref', 'notes', 'nr_bursts', 'nr_pings', 'operator', 'owner_callsign',
                    'precedence', 'prop_mode', 'public_key', 'qslmsg', 'qso_complete', 'qso_random', 'region', 'rig',
                    'rx_pwr', 'sat_mode', 'sat_name', 'sfi', 'sig', 'sig_info', 'skcc', 'swl', 'ten_ten', 'uksmg',
                    'usaca_counties', 'vucc_grids', 'web', 'transmitter_id']


class ComboDelegate(QItemDelegate):
    def __init__(self, parent, contest_field_names):
        super(ComboDelegate, self).__init__(parent)
        self.parent = parent
        self.fields = list(available_fields)
        for n in contest_field_names:
            if n in self.fields:
                self.fields.remove(n)

    def createEditor(self, parent, option, index):
        combobox = QComboBox(parent)
        combobox.addItems(self.fields)
        combobox.setEditable(False)
        return combobox

    def setEditorData(self, editor: typing.Optional[QWidget], index: QModelIndex) -> None:
        value = index.data()
        if value:
            editor.setCurrentText(value)


class EntryFieldModel(QAbstractTableModel):
    _data: list[dict] = None
    dirty = False
    _contest_fields: list[ContestField]

    def __init__(self, contest_fields: list[ContestField], configured_fields: list[dict]):
        super(QAbstractTableModel, self).__init__()
        self._contest_fields = contest_fields
        self._data = [vars(x) for x in contest_fields]
        if configured_fields:
            self._data.extend(configured_fields)

    def get_user_fields(self):
        return self._data[len(self._contest_fields):]

    def data(self, index: QModelIndex, role: Qt.ItemDataRole = None):
        if role == Qt.ItemDataRole.DisplayRole:
            if index.row() < len(self._data):
                field = self._data[index.row()]
                if index.column() == 0:
                    return field['name']
                if index.column() == 1:
                    return field['display_label']
                if index.column() == 2:
                    return field.get('space_tabs', False)
                if index.column() == 3:
                    return field['stretch_factor']
                if index.column() == 4:
                    return field.get('max_chars', 255)
        if role == Qt.ItemDataRole.EditRole:
            if index.row() < len(self._data):
                field = self._data[index.row()]
                if index.column() == 0:
                    return field['name']
                if index.column() == 1:
                    return field['display_label']
                if index.column() == 2:
                    return field['space_tabs']
                if index.column() == 3:
                    return field['stretch_factor']
                if index.column() == 4:
                    return field['max_chars']
            else:
                # no row defined yet set default values
                if index.column() == 2:
                    return False
                if index.column() == 4:
                    return 2
                if index.column() == 4:
                    return 255
        return None

    def rowCount(self, parent: QModelIndex = None):
        return len(self._data) + 1

    def columnCount(self, parent: QModelIndex = None):
        return 5

    def setData(self, index: QModelIndex, value: typing.Any, role: Qt.ItemDataRole = None) -> bool:
        try:
            if index.row() == len(self._data):
                self.beginInsertRows(QModelIndex(), index.row(), index.row())
                self._data.append(
                    {'name': '', 'display_label': '', 'space_tabs': False, 'stretch_factor': 2, 'max_chars': 255})
                self.endInsertRows()
            row = self._data[index.row()]
            if index.column() == 0:
                # make sure the user does not create duplicate fields
                if value != available_fields[0] and value in [f['name'] for f in self._data]:
                    return False
                row['name'] = value
                if not row['display_label']:
                    row['display_label'] = value

            if index.column() == 1:
                row['display_label'] = str(value)[:20]
            if index.column() == 2:
                row['space_tabs'] = bool(value)
            if index.column() == 3:
                row['stretch_factor'] = min(10, max(1, int(value)))
            if index.column() == 4:
                row['max_chars'] = min(255, max(1, int(value)))
            self.dataChanged.emit(index, index)
            self.dirty = True
            return True
        except Exception as e:
            logger.exception("Error editing field definitions")
            _show_info_message_box(str(e))
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ['QSO Field', 'Display Label', 'Space=Tab?', 'Stretch Weight', 'Max length'][section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if index.row() < len(self._contest_fields):
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def removeRows(self, row: int, count: int, parent: QModelIndex = None) -> bool:
        if row == len(self._data):
            return False
        self.beginRemoveRows(parent, row, row + count - 1)
        removed = self._data[row:row + count]
        del self._data[row:row + count]
        self.endRemoveRows()
        self.dirty = True
        return True


class ContestEdit(QtWidgets.QDialog):
    display_name: QLineEdit
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

    table_fields: QTableView
    tabWidget: QTabWidget

    def __init__(self, app_data_path, parent=None):
        super().__init__(parent)
        self.settings = fsutils.read_settings()
        uic.loadUi(app_data_path / "ContestEdit.ui", self)

        self.button_close.clicked.connect(self.close)
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

        self.tabWidget.currentChanged.connect(self.handle_tab_change)
        self.display_name.installEventFilter(self)

        self.clear_form()
        if self.settings.get("active_contest_id", None) is not None:
            # initial view = show the active contest
            c = Contest.select().where(Contest.id == self.settings.get("active_contest_id")).get_or_none()
            self.populate_contest_select(c)
            if c:
                self.populate_form(c)
            elif self.settings.get('active_contest_id'):
                del self.settings['active_contest_id']
        else:
            self.populate_contest_select()

    def populate_contest_select(self, select_contest: Contest = None):
        self.select_contest.clear()
        self.select_contest.addItem("", None)
        active_contest_id = self.settings.get("active_contest_id", None)
        found_active = False
        for contest in Contest.select().where(Contest.deleted != True).order_by(Contest.start_date.desc()):
            name = f"{contest.start_date.date()} {contest.fk_contest_meta.display_name} {contest.label or ''}".strip()
            if active_contest_id == contest.id:
                name = f"[ACTIVE] {name}"
                found_active = True
            self.select_contest.addItem(name, contest)
            if select_contest and select_contest.get_id() == contest.get_id():
                self.contest = contest
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
        self.tabWidget.setEnabled(True)

        if contest.fk_contest_meta_id:
            self.select_item(self.fk_contest, contest.fk_contest_meta.display_name)

        if contest.fk_station_id:
            self.select_item(self.fk_station, contest.fk_station.station_name)

        self.display_name.setText(contest.label)
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
        self.fk_contest.setFocus()

    def select_item(self, target: QComboBox, text: str) -> None:
        index = target.findText(text)
        if index >= 0:
            target.setCurrentIndex(index)

    def clear_form(self):
        self.contest = None
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.setEnabled(False)
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
        self.display_name.clear()

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
        # prefill default contest values
        self.contest_meta_changed()

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
        self.contest.label = self.display_name.text()
        self.contest.save()
        if self.field_table_save() and self.settings.get('active_contest_id', None) == self.contest.id:
            # if the entry fields have been updated, refresh the fields in the main window
            appevent.emit(ContestActivated(self.contest))

        self.populate_contest_select(self.contest)

    def activate_contest(self):
        # TODO activating a new contest didn't work
        if not self.contest:
            return

        if self.settings.get('active_contest_id', None) == self.contest.id:
            return

        self.settings['active_contest_id'] = self.contest.id
        fsutils.write_settings({'active_contest_id': self.contest.id})
        self.populate_contest_select(self.contest)
        logger.debug(f"self contest id {self.contest.id}, cabrillo {self.contest.fk_contest_meta.cabrillo_name}")
        appevent.emit(ContestActivated(self.contest))

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
                                          f"All associated {qso_count} QSO logs will also be removed.",
                                          )
            if result == QMessageBox.StandardButton.Yes:
                self.contest.deleted = True
                self.contest.save()
                # foreign keys should still work as the station and contest are not actually removed from the table
                DeletedQsoLog.insert_from(
                    query=QsoLog.select().where(QsoLog.fk_contest == self.contest),
                    fields=list(QsoLog._meta.sorted_field_names)).execute()
                QsoLog.delete().where(QsoLog.fk_contest == self.contest)
                self.populate_contest_select()

    def contest_meta_changed(self):
        """if the contest type (meta) is changed and this is a new contest (not saved yet), then fill in
        default values from the contest plugin
        """
        if self.contest and not self.contest.id:
            plugin = contests_by_cabrillo_id[self.fk_contest.currentData().cabrillo_name]
            values = plugin.get_suggested_contest_setup()

            for name in ['assisted_category', 'mode_category', 'band_category', 'operator_category', 'overlay_category', 'power_category', 'station_category', 'transmitter_category']:
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

    def closeEvent(self, event: typing.Optional[QtGui.QCloseEvent]) -> None:
        if not self.settings.get('active_contest_id', None):
            event.ignore()
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Contest Required")
            dlg.setText("You must create and activate a contest to continue. Go for General Logging to start with.")
            dlg.exec()


    def eventFilter(self, source, event: QEvent):
        if source == self.display_name:
            if event.type() == QEvent.Type.FocusIn:
                if self.display_name.text() == '':
                    self.display_name.setText(f"{self.fk_contest.currentText()} starting {self.start_date.date().toPyDate()}")
                    QTimer.singleShot(0, self.display_name.selectAll)
                    return True
        return False

    def handle_tab_change(self, index: int):
        if self.contest and self.tabWidget.currentWidget().objectName() == 'field_tab':
            if self.fk_contest.currentData() and self.fk_contest.currentData().cabrillo_name:
                self.setup_field_tab()

    def setup_field_tab(self):
        if self.contest:

            self.contest.fk_contest_meta = self.fk_contest.currentData()
            contest_plugin = contests_by_cabrillo_id[self.contest.fk_contest_meta.cabrillo_name](self.contest)
            contest_fields = list(contest_plugin.get_qso_fields())
            contest_fields.insert(0, ContestField(name="call", display_label="Callsign", space_tabs=True, stretch_factor=4, max_chars=20))
            user_fields = self.contest.get_setting('user_fields', None)

            force_model_dirty = False
            if user_fields is None and self.contest.id is None and isinstance(contest_plugin, GeneralLogging):
                # General logging by default doesn't provide any fields beyond call & rsts, so add example columns
                # for the user to start with (that mimic n1mm)
                user_fields = [{'name': 'name', 'display_label': 'Name', 'stretch_factor': 4, 'space_tabs': False, 'max_chars': 255},
                               {'name': 'comment', 'display_label': 'Comment', 'stretch_factor': 4, 'space_tabs': False, 'max_chars': 255}]
                force_model_dirty = True

            model = EntryFieldModel(contest_fields, user_fields)
            self.table_fields.setItemDelegateForColumn(0, ComboDelegate(self.table_fields, [f.name for f in contest_fields]))
            self.table_fields.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.table_fields.setModel(model)
            if force_model_dirty:
                model.dirty = True
            self.table_fields.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            delete_action = QAction("Remove Selected Row(s)", self.table_fields)
            delete_action.triggered.connect(self.field_table_action_delete)
            self.table_fields.addAction(delete_action)

    def field_table_action_delete(self):
        selection = self.table_fields.selectedIndexes()
        rows = set([x.row() for x in selection])
        rows = sorted(rows)
        for i in sorted(rows, reverse=True):
            self.table_fields.model().removeRow(i)

    def field_table_save(self) -> bool:
        if self.table_fields.model() and self.table_fields.model().dirty:
            user_fields = self.table_fields.model().get_user_fields()
            self.contest.merge_settings({'user_fields': user_fields})
            return True
        return False