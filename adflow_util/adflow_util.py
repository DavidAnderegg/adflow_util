from tabulate import tabulate
import numpy
import os

# automatically write solution when quiting

# ADFLOW_AVAIL existst so this script can be testet on a windows machine
try:
    from adflow import ADFLOW
    from baseclasses import *
    from mpi4py import MPI
    ADFLOW_AVAIL = True
except ImportError:
    print('Could not import adflow. Only ADFLOW_AVAIL available.')
    ADFLOW_AVAIL = False

# This values can not be iterated on as they are allowed to be arreys
is_arraylike = [
    'coefPol', 'cosCoefFourier', 'sinCoefFourier', 'momentAxis', 'solverOptions', 'evalFuncs'
]


class Error(Exception):
    """
    Format the error message in a box to make it clear this
    was a explicitly raised exception.
    """
    def __init__(self, message):
        msg = '\n+'+'-'*78+'+'+'\n' + '| pyHyp Error: '
        i = 14
        for word in message.split():
            if len(word) + i + 1 > 78: # Finish line and start new one
                msg += ' '*(78-i)+'|\n| ' + word + ' '
                i = 1 + len(word)+1
            else:
                msg += word + ' '
                i += len(word)+1
        msg += ' '*(78-i) + '|\n' + '+'+'-'*78+'+'+'\n'
        print(msg)
        Exception.__init__(self)


class ADFLOW_UTIL:
    def __init__(self, aeroOptions, solverOptions, utilOptions=None):
        self.aeroOptions = aeroOptions
        self.solverOptions = solverOptions
        # self.name = name
        # self.reset_ap = reset_ap

        defaultUtilOptions = {
            # The name that is beeing used for the '.out' file and AP
            "name": 'default',

            # If the AeroPoint should be reseted for every new calculation. This can be usefull in
            # in cases with small changes where the NK solver kicks in before the residual can climb.
            # Because the NK solve is so early, it starts diverging
            "resetAP": False,

            # If ADflow automatically should restart if a restart-file with the exact Name is found.
            # the script looks in the output folder for the restart file
            "autoRestart": True,

            # If ADflow should write the solution if the script is terminated early
            "writeSolOnCancel": True,
        }

        # Get keys for every option
        self.defaultOptionKeys = set(k.lower() for k in defaultUtilOptions)

        # Setup the options
        self.options = {}
        self._checkOptions(utilOptions, defaultUtilOptions)

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
                # reset AP
                if self.options['resetAP']:
                    self.create_aeroProblem()
                self.run_point(n)
        else:
            self.run_point()

    def run_point(self, n=0):
        arrays = self.find_array_aeroOptions()

        # figure out how the name should be
        name = self.options['name']
        if len(arrays) > 0:
            for ar in arrays:
                name += "_{}{}".format(ar, self.aeroOptions[ar][n])
        self.aeroProblem.name = name

        # auto restart solution
        if self.options['autoRestart']:
            self.auto_restart(name)

        # set all AP variables
        if len(arrays) > 0:
            for ar in arrays:
                setattr(self.aeroProblem, ar, self.aeroOptions[ar][n])
        
        # solve
        if ADFLOW_AVAIL:
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
    
    def auto_restart(self, name):
        # only do this if there is nothing about restart in the solver options
        if 'solRestart' in self.solverOptions:
            if not self.aeroOptions['solRestart']:
                return
        
        # if we use a restart file, we have to update the aeropoint anyways
        self.create_aeroProblem()
    
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
        if ADFLOW_AVAIL:
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

        if ADFLOW_AVAIL:
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
        # only create solver if not ADFLOW_AVAIL
        if ADFLOW_AVAIL:
            self.CFDSolver = ADFLOW(options=self.solverOptions)

            # create output folder if it does not exist
            if MPI.COMM_WORLD.Get_rank() == 0:
                if "outputDirectory" in self.solverOptions:
                    out_dir = self.solverOptions['outputDirectory']
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)

    def create_aeroProblem(self):
        kwargs = self.get_ap_kwargs()

        if ADFLOW_AVAIL:
            self.aeroProblem = AeroProblem(name=self.options['name'], **kwargs)
        else:
            self.aeroProblem = type('', (), {})
            self.aeroProblem.name = self.options['name']
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
        self.file = open(self.options['name'] + '.out', 'w')

        self.file.write(self.options['name'] + "\n\n")

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
    
    def _checkOptions(self, options, defaultOptions):
        """
        Check the solver options against the default ones
        and add option iff it is NOT in options
        """
        # Set existing ones
        for key in options:
            self.setOption(key, options[key])

        # Check for the missing ones
        optionKeys = set(k.lower() for k in options)
        for key in defaultOptions:
            if not key.lower() in optionKeys:
                self.setOption(key, defaultOptions[key])
    
    def setOption(self, name, value):
        """
        Set the value of the requested option.
        Parameters
        ----------
        name : str
           Name of option to get. Not case sensitive
        value : varries
           Value to set
        """

        if name.lower() in self.defaultOptionKeys:
            self.options[name.lower()] = value
        else:
            raise Error('setOption: %s is not a valid adflow_util option.'%name)


if __name__ == '__main__':
    aeroOptions = {
            'alpha': [10, 20, 40],
            'reynolds': [1, 1, 1],
            'T': 288,
            'mach': 0.1
        }
    
    au = ADFLOW_UTIL(aeroOptions, {}, 'test')

    au.run()