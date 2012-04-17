# Name server

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

# TODO: make identify more efficient

# TODO: add check for errors on all try_address or identity_test s

# TODO: remove redundant passing of node

# todo: Use compiled version of rijndael.  E.g. baader says he can't relay IRC
# messages because the python-encryption apparently eats a lot of CPU.  The
# rijndael homepage (http://www.esat.kuleuven.ac.be/~rijmen/rijndael/) has
# implementations of the algorithm in various languages.
# http://www.cr0.net:8040/code/crypto/aes.php has a C implementation that looks
# fairly straightforward.

"""
    This file belongs to the core of circle

    However, name_server is instanciated
    only when a gui is running 
"""


from __future__ import generators
import time,os,types,traceback,select,threading
import sys
import stat
import string
import crypto.RSA
import crypto.rijndael
import check
import error
import hash
import node
import safe_pickle
import settings
import utility


def key_name(key):
    ret = hash.hash_of(safe_pickle.dumps(key))
    check.check_is_name(ret)  #=@E25
    # Proof: @E24.
    return ret

def identity_test_thread(address, key, the_node, id_test_result):
    #from node import Node
    # Test identity
    check.check_is_af_inet_address(address)
    #check.check_isinstance(the_node, Node)

    tester = utility.random_bytes(settings.name_bytes)

    ticket, template, wait = the_node.call(address, ('identity test',tester))
    if wait: yield 'call',(the_node,ticket)
    try:
        result = the_node.get_reply(ticket, template)
    except error.Error,err:
        print "error",err
        id_test_result.append(0)
        return 

    tester = hash.hash_of('identity test '+tester)
    try:
        if not crypto.RSA.construct(key).verify(tester,result):
            print "Fake identity."
            id_test_result.append(0)
            return
    except:
        traceback.print_exc()
        print 'Error in RSA.'
        id_test_result.append(0)
        return
    
    id_test_result.append(1)
    return 


def acquaintance_watch_thread(acq,node):

    if not acq.running:
        return
    pipe = node.retrieve(acq.name, settings.identity_redundancy)

    failures = [ ]
    while not pipe.finished():
        list = pipe.read_all()
        for item in list:
            # Todo: check it is a proper identity!!!!!

            # Make sure we don't watch ourself (for startup detect other peer)
            if item[1].get('peer-name',None) == node.name:
                continue

            if item[0] not in failures:
                try:
                    result, thread = try_address(acq,item[0],node)
                    yield 'wait',thread

                    if acq.online:
                        pipe.stop()
                        return
                except error.Error:
                    failures.append(item[0])

        if not acq.running:
            pipe.stop()
            return

        # Ugh yuck bleah
        yield 'sleep',0.25

    pipe.stop()
    acq.watched = 1


