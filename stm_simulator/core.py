"""Tersoff-Hamann maps from VASP volumetric partial charge files."""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
from .native_backend import parse_density

@dataclass
class Volume:
    lattice: np.ndarray
    positions: np.ndarray
    values: np.ndarray
    name: str
    elements: tuple[str, ...] = ()

    @property
    def cell_volume(self):
        return abs(np.linalg.det(self.lattice))


def read_parchg(path, progress=None):
    """Read the first (total-density) block. Preserve VASP's raw normalization."""
    with open(path, encoding="utf-8", errors="replace") as stream:
        name = stream.readline().strip()
        scales = np.fromstring(stream.readline(), sep=" ")
        lattice = np.array([np.fromstring(stream.readline(), sep=" ") for _ in range(3)])
        if lattice.shape != (3, 3) or len(scales) not in (1, 3):
            raise ValueError("Invalid lattice header")
        if len(scales) == 1:
            factor = scales[0]
            if factor < 0:
                factor = (abs(factor) / abs(np.linalg.det(lattice))) ** (1/3)
            lattice *= factor
            cart_scale = factor
        else:
            if np.any(scales <= 0):
                raise ValueError("Three scale factors must be positive")
            lattice *= scales
            cart_scale = scales
        line = stream.readline().split()
        symbols = None
        if not all(token.isdigit() for token in line):
            symbols = line
            line = stream.readline().split()
        counts = [int(token) for token in line]
        if not counts or (symbols is not None and len(symbols) != len(counts)):
            raise ValueError("Element names and atom counts do not match")
        if symbols is None:
            symbols = [f"X{i+1}" for i in range(len(counts))]
        elements = tuple(symbol for symbol, count in zip(symbols, counts) for _ in range(count))
        mode = stream.readline().strip()
        if mode.lower().startswith("s"):
            mode = stream.readline().strip()
        positions = np.array([[float(v) for v in stream.readline().split()[:3]]
                              for _ in range(sum(counts))])
        if mode.lower().startswith(("c", "k")):
            positions = (positions * cart_scale) @ np.linalg.inv(lattice)
        elif not mode.lower().startswith("d"):
            raise ValueError("Unknown coordinate mode")
        line = stream.readline()
        while line and not line.strip():
            line = stream.readline()
        shape = tuple(int(v) for v in line.split())
        if len(shape) != 3 or min(shape) <= 0:
            raise ValueError("Invalid FFT grid dimensions")
        size = int(np.prod(shape))
        values = np.empty(size)
        offset = 0
        if progress:
            progress(0)
        while offset < size:
            lines = []
            token_count = 0
            while len(lines) < 2048 and offset + token_count < size:
                line = stream.readline()
                if not line:
                    raise ValueError("Incomplete density block")
                lines.append(line)
                token_count += len(line.split())
            if offset + token_count > size:
                raise ValueError("Too many values in density block")
            chunk = parse_density(" ".join(lines), token_count)
            if len(chunk) != token_count:
                raise ValueError("Invalid density value")
            values[offset:offset + len(chunk)] = chunk
            offset += len(chunk)
            if progress:
                progress(min(99, int(offset * 100 / size)))
    if not np.isfinite(values).all():
        raise ValueError("Density contains non-finite values")
    if progress:
        progress(100)
    return Volume(lattice, positions, values.reshape(shape, order="F"), name, elements)


def simulate(volume, mode="current", height=4., threshold=0.001,
             side="top", sigma=0., z_min=None, z_max=None, engine="bounded"):
    """Threshold is in raw PARCHG units; heights use Cartesian angstroms.

    Constant-current chooses the first vacuum-to-surface upward crossing in
    the selected z interval. Missing crossings remain NaN, never zero.
    """
    lattice = volume.lattice
    if not (np.allclose(lattice[:2, 2], 0, atol=1e-7)
            and np.allclose(lattice[2, :2], 0, atol=1e-7) and lattice[2, 2] > 0):
        raise ValueError("Requires a,b in xy and a positive c vector along z")
    if side not in ("top", "bottom") or mode not in ("height", "current"):
        raise ValueError("Unknown simulation mode or surface")
    if sigma < 0:
        raise ValueError("Smoothing sigma must be nonnegative")
    data = volume.values
    if sigma:
        data = gaussian_filter(data, sigma=sigma, mode="wrap")
    length = lattice[2, 2]
    z = np.arange(data.shape[2]) * length / data.shape[2]
    atom_z = volume.positions[:, 2] * length
    if mode == "height":
        if height < 0:
            raise ValueError("Tip distance must be nonnegative")
        target = atom_z.max()+height if side == "top" else atom_z.min()-height
        if not z[0] <= target <= z[-1]:
            raise ValueError("Tip plane is outside the stored cell")
        index = min(int(target / length * len(z)), len(z)-2)
        fraction = (target-z[index]) / (z[index+1]-z[index])
        return data[:, :, index]*(1-fraction)+data[:, :, index+1]*fraction, target
    if threshold <= 0:
        raise ValueError("Density threshold must be positive")
    if engine == "p4vasp":
        from .p4vasp_backend import constant_current
        if z_min is not None or z_max is not None:
            raise ValueError("p4vasp auto mode uses a full periodic cell; clear z bounds")
        return constant_current(data, length, threshold, -1 if side == "top" else 1), None
    # Defaults only search the vacuum adjacent to the selected surface.
    low = atom_z.max() if side == "top" else z[0]
    high = z[-1] if side == "top" else atom_z.min()
    low = low if z_min is None else z_min
    high = high if z_max is None else z_max
    if not (0 <= low < high <= z[-1]):
        raise ValueError("Invalid search interval within the stored cell")
    indices = np.where((z >= low) & (z <= high))[0]
    if side == "top":
        indices = indices[::-1]
    if len(indices) < 2:
        raise ValueError("Search interval needs at least two grid planes")
    result = np.full(data.shape[:2], np.nan)
    for outer, inner in zip(indices[:-1], indices[1:]):
        first, second = data[:, :, outer], data[:, :, inner]
        crossing = np.isnan(result) & (first < threshold) & (second >= threshold)
        fraction = np.zeros_like(first)
        np.divide(threshold-first, second-first, out=fraction, where=crossing)
        result[crossing] = (z[outer]+fraction*(z[inner]-z[outer]))[crossing]
    return result, None
