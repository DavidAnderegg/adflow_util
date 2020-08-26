from adflow_util import ADFLOW_PLOT
import unittest

class ADFLOW_PLOT_Tests(unittest.TestCase):
    def setUp(self):
        self.ap = ADFLOW_PLOT()

        # self.test_log = [line.rstrip('\n') for line in open('test.log')]

    # parse_adflow_vars
    def test_parse_adflow_vars(self):
        stdout_lines = [
            # "#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------",
            "#  Grid  | Iter | Iter |  Iter  |   CFL   | Step | Lin  |        Res rho         |       Res nuturb       |         C_lift         |        C_drag          |        totalRes        |",
            "#  level |      | Tot  |  Type  |         |      | Res  |                        |                        |                        |                        |                        |",
            # "#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"
        ]

        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes"]

        self.assertEqual(self.ap.parse_adflow_vars(stdout_lines), supposed)
    
    # parse_stdout_line
    # def test_parse_stdout_line(self):