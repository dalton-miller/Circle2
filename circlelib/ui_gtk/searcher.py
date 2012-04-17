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


# TODO
#   "availabe from n sources including njh"
#   "trust person x's taste music"

import sys,os,string,types,gtk

from circlelib import error, settings, utility, hash, check, search
from circlelib.name_server import key_name        
import widgets

import textviewer
try:
    import imageviewer
except:
    imageviewer = None


def play_file(leaf, action, app):
    """
    If self.item does not have a 'name', it must have a 'local_path'.
    it means it was returned by a 'files availables' query.
    in that case I should know where it is, and be able to
    download it without querying the hashtable.
    see /give
    """
    if not hasattr(leaf,'file_field'):
        leaf.file_field=None

    #first case: local file accessed through /ls
    if leaf.item.get('local_path'):
        leaf.players[action](leaf.item, None,leaf.file_field)
        return

    #2nd case: locally published file
    if app.file_server.paths.has_key(leaf.item['name']):
        path, mtime = app.file_server.paths.get(leaf.item['name'])
        try:
            leaf.item['local_path'] = path
            leaf.players[action]( leaf.item, None, leaf.file_field)
        except error.Error, err:
            app.show_error(err)
            # and don't show checkbox...            
        return

    #3rd case: file is not local. we will have to download it

    #first check if already downloading
    for d in app.file_server.downloaders:
        if d.data['name']==leaf.item['name']:
            downloader=d
            break
    else:
        try:
            downloader = app.file_server.download(
                leaf.item, leaf.sources,app.daemon.config['download_dir'])
        except error.Error, err:
            app.show_error(err)
            return

    try:
        leaf.players[action](leaf.item, downloader, leaf.file_field)
    except error.Error, err:
        app.show_error(err)
        if downloader.running:
            downloader.stop()
        app.file_server.remove_file(downloader.data['name'],downloader.filename)
        return








def search_browse_files(address, node,app, notebook=None):
    pipe = node.search_browse_task(address, [])
    Searcher('Local files',pipe, node,app, notebook).start()

def search_for_files(str, node, app, notebook=None,mime=''):
    temp_list = string.split(str)
    list = [ ]
    for item in temp_list:
        if len(item) >= settings.min_search_keyword_len:
            list.append(utility.remove_accents(item.lower()))

    if not list:
        raise error.Error(_("Please specify some keywords to search for.\n" +\
                            "(keywords must contain at least %d letters)") \
                          % settings.min_search_keyword_len)

    largest,keywords,anti_keywords,title = utility.parse_keywords(list)
    if not keywords:
        raise error.Error(
            _("Please specify at least one positive search term (i.e. not preceded by !).\n" ))
    pipe = node.retrieve(hash.hash_of(largest))
    Searcher(title, pipe, node, app, notebook, keywords, anti_keywords, mime).start()
    

def search_for_auctions(str, node, app, notebook=None):
    temp_list = string.split(str)
    list = [ ]
    for item in temp_list:
        if len(item) >= settings.min_search_keyword_len:
            list.append(utility.remove_accents(item.lower()))

    if not list:
        raise error.Error(_("Please specify some keywords to search for.\n" +\
                            "(keywords must contain at least %d letters)") \
                          % settings.min_search_keyword_len)

    largest,keywords,anti_keywords,title = utility.parse_keywords(list)
    if not keywords:
        raise error.Error(_("Please specify at least one positive keyword.\n" ))
    pipe = node.retrieve(hash.hash_of('auction-name '+largest),settings.identity_redundancy)
    Searcher(title,pipe, node,app,notebook,keywords,anti_keywords).start()


def search_for_name(name,title, node,app):
    pipe = node.retrieve(name)
    Searcher(title,pipe,node,app).start()

def search_for_people(str, node,app):
    list = string.split(utility.remove_accents(str.lower()))
    if not list:
        raise error.Error(_("Please specify some keywords to search for.\n" +\
                            "For example, their name or username."))
    largest,keywords,anti_keywords,title = utility.parse_keywords(list)
    pipe = node.retrieve(hash.hash_of('identity-name '+largest), settings.identity_redundancy)
    Searcher(_('People matching: ')+title,pipe, node,app,keywords,anti_keywords).start()

def search_for_all_people(node,app):
    pipe = node.retrieve(hash.hash_of('service identity'), settings.identity_redundancy)
    Searcher(_('All people'),pipe, node,app).start()

def search_for_all_channels(node,app):
    pipe = node.retrieve(hash.hash_of('channel exists'), settings.channel_redundancy)
    Searcher(_('All channels'),pipe, node,app).start()

def search_for_people_on_channel(channel, node,app):
    pipe = node.retrieve(hash.hash_of('channel subscribe '+channel), settings.channel_redundancy)
    Searcher(_('People on %s')%channel,pipe, node,app).start()

