# Channels

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

import check
import error
import hash
import settings
import utility

class Channels:
    
    def __init__(self,app):
    
        self.app = app
        self.node = app.node
        self.list = utility.get_config("channels", {'#welcome': {'muted': 0}})
        self.ads = {}
        self.subs = {}
        self.cache = {} # cache the list of people wo are listening to a channel

    def start(self):
        #self.node.add_handler("channel subscribe query",self)
        for ch in self.list.keys():
            if not self.list[ch]['muted']:
                self.do_sub(ch)

    def stop(self):
        #self.node.remove_handler("channel subscribe query")
        for ch in self.list.keys():
            if not self.list[ch]['muted']:
                self.do_unsub(ch)
        self.save()

    def save(self):
        utility.set_config("channels", self.list);
 

    def get_listening(self):
        list = [ ]
        for item in self.list.keys():
            if not self.list[item]['muted']:
                list.append(item)
        return list

    def is_listening_to(self, channel):
        if not self.list.has_key(channel):
            return 0
        return not self.list[channel]['muted']


    def sub_list_pipe(self, channel):
        return self.node.retrieve(
            hash.hash_of("channel subscribe "+channel),
            settings.channel_redundancy,1)

    def do_sub(self,ch):

        check.check_is_text(ch)
        # Relevance: @R50.

        if self.subs.has_key(ch) or self.ads.has_key(ch):
            raise error.Error(_("erroneous subscription"))
        self.ads[ch]={'type': 'channel exists',
                                    'name': ch,
                                    'keywords':[]}

        #me = self.app.name_server.get_info()
        #self.subs[ch]={'channel': ch}
        #for field in ('type', 'key', 'name'):
        #  self.subs[ch][field]=me[field]
        #del self.subs[ch]['channel']
        #me = self.app.name_server.get_info()
        
        self.subs[ch] = lambda self=self: self.app.name_server.get_info()
        # - has to be a distinct object to allow unpublish
        
        self.node.publish(hash.hash_of('channel exists'),
                          self.ads[ch],settings.channel_redundancy)
        self.node.publish(hash.hash_of('channel subscribe '+ch),
                          self.subs[ch],settings.channel_redundancy)

    def do_unsub(self,ch):

        if not self.subs.has_key(ch) or not self.ads.has_key(ch):
            raise error.Error(_("erroneous unsubscription"))
        self.node.unpublish(self.subs[ch])
        self.node.unpublish(self.ads[ch])
        del self.subs[ch]
        del self.ads[ch]


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
