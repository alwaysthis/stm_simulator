import unittest
from unittest.mock import patch
import numpy as np
from stm_simulator import native_backend
from stm_simulator.p4vasp_backend import constant_current


@unittest.skipUnless(native_backend.AVAILABLE, "Build native backend to test C++ parity")
class NativeTests(unittest.TestCase):
    def test_search_matches_numpy(self):
        rng = np.random.default_rng(13)
        base = rng.random((13, 11, 19))
        for data in (base, np.asfortranarray(base), base[::-1]):
            for direction in (-1, 1):
                for start in (None, 0, 18):
                    for threshold in (.2, .9, 2):
                        actual = constant_current(data, 24., threshold, direction, start)
                        with patch.object(native_backend, "AVAILABLE", False):
                            expected = constant_current(data, 24., threshold, direction, start)
                        np.testing.assert_allclose(actual, expected, atol=1e-12, equal_nan=True)

    def test_start_above_threshold_never_extrapolates(self):
        data = np.array([600., 599., 601.])[None, None, :]
        self.assertTrue(np.isnan(constant_current(data, 40., .001, start=0)).all())

    def test_parser_exponents_and_invalid_values(self):
        text = "1D-3 +2.0E+1 -3.5 0\t1\r\n2"
        np.testing.assert_allclose(native_backend.parse_density(text, 6), [.001, 20, -3.5, 0, 1, 2])
        for text in ("invalid", "1.2bad", "nan", "inf", "1 2"):
            with self.assertRaises(ValueError):
                native_backend.parse_density(text, 1)
