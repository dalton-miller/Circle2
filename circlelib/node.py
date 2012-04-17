
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

"""Fundamental decentralized hash networking class

     Provides the basic network services that all other components of
     Circle rely on.

     - remote procedure calls with 'call'
     - decentralized hashtable publishing and searching
     
     This module can be used effectively on its own. See the 'circleget'
     utility for a simple example.
     
"""

# TODO: ICMP on windows

# TODO: something goes wrong after sleeping... what?

# Problem: A node does not know its own address
#  - on receiving an address map None -> real address

# TODO:
#  - monitor messages for sanity

# Dealing with common keys 
#   - salt names with 4 bytes to make them mostly unique
#   - choose node name carefully: one of the names from last time

# For simplicity, each datum we publish is salted with the same salt

# TODO: do we really need large buffers?

# TODO: (toby)
#   allow server side keyword checking, rather than d/ling all then checking them client side

# TODO: Read http://www.cs.rice.edu/Conferences/IPTPS02/173.pdf 
# "Security Considerations for Peer-to-Peer Distributed Hashtables"

from __future__ import generators
import sys,os,string,socket,time,traceback,types,random,math,Queue,bisect
import threading

import hash
from settings import *
from utility import Task, Task_manager
import utility
import safe_pickle
from error import Error
import check

simulate_rogue_replies = 0  # Do not commit when set to 1.
if simulate_rogue_replies:
    import random_inst

# Iff non-zero then try to call check_invar after every non-const operation
# on Node objects, rather than every ~5 minutes (search for next_check_invar).
# The intent is that setting to 0 is the default (don't hog CPU with checking),
# but setting to 1 facilitates locating bugs.
always_check = 0

_recv_flags = 0
try:
    import select
    if sys.platform == 'win32':
        _recv_flags = 0
    else:
        _recv_flags = socket.MSG_DONTWAIT
except:
    pass  # Jython.


def is_cohort(cohort):
    """Returns true iff peer appears to be a valid cohort."""
    return ((type(cohort) == types.TupleType)
            and (len(cohort) >= 2)  # Permissive: current version always has len 2.
            and check.is_af_inet_address(cohort[1]))


# Check if on masq network

def need_proxy():
    """Check if Circle needs to work around masquerading by starting a proxy.
         This is called by the Circle login screen, which then decides whether
         or not to use the Proxy class."""

    if sys.platform == 'win32':
        gateway_column = 2
    else:
        gateway_column = 1

    error = 0
    try:
        #pipe = os.popen('/sbin/route -n','r')

        # netstat also available under BSD
        # note: popen seems broken, sometimes produces "Interrupted
        #   system call" on read
        #   A small sleep seems to fix it. Eh.
        pipe = utility.popen('netstat -rn','r')

        pipe.readline()
        while 1:
            line = pipe.readline()
            if not line:
                break

            list = string.split(line)
            if len(list) < 3:
                continue

            #if list[2] == '0.0.0.0':   # genmask == this -> default gw

            # linux2: 
            #  Destination Gateway  Genmask ...
            #  0.0.0.0     10.0.0.1 0.0.0.0
            # freebsd4:
            #  Destination Gateway  Flags, ...
            #  default     10.0.0.1 ...
            # win32:
            #  Net-addr    Netmask  Gateway   Interface  Metric
            #  0.0.0.0              

            # RFC 1918 specifies 10., 172.16., 192.168.
            # DHCP uses 169.254. (?)

            if list[2] == '0.0.0.0' or list[0] == 'default' or list[0] == '0.0.0.0':
                for prefix in [ '10.', '172.16.', '192.168.', '169.254.' ]:
                    if list[gateway_column][:len(prefix)] == prefix:
                        error = 1
        pipe.close()
    except:
        traceback.print_exc()
        pass

    return error

    #if error:
    #  raise Error('You appear to be trying to run Circle on a masquerading network.\n\n' + \
    #              'On masquerading networks, Circle needs to run a proxy on your firewall.\n\n' + \
                #       'Type "circle --help" for more information.')

def make_timeout(window):
    """ (internal) Construct a timeout that is robust against someone fscking
            with the clock. """
    check.check_has_type(window, types.FloatType)  #=@R28
    
    now = time.time()
    if window < 0.0: 
        window = 0.0

    # poll task can get behind the times a bit...

    return (now-window, now+window)

def is_timed_out(timeout, now=None):
    """ (internal) Check a timeout. """

    if not now:
        now = time.time()
    return now > timeout[1] or now < timeout[0] 


# Address mangle / demangle

def address_mangle(address, sender):
    """(internal) It turns out to be difficult to determine your own IP address:
         every interface has its own IP, which to choose? So what we do is
         never actually send our IP, just replace it with None. Then the
         other end (which will know our IP from the socket.recvfrom) can
         substitute it back in with address_demangle."""
    check.check_is_af_inet_address(address)  #=@R6
    check.check_is_af_inet_address(sender)  #=@R7
    
    if address == sender or address == ('127.0.0.1',sender[1]):
        ret = None
    elif address[0] == sender[0] or address[0] == '127.0.0.1':
        ret = (None, address[1])
    else:
        ret = address

    check.check_is_mangled_address(ret)  #=@E2
    return ret

def address_demangle(address, sender):
    check.check_is_mangled_address(address)  #=@R11
    # TODO: guarantee check.is_af_inet_address(ret) if we can,
    # at least in the case that is_af_inet_address(sender).
    
    if address == None:
        return sender
    elif address[0] == None:
        return (sender[0], address[1])
    else:
        return address


# Long name operations

salt_min = chr(0)   * name_salt
salt_max = chr(255) * name_salt

def long_name_minus(a,b):
    result = ''
    carry  = 0
    for i in range(long_name_bytes-1,-1,-1):
        value = ord(a[i]) - ord(b[i]) + carry
        result = chr(value & 0xff) + result
        carry = value >> 8

    return result

# Only meaningfull on the result of a name_minus
def long_name_compare(a, b):
    # effic: AFAICT, this is equivalent to cmp(a,b).
    for i in range(long_name_bytes):
        if ord(a[i]) < ord(b[i]): return -1
        if ord(a[i]) > ord(b[i]): return 1
    return 0

def long_name_bracketed(a,b,c):
    """(internal)
       Check if b is between a and c (or equal to a or c) on the circle.
       "Between" is reckoned by considering a to be strictly less than c (by no
       more than one revolution) and checking whether b falls in the arc traced
       between those."""

    #return long_name_compare(
    #  long_name_minus(b,a),
    #  long_name_minus(c,a)
    #) <= 0
    return a<=b<=c or c<=a<=b or b<=c<=a

def name_rotate(name, ticks):
    """(internal) To increase reliability, some modules publish to multiple 
         locations. This function generates names spaced nicely around the circle."""

    reverse = 0
    for i in range(8):
        if ticks & (1<<i):
            reverse = reverse + (128>>i)

    return chr((ord(name[0]) + reverse) & 0xff) + name[1:]


def bad_peer(addr, msg):
    """Something to call when the client at the other end sends some
       bad data.  Currently we don't do much; maybe in future we could
       tell the remote client of this (especially if it's an address we
       trust, e.g. one of the circle developers having made a mistake).
       We might also be slightly less trusting of information received from
       that peer: where there are bugs, there are more bugs."""
    
    check.check_is_af_inet_address(addr)  #=@R41
    check.check_has_type(msg, types.StringType)
    
    sys.stderr.write(_('Bad peer %s: %s\n') % (str(addr), msg))


class Link_state(utility.Synchronous):
    """(internal)
    This class is used by Node.call to avoid flooding addresses. 
    It limits the number of packets in flight to an address at any one time.

    """

    def __init__(self):
        utility.Synchronous.__init__(self)

        self.waiters = [ ]
        self.queue   = [ ]
        self.low_priority_queue   = [ ]

        self.round_trip     = udp_default_ping_time
        self.s_dev          = udp_default_ping_time

        #self.round_trip_2   = udp_default_ping_time*udp_default_ping_time
        
        #self.factor         = 1.0
        #self.n_successes    = 0
        #self.n_failures     = 0

        self.window         = 2.0        
        self.error          = 0
        self.last           = time.time()

    def wake_queuers(self,node):
        for i in range(int(self.window)-len(self.waiters)):

            if len(self.queue):
                ticket = self.queue.pop(0)
                if self.low_priority_queue:
                    self.queue.append(self.low_priority_queue.pop(0))

                thread,stack = node.pending_calls[ticket]
                utility.start_thread(thread,stack)

            elif len(self.low_priority_queue):
                ticket = self.low_priority_queue.pop(0)

                thread,stack = node.pending_calls[ticket]
                utility.start_thread(thread,stack)
                

    def error_received(self,node):
        self.error = 1
        self.error_timeout = make_timeout(udp_error_time)
        # Proof of @R28: @I10.


    def is_error(self):
        return self.error and not is_timed_out(self.error_timeout)


    def acquire_access(self, ticket, low_priority=0):
        """
        put it in the queue and returns immediately
        """

        if low_priority:
            self.low_priority_queue.append(ticket)
        else:
            self.queue.append(ticket)

        if self.error and not is_timed_out(self.error_timeout):
            return None

        #s_dev = self.round_trip_2 - self.round_trip*self.round_trip
        #if s_dev < 0.0:
        #    s_dev = 0.0
        #else:
        #    s_dev = math.sqrt(s_dev)

        max_round_trip = self.round_trip + 2.0*self.s_dev

        if max_round_trip < udp_min_ping_time:
            max_round_trip = udp_min_ping_time
        if max_round_trip > udp_max_ping_time:
            max_round_trip = udp_max_ping_time

        return max_round_trip
      
                 

    def release_access(self, ticket, success, n_failures, time_taken, low_priority=0):
        # reply is very likely from first Tx

        if success:
            self.round_trip   = self.round_trip*0.9+time_taken*0.1
            self.s_dev        = self.s_dev*0.9 + abs(self.round_trip - time_taken)+0.1            
            #self.round_trip_2 = self.round_trip_2*0.9+time_taken*time_taken*0.1

            if len(self.waiters) == int(self.window):
                self.window = self.window + 0.5/self.window
                if self.window > udp_max_window:
                    self.window = udp_max_window

        for i in range(n_failures):
            self.window = self.window - 0.5
            if self.window < 1.0:
                self.window = 1.0

        self.waiters.remove(ticket)
        self.last = time.time()


