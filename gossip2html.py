#! /usr/bin/python

# `gossip2html.py somedir' converts your ~/.circle/gossip file to
# somedir/index.html and somedir/goss_*.html.

# Note: This is a throwaway demonstration of how one could do a gateway
# from gossip to whatever other system.  If you want to add features,
# then PLEASE consider starting from some existing web forum software,
# making this script just feed into that system.

# See GroupLens (google finds both the home page
# http://www.cs.umn.edu/Research/GroupLens/ and caches of their paper) for how
# to do ratings better than circle does.  Such functionality would be a useful
# addition to any web forum software, and would have an immediate user base of
# tens of thousands rather than the tens of circle users.

import os
import string
import sys
import time
import types

from circlelib import chat, hash, utility

try:
    import gettext
    gettext.install('circle')
except:
    __builtins__._ = lambda s: s


if len(sys.argv) != 2:
    sys.stderr.write("Usage: %s <output directory>.\n" % sys.argv[0])
    sys.exit(1)

out_dir = sys.argv[1]

gossips = utility.get_checked_config('gossip', types.ListType, [ ])

def elem(tag, html):
    return '<' + tag + '>' + html + '</' + tag + '>';

def tr(html):
    return elem('tr', html)

def td(html):
    return elem('td', html)

def a(html, href=None):
    """href must already be in quoted form."""
    if href is not None:
        return '<a href=' + href + '>' + html + '</a>'
    else:
        return elem('a', html)

encoding = 'utf8'

def force_unicode(text):
    if type(text) == types.StringType:
        text = unicode(text, 'CP1252', 'replace')
    assert(type(text) == types.UnicodeType)
    return text

# pjm: I'm not sure why `http-equiv... charset=' wasn't effective.
# We'll just encode as numeric references, which seems to work.
def html_encode_char(ch):
    assert(type(ch) == types.UnicodeType)
    if ch == u'&':
        ret = '&amp;'
    elif ch == u'<':
        ret = '&lt;'
    elif ch == u'>':
        ret = '&gt;'
    elif ch == u'\n':
        ret = '<br>\n'
    else:
        o = ord(ch)
        if o > 127:
            ret = '&#x%x;' % o
        else:
            ret = chr(o)
    assert(type(ret) == types.StringType)
    return ret

def html_encode(text):
    ret = ''.join(map(html_encode_char, force_unicode(text)))
    assert(type(ret) == types.StringType)
    return ret
    #str = force_unicode(text).encode(encoding, 'replace')
    #str = string.replace(str, '&', '&amp;')
    #str = string.replace(str, '<', '&lt;')
    #str = string.replace(str, '>', '&gt;')
    #str = string.replace(str, '\n', '<br>')
    #return str

subj_rows = []
for g in gossips:
    if type(g) != types.DictionaryType:
        print _("Warning: ignoring corrupt gossip item: "), `g`
        continue

    wodge = g.get('wodge')
    if type(wodge) != types.DictionaryType:
        print _("Warning: ignoring non-dictionary wodge: "), `wodge`
        continue
    
    enc = {}
    for key in ('subject', 'human-name', 'text'):
        val = wodge.get(key)
        if type(val) not in (types.StringType, types.UnicodeType):
            print _("Warning: ignoring wodge with non-text '%s': %s") % (key, `val`)
        enc[key] = html_encode(val)
    val = wodge.get('post-time')
    if type(val) != types.LongType:
        print _("Warning: ignoring wodge with non-long 'post-time': %s") % `val`

    wodge_hash = hash.hash_of(string.join([force_unicode(wodge[key]) for key in ('subject', 'human-name', 'text')], u'\0').encode('utf8', 'replace'))
    wodge_hash_str = hash.hash_to_url(wodge_hash)[len('circle-file:'):]
    basename = 'goss_' + wodge_hash_str + '.html'
    href = '"' + basename + '"'
    subj = enc['subject']
    if not subj:
        subj = '(None)'
    subj_rows.append((-wodge['post-time'], tr(td(enc['human-name']) + td(a(subj, href=href)))))

    date = chat.standard2host_timestamp(wodge['post-time'])

    lines = [
     '<html>',
     '<head>',
     '<title>Gossip: ' + subj + '</title>',
     '</head>',
     '<body>',
     '<h1>' + subj + '</h1>',
     '<p>Posted ' + time.strftime('%d %b %Y', time.localtime(date))
       + ' by ' + enc['human-name'] + '</p>',
     '<p>' + enc['text'] + '</p>',
     '</body>',
     '</html>']
    f = open(os.path.join(out_dir, basename), 'w')
    f.write(string.join(lines, '\n'))
    f.close()

subj_rows.sort()

index_lines = [
 '<html>',
 '<head>',
 '<meta http-equiv="Content-Type" content="text/html; charset=' + encoding + '" />',
 '<title>Gossips</title>',
 '</head>',
 '<body>',
 '<h1>Gossips</h1>',
 '<table summary="Links to gossip items posted, sorted by date">',
 '<tr><th>Name</th><th>Subject</th></tr>']
index_lines.extend([r[1] for r in subj_rows])
index_lines.extend([
 '</table>',
 '</body>',
 '</html>'])
f = open(os.path.join(out_dir, 'index.html'), 'w')
f.write(string.join(index_lines, '\n'))
f.close()


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
