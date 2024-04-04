#!/usr/bin/env python3
"""
Display current log
"""
# pylint: disable=no-name-in-module, unused-import, no-member, c-extension-no-member
# pylint: disable=logging-fstring-interpolation, too-many-lines

import logging
import os
from json import loads

from PyQt6 import QtGui, QtWidgets, uic
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, pyqtSignal
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

import not1mm.fsutils as fsutils
from not1mm.lib import ham_utility
from not1mm.lib.database import DataBase
import not1mm.lib.event as appevent

logger = logging.getLogger(__name__)

_column_names = {
    "TS": "Timestamp",
#    "Call" : "",
    "Freq": "Freq (Khz)",
    "QSXFreq" : "TXFreq",
#    "Mode" : "",
#    "ContestName" : "",
#    "SNT" : "",
#    "RCV" : "",
#    "CountryPrefix" : "",
#    "StationPrefix" : "",
#    "QTH" : "",
#    "Name" : "",
#    "Comment" : "",
    "NR" : "RecvNr",
#    "Sect" : "",
#    "Prec" : "",
#    "CK" : "",
#    "ZN" : "",
#    "SentNr" : "",
#    "Points" : "",
#    "IsMultiplier1" : "",
#    "IsMultiplier2" : "",
#    "Power" : "",
#    "Band" : "",
#    "WPXPrefix" : "",
#    "Exchange1" : "",
#    "RadioNR" : "",
#    "ContestNR" : "",
#    "isMultiplier3" : "",
#    "MiscText" : "",
#    "IsRunQSO" : "",
#    "ContactType" : "",
#    "Run1Run2" : "",
#    "GridSquare" : "",
#    "Operator" : "",
#    "Continent" : "",
#    "RoverLocation" : "",
#    "RadioInterfaced" : "",
#    "NetworkedCompNr" : "",
#    "IsOriginal" : "",
#    "ID" : "",
#    "CLAIMEDQSO" : "",
}

_default_column_order = [
    "TS",
    "Call",
    "Band",
    "Freq",
    "QSXFreq",
    "Mode",
    "SNT",
    "RCV",
    "Name",
    "Comment",
    "Power",

    "NR",
    "SentNr",
    "QTH",
    "Sect",
    "Prec",
    "CountryPrefix",
    "StationPrefix",
    "GridSquare",
    "CK",
    "ZN",
    "Points",
    "IsMultiplier1",
    "IsMultiplier2",
    "ContestName",
    "WPXPrefix",
    "Exchange1",
    "RadioNR",
    #"ContestNR",
    "isMultiplier3",
    "MiscText",
    "IsRunQSO",
    "ContactType",
    "Run1Run2",
    "Operator",
    "Continent",
    "RoverLocation",
    "RadioInterfaced",
    "NetworkedCompNr",
    "ID",
    "CLAIMEDQSO"]

_monospace_font = QFont()
_monospace_font.setFamily("JetBrains Mono")

class QsoTableModel(QAbstractTableModel):
    edited = pyqtSignal(dict, dict)
    deleted = pyqtSignal(list)

    _columns = list(_default_column_order)

    _data: list[dict] = None

    def __init__(self, data, database: DataBase):
        super(QAbstractTableModel, self).__init__()
        self._data = data
        self._db = database

    def setColumnOrder(self, column_list):
        self._columns = list(_default_column_order)
        index = 2
        for col in column_list:
            if col == 'TS' or col == 'Call':
                continue
            self._columns.remove(col)
            self._columns.insert(index, col)
            index += 1

    def getDataset(self):
        return self._data

    def replaceDataset(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def data(self, index: QModelIndex, role:  Qt.ItemDataRole = None):
        if role == Qt.ItemDataRole.DisplayRole:
            val = self._data[index.row()][self._columns[index.column()]]
            if self._columns[index.column()] == 'Band':
                return ham_utility.get_adif_band(val)
            return val

        if role == Qt.ItemDataRole.EditRole:
            return self._data[index.row()][self._columns[index.column()]]
        if role == Qt.ItemDataRole.FontRole and self._columns[index.column()] in ('TS', 'Call', 'Freq', 'QSXFreq'):
            return _monospace_font

    def rowCount(self, parent: QModelIndex = None):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, parent: QModelIndex = None):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._columns)

    def setData(self, index: QModelIndex, value, role: Qt.ItemDataRole = None):
        record = self._data[index.row()]
        record_before = dict(record)
        column = self._columns[index.column()]
        if record[column] == value:
            logger.warning(f"abort edit qso record for {record['ID']}, {column} = {value}, value is not different")
            return False
        logger.warning(f"update db qso record for {record['ID']}, {column} = {value}")
        if column == 'Freq':
            record['Band'] = float(ham_utility.get_logged_band(str(int(value * 1000))))

        record[column] = value
        if self._db.change_contact(record):
            self.edited.emit(record_before, record)
            return True
        return False

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return _column_names.get(self._columns[section], self._columns[section])

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        # disable editing for these fields
        if self._columns[index.column()] in ('ID', 'ContestName'):
            return Qt.ItemFlag.NoItemFlags

        # normal fields that can be edited
        return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def removeRows(self, row: int, count: int, parent: QModelIndex = None) -> bool:
        self.beginRemoveRows(parent, row, row + count - 1)
        removed = self._data[row:row + count]
        del self._data[row:row+count]
        result = True
        for record in removed:
            logger.debug(f"deleting row from table & db {record['ID']}")
            result &= self._db.delete_contact(record['ID'])
        self.endRemoveRows()
        self.deleted.emit(removed)
        return result

