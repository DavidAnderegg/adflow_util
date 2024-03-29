from tabulate import tabulate
import numpy as np
import os
from os import listdir
from os.path import isfile, join
import copy


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
    'coefPol',
    'cosCoefFourier',
    'sinCoefFourier',
    'momentAxis',
    'solverOptions',
    'evalFuncs'
]


class Error(Exception):
    """
    Format the error message in a box to make it clear this
    was a explicitly raised exception.
    """

    def __init__(self, message):
        msg = '\n+'+'-'*78+'+'+'\n' + '| adflow_util Error: '
        i = 14
        for word in message.split():
            if len(word) + i + 1 > 78:  # Finish line and start new one
                msg += ' '*(78-i)+'|\n| ' + word + ' '
                i = 1 + len(word)+1
            else:
                msg += word + ' '
                i += len(word)+1
        msg += ' '*(78-i) + '|\n' + '+'+'-'*78+'+'+'\n'
        print(msg)
        Exception.__init__(self)


class ADFLOW_UTIL:
    def __init__(self, aeroOptions, solverOptions, options=None):
        self.aeroOptions = aeroOptions
        self.solverOptions = solverOptions

        defaultOptions = {
            # The name that is beeing used for the '.out' file and AP
            "name": 'default',

            # If the AeroPoint should be reseted for every new calculation.
            # This can be usefull in cases with small changes where the NK
            # solver kicks in before the residual can climb cause NK to diverge
            "resetAP": False,

            # If ADflow automatically should restart if a restart-file with the
            # exact Name is found.  the script looks in the output folder for
            # the restart file "disableNumberSolutions" must be set to "True"
            # to use this function
            "autoRestart": False,

            # this automatically disables numbering of solutions. Usually it is
            # okey, because adflow_util picks a unique name by its own
            "disableNumberSolutions": True,

            # This allows to define some familygroupes.  it takes a dict in the
            # from: {"group": ["surface1", "surface2"]} adflow_util basically
            # iterates through this dict and runs "CFDSolver.addFamilyGroup()"
            "surfaceFamilyGroups": None,

            # This allows to execute stuff on the solver itself before and
            # after running. Both need to be in this form:
            # def callbackt(Solver, AeroProblem, n) where:
            #   Solver:         ADflow solver Instance
            #   AeroProblem:    The Aeroproblem instance
            #   n:              Which run it is (0-based)
            "preRunCallback": None,
            "postRunCallback": None,
        }

        # Get keys for every option
        self.defaultOptionKeys = set(k.lower() for k in defaultOptions)

        # Setup the options
        self.options = {}
        self._checkOptions(options, defaultOptions)

        self.CFDSolver = None

        self.funcs_data = []

    def run(self):
        # init stuff
        self.check_ap_input()
        self.create_solver()
        self.create_aeroProblem()

        # run loop
        arrays = self.find_array_aeroOptions()

        # loop through all design points
        if len(arrays) > 0:
            for n in range(len(self.aeroOptions[arrays[0]])):
                # reset AP
                if self.options['resetap']:
                    self.create_aeroProblem()
                self.run_point(n)
        else:
            self.run_point()

    def run_point(self, n=0):
        ap_arrays = self.find_array_aeroOptions()

        # figure out how the name should be
        name = self.options['name']
        if len(ap_arrays) > 0:
            for ar in ap_arrays:
                name += "_{}{}".format(ar, self.aeroOptions[ar][n])
        self.aeroProblem.name = name

        # set all AP variables
        if len(ap_arrays) > 0:
            for ar in ap_arrays:
                setattr(self.aeroProblem, ar, self.aeroOptions[ar][n])

         # auto restart solution
        if self.options['autorestart']:
            temp_solverOptions = self.auto_restart()
            # add solver options to existing onesj
            if 'adflow' not in self.aeroProblem.solverOptions:
                self.aeroProblem.solverOptions = {'adflow': {}}

            for key, value in temp_solverOptions.items():
                self.aeroProblem.solverOptions['adflow'][key] = value

        # solve
        if ADFLOW_AVAIL:
            if self.options["preruncallback"] is not None:
                self.options["preruncallback"](
                        self.CFDSolver, self.aeroProblem, n
                )

            self.CFDSolver(self.aeroProblem)

            if self.options["postruncallback"] is not None:
                self.options["postruncallback"](
                        self.CFDSolver, self.aeroProblem, n
                )

        self.write_summary(n)

    def auto_restart(self):
        # only do this if there is nothing about restart in the solver options
        if 'solRestart' in self.solverOptions:
            if not self.solverOptions['solRestart']:
                return {}

        # disable numbering
        if not self.options['disablenumbersolutions']:
            raise Error(
                '"disableNumberSolutions" must be True when using "autoRestart"')

        temp_solverOptions = dict()

        # look for the restart sol file
        out_dir = self.solverOptions['outputDirectory']
        out_file = os.path.join(out_dir, self.aeroProblem.name + '_vol.cgns')
        if os.path.isfile(out_file):
            temp_solverOptions['restartfile'] = out_file
            # temp_solverOptions['solrestart'] = True

        # make sure some needed adflow-options are saved
        temp_solverOptions['writevolumesolution'] = True
        temp_solverOptions['solutionprecision'] = 'double'

        return temp_solverOptions

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
            header.append(name.replace(self.aeroProblem.name + '_', ''))
            data.append(value)

        # add solver information
        if ADFLOW_AVAIL:
            header.append('totalRes')
            data.append(copy.copy(self.CFDSolver.adflow.iteration.totalrfinal))
            header.append('iterTot')
            data.append(copy.copy(int(self.CFDSolver.adflow.iteration.itertot)))

        # add it to the global data array
        self.funcs_data.append(data)

        data_string = tabulate(
            self.funcs_data, headers=header, floatfmt=".8f") + "\n"

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

            if isinstance(value, (list, np.ndarray)):
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
                    raise Error('All sweep variables must be the same length.')

        return True

    def create_solver(self):
        # disable autmatic numbering of solution
        if self.options['disablenumbersolutions']:
            self.solverOptions['numbersolutions'] = False

        # only create solver if not ADFLOW_AVAIL
        if ADFLOW_AVAIL:
            self.CFDSolver = ADFLOW(options=self.solverOptions)

            # create output folder if it does not exist
            if MPI.COMM_WORLD.Get_rank() == 0:
                if "outputDirectory" in self.solverOptions:
                    out_dir = self.solverOptions['outputDirectory']
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)

            # create the surface families
            if self.options['surfacefamilygroups'] is not None:
                for group_name, surfaces in self.options['surfacefamilygroups'].items():
                    self.CFDSolver.addFamilyGroup(group_name, surfaces)

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

    def write_summary(self, n=0):
        file = open(self.options['name'] + '.out', 'w')

        # write options
        file.write(self.options['name'] + "\n\n")

        # write aero options
        file.write('Aero Options\n')
        aero_data = []
        for name, value in self.aeroOptions.items():
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))
            else:
                value_str = str(value)

            aero_data.append([name, value_str])
        file.write(tabulate(aero_data))

        # write results
        file.write("\n\n\n RESULTS \n")
        funcs = self.eval_funcs()
        file.write(self.create_funcs_table(funcs, n))

        file.close()

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
            raise Error(
                'setOption: %s is not a valid adflow_util option.' % name)


if __name__ == '__main__':
    aeroOptions = {
        'alpha': [10, 20, 40],
        'reynolds': [1, 1, 1],
        'T': 288,
        'mach': 0.1
    }

    au = ADFLOW_UTIL(aeroOptions, {}, 'test')

    au.run()
