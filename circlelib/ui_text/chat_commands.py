# Chat commands

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

#
# commands for text mode
#

from __future__ import generators
import os, re, string, time, threading, types, sys, traceback, string
from circlelib import chat, hash, check, error, safe_pickle, settings, utility, search


def do_join(chat_obj, params):

    def join_thread(chat_obj,params):

        if not params:
            if not chat_obj.channel:
                chat_obj.show(_('Use /join <nickname> to talk to someone.'))
            chat_obj.set_channel([ ])
            return

        param = params[0]
        if param[0] in '+-':
            prefix = param[0]
            param = param[1:]
        else:
            prefix = ''

        new_list = utility.split_list(param)
        old_list = chat_obj.channel[:]

        if prefix == '+':
            for item in old_list:
                if item not in new_list:
                    new_list.append(item)

        elif prefix == '-':
            for item in new_list:
                if item in old_list:
                    old_list.remove(item)
                else:
                    chat_obj.show(_('Not joined to %s')%item)    
            new_list = old_list

        for item in new_list:
            if item[0]!='#':
                result, thread = chat_obj.app.name_server.check_acquaintance(chat_obj.identity_list,item)
                yield 'wait',thread
                if not result:
                    chat_obj.show( 'No %s in your aquaintances list.'% item)
                    new_list.remove(item)

        chat_obj.set_channel(new_list)
        if new_list:
            chat_obj.show(_('Joined %s') % string.join(chat_obj.channel,',') )
        else:
            chat_obj.show(_('Joined nobody') )

    utility.start_thread(join_thread(chat_obj,params))

        

def do_listen(self, params):
    if not params:
        self.show(_('Listening to %s') %
	  string.join(self.channels.get_listening(),',') )
        return

    param = params[0]
    if param[0] in '+-':
        prefix = param[0]
        param = param[1:]
    else:
        prefix = ''
 
    new_list = utility.split_list(param) 
    for item in new_list:
        if item[:1] != '#':
            self.show(_('All channel names must begin with a # character.'))
            return
    old_list = self.channels.get_listening()

    if prefix == '+':
        for item in old_list:
            if item not in new_list:
                new_list.append(item)

    elif prefix == '-':
        for item in new_list:
            if item in old_list:
                old_list.remove(item)
            else:
                self.show(_('Not listening to %s')%item)
    
        new_list = old_list
        
    for item in new_list:
        self.channel_sub(item)
    for key in self.channels.list.keys():
        self.channel_mute(key, key not in new_list)

    self.show(_('Listening to %s') % string.join(new_list,',') )

def do_msg(self, param, augmentation):
    self.send_message(utility.split_list(param[0]), param[1], None, augmentation)
    
def _giveto(self, dests, param, augmentation):
    expression = param[0]

    if expression[:1] == '!':
        # Python expression
        try:
            result = eval(expression[1:],self.exec_vars)
        except:
            self.show(_('Error:\n')+\
                string.join(apply(traceback.format_exception,sys.exc_info())))
            return
    else:
        # File
        try:
            if not os.path.isfile(expression):
                raise error.Error(_('The file %s does not exist.') % expression)
            
            expression = os.path.abspath(expression)
            #self.app.file_server.add_root(expression)
            
            #result = self.app.file_server.get_reference(expression)
            result = self.app.file_server.add_private(expression)
        except error.Error, err:
            self.show(err.message + '\n')
            return

    if len(param) == 2:
        message = param[1]
    else:
        message = ''

    # Check that the object can be pickled
    try:
        safe_pickle.dumps(result)
    except:
        self.show(_("Couldn't SafePickle your object."))
        return
        
    self.send_message(dests,message,result,augmentation)
    return

def do_give(self, param, augmentation):
    _giveto(self, self.channel[:], param, augmentation)

def do_giveto(self, param, augmentation):
    _giveto(self, utility.split_list(param[0]), param[1:], augmentation)



def do_recall(self, params_dummy):
    
    def recall_thread(self,recall_list):
        if recall_list == [ ]:
            self.show( _('No message to recall.'))
        else:
            str = ''
            for item in recall_list:
                self.show(str+('Recalling message to %s...') % item[0])
                pipe = self.node.retrieve(item[1],settings.cache_redundancy)
                n    = 0
                while not pipe.finished():
                    for pair in pipe.read_all():
                        if pair[1] == item[2]:
                            try:
                                ticket = self.node.call(pair[0],('data cache remove',item[3]))
                                yield 'call',(self.node,ticket)
                                result = node.get_result(ticket)
                                n = n + 1
                            except error.Error:
                                pass
                    yield 'sleep',0.25

                if n == settings.cache_redundancy:
                    str = str + _('Recalled all %d copies of message to %s.') % (n,item[0])
                elif n == 0:
                    str = str + _('Could not recall message to %s.') % item[0]
                else:
                    str = str + _('Recalled %d copies of message to %s.') % (n,item[0])            
            self.show( str)
            
    utility.start_thread(recall_thread(self, self.recall_list))
 

