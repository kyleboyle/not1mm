import typing

from PyQt6 import QtGui, QtCore
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QLineEdit, QSizePolicy

"""
Widget for each main window qso entry field. dynamically generated for each contest type.
"""

class LineEdit(QLineEdit):
    focused = pyqtSignal(QLineEdit)

    def __init__(self, parent=None):
        super().__init__(parent)

    def focusInEvent(self, event: typing.Optional[QtGui.QFocusEvent]) -> None:
        super().focusInEvent(event)
        self.focused.emit(self)

class QsoEntryField(QFrame):
    label: QLabel
    input_field: LineEdit

    def __init__(self, field_name, field_label, parent=None):
        super().__init__(parent)
        self.setObjectName(field_name + '_frame')
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setObjectName(field_name + "_layout")
        self.setLayout(layout)
        self.label = QLabel(field_label)
        self.label.setObjectName(field_name + "_label")
        self.label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.label)

        self.input_field = LineEdit(self)
        self.input_field.setObjectName(field_name + "_input")
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        self.input_field.setSizePolicy(size_policy)
        self.input_field.setMinimumSize(QSize(0, 0))
        self.input_field.setMaximumSize(QSize(16777215, 16777215))
        self.input_field.setFrame(True)
        layout.addWidget(self.input_field)

