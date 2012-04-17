# Safe pickler (no importing)

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

import cStringIO
import check
from types import *

from error import Error
from crypto.number import longtobytes, bytestolong

def _safe_pickle_error():
    return Error('error pickling object')

# Note: value must be a non-negative int.
def save_int(value, file):
    if(value < 0):
        raise _safe_pickle_error()
    while 1:
        low = value & 127
        value = value >> 7
        if value:
            low = low + 128
        file.write(chr(low))
        if not value:
            break

def load_int(file):
    result = 0
    position = 0
    more = 1
    while more:
        value = ord(file.read(1))
        more = value & 128
        result = result + ((value&127)<<position)
        position = position + 7 

    return result

def dump(object, file):
    """Try to safe-pickle object into the specified file.

       If object is not safe-picklable, then raises a _safe_pickle_error.
       """
    if type(object) == NoneType:
        file.write('N')
    elif type(object) in (IntType, type(not 0)) and object >= 0:
        file.write('I')
        save_int(object, file)
    elif type(object) == IntType:
        file.write('J')
        save_int(-object, file)
    elif type(object) == LongType and object >= 0:
        file.write('B')
        str = longtobytes(object)
        save_int(len(str),file)
        file.write(str)
    elif type(object) == LongType:
        file.write('C')
        str = longtobytes(-object)
        save_int(len(str),file)
        file.write(str)
    elif type(object) == StringType:
        file.write('S')
        save_int(len(object),file)
        file.write(object)
    elif type(object) == UnicodeType:
        file.write('U')
        str = object.encode('utf8')
        save_int(len(str),file)
        file.write(str)
    elif type(object) == TupleType:
        file.write('T')
        save_int(len(object),file)
        for item in object:
            dump(item,file)
    elif type(object) == ListType:
        file.write('L')
        save_int(len(object),file)
        for item in object:
            dump(item,file)
    elif type(object) == DictionaryType:
        file.write('M')
        save_int(len(object),file)
        for item in object.items():
            dump(item[0],file)
            dump(item[1],file)
    elif type(object) == InstanceType and object.__class__ == Error:
        file.write('E')
        save_int(len(object.message),file)
        file.write(object.message)
    else:
        raise _safe_pickle_error()

def load(file):
    t = file.read(1)
    if t == 'N':
        return None
    elif t == 'I':
        return load_int(file)
    elif t == 'J':
        return -load_int(file)
    elif t == 'B':
        length = load_int(file)
        str = file.read(length)
        return bytestolong(str)
    elif t == 'C':
        length = load_int(file)
        str = file.read(length)
        return -bytestolong(str)
    elif t == 'S':
        length = load_int(file)
        return file.read(length)
    elif t == 'U':
        length = load_int(file)
        str = file.read(length)
        try:
            return unicode(str,'utf8')

            # Force unicode to ascii. This is transitional stuff: gtk throws an
            # exception if it gets a unicode character it can't represent, which
            # would mean that during transition to unicode, the CVS version would
            # crash the released version. To avoid that, we make the released
            # version smash unicode to ascii. Then the CVS version can play with
            # unicode all it likes, without hurting other users. 
            #                                                 --Jiri
            #return unicode(str,'utf8').encode('ascii','replace')
        except UnicodeError:
            raise _safe_pickle_error()
    elif t == 'T':
        length = load_int(file)
        result = ( )
        for i in range(length):
            result = result + (load(file),)
        return result
    elif t == 'L':
        length = load_int(file)
        result = [ ]
        for i in range(length):
            result.append(load(file))
        return result
    elif t == 'M':
        length = load_int(file)
        result = { }
        for i in range(length):
            key   = load(file)
            value = load(file)
            result[key] = value
        return result
    elif t == 'E':
        length = load_int(file)
        return Error(file.read(length))
    else:
        raise _safe_pickle_error()

def dumps(object):
    """Try to safe-pickle object into a string, and return the result.

       If object is not safe-picklable, then raises a _safe_pickle_error.
       """
    file = cStringIO.StringIO()
    dump(object,file)
    ret = file.getvalue()

    check.check_is_string(ret) #=@E1
    return ret

def loads(string):
    """De-pickle string, or raise an exception if not a valid pickled object."""
    if type(string) != StringType:
        raise Error('bad pickle: not a string')
    file = cStringIO.StringIO(string)
    return load(file)


# vim: set expandtab :
