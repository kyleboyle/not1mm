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
        if event.type() == QEvent.Type.KeyPress and isinstance(source, QLineEdit):
            # can't pass events from eveint proces to a Qt.ConnectionType.QueuedConnection slot as it
            # appears the qevent objects get reused somewhere in the middle an dthe event at the slot is
            # not the same event
            #self.field_signal.emit(source, event)
            event.accept()
            self.callback(source, event)
        return super(ContestFieldEventFilter, self).eventFilter(source, event)