def do_quiet(self, param):
    if param:
        self.set_status(1,param[0])
    else:
        self.set_status(not self.quiet, '')
        
    self.show_status()

def do_me(self, param):
    if param:
        activity = param[0]
    else:
        activity = ''

    self.set_status(0,activity)
    self.show_status()


def do_look(self, param):
    
    def look_thread(self,nick):
        try:
            result, thread = self.app.name_server.check_acquaintance(self.identity_list,nick)
            yield 'wait',thread
            if not result:
                self.show( 'No %s in your aquaintances list.'% nick)
                return
            acq = result[0]

            acq.start_watching(self.node)
            while not acq.watched:
                yield 'sleep',0.1

            online  = acq.online
            address = acq.address

            if online:
                ticket, template, wait = self.node.call(address,('chat look',))
                if wait:
                    yield ('call',(self.node,ticket))
                result = self.node.get_reply(ticket,template)
                
                if not check.matches(result, (types.IntType, 'text')):
                    str = _(' is using a bad Circle client')
                elif result[0]:
                    if result[1] == '':
                        str = _(' is listening')
                    else:
                        str = ' '+result[1]
                else:
                    if result[1] == '':
                        str = _(' is quiet')
                    else:
                        str = _(' is quiet: %s') % result[1]

                #str = str + _(' (on %s)') % utility.hostname_of_ip(address[0])
            else:
                str = _(' is offline')
            self.show(nick+str)
        except error.Error,err:
            print err.message

    if param:
        utility.start_thread(look_thread(self, param[0]))
    else:
        values = self.app.name_server.acquaintances.values()
        for item in values:
            if item.watch:
                utility.start_thread(look_thread(self, item.nickname))


def do_who(self, params):
    
    # todo:
    # if I subscribe to a channel, I should be warned when people join/leave

    if params:

        channel= params[0]
        if channel[0]!='#':
            self.show('\'%s\' is not a valid channel name. Channel names begin with \'#\''\
                      %channel)
            return
        else:
            pipe = self.node.retrieve(hash.hash_of('channel subscribe '+channel), \
                                      settings.channel_redundancy)
            empty_text = _('Nobody')
            single_text = _('1 person')
            show_ip=1
            show_number=0

            root = search.Search_tree_interior(
                lambda self=self: pipe, [], [], 'people', '',\
                '', empty_text,single_text,1)

            self.lock.acquire()
            self.identity_list =root.list
            self.root=root
            self.lock.release()

            self.show('People listening on channel '+channel+':')
            self.show_interior(root)

    else:

        self.show(_('Watched people currently online:'))
        self.app.name_server.lock.acquire()
        values = self.app.name_server.acquaintances.values()
        self.app.name_server.lock.release()

        for acq in values:
            acq.lock.acquire()
            name = acq.nickname
            acq.lock.release()

            acq.start_watching(self.node)
            #while not acq.watched:
            #    time.sleep(0.1)
            acq.lock.acquire()
            online = acq.online
            address = acq.address
            acq.lock.release()
            if online:
                self.show(name+' ')



def do_help(self, param):
    if param:
        # Discard all but first word.
        words = string.split(param[0], maxsplit=1)
        section = words[0]        
        if section[0] == '/':
            section = section[1:]
    else:
        section = ''
    
    #utility.stdin_echo(1)
    section = '#' + section
    try:
        utility.browse_file("html/chat_commands.html", section)
    except error.Error, err:
        self.show(err.message)
    #utility.stdin_echo(0)


def do_stats(self, param):
    node = self.app.node
    node.acquire_lock('stat')
    try:
        tot = node.network_usage
        prof = node.network_profile
        npeers = len(node.peers)
    finally:
        node.release_lock('stat')
    str = (_('Network usage so far: %s\nNumber of known peers: %d\n')
           % (utility.human_size(tot), npeers))
    if param and param[0] in ('-p', '--profile'):
        str += _('Profile:\n')
        prof_items = map(lambda item: (item[1][1], item[1][0], item[0]),
                         prof.items())
        prof_items.sort()
        for nbytes,count,key in prof_items:
            str += (' ' + key + ': \t' + utility.human_size(nbytes)
                    + _(' in %d items\n') % count)
    self.show(str)

