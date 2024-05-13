import copy
import logging
import pickle
import typing

from PyQt6 import uic, QtWidgets, QtCore
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QMimeData, pyqtSignal, QTimer

from qsourcelogger import fsutils
from qsourcelogger.contest import contests_by_cabrillo_id
from qsourcelogger.model import QsoLog, Contest
from qsourcelogger.qtcomponents.DockWidget import DockWidget
from qsourcelogger.qtcomponents.QsoFieldDelegate import QsoFieldDelegate, handle_set_data, get_table_data, field_display_names
from qsourcelogger.qtcomponents.SvgIcon import SvgIcon

logger = logging.getLogger(__name__)

_default_field_structure = [
    ('Main', ['time_on', 'call', 'rst_sent', 'rst_rcvd', 'freq', 'band', 'mode', 'submode', 'name', 'comment',
              'distance', 'freq_rx', 'band_rx', 'force_init', 'time_off',]),
    ('Contact',
     ['address', 'state', 've_prov', 'country', 'continent', 'gridsquare', 'lat', 'lon', 'gridsquare_ext', 'dxcc',
      'prefix', 'email', 'cqz', 'ituz', 'arrl_sect', 'wpx_prefix', 'qth', 'county', 'region', 'altitude',
      'age', 'contacted_op', 'guest_op', 'notes', 'prop_mode', 'qso_complete', 'qso_random',
      'sat_mode', 'sat_name', 'silent_key', 'swl', 'usaca_counties', 'vucc_grids']),
    ('Their Station', ['ant_path', 'ant_az', 'ant_el', 'eq_call', 'rig', 'rx_pwr', 'web']),
    ('My Station', ['station_callsign', 'operator',
                    'owner_callsign', 'tx_pwr', 'my_altitude', 'my_antenna',
                    'my_ant_az', 'my_ant_el', 'my_arrl_sect', 'my_city', 'my_county', 'my_country', 'my_cq_zone',
                    'my_dxcc', 'my_fists', 'my_gridsquare', 'my_gridsquare_ext',
                    'my_iota', 'my_iota_island_id', 'my_itu_zone', 'my_lat', 'my_lon', 'my_name', 'my_postal_code',
                    'my_pota_ref', 'my_rig', 'my_sig', 'my_sig_info', 'my_sota_ref',
                    'my_state', 'my_street', 'my_usaca_counties', 'my_vucc_grids', 'my_wwff_ref', ]),
    ('SIG', ['pota_ref', 'wwff_ref', 'iota', 'sota_ref', 'iota_island_id', 'sig', 'sig_info']),
    ('Contest Fields',
     ['stx', 'stx_string', 'srx', 'srx_string', 'points', 'check', 'class_contest', 'contest_id', 'fists', 'fists_cc',
      'precedence', 'skcc', 'ten_ten', 'uksmg']),
    ('Conditions', ['a_index', 'k_index', 'max_bursts', 'ms_shower', 'nr_bursts', 'nr_pings', 'sfi', 'transmitter_id']),
    ('Awards',
     ['award_granted', 'award_submitted', 'clublog_qso_upload_date', 'clublog_qso_upload_status', 'credit_granted',
      'credit_submitted', 'darc_dok',
      'eqsl_qsl_rcvd', 'eqsl_qslrdate', 'eqsl_qsl_sent', 'eqsl_qslsdate', 'hamlogeu_qso_upload_date',
      'hamlogeu_qso_upload_status', 'hamqth_qso_upload_date', 'hamqth_qso_upload_status', 'hrdlog_qso_upload_date',
      'hrdlog_qso_upload_status',
      'lotw_qsl_rcvd', 'lotw_qsl_sent', 'lotw_qslrdate', 'lotw_qslsdate', 'qrzcom_qso_upload_date',
      'qrzcom_qso_upload_status', 'qsl_rcvd', 'qsl_rcvd_via', 'qsl_sent', 'qsl_sent_via', 'qsl_via', 'qslmsg',
      'qslrdate', 'qslsdate', ]),
    ('Internal', ['id', 'public_key', 'other', 'is_original', 'hostname', 'is_run', 'fk_station', 'fk_contest']),
]


def _show_info_message_box(message: str) -> None:
    message_box = QtWidgets.QMessageBox()
    message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
    message_box.setText(message)
    message_box.setWindowTitle("Information")
    message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    _ = message_box.exec()

