import json
import logging
import typing
import uuid
from dataclasses import dataclass
from datetime import datetime

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem, QLineEdit, QComboBox, QDateTimeEdit
from peewee import FloatField

from qsourcelogger.lib import hamutils
from qsourcelogger.model import QsoLog, Contest, Station, Enums

logger = logging.getLogger(__name__)
_monospace_font = QFont()
_monospace_font.setFamily("Roboto Mono")


field_display_names = {
    'time_on': 'timestamp',
    '_flag': '',
    'srx': 'serial_rcv',
    'srx_string': 'exch_rcv',
    'stx': 'serial_snt',
    'stx_string': 'exch_snt',
    'force_init': 'eme_initial'
}


@dataclass
class EnumEditor:
    current_value: str
    values: list
    editable: typing.Optional[bool] = False


class QsoFieldDelegate(QStyledItemDelegate):
    """
    Overrides default edit widgets based on data coming in from the qso model.

    For Doubles/Floats the default delegate will create a double spinner which truncates 2 decimal places. this is
    unacceptable for normal doubles like lat/lon so this uses a normal text edit for floats.

    For adif enumerations a custom data type is provided (EnumEditor) for models to use in the EditRole so that this can
    construct a combo box for selecting predefined values.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def setModelData(self, editor: typing.Optional[QWidget], model: typing.Optional[QtCore.QAbstractItemModel],
                     index: QtCore.QModelIndex) -> None:
        if isinstance(editor, QLineEdit):
            input: QLineEdit = editor
            model.setData(index, input.text(), Qt.ItemDataRole.EditRole)
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def setEditorData(self, editor: typing.Optional[QWidget], index: QtCore.QModelIndex) -> None:
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(value, float):
            editor.setText(str(value))
        elif isinstance(value, EnumEditor) and editor.property('enum'):
            if value.editable or (value.current_value and value.current_value not in value.values):
                # if the provided value is not in the enum, allow it to exist as an editable value
                editor.setEditable(True)
            else:
                editor.setEditable(False)
            editor.setCurrentText(value.current_value)
        else:
            super().setEditorData(editor, index)

    def createEditor(self, parent: typing.Optional[QWidget], option: QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> typing.Optional[QWidget]:
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if isinstance(value, float):
            # the default delegate will create a double spinner which truncates 2 decimal places. this
            # is a freeform text box. model should validate valid values.
            editor = QLineEdit(parent)
            editor.setFrame(False)
            return editor
        elif isinstance(value, EnumEditor):
            editor = QComboBox(parent)
            editor.setProperty('enum', value)
            editor.addItem("")
            for v in value.values:
                if isinstance(v, tuple):
                    editor.addItem(v[0])
                else:
                    editor.addItem(v)
            return editor
        generic = super().createEditor(parent, option, index)
        if isinstance(generic, QDateTimeEdit):
            generic.setCalendarPopup(True)
            generic.setDisplayFormat('yyyy-MM-dd HH:mm:ss')
        return generic

def handle_set_data(qso: QsoLog, field_name: str, value ) -> bool:
    if value == '':
        value = None
    if isinstance(value, QDateTime):
        value = value.toPyDateTime()
    if getattr(qso, field_name) == value:
        logger.warning(f"abort edit qso record for {qso.id}, {field_name} = {value}, value is not different")
        return False
    logger.info(f"update qso record for {qso.id}, {field_name} = {value}")
    if field_name == 'freq':
        band = hamutils.adif.common.convert_freq_to_band(int(value) / 1000_000)
        if not band:
            raise Exception(f"Frequency {value} does not fall within a band")
        qso.band = band
        value = int(value)
    elif field_name == 'freq_rx':
        qso.band_rx = hamutils.adif.common.convert_freq_to_band(int(value) / 1000_000)
        value = int(value)
    elif field_name == 'call':
        value = value.strip().upper()
        #TODO re-generate other dependent fields?

    if isinstance(qso._meta.fields.get(field_name), FloatField):
        try:
            value = float(value)
        except ValueError:
            return False
    elif field_name == 'other' and value:
        value = json.loads(value)
    setattr(qso, field_name, value)
    return True


def get_table_data(qso: typing.Optional[QsoLog], field_name: str, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole):

    if role == Qt.ItemDataRole.DisplayRole:
        if field_name.startswith('_'):
            return None
        val = getattr(qso, field_name)
        if isinstance(val, datetime):
            return val.strftime('%Y-%b-%d %H:%M:%S')
        if isinstance(val, uuid.UUID) or isinstance(val, dict):
            return str(val)
        if isinstance(val, Contest):
            return f"({val.id}){val.fk_contest_meta.display_name}"
        if isinstance(val, Station):
            return val.station_name
        if field_name in ['freq', 'freq_rx'] and val:
            return f'{val:,}'.replace(',', '.')
        return val

    if role == Qt.ItemDataRole.EditRole:
        val = getattr(qso, field_name)
        if isinstance(val, datetime):
            return QDateTime(val.date(), val.time())
        if field_name == 'mode':
            return EnumEditor(val, Enums.adif_enums['mode'])
        elif field_name == 'submode':
            if qso.mode in Enums.adif_enums['sub_mode_by_parent_mode']:
                return EnumEditor(val, Enums.adif_enums['sub_mode_by_parent_mode'][qso.mode])
            else:
                return EnumEditor(val, Enums.adif_enums['sub_mode'])
        elif field_name == 'arrl_sect' or field_name == 'my_arrl_sect':
            return EnumEditor(val, [x[0] for x in Enums.adif_enums['arrl_sect']], True)
        elif field_name in Enums.qso_field_enum_map.keys():
            return EnumEditor(val, Enums.adif_enums[Enums.qso_field_enum_map[field_name]])
        elif field_name == 'other' and val:
            return json.dumps(val)

        return val

    if role == Qt.ItemDataRole.FontRole and field_name in ('time_on', 'call', 'freq', 'freq_rx', 'time_off', 'rst_sent', 'rst_rcvd'):
        return _monospace_font
