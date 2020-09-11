import argparse
import os
import subprocess
import shlex
import adflow_util.plot as plx
import curses
from collections import OrderedDict
from time import sleep
import threading

# todo:
# - clean up stuff after adflow has finished
# - implement mpi support
# - limit adflow output size

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


class Buffer():
    def __init__(self):
        self._active = ''
        self._history = []
        self._has_new_commited = False
    
    def add(self, c):         
        self._active += c
    
    def remove(self, n=1):
        if len(self._active) >= n:
            for m in range(n):
                self._active = self._active[:-1]

    def commit(self):
        self._history.append(self._active)
        self._has_new_commited = True
        self._active = ''
    
    def get_commited(self, n=0):
        if len(self._history) == 0:
            return None
        self._has_new_commited = False
        return self._history[-(n+1)]

    def get_active(self):
        return self._active



class ADFlowPlot():
    """
    This Class provides the curse window and plots the data parsed by ADflowData
    """

    def __init__(self, adData):
        self._screen = None
        self._buffer = Buffer()
        self._adData = adData

        # user changable vars
        self._n_adflowout = 15
        self._plot_vars = ['Res_rho']
        self._n_plot_iterations = 10


        # init stuff
        self._screen = curses.initscr()
        curses.noecho()
        self._screen.keypad(True)
        self._screen.nodelay(True)
    
    def __del__(self):
        self.cleanup()
    
    def cleanup(self):
        # shudown stuff
        curses.nocbreak()
        self._screen.keypad(False)
        curses.echo()
        curses.endwin()

    def refresh(self):
        try: 
            if self._buffer._has_new_commited:
                self.parse_new_command()

            num_rows, num_cols = self._screen.getmaxyx()
            self._screen.clear()

            # print console output at top
            for n in range(self._n_adflowout, 0, -1):
                if len(self._adData.stdout_lines) >= n:
                    stdout_line = self._adData.stdout_lines[-n]#[0:num_cols]
                    # stdout_line = 'asdf'
                else:
                    stdout_line = ''
                self._screen.addstr(self._n_adflowout - n, 0, stdout_line)
            
            # plot vars
            # if len(self._adData.adflow_vars) > 0:
            self.plot(num_cols-4, num_rows - self._n_adflowout - 3)
            # self._screen.addstr(self._n_adflowout, 0, plot_str)

            # print command line at bottom:
            self._screen.addstr(num_rows-1, 0, 'Command: ' + self._buffer.get_active())

            # refresh and key input
            self._screen.refresh()
            self.parse_input()
        except:
            self.cleanup()
            raise
    
    def plot(self, cols, rows):
        x = []
        if len(self._adData.adflow_vars) > 0:
            iterlist = self._adData.adflow_vars['Iter']
            x = iterlist[len(iterlist) - min(len(iterlist), self._n_plot_iterations):-1]
        if len(x) >= 2: 
            plx._vars.__init__()
            plx._vars.cols_term = cols
            plx._vars.rows_term = rows

            for plot_var in self._plot_vars:
                y = self._adData.adflow_vars[plot_var]

                # x = [1, 2, 3]
                # y = [1, 2, 3]

                plx.plot(x,y)
        
            # plx.set_cols(cols)
            # plx.set_rows(rows)
            # plx.set_xlim([min(len(x), self._n_plot_iterations), x[-1]])
            # plx.set_ylim([min(y), max(y)])
            # plx.set_spacing([10, 5])
            plx._set_xlim()
            plx._set_ylim()
            plx._set_grid()
            plx._add_yaxis()
            plx._add_xaxis()
            # plx._set_canvas()
            # plx._add_equations()

            lines = []
            for r in range(len(plx._vars.grid) -1, -1, -1):
                lines.append(plx._remove_color("".join(plx._vars.grid[r])))

            len_lines = len(lines)
            for n in range(len_lines):
                self._screen.addstr(
                    self._n_adflowout + n, 0, 
                    lines[n])

            # canvas = plx._get_canvas()
            # if plx._vars.no_color:
            # canvas=plx._remove_color(canvas)
            # f = open('test.txt', 'w')
            # f.write(canvas)
            # f.close()
        # else:
        #     canvas = ''
        
        # return canvas
    
    def parse_input(self):
        try: 
            c = self._screen.getch()
            if c == curses.ERR:
                return
            
            if isinstance(c, int):
                switcher = {
                    curses.KEY_BACKSPACE:   self._buffer.remove,
                    8:                      self._buffer.remove,

                    curses.KEY_ENTER:       self._buffer.commit,
                    10:                     self._buffer.commit,
                }
                func = switcher.get(c)
                if func is not None: func()
            # if curses.ascii.isprint(c):
            #     self._buffer.add(chr(c))
                if c > 31 and c < 127:
                    self._buffer.add(chr(c))
        except curses.error:
            pass
    
    def parse_new_command(self):
        command = self._buffer.get_commited()
        switcher = {
            'quit': self.cmd_quit,
            'q': self.cmd_quit,
        }
        func = switcher.get(command)
        if func is not None: func()

    def cmd_quit(self):
        self._adData.exit = True
        

class ADflowData():
    """
    This class runs ADFlow and processes the data to an array
    """
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Allows to plot ADflow output on the command line')
        self.init_vars()
        self.exit = False
        self._adPlot = ADFlowPlot(self)

    def init_vars(self):
        # this is not in __init__, so it can be called to reset
        self.stdout_lines = []
        self.adflow_vars = OrderedDict()
        self.ap_name = ''

    def run(self):
        # init stuff
        self.parse_args()

        # run adflow script
        command = self.create_adflow_command()
        # print(command)
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        while True:
            line = process.stdout.readline()
            # if line == '':
            #     break

            if self.exit:
                break

            self.stdout_lines.append(line.decode("utf-8").rstrip())
            self.parse_stdout_line()

            self._adPlot.refresh()

        self._adPlot.cleanup()
        rc = process.poll()
        return rc
    
    def create_adflow_command(self):
        command = ''
        if self.args.mpi_np is not None:
            command += '{} -np {} '.format(self.args.mpi_command, self.args.mpi_np)
        command += 'python {}'.format(self.args.inputfile)

        return command
    
    def parse_args(self):
        # input file
        self.parser.add_argument("-i", dest="inputfile", required=True,
        # self.parser.add_argument("-i", dest="inputfile", required=False,
            help="The ADflow script to run.")
        
        self.parser.add_argument("-mpi", dest="mpi_command", default="mpirun", 
            help="The mpi command to use")
        
        self.parser.add_argument("-np", dest="mpi_np", 
            help="Number of corse to use by mpi")

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
    ap = ADflowData()
    ap.run()

    # aPlot = ADFlowPlot()
    # aPlot.run()
    

# if __name__ == '__main__':
#     aPlot = ADFlowPlot()
#     aPlot.run()