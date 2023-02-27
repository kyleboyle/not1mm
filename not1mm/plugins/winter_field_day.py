from PyQt5 import QtWidgets

name = "Winter Field Day"
# 1 once per contest, 2 work each band, 3 each band/mode, 4 no dupe checking
mode = "BOTH"  # CW SSB BOTH RTTY
dupe_type = 4


def interface(self):
    self.field1.hide()
    self.field2.hide()
    self.field3.show()
    self.field4.show()
    label = self.field3.findChild(QtWidgets.QLabel)
    label.setText("Class")
    label = self.field4.findChild(QtWidgets.QLabel)
    label.setText("Section")


def set_tab_next(self):
    self.tab_next = {
        self.callsign: self.field1.findChild(QtWidgets.QLineEdit),
        self.field1.findChild(QtWidgets.QLineEdit): self.field2.findChild(
            QtWidgets.QLineEdit
        ),
        self.field2.findChild(QtWidgets.QLineEdit): self.field3.findChild(
            QtWidgets.QLineEdit
        ),
        self.field3.findChild(QtWidgets.QLineEdit): self.field4.findChild(
            QtWidgets.QLineEdit
        ),
        self.field4.findChild(QtWidgets.QLineEdit): self.callsign,
    }
