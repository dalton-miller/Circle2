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

# Issues:
#  - Need to be passed a "self" object, so ~/.circle/user_commands.py needs
#    to be given that self thing.
#
#  - Ideally want to make it hard for the user to shoot self in foot.
#

from __future__ import generators
import os, re, string, time, threading, types, sys, traceback, string
from circlelib import chat, hash, check, error, safe_pickle, settings, utility, search


def do_join(chat_obj, params):

    def join_thread(chat_obj,params):

        if not params:
            if not chat_obj.channel:
                chat_obj.show(_('Use /join <nickname> to talk to someone.\n'))
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
                    chat_obj.show(_('Not joined to %s\n')%item)    
            new_list = old_list

        for item in new_list:
            if item[0]!='#':
                result, thread = chat_obj.app.name_server.check_acquaintance(chat_obj.identity_list,item)
                yield 'wait',thread
                if not result:
                    chat_obj.show( 'No %s in your aquaintances list.\n'% item,'grey')
                    new_list.remove(item)

        chat_obj.set_channel(new_list)
        if new_list:
            chat_obj.show(_('Joined %s\n') % string.join(chat_obj.channel,',') )
        else:
            chat_obj.show(_('Joined nobody\n') )

    utility.start_thread(join_thread(chat_obj,params))

        

def do_listen(self, params):
    if not params:
        self.show(_('Listening to %s\n') %
	  string.join(self.channels.get_listening(),', ') )
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
            self.show(_('All channel names must begin with a # character.\n'))
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
                self.show(_('Not listening to %s\n')%item)
    
        new_list = old_list
        
    for item in new_list:
        self.channel_sub(item)
    for key in self.channels.list.keys():
        self.channel_mute(key, key not in new_list)

    self.show(_('Listening to %s\n') % string.join(new_list,',') )

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
    
    def recall_thread(self,recall_list,field):
        if recall_list == [ ]:
            field.show( _('No message to recall.\n'), ['grey'])
        else:
            str = ''
            for item in recall_list:
                field.show(str+('Recalling message to %s...\n') % item[0],['grey'])
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
                    str = str + _('Recalled all %d copies of message to %s.\n') % (n,item[0])
                elif n == 0:
                    str = str + _('Could not recall message to %s.\n') % item[0]
                else:
                    str = str + _('Recalled %d copies of message to %s.\n') % (n,item[0])            
            field.show( str, ['grey'])
            
        field.close()

    utility.start_thread(recall_thread(self, self.recall_list, self.get_field()))
 
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
    
    def look_thread(self,nick,field):
        try:
            result, thread = self.app.name_server.check_acquaintance(self.identity_list,nick)
            yield 'wait',thread
            if not result:
                self.show( 'No %s in your aquaintances list.\n'% nick,'grey')
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
            field.show(nick,'people')
            field.name = acq.name
            field2=self.get_field_after(field)
            field2.show(str+'\n','grey')
        except error.Error,err:
            print err.message
        field.close()

    if param:
        utility.start_thread(look_thread(self, param[0], self.get_field()))
    else:
        values = self.app.name_server.acquaintances.values()
        for item in values:
            if item.watch:
                utility.start_thread(look_thread(self, item.nickname, self.get_field('person')))


def do_who(self, params):
    
    # todo:
    # if I subscribe to a channel, I should be warned when people join/leave

    if params:

        channel= params[0]
        if channel[0]!='#':
            self.show('\'%s\' is not a valid channel name. Channel names begin with \'#\'\n'\
                      %channel,'grey')
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

            str = 'People listening on channel '+channel
            first_field=self.get_field()
            self.show_before(first_field, str+':\n')
            self.show_interior(root,first_field,1)

    else:

        field = self.show(_('Watched people currently online:\n'))
        new_field = self.get_field_after(field,'person')
        field = new_field

        self.app.name_server.lock.acquire()
        values = self.app.name_server.acquaintances.values()
        self.app.name_server.lock.release()

        n = [0]
        fields = { }
        for item in values:
            if item.watch:
                n[0] = n[0]+1
                fields[item], field = field, self.get_field_after(field,'person')

        if n[0]:
            field.show(' ...\n')
            for acq in fields.keys():

                acq.lock.acquire()
                name = acq.nickname
                acq.lock.release()

                acq.start_watching(self.node)
                while not acq.watched:
                    print "yy"
                    time.sleep(0.1)

                acq.lock.acquire()
                online = acq.online
                address = acq.address
                acq.lock.release()

                if online:
                    fields[acq].show( name+' ','people')
                    fields[acq].name = acq.name
                else:
                    fields[acq].show('')
                fields[acq].close()

                self.lock.acquire()
                n[0] = n[0] - 1
                if n[0] == 0:
                    field.show('\n')
                    field.close()
                self.lock.release()

        else:
            field.show('\n')
            field.close()


