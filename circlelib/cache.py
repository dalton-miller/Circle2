# Caching data for others

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001,2002  Paul Francis Harrison
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

# TODO: barf if can't offload
# TODO: barf if no caches in pool

from __future__ import generators
import time, random, threading, types

import check
from error import Error
import hash
import settings
import utility

class Cache_item:
    def __init__(self, names,data,expiry_interval,call):
        self.names = names
        self.data = data
        self.expiry_time = time.time() + expiry_interval
        self.call = call

class Cache(utility.Task_manager):
    def __init__(self, node):
        utility.Task_manager.__init__(self)

        self.node = node

        self.start_time = time.time() # for up_time

        self.cache_pool = [ ]   # list of known caches
        self.cache_pool_last_refresh  = 0.0
        self.cache_pool_original_size = 0
        self.cache_pool_lock = threading.RLock()

        self.data = {
            'type'            : 'service data cache',
            'up time'         : 0,
            'max expiry time' : 30*24*60*60 
        }

        self.name = hash.hash_of('service data cache')

        self.queued_items = [ ]

        self.cached_items = { }

    def data_function(self):
        up_time = time.time() - self.start_time

        # Try to make it a reasonable number (in case someone's reset the
        # system clock).  We could make a more accurate guess than this, but
        # up-time isn't used for much.
        # Note: this code is ~duplicated in name_server.py.
        if up_time < 0.0:
            up_time = 10.0 * 60
            self.start_time = time.time() - up_time
        elif up_time > 365 * 24 * 60 * 60.0:
            up_time = 25 * 60 * 60.0
            self.start_time = time.time() - up_time
        
        self.data['up time'] = int(up_time)
        return self.data

    def start(self):
        utility.Task_manager.start(self)

        self.node.publish(self.name, self.data_function, settings.cache_redundancy)
        self.node.add_handler('data cache store', self, ('name', 'name', {'type':types.StringType}, 'integer'))
        self.node.add_handler('data cache store multi', self, ('name', ['name'], {'type':types.StringType}, 'integer'))
        self.node.add_handler('data cache remove', self, ('text',))

    def stop(self):
        self.node.unpublish(self.data_function)
        self.node.remove_handler('data cache store')  # lock, name, data, expiry_interval
        self.node.remove_handler('data cache store multi')  # lock, [name,name,...], data, expiry_interval
        self.node.remove_handler('data cache remove') # key

        # here the cached items are handed over to other nodes.
        # redundancy is 1 to avoid amplification.
        # thomasV: in order to ensure redundancy: use redundancy 4 instead of 1 below
        for item in self.cached_items.items():
            result, subthread = self.publish(
                item[1].names,item[1].data,item[0],4,
                int(item[1].expiry_time-time.time()))
            yield 'wait',subthread


            # note: here too I need to know when the thread finishes.

        utility.Task_manager.stop(self)

    def handle(self, request,address,call_id):
        check.check_matches(request, (types.StringType,))
        check.check_is_af_inet_address(address)
        
        # Idempotence is a bugger

        if request[0] == 'data cache store' or \
             request[0] == 'data cache store multi':
            self.lock.acquire()
            try:
                if self.cached_items.has_key(request[1]):
                    if self.cached_items[request[1]].call == (address,call_id):
                        return None
                    return Error('already storing')

                if request[0] == 'data cache store':
                    names = [ request[2] ]
                else:
                    names = request[2]

                if len(names) > settings.max_cache_names:
                    return Error('too many names')
                
                item = Cache_item(names,request[3],request[4],(address,call_id))
 
                self.cached_items[request[1]] = item

                # here is the actual publish: redundancy is settings.cache_redundancy
                for name in names:
                    self.node.publish(name, request[3], settings.cache_redundancy)
            finally:
                self.lock.release()
            return None

        if request[0] == 'data cache remove':
            self.lock.acquire()
            try:
                lock = hash.hash_of(request[1])
                if self.cached_items.has_key(lock):
                    self.node.unpublish(self.cached_items[lock].data)
                    del self.cached_items[lock]
            finally:
                self.lock.release()

            return None


    
    def publish(self, names, data, lock, redundancy=settings.cache_redundancy, expiry=None):
        """
        This is a meta-operation: it publishes in the
        cache of redundancy nodes, which will themselves
        publish the data with their own method node.publish
        
        Returns a non-negative integer representing the number of nodes at
        which the data has been stored."""
        
        check.check_matches(names, ['name'])
        check.check_matches(data, {'type': types.StringType})
        check.check_is_name(lock)

        def publish_thread(self, result, names, data, lock, redundancy, expiry):

            if not (self.cache_pool_last_refresh+10*60 > time.time() or \
                 len(self.cache_pool) > self.cache_pool_original_size/2):

                cache_pool = [ ]

                pipe = self.node.retrieve(self.name, settings.cache_redundancy)

                while len(cache_pool) < 50 and not pipe.finished():
                    list = pipe.read_all()
                    for item in list:
                        check.check_matches(item, ('af_inet_address', 'any'))
                        # Proof: @E6.  Combine with @E10 and the fact that we don't
                        # pass pipe to anything else (nor write to it ourselves
                        # other than through pipe.read_all()) to show that @E6
                        # isn't broken by some other write.

                        if type(item[1]) != types.DictionaryType:
                            # todo: consider printing debug info
                            continue

                        if item[1].get('type','') == 'service data cache':
                            #cache_pool.append((-item[1]['up time'],item[0],item[1]))
                            
                            up_time = item[1].get('up time')

                            if type(up_time) != types.IntType:
                                # todo: consider printing debug info
                                continue

                            # Treat all up for over a day as equal to share load
                            if up_time > 24*60*60:
                                up_time = 24*60*60 + random.random()

                            cache_pool.append((-up_time,item[0],item[1]))
                        
                    yield 'sleep',1

                pipe.stop()
                self.cache_pool = cache_pool
                self.cache_pool.sort()
                self.cache_pool_original_size = len(self.cache_pool)

            if not expiry:
                expiry = self.data['max expiry time']

            if expiry < 0:
                result.append(0)
                return 

            pool = self.cache_pool[:]
            bad_items = [ ]

            pos = 0
            n   = 0
            while n < redundancy:
                if len(pool) <= pos:
                    result.append(n)
                    return 

                try:
                    if len(names) == 1:
                        ticket, template, wait = self.node.call(
                            pool[pos][1],('data cache store',lock,names[0],data,expiry))
                        if wait: yield 'call',(self.node,ticket)
                        dummy_result = self.node.get_reply(ticket, template)
                    else:
                        ticket, template, wait = self.node.call(
                            pool[pos][1],('data cache store multi',lock,names,data,expiry))
                        if wait: yield 'call',(self.node,ticket)
                        dummy_result = self.node.get_reply(ticket, template)
                except Error, error:
                    if error.message != 'already storing':
                        bad_items.append(pool[pos])
                    else:
                        # thomasV: we need to limit amplification
                        # print 'already storing', pool[pos]
                        n = n + 1
                        # end thomasV
                    pos = pos + 1
                    continue
                pos = pos + 1
                n   = n   + 1

            self.cache_pool_lock.acquire()
            try:
                for item in bad_items:
                    if item in self.cache_pool:
                        self.cache_pool.remove(item)
            finally:
                self.cache_pool_lock.release()

            result.append(n)
            return 
    
        result = [ ]
        return result, publish_thread(
            self,result, names, data, lock, redundancy, expiry)



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
