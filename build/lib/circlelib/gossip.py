# Gossip exchange system

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

from __future__ import generators
import string
import time
import types
import check
import error
import node
import safe_pickle
import hash
import settings
import utility

# A wodge contains:
#
#  'post-time'
#  'author'
#  'subject'
#  'text'
#
# As a map with prepended signature.
#
# Also remember: minimum distance to me, sources

# Todo:

# njh: make gossips appear as they are found, incrementally.


# Currently, 'gossip list' is one of the biggest items in the network
# profile (/stats -p).  'gossip list' conversations involve sending
# the full list of gossip, which is inefficient given that usually
# very little has changed (except for the time-based decay, which the
# caller can calculate for themselves).  Note that 'gossip list'
# conversations apparently take place hourly (see Gossip.start,
# which schedules a gossip_sync_poller in 20 seconds then once per hour
# after that).
#
# Ouch, actually, it looks to me as if it gets called every time
# show_gossip is called with update!=0: show_gossip calls request_update,
# which calls run_poller_now, which calls self.poller_function which
# I think equals the poller function defined in start_poller, which
# calls func, which I think equals gossip_sync_poller.  Furthermore,
# it seems that having gossip_sync_poller as a poller function doesn't
# do anything, since it seems that the only way to add to
# gossip_obj.update_requests is to call request_update, which gets
# gossip_sync_poller called [conditional on running], which clears
# gossip_obj.update_requests.  I haven't checked this very carefully.
#
# The proposed fix is that each time a change occurs, we increment
# a gossip event counter for this peer (saved to disk), and store the
# new event counter value in the affected wodge.
# Give out wodge info in order of increasing event counter value (i.e.
# from oldest to most recently changed wodge).  Clients can use their
# most recent event counter value instead of a position number.
#
# Specific changes:
#
#   - Add attribute .change_stamp to Wodge.  This gets saved to disk.
#
#   - When reading wodges from disk, we initialize our counter from
#     the highest-numbered .change_stamp read.
#
#   - When saving wodges to disk, ensure that the highest-numbered
#     corresponds to our event counter value.  (It may not due to
#     deletions.)  Add a dummy item to the list if necessary.
#
#   - With each stored acquaintance, store that acquaintance's event
#     bookmark of that acquaintance along with the trust distance.


# There is a denial-of-service opportunity with 'gossip list',
# but it's nothing more than already exists through retrieving files.
# I think that should be addressed at a global level: limit
# how much / how quickly we send to any given peer.


class Wodge:
    #Members:
    #  wodge_string
    #  wodge
    #  distance
    member_tmpls = {
        'wodge': 'any',
        'string': 'any',
        'signature': 'any',
        'initial_time': 'any',
        'initial_distance': 'any', # user's opinion at initial_time, or None
        'unit_decay_time': 'int',
        'opinions': types.DictionaryType,
        'collapsed': types.IntType
    }

    def __init__(self, map):
        self.togglees = [ ] # Calls to make to update display if wodge is folded/unfolded
        self.wodge = None
        self.string = None
        self.signature = None
        self.initial_time = None
        self.initial_distance = None
        self.unit_decay_time = 60*60*24*7
        self.opinions = { }    # acq.name -> distance at initial_time
        self.collapsed = 0
        
        for (key, tmpl) in self.member_tmpls.items():
            if map.has_key(key):
                val = map[key]
                if check.matches(val, tmpl):
                    setattr(self, key, val)

        # .initial_time.
        if type(self.initial_time) in (types.FloatType, types.IntType, types.LongType):
            try:
                self.initial_time = float(self.initial_time)
            except:
                self.initial_time = None
        if type(self.initial_time) != types.FloatType:
            self.initial_time = time.time()

        # .opinions.
        for (key, dist) in self.opinions.items():
            if type(dist) not in (types.FloatType, types.IntType, types.LongType):
                del self.opinions[key]

    def add_togglee(self, togglee):
        self.togglees.append(togglee)

    def remove_togglee(self, togglee):
        self.togglees.remove(togglee)

    def toggle(self):
        self.collapsed = (int)(not self.collapsed)
        for togglee in self.togglees:
            togglee(self.collapsed)

    def to_map(self):
        map = { }
        for key in self.member_tmpls.keys():
            map[key] = getattr(self,key)
        return map

    def adjust_decays(self):
        "Make sure distance decays at least while we are online if clock is skewing."
        decay = self.decay()
        self.initial_time = time.time()
        if self.initial_distance is not None:
            self.initial_distance += decay
        for key in self.opinions.keys():
            self.opinions[key] += decay

    def decay(self):
        """Returns the amount of decay (i.e. distance increase) since initial.
           Doesn't modify this wodge."""

        value = (time.time() - self.initial_time) / self.unit_decay_time
        if value < 0.0:
            return 0.0
        else:
            return value

    def distance(self, name_server, perspective=None):
        decay = self.decay()

        if perspective:
            value = self.opinions.get(perspective)
            if value:
                return value + decay
            
            return 1000.0 #Lots

        initial_distance = self.initial_distance
        if initial_distance == None:
            initial_distance = 1000.0 #Lots

            for pair in self.opinions.items():
                acq = name_server.acquaintances.get(pair[0])
                if acq:
                    acq_distance = acq.distance
                    if acq_distance is not None:
                        distance = acq_distance + pair[1]
                        if distance < initial_distance:
                            initial_distance = distance
        
        return initial_distance + decay

                
