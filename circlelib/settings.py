# Constants

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Paul Francis Harrison
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

import sys

# Don't crash if there is no i18n
try:
    _
except:
    def _(s): return s

def gtk_loaded():
    return sys.modules.has_key('gtk')

# Circle does not rely on DNS to work, so if you add a host
# with a static IP, sometimes add it by IP

initial_peers = (
        'hawks.cs.mu.oz.au',             # 128.250.37.21
        '130.194.67.56',                 # depot.csse.monash.edu.au
        'bowman.csse.monash.edu.au',     # 130.194.67.120
        '128.250.33.10',                 # ceres.cs.mu.oz.au
        'circle.slhan.org',              # Dynamic IP (62.31.4.196)
        '130.194.67.182',                # barrymore.csse.monash.edu.au
        '210.49.194.121',                # No reverse DNS
        'redback.cs.rmit.edu.au:32792',  # 131.170.24.65
        '141.20.65.178',                 # dale.biologie.hu-berlin.de'
        'poole.csse.monash.edu.au',
        #'hawthorn.csse.monash.edu.au',
        'thecircle.dyndns.org'           # dynamic IP 
        '130.194.67.206')                # mandarin.csse.monash.edu.au

name_bytes = 16
name_salt = 4
long_name_bytes = name_bytes + name_salt

min_search_keyword_len = 3

#max_node_threads = 20
#max_task_manager_threads = 20

max_active_threads = 16

# Activate hashtable this many seconds after node startup.
hashtable_activate_time = 60*60.0

# Average ping time an active node should be able to achieve.
hashtable_activate_threshold = 4.0

# assumption: any participating node has already been stable for hashtable_activate_time
start_poll_interval = hashtable_activate_time/2.0 # was 10*60
poll_max_interval = 6*60.0*60.0

# @I12: type(start_poll_interval) == types.FloatType.
poll_expand_factor = 1.25
poll_breathingspace = 5*60
publish_retry_interval = 5*60.0
# @I13: type(publish_retry_interval) == types.FloatType.

neighbourhood_size = 5
peer_cache_size = 20
peer_poll_start_interval = 60.0
peer_poll_max_interval = 15*60.0
# @I11: type(peer_poll_start_interval) == types.FloatType
peer_poll_expand_factor = 1.2 #was 1.05



reply_cache_size = 100

max_known_peers = 40

link_state_timeout = 2*60

udp_default_ping_time = 3.0  
udp_max_ping_time = 10.0
udp_min_ping_time = 0.25 # was 0.25, set to more conservative setting because people complained in v0.25 
udp_max_window = 10.0 # the max number of queries to a socket
udp_retries = 20
udp_error_time = 30.0 # must exceed max ping time
# @I10: type(udp_error_time) == types.FloatType

gossip_fetch_time = 60.0 # this is a timeout for fetching gossip

max_packet_size = 65536

identity_redundancy = 4
cache_redundancy = 4
channel_redundancy = 4

max_cache_names = 10  # Number of hashtable entries a cache item can use

download_threads = 8 
download_chunk = 1400

default_ports = range(29610,29620)

default_http_port = 29621

drawing_size = 60

#How many wodges to cache
gossip_cache_size = 1000

#How many messages to cache
incoming_message_history_size = 100

# (distance >= than this, description)
distance_descriptions = [
    (0.0, _('The gospel truth.')),
    (0.5, _('Exceptionally insightful.')),
    (1.0, _('Interesting and informative.')),
    (2.0, _('Quite interesting and fairly accurate.')),
    (5.0, _('Sometimes interesting.')),
    (10.0, _('Of very occasional interest.')),
    (15.0, _('Frankly, a load of rubbish.')),
    (20.0, _('Evil, evil lies.'))
]

