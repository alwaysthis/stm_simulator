"""Interactive Cartesian STM surface and atomic-position view."""
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap, Normalize

STM_COLORS = ["#0b1122", "#15456d", "#1d9996", "#93d794", "#ffefac"]


class SurfaceView(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(facecolor="#222222")
        super().__init__(self.figure)
        self.setMinimumSize(240, 260)
        self.axes = self.figure.add_subplot(111, projection="3d")
        self.figure.subplots_adjust(left=.02, right=.92, bottom=.08, top=1)
        self.atom_artist = None
        self.show_atoms = True
        self.clear()

    def clear(self):
        self.axes.clear()
        self.atom_artist = None
        self.axes.set_facecolor("#222222")
        self.axes.tick_params(colors="#9e9e9e", labelsize=8)
        for axis, label in zip((self.axes.xaxis, self.axes.yaxis, self.axes.zaxis),
                               ("x / Å", "y / Å", "z / Å")):
            axis.set_pane_color((.14, .14, .14, 1))
            axis.label.set_color("#9e9e9e")
            axis.set_label_text(label, fontsize=9)
        self.draw_idle()

    def set_atoms_visible(self, visible):
        self.show_atoms = visible
        if self.atom_artist is not None:
            self.atom_artist.set_visible(visible)
        self.draw_idle()

    def set_data(self, result, volume, plane_height=None):
        elevation, azimuth = self.axes.elev, self.axes.azim
        self.clear()
        # Limit display geometry only. Scientific results and exports stay full resolution.
        indices = [np.unique(np.linspace(0, n-1, min(n, 120)).astype(int))
                   for n in result.shape]
        i, j = np.meshgrid(*indices, indexing="ij")
        xy = np.stack((i/result.shape[0], j/result.shape[1]), axis=-1) @ volume.lattice[:2, :2]
        values = result[np.ix_(*indices)]
        finite = result[np.isfinite(result)]
        norm = Normalize(float(finite.min()), float(finite.max()))
        colors = LinearSegmentedColormap.from_list("stm", STM_COLORS)(norm(values))
        colors[~np.isfinite(values), 3] = 0
        z = values if plane_height is None else np.full_like(values, plane_height)
        z = np.where(np.isfinite(values), z, np.nan)
        self.axes.plot_surface(xy[..., 0], xy[..., 1], z, facecolors=colors,
                               rstride=1, cstride=1, linewidth=0, shade=False,
                               antialiased=False, alpha=.8)
        atoms = volume.positions @ volume.lattice
        # p4vasp returns an unwrapped periodic z branch. Show the nearest
        # periodic copy of the atoms so the structure accompanies that branch.
        center = float(np.nanmedian(z))
        shift = np.round((center - np.median(atoms[:, 2])) / volume.lattice[2, 2])
        atoms[:, 2] += shift * volume.lattice[2, 2]
        self.atom_artist = self.axes.scatter(*atoms.T, s=26, c="#c8c8c8",
                                            edgecolors="#ffffff", linewidths=.4,
                                            depthshade=True, visible=self.show_atoms)
        corners = np.array([[0, 0], volume.lattice[0, :2], volume.lattice[1, :2],
                            volume.lattice[0, :2]+volume.lattice[1, :2]])
        low, high = corners.min(axis=0), corners.max(axis=0)
        self.axes.set_xlim(low[0], high[0])
        self.axes.set_ylim(low[1], high[1])
        zlow = min(float(np.nanmin(z)), float(atoms[:, 2].min()))
        zhigh = max(float(np.nanmax(z)), float(atoms[:, 2].max()))
        padding = max(.5, (zhigh-zlow)*.08)
        self.axes.set_zlim(zlow-padding, zhigh+padding)
        self.axes.set_box_aspect((max(high[0]-low[0], .1), max(high[1]-low[1], .1),
                                 max(zhigh-zlow+2*padding, .1)), zoom=.85)
        self.axes.view_init(elevation, azimuth)
        self.draw_idle()
