# URLs for Circle files

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

import md5, types

import check
import error
import settings
import utility

# Constants for encoding hashes

_encoding = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-+'
_hex_encoding = '0123456789abcdef'

_decoding = { }
for i in range(64):
    _decoding[_encoding[i]] = i

_hex_decoding = { }
for i in range(16):
    _hex_decoding[_hex_encoding[i]] = i
del i


def hash_of(str):
    """ Find the true name of a string.

            hash_of returns the md5 digested value of str."""
    check.check_is_text(str)    #=@R50

    if type(str) == types.UnicodeType:
        str = str.encode('utf8')
    
    m = md5.new()
    m.update(str)
    ret = m.digest()
    check.check_is_name(ret)  #=@E24
    return ret

def float_hash(address):
    """ Generate a floating-point approximation to address.

            float_name returns a floating-point number in [0, 1.0)
            representing address.  NB that multiple addresses will map to
            the same floating point number."""
    
    sum = 0.0
    for i in range(6, -1, -1):  # i.e. first 7 bytes: ceil(DBL_MANT_DIG/8.0).
        sum = (ord(address[i]) + sum) / 256.0
    return sum

def hash_to_url(name):
    """ Convert an md5 hash generated with hash_of to a human typeable
            representation. """
    value = 0L
    for i in range(settings.name_bytes):
        value = (value<<8) + ord(name[i])

    str = ''
    for i in range(0,settings.name_bytes*8,6):
        str = _encoding[value & 0x3f] + str
        value = value >> 6
    return 'circle-file:'+str+''

def hash_to_person(name):
    check.check_is_name(name)
    value = 0L
    for i in range(settings.name_bytes):
        value = (value<<8) + ord(name[i])

    str = ''
    for i in range(0,settings.name_bytes*8,6):
        str = _encoding[value & 0x3f] + str
        value = value >> 6
    return 'circle-person:'+str+''


def _roundup_divide(numerator, denominator):
    return int((numerator - 1) / denominator) + 1

def hex_md5_to_hash(text):
    """If TEXT is a valid hex-encoded md5sum then return the corresponding name string;
         otherwise raise error.Error."""
    if len(text) != settings.name_bytes * 2:
        raise error.Error('not an MD5 sum')

    str = ''
    for i in range(settings.name_bytes):
        hi_char = text[i * 2]
        lo_char = text[i * 2 + 1]
        if not (_hex_decoding.has_key(hi_char) \
                        and _hex_decoding.has_key(lo_char)):
            return None
        value = (_hex_decoding[hi_char] << 4) + _hex_decoding[lo_char]
        str = str + chr(value)
    return str

def url_to_hash(url):
    """ Convert a string produced with hash_to_url back to a hash. 
    Also recognize hex encoded hashes."""
    try:
        return hex_md5_to_hash(url)
    except error.Error:
        pass

    if url[:12] != 'circle-file:':
        raise error.Error('not a circle url')

    value = 0L
    if len(url[12:]) == _roundup_divide(settings.name_bytes * 8, 6):
        # Standard circle encoding, 6 bits per char.
        for char in url[12:]:
            if not _decoding.has_key(char):
                raise error.Error('not a circle url')
            value = (value<<6) + _decoding[char]
    elif len(url[12:]) == settings.name_bytes * 2:
        # Encoding used by md5sum utility.
        for char in url[12:]:
            if not _hex_decoding.has_key(char):
                raise error.Error('not a circle url')
            value = (value<<4) + _hex_decoding[char]
    else:
        raise error.Error('not a circle url')

    str = ''
    for i in range(settings.name_bytes):
        str = chr(value & 0xff) + str
        value = value >> 8

    return str


def person_to_hash(url):
    """ Convert a string produced with hash_to_person back to a hash. 
    Also recognize hex encoded hashes."""

    if url[:14] != 'circle-person:':
        raise error.Error('not a circle identity')

    value = 0L
    for char in url[14:]:
        if not _decoding.has_key(char):
            raise error.Error('not a circle identity')
        value = (value<<6) + _decoding[char]

    str = ''
    for i in range(settings.name_bytes):
        str = chr(value & 0xff) + str
        value = value >> 8

    return str



# vim: set expandtab :
