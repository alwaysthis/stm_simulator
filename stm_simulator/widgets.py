"""Studio-inspired controls. Geometry follows the reference studio branch."""
from PyQt6.QtCore import Qt, QSize, QRectF, QLocale
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QFontMetrics, QCursor
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QTabBar

class ChevronComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#c8c8c8" if self.isEnabled() else "#666666"), 1.6))
        x, y = self.width()-17, self.height()//2
        painter.drawLine(x-5, y-2, x, y+3)
        painter.drawLine(x, y+3, x+5, y-2)

class NumericBox(QDoubleSpinBox):
    def __init__(self, value, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setDecimals(10)
        self.setRange(0, 1e12)
        self.setSingleStep(.1)
        self.setKeyboardTracking(False)
        self.setValue(float(value))

    def textFromValue(self, value):
        return f"{value:.10f}".rstrip("0").rstrip(".") or "0"

    def wheelEvent(self, event):
        event.ignore()

class WorkspaceTabBar(QTabBar):
    """Compact round-top tabs, full-width strip, fixed label position."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def tabSizeHint(self, index):
        font = QFont(self.font())
        font.setPixelSize(12)
        metrics = QFontMetrics(font)
        return QSize(max(64, metrics.horizontalAdvance(self.tabText(index))+16)+4,
                     max(26, metrics.height()+12))

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#303030"))
        font = QFont(self.font()); font.setPixelSize(12); painter.setFont(font)
        cursor = self.mapFromGlobal(QCursor.pos())
        for index in range(self.count()):
            rect = QRectF(self.tabRect(index)).adjusted(0, 0, -4, 0)
            if index == self.currentIndex():
                radius = min(10.,rect.height()/2)
                path = QPainterPath()
                path.moveTo(rect.left(),rect.bottom())
                path.lineTo(rect.left(),rect.top()+radius)
                path.quadTo(rect.left(),rect.top(),rect.left()+radius,rect.top())
                path.lineTo(rect.right()-radius,rect.top())
                path.quadTo(rect.right(),rect.top(),rect.right(),rect.top()+radius)
                path.lineTo(rect.right(),rect.bottom());path.closeSubpath()
                painter.fillPath(path,QColor("#222222"))
            elif rect.contains(float(cursor.x()),float(cursor.y())):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#3c3c3c"))
                painter.drawRoundedRect(rect.adjusted(2,2,-2,-2),6,6)
            painter.setPen(QColor("#9e9e9e"))
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,self.tabText(index))
