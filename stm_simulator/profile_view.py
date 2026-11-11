"""Interactive line profile with transparent export and data-coordinate readouts."""
import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor


class ProfilePlot(pg.PlotWidget):
    position_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__(background="white")
        self.show_coordinates = True
        self.show_points = True
        self.values = None
        self.selection = None
        self.plotItem.vb.setMouseEnabled(x=True, y=True)
        self.plotItem.vb.setMouseMode(pg.ViewBox.PanMode)
        self.plotItem.vb.setAspectLocked(False)
        self.plotItem.vb.setBorder(pg.mkPen("#526174", width=1))
        self.marker = pg.ScatterPlotItem(size=8, brush="#3979bd", pen="white")
        self.annotation = pg.TextItem(color="#243244", anchor=(0, 1), fill=None)
        self.addItem(self.marker, ignoreBounds=True)
        self.addItem(self.annotation, ignoreBounds=True)
        self.scene().sigMouseMoved.connect(self.track_mouse)
        self.scene().sigMouseClicked.connect(self.pick_point)

    def track_mouse(self, position):
        if self.show_coordinates and self.plotItem.vb.sceneBoundingRect().contains(position):
            point = self.plotItem.vb.mapSceneToView(position)
            self.position_changed.emit(f"x  {point.x():.5g}    y  {point.y():.6g}")
        else:
            self.position_changed.emit("")

    def leaveEvent(self, event):
        self.position_changed.emit("")
        super().leaveEvent(event)

    def set_samples(self, distance, values):
        self.distances, self.values = np.asarray(distance), np.asarray(values)
        self.fit_curve()
        if self.selection is not None:
            self.select_index(min(self.selection, len(values)-1))

    def fit_curve(self):
        """Fit finite data explicitly, including extrema, independent of hidden-panel geometry."""
        if self.values is None:
            return
        valid = np.isfinite(self.distances) & np.isfinite(self.values)
        if not valid.any():
            return
        x = self.distances[valid]
        y = self.values[valid]
        def padded(values, fraction):
            low, high = float(values.min()), float(values.max())
            span = high-low
            margin = span*fraction if span else max(abs(low)*.01, .01)
            margin = max(margin, np.finfo(float).eps*max(abs(low), abs(high), 1.)*16)
            return (low-margin, high+margin)
        self.plotItem.vb.setRange(xRange=padded(x, .03), yRange=padded(y, .10), padding=0)

    def pick_point(self, event):
        if event.button().value != 1 or self.values is None:
            return
        position = event.scenePos()
        if not self.plotItem.vb.sceneBoundingRect().contains(position):
            return
        finite = np.flatnonzero(np.isfinite(self.values))
        if not finite.size:
            return
        # Measure proximity in screen coordinates, so vertical/horizontal units do not bias picking.
        from PyQt6.QtCore import QPointF
        points = [self.plotItem.vb.mapViewToScene(QPointF(float(self.distances[i]), float(self.values[i]))) for i in finite]
        squared = [(p.x()-position.x())**2+(p.y()-position.y())**2 for p in points]
        nearest = int(np.argmin(squared))
        if squared[nearest] <= 15**2:
            self.select_index(int(finite[nearest]))

    def select_index(self, index):
        self.selection = index
        x, y = self.distances[index], self.values[index]
        valid = np.isfinite(y) and self.show_points
        self.marker.setData([x] if valid else [], [y] if valid else [])
        self.annotation.setText(f"({x:.5g}, {y:.6g})")
        bounds = self.viewRange()
        self.annotation.setAnchor((1 if x > sum(bounds[0])/2 else 0, 0 if y > sum(bounds[1])/2 else 1))
        self.annotation.setPos(x, y if np.isfinite(y) else 0)
        self.annotation.setVisible(valid)

    def set_points_visible(self, visible):
        self.show_points = visible
        self.marker.setVisible(visible)
        self.annotation.setVisible(visible and self.selection is not None)

    def set_coordinates_visible(self, visible):
        self.show_coordinates = visible
        if not visible:
            self.position_changed.emit("")

    def transparent_image(self):
        exporter = ImageExporter(self.plotItem)
        exporter.parameters()["background"] = QColor(0, 0, 0, 0)
        exporter.parameters()["width"] = int(self.width()*self.devicePixelRatioF())
        return exporter.export(toBytes=True)