class Peer:
    """(internal) This structure is used by Node to store information about the 
         peers that it currently knows about.""" 

    def __init__(self, name, address):
        check.check_is_long_name(name)  #=@R8
        check.check_is_af_inet_address(address)  #=@R9
        
        self.name    = name
        self.address = address

        # The following is a leaky average, updated in poll_peer_task.
        # Initial value is supra-threshold

        #self.ping_time = 4*hashtable_activate_threshold
        self.ping_time = 0

        self.poll_interval = peer_poll_start_interval
        self.timeout       = make_timeout(peer_poll_start_interval) #time.time() + self.poll_interval
        # Proof of @R28: @I11.

        # Proof of @R.I4: @R8.  name is deeply immutable (@E18).
        # Proof of @R.I3: @R9.  address is deeply immutable (@E11).
        self.check_invar()

    def check_invar(self):
        check.check_is_long_name(self.name)  #=@I4
        check.check_is_af_inet_address(self.address)  #=@I3

class Link:
    """(internal) This structure is used to store information about links that 
         the Node is in charge of."""

    def __init__(self, name,dest):
        check.check_is_long_name(name)  #=@R26
        check.check_is_mangled_address(dest)  #=@R15
        
        self.name    = name
        self.dest    = dest

        self.poll_interval = start_poll_interval * (random.random()+0.5)
        self.timeout = make_timeout(self.poll_interval)
        # Proof of @R28 and @R.I14: @I12, random.random() returns float.

        # Proof of @R.I7: self.dest assigned solely from dest, which isn't
        # modified since beginning of method; and @R15.  dest is deeply
        # immutable, from @R15 and @E15.
        self.check_invar()
    
    def check_invar(self):
        check.check_is_long_name(self.name)  #=@I8
        check.check_is_mangled_address(self.dest)  #=@I7
        check.check_has_type(self.poll_interval, types.FloatType)  #=@I14
    
    def __cmp__(self, other):
        """ Used with bisect to maintain a sorted list of links. """

        check.check_isinstance(other, Link)
        return cmp((self.name, self.dest),
                   (other.name, other.dest))

    def __repr__(self):
        return '<Link '+repr(self.name)+' '+repr(self.dest)+'>'


def poll_link_thread(node,link, old_timeout):
    check.check_isinstance(node, Node)  #=@R13
    check.check_assertion(hasattr(node, 'address'))  #=@R16
    check.check_isinstance(link, Link)  #=@R14

    node.poll_threads +=1

    #print "Polling %s" % nickname(link.name)

    ok = 1

    # Drop inappropriate links (eg if a new peer has come online)
    right = node.right_neighbours[:1]
    if right:
        right_address = node.peers[right[0]].address
    if right and \
       long_name_bracketed(node.name, right[0], link.name):
        ok = 0
    
    address = address_demangle(link.dest, node.address)
    # Proof of @R11: link not reassigned since beginning, @R14, Link @I7.
    # Proof that is_af_inet_address(node.address): node not reassigned since
    # beginning, @R13, Node @I17, @R16.
        
    if ok:
        ticket, template, wait = node.call(
            address,('poll',link.name,int(link.poll_interval + poll_breathingspace)), 1)
        if wait: yield 'call',(node,ticket)
        try:
            node.get_reply(ticket,template)
        except Error, error:
            if link in node.links:
                node.links.remove(link)

            if error.message == 'no reply':
                i = 0
                while i < len(node.links):
                    if node.links[i].dest == link.dest:
                        del node.links[i]
                    else:
                        i = i + 1
    else:
        try:
            try:
                if not right:
                    raise Error('no right neighbour')

                ticket, template, wait = node.call(
                    right_address,('store link for',link.name,link.dest,int(old_timeout[1]-time.time())),1)
                if wait: yield 'call',(node,ticket)
                result = node.get_reply(ticket,template)
            except Error:
                ticket, template, wait = node.call(
                    address,('dropped link',link.name), 1)
                if wait: yield 'call',(node,ticket)
                result = node.get_reply(ticket,template)
        except Error:
            pass

        if link in node.links:
            node.links.remove(link)

    node.poll_threads -=1



def poll_peer_thread(node, peer):
    node.poll_threads +=1

    ok = 1
    if len(node.peers) > peer_cache_size and \
         peer.name not in node.left_neighbours and \
         peer.name not in node.right_neighbours:
        ok = 0

    if ok:
        start_time = time.time()
        ticket,template,wait = node.call(peer.address,('who are you',), 1)
        if wait: yield 'call',(node,ticket)
        try:
            name = node.get_reply(ticket,template)
            elapsed_time = time.time() - start_time
            if name != peer.name:
                ok = 0
        except Error:
            ok = 0

    if not ok:
        if node.peers.has_key(peer.name):
            del node.peers[peer.name]
        node.build_neighbours()
    else:
        peer.ping_time = 0.5*peer.ping_time + 0.5*elapsed_time

    node.poll_threads -=1
 

def poll_thread(node):
    
    check.check_isinstance(node, Node)  #=@R12    
    right_name = None
    next_check_invar = time.time()

    node.poll_threads = 0
    
    while 1:
        time_now = time.time()
        
        if time_now >= next_check_invar:
            try:
                # Note: if this fails, set always_check to 1
                #       and try to replicate the problem
                node.check_invar()
            except:
                traceback.print_exc()
            next_check_invar = time_now + 5*60.0

        node.poll_tasks = [ ]

        links_to_poll = [ ]
        
        if not node.running:
            break

        if time_now > node.start_time + hashtable_activate_time or node.hashtable_running:
            sum = 0
            for name,peer in node.peers.items():
                if peer.ping_time < hashtable_activate_threshold:
                    sum = sum + 1
            if sum >= len(node.peers)/2:
                if not node.hashtable_running:
                    node.activate_hashtable()
            else:
                if node.hashtable_running:
                    node.deactivate_hashtable()
 
        # Drop bad loopback links

        ## Somewhat inefficient
        #for link in node.links[:]:
        #  if link.dest == None and \
        #     len(node.right_neighbours) and \
        #     long_name_bracketed(node.name,node.right_neighbours[0],link.name):
                #node.links.remove(link)
                #if node.data.has_key(link.name):
                #  node.data_timeout[link.name] = time_now-1
                
        # Poll links

        # 28/12/01 not sure why i forgot this bit...
        if len(node.right_neighbours) and \
             node.right_neighbours[0] != right_name:
            right_name = node.right_neighbours[0]
            
            for link in node.links[:]:
                if long_name_bracketed(node.name,right_name,link.name):
                    node.links.remove(link)
                    links_to_poll.append(link)

        for link in node.links:
            if is_timed_out(link.timeout,time_now):
                links_to_poll.append(link)

                # Don't create too many link poll tasks
                # and therefore never get around to polling peers or
                # publishing our own data
                if len(links_to_poll) > 20:
                    break

        for link in links_to_poll:
            old_timeout = link.timeout
            if link.poll_interval < poll_max_interval:
                link.poll_interval = link.poll_interval * poll_expand_factor
            link.timeout = make_timeout(link.poll_interval)
            
            node.poll_tasks.append(poll_link_thread(node,link,old_timeout))
            
            # Proof of @R13: our @R12, node not reassigned since then.
            # Proof of @R14: link in links_to_poll, links_to_poll constructed
            # from elements of node.links, node isinstance Node (see @R13
            # proof), Node @I5.  links_to_poll not passed to any other object,
            # so no other thread can write to it.
            # Proof of @R16: given that links_to_poll is non-empty, we must
            # have got past the node.running test at the beginning of the above
            # `try' block.  Combine with Node @I1.

        # Poll peers

        list = [ ]
        for peer in node.peers.values():
            if is_timed_out(peer.timeout,time_now):
                list.append(peer)

        for peer in list:
            if peer.poll_interval < peer_poll_max_interval:
                peer.poll_interval = peer.poll_interval * peer_poll_expand_factor
            peer.timeout = make_timeout(peer.poll_interval)
            
            node.poll_tasks.append(poll_peer_thread(node,peer))
        
        # Poll data

        for item in node.data_timeout.items():
            if is_timed_out(item[1],time_now):
                # Defer low redundancy (ie low priority) publishes if we have too much to do
                if node.data_priority[item[0]] <= 1 and len(node.poll_tasks) > 20:
                    continue

                node.data_timeout[item[0]] = make_timeout(publish_retry_interval)
                # Proof of @R28: @I13.

                def announce_thread(node, item):

                    node.poll_threads +=1                    
                    result, subthread = node.find_nodes(item, 4, 1)
                    yield 'wait',subthread
                    if result:
                        peer = result[0]

                        ticket, template, wait = node.call(peer[1],('store link',item), 1)
                        if wait: yield 'call',(node,ticket)
                        try:
                            poll_interval = node.get_reply(ticket,template)

                            if not check.matches(poll_interval, types.IntType):
                                sys.stderr.write(_("Bad response to `%s' from peer %s.\n")
                                                 % ('store link', peer[1]))
                                return

                            timeout = make_timeout(float(poll_interval))
                            if node.data.has_key(item):
                                node.data_timeout[item] = timeout
                        except:
                            pass
                        
                    node.poll_threads -=1

                node.poll_tasks.append(announce_thread(node,item[0]))

        # Drop unused link states
        for pair in node.link_states.items():
            if pair[1].last + link_state_timeout < time_now:
                del node.link_states[pair[0]]
    
        if not node.poll_tasks:
            yield 'sleep',2
            continue
        
        for task in node.poll_tasks:
            utility.start_thread(task)

        while node.poll_threads >0:
            yield 'sleep',0.5