class Acquaintance(utility.Task_manager):
    members = ['info','nickname','name','address','watch','distance','drm']
    info_template = { 'type' : types.StringType,
                      'name' : 'text',
                      'key' : 'public key' }
    status_template = types.DictionaryType
    map_tmpl = {'info': info_template,
                'name': 'name',
                'nickname': 'text'}

    def __init__(self, name_server, map, remember):
        check.check_isinstance(name_server, Name_server)
        check.check_matches(map, self.map_tmpl)
        check.check_has_type(remember, types.IntType)
        check.check_assertion(remember in (0, 1))
        
        utility.Task_manager.__init__(self)
        self.editor_open = 0
        
        self.watch     = 0  # used to tell if the person logs in or out in chat window
                            # nothing to do with 'watchers'
        
        self.distance  = None
        self.drm       = 0

        self.address   = None
        self.watching  = 0
        self.watched   = 0
        self.online    = 0
        self.status    = { }

        # .name and .nickname will be filled in from map.  We initialize
        # them here just to placate pychecker.
        # Note: Don't confuse self.name (check.is_name) with self.info['name']
        # (person's preferred nickname).
        self.name = '(error)'
        self.nickname = '(error)'
        
        self.name_server = name_server
        
        for key,value in map.items():
            setattr(self, key, value)

        self.remember = remember        
        self.check_invar()

    def check_invar(self):
        check.check_is_name(self.name)  #=@I21
    
    def stop(self, node):
        if self.watching:
            self.stop_watching(node)

        utility.Task_manager.stop(self, 1)

    def start_watching(self, node):
        
        if not self.running:
            return

        if not self.watching:
            self.watcher = {
                'type' : 'watch',
                'whom' : self.name
                }
            name = self.name
            watcher = self.watcher
            self.watching = 1

            node.publish(hash.hash_of('watch '+name), watcher, settings.identity_redundancy)

            if not self.online:
                self.watched  = 0
                utility.start_thread(acquaintance_watch_thread(self,node))
            else:
                self.watched  = 1

    def stop_watching(self, node):
        self.lock.acquire()
        try:
            if not self.watching:
                return

            node.unpublish(self.watcher)
            self.watching = 0
            self.watched  = 1 # Wake up any waiters
        finally:
            self.lock.release()

    def sort_value(self):
        self.lock.acquire()
        try:
            if self.distance != None:
                return self.distance
            elif self.watch:
                return 100.0
            else:
                return 101.0
        finally:
            self.lock.release()
            




    def disconnection(self, address):
        """Returns true iff self becomes offline, i.e. if .online was true
           of self and is no longer true of self."""
        became_offline = 0
        self.lock.acquire()
        try:
            if address == self.address:
                became_offline = self.online
                self.online = 0
        finally:
            self.lock.release()

        return became_offline

    def verify(self, str,sig):
        self.lock.acquire()
        try:
            if not crypto.RSA.construct(self.info['key']).verify(hash.hash_of(str),sig):
                raise error.Error(_('Bad signature.'))
        finally:
            self.lock.release()

    def encrypt(self, object):
        self.lock.acquire()
        try:
            key = utility.random_bytes(16)

            pub_key   = crypto.RSA.construct(self.info['key'])
            encryptor = crypto.rijndael.rijndael(key, 16)
            
            encrypted_key  = pub_key.encrypt(key,'')[0]
            encrypted_text = encryptor.encrypt_cbc(safe_pickle.dumps(object))
            
            return (encrypted_key, encrypted_text)
        finally:
            self.lock.release()

    def to_map(self):
        self.lock.acquire()
        try:
            map = { }
            for key in self.members:
                map[key] = getattr(self,key)
            return map
        finally:
            self.lock.release()

    def make_search_info(self):
        self.lock.acquire()
        try:
            return {
                'type': 'acquaintance',
                'nickname': self.nickname,
                'name': self.name,
                'data': self,
                'keywords': [ ]
            }
        finally:
            self.lock.release()
    

def name_server_add_watcher_thread(ns,address):
    if not ns.running:
        return
    if address in ns.watchers:
        return
    ns.watchers.append(address)
    try:
        ticket, template, wait = ns.node.call(
            address,('identity connecting',ns.public_key_name))
        if wait: yield 'call',(ns.node,ticket)
        dummy_result = ns.node.get_reply(ticket,template)
    except error.Error:
        pass


def name_server_watch_poller_thread(self):
    # every 10 minutes, retrieve and update the list of people watching me

    while self.running:
        pipe = self.node.retrieve(hash.hash_of('watch '+self.public_key_name),
                                  settings.identity_redundancy)
        watcher = {
            'type' : 'watch',
            'whom' : self.public_key_name
            }
        
        try:
            while not pipe.finished():
                for item in pipe.read_all():
                    if item[1] == watcher:
                        if item[0] not in self.watchers:
                            utility.start_thread(
                                name_server_add_watcher_thread(self,item[0]))
                if not self.running:
                    return
                # Ugh yuck bleah
                yield 'sleep',2
        except:
            pass
        pipe.stop()
        
        yield 'sleep',10*60


def try_address(acq, address, the_node):
    """returns a boolean."""

    def try_address_thread(self, address, the_node, result):

        if self.online and self.address == address:
            result.append(0)
            return 

        key = self.info['key']
        id_test_result = []
        yield 'wait', identity_test_thread(address, key, the_node, id_test_result)
        if not id_test_result[0]:
            print "identity did not pass test"
            #result.append(0)
            #return

        ticket,template, wait = the_node.call(address,('identity query',))
        if wait: yield 'call',(the_node,ticket)
        try:
            info = the_node.get_reply(ticket,template)
        except:
            result.append(0)
            return

        if not check.matches(info, Acquaintance.info_template):
            node.bad_peer(address,
                     _("bad response to 'identity query': ") + `info`)
            result.append(0)
            return 
        self.info = info

        if info.get('peer-name') == the_node.name:
            result.append(0)
            return 

        ticket,template, wait = the_node.call(address,('identity watch',))
        if wait: yield 'call',(the_node,ticket)
        try:
            status = the_node.get_reply(ticket,template)
        except:
            result.append(0)
            return

        if type(status) != types.DictionaryType:
            status = { }

        was_online = self.online
        self.address  = address
        self.online   = 1
        self.watched  = 1
        self.status = status

        # up_time is an interval. connect_time is time in my zone.
        up_time = self.info.get('up time')
        if type(up_time) == types.IntType:
            self.connect_time = time.time() - up_time
        else:
            self.connect_time = None

        if self.drm:
            the_node.trusted_addresses.append(address)
        else:
            while address in the_node.trusted_addresses:
                the_node.trusted_addresses.remove(address)

        self.start_watching(the_node)

        self.name_server.acquaintance_status_changed(self, 'discover')

        result.append(not was_online)
        return


    result = []
    return result, try_address_thread(acq, address, the_node, result)



