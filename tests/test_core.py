import tempfile
import unittest
from pathlib import Path
import numpy as np
from stm_simulator.core import Volume, read_parchg, simulate

class CoreTests(unittest.TestCase):
    def test_vasp_order_and_spin_block(self):
        text = "test\n1\n2 0 0\n0 2 0\n0 0 10\nH\n1\nDirect\n0.5 0.5 0.5\n\n2 2 2\n0 1 2 3 4 5 6 7\n\n2 2 2\n9 9 9 9 9 9 9 9\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"PARCHG"
            path.write_text(text)
            volume = read_parchg(path)
        self.assertEqual(volume.values[1,0,1], 5)
        self.assertEqual(volume.values[0,1,0], 2)

    def test_top_bottom_and_missing_crossings(self):
        z = np.arange(201)*20/201
        density = np.exp(-np.abs(z-10))[None,None,:]
        volume = Volume(np.diag([2.,2.,20.]), np.array([[.5,.5,.5]]), density, "test")
        top,_ = simulate(volume, threshold=np.exp(-3), side="top")
        bottom,_ = simulate(volume, threshold=np.exp(-3), side="bottom")
        self.assertAlmostEqual(top[0,0],13,places=2)
        self.assertAlmostEqual(bottom[0,0],7,places=2)
        missing,_ = simulate(volume, threshold=2)
        self.assertTrue(np.isnan(missing).all())

    def test_p4vasp_periodic_search_and_interpolation(self):
        from stm_simulator.p4vasp_backend import constant_current
        data = np.array([0., 1., 3., 1., 0., 0.])[None,None,:]
        # p4vasp searchMinPlaneZ chooses the first minimum, index 0.
        # Negative search wraps to 5,4,3,2 and returns an unwrapped height.
        top = constant_current(data, 6., 2., -1)
        bottom = constant_current(data, 6., 2., 1)
        self.assertEqual(top[0,0], -3.5)
        self.assertEqual(bottom[0,0], 1.5)
        self.assertTrue(np.isnan(constant_current(data,6.,4.)).all())

    def test_constant_height(self):
        z = np.arange(40)*.5
        volume = Volume(np.diag([2.,2.,20.]), np.array([[.5,.5,.5]]), z[None,None,:], "linear")
        image,height = simulate(volume,mode="height",height=2.25)
        self.assertEqual(height,12.25)
        self.assertEqual(image[0,0],12.25)

if __name__ == "__main__":
    unittest.main()
