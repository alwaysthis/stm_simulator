"""Element display styles from the crystalX VESTA theme."""
import json
from pathlib import Path
import numpy as np

STYLES = json.loads(Path(__file__).with_name("element_styles.json").read_text(encoding="utf-8"))


def atom_styles(volume):
    elements = volume.elements or tuple("X" for _ in volume.positions)
    colors, radii = [], []
    for element in elements:
        style = STYLES.get(element.split("_")[0], {"color": [.6, .6, .6], "radius": .8})
        colors.append([*style["color"], 1.])
        radii.append(style["radius"])
    return elements, np.asarray(colors, dtype=np.float32), np.asarray(radii, dtype=np.float32)
