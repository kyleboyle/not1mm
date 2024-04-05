from typing import Optional, Callable

from PyQt6.QtCore import QObject, QEvent, pyqtSignal, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLineEdit


class EmacsCursorEventFilter(QObject):
    """emulate some emacs cursor movement shortcuts"""
    mark_active: bool = False

    def __init__(self, parent=None):
        super(EmacsCursorEventFilter, self).__init__(parent)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]) -> bool:
        if event.type() == QEvent.Type.KeyPress and type(source) == QLineEdit:
            box: QLineEdit = source
            modifiers = event.modifiers()
            if modifiers == Qt.KeyboardModifier.MetaModifier:
                if event.key() == Qt.Key.Key_Space:
                    if self.mark_active:
                        box.deselect()
                    self.mark_active = not self.mark_active
                elif event.key() == Qt.Key.Key_E:
                    box.end(self.mark_active)
                elif event.key() == Qt.Key.Key_A:
                    box.home(self.mark_active)
                elif event.key() == Qt.Key.Key_F:
                    box.cursorForward(self.mark_active)
                elif event.key() == Qt.Key.Key_B:
                    box.cursorBackward(self.mark_active)
                elif event.key() == Qt.Key.Key_D:
                    self.mark_active = False
                    # delete selected text or character in front of cursor
                    if box.selectedText():
                        box.backspace()
                    else:
                        current_pos = box.cursorPosition()
                        box.cursorForward(True)
                        if box.cursorPosition() != current_pos:
                            box.backspace()
                elif event.key() == Qt.Key.Key_K:
                    self.mark_active = False
                    # delete selected text or character in front of cursor
                    if box.selectedText():
                        box.backspace()
                    else:
                        current_pos = box.cursorPosition()
                        box.end(True)
                        if box.cursorPosition() != current_pos:
                            box.backspace()
                elif event.key() == Qt.Key.Key_G:
                    box.deselect()
                    self.mark_active = False

        elif event.type() == QEvent.Type.FocusIn:
            self.mark_active = False

        return super(EmacsCursorEventFilter, self).eventFilter(source, event)


