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
# note: the cache for channels is buggy, because of multiple threads
# writing the same data
#

# TODO: detect when someone drops off the network badly

# TODO: float pickle

# TODO: improve /recall : select from list, only recall from some people for single message


from __future__ import generators
import cStringIO
import os
import re
import select
import string
import sys
import traceback
import types
import threading

import settings
import utility
import error
import safe_pickle, hash, channels
import calendar
import time
import check


# When publishing timestamps, we standardize on the Unix epoch of 1970.
host2standard_time_offset = calendar.timegm((1970, 1, 1, 0, 0, 0, 3, 1, -1))

if time.gmtime(host2standard_time_offset)[:6] != (1970, 1, 1, 0, 0, 0):
    check.show_bug(_('Bug in calculating epoch offset.'))


def host2standard_timestamp(host_tstamp):
    check.check_has_type(host_tstamp, types.FloatType)
    
    ret = long(host_tstamp + host2standard_time_offset)
    
    check.check_has_type(ret, types.LongType)  #=@E16
    return ret

def standard2host_timestamp(std_tstamp):
    check.check_has_type(std_tstamp, types.LongType)  #=@R36
    
    ret = float(std_tstamp - host2standard_time_offset)
    
    check.check_has_type(ret, types.FloatType)  #=@E17
    return ret


