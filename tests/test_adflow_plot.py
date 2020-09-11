from adflow_util import ADflowData
from adflow_util.adflow_plot import str_to_number
from collections import OrderedDict
import unittest

class util_func_Tests(unittest.TestCase):

    def test_str_to_number_pos_int(self):
        self.assertEqual(str_to_number('1'), 1)
    
    def test_str_to_number_neg_int(self):
        self.assertEqual(str_to_number('-3'), -3)
    
    def test_str_to_number_float(self):
        self.assertEqual(str_to_number('-1.34'), -1.34)
    
    def test_str_to_number_string(self):
        self.assertEqual(str_to_number('test'), 'test')

class ADFLOW_PLOT_Tests(unittest.TestCase):
    def setUp(self):
        self.ap = ADflowData()
        self.test_log = [line.rstrip('\n') for line in open('tests/test.log')]
    

    # parse_adflow_vars
    def test_parse_adflow_vars(self):
        stdout_line = self.test_log[335:337]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes"]
        supposed_dict = OrderedDict()
        for sup in supposed:
            supposed_dict[sup] = []

        self.assertEqual(self.ap.parse_adflow_vars(stdout_line), supposed_dict)
    

    # parse_adflow_iteration
    def test_parse_adflow_iteration(self):
        stdout_line = self.test_log[335:337]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes"]
        supposed_values = [1, 0, 0, 'None', 0.00E+00, 1.00, '----', 0.7320062894350213E+04, 0.1153951480946582E-01, 0.9149551373100052E-01, 0.3701037668832862E+01, 0.6673485782026773E+07]
        supposed_dict = OrderedDict()
        n = 0
        for sup in supposed:
            supposed_dict[sup] = [supposed_values[n]]
            n += 1
        self.ap.adflow_vars = self.ap.parse_adflow_vars(stdout_line)

        self.ap.parse_adflow_iteration(self.test_log[338])
        self.assertEqual(self.ap.adflow_vars, supposed_dict)


    # parse_stdout_line
    def test_parse_stdout_line_adflow_vars(self):
        stdout_line = self.test_log[334:338]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes"]
        supposed_dict = OrderedDict()
        for sup in supposed:
            supposed_dict[sup] = []

        self.ap.stdout_lines = stdout_line
        self.ap.parse_stdout_line()
        self.assertEqual(self.ap.adflow_vars, supposed_dict)
    
    def test_parse_stdout_line_ap_name(self):
        # Check if the name gets parsed
        for n in range(350):
            self.ap.stdout_lines.append(self.test_log[n])
            self.ap.parse_stdout_line()
        
        self.assertEqual(self.ap.ap_name, '010_10.00')


    def test_parse_stdout_line_cleanup(self):
        # simulate first 341 lines of adflow output
        for n in range(341):
            self.ap.stdout_lines.append(self.test_log[n])
            self.ap.parse_stdout_line()        
        # print(self.ap.adflow_vars)

        # simulate last few lines
        for n in range(1311, 1370):
            self.ap.stdout_lines.append(self.test_log[n])
            self.ap.parse_stdout_line()

        self.assertEqual(self.ap.adflow_vars, dict())
        self.assertEqual(self.ap.ap_name, '')
        

