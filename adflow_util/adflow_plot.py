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

def str2number(s):
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


class BaseBuffer():

    __attr_changed = False

    def __init__(self):
        self.a = 1
        self.b = 2
    
    def __eq__(self, other): 
        if not isinstance(other, BaseBuffer):
            # don't attempt to compare against unrelated types
            return NotImplemented

        # iterate through atributes and compare
        similar = True

        # test obj1 against obj2
        for attr, value in self.__dict__.items():
            other_value = getattr(other, attr, 'nav')
            if value != other_value or other_value == 'nav':
                similar = False
        # test obj2 against obj1
        for attr, value in other.__dict__.items():
            other_value = getattr(self, attr, 'nav')
            if value != other_value or other_value == 'nav':
                similar = False
        
        return similar

    def __setattr__(self, instance, value):
        is_value = getattr(self, instance, None)
        super(BaseBuffer, self).__setattr__(instance, value)

        if '__attr_changed' in instance:
            return

        if not self.__attr_changed:
            if not is_value == value:
                self.__attr_changed = True
    
    def _has_attr_changed(self):
        if not self.__attr_changed:
            return False

        self.__attr_changed = False
        return True


class CommandBuffer(BaseBuffer):
    """
        This Class buffers the commands which a user inputs
    """
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

class ScreenBuffer(BaseBuffer):
    """
        This class handles the decision to redraw or not.

        It buffers the last values and returns __redraw = True if something changed. 
        After accessing __redraw, it is set back to False
    """

    @property
    def redraw(self):
        redraw = False

        # create a list of all sub-objects
        check_objects = [self]
        for obj in self.__dict__.values():
            if isinstance(obj, BaseBuffer):
                check_objects.append(obj)

        # check all subobjects
        for obj in check_objects:
            if obj._has_attr_changed():
                redraw = True
                # no break here, so all __attr_changed will be reseted
        return redraw
    

class Message(BaseBuffer):
    """
        This Class handles the message at the bottom of the window.
    """
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

        if self._type != self.typeNone:
            lines[0] = "{}: {}".format(self.prefix[self._type], lines[0])
        line_count = len(lines)
        return lines, line_count, self._type


