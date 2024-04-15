#!/usr/bin/env python3
"""
Display current log
"""
# pylint: disable=no-name-in-module, unused-import, no-member, c-extension-no-member
# pylint: disable=logging-fstring-interpolation, too-many-lines

import logging
import os
import copy
import uuid
from datetime import datetime

import hamutils.adif.common
import typing
from PyQt6 import QtGui, QtWidgets, uic
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, pyqtSignal, QDateTime, QByteArray
from PyQt6.QtGui import QFont, QAction, QIcon
from PyQt6.QtWidgets import QTableView, QHeaderView, QAbstractItemView
from peewee import DoubleField, FloatField

import not1mm.fsutils as fsutils
from not1mm.contest.AbstractContest import AbstractContest
import not1mm.lib.event as appevent
from not1mm.lib import flags
from not1mm.model import QsoLog, Contest, DeletedQsoLog, Station, Enums
from not1mm.contest import contests_by_cabrillo_id
from not1mm.qtcomponents.CustomItemDelegate import CustomItemDelegate, EnumEditor

logger = logging.getLogger(__name__)

_monospace_font = QFont()
_monospace_font.setFamily("Roboto Mono")

_column_names = {
    'time_on': 'timestamp',
    '_flag': '',
    'srx': 'serial_rcv',
    'stx': 'serial_snt',
}

def _show_info_message_box(message: str) -> None:
    message_box = QtWidgets.QMessageBox()
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
    message_box.setText(message)
    message_box.setWindowTitle("Information")
    message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    _ = message_box.exec()

def get_default_column_list():
    col = list(QsoLog._meta.sorted_field_names)
    col.remove('id')
    col.remove('time_on')
    col.remove('call')
    col.insert(0, 'call')
    col.insert(0, 'time_on')
    col.insert(0, '_flag')
    col.append('id')
    return col

class QsoTableModel(QAbstractTableModel):
    edited = pyqtSignal(QsoLog, QsoLog)
    deleted = pyqtSignal(list)

    _columns = []

    _data: list[QsoLog] = None

    def __init__(self, data):
        super(QAbstractTableModel, self).__init__()
        self._data = data

    def setColumnOrder(self, column_list):
        self._columns = get_default_column_list()
        index = self._columns.index('call') + 1
        for col in column_list:
            if col == 'time_on' or col == 'call':
                continue
            self._columns.remove(col)
            self._columns.insert(index, col)
            index += 1

    def getDataset(self):
        return self._data

    def replaceDataset(self, data):
        self.beginResetModel()
        self._data = list(data)
        self.endResetModel()

    def data(self, index: QModelIndex, role:  Qt.ItemDataRole = None):

        if role == Qt.ItemDataRole.DisplayRole:
            column_name = self._columns[index.column()]
            if column_name.startswith('_'):
                return None
            val = getattr(self._data[index.row()], column_name)
            if isinstance(val, datetime):
                return val.strftime('%Y-%b-%d %H:%M:%S')
            if isinstance(val, uuid.UUID) or isinstance(val, dict):
                return str(val)
            if isinstance(val, Contest):
                return f"({val.id}){val.fk_contest_meta.display_name}"
            if isinstance(val, Station):
                return val.station_name
            if column_name in ['freq', 'freq_rx']:
                return f'{val:,}'.replace(',', '.')
            return val

        if role == Qt.ItemDataRole.EditRole:
            column_name = self._columns[index.column()]
            val = getattr(self._data[index.row()], column_name)
            if isinstance(val, datetime):
                return QDateTime(val.date(), val.time())
            if column_name == 'rst_sent' or column_name == 'rst_received':
                return int(val)
            if column_name == 'mode':
                return EnumEditor(val, Enums.adif_enums['mode'])
            elif column_name == 'submode':
                qso = self._data[index.row()]
                if qso.mode in Enums.adif_enums['sub_mode_by_parent_mode']:
                    return EnumEditor(val, Enums.adif_enums['sub_mode_by_parent_mode'][qso.mode])
                else:
                    return EnumEditor(val, Enums.adif_enums['sub_mode'])
            elif column_name == 'arrl_sect' or column_name == 'my_arrl_sect':
                return EnumEditor(val, [x[0] for x in Enums.adif_enums['arrl_sect']], True)
            elif column_name in Enums.qso_field_enum_map.keys():
                return EnumEditor(val, Enums.adif_enums[Enums.qso_field_enum_map[column_name]])
            return val

        if role == Qt.ItemDataRole.FontRole and self._columns[index.column()] in ('time_on', 'call', 'freq', 'freq_rx', 'time_off', 'rst_sent', 'rst_rcvd'):
            return _monospace_font

        if role == Qt.ItemDataRole.DecorationRole and self._columns[index.column()] == '_flag':
            qso = self._data[index.row()]
            if qso.dxcc:
                return flags.get_pixmap(qso.dxcc, 20)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            column_name = self._columns[index.column()]
            if column_name.startswith('_'):
                return None
            if column_name in ['rst_sent', 'rst_rcvd'] \
                or isinstance(getattr(self._data[index.row()], column_name), float):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

    def rowCount(self, parent: QModelIndex = None):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, parent: QModelIndex = None):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._columns)

    def setData(self, index: QModelIndex, value, role: Qt.ItemDataRole = None):
        record = self._data[index.row()]
        record_before = copy.deepcopy(record)
        column = self._columns[index.column()]

        if isinstance(value, QDateTime):
            value = value.toPyDateTime()
        if getattr(record, column) == value:
            logger.warning(f"abort edit qso record for {record.id}, {column} = {value}, value is not different")
            return False
        logger.warning(f"update db qso record for {record.id}, {column} = {value}")
        if column == 'freq':
            record.band = hamutils.adif.common.convert_freq_to_band(int(value) / 1000_000)
        if column == 'freq_rx':
            record.band_rx = hamutils.adif.common.convert_freq_to_band(int(value) / 1000_000)
        #TODO re-generate other dependent fields

        if isinstance(record._meta.fields.get(column), FloatField):
            try:
                value = float(value)
            except ValueError:
                return False
        setattr(record, column, value)
        try:
            record.save()
            self.edited.emit(record_before, record)
            return True
        except Exception as e:
            logger.exception("Problem saving qso log")
            _show_info_message_box(str(e))
        return False

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return _column_names.get(self._columns[section], self._columns[section])

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        column_name = self._columns[index.column()]
        # disable editing for these fields
        if column_name in ('id', 'fk_contest', 'fk_station'):
            return Qt.ItemFlag.NoItemFlags
        if column_name.startswith("_"):
            return Qt.ItemFlag.ItemIsEnabled

        # normal fields that can be edited
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def removeRows(self, row: int, count: int, parent: QModelIndex = None) -> bool:
        self.beginRemoveRows(parent, row, row + count - 1)
        removed = self._data[row:row + count]
        del self._data[row:row+count]
        result = True
        for record in removed:
            logger.debug(f"deleting row from table & db {record.id}")
            DeletedQsoLog.insert_from(
                query=QsoLog.select().where(QsoLog.id == record.id),
                fields=list(QsoLog._meta.sorted_field_names)).execute()
            record.delete_instance()
        self.endRemoveRows()
        self.deleted.emit(removed)
        return result