def chat_tell_thread(chat, dests, message, attachment=None, augmentation=None):
    """Messages are sent in parallel, one thread per recipient. The
       information displayed in field ends with '...' until the last
       message has been sent, then with '..' until all recipients
       have answered, and finally with '.' The field is closed by
       the last thread to finish """
    
    check.check_matches(dests, ['text'])
    check.check_is_text(message)
    std_timestamp = host2standard_timestamp(time.time())
    if augmentation and len(augmentation) != len(message):
        sys.stderr.write("Augmentation %d bytes, should be %d bytes.\n"
                         % (len(augmentation), len(message)))
        augmentation = None
    
    message_id = chat.create_message_id()
    try:
        result = ['','','','','...\n']
        dest_list = [ ]
        dest_address  = [ ]
        checked_address = [ ]
        dest_names = [ ]
        received_names = [ ]
        offline_list  = [ ]
        offline_names = [ ]
        recipient_list = [ ]
        channel_pipes = { }
        chan_cnt=[0]

        for dest in dests:
            if dest[0]=='#':
                channel_pipes[dest] = chat.channels.sub_list_pipe(dest)
                recipient_list.append((None,None,dest))
                continue
            acq = chat.app.name_server.locate(dest)
            acq.start_watching(chat.node)
            while not acq.watched:
                yield 'sleep',0.1

            acq.lock.acquire()
            online = acq.online
            address = acq.address
            name = acq.name
            username = acq.info['name']
            acq.lock.release()

            if not online:
                offline_list.append(acq)
                offline_names.append(dest)
                recipient_list.append((name,None,username))
            else:
                dest_list.append(acq)
                dest_address.append(address)
                dest_names.append(dest)
                recipient_list.append((name,address,username))

        my_details = (
            chat.app.name_server.public_key_name,
            chat.app.name_server.name
        )

        package = {
            'from': my_details,
            'to': recipient_list,
            'text': message
        }
        if augmentation:
            package['aug'] = augmentation
        if attachment:
            package['attach'] = attachment

        package_pickle = safe_pickle.dumps(package)
        signature = chat.app.name_server.sign(package_pickle)
        message = ('chat message 2',package_pickle,signature)

        def recipient_thread(chat,address,name,channel,received_names,dest_address,
                             checked_address,chan_cnt,message_id,result, message=message):

            succ = 1
            try:
                ticket, template, wait = chat.node.call(address,message)
                if wait: yield ('call',(chat.node,ticket))
                ret_value = chat.node.get_reply(ticket,template)

                #Type checking
                if type(ret_value) != types.TupleType:
                    succ = 0
                    if not channel:
                        result[2] = result[2] + name + _(' sent bad reply.\n')
                        chat.update_message_status(message_id, result[0]+result[4]+result[2])
            except error.Error,err:
                succ = 0
                if not channel:
                    result[2] = result[2] + name + _(' could not be contacted: ')+err.message+'\n'
                    chat.update_message_status(message_id, result[0]+result[4]+result[2])
                    chat.app.name_server.bad_address(address)
                    
            if succ:
                if channel:
                    chan_cnt[0] += 1
                else:
                    received_names.append(name)
                    if ret_value[0]:
                        pass
                        #if ret_value[1] != '':
                        #    result[2] = result[2] + name + ' ' + ret_value[1] + '\n'
                    else:
                        if ret_value[1] == '':
                            result[2] = result[2] + name + _(' is quiet.\n')
                        else:
                            result[2] = result[2] + name + _(' is quiet: ') + ret_value[1] + '\n'
                            
                if chan_cnt[0] == 0:
                    result[0] = _('Message received by ') + utility.english_list(received_names) 
                elif chan_cnt[0] == 1:
                    result[0] = _('Message received by ')\
                                +utility.english_list(received_names+[ _('1 person')])+result[1]
                else:                            
                    result[0] = _('Message received by ')\
                                +utility.english_list(received_names+[ _('%d people') % chan_cnt[0] ])+result[1]
                chat.update_message_status(message_id,result[0]+result[4]+result[2])

            checked_address.append(address)
            checked_address.sort()
            if result[4]=='..\n' and checked_address == dest_address:
                if chan_cnt[0]==0 and received_names == []:
                    result[0] = _('Nobody received your message')
                result[4] = '.\n'
                chat.update_message_status(message_id, result[0]+result[4]+result[2])

        for i in range(len(dest_list)):
            utility.start_thread(recipient_thread(chat,dest_address[i],dest_names[i],0,\
                       received_names,dest_address,checked_address,chan_cnt,message_id,result))
         
        if channel_pipes:
            if channel_pipes.__len__()>1:
                result[1] = (_(' on channels %s') % utility.english_list(channel_pipes.keys()))
            else:
                result[1] = (_(' on channel %s') % channel_pipes.keys()[0])

        if channel_pipes:
            for chan_name in channel_pipes.keys():
                if not chat.channels.cache.has_key(chan_name):
                    chat.channels.cache[chan_name]=[]
                else:                    
                    for address in chat.channels.cache[chan_name]:
                        if address in dest_address:
                            continue                    
                        dest_address.append(address)
                        utility.start_thread(
                            recipient_thread(chat,address,'',1,received_names,
                                             dest_address,checked_address,chan_cnt,message_id,result))
                #reset the cache:
                chat.channels.cache[chan_name]=[]
                    
                    
        while channel_pipes:
            for chan_name,chan_pipe in channel_pipes.items():
                if chan_pipe.finished():
                    chan_pipe.stop()
                    del channel_pipes[chan_name]
                    continue
                
                for address in chan_pipe.read_all():
                    #update the cache
                    if address not in chat.channels.cache[chan_name]:
                        chat.channels.cache[chan_name].append(address)
                    if address in dest_address:
                        continue
                    dest_address.append(address)
                    utility.start_thread(recipient_thread(chat,address,'',1,received_names,
                               dest_address,checked_address,chan_cnt,message_id,result))
                    
            yield 'sleep',0.1

        #we now have launched all the tasks
        dest_address.sort()
        result[4]='..\n'
        if checked_address == dest_address:
            if chan_cnt[0]==0 and received_names == []:
                result[0] = _('Nobody received your message')
            result[4] = '.\n'
            chat.update_message_status(message_id, result[0]+result[4]+result[2])

        recall_list = [ ]
        if offline_list:
            chat.update_message_status(message_id,'Caching message...\n',1)
        for i in range(len(offline_list)):
            key   = utility.random_bytes(settings.name_bytes)
            lock  = hash.hash_of(key)
            crypt = offline_list[i].encrypt((key, message, std_timestamp))
            data  = {
                'type' : 'offline message',
                'crypt': crypt
            }
            name  = hash.hash_of('offline message '+offline_list[i].name)
            # Loose proof of @R50: @I21, @E22.

            recall_list.append((offline_list[i].nickname,name,data,key))

            publish_result, subthread = chat.app.cache.publish([name],data,lock)
            yield 'wait',subthread
            if publish_result:
                redundancy = publish_result[0]
            else: redundancy = 0
            if redundancy == settings.cache_redundancy:
                str = offline_names[i] + _(' will get your message when next logged on.\n')
            elif redundancy == 0:
                str = _('Could not store message for ') + offline_names[i] + '!\n'
            else:
                str = (offline_names[i]
                       + _(' will probably get your message when next logged on:\n' +\
                           '  Message only stored with redundancy %d.\n') % redundancy)

            result[3] = result[3] + str
            chat.update_message_status(message_id,result[3]+'\n',1)
            
        chat.recall_list = recall_list
    except error.Error, err:
        chat.update_message_status(message_id,_('Error sending message:\n') + err.message + '\n')