class ADFlowPlot():
    """
    This Class provides the curses window and plots the data parsed by ADflowData.
    """

    def __init__(self):
        self.screen = None
        self.commandBuffer = CommandBuffer()
        self.screenBuffer = ScreenBuffer()
        self.adData = ADflowData()
        self.message = Message()
        self.fps = 60

        # user changable vars
        self._exit = False
        self._n_adflowout = 0
        self._plot_vars = {'Res_rho': 1}
        self._n_plot_iterations = 0
        self._ymin = None
        self._ymax = None
        self._plot_log = True
        self._confirm_quiting = False

        # init stuff
        self.init_commands()
        self.screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        self.screen.keypad(True)
        self.screen.nodelay(True)

        # init colors
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)

        # init solver markers
        self.solvers_in_use = []
        self._solver_markers = {
            'None': '•',
            'RK': '•',
            'ANK': 'o',
            'SANK': '+',
            'CANK': '×',
            'CSANK': '¤',
            'NK': '÷',
            'preCon': 'X'   # PreConditioner Marker
        }
    
    def __del__(self):
        if self.screen is not None:
            self.cleanup()
    
    def cleanup(self):
        # shudown stuff
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()
    
    def main_loop(self):
        self.adData.start_adflow()
        while not self._exit:
            t0 = time.time()

            if self.commandBuffer._has_new_commited:
                self.parse_command()

            rows, cols = self.screen.getmaxyx()

            # update buffer with new values to get decision to redraw
            self.screenBuffer.scr_cols = cols
            self.screenBuffer.scr_rows = rows
            self.screenBuffer.message = self.message
            self.screenBuffer.command = self.commandBuffer
            self.screenBuffer.adflow_stdout_len = len(self.adData.stdout_lines)
            if len(self.adData.adflow_vars) > 0:
                self.screenBuffer.adflow_iter_len = len(self.adData.adflow_vars['Iter'])

            # redraw if something has changed
            if self.screenBuffer.redraw:
                self.draw(rows, cols)

            # refresh and key input
            self.parse_key_input()

            self.adData.read_stdout_lines()

            # sleep for the rest of the frame
            d_t = 1/self.fps - (time.time() - t0)
            if d_t > 0:
                time.sleep(d_t)
    
    def draw(self, rows, cols):
        # flicker fix. Use erase instead of clear. But clear before first plot
        self.screen.erase()
        if len(self.adData.stdout_lines) == 0:
            self.screen.clear()

        # message lines:
        line_count = self.print_message(rows) 

        # print console output at top
        self.print_adflow_output(rows, line_count)

        if len(self.adData.adflow_vars) > 0:
            adflow_iter_len = len(self.adData.adflow_vars['Iter'])
            
            # only plot if at least 2 iterations and new data available
            if adflow_iter_len >= 2:
                # plot vars
                self.print_plot(cols-3, rows - self._n_adflowout - line_count)

                # print labels
                self.print_labels(cols, rows)

                # print solver information
                self.print_solver_info(cols)

                # print marker information
                self.print_markers(cols, rows)

                # print finished message
                if self.adData.has_finished:
                    self.print_finished_message(cols, rows)

        # print command line at bottom:
        self.screen.addstr(rows-1, 0, self.commandBuffer.get_active())
    
    def print_message(self, rows):
        lines, line_count, _type = self.message.text()
        n = line_count
        for line in lines:
            self.screen.addstr(rows-1-n, 0, line, curses.color_pair(_type))
            n -= 1
        
        return line_count
    
    def print_adflow_output(self, height, line_count):
        len_output = self._n_adflowout
        if len(self.adData.adflow_vars) == 0:
            len_output = height -1 - line_count

        # print output
        for n in range(len_output, 0, -1):
            if len(self.adData.stdout_lines) >= n:
                stdout_line = self.adData.stdout_lines[-n]
            else:
                stdout_line = ''
            self.screen.addstr(len_output - n, 0, stdout_line)
    
    def print_labels(self, cols, rows):
        # prepare print
        labels = []
        max_len_label = 0
        for var, color in self._plot_vars.items():
            label = [color]
            if self._plot_log:
                label.append('• log({})'.format(var))
            else:
                label.append('• {}'.format(var))
            labels.append(label)
            
            if len(label[1]) > max_len_label:
                max_len_label = len(label[1])
        n = 0

        # print
        for label in labels:
            self.screen.addstr(
                self._n_adflowout + 1 + n, cols - max_len_label - 8 - 25, 
                label[1],
                curses.color_pair(label[0]))
            n += 1
    
    def print_markers(self, cols, rows):
        n = 0
        for solver in self.solvers_in_use:
            if solver == 'None':
                continue

            marker = self._solver_markers[solver]
            self.screen.addstr(
                self._n_adflowout + n + 9, 
                cols - 20 - 7, 
                '{} {}'.format(marker, solver))
            n += 1
    
    def print_solver_info(self, cols):
        iter_tot = self.adData.adflow_vars_raw['Iter_Tot']
        cfl = self.adData.adflow_vars_raw['CFL'][-1]
        pairs = [
            ['Grd Lvl',     self.adData.adflow_vars_raw['Grid_level'][-1]],
            ['IterTot',     iter_tot[-1] if iter_tot[-1] < 1e6 else '{:.1e}'.format(iter_tot[-1])],
            ['Iter Diff',   iter_tot[-1] - iter_tot[-2]],
            ['IterType',    self.adData.adflow_vars_raw['Iter_Type'][-1]],
            ['CFL',         cfl if isinstance(cfl, str) else '{:.1e}'.format(cfl)],
            ['Step',        self.adData.adflow_vars_raw['Step'][-1]],
            ['Lin Res',     self.adData.adflow_vars_raw['Lin_Res'][-1]]
        ]

        info_str = []
        for pair in pairs:
            info_str.append('{:9}: {:>7}'.format(pair[0], pair[1]))
            
        # print name
        name = self.adData.ap_name + '_' + str(self.adData.hist_iteration)
        self.screen.addstr(
            self._n_adflowout, int((cols - len(name) - 5) / 2), 
            name)
        
        # print info
        n = 0
        for line in info_str:
            self.screen.addstr(self._n_adflowout + 1 + n, cols - 20 - 7, line)
            n += 1
    
    def print_finished_message(self, cols, rows):
        if self.adData.has_finished_total_call_time is None:
            return
        
        if self.adData.has_finished_total_func_time is None:
            return

        time = self.adData.has_finished_total_call_time + self.adData.has_finished_total_func_time

        text = 'ADflow has finished in {} seconds.'.format(time)

        y = int(rows/2)
        x = int((cols - len(text)) / 2)

        self.screen.addstr( y, x, text, curses.color_pair(1))

    def print_plot(self, width, height):
        if len(self._plot_vars) == 0:
            return

        x = self.adData.adflow_vars['Iter']

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
        x = x[min_i:]

        # set marker for solver
        line_marker = []
        solvers_in_use = []
        for solver in self.adData.adflow_vars_raw['Iter_Type'][min_i:]:
            pc_marker = None
            if solver[0] == '*':
                solver = solver[1:]
                pc_marker = self._solver_markers['preCon']
            marker = self._solver_markers[solver]

            # add solver to solvers in unse
            if solver not in solvers_in_use:
                solvers_in_use.append(solver)
            if pc_marker is not None:
                if 'preCon' not in solvers_in_use:
                    solvers_in_use.append('preCon')
            
            # pc marker
            if pc_marker is not None:
                marker = pc_marker + marker
            line_marker.append(marker)
        self.solvers_in_use = solvers_in_use

        # add plot data
        for key, color in self._plot_vars.items():
            y = self.adData.adflow_vars[key][min_i:]

            # take log of y values
            if self._plot_log:
                y = np.ma.log10(y)
                y = y.filled(0.0)

            # set plot data
            plx.plot(x,y, line_color=color, line_marker=line_marker)

            # calculate automatic limits
            if ylim is None and len(y) >= 2:
                ylim = [
                    min(y), 
                    max(y)]
            else:
                ylim = [min(min(y), ylim[0]),
                        max(max(y), ylim[1])]
        
        # set user limits
        if self._ymin is not None:
            ylim[0] = self._ymin
        if self._ymax is not None:
            ylim[1] = self._ymax

        # if ymin and max are the same, set it to 1
        if ylim[0] >= ylim[1]:
            ylim[1] = ylim[0] + 1
            ylim[0] = ylim[0] - 1
            self.message.set('ymax is lower or same as ymin.', Message.typeError)
    
        # prepare plot
        plx.set_xlim([x[0], x[-1]])
        plx.set_ylim(ylim)
        plx._set_xlim()
        plx._set_ylim()
        plx._set_grid()
        plx._add_yaxis()
        plx._add_xaxis()

        # draw plot
        lines = []
        for r in range(len(plx._vars.grid) -1, -1, -1):
            lines.append("".join(plx._vars.grid[r]))

        len_lines = len(lines)
        for n in range(len_lines):

            # plot in proper colors
            sub_lines = lines[n].split('\033')[1:]
            x = 0
            for sub_line in sub_lines:
                color_str = sub_line.split('m')[0]
                string = sub_line[len(color_str)+1:]

                self.screen.addstr(
                    self._n_adflowout + n, x, 
                    string,
                    curses.color_pair(int(color_str[1:])))
                x += len(string)
    
    def parse_key_input(self):
        try: 
            c = self.screen.getch()
            if c == curses.ERR:
                return
            
            if isinstance(c, int):
                
                switcher = {
                    curses.KEY_BACKSPACE:   self.commandBuffer.remove,
                    8:                      self.commandBuffer.remove,
                    127:                    self.commandBuffer.remove,

                    curses.KEY_ENTER:       self.commandBuffer.commit,
                    10:                     self.commandBuffer.commit,
                }
                func = switcher.get(c)
                if func is not None: func()
                if c > 31 and c < 127:
                    self.commandBuffer.add(chr(c))
        except curses.error:
            pass
    
    def parse_command(self):
        temp = self.commandBuffer.get_commited().split()
        command = temp[0]
        args = temp[1:]

        # confirm quiting
        if self._confirm_quiting:
            self.cmd_quit_confirm(command)
            return

        # execute command
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
                            'int            height in lines.'],
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

        self.message.set(help_text[:-1], Message.typeNone)
        
    def cmd_clear(self, args):
        self.message.set('', Message.typeNone)

    def cmd_quit(self, args):
        self.message.set('Do you really want to quit?', Message.typeInfo)
        self._confirm_quiting = True

    def cmd_quit_confirm(self, args):
        try:
            answer = str2bool(args)
        except:
            answer = False

        if answer:
            self._exit = True
        else:
            self._confirm_quiting = False
            self.message.set('', Message.typeNone)
    
    def cmd_list_var(self, args):
        if len(self.adData.adflow_vars) > 0:
            text = 'Plottable ADflow variables:\n'
            for var in self.adData.adflow_vars.keys():
                if var in self.adData.not_plottable_vars:
                    continue
                if var in self._plot_vars:
                    continue

                text += '"{}", '.format(var)
        
            text = text[:-2]
            self.message.set(text, Message.typeNone)
            return

        self.message.set('No ADflow output detected, can not plot anything.', Message.typeError)

    def cmd_add_var(self, args):
        # check how many values there are
        if len(args) == 0:
            self.message.set('No Variable defined', Message.typeError)
            return
        
        value = args[0]

        # check if value exists and get proper case
        exists = False
        n_color = 0
        for var in self.adData.adflow_vars:
            # if var is not plotable, continue
            if var in self.adData.not_plottable_vars:
                continue
            
            if value.lower() == var.lower():
                exists = True
                value = var
                break
            n_color += 1
        if not exists:
            self.message.set('"{}" ist not a Variable.'.format(value), Message.typeError)
            return
        
        # check if value hast not been added allready
        if value in self._plot_vars:
            self.message.set('"{}" is allready plotting.'.format(value), Message.typeError)
        
        # check if value is plottable
        if value in self.adData.not_plottable_vars:
            self.message.set('"{}" can not be plotet.'.format(value), Message.typeError)
            return
        
        # figure out color
        color = (n_color + 10) % 7 

        self._plot_vars[value] = color

        self.message.set('"{}" now plotting.'.format(value), Message.typeSuccess)
    
    def cmd_remove_var(self, args):
        # check if there is an arg
        if len(args) == 0:
            self.message.set('No variable named.', Message.typeError)
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
            self.message.set('"{}" is not active.'.format(value), Message.typeError)
            return

        # if value not in self._plot_vars:
        #     self._message.set('"{}" is not active.'.format(value), Message.typeError)
        #     return
        
        # remove key
        del self._plot_vars[value]
        self.message.set('"{}" has been removed.'.format(value), Message.typeSuccess)

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
            self.message.set('Iterations count must be an integer.', Message.typeError)
            return

        value = int(value)

        if value < 2 and value > 0:
            self.message.set('Iteration limit must at least be 2.', Message.typeError)
            return

        self._n_plot_iterations = value
        if value > 0:
            self.message.set('Showing last {} iterations.'.format(value), Message.typeSuccess)
        elif value < 0:
            self.message.set('Not showing first {} iterations.'.format(-value), Message.typeSuccess)
        else:
            self.message.set('Showing all iterations.', Message.typeSuccess)

    def cmd_ymin(self, args):
        # check if there is an arg
        if len(args) == 0:
            self._ymin = None
            self.message.set('Ymin is automatic.', Message.typeSuccess)
            return
        
        try:
            value = float(args[0])
        except ValueError:
            self.message.set('"{}" is not a number.'.format(args[0]), Message.typeError)
            return

        if self._ymax is not None:
            if value >= self._ymax:
                self.message.set('Ymin must be smaler than Ymax', Message.typeError)
                return
        
        self._ymin = value
        self.message.set('Ymin was set to "{}"'.format(value), Message.typeSuccess)

    def cmd_ymax(self, args):
        # check if there is an arg
        if len(args) == 0:
            self._ymax = None
            self.message.set('Ymax is automatic.', Message.typeSuccess)
            return
        
        try:
            value = float(args[0])
        except ValueError:
            self.message.set('"{}" is not a number.'.format(args[0]), Message.typeError)
            return

        if self._ymin is not None:
            if value <= self._ymin:
                self.message.set('Ymax must be greater than Ymin', Message.typeError)
                return
        
        self._ymax = value
        self.message.set('Ymax was set to "{}"'.format(value), Message.typeSuccess)

    def cmd_log(self, args):
        self._plot_log = not self._plot_log

        if self._plot_log:
            self.message.set('Showing logarithmic scale.', Message.typeSuccess)
        else:
            self.message.set('Showing normal scale.', Message.typeSuccess)

    def cmd_hlog(self, args):
        if len(args) == 0:
            self.message.set('Log height needs an argument', Message.typeError)
            return
        
        value = args[0]

        if not value.isdigit():
            self.message.set('Log height must be a positve integer.', Message.typeError)
            return

        value = int(value)
        # check that log height is not more than 2/3 of window
        num_rows, _ = self.screen.getmaxyx()
        if value > num_rows * 2/3:
            self.message.set(
                'Log height can not be more than 2/3 ({}) of screen'.format(int(num_rows * 2 / 3)), 
                Message.typeError)
            return

        self._n_adflowout = value
        self.message.set('Log height was set to "{}"'.format(value), Message.typeSuccess)


