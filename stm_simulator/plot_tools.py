"""Hover actions shared by image, profile and OpenGL views."""
from PyQt6.QtCore import QObject, QEvent, QTimer, Qt, QSize
from PyQt6.QtGui import QCursor, QImage, QPixmap, QPainter, QPen, QColor, QIcon
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QToolButton, QApplication, QFileDialog


def action_icon(kind):
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#354b65"), 1.6))
    if kind == "reset":
        painter.drawArc(3, 3, 12, 12, 40*16, 290*16)
        painter.drawLine(14, 2, 14, 7)
        painter.drawLine(14, 7, 9, 7)
    elif kind == "copy":
        painter.drawRect(6, 6, 9, 9)
        painter.drawLine(3, 11, 3, 3)
        painter.drawLine(3, 3, 11, 3)
    else:
        painter.drawLine(9, 2, 9, 12)
        painter.drawLine(5, 8, 9, 12)
        painter.drawLine(9, 12, 13, 8)
        painter.drawLine(3, 13, 3, 16)
        painter.drawLine(3, 16, 15, 16)
        painter.drawLine(15, 16, 15, 13)
    painter.end()
    return QIcon(pixmap)


class HoverActions(QObject):
    def __init__(self, view, reset, filename):
        super().__init__(view)
        self.view = view
        self.filename = filename
        self.bar = QFrame(view)
        self.bar.setStyleSheet("QFrame {background:#ffffff;border:1px solid #c8d2df;border-radius:5px;} QToolButton {border:none;background:transparent;padding:5px;color:#243244;} QToolButton:hover {background:#d7e4f3;}")
        layout = QVBoxLayout(self.bar)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        for icon, label, callback in (("reset", "重置视图", reset), ("copy", "复制图像", self.copy), ("export", "导出图像", self.export)):
            button = QToolButton(self.bar)
            button.setIcon(action_icon(icon))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.bar.adjustSize()
        self.bar.hide()
        view.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.bar.move(max(0, self.view.width()-self.bar.width()-8), 8)
            self.bar.raise_()
        elif event.type() == QEvent.Type.Enter:
            self.bar.show()
            self.bar.raise_()
        elif event.type() == QEvent.Type.Leave:
            QTimer.singleShot(50, self.check_hover)
        return False

    def check_hover(self):
        if not self.view.rect().contains(self.view.mapFromGlobal(QCursor.pos())):
            self.bar.hide()

    def capture(self):
        visible = self.bar.isVisible()
        self.bar.hide()
        try:
            return self.view.grab()
        finally:
            self.bar.setVisible(visible)

    def copy(self):
        # Convert the OpenGL-backed pixmap before handing it to Windows.
        image = self.capture().toImage().convertToFormat(QImage.Format.Format_RGB32).copy()
        QApplication.clipboard().setImage(image)

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self.view, "导出图像", self.filename, "PNG (*.png)")
        if path:
            self.capture().save(path)