def to_fixed(value):
    return int(value*256+0.5)

def from_fixed(value):
    return value / 256.0

def gossip_poll_thread(gossip):
    yield 'sleep',20    
    while gossip.running:
        yield 'wait', gossip.sync_gossip_thread()
        yield 'sleep',60*60

class Gossip:
    def __init__(self, app):

        self.app = app
        self.node = app.node

        self.any_gossip_gets = 0

        self.update_requests = [ ]

        gossip_list = utility.get_config("gossip", [ ])
        self.gossip = [ ]
        for item in gossip_list:
            if type(item) != types.DictionaryType:
                print _("Warning: ignoring corrupt gossip item: "), `item`
                continue
            wodge = Wodge(item)
            wodge.adjust_decays()
            self.gossip.append(wodge)

    def check_invar(self):
        check.check_has_type(self.gossip, types.ListType)
        for wodge in self.gossip:
            check.check_isinstance(wodge, Wodge)
    
    def start(self):
        self.running = 1
        self.node.add_handler('gossip list', self,
                              (types.IntType, types.IntType))
        self.node.add_handler("gossip get",self)

        if self.app.config.get('poll_gossip'):
            utility.start_thread(gossip_poll_thread(self))

    def stop(self):
        self.running = 0
        self.node.remove_handler("gossip list")
        self.node.remove_handler("gossip get")
        self.save()
        
    def save(self):
        gossip_list = [ ]
        for item in self.gossip:
            gossip_list.append(item.to_map())
        utility.set_config("gossip", gossip_list, 1)

    def request_update(self, callback):
        self.update_requests.append(callback)
        utility.start_thread(self.sync_gossip_thread())

    def sorted_wodges(self, perspective=None):
        list = [ ]
        for item in self.gossip:
            list.append((item.distance(self.app.name_server, perspective),item))
        list.sort()
        return list

    def sync_gossip_thread(self):
        
        def gossip_fetch_thread(self,acq):
            self.fetch_threads+=1
            
            if not self.running:
                self.fetch_threads-=1
                return

            if acq.distance != None:
                #acq.start_watching(self.node, 1)
                
                acq.lock.acquire()
                online = acq.online
                address = acq.address
                distance = acq.distance
                acq.lock.release()

                if distance == None or not online:
                    self.fetch_threads-=1
                    return

                pos = 0
                fetch_timeout = node.make_timeout(settings.gossip_fetch_time) 
                while not node.is_timed_out(fetch_timeout):
                    try:
                        ticket, template, wait = self.node.call(address,('gossip list',pos,pos+20))
                        if wait: yield 'call',(self.node,ticket)
                        result = self.node.get_reply(ticket,template)
                        
                        if not check.matches(result,
                                             [(types.IntType, 'any', 'any')]):
                            node.bad_peer(address,
                                     _("Bad reply to 'gossip list': ") + `result`)
                            break
                        if len(result) == 0:
                            break

                        all_ok = 1
                        # effic: sort self.gossip, sort the returned results,
                        # to speed up searches for signatures.  However, I
                        # haven't yet seen gossip_fetch_task come up in
                        # profiles.
                        for item in result:
                            already_there = 0

                            for wodge in self.gossip:
                                if wodge.signature == item[2]:
                                    #if wodge.distance(self.app.name_server) > from_fixed(item[0])+distance:
                                    #  # TODO: What to do with unit_decay_time?
                                    #  wodge.initial_distance = from_fixed(item[0])+distance
                                    #  wodge.initial_time     = time.time()
                                    wodge.opinions[acq.name] = from_fixed(item[0]) - wodge.decay()
                                    already_there = 1
                                    break

                            if already_there:
                                continue

                            try:
                                ticket, template, wait = self.node.call(
                                    address,('gossip get',item[2]))
                                if wait: yield 'call',(self.node,ticket)
                                string = self.node.get_reply(ticket, template)
                                wodgewodge = safe_pickle.loads(string)
                            except error.Error:
                                all_ok = 0
                                break

                            #TODO: Confirm signature of known people

                            wodge = Wodge({
                                'wodge': wodgewodge,
                                'string': string,
                                'signature': item[2],
                                'initial_time': time.time(),
                                'initial_distance': None,
                                #'initial_distance': from_fixed(item[0]) + distance
                                'unit_decay_time': item[1],
                                'opinions': { acq.name : from_fixed(item[0]) },
                                'collapsed': 0})

                            if not self.insert_wodge(wodge):
                                all_ok = 0
                                break

                        if not all_ok:
                            break
                        
                        pos = pos + 18
                    except error.Error:
                        break
            self.fetch_threads-=1
        
        self.fetch_threads=0
        for acq in self.app.name_server.acquaintances.values():
            if acq.distance != None:
                #acq.start_watching(self.node, 1)
                #name server starts watching all
                #want start watching to be gradual, see name server start()
                while not acq.watched:
                    yield 'sleep',1
                    if not self.running:
                        return

                if acq.online:
                    utility.start_thread(gossip_fetch_thread(self,acq))

        while self.fetch_threads != 0:
            yield 'sleep',0.1

        requests = self.update_requests
        self.update_requests = [ ]
        for item in requests:
            self.app.idle_add(item)


    def handle(self, request, ignored__address, call_id):
        check.check_matches(request, (types.StringType,))
        check.check_is_af_inet_address(ignored__address)
        
        if request[0] == 'gossip list':
            #TODO: Type checking, locking, oh, and this is really inefficient
            self.any_gossip_gets = 1

            list = [ ]
            for item in self.gossip[:]:
                list.append((to_fixed(item.distance(self.app.name_server)),
                             item.unit_decay_time,
                             item.signature))
            list.sort()
            return list[request[1]:request[2]]
        elif request[0] == 'gossip get':
            for item in self.gossip:
                if item.signature == request[1]:
                    return item.string
            return error.Error(_("No such wodge."))

    def insert_wodge(self, wodge):
        check.check_isinstance(wodge, Wodge)
        
        for item in self.gossip:
            if item.signature == wodge.signature:
                # TODO: Should probably update trust list here...

                return 0
                
        if len(self.gossip) < settings.gossip_cache_size:
            self.gossip.append(wodge)
            return 1

        worst_pos      = -1
        worst_distance = wodge.distance(self.app.name_server)
        for i in range(len(self.gossip)):
            distance = self.gossip[i].distance(self.app.name_server)
            if distance < worst_distance:
                worst_pos = i
                worst_distance = distance
            
        if worst_pos >= 0:
            self.gossip[worst_pos] = wodge
            return 1

        return 0


    def post_wodge(self, topics,subject,text,distance,anonymous,in_reply_to=None):
        if topics == [ ]:
            raise error.Error(_('Please specify some topics.'))
        if self.app.config['human-name'] == '' and not anonymous:
            raise error.Error(_('Please specify your name using the "Network/Configure..." menu item.'))
        if subject == '':
            raise error.Error(_('Please give a subject for your item.'))
        if text == '':
            raise error.Error(_('Please write some text for your item.'))
    
        wodge_info = {
            'topics'         : topics,
            'subject'        : subject,
            'text'           : text,
            'post-time'      : long(time.time())
        }

        if anonymous:
            wodge_info['name'] = ''
            wodge_info['human-name'] = ''
        else:
            wodge_info['name'] = self.app.name_server.public_key_name
            wodge_info['human-name'] = self.app.config['human-name']

        if in_reply_to:
            wodge_info['in-reply-to'] = in_reply_to.signature

        wodge_str = safe_pickle.dumps(wodge_info)
        if anonymous:
            wodge_sig = hash.hash_of(wodge_str)
        else:
            wodge_sig = self.app.name_server.sign(wodge_str)

        wodge = Wodge({
            'wodge': wodge_info,
            'string': wodge_str,
            'signature': wodge_sig,
            'initial_time': time.time(),
            'initial_distance': distance,
            #Fixme: make unit_decay_time an option
            'unit_decay_time': 60*60*24*7,
            'opinions': { },
            'collapsed': 0})
        # distance = post_distance + (time - post_time)/unit_decay_time

        self.insert_wodge(wodge)
        self.save()



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