def probe_thread(node,address):

    node.active_probes += 1
    check.check_is_af_inet_address(address)  #=@R20  fixme callers    
    ticket,template,wait = node.call(address, ('who are you',))
    if wait: yield 'call',(node,ticket)
    try:
        name = node.get_reply(ticket, template)            
        # add_peer does its own checking on name.
        yield 'wait',node.add_peer_thread(name,address)
        # Proof of @R10: @R20; immutability from @E11.
    except Error:
        pass
    node.active_probes -= 1

 
def probe_neighbours_thread(node,address):

    try:
        check.check_is_af_inet_address(address)  #=@R21
            
        ticket, template, wait = node.call(
            address, ('get peers', '<', node.name,neighbourhood_size))
        if wait: yield 'call',(node,ticket)
        left_list = node.get_reply(ticket,template)
            
        ticket, template, wait = node.call(
            address, ('get peers', '>', node.name,neighbourhood_size))
        if wait: yield 'call',(node,ticket)
        right_list = node.get_reply(ticket,template)
            
        # Proof of @R18: @R21; deep immutability from @E11.
            
        # pjm: I haven't really thought about how to handle errors.
        # (Actually, I haven't even checked whether call converts
        # error returns to exceptions.)  Fixme: it raises as exception.
        if isinstance(left_list, Error):
            left_list = [ ]
        if isinstance(right_list, Error):
            left_list = [ ]
            
        for list in (left_list, right_list):
            if not check.matches(list, [('long name', 'mangled address')]):
                bad_peer(address, 'get peers reply ' + `list`)
                # Proof of @R41: @R21; immutability from @E11.
                return
        for list in (left_list, right_list):
            for i in list:
                yield 'wait',node.add_peer_thread(i[0], address_demangle(i[1], address), 0)
                # Proof of @R11: the check.matches condition.
                # Proof of @R10: fixme: add postcondition to
                # address_demangle.
    except Error:
        pass

    node.active_probes -= 1



def handle_request(node, request, address,call_id):
    check.check_is_af_inet_address(address)  #=@R24
    check.check_has_type(call_id, types.IntType)  #=@R48
    
    try:
        result = node.reply_cache[(address,call_id)]
    except KeyError:
        try:
            result = perform_request(node,request,address,call_id)
            # Proof of @R25: @R24, address not reassigned since then, deeply
            # immutable from @E11.
        except Error, error:
            result = error

        node.reply_cache[(address,call_id)] = result
        node.reply_cache_keys.append((address,call_id))
        while len(node.reply_cache_keys) > reply_cache_size:
            key = node.reply_cache_keys.pop(0)
            try:
                del node.reply_cache[key]
            except KeyError:
                pass

    check.check_is_dumpable(result)  #=@E26
    return result

def perform_standard_request(node, request, address, call_id):
    check.check_isinstance(node, Node)  #=@R5
    check.check_matches(request, ('string',))
    check.check_assertion(node.handlers.get(request[0], (0,))[0] is node)
    check.check_matches(request[1:], node.handlers[request[0]][1])  #=@R42
    check.check_is_af_inet_address(address)  #=@R25
    
    # Multiple requests per packet
    if request[0] == 'glob':
        result = [ ]
        for sub_req in request[1:]:
            if (type(sub_req) != types.TupleType) \
               or sub_req == () \
               or (type(sub_req[0]) != types.StringType):
                result.append(Error('glob: bad subrequest ' + `sub_req`))
            else:
                # TODO: Decide what to do if an exception is thrown from
                # perform_request.
                result.append(perform_request(node, sub_req, address, call_id))
                # Proof of recursive @R25: address not reassigned since our own
                # @R25 checked.

        # Loose proof of @E29: result is a list whose items are either
        # Error('...') or return values from perform_request, which should be
        # dumpable by @E27.  However, result can contain mutable types
        # (e.g. list), so we would need to show that these aren't modified.

        # The reason we don't properly check @E29 here is just to avoid possible
        # n^2 time cost, for deeply nested glob requests.  I don't know whether
        # or not nested globs are allowed; at a guess, I'd say that the standard
        # client never generates nested glob requests, but that it doesn't
        # forbid them either.  If correct, then checking here would create a
        # CPU-time denial-of-service possibility.
        return result

    if request[0] == 'who are you':
        if not node.hashtable_running:
            return Error('hashtable not active')
        ret = node.name
        check.check_is_dumpable(ret)  #=@E29
        # Proof: @I9, and assumption that long_names are dumpable.
        # (todo: Add `!ret || is_dumpable' postcondition to is_long_name.)
        return ret

    if request[0] == 'add peer':
        if not check.is_long_name(request[1]):
            return Error('add peer: request[1] should be is_long_name')
        if not check.is_mangled_address(request[2]):
            return Error('add peer wants is_mangled_address(request[2])')
        # Proof of @R11: checked above.
        peer_address = address_demangle(request[2],address)
        utility.start_thread(node.add_peer_thread(request[1], peer_address))
        return None

    if request[0] == 'get peers':
        if not ((len(request) >= 4)
                and (type(request[1]) == types.StringType)
                and check.is_long_name(request[2])
                and (type(request[3]) == types.IntType)):
            return bad_request(request)
    
        node.acquire_lock('get prs')
        try:
            list = node.query_peers(request[2],request[1],request[3])
            # Proof of @R37,@R38: checked above.
            result = [ ]
            for item in list:
                result.append((item,
                               address_mangle(node.peers[item].address,
                                              node.address)))
                # Proof that node.peers.has_key(item): @E20; holding the
                # node lock should suffice to show that it remains true.
                # Proof of @R6: @R5, fixme: show peers each of type Node.
                # Proof of @R7: @R5, fixme: show node.address is address.
        finally:
            node.release_lock('get prs')

        check.check_is_dumpable(result)  #=@E29
        return result

    # Fetch neighbours who could also be holding a particular link
    if request[0] == 'get cohorts':
        if not ((len(request) >= 2)
                and check.is_name(request[1])):
            return bad_request(request)

        min = request[1] + salt_min
        max = request[1] + salt_max

        node.acquire_lock('get co')
        try:
            cohorts = [ ]

            list = [(node.name,node.address)]
            for peer in node.left_neighbours:
                list.insert(0, (peer,node.peers[peer].address))
            for peer in node.right_neighbours:
                list.append((peer,node.peers[peer].address))

            for i in range(len(list)-1):
                if list[i][0] != node.name and \
                     ( long_name_bracketed(list[i][0], min, list[i+1][0]) or \
                         long_name_bracketed(list[i][0], max, list[i+1][0]) or \
                         long_name_bracketed(min, list[i][0], max) ):
                    cohorts.append(list[i])
        finally:
            node.release_lock('get co')

        check.check_is_dumpable(cohorts)  #=@E29
        return cohorts
        
    if request[0] == 'store link' or request[0] == 'store link for':
        node.acquire_lock('store lnk')
        try:
            if not node.hashtable_running:
                return Error('hashtable not active')

            # ('store link for ', name, [address, timeout])
            if request[0] == 'store link for':
                if not ((len(request) >= 4)
                        and check.is_long_name(request[1])
                        and check.is_mangled_address(request[2])
                        and ((request[3] is None)
                             or (type(request[3]) == types.IntType))):
                    return bad_request(request)

                # Proof of @R11: checked above.
                address  = address_demangle(request[2], address)
                interval = float(request[3])
            else:
                interval = None

            # Special protocol for self-links, as we do not know our own address
            address = address_mangle(address, node.address)

            link = None
            # effic: node.links is sorted, so no need to do linear search.
            #for item in node.links:
            #    if item.name == request[1] and item.dest == address:
            #        link = item
            pos = utility.bisect(node.links,
                                 lambda elem, req_name=request[1]: req_name <= elem.name)
            while pos < len(node.links) and node.links[pos].name == request[1]:
                if node.links[pos].dest == address:
                    link = node.links[pos]
                    break
                pos = pos + 1

            if link is None:
                # Proof of @R15: address last assigned from address_mangle; @E2.
                link = Link(request[1],address)
                if interval is not None:
                    link.timeout = make_timeout(interval) #time.time() + interval
                    # Proof of @R28: checked near top of this handler before
                    # assigning to interval.

                # Proof that node.links is sorted for bisect.insort: node
                # isinstance Node, from @R5.  @I6.
                # Proof of node invars: node isinstance Node, from @R5.
                #  Proof of @R.I5: link is constructed a few lines up and not
                #  reassigned since then.
                #  Proof of @R.I6: ensured by bisect.insort.
                bisect.insort(node.links, link)
            else:
                link.timeout = make_timeout(link.poll_interval) #time.time() + link.poll_interval
                # Proof of @R28: @I14.
        finally:
            node.release_lock('store lnk')

        if always_check:
            node.check_invar()

        #return int(link.poll_interval + poll_breathingspace)
        return int(link.timeout[1] - time.time() + poll_breathingspace)
        
    if request[0] == 'query link':
        if not ((len(request) >= 4)
                and check.is_name(request[1])
                and (type(request[2]) == types.IntType)
                and (type(request[3]) == types.IntType)):
            return bad_request(request)

        node.acquire_lock('qry lnk')
        try:
            if not node.hashtable_running:
                return Error('hashtable not active')
            
            # Note that Link .name attributes are long names (concatenation of
            # a short name and a few bytes of salt), whereas request[1] is just
            # a short name, so `<' and `<=' are equivalent.
            i = utility.bisect(node.links,
                               lambda elem, req_name=request[1]: req_name < elem.name)
            req_name_last = request[1] + '\xff'*name_salt
            result = [ ]
            while i < len(node.links):
                elem = node.links[i]
                if req_name_last < elem.name:
                    break
                result.append(elem.dest)
                i += 1
            ret = result[ request[2]:request[3] ]
        finally:
            node.release_lock('qry lnk')

        check.check_is_dumpable(ret)  #=@E29
        return ret
    
    if request[0] == 'query data':
        data = node.data.get(request[1] + node.salt,[ ])
        # Proof that `+' is defined for request[1],node.salt:
        # is_name(request[1]) from call signature and @R42;
        # request hasn't been reassigned since then, and tuples are
        # immutable.  is_name implies string (@E22), and strings are
        # immutable.  node.salt is also a string (@I20).

        result = [ ]
        for item in data[ request[2]:request[3] ]:
            if type(item) in [types.FunctionType, types.MethodType]:
                result.append(apply(item,()))
            else:
                result.append(item)

        check.check_is_dumpable(result)  #=@E29
        return result

    if request[0] == 'poll':
        if not ((len(request) >= 3)
                and check.is_long_name(request[1])
                and (type(request[2]) == types.IntType)):
            return bad_request(request)

        node.acquire_lock('poll')
        try:
            ok = node.data.has_key(request[1])
            if ok:
                node.data_timeout[request[1]] = make_timeout(float(request[2]))
        finally:
            node.release_lock('poll')

        check.check_is_dumpable(ok)  #=@E29
        return ok

    if request[0] == 'dropped link':
        if not ((len(request) >= 2)
                and check.is_long_name(request[1])):
            return bad_request(request)
        
        # Poll task will republish
        node.acquire_lock('dropped lnk')
        try:
            ok = request[1][name_bytes:] == node.salt and \
                     node.data.has_key(request[1][:name_bytes])
            if ok:
                node.data_timeout[request[1]] = make_timeout(0.0)
        finally:
            node.release_lock('dropped lnk')
        
        return None

    if request[0] == 'going offline': # actually means hashtable deactivate

        for item in node.peers.items():
            if item[1].address == address:
                del node.peers[item[0]]
                node.build_neighbours()

        return None

    check.show_bug('perform_standard_request called with unknown request type')