def safe_float(the_input: any, default=0.0) -> float:
    """
    Convert a string or int to a float.

    Parameters
    ----------
    the_input: any
    default: float, defaults to 0.0

    Returns
    -------
    float(input)
    or
    default value if error
    """
    if the_input:
        try:
            return float(input)
        except ValueError:
            return default
        except TypeError:
            return default
    return default


class LogWindow(QtWidgets.QDockWidget):
    """
    The main window
    """
    dbname = None
    edit_contact_dialog = None
    pref = {}

    qsoTable: QTableView = None
    stationHistoryTable: QTableView = None
    qsoModel: QsoTableModel = None
    stationHistoryModel: QsoTableModel = None
    active_call: str = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.load_pref()

        self.dbname = fsutils.USER_DATA_PATH / self.pref.get(
            "current_database", "ham.db"
        )
        self.database = DataBase(self.dbname, fsutils.USER_DATA_PATH)
        self.database.current_contest = self.pref.get("contest", 0)

        self.qsoModel = QsoTableModel([], self.database)
        self.stationHistoryModel = QsoTableModel([], self.database)

        uic.loadUi(fsutils.APP_DATA_PATH / "logwindow.ui", self)
        self.setWindowTitle(
            f"QSO History - {self.pref.get('current_database', 'ham.db')}"
        )
        
        self.checkmark = QtGui.QPixmap(str(fsutils.APP_DATA_PATH / "check.png"))
        self.checkicon = QtGui.QIcon()
        self.checkicon.addPixmap(self.checkmark)

        self.populate_qso_log()
        self.qsoTable.verticalHeader().setVisible(False)
        self.stationHistoryTable.verticalHeader().setVisible(False)
        self.qsoTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)


        self.qsoTable.setSortingEnabled(True)
        self.qsoTable.sortByColumn(0, Qt.SortOrder.DescendingOrder)

        self.qsoTable.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
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
        self.qsoTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        appevent.register(appevent.CallChanged, self.event_call_changed)
        appevent.register(appevent.ContestColumns, self.event_contest_columns)
        appevent.register(appevent.LoadDb, self.event_new_db)
        appevent.register(appevent.UpdateLog, self.event_update_log)

        appevent.emit(appevent.GetContestColumns())

    def load_pref(self) -> None:
        """
        Loads the preferences from the config file into the self.pref dictionary.

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
                    logger.info("%s", self.pref)
            else:
                self.pref["current_database"] = "ham.db"

        except IOError as exception:
            logger.critical("Error: %s", exception)

    def load_new_db(self) -> None:
        """
        If the database changes reload it.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.load_pref()
        self.dbname = fsutils.USER_DATA_PATH / self.pref.get(
            "current_database", "ham.db"
        )
        self.database.reload_db(self.dbname, fsutils.APP_DATA_PATH)
        self.database.current_contest = self.pref.get("contest", 0)

        self.contact = self.database.empty_contact

        self.populate_qso_log()
        self.setWindowTitle(
            f"Log Display - {self.pref.get('current_database', 'ham.db')}"
        )

    def populate_qso_log(self) -> None:
        """
        Get Log, Show it.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        logger.debug("Getting Log")
        current_log = self.database.fetch_all_contacts_desc()
        self.qsoModel.replaceDataset(current_log)
        if not self.qsoTable.model():
            sort_model = QSortFilterProxyModel(self)
            sort_model.setSourceModel(self.qsoModel)
            self.qsoTable.setModel(sort_model)
        self.qsoTable.resizeColumnsToContents()

    def event_update_log(self, event: appevent.UpdateLog):
        self.populate_qso_log()

    def event_call_changed(self, event: appevent.CallChanged):
        self.active_call = event.call
        self.populate_matching_qsos(self.active_call)

    def event_new_db(self, event: appevent.LoadDb):
        self.load_new_db()

    def event_contest_columns(self, event: appevent.ContestColumns):
        self.qsoModel.setColumnOrder(event.columns)
        self.stationHistoryModel.setColumnOrder(event.columns)

        # re-render the tables
        self.qsoModel.replaceDataset(self.qsoModel.getDataset())
        self.stationHistoryModel.replaceDataset(self.stationHistoryModel.getDataset())

    def populate_matching_qsos(self, call: str) -> None:
        if not self.stationHistoryTable.model():
            self.stationHistoryTable.setModel(self.stationHistoryModel)

        if call == "":
            self.stationHistoryModel.replaceDataset([])
            return

        db_records = self.database.fetch_like_calls(call)
        self.stationHistoryModel.replaceDataset(db_records)
        self.stationHistoryTable.resizeColumnToContents(0)
        self.stationHistoryTable.sortByColumn(0, Qt.SortOrder.DescendingOrder)


    def show_message_box(self, message: str) -> None:
        """
        Displays a dialog box with a message.

        Paramters
        ---------
        message : str

        Returns
        -------
        None
        """
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message_box.setText(message)
        message_box.setWindowTitle("Information")
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        _ = message_box.exec()

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

    def table_model_edit(self, qso_record_before: dict, qso_record_after: dict):
        appevent.emit(appevent.QsoUpdated(qso_record_before, qso_record_after))
        # only need to potentially update the other table since the edits are reflected in memory on the edited table
        if self.sender() == self.qsoModel:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()

    def table_model_delete(self, qso_records: list):
        for qso_record in qso_records:
            appevent.emit(appevent.QsoDeleted(qso_record))
        # only need to potentially update the other table since the row is removed reflected in memory
        if self.sender() == self.qsoModel:
            self.populate_matching_qsos(self.active_call)
        else:
            self.populate_qso_log()