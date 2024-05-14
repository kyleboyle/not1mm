
from PyQt6 import QtWidgets, uic

from qsourcelogger import fsutils


class Spotsend(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(fsutils.APP_DATA_PATH / "spot_confirm.ui", self)