def do_ls(self,list):
    utility.start_thread(ls_thread(self,list))

def ls_thread(self,list):        
    mime=''
    show_url=0
    show_number=0
    while list and list[0][0]=='-':
        option=list[0]
        list.remove(option)
        for opt in option[1:]:
            if opt=='u':
                show_url=1
            elif opt=='n':
                show_number=1
            elif opt=='a':
                mime='audio'
            elif opt=='v':
                mime='video'
            elif opt=='i':
                mime='image'
            else:
                raise error.Error(_('Unrecognized option \''+opt+'\'.\n'\
                                    +'Available /ls options are:\n'\
                                    +' -u : display url\n'\
                                    +' -n : number results\n'
                                    +' -a : audio files\n'
                                    +' -v : video files\n'
                                    +' -i : images'))
    if list:
        nickname, path = get_absolute_path(self,list[0])
    else:
        path = self.current_path
        nickname = self.current_path_nickname
        
    keywords = []
    anti_keywords = []
    

    if mime:
        what = mime+' files'
    else:
        what = 'files'
    if keywords:
        what=what+' matching %s'%title
    if nickname:
        self.show("checking %s's identity..."%nickname)
        result, thread = self.app.name_server.check_acquaintance(self.identity_list,nickname)
        yield 'wait',thread
        if not result:
            self.show('No %s in your aquaintances list.'% nickname)
            return
        acq = result[0]
        if acq.status_known and not acq.online:
            self.show('%s is offline.'% nickname)
            return
        address = acq.address
        where = ' in '+nickname+'\'s directory '+string.join(path,'/')
    else:
        address=self.app.node.address
        what = 'local ' + what
        if path:
            where = ' in '+string.join(path,'/')
        else:
            where = ''
            
    title = what + where +' :'
    title=title[0].upper()+title[1:]

    empty_text  = _('None')
    single_text = _('1 file')

    pipe = self.app.node.search_browse_task(address, path)
    root = search.Search_tree_interior(
        lambda self=self: pipe, keywords, anti_keywords,\
        'files', mime, '', empty_text,single_text, 0)
    root.nickname = nickname
    self.lock.acquire()
    self.file_list=root.list
    self.root=root
    self.lock.release()
    self.show(title)
    self.show_interior(root)





def get_absolute_path(self,path):

    if path:
        if path.find(':') != -1:
            index = path.index(':')
            nickname = path[:index]
            a_path = path[index+1:].split('/')
        else:
            nickname = self.current_path_nickname
            path = path.split('/')
            if path[0]=='.':
                prefix = self.current_path
                path.remove('.')
            elif path[0]=='..':
                prefix = self.current_path[:-1]
                path.remove('..')
            else:
                prefix = self.current_path
            a_path=prefix+path
    else:
        nickname = ''
        path = [ ]

    while '' in a_path:
        a_path.remove('')

    return (nickname,a_path)
     

def do_cd(self,param):
    if param:
        self.current_path_nickname, self.current_path = get_absolute_path(self,param[0])
    else:
        self.current_path_nickname, self.current_path = '',[ ]
    self.show("current path: "+self.current_path_nickname+':'+string.join(self.current_path,'/'))


def do_search(self, param):
    """search for files. called from mainthread"""

    if param:
        param = param[0]
    else:
        param = ''
    list = string.split(string.lower(utility.remove_accents(param)))
    show_url=0
    show_number=0
    mime=''
    local_only=0
    remote_only=0

    while list and list[0][0]=='-':
        option=list[0]
        list.remove(option)
        for opt in option[1:]:
            if opt=='u':
                show_url=1
            elif opt=='n':
                show_number=1
            elif opt=='a':
                mime='audio'
            elif opt=='v':
                mime='video'
            elif opt=='l':
                local_only=1
            elif opt=='r':
                remote_only=1
            elif opt=='i':
                mime='image'
            elif opt=='t':
                mime='text'
            else:
                raise error.Error(_('Unrecognized option \''+opt+'\'.\n'\
                                    +'Available /search options are:\n'\
                                    +' -u : display url\n'\
                                    +' -n : number results\n'
                                    +' -l : only local files\n'
                                    +' -r : only remote files\n'
                                    +' -a : only audio files\n'
                                    +' -t : only text files\n'
                                    +' -v : only video files\n'
                                    +' -i : only images'))

    show_number=1
    largest,keywords,anti_keywords,title = utility.parse_keywords(list)

    if keywords:
        pipe = self.app.node.retrieve(hash.hash_of(largest),1,0,local_only)
        #if self.app.overnet and not local_only:
        #    self.app.overnet.retrieve(largest,pipe)
    else:
        self.show('Please specify at least one positive search term (i.e. not preceded by !)')
        return

    empty_text = _('None')
    single_text = _('1 file')
    
    # todo: search tree interior should have two child classes for files and people...
    # about filtering: the pipe should already contain the right information..
    root = search.Search_tree_interior(
        lambda self=self: pipe, keywords, anti_keywords, 'files', mime,'', \
        empty_text,single_text,0,remote_only)
    self.lock.acquire()
    self.file_list=root.list
    self.root=root
    self.lock.release()

    str = 'files'
    if mime:
        str = mime+' ' + str
    if list:
        str=str+' matching %s'%title
    if remote_only:
        str= 'remote '+str
    if local_only:
        str= 'local '+str
    str=str[0].upper()+str[1:]

    self.show(str+':')
    self.show_interior(root)



