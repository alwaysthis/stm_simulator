"""ctypes bridge for the optional C++ parser and p4vasp linear search."""
import ctypes
from pathlib import Path
import sys
import numpy as np

_library = None
_path = Path(__file__).with_name("_stm_native_v2.dll" if sys.platform == "win32" else "_stm_native_v2.so")
try:
    _library = ctypes.CDLL(str(_path))
except OSError:
    pass

_double_pointer = ctypes.POINTER(ctypes.c_double)
if _library is not None:
    _library.parse_density.argtypes = [ctypes.c_char_p, ctypes.c_size_t, _double_pointer, ctypes.c_size_t]
    _library.parse_density.restype = ctypes.c_longlong
    _library.constant_current.argtypes = [_double_pointer] + [ctypes.c_size_t]*6 + [
        ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_longlong, _double_pointer]
    _library.constant_current.restype = None

AVAILABLE = _library is not None


def parse_density(text, count):
    text = text.replace("D", "E").replace("d", "e")
    if not AVAILABLE:
        return np.fromstring(text, sep=" ")
    encoded = text.encode("ascii")
    output = np.empty(count, dtype=np.float64)
    parsed = _library.parse_density(encoded, len(encoded), output.ctypes.data_as(_double_pointer), count)
    if parsed != count:
        raise ValueError("Invalid density value")
    return output


def constant_current(data, cell_height, threshold, direction, start):
    # Keep positive-stride NumPy layouts without copying the whole volume.
    data = np.asarray(data, dtype=np.float64)
    if any(stride < 0 for stride in data.strides):
        data = np.ascontiguousarray(data)
    output = np.empty(data.shape[:2], dtype=np.float64)
    strides = [stride // data.itemsize for stride in data.strides]
    _library.constant_current(data.ctypes.data_as(_double_pointer), *data.shape, *strides,
                              cell_height, threshold, direction, start,
                              output.ctypes.data_as(_double_pointer))
    return output
