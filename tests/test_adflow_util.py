from adflow_util import ADFLOW_UTIL
import unittest

class ADFLOW_UTIL_Tests(unittest.TestCase):
    def setUp(self):
        aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': [1, 1, 1],
            'T': 288,
            'mach': 0.1
        }

        self.au = ADFLOW_UTIL(aeroOptions, {}, 'test')

    # check_ap_input
    def test_check_ap_input_wrong_arrays(self):
        self.au.aeroOptions = {
            'alpha': [10, 12, 13],
            'reynolds': 3e6,
            'T': [288, 10],
            'mach': 0.1
        }
        
        with self.assertRaises(ValueError):
            self.au.check_ap_input()

    def test_check_ap_input_no_arrays(self):
        self.au.aeroOptions = {
            'alpha': 10,
            'reynolds': 3e6,
            'T': 288,
            'mach': 0.1
        }

        self.assertTrue(self.au.check_ap_input())
    
    def test_check_ap_input_one_array(self):
        self.au.aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': 3e6,
            'T': 288,
            'mach': 0.1
        }

        self.assertTrue(self.au.check_ap_input())

    def test_ckeck_ap_input_right_arrays(self):
        self.au.aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': [3e6, 1,1],
            'T': 288,
            'mach': 0.1
        }

        self.assertTrue(self.au.check_ap_input())
    
    def test_check_ap_input_right_arrays_and_arraylike(self):
        self.au.aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': [3e6, 1,1],
            'T': 288,
            'mach': 0.1, 
            'cosCoefFourier': [1, 2]
        }

        self.assertTrue(self.au.check_ap_input())

    # get_ap_kwargs
    def test_get_ap_kwargs_no_arrays(self):
        self.au.aeroOptions = {
            'alpha': 10,
            'reynolds': 3e6,
            'T': 288,
            'mach': 0.1
        }
        kwargs_dict = self.au.get_ap_kwargs()
        self.assertDictEqual(kwargs_dict, self.au.aeroOptions)
    
    def test_get_ap_kwargs_arrays(self):
        self.au.aeroOptions = {
            'alpha': [10, 20],
            'reynolds': 3e6,
        }
        kwargs_dict = self.au.get_ap_kwargs(0)
        self.assertDictEqual(kwargs_dict, {
            'alpha': 10,
            'reynolds': 3e6,
        })
    
    def test_get_ap_kwargs_arrays_and_arraylike(self):
        self.au.aeroOptions = {
            'alpha': [10, 20],
            'reynolds': 3e6,
            'cosCoefFourier': [1, 2]
        }
        kwargs_dict = self.au.get_ap_kwargs(0)
        self.assertDictEqual(kwargs_dict, {
            'alpha': 10,
            'reynolds': 3e6,
            'cosCoefFourier': [1, 2]
        })
    
    # run_point
    def test_run_point_arrays(self):
        self.au.create_aeroProblem()
        try:
            self.au.run_point(1) 
        except AttributeError:
            pass
        self.assertEqual(self.au.aeroProblem.name, 'test_alpha20_reynolds1')
        self.assertEqual(self.au.aeroProblem.alpha, 20)
    
    def test_run_point_no_arrays(self):
        self.au.aeroOptions = {
            'T': 288,
            'mach': 0.1
        }

        self.au.create_aeroProblem()
        try:
            self.au.run_point(0) 
        except AttributeError:
            pass
        self.assertEqual(self.au.aeroProblem.name, 'test')
        self.assertEqual(self.au.aeroProblem.mach, 0.1)