# (If you change these then search for uses and update the
# proofs, or at least add a todo note.)
incoming_message_history_item_tmpl = ('any', types.FloatType)
unread_message_list_item_tmpl = ((types.StringType,),
                                 'opt-address',
                                 types.FloatType)






def retrieve_cached_messages_thread(self,on_complete):

    pipe = self.node.retrieve(
        hash.hash_of('offline message '+self.app.name_server.public_key_name),
        settings.cache_redundancy)

    # Loose proof of @R50: @I22, @E22.
    pipe_reads = [ ]
    if not pipe.finished():
        while 1:
            pipe_reads.extend(pipe.read_all())
            if pipe.finished():
                break
            yield 'sleep',1
    pipe.stop()
    # pjm 2002-08-05: I've changed the above to sleep only if
    # one read_all call isn't enough.  However, I don't know why
    # sleep is wanted in the first place, or whether a different
    # duration might be better.  (Python sleep allows its
    # argument to be fractional, implemented in terms of
    # select.)

    unique_messages = [ ]
    for item in pipe_reads:
        # I think we're guaranteed that item matches ('af_inet_address', 'any').
        if not check.matches(item[1], {'type' : types.StringType,
                                       'crypt' : ('any', 'any')}):
            # print bad peer
            pass
        elif item[1] not in unique_messages:
            unique_messages.append(item[1])

    message_list = [ ]
    for raw_msg in unique_messages:
            if type(raw_msg) == type({}) \
               and raw_msg.get('type','') == 'offline message' \
               and raw_msg.has_key('crypt'):
                try:
                    decrypt = self.app.name_server.decrypt(raw_msg['crypt'])
                    if not check.matches(decrypt, ('text',
                                                   (types.StringType,),
                                                   types.LongType)):
                        raise error.Error('bad decrypted reply')

                    # Remove from caches
                    for thing in pipe_reads:
                        if thing[1] == raw_msg:
                            try:
                                ticket, template, wait = self.node.call(\
                                    thing[0],('data cache remove',decrypt[0]))
                                if wait: yield ('call',(self.node,ticket))
                                self.node.get_reply(ticket,template)

                            except error.Error:
                                pass

                    message_list.append((decrypt[2],decrypt[1]))
                except error.Error:
                    pass

    message_list.sort()
    self.lock.acquire()
    try:
        any = 0
        for msg in message_list:
            if msg not in self.offline_message_buffer:
                self.offline_message_buffer = [msg] + self.offline_message_buffer[:50]

                new_item = (msg[1], None,
                            standard2host_timestamp(msg[0]))
                # Proof of @R36: msg is taken from message_list.
                # message_list is local to this method, and is not
                # passed to any other method (so is not shared with any
                # other thread).  message_list starts as empty and is
                # written to solely as (decrypt[2],decrypt[1]) pairs,
                # and only where decrypt has already been found to
                # match ('any', ('string',), 'long').  The relevant
                # types are immutable.
                check.check_matches(new_item,
                                    unread_message_list_item_tmpl)
                # Proof: the @R36 proof just above also shows that
                # msg[1] (i.e. decrypt[1]) matches ('string',) and
                # is immutable.  new_item[1] matches because
                # is_opt_address(None).  new_item[2] matches from @E17.
                # Relevance: @R.I15
                self.unread_message_list.append(new_item)
                any = 1
            else:
                print _("Duplicate offline message.")
    finally:
        self.lock.release()

    on_complete(self,any)




