import tempfile
import unittest
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import QApplication
from stm_simulator.app import App
from stm_simulator.core import Volume


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_line_uses_cartesian_distance_and_bilinear_values(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(Path(directory)/"settings.ini")
            lattice = np.array([[10., 0, 0], [3., 8., 0], [0, 0, 30.]])
            i, j = np.indices((40, 40))
            result = 12.+i/40*2+j/40*3
            volume = Volume(lattice, np.array([[.5, .5, .3]]), np.zeros((40, 40, 2)), "test")
            window.loaded(volume)
            window.calculated((result, None), dict(mode="current", side="top", engine="test"))
            start = np.array([.2, .3]) @ lattice[:2, :2]
            end = np.array([.7, .8]) @ lattice[:2, :2]
            window.update_profile(start, end)
            fraction = np.linspace([.2, .3], [.7, .8], len(window.profile_values))
            np.testing.assert_allclose(window.profile_values, 3.+fraction[:, 0]*2+fraction[:, 1]*3)
            self.assertAlmostEqual(window.profile_distance[-1], np.linalg.norm(end-start))
            window.close()

    def test_missing_data_produces_gaps_and_reset_closes_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(Path(directory)/"settings.ini")
            volume = Volume(np.diag([10., 10., 30.]), np.array([[.5, .5, .3]]), np.zeros((20, 20, 2)), "test")
            values = np.full((20, 20), 12.)
            values[8:12, :] = np.nan
            window.loaded(volume)
            window.calculated((values, None), dict(mode="current", side="top", engine="test"))
            window.update_profile(np.array([1., 5.]), np.array([8., 5.]))
            self.assertTrue(np.isnan(window.profile_values).any())
            self.assertTrue(np.isfinite(window.profile_values).any())
            window.image.reset_view()
            self.assertTrue(window.profile_panel.isHidden())
            window.close()
