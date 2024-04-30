#!/usr/bin/env python3
"""
Display current log
"""
# pylint: disable=no-name-in-module, unused-import, no-member, c-extension-no-member
# pylint: disable=logging-fstring-interpolation, too-many-lines

import copy
import logging
import os
from datetime import datetime

from PyQt6 import QtGui, QtWidgets, uic
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, pyqtSignal, QByteArray
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

from . import fsutils
from .contest import contests_by_cabrillo_id
from .contest.AbstractContest import AbstractContest
from .lib import event as appevent
from .lib import flags
from .model import QsoLog, Contest, DeletedQsoLog
from .qsoeditwindow import QsoEditWindow
from .qtcomponents.DockWidget import DockWidget
from .qtcomponents.QsoFieldDelegate import QsoFieldDelegate, handle_set_data, get_table_data, field_display_names

logger = logging.getLogger(__name__)

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

    def data(self, index: QModelIndex, role: Qt.ItemDataRole = None):

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole or role == Qt.ItemDataRole.FontRole:
            column_name = self._columns[index.column()]
            return get_table_data(self._data[index.row()], column_name, role)

        if role == Qt.ItemDataRole.UserRole:
            # custom sort values that may differ from the display value
            column_name = self._columns[index.column()]
            if column_name == '_flag':
                return self._data[index.row()].dxcc or -1
            if column_name.startswith("_"):
                return None
            val = getattr(self._data[index.row()], column_name)
            if column_name in ['freq', 'freq_rx'] and val:
                return val
            if isinstance(val, datetime):
                return val.strftime('%Y-%m-%d %H:%M:%S')
            # default to display value
            return get_table_data(self._data[index.row()], column_name)

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

        result = handle_set_data(record, column, value)
        if result:
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
                return field_display_names.get(self._columns[section], self._columns[section])

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


