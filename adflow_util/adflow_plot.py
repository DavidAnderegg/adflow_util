import argparse
import os
import subprocess
import shlex
import adflow_util.plot as plx
import curses
# import culour
from collections import OrderedDict
import time
import threading
import sys
import queue

# todo:
# - clean up stuff after adflow has finished
# - implement mpi support
# - limit adflow output size
# - create help text
# - logarithmic scale
# - label curves
# - add color

ON_POSIX = 'posix' in sys.builtin_module_names

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

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


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


class Message():
    typeNone = 0
    typeError = 1
    typeSuccess = 2
    typeInfo = 3

    prefix = {
        typeNone: '',
        typeError: 'Error',
        typeSuccess: 'Success',
        typeInfo: 'Info'
    }
    def __init__(self):
        self._text = ''
        self._type = self.typeNone

    def set(self, text, t=None):
        if t == None: t == self.typeNone
        self._text = text
        self._type = t

    def text(self):
        if self._type == self.typeNone:
            return ""
        return "{}: {}".format(self.prefix[self._type], self._text)


class ADFlowPlot():
    """
    This Class provides the curse window and plots the data parsed by ADflowData
    """

    def __init__(self):
        self._screen = None
        self._buffer = Buffer()
        self._adData = ADflowData()
        self._message = Message()
        self._markers = ['*', 'x', 'v', 'o']

        # user changable vars
        self._exit = False
        self._n_adflowout = 15
        self._plot_vars = {'C_lift': '*'}
        self._n_plot_iterations = 50
        self._ymin = None
        self._ymax = None


        # init stuff
        self._screen = curses.initscr()
        curses.start_color()
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
    
    def run(self):
        self._adData.start_adflow()
        while not self._exit:
            self.redraw()

            # sleep, but only if queue is empty
            t0 = time.time()
            while (time.time() - t0) < 1/60:
                if self._adData.iter_adflow():
                    break

    def redraw(self):
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

            # message line:
            self._screen.addstr(num_rows-2, 0, self._message.text())

            # print command line at bottom:
            self._screen.addstr(num_rows-1, 0, 'Command: ' + self._buffer.get_active())

            # refresh and key input
            self._screen.refresh()
            self.parse_input()
        except:
            self.cleanup()
            raise
    
    def plot(self, cols, rows):
        if len(self._plot_vars) == 0:
            return

        if len(self._adData.adflow_vars) == 0:
            return

        x = self._adData.adflow_vars['Iter']
        if len(x) < 2:
            return

        # reset plot variables
        plx._vars.__init__()
        plx._vars.cols_term = cols
        plx._vars.rows_term = rows
        ylim = None

        # only show parts of iteration history
        min_i = 0
        if self._n_plot_iterations > 0:
            min_i =  len(x) - min(len(x), self._n_plot_iterations)
        elif self._n_plot_iterations < 0:
            min_i = min(len(x) - 2, -self._n_plot_iterations)
            
        

        # add plot data
        if len(self._adData.adflow_vars) > 0:
            for key, marker in self._plot_vars.items():
                y = self._adData.adflow_vars[key]
                plx.plot(x,y, line_marker=marker)

                if ylim is None and len(y) >= 2:
                    ylim = [
                        min(y[min_i:]), 
                        max(y[min_i:])]
                else:
                    ylim = [min(min(y[min_i:]), ylim[0]),
                            max(max(y[min_i:]), ylim[1])]
        
        # set default min/max
        if self._ymin is not None:
            ylim[0] = self._ymin
        if self._ymax is not None:
            ylim[1] = self._ymax
    
        # prepare plot
        plx.set_xlim([x[min_i], x[-1]])
        plx.set_ylim(ylim)
        plx._set_xlim()
        plx._set_ylim()
        plx._set_grid()
        plx._add_yaxis()
        plx._add_xaxis()

        # draw plot
        lines = []
        for r in range(len(plx._vars.grid) -1, -1, -1):
            lines.append(plx._remove_color("".join(plx._vars.grid[r])))

        len_lines = len(lines)
        for n in range(len_lines):
            self._screen.addstr(
                self._n_adflowout + n, 0, 
                lines[n])
    
    def parse_input(self):
        try: 
            c = self._screen.getch()
            if c == curses.ERR:
                return
            
            if isinstance(c, int):
                
                switcher = {
                    curses.KEY_BACKSPACE:   self._buffer.remove,
                    8:                      self._buffer.remove,
                    127:                    self._buffer.remove,

                    curses.KEY_ENTER:       self._buffer.commit,
                    10:                     self._buffer.commit,
                }
                func = switcher.get(c)
                if func is not None: func()
                if c > 31 and c < 127:
                    self._buffer.add(chr(c))
        except curses.error:
            pass
    
    def parse_new_command(self):
        temp = self._buffer.get_commited().split()
        command = temp[0]
        args = temp[1:]

        switcher = {
            'quit': self.cmd_quit,
            'q': self.cmd_quit,

            'add': self.cmd_add_var,
            'a': self.cmd_add_var,

            'remove': self.cmd_remove_var,
            'r': self.cmd_remove_var,

            'iterations': self.cmd_iterations,
            'i': self.cmd_iterations,

            'ymin': self.cmd_ymin,

            'ymax': self.cmd_ymax,

            'hlog': self.cmd_hlog,
        }
        func = switcher.get(command)
        if func is not None: func(args)

    def cmd_quit(self, args):
        self._exit = True
    
    def cmd_add_var(self, args):
        # check how many values there are
        if len(args) == 0:
            self._message.set('No Variable defined', Message.typeError)
            return
        
        value = args[0]
        if len(args) == 2:
            marker = args[1]
        else:
            marker = self._markers[len(self._plot_vars) % len(self._markers)]

        # check if value exists
        if not value in self._adData.adflow_vars:
            self._message.set('"{}" ist not a Variable.'.format(value), Message.typeError)
            return
        
        # check if value hast not been added allready
        if value in self._plot_vars:
            self._message.set('"{}" is allready plotting.'.format(value), Message.typeError)
        
        # check if value is plottable
        not_plottable = ['Iter_Type']
        if value in not_plottable:
            self._message.set('"{}" can not be plotet.'.format(value), Message.typeError)
            return

        self._plot_vars[value] = marker

        self._message.set('"{}" now plotting as "{}".'.format(value, marker), Message.typeSuccess)
    
    def cmd_remove_var(self, args):
        # check if there is an arg
        if len(args) == 0:
            self._message.set('No variable named.', Message.typeError)
            return
        
        value = args[0]

        # check if the var is getting plotted
        if value not in self._plot_vars:
            self._message.set('"{}" is not active.'.format(value), Message.typeError)
            return
        
        # remove key
        del self._plot_vars[value]
        self._message.set('"{}" has been removed.'.format(value), Message.typeSuccess)

    def cmd_iterations(self, args):
        # check if there is an arg
        if len(args) == 0:
            value = '0'
        else:
            value = args[0]
        
        # check fo int
        is_int = False
        if value[0] in ('-', '+'):
            is_int = value[1:].isdigit()
        else:
            is_int = value.isdigit()
        
        if not is_int:
            self._message.set('Iterations count must be an integer.', Message.typeError)
            return

        

        # if value < 0:
        #     self._message.set('Iterations count must be 0 or highter.', Message.typeError)
        #     return
        value = int(value)
        self._n_plot_iterations = value
        if value > 0:
            self._message.set('Showing last {} iterations.'.format(value), Message.typeSuccess)
        elif value < 0:
            self._message.set('Not showing first {} iterations.'.format(-value), Message.typeSuccess)
        else:
            self._message.set('Showing all iterations.', Message.typeSuccess)

    def cmd_ymin(self, args):
        # check if there is an arg
        if len(args) == 0:
            self._ymin = None
            self._message.set('Ymin is automatic.', Message.typeSuccess)
            return
        
        try:
            value = float(args[0])
        except ValueError:
            self._message.set('"{}" is not a number.'.format(args[0]), Message.typeError)
            return

        if self._ymax is not None:
            if value >= self._ymax:
                self._message.set('Ymin must be smaler than Ymax', Message.typeError)
                return
        
        self._ymin = value
        self._message.set('Ymin was set to "{}"'.format(value), Message.typeSuccess)

    def cmd_ymax(self, args):
        # check if there is an arg
        if len(args) == 0:
            self._ymax = None
            self._message.set('Ymax is automatic.', Message.typeSuccess)
            return
        
        try:
            value = float(args[0])
        except ValueError:
            self._message.set('"{}" is not a number.'.format(args[0]), Message.typeError)
            return

        if self._ymin is not None:
            if value <= self._ymin:
                self._message.set('Ymax must be greater than Ymin', Message.typeError)
                return
        
        self._ymax = value
        self._message.set('Ymax was set to "{}"'.format(value), Message.typeSuccess)

    def cmd_hlog(self, args):
        if len(args) == 0:
            self._message.set('Log height needs an argument', Message.typeError)
            return
        
        value = args[0]

        if not value.isdigit():
            self._message.set('Log height must be a positve integer.', Message.typeError)
            return

        value = int(value)
        # check that log height is not more than 2/3 of window
        num_rows, _ = self._screen.getmaxyx()
        if value > num_rows * 2/3:
            self._message.set(
                'Log height can not be more than 2/3 ({}) of screen'.format(int(num_rows * 2 / 3)), 
                Message.typeError)
            return

        self._n_adflowout = value
        self._message.set('Log height was set to "{}"'.format(value), Message.typeSuccess)