class Chat:
    """ Base class of Chat_gtk and Chat_text, provides basic chat functions. """

    def __init__(self,app):

        self.lock = threading.RLock()
        self.node = app.node
        self.app  = app 

        # Visible status
        self.quiet       = 0
        self.activity    = ''
        self.n_unseen_messages = 0

        # Results of /find and /search
        self.identity_list = [ ]
        self.file_list=[ ]

        # Python environment
        self.exec_vars = { 'app' : app, 'node' : app.node, 'daemon':app.daemon }

        # Detect repeated offline messages
        self.offline_message_buffer = [ ]

        # Store a copy of recent messages
        self.incoming_message_history = [ ]

        # used for /ls
        self.current_path_nickname = ''
        self.current_path = [ ]

        # While quiet, messages are buffered for later display.
        # Tuples of form (request, opt-address, time.time()).
        # address for offline-sent messages is None.
        # The time item must be wrt this client's epoch.
        self.unread_message_list = [ ]
        
        config = utility.get_checked_config("chat", types.DictionaryType, { })
        for name,tmpl in [('quiet', 'any'),
                          ('activity', 'any'),
                          ('offline_message_buffer', 'any'),
                          ('incoming_message_history', [('any', 'any timestamp')]),
                          ('unread_message_list', [((types.StringType,),
                                                    'opt-address',
                                                    'any timestamp')])]:
            if config.has_key(name):
                config_val = config[name]
                if check.matches(config_val, tmpl):
                    setattr(self, name, config_val)
                else:
                    print (_("Warning: ignoring chat config item %s, which doesn't match %s.")
                           % (name, tmpl))
        # The current version of Circle always writes these timestamps in
        # standardized form, but previous versions wrote a mixture of floats
        # and longs.
        for i in xrange(len(self.incoming_message_history)):
            request,tstamp = self.incoming_message_history[i]
            if type(tstamp) == types.LongType:
                self.incoming_message_history[i] = (request,
                                                    standard2host_timestamp(tstamp))
            check.check_matches(self.incoming_message_history[i],
                                incoming_message_history_item_tmpl)
            # Loose proof: definition of check.is_any_timestamp, @E17.
            # Relevance: @R.I16.
        for i in xrange(len(self.unread_message_list)):
            request,addr,tstamp = self.unread_message_list[i]
            if type(tstamp) == types.LongType:
                self.unread_message_list[i] = (request, addr,
                                               standard2host_timestamp(tstamp))
            check.check_matches(self.unread_message_list[i],
                                unread_message_list_item_tmpl)
            # Loose proof: as above.
            # Relevance: @R.I15.
        
        self.recall_list = [ ]

        # Detect repeated messages
        self.message_buffer = [ ]

        self.channel = [ ]
        self.channels = channels.Channels(self.app)
        self.chat_check_invar()



    def identify(self,key_name,address,on_complete):
        
        def identify_thread(chat, key_name, address, on_complete):
            try:
                result_id, thread = chat.app.name_server.identify(key_name,address)
                yield 'wait',thread
                result = result_id[0]
            except:
                result = None
            on_complete(result)

        utility.start_thread(identify_thread(
            self,key_name,address,on_complete))

    def receive(self, request, address, quiet, send_time, add_to_history=1):
        """send_time should be as if from time.time() (i.e. a float expressing seconds
           since the local machine's epoch) rather than the standardized timestamps
           sent over the network (i.e. a long expressing seconds since the Unix epoch
           of 1970)."""

        # TODO: more checking of message format
        # TODO: search for people not in acq list

        check.check_is_opt_address(address)  #=@R33  fixme callers
        check.check_has_type(send_time, types.FloatType)  #=@R35  fixme callers
        # fixme: should probably require that request be a tuple with 5+ elems.

        if 1:
            if not self.is_visible():
                self.n_unseen_messages = self.n_unseen_messages + 1
                if self.n_unseen_messages == 1:
                    title = _('1 unseen message')
                else:
                    title = _('%d unseen messages') % self.n_unseen_messages
                self.app.set_title(title)

            if request[0] == 'chat message 2':
                package = safe_pickle.loads(request[1])
                text = package['text']
                augmentation = package.get('aug')
                has_attachment = package.has_key('attach')
                attachment = package.get('attach')
                sender_key_name, sender_name = package['from']
                recipients = package['to']

                verify_text = request[1]
                verify_sig = request[2]

            else:
                # Legacy message format
                text = request[3]
                augmentation = None
                has_attachment = (len(request) == 6)
                if has_attachment:
                    attachment = safe_pickle.loads(request[4])

                recipients = request[2]

                if type(request[1]) == type(()):
                    sender_key_name = request[1][0]
                    sender_name = request[1][1]
                else:
                    # Used not to send username with key name
                    sender_key_name = request[1]
                    sender_name = 'unknown'

                if has_attachment:
                    verify_text = request[3].encode('utf8')+request[4]
                    verify_sig = request[5]
                else:
                    verify_text = request[3]
                    verify_sig = request[4]

            if not augmentation:
                augmentation = chr(128) * len(text)


            self.show_received_message(sender_name,sender_key_name,address,recipients,
                                       text,verify_text,verify_sig,quiet,
                                       send_time,augmentation,has_attachment,attachment)

        #except error.Error:
        #    self.show(_('Bad message received from ') + repr(address) + '\n')

        if add_to_history:
            self.lock.acquire()
            try:
                new_item = (request, send_time)
                check.check_matches(new_item, incoming_message_history_item_tmpl)
                # Proof: @R35, immutability of float, send_time not reassigned
                # in this function.
                # Relevance: @I16.
                self.incoming_message_history.append(new_item)

                while len(self.incoming_message_history) > settings.incoming_message_history_size:
                    del self.incoming_message_history[0]
            finally:
                self.lock.release()
                

    def chat_check_invar(self):
        check.check_matches(self.unread_message_list,
                            [unread_message_list_item_tmpl])  #=@I15
        check.check_matches(self.incoming_message_history,
                            [incoming_message_history_item_tmpl])  #=@I16
        check.check_matches(self.channel, ['text'])  #=@I31

    def repeated(self, address,call_id):
        if (address,call_id) in self.message_buffer:
            return 1
        self.message_buffer.append((address,call_id))
        if len(self.message_buffer) > 50:
            del self.message_buffer[0]
        return 0

    def start(self):

        self.app.name_server.set_status('chat',(not self.quiet,self.activity))        
        self.set_prompt()
        self.node.add_handler('chat message 2',
                              self, ('string',  # pickled message details
                                    ('long',))) # signature
        self.node.add_handler('chat look', self)
        # The expected call/return signatures are () / (types.IntType, 'text')
        # respectively.  But don't bother checking return type, as callers
        # already do their own checking.

        self.app.name_server.add_watch_callback(self)        
        self.channels.start()


    def retrieve_cached_messages(self,on_complete):
        utility.start_thread(retrieve_cached_messages_thread(self,on_complete))


    def stop(self):
        #self.change_activity('removing callbacks')
        self.channels.stop()
        
        self.node.remove_handler('chat message 2')
        #self.node.remove_handler('chat look')

        #thomasV: I guess the following should belong to name_server
        #self.app.name_server.remove_watch_callback(self)

        #self.change_activity('preparing config')
        config = { }
        for item in ['quiet','activity','offline_message_buffer']:
            config[item] = getattr(self,item)
        # Convert timestamps to standardized epoch.  The intent is to allow
        # sharing/copying a .circle directory between different operating
        # systems (in particular, between operating systems that have a
        # value of time.gmtime(0), i.e. different epochs).
        config['incoming_message_history'] \
          = map(lambda item: (item[0], host2standard_timestamp(item[1])),
                self.incoming_message_history)
        config['unread_message_list'] \
          = map(lambda item: (item[0], item[1], host2standard_timestamp(item[2])),
                self.unread_message_list)

        #self.change_activity('saving to disk')
        utility.set_config("chat",config)
        #self.change_activity('')



    def handle(self, request, address,call_id):
        check.check_matches(request, (types.StringType,))  #=@R34
        check.check_is_af_inet_address(address)  #=@R31
        
        self.lock.acquire()
        try:
            if request[0] == 'chat look':
                return (not self.quiet, self.activity)
            if request[0] in ['chat message 2']:
                unpacked = safe_pickle.loads(request[1])
                # TODO check unpacked against template
                # TODO don't unpack twice (here and in receive task)
                sender = unpacked['from']
                recipients = unpacked['to']
                    
                for recipient in recipients:
                    if recipient[0] == self.app.name_server.public_key_name:
                        break
                    if recipient[2][:1] == '#' and \
                         self.channels.is_listening_to(recipient[2]) and \
                         sender[0] != self.app.name_server.public_key_name:
                        break
                else:
                    return None
            
                if not self.repeated(address,call_id):
                    if self.quiet:
                        new_item = (request, address, time.time())
                        check.check_matches(new_item,
                                            unread_message_list_item_tmpl)
                        # Proof: @R34,@R31, and not having modified request or
                        # address, and the relevant types being immutable
                        # (partly by @E11).  time.time() returns float.
                        # Relevance: @R.I15.
                        self.unread_message_list.append(new_item)
                        self.set_prompt()
                        del new_item
                    else:
                        self.receive(request,address,self.quiet,time.time())
                        # Proof of @R33: @R31; deep immutability by @E11.
                        # Proof of @R35: time.time() returns float.

                return (not self.quiet, self.activity)

        finally:
            self.lock.release()

    

    def show_status(self):
        if self.quiet:
            if self.activity == '':
                self.show(_('You are quiet.\n'))
            else:
                self.show(_('You are quiet: ')+self.activity+'\n')
        else:
            if self.activity == '':
                self.show(_('You are listening.\n'))
            else:
                self.show(_('What you are doing: %s')%self.activity+'\n')

        if self.unread_message_list:
            self.show(_('You have unread messages. Type /read to read them.\n'))

    def remove_channel(self, dest):
        check.check_matches(dest, 'text')  #=@R51
        # Relevance: @R.I31.

        self.lock.acquire()
        try:
            if dest not in self.channel:
                return
            self.channel.remove(dest)
            self.app.refresh_userlist()
            self.set_prompt()
        finally:
            self.lock.release()

    def set_channel(self, dests):
        check.check_matches(dests, ['text'])  #=@R49
        # Relevance: @R.I31.

        self.lock.acquire()
        try:
            self.channel = dests
            for dest in self.channel:
                if dest[0]=='#':
                    self.channel_sub(dest)
                    self.channel_mute(dest,0)
            self.app.refresh_userlist()
            self.set_prompt()
        finally:
            self.lock.release()

    def get_chat_prompt(self):

        if not self.channel:
            str = '['+self.app.config['name']+']'
        else:
            str = '['+self.app.config['name']+' >> '+string.join(self.channel,' ')+']'

        l = len(self.unread_message_list)
        if l:
            str = str + _(' (%d unread)')%l

        return str

        #if not self.use_gtk:
        #    status = utility.get_config('text_status',{ })
        #    status['unread'] = len(self.unread_message_list)
        #    utility.set_config('text_status',status)


    def channel_mute(self, channel, mute=1):
        if self.channels.list[channel]['muted']!=mute:
            self.channels.list[channel]['muted']=mute
            self.app.refresh_userlist()
            if mute:
                self.channels.do_unsub(channel)
            else:
                self.channels.do_sub(channel)

    def channel_sub(self, channel, muted_on_create=0):
        if not self.channels.list.has_key(channel):
            self.channels.list[channel]={'muted': muted_on_create}
            if not muted_on_create:
                self.channels.do_sub(channel)
            self.app.refresh_userlist()

    def channel_unsub(self, channel):
        if self.channels.list.has_key(channel):
                del self.channels.list[channel]
                try:
                    self.channels.do_unsub(channel)
                except error.Error:
                    pass
                self.app.refresh_userlist()
        else:
            pass #should report an error here


    def set_status(self, quiet,activity):
        self.lock.acquire()
        self.quiet = quiet
        self.activity = activity
        self.lock.release()
        self.set_prompt()
        self.app.name_server.set_status('chat',(not quiet,activity))

    def send_message(self, dests, message, attachment=None, augmentation=None):
        check.check_matches(dests, ['text'])
        check.check_is_text(message)

        if self.quiet:
            self.show_status()

        utility.start_thread(chat_tell_thread(
            self,dests,message,attachment,augmentation))



    ###################################################
    #
    # Abstract methods, to be defined in subclass
    #
    
    def is_visible(self):
        """ returns true iff we can display messages  """
        pass

    def handle_watch(self, acq, because_of, **extras):
        pass

    def set_prompt(self):
        pass

    def show_received_message(
        self,sender_name,sender_key_name,address,recipients,
        text,verify_text,verify_sig,quiet,
        send_time,augmentation,has_attachment,attachment):
        pass
    
    def refresh_userlist(self):
        pass

    def create_message_id(self):
        """
        return an identifier for a chat message sent.
        the id will be used by update_message_status
        it may be of any type you wish
        """
        pass

    def update_message_status(self, message_id, status):
        pass
    



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
