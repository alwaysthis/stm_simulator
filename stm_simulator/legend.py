"""Shared transparent atom legend for the STM and 3D views."""
import math
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QFont, QPen, QRadialGradient
from .elements import atom_styles


def paint_atom_legend(painter, volume, width, height):
    if volume is None:
        return
    elements, colors, radii = atom_styles(volume)
    unique = list(dict.fromkeys(elements))
    if not unique:
        return
    indices = [elements.index(element) for element in unique]
    rows = max(1, min(len(indices), (height-40)//20))
    columns = math.ceil(len(indices)/rows)
    left = max(6, width-12-columns*62)
    top = max(8, height-12-rows*20-19)
    painter.save()
    painter.setOpacity(1.)
    painter.setRenderHint(painter.RenderHint.Antialiasing)
    painter.setFont(QFont("Microsoft YaHei UI", 8))
    painter.setPen(QColor("#243244"))
    painter.drawText(left, top+11, "原子图例")
    largest = max(float(radii[i]) for i in indices)
    for k, i in enumerate(indices):
        x = left+(k//rows)*62+8
        y = top+28+(k%rows)*20
        radius = max(3., 7.*float(radii[i])/max(largest, .01))
        color = QColor.fromRgbF(*colors[i])
        gradient = QRadialGradient(QPointF(x-radius*.3, y-radius*.35), radius*1.5)
        gradient.setColorAt(0, QColor("white"))
        gradient.setColorAt(.3, color.lighter(130))
        gradient.setColorAt(.6, color)
        gradient.setColorAt(1, color.darker(230))
        painter.setBrush(gradient)
        painter.setPen(QPen(color.darker(160), .6))
        painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.setPen(QColor("#243244"))
        painter.drawText(QPointF(x+12, y+4), elements[i])
    painter.restore()
