import argparse
import os
import subprocess
import shlex
import adflow_util.plot as plx
import curses
from collections import OrderedDict
import time
import threading
import sys
import queue
import math
import numpy as np
import copy

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

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


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
        lines = self._text.splitlines()
        if lines == []:
            return '', 0, self.typeNone
        # else:
        #     lines = [lines]

        if self._type != self.typeNone:
            lines[0] = "{}: {}".format(self.prefix[self._type], lines[0])
        line_count = len(lines)
        return lines, line_count, self._type


class ADFlowPlot():
    """
    This Class provides the curse window and plots the data parsed by ADflowData
    """

    def __init__(self):
        self._screen = None
        self._buffer = Buffer()
        self._adData = ADflowData()
        self._message = Message()
        self._markers = ['•', '*', 'x', 'v', 'o']
        self._marker_n = 1
        self._plot_log = False

        # user changable vars
        self._exit = False
        self._n_adflowout = 15
        self._plot_vars = {'Res_rho': self._markers[self._marker_n - 1]}
        self._n_plot_iterations = 0
        self._ymin = None
        self._ymax = None

        # init stuff
        self.init_commands()
        self._screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        self._screen.keypad(True)
        self._screen.nodelay(True)

        # init colors
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    
    def __del__(self):
        if self._screen is not None:
            self.cleanup()
    
    def cleanup(self):
        # shudown stuff
        curses.nocbreak()
        self._screen.keypad(False)
        curses.echo()
        curses.endwin()
    
    def main_loop(self):
        self._adData.start_adflow()
        while not self._exit:
            t0 = time.time()

            try: 
                if self._buffer._has_new_commited:
                    self.parse_command()

                num_rows, num_cols = self._screen.getmaxyx()
                self._screen.clear()

                # message lines:
                line_count = self.print_message(num_rows) 

                # print console output at top
                self.print_adflow_output(num_rows, line_count)

                if len(self._adData.adflow_vars) > 0:
                    # plot vars
                    self.print_plot(num_cols-3, num_rows - self._n_adflowout - line_count)

                    # print labels
                    self.print_labels(num_cols, num_rows)

                # print command line at bottom:
                self._screen.addstr(num_rows-1, 0, 'Command: ' + self._buffer.get_active())

                # refresh and key input
                self._screen.refresh()
                self.parse_key_input()
            except:
                self.cleanup()
                raise

            self._adData.read_stdout_lines()

            # sleep for the rest of the frame
            d_t = 1/24 - (time.time() - t0)
            if d_t > 0:
                time.sleep(d_t)
    
    def print_message(self, rows):
        lines, line_count, _type = self._message.text()
        n = line_count
        for line in lines:
            self._screen.addstr(rows-1-n, 0, line, curses.color_pair(_type))
            n -= 1
        
        return line_count
    
    def print_adflow_output(self, height, line_count):
        len_output = self._n_adflowout
        if len(self._adData.adflow_vars) == 0:
            len_output = height -1 - line_count

        # print output
        for n in range(len_output, 0, -1):
            if len(self._adData.stdout_lines) >= n:
                stdout_line = self._adData.stdout_lines[-n]
            else:
                stdout_line = ''
            self._screen.addstr(len_output - n, 0, stdout_line)
    
    def print_labels(self, cols, rows):
        labels = []
        max_len_label = 0
        for var, symbol in self._plot_vars.items():
            if self._plot_log:
                label = '{} - log({})'.format(symbol, var)
            else:
                label = '{} - {}'.format(symbol, var)
            labels.append(label)
            if len(label) > max_len_label:
                max_len_label = len(label)
        n = 0
        for label in labels:
            self._screen.addstr(self._n_adflowout + 2 + n, cols - max_len_label - 10, label)
            n += 1
    
    def print_plot(self, width, height):
        if len(self._plot_vars) == 0:
            return

        if len(self._adData.adflow_vars) == 0:
            return

        x = self._adData.adflow_vars['Iter']
        if len(x) < 2:
            return

        # reset plot variables
        plx._vars.__init__()
        plx._vars.cols_term = width
        plx._vars.rows_term = height
        ylim = None

        # only show parts of iteration history
        min_i = 0
        if self._n_plot_iterations > 0:
            min_i =  len(x) - min(len(x), self._n_plot_iterations)
        elif self._n_plot_iterations < 0:
            min_i = min(len(x) - 2, -self._n_plot_iterations + 1)
            
        # add plot data
        for key, marker in self._plot_vars.items():
            y = self._adData.adflow_vars[key]

            # take log of y values
            if self._plot_log:
                y = np.ma.log10(y)
                y = y.filled(0.0)

            # set plot data
            plx.plot(x,y, line_marker=marker)

            # calculate automatic limits
            if ylim is None and len(y) >= 2:
                ylim = [
                    min(y[min_i:]), 
                    max(y[min_i:])]
            else:
                ylim = [min(min(y[min_i:]), ylim[0]),
                        max(max(y[min_i:]), ylim[1])]
        
        # set user limits
        if self._ymin is not None:
            ylim[0] = self._ymin
        if self._ymax is not None:
            ylim[1] = self._ymax

        # if ymin and max are the same, set it to 1
        if ylim[0] >= ylim[1]:
            ylim[1] = ylim[0] + 1
            ylim[0] = ylim[0] - 1
            self._message.set('ymax is lower or same as ymin.', Message.typeError)
    
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
    
    def parse_key_input(self):
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
    
    def parse_command(self):
        temp = self._buffer.get_commited().split()
        command = temp[0]
        args = temp[1:]

        func = self.commands_switcher.get(command)
        if func is not None: func(args)
    
    def init_commands(self):
        self.commands = {
            'help':         [self.cmd_help,
                            ['h', 'help'],
                            'Shows this help text.',
                            'str            command where further explanaition is wanted.\n' \
                            'no argument    lists all available commands.'],
            'clear':        [self.cmd_clear,
                            ['c', 'clear'],
                            'Cleares the message window.'],

            'quit':         [self.cmd_quit,
                            ['q', 'quit'],
                            'Forces the application to close.'],

            'list':         [self.cmd_list_var,
                            ['l', 'list'],
                            'Lists for plot available variables.'],
            'add':          [self.cmd_add_var,
                            ['a', 'add'],
                            'Adds a new variable to the plot.',
                            'string         name of variable.'],
            'remove':       [self.cmd_remove_var,
                            ['r', 'remove'],
                            'Removes a variable from the plot.',
                            'string         name of variable.'],

            'iterations':   [self.cmd_iterations,
                            ['i', 'iterations'],
                            'Changes how many iterations are shown.',
                            'positive int   shows the last x iterations.\n' \
                            'negative int   does\'t show the first x iterations\n' \
                            'no argument    shows all iterations'],
            'ymin':         [self.cmd_ymin,
                            ['ymin'],
                            'Sets the minimum of the y axis.',
                            'float          sets the minimum to that number.\n' \
                            'no argument    sets minimum automatically.'],
            'ymax':         [self.cmd_ymax,
                            ['ymax'],
                            'Sets the maximum of the y axis.',
                            'float          sets the maximum to that number.\n' \
                            'no argument    sets maximum automatically.'],
            'log':          [self.cmd_log,
                            ['log'],
                            'Switches between normal and logarithmic scale. Zero values will be printed as 0.'],
            
            'hlog':         [self.cmd_hlog,
                            ['hlog'],
                            'Sets the height of console window at the top.',
                            'int            height in lines.']
        }

        # prepare command switcher
        switcher = dict()
        for command in self.commands.values():
            for alias in command[1]:
                switcher[alias] = command[0]
        self.commands_switcher = switcher
    
    def cmd_help(self, args):
        def get_description(name, command):
            alias_text = ''
            for alias in command[1]:
                alias_text += ' "{}",'.format(alias)
            alias_text = alias_text[:-1]

            return '{: <12} access with{} \n {: <12}\n\n'.format(
                name, alias_text, command[2]) 

        # list all commands
        if len(args) == 0:
            help_text = ''
            for name, command in self.commands.items():
                help_text += get_description(name, command)
        
        # list infos to a specific command
        else: 
            name = args[0]
            command = self.commands.get(name)
            if command == None:
                return
            
            help_text = get_description(name, command)
            if len(command) > 3:
                help_text += 'Arguments:\n'
                help_text += command[3]

        self._message.set(help_text[:-1], Message.typeNone)
        
    def cmd_clear(self, args):
        self._message.set('', Message.typeNone)

    def cmd_quit(self, args):
        self._exit = True
    
    def cmd_list_var(self, args):
        if len(self._adData.adflow_vars) > 0:
            text = 'Plottable ADflow variables:\n'
            for var in self._adData.adflow_vars.keys():
                if var in self._adData.not_plottable_vars:
                    continue
                if var in self._plot_vars:
                    continue

                text += '"{}", '.format(var)
        
            text = text[:-2]
            self._message.set(text, Message.typeNone)
            return

        self._message.set('No ADflow output detected, can not plot anything.', Message.typeError)

    def cmd_add_var(self, args):
        # check how many values there are
        if len(args) == 0:
            self._message.set('No Variable defined', Message.typeError)
            return
        
        value = args[0]
        if len(args) == 2:
            marker = args[1]
        else:
            marker = self._markers[self._marker_n]
            self._marker_n += 1
            if self._marker_n >= len(self._markers):
                self._marker_n = 0

        # check if value exists and get proper case
        exists = False
        for var in self._adData.adflow_vars:
            if value.lower() == var.lower():
                exists = True
                value = var
                break
        if not exists:
            self._message.set('"{}" ist not a Variable.'.format(value), Message.typeError)
            return
        
        # check if value hast not been added allready
        if value in self._plot_vars:
            self._message.set('"{}" is allready plotting.'.format(value), Message.typeError)
        
        # check if value is plottable
        if value in self._adData.not_plottable_vars:
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
        # check if value exists and get proper case
        exists = False
        for var in self._plot_vars:
            if value.lower() == var.lower():
                exists = True
                value = var
                break
        if not exists:
            self._message.set('"{}" is not active.'.format(value), Message.typeError)
            return

        # if value not in self._plot_vars:
        #     self._message.set('"{}" is not active.'.format(value), Message.typeError)
        #     return
        
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

    def cmd_log(self, args):
        self._plot_log = not self._plot_log

        if self._plot_log:
            self._message.set('Showing logarithmic scale.', Message.typeSuccess)
        else:
            self._message.set('Showing normal scale.', Message.typeSuccess)

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
        self.parser = argparse.ArgumentParser(
            description='Allows to plot ADflow output on the command line')
        self.parse_input_args()
        self.init_vars()
        self.exit = False
        self.not_plottable_vars = ['Iter_Type', 'Iter']
        self.flush_hist_n = 20
        # self._adPlot = ADFlowPlot(self)

    def init_vars(self):
        # this is not in __init__, so it can be called to reset
        self.stdout_lines = []
        self.adflow_vars = OrderedDict()
        self.adflow_vars_raw = OrderedDict()
        self.ap_name = ''
        self.hist_file = None
    
    def start_adflow(self):
        # run adflow script
        command = self.create_adflow_run_command()
        # process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        self.adflow_process = subprocess.Popen(
            shlex.split(command), env=os.environ,
            stdout=subprocess.PIPE, stdin=subprocess.PIPE, bufsize=1, close_fds=ON_POSIX)
        
        # Pipe thread
        self.adflow_queue = queue.Queue()
        self.adflow_thread = threading.Thread(
            target=enqueue_output, args=(self.adflow_process.stdout, self.adflow_queue))
        self.adflow_thread.daemon = True # thread dies with the program
        self.adflow_thread.start()

    def create_adflow_run_command(self):
        command = ''

        # mpirun -np
        if self.args.mpi_np is not None:
            command += '{} -np {} '.format(self.args.mpi_command, self.args.mpi_np)

        # mpirun -H
        if self.args.mpi_H is not None:
            command += '{} -H {} '.format(self.args.mpi_command, self.args.mpi_np)

        # basic python command
        command += '{} {}'.format(sys.executable, self.args.inputfile)

        return command

    def read_stdout_lines(self):
        while True:
            try:  
                line = self.adflow_queue.get_nowait()
            except queue.Empty:
                break
            else:
                # parse the line
                self.stdout_lines.append(line.decode("utf-8").rstrip())
                self.parse_stdout_line()

                # write the history File 
                if self.args.hist:
                    self.write_history()

                # return True
    
    def parse_input_args(self):
        # input file
        self.parser.add_argument("-i", dest="inputfile", required=True, type=str,
            help="The ADflow script to run.")

        # history file
        self.parser.add_argument("-hist", dest="hist", default=True,  type=str2bool,
            help="Should be false if no history file should be written.") 
        self.parser.add_argument("-histFile", dest="histFile", default=None, type=str,
            help="The .csv file where the convergence history should be written. " \
                 "Default uses AeroProblem Name.")  
        self.parser.add_argument('-histDel', dest="histDel", default=';', type=str,
            help='The delimeter to be used in the history file. (default: ;')
        
        # mpi stuff
        mpigroup = self.parser.add_mutually_exclusive_group()
        self.parser.add_argument("-mpi", dest="mpi_command", default="mpirun", type=str,
            help='The mpi command to use. (default: mpirun)')
        mpigroup.add_argument("-np", dest="mpi_np", default=None, type=int,
            help="Number of cores to use by mpi.")
        mpigroup.add_argument("-H", dest="mpi_H", default=None, type=str,
            help="The hosts to use by mpi.") 

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
                    adflow_vars = self.parse_adflow_var_names(self.stdout_lines[-3:-1])
                    self.adflow_vars = adflow_vars
                    self.adflow_vars_raw = copy.deepcopy(adflow_vars)
        else:
            # figure out if this is an iteration ouput 
            # (only do this if adflow_vars allready have been parsed)
            if self.stdout_lines[-1][0:5] == '     ':
                self.parse_adflow_var_values(self.stdout_lines[-1])

            # figure out if the end has been reached
            # only do this adflow_vars has allready been parsed)
            if self.stdout_lines[-1] == '#':
                # save stuff

                # close history file
                if self.hist_file is not None:
                    self.hist_file.close()

                # reset stuff so it is ready for the next run
                self.init_vars()

    def parse_adflow_var_values(self, stdout_lines):
        bits = stdout_lines.split()

        n = 0
        for adflow_var in self.adflow_vars:
            bit = str_to_number(bits[n])
            self.adflow_vars_raw[adflow_var].append(bit)
            self.adflow_vars[adflow_var].append(bit)

            if isinstance(bit, str):
                self.adflow_vars[adflow_var][-1] = 0.0
                
            # self.adflow_vars[adflow_var].append(str_to_number(bits[n]))
            n += 1
    
    def parse_adflow_var_names(self, stdout_lines):
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

    def write_history(self):
        if len(self.adflow_vars_raw) == 0:
            return False

        delimeter = str(self.args.histDel)

        # Open File and write header
        if self.hist_file is None:
            filename = self.ap_name + '_hist.csv'
            if self.args.histFile is not None:
                filename = self.args.histFile
            self.hist_file = open(filename, 'w')

            header_str = ''
            for key in self.adflow_vars_raw.keys():
                header_str += key + delimeter
            self.hist_file.write(header_str + '\n')
        
        # write iteration
        if len(self.adflow_vars_raw['Iter']) > 0:
            iter_str = ''
            for value in self.adflow_vars_raw.values():
                iter_str += str(value[-1]) + delimeter
            self.hist_file.write(iter_str + '\n')

            # flush only all xx iterations
            if len(self.adflow_vars_raw['Iter']) % self.flush_hist_n == 0:
                self.hist_file.flush()
        


def adflow_plot():
    aPlot = ADFlowPlot()
    aPlot.main_loop()