def make_acquaintance_thread(result, self, info,address=None):

    # Currently, many callers don't do their own error checking.
    if not info.has_key('type') or \
         not info.has_key('name') or \
         not info.has_key('key')  or \
         info['type'] not in ['identity','identity offline demangled']:
        raise error.Error(_('Not an identity.'))
    if not check.is_text(info['name']):
        raise error.Error('bad acquaintance info: name field not a string.')
    if not check.is_public_key(info['key']):
        raise error.Error('bad acquaintance info: key field not a public key.')
    name = key_name(info['key'])
    self.lock.acquire()
    if self.acquaintances.has_key(name):
        self.lock.release()
        if address:
            try_result, subthread = try_address(self.acquaintances[name],address,self.node)
            yield 'wait',subthread
        result.append(self.acquaintances[name])
        return
    try:
        acq = Acquaintance(
            self, {'info': info,'name': name,
                   'nickname': self.choose_nickname(info['name'])}, 0)
        # Proof of @R44: checked at head of this method that info has
        # a 'name' key and that info['name'] is a string, which is
        # text by @E23.
        self.acquaintances[name]     = acq
        self.nicknames[acq.nickname] = acq
    finally:
        self.lock.release()
    acq.start()
    if address:
        try_result, subthread = try_address(acq,address,self.node)
        yield 'wait',subthread
    acq.start_watching(self.node)
    self.acquaintance_status_changed(acq, "create")
    result.append(acq)
    return 