def do_find(self, param):
    
    if param:
        param = param[0]
    else:
        param = ''
    list = string.split(string.lower(utility.remove_accents(param)))
    online_only = 0
    show_ip=0
    show_number=0

    while '--online' in list:
        list.remove('--online')
        online_only = 1

    while list and list[0][0]=='-':
        option=list[0]
        list.remove(option)
        for opt in option[1:]:
            if opt=='n':
                show_number=1
            elif opt=='i':
                show_ip=1
            elif opt=='h':
                show_ip=2
            elif opt=='o':
                online_only=1
            else:
                raise error.Error(_('Unrecognized option \''+opt+'\'.\n'\
                                    +'Available /find options are:\n'\
                                    +' -o : online people\n'\
                                    +' -n : number results\n'
                                    +' -i : display IP address\n'
                                    +' -h : display hostname'))


    largest,keywords,anti_keywords,title = utility.parse_keywords(list)
    
    if list:
        pipe = self.app.node.retrieve(
            hash.hash_of('identity-name '+largest), settings.identity_redundancy)
    else:
        pipe = self.app.node.retrieve(
            hash.hash_of('service identity'), settings.identity_redundancy)

    empty_text = _('Nobody')
    single_text = _('1 person')

    # there should be 2 child classes
    root = search.Search_tree_interior(
        lambda self=self: pipe, keywords, anti_keywords, 'people', '',\
        '', empty_text,single_text,online_only)

    self.lock.acquire()
    self.identity_list = root.list
    self.root=root
    self.lock.release()

    str = 'people'
    if not list and not online_only:
        str = 'all ' + str
    if online_only:
        str = 'online ' + str
    str=str[0].upper()+str[1:]
    if list:
        str=str+' matching %s'%title

    self.show(str+':')
    self.show_interior(root)


def do_add(self, param):
    """Deprecated. Useful for text mode only. Use /remember in the gui mode"""
    try:
        value = int(param[0])

    except ValueError:
        raise error.Error(_("/add requires a number (ie a result from /find)."))

    if value > len(self.identity_list):
        raise error.Error(_("The list of identities isn't that long."))
    if value < 1:
        raise error.Error(_("/add requires a positive number."))
    value = self.identity_list[value-1].item

    def add_thread(self,value=value):
        result, thread = self.app.name_server.make_acquaintance(value, None)
        yield 'wait',thread
        if result:
            acq=result[0]
            acq.watch = 1
            acq.remember = 1
            name = acq.nickname
            self.show(_('%s has been added to your contact list.')%name)
            acq.start_watching(self.app.node)
            
    utility.start_thread(add_thread(self))


def do_remember(self,param):
    """Replacement of /add. Takes a nickname as argument"""

    def remember_thread(self,param):
        nickname = param[0]
        result, thread = self.app.name_server.check_acquaintance(self.identity_list,nickname)
        yield 'wait',thread
        if result:
            acq=result[0]
            acq.remember = 1
            self.show( _('%s will be remembered.')%acq.nickname)
            name = acq.nickname
        else:
            self.show( 'I know nothing about %s. Try \'/find %s\' before.'% (nickname,nickname))
            
    utility.start_thread( remember_thread(self,param))
        

#todo: unpublish watcher is done, but does not seem to be sufficient...
#maybe the watched person is not warned about that
def do_forget(self, param):
    if not self.app.name_server.nicknames.has_key(param[0]):
        self.show(_('%s is not in your contact list.') % param[0])
        return
    else:
        self.app.name_server.forget(param[0])
        self.show(_('%s has been removed from your contact list.')%param[0])

