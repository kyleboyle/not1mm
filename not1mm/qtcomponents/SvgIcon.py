from PyQt6.QtGui import QIcon
from qdarktheme._icon.icon_engine import SvgIconEngine
from qdarktheme._icon.svg import Svg

_svgs = {
    "pin": '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="m640-480 80 80v80H520v240l-40 40-40-40v-240H240v-80l80-80v-280h-40v-80h400v80h-40v280Zm-286 80h252l-46-46v-314H400v314l-46 46Zm126 0Z"/></svg>',
    "pin_full_rounded": '<svg xmlns="http://www.w3.org/2000/svg" enable-background="new 0 0 24 24" height="24px" viewBox="0 0 24 24" width="24px" fill="#000000"><g><rect fill="none" height="24" width="24"/><rect fill="none" height="24" width="24"/></g><g><path d="M19,12.87c0-0.47-0.34-0.85-0.8-0.98C16.93,11.54,16,10.38,16,9V4l1,0 c0.55,0,1-0.45,1-1c0-0.55-0.45-1-1-1H7C6.45,2,6,2.45,6,3c0,0.55,0.45,1,1,1l1,0v5c0,1.38-0.93,2.54-2.2,2.89 C5.34,12.02,5,12.4,5,12.87V13c0,0.55,0.45,1,1,1h4.98L11,21c0,0.55,0.45,1,1,1c0.55,0,1-0.45,1-1l-0.02-7H18c0.55,0,1-0.45,1-1 V12.87z" fill-rule="evenodd"/></g></svg>',
}


class SvgIcon(Svg):

    def __init__(self, id: str, rotate=None) -> None:
        if id in _svgs:
            self._source = _svgs[id]
            self._rotate = rotate
        else:
            super().__init__(id)

    def get_icon(self) -> QIcon:
        if self._rotate:
            icon_engine = SvgIconEngine(self.rotate(self._rotate))
        else:
            icon_engine = SvgIconEngine(self)
        return QIcon(icon_engine)