def perform_request(node, request, address,call_id):
    check.check_isinstance(node, Node)  #=@R5
    check.check_is_af_inet_address(address)  #=@R25
    
    if not((type(request) == types.TupleType)
           and (type(request[0]) == types.StringType)):
        return Error('bad request form: expecting tuple whose first element is a string.')
    
    if address is None:  # fixme remove this or @R25
        raise "blarg"

    if node.handlers.has_key(request[0]):
        obj, request1_tmpl, ret_tmpl = node.handlers[request[0]]
        if not check.matches(request[1:], request1_tmpl):
            # Proof of @E27: @E28.
            return bad_request(request)
        
        check.check_is_af_inet_address(address)
        # Proof: @R25.
        ret = obj.handle(request, address, call_id)
        if ret_tmpl != 'any' and not isinstance(ret, Error):
            check.check_matches(ret, ret_tmpl)
        check.check_is_dumpable(ret)  #=@E27
        return ret
    
    # Note: don't apply gettext to the below: the calling client (which could
    # be any version of Circle) may want to do a string compare on the result.
    return Error('Request not understood: '+request[0])

def bad_request(request):
    check.check_matches(request, ('string',))

    ret = Error('bad request form for ' + request[0])
    check.check_is_dumpable(ret)  #=@E28
    return ret


def handle_message(node, message_str, address):
    """is called from mainthread
       note: there should be a lower priority for download chunk"""

    # message_str is a string to be interpreted by safe_pickle.safe_loads.
    check.check_is_af_inet_address(address) #=@R2

    message_len = len(message_str)
    message = safe_pickle.loads(message_str)
    if not((type(message) == types.TupleType)
           and (len(message) >= 3)):
        result = Error('handle_message: expecting unpickled message to be tuple of len 3.')
        
    elif message[0] == 'reply':        
        ticket = message[1]
        if node.pending_calls.has_key(ticket):
            node.replies[ticket] = (message[2], message_len)
            thread = node.pending_calls[ticket]
            utility.start_thread(thread)
        return
                
    elif type(message[1]) != types.IntType:
        result = Error('handle_message: expecting message[1] to be int')

    elif ((message[0] != None) and not check.is_long_name(message[0])):
        result = Error('handle_message: expecting message[0] to be None or long name')

    else:
        if message[0] is not None:
            check.check_is_long_name(message[0])
            # Proof: checked above, and message is a tuple so should be read-only.
            
            utility.start_thread(node.add_peer_thread(message[0],address))

        try:
            # Proof of @R24: @R2, address not reassigned since then.
            # Proof of @R48: checked above, not modified since then.
            result = handle_request(node, message[2], address,message[1])
        except:
            traceback.print_exc()
            result = Error('Bug in remote peer.')

    check.check_is_dumpable(message[1])
    # Loose proof: message came from safe_pickle.loads.
    # (todo: Add postcondition.)  message is not modified locally.
    # The only calls passing message[1] are after checking that it
    # is an int (hence deeply immutable).
    # Relevance: don't want to get pickle error at runtime.

    check.check_is_dumpable(result)    
    result = safe_pickle.dumps(('reply',message[1],result))

    # Proof of @R1: safe_pickle.dumps @E1.
    # Proof of @R3: our @R2.
    node.socket_sendto(result,address)
    node.update_network_usage("hdl msg '" + message[2][0] + "'", len(result))
    # fixme: haven't checked that message[2] is of tuple type or that its
    # first elem is string type.

    try:
        for monitor in node.monitors:
            monitor( 0, address, message[2], len(result)+message_len )
    except:
        traceback.print_exc()


def listen_task(node):
    """ Listen to the socket. This task runs in a separate OS thread. """
    
    def message_handler(unused__node, queue):
        while 1:
            item = queue.get()
            if not item:
                return
            try:
                utility.mainthread_call(apply,handle_message,item)
            except:
                traceback.print_exc()

    if 0:  # TODO: test whether profiling has been requested.
        def message_handler(queue, unused__node, handler=message_handler):
            import profile
            prof = profile.Profile()
            prof.runcall(handler, unused__node, queue)
            prof.print_stats()

    queue = Queue.Queue(0)
    Task(message_handler, node, queue).start()

    while 1:
        if not node.running:
            break

        if not node.socket_proxy:
            try:
                # Signal can cause error here (eg ^C, SIGTERM)
                result = select.select([node.socket],[ ],[node.socket],2)
            except:
                result = [[],[],[]]

            if result[2]:
                node.socket_handle_errors()

            if result[0] == [ ]:
                continue
        
            usage = 0
            while 1: 
                try:
                    message, address = node.socket_recvfrom()
                except:
                    break

                usage = usage + len(message)

                queue.put((node,message,address))

                if not select.select([node.socket],[ ],[ ],0)[0]:
                    break

            node.update_network_usage('direct recvfrom', usage)

        else:
            try:
                message, address = node.socket_recvfrom()
            except Error:
                continue
            except:
                break
                
            queue.put((node,message,address))
            
            node.update_network_usage('proxy recvfrom', len(message))

    queue.put(None)
            

def node_search(pipe, node, search_for, redundancy, addresses_only, local_only=0):
    """Ensures @E7: for each item i written to pipe: if addresses_only
       then check.is_af_inet_address(i)
       else check.matches(i, ('af_inet_address', 'any')).
       """

    pipe.tried_addresses = [ ]

    if node.data.has_key(search_for+node.salt):
        # Proof of @R17: is_mangled_address(None) (@E4).
        utility.start_thread(node_search_subsubthread(
            pipe,node,search_for,None,node.address,addresses_only))

    if not local_only:
        for tick in range(redundancy):            
            utility.start_thread(node_search_subthread(
                pipe,node,name_rotate(search_for,tick),addresses_only))

    # Loose proof of @E7: we don't write any items to pipe except via
    # node_search_subsubtask (which ensures @E5) and node_search_subtask
    # (which ensures @E8).

def node_search_subthread(pipe,node,search_for, addresses_only):
    """Ensures @E8: for each item i written to pipe: if addresses_only
       then check.is_af_inet_address(i)
       else check.matches(i, ('af_inet_address', 'any')).
       """

    pipe.threads+=1
    
    salted_search = search_for
    for i in range(name_salt):
        salted_search = salted_search + chr(random.randint(0,255)) 

    result, subthread = node.find_nodes(salted_search)
    yield 'wait',subthread
    if not result:
        pipe.threads-=1
        return
    peer = result[0]

    # todo: consider assert(is_cohort(peer)).

    tried_peers = [ ]
    suggested_peers = [ peer ]

    while pipe.running and suggested_peers:
        peer = suggested_peers.pop()
        if not is_cohort(peer):
            # bad peer: bad data from get cohorts call.
            continue
        if peer not in tried_peers:
            tried_peers.append(peer)

            position = 0
            failed   = 0
            while pipe.running:

                ticket, template, wait = node.call(
                    peer[1],('query link',search_for,position,position+20))
                if wait: yield 'call',(node,ticket)
                try:
                    links = node.get_reply(ticket,template)
                except Error:
                    break
                    failed = 1

                for link in links:
                    if not check.is_mangled_address(link):
                        # bad peer peer[1] query link response
                        continue
                    # Proof of @R17: checked above.
                    utility.start_thread(node_search_subsubthread(
                        pipe,node,search_for,link,peer[1],addresses_only))

                if len(links) < 20:
                    break

                # Paranoid check for overflow.
                # (Almost impossible unless the other end is hacked/buggy.)
                # Don't change the below expression unless you've considered
                # all the overflow possibilities.
                if long(position) + (-1)<<31 + len(links) >= 0:
                    failed = 1
                    break
                
                position = position + len(links)
                
            if not failed:
                ticket, template, wait = node.call(peer[1],('get cohorts',search_for))
                if wait: yield 'call',(node,ticket)
                try:
                    peers = node.get_reply(ticket,template)
                    suggested_peers.extend(peers)
                except Error:
                    pass

    pipe.threads-=1    
    # Loose proof of @E8: pipe passed only to node_search_subsubtask; @E5.