class LogWindow(QtWidgets.QDockWidget):

    db_file_name: str = None
    edit_contact_dialog = None
    contest: Contest = None
    contest_plugin_class: AbstractContest = None

    qsoTable: QTableView = None
    stationHistoryTable: QTableView = None
    qsoModel: QsoTableModel = None
    stationHistoryModel: QsoTableModel = None
    active_call: str = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.qsoModel = QsoTableModel([])
        self.stationHistoryModel = QsoTableModel([])

        uic.loadUi(fsutils.APP_DATA_PATH / "logwindow.ui", self)

        self.checkmark = QtGui.QPixmap(str(fsutils.APP_DATA_PATH / "check.png"))
        self.checkicon = QtGui.QIcon()
        self.checkicon.addPixmap(self.checkmark)

        self.qsoTable.verticalHeader().setVisible(False)
        self.stationHistoryTable.verticalHeader().setVisible(False)
        self.qsoTable.setItemDelegate(CustomItemDelegate(self))
        self.stationHistoryTable.setItemDelegate(CustomItemDelegate(self))
        self.qsoTable.setSortingEnabled(True)

        self.qsoTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.qsoTable.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.qsoTable.horizontalHeader().sectionMoved.connect(self.header_section_moved)
        self.qsoTable.horizontalHeader().sectionResized.connect(self.header_section_resized)

        delete_action = QAction("Delete QSO(s)", self.qsoTable)
        delete_action.triggered.connect(self.delete_action)
        self.qsoTable.addAction(delete_action)

        self.stationHistoryTable.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        delete_action = QAction("Delete QSO(s)", self.stationHistoryTable)
        delete_action.triggered.connect(self.delete_action)
        self.stationHistoryTable.addAction(delete_action)

        self.qsoModel.edited.connect(self.table_model_edit)
        self.qsoModel.deleted.connect(self.table_model_delete)
        self.stationHistoryModel.edited.connect(self.table_model_edit)
        self.stationHistoryModel.deleted.connect(self.table_model_delete)

        appevent.register(appevent.CallChanged, self.event_call_changed)
        appevent.register(appevent.ContestActivated, self.event_contest_activated)
        appevent.register(appevent.GetActiveContestResponse, self.event_active_contest_response)
        appevent.register(appevent.QsoAdded, self.event_qso_added)

        appevent.emit(appevent.GetActiveContest())

    def reset_table_for_contest(self, contest: Contest) -> None:
        if not contest:
            return

        if self.contest:
            self.save_settings()

        self.contest = contest
        self.contest_plugin_class = contests_by_cabrillo_id[self.contest.fk_contest_meta.cabrillo_name]

        self.db_file_name = os.path.basename(fsutils.read_settings().get("current_database"))

        self.populate_qso_log()

        self.qsoModel.setColumnOrder(self.contest_plugin_class.get_preferred_column_order())
        self.stationHistoryModel.setColumnOrder(self.contest_plugin_class.get_preferred_column_order())
        self.qsoModel.replaceDataset(self.qsoModel.getDataset())
        self.stationHistoryModel.replaceDataset(self.stationHistoryModel.getDataset())

        self.load_settings()


    def populate_qso_log(self) -> None:
        self.setWindowTitle(
            f"QSO Log - {self.db_file_name} - ({self.contest.id}){self.contest.fk_contest_meta.name}"
            f"[{self.contest.start_date.date()}]"
            f" - {QsoLog.select().where(QsoLog.fk_contest == self.contest).count()}"
        )
        logger.debug("Getting Log")
        # TODO paging
        current_log = QsoLog.select().where(QsoLog.fk_contest == self.contest).order_by(QsoLog.time_on.desc())
        self.qsoModel.replaceDataset(current_log)

        if not self.qsoTable.model():
            sort_model = QSortFilterProxyModel(self)
            sort_model.setSourceModel(self.qsoModel)
            self.qsoTable.setModel(sort_model)

    def event_qso_added(self, event: appevent.QsoAdded):
        self.populate_qso_log()
        # TODO select and scroll to new qso (don't focus)

    def event_call_changed(self, event: appevent.CallChanged):
        self.active_call = event.call
        self.populate_matching_qsos(self.active_call)

    def event_contest_activated(self, event: appevent.ContestActivated):
        self.reset_table_for_contest(event.contest)

    def event_active_contest_response(self, event: appevent.GetActiveContestResponse):
        self.reset_table_for_contest(event.contest)

    def populate_matching_qsos(self, call: str) -> None:
        if not self.stationHistoryTable.model():
            self.stationHistoryTable.setModel(self.stationHistoryModel)

        if call == "":
            self.stationHistoryModel.replaceDataset([])
            return

        # prioritize exact match
        history = QsoLog.select().where(QsoLog.fk_contest == self.contest).where(QsoLog.call == call)
        if len(history) == 0:
            history = QsoLog.get_logs_by_like_call(call, self.contest)

        self.stationHistoryModel.replaceDataset(history)

    def delete_action(self):
        table = self.qsoTable if self.qsoTable.hasFocus() else self.stationHistoryTable

        selection = table.selectedIndexes()
        rows = set([x.row() for x in selection])

        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        message_box.setText(f"{len(rows)} QSO record(s) selected for deletion.")
        message_box.setInformativeText(f"Are you sure you would like to delete all of these {len(rows)} QSO logs?")
        message_box.setWindowTitle("Confirm Delete")
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel)
        result = message_box.exec()
        if result != QtWidgets.QMessageBox.StandardButton.Ok:
            return

        logger.debug(f"deleting {rows}")

        for i in sorted(rows, reverse=True):
            table.model().removeRow(i)

    def table_model_edit(self, qso_record_before: QsoLog, qso_record_after: QsoLog):
        appevent.emit(appevent.QsoUpdated(qso_record_before, qso_record_after))
        # only need to potentially update the other table since the edits are reflected in memory on the edited table
        if self.sender() == self.qsoModel:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()

    def table_model_delete(self, qso_records: list[QsoLog]):
        for qso_record in qso_records:
            appevent.emit(appevent.QsoDeleted(qso_record))
        # only need to potentially update the other table since the row is removed reflected in memory
        if self.sender() == self.qsoModel:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()

    def header_section_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int):
        # replicate changes to station history table
        self.save_settings()

    def header_section_resized(self, logical_index: int, old_size: int, new_size: int):
        # replicate changes to station history table
        self.save_settings()

    def save_settings(self):
        self.stationHistoryTable.horizontalHeader().restoreState(self.qsoTable.horizontalHeader().saveState())
        self.stationHistoryTable.horizontalHeader().setSectionsMovable(False)
        self.stationHistoryTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        if self.contest:
            column_state = self.qsoTable.horizontalHeader().saveState()
            self.contest.merge_settings({"qso_table_column_state": bytes(column_state.toHex()).decode('ascii')})

    def load_settings(self):
        state = self.contest.get_setting("qso_table_column_state")
        if state:
            self.qsoTable.horizontalHeader().restoreState(
                QByteArray.fromHex(bytes(state, 'ascii')))
            self.stationHistoryTable.horizontalHeader().restoreState(
                QByteArray.fromHex(bytes(state, 'ascii')))
        else:
            flag_index = self.qsoModel._columns.index('_flag')
            if flag_index >= 0:
                self.qsoTable.resizeColumnToContents(self.qsoModel._columns.index('_flag'))
                self.qsoTable.columnWidth(flag_index)
                self.qsoTable.setColumnWidth(flag_index, self.qsoTable.columnWidth(flag_index) - 15)
            self.qsoTable.resizeColumnToContents(self.qsoModel._columns.index('time_on'))

        self.stationHistoryTable.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.qsoTable.sortByColumn(self.qsoModel._columns.index('time_on'), Qt.SortOrder.DescendingOrder)
        self.qsoTable.horizontalHeader().setSectionsMovable(True)
        self.stationHistoryTable.horizontalHeader().setSectionsMovable(False)
        self.stationHistoryTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)


