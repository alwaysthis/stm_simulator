"""Interactive line profile with transparent export and data-coordinate readouts."""
import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PyQt6.QtCore import pyqtSignal, QPointF, Qt
from PyQt6.QtGui import QColor


class CoordinateBox(pg.TextItem):
    """Screen-sized draggable label whose nearest corner stays tethered to its sample."""
    def __init__(self, plot, index):
        super().__init__(color="#243244", anchor=(0, 0),
                         border=pg.mkPen("#627187", width=1), fill=(255, 255, 255, 240))
        self.plot = plot
        self.index = index
        self.offset = None
        self.setZValue(25)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.textItem.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.connector = pg.PlotCurveItem(pen=pg.mkPen("#627187", width=1))
        self.connector.setZValue(24)
        plot.addItem(self.connector, ignoreBounds=True)
        plot.addItem(self, ignoreBounds=True)

    def hoverEvent(self, event):
        if not event.isExit():
            event.acceptDrags(Qt.MouseButton.LeftButton)
            event.acceptClicks(Qt.MouseButton.LeftButton)

    def mouseClickEvent(self, event):
        event.accept()

    def mouseDragEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()
        if event.isStart():
            self.drag_origin = QPointF(self.offset)
            self.drag_start = event.buttonDownScenePos()
        self.move_offset(self.drag_origin+event.scenePos()-self.drag_start)

    def move_offset(self, offset):
        self.offset = QPointF(offset)
        self.refresh()

    def refresh(self):
        x, y = float(self.plot.distances[self.index]), float(self.plot.values[self.index])
        self.setText(f"({x:.5g}, {y:.6g})")
        view = self.plot.plotItem.vb
        point = view.mapViewToScene(QPointF(x, y))
        size = self.boundingRect().size()
        if self.offset is None:
            bounds = view.sceneBoundingRect()
            self.offset = QPointF(16 if point.x() < bounds.center().x() else -size.width()-16,
                                  -size.height()-14 if point.y() > bounds.center().y() else 14)
        target = point+self.offset
        # Keep the whole label inside the plotting area when panning or resizing.
        bounds = view.sceneBoundingRect().adjusted(3, 3, -3, -3)
        target.setX(max(bounds.left(), min(target.x(), bounds.right()-size.width())))
        target.setY(max(bounds.top(), min(target.y(), bounds.bottom()-size.height())))
        self.setPos(view.mapSceneToView(target))
        rectangle = self.sceneBoundingRect()
        corners = (rectangle.topLeft(), rectangle.topRight(), rectangle.bottomLeft(), rectangle.bottomRight())
        corner = min(corners, key=lambda p: (p.x()-point.x())**2+(p.y()-point.y())**2)
        self.corner_scene = corner
        end = view.mapSceneToView(corner)
        self.connector.setData([x, end.x()], [y, end.y()])
        visible = self.plot.show_points
        self.setVisible(visible)
        self.connector.setVisible(visible)

    def remove(self):
        self.plot.removeItem(self.connector)
        self.plot.removeItem(self)


class ProfilePlot(pg.PlotWidget):
    position_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__(background="white")
        self.show_coordinates = True
        self.show_points = True
        self.values = None
        self.annotations = {}
        self.plotItem.vb.setMouseEnabled(x=True, y=True)
        self.plotItem.vb.setMouseMode(pg.ViewBox.PanMode)
        self.plotItem.vb.setAspectLocked(False)
        self.plotItem.vb.setBorder(pg.mkPen("#526174", width=1))
        self.marker = pg.ScatterPlotItem(size=8, brush="#3979bd", pen="white")
        self.addItem(self.marker, ignoreBounds=True)
        self.marker.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.plotItem.vb.sigRangeChanged.connect(self.refresh_annotations)
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
        for index in list(self.annotations):
            if index >= len(values) or not np.isfinite(self.values[index]):
                self.deselect_index(index)
        self.fit_curve()
        self.refresh_annotations()
        self.update_markers()

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
        if event.button().value != 1 or self.values is None or not self.show_points:
            return
        position = event.scenePos()
        if not self.plotItem.vb.sceneBoundingRect().contains(position):
            return
        view = self.plotItem.vb
        for index in list(self.annotations):
            selected = view.mapViewToScene(QPointF(float(self.distances[index]), float(self.values[index])))
            if (selected.x()-position.x())**2+(selected.y()-position.y())**2 <= 100:
                self.deselect_index(index)
                return
        if any(box.sceneBoundingRect().contains(position) for box in self.annotations.values() if box.isVisible()):
            return
        finite = np.flatnonzero(np.isfinite(self.values))
        if not finite.size:
            return
        # Measure proximity in screen coordinates, so vertical/horizontal units do not bias picking.
        points = [self.plotItem.vb.mapViewToScene(QPointF(float(self.distances[i]), float(self.values[i]))) for i in finite]
        squared = [(p.x()-position.x())**2+(p.y()-position.y())**2 for p in points]
        nearest = int(np.argmin(squared))
        if squared[nearest] <= 15**2:
            self.select_index(int(finite[nearest]))

    def select_index(self, index):
        if not np.isfinite(self.values[index]):
            return
        if index not in self.annotations:
            self.annotations[index] = CoordinateBox(self, index)
        self.annotations[index].refresh()
        self.update_markers()

    def deselect_index(self, index):
        box = self.annotations.pop(index)
        box.remove()
        self.update_markers()

    def clear_selection(self):
        for index in list(self.annotations):
            self.deselect_index(index)

    def update_markers(self):
        indices = [i for i in self.annotations if i < len(self.values) and np.isfinite(self.values[i])] if self.show_points else []
        self.marker.setData(self.distances[indices] if indices else [], self.values[indices] if indices else [])

    def refresh_annotations(self, *args):
        for box in self.annotations.values():
            box.refresh()

    def set_points_visible(self, visible):
        self.show_points = visible
        self.update_markers()
        self.refresh_annotations()

    def set_coordinates_visible(self, visible):
        self.show_coordinates = visible
        if not visible:
            self.position_changed.emit("")

    def transparent_image(self):
        exporter = ImageExporter(self.plotItem)
        exporter.parameters()["background"] = QColor(0, 0, 0, 0)
        exporter.parameters()["width"] = int(self.width()*self.devicePixelRatioF())
        return exporter.export(toBytes=True)
