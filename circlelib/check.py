# Type checking and assertions

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

import types, threading

import error
import settings
if hasattr(settings, '_'):
    from settings import _

# Used by is_mainthread()
#_mainthread = threading.currentThread()



def check_has_type(item, the_type):
    if type(item) != the_type:
        show_data_type_error(str(the_type), item)

def is_callable(func):
    """Returns true iff func is suitable for passing to apply."""
    
    return (type(func) in (types.FunctionType,
                           types.MethodType,
                           types.BuiltinFunctionType,
                           types.BuiltinMethodType,
                           types.ClassType))

def check_is_callable(func):
    if not is_callable(func):
        show_data_type_error('something callable', func)

def forall(list, pred):
    """Returns true iff pred is true of each element of list."""
    check_assertion(type(list) in (types.TupleType, types.ListType))
    check_is_callable(pred)
    
    for i in list:
        if not apply(pred, (i,)):
            return 0
    return 1

def is_dumpable(obj):
    """Returns true iff obj may be passed to safe_pickle.safe_dump."""
    t = type(obj)
    return ((t == types.NoneType)
            or (t == types.IntType)
            or (t == type(not 0))
            or (t == types.LongType)
            or (t == types.StringType)
            or (t == types.UnicodeType)
            or ((t == types.TupleType)
                and forall(obj, is_dumpable))
            or ((t == types.ListType)
                and forall(obj, is_dumpable))
            or ((t == types.DictionaryType)
                and forall(obj.items(), is_dumpable))
            or ((t == types.InstanceType)
                and obj.__class__ == error.Error))

def check_is_dumpable(obj):
    t = type(obj)
    if ((t == types.NoneType)
        or (t == types.IntType)
        or (t == type(not 0))
        or (t == types.LongType)
        or (t == types.StringType)
        or (t == types.UnicodeType)
        or ((t == types.InstanceType)
            and obj.__class__ == error.Error)):
        return
    if ((t == types.TupleType)
        or (t == types.ListType)):
        for item in obj:
            check_is_dumpable(item)
        return
    if (t == types.DictionaryType):
        for (key,val) in obj.items():
            check_is_dumpable(key)
            check_is_dumpable(val)
        return
    show_data_type_error('something dumpable', obj)

def check_isinstance(obj, the_class):
    check_has_type(the_class, types.ClassType)
    if not isinstance(obj, the_class):
        msg = 'data type error: expecting instance of ' + str(the_class)
        t = type(obj)
        if t == types.InstanceType:
            msg = msg + ', got instance of ' + str(obj.__class__)
        else:
            msg = msg + ', got something of type ' + str(t)
        show_bug(msg + ': `' + str(obj) + "'.")

def is_any(item):
    return 1

def check_is_any(item):
    pass

def is_integer(item):
    return type(item) in (types.IntType, types.LongType, type(not 0))

def check_is_integer(item):
    if not is_integer(item):
        show_data_type_error('integer', item)

def is_long(item):
    return type(item) == types.LongType

def check_is_long(item):
    if type(item) != types.LongType:
        show_data_type_error('long', item)

def is_string(item):
    return type(item) == types.StringType

def check_is_string(item):
    if type(item) != types.StringType:
        show_bug('data type error: expecting string, got ' + repr(item))

def is_text(item):
    "Ensures @E23: (type(item) != types.StringType) or ret."
    return type(item) in (types.StringType, types.UnicodeType)

def check_is_text(item):
    if not is_text(item):
        show_data_type_error('text', item)

def is_opt_text(item):
    return type(item) in (types.StringType, types.UnicodeType, types.NoneType)

def check_is_opt_text(item):
    if not is_opt_text(item):
        show_data_type_error('opt-text', item)

def is_name(item):
    "Ensures @E22: (not ret) or (type(item) == StringType)."
    return ((type(item) == types.StringType)
            and (len(item) == settings.name_bytes))

