# SPDX-License-Identifier: GPL-2.0-or-later
# Python adaptation of p4vasp STMSearchProcess::searchFast/getHeightFast.
# Original p4vasp Copyright (C) 2003 Orest Dubay.
"""Periodic constant-current search matching p4vasp's linear mode."""
import numpy as np
from . import native_backend

def constant_current(data, cell_height, threshold, direction=-1, start=None):
    """Auto-start at minimum plane-averaged density, search one periodic cell.

    Returns unwrapped physical z, preserving p4vasp's periodic coordinate branch.
    p4vasp's missing-crossing zero is represented by NaN here.
    """
    nz = data.shape[2]
    start = int(np.argmin(data.mean(axis=(0, 1)))) if start is None else int(start)
    step = -1 if direction <= 0 else 1
    if native_backend.AVAILABLE:
        return native_backend.constant_current(data, cell_height, threshold, step, start)
    result = np.full(data.shape[:2], np.nan)
    count = nz+1 if step < 0 else nz
    for offset in range(count):
        inner = start + step*offset
        outer = inner-step
        y1 = data[:, :, inner % nz]
        y2 = data[:, :, outer % nz]
        found = np.isnan(result) & (y1 >= threshold)
        fraction = np.zeros_like(y1)
        np.divide(threshold-y1, y2-y1, out=fraction, where=found & (y2 != y1))
        height = (inner + (outer-inner)*fraction)*cell_height/nz
        result[found] = height[found]
    return result
