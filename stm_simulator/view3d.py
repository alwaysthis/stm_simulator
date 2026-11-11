"""GPU-rendered STM mesh and atoms in a shared Cartesian angstrom frame."""
import numpy as np
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QVector3D, QFont, QPainter, QColor, QMatrix4x4
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import shaders
from .elements import atom_styles
from .atoms import GlossyAtoms

AXIS_COLORS = ("#d84444", "#249650", "#397bd0")
shaders.ShaderProgram("axis_front_lit", [
    shaders.VertexShader(shaders.getShaderProgram("shaded").shaders[0].code),
    shaders.FragmentShader("""
        #ifdef GL_ES
        precision mediump float;
        #endif
        varying vec4 v_color;
        varying vec3 v_normal;
        void main() {
            vec3 normal = normalize(v_normal);
            vec3 light = normalize(vec3(-0.3, 0.5, 1.0));
            float diffuse = max(dot(normal, light), 0.0);
            vec3 halfway = normalize(light + vec3(0.0, 0.0, 1.0));
            float highlight = pow(max(dot(normal, halfway), 0.0), 28.0);
            vec3 rgb = v_color.rgb * (0.65 + 0.35*diffuse) + vec3(0.22)*highlight;
            gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), v_color.a);
        }
    """),
])


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
        self.show_signal = True
        self.show_atom_labels = False
        self.atom_labels = []
        self.surface_item = None
        self._fitted = False
        self.home_camera = None
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
        self.home_camera = None
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
        cell = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]) @ volume.lattice
        bounds = np.concatenate((self.atom_positions, cell))
        low, high = bounds.min(axis=0), bounds.max(axis=0)
        span = np.maximum(high-low, .5)
        self._draw_cell(volume.lattice)
        self._draw_axes(low, high, span)
        self.opts['center'] = QVector3D(*((low+high)/2))
        self.setCameraPosition(distance=float(np.linalg.norm(span)*1.05*np.tan(np.deg2rad(30))/np.tan(np.deg2rad(10))), elevation=25, azimuth=-55)
        self.home_camera = self.cameraParams().copy()
        self.update()

    def reset_view(self):
        if self.home_camera is not None:
            self.setCameraParams(**self.home_camera)
        self.update()

    def set_signal_visible(self, visible):
        self.show_signal = visible
        if self.surface_item is not None:
            self.surface_item.setVisible(visible)
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
            self.axes_footer.sync_camera()

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
        self.surface_item.setVisible(self.show_signal)
        self.addItem(self.surface_item)
        # Both objects use physical Cartesian coordinates, with one shared view
        # transform and no independent z stretch or implicit periodic translation.
        self.atom_positions = volume.positions @ volume.lattice
        elements, self.atom_colors, self.atom_radii = atom_styles(volume)
        self.atom_labels = list(zip(self.atom_positions, elements))
        self.atom_artist = GlossyAtoms(self.atom_positions, self.atom_colors, self.atom_radii)
        self.atom_artist.setVisible(self.show_atoms)
        self.addItem(self.atom_artist)
        cell = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]) @ volume.lattice
        points = np.concatenate((self.surface_vertices[valid], self.atom_positions, cell))
        low, high = points.min(axis=0), points.max(axis=0)
        span = np.maximum(high-low, .5)
        self._draw_cell(volume.lattice)
        self._draw_axes(low, high, span)
        if not fitted:
            self.opts['center'] = QVector3D(*((low+high)/2))
            self.setCameraPosition(distance=float(np.linalg.norm(span)*1.05*np.tan(np.deg2rad(30))/np.tan(np.deg2rad(10))), elevation=25, azimuth=-55)
            self.home_camera = self.cameraParams().copy()
        self._fitted = True
        self.update()

    def _draw_cell(self, lattice):
        vertices = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
        segments = []
        for index, vertex in enumerate(vertices):
            for axis in range(3):
                if vertex[axis] == 0:
                    neighbor = vertex.copy()
                    neighbor[axis] = 1
                    segments.extend((vertex @ lattice, neighbor @ lattice))
        self.cell_edges = np.asarray(segments, dtype=np.float32)
        self.addItem(gl.GLLinePlotItem(pos=self.cell_edges, mode="lines",
                                      color=(.18, .23, .3, 1), width=1, antialias=True))

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
            self.axes_footer.sync_camera()


class DirectionAxes(gl.GLViewWidget):
    """Lit cylinder-and-cone axes in their own three-dimensional viewport."""
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setFixedHeight(90)
        self.setBackgroundColor("#f5f7fa")
        self.opts['fov'] = 25
        self.opts['distance'] = 10.
        self.opts['center'] = QVector3D(.3, .3, .3)
        self.parts = []
        for axis in range(3):
            for radius, length, offset in (([.065, .065], .72, 0), ([.15, 0], .32, .72)):
                mesh = gl.MeshData.cylinder(rows=2, cols=24, radius=radius, length=length)
                item = gl.GLMeshItem(meshdata=mesh, color=QColor(AXIS_COLORS[axis]).getRgbF(),
                                     smooth=True, shader="axis_front_lit", glOptions="opaque")
                item.translate(0, 0, offset)
                if axis == 0:
                    item.rotate(90, 0, 1, 0)
                elif axis == 1:
                    item.rotate(-90, 1, 0, 0)
                self.addItem(item)
                self.parts.append(item)
        center = gl.GLMeshItem(meshdata=gl.MeshData.sphere(rows=8, cols=16, radius=.095),
                               color=(.6, .65, .7, 1), smooth=True, shader="axis_front_lit")
        self.addItem(center)
        self.labels = DirectionLabels(self)
        view.axes_footer = self
        self.sync_camera()

    def sync_camera(self):
        self.opts['elevation'] = self.view.opts['elevation']
        self.opts['azimuth'] = self.view.opts['azimuth']
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.opts['distance'] = 2.6/(2*np.tan(np.deg2rad(12.5)))*max(1., self.width()/max(1, self.height()))
        if hasattr(self, "labels"):
            self.labels.setGeometry(self.rect())

    def paintGL(self):
        super().paintGL()
        self.labels.update()

    def wheelEvent(self, event):
        event.ignore()

    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()


class DirectionLabels(QWidget):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self.setGeometry(view.rect())

    def paintEvent(self, event):
        viewport = self.view.getViewport()
        screen = QMatrix4x4()
        screen.viewport(0, self.height(), self.width(), -self.height())
        transform = screen*self.view.projectionMatrix(viewport, viewport)*self.view.viewMatrix()
        painter = QPainter(self)
        painter.setPen(QColor("#243244"))
        painter.setFont(QFont("Arial", 9))
        for position, label in ((QVector3D(1.16, 0, 0), "x"),
                                (QVector3D(0, 1.16, 0), "y"),
                                (QVector3D(0, 0, 1.16), "z")):
            painter.setPen(QColor(AXIS_COLORS["xyz".index(label)]))
            point = transform.map(position)
            painter.drawText(int(point.x()), int(point.y()), label)
        painter.end()