def check_is_name(item):
    if type(item) != types.StringType or len(item) != settings.name_bytes:
        show_data_type_error('name', item)

def is_long_name(item):
    """Ensures @E18: not(ret) or (item is deeply immutable)."""
    return ((type(item) == types.StringType)
            and (len(item) == settings.long_name_bytes))

def check_is_long_name(item):
    if type(item) != types.StringType or len(item) != settings.long_name_bytes:
        show_bug('data type error')

def is_nullless_string(str):
    return type(str) == types.StringType and str.find('\0') == -1

def check_is_nullless_string(str):
    check_is_string(str)
    if str.find('\0') != -1:
        show_bug('data type error: found null byte in string')

def is_af_any_address(addr):
    return is_af_inet_address(addr) or is_af_unix_address(addr)

def is_af_unix_address(addr):
    return type(addr) == types.StringType

def is_af_inet_address(addr):
    """Ensures @E11: (not ret) or (the object to which addr refers is "deeply
       immutable": it cannot be changed under you."""
    return ((type(addr) == types.TupleType) \
            and (len(addr) == 2) \
            and (is_nullless_string(addr[0])) \
            and (type(addr[1]) == types.IntType))

def check_is_af_inet_address(addr):
    if type(addr) != types.TupleType or len(addr) != 2:
        show_data_type_error('af_inet_address', addr)
    check_is_nullless_string(addr[0])
    check_has_type(addr[1], types.IntType)
    assert(is_af_inet_address(addr))

def is_opt_address(item):
    "Ensures @E21: (not ret) or (item is deeply immutable)."
    return ((item is None)
            or is_af_inet_address(item))
    # Proof of @E21: None is immutable, and @E11.

def check_is_opt_address(item):
    if not is_opt_address(item):
        show_data_type_error('opt-address', item)

def is_mangled_address(maddress):
    """Ensures @E15: (not ret) or (maddress is deeply immutable)."""
    return ((maddress == None)  #=@E4
            or ((type(maddress) == types.TupleType)
                and (maddress[0] is None or is_nullless_string(maddress[0]))
                and (type(maddress[1]) == types.IntType)))

def check_is_mangled_address(item):
    if not is_mangled_address(item):
        show_bug('data type error: expecting mangled address, got ' + str(item))

def is_public_key(item):
    return ((type(item) == types.TupleType)
            and (type(item[0]) == types.LongType)
            and (type(item[1]) == types.LongType))

def check_is_public_key(item):
    if type(item) != types.TupleType or \
         type(item[0]) != types.LongType or \
         type(item[1]) != types.LongType:
        show_bug('data type error')

def is_template(item):
    t = type(item)
    return (((t == types.TupleType)
             and forall(item, is_template))
            or ((t == types.ListType)
                and (item != [])
                and forall(item, is_template))
            or ((t == types.DictionaryType)
                and forall(item.values(), is_template))
            or ((t == types.StringType)
                and _matchers.has_key(item))
            or (t == types.FunctionType)
            or (t == types.TypeType))

def check_is_template(item):
    if not is_template(item):
        show_data_type_error('template', item)

def is_any_timestamp(item):
    t = type(item)
    return t in (types.FloatType, types.LongType)

def check_is_any_timestamp(item):
    if not is_any_timestamp(item):
        show_data_type_error('any timestamp', item)

_matchers = {
  'any': is_any,
  'any timestamp': is_any_timestamp,
  'dumpable': is_dumpable,
  'int': is_integer,
  'integer': is_integer,
  'long': is_long,
  'string': is_string,
  'text': is_text,
  'opt-text': is_opt_text,
  'name': is_name,
  'long name': is_long_name,
  'af_inet_address': is_af_inet_address,
  'address': is_af_inet_address,
  'mangled address': is_mangled_address,
  'opt-address': is_opt_address,
  'public key': is_public_key,
  'template': is_template
}

