# Glue code with magic.py

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Thomas Mangin
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

# BUG/TODO/LIMITATION:
# The magic format is not up to decode JPG file size
#   1 - Learn to live with it
#   2 - Create a new format and convert the magic file to it (Long)

# Initialise two magicA object:
#   one with magic.circle to get the circle type and all information
#   ome with magic.linux to get info about weird file

# Then add the information in fileserver.py

import string
import utility
import os

class classify:
    def __init__(self):
        import magic
        
        file_circle=utility.find_file('magic.circle')
        file_linux=utility.find_file('magic.linux')

        cache_circle=os.path.join(utility.config_dir,"magic.circle.cache")
        cache_linux=os.path.join(utility.config_dir,"magic.linux.cache")

        self.magic={}
        self.magic['circle']=magic.Magic(file_circle,cache_circle)
        self.magic['linux']=magic.Magic(file_linux,cache_linux)
    
    def information(self,file):
        last=""

        result={}
        result['generic']=self.magic['linux'].classify(file)

        circle = self.magic['circle'].classify(file)

        if circle == None:
            result['mime']=None
            return result

        parts=string.split(circle)

        for part in parts:
            if string.find(part,':') > 0:
                split=string.split(part,':')
                if len(split) != 2:
                    raise StandardError, "An error parsing the output of magic"
                result[split[0]]=split[1]
                last=split[0]
            else:
                if last == "":
                    raise StandardError, "An error parsing the output of magic"
                result[last]+= " " + part

        return result

# Not very nice as global initialisation but works,
# It is better than read the magic cache at each call
classifier=classify()

if __name__ == '__main__':
    import sys
    try:    name = sys.argv[1]
    except: name = sys.argv[0]

    info = classifier.information(name)

    for key in info.keys():
        print "key is [", key, "] its content is [", info[key], "]"

# vim: expandtab:shiftwidth=4 :
