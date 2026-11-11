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

    def test_missing_data_gaps_and_reset_preserves_profile(self):
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
            self.assertFalse(window.profile_panel.isHidden())
            window.image.clear_line()
            self.assertTrue(window.profile_panel.isHidden())
            window.close()

    def test_selection_coordinates_and_transparent_profile_export(self):
        from stm_simulator.profile_view import ProfilePlot
        from PyQt6.QtCore import QPointF, Qt
        plot = ProfilePlot()
        plot.resize(600, 220)
        plot.show()
        plot.plot([0., 1., 2.], [2., 3., 2.])
        plot.set_samples(np.array([0., 1., 2.]), np.array([2., 3., 2.]))
        self.app.processEvents()
        plot.autoRange()
        position = plot.plotItem.vb.mapViewToScene(QPointF(1., 3.))
        class Click:
            def button(self): return Qt.MouseButton.LeftButton
            def scenePos(self): return position
        plot.pick_point(Click())
        self.assertEqual(plot.selection, 1)
        self.assertIn("3", plot.annotation.toPlainText())
        texts = []
        plot.position_changed.connect(texts.append)
        plot.track_mouse(position)
        self.assertTrue(texts[-1].startswith("x  1"))
        plot.set_coordinates_visible(False)
        self.assertEqual(texts[-1], "")
        image = plot.transparent_image()
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        plot.close()

    def test_projected_atom_depth_uses_selected_surface_and_keeps_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(Path(directory)/"settings.ini")
            volume = Volume(np.diag([10., 10., 30.]),
                            np.array([[.2, .2, .2], [.4, .4, .3], [.6, .6, .4]]),
                            np.zeros((20, 20, 2)), "test", ("Cr", "Sb", "Cr"))
            window.loaded(volume)
            window.atom_depth_slider.setValue(300)
            np.testing.assert_allclose(window.image.atom_depths()[0], [6., 3., 0.])
            np.testing.assert_array_equal(window.image.atom_opacities(), [0., 1., 1.])
            window.side.setCurrentIndex(1)
            np.testing.assert_array_equal(window.image.atom_opacities(), [1., 1., 0.])
            window.atom_depth_slider.setValue(window.atom_depth_slider.maximum())
            np.testing.assert_array_equal(window.image.atom_opacities(), [1., 1., 1.])
            window.close()

    def test_left_atom_toggle_controls_existing_3d_cutoff_and_survives_redraw(self):
        with tempfile.TemporaryDirectory() as directory:
            window = App(Path(directory)/"settings.ini")
            volume = Volume(np.diag([10., 10., 30.]),
                            np.array([[.2, .2, .2], [.4, .4, .3], [.6, .6, .4]]),
                            np.zeros((20, 20, 2)), "test", ("Cr", "Sb", "Cr"))
            window.loaded(volume)
            window.atom_depth_slider.setValue(300)
            self.assertEqual(window.surface.cutoff_items, [])
            window.projection_atoms_toggle.setChecked(True)
            np.testing.assert_array_equal(window.image.atom_opacities(), [0., 1., 1.])
            np.testing.assert_array_equal(window.surface.projection_alphas, [.2, 1., 1.])
            self.assertAlmostEqual(window.surface.cutoff_z, 9.)
            self.assertEqual(len(window.surface.cutoff_items), 2)
            window.calculated((np.full((20, 20), 14.), None), dict(mode="current", side="top", engine="test"))
            self.assertEqual(len(window.surface.cutoff_items), 2)
            window.side.setCurrentIndex(1)
            np.testing.assert_array_equal(window.surface.projection_alphas, [1., 1., .2])
            window.projection_atoms_toggle.setChecked(False)
            self.assertEqual(window.surface.cutoff_items, [])
            np.testing.assert_array_equal(window.surface.atom_artist.colors[:, 3], [1., 1., 1.])
            window.close()
