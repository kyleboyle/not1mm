from PyQt6 import QtWidgets, uic
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from not1mm import fsutils


class About(QtWidgets.QDialog):
    label_logo: QLabel

    def __init__(self, app_data_path):
        parent = None
        super().__init__(parent)
        uic.loadUi(app_data_path / "about.ui", self)
        self.label_logo.setPixmap(QPixmap(str(fsutils.APP_DATA_PATH / 'qsource-128.png')))