def _read_and_repeat_helper(self, list):
    if not list:
        return

    list.sort()
    
    lock = threading.Lock()

    def read_list(self,lock=lock,list=list):
        while 1:
            lock.acquire()
            try:
                if not list:
                    break
                item = list.pop(0)
            finally:
                lock.release()

            self.receive(item[2], item[3], 1, item[0], 0)
            
    read_list(self)

def do_repeat(chat_obj, param):
    try:
        value = int(param[0])
    except ValueError:
        raise error.Error(_("/repeat requires a number."))

    if value <= 0:
        return

    chat_obj.lock.acquire()
    try:
        if value > len(chat_obj.incoming_message_history):
            value = len(chat_obj.incoming_message_history)

        # [(date, index, actual message, address)]
        list = map((lambda msg,ix: (msg[1], ix, msg[0], None)),
                   chat_obj.incoming_message_history[-value:], range(value))
        # The map is in preparation for sorting.

        _read_and_repeat_helper(chat_obj, list)
    finally:
        chat_obj.lock.release()

def do_read(self, params_dummy):
    self.show(_('Displaying unread messages.'))
    self.lock.acquire()
    try:
        # [(date, index, actual message, address)]
        list = map((lambda msg,ix: (msg[2], ix, msg[0], msg[1])),
                   self.unread_message_list, range(len(self.unread_message_list)))

        for msg_info in list:
            new_item = (msg_info[2], msg_info[0])
            # request, time
            check.check_matches(new_item,
                                chat.incoming_message_history_item_tmpl)
            # Proof: list taken from self.unread_message_list; @I15.  list unmodified
            # other than sorting, and is local to this method and not passed to any
            # other objects (hence not shared with other threads that could write
            # into the list).
            # Relevance: @R.I16.
            self.incoming_message_history.append(new_item)

        _read_and_repeat_helper(self, list)

        # Don't clear the list of unread messages unless they've all been
        # successfully shown (or at least that no exceptions are thrown
        # in this thread).  Of course, for this to be safe, we must hold the
        # lock from before reading the list until after clearing the list, and
        # all updates to the list must hold the lock.
        self.unread_message_list = [ ]
        self.set_prompt()
    finally:
        self.lock.release()

def do_set(self, param):
    if not param: 
        for item in self.app.config_keys:
            self.show(item[1] + ' = ' + self.app.config[item[0]] )
        return

    match = re.match(r"(\S*)\s*(=|\s)?\s*(.*)",param[0],re.DOTALL)
    if not match:
        raise error.Error(_("Couldn't understand your /set command."))

    for item in self.app.config_keys:
        if item[1] == match.group(1):
            self.app.config[item[0]] = match.group(3)
            break
    else:
        self.show(_("No configuration item called %s")%match.group(1))
        return

    self.app.sync_config()

def do_say(self, param):
    if not self.channel:
        raise error.Error(_("Before sending messages, you need to select a person or channel to talk to in the list to the right. If the person is not in the list, you need to search for them in the search box above and add them to your list of contacts."))

    self.send_message(self.channel[:],param[0])

def do_exit(self,param):
    check.check_matches(param, ['text'])
    
    if param:
        message = param[0]
    else:
        message = ''
    self.app.shutdown(message, 0)

def do_logout(self,param):
    check.check_matches(param, ['text'])
    
    if param:
        message = param[0]
    else:
        message = ''
    self.app.shutdown(message, 1)




def register_commands(self):
    """ Register commands. 
    parameters are : name, min_args, max_args, function
    max_args == -1 means no limit"""

    self.register("add",      1,1, do_add)
    self.register("cd",       0,1, do_cd)
    self.register("exit",     0,1, do_exit)
    self.register("find",     0,1, do_find)
    self.register("search",   1,1, do_search)
    self.register("forget",   1,1, do_forget)
    self.register("give",     1,2, do_give)
    self.register("giveto",   2,3, do_giveto)
    self.register("help",     0,1, do_help)
    self.register("join",     0,1, do_join)
    self.register("listen",   0,1, do_listen)
    self.register("ls",       0,-1, do_ls)
    self.register("look",     0,1, do_look)
    self.register("logout",   0,1, do_logout)
    self.register("me",       0,1, do_me)
    self.register("msg",      2,2, do_msg)
    self.register("quiet",    0,1, do_quiet)
    self.register("quietly",  0,1, do_quiet)
    self.register("read",     0,0, do_read)
    self.register("recall",   0,0, do_recall)
    self.register("remember", 1,1, do_remember)
    self.register("repeat",   1,1, do_repeat)
    self.register("say",      1,1, do_say)
    self.register("set",      0,1, do_set)
    self.register("stats",    0,1, do_stats)
    self.register("who",      0,1, do_who)


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
