"""Qt instrument panel, styled after the clc_mbe control panel."""
import queue
import threading
from pathlib import Path
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QFont
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QSplitter, QFileDialog, QMessageBox, QScrollArea)
from .core import read_parchg, simulate, demo_volume
from .widgets import ChevronComboBox, NumericBox

STYLE = """
QMainWindow, QWidget {background:#242424;color:#ffffff;font-family:'Microsoft YaHei UI';font-size:13px;}
QFrame#panel {background:#1c1c1c;border:1px solid #303030;border-radius:8px;}
QFrame#card {background:#1c1c1c;border:1px solid #303030;border-radius:4px;}
QLabel {background:transparent;border:none;}
QLabel#muted {color:#9e9e9e;}
QPushButton {background:#4a4a4a;border:1px solid #3a3a3a;border-radius:4px;padding:6px 12px;}
QPushButton:hover {background:#5a5a5a;border-color:#4a90d9;}
QPushButton:pressed {background:#333333;}
QPushButton:disabled {color:#777777;}
QPushButton#primary {background:#3d6a9a;border-color:#4a90d9;}
QPushButton#primary:hover {background:#4a90d9;}
QLineEdit,QComboBox,QDoubleSpinBox {background:#1e1e1e;border:1px solid #3a3a3a;border-radius:4px;padding:3px 8px;min-height:20px;selection-background-color:#4a90d9;}
QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {border-color:#4a90d9;}
QLineEdit:hover,QComboBox:hover,QDoubleSpinBox:hover {border-color:#4a90d9;background:#242424;}
QLineEdit:disabled,QComboBox:disabled,QDoubleSpinBox:disabled {color:#666666;border-color:#303030;}
QComboBox::down-arrow {image:none;}
QComboBox QAbstractItemView {background:#1e1e1e;color:#ffffff;border:1px solid #3a3a3a;selection-background-color:#3d6a9a;outline:none;padding:4px;}
QComboBox QAbstractItemView::item {min-height:26px;padding:3px 8px;}
QDoubleSpinBox::up-button {width:18px;border:none;border-top-right-radius:4px;}
QDoubleSpinBox::down-button {width:18px;border:none;border-bottom-right-radius:4px;}
QDoubleSpinBox::up-button:hover,QDoubleSpinBox::down-button:hover {background:#3c3c3c;}
QComboBox::drop-down {border:none;width:22px;}
QScrollArea {border:none;background:transparent;}
QScrollBar:vertical {background:transparent;width:6px;}
QScrollBar::handle:vertical {background:#4a4a4a;border-radius:3px;min-height:25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QSplitter::handle {background:#242424;width:8px;}
"""

