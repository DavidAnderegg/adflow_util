from tabulate import tabulate
import numpy
import os

TESTING = False
try:
    from adflow import ADFLOW
    from baseclasses import *
    from mpi4py import MPI
except ImportError:
    print('Could not import adflow. Only testing available.')
    TESTING = True

# This values can not be iterated on as they are allowed to be arreys
is_arraylike = [
    'coefPol', 'cosCoefFourier', 'sinCoefFourier', 'momentAxis', 'solverOptions', 'evalFuncs'
]

class ADFLOW_UTIL:
    def __init__(self, aeroOptions, solverOptions, name='default'):
        self.aeroOptions = aeroOptions
        self.solverOptions = solverOptions
        self.name = name

    
    def run(self):
        # init stuff
        self.check_ap_input()
        self.create_solver()
        self.create_aeroProblem()
        self.write_header()

        # run loop
        arrays = self.find_array_aeroOptions()

        # loop through all design points
        if len(arrays) > 0:
            for n in range(len(self.aeroOptions[arrays[0]])):
                self.run_point(n)
        else:
            self.run_point()

    def run_point(self, n=0):
        arrays = self.find_array_aeroOptions()

        # figure out how the name should be
        name = self.name
        if len(arrays) > 0:
            for ar in arrays:
                name += "_{}{}".format(ar, self.aeroOptions[ar][n])
        self.aeroProblem.name = name

        # set all AP variables
        if len(arrays) > 0:
            for ar in arrays:
                setattr(self.aeroProblem, ar, self.aeroOptions[ar][n])
        
        # solve
        if not TESTING:
            self.CFDSolver(self.aeroProblem)

        # eval Funcs
        funcs = self.eval_funcs()

        # write funcs table data to file
        if n == 0:
            self.file.write("\n\n\n RESULTS \n")
        self.file.write(self.create_funcs_table(funcs, n))

        # flush file after one iteration
        try:
            self.file.flush()
        except AttributeError:
            pass
    
    def create_funcs_table(self, funcs, n=0):
        header = []
        data = []

        # add array variables
        arrays = self.find_array_aeroOptions()
        for ar in arrays:
            header.append(ar)
            data.append(self.aeroOptions[ar][n])

        # add result
        for name, value in funcs.items():
            header.append(name.split('_')[-1])
            data.append(value)

        # add solver information
        header.append('totalRes')
        data.append(self.CFDSolver.adflow.iteration.totalrfinal)
        header.append('iterTot')
        data.append(int(self.CFDSolver.adflow.iteration.itertot))
        
        # only write header if it is the first line
        data_string = tabulate([data], headers=header, floatfmt=".8f") + "\n"
        if n > 0: # strip off header if it is not the first run (this is done for alignment purposes)
            data_string = data_string.split("\n",2)[2]
        
        return data_string

    def eval_funcs(self):
        funcs = {}

        if not TESTING:
            self.CFDSolver.evalFunctions(self.aeroProblem, funcs)
        else:
            funcs = {
                self.aeroProblem.name + '_cl': 0.1,
                self.aeroProblem.name + '_cd': 0.005
            }
        
        return funcs

    def find_array_aeroOptions(self):
        arrays = []
        for name, value in self.aeroOptions.items():
            if name in is_arraylike:
                continue

            if isinstance(value, list):
                arrays.append(name)
        return arrays

    def check_ap_input(self):
        # if one or more are arrays, all arrays should be the same legth

        # find all arrays
        arrays = self.find_array_aeroOptions()
        
        # if there are more arrays, check if they are the same length
        if len(arrays) > 1:
            a_length = len(self.aeroOptions[arrays[0]])
            for name in arrays:
                # check if they are the same length, if they can be array_like, it doesnt matter
                if a_length != len(self.aeroOptions[name]) and not name in is_arraylike:
                    raise ValueError('All Arrays must be the same length.')

        return True

    def create_solver(self):
        # only create solver if not testing
        if not TESTING:
            self.CFDSolver = ADFLOW(options=self.solverOptions)

            # create output folder if it does not exist
            if "outputDirectory" in self.solverOptions:
                out_dir = self.solverOptions['outputDirectory']
                if not os.path.exists(out_dir):
                    os.makedirs(out_dir)

    
    def create_aeroProblem(self):
        kwargs = self.get_ap_kwargs()

        if not TESTING:
            self.aeroProblem = AeroProblem(name=self.name, **kwargs)
        else:
            self.aeroProblem = type('', (), {})
            self.aeroProblem.name = self.name
            for name, value in kwargs.items():
                setattr(self.aeroProblem, name, value)

    def get_ap_kwargs(self, n=0):
        kwargs = {}
        for name, value in self.aeroOptions.items():
            # if not name in iteratable:
            #     continue

            if isinstance(value, list) and not name in is_arraylike:
                value_single = value[n]
            else:
                value_single = value
            
            kwargs[name] = value_single
        
        return kwargs

    def write_header(self):
        self.file = open(self.name + '.out', 'w')

        self.file.write(self.name + "\n\n")

        # write aero options
        self.file.write('Aero Options\n')
        aero_data = []
        for name, value in self.aeroOptions.items():
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))
            else:
                value_str = str(value)

            aero_data.append([name, value_str])
        self.file.write(tabulate(aero_data))


    def __del__(self):
        try:
            self.file.close()
        except AttributeError:
            pass


if __name__ == '__main__':
    aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': [1, 1, 1],
            'T': 288,
            'mach': 0.1
        }
    
    au = ADFLOW_UTIL(aeroOptions, {}, 'test')

    au.run()