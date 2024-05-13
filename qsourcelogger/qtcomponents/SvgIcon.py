from PyQt6.QtGui import QIcon
from qdarktheme._icon.icon_engine import SvgIconEngine
from qdarktheme._icon.svg import Svg

_svgs = {
    "pin": '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="m640-480 80 80v80H520v240l-40 40-40-40v-240H240v-80l80-80v-280h-40v-80h400v80h-40v280Zm-286 80h252l-46-46v-314H400v314l-46 46Zm126 0Z"/></svg>',
    "pin_full_rounded": '<svg xmlns="http://www.w3.org/2000/svg" enable-background="new 0 0 24 24" height="24px" viewBox="0 0 24 24" width="24px" fill="#000000"><g><rect fill="none" height="24" width="24"/><rect fill="none" height="24" width="24"/></g><g><path d="M19,12.87c0-0.47-0.34-0.85-0.8-0.98C16.93,11.54,16,10.38,16,9V4l1,0 c0.55,0,1-0.45,1-1c0-0.55-0.45-1-1-1H7C6.45,2,6,2.45,6,3c0,0.55,0.45,1,1,1l1,0v5c0,1.38-0.93,2.54-2.2,2.89 C5.34,12.02,5,12.4,5,12.87V13c0,0.55,0.45,1,1,1h4.98L11,21c0,0.55,0.45,1,1,1c0.55,0,1-0.45,1-1l-0.02-7H18c0.55,0,1-0.45,1-1 V12.87z" fill-rule="evenodd"/></g></svg>',
    "image_polaroid": '<svg xmlns="http://www.w3.org/2000/svg"  viewBox="0 0 24 24" style="enable-background:new 0 0 24 24;"><g><path d="M8.24,12.22l-1.97,2.47c-0.18,0.22-0.21,0.53-0.09,0.78c0.12,0.26,0.38,0.42,0.67,0.42h2.96h0.99h6.41c0.27,0,0.53-0.15,0.65-0.39c0.13-0.24,0.11-0.54-0.04-0.76l-3.7-5.43c-0.14-0.2-0.37-0.32-0.61-0.32c-0.24,0-0.47,0.12-0.61,0.32l-2.68,3.93L9.4,12.22c-0.14-0.18-0.35-0.28-0.58-0.28C8.6,11.95,8.38,12.05,8.24,12.22z"/><path d="M7.59,8.99c0.82,0,1.48-0.66,1.48-1.48c0-0.82-0.66-1.48-1.48-1.48S6.11,6.69,6.11,7.51C6.11,8.32,6.77,8.99,7.59,8.99z"/><path d="M20.27,3.76H3.73C3.55,3.76,3.4,3.9,3.4,4.09V19.9c0,0.18,0.15,0.33,0.33,0.33h16.54c0.18,0,0.33-0.15,0.33-0.33V4.09C20.6,3.9,20.45,3.76,20.27,3.76z M18.95,16.9H5.11V5.19h13.84V16.9z"/></g></svg>'
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


