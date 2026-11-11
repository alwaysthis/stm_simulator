"""Qt instrument panel, styled after the clc_mbe control panel."""
import queue
import threading
from pathlib import Path
import numpy as np
from PyQt6.QtCore import Qt, QTimer, QSettings, QSignalBlocker, QRegularExpression, pyqtSignal, QPointF
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QFont, QLinearGradient, QPen, QRegularExpressionValidator, QRadialGradient
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QSplitter, QFileDialog, QMessageBox, QScrollArea, QCheckBox, QProgressBar, QSlider)
from .core import read_parchg, simulate, sample_heights
from .widgets import ChevronComboBox, NumericBox, DragSlider
from .view3d import SurfaceView, DirectionAxes
from .colors import ColorScale, PALETTES
from .plot_tools import HoverActions
from .profile_view import ProfilePlot
from .elements import atom_styles
import pyqtgraph as pg
from scipy.ndimage import map_coordinates

STYLE = """
QMainWindow, QWidget {background:#ffffff;color:#243244;font-family:'Microsoft YaHei UI';font-size:13px;}
QFrame#panel {background:#ffffff;border:1px solid #d9e1eb;border-radius:8px;}
QFrame#card {background:#ffffff;border:1px solid #d9e1eb;border-radius:4px;}
QLabel {background:transparent;border:none;}
QLabel#muted {color:#627187;}
QCheckBox {spacing:7px;}
QCheckBox::indicator {width:14px;height:14px;border:1px solid #354b65;border-radius:3px;background:white;}
QCheckBox::indicator:checked {background:#3979bd;border:2px solid #243244;image:url(__CHECK_ICON__);}
QCheckBox::indicator:disabled {border-color:#7f8b99;}

QPushButton {background:#e3e9f1;border:1px solid #c8d2df;border-radius:4px;padding:6px 12px;}
QPushButton:hover {background:#d7e4f3;border-color:#4a90d9;}
QPushButton:pressed {background:#c3d5eb;}
QPushButton:checked {background:#c3d5eb;border-color:#3979bd;color:#1e568e;}
QPushButton:disabled {color:#9aa6b5;}
QPushButton#primary {color:white;background:#3979bd;border-color:#4a90d9;}
QPushButton#primary:hover {background:#4a90d9;}
QLineEdit,QComboBox,QDoubleSpinBox {background:#ffffff;border:1px solid #c8d2df;border-radius:4px;padding:3px 8px;min-height:20px;selection-background-color:#4a90d9;}
QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {border-color:#4a90d9;}
QLineEdit:hover,QComboBox:hover,QDoubleSpinBox:hover {border-color:#4a90d9;background:#f1f4f8;}
QLineEdit:disabled,QComboBox:disabled,QDoubleSpinBox:disabled {color:#a4afbd;border-color:#d9e1eb;}
QComboBox::down-arrow {image:none;}
QComboBox QAbstractItemView {background:#ffffff;color:#243244;border:1px solid #c8d2df;selection-background-color:#3979bd;outline:none;padding:4px;}
QComboBox QAbstractItemView::item {min-height:26px;padding:3px 8px;}
QDoubleSpinBox::up-button {width:18px;border:none;border-top-right-radius:4px;}
QDoubleSpinBox::down-button {width:18px;border:none;border-bottom-right-radius:4px;}
QDoubleSpinBox::up-button:hover,QDoubleSpinBox::down-button:hover {background:#e7eef7;}
QComboBox::drop-down {border:none;width:22px;}
QScrollArea {border:none;background:transparent;}
QScrollBar:vertical {background:transparent;width:6px;}
QScrollBar::handle:vertical {background:#e3e9f1;border-radius:3px;min-height:25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QSlider::groove:horizontal {height:4px;background:#c8d2df;border-radius:2px;}
QSlider::sub-page:horizontal {background:#3979bd;border-radius:2px;}
QSlider::handle:horizontal {background:#9dc2e8;width:12px;margin:-5px 0;border-radius:6px;}
QSlider::sub-page:horizontal:disabled {background:#c8d2df;}
QSlider::handle:horizontal:disabled {background:#a4afbd;}
QProgressBar {border:1px solid #c8d2df;border-radius:4px;text-align:center;min-height:18px;}
QProgressBar::chunk {background:#3979bd;border-radius:3px;}
QSplitter::handle {background:#ffffff;width:8px;}
"""

STYLE = STYLE.replace("__CHECK_ICON__", (Path(__file__).parent / "assets/check.svg").as_posix())