def search_show_sources(source_list, node,app, title='Sources'):
    pipe = node.search_address_list_task(source_list)
    Searcher(title,pipe, node, app).start()



def set_leaf_widget(leaf):

    if leaf.type == 'file':
        if leaf.item.get('name'):
            leaf.widget = gtk.HBox(gtk.FALSE, 0)
            leaf.widget.pack_start(gtk.Label(_('URL: ')), gtk.FALSE, gtk.FALSE, 0)
            entry = gtk.Entry()
            entry.set_text(hash.hash_to_url(leaf.item['name']))
            leaf.widget.pack_start(entry, gtk.TRUE, gtk.TRUE, 0)

    elif leaf.type == 'identity':
        leaf.widget = widgets.Signature(key_name(leaf.item['key']))

    elif leaf.type == 'auction':
        leaf.widget = gtk.HBox(gtk.FALSE, 0)
        leaf.widget.pack_start(gtk.Label(_('Bid: ')), gtk.FALSE, gtk.FALSE, 0)
        entry = gtk.Entry()
        entry.set_text('0')
        leaf.widget.pack_start(entry, gtk.TRUE, gtk.TRUE, 0)


def set_leaf_player(leaf,app):
    if leaf.players is None:
        leaf.players = {}
        if sys.platform == 'win32':
            return
        extension = string.split(leaf.item['filename'], ".")[-1]
        lext = string.lower(extension)
        if lext in ['mp3','ogg']:
            leaf.players['Play'] = app.play_music_now
            leaf.players['Append'] = app.play_music_later
        elif lext in ['jpg','jpeg','gif','png','xpm','bmp']:
            if imageviewer:
                leaf.players['View'] = imageviewer.imageviewer
        elif lext == 'txt':
            leaf.players['View'] = textviewer.Text_Viewer
        elif lext in ['html', 'htm']:
            leaf.players['View'] = textviewer.External_Viewer
        elif lext in ['pdf']:
            leaf.players['View'] = textviewer.External_Viewer        
      


def get_leaf_buttons(leaf,app):

    list = []
    if leaf.sources and leaf.type == 'file':
        set_leaf_player(leaf,app)
        for action in leaf.players.keys():
            list.append((action, lambda b, leaf=leaf,app=app,action=action: play_file(leaf,action,app)))
        if leaf.item.get('local_path'):
            list.append(
                (_("Delete"),lambda _b, leaf=leaf,app=app,item=leaf.item: leaf.delete(app,item)))
        elif leaf.item.get('name'):
            list.append(
                (_("Download"), lambda _b, leaf=leaf,app=app: leaf.download(app)))
        list.append(
            (_("View sources"), lambda _b,leaf=leaf,app=app:
             search_show_sources(leaf.sources, app.node, app)))

    elif leaf.type == 'channel exists':
        if app.chat.channels.list.has_key(leaf.item['name']):
            list.append(
                (_("Unsubscribe"),lambda _b, leaf=leaf,app=app:
                 app.chat.channel_unsub(leaf.item['name'])))
        else:
            list.append(
                (_("Subscribe"),lambda _b, leaf=leaf,app=app:
                 app.chat.channel_sub(leaf.item['name'])))
        list.append(
            (_("List subscribers"), lambda _b,_leaf=leaf, _app=app:
             search_for_people_on_channel(leaf.item['name'],_app.node,_app)))

    elif leaf.type == 'identity':
        if app.name_server.acquaintances.has_key(key_name(leaf.item['key'])):
            str = _("View")
        else:
            str = _("Add to contact list")
        def on_complete(acq,app=app):
            app.edit_acquaintance(acq,app.name_server)
        list.append((str,
                     lambda _b, leaf=leaf,app=app, on_complete=on_complete:
                     app.name_server.make_acquaintance_sync(
            leaf.item,on_complete,app,leaf.address)))
        if leaf.address:
            list.append(
                (_("Browse their files"), lambda _b, leaf=leaf,app=app:
                 search_browse_files(leaf.sources[0], app.node,app)))

    elif leaf.type =='auction':
        list.append((_("View"), lambda _b, leaf=leaf, app=app:
                     app.edit_auction(leaf.item)))

    elif leaf.type == 'daemonic node':
        list.append(
            (_("Browse their files"), lambda _b, leaf=leaf, app=app:
             search_browse_files(leaf.sources[0], app.node,app)))

    elif leaf.type == 'directory':
        if not leaf.item.get('local_path'):
            list.append((_("Download directory"),
                         lambda _b, leaf=leaf, app=app: app.download_directory_dialog(leaf)))

    buttons = []
    for title,action in list:
        button = gtk.Button(title)
        button.connect("clicked",action)
        buttons.append(button)
    return buttons