class ADflowData():
    """
    This class runs ADFlow and processes the data to an array
    """
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Allows to plot ADflow output on the command line')
        self.init_vars()
        self.exit = False
        # self._adPlot = ADFlowPlot(self)

    def init_vars(self):
        # this is not in __init__, so it can be called to reset
        self.stdout_lines = []
        self.adflow_vars = OrderedDict()
        self.ap_name = ''
    
    def start_adflow(self):
        # init stuff
        self.parse_args()

        # run adflow script
        command = self.create_adflow_command()
        # process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        self.adflow_process = subprocess.Popen(
            shlex.split(command), stdout=subprocess.PIPE, bufsize=1, close_fds=ON_POSIX)
        self.adflow_queue = queue.Queue()
        self.adflow_thread = threading.Thread(
            target=enqueue_output, args=(self.adflow_process.stdout, self.adflow_queue))
        self.adflow_thread.daemon = True # thread dies with the program
        self.adflow_thread.start()

    def iter_adflow(self):
        try:  line = self.adflow_queue.get_nowait() # or q.get(timeout=.1)
        except queue.Empty:
            return False
        else:
            self.stdout_lines.append(line.decode("utf-8").rstrip())
            self.parse_stdout_line()
            return True

    
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
    # ap = ADflowData()
    # ap.run()

    aPlot = ADFlowPlot()
    aPlot.run()
    

# if __name__ == '__main__':
#     aPlot = ADFlowPlot()
#     aPlot.run()