import argparse
import os
import subprocess
import shlex
import plotext.plot as plx
from collections import OrderedDict

# todo:
# - clean up stuff after adflow has finished
# - implement mpi support

def str_to_number(s):
    # converts a string to int or float if possible
    # if it is neither, it returns the string itself

    # check fo int
    is_int = False
    if s[0] in ('-', '+'):
        is_int = s[1:].isdigit()
    else:
        is_int = s.isdigit()
    
    if is_int:
        return int(s)
    
    # check for float
    try:
        return float(s)
    except ValueError:
        return s


class ADFLOW_PLOT():
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Allows to plot ADflow output on the command line')
        self.init_vars()

    def init_vars(self):
        # this is not in __init__, so it can be called to reset
        self.stdout_lines = []
        self.adflow_vars = OrderedDict()
        self.ap_name = ''

    def run(self):
        # init stuff
        self.parse_args()

        # run adflow script
        command = 'python {}'.format(self.args.inputfile)
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        while True:
            self.stdout_lines.append(process.stdout.readline().decode("utf-8").rstrip())
            self.parse_stdout_line()
            if self.stdout_lines[-1] == '':
                break

            # print adflowline for testing
            print('test {}'.format(self.stdout_lines[-1]))
        rc = process.poll()
        return rc
    
    def parse_args(self):
        # input file
        self.parser.add_argument("-i", dest="inputfile", required=True,
            help="The ADflow script to run.")

        self.args = self.parser.parse_args()

    def parse_stdout_line(self):
        # parse every stdout line and do the appropriate action

        # if the AeroProblem Name is not set, do it
        if self.ap_name == '':
            if self.stdout_lines[-1][0:29] == '|  Switching to Aero Problem:':
                self.ap_name = self.stdout_lines[-1][29:-2].strip()

        # figure out if the line is a var description 
        # (only do this if it hasn't been done allready)
        if len(self.adflow_vars) == 0:
            if len(self.stdout_lines) > 3:
                var_desc_string = '#---------'
                if (self.stdout_lines[-1][0:10] == var_desc_string and 
                    self.stdout_lines[-4][0:10] == var_desc_string):
                    self.adflow_vars = self.parse_adflow_vars(self.stdout_lines[-3:-1])
        else:
            # figure out if this is an iteration ouput 
            # (only do this if adflow_vars allready have been parsed)
            if self.stdout_lines[-1][0:5] == '     ':
                self.parse_adflow_iteration(self.stdout_lines[-1])

            # figure out if the end has been reached
            # only do this adflow_vars has allready been parsed)
            if self.stdout_lines[-1] == '#':
                # save stuff

                # reset stuff so it is ready for the next run
                self.init_vars()

    
    def parse_adflow_iteration(self, stdout_lines):
        bits = stdout_lines.split()

        n = 0
        for adflow_var in self.adflow_vars:
            self.adflow_vars[adflow_var].append(str_to_number(bits[n]))
            n += 1
    
    def parse_adflow_vars(self, stdout_lines):
        # split all lines
        var_bits = []
        for line in stdout_lines:
            var_bits.append(line[1:-1].split('|')) # split and remove first '#'

        # create variables from lines
        adflow_vars = []
        n = 0
        for line in var_bits:
            m = 0
            for bit in line:
                bit_stripped = bit.strip()
                bit_stripped = bit_stripped.replace(' ', '_')
                if n == 0:
                    adflow_vars.append(bit_stripped)
                else:
                    if bit_stripped != '':
                        adflow_vars[m] += '_' + bit_stripped
                m += 1
            n += 1
        
        # convert it to a ordered dict that is empty
        adflow_vars_dict = OrderedDict()
        for adflow_var in adflow_vars:
            adflow_vars_dict[adflow_var] = []
        
        return adflow_vars_dict

def adflow_plot():
    ap = ADFLOW_PLOT()
    ap.run()
    

if __name__ == '__main__':
    ap = ADFLOW_PLOT()
    ap.run()