def do_help(self, param):
    if param:
        # Discard all but first word.
        words = string.split(param[0], maxsplit=1)
        section = words[0]        
        if section[0] == '/':
            section = section[1:]
    else:
        section = ''
    
    if not section:
        self.show_xml_file("ixml/help.xml")
    else:
        self.show_xml_file("ixml/cmd_%s.xml"%section)

    #else: (non gtk)
    #    utility.stdin_echo(1)
    #    section = '#' + section
    #    try:
    #        utility.browse_file("html/chat_commands.html", section)
    #    except error.Error, err:
    #        self.show(err.message+'\n')
    #    utility.stdin_echo(0)


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
    
    first_field=self.get_field()
    title_field=self.get_field_before(first_field)

    if mime:
        what = mime+' files'
    else:
        what = 'files'
    if keywords:
        what=what+' matching %s'%title
    if nickname:
        self.show_at(title_field,"checking %s's identity...\n"%nickname)
        result, thread = self.app.name_server.check_acquaintance(self.identity_list,nickname)
        yield 'wait',thread
        if not result:
            self.show_at(title_field,'No %s in your aquaintances list.\n'% nickname)
            return
        acq = result[0]
        if acq.status_known and not acq.online:
            self.show_at(title_field,'%s is offline.\n'% nickname)
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
            
    title = what + where +' :\n'
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
    self.show_at(title_field,title)
    #title_field.close()
    self.show_interior(root,first_field)





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
    self.show("current path: "+self.current_path_nickname+':'+string.join(self.current_path,'/')+'\n')


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

    #if not self.use_gtk:
    #    show_number=1

    largest,keywords,anti_keywords,title = utility.parse_keywords(list)

    if keywords:
        pipe = self.app.node.retrieve(hash.hash_of(largest),1,0,local_only)
        #if self.app.overnet and not local_only:
        #    self.app.overnet.retrieve(largest,pipe)
    else:
        self.show('Please specify at least one positive search term (i.e. not preceded by !).\n','grey')
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

    first_field=self.get_field()
    self.show_before(first_field, str+':\n')
    self.show_interior(root,first_field,show_url)



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

    #if not self.use_gtk:
    #    show_number=1

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

    first_field=self.get_field()
    self.show_before(first_field, str+':\n')
    self.show_interior(root,first_field,show_ip)


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
            self.show(_('%s has been added to your contact list.\n')%name)
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
            self.show( _('%s will be remembered.\n')%acq.nickname)
            name = acq.nickname
        else:
            self.show( 'I know nothing about %s. Try \'/find %s\' before.\n'% (nickname,nickname),'grey')
            
    utility.start_thread( remember_thread(self,param))
        

def do_play(self,param):
    import searcher
    for item in self.file_list:
        if utility.force_unicode(item.item['filename']) == param[0]:
            leaf=item
            break
    else:
        self.show( 'unknown file %s.\n'%param[0],'grey')
        return
    try:
        searcher.set_leaf_player(leaf,self.app)
        playername=leaf.players.items()[0][0]
    except:
        self.show( 'I do not know how to play this file.\n','grey')
        return
 
    if playername:
        searcher.play_file(leaf,playername,self.app)



def do_get(self, param):
    """downloads a list of files from the last search results"""

    download_list=[]
    if param[0]=='*':
        self.lock.acquire()
        for item in self.file_list:
            if item.item['type']=='file':
                download_list.append(item)
        self.lock.release()
    else:
        for item in self.file_list:
            if utility.force_unicode(item.item['filename']) in param:
                download_list.append(item)
                
    if not download_list:
        self.show( 'unknown file %s.\n'%param[0],'grey')
        return

    last_field=self.get_field()
    first_field=self.get_field_before(last_field)
    bad_list = [ ]
    dir_list = [ ]
    size=0
    
    for item in download_list:        
        if item.item['type'] == 'file':
            downloader=self.app.file_server.download(
                item.item,item.sources,self.app.config['download_dir'],no_overload=1)
            if downloader:
                size=size+item.item['length']
            else:
                bad_list.append(item)

        elif item.item['type'] == 'directory':
            item.download(self.app)
            dir_list.append(item)
        else:
            raise error.Error("bug")
            
    if not download_list:
        str=_('The list of files is empty.\n')
    elif len(download_list)-len(bad_list)==0:
        str=_('Not downloading.\n')
    elif len(download_list)-len(bad_list)==1:
        if dir_list:            
            str=_('Downloading 1 directory. \n')
        else:
            str=_('Downloading 1 file. \n')
    else:
        str=_('Downloading %d files. \n')%(len(download_list)-len(bad_list))
        
    if bad_list:
        if len(bad_list)==len(download_list):
            str=_('Requested files are already in your directory. ')+str
        elif len(bad_list)==1:
            str=_('1 file already in your directory. ')+str
        else:
            str=_('%d files already in your directory. ')%len(bad_list)+str
    first_field.show(str,['grey'])
    first_field.close()
    if size:
        last_field.show(_('Total %s.\n'%utility.human_size(size)),['grey'])
    last_field.close()