class Name_server(utility.Task_manager):
    def __init__(self, app, node, random_func):
        utility.Task_manager.__init__(self)

        self.app = app
        self.node = node

        self.key = utility.get_config("private_key",None)

        if self.key == None:
            random = random_func()
            self.key = crypto.RSA.deconstruct(crypto.RSA.generate(1024,random.randfunc))
            random.finish()
            utility.set_config("private_key",self.key)

        self.key  = crypto.RSA.construct(self.key)
        self.public_key = crypto.RSA.deconstruct(self.key.publickey())
        self.public_key_name = key_name(self.public_key)
        self.public_key_name_offline = hash.hash_of('identity-offline '+key_name(self.public_key))
        self.name   = None
        self.info   = { }
        self.status = { }    # eg chat status stored under 'chat' key

        # For searching for all people
        self.service_name = hash.hash_of("service identity")

        self.acquaintances = { }
        self.nicknames     = { }

        self.watchers      = [ ]                    #the people who are watching me
        
        self.watch_callbacks = [ ]

        self.start_time = time.time()

        self.get_info_func = lambda self=self: self.app.name_server.get_info()
        # - has to be a distinct object to allow unpublish
 
        self.aborted = 0
        self.disconnect_threads = 0

        # Proof of @R.I22: @E25
        self.check_invar()

    def check_invar(self):
        check.check_is_name(self.public_key_name)  #=@I22
    
    def add_watch_callback(self, object):
        self.lock.acquire()
        try:
            self.watch_callbacks.append(object)
        finally:
            self.lock.release()
    
    def remove_watch_callback(self, object):
        self.lock.acquire()
        try:
            self.watch_callbacks.remove(object)
        finally:
            self.lock.release()

    def set_status(self, key,value):
        self.lock.acquire()
        try:
            if not self.status.has_key(key) or \
                 self.status[key] != value:
                self.status[key] = value

                def id_change_thread(self, address, status):
                    try:
                        ticket, template, wait = self.node.call(
                            address,('identity status changed',self.public_key_name,status))
                        if wait: yield 'call',(self.node,ticket)
                        result = self.node.get_reply(ticket, template)
                    except error.Error:
                        pass
                for item in self.watchers:
                    utility.start_thread(id_change_thread(self,item,self.status))
        finally:
            self.lock.release()
    
    def set_name(self, name, human_name, description):
        """called before start"""
        if name == self.info.get('name') and \
             human_name == self.info.get('human-name') and \
             description == self.info.get('description'):
            return
    
        now = time.time()
        timezone = long(time.mktime(time.gmtime(now)) - now)

        new_info = {
            'type'       : 'identity',
            'name'       : name,
            'human-name' : human_name,
            'description': description,
            'timezone'   : timezone,
            'key'        : self.public_key,
            'peer-name'  : self.node.name, # Used in startup
            'keywords'   : [ name ] + string.split(string.lower(human_name))
        }

        self.lock.acquire()
        running = self.running
        self.lock.release()

        if running:
            self.stop('Reconfiguring')

        self.name = name
        self.info = new_info

        if running:
            self.start()


    def get_info(self):
        up_time = time.time() - self.start_time

        # Try to make it a reasonable number (in case someone's reset the
        # system clock).  We could make a more accurate guess than this, but
        # up-time isn't used for much.
        # Note: this code is duplicated in cache.py.
        if up_time < 0.0:
            up_time = 10.0 * 60
            self.start_time = time.time() - up_time
        elif up_time > 365 * 24 * 60 * 60.0:
            up_time = 25 * 60 * 60.0
            self.start_time = time.time() - up_time

        self.info['up time'] = int(up_time)
        return self.info
    
    def start(self, status_monitor=None):
        utility.Task_manager.start(self)

        acq_list = utility.get_checked_config('acquaintances', types.ListType, [ ])
        for item in acq_list:
            if not check.matches(item, Acquaintance.map_tmpl):
                print _("Warning: corrupted acquaintances config file; ignoring item: "), item
                continue

            acq = Acquaintance(self, item, 1)
            self.acquaintances[acq.name] = acq
            self.nicknames[acq.nickname] = acq
            acq.start()


        def make_acquaintance_noaddr(self, info):

            name = key_name(info['key'])

            acq = Acquaintance(self, {'info': info,
                                          'name': name,
                                          'nickname': self.choose_nickname(info['name'])},0)
            self.acquaintances[name]     = acq
            self.nicknames[acq.nickname] = acq

            acq.start()
            acq.start_watching(self.node)
            self.acquaintance_status_changed(acq, "create")

            return acq

        self.me = make_acquaintance_noaddr(self,self.info)

        # Other me may want to test identity
        # May start chatting before test complete
        self.node.add_handler('identity test', self, ('name',), crypto.pubkey.signature_tmpl)
        self.node.add_handler('identity query', self, (), Acquaintance.info_template)
        self.node.add_handler('identity watch', self, (), types.DictionaryType)
        self.node.add_handler('identity connecting', self)
        self.node.add_handler('identity status changed', self, ('any', Acquaintance.status_template))
        self.node.add_handler('identity disconnecting', self,('string', 'opt-text'))
        self.node.add_handler('identity abort', self)

        self.node.publish(self.public_key_name,self.get_info_func, settings.identity_redundancy)
        self.node.publish(self.public_key_name_offline,self.get_info_func, settings.identity_redundancy)
        self.node.publish(self.service_name,self.get_info_func, settings.identity_redundancy)
        for item in self.info['keywords']:
            self.node.publish(hash.hash_of('identity-name '+item),
                              self.get_info_func, settings.identity_redundancy)

        def startup_thread(self, status_monitor=status_monitor):
            
            list = self.acquaintances.values()
            list.sort(lambda x,y: cmp(x.sort_value(),y.sort_value()))
            for item in list:
                item.start_watching(self.node)

                #start watching tends to breed, try to make sure we don't get
                #too many threads.
                #yes, this is hacky
                #print item.nickname, threading.activeCount()
                #time.sleep(0.25)

                while 1:
                    yield 'sleep',0.25
                    if threading.activeCount() < 40:
                        break
                 
            self.me.start_watching(self.node)
            while not self.me.watched:
                yield 'sleep',0.1
            
            online = self.me.online
            address = self.me.address
            if online:
                if status_monitor:
                    status_monitor(_('Shutting down your other peer.'))
                while 1:
                    ticket,template,wait = self.node.call(address, ('identity abort',))
                    if wait: yield 'call',(self.node,ticket)
                    try:
                        dummy_result = self.node.get_reply(ticket, template)
                    except error.Error:
                        break
                    yield 'sleep',4
            
            self.me.online  = 1
            self.me.address = self.node.address
            self.me.connect_time = time.time()
            # Task to retrieve existing watchers
            # Task to poll existing watchers
            utility.start_thread(name_server_watch_poller_thread(self))
            # now refresh my own offline presence
            pipe = self.node.retrieve(self.public_key_name_offline, settings.cache_redundancy)
            list = [ ]

            while not pipe.finished():
                for item in pipe.read_all():
                    if type(item[1]) == types.DictType and \
                           item[1].get('type') == 'identity offline' and \
                           item[1].get('salt'):
                        list.append(item)
                yield 'sleep',2
                if not self.running:
                    return
            pipe.stop()

            #if len(list) != 4:
            #    print _("%d peers holding your offline presence.") % len(list)

            for item in list:
                address, value = item
                key = hash.hash_of(safe_pickle.dumps(self.sign(value['salt'])))
                ticket, template, wait = self.node.call(address, ('data cache remove',key))
                if wait: yield 'call',(self.node,ticket)
                try:
                    dummy_result = self.node.get_reply(ticket,template)
                except error.Error:
                    pass

            self.lock.acquire()
            try:
                package = {
                    'name'       : self.info['name'],
                    'human-name' : self.info['human-name'],
                    'description': self.info['description'],
                    'timezone'   : self.info['timezone'],
                    'key'        : self.public_key,
                    'keywords'   : self.info['keywords'],
                }
            finally:
                self.lock.release()

            package_dumped = safe_pickle.dumps(package)
            signature = self.sign(package_dumped)


            # now publish and cache offline identity
            value = {
                'type' : 'identity offline',
                'package' : package_dumped,
                'signature' : signature,
                'salt' : utility.random_bytes(settings.name_bytes)
            }
            lock = hash.hash_of(hash.hash_of(safe_pickle.dumps(self.sign(value['salt']))))
            publications = [ self.public_key_name_offline, self.service_name ]
            for item in package['keywords']:
                publications.append(hash.hash_of('identity-name '+item))
            # thomasV
            # redundancy 4: this is the meta-publish
            result, publish_thread = self.app.cache.publish(publications,value,lock, 4)
            yield 'wait',publish_thread
            
        utility.start_thread(startup_thread(self))

    def bad_address(self, address):
        for item in self.acquaintances.items():
            acq=item[1]
            if acq.online and acq.address==address:
                if acq.disconnection(address):
                    self.acquaintance_status_changed(acq, 'no reply')
                break
              

    def stop(self, quit_message):
        check.check_is_opt_text(quit_message)

        self.change_activity('saving acquaintance details')
        self.save()

        # Inform watchers of going offline
        self.change_activity('informing watchers of going offline')

        self.running = 0
        
        def id_disconnect_thread(self, address, quit_message=quit_message):
            self.disconnect_threads+=1
            try:
                ticket, template, wait = self.node.call(
                    address,('identity disconnecting',self.public_key_name,quit_message))
                if wait: yield 'call',(self.node,ticket)
                result = self.node.get_reply(ticket, template)
            except error.Error,err:
                #print "error on disconnecting",err,address
                pass
            except:
                pass
            self.disconnect_threads-=1

        # self.watchers might change while we are disconnecting (especially due to 127.0.0.1)
        # so we need to copy them before
        if not self.aborted:
            threads = []
            for item in self.watchers:
                threads.append(id_disconnect_thread(self,item))
            for thread in threads:
                utility.start_thread(thread)

        self.watchers      = [ ]        
        list = self.acquaintances.values()
        self.change_activity('calling acq.stop_watching')
        for item in list:
            def stopper_task(self, item):
                item.stop(self.node)
            utility.Task(stopper_task, self, item).start()    
        #note that this might wait for all tasks: could be long
        utility.Task_manager.stop(self)            

        self.change_activity('unpublishing self')
        self.node.unpublish(self.get_info_func)

        self.change_activity('removing handlers')
        self.node.remove_handler('identity test')
        self.node.remove_handler('identity query')
        self.node.remove_handler('identity watch')
        self.node.remove_handler('identity connecting')
        self.node.remove_handler('identity status changed')
        self.node.remove_handler('identity disconnecting')
        self.node.remove_handler('identity abort')
        
        # Remove cyclical dependancy in ref counting
        self.acquaintances = { }
        self.nicknames     = { }
        self.change_activity('')

    def save(self):
        self.lock.acquire()
        try:
            list = [ ]
            for item in self.acquaintances.values():
                if item.remember:
                    list.append(item.to_map())
            utility.set_config('acquaintances', list)
        finally:
            self.lock.release()

    def sign(self, str):
        return self.key.sign(hash.hash_of(str),'')

    def decrypt(self, crypt):
        # Todo: catch errors
        self.lock.acquire()
        try:
            encrypted_key, encrypted_text = crypt

            key = self.key.decrypt((encrypted_key,))
            while len(key) < 16:
                key = chr(0)+key

            decryptor = crypto.rijndael.rijndael(key, 16)
            text      = decryptor.decrypt_cbc(encrypted_text)

            return safe_pickle.loads(text)
        finally:
            self.lock.release()

    def acquaintance_status_changed(self, acq, because_of, **extras):
        self.lock.acquire()
        callbacks = self.watch_callbacks[:]
        self.lock.release()

        for item in callbacks:
            apply(item.handle_watch,(acq,because_of),extras)

    def handle(self, request, address,call_id):
        check.check_matches(request, (types.StringType,))
        check.check_is_af_inet_address(address)  #=@R30
        
        if request[0] == 'identity test':
            check.check_matches(request[1:], ('name',))
            
            return self.sign('identity test ' + request[1])
        
        elif request[0] == 'identity query':
            return self.get_info()
        elif request[0] == 'identity watch':
            self.lock.acquire()
            try:
                if address not in self.watchers:
                    self.watchers.append(address)
                status = self.status
            finally:
                self.lock.release()
            return status
        elif request[0] == 'identity abort':
            def abort_thread(self, address=address):
                id_test_result = []
                yield 'wait', identity_test_thread(address,self.public_key,self.node,id_test_result)
                if not id_test_result[0]:
                    print "error testing identity"
                    return
                self.aborted = 1
                self.app.shutdown(_('Reconnecting from different machine'))
            utility.start_thread(abort_thread(self))
            return None
        elif request[0] == 'identity connecting':
            if not (len(request) >= 2):
                return error.Error('Name_server.handle: identity connecting: expecting tuple of at least 2.')
            self.acquire_lock('get acq')
            try:
                acq = self.acquaintances.get(request[1])
            finally:
                self.release_lock('get acq')
            if acq is None:
                return error.Error(_("I don't know you."))
            else:
                #if len(request) > 2:
                #  status = request[2]
                #else:
                #  status = { }

                def acq_change_thread(ns, acq, address, call_id, node):
                    check.check_is_af_inet_address(address)  #=@R29
                    
                    try:
                        result, subthread = try_address(acq,address,node)
                        yield 'wait',subthread
                        if not result[0]:
                            return
                    except error.Error:
                        return

                    #acq.lock.acquire()
                    #acq.status = status
                    #acq.lock.release()
                    ns.acquaintance_status_changed(acq, 'connect')
                utility.start_thread(acq_change_thread(self, acq, address, call_id, self.node))
                # Proof of @R29: @R30; deeply immutable by @E11.

                return None

        elif request[0] == 'identity status changed':
            if not (len(request) >= 3):
                return error.Error('Name_server.handle: identity status changed: expecting tuple of at least 3.')
            self.lock.acquire()
            try:
                acq = self.acquaintances.get(request[1],None)
                if acq:
                    acq.lock.acquire()
                    try:
                        acq.status = request[2]
                    finally:
                        acq.lock.release()
                    self.acquaintance_status_changed(acq, 'status changed')
            finally:
                self.lock.release()
        elif request[0] == 'identity disconnecting':
            if not (len(request) >= 2):
                return error.Error('Name_server.handle: identity disconnecting: expecting tuple of at least 2.')
            self.lock.acquire()
            if address in self.watchers:
                self.watchers.remove(address)
            
            if self.acquaintances.has_key(request[1]):
                acq = self.acquaintances[request[1]]
                self.lock.release()
                if acq.disconnection(address):
                    self.acquaintance_status_changed(acq, 'disconnect', message=request[2])
                return None
            else:
                self.lock.release()
                return error.Error(_("I don't know you."))

    def choose_nickname(self,name):
        """Note You must hold self.lock when calling this method, and you must
           update self.nicknames before releasing the lock."""
        #check.check_assertion(self.is_locked_by_this_thread())
        check.check_is_text(name)  #=@R44 fixme callers
        
        if name == '':
            name = 'unknown'
        i = 0
        nick = name
        while self.nicknames.has_key(nick):
            i = i + 1
            nick = name + ('%d'%i)

        check.check_is_text(nick)
        # Loose proof: name is initially checked to be text;
        # the only subsequent assignment is from a string (which is text by
        # @E23).  nick is assigned from either name or from (name + a string);
        # +(text,string) = text.
        return nick

    def change_nickname(self, acq,new_nick):
        check.check_isinstance(acq, Acquaintance)  # fixme callers
        check.check_is_text(new_nick)  # fixme callers
        
        self.acquire_lock('chg nk')
        try:
            if new_nick == acq.nickname:
                return
            if self.nicknames.has_key(new_nick):
                raise error.Error(_("There is someone else with the nickname %s")%new_nick)
            del self.nicknames[acq.nickname]
            self.nicknames[new_nick] = acq
            acq.nickname = new_nick
        finally:
            self.release_lock('chg nk')


    def locate(self, nick):
        if not self.nicknames.has_key(nick):
            raise error.Error(
                _('That person is not in the list of acquaintances.\n'+\
                  'You need to search for %s before you can talk to them.')%nick)
        return self.nicknames[nick]



    def identify(self, name,address):
        """called upon receival of a chat message"""
        check.check_is_opt_address(address)  #=@R32

        def identify_thread(self, result, name, address):

            if self.acquaintances.has_key(name):
                acq = self.acquaintances[name]
                acq_online = acq.online
                acq_address = acq.address

                # May as well test the address
                if address is not None and \
                       (not acq_online or address != acq_address):
                    dummy_result, subthread = try_address(acq,address,self.node)
                    yield 'wait', subthread
                result.append(acq)
                return

            if address is None:
                return
                #raise error.Error('no address')

            ticket, template, wait = self.node.call(address, ('identity query',))
            if wait: yield 'call', (self.node,ticket)
            try:
                info = self.node.get_reply(ticket,template)
            except:
                print "cannot identify"
                result.append(None)
                return
            
            acq_result, thread = self.make_acquaintance(info,address)
            yield 'wait',thread
            result.append(acq_result[0])
            return

        result = []
        thread = identify_thread(self,result,name,address)
        return result,thread

 
    def make_acquaintance(self, info, address=None):
        """returns the acquaintance just made"""
        result = []
        thread = make_acquaintance_thread(result, self, info,address)
        return result, thread


    def make_acquaintance_sync(self, info, on_complete, app, address=None):
        """
        to be called by the gui. on_complete is executed in the gui thread        
        """
        def make_acq_thread(self,info,on_complete,app,address):
            try:
                result, thread = self.make_acquaintance(info,address)
                yield 'wait',thread                
                app.idle_add(on_complete,result[0])
            except error.Error, err:
                app.idle_add(app.show_error,err)
                return
        utility.start_thread(make_acq_thread(self,info,on_complete,app,address))


    def forget(self,nickname):
        acq = self.locate(nickname)            
        self.acquaintances.__delitem__(acq.name)
        self.node.unpublish(acq.watcher)
        self.nicknames.__delitem__(nickname)
        self.acquaintance_status_changed(acq, 'deleted')
        del acq
 

    def check_acquaintance(self,identity_list,nickname):
        """this is the function called by most chat commands"""

        def check_acquaintance_thread(result,self,identity_list,nickname):
            """try to make an acquaintance from list of search results"""
            try:
                acq = self.locate(nickname)
                acq.status_known = 1
                result.append(acq)
                return
            except:
                for item in identity_list:
                    if item.item['name'] == nickname:
                        dummy_result, thread = self.make_acquaintance(item.item)
                        yield 'wait',thread
                        acq = self.locate(nickname)
                        if item.item['type']== 'identity':
                            dummy_result, thread = try_address(acq,item.address,self.node)
                            yield 'wait',thread
                            acq.address = item.address
                            acq.status_known = 0
                        else:
                            acq.address = None
                            acq.online = 0
                            acq.status_known = 1
                        result.append(acq)
                        return 
                else:
                    return
                
        result = []
        thread = check_acquaintance_thread(result,self,identity_list,nickname)
        return result, thread



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