class LogWindow(DockWidget):

    db_file_name: str = None
    edit_contact_dialog = None
    contest: Contest = None
    contest_plugin_class: AbstractContest = None

    qsoTable: QTableView = None
    stationHistoryTable: QTableView = None
    qsoModel: QsoTableModel = None
    stationHistoryModel: QsoTableModel = None
    active_call: str = None

    edit_sheet_did_edit = False


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
        self.qsoTable.setItemDelegate(QsoFieldDelegate(self))
        self.stationHistoryTable.setItemDelegate(QsoFieldDelegate(self))
        self.qsoTable.setSortingEnabled(True)

        self.qsoTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.qsoTable.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.qsoTable.horizontalHeader().sectionMoved.connect(self.header_section_moved)
        self.qsoTable.horizontalHeader().sectionResized.connect(self.header_section_resized)

        edit_action = QAction("Open Edit Sheet", self.qsoTable)
        edit_action.triggered.connect(self.action_edit)
        self.qsoTable.addAction(edit_action)
        sep = QAction("|", self.qsoTable)
        sep.setSeparator(True)
        self.qsoTable.addAction(sep)

        delete_action = QAction("Delete QSO(s)", self.qsoTable)
        delete_action.triggered.connect(self.action_delete)
        self.qsoTable.addAction(delete_action)

        self.stationHistoryTable.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        delete_action = QAction("Delete QSO(s)", self.stationHistoryTable)
        delete_action.triggered.connect(self.action_delete)
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

        logger.debug(f"self contest id {self.contest.id}, cabrillo {self.contest.fk_contest_meta.cabrillo_name}")

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
            f"QSO Log - {self.db_file_name} - ({self.contest.id}){self.contest.fk_contest_meta.display_name}"
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
            sort_model.setSortRole(Qt.ItemDataRole.UserRole)
            self.qsoTable.setModel(sort_model)

    def event_qso_added(self, event: appevent.QsoAdded):
        self.populate_qso_log()

        # scroll to new item if the table is sorted by timestamp
        sorted_label = self.qsoTable.model().headerData(self.qsoTable.horizontalHeader().sortIndicatorSection(), Qt.Orientation.Horizontal)
        if sorted_label == field_display_names.get('time_on', 'time_on'):
            if self.qsoTable.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder:
                # on top
                self.qsoTable.selectRow(0)
                self.qsoTable.scrollTo(self.qsoTable.model().index(0, 0))
            else:
                # on botton
                self.qsoTable.selectRow(self.qsoTable.model().rowCount()-1)
                self.qsoTable.scrollTo(self.qsoTable.model().index(self.qsoTable.model().rowCount()-1, 0))

    def event_call_changed(self, event: appevent.CallChanged):
        # keep the previous call active after insert
        if event.call != "" or self.active_call is None:
            if len(event.call) < 3:
                self.active_call = ''
            else:
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

        # TODO handle slash prefixes and slash suffix (/M /P) appropriately
        # prioritize exact match
        history = QsoLog.select().where(QsoLog.fk_contest == self.contest).where(QsoLog.call == call)
        if len(history) == 0:
            history = QsoLog.get_logs_by_like_call(call, self.contest)

        self.stationHistoryModel.replaceDataset(history)

    def action_delete(self):
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

    def action_edit(self):
        """open a edit sheet for the selected qso"""
        selection = self.qsoTable.selectedIndexes()
        rows = set([x.row() for x in selection])
        if rows and len(rows) == 1:
            index = self.qsoTable.model().mapToSource(selection[0]).row()
            self.qso_to_edit = self.qsoModel.getDataset()[index]
            if self.qso_to_edit:
                edit_window = QsoEditWindow(self.qso_to_edit, parent=self.parent(), is_dockable=False, contest=self.contest)
                edit_window.setFloating(True)
                edit_window.show()
                edit_window.model.edited.connect(self.edit_sheet_edit)
                edit_window.closed.connect(self.edit_sheet_closed)

    def edit_sheet_edit(self, qso_record_before: QsoLog, qso_record_after: QsoLog):
        """ When edits are made, the edited value will potentially need to be reflected in the tables"""
        qso_record_after.save()
        appevent.emit(appevent.QsoUpdated(qso_record_before, qso_record_after))

    def edit_sheet_closed(self, event):
        """ When edits are made, the edited value will potentially need to be reflected in the tables"""
        if event.source.model.did_make_changes:
            self.populate_matching_qsos(self.active_call)
            self.populate_qso_log()

    def table_model_edit(self, qso_record_before: QsoLog, qso_record_after: QsoLog):
        """ When edits are made, the edited value will potentially need to be reflected in the other table if they
        are both showing the same record"""
        appevent.emit(appevent.QsoUpdated(qso_record_before, qso_record_after))
        # only need to potentially update the other table since the edits are reflected in memory on the edited table
        if self.sender() == self.qsoModel and len(self.stationHistoryModel.getDataset()) > 0:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()

    def table_model_delete(self, qso_records: list[QsoLog]):
        for qso_record in qso_records:
            appevent.emit(appevent.QsoDeleted(qso_record))
        # only need to potentially update the other table since the row is removed reflected in memory
        if self.sender() == self.qsoModel and len(self.stationHistoryModel.getDataset()) > 0:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()

    def header_section_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int):
        # replicate changes to station history table
        self.save_settings()

    def header_section_resized(self, logical_index: int, old_size: int, new_size: int):
        # replicate changes to station history table
        # changing dark mode will reset the column widths back and forth so make sure the user
        # is actively resizing the columns
        if self.qsoTable.hasFocus():
            self.save_settings()

    def save_settings(self):
        """settings are the column order and size.
        The qt state is copied from the main qso table to the history table so that the table columns are identical
        The qt state is persisted and reloaded whenever the contest is loaded
        """
        self.stationHistoryTable.horizontalHeader().restoreState(self.qsoTable.horizontalHeader().saveState())
        self.stationHistoryTable.horizontalHeader().setSectionsMovable(False)
        self.stationHistoryTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        if self.contest:
            column_state = self.qsoTable.horizontalHeader().saveState()
            self.contest.merge_settings({"qso_table_column_state": bytes(column_state.toHex()).decode('ascii')})

    def load_settings(self):
        """
        sets the column order and size from saved state. history table mimics the main table and it's columns
        are reset to non interactive
        """
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