gratuitous_plugs = [
    _('Circle Chat will be even more fun once all your friends are on it...'),
    _('Circle Gossip will be even more interesting when all your friends are posting...'),
    _('The more people on Circle, the more music to listen to!'),
    _('Share and enjoy :-)'),
    _('Obey the cat.'),
    _('Look ma! No control points!'),
    '"... stop yanking and just stare at the coconut for a while." -Pirsig, ZAMM',

    '"These little Japanese voodoo cats. Maneki neko, right? They started showing up everywhere I went. There\'s a china cat in my handbag. There\'s three china cats at the office. Suddenly they\'re on display in the windows of every antique store in Providence. My car radio starts making meowing noises at me."  -Bruce Sterling, Maneki Neko',

    u'"\xa1Quien calla, otorga!"',
    _('There is no conspiracy.'),
    _('One would never guess it, but it\'s actually simpler than it looks.'),

    "Ubi dubium ibi libertas.",

    "All your music are belong to us",

    "What the f*** do you think you're doing?\n - Madonna",

    "We must not believe the many, who say that only free people ought to be educated, but we should rather believe the philosophers who say that only the educated are free.\n  -Epictetus, Discourses",

    "....only those who study but do not share a specific social understanding think of it as a system of rules.\n  -H. Dreyfus, 1991",

    "Just when scientists get really good at doing what they are doing, they die.\n  -David Hull",

    "This is the world we live in and these are the hands we're given.\n  -Phil Collins",

    "The children thought they were playing a game. They didn't realize they were rewiring their brains.\n  -Chicago Tribune, 5 Jan 1996",

"""Though nothing can bring back the hour
Of splendour in the grass, of glory in the flower;
We will grieve not, rather find
Strength in what remains behind;
-William Wordsworth""",

    "Shoot me now!  Shoot me now!\n  - Daffy Duck"
    ]

tips = [
    _("""
    Your settings are stored in ~/.circle (or \\Documents
    and Settings\\username\\circle_config under Windows).
    If you want to appear as the same person when using
    another machine, copy this directory across to it."""),
    _("""
    Use \'/who #welcome\' to see who else is on channel #welcome."""),
    _("""
    Use \'/search <keyword>\' to search for files."""),
    _("""
    You may create a new chat channel by posting to it.
    Example:
      [myself] /join #mychannel
      Joined #mychannel
      [myself >> #mychannel] hello!"""),
    _("""
    You can click on most coloured text.
    Click on 'tip' if you want a new tip."""),
    _("""
    After startup, it takes a few minutes before your files are published."""),
    _("""
    The right panel contains your list of acquaintances."""),
    _("""
    You may paste a circle URL inside a chat message.
    The people who will receive it will see it as a link."""),
    _("""
    Use \'/ls nick:\' to list nick's directory."""),
    _("""
    Keyboard Shortcuts:
    Ctrl-X  /exit\t  Ctrl-O  postpone command    
    Ctrl-L  /clear\t  Ctrl-D  enter/leave shell
    Ctrl-J  /join\t   Ctrl-W  /who
    Ctrl-F  /find\t  Crtl-S  /search."""),
    _("""
    You can clear the window with ctrl-L."""),
    _("""
    You may push the line you are typing in the history
    with Ctrl-O, and retrieve it later with the up arrow.
    This is useful if someone interrupts you while you
    are typing a long message."""),
    _("""
    If you play a remote music file, it will be
    downloaded and played at the same time.
    Cancel the download if the music is not good."""),
    _("""
    Circle commands begin with \'/\'. When typing a command,
    the tabulation gives you access to auto-completions.
    Type '/' and TAB to see the whole list of commands."""),
    _("""
    A search keyword prefixed with \'!\' is negated.
    Example: \'/search python !monty\'"""),
    _("""
    When you are offline, your identity information
    is maintained by the other nodes of the network.
    It will expire if you stay offline for more than 30 days."""),
    _("""
    Use \'/quiet\' to indicate when you are busy and can\'t chat."""),
    _("""
    You can give someone a file with \'/give <filename>\'."""),
    _("""
    You can use Circle as a Python interpreter, just prefix your
    command with a "!". This makes a handy calculator among other things."""),
    _("""
    You can run shell commands in Circle (under Un*x),
    just prefix the command with a \'//\'.""")
]

tab_size = 3.5

terminal_encoding = sys.getdefaultencoding()

# Most terminals will support this (?)
if terminal_encoding == 'ascii':
    terminal_encoding = 'latin-1'

# vim: expandtab:shiftwidth=4 :
