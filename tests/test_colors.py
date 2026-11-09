import unittest
import numpy as np
from stm_simulator.colors import ColorScale


class ColorTests(unittest.TestCase):
    def test_linear_clipping_and_missing_values(self):
        scale = ColorScale(10., 20., "灰度")
        rgba = scale.rgba(np.array([0., 10., 15., 20., 30., np.nan]))
        np.testing.assert_allclose(rgba[:5, 0], [0, 0, .5, 1, 1])
        self.assertEqual(rgba[-1, 3], 0)

    def test_relative_nm_keeps_same_mapping(self):
        scale = ColorScale(12., 14., "铜色", .1, 12., "Δz / nm")
        np.testing.assert_allclose(scale.display_value(np.array([12., 13., 14.])), [0, .1, .2])
        original = ColorScale(12., 14., "铜色")
        np.testing.assert_array_equal(scale.rgba(np.array([12., 13., 14.])), original.rgba(np.array([12., 13., 14.])))

    def test_constant_map(self):
        scale = ColorScale(12., 12., "灰度")
        self.assertTrue(np.isfinite(scale.rgba(np.full((2, 2), 12.))).all())