def node_search_subsubthread(pipe,node,search_for,link,source,addresses_only):
    """Ensures @E5: If addresses_only then write items of type
       is_af_inet_address to the pipe,
       else write items matching ('address', 'any') to the pipe."""
    check.check_is_mangled_address(link)  #=@R17
    # Proof of @R11: @R17.
    link = address_demangle(link, source)
    # fixme: I believe we need to require source is if_anet_address.

    pipe.threads += 1
    
    if link in pipe.tried_addresses:
        pipe.threads-=1
        return
    pipe.tried_addresses.append(link)

    if addresses_only:
        pipe.write(link)
        pipe.threads-=1
        return

    data_position = 0

    while pipe.running:
        
        ticket, template, wait = node.call(
            link,('query data',search_for,data_position,data_position+1))
        if wait: yield 'call',(node,ticket)
        try:
            data = node.get_reply(ticket, template)
        except Error,err:
            #print err.message
            break
        
        if type(data) != types.ListType:
            break

        for datum in data:
            pipe.write((link, datum))

        if len(data) < 1:
            break

        data_position = data_position + len(data)
        
    pipe.threads-=1

class Null_proxy:
    def __init__(self):
        self.queue = Queue.Queue(0)

    def sendto(self, message, address):
        self.queue.put((1,address,message))

    def recvfrom(self):
        gotten = self.queue.get()

        if not gotten:
            raise Error('stopped')

        return gotten

    def stop(self):
        self.queue.put(None)

