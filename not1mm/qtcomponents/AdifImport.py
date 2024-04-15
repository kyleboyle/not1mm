import typing

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QWidget


class AdifImport(QtWidgets.QDialog):
    def __init__(self, parent = None) -> None:
        super().__init__(parent)