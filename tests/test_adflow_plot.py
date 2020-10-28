from adflow_util import ADflowData
from adflow_util.adflow_plot import *
from collections import OrderedDict
import sys
import unittest

class util_func_Tests(unittest.TestCase):

    def test_str_to_number_pos_int(self):
        self.assertEqual(str2number('1'), 1)
    
    def test_str_to_number_neg_int(self):
        self.assertEqual(str2number('-3'), -3)
    
    def test_str_to_number_float(self):
        self.assertEqual(str2number('-1.34'), -1.34)
    
    def test_str_to_number_string(self):
        self.assertEqual(str2number('test'), 'test')

class ScreenBuffer_Tests(unittest.TestCase):
    # def setUp(self):
    #     self.SB = ScreenBuffer()

    def test_redraw_true(self):
        sb = ScreenBuffer()
        # change an attribute to a new name -> redraw should be true
        sb.scr_rows = 10
        sb_return = sb.redraw
        self.assertTrue(sb_return)

        # after accessing redraw, it should be false
        self.assertFalse(sb.redraw)
    
    def test_redraw_message_true(self):
        sb = ScreenBuffer()
        message = Message()
        sb.message = message

        self.assertTrue(sb.redraw)
        self.assertFalse(sb.redraw)
        
        message.set('test', Message.typeInfo)
        
        self.assertTrue(sb.redraw)

        # message.set('test2', Message.typeInfo)
        # sb.message = message
        message.set('test2', Message.typeError)
        self.assertTrue(sb.redraw)
    
    def test_redraw_command_true(self):
        sb = ScreenBuffer()

        sb.redraw
        self.assertFalse(sb.redraw)

        command = CommandBuffer()
        command.add('d')
        sb.command = command
        self.assertTrue(sb.redraw)

        command.add('d')
        self.assertTrue(sb.redraw)
    
    def test__eq__True(self):
        sb1 = ScreenBuffer()
        sb2 = ScreenBuffer()

        self.assertTrue(sb1 == sb2)
    
    def test__eq__False(self):
        sb1 = ScreenBuffer()
        sb2 = ScreenBuffer()
        sb2.scr_cols = 10

        # make sure, ever object ist tested against the other
        self.assertFalse(sb2 == sb1)
        self.assertFalse(sb1 == sb2)

class BaseBuffer_Tests(unittest.TestCase):
    def test__eq__True(self):
        b1 = BaseBuffer()
        b2 = BaseBuffer()

        # make sure, ever object ist tested against the other
        self.assertTrue(b1 == b2)
        self.assertTrue(b2 == b1)
    
    def test__eq__False(self):
        b1 = BaseBuffer()
        b2 = BaseBuffer()
        b2.a = 4

        # make sure, ever object ist tested against the other
        self.assertFalse(b1 == b2)
        self.assertFalse(b2 == b1)
    
    def test__has_attr_changed(self):
        b = BaseBuffer()
        b.a = 1

        self.assertTrue(b._has_attr_changed())
        self.assertFalse(b._has_attr_changed())

        b.a = 2
        self.assertTrue(b._has_attr_changed())



class ADFLOW_PLOT_Tests(unittest.TestCase):
    def setUp(self):
        self.ap = ADflowData(args=['-i', 'test.py'])
        self.test_log = [line.rstrip('\n') for line in open('tests/test.log')]
    

    # parse_adflow_vars
    def test_parse_adflow_vars(self):
        stdout_line = self.test_log[335:337]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes", 'relRes']
        supposed_dict = OrderedDict()
        for sup in supposed:
            supposed_dict[sup] = []

        self.assertEqual(self.ap.parse_adflow_var_names(stdout_line), supposed_dict)
    

    # parse_adflow_iteration
    def test_parse_adflow_iteration(self):
        stdout_line = self.test_log[335:337]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes", 'relRes']
        supposed_values = [1, 0, 0, 'None', 0.00E+00, 1.00, '----', 0.7320062894350213E+04, 0.1153951480946582E-01, 0.9149551373100052E-01, 0.3701037668832862E+01, 0.6673485782026773E+07, 0.0]
        supposed_dict = OrderedDict()
        n = 0
        for sup in supposed:
            supposed_dict[sup] = [supposed_values[n]]
            n += 1
        self.ap.adflow_vars = self.ap.parse_adflow_var_names(stdout_line)
        self.ap.adflow_vars_raw = self.ap.parse_adflow_var_names(stdout_line)

        self.ap.parse_adflow_var_values(self.test_log[338])
        self.assertEqual(self.ap.adflow_vars_raw, supposed_dict)


    # parse_stdout_line
    def test_parse_stdout_line_adflow_vars(self):
        stdout_line = self.test_log[334:338]
        supposed = ["Grid_level", "Iter", "Iter_Tot", "Iter_Type", "CFL", "Step", "Lin_Res", "Res_rho", "Res_nuturb", "C_lift", "C_drag", "totalRes", 'relRes']
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

    def test_parse_stdout_line_total_call_time(self):
        self.ap.stdout_lines = self.test_log[1300:1354]
        # print(self.ap.stdout_lines[-1])
        self.ap.has_finished = True
        self.ap.parse_stdout_line()

        self.assertEqual(self.ap.has_finished_total_call_time, 582.610)
    
    def test_parse_stdout_line_total_func_time(self):
        self.ap.stdout_lines = self.test_log[1300:1365]
        # print(self.ap.stdout_lines[-1])
        self.ap.has_finished = True
        self.ap.parse_stdout_line()

        self.assertEqual(self.ap.has_finished_total_func_time, 0.003)

        

if __name__ == '__main__':
    unittest.main()