"""GPU-rendered STM mesh and atoms in a shared Cartesian angstrom frame."""
import numpy as np
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QVector3D, QFont, QPainter, QColor, QMatrix4x4
import pyqtgraph.opengl as gl
from .elements import atom_styles
from .atoms import GlossyAtoms


class AxisLabels(QWidget):
    """Qt overlay keeps axis labels crisp above the OpenGL framebuffer."""
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")

    def paintEvent(self, event):
        view = self.view
        if not view.axis_labels and not view.atom_labels:
            return
        viewport = view.getViewport()
        screen = QMatrix4x4()
        screen.viewport(0, self.height(), self.width(), -self.height())
        transform = screen * view.projectionMatrix(viewport, viewport) * view.viewMatrix()
        painter = QPainter(self)
        painter.setPen(QColor("#526174"))
        painter.setFont(QFont("Arial", 8))
        metrics = painter.fontMetrics()
        if view.show_atom_labels and view.atom_labels:
            pixel_sizes = np.asarray(view.pixelSize(view.atom_positions))
            for index, (position, text) in enumerate(view.atom_labels):
                point = transform.map(QVector3D(*position))
                if not (-1 <= point.z() <= 1 and 0 <= point.x() < self.width() and 0 <= point.y() < self.height()):
                    continue
                radius = view.atom_radii[index] / max(float(pixel_sizes[index]), 1e-9)
                text_width = metrics.horizontalAdvance(text)
                x = int(point.x()+radius+4)
                if x+text_width+3 > self.width():
                    x = int(point.x()-radius-text_width-4)
                x = max(2, x)
                y = int(np.clip(point.y()-radius-3, metrics.height(), self.height()-3))
                rect = QRect(x-2, y-metrics.ascent()-2, metrics.horizontalAdvance(text)+6, metrics.height()+2)
                painter.fillRect(rect, QColor(255, 255, 255, 220))
                painter.setPen(QColor("#243244"))
                painter.drawText(x, y, text)
        painter.end()


