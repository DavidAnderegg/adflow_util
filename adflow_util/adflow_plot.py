import argparse
import os
import subprocess
import shlex
import plotext.plot as plx



class ADFLOW_PLOT():
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Allows to plot ADflow output on the command line')
        self.init_vars()

    def init_vars(self):
        # this is not in __init__, so it can be called to reset
        self.stdout_lines = []
        self.adflow_vars = {}

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
        rc = process.poll()
        return rc
    
    def parse_args(self):
        # input file
        self.parser.add_argument("-i", dest="inputfile", required=True,
            help="The ADflow script to run.")

        self.args = self.parser.parse_args()

    def parse_stdout_line(self):
        # print(self.stdout_lines[-1])

        # figure out if the line is a var description 
        # (only do this if it hasn't been done allready)
        if not self.adflow_vars:
            var_desc_string = '#---------'
            if (self.stdout_lines[-1][0:10] == var_desc_string and 
               self.stdout_lines[-4][0:10] == var_desc_string):
               self.adflow_vars = self.parse_adflow_vars(self.stdout_lines[-3:-2])
    
    def parse_adflow_vars(self, stdout_lines):
        # check if the line is var line

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
        
        return adflow_vars
    

if __name__ == '__main__':
    ap = ADFLOW_PLOT()
    ap.run()