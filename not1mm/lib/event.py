import types
import weakref
from typing import Callable, Collection

from PyQt6.QtCore import QRunnable, pyqtSlot, QThreadPool

from event_model import *

"""
use emit to send an event object to all listeners

use register to listen for events
"""
_callbacks: dict[type(AppEvent), weakref.WeakSet] = {}

_isolated_callbacks: dict[type(AppEvent), weakref.WeakSet] = {}

_threadpool = QThreadPool()

def register(event_type: type(AppEvent), callback: Callable[[type(AppEvent)], None], isolated = False):
    target = _callbacks.setdefault(event_type, weakref.WeakSet())
    if isolated:
        target = _isolated_callbacks.setdefault(event_type, weakref.WeakSet())
    if isinstance(callback, types.MethodType):
        if not hasattr(callback.__self__, '__event_cb_stash'):
            # stash a strong reference to the bound callback to the callback owner. when the owner is deleted,
            # this weak ref will be cleaned up
            callback.__self__.__event_cb_ref_stash = dict()
        callback.__self__.__event_cb_ref_stash[id(callback)] = callback

    target.add(callback)


class _Worker(QRunnable):

    callback: Collection[Callable[[type(AppEvent)], None]] = None
    event: AppEvent = None

    def __init__(self, event: AppEvent, callbacks: Collection[Callable[[type(AppEvent)], None]]):
        super(_Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.callbacks = callbacks
        self.event = event

    @pyqtSlot()
    def run(self):
        for i in self.callbacks:
            i(self.event)


def emit(event: AppEvent):
    c = _callbacks.get(type(event), set())
    if c:
        _threadpool.start(_Worker(event, c))

    for i in _isolated_callbacks.get(type(event), set()):
        _threadpool.start(_Worker(event, [i]))


def callback(e: CallChanged):
    print(e.call)


if __name__ == '__main__':
    e = CallChanged('VEEEE')

    register(CallChanged, callback)
    emit(e)
