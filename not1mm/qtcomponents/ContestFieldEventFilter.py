from typing import Optional, Callable

from PyQt6.QtCore import QObject, QEvent, pyqtSignal, Qt
from PyQt6.QtWidgets import QLineEdit


class ContestFieldEventFilter(QObject):
    """
    Decouples events from event processing
    """
    field_signal = pyqtSignal(QLineEdit, QEvent)

    def __init__(self, callback: Callable[[Optional[QObject], Optional[QEvent]], None], parent=None):
        super(ContestFieldEventFilter, self).__init__(parent)
        self.callback = callback
        self.field_signal.connect(callback, Qt.ConnectionType.QueuedConnection)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        #print(f"{source.objectName()} event filter")
        if event.type() == QEvent.Type.FocusIn and isinstance(source, QLineEdit):
            self.field_signal.emit(source, event)


        return super(ContestFieldEventFilter, self).eventFilter(source, event)


