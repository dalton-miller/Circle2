#    The Circle - Decentralized resource discovery software
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


# chatgtk.py
#
# All messages in the chat widget are displayed in "fields",
# eg a field may display a message indicating some task is in progress, 
# then later change to say that it has finished
#
# fields are defined in fterm.py



# about tickets and xml: some fields use tickets
# this should be for external applications,
# as they cannot share their data...
# for those, there should be a way to pass parameters
#
#
# it does not make sense to use xml for fields that share internal data
# for efficiency reasons

# for external applications: define a particular
# class of field, that does the IO stuff



from __future__ import generators
import gtk, string, types, os, re, cStringIO, sys, traceback, time
from circlelib.chat import Chat
from circlelib import search, error, check, utility, name_server, hash, settings
import widgets, searcher, chat_commands, fterm

from fterm import Field,Active_Field

class Chat_gtk(Chat):

    # show: methods that use a field
    def show_at(self,field,str,opt=[]):
        field.show(str,opt)

    def show(self,str,tags='grey',augmentation=None):
        #type, str_options = self.format_options(options)
        #constructor = self.fterm.markers[type]
        return self.fterm.show(str,tags,augmentation)

    def show_before(self,field,str,options={'type':'field'}):
        type, str_options = self.format_options(options)
        constructor = self.fterm.markers[type]
        return self.fterm.show_before(field,str,constructor)

    def show_after(self,field,str,options={'type':'field'}):
        type, str_options = self.format_options(options)
        constructor = self.fterm.markers[type]
        return self.fterm.show_after(field,str,constructor)

    def get_field(self,type='field'):
        constructor = self.fterm.markers[type]
        return self.fterm.get_field(constructor)

    def get_field_before(self,field,type='field'):
        constructor = self.fterm.markers[type]
        return self.fterm.get_field_before(field,constructor)

    def get_field_after(self,field,type='field'):
        constructor = self.fterm.markers[type]
        return self.fterm.get_field_after(field,constructor)


    # show: xml methods, they use a ticket
    def show_t_at(self,field,str,options=None):
        type, str_options = self.format_options(options)
        str='<'+type+' ref="'+field+'"'+str_options+'>'+str+'</'+type+'>'
        self.fterm.show_xml(str)

    def show_t(self,str,options=None):
        me=self.get_ticket()
        type, str_options = self.format_options(options)
        str='<'+type+' ref="'+me+'"'+str_options+'>'+str+'</'+type+'>'
        self.fterm.show_xml(str)
        return me

    def show_t_after(self,after,str,options=None):
        me=self.get_ticket()
        type, str_options = self.format_options(options)
        str='<'+type+' ref="'+me+'"'+' after="'+after+'"'+str_options+'>'+str+'</'+type+'>'
        self.fterm.show_xml(str)
        return me

    def show_t_before(self,before,str,options=None):
        me=self.get_ticket()
        type, str_options = self.format_options(options)
        str='<'+type+' ref="'+me+'"'+' before="'+before+'"'+str_options+'>'+str+'</'+type+'>'
        self.fterm.show_xml(str)
        return me

    def get_t_field(self):
        return self.show_t('')

    def get_t_field_before(self,before):
        return self.show_t_before(before,'')

    def get_t_field_after(self,after):
        return self.show_t_after(after,'')

    def get_ticket(self):
        self.field_ticket += 1
        ticket="field-%d"%self.field_ticket
        return ticket

    def format_options(self,options):
        str_options=''
        type='field'
        while options:
            key,val=options.popitem()
            if key not in ['type']:
                str_options+=' '+key+'="'+val+'"'
            else:
                type = val
        return type,str_options



    def is_visible(self):
        return self.fterm.widget_visible


    def show_interior(self, root, first_field,show_url=0):
        """displays a list"""

        def show_interior_thread(root, self, first_field,show_url):

            root.first_field=first_field
            root.last_field=self.get_field_after(first_field)

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
                if children:
                    children = children[:]
                    children.sort(lambda x,y: cmp(x.get_comparator(),y.get_comparator()))
                field=root.first_field

                for leaf in children:
                    if leaf in list:
                        field=leaf.field
                    else:
                        if leaf.item['type']=='directory':
                            leaf.expanded=0
                        elif leaf.item['type']== 'file':
                            size=size+leaf.item['length']

                        field=self.get_field_after(field)
                        if not field:
                            return
                        leaf.field=field
                        # ok, this is ugly...
                        if leaf.item['type']=='file' and leaf.item.get('name'):
                            for d in self.app.file_server.downloaders:
                                if d.data['name']==leaf.item['name']:
                                    d.fields.append(leaf.field)

                        root.list.append(leaf)
                        #if root.show_number:
                        #    number=len(root.list)
                        #else:
                        #    number=0
                        number=0
                        self.show_leaf(leaf,root.depth(),show_url,number)
                        list.append(leaf)
                    stats='    '*root.depth()+'%d %s'%(len(root.list),root.what)
                    if root.what=='files':
                        stats=stats +', '+utility.human_size(size)
                if not root.list:
                    stats='    '*root.depth()+root.empty_text
                if len(root.list)==1:
                    stats='    '*root.depth()+root.single_text                
                root.last_field.show(stats+'...\n')
                root.update(self.app)

            root.last_field.show(stats+'.\n')
            root.pipe.stop()

        utility.start_thread(show_interior_thread(root,self,first_field,show_url))


    def show_leaf(self, leaf, depth, show_url, number):

        if leaf.type == 'directory':

            self.show_before(leaf.field, '    '*depth)
            if number:
                self.show_before(leaf.field, '%d. '% number)
            self.app.idle_add(self.fterm.set_tabs,len(leaf.get_text())+3)        
            leaf.file_field = self.show_before(
                leaf.field, utility.force_unicode(leaf.get_text()),{'type':'directory'})
            leaf.file_field.root = leaf

            self.show_before(leaf.field,'\t--')
            self.show_before(leaf.field,'\tdirectory\n')

        elif leaf.type == 'identity':

            def show_address(leaf):
                if leaf.address:
                    if leaf.show_ip:
                        host = leaf.address[0]
                    else:
                        import socket
                        try:
                            host = socket.gethostbyaddr(leaf.address[0])[0]
                        except:
                            host = leaf.address[0]
                    leaf.address_field.show(host+':%d'%leaf.address[1])
                else:
                    leaf.address_field.show('offline')
                    leaf.address_field.set_active(0)

            self.show_before(leaf.field, '    '*depth)
            if number: self.show_before(leaf.field, '%d. '% number)
            
            field = self.show_before(leaf.field, leaf.item.get('name'),{'type':'person'})
            field.data = leaf.item

            if leaf.item.get('human-name'):
                self.show_before(leaf.field, ' (%s)'% leaf.item.get('human-name'))

            if show_url:
                if show_url==1:
                    leaf.show_ip=1
                else:
                    leaf.show_ip=0
                self.show_before(leaf.field, '\t ')
                leaf.address_field = self.get_field_before(leaf.field,'host')
                leaf.on_new_address =  lambda leaf=leaf: show_address(leaf)
                leaf.self=self
                show_address(leaf)

            self.show_before(leaf.field, '\n')
            # this is gui: we should send delimiters for the array
            self.app.idle_add(self.fterm.set_tabs,len(leaf.item.get('name')+leaf.item.get('human-name'))+6)

        elif leaf.type == 'file':

            self.show_before(leaf.field, '    '*depth)
            if number:
                str='%d. '%number
            else:
                str=''
            self.show_before(leaf.field, str)
            if leaf.item.get('name'):
                attr = {'type':'file',
                        'filename':leaf.item['filename'],
                        'url':hash.hash_to_url(leaf.item['name'])}
            else:
                attr = {'type':'file',
                        'filename':leaf.item['filename'],
                        'path':leaf.item['local_path']}
            leaf.file_field = self.show_before(
                leaf.field,utility.force_unicode(leaf.title),attr)
            leaf.file_field.leaf = leaf

            self.show_before(leaf.field, ' \t')
            self.app.idle_add(self.fterm.set_tabs,len(leaf.title)+3)
            self.show_before(leaf.field, utility.human_size(leaf.item['length'])+' \t')

            if leaf.item.get('mime'):
                mime_str=leaf.item.get('mime').replace(' \x08','')
            else:
                mime_str='unknown    '
            self.show_before(leaf.field,mime_str+' \t')
            if leaf.item.get('bitrate'):
                self.show_before(leaf.field,' %dKb/s'%leaf.item.get('bitrate')+' \t')

            leaf.field.show('\n')






    def __init__(self,app):

        Chat.__init__(self,app)

        # Command registry
        self._commands = { }  # name -> (min n. params, max n. params, function)
        chat_commands.register_commands(self)

        self.mode = 'chat_mode' #can be chat_mode or shell_mode

        self.field_ticket=0

        # Field Terminal
        self.fterm = fterm.FTerm(self.app,self)
        self.fterm.register_marker('gossip', Gossip_Field)
        self.fterm.register_marker('link',   Link_Field)
        self.fterm.register_marker('channel',Channel_Field)
        self.fterm.register_marker('url',    URL_Field)
        self.fterm.register_marker('file',   File_Field)
        self.fterm.register_marker('tip',    Tip_Field)
        self.fterm.register_marker('host',   Host_Field)
        self.fterm.register_marker('command',Command_Field)
        self.fterm.register_marker('directory', Directory_Field)
        self.fterm.register_marker('take',   Take_Field)
        self.fterm.register_marker('person', Person_Field)


        #selection
        self.selected_files = []

        # Shell command support
        self.shell = None   # (pid, write_pipe)        
        try:
            openpty = None
            try:
                from pty import openpty
            except:
                from os import openpty
            self.shell_master, self.shell_slave = openpty()
            
            def callback(source, condition, fd=self.shell_master, self=self):
                """
                There is one chat field for each running command: self.shell_field
                escape commands are allowed within that field
                """
                try:
                    str = os.read(fd,256)
                except OSError:
                    str = ''
                #str = string.replace(str,'\r','')
                
                #for the moment we do not have local tabs
                #therefore we better convert tabs into spaces
                str = string.replace(str,'\t','    ')
                
                if string.find(str,chr(7)) != -1:
                    str = string.replace(str,chr(7),'')
                    utility.beep()

                #here I can insert xml tags, (for colors, for example)

                new_text = self.shell_field.text
                m = re.search(r'\x1B\[\d*;?\d*[a-zA-Z@:#~ ]', str)
                while m:
                    escape = m.group()
                    if escape[:-1] == 'H':
                        print "home"
                        if escape == '\x1B[H':
                            index = 0
                        elif re.match(r'\x1B\[\d*;\d*H'):
                            index = 0

                    new_text = new_text+str[0:m.start()]
                    str = str[m.end():]
                    m = re.search(r'\x1B\[\d*;?\d*[a-zA-Z@:#~ ]', str)
                
                new_text = new_text + str
                utility.force_unicode(new_text)
                    
                self.shell_field.show(new_text, ['monospace'])
                return 1

            self.shell_tag = gtk.input_add(self.shell_master,gtk.gdk.INPUT_READ,callback)
        
            import termios

            attr = termios.tcgetattr(self.shell_slave)
            attr[3] = attr[3] & ~termios.ECHO
            termios.tcsetattr(self.shell_slave,termios.TCSANOW,attr)
        except:
            self.shell_master = None
            self.shell_slave  = None


        # Second shell command support
        self.bgshell = None   # (pid, write_pipe)
        self.bgshell_current_path='.'
        try:
            openpty = None
            try:
                from pty import openpty
            except:
                from os import openpty

            self.bgshell_master, self.bgshell_slave = openpty()
            self.bgshell_tag = gtk.input_add(
                self.bgshell_master,gtk.gdk.INPUT_READ,callback_bgshell,self)

            import termios
            attr = termios.tcgetattr(self.bgshell_slave)
            attr[3] = attr[3] & ~termios.ECHO
            termios.tcsetattr(self.bgshell_slave,termios.TCSANOW,attr)
        except:
            self.bgshell_master = None
            self.bgshell_slave  = None

    def run_shell(self, command):
        """run a command in a shell"""

        if self.shell_master == None:
            self.show( _("No openpty in pty module.\n"))
            return


        self.shell_field = self.fterm.get_field()
        try:
            pid = os.fork()
        except:
            self.show(_("Could not fork.\n"))
            return        

        if not pid:
            os.dup2(self.shell_slave, 0)
            os.dup2(self.shell_slave, 1)
            os.dup2(self.shell_slave, 2)
            os.execlp('/bin/bash','/bin/bash','-c',command)
            os._exit(0)

        self.shell = pid
        self.fterm.enter_direct_mode()

        def timeout(self=self,pid=pid):
            result = os.waitpid(pid,os.WNOHANG)
            if result[0] == pid:
                self.shell = None
                self.set_prompt()
                self.fterm.enter_command_mode()
                return 0
            return 1

        gtk.timeout_add(150, timeout)



    def handle_tabulation_key(self, prefix, _e):

        # auto-completions

        # in chat mode, only if there is a command prefix
        if self.mode == 'chat_mode':
            if not prefix:
                if self.fterm.completion_field:
                    self.fterm.completion_field.show('')
                return gtk.TRUE            
            if prefix[0] !='/':
                if self.fterm.completion_field:
                    self.fterm.completion_field.show('')
                return gtk.TRUE

        words=prefix.split()
        # filenames may include whitespaces
        for i in range(len(words)-1):
            if words[i][-1:]=='\\':
                words[i+1] = words[i][:-1]+' '+words[i+1]
                words[i]=''
        while '' in words:
            words.remove('')

        choices = []
        # extract the last word
        if words:
            last_word=words[-1:][0]
        else:
            last_word=''
        if prefix[-1:]==' ':
            if prefix[-2:] !='\\ ':
                last_word=''

        if self.bgshell:
            if last_word:
                path = last_word.split('/')
                dir = string.join([self.bgshell_current_path]+path[:-1],'/')
            else:
                dir=self.bgshell_current_path
            print "lw,dir is ",last_word," ",dir
            choices = os.listdir(dir)
            suffix = ''
        else:
            if len(words) == 1 and prefix[-1:] != ' ':
                choices=self._commands.keys()
                for i in range(len(choices)):
                    choices[i]='/'+choices[i]
                suffix=' '
            else:                
                command = prefix.split()[0]
                if command not in ['/ls','/cd','/join',
                                   '/forget','/remember',
                                   '/look','/listen','/get',
                                   '/play','/help','/who']:
                    return 

                if command in ['/ls','/cd','/join','/forget','/remember','/look','/listen']:
                    choices=self.app.name_server.nicknames.keys()
                    for id in self.identity_list:
                        nick=id.item['name']
                        if nick not in choices:
                            choices.append(nick)

                if command in ['/join','/listen','/who']:
                    for ch in self.channels.list.keys():
                        if ch not in choices:
                            choices.append(ch)

                if command in ['/help']:
                    choices=self._commands.keys()
                    for i in range(len(choices)):
                        choices[i]='/'+choices[i]
                        suffix=' '

                for i in range(len(choices)):
                    if command in ['/ls','/cd']:
                        choices[i]=choices[i]+':'
                        suffix=''
                    else:
                        choices[i]=choices[i]
                        suffix = ' '

                if command in ['/ls','/cd']:
                    choices.append(':')
                    for dir in search.visited_directories:
                        if dir.find(last_word)==0:
                            z = dir[len(last_word):]
                            colon_index = z.find(':')
                            slash_index = z.find('/')
                            if colon_index !=-1:
                                z = z[:colon_index+1]
                            elif slash_index != -1:
                                z= z[:slash_index+1]
                            completion = last_word+z
                            if completion not in choices:
                                choices.append(completion)

                if command in ['/play','/get']:
                    for file in self.file_list:
                        filename = utility.force_unicode(file.item['filename'])
                        if filename not in choices:
                            choices.append(filename)
                    suffix=' '

        choices.sort()
        root, completions = utility.complete(last_word,choices)
        if len(completions)>1:
            str=''
            for i in completions:
                colon_index = last_word.rfind(':')
                slash_index = last_word.rfind('/')
                if slash_index !=-1:
                    i = i[slash_index+1:]
                elif colon_index != -1:
                    i = i[colon_index+1:]
                str=str+i+'   '
            if self.fterm.completion_field == None:
                self.fterm.completion_field=self.fterm.get_field()
            self.fterm.completion_field.show(str+'\n','grey')
        else:
            if self.fterm.completion_field:
                self.fterm.completion_field.show('')

        if last_word == '':
            suffix = ''

        if len(completions)!=1:
            suffix = ''

        self.fterm.lock.acquire()
        i=self.fterm.buffer.get_end_iter()
        self.fterm.buffer.insert(i,root[len(last_word):].replace(' ','\\ ')+suffix)
        self.fterm.lock.release()

        return gtk.TRUE


    def handle_control_key(self, prefix, _e):
      
            if self.shell != None:
           
                if _e.keyval == ord('c'): #Ctrl-C
                    self.fterm.lock.acquire()
                    try:
                        os.kill(self.shell,2)
                        self.fterm.view.emit_stop_by_name("key-press-event")
                    except OSError:
                        pass
                    self.fterm.lock.release()
                return

            # this pushes prefix in the stack
            # useful if you want to postpone a message or command
            if _e.keyval == ord('o'): #Ctrl-O
                if prefix:
                    self.fterm.history[-1] = prefix
                    self.fterm.history.append('')
                    self.fterm.history_position = len(self.fterm.history)-1
                    self.fterm.buffer.delete(
                        self.fterm.buffer.get_iter_at_offset(self.fterm.prompt_end),
                        self.fterm.buffer.get_end_iter())

            if prefix:
                return
            
            if _e.keyval == ord('x'):
                self.fterm.insert_at_end('/exit ')
            elif _e.keyval == ord('s'): 
                self.fterm.insert_at_end('/search ')
            elif _e.keyval == ord('f'):         
                self.fterm.insert_at_end('/find ')            
            elif _e.keyval == ord('j'):           
                self.fterm.insert_at_end('/join ')
            elif _e.keyval == ord('m'):
                self.fterm.insert_at_end('/me ')
            elif _e.keyval == ord('w'):
                self.fterm.insert_at_end('/who ')

            elif _e.keyval == ord('l'):
                self.fterm.clear()
                self.set_prompt()

            elif _e.keyval == ord('d'): #Ctrl-D
                if self.mode == 'chat_mode':
                    self.mode = 'shell_mode'
                    self.run_bgshell()
                    self.fterm.set_prompt('>>')
                elif self.mode == 'shell_mode':
                    try:
                        os.kill(self.bgshell,9)
                        self.fterm.view.emit_stop_by_name("key-press-event")
                    except OSError:
                        pass
                return



            #elif _e.keyval == ord('a') and (_e.state & 5): # Ctrl-A
            #    self.buffer.place_cursor(cmd_line)
            #    return gtk.TRUE
            #
            #elif _e.keyval == ord('k') and (_e.state & 5): # Ctrl-K
            #    eol = insertion.copy()
            #    eol.forward_line()
            #    self.buffer.delete(insertion, eol)
            #    return gtk.TRUE


    def handle_direct_mode(self,str):
        if self.shell:
            try:
                while str:
                    n = os.write(self.shell_master,str)
                    str = str[n:]
            except OSError:
                print "error in direct mode"


    def handle_user_entry(self, str, str_aug=None):
        """ Handler user typing enter key.

        in case of shell, forward immediately
        in case of line, buffer line
        """
        if self.shell:
            self.fterm.set_prompt('')
            str = str + '\n'
            try:
                while str:
                    n = os.write(self.shell_master,str)
                    str = str[n:]
            except OSError:
                pass
            return

        if self.bgshell:
            self.fterm.set_prompt('')
            self.fterm.enter_direct_mode()
            str = str + '\n'
            try:
                while str:
                    n = os.write(self.bgshell_master,str)
                    str = str[n:]
            except OSError:
                pass
            return
            
        self.do(str, str_aug)





    def do(self, str, str_aug=None):
        """ Execute a chat command. """        

        if not str_aug:
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
                        _("Unknown command '/%s'.\nType <command>/help</command> for help on available commands.")%list[0] )

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
                                  +"Type <command>/help %s</command> for more help.") % (list[0],list[0]))
                        param = [ ]

                if len(param) < command[0]:
                    raise error.Error(_('/%s requires at least %d parameters.\n'\
                                        +'Type <command>/help %s</command> for more help.')\
                                      %(list[0],command[0],list[0]))

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
                sys.stdout = stdout
                sys.stderr = stderr
                self.fterm.show(file.getvalue())
                
            elif self.channel == [ ]:
                self.show_xml_file("ixml/empty_channel.xml")
            else:
                self.send_message(self.channel[:], str, None, str_aug)
        
        except error.Error, err:
            self.fterm.show_xml(err.message+'\n\n')
        
        self.set_prompt()






    def set_prompt(self):
        tags = ['people']
        if self.quiet:
            tags = ['quiet']
        if self.shell:
            str = ''
        elif self.bgshell:
            str='>>'
        else:
            str = self.get_chat_prompt()

        self.fterm.set_prompt(str,tags)
    

    def run_bgshell(self):
        #
        # note: I need to detect the beginning/end of the execution of a command
        # the clean way to do this is to modify readline, add escape sequences that delimit
        # the beginning and the end of execution of a comand (and the prompt too)
        #
        # maybe the current bash can do it without being recompiled:
        # it is sufficient to detect the prompt

        if self.bgshell:
            self.show( _("Shell already running.\n"))
            return

        if self.bgshell_master == None:
            self.show( _("No openpty in pty module.\n"))
            return

        self.bgshell_field = None #self.fterm.get_field()
        
        try:
            pid = os.fork()
        except:
            self.show(_("Could not fork.\n"))
            return        

        if not pid:
            os.dup2(self.bgshell_slave, 0)
            os.dup2(self.bgshell_slave, 1)
            os.dup2(self.bgshell_slave, 2)
            os.execlp('/bin/bash','/bin/bash','--rcfile',utility.find_file('bashrc-circleshell'))
            os._exit(0)

        self.bgshell = pid
        def timeout(self=self,pid=pid):
            result = os.waitpid(pid,os.WNOHANG)
            if result[0] == pid:
                self.bgshell = None
                self.mode = 'chat_mode'
                self.set_prompt()
                self.fterm.enter_command_mode()
                return 0
            return 1

        gtk.timeout_add(250, timeout)


    def show_xml_file(self,name, index_field=None):
        try:
            file_name = utility.find_file(name)
            file = open(file_name,"rt")
            str = file.read()
            file.close()
        except:
            str = "Error: file not found: %s\n\n"%name
            
        #try:
        self.fterm.show_xml(str, index_field)
        #except:
        #    self.show("parsing error in %s\n\n")%name


    def start(self):


        Chat.start(self)

        self.app.refresh_userlist()
        if self.app.config['show_tips']:
            self.show_tip()

        if self.app.gossip and self.app.config['show_gossip']:
            title_field = self.show('Fetching gossip...\n')
            gossip_fields = []
            for i in range(5):
                field = self.get_field('gossip')
                gossip_fields.append(field)

            def on_gossiped(title_field=title_field,gossip_fields=gossip_fields,
                            self=self,gossip=self.app.gossip):
                n = 0
                for item in gossip.sorted_wodges()[:100]:
                    if not item[1].collapsed:
                        self.show_at(
                            gossip_fields[n],
                            item[1].wodge['subject']+'\n')
                        n = n + 1
                        if n >= 5: 
                            break
                for i in range(5-n):
                    self.show_at(gossip_fields[4-i],'')
                    #gossip_fields[4-i].close()
                
                if n == 0:
                    str = ''
                else:
                    str="Today's hot gossip:\n"
                self.show_at(title_field,str, ['bold'])
                #title_field.close()
            self.app.gossip.request_update(on_gossiped)

        offline_field=self.show(
            _('Retrieving any messages sent while you were offline...\n'))
        def on_complete(self,any,offline_field=offline_field):
            if any:
                self.show_at(
                    offline_field,
                    _('\nYou received messages while you were offline. Type /read to read them.\n'))
                self.set_prompt()
            else:
                self.show_at(offline_field,'\n')

        self.retrieve_cached_messages(on_complete)

        if self.quiet or self.activity != '':
            self.show('\n')
            self.show_status()


    def create_message_id(self):
        field = self.show(_('Sending message...\n'))
        self.show_after(field,'\n')
        return field

    def update_message_status(self, field, status, offline=0):
        if not offline:
            field.show(status)
        else:
            field.next.show(status)


    def show_tip(self):
        import random
        tip_field = self.get_field('tip')
        tip_field.show('Tip: ')
        self.show_after(tip_field,random.choice(settings.tips)+'\n\n')


    def show_received_message(self,sender_name,sender_key_name,address,recipients,
                              text,verify_text,verify_sig,quiet,
                              send_time,augmentation,has_attachment,attachment):
        
        field1=self.show('[')
        # Until we work out who they really are...
        field_sender = self.show_after(field1,'<'+sender_name+'>',{'type':'person'})
        field_sender.set_active(0)
        field_middle = self.show_after(field_sender,' >> ')
        field_right = self.show_after(field_middle,' ...] ')

        field = self.get_field_after(field_right) 

        while 1:
            match = re.search('(http:|ftp:|circle-file:)[^ \t\n]*',text)
            if not match:
                break
            
            match_start, match_end = match.span()
            field.show(text[:match_start],[],augmentation)

            if text[match_start:match_start+4] in ['http','ftp:']:
                link_field = self.get_field_after(field,'url')
            elif text[match_start:match_start+12] == 'circle-file:':
                def lookup_url_thread(self,field,name):
                    from circlelib import search
                    pipe = self.app.node.retrieve(name)
                    root = search.Search_tree_interior(
                        lambda self=self: pipe, [], [], 'file','',
                        '', _(': couldn\'t find anything, sorry'),'')
                    sleep_time=0.1
                    while root.still_searching:
                        yield 'sleep',sleep_time
                        sleep_time=sleep_time*1.25
                        root.update(self.app.node)
                    if root.get_children():
                        leaf = root.get_children()[0]
                        searcher.set_leaf_player(leaf,self.app)
                        field.leaf = leaf
                        leaf.file_field = field
                        field.show('%s'%leaf.get_text()+' ') 
                        leaf.field=self.get_field_after(field)
                    else:
                        field.show('%s' % field.text)
                    pipe.stop()
                try:
                    name=hash.url_to_hash(text[match_start:match_end])
                    link_field = self.get_field_after(field,'file')
                    utility.start_thread(lookup_url_thread(self,link_field,name))
                except:
                    link_field = self.get_field_after(field)
                    
            link_field.show(text[match_start:match_end])
            
            field = self.get_field_after(link_field)
            text = text[match_end:]
            augmentation = augmentation[match_end:]

        field.show(text,[],augmentation)
        field3 = self.get_field_after(field)

        now_date  = time.strftime(_('%A %B %d, %Y'),time.localtime(time.time()))
        then_date = time.strftime(_('%A %B %d, %Y'),time.localtime(send_time))

        if now_date != then_date:
            date_str = '\n'+then_date+' '
        else:
            date_str = '  '
        date_str = date_str + time.strftime(_('%I:%M %p'),time.localtime(send_time))
                        
        if has_attachment:
            self.lock.acquire()
            i = 1
            while self.exec_vars.has_key("%s%d" % (sender_name, i)):
                i = i + 1
            self.exec_vars["%s%d"        % (sender_name, i)] = attachment
            self.exec_vars["%s%d_source" % (sender_name, i)] = address
            self.lock.release()
            if type(attachment) == type({}) and attachment.get('type',None) == 'file':

                field3_extra = _('\nContains attachment: '+attachment['filename']\
                                 +"; type `!%s%d\' to see its details, type `"%(sender_name,i))
                self.show_before(field3, date_str + field3_extra, {'tags':'light_grey'})
                self.show_at(field3,'/take %s%d'%(sender_name,i)) 
                field4=self.show_after(field3,_("' to retrieve it\n\n"))
            else:
                field3_extra = _('\nContains attached python object; type `!%s%d\' to see.') % (sender_name,i)
        else:
            self.show_at(field3,date_str + '\n\n', ['light_grey'])

        if not quiet and self.app.config['beep_on_message']:
            utility.beep()

        previous_field = field_middle
        
        for item in recipients:
            if not check.matches(item, ('any', 'opt-address')):
                sys.stderr.write('chat_receive_task passed bad item in recipients list: '
                                 + `item` + '.  Ignoring this item.\n')
                continue

            
            recipient_key_name,recip_address = item[0],item[1]
            if recipient_key_name==None and len(item)>=3 and item[2][0]=='#':
                #if self.app.config['auto_list_channels']:  # kc5tja, 22jul2002
                #    self.channels.sub(item[2], 1)
                field_recipient = self.get_field_after(previous_field,'channel')
                field_recipient.show(' '+item[2])
                previous_field = field_recipient
                continue

            field_recipient = self.get_field_after(previous_field,'person')
            previous_field = field_recipient

            def show_recipient(recipient,field_recipient=field_recipient,self=self):
                if recipient:
                    field_recipient.show(' ' + recipient.nickname)
                    field_recipient.name = recipient.name
                    field_recipient.set_active(1)
                else:
                    if len(item) >= 3:
                        bad_nick_str = ' <'+item[2]+'>'
                    else:
                        bad_nick_str = ' ?'
                    field_recipient.show(bad_nick_str,['grey'])
                    field_recipient.set_active(0)

            # this should be moved in chat.py
            self.identify(recipient_key_name, recip_address, show_recipient)
            
        field_right.show('] ')

        def show_sender(sender,field_sender=field_sender,self=self):
            if sender:
                try:
                    sender.verify(verify_text,verify_sig)
                    field_sender.show(sender.nickname)
                    field_sender.name = sender.name
                    field_sender.set_active(1)
                except error.Error:
                    self.show_at(field_sender,'IMPOSTER '+sender.nickname.upper(), ['red'])

        self.identify(sender_key_name,address,show_sender)


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
                self.show(time.strftime(_('%I:%M %p') + ' ',time.localtime(time.time())),'light_grey')
                field = self.get_field('person')
                field.show(nickname)
                field.name = acq.name
                self.show_after(field,action)
        finally:
            self.lock.release()



    def register(self, name, min_param, max_param, function):
        """ Register a command. 
        
                A command takes a certain number of parameters separated by spaces,
                up to max_param, and not less than min_param. The last parameter may
                contain spaces.

                function may assert that its argument matches ['text'] (i.e. is
                a list of items each of type string or unicode) and that the
                length of this list is in the range [min_param, max_param].

                E.g.:
                
                def mycommand(chat, params):
                    check.check_matches(params, ['text'])
                    check.check_assertion(1 <= len(params) <= 2)
                    
                    str = 'You typed ' + params[0]
                    if len(params) == 2:
                        str += '; ' + params[1]
                    chat.show(str + '\n')
                app.chat.register('mycommand', 1, 2, mycommand)
                
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




class Person_Field(Active_Field):

    def __init__(self, fterm, start=None, end=None, next=None):
        Active_Field.__init__(self, fterm, start, end, next)
        self.nickname = None
        self.name = None

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'people')
    
    def context_menu(self,app):
        self.identify(app.chat)
        return name_context_menu(app.chat,self.nickname)

    def identify(self,chat):
        """
        this method assumes that if self.name is not set, 
        either name_server knows it or self.data is available
        """
        if not self.nickname:
            if not self.name:
                self.name = name_server.key_name(self.data['key'])
                
            if not chat.app.name_server.acquaintances.has_key(self.name):
                def on_complete(acq,self=self):
                    self.nickname = acq.nickname
                chat.app.name_server.make_acquaintance_sync(
                    self.data,on_complete,chat.app)
                self.nickname = self.data['name']
            else:
                acq = chat.app.name_server.acquaintances[self.name]
                self.nickname = acq.nickname
    
    def on_click(self,chat,widget,event):
        self.identify(chat)
        
        if event.button == 1:
            if event.type == gtk.gdk.BUTTON_RELEASE:
                if self.nickname not in chat.channel:
                    chat.channel.append(self.nickname)
                else:
                    chat.channel.remove(self.nickname)
                chat.set_prompt()
                chat.app.refresh_userlist()
                return gtk.TRUE
            elif  event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE
            return gtk.FALSE
        elif event.type == gtk.gdk.BUTTON_PRESS and event.button==3:
            self.popup_menu(widget,event,chat.app)
            return gtk.TRUE


class Command_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')

    def on_click(self,chat,widget,event):
        if event.button == 1:
            if event.type == gtk.gdk.BUTTON_RELEASE:
                chat.fterm.delete_line()
                chat.fterm.insert_at_end(self.text)
                return gtk.TRUE
            elif event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE
        return gtk.FALSE

class Link_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')

    def on_click(self,chat,widget,event):
        if event.button == 1:
            if event.type == gtk.gdk.BUTTON_RELEASE:
                index  = self.page_end.next
                chat.fterm.delete_fields(self.page_begin,self.page_end)
                path = self.attr['path']
                chat.show_xml_file(path,index)
                return gtk.TRUE
            elif event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE
            return gtk.FALSE

        elif event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popup_menu(widget,event,chat.app)
            return gtk.TRUE

    def context_menu(self,app):
        return  link_context_menu(app,self)
            

class Channel_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')

    def context_menu(self,app):
        return channel_context_menu(app.chat,app.chat.channels,self.text.strip())

    def on_click(self,chat,widget,event):
        app=chat.app
        if event.button == 1:
            if event.type == gtk.gdk.BUTTON_RELEASE:
                name=self.text.strip()
                chat.lock.acquire()
                if name not in chat.channel:
                    chat.channel.append(name)
                else:
                    chat.channel.remove(name)
                if chat.channels.list.has_key(name):
                    chat.app.refresh_userlist()
                chat.set_prompt()
                #chat.widget.set_position(chat.widget.get_length())
                chat.lock.release()
                return gtk.TRUE
            elif event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE
            return gtk.FALSE
        
        elif event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popup_menu(widget,event,chat.app)
            return gtk.TRUE


class URL_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')

    def on_click(self,chat,widget,event):
        app=chat.app
        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 1:
            try:
                if self.text[0:12]=='circle-file:':
                    searcher.search_for_name(
                        hash.url_to_hash(self.text),'Files matching url', app.node,app)
                else:
                    utility.browse_url(self.text)
            except error.Error, err:
                chat.app.show_error(err,)
            return gtk.TRUE
        else:
            return gtk.FALSE

class Host_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')
    
    def on_click(self,chat,widget,event):
        if event.type == gtk.gdk.BUTTON_RELEASE :            
            str=utility.force_string(self.text.split()[0])
            address=str.split(':')
            searcher.search_browse_files((address[0],int(address[1])),chat.app.node,chat.app)
        return gtk.TRUE


class File_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'files')

    def context_menu(self,app):
        return file_context_menu(self,app)
    
    def on_click(self,chat,widget,event):

        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 2:
            chat.drag = self
            chat.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
            return gtk.TRUE
        
        elif event.type == gtk.gdk.BUTTON_RELEASE and event.button == 2:

            if chat.drag:
                file_field = chat.drag.file_field
                file_field.show(file_field.text,['grey'])
                file_field.set_action(None)
                #file_field.show(_('moved.\n'),['grey'])
                chat.app.file_server.move_file(chat.drag,self.father)
                #todo: self.father should be the dir I belong to

                chat.drag = None
                chat.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
                return gtk.TRUE

        elif event.button == 1:

            if event.type == gtk.gdk.BUTTON_RELEASE:
                searcher.set_leaf_player(self.leaf,chat.app)
                try:
                    playername = self.leaf.players.items()[0][0]
                except:
                    playername=''
                if playername:
                    searcher.play_file(self.leaf,playername,chat.app)
                    #self.leaf.self.show("playing\n",['grey'])
                    #self.show(self.text,['active'])
                else:
                    if not self.leaf.item.get('local_path'):
                        if not chat.app.file_server.paths.has_key(self.leaf.item['name']):
                            downloader = chat.app.file_server.download(
                                self.leaf,chat.app.daemon.config['download_dir'])
                            downloader.fields.append(self.leaf.field)
                return gtk.TRUE
            elif event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE

            return gtk.FALSE
        
        elif event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popup_menu(widget,event,chat.app)
            return gtk.TRUE
        else:
            return gtk.FALSE
          
    def on_edit(self,text):
        #todo:file_server should do that
        import os
        old_path = self.leaf.item.get('local_path')
        if not old_path:
            print "no path"
            return
        new_path = os.path.join(os.path.split(old_path)[0],text)
        os.rename(old_path,new_path)
        self.attr['path'] = new_path
        self.show(text,'files')




class Directory_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'files')

    def context_menu(self,app):
        return directory_context_menu(app,self.root,self)
    
    def on_click(self,chat,widget,event):
        root = self.root

        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 2:
            chat.drag = self.leaf
            chat.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
            return gtk.TRUE

        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 2:
            #if chat.drag:
            #    chat.app.file_server.move_file(chat.drag,root)                
            #    file_self = chat.drag.file_self
            #    file_self.show(file_self.text,['grey'])
            #    file_self.set_action(None)
            #    chat.drag.self.show(_('moved.\n'),['grey'])
            #    chat.drag = None
            #    chat.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
            #    return gtk.TRUE

            if chat.drag:
                file_field = chat.drag.file_field
                file_field.show(file_field.text,['grey'])
                file_field.set_action(None)
                file_field.show(_('moved.\n'),['grey'])
                chat.app.file_server.move_file(chat.drag,root)                

                chat.drag = None
                chat.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
                return gtk.TRUE

        elif event.button == 1:
            if event.type == gtk.gdk.BUTTON_RELEASE:
                if root.expanded:
                    chat.fterm.delete_fields(root.first_field,root.last_field)
                    root.first_field=None
                    root.last_field=None
                    root.expanded=0
                else:
                    root.expanded=1
                    chat.show_interior(root,chat.fterm.get_field_after(root.field))
                return gtk.TRUE
            elif event.type == gtk.gdk.BUTTON_PRESS:
                return gtk.TRUE
            return gtk.FALSE
        
        elif event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popup_menu(widget,event,chat.app)
            return gtk.TRUE
        else:
            return gtk.FALSE

    def on_edit(self,text):
        #todo:file_server should do that
        import os
        old_path = self.leaf.item.get('local_path')
        if not old_path:
            print "no path"
            return
        new_path = os.path.join(os.path.split(old_path)[0],text)
        os.rename(old_path,new_path)
        self.attr['path'] = new_path
        self.show(text,'files')


class Gossip_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,['links','indented'])

    def on_click(self,chat,widget,event):
        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 1:
            #Really should scroll to relevant wodge, until then
            #field.show(field.text,['purple','indented'])
            chat.app.show_gossip()
        return gtk.TRUE

class Tip_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')
    
    def on_click(self,chat,widget,event):
        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 1:
            import random
            self.next.show(random.choice(settings.tips)+'\n\n',['grey'])
        #return gtk.TRUE

class Take_Field(Active_Field):

    def show(self,str,tags=[],aug=[]):
        Field.show(self,str,'links')
    
    def on_click(self,chat,widget,event):
        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 1:
            do_take(chat, self.attr['what'] )
        return gtk.TRUE


#
# popup menus
#


def channel_context_menu(chat, channels, channel):
    menu = []
    if channels.list.has_key(channel):

        if channel in chat.channel:
            def untalk(data, channel=channel):
                if channel in chat.channel:
                    chat.remove_channel(channel)
                    chat.set_prompt()
            menu.append((_("Stop talking on %s")%channel, untalk))
        else:
            if channels.list[channel]['muted']:
                def unmute(data, channel=channel):
                    chat.channel_mute(channel, 0)
                menu.append((_("Listen to %s")%channel, unmute))
            else:
                def mute(data, channels=channels, channel=channel):
                    chat.channel_mute(channel, 1)
                menu.append((_("Mute %s")%channel, mute))

            def talk(data, channel=channel):
                if not channel in chat.channel:
                    chat.channel_mute(channel, 0)
                    chat.channel.append(channel)
                    chat.app.refresh_userlist()
                    chat.set_prompt()
            menu.append((_("Talk on %s")%channel, talk))

        if chat.channel!=[] and chat.channel!=[channel]:
            def talkonly(data, channels=channels, channel=channel):
                chat.channel_mute(channel, 0)
                chat.set_channel([channel])
            menu.append((_("Talk only on %s")%channel, talkonly))

        def unsub(data, _ch=channel):
            chat.channel_unsub(_ch)
        menu.append((_("Remove %s from sidebar")%channel,unsub))

    else:
        def sub(data, _s=channels, _ch=channel):
            chat.channel_sub(_ch)
        menu.append((_("Subscribe to %s")%channel,sub))

    def list(_b,_ch=channel,_s=channels):
        searcher.search_for_people_on_channel(_ch, _s.node,_s.app)
    menu.append((_("List %s subscribers")%channel, list))

    return menu



def name_context_menu(chat,name):
    """name should be an acquaintance nickname"""
    
    menu = []

    if name in chat.channel:
        def untalk(data, chat=chat, name=name):
            if name in chat.channel:
                chat.channel.remove(name)
                chat.app.refresh_userlist()
                chat.set_prompt()
        menu.append((_("Stop talking to %s")%name,untalk))
    else:
        def talk(data, chat=chat, name=name):
            if name not in chat.channel:
                chat.channel.append(name)
                chat.app.refresh_userlist()
                chat.set_prompt()
        menu.append((_("Talk to %s")%name,talk))
    if chat.channel!=[] and chat.channel!=[name]:
        def talkonly(data, chat=chat, name=name):
            chat.channel = [name]
            chat.app.refresh_userlist()
            chat.set_prompt()
        menu.append((_("Talk only to %s")%name,talkonly))
    def details(data, chat=chat, name=name):
        chat.app.name_server.lock.acquire()
        try:
            chat.app.edit_acquaintance(
                chat.app.name_server.nicknames[name],
                chat.app.name_server)
        finally:
            chat.app.name_server.lock.release()
    menu.append((_("View %s's details")%name, details))
    if chat.app.name_server.nicknames[name].online:
        def browse(data, chat=chat, name=name):
            searcher.search_browse_files(
                chat.app.name_server.nicknames[name].address,
                chat.app.name_server.node,
                chat.app)
        menu.append((_("Browse %s's files")%name, browse))
    if not chat.app.name_server.nicknames[name].remember:
        def remember(data, chat=chat, name=name):
            acq = chat.app.name_server.nicknames[name]
            acq.lock.acquire()
            acq.remember = 1
            acq.lock.release()
        menu.append((_("Remember %s")%name, remember))
    def forget(data, chat=chat, name=name):
        chat.app.name_server.forget(name)
    menu.append((_("Forget %s")%name, forget))
    return menu





def directory_context_menu(app,leaf,field):
    menu = []        

    def hide(data,root=leaf,chat=app.chat,field=field):
        chat.fterm.delete_fields(root.first_field,root.last_field)
        root.first_field=None
        root.last_field=None
        root.expanded=0
        field.show(field.text,['files'])
    def show(data,root=leaf,chat=app.chat,field=field):
        root.expanded=1
        chat.show_interior(root,chat.get_field_after(root.field))
        
        
    if leaf.expanded:
        menu.append((_("Minimize"), hide))
    else:
        menu.append((_("Expand"), show))
        
    if not leaf.item.get('local_path'):
        menu.append((_("Download directory"),
                     lambda x: app.download_directory_dialog(leaf)))

    #if leaf.item.get('name'):
    #    def view_sources(data):
    #        searcher.search_show_sources(leaf.sources, app.node, app)
    #    menu.append((_("View sources"), view_sources))

    if leaf.item.get('local_path'):
        def delete(data,leaf=leaf):
            try:
                os.rmdir(leaf.item['local_path'])
                field.set_active(0)
            except OSError,err:
                app.show_error(
                    error.Error("Cannot delete this directory:\n"+err.__str__()))
        menu.append((_("Delete"), delete))
        def rename(data,field=field):
            field.fterm.edit_field(field)
        menu.append((_("Rename"), rename))
        if app.chat.selected_files :
            def movehere(data,app=app):
                # move selected files here...
                pass
            menu.append((_("Move selection here"), movehere))
    return menu


def file_context_menu(field,app):

    menu = []
    searcher.set_leaf_player(field.leaf,app)
    try:
        playername=field.leaf.players.items()[0][0]
    except:
        playername=''
    # Todo: should create one menu item per player

    if playername:
        if app.music_manager.player and app.music_manager.player.field == field:
            def stop_playing(data,playername=playername):
                app.music_manager.stop_music()
            menu.append((_('Stop playing'), stop_playing))
        else:
            def play(data,playername=playername):
                searcher.play_file(field.leaf,playername,app)
            menu.append((_("%s")%playername, play))

            if field.leaf.players.has_key('Append'):
                def play_later(data):
                    searcher.play_file(field.leaf,'Append',app)
                menu.append((_("Append to playlist"), play_later))

    #check if the file is local:
    if not field.leaf.item.get('local_path'):    
        for d in app.file_server.downloaders:
            if d.data['name']==field.leaf.item['name']:
                def cancel(data,d=d):
                    d.cancel_download()
                    d.stop()
                menu.append((_("Cancel download"), cancel))
                break
        else:
            if not app.file_server.paths.has_key(field.leaf.item['name']):
                def download(data,leaf=field.leaf):
                    downloader=app.file_server.download(
                        leaf.item, leaf.sources, app.daemon.config['download_dir'])
                    downloader.fields.append(leaf.field)

                menu.append((_("Download"), download))

    if field.leaf.item.get('name'):
        def paste_url(data,app=app):
            str = ' '+hash.hash_to_url(field.leaf.item.get('name'))
            new_field = app.chat.fterm.insert_field(field,str,File_Field)
            new_field.leaf = field.leaf
        menu.append((_("Paste url"), paste_url))

    if field.leaf.item.get('name'):
        def view_sources(data):
            searcher.search_show_sources(field.leaf.sources, app.node, app)
        menu.append((_("View sources"), view_sources))

        def delete(data,field=field):
            app.file_server.remove_file(field.leaf.item.get('name'))
            field.show(field.text,['grey'])
            field.leaf.field.show(_('deleted.\n'),['grey'])
        if app.file_server.paths.has_key(field.leaf.item.get('name')):
            menu.append((_("Delete local copy"), delete))

    elif field.leaf.item.get('local_path'):
        def delete(data,field=field):
            os.unlink(field.leaf.item['local_path'])
            field.leaf.field.show(_('deleted.\n'),['grey'])
            field.set_active(0)
        menu.append((_("Delete"), delete))
        def rename(data,field=field):
            field.fterm.edit_field(field)
        menu.append((_("Rename"), rename))
   

        #def move_to(data,leaf=leaf):
        #menu.append((_("move to"), move_to))

    return menu



def link_context_menu(app,field):
    menu = []        

    def back(data,chat=app.chat,field=field):
        pass
    menu.append((_("Back"), back))
    menu.append((_("Forward"), back))

    return menu


def callback_bgshell(source, condition, self):
    """
    This callback is for a shell entered with ctrl D
    Every command has its own field.
    """

    fd=self.bgshell_master
    try:
        str = os.read(fd,256)
    except OSError:
        str = ''

    # if there is no field, create
    # it means that we had a prompt
    if not self.bgshell_field:
        self.bgshell_field = self.fterm.get_field()

    #str = string.replace(str,'\r','')
    #for the moment we do not have local tabs
    #therefore we better convert tabs into spaces
    str = string.replace(str,'\t','    ')

    if string.find(str,chr(7)) != -1:
        str = string.replace(str,chr(7),'')
        utility.beep()

    #post-processing commands:
    #here I can insert xml tags, (for colours, for example)

    # detect escape sequences
    # escape sequence for prompt: \e[y path \e[Y
    prompt_detected=0
    new_text = self.bgshell_field.text
    m = re.search(r'\x1B\[\d*;?\d*[a-zA-Z@:#~ ]', str)
    while m:
        new_text = new_text+str[0:m.start()]

        escape = m.group()
        if escape[1:] == '[y':
            str = str[m.end():]
            m = re.search(r'\x1B\[Y', str)
            self.bgshell_current_path= str[:m.end()-3]
            prompt_detected = 1
            str = str[m.end():]

        elif escape[:-1] == 'H':
            print "home"
            if escape == '\x1B[H':
                index = 0
            elif re.match(r'\x1B\[\d*;\d*H'):
                index = 0

        str = str[m.end():]
        m = re.search(r'\x1B\[\d*;?\d*[a-zA-Z@:#~ ]', str)

    new_text = new_text + str
    #try:
    utility.force_unicode(new_text)
    self.bgshell_field.show(new_text, ['monospace'])
    #except:
    #    pass

    if prompt_detected:
        self.bgshell_field = None
        self.fterm.set_prompt('>>')
        self.fterm.enter_command_mode()

    return 1