#todo: unpublish watcher is done, but does not seem to be sufficient...
#maybe the watched person is not warned about that
def do_forget(self, param):
    if not self.app.name_server.nicknames.has_key(param[0]):
        self.show(_('%s is not in your contact list.\n') % param[0])
        return
    else:
        self.app.name_server.forget(param[0])
        self.show(_('%s has been removed from your contact list.\n')%param[0])

def _read_and_repeat_helper(self, list):
    if not list:
        return

    list.sort()
    
    fields = [self.get_field()]
    while len(fields) < len(list):
        fields.append(self.get_field_after(fields[-1]))

    lock = threading.Lock()

    def read_list(self,lock=lock,list=list,fields=fields):
        while 1:
            lock.acquire()
            try:
                if not list:
                    break
                item = list.pop(0)
                field = fields.pop(0)
            finally:
                lock.release()

            # chat_obj, request, address,
            # receptacle widget, quiet:yes, time, add_to_history:no
            
            self.receive(item[2], item[3], 1, item[0], 0)
            
            # fixme prove that list[i][0] is like time():
            # prove of chat.unread_message_list items.

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
    self.show(_('Displaying unread messages.\n'))
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
            self.show(item[1] + ' = ' + self.app.config[item[0]] + '\n')
        return

    match = re.match(r"(\S*)\s*(=|\s)?\s*(.*)",param[0],re.DOTALL)
    if not match:
        raise error.Error(_("Couldn't understand your /set command."))

    for item in self.app.config_keys:
        if item[1] == match.group(1):
            self.app.config[item[0]] = match.group(3)
            break
    else:
        self.show(_("No configuration item called %s")%match.group(1)+"\n")
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



def do_downloads(self,params_dummy):

    pipe = self.app.file_server.retrieve_downloaders()
    empty_text = _('None')
    single_text = _('1 file')

    root = search.Search_tree_interior(
        lambda self=self: pipe, [], [], 'files', '',\
        '', empty_text,single_text,0)
    str = 'Files being downloaded'
    first_field=self.get_field()
    self.show_before(first_field, str+':\n')
    self.show_interior(root,first_field)

#
# commands of the gtk interface
#

def do_tip(self, params_dummy):
    self.show_tip()

def do_post(self, params_dummy):
    if self.app.gossip is None:
        self.show(_("Gossip is currently disabled, sorry.\n"))
        return
    self.app.prompt_for_wodge()

def do_gossip(self, params_dummy):
    if self.app.gossip is None:
        self.show(_("Gossip is currently disabled, sorry.\n"))
        return
    self.app.show_gossip(update=1)

def do_clear(self, params_dummy):
    self.fterm.clear()

def do_take(self, param):
    what = param[0]
    self.lock.acquire()
    try:
        if not self.exec_vars.has_key(what) or \
             not self.exec_vars.has_key(what+'_source'):
            self.show(_('No such reference.\n'))
            return
        
        ref = self.exec_vars[what]
        source = self.exec_vars[what+'_source']
        if not (check.matches(ref,
                  {'type':'string', 'filename':'text', 'name':'name', 'length':'integer'})
                and ref['type'] == 'file'):
            self.show(_('Not a reference to a file.\n'))
            return
        
        leaf = search.Search_tree_file(ref,source)
        leaf.field = self.get_field()
        self.show_before(leaf.field,_('Download of %s :\n') % ref['filename'])
        try:
            d = self.app.file_server.download(
                leaf.item,leaf.sources,self.app.daemon.config['download_dir'])
            if d:
                d.fields.append(leaf.field)
            else:
                leaf.field.show('Done\n')
        except error.Error, err:
            leaf.field.show(_('Problem: ') + err.message + '\n')
    finally:
        self.lock.release()



def register_commands(self):
    """ Register commands. 
    parameters are : name, min_args, max_args, function
    max_args == -1 means no limit"""

    self.register("tip",      0,0, do_tip)
    self.register("post",     0,0, do_post)
    self.register("gossip",   0,0, do_gossip)
    self.register("clear",    0,0, do_clear)
    self.register("take",     1,1, do_take)

    self.register("add",      1,1, do_add)
    self.register("cd",       0,1, do_cd)
    self.register("downloads",0,0, do_downloads)    
    self.register("exit",     0,1, do_exit)
    self.register("find",     0,1, do_find)
    self.register("search",   1,1, do_search)
    self.register("forget",   1,1, do_forget)
    self.register("get",      1,-1, do_get)
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
    self.register("play",     1,-1, do_play)
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
