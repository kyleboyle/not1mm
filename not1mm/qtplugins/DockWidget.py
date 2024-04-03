import typing

from PyQt6 import QtGui
from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QDockWidget


class DockWidget(QDockWidget):

    closed = pyqtSignal(QEvent)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def closeEvent(self, event: typing.Optional[QtGui.QCloseEvent]) -> None:
        super().closeEvent(event)
        event.source = self
        self.closed.emit(event)


