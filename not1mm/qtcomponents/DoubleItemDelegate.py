import typing

from PyQt6 import QtCore
from PyQt6.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem


class DoubleItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def updateEditorGeometry(self, editor: typing.Optional[QWidget], option: QStyleOptionViewItem,
                             index: QtCore.QModelIndex) -> None:
        super().updateEditorGeometry(editor, option, index)

    def setModelData(self, editor: typing.Optional[QWidget], model: typing.Optional[QtCore.QAbstractItemModel],
                     index: QtCore.QModelIndex) -> None:
        super().setModelData(editor, model, index)

    def setEditorData(self, editor: typing.Optional[QWidget], index: QtCore.QModelIndex) -> None:
        super().setEditorData(editor, index)

    def createEditor(self, parent: typing.Optional[QWidget], option: QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> typing.Optional[QWidget]:
        return super().createEditor(parent, option, index)