def matches(item, template):
    """Return true iff item has the type specified by template (see below).

       A valid template is either a key of _matchers,
       or a type (e.g. types.FloatType),
       or a tuple of valid templates,
       or a non-empty list of valid templates,
       or a dictionary each of whose values is a valid template,
       or a function (or lambda) taking one argument.

       List templates: A template with a single element t matches a list each of
       whose elements matches t.  Whereas a template with elements t1,...,tn (n>1)
       matches anything that matches either t1 or ... or tn.

       Note that the tuple and dictionary templates are permissive in the sense
       that they allow item to contain more elements than are specified by the
       template.  E.g. (5, "foo") matches both ('int', 'string') and ('int',)
       and () (but not ('string',) or ('string', 'int')).  Thus you may wish to
       test len(item) after calling matches."""
    
    if type(template) == types.TupleType:
        if type(item) != types.TupleType \
           or len(item) < len(template):
            return 0
        for i in range(len(template)):
            if not matches(item[i], template[i]):
                return 0
        return 1
    
    elif type(template) == types.DictionaryType:
        if type(item) != types.DictionaryType:
            return 0
        for key in template.keys():
            if not item.has_key(key) \
               or not matches(item[key], template[key]):
                return 0
        return 1
    
    elif type(template) == types.FunctionType:
        return template(item)
    
    elif type(template) == types.StringType:
        return _matchers[template](item)
    
    elif type(template) == types.TypeType:
        return type(item) == template
    
    elif type(template) == types.ListType:
        check_assertion(template != [])
        if len(template) == 1:
            if type(item) != types.ListType:
                return 0
            for i in item:
                if not matches(i, template[0]):
                    return 0
            return 1
        else:
            for sub_tmpl in template:
                if matches(item, sub_tmpl):
                    return 1
            return 0

    else:
        show_bug('Unrecognized template')


def check_matches(item, template):
    """If item has the type specified by template (see below) then do nothing;
       otherwise indicate the bug by calling show_bug.

       A valid template is either a key of _matchers,
       or a type (e.g. types.FloatType),
       or a tuple of valid templates,
       or a list of exactly one element, which is a valid template,
       or a dictionary each of whose values is a valid template,
       or a function (or lambda) taking one argument.

       Note that the tuple and dictionary templates are permissive in the sense
       that they allow item to contain more elements than are specified by the
       template.  E.g. (5, "foo") matches both ('int', 'string') and ('int',)
       and () (but not ('string',) or ('string', 'int')).  Thus you may wish to
       test len(item) after calling check_matches."""

    check_is_template(template)

    if not matches(item, template):
        show_bug('data type error:\n'+repr(item)[:70]+'\ndoes not match\n'+repr(template)[:70])

def check_assertion(truth):
    if not truth:
        show_bug('assertion failed')

def check_postcondition(succ, name):
    check_has_type(name, types.StringType)
    
    if not succ:
        show_bug(_('postcondition %s failed') % name)

def show_data_type_error(expected, got, skip=0):
    if type(expected) != types.StringType:
        show_bug('expected must be a string')
    if type(skip) != types.IntType or skip < 0:
        show_bug('skip must be non-negative int')
    
    show_bug('data type error: expecting ' + expected + ', got something of '
             + str(type(got)) + ': ' + `got`, skip + 1)

def show_bug(msg, skip=0):
    """N.B. Don't rely on this raising an exception; in future we may simply
       exit, dump core, erase the hard disk etc."""
    import string
    import sys
    import traceback
    stack_lines = traceback.format_stack()
    if type(msg) != types.StringType:
        msg = 'msg must be string'
        skip = 0
    if type(skip) == types.IntType and len(stack_lines) > 1+skip:
        del stack_lines[-1 - skip:]    
    sys.stderr.write('Circle: ' + msg + '.  ' + _('Traceback:\n')
                     + string.join(stack_lines, ''))
    raise error.Error('bug encountered')


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