class Node(Task_manager):
    """This class provides all of the lowest level network services in circle.

         - remote procedure calls using UDP (call)
         - publishing data to the hashtable (publish)
         - retrieving data from the hashtable (retrieve)
         - passing on RPC calls to other classes (add/remove_handler)"""

    def __init__(self):
        Task_manager.__init__(self)

        self.start_time       = time.time()
        self.network_usage    = 0L # This can overflow if its just an int (!)
        self.network_profile  = { }
        self.active_probes    = 0
    
        self.call_no          = 0
        self.pending_calls    = { } # subthreads
        self.calling_threads  = { } # threads that made a call.
        self.replies          = { } # Call no -> (reply, reply_length)

        self.handlers         = {
            'glob': (self, (), types.ListType),
            'who are you': (self, (), 'long name'),
            'add peer': (self, ('long name', 'mangled address'),
                         'any'), # Currently returns None; ignored.
            'get peers': (self, (types.StringType, 'long name', types.IntType),
                          [('long name', 'af_inet_address')]),
            # fixme: Some callers of get peers pass the result directly to
            # call_timed, which requires af_inet_address; but our handler looks
            # as if it's returning mangled addresses.  In particular, I suspect
            # there's a bug if one of our peers is on localhost.

            'get cohorts': (self, ('name',),
                            [('long name', 'af_inet_address')]),
            'store link': (self, ('long name',), types.IntType),
            'store link for': (self, ('long name', 'mangled address'),
                               types.IntType),
            'query link': (self, ('name', types.IntType, types.IntType),
                           ['mangled address']),
            'query data': (self, ('name', types.IntType, types.IntType),
                           [{'type': types.StringType}]),
            'poll': (self, ('long name', types.IntType),
                     'any'), # Returns boolean (ignored).
            'dropped link': (self, ('long name',),
                             'any'),   # Currently returns None; ignored.
            'going offline': (self, (), 'any')}
        self.reply_cache      = { } # Cache replies to incoming requests
        self.reply_cache_keys = [ ]

        self.monitors         = [ ] # For monitoring incoming requests (eg to collect stats)

        self.peers            = { } # Peers indexed by long name
        self.link_states      = { } # Windowing, round trip time, etc
        self.left_neighbours  = [ ]
        self.right_neighbours = [ ]
        self.data             = { } # Data indexed by long name
        self.info2names       = { } # Reverse mapping on self.data (id(info) -> name)
        self.data_timeout     = { } # When to assume peer holding link has gone AWOL, and republish
        self.data_priority    = { } # ~= redundancy. Republish high redundancy items first.
        self.links            = [ ] # Link objects, sorted by name

        # How often are we dropping packets?
        self.call_p_success   = 1.0

        # Monitor ping times (to decide whether we should activate the hashtable)
        # (ping time for find_nodes is measured)
        #self.ping_total_time  = 0.0
        #self.ping_count       = 0
        #self.pings_under_threshold = 0
        #self.pings_over_threshold = 0

        self.hashtable_running = 0
        #self.hashtable_stopped = 0
        self.hashtable_offloaders = 0 # List of tasks offloading hashtable
                                      # entries (for asynchronous hashtable shutdown)

        svd_name = utility.get_checked_config("node_name_seed",
                                              types.StringType,
                                              "")[:name_bytes]

        # Ensure name is not re-used, eg by daemon
        utility.set_config("node_name_seed", "")

        self.name = svd_name + utility.random_bytes(long_name_bytes - len(svd_name))
        # Proof of @R27: svd_name is explicitly truncated above to be no more
        # than name_bytes long, and we assume name_bytes < long_name_bytes.

        # self.salt is never modified.
        self.salt = self.name[-name_salt:]

        self.trusted_addresses = [ ] #list of addresses who may download files from me

        # Proof of @R.I5,@R.I6: links is empty.
        # Proof of @R.I17: we don't yet have an address attr.
        # Proof of @R.I2: peers is empty.
        # Proof of @R.I9: svd_name is a string (from @E13) of no more than
        # name_bytes characters (we explicitly truncate it above).
        # random_bytes returns a string of the specified length (@E14).
        # svd_name is local to this method; nothing else writes to it,
        # and string is immutable.  self.name is assigned from the
        # concatenation of svd_name and random_bytes; its length will be the
        # sum of the lengths of the two components, i.e. long_name_bytes.
        self.check_invar()
    
    def check_invar(self):
        self.acquire_lock('node.check_invar')
        try:
            # self.running, self.address.
            # @I1: If .running has ever been true of self then
            # hasattr(self, 'address').
            if self.running:
                check.check_assertion(hasattr(self, 'address'))
            if hasattr(self, 'address'):
                check.check_is_af_inet_address(self.address)  #=@I17

            # self.peers.
            for key,val in self.peers.items():
                check.check_is_long_name(key)  #=@I18
                check.check_isinstance(val, Peer)  #=@I2
                check.check_assertion(key == val.name)  #=@I19
            
            # self.links.
            prev = None
            for link in self.links:
                check.check_isinstance(link, Link)  #=@I5
                link.check_invar()
                if prev is not None:
                    check.check_assertion(prev < link)  #=@I6
                prev = link
            
            # self.name, self.salt.
            check.check_is_long_name(self.name)  #=@I9
            check.check_has_type(self.salt, types.StringType)  #=@I20
            check.check_assertion(len(self.salt) == name_salt)

            # self.call_no
            check.check_has_type(self.call_no, types.IntType)  #=@I30
            
            # self.data, self.info2names.
            for info_id,names in self.info2names.items():
                check.check_has_type(info_id, types.IntType)
                check.check_matches(names, ['long name'])
            for name,data in self.data.items():
                check.check_is_long_name(name)
                check.check_assertion(name[-name_salt:] == self.salt)
                for info in data:
                    check.check_assertion(name in self.info2names.get(id(info), []))
            
            # self.handlers.
            check.check_has_type(self.handlers, types.DictionaryType)
            for (req_name, handler) in self.handlers.items():
                check.check_has_type(req_name, types.StringType)
                check.check_matches(handler, (types.InstanceType, 'template', 'template'))
                check.check_assertion(len(handler) == 3)
                check.check_assertion(hasattr(handler[0], 'handle'))
                check.check_matches(handler[1], [types.TupleType, [types.TupleType]])
        finally:
            self.release_lock('node.check_invar')

    def update_network_usage(self, key, inc):
        check.check_has_type(key, types.StringType)
        check.check_has_type(inc, types.IntType)
        check.check_assertion(inc >= 0)
        
        self.network_usage += inc
        if self.network_profile.has_key(key):
            curr = self.network_profile[key]
        else:
            curr = (0, 0)
        self.network_profile[key] = (curr[0] + 1, curr[1] + inc)

    def save_seed(self):
        """In order to match the distribution of links about the circle, Node
             needs to choose a random link to serve as its address next time it 
             starts. This allows the circle to deal with very common links gracefully,
             eg 'mp3' 'service data cache'.

             This should be called on shutdown, before shutting down any classes that
             provide circle services."""
        
        self.acquire_lock('save seed')
        try:
            if self.data:
                utility.set_config("node_name_seed",
                                   random.choice(self.data.keys())[:name_bytes])
        finally:
            self.release_lock('save seed')

    def start(self, proxy=None, no_connect=0):
        """Start the Node.
             This can raise an Error if starting the proxy fails.
             Ensures @E12: is_af_inet_address(self.address)."""

        Task_manager.start(self)

        self.socket_lock = threading.Lock()

        if no_connect:
            self.socket_proxy = Null_proxy()
            self.address = self_address = ('127.0.0.1', 29610)
        elif proxy:
            self.socket_proxy = proxy
            self.address = self_address = proxy.address
            # fixme: Prove is_af_inet_address.
        else:
            self.socket_proxy = None
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            #for port in range(29617,29627):
            for port in default_ports:
                try:
                    self.socket.bind(('',port))
                    break
                except:
                    pass
            else:
                self.socket.bind(('',socket.INADDR_ANY))

            self.address = self_address = (
                '127.0.0.1',
                self.socket.getsockname()[1]
            )
            # Loose proof that is_af_inet_address(self.address): self.socket
            # is constructed above as AF_INET, which hasn't changed since.
            # We've assigned self.address[1] from self.socket.getsockname()[1],
            # where self.socket.getsockname() returns an AF_INET address.

            # On linux, really only gives 1<<17 bytes buffers, but we can wish...
            # Note: BSD throws error instead of silently failing
            for i in range(20,12,-1):
                try:
                    self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,1<<i)
                    self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1<<i)
                    break
                except socket.error:
                    pass

            #self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,1<<13)
            #self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1<<13)
            
            #print self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF)
            #print self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF)

            # Enable ICMP error reception (SOL_IP,IP_RECVERR)
            #print self.socket.getsockopt(0,11)
            
            # Not sure how to do this on windows
            if sys.platform != 'win32':
                self.socket.setsockopt(socket.SOL_IP,11,1)

            # Disable path MTU discovery
            # Do we need this for BSD as well (or Windows...)?
            if sys.platform == 'linux2':
                self.socket.setsockopt(socket.SOL_IP,10,0)

            #print self.socket.getsockopt(0,11)

        Task(listen_task,self).start()
        # Proof of @R12: this is a method of class Node.
        
        utility.start_thread(poll_thread(self))

        self.greet_known_peers()
        
        check.check_is_af_inet_address(self_address) #=@L1
        # Proof: self_address is assigned unconditionally in each of
        # the branches of the `if' tree above to a valid is_af_inet_address
        # object, and isn't subsequently reassigned.  @E11 shows that
        # the self_address can't be changed under us.
        check.check_is_af_inet_address(self.address) #=@E12
        # Loose proof: self.address is assigned from self_address; see @L1.
        # Although we've no guarantee that self.address hasn't been made to
        # point to something else in the meantime (by another thread), we rely
        # on @I1 being maintained by anything that does write to self.address.
        self.check_invar()
        # Proof of @R.I1: @E12.

    def stop(self):
        # Save peers for next time
        self.acquire_lock('stop')
        try:
            known_peers = utility.get_checked_config("known_peers",
                                                     ['af_inet_address'],
                                                     [ ])
            # TODO: apply filter(check.is_af_inet_address) (but with warning
            # if any are filtered out) instead of discarding all elements if
            # we find a non-af_inet_address item.
            
            for peer in self.peers.values():
                if peer.address in known_peers:
                    known_peers.remove(peer.address)
                if peer.address[1] == default_ports[0]:
                    known_peers.insert(0,peer.address)

            utility.set_config("known_peers", known_peers[:max_known_peers])
        finally:
            self.release_lock('stop')

        self.deactivate_hashtable()

            
        self.running = 0
        # Abort all pending calls
        #for subthread in self.pending_calls.values:
        #    subthread.next()
        
        if self.socket_proxy:
            self.socket_proxy.stop()
        
        Task_manager.stop(self)

    def greet_known_peers(self): 
        """ (Internal) Greet peers in initial list or saved from last time.
                Called by start.  As of 2002-08-24, also accessible from the
                menu as 'Network/Connect to previous peers'. """

        known_peers = utility.get_checked_config("known_peers",['af_inet_address'],[ ])
        
        any = 0
        for item in known_peers:
            if not check.is_af_inet_address(item):
                # print bad known_peers config item
                continue
            # Don't allow probing loopback, as will record wrong address
            if item[0] != '127.0.0.1':
                self.probe(item)
                # Proof of @R22: checked above.
                any = 1

        if not any:
            for item in initial_peers:
                try:
                    address = socket.gethostbyname(item)
                    self.probe((address,default_ports[0]))
                    # Proof of @R22: socket.gethostbyname returns string,
                    # settings.default_ports is a non-empty list of int's.
                    any = 1
                except:
                    pass
        return any

    def is_connected(self):
        """ Is this node connected to any others? """

        if self.peers:
            return 1
        else:
            return 0

    def is_connecting(self):
        """ Is this node still looking for other nodes? """

        return self.active_probes and not self.peers

    def add_handler(self, msg_name, how, param_tmpl = (), result_tmpl = 'any'):
        """Add a handler for a specific message.

             msg_name: what message type to handle (i.e. request[0])
             how : a class instance with a method defined thus:
                     handle(self, request, address, call_id)
                 where
                     request is the actual message
                     address is the address of the caller
                     call_id is (with address) a unique identifier of the message
                 and returning the reply.

                 Note: because UDP is an unreliable protocol, the handler might
                     be called more than once for the one message (if the reply
                     packet was dropped). Use (address,call_id) to check for repeats
                     if this is a problem.
                 """
        
        check.check_has_type(msg_name, types.StringType)
        check.check_is_template(param_tmpl)
        check.check_is_template(result_tmpl)
        check.check_assertion(hasattr(how, 'handle'))
        check.check_matches(param_tmpl, [types.TupleType, [types.TupleType]])

        if simulate_rogue_replies:
            # Check in advance that random_inst can handle it.
            random_inst.random_inst(result_tmpl)

        self.handlers[msg_name] = (how, param_tmpl, result_tmpl)
        
        if always_check:
            self.check_invar()

    def remove_handler(self, msg_name):
        """Remove a previously installed message handler."""

        check.check_has_type(msg_name, types.StringType)        
        if self.handlers.has_key(msg_name):
            del self.handlers[msg_name]

    def handle(self, request, address, call_id):
        return perform_standard_request(self, request, address, call_id)

    def add_monitor(self, monitor):
        self.monitors.append(monitor)

    def remove_monitor(self, monitor):
        if monitor in self.monitors:
            self.monitors.remove(monitor)

    def publish(self, name, info, redundancy=1):
        """Publish a data item to the hashtable.

             name is the name of the link, it should be a string name_bytes long.
                 This is generally an MD5 hash generated by hash.hash_of.
                 eg hash.hash_of("myservice blah garfunkle")
                 
             info the data to be associated with the name. This should be a fairly
                 small dictionary, containing at least a 'type' attribute.

                 info can also be a function taking no parameters. If you use this
                 option, the function should return the data you want associated
                 with the name. This is useful for example if you want to include
                 a constantly changing value, such as up-time.
                 
             redundancy is the degree of redundancy with which to publish the data.
                 a redundancy of about 4 should guarantee that the published item is
                 always visible."""
    
        check.check_is_name(name)
        check.check_assertion(type(redundancy) == types.IntType
                              and redundancy >= 1)
        try:
            tmp = info()
        except:
            tmp = info
        check.check_matches(tmp, {'type': types.StringType})


        pub_names = []
        # Announcing now done by poll task
        for tick in range(redundancy):
            rot_name = name_rotate(name,tick) + self.salt

            new_key = 0
            if not self.data.has_key(rot_name):
                self.data[rot_name] = [ ]
                new_key = 1

            if info not in self.data[rot_name]:
                self.data[rot_name].append(info)
                pub_names.append(rot_name)

            if new_key:
                self.data_timeout[rot_name] = make_timeout(0.0)

            self.data_priority[rot_name] = max(redundancy, self.data_priority.get(rot_name,1))

        info_id = id(info)
        if self.info2names.has_key(info_id):
            self.info2names[info_id].extend(pub_names)
        else:
            self.info2names[info_id] = pub_names
        
        if always_check:
            self.check_invar()

    def unpublish_efficiently(self, name, info, redundancy):
        """Efficient version of unpublish when you're sure of the exact
           name,info,redundancy tuple passed to publish."""

        check.check_has_type(redundancy, types.IntType)

        pub_names = { }
        for tick in range(redundancy):
            rot_name = name_rotate(name,tick) + self.salt
            self.unpublish_named(rot_name, self.data[rot_name], info)
            pub_names[rot_name] = None
        info_id = id(info)
        if self.info2names.has_key(info_id):
            names = self.info2names[info_id]
            for i in range(len(names)):
                if pub_names.has_key(names[i]):
                    del names[i]
                    del pub_names[names[i]]

        if always_check:
            self.check_invar()

    def unpublish(self, info):
        """Unpublish a previously published item of information.
             This will unpublish *all* links to the item.
             
             info must be the same object, not just equal."""

        try:
            tmp = info()
        except:
            tmp = info
        check.check_matches(tmp, {'type': types.StringType})

        #for name,val in self.data.items():
        #    self.unpublish_named(name, val, info)

        info_id = id(info)
        names = self.info2names.get(info_id, [])
        if names:
            for name in names:
                self.unpublish_named(name, self.data[name], info)
            del self.info2names[info_id]

        if always_check:
            self.check_invar()

    def unpublish_named(self, name, val, info):
        # Requires that the lock be held.
        
        # effic: unpublish takes a non-neglible amount of time.
        # Could we use a different data structure, to avoid
        # the linear search?  Also, if it's common for info
        # to be present more than once in the list, then
        # investigate doing deletion differently; I suspect that
        # each del operation is linear in the length of the list.
        pos = len(val)
        while pos:
            pos -= 1
            if val[pos] is info:
                del val[pos]

        #if info in self.data[name]:
        #  self.data[name].remove(info)

        if self.data[name] == [ ]:
            del self.data[name]
            del self.data_timeout[name]
            del self.data_priority[name]

    def unpublish_set(self, infos):
        self.acquire_lock('unpset')
        try:
            to_unpublish = { }
            prev_id = None
            for info in infos:
                info_id = id(info)
                if info_id == prev_id:
                    continue
                prev_id = info_id
                names = self.info2names.get(info_id, [])
                if names:
                    for name in names:
                        try:
                            to_unpublish[name].append((info_id, info))
                        except:
                            to_unpublish[name] = [(info_id, info)]
                    del self.info2names[info_id]
            if not self.info2names:
                self.data = { }
            else:
                for (name, name_infos) in to_unpublish.items():
                    if len(name_infos) == len(self.data[name]):
                        tst1 = map(lambda p: p[1], name_infos)
                        tst1.sort()
                        self.data[name].sort()
                        check.check_assertion(self.data[name] == tst1)
                        del self.data[name]
                    else:
                        val = self.data[name]
                        for info_pair in name_infos:
                            self.unpublish_named(name, val, info_pair[1])
        finally:
            self.release_lock('unpset')
        
        if always_check:
            self.check_invar()

    def retrieve(self, name, redundancy=1, addresses_only=0, local_only=0):
        """Retrieve data items associated with a name from the hashtable.
             This returns a pipe object that emits either (address, data) pairs
             or address items, depending on addresses_only value.

             Example usage:

             pipe = node.retrieve(hash.hash_of("thingy"))
             try:
                 while not pipe.finished():
                     for item in pipe.read_all()
                         # item[0] is the address
                         # item[1] is the data
                         ... do something ...
                     time.sleep(1)
             finally:
                 pipe.stop()
                 
             And yes, a pipe implementation that doesn't need polling would
             be nice...
             
             Ensures @E6: if addresses_only then
             check.is_list_of('af_inet_address', ret.read_all())
             else check.is_list_of(('af_inet_address', 'any'), ret.read_all()).

             Ensures @E10: the returned Pipe object is not passed to any other
             thread; i.e. you can rely on @E6 holding if you don't yourself
             pass the returned Pipe object to any other thread.
             """
        pipe = utility.Pipe()
        pipe.start(node_search,self,name,redundancy,addresses_only,local_only)
        # Loose proof of @E6: fixme
        return pipe

    def probe(self, address):
        check.check_is_af_inet_address(address)  #=@R22  fixme callers
        
        utility.start_thread(probe_thread(self,address))

        
        # Proof of @R20: @R22.  Deep immutability from @E11.

    def probe_neighbours(self, address):        
        check.check_is_af_inet_address(address)  #=@R23  fixme callers        
        self.active_probes += 1        
        utility.start_thread(probe_neighbours_thread(self,address))
        # Proof of @R21: @R23.  Deeply immutable from @E11.

    def build_neighbours(self):
        old_neighbours = self.left_neighbours + self.right_neighbours

        self.left_neighbours  = self.query_peers(self.name,'<',neighbourhood_size)
        self.right_neighbours = self.query_peers(self.name,'>',neighbourhood_size)
        # Proof of @R37 in each of the above: @I9.
        # Proof of @R38: settings.neighbourhood_size is a constant int.

        new_neighbours = [ ]
        for peer in self.left_neighbours + self.right_neighbours:
            if peer not in new_neighbours and peer not in old_neighbours:
                new_neighbours.append(peer)

        for peer in new_neighbours:
            self.probe_neighbours(self.peers[peer].address)
                # Proof of @R23: this is a method of Node, so self isinstance Node.
                # @I2, @I3.  fixme: show that peer is a key of self.peers.

    # Knowledge base maintenance    
    def add_peer_thread(self, name, address, confirmed=1):
        if always_check:
            self.check_invar()
        check.check_is_af_inet_address(address)  #=@R10  fixme callers
        
        if (not check.is_long_name(name)
            or self.peers.has_key(name)
            or name == self.name):
            return
        
        if not confirmed:
            
            ticket, template, wait = self.call(address, ('who are you',))
            if wait: yield 'call',(self,ticket)
            try:
                name = self.get_reply(ticket,template)                
            except Error:
                #print "Bad peer"
                return
            if not check.is_long_name(name):
                #print "Bad peer"
                return
            confirmed = 1

        if self.peers.has_key(name) or name == self.name:
            return

        self.peers[name] = Peer(name,address)
        # Proof of @R8 and @R.I18: tested at head of function; only
        # modification since then is immediately followed by check.
        # name is deeply immutable from @E18.
        # Proof of @R9: @R10; immutability from @E11.
        
        #Optimize!!
        self.build_neighbours()
        
        if always_check:
            self.check_invar()

    # Task utility functions

    def activate_hashtable(self):
        if self.hashtable_running:
        #or self.hashtable_stopped:
            return

        self.hashtable_running = 1
        for peer in self.left_neighbours:
            self.probe(self.peers[peer].address)
        for peer in self.right_neighbours:
            if peer not in self.left_neighbours:
                self.probe(self.peers[peer].address)
        self.check_invar()

    def deactivate_hashtable(self):
        """ Once deactivated, the hashtable can not be reactivated. """

        hashtable_was_running = self.hashtable_running
        self.hashtable_running = 0
        #self.hashtable_stopped = 1

        if not hashtable_was_running:
            return

        def farewell_thread(node, address):
            node.farewellers+=1
            ticket, template, wait = node.call(
                address,('going offline',)) # actually means hashtable deactivate
            if wait: yield 'call',(node,ticket)
            try:
                #note: get_reply is necessary in order to free the entry..
                result = node.get_reply(ticket,template)
            except Error:
                pass
            node.farewellers-=1

        self.farewellers = 0
        for peer in self.peers.values():
            if peer.name in self.left_neighbours or \
                   peer.name in self.right_neighbours:
                utility.start_thread(farewell_thread(self,peer.address))

        def offload_thread(node):
            node.hashtable_offloaders+=1
            
            while node.links:
                links = node.links[:30]
                del node.links[:30]

                if len(node.left_neighbours):
                    left = node.peers[node.left_neighbours[0]].address
                else:
                    left = None
                    
                try:
                    if left == None:
                        raise Error('no left neighbour')                    
                    glob = ['glob']
                    for link in links:
                        glob.append(('store link for',link.name,
                          link.dest,int(link.timeout[1] - time.time())))
                    ticket, template, wait = node.call(left,tuple(glob), 0,2)
                    if wait: yield 'call',(node,ticket)
                    dummy_result = node.get_reply(ticket,template)
                    #print "offloading result:",dummy_result
                except Error,err:
                    print "offloading error",err.message
                    pass

            node.hashtable_offloaders -=1
                


        def after_farewellers_thread(self, offload_thread=offload_thread):
            while self.farewellers:
                yield 'sleep',0.1

            self.hashtable_offloaders=0
            for i in range(20):
                utility.start_thread(offload_thread(self))

        utility.start_thread(after_farewellers_thread(self))
        self.check_invar()
 
    def query_peers(self, name,op,size):
        """op should be either '<' or '>'.

           (However, there may be some benefit in adding support for
           '(<,>)' to return the obvious pair of lists in a single
           call.)

           Ensures @E19: matches(ret, ['long name']), and ret is a new
           object with no other references.
           Ensures @E20: ret \subseteq self.peers.keys()."""
        
        check.check_is_long_name(name)  #=@R37
        check.check_has_type(size, types.IntType)  #=@R38
        
        list = [ ]

        # effic: Don't bother doing arithmetic on the long names,
        # just sort the bare names, locate name with bisect,
        # and extract list items in a modulo fashion.  (Remember to
        # trim size to no more than len(list) though.)
        for peer_name in self.peers.keys():
            if op == '<' :
                list.append((long_name_minus(name, peer_name),
                             peer_name))
            else:
                list.append((long_name_minus(peer_name, name),
                             peer_name))

        list.sort(lambda a,b: long_name_compare(a[0],b[0]))

        result = [ ]
        for item in list[0:size]:
            elem = item[1]
            check.check_is_long_name(elem)
            # Proof: @I2, @I4.
            result.append(elem)
         
        return result

    def socket_handle_errors(self):
        try:
            self.socket_lock.acquire()
            try:
                result, address = self.socket.recvfrom(max_packet_size,0x2000 | _recv_flags)
            finally:
                self.socket_lock.release()

            state = self.link_states.get(address)
            if state:
                state.error_received(self)
        except socket.error:
            pass
    
    def socket_sendto(self,msg,address):
        check.check_is_string(msg)  #=@R1
        check.check_is_af_inet_address(address)  #=@R3
        
        if self.socket_proxy:
            self.socket_proxy.sendto(msg,address)
        else:
            for i in range(100):
                try:
                    #locking is necessary because recvfrom is in a different thread
                    self.socket_lock.acquire()                    
                    try:
                        self.socket.sendto(msg,address)
                        return
                    finally:
                        self.socket_lock.release()
                except socket.error, error:
                    # sleeping avoids flooding the socket
                    # this is a bad idea because we are in the main thread...
                    # better use link_state
                    time.sleep(0.01)
                    # print 'sendto',socket.error,error,address
                    self.socket_handle_errors()
            print "sendto: socket misbehaving",error,address
            #raise Error('Socket misbehaving.')

    def socket_recvfrom(self):
        if self.socket_proxy:
            is_error, address, message = self.socket_proxy.recvfrom()
            if not is_error:
                return message, address

            self.acquire_lock('socket recvfrom')
            try:
                if self.link_states.has_key(address):
                    self.link_states[address].error_received(self)
            finally:
                self.release_lock('socket recvfrom')
            raise Error('socket misbehaving')
        else:
            try:
                self.socket_lock.acquire()
                try:
                    message, address = self.socket.recvfrom(max_packet_size,_recv_flags)
                finally:
                    self.socket_lock.release()
            except socket.error, error:
                self.socket_handle_errors()
                raise Error('socket misbehaving')

            return message, address


    def call(self, address, query, low_priority=0, n_retries=udp_retries):
        """Perform a UDP remote procedure call.

        This function should be called from a generator
        Example:
             
        ticket, template, wait = node.call(params)
        if wait: yield ticket
        result = node.get_reply(ticket,template)

        get_reply must always be called
             
        """

        check.check_is_af_inet_address(address)  #=@R18 fixme check callers
        check.check_matches(query, (types.StringType,))

        # todo: Consider having the signatures be constant, and have
        # add_handler/remove_handler only control whether the object
        # is None.  That way we can check the return value of the call
        # whether or not this node has a handler for the query.
        query_name = query[0]
        (query1_tmpl, result_tmpl) = self.handlers.get(query_name, ('', 'any', 'any'))[1:]
        check.check_matches(query[1:], query1_tmpl)

        if simulate_rogue_replies and query_name != 'glob' and random.random() < 0.2:
            # todo: Remove the restriction on glob.
            return (random_inst.random_inst(result_tmpl), 0.0)

        if address == self.address:

            ticket = self.call_no
            # Proof that self.call_no attribute exists and is of
            # type int: @I30.
            self.call_no += 1
        
            # Proof of @R24: @R4, address not reassigned since then.
            # Proof of @R48: ticket assigned from self.call_no and not
            # reassigned since then; @I30.
            reply = handle_request(self,query,address,ticket)
            if type(reply) == types.InstanceType and reply.__class__ == Error:
                raise reply
            if result_tmpl != 'any':
                check.check_matches(reply, result_tmpl)

            self.replies[ticket]=(reply,0)
            return (ticket,result_tmpl,0)
        
        
        ticket = self.call_no
        self.call_no = self.call_no + 1

        if not self.running:
            self.replies[ticket] = (Error('Node is stopped.'),0)
            return (ticket,result_tmpl,0)

        if self.hashtable_running:
            message = (self.name,ticket,query)
        else:
            message = (None,ticket,query)

        if self.link_states.has_key(address):
            state = self.link_states[address]
        else:
            state = Link_state()
            self.link_states[address] = state
            state.address = address #for monitoring
        message = safe_pickle.dumps(message)


        def call_subthread(self,state,message,n_retries,result_tmpl,query_name,ticket):

            wait_time = state.acquire_access(ticket,low_priority)

            #yield 'wake',(self,state)
            #print "ls",state.address,len(state.waiters),len(state.queue),len(state.low_priority_queue)
            state.waiters.append(ticket)

            # link is down
            if wait_time == None:
                #print 'link down'
                self.replies[ticket]= (Error('no reply'),0)
                #yield 'wake',(self,state)
                (thread,stack) = self.calling_threads[ticket]
                del self.calling_threads[ticket]
                del self.pending_calls[ticket]
                utility.mainthread_call(utility.start_thread,thread,stack)
                return

            total_traffic = 0
            success = 0
            
            for i in range(n_retries):

                if state.is_error():
                    break

                try:
                    # Proof of @R1: message assigned from safe_pickle.dumps above,
                    # not modified since (including in this for loop).  @E1.
                    # Proof of @R3: address not modified in this method;
                    # and our @R4.
                    self.socket_sendto(message, address)
                    total_traffic = total_traffic + len(message)
                    self.update_network_usage("send msg '" + query[0] + "'",len(message))
                except Error:
                    print "sendto error"
                    break

                yield 'sleep',wait_time
                
                success = self.replies.has_key(ticket)
                if success:
                    for j in range(i):
                        self.call_p_success = self.call_p_success*0.99
                    self.call_p_success = self.call_p_success*0.99+0.01
                    total_traffic = total_traffic + self.replies[ticket][1]
                    break

                if not self.running:
                    self.replies[ticket] = (Error('node stopped'),0)
                    break

            state.release_access(ticket, success,i, 0, low_priority)
            #state.wake_queuers(self)
            
            for monitor in self.monitors:
                monitor( 1, address, query, total_traffic )
            
            (thread,stack) = self.calling_threads[ticket]
            del self.calling_threads[ticket]

            if not self.replies.has_key(ticket):            
                if n_retries == udp_retries:
                    state.error_received(self)
                self.replies[ticket] = (Error('no reply'),0)

            # now the calling thread may go on...
            del self.pending_calls[ticket]
            utility.mainthread_call(utility.start_thread,thread,stack)
            return
             
        self.pending_calls[ticket] = call_subthread(
            self,state,message,n_retries,result_tmpl,query_name,ticket)
        
        return (ticket,result_tmpl,1)
   

    def get_reply(self,ticket,template):
        """ Returns the result of a call
        It will raise an Error('no reply') if the address could not be contacted.             
        It will also raise an Error if the remote computer replies with an Error object.
        """

        if self.replies.has_key(ticket):
            reply = self.replies[ticket][0]
            del self.replies[ticket]                
            
            if type(reply) == types.InstanceType and reply.__class__ == Error:
                raise reply
            if (template != 'any' and not check.matches(reply, template)):
                #sys.stderr.write(_("Bad reply from `%s' query: %s doesn't match %s.\n") \
                #                 % ('unknown query', `reply`, `template`))
                raise Error('bad reply')
            return reply
        
        raise Error('reply is missing!!!!')
    

    def find_nodes(self, name, low_priority=0, how_many=4):
        
        def find_nodes_thread(self, find_result, name, low_priority=0, how_many=4):

            failure_list = [ ]
            success_list = [ ]

            if self.hashtable_running:
                list = [(self.name, self.address)]
            else:            
                ticket,template,wait = self.call(
                    self.address,('get peers','<',name,how_many),low_priority)
                if wait: yield 'call',(node,ticket)            
                list = self.get_reply(ticket, template)

                # Loose proof that list matches [('long name', 'mangled address')]:
                # self.call (or rather call_timed) special-cases calls against
                # self.address to do a local despatch.  Our handler for get peers
                # calls query_peers, which (@E19) returns long names.  The handler
                # appends a mangled address.
                # FIXME: what we actually want is a demangled address, afaict.
                if list == [ ]:
                    return
                    #raise Error('find_nodes failed')

            while 1:
                head = list[0]

                try:
                    try:
                        start_time = time.time()
                        ticket, template, wait = self.call(
                            head[1],('glob',('who are you',),('get peers','<',name,how_many)),low_priority)
                        if wait: yield 'call',(self,ticket)
                        returned_value = self.get_reply(ticket,template)
                        elapsed_time = time.time() - start_time 

                        if len(returned_value) != 2:
                            bad_peer(head[1], 'glob reply ' + `returned_value`)
                            raise Error('unexpected reply')

                        real_name, result = returned_value

                        #self.ping_total_time = self.ping_total_time + elapsed_time
                        #self.ping_count = self.ping_count + 1
                        #if elapsed_time > hashtable_activate_threshold:
                        #    self.pings_over_threshold = self.pings_over_threshold + 1
                        #else:
                        #    self.pings_under_threshold = self.pings_under_threshold + 1

                    except Error, error:
                        if error.message == 'no reply':
                            raise error

                        ticket, template, wait = self.call(
                            head[1],('who are you',),low_priority)
                        if wait: yield 'call',(self,ticket)
                        real_name = self.get_reply(ticket,template)

                        ticket, template,wait = self.call(
                            head[1],('get peers','<',name,how_many),low_priority)
                        if wait: yield 'call',(self,ticket)
                        result    = self.get_reply(ticket,template)

                    except TypeError:
                        raise Error('bad reply')

                    if real_name != head[0]:
                        raise Error('wrong name')

                    if type(result) != types.ListType:
                        raise Error('got non-list result from peer')

                    for item in result:
                        if ((type(item) != types.TupleType)
                            or (len(item) != 2)
                            or not check.is_mangled_address(item[1])):
                            raise Error('unexpected reply')

                    success_list.append(head)
                except Error:
                    list = list[1:]
                    failure_list.append(head)
                    result = [ ]

                for item_mangled in result:
                    # Proof of @R11: item_mangled in result; result is either
                    # empty list (`except' clause) or else it has been through the
                    # equivalent of
                    # check.matches(item_mangled, ('any', 'mangled address')).
                    item = (item_mangled[0],address_demangle(item_mangled[1],head[1]))
                    if item not in list and item not in failure_list and item[0] != self.name:
                        index = 0
                        while index < len(list) and not long_name_bracketed(list[index][0],item[0],name):
                            index = index + 1
                        list.insert(index,item)

                if list == [ ]:
                    return
                    #raise Error('find_nodes failed')

                if head == list[0]:
                    break

            def fyi_thread(self, list, whom):
                address = address_mangle(whom[1],self.address)
                for item in list:
                    ticket, template, wait = self.call(item[1],('add peer',whom[0],address),1)
                    if wait: yield 'call',(self,ticket)
                    try:
                        self.get_reply(ticket,template)
                    except Error:
                        pass

            # This optimizes interconnections in the network to
            # respond quickly to common queries and in log time
            # to others.
            utility.start_thread(fyi_thread(self,success_list[1:],head))

            find_result.extend(list)
            return 

        result = [ ]
        subthread = find_nodes_thread(self,result, name, low_priority, how_many)
        return result, subthread
        

    ######################################
    # search methods
    #

    def search_browse_task(self,address,path):
        """Note: there can be duplicates written to pipe."""
        #note: error should not be gui dependent
        import error
        

        def search_browse_subthread(pipe,node,address,path):
            pipe.threads+=1
            position = 0
            while pipe.running:            
                try:
                    ticket, template, wait = node.call(
                        address,('files available',position,position+20,path))
                    if wait: yield 'call',(node,ticket)
                    files = node.get_reply(ticket,template)
                except error.Error, err:
                    pipe.write((address,err.message))
                    if err.message == 'no reply':
                        #todo: do something else
                        #app.name_server.bad_address(address)
                        pass
                    pipe.threads-=1
                    return

                for item in files:

                    if type(item) == types.StringType:
                        #this is just for compatibility with old clients. it should go...
                        utility.start_thread(search_subsubthread(pipe,node,item,address,None))
                    else:
                        pipe.write((address,item))

                if len(files) < 20:
                    break
                position = position + len(files)

            pipe.threads-=1

        def search_subsubthread(pipe,node,search_for,link,source):
            """Note: there can be duplicates written to pipe."""
            
            pipe.threads+=1
            if link == None:
                link = source    
            data_position = 0
            while pipe.running:
                try:
                    # TODO: Why request only one item per packet?
                    ticket, template, wait = node.call(
                        link,('query data',search_for,data_position,data_position+1) )
                    if wait: yield 'call',(node,ticket)
                    data = node.get_reply(ticket, template)
                    # TODO: Check that data is of sequence type.
                except error.Error:
                    break

                for datum in data:
                    pipe.write((link, datum))

                if len(data) < 1:
                    break
                data_position = data_position + len(data)
            pipe.threads-=1

        def search_browse(pipe,node,address,path):
            utility.start_thread(search_browse_subthread(pipe,node,address,path))

        pipe = utility.Pipe()
        pipe.start(search_browse,self,address, path)
        return pipe


    def search_address_list_task(self, source_list):
        import error
        
        def search_address_list_subthread(node, pipe, item):
            pipe.threads += 1
            ticket,template,wait = node.call(item,('identity query',))
            if wait: yield 'call',(node,ticket)
            try:
                result = node.get_reply(ticket,template)
                pipe.write((item,result))
            except error.Error:
                pipe.write((item,{ \
                    'type' : 'daemonic node', \
                    'name' : utility.hostname_of_ip(item[0]) + ':%d' % item[1], \
                    'keywords' : [ ] \
                }))
            pipe.threads -=1


        def search_address_list(pipe,node,list):
            for item in list:
                utility.start_thread(search_address_list_subthread(node,pipe,item))

        pipe = utility.Pipe()
        pipe.start(search_address_list,self,source_list)
        return pipe
            




# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