class Searcher:

    def __init__(self, title, pipe, node, app,
                 notebook = None, keywords=[], anti_keywords=[], mime=None):
        self.title = title
        self.pipe  = pipe
        self.keywords  = keywords
        self.anti_keywords = anti_keywords
        self.mime = mime
        
        self.node  = node
        self.app   = app
        self.current_selection = None
        self.selected_row = 0
        self.buttons = [ ]
        self.running = 0
        self.notebook = notebook

        if mime:
            self.detailed_title = mime+' files matching '+self.title+':'
        else:
            self.detailed_title = self.title

    def start(self):
        self.running = 1
        vbox = gtk.VBox(gtk.FALSE, 5)

        if not self.notebook:
            self.window = gtk.Window(gtk.WINDOW_TOPLEVEL) 
            self.window.set_default_size(400,400)
            self.window.set_title(self.title)
            self.window.connect(
                "destroy", lambda _b, _self=self: _self.stop())
            self.window.add(vbox)            
        else:
            self.notebook.append_page(vbox, gtk.Label(self.title))

        def on_selection_change(new_selection, self=self):
            self.bin.foreach(lambda c, self=self: self.bin.remove(c))

            for item in self.buttons:
                self.hbox.remove(item)
            self.buttons = [ ]

            if not new_selection:
                self.description_label.set_text('')
                self.vbox_2.queue_resize()
                return

            self.current_selection = new_selection
            self.buttons = get_leaf_buttons(new_selection[-1],self.app)
            for item in self.buttons:
                item.set_flags(gtk.CAN_DEFAULT)
                self.hbox.pack_start(item, gtk.TRUE, gtk.TRUE, 0)
            self.hbox.show_all()
            
            if self.buttons:
                self.buttons[0].grab_default()

            self.description_label.set_text(
                new_selection[-1].get_description(self.node.address))

            leaf = new_selection[-1]
            if leaf.widget is None:
                set_leaf_widget(leaf)
            if leaf.widget:
                leaf.widget.show_all()
                self.bin.add(leaf.widget)
                leaf.widget.show()

            self.vbox_2.queue_resize()

        def child_getter(path):
            children = path[-1].get_children()
            if not children:
                return children

            children = children[:]
            children.sort(lambda x,y: cmp(x.get_comparator(),y.get_comparator()))
            return children

        self.root = search.Search_tree_interior(
            lambda self=self: self.pipe, self.keywords, self.anti_keywords,'files',
            self.mime, self.detailed_title,_('couldn\'t find anything, sorry'))

        self.tree_widget = widgets.Tree(
            [self.root],child_getter,lambda x: x.get_text(),on_selection_change)
        
        self.root.on_delete = self.tree_widget.on_delete

        vbox.pack_start(self.tree_widget.packee(), gtk.TRUE, gtk.TRUE, 0)

        self.vbox_2 = gtk.VBox(gtk.FALSE, 5)
        self.vbox_2.set_border_width(10)
        vbox.pack_start(self.vbox_2, gtk.FALSE, gtk.FALSE, 0)
        
        self.description_label = gtk.Label('')
        self.description_label.set_justify(gtk.JUSTIFY_LEFT)
        self.description_label.set_alignment(0,0)
        self.vbox_2.pack_start(self.description_label, gtk.FALSE, gtk.FALSE, 0)

        self.bin = gtk.Alignment(1,1,0.5,1)
        self.vbox_2.pack_start(self.bin, gtk.FALSE, gtk.FALSE, 0)

        # Obscure GTK sizing bug workaround
        self.alignment = gtk.Alignment(0,0,1,1)
        self.vbox_2.pack_end(self.alignment, gtk.FALSE, gtk.FALSE, 0)
        self.hbox = gtk.HBox(gtk.FALSE, 5)
        self.alignment.add(self.hbox)
        
        self.close_button = gtk.Button(_("Close"))
        if not self.notebook:
            self.close_button.connect(
                "clicked",lambda _b, _window=self.window: _window.destroy())
        else:
            self.close_button.connect(
                "clicked",lambda _b, _notebook=self.notebook:
                _notebook.remove_page(_notebook.get_current_page()))

        self.close_button.set_flags(gtk.CAN_DEFAULT)
        self.hbox.pack_end(self.close_button, gtk.TRUE, gtk.TRUE, 0)
        
        if not self.notebook:
            self.app.show_window(self.window, 'search')
        else:
            self.notebook.show_all()    
            self.notebook.set_current_page(-1)

        self.update(250.0)


    def stop(self):
        list = [ self.root ]
        while list:
            children = list[0].get_children()
            if children:
                list.extend(children)
            list[0].stop()
            del list[0]

        self.running = 0
 
    def update(self, last_time):        
        #check.check_is_gtkthread()        
        assert(type(last_time) == types.FloatType)
        if not self.running:
            return
        any = 0
        for item in self.tree_widget.current_path:
            any = item.update(self.app) or any

        if any:
            self.tree_widget.refresh_display()

        new_time = last_time * 5.0 / 4.0
        if new_time > 10000.0:
            new_time = 10000.0

        gtk.timeout_add(int(new_time), self.update, new_time)
        



