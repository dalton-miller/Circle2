# Generate random data matching a template as used by the `check' module.
# This is useful for doing randomized testing of e.g. perform_request
# and the users of call data.

# Copyright (C) 2003 Monash University
# May be modified & distributed under the terms of the GNU GPL v2.

import math
import random
import types

if __name__ == '__main__':
    import sys
    sys.path = ["."] + sys.path

import check
import error


def random_nat(avg):
    return int(random.expovariate(1.0 / avg) + .5)

def random_char():
    x = random.randrange(256 * 9/8)
    assert(type(x) == types.IntType)
    if x >= 256:
        x = 0
    assert(0 <= x)
    assert(x < 256)
    ret = chr(x)

    assert(type(ret) == types.StringType)
    assert(len(ret) == 1)
    return ret

def random_nullless_char():
    x = random.randrange(255) + 1
    assert(type(x) == types.IntType)
    assert(0 < x)
    assert(x < 256)
    ret = chr(x)

    assert(type(ret) == types.StringType)
    assert(len(ret) == 1)
    assert(ret != '\0')
    return ret

def random_unichar():
    x = random.randrange(65536 * 17/16)
    assert(type(x) == types.IntType)
    if x >= 65536:
        x = 0
    assert(0 <= x)
    assert(x < 65536)
    ret = unichr(x)

    assert(type(ret) == types.UnicodeType)
    assert(len(ret) == 1)
    return ret

def random_concat(empty, avg_len, f):
    ret = empty
    for i in range(random_nat(avg_len)):
        ret += f()
    return ret

def random_append(empty, avg_len, f):
    ret = empty
    for i in range(random_nat(avg_len)):
        ret.append(f())
    return ret

def random_unicode():
    ret = random_concat(u'', 6, random_unichar)

    assert(type(ret) == types.UnicodeType)
    return ret

def random_string():
    ret = random_concat('', 3, random_char)

    assert(type(ret) == types.StringType)
    return ret

def random_nullless_string():
    ret = random_concat('', 6, random_nullless_char)

    assert(type(ret) == types.StringType)
    assert(ret.find('\0') == -1)
    return ret

def random_long():
    if random.random() < 0.1:
        return 0L
    else:
        return long(random.gauss(0.0, math.pow(2.0, 32)))

def random_int():
    return int(random.gauss(0.0, 65536.0))

def random_integer():
    if random.randrange(2):
        return random_long()
    else:
        return random_int()

def random_text():
    if random.randrange(2):
        ret = random_string()
    else:
        ret = random_unicode()
    
    check.check_is_text(ret)
    return ret

def random_name():
    ret = ''
    for i in range(16):
        ret += random_char()

    check.check_is_name(ret)
    return ret

def random_long_name():
    ret = ''
    for i in range(20):
        ret += random_char()

    check.check_is_long_name(ret)
    return ret

def random_opt_text():
    p = random.random()
    if p < 0.3:
        return None
    else:
        return random_text()

def random_immutable():
    p = random.random()
    if p < 0.2:
        ret = random_int()
    elif p < 0.3:
        ret = random_long()
    elif p < 0.5:
        ret = random_string()
    elif p < 0.6:
        ret = random_unicode()
    elif p < 0.8:
        ret = None
    else:
        ret = tuple(random_append([], 2, random_immutable))

    {ret: 0}  # I.e. assert that it's hashable and presumably immutable.
    return ret

def random_dumpable():
    """Random dumpable data."""
    p = random.random()
    if p < 0.1:
        ret = None
    elif p < 0.2:
        ret = random_int()
    elif p < 0.3:
        ret = random_long()
    elif p < 0.4:
        ret = random_string()
    elif p < 0.5:
        ret = random_unicode()
    elif p < 0.7:
        ret = random_append([], 2, random_dumpable)
        if random.random() < 0.5:
            ret = tuple(ret)
    elif p < 0.8:
        ret = {}
        for i in range(random_nat(2)):
            ret[random_immutable()] = random_any()
    else:
        ret = error.Error(random_string())

    check.check_is_dumpable(ret)
    return ret

def random_dumpable_dictionary():
    ret = {}
    for i in range(random_nat(2)):
        ret[random_immutable()] = random_dumpable()
    
    assert(type(ret) == types.DictionaryType)
    check.check_is_dumpable(ret)
    return ret

def random_dumpable_list():
    ret = []
    for i in range(random_nat(2)):
        ret.append(random_any())
    
    assert(type(ret) == types.ListType)
    check.check_is_dumpable(ret)
    return ret

