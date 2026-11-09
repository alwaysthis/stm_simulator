"""One linear value-to-color mapping shared by both views and the colorbar."""
from dataclasses import dataclass
import numpy as np

PALETTES = {
    "铜色": [(0, 0, 0), (100, 50, 25), (200, 113, 57), (255, 199, 127), (255, 245, 220)],
    "灰度": [(0, 0, 0), (255, 255, 255)],
    "蓝绿": [(11, 17, 34), (21, 69, 109), (29, 153, 150), (147, 215, 148), (255, 239, 172)],
}


@dataclass
class ColorScale:
    low: float
    high: float
    palette: str = "铜色"
    factor: float = 1.
    offset: float = 0.
    label: str = "z / Å"

    def rgba(self, values):
        values = np.asarray(values)
        span = self.high-self.low
        normalized = np.clip((values-self.low)/(span if span else 1.), 0, 1)
        normalized = np.nan_to_num(normalized)
        anchors = np.asarray(PALETTES[self.palette], dtype=float)/255
        rgb = np.stack([np.interp(normalized, np.linspace(0, 1, len(anchors)), anchors[:, c])
                        for c in range(3)], axis=-1)
        return np.concatenate((rgb, np.isfinite(values)[..., None].astype(float)), axis=-1)

    def display_value(self, raw):
        return (raw-self.offset)*self.factor