class ImageView(QWidget):
    line_changed = pyqtSignal(object, object)
    line_cleared = pyqtSignal()
    def __init__(self, readout):
        super().__init__()
        self.line_enabled = False
        self.line_points = None
        self.drawing_line = False
        self.setMouseTracking(True)
        self.readout = readout
        self.pixels = self.image = self.result = None
        self.exporting = False
        self.show_colorbar = True
        self.show_line = True
        self.show_atoms = False
        self.show_atom_labels = False
        self.atom_scale = 1.
        self.atom_depth = 5.
        self.atom_side = "top"
        self.volume = None
        self.setMinimumSize(220, 160)

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.exporting:
            painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#526174"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self.image is None:
            painter.setPen(QColor("#808080"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,"打开 PARCHG 文件开始模拟")
            return
        scale = min(max(1, self.width()-40)/self.image.width(),
                    max(1, self.height()-125)/self.image.height())
        width, height = max(1, int(self.image.width()*scale)), max(1, int(self.image.height()*scale))
        x, y = max(10, (self.width()-width)//2), max(35, (self.height()-height-20)//2)
        self.rect_image = (x, y, width, height)
        painter.drawPixmap(x, y, width, height, QPixmap.fromImage(self.image))
        painter.setPen(QColor("#627187"))

        if self.show_colorbar:
            bar_x, bar_y = 18, self.height()-66
            bar_width, bar_height = 10, 50
            gradient = QLinearGradient(bar_x, bar_y+bar_height, bar_x, bar_y)
            levels = np.linspace(self.color_scale.low, self.color_scale.high, 65)
            for stop, rgba in zip(np.linspace(0, 1, 65), self.color_scale.rgba(levels)):
                gradient.setColorAt(float(stop), QColor.fromRgbF(*rgba))
            painter.fillRect(bar_x, bar_y, bar_width, bar_height, gradient)
            painter.setPen(QColor("#526174"))
            painter.drawRect(bar_x, bar_y, bar_width, bar_height)
            low = self.color_scale.display_value(self.color_scale.low)
            high = self.color_scale.display_value(self.color_scale.high)
            painter.drawText(bar_x+bar_width+7, bar_y+bar_height+4, f"{low:.4g}")
            painter.drawText(bar_x+bar_width+7, bar_y+4, f"{high:.4g}")
            painter.drawText(bar_x+bar_width+7, bar_y+bar_height//2+4, self.color_scale.label)
        self.paint_atoms(painter)
        if self.show_line and self.line_points is not None:
            points = []
            for position in self.line_points:
                fraction = (position-self.low)/(self.high-self.low)
                points.append(QPointF(x+fraction[0]*width, y+(1-fraction[1])*height))
            painter.setPen(QPen(QColor("#1686d9"), 2))
            painter.drawLine(*points)
            painter.setBrush(QColor("#ffffff"))
            for point in points:
                painter.drawEllipse(point, 4, 4)


    def xy_at(self, position):
        if self.image is None or not hasattr(self, "rect_image"):
            return None
        x, y, width, height = self.rect_image
        u = np.clip((position.x()-x)/width, 0, 1)
        v = np.clip(1-(position.y()-y)/height, 0, 1)
        return self.low+np.array([u, v])*(self.high-self.low)

    def reset_view(self):
        self.update()  # The STM image always fits its panel; preserve the selected profile.

    def clear_line(self):
        self.line_points = None
        self.drawing_line = False
        self.line_cleared.emit()
        self.update()

    def set_visibility(self, name, visible):
        setattr(self, name, visible)
        self.update()

    def set_atom_scale(self, value):
        self.atom_scale = value/100
        self.update()

    def set_atom_depth(self, value):
        self.atom_depth = value/100
        self.update()

    def atom_depths(self):
        z = (self.volume.positions @ self.volume.lattice)[:, 2]
        surface = float(z.max() if self.atom_side == "top" else z.min())
        return (surface-z if self.atom_side == "top" else z-surface), surface

    def atom_opacities(self):
        depths, _ = self.atom_depths()
        return np.where(depths <= self.atom_depth+1e-8, 1., 0.)

    def paint_atoms(self, painter):
        if not self.show_atoms or self.volume is None:
            return
        x, y, width, height = self.rect_image
        elements, colors, radii = atom_styles(self.volume)
        depths, _ = self.atom_depths()
        opacities = self.atom_opacities()
        # Paint deep atoms first; near-surface atoms must remain above them in projection.
        order = np.argsort(-depths, kind="stable")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(x, y, width, height)
        sx, sy = np.array([width, height])/(self.high-self.low)
        stride = max(1, int(np.ceil(np.sqrt(len(elements)*float(np.prod(self.repeats))/50000))))
        for a in range(0, int(self.repeats[0]), stride):
            for b in range(0, int(self.repeats[1]), stride):
                for i in order:
                    if opacities[i] == 0:
                        continue
                    atom = self.volume.positions[i]
                    xy = ((atom[:2] % 1)+[a, b]) @ self.lattice[:2, :2]
                    px = x+(xy[0]-self.low[0])*sx
                    py = y+height-(xy[1]-self.low[1])*sy
                    radius = max(1., float(radii[i])*min(sx, sy)*self.atom_scale*.35)
                    base = QColor.fromRgbF(*colors[i])
                    gradient = QRadialGradient(QPointF(px-radius*.3, py-radius*.35), radius*1.5)
                    gradient.setColorAt(0., QColor.fromRgbF(*(.9+.1*colors[i, :3])))
                    gradient.setColorAt(.10, base.lighter(180))
                    gradient.setColorAt(.25, base.lighter(125))
                    gradient.setColorAt(.55, base)
                    gradient.setColorAt(1., base.darker(240))
                    painter.setOpacity(float(opacities[i]))
                    painter.setBrush(gradient)
                    painter.setPen(QPen(base.darker(180), .7))
                    painter.drawEllipse(QPointF(px, py), radius, radius)
                    if self.show_atom_labels:
                        painter.setPen(QColor("#243244"))
                        painter.drawText(QPointF(px+radius+3, py-3), elements[i])
        painter.restore()

    def transparent_image(self):
        image = QImage(self.size()*self.devicePixelRatioF(), QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(self.devicePixelRatioF())
        image.fill(Qt.GlobalColor.transparent)
        self.exporting = True
        try:
            self.render(image, flags=QWidget.RenderFlag.DrawChildren)
        finally:
            self.exporting = False
        return image

    def mousePressEvent(self, event):
        if self.line_enabled and event.button() == Qt.MouseButton.LeftButton:
            if self.image is None or not hasattr(self, "rect_image"):
                return super().mousePressEvent(event)
            x, y, width, height = self.rect_image
            if not (x <= event.position().x() <= x+width and y <= event.position().y() <= y+height):
                return super().mousePressEvent(event)
            point = self.xy_at(event.position())
            if point is not None:
                frac = point @ np.linalg.inv(self.lattice[:2, :2])
                if np.all((frac >= 0) & (frac <= self.repeats)):
                    self.line_points = (point, point.copy())
                    self.drawing_line = True
                    self.update()
                    return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_line and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_line = False
            endpoint = self.xy_at(event.position())
            if endpoint is not None:
                self.line_points = (self.line_points[0], endpoint)
                self.line_changed.emit(*self.line_points)
                self.update()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self,event):
        if self.drawing_line:
            endpoint = self.xy_at(event.position())
            if endpoint is not None:
                self.line_points = (self.line_points[0], endpoint)
                self.line_changed.emit(*self.line_points)
                self.update()

        if self.image is None or not hasattr(self,"rect_image"):
            return
        ox,oy,w,h = self.rect_image
        px,py = event.position().x(),event.position().y()
        if not (ox <= px < ox+w and oy <= py < oy+h):
            return
        xy = self.low+np.array([(px-ox)/w,1-(py-oy)/h])*(self.high-self.low)
        frac = xy @ np.linalg.inv(self.lattice[:2,:2])
        if np.all((frac>=0)&(frac<self.repeats)):
            i,j=((frac % 1)*np.array(self.result.shape)).astype(int)
            self.readout.setText(f"x  {xy[0]:.3f} Å     y  {xy[1]:.3f} Å     值  {self.color_scale.display_value(self.result[i,j]):.6g} {self.color_scale.label}")

    def set_data(self,result,lattice,unit,color_scale,repeats=1):
        self.repeats = np.broadcast_to(np.asarray(repeats, dtype=float), (2,)).copy()
        repeats = self.repeats
        self.result,self.lattice,self.unit=result,lattice,unit
        self.color_scale = color_scale
        rgb = np.round(color_scale.rgba(result)[..., :3]*255).astype(np.uint8)
        rgb[~np.isfinite(result)] = [110, 30, 70]
        corners=np.array([[0,0],lattice[0,:2]*repeats[0],lattice[1,:2]*repeats[1],lattice[0,:2]*repeats[0]+lattice[1,:2]*repeats[1]])
        self.low,self.high=corners.min(axis=0),corners.max(axis=0)
        shape=np.maximum(1,((self.high-self.low)/max(self.high-self.low)*900).astype(int))
        xx,yy=np.meshgrid(np.linspace(self.low[0],self.high[0],shape[0]),np.linspace(self.high[1],self.low[1],shape[1]))
        fractional=np.stack([xx,yy],axis=-1) @ np.linalg.inv(lattice[:2,:2])
        mask=np.all((fractional>=0)&(fractional<=repeats),axis=-1)
        ij=np.clip(((fractional % 1)*np.array(result.shape)).astype(int),0,np.array(result.shape)-1)
        self.pixels=np.ascontiguousarray(np.dstack((rgb[ij[:,:,0],ij[:,:,1]], mask.astype(np.uint8)*255)))
        self.image=QImage(self.pixels.data,shape[0],shape[1],shape[0]*4,QImage.Format.Format_RGBA8888).copy()
        self.update()

class App(QMainWindow):
    def __init__(self, settings_path=None):
        super().__init__()
        settings_path = settings_path or Path(__file__).resolve().parent.parent / ".settings.ini"
        self.settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(250)
        self.preview_timer.timeout.connect(self.preview)
        self.setWindowTitle("STM Simulator")
        self.resize(1240,720)
        self.setMinimumSize(950,650)
        self.setStyleSheet(STYLE)
        self.volume=self.result=None
        self.busy=False
        self.jobs=queue.Queue()
        self.progress_updates=queue.Queue()
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(50)
        root=QWidget();self.setCentralWidget(root)
        layout=QVBoxLayout(root);layout.setContentsMargins(8,6,8,6);layout.setSpacing(8)
        toolbar=QHBoxLayout();toolbar.setSpacing(8)
        title=QLabel("STM Simulator");title.setFont(QFont("Microsoft YaHei UI",11,QFont.Weight.Bold));toolbar.addWidget(title);toolbar.addSpacing(20)
        for text,callback in [("打开文件",self.open_file),("导入高度",self.open_heights),("导出图像",self.export_image),("导出数据",self.export_data),("帮助",self.show_help)]:
            button=QPushButton(text);button.clicked.connect(callback);toolbar.addWidget(button)
        self.line_button = QPushButton("截面线")
        self.line_button.setCheckable(True)
        self.line_button.toggled.connect(self.set_line_mode)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        body=QHBoxLayout();body.setSpacing(8);layout.addLayout(body,1)
        split=QSplitter();body.addWidget(split,1)
        view=QWidget()
        view_layout=QVBoxLayout(view);view_layout.setContentsMargins(8,6,8,6)
        self.summary=QLabel("等待数据");self.summary.setObjectName("muted");view_layout.addWidget(self.summary)
        self.readout=QLabel("x  —     y  —     值  —");self.readout.setObjectName("muted")
        self.plots = plots = QSplitter()
        map_panel = QWidget()
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_header = QHBoxLayout()
        map_header.addWidget(QLabel("面内显示范围"))
        self.tiles_a = QLineEdit("1")
        self.tiles_b = QLineEdit("1")
        for field, direction in ((self.tiles_a, "a"), (self.tiles_b, "b")):
            field.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9]*"), field))
            field.setToolTip(f"{direction}方向重复数量，输入正整数后按回车")
            field.setFixedWidth(48)
            field.editingFinished.connect(self.refresh_colors)
        map_header.addWidget(self.tiles_a)
        map_header.addWidget(QLabel("×"))
        map_header.addWidget(self.tiles_b)
        map_header.addWidget(self.line_button)
        map_header.addStretch()
        map_layout.addLayout(map_header)
        self.image = ImageView(self.readout)
        self.image.setMinimumWidth(240)
        map_layout.addWidget(self.image, 1)
        map_layout.addWidget(self.readout)
        plots.addWidget(map_panel)
        surface_panel = QWidget()
        surface_layout = QVBoxLayout(surface_panel)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        self.surface = SurfaceView()
        self.surface.setMinimumWidth(170)
        surface_layout.addWidget(self.surface, 1)
        self.direction_axes = DirectionAxes(self.surface)
        footer = QHBoxLayout()
        footer.addWidget(self.direction_axes)
        footer.addStretch()
        surface_layout.addLayout(footer)
        plots.addWidget(surface_panel)
        plots.setStretchFactor(0, 3)
        plots.setStretchFactor(1, 1)
        plots.setSizes([675, 225])
        self.profile_panel = QWidget()
        profile_layout = QVBoxLayout(self.profile_panel)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_header = QHBoxLayout()
        profile_header.addWidget(QLabel("截面图"))
        profile_header.addStretch()
        self.profile_position = QLabel("")
        profile_header.addWidget(self.profile_position)
        close_profile = QPushButton("关闭")
        close_profile.clicked.connect(self.image.clear_line)
        profile_header.addWidget(close_profile)
        profile_layout.addLayout(profile_header)
        self.profile_plot = ProfilePlot()
        self.profile_plot.position_changed.connect(self.profile_position.setText)
        self.profile_plot.setMinimumHeight(170)
        self.profile_plot.setMenuEnabled(False)
        self.profile_plot.hideButtons()
        self.profile_plot.setLabel("bottom", "沿线距离", units="Å")
        for axis in ("left", "bottom"):
            self.profile_plot.getAxis(axis).setPen("#627187")
            self.profile_plot.getAxis(axis).setTextPen("#243244")
        self.profile_curve = self.profile_plot.plot(pen=pg.mkPen("#3979bd", width=2), connect="finite")
        profile_layout.addWidget(self.profile_plot)
        self.profile_panel.hide()
        self.vertical_plots = QSplitter(Qt.Orientation.Vertical)
        self.vertical_plots.addWidget(plots)
        self.vertical_plots.addWidget(self.profile_panel)
        view_layout.addWidget(self.vertical_plots, 1)
        self.image.line_changed.connect(self.update_profile)
        self.image.line_cleared.connect(self.profile_panel.hide)
        self.image_tools = HoverActions(self.image, self.image.reset_view, "stm.png")
        self.surface_tools = HoverActions(self.surface, self.surface.reset_view, "stm_3d.png")
        self.profile_tools = HoverActions(self.profile_plot, self.profile_plot.autoRange, "profile.png")
        self.atoms_toggle = self.surface_tools.add_visibility("原子", True, self.surface.set_atoms_visible)
        self.atom_labels_toggle = self.surface_tools.add_visibility("原子标签", False, self.surface.set_atom_labels_visible)
        self.signal_layer_toggle = self.surface_tools.add_visibility("信号层", True, self.surface.set_signal_visible)
        self.surface_tools.add_visibility("晶胞", True, self.surface.set_cell_visible)
        self.surface_tools.add_visibility("方向轴", True, self.direction_axes.setVisible)
        self.atom_size_slider = DragSlider(Qt.Orientation.Horizontal)
        self.atom_size_slider.setRange(10, 300)
        self.atom_size_slider.setValue(100)
        self.atom_size_slider.setFixedWidth(110)
        self.atom_size_slider.setToolTip("投影原子大小：0.1–3倍")
        self.atom_size_slider.valueChanged.connect(self.image.set_atom_scale)
        self.atom_depth_slider = DragSlider(Qt.Orientation.Horizontal)
        self.atom_depth_slider.setRange(0, 500)
        self.atom_depth_slider.setValue(500)
        self.atom_depth_slider.setFixedWidth(110)
        self.atom_depth_slider.setEnabled(False)
        self.atom_depth_slider.setToolTip("从所选表面向内部的深度；左图隐藏范围外原子，右图以0.2透明度显示")
        self.atom_depth_slider.valueChanged.connect(self.change_atom_depth)
        depth_controls = QWidget()
        depth_layout = QHBoxLayout(depth_controls)
        depth_layout.setContentsMargins(24, 0, 0, 2)
        depth_layout.addWidget(QLabel("原子范围"))
        self.atom_depth_label = QLabel("5.00 Å")
        depth_layout.addWidget(self.atom_depth_label)
        depth_layout.addStretch()
        depth_layout.addWidget(self.atom_depth_slider)
        self.projection_atoms_toggle = self.image_tools.add_visibility("原子", False, self.set_projection_atoms_visible, self.atom_size_slider, details=depth_controls)
        self.image_tools.add_visibility("原子标签", False, lambda v: self.image.set_visibility("show_atom_labels", v))
        self.image_tools.add_visibility("截面线", True, lambda v: self.image.set_visibility("show_line", v))
        self.image_tools.add_visibility("颜色条", True, lambda v: self.image.set_visibility("show_colorbar", v))
        self.profile_tools.add_visibility("曲线", True, self.profile_curve.setVisible)
        self.profile_tools.add_visibility("选点标注", True, self.profile_plot.set_points_visible)
        self.profile_tools.add_visibility("鼠标坐标", True, self.profile_plot.set_coordinates_visible)
        split.addWidget(view)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMinimumWidth(290);scroll.setMaximumWidth(360)
        panel=QFrame();panel.setObjectName("panel");scroll.setWidget(panel);split.addWidget(scroll);split.setSizes([900,300])
        controls=QVBoxLayout(panel);controls.setContentsMargins(12,12,12,12);controls.setSpacing(12)
        controls.addWidget(QLabel("模拟设置"))
        self.run_button=QPushButton("运行模拟");self.run_button.setObjectName("primary");self.run_button.clicked.connect(self.run);controls.addWidget(self.run_button)
        source=self.card(controls,"数据源");self.file_label=QLabel("尚未载入 PARCHG");self.file_label.setWordWrap(True);self.file_label.setMinimumHeight(64);self.file_label.setObjectName("muted");source.addRow(self.file_label)
        form=self.card(controls,"扫描参数")
        self.mode=self.combo(form,"扫描模式",["恒流","恒高","高度文件"])
        self.engine=self.combo(form,"搜索算法",["p4vasp 线性","限定真空 · 线性"])
        self.side=self.combo(form,"扫描表面",["上表面 / −c","下表面 / +c"])
        self.side.setToolTip("上表面从真空沿 −c 搜索，下表面沿 +c 搜索。指定(hkl)晶面需先构建并计算该晶面的slab。")
        self.threshold=self.entry(form,"目标信号 / 原始密度","0.001");self.threshold.setRange(1e-10,1e12);self.threshold.setSingleStep(.0001)
        self.threshold.setToolTip("恒流目标信号。固定偏压下，阈值越大通常越靠近表面。使用 PARCHG 原始单位。")
        self.signal_slider = DragSlider(Qt.Orientation.Horizontal)
        self.signal_slider.setRange(0, 1000)
        self.signal_limits = (-10., 12.)
        self.signal_slider.setToolTip("拖动调节恒流目标信号，对数刻度")
        form.addRow(self.signal_slider)
        self.height=self.entry(form,"距所选表面 / Å","4.0");self.height.setSingleStep(.1)
        self.height.setToolTip("恒高截面到所选表面最外层原子的距离，单位 Å。")
        self.height_slider = DragSlider(Qt.Orientation.Horizontal)
        self.height_slider.setRange(0, 1000)
        self.height_limit = 20.
        self.height_slider.setToolTip("拖动调节恒高截面距外层原子的距离")
        form.addRow(self.height_slider)
        self.signal_slider.valueChanged.connect(self.drag_signal)
        self.height_slider.valueChanged.connect(self.drag_height)
        self.threshold.valueChanged.connect(self.parameter_changed)
        self.height.valueChanged.connect(self.parameter_changed)
        self.update_sliders()
        self.sigma=self.entry(form,"平滑 / 网格 σ","0")
        bounds=self.card(controls,"限定真空范围 · 留空自动")
        self.zmin=self.entry(bounds,"z 下界 / Å","");self.zmax=self.entry(bounds,"z 上界 / Å","")
        self.engine.currentIndexChanged.connect(self.sync_controls);self.mode.currentIndexChanged.connect(self.sync_controls)
        self.side.currentIndexChanged.connect(self.update_slider_ranges)
        self.side.currentIndexChanged.connect(self.update_atom_side)
        colors = self.card(controls, "颜色标尺")
        self.palette = self.combo(colors, "配色", list(PALETTES))
        self.color_units = self.combo(colors, "高度标注", ["距表面 / Å", "距表面 / nm"])
        self.color_range = self.combo(colors, "范围", ["全范围", "固定范围"])
        self.color_min = self.entry(colors, "色标下限", "")
        self.color_max = self.entry(colors, "色标上限", "")
        for combo in (self.palette, self.color_units, self.color_range):
            combo.currentIndexChanged.connect(self.refresh_colors)
        for field in (self.color_min, self.color_max):
            field.editingFinished.connect(self.refresh_colors)
        self.sync_controls();self.refresh_colors();controls.addStretch()
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status=QLabel("就绪    ·    PARCHG 原始密度单位");self.status.setObjectName("muted");layout.addWidget(self.status)
        QTimer.singleShot(0, self.restore_file)

    def show_help(self):
        QMessageBox.information(self, "方法说明", "Tersoff–Hamann 近似\n\np4vasp 线性模式\n从平面平均密度最小层开始，周期搜索首个达到阈值的点，再线性插值。\n上表面沿 −c 搜索，下表面沿 +c 搜索。输出保留展开的周期坐标。\n无交点以 NaN 标记。\n\n限定真空模式\n仅搜索最外层原子之外的真空，可指定 z 范围。\n\n偏压能窗由 VASP 的 EINT 设置。阈值为 PARCHG 原始数值。\n\n拖动滑条或修改目标信号、高度后自动更新双图，也可点击运行模拟。\n恒流调整目标信号，恒高调整距外层原子的距离。\n三维图可勾选显示原子、元素标签或信号层。\n原子颜色和显示半径参考 crystalX 的 VESTA 主题。\n选择指定(hkl)表面前，需先构建该晶面的slab并计算PARCHG。\n曲面和原子共用笛卡尔 Å 坐标，保持xyz等比例。\n颜色标尺支持全范围或固定范围，可选择相对最低高度nm。\n恒流目标信号滑条采用对数刻度，便于跨数量级调节。\n\n顶部“截面线”开启后，在左图按住鼠标左键拉线，下方显示沿线截面。\n三个图的右上角悬浮工具栏提供重置、复制和导出图像。")

    def card(self,parent,title):
        frame=QFrame();frame.setObjectName("card");box=QVBoxLayout(frame);box.setContentsMargins(10,10,10,10)
        label=QLabel(title);label.setObjectName("muted");box.addWidget(label)
        form=QFormLayout();form.setSpacing(8);form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows);box.addLayout(form);parent.addWidget(frame);return form

    def entry(self,form,label,value):
        entry=NumericBox(value) if value else QLineEdit()
        if not value:
            entry.setPlaceholderText("自动")
        form.addRow(label,entry)
        return entry

    def combo(self,form,label,values):
        combo=ChevronComboBox();combo.addItems(values);form.addRow(label,combo);return combo

    def sync_controls(self):
        self.side.setEnabled(self.mode.currentIndex() in (0, 1))
        current=self.mode.currentIndex()==0
        self.signal_slider.setEnabled(current)
        self.height_slider.setEnabled(self.mode.currentIndex()==1)
        self.threshold.setEnabled(current);self.height.setEnabled(self.mode.currentIndex()==1);self.engine.setEnabled(current)
        for entry in (self.zmin,self.zmax): entry.setEnabled(current and self.engine.currentIndex()==1)

    def restore_file(self):
        path = self.settings.value("last_file", "")
        if path and Path(path).is_file():
            self.load_path(path)

    def load_path(self, path):
        self.preview_timer.stop()
        self.settings.setValue("last_directory", str(Path(path).parent))
        self.settings.sync()
        self.background(lambda: read_parchg(path, self.progress_updates.put),
                        lambda volume: self.loaded(volume, path))

    def update_slider_ranges(self):
        if self.volume is None:
            return
        positive = self.volume.values[self.volume.values > 0]
        if positive.size:
            low = min(1e11, max(1e-10, float(positive.min())))
            high = min(1e12, max(low*10, float(positive.max())))
            self.signal_limits = (np.log10(low), np.log10(high))
        length = self.volume.lattice[2, 2]
        atom_z = self.volume.positions[:, 2] * length
        if self.side.currentIndex() == 0:
            limit = length*(self.volume.values.shape[2]-1)/self.volume.values.shape[2] - atom_z.max()
        else:
            limit = atom_z.min()
        self.height_limit = max(0., np.floor(float(limit)*1e10)/1e10)
        self.update_sliders()

    def update_sliders(self):
        low, high = self.signal_limits
        with QSignalBlocker(self.signal_slider):
            position = (np.log10(max(self.threshold.value(), 1e-10))-low)/(high-low)*1000
            self.signal_slider.setValue(int(np.clip(position, 0, 1000)))
        with QSignalBlocker(self.height_slider):
            position = self.height.value()/max(self.height_limit, 1e-10)*1000
            self.height_slider.setValue(int(np.clip(position, 0, 1000)))

    def drag_signal(self, position):
        low, high = self.signal_limits
        self.threshold.setValue(10**(low+(high-low)*position/1000))

    def drag_height(self, position):
        self.height.setValue(self.height_limit*position/1000)

    def parameter_changed(self):
        self.update_sliders()
        if self.volume is not None:
            self.preview_timer.start()

    def preview(self):
        if self.busy:
            self.preview_timer.start()
        else:
            self.run()

    def background(self,operation,callback):
        if self.busy:return
        self.busy=True;self.run_button.setEnabled(False);self.status.setText("正在处理…")
        self.progress.setRange(0, 0);self.progress.setVisible(True)
        def worker():
            try:self.jobs.put((callback,operation(),None))
            except Exception as error:self.jobs.put((callback,None,str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        while not self.progress_updates.empty():
            value = self.progress_updates.get_nowait()
            self.progress.setRange(0, 100)
            self.progress.setValue(value)
        try:callback,value,error=self.jobs.get_nowait()
        except queue.Empty:return
        self.busy=False;self.run_button.setEnabled(True)
        self.progress.setVisible(False)
        if error:
            self.status.setText(error);QMessageBox.warning(self,"STM Simulator",error)
        else:callback(value)

    def open_file(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,"选择 PARCHG",self.settings.value("last_directory", ""),"VASP volume (PARCHG* CHGCAR*);;All files (*)")
        if path:self.load_path(path)

    def loaded(self,volume, path=None):
        if path:
            self.settings.setValue("last_file", str(Path(path).resolve()))
            self.settings.sync()
        if hasattr(self, "height_map"):
            del self.height_map
        self.image.clear_line()
        self.volume=volume;self.image.volume=volume;self.result=None;self.image.image=None;self.image.update()
        z = (volume.positions @ volume.lattice)[:, 2]
        maximum = max(1, int(np.ceil(float(np.ptp(z))*100)))
        self.atom_depth_slider.setEnabled(True)
        self.atom_depth_slider.setMaximum(maximum)
        self.atom_depth_slider.setValue(min(500, maximum))
        self.change_atom_depth(self.atom_depth_slider.value())
        self.update_atom_side()
        self.file_label.setText(f"{volume.name}\n网格  {volume.values.shape}\n原子  {len(volume.positions)}")
        self.update_slider_ranges()
        self.surface.show_structure(volume)
        self.readout.setText("x  —     y  —     值  —")
        self.summary.setText("等待模拟");self.status.setText("已载入第一数据块 · 总部分密度")
        minimum, maximum = float(volume.values.min()), float(volume.values.max())
        if minimum < -max(1e-8, abs(maximum)*1e-4):
            self.status.setText(f"数据含明显负值 {minimum:.5g}，请核对总部分电荷密度来源；原子结构已显示")

    def open_heights(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择高度文件", self.settings.value("last_directory", ""), "Height archive (*.npz)")
        if not path:
            return
        try:
            with np.load(path, allow_pickle=False) as data:
                if str(data['unit']) != 'Å':
                    raise ValueError("高度文件单位必须为 Å，请使用恒流模式导出的 NPZ")
                heights = np.array(data['values'], dtype=float)
                lattice = np.array(data['lattice'], dtype=float)
            if heights.ndim != 2 or not np.isfinite(heights).any() or np.isinf(heights).any():
                raise ValueError("高度文件需要包含二维高度数组")
            if self.volume is None:
                raise ValueError("请先打开对应的 PARCHG，再导入恒流高度文件")
            if lattice.shape != (3, 3) or not np.allclose(lattice, self.volume.lattice):
                raise ValueError("高度文件与当前 PARCHG 的晶格不一致")
            if heights.shape != self.volume.values.shape[:2]:
                raise ValueError("高度文件与当前 PARCHG 的面内网格不一致")
            self.height_map = heights
            self.mode.setCurrentIndex(2)
            self.run()
        except (ValueError, KeyError, OSError) as error:
            QMessageBox.warning(self, "高度文件", str(error))

    def run(self):
        if self.volume is None or self.busy:return
        if self.mode.currentIndex() == 2:
            if not hasattr(self, "height_map"):
                self.open_heights()
                return
            volume, heights = self.volume, self.height_map.copy()
            parameters = dict(mode="height_map", engine="height_file")
            self.background(lambda: (sample_heights(volume, heights), heights),
                            lambda output: self.calculated(output, parameters))
            return
        self.preview_timer.stop()
        for field in (self.threshold,self.height,self.sigma):
            field.interpretText()
        try:
            bounded=self.engine.currentIndex()==1
            parameters=dict(mode="current" if self.mode.currentIndex()==0 else "height",engine="bounded" if bounded else "p4vasp",side="top" if self.side.currentIndex()==0 else "bottom",threshold=float(self.threshold.text()),height=float(self.height.text()),sigma=float(self.sigma.text()),z_min=float(self.zmin.text()) if bounded and self.zmin.text().strip() else None,z_max=float(self.zmax.text()) if bounded and self.zmax.text().strip() else None)
        except ValueError:
            QMessageBox.warning(self,"参数","请输入有效数值");return
        self.run_button.setFocus()
        self.preview_timer.stop()
        volume=self.volume
        self.background(lambda:simulate(volume,**parameters),lambda output:self.calculated(output,parameters))

    def calculated(self,output,parameters):
        self.result,self.plane_height=output;self.parameters=parameters
        finite=self.result[np.isfinite(self.result)]
        if not finite.size:
            self.result=None;self.image.clear_line();self.image.image=None;self.image.update();self.surface.show_structure(self.volume);self.status.setText("没有有效交点：起始密度必须低于阈值，请检查数据、阈值和搜索范围");return
        self.unit="Å" if parameters["mode"]=="current" else "raw density"
        self.summary.setText(f"{'恒流' if parameters['mode'] == 'current' else ('高度文件' if parameters['mode'] == 'height_map' else '恒高')}    |    {parameters['engine']}    |    {finite.min():.5g} — {finite.max():.5g} {self.unit}")
        self.status.setText(f"完成    ·    起伏 {np.ptp(finite):.5g} {self.unit}    ·    无交点 {100*np.isnan(self.result).mean():.1f}%")
        self.refresh_colors()

    def refresh_colors(self):
        if not self.tiles_a.hasAcceptableInput() or not self.tiles_b.hasAcceptableInput():
            return
        repeats = (int(self.tiles_a.text()), int(self.tiles_b.text()))
        fixed = self.color_range.currentIndex() == 1
        self.color_min.setEnabled(fixed)
        self.color_max.setEnabled(fixed)
        if self.result is None:
            return
        current = self.parameters["mode"] == "current"
        self.color_units.setEnabled(current)
        finite = self.result[np.isfinite(self.result)]
        low, high = float(finite.min()), float(finite.max())
        factor, offset = 1., 0.
        label = "density (raw)"
        if current:
            atom_z = (self.volume.positions @ self.volume.lattice)[:, 2]
            top = self.parameters.get("side", "top") == "top"
            offset = float(atom_z.max() if top else atom_z.min())
            length = self.volume.lattice[2, 2]
            branch = (offset-float(np.median(finite)))/length
            offset -= (np.ceil(branch) if top else np.floor(branch))*length
            factor = (1. if top else -1.) * (.1 if self.color_units.currentIndex() == 1 else 1.)
            label = "d / nm" if self.color_units.currentIndex() == 1 else "d / Å"
        if fixed:
            try:
                bottom = float(self.color_min.text()) if self.color_min.text().strip() else (low-offset)*factor
                top = float(self.color_max.text()) if self.color_max.text().strip() else (high-offset)*factor
                if not np.isfinite([bottom, top]).all() or bottom >= top:
                    raise ValueError()
                low, high = sorted((bottom/factor+offset, top/factor+offset))
            except ValueError:
                self.status.setText("色标范围无效，已使用全范围，请输入下限小于上限的有效数值")
                with QSignalBlocker(self.color_range):
                    self.color_range.setCurrentIndex(0)
                self.color_min.setEnabled(False)
                self.color_max.setEnabled(False)
        self.color_scale = ColorScale(low, high, self.palette.currentText(), factor, offset, label)
        if current:
            distances = self.color_scale.display_value(finite)
            self.summary.setText(f"恒流    |    距所选表面 {distances.min():.5g} — {distances.max():.5g} {'nm' if abs(factor)==.1 else 'Å'}")
        elif self.parameters['mode'] == 'height':
            self.summary.setText(f"恒高    |    距所选表面 {self.parameters['height']:.5g} Å    |    密度 {finite.min():.5g} — {finite.max():.5g}")
        self.image.set_data(self.result, self.volume.lattice, self.unit, self.color_scale, repeats)
        self.surface.set_data(self.result, self.volume, self.plane_height, self.color_scale)
        if self.image.line_points is not None:
            self.update_profile(*self.image.line_points)

    def set_projection_atoms_visible(self, visible):
        self.image.set_visibility("show_atoms", visible)
        self.sync_projection_range()

    def sync_projection_range(self):
        self.surface.set_projection_range(self.image.show_atoms, self.image.atom_depth, self.image.atom_side)

    def change_atom_depth(self, value):
        self.image.set_atom_depth(value)
        self.atom_depth_label.setText(f"{value/100:.2f} Å")
        self.sync_projection_range()

    def update_atom_side(self):
        self.image.atom_side = "top" if self.side.currentIndex() == 0 else "bottom"
        self.image.update()
        self.sync_projection_range()

    def set_line_mode(self, enabled):
        self.image.line_enabled = enabled
        if not enabled:
            self.image.drawing_line = False
        self.image.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def update_profile(self, start, end):
        if self.result is None or np.linalg.norm(end-start) < 1e-9:
            return
        inverse = np.linalg.inv(self.volume.lattice[:2, :2])
        start_frac, end_frac = start @ inverse, end @ inverse
        count = max(2, min(4096, int(np.linalg.norm((end_frac-start_frac)*self.result.shape)*2)+1))
        positions = np.linspace(start, end, count)
        fractional = positions @ inverse
        valid = np.all((fractional >= 0) & (fractional <= self.image.repeats), axis=1)
        coordinates = (fractional % 1)*np.array(self.result.shape)
        values = map_coordinates(self.result, coordinates.T, order=1, mode="grid-wrap", prefilter=False)
        values[~valid] = np.nan
        distance = np.linspace(0, np.linalg.norm(end-start), count)
        self.profile_distance = distance
        self.profile_values = self.color_scale.display_value(values)
        self.profile_curve.setData(distance, self.profile_values)
        self.profile_plot.set_samples(distance, self.profile_values)
        self.profile_plot.setLabel("left", self.color_scale.label)
        if self.profile_panel.isHidden() and not self.image.drawing_line:
            self.profile_panel.show()
            self.vertical_plots.setSizes([450, 180])
            self.profile_plot.autoRange()

    def export_data(self):
        if self.result is None:return
        path,_=QFileDialog.getSaveFileName(self,"导出数据","stm.npz","NumPy archive (*.npz)")
        if not path:return
        np.savez_compressed(path,values=self.result,lattice=self.volume.lattice,parameters=str(self.parameters),unit=self.unit)
        i,j=np.indices(self.result.shape)
        xy=np.stack([i/self.result.shape[0],j/self.result.shape[1]],axis=-1) @ self.volume.lattice[:2,:2]
        np.savetxt(Path(path).with_suffix(".csv"),np.column_stack([xy.reshape(-1,2),self.result.ravel()]),delimiter=",",header=f"x_A,y_A,value_{self.unit}",comments="")
        self.status.setText("已导出 NPZ 和 CSV")

    def export_image(self):
        if self.image.image is None:return
        path,_=QFileDialog.getSaveFileName(self,"导出图像","stm.png","PNG (*.png)")
        if path:self.image_tools.capture().save(path);self.status.setText("已导出 PNG")

def main():
    import sys
    app=QApplication(sys.argv);app.setStyle("Fusion")
    window=App();window.show();return app.exec()
