import logging
from typing import Callable

from PyQt6.QtCore import pyqtSignal, Qt, QObject

from .event_model import *

"""
Use emit to send an event object to all listeners

Use register to listen for events for the specified event type
"""

logger = logging.getLogger(__name__)


class SignalWrapper(QObject):
    signal = pyqtSignal(AppEvent)

_signals: dict[type(AppEvent), SignalWrapper] = {}


def register(event_type: type(AppEvent), callback: Callable[[type(AppEvent)], None]):
    """
    Slots still process in the main qt loop. Batch work should be done in a qthread.
    """
    if event_type not in _signals:
        _signals[event_type] = SignalWrapper()

    _signals[event_type].signal.connect(callback, Qt.ConnectionType.QueuedConnection)

def emit(event: AppEvent):
    logger.debug(f'Emitting event {event}')
    s = _signals.get(type(event), None)
    if s:
        s.signal.emit(event)

def callback(e: CallChanged):
    print(e.call)

if __name__ == '__main__':
    e = CallChanged('VEEEE')

    register(CallChanged, callback)
    emit(e)
