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
    Searching for various things in the hashtable.
"""

# TODO
#   "availabe from n sources including njh"
#   "trust person x's taste music"

from __future__ import generators
import sys,os,string,types
import error, file_server, settings, utility, hash, check

visited_directories=[]


# Search tree classes
#
# All such classes must provide "get_children", "get_text",
# "get_description", "get_comparator", "update" and "stop"

class Search_tree_object:
    def __init__(self):
        pass

    def stop(self):
        pass

    def get_children(self):
        return None

    def update(self, app):
        return 0

    def get_description(self, node_address):
        return ''

    def get_comparator(self):
        return (-1e10, 0, string.lower(self.text)) 

    def matches(self, item,address):
        return 0


class Search_tree_interior(Search_tree_object):
    def __init__(self, pipe_getter, keywords, anti_keywords, what, mime,\
                 text='',empty_text=' (None)',single_text=' (1 element)',\
                 online_only=0, remote_only=0):
        
        Search_tree_object.__init__(self)
        self.sources = None

        self.on_delete = None
        self.keywords = keywords
        self.remote_only = remote_only
        self.nickname=''
        self.anti_keywords = anti_keywords
        self.mime=mime
        self.what=what
        self.text=text

        self.widget = None        
        self.empty_text=empty_text
        self.single_text=single_text
        self.online_only=online_only
        
        self.pipe_getter = pipe_getter
        self.pipe = None
        
        self.children = [ ]
        self.still_searching = 1
        self.list = [ ] #the children that match the search_params criterion
        self._setup()

    def get_children(self):
        return self.children

    def _setup(self):
        self.type = 'interior'

    def delete(self,child):
        self.children.remove(child)
        apply(self.on_delete,[child.item])

    def get_text(self):
        if self.still_searching and self.pipe:
            return self.text + ' ...'
        elif not self.still_searching and self.children == [ ]:
            return self.text + ': '+self.empty_text
        else:
            return self.text

    def get_comparator(self):
        return (-1e10, 0, string.lower(self.text)) 

    def update(self, app):
        any = 0

        if not self.pipe:
            self.pipe = self.pipe_getter()
            any = 1

        if self.pipe.finished() and self.still_searching:
            self.still_searching = 0
            return 1

        list = self.pipe.read_all()

        prev_pair = None
        for pair in list:
            if pair == prev_pair:
                continue
            link, item = prev_pair = pair

            # this is bad, really
            try:
                item = utility.check_and_demangle_item(item)
            except:
                self.empty_text = item
                continue

            keywords = item.get('keywords',[ ])

            if type(keywords) != types.ListType:
                continue

            # Comparing a string to a unicode can throw an error,
            # so force everything to unicode
            for i in range(len(keywords)):
                keywords[i] = utility.force_unicode(keywords[i])

            bad = 0                
            for key in self.keywords:
                if key not in keywords:
                    bad = 1
            for key in self.anti_keywords:
                if key in keywords:
                    bad = 1
            if item.get('type')=='file':
                if self.mime:
                    mime = item.get('mime')
                    if not mime:
                        bad=1
                    else:
                        if mime.find(self.mime) == -1:
                            bad = 1

            if item.get('type') != 'identity' and self.online_only:
                bad = 1                
                            
            if item.get('type') == 'file' and self.remote_only :
                if app.node.data.has_key(item.get('name')+app.node.salt):
                    bad=1
            
            if bad:
                continue

            any = 1
            if item.get('type') == 'directory':
                any=1
                def pipe_getter(path=item['path'],app=app,link=link):
                    pipe = app.node.search_browse_task(link,path)
                    return pipe
                
                new_interior = Search_tree_directory(
                    pipe_getter,self.keywords,self.anti_keywords,\
                    self.what,self.mime,item['filename'],\
                    self.empty_text,self.single_text,0)
                new_interior.item=item
                
                if self.nickname:
                    new_interior.nickname=self.nickname
                    d=self.nickname+':'
                    if item['path']:
                        d=d+utility.force_unicode(string.join(item['path'],'/'))+'/'
                    visited_directories.append(d)

                self.children.append( new_interior )
            else:
                for child in self.children:
                    if child.matches(item,link):
                        child.add_source(item,link)
                        break
                else:
                    try:
                        if search_item_table.has_key(item['type']):
                            self.children.append( search_item_table[item['type']](item,link,self) )
                    except:                     
                        pass
                    
        return any

    def depth(self):
        return 0


    def stop(self):
        Search_tree_object.stop(self)
        if self.pipe:
            self.pipe.stop()


class Search_tree_directory(Search_tree_interior):

    def _setup(self):
        self.type = 'directory'

    def depth(self):
        return len(self.item['path'])

    def download(self, app, dir=None,download_subdirs=0):
        """ download a directory  """

        def download_thread(self, app, dirname, download_subdirs):
            if not dirname:
                dirname = app.daemon.config['download_dir']
            dirname = os.path.join(dirname, self.item['path'][-1])
            if not os.path.exists(dirname):
                os.mkdir(dirname)
            list = []
            self.still_searching=1
            sleep_time=0.1
            while self.still_searching:
                yield 'sleep',sleep_time
                sleep_time=sleep_time*1.25
                children = self.get_children()
                for item in children:
                    if item not in list:
                        list.append(item)
                        if item.item['type']=='file':
                            app.file_server.download(item.item,item.sources,dirname,no_overload=1)
                        elif download_subdirs:
                            item.download(app,dirname,1)
                self.update(app)

        utility.start_thread(download_thread(self, app, dir, download_subdirs))


class Search_tree_leaf(Search_tree_object):
    
    def __init__(self, item, source, father = None):
        Search_tree_object.__init__(self)

        self.father  = father  # the interior to which this leaf belongs

        self.item    = item
        self.sources = [ source ]
        self.widget  = None        
        self.type    = 'leaf'
        self._setup()

        self.on_new_address = None #what to do if a new source is found

    def get_text(self):
        return self.title

    def get_comparator(self):
        return (-len(self.sources), 0, string.lower(self.title))

    def get_description(self, node_address):
        return self.description

    def add_source(self,item,address):
        if address in self.sources:
            return 0
        self.sources.append(address)
        return 1


class Search_tree_identity(Search_tree_leaf):

    def __init__(self, item,source,father):
        self.address = None
        Search_tree_leaf.__init__(self, item,source,father)
        self.type = 'identity'

    def _setup(self):
        if self.item['type'] == 'identity':
            self.address = self.sources[0]

        self.name = utility.force_unicode(self.item['name']) + \
                    ' (' + utility.force_unicode(self.item.get('human-name','')) + ')'

        self.update_description()


    def update_description(self):
        self.title = self.name
        self.description = _('Name: ') + \
                           utility.force_unicode(self.item.get('human-name','')) + \
                           '\n  '+_('Username: ') + \
                           utility.force_unicode(self.item['name'])
                                             
        if self.address:
            self.title = self.title + _(' (online)')
            self.description = self.description + \
                '\n  '+_('Location: ')+ self.address[0]+':'+repr(self.address[1]) 

    def get_comparator(self):
        return (0, 0, string.lower(self.title))

    def add_source(self,item,address):
        if not Search_tree_leaf.add_source(self,item,address):
            return 0

        if item['type'] == 'identity':
            self.address = address
            self.update_description()
            
            if self.on_new_address:
                self.on_new_address()
        return 1


    def matches(self, item,address):
        return item['type'] in ['identity','identity offline demangled']\
               and self.item['key'] == item['key']



class Search_tree_daemonic_node(Search_tree_leaf):
    def _setup(self):
        self.title = _('Daemon at %s')%self.item['name']
        self.description = self.title
        self.type = 'daemonic node'

    def get_comparator(self):
        return (-len(self.sources), 1, string.lower(self.title))
    

class Search_tree_channel_exists(Search_tree_leaf):
    def _setup(self):
        self.title = utility.force_unicode( self.item['name'] )
        self.description = _("1 subscriber on-line.")
        self.type = 'channel exists'

    def add_source(self, item,address):
        if not Search_tree_leaf.add_source(self,item,address):
            return 0

        self.description = _("%d subscribers on-line.") % len(self.sources)
        return 1
 
    def matches(self, item,address):
        return self.item['type'] == 'channel exists' and self.item['name'] == item['name']


class Search_tree_file(Search_tree_leaf):

    def _setup(self):

        self.type = 'file'
        self.players = None
        if not self.item.has_key('filename') or \
             not self.item.has_key('length'):
             #or not self.item.has_key('name'):
            raise error.Error(_('Bad datum'))

        #if self.item.get('music_title'):
        #    self.title = self.item['music_title']
        #    if self.item.get('music_artist'):
        #        self.title = self.title + _(' by ') + self.item['music_artist']
        #else:
        #    self.title = self.item['filename']

        self.title = utility.force_unicode(self.item['filename'])
        self.title = utility.force_unicode(self.title)         
        keys = [('filename',''),('music_title',_('   Title: ')),('music_album',_('   Album: ')),('music_artist',_('   Artist: '))]
        self.description = ''
        for key in keys:
            if self.item.has_key(key[0]):
                self.description = self.description+key[1]+\
                    utility.force_unicode(self.item[key[0]])+'\n'
        self.description_template = self.description


    def get_description(self, node_address):

        if node_address in self.sources:
            n = max(1,len(self.sources)-1)
        else:
            n = len(self.sources)

        return self.description_template + \
            (_("File available from %d source%s.") % (n,(n>1 and 's' or '')))

    def add_source(self, item,address):
        if not Search_tree_leaf.add_source(self,item,address):
            return 0
        return 1
 

    def matches(self, item,address):
        if self.item.get('name'):            
            return self.item.get('name') == item.get('name')        
        else:            
            return self.item == item        

        
    def delete(self, app, item):
        try:
            if item.get('name'):
                app.file_server.remove_file(item['name'])
            else:
                try:
                    os.unlink(item['local_path'])
                except OSError,err:
                    raise error.Error('Cannot delete '+item['local_path']+': file not found')
            #update the interior
            self.father.delete(self)
        except error.Error, err:
            app.show_error(err)


    def download(self, app):
        try:
            app.file_server.download(self.item,self.sources,app.daemon.config['download_dir'])
        except error.Error, err:
            app.show_error(err)

    def get_text(self):
        return self.title + '  (%s) '  % utility.human_size(self.item['length'])


class Search_tree_auction(Search_tree_leaf):

    def _setup(self):

        self.title = utility.force_unicode(self.item['title'])
        self.type = 'auction'

    def get_description(self, node_address):
        return 'auction'

    def add_source(self, item,address):
        if not Search_tree_leaf.add_source(self,item,address):
            return 0

        return 1
 
    def matches(self, item,address):
        if self.item.get('name'):            
            return self.item.get('name') == item.get('name')        
        else:            
            return self.item == item        
        
    def get_text(self):
        return self.title



search_item_table = {
    'identity' : Search_tree_identity,
    'identity offline demangled' : Search_tree_identity,
    'daemonic node' : Search_tree_daemonic_node,
    'channel exists' : Search_tree_channel_exists,
    'file' : Search_tree_file,
    'auction' : Search_tree_auction
}