class SheetModel(QAbstractItemModel):
    qso: QsoLog = None
    structure: list[tuple[str, list[str]]] = []
    child_to_parent: dict[str, str]
    category_list: list[str]

    edited = pyqtSignal(QsoLog, QsoLog, str, object)
    did_make_changes = False
    pinned_fields = set()

    def __init__(self, parent):
        QAbstractItemModel.__init__(self, parent)

    def set_qso(self, qso: QsoLog):

        self.beginResetModel()
        self.did_make_changes = False
        self.qso = qso
        self.endResetModel()

    def set_row_structure(self, structure: list[tuple[str, list[str]]]):
        self.structure = structure
        self.category_list = [x[0] for x in self.structure]
        self.child_to_parent = {}
        for p in self.structure:
            for c in p[1]:
                self.child_to_parent[c] = p[0]
        # sanity check on field inclusion. check to make sure all fields from qso log are made available
        for name in QsoLog._meta.sorted_field_names:
            if name not in self.child_to_parent:
                logger.warning(f"qso field {name} not included in any category by default, adding to Internal")
                self.child_to_parent[name] = 'Internal'
                self.structure[self.category_list.index('Internal')][1].append(name)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "Field"
            elif section == 1:
                return "Value"
        return None

    def index(self, row: int, column: int, parent_index: QModelIndex = None) -> QModelIndex:
        if self.hasIndex(row, column, parent_index):
            # hasIndex has already called rowCount to initialize children
            if not parent_index.isValid():
                return self.createIndex(row, column, self.structure[row][0])
            else:
                child_list = self.structure[self.category_list.index(parent_index.internalPointer())][1]
                return self.createIndex(row, column, child_list[row])
        else:
            return QModelIndex()

    def parent(self, child_index: QModelIndex) -> QModelIndex:
        if child_index.isValid() and child_index.internalPointer() in self.child_to_parent:
            parent_category = self.child_to_parent[child_index.internalPointer()]
            if parent_category:
                parent_row = self.category_list.index(parent_category)
                return QtCore.QAbstractItemModel.createIndex(self, parent_row, 0, parent_category)
        return QtCore.QModelIndex()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent_index: QModelIndex = None) -> int:
        if parent_index and parent_index.isValid():
            if parent_index.internalPointer() in self.child_to_parent:
                # children fields have no children rows
                return 0
            return len(self.structure[parent_index.row()][1])
        return len(self.structure)

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> typing.Any:
        if role == Qt.ItemDataRole.DisplayRole:
            if index.parent().row() == -1:
                # this is a category
                if index.column() == 0:
                    return self.structure[index.row()][0]
            elif index.parent().row() >= 0:
                # a child qso field, not a category
                field_name = index.internalPointer()
                if index.column() == 0:
                    # field name label
                    return field_display_names.get(field_name, field_name)
                elif self.qso and index.column() == 1:
                    # field value use common code
                    return get_table_data(self.qso, field_name, role)
        elif index.parent().row() >= 0 and self.qso and index.column() == 1:
            # handle value columm
            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole or role == Qt.ItemDataRole.FontRole:
                # return common value cell data
                field_name = index.internalPointer()
                return get_table_data(self.qso, field_name, role)
            elif role == Qt.ItemDataRole.DecorationRole and index.internalPointer() in self.pinned_fields:
                return SvgIcon('pin_full_rounded', rotate=25).get_icon()


    def setData(self, index: QtCore.QModelIndex, value: typing.Any, role: Qt.ItemDataRole = None) -> bool:
        record_before = copy.deepcopy(self.qso)
        field_name = index.internalPointer()
        try:
            result = handle_set_data(self.qso, field_name, value)
            if result:
                self.dataChanged.emit(index, index)
                self.edited.emit(record_before, self.qso, field_name, value)
                self.did_make_changes = True
                return True
        except Exception as e:
            logger.exception("Problem saving qso log")
            _show_info_message_box(str(e))
        return False

    def set_pin_state(self, index: QtCore.QModelIndex, is_pinned: bool):
        if is_pinned:
            self.pinned_fields.add(index.internalPointer())
        else:
            self.pinned_fields.remove(index.internalPointer())
        self.dataChanged.emit(index, index)

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlag:
        if index.column() in [0]:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == 1:
            if index.parent().row == -1:
                # this is a category
                return Qt.ItemFlag.ItemIsEnabled
            elif index.parent().row() >= 0:
                field_name = self.structure[index.parent().row()][1][index.row()]
                if field_name:
                    # disable editing for these fields
                    if field_name in ('id', 'fk_contest', 'fk_station'):
                        return Qt.ItemFlag.NoItemFlags
                    if field_name.startswith("_"):
                        return Qt.ItemFlag.ItemIsEnabled
                    # normal fields that can be edited
                    return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                else:
                    return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled

    def dropMimeData(self, data: typing.Optional[QMimeData], action: Qt.DropAction, row: int, column: int,
                     parent: QModelIndex) -> bool:
        fields_to_move = pickle.loads(data.data('application/x-qabstractitemmodeldatalist'))
        logger.debug(f"Drop mime data {fields_to_move[0]} action {action}, row {row} column {column}, parent {parent.row()} {parent.internalPointer()}")
        move_to = parent.internalPointer()
        # handle the drop operation by figuring out the correct inputs for the model moveRows call which are:
        # source parent index and source row index
        # target parent index and target row index
        ret = True
        if move_to and fields_to_move:
            for field_name, source_parent_row, source_parent_parent_row, source_row in reversed(fields_to_move):

                # reconstruct the source parent index as qmodelindex cannot be serialized
                source_parent_index = self.index(source_parent_row, 0,
                           QModelIndex() if source_parent_parent_row == -1 else self.index(source_parent_parent_row, 0,
                                                                                           QModelIndex()))
                if source_parent_index.row() == -1:
                    source_parent_index = QModelIndex()

                target_parent_index = parent
                target_row = row

                if target_parent_index.internalPointer() in self.child_to_parent:
                    # if the drop was onto a child field, set the row move target to the category item and
                    # the row to the child field's row
                    target_row = target_parent_index.row()
                    target_parent_index = target_parent_index.parent()
                elif target_parent_index.internalPointer() in self.category_list and row == -1:
                    # the drop was onto a category so put it at the end
                    target_row = len(self.structure[self.category_list.index(target_parent_index.internalPointer())][1])

                if source_parent_index.row() == -1 and target_parent_index != -1:
                    # a category is being dropped. it should be replacing whatever category it was dropped on / in
                    target_row = target_parent_index.row()
                    target_parent_index = target_parent_index.parent()

                ret = ret & self.moveRows(source_parent_index, source_row, 1, target_parent_index, target_row)

        return ret

    def moveRows(self, sourceParent: QModelIndex, sourceRow: int, count: int, destinationParent: QModelIndex,
                 destinationRow: int) -> bool:

        logger.debug(f"move Rows count {count} source parent {sourceParent.internalPointer()} source row: {sourceRow}, "
                     f"destinationParent {destinationParent.internalPointer()}  destinationRow {destinationRow} ")
        if count != 1:
            return False

        self.beginMoveRows(sourceParent, sourceRow, count, destinationParent, destinationRow)
        # update our internal structure
        if sourceParent.row() == -1 and destinationParent.row() == -1:
            # category move
            self.structure.insert(destinationRow, self.structure.pop(sourceRow))

        elif sourceParent.internalPointer() in self.category_list:
            field = self.structure[sourceParent.row()][1].pop(sourceRow)
            self.structure[destinationParent.row()][1].insert(destinationRow, field)

        self.set_row_structure(self.structure)
        self.endMoveRows()

        return True

    def mimeData(self, indexes: typing.Iterable[QModelIndex]) -> typing.Optional[QMimeData]:
        items_to_move = []
        for i in indexes:
            if i.internalPointer() and (i.internalPointer() in self.child_to_parent or i.internalPointer() in self.category_list):
                logger.debug(f"trying to drag item {i.internalPointer()}")
                # can't pickle the qt index object, so pickle some native info recontruct in the drop handler
                items_to_move.append((i.internalPointer(), i.parent().row(), i.parent().parent().row(), i.row()))
        if items_to_move:
            mime = QMimeData()
            mime.setData('application/x-qabstractitemmodeldatalist', pickle.dumps(items_to_move))
            return mime

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction


