"""Studio-inspired controls. Geometry follows the reference studio branch."""
from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox

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
