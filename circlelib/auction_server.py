# Auction server

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


"""
    This file belongs to the core of circle


    like for files: each auction has a name

"""

# auctions can be watched, like acquaintances, publish watchers
# I may publish:
#  - auctions (like id online)
#  - auction watchers
#  - may send an email to watchers if they require



from __future__ import generators
import time,os,types,traceback,select,threading
import sys
import stat
import string
import check
import error
import hash
import node
import safe_pickle
import settings
import utility





class Auction_server:
    
    def __init__(self, app, node):

        self.app = app
        self.node = node

        self.auctions = { }        # the list of items I am selling
        self.auctions_prices = { } # current prices
        self.watchers      = [ ]   # the people who are watching my auctions
            
    
    def publish_auction(self, title, category, description, initial_price=0):

        info = {
            'type'       : 'auction',
            'category'   : category,
            'title'      : title,
            'seller'     : self.app.node.name,
            'description': description
            }        
        name = hash.hash_of(safe_pickle.dumps(info))
        self.auctions[name] = info
        self.auctions_prices[name] = initial_price
                
        keywords = string.split(string.lower(title))
        for item in keywords:
            self.node.publish(hash.hash_of('auction-name '+ item),
                              info, settings.identity_redundancy)

        self.node.publish(hash.hash_of('auction-category '+ category),
                          info, settings.identity_redundancy)


    def start(self):
        self.running = 1
        self.node.add_handler('auction bid', self, (types.IntType, types.IntType))
        self.node.add_handler('auction list',self)
        self.node.add_handler('auction get',self)


    def stop(self):
        self.running = 0
        self.node.remove_handler("auction list")
        self.node.remove_handler("auction get")
        self.node.remove_handler("auction bid")
        

    def handle(self, request, address, call_id):
        check.check_matches(request, (types.StringType,))
        check.check_is_af_inet_address(address)

        if request[0] == 'auction bid':
            name = request[1]
            bid = request[2]
            if self.auctions.has_key(name):
                print "auction found"
                if self.auctions_prices[name] < bid:
                    self.auctions_prices[name] = bid
                    return 'ok'
                else:
                    print "bid too low"
                    return 'bid too low'
            else:
                return 'error: no such auction'
            
            
        elif request[0] == 'auction list':

            list = self.auctions
            return list



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