class ADflowData():
    """
    This class runs ADFlow and processes the data to an array
    """
    def __init__(self, args=None):
        self.parser = argparse.ArgumentParser(
            description='Allows to plot ADflow output on the command line')
        
        # options
        self.not_plottable_vars = ['Iter_Type', 'Iter']
        self.flush_hist_n = 20

        # adflow process vars
        self.adflow_process = None
        self.adflow_queue = None
        self.adflow_thread = None

        # state vars
        self.stdout_lines = []
        self.has_finished = True
        self.has_finished_total_call_time = None
        self.has_finished_total_func_time = None
        self.ap_name = ''
        self.hist_file = None
        self.hist_iteration = 0
        self.adflow_vars = OrderedDict()
        self.adflow_vars_raw = OrderedDict()

        # init functions
        self.parse_input_args(args if args is not None else sys.argv[1:])
        # self.init_vars()
    
    def __del__(self):
        # kill adflow
        if self.adflow_process is not None:
            self.adflow_process.kill()

    def reset_vars(self):
        self.adflow_vars = OrderedDict()
        self.adflow_vars_raw = OrderedDict()
        self.hist_iteration += 1
    
    def start_adflow(self):
        # run adflow script
        command = self.create_adflow_run_command()
        # process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
        self.adflow_process = subprocess.Popen(
            shlex.split(command), env=os.environ,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, 
            bufsize=1, close_fds=ON_POSIX)
        
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
            command += '{} -H {} '.format(self.args.mpi_command, self.args.mpi_H)

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
    
    def parse_input_args(self, args):
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

        self.args = self.parser.parse_args(args)

    def parse_stdout_line(self):
        # parse every stdout line and do the appropriate action

        # if the AeroProblem Name is not set, do it
        if self.ap_name == '':
            if self.stdout_lines[-1][0:29] == '|  Switching to Aero Problem:':
                self.ap_name = self.stdout_lines[-1][29:-2].strip()

        
        # if len(self.adflow_vars) == 0:
        if self.has_finished:
            if len(self.stdout_lines) <= 3:
                return

            # figure out if the line is a var description 
            var_desc_string = '#---------'
            if (self.stdout_lines[-4][0:10] == var_desc_string and 
                self.stdout_lines[-3][0:10] == '#  Grid  |' and
                self.stdout_lines[-2][0:10] == '#  level |' and
                self.stdout_lines[-1][0:10] == var_desc_string):
                # reset vars
                self.reset_vars()
                self.has_finished = False
                self.has_finished_total_call_time = None
                self.has_finished_total_func_time = None

                # parse new vars
                adflow_vars = self.parse_adflow_var_names(self.stdout_lines[-3:-1])
                self.adflow_vars = adflow_vars
                self.adflow_vars_raw = copy.deepcopy(adflow_vars)
            # return
                    
        # figure out if this is an iteration ouput 
        if self.stdout_lines[-1][0:5] == '     ':
            self.parse_adflow_var_values(self.stdout_lines[-1])

            # write the history File 
            if self.args.hist:
                self.write_history()

        # figure out if the end has been reached
        if self.stdout_lines[-1] == '#':
            # save stuff
            self.has_finished = True

            # close history file
            if self.hist_file is not None:
                self.hist_file.close()
                self.hist_file = None

        
        # if adflow has finished, figure out how long it took
        if self.has_finished:
            if self.stdout_lines[-1][0:17] == '| Total Call Time':
                tmp1 = self.stdout_lines[-1].split(':')[1]
                self.has_finished_total_call_time = str2number(tmp1.split()[0])
            
            if self.stdout_lines[-1][0:32] == '| Total Function Evaluation Time':
                tmp1 = self.stdout_lines[-1].split(':')[1]
                self.has_finished_total_func_time = str2number(tmp1.split()[0])

    def parse_adflow_var_values(self, stdout_lines):
        bits = stdout_lines.split()

        n = 0
        for adflow_var in self.adflow_vars:
            if adflow_var == 'relRes':
                continue

            bit = str2number(bits[n])
            self.adflow_vars_raw[adflow_var].append(bit)
            self.adflow_vars[adflow_var].append(bit)

            if isinstance(bit, str):
                self.adflow_vars[adflow_var][-1] = 0.0
                
            # self.adflow_vars[adflow_var].append(str_to_number(bits[n]))
            n += 1
        
        # calculate relative convergence
        if len(self.adflow_vars['totalRes']) > 1:
            rel_conv = self.adflow_vars['totalRes'][0] / self.adflow_vars['totalRes'][-1]
        else:
            rel_conv = 0.0
        
        self.adflow_vars_raw['relRes'].append(rel_conv)
        self.adflow_vars['relRes'].append(rel_conv)
    
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
        
        # add relative convergence
        adflow_vars_dict['relRes'] = []
        
        return adflow_vars_dict

    def write_history(self):
        if len(self.adflow_vars_raw) == 0:
            return False

        delimeter = str(self.args.histDel)

        # Open File and write header
        if self.hist_file is None:
            filename = self.ap_name + '_' + str(self.hist_iteration) + '_hist.csv'
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
    try: 
        aPlot = ADFlowPlot()
        aPlot.main_loop()
    except:
        try:
            aPlot.cleanup()
        except NameError:
            pass
        raise
