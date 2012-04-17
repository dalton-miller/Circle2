# text mode chat

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Paul Francis Harrison
#    Copyright (C) 2002  Monash University
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


from __future__ import generators
import os
import select
import string
import sys
from circlelib import utility, error
from circlelib.chat import *

import chat_commands



class Chat_text(Chat):
    """ Text mode chat interface. """
    
    def __init__(self,app):
        Chat.__init__(self,app)

        self.prompt = ''
        self.command_text_lines = [ ]
        self.command_text = ''
        self.input_queue = ''
        self.escape_queue = [ ]
        self.command_visible = 0

        # Command registry
        self._commands = { }  # name -> (min n. params, max n. params, function)
        chat_commands.register_commands(self)

        self.history = [ '' ] # Command history
        self.history_position = 0

        self.input = app.input
        self.output = app.output
        self.widget_visible = 1

        self.shell = None
        self.bgshell = None

    def stop(self):
        self.hide_command_line()
        Chat.stop(self)

    def run_shell(self, command):
        """bug: does not write to the correct output"""
        self.hide_command_line()
        os.system(command)
        self.show_command_line()


    def show(self, str):
        # IO might raise an error if output has been closed 
        try:
            self.hide_command_line()
            self.output.write(utility.force_string(str)+'\n')
            self.show_command_line()
            self.output.flush()
        except:
            pass
        
    def read_input(self):
        char = self.input.read(1)
        if not char:
            raise error.Error('interrupted')
        
        self.input_queue = self.input_queue + char

        if (char >= 'a' and char <= 'z') or \
             (char >= 'A' and char <= 'Z'):
            pos = string.find(self.input_queue,chr(27)+'[')
            if pos != -1:
                #self.show("escape")
                self.escape_queue.append(self.input_queue[pos+2:])
                self.input_queue = self.input_queue[:pos]

    def text_get_escape(self,code):
        while 1:
            for i in range(len(self.escape_queue)):
                if self.escape_queue[i][-1] == code:
                    return self.escape_queue.pop(i)
            self.read_input()

    def text_backspace(self, n):
        while n:
            self.output.write(chr(27)+'[6n')
            self.output.flush()

            escape = self.text_get_escape('R')

            try:
                column = int(string.split(escape[:-1],';')[1]) - 1
            except:
                print _('Badly formatted escape sequence '),escape
                return

            if column == 0:
                self.output.write(chr(27)+'[A'+chr(27)+'[999C'+chr(27)+'[K')
                self.output.flush()
                n = n - 1
                continue
            
            if n < column:
                move = n
            else:
                move = column
            self.output.write(chr(27)+'[%dD'%move+chr(27)+'[K')
            self.output.flush()
            n = n - move

    def hide_command_line(self):        
        self.command_visible = self.command_visible - 1
        if self.command_visible == 0:
            self.output.write( (chr(8)+' '+chr(8))*(len(self.prompt)+len(self.command_text) +1) )
            self.output.flush()
        #    self.text_backspace( len(self.prompt)+len(self.command_text)+1 )

    def show_command_line(self):
        self.command_visible = self.command_visible + 1
        if self.command_visible == 1:
            self.output.write( self.prompt+' '+self.command_text )
            self.output.flush()

    def advance_command_line(self):
        self.output.write('\n')
        self.command_text = ''
        self.command_visible = 0

    def text_mainloop(self):
        self.command_text_lines = [ ]
        self.command_text = ''
        self.set_prompt()
        self.app.running = 1

        utility.set_config('text_status',{'running':1})

        self.show_command_line()
        try:
            while self.app.running:
                utility._daemon_action_timeout()
                    
                if select.select([self.input],[],[ ],0.1)[0]:
                    self.read_input()

                while self.escape_queue:
                    item = self.escape_queue.pop(0)

                    if self.command_text_lines:
                        continue

                    if item == 'A' and self.history_position > 0:
                        self.history[self.history_position] = self.command_text
                        self.history_position = self.history_position - 1
                        self.hide_command_line()
                        self.command_text = self.history[self.history_position]
                        self.show_command_line()

                    if item == 'B' and self.history_position < len(self.history)-1:
                        self.history[self.history_position] = self.command_text
                        self.history_position = self.history_position + 1
                        self.hide_command_line()
                        self.command_text = self.history[self.history_position]
                        self.show_command_line()

                while self.input_queue and self.input_queue != chr(27) and self.input_queue[:2] != chr(27)+'[':
                    char = self.input_queue[0]
                    self.input_queue = self.input_queue[1:]

                    if char == '\n':
                        line = self.command_text
                        self.advance_command_line()
                            
                        self.history[-1] = line
                        self.history.append('')
                        self.history_position = len(self.history)-1

                        if line[-1:] == '\\':
                            self.command_text_lines.append(line[:-1])
                            self.set_prompt()
                            self.show_command_line()
                        else:
                            lines = self.command_text_lines
                            self.command_text_lines = [ ]
                            lines.append(line)
                            command = string.strip(string.join(lines,'\n'))
                            self.do(command)
                            self.show_command_line()
                        continue

                    if char == chr(4):
                        self.hide_command_line()
                        self.show(_('Entering shell (Circle is still running)\n'))

                        self.lock.acquire()
                        old_quiet = self.quiet
                        old_activity = self.activity
                        self.lock.release()

                        if not old_quiet:
                            self.set_status(1,'(shell)')
        
                        command = 'exec $SHELL'
                        status = utility.get_config('text_status',{ })
                        if status.get('directory',None):
                            command = 'cd '+utility.quote_for_shell(status['directory'])+' && '+command
                            check_directory = 0
                        else:
                            check_directory = 1

                        try:
                            self.do('//'+command)
                            self.show('\n')
                        finally:
                            self.show_command_line()
                        
                        if check_directory:
                            status = utility.get_config('text_status',{ })
                            if not status.has_key('directory'):
                                self.show(_(
                                    "Current working directory was not saved.\n"+\
                                    "Suggest adding `circle -s` to your shell prompt (see /help).\n"))

                        if not old_quiet:
                            self.set_status(old_quiet,old_activity)

                        continue

                    if ord(char) < 32:
                        continue
                    
                    if char == chr(127):
                        if self.command_text:
                            self.command_text = self.command_text[:-1]
                            self.output.write(chr(8)+' '+chr(8))
                            self.output.flush()
                            #self.text_backspace(1)
                    else:
                        self.output.write(char)
                        self.output.flush()
                        self.command_text = self.command_text + char

        finally:
            utility.set_config('text_status',{'running':0})
            self.hide_command_line()


    def do(self, str):
        """ Execute a chat command. """        
        
        str_aug = chr(128) * len(str)

        #str = string.strip(str)
        while str[:1] in [' ','\n','\t']:
            str = str[1:]
            str_aug = str_aug[1:]
        while str[-1:] in [' ','\n','\t']:
            str = str[:-1]
            str_aug = str_aug[:-1]

        try:
            if not str:
                pass

            elif str[:2] == '//':
                self.run_shell(str[2:])

            elif str[0] == '/':
                # pjm: I'm not sure what we should do if str is just "/" or
                # is "/ blah", and whether the behaviour should depend
                # on whether "/blah" would be a valid command.
                # Usually the user would mean "/say /" (or "/say / blah").
                # Versions of circle up to 0.31 implicitly treat "/ blah"
                # the same as "/blah" (due to the behaviour of string.split).
                if ((str == '/') or (str[1] in string.whitespace)):
                    list = ['', string.lstrip(str[2:])]
                else:
                    list = string.split(str[1:], maxsplit=1)
                command = self._commands.get(list[0])
                if command is None:
                    raise error.Error(
                        _("Unknown command /%s.\n"\
                          +"Type /help for help on available commands.") % list[0])

                if len(list) == 2:
                    remainder = list[1]
                else:
                    remainder = ''

                if list[0] in ['ls','play','get']:
                    
                    param = string.split(remainder)
                    # filenames may include whitespaces
                    for i in range(len(param)-1):
                        if param[i][-1:]=='\\':
                            param[i+1] = param[i][:-1]+' '+param[i+1]
                            param[i]=''
                    while '' in param:
                        param.remove('')

                else:
                    if command[1]:
                        param = string.split(remainder,maxsplit=command[1]-1)
                    else:
                        if remainder:
                            raise error.Error(_("/%s doesn't accept parameters.\n"\
                                                +"Type /help for descriptions of commands.") % list[0])
                        param = [ ]

                if len(param) < command[0]:
                    raise error.Error(_('/%s requires at least %d parameters.\n'\
                                        +'Type /help for help on command usage.')%(list[0],command[0]))

                check.check_matches(param, ['text'])
                check.check_assertion(command[0] <= len(param))
                if command[1] != -1:
                    check.check_assertion( len(param) <= command[1])

                if command[2].func_code.co_argcount == 3:
                    # Command uses augmentation
                    apply(command[2],(self,param,str_aug[-len(param[-1]):]))
                else:
                    # Command does not use augmentation
                    apply(command[2],(self,param))
            
            elif str[0] == '!':
                file = cStringIO.StringIO()
                stdout = sys.stdout
                stderr = sys.stderr
                sys.stdout = file
                sys.stderr = file
                try:
                    try:
                        result = eval(str[1:],self.exec_vars)
                        if result is not None:
                            print `result`
                    except SyntaxError:
                        exec str[1:]+'\n' in self.exec_vars
                except:
                    traceback.print_exc()
                    if len(str) > 10:
                        short_str = str[:7] + '...'
                    else:
                        short_str = str
                    #print _("(Perhaps you meant `/say %s' ?)" % short_str)
                sys.stdout = stdout
                sys.stderr = stderr
                self.show(file.getvalue())
                
            elif self.channel == [ ]:
                self.show("message: %s\n"%str)
            else:
                self.send_message(self.channel[:], str, None, str_aug)
        
        except error.Error, err:
            self.show(err.message+'\n')
        
        self.set_prompt()



    def register(self, name, min_param, max_param, function):
        """ Register a command. 
        """
        check.check_has_type(name, types.StringType)
        check.check_has_type(min_param, types.IntType)
        check.check_has_type(max_param, types.IntType)
        check.check_is_callable(function)
        check.check_assertion(0 <= min_param)
        #check.check_assertion(min_param <= max_param)
        
        self.lock.acquire()
        self._commands[name] = (min_param, max_param, function)
        self.lock.release()


    def show_interior(self, root):

        def show_interior_thread(root, self):

            size=0
            stats=''
            root.still_searching=1
            sleep_time= 0.01
            list = []
            while root.list:
                root.list.remove(root.list[0])
            while root.still_searching:

                yield 'sleep',sleep_time
                sleep_time=sleep_time*1.25
                root.update(self.app)
                children = root.get_children()

                for leaf in children:
                    if leaf not in list:
                        if leaf.item['type']=='directory':
                            leaf.expanded=0
                        elif leaf.item['type']== 'file':
                            size=size+leaf.item['length']

                        root.list.append(leaf)
                        number=len(root.list)
                        self.show("%d "%number + leaf.get_text()) 
                        list.append(leaf)

                root.update(self.app)

            root.pipe.stop()
            
            stats='    '*root.depth()+'%d %s'%(len(root.list),root.what)
            if root.what=='files':
                stats=stats +', '+utility.human_size(size)
            if not root.list:
                stats='    '*root.depth()+root.empty_text
            if len(root.list)==1:
                stats='    '*root.depth()+root.single_text                
            self.show(stats+'.')


        utility.start_thread(show_interior_thread(root,self))




    #
    # inherited methods from Chat

    def is_visible(self):
        """ returns true iff we can display messages  """
        return 1

    def set_prompt(self):
        str = self.get_chat_prompt()
        self.lock.acquire()
        try:
            if str == self.prompt:
                return
            
            self.hide_command_line()
            self.prompt = str
            self.show_command_line()
        finally:
            self.lock.release()
        return


    def handle_watch(self, acq, because_of, **extras):

        acq.lock.acquire()
        try:
            nickname = acq.nickname
            watch    = acq.watch
        finally:
            acq.lock.release()

        if because_of == 'edit':
            self.lock.acquire()
            try:
                new_channel = filter(
                    lambda dest: dest[:1] == '#' or \
                    self.app.name_server.nicknames.has_key(dest),
                    self.channel)
            finally:
                self.lock.release()

            self.set_channel(new_channel)
            # Proof of @R49: new_channel subsetof self.channel; @I31.

        elif acq != self.app.name_server.me:
            self.app.refresh_userlist()
            
        if not watch or (because_of not in [ 'connect','disconnect','status changed'] ):
            return

        self.lock.acquire()
        try:
            if not self.quiet:
                if because_of == 'connect':
                    action = _(' just arrived.\n')
                elif because_of == 'status changed':
                    s = acq.status.get('chat')
                    if not s: return
                    if not s[1]: return
                    action = ' '+s[1]+'\n'
                elif because_of == 'no reply':
                    action = _(' does not reply.\n')
                else:
                    if extras['message']:
                        action = _(' just left: ') + extras['message'] + '\n'
                    else:
                        action = _(' just left.\n')
                self.show(time.strftime(_('%I:%M %p' ),time.localtime(time.time())) +nickname+action)
        finally:
            self.lock.release()


    def show_received_message(
        self,sender_name,sender_key_name,address,recipients,
        text,verify_text,verify_sig,quiet,
        send_time,augmentation,has_attachment,attachment):

        time_str = time.strftime(_('%I:%M %p' ),time.localtime(time.time()))

        str = '[' + sender_name + ' >> ' 
        for item in recipients:
            str = str+ item[2] +' '
        str = str[:-1] +'] '+ text +' '+time_str
        self.show(str)
    

    def create_message_id(self):
        """
        return an identifier for a chat message sent.
        the id will be used by update_message_status
        it may be of any type you wish
        """
        pass

    def update_message_status(self, message_id, status, n=0):
        pass
    



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
