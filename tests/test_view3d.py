import unittest
import numpy as np
from PyQt6.QtWidgets import QApplication
from stm_simulator.core import Volume
from stm_simulator.colors import ColorScale
from stm_simulator.view3d import SurfaceView


class CoordinateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_atoms_and_surface_share_unmodified_angstrom_frame(self):
        volume = Volume(np.array([[12., 0, 0], [3., 10., 0], [0, 0, 24.]]),
                        np.array([[.2, .3, .4], [.8, .7, .4]]), np.zeros((2, 2, 2)), "test")
        result = np.array([[-4., -3.], [-2., -1.]])
        view = SurfaceView()
        scale = ColorScale(-4., -1.)
        for plane in (None, 12.6):
            view.set_data(result, volume, plane, scale)
            np.testing.assert_array_equal(view.atom_positions, volume.positions @ volume.lattice)
            expected = result.ravel() if plane is None else np.full(4, plane)
            np.testing.assert_array_equal(view.surface_vertices[:, 2], expected)
            self.assertTrue(view.surface_item.transform().isIdentity())
            self.assertTrue(view.atom_artist.transform().isIdentity())
        view.close()

    def test_missing_vertices_do_not_form_faces_and_camera_is_preserved(self):
        volume = Volume(np.diag([12., 12., 24.]), np.array([[.5, .5, .4]]), np.zeros((2, 2, 2)), "test")
        result = np.array([[1., 2., 3.], [2., np.nan, 4.], [3., 4., 5.]])
        view = SurfaceView()
        view.set_data(result, volume, None, ColorScale(1., 5.))
        mesh = view.surface_item.opts['meshdata']
        self.assertFalse(np.any(mesh.faces() == 4))
        view.orbit(15, 5)
        camera = view.cameraParams()
        view.set_data(result, volume, None, ColorScale(1., 5., "灰度"))
        self.assertEqual(view.cameraParams(), camera)
        view.close()