def random_dumpable_tuple():
    return tuple(random_dumpable_list())

def random_any():
    """Random dumpable data.  (Not really just any data.)"""
    return random_dumpable()

def random_mangled_address():
    p = random.random()
    if p < 0.3:
        ret = None
    else:
        if p < 0.6:
            i = None
        else:
            i = random_nullless_string()
        ret = (i, random_int())
    check.check_is_mangled_address(ret)
    return ret

def random_af_inet_address():
    ret = (random_nullless_string(), random_int())

    check.check_is_af_inet_address(ret)
    return ret

def random_public_key():
    ret = (random_long(), random_long())

    check.check_is_public_key(ret)
    return ret

randers = {
    'af_inet_address' : random_af_inet_address,
    'any' : random_dumpable,  # Hack for use with perform_request.
    'dumpable' : random_dumpable,
    'int' : random_integer,
    'integer' : random_integer,
    'long' : random_long,
    'long name' : random_long_name,
    'mangled address' : random_mangled_address,
    'name' : random_name,
    'opt-text' : random_opt_text,
    'public key' : random_public_key,
    'string' : random_string,
    'text' : random_text
}

type_randers = {
    types.IntType : random_int,
    types.LongType : random_long,
    types.StringType : random_string,
    types.UnicodeType : random_unicode,
    types.DictionaryType : random_dumpable_dictionary,
    types.ListType : random_dumpable_list,
    types.TupleType : random_dumpable_tuple
}

def random_template():
    p = random.random()
    if p < 0.1:
        ret = tuple(random_append([], 2, random_template))
    elif p < 0.25:
        ret = random_append([random_template()], 1, random_template)
    elif p < 0.4:
        ret = {}
        for i in range(random_nat(3)):
            ret[random_immutable()] = random_template()
    elif p < 0.9:
        ret = random.choice(randers.keys())
    else:
        ret = random.choice(type_randers.keys())

    check.check_is_template(ret)
    return ret

# Keys that circle code sometimes looks for in dictionaries.
# Extracted from circle code from an unintelligent script:
#   perl -ne "if(s/.*(?:has_key|\.get)[(]'([^']*)'.*/ '\$1',/g) {print}" *y
#     | sort -u
# and manually removing a couple of things.
extra_keys = (
 'attach', 'aug', 'chat', 'crypt', 'description', 'directory', 'filename',
 'freq', 'from', 'gtk', 'human-name', 'key', 'keywords', 'length', 'misc',
 'music_album', 'music_artist', 'music_title', 'name', 'peer-name', 'rate',
 'salt', 'start', 'stop', 'subdirectories', 'text', 'timezone', 'to', 'topics',
 'type', 'up time')

def random_inst(tmpl):
    # todo: Return an error.Error instance in more cases.
    # todo: This is currently specific to request results, in that
    # the results are always dumpable and sometimes contain error.Error
    # instances.
    check.check_is_template(tmpl)

    if type(tmpl) == types.TupleType:
        ret = tuple(map(random_inst, tmpl) + random_dumpable_list())
        # `+ random_dumpable_list()' is because check_matches currently
        # allows so, and some requests do take a variable number of arguments.
    elif type(tmpl) == types.DictionaryType:
        ret = {}
        # Some extra items in case these keys are checked for.
        for i in range(random_nat(3)):
            ret[random.choice(extra_keys)] = random_dumpable()
        for (k,v) in tmpl.items():
            ret[k] = random_inst(v)
    elif type(tmpl) == types.ListType:
        assert(tmpl != [])
        if len(tmpl) == 1:
            ret = []
            for i in range(random_nat(2)):
                ret.append(random_inst(tmpl[0]))
        else:
            ret = random_inst(random.choice(tmpl))
    elif type(tmpl) == types.TypeType:
        f = type_randers.get(tmpl)
        if f is not None:
            ret = f()
        else:
            print "Unhandled type template " + `tmpl` + "\n"
            assert(0)
    elif type(tmpl) == types.StringType:
        f = randers.get(tmpl)
        if f is not None:
            ret = f()
        else:
            print "Unhandled template string " + `tmpl` + "\n"
            assert(0)
    else:
        print "Unrecognized template " + `tmpl` + "\n"
        assert(0)
    check.check_matches(ret, tmpl)
    return ret


if __name__ == '__main__':
    # Create some random templates & their instantiations, and compare
    # with the check module.
    for i in xrange(1000):
        tmpl = random_template()
        check.check_is_template(tmpl)
        x = random_inst(tmpl)


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