class QsoEditWindow(DockWidget):
    table_qso: QtWidgets.QTreeView
    model: SheetModel
    contest: Contest

    def __init__(self, qso: typing.Optional[QsoLog], parent=None, is_in_progress=True, contest=None):
        super().__init__(parent)
        self.contest = contest

        uic.loadUi(fsutils.APP_DATA_PATH / "qso_edit_sheet.ui", self)

        if not is_in_progress:
            # if the edit sheet is not the 'in progress' qso, force it to be floating only and not integrated into the
            # docking widgets
            self.setFloating(True)
            self.setAllowedAreas(Qt.DockWidgetArea.NoDockWidgetArea)

        if qso:
            self.setObjectName(f"qsoedit_{qso.id}")
            self.setWindowTitle(f"QSO {qso.call} at {qso.time_on.isoformat(timespec='minutes')}")

        self.model = SheetModel(parent=self)

        self.table_qso.setIndentation(15)
        self.table_qso.clicked.connect(self.on_clicked)
        self.table_qso.setModel(self.model)

        self.table_qso.setItemDelegateForColumn(1, QsoFieldDelegate())

        self.table_qso.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)

        self.set_contest(contest)
        self.set_qso(qso)
        self.table_qso.header().setSectionsMovable(False)
        self.model.rowsMoved.connect(self.save_settings)

        if is_in_progress:
            self.table_qso.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            self.action_setup()

    def on_clicked(self, index):
        if not index.parent().isValid():
            self.table_qso.setExpanded(index, not self.table_qso.isExpanded(index))
            if self.table_qso.isExpanded(index):
                QTimer.singleShot(0, lambda: self.table_qso.header().setSectionResizeMode(0,
                                             QtWidgets.QHeaderView.ResizeMode.ResizeToContents))

    def action_setup(self):
        pin = self.table_qso.addAction(SvgIcon('pin_full_rounded').get_icon(), "Pin Field")
        unpin = self.table_qso.addAction("Remove Field Pin")
        sep = self.table_qso.addAction("|")
        sep.setSeparator(True)
        unpin_all = self.table_qso.addAction("Unpin All")
        pin.triggered.connect(self.action_pin)
        unpin.triggered.connect(self.action_unpin)
        unpin_all.triggered.connect(self.action_unpin_all)

    def action_pin(self):
        indexes = self.table_qso.selectedIndexes()
        for column in indexes:
            if column.parent().row() != -1 and column.column() == 1:
                field_name = column.internalPointer()
                if field_name:
                    pinned_settings = self.contest.get_setting('pinned_fields', {})
                    if field_name not in pinned_settings:
                        pinned_settings[field_name] = None
                        self.contest.merge_settings({'pinned_fields': pinned_settings})
                        self.model.set_pin_state(column, True)

    def action_unpin(self):
        indexes = self.table_qso.selectedIndexes()
        for column in indexes:
            if column.parent().row() != -1 and column.column() == 1:
                field_name = column.internalPointer()
                if field_name:
                    pinned_settings: list = self.contest.get_setting('pinned_fields', {})
                    if field_name in pinned_settings:
                        del pinned_settings[field_name]
                        self.contest.merge_settings({'pinned_fields': pinned_settings})
                        self.model.set_pin_state(column, False)

    def action_unpin_all(self):
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        message_box.setText(f"Unpin Fields")
        message_box.setInformativeText(f"Are you sure you would like to unpin all field values?")
        message_box.setWindowTitle("Confirm Unpin")
        message_box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel)
        result = message_box.exec()
        if result != QtWidgets.QMessageBox.StandardButton.Ok:
            return
        self.contest.merge_settings({'pinned_fields': {}})
        self.model.pinned_fields = set(self.contest.get_setting("pinned_fields", {}))
        self.set_qso(self.model.qso)

    def set_contest(self, contest: Contest):
        if contest is not None:
            self.reset_layout_for_contest(contest)

    def set_qso(self, qso: QsoLog):
        scroll_pos = self.table_qso.verticalScrollBar().value()
        # cache category expanded state to restore after dataset reset
        expanded_state = [self.table_qso.isExpanded(self.model.index(row, 0, QModelIndex()))
                          for row in range(self.model.rowCount())]
        main_index = self.model.category_list.index('Main')

        self.model.set_qso(qso) # can be None

        for i in range(len(self.model.category_list)):
            self.table_qso.setFirstColumnSpanned(i, QModelIndex(), True)

        if not any(expanded_state):
            self.table_qso.setExpanded(self.table_qso.model().index(main_index, 0, QModelIndex()), True)
        else:
            for row, is_expanded in enumerate(expanded_state):
                self.table_qso.setExpanded(self.table_qso.model().index(row, 0, QModelIndex()), is_expanded)
            QTimer.singleShot(0, lambda: self.table_qso.scroll(0, scroll_pos))
            QTimer.singleShot(0, lambda: self.table_qso.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents))

    def reset_layout_for_contest(self, contest: Contest) -> None:
        if not contest:
            return
        # Contests will have different fields that they are using. make sure those fields appear in the main section
        self.contest = contest
        plugin_class = contests_by_cabrillo_id[self.contest.fk_contest_meta.cabrillo_name]
        # restore row order from previous session
        field_structure = self.contest.get_setting("qso_edit_sheet_row_structure") or _default_field_structure

        # make sure contest fields are in main section
        contest_fields = plugin_class.get_preferred_column_order()
        for c in field_structure:
            if c[0] == 'Main':
                # add contest fields to Main
                for f in contest_fields:
                    if f not in c[1]:
                        c[1].append(f)
            else:
                # remove contest fields from other categories
                for f in contest_fields:
                    if f in c[1]:
                        c[1].remove(f)
        self.model.pinned_fields = set(self.contest.get_setting("pinned_fields", {}).keys())
        self.model.set_row_structure(field_structure)


    def save_settings(self):
        if self.model and self.model.structure:
            self.contest.merge_settings({"qso_edit_sheet_row_structure": self.model.structure})