class SurfaceView(gl.GLViewWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(170, 220)
        self.opts["fov"] = 20
        self.setBackgroundColor("#f5f7fa")
        self.atom_artist = None
        self.show_atoms = True
        self.show_atom_labels = False
        self.atom_labels = []
        self.surface_item = None
        self._fitted = False
        self.axis_labels = []
        self.labels_overlay = AxisLabels(self)
        self.labels_overlay.setGeometry(self.rect())
        self.labels_overlay.raise_()
        self.clear()

    def clear(self):
        super().clear()
        self.atom_artist = None
        self.surface_item = None
        self._fitted = False
        self.axis_labels = []
        self.atom_labels = []
        self.update()

    def show_structure(self, volume):
        self.clear()
        self.atom_positions = volume.positions @ volume.lattice
        elements, self.atom_colors, self.atom_radii = atom_styles(volume)
        self.atom_labels = list(zip(self.atom_positions, elements))
        self.atom_artist = GlossyAtoms(self.atom_positions, self.atom_colors, self.atom_radii)
        self.atom_artist.setVisible(self.show_atoms)
        self.addItem(self.atom_artist)
        low, high = self.atom_positions.min(axis=0), self.atom_positions.max(axis=0)
        span = np.maximum(high-low, .5)
        self._draw_axes(low, high, span)
        self.opts['center'] = QVector3D(*((low+high)/2))
        self.setCameraPosition(distance=float(np.linalg.norm(span)*1.05*np.tan(np.deg2rad(30))/np.tan(np.deg2rad(10))), elevation=25, azimuth=-55)
        self.update()

    def set_atoms_visible(self, visible):
        self.show_atoms = visible
        if self.atom_artist is not None:
            self.atom_artist.setVisible(visible)
        self.update()

    def set_atom_labels_visible(self, visible):
        self.show_atom_labels = visible
        self.labels_overlay.update()
        if hasattr(self, "axes_footer"):
            self.axes_footer.update()

    def set_data(self, result, volume, plane_height, color_scale):
        fitted = self._fitted
        super().clear()
        indices = [np.unique(np.linspace(0, n-1, min(n, 160)).astype(int)) for n in result.shape]
        i, j = np.meshgrid(*indices, indexing="ij")
        xy = np.stack((i/result.shape[0], j/result.shape[1]), axis=-1) @ volume.lattice[:2, :2]
        values = result[np.ix_(*indices)]
        z = values if plane_height is None else (np.asarray(plane_height)[np.ix_(*indices)] if np.ndim(plane_height) == 2 else np.full_like(values, plane_height))
        z = np.where(np.isfinite(values), z, np.nan)
        self.surface_vertices = np.column_stack((xy.reshape(-1, 2), z.ravel()))
        rows, columns = values.shape
        base = (np.arange(rows-1)[:, None]*columns+np.arange(columns-1)).ravel()
        faces = np.concatenate((np.column_stack((base, base+1, base+columns)),
                                np.column_stack((base+1, base+columns+1, base+columns))))
        valid = np.isfinite(self.surface_vertices[:, 2])
        faces = faces[valid[faces].all(axis=1)]
        vertices = np.nan_to_num(self.surface_vertices).astype(np.float32)
        colors = color_scale.rgba(values).reshape(-1, 4).astype(np.float32)
        self.surface_item = gl.GLMeshItem(vertexes=vertices, faces=faces.astype(np.uint32),
                                          vertexColors=colors, smooth=False, computeNormals=False,
                                          shader=None, glOptions="opaque")
        self.addItem(self.surface_item)
        # Both objects use physical Cartesian coordinates, with one shared view
        # transform and no independent z stretch or implicit periodic translation.
        self.atom_positions = volume.positions @ volume.lattice
        elements, self.atom_colors, self.atom_radii = atom_styles(volume)
        self.atom_labels = list(zip(self.atom_positions, elements))
        self.atom_artist = GlossyAtoms(self.atom_positions, self.atom_colors, self.atom_radii)
        self.atom_artist.setVisible(self.show_atoms)
        self.addItem(self.atom_artist)
        points = np.concatenate((self.surface_vertices[valid], self.atom_positions))
        low, high = points.min(axis=0), points.max(axis=0)
        span = np.maximum(high-low, .5)
        self._draw_axes(low, high, span)
        if not fitted:
            self.opts['center'] = QVector3D(*((low+high)/2))
            self.setCameraPosition(distance=float(np.linalg.norm(span)*1.05*np.tan(np.deg2rad(30))/np.tan(np.deg2rad(10))), elevation=25, azimuth=-55)
        self._fitted = True
        self.update()

    def _draw_axes(self, low, high, span):
        self.axis_labels = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "labels_overlay"):
            self.labels_overlay.setGeometry(self.rect())

    def paintGL(self):
        super().paintGL()
        self.labels_overlay.update()
        if hasattr(self, "axes_footer"):
            self.axes_footer.update()


class DirectionAxes(QWidget):
    """Dedicated footer outside the scene, so axes cannot cover atoms."""
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setFixedHeight(72)
        self.setStyleSheet("background:#f5f7fa;")
        view.axes_footer = self

    def paintEvent(self, event):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#243244"), 1.8))
        painter.setFont(QFont("Arial", 9))
        origin = QPointF(40, 38)
        rotation = self.view.viewMatrix()
        for vector, label in zip((QVector3D(1, 0, 0), QVector3D(0, 1, 0), QVector3D(0, 0, 1)), "xyz"):
            direction = rotation.mapVector(vector)
            end = origin + QPointF(direction.x()*25, -direction.y()*25)
            painter.drawLine(origin, end)
            painter.drawText(end+QPointF(3, -3), label)
        painter.drawText(82, 40, "Å · 等比例")
        painter.end()
