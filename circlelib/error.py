# Error class

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

class Error:
    """ An Error class that is used throughout Circle. """

    def __init__(self, str):
        """ Create an Error with a specific message. 
        
                The message might either be an internal message,
                such as "no reply", or a more verbose message to
                be displayed to the used.
                """
        self.message = str

    def __repr__(self):
        return '<Error: '+self.message+'>'


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
