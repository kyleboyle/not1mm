import datetime
import logging

import cartopy
import cartopy.crs as ccrs
from PyQt6 import uic, QtGui
from PyQt6.QtCore import QTimer, QThread
from cartopy.feature.nightshade import Nightshade
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from not1mm import fsutils
from not1mm.lib import event
from not1mm.model import Station
from not1mm.qtcomponents.DockWidget import DockWidget

logger = logging.getLogger(__name__)

class RenderWorker(QThread):

    def __init__(self, map_widget):
        super().__init__()
        self.map_widget = map_widget

    def run(self):
        self.map_widget.plot_render()


class WorldMap(DockWidget):
    station: Station = None
    call_coords: list = None

    plot_debounce_timer = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(fsutils.APP_DATA_PATH / "world_map.ui", self)

        event.register(event.IntermediateQsoUpdate, self.intermediate_qso_update)
        event.register(event.CallChanged, self.event_call_changed)
        event.register(event.StationActivated, self.event_station_activated)

        self.figure = Figure()
        self.figure.set_facecolor("none")
        self.canvas = FigureCanvasQTAgg(self.figure)

        self.setWidget(self.canvas)
        self.canvas.setPalette(QtGui.QGuiApplication.palette())
        self.load_station()

    def load_station(self, station: Station = None):
        if station is None:
            active_station_id = fsutils.read_settings().get("active_station_id", None)
            if active_station_id:
                try:
                    self.station = Station.get_by_id(active_station_id)
                except:
                    ...
        else:
            self.station = station
        self.plot()

    def event_station_activated(self, e: event.StationActivated):
        self.load_station(e.station)

    def event_call_changed(self, event: event.CallChanged):
        # keep the previous call active after insert
        if not event.call:
            if self.call_coords is not None:
                self.call_coords = None
                self.plot()

    def intermediate_qso_update(self, e: event.IntermediateQsoUpdate):
        if e.qso.lon and e.qso.lat:
            self.call_coords = [e.qso.lon, e.qso.lat]
            logger.debug(f"call {e.qso.call} {self.call_coords}")
            self.plot()
        elif self.call_coords is not None:
            self.call_coords = None
            self.plot()

    def plot(self):
        # debounce the plot calls incase they come in quick succession
        if not self.plot_debounce_timer:
            self.plot_debounce_timer = True
            QTimer.singleShot(500, self._plot_debounce)

    def _plot_debounce(self):
        self.render_thread = RenderWorker(self)
        self.render_thread.start(QThread.Priority.LowPriority)

    def plot_render(self):
        self.plot_debounce_timer = False

        center_map = None
        if self.station and self.station.longitude:
            center_map = self.station.longitude

        ax = self.figure.add_subplot(1, 1, 1, projection=ccrs.PlateCarree(central_longitude=center_map), frame_on=False)

        # make the map global rather than have it zoom in to
        # the extents of any plotted data
        ax.set_global()

        # ax.stock_img()
        date = datetime.datetime.now(datetime.UTC)

        #ax.coastlines()
        ax.add_feature(cartopy.feature.LAND)  # , facecolor="olivedrab")
        ax.add_feature(cartopy.feature.OCEAN)  # , facecolor="cornflowerblue")
        ax.add_feature(cartopy.feature.BORDERS, alpha=0.2)

        if self.station and self.station.latitude and self.station.longitude:
            ax.plot(self.station.longitude, self.station.latitude, linewidth=1, marker='x',
                    transform=ccrs.PlateCarree(), color='red', markersize=4)
            if self.call_coords:
                ax.plot([self.station.longitude, self.call_coords[0]], [self.station.latitude, self.call_coords[1]],
                        color="blue",
                        transform=ccrs.Geodetic())

        ax.add_feature(Nightshade(date + datetime.timedelta(minutes=10), alpha=0.3, delta=0.1))
        ax.add_feature(Nightshade(date - datetime.timedelta(minutes=10), alpha=0.3, delta=0.1))

        # remove margins
        self.figure.subplots_adjust(left=0, right=1, bottom=0, top=1)

        self.canvas.draw()