class ImageView(QWidget):
    def __init__(self, readout):
        super().__init__()
        self.setMouseTracking(True)
        self.readout = readout
        self.pixels = self.image = self.result = None
        self.setMinimumSize(350, 300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        if self.image is None:
            painter.setPen(QColor("#808080"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,"打开 PARCHG 或载入演示数据")
            return
        scale = min((self.width()-70)/self.image.width(),(self.height()-70)/self.image.height())
        width, height = int(self.image.width()*scale),int(self.image.height()*scale)
        self.rect_image = ((self.width()-width)//2,(self.height()-height)//2,width,height)
        x,y,_,_ = self.rect_image
        painter.drawPixmap(x,y,width,height,QPixmap.fromImage(self.image))
        painter.setPen(QColor("#9e9e9e"))
        painter.drawText(x,y+height+22,"x / y (Å)    暗 → 低    亮 → 高    洋红 → 无交点")

    def mouseMoveEvent(self,event):
        if self.image is None or not hasattr(self,"rect_image"):
            return
        ox,oy,w,h = self.rect_image
        px,py = event.position().x(),event.position().y()
        xy = self.low+np.array([(px-ox)/w,1-(py-oy)/h])*(self.high-self.low)
        frac = xy @ np.linalg.inv(self.lattice[:2,:2])
        if np.all((frac>=0)&(frac<1)):
            i,j=(frac*np.array(self.result.shape)).astype(int)
            self.readout.setText(f"x  {xy[0]:.3f} Å     y  {xy[1]:.3f} Å     值  {self.result[i,j]:.6g} {self.unit}")

    def set_data(self,result,lattice,unit):
        self.result,self.lattice,self.unit=result,lattice,unit
        finite=result[np.isfinite(result)]
        low,high=float(finite.min()),float(finite.max())
        normalized=np.nan_to_num((result-low)/(high-low if high>low else 1),nan=0)
        anchors=np.array([[11,17,34],[21,69,109],[29,153,150],[147,215,148],[255,239,172]])
        rgb=np.stack([np.interp(normalized,np.linspace(0,1,5),anchors[:,c]) for c in range(3)],axis=-1).astype(np.uint8)
        rgb[np.isnan(result)]=[110,30,70]
        corners=np.array([[0,0],lattice[0,:2],lattice[1,:2],lattice[0,:2]+lattice[1,:2]])
        self.low,self.high=corners.min(axis=0),corners.max(axis=0)
        shape=np.maximum(1,((self.high-self.low)/max(self.high-self.low)*900).astype(int))
        xx,yy=np.meshgrid(np.linspace(self.low[0],self.high[0],shape[0]),np.linspace(self.high[1],self.low[1],shape[1]))
        fractional=np.stack([xx,yy],axis=-1) @ np.linalg.inv(lattice[:2,:2])
        mask=np.all((fractional>=0)&(fractional<=1),axis=-1)
        ij=np.clip((fractional*np.array(result.shape)).astype(int),0,np.array(result.shape)-1)
        self.pixels=np.ascontiguousarray(rgb[ij[:,:,0],ij[:,:,1]])
        self.pixels[~mask]=[17,17,17]
        self.image=QImage(self.pixels.data,shape[0],shape[1],shape[0]*3,QImage.Format.Format_RGB888).copy()
        self.update()

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STM Simulator")
        self.resize(1240,720)
        self.setMinimumSize(950,650)
        self.setStyleSheet(STYLE)
        self.volume=self.result=None
        self.busy=False
        self.jobs=queue.Queue()
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(50)
        root=QWidget();self.setCentralWidget(root)
        layout=QVBoxLayout(root);layout.setContentsMargins(8,6,8,6);layout.setSpacing(8)
        toolbar=QHBoxLayout();toolbar.setSpacing(8)
        title=QLabel("STM Simulator");title.setFont(QFont("Microsoft YaHei UI",11,QFont.Weight.Bold));toolbar.addWidget(title);toolbar.addSpacing(20)
        for text,callback in [("打开文件",self.open_file),("演示数据",self.demo),("导出图像",self.export_image),("导出数据",self.export_data),("帮助",self.show_help)]:
            button=QPushButton(text);button.clicked.connect(callback);toolbar.addWidget(button)
        toolbar.addStretch();state=QLabel("●  离线分析");state.setStyleSheet("color:#83bd8b");toolbar.addWidget(state)
        layout.addLayout(toolbar)
        body=QHBoxLayout();body.setSpacing(8);layout.addLayout(body,1)
        split=QSplitter();body.addWidget(split,1)
        view=QWidget();view.setStyleSheet("background:#222222;")
        view_layout=QVBoxLayout(view);view_layout.setContentsMargins(24,10,24,10)
        self.summary=QLabel("等待数据");self.summary.setObjectName("muted");view_layout.addWidget(self.summary)
        self.readout=QLabel("x  —     y  —     值  —");self.readout.setObjectName("muted")
        self.image=ImageView(self.readout);view_layout.addWidget(self.image,1);view_layout.addWidget(self.readout)
        split.addWidget(view)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setMinimumWidth(290);scroll.setMaximumWidth(360)
        panel=QFrame();panel.setObjectName("panel");scroll.setWidget(panel);split.addWidget(scroll);split.setSizes([900,300])
        controls=QVBoxLayout(panel);controls.setContentsMargins(12,12,12,12);controls.setSpacing(12)
        controls.addWidget(QLabel("模拟设置"))
        self.run_button=QPushButton("运行模拟");self.run_button.setObjectName("primary");self.run_button.clicked.connect(self.run);controls.addWidget(self.run_button)
        source=self.card(controls,"数据源");self.file_label=QLabel("尚未载入 PARCHG");self.file_label.setWordWrap(True);self.file_label.setMinimumHeight(64);self.file_label.setObjectName("muted");source.addRow(self.file_label)
        form=self.card(controls,"扫描参数")
        self.mode=self.combo(form,"扫描模式",["恒流","恒高"])
        self.engine=self.combo(form,"搜索算法",["p4vasp 线性","限定真空 · 线性"])
        self.side=self.combo(form,"扫描表面",["上表面 / −c","下表面 / +c"])
        self.threshold=self.entry(form,"等密度阈值","0.001");self.threshold.setRange(1e-10,1e12);self.threshold.setSingleStep(.0001)
        self.height=self.entry(form,"距外层原子 / Å","4.0");self.height.setSingleStep(.1)
        self.sigma=self.entry(form,"平滑 / 网格 σ","0")
        bounds=self.card(controls,"限定真空范围 · 留空自动")
        self.zmin=self.entry(bounds,"z 下界 / Å","");self.zmax=self.entry(bounds,"z 上界 / Å","")
        self.engine.currentIndexChanged.connect(self.sync_controls);self.mode.currentIndexChanged.connect(self.sync_controls)
        self.sync_controls();controls.addStretch()
        self.status=QLabel("就绪    ·    PARCHG 原始密度单位");self.status.setObjectName("muted");layout.addWidget(self.status)

    def show_help(self):
        QMessageBox.information(self, "方法说明", "Tersoff–Hamann 近似\n\np4vasp 线性模式\n从平面平均密度最小层开始，周期搜索首个达到阈值的点，再线性插值。\n上表面沿 −c 搜索，下表面沿 +c 搜索。输出保留展开的周期坐标。\n无交点以 NaN 标记。\n\n限定真空模式\n仅搜索最外层原子之外的真空，可指定 z 范围。\n\n偏压能窗由 VASP 的 EINT 设置。阈值为 PARCHG 原始数值。")

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
        current=self.mode.currentIndex()==0
        self.threshold.setEnabled(current);self.height.setEnabled(not current);self.engine.setEnabled(current)
        for entry in (self.zmin,self.zmax): entry.setEnabled(current and self.engine.currentIndex()==1)

    def background(self,operation,callback):
        if self.busy:return
        self.busy=True;self.run_button.setEnabled(False);self.status.setText("正在处理…")
        def worker():
            try:self.jobs.put((callback,operation(),None))
            except Exception as error:self.jobs.put((callback,None,str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        try:callback,value,error=self.jobs.get_nowait()
        except queue.Empty:return
        self.busy=False;self.run_button.setEnabled(True)
        if error:
            self.status.setText(error);QMessageBox.warning(self,"STM Simulator",error)
        else:callback(value)

    def open_file(self):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,"选择 PARCHG","","VASP volume (PARCHG* CHGCAR*);;All files (*)")
        if path:self.background(lambda:read_parchg(path),self.loaded)

    def loaded(self,volume):
        self.volume=volume;self.result=None;self.image.image=None;self.image.update()
        self.file_label.setText(f"{volume.name}\n网格  {volume.values.shape}\n原子  {len(volume.positions)}")
        self.summary.setText("等待模拟");self.status.setText("已载入第一数据块 · 总部分密度")

    def demo(self):
        if not self.busy:self.loaded(demo_volume());self.run()

    def run(self):
        if self.volume is None or self.busy:return
        for field in (self.threshold,self.height,self.sigma):
            field.interpretText()
        try:
            bounded=self.engine.currentIndex()==1
            parameters=dict(mode="current" if self.mode.currentIndex()==0 else "height",engine="bounded" if bounded else "p4vasp",side="top" if self.side.currentIndex()==0 else "bottom",threshold=float(self.threshold.text()),height=float(self.height.text()),sigma=float(self.sigma.text()),z_min=float(self.zmin.text()) if bounded and self.zmin.text().strip() else None,z_max=float(self.zmax.text()) if bounded and self.zmax.text().strip() else None)
        except ValueError:
            QMessageBox.warning(self,"参数","请输入有效数值");return
        volume=self.volume
        self.background(lambda:simulate(volume,**parameters),lambda output:self.calculated(output,parameters))

    def calculated(self,output,parameters):
        self.result,self.plane_height=output;self.parameters=parameters
        finite=self.result[np.isfinite(self.result)]
        if not finite.size:
            self.result=None;self.image.image=None;self.image.update();self.status.setText("没有交点，请调整阈值或范围");return
        self.unit="Å" if parameters["mode"]=="current" else "raw density"
        self.summary.setText(f"{self.mode.currentText()}    |    {parameters['engine']}    |    {finite.min():.5g} — {finite.max():.5g} {self.unit}")
        self.status.setText(f"完成    ·    起伏 {np.ptp(finite):.5g} {self.unit}    ·    无交点 {100*np.isnan(self.result).mean():.1f}%")
        self.image.set_data(self.result,self.volume.lattice,self.unit)

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
        if path:self.image.image.save(path);self.status.setText("已导出 PNG")

def main():
    import sys
    app=QApplication(sys.argv);app.setStyle("Fusion")
    window=App();window.show();return app.exec()
