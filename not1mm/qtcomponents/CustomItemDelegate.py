import typing
from dataclasses import dataclass

from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem, QLineEdit, QComboBox


@dataclass
class EnumEditor:
    current_value: str
    values: list
    editable: typing.Optional[bool] = False


class CustomItemDelegate(QStyledItemDelegate):
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
        return super().createEditor(parent, option, index)
