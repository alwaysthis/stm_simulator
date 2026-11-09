# p4vasp source adaptation

The linear constant-current backend in stm_simulator/p4vasp_backend.py is adapted from p4vasp, copyright Orest Dubay, GPL-2.0-or-later. This distribution uses GPL-2.0-or-later. Original repository MIT notice is retained in LICENSE-MIT-original.

Source: https://github.com/orest-d/p4vasp
Pinned revision: 1fbd85e52f1e56f1d096934dc6aaa37bebfedb1a
Functions: src/ChgcarSmear.cpp STMSearchProcess::update, searchFast, getHeightFast; src/Chgcar.cpp searchMinPlaneZ; src/include/p4vasp/Chgcar.h defaults n=-1, delta=-1.

The port preserves automatic minimum-plane start, negative default direction, periodic indexing, first >= threshold hit and linear height interpolation. Missing hits use NaN instead of 0. Cubic mode is not ported. The independent bounded backend remains available. Raw PARCHG units are preserved.

The equivalent C++ linear search in native/stm_native.cpp uses the same pinned p4vasp algorithms and GPL-2.0-or-later attribution. The density parser uses the C++ standard library from_chars implementation.
