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

""" main class of the GUI"""

import os, sys, time, traceback, string, math, types, random, threading
import gtk
from circlelib import __init__, check, error, hash, node, settings, utility
from circlelib import gossip, name_server, channels, auction_server,chat
import download_manager, playlist, node_monitor, searcher, chatgtk


is_jython = (str(types.IntType)[:4] == 'org.')

if is_jython:
    # No signal module.
    exit_signals = ()
else:
    import signal
    if hasattr(signal, 'SIGPWR'):
        exit_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGPWR)
    else:
        exit_signals = (signal.SIGINT, signal.SIGTERM)

if settings.gtk_loaded():
    import gtk
    # Not sure this is the best spot, but lets give it a go:
    try:
        # The aim is to try and display a dialog using gtk 1.2
        # binding - if that works then we alert the user and quit

        dial = gtk.GtkDialog ()
        dial.set_title ("Wrong python-gtk series")
        dial.set_border_width (5)
        dial.set_position(gtk.WIN_POS_CENTER)
        dial.connect ("delete_event", gtk.mainquit)

        quit_button = gtk.GtkButton ("Quit")
        quit_button.connect ("clicked", gtk.mainquit)
        dial.action_area.pack_start (quit_button)
        quit_button.show ()

        quit_label = gtk.GtkLabel("This version of Circle needs the gtk 2.0 bindings,\n on debian python-gtk2, otherwise pygtk-1.99 or later.")
        dial.vbox.pack_start (quit_label)
        quit_label.show ()

        dial.show()
        gtk.mainloop()
        sys.exit()
    except:
        pass
    import widgets



def gui_task(daemon,fork):

    # after importing gtk the terminal encoding needs to be updated    
    settings.terminal_encoding = sys.getdefaultencoding()
    global _gtkthread
    _gtkthread = threading.currentThread()

    try:
        gtk.threads_init()
        daemon.accept_gtk=1
    except:
        daemon.accept_gtk=0
        daemon.gtk_interface_requested=0
        return
    # all calls to gtk must be made from this thread,
    # between threads_enter and threads_leave
    gtk.threads_enter()
    sys.excepthook = utility.report_bug 

    while not daemon.stopping:
        # wait until interface requested
        while not daemon.gtk_interface_requested:
            time.sleep(1)

        daemon.interface_running = 1
        #gtk.gdk.Display(os.environ["DISPLAY"])        
        # reload the roots
        if not daemon.config['keep_sharing']:                                    
            daemon.file_server.set_roots(daemon.config)

        daemon.interface = Circle_gtk(daemon)
        daemon.interface.run_main()
        daemon.interface_running = 0
        daemon.gtk_interface_requested = 0

        if not daemon.config['stay_alive']:
            daemon.stopping = 1
        else:
            if not daemon.config['keep_sharing']:
                daemon.file_server.roots = [ ]
        if not fork:
            daemon.stopping = 1
        
    gtk.threads_leave()




def is_gtkthread():
    """Returns true iff the caller is running in the GTK thread. """    
    return threading.currentThread() is _gtkthread

def check_is_gtkthread():
    if not is_gtkthread():
        raise error.Error("GTK-using function called from another thread.")


class Circle_gtk:

    config_keys = [
        ('name', 'username'),
        ('human-name', 'name'),
        ('description', 'finger')
    ]

    def __init__(self,daemon):
    
        self.config = utility.get_config("configuration", { })
        self.running = 1
        self.daemon = daemon
        self.open_windows = [ ]

        # Try to get a sensible default human name.
        dfl_human_name = ''
        try:
            import posix
            import pwd
            pw = pwd.getpwuid(posix.geteuid())
            if pw:
                gecos = pw[4]
                dfl_human_name = string.split(gecos, ',')[0]
        except:
            pass

        # we have two files for the options:
        # some options belong to the gui, others to the daemon
        
        for pair in [('name', os.environ.get('USER','anon')),
                     ('human-name', dfl_human_name),
                     ('description', ''),
                     ('background_color',(65535,65535,65535)),
                     ('text_color',(0,0,0)),
                     ('links_color',(0,0,65535)),
                     ('people_color',(0,0,65535)),
                     ('files_color',(0,0,65535)),
                     ('active_color',(41120,8224,61680)),
                     ('quiet_color',(26727, 44310, 14828)),
                     ('beep_on_message', 1),
                     ('show_tips', 1),
                     ('show_gossip', 0),
                     ('poll_gossip', 0),
                     ('use_gossip', 0),
                     ('report_bugs', 1),
                     ('file_sharing', 1),
                     ('auctions',1),
                     ('auto_list_channels', 1),
                     ('augmented_text', 0)]:
            if not self.config.has_key(pair[0]):
                self.config[pair[0]] = pair[1]


    def idle_add(self,func,*parameters):
        #do not use gtk.idle_add
        gtk.timeout_add(0,func,*parameters)

    def timeout_add(self,delay,func,*parameters):
        gtk.timeout_add(delay,func,*parameters)

    def show_window(self, window, name, close_on_exit = 1, show_all = 1):
        """ Open a window. Add to list of open windows, so that all windows
                can be closed on exit. """

        pair = (window, close_on_exit)

        if pair not in self.open_windows:
            window.set_wmclass(name,'the_circle')
            self.open_windows.append((window,close_on_exit))
            window.connect("destroy", lambda window, pair=pair: self.open_windows.remove(pair))

        if show_all:
            window.show_all()
        else:
            window.show()

    def close_all_windows(self):
        """
        Close all open windows opened with
        show_window and the close_on_exit option set to true. """

        for pair in self.open_windows[:]:
            if pair[1]:
                pair[0].destroy()



    #def run_gtk(self, proxy_mode='auto', no_connect=0, daemon = None):

        #self.daemon = daemon
        #if no_connect:
        #    proxy_mode = 'never'
        #proxy_host = None
        #proxy_password = None
        #self.open_window()

        #if proxy_mode == 'always' or \
        #       (proxy_mode == 'auto' and node.need_proxy()):
        #    self.continue_running = 0
        #    proxy_host, proxy_password = self.run_login_screen(proxy_mode)
        #else:
        #    self.continue_running = 1

        #while 1:
        #    if not self.continue_running:
        #        break
        #    self.continue_running = 0

        #self.run_main()

        #    if not self.continue_running:
        #        break            
        #    self.continue_running = 0
        #    proxy_host, proxy_password = self.run_login_screen(proxy_mode)

    
    def run_main(self):
        
        check_is_gtkthread()

        self.open_window()
        self.node        = self.daemon.node
        self.cache       = self.daemon.cache
        self.file_server = self.daemon.file_server

        self.chat  = chatgtk.Chat_gtk(self)
        
        self.name_server = name_server.Name_server(self,self.node, lambda : Random_gtk(self.window))
        self.auction_server = auction_server.Auction_server(self,self.node)

        self.gossip   = gossip.Gossip(self)

        
        self.quit_message = None
        check.check_is_af_inet_address(self.node.address)
        # Proof: @E12.
        
        #if not no_connect:
        #    def waiter(the_node):
        #        if not the_node.is_connecting():
        #            utility.threadnice_mainquit()
        #            return gtk.FALSE
        #        return gtk.TRUE
        #    utility.schedule_mainthread(100.0, waiter, self.node)
        #    utility.threadnice_mainloop()

        try:
            self.name_server.set_name(
                self.config['name'],
                self.config['human-name'],
                self.config['description'])
        except error.Error:
            self.show_error(sys.exc_info()[1])

        self.name_server.start(
            lambda str, self=self: self.chat.show('\n'+str+'\n\n'))

        if self.gossip is not None:
            self.gossip.start()

        self.chat.start()              # idem
        utility.chat_obj = self.chat   #for bug reports

        self.start_plug_ins()
        self.create_main_window()

        no_connect = 0

        if not no_connect:

            i=0            
            while not self.node.is_connected():
                time.sleep(0.1)
                i=i+1
                if i>20:
                    break
            
            if not self.node.is_connected():
                self.show_error(error.Error(
                    _("Couldn't find any peers.\n\n"+
                      "You need to specify the location of at least one peer,\n"+
                      "using the \"Network/Connect to peer manually...\" menu item.\n\n"+
                      "If your network connection is currently down,\n"+
                      "use \"Network/Connect to previous peers\" once it's up.")),self.window)


        gtk.mainloop()
        self.node.remove_monitor(self.monitor_func)        
        self.music_manager.stop_music()
        utility.set_config("configuration", self.config)

        self.name_server.stop(self.quit_message)
        utility.chat_obj = None
        self.chat.stop()
        self.stop_plug_ins()

        if self.gossip is not None:
            self.gossip.stop()

        #close windows now
        self.close_all_windows()
        self.window.destroy()
        while gtk.events_pending():
            gtk.mainiteration()


    def run_login_screen(self, proxy_mode):

        # not used anymore: fossil code
        
        hbox = gtk.HBox(gtk.FALSE, 0)

        catbar = self._make_catbar()
        hbox.pack_start(catbar, gtk.FALSE, gtk.FALSE, 0)

        filler = gtk.Alignment(0,0,0,0)
        hbox.pack_start(filler, gtk.FALSE, gtk.FALSE, 25)
        
        vbox = gtk.VBox(gtk.FALSE, 10)
        vbox.set_border_width(10)
        hbox.pack_start(vbox, gtk.TRUE, gtk.TRUE, 0)

        align = gtk.Alignment(1.0,0.0,0,0)
        vbox.pack_start(align, gtk.TRUE, gtk.TRUE, 0)

        text = widgets.Text(400, 0)
        text.write('\n'+random.choice(settings.gratuitous_plugs)+'\n')
        align.add(text)

        if proxy_mode in ['always','auto']:
            #sometimes hidden proxy dialog
            proxy_box = gtk.VBox(gtk.FALSE, 10)
            vbox.pack_start(proxy_box, gtk.FALSE, gtk.FALSE, 0)
            
            if sys.platform == 'win32':
                heading = widgets.Helpful_label(_("username@machine.name to run proxy on:"),
                    _("You appear to be using a masquerading network.\n\n"+\
                    "Circle needs to run a proxy on your firewall in order to work "+\
                    "correctly.\n\n"+\
                    "Enter the username and name of the machine (or PuTTY session name) for your firewall in the box below.\n\n"+\
                    "For detailed instructions, press the \"Help\" button."))
            else:
                heading = widgets.Helpful_label(_("username@machine.name to run proxy on:"),
                    _("You appear to be using a masquerading network.\n\n"+\
                    "Circle needs to run a proxy on your firewall in order to work "+\
                    "correctly. For this you need to have installed ssh and python "+\
                    "on your firewall.\n\n"+
                    "Give the hostname or username@hostname (as in ssh) for your firewall "+\
                    'in the box below then click "log in" to start the proxy.'))
                
            proxy_box.pack_start(heading.packee(), gtk.FALSE, gtk.FALSE, 0)

            entry = gtk.Entry()
            entry.set_text(utility.get_config('proxy',''))
            proxy_box.pack_start(entry, gtk.FALSE, gtk.FALSE, 0)

            if sys.platform == 'win32':
                label = gtk.Label(_('Password:'))
                label.set_alignment(0,0)
                proxy_box.pack_start(label, gtk.FALSE, gtk.FALSE, 0)

                password_entry = gtk.Entry()
                password_entry.set_visibility(0)
                proxy_box.pack_start(password_entry, gtk.FALSE, gtk.FALSE, 0)

            vbox.pack_start(gtk.Label(''), gtk.TRUE, gtk.TRUE, 0)

            # Check for masquerading
            masquerading = [1]

            def on_timeout(masquerading=masquerading,proxy_box=proxy_box):
                need = node.need_proxy()
                if need and not masquerading[0]:
                    masquerading[0] = 1
                    proxy_box.show_all()
                elif not need and masquerading[0]:
                    masquerading[0] = 0
                    proxy_box.hide()

                return gtk.TRUE

            if proxy_mode == 'auto':
                utility.schedule_mainthread(1000.0, on_timeout)
     
        hbox_buttons = gtk.HBox(gtk.FALSE, 0)
        vbox.pack_start(hbox_buttons, gtk.FALSE, gtk.FALSE, 5)

        login_button = gtk.Button(_("Log in"))
        def on_clicked(button, self=self):
            self.continue_running = 1
            utility.threadnice_mainquit()
        login_button.connect("clicked",on_clicked)
        login_button.set_flags(gtk.CAN_DEFAULT)
        hbox_buttons.pack_start(login_button, gtk.TRUE, gtk.TRUE, 5)
        
        button = gtk.Button(_("Exit"))
        button.connect("clicked",utility.threadnice_mainquit)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox_buttons.pack_start(button, gtk.TRUE, gtk.TRUE, 5)

        button = gtk.Button(_("Help"))
        def on_clicked(button, self=self):
            try:
                utility.browse_file("getting_started.html","#Preliminaries")
            except error.Error, err:
                self.show_error(err)
        button.connect("clicked",on_clicked)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox_buttons.pack_start(button, gtk.TRUE, gtk.TRUE, 5)

        self.set_window_child(hbox, 1)

        login_button.grab_default()

        if proxy_mode == 'auto':
            on_timeout()

        gtk.mainloop()

        if proxy_mode in ['always','auto']:
            utility.unschedule_mainthread(on_timeout)
            #timeout_remove(timeout_tag)

            if masquerading[0] and self.continue_running:
                text = string.strip(widgets.get_utext(entry)) 

                if text:
                    utility.set_config('proxy',text)
                    if sys.platform == 'win32':
                        return text, widgets.get_utext(password_entry)
                    else:
                        return text, None
                else:
                    error.Error(_("To operate correctly, Circle needs to start a proxy on your firewall.\n\n"+\
                                "Please give the hostname or address of your firewall.")).show(self.window)
                    return self.run_login_screen(proxy_mode)

        return None, None


    def shutdown(self, message=None, continue_running=0):
        """ This only sets the running flag to 0.
            update will trigger the shutdown in the gtk thread.
            This can be called from any thread.
        """

        check.check_is_opt_text(message)
        self.continue_running = continue_running
        self.quit_message = message
        self.running = 0


    def edit_channel_settings(self, channels, channel):

        self.chat.lock.acquire()
        try:
            window = gtk.Window()
            window.set_border_width(10)
            window.set_title(_('Channel: ')+channel)

            vbox = gtk.VBox(0,5)
            window.add(vbox)

            label = gtk.Label(channel)
            vbox.add(label)

            #label = gtk.Label('(Here should go the subscriber list)')
            label = gtk.Label('')
            vbox.add(label)

            hbox = gtk.HBox(0,5)

            button = gtk.Button(_("Remove from sidebar"))
            def unsub(_b,_ch=channel,_self=self,_w=window):
                _self.chat.channel_unsub(_ch)
                _w.destroy()
            button.connect("clicked",unsub)
            hbox.pack_start(button, 1,1,0)

            button = gtk.Button(_("List subscribers"))
            def list(_b,_ch=channel,_s=channels):
                searcher.search_for_people_on_channel(_ch, _s.node,_s.app)
            button.connect("clicked",list)
            hbox.pack_start(button, 1,1,0)

            button = gtk.Button(_("Cancel"))
            button.connect("clicked",lambda _b,_window=window:_window.destroy())
            hbox.pack_start(button, 1,1,0)

            vbox.pack_start(hbox, 0,0,0)
            
            channels.app.show_window(window, _('channel'))

        finally:
            self.chat.lock.release()




    def refresh_userlist(self):

        def refresh_userlist_task(self):
            import gtk
            import widgets
            widget = gtk.VBox(0,0)

            channels = self.chat.channels.list.keys()
            channels.sort()
            for name in channels:
                try:
                    ch = self.chat.channels.list[name]
                except ValueError:
                    continue
                
                hbox = gtk.HBox(0,0)

                mute = widgets.Toggle_icon('<')
                mute.set_relief(gtk.RELIEF_NONE)
                def on_toggle(mute, name=name,self=self):
                    self.chat.lock.acquire()
                    self.chat.channel_mute(name,not mute.get_active())
                    self.chat.lock.release()
                    self.chat.fterm.view.grab_focus()
                mute.connect("toggled", on_toggle)
                self.chat.lock.acquire()
                mute.set_active(not ch['muted'])
                self.chat.lock.release()
                hbox.pack_start(mute,0,0,0)
                widgets.tooltips.set_tip(mute,_("listen to channel %s")%name,"")
                
                checker = widgets.Toggle_icon('>')
                checker.set_relief(gtk.RELIEF_NONE)
                def on_toggle(checker, name=name,self=self):
                    self.chat.lock.acquire()
                    if checker.get_active():
                        if name not in self.chat.channel:
                            self.chat.channel.append(name)
                            self.chat.channel_mute(name,0)
                    else:
                        if name in self.chat.channel:
                            self.chat.channel.remove(name)
                    self.chat.lock.release()
                    self.chat.fterm.view.grab_focus()
                    self.chat.set_prompt()
                checker.connect("toggled", on_toggle)
                self.chat.lock.acquire()
                checker.set_active(name in self.chat.channel)
                self.chat.lock.release()
                hbox.pack_start(checker,0,0,0)
                widgets.tooltips.set_tip(checker,_("talk on %s")%name,"")

                n = name
                if len(n) > 36:
                    n = name[0:33]+"..."
                
                button = widgets.Text_button(n) 
                button.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("blue"))# set_style(self.blue_style)
                button.set_relief(gtk.RELIEF_NONE)
                def on_click(button, name=name,self=self):
                    self.edit_channel_settings(self.chat.channels,name)
                def on_press(button, ev, name=name,self=self):
                    if ev.button == 3:
                        menu = chatgtk.channel_context_menu(self.chat,self.chat.channels,name)
                        menuwidget = gtk.Menu()
                        for (text, action) in menu:
                            mi = gtk.MenuItem(text)
                            mi.connect("activate", action)
                            mi.show()
                            menuwidget.append(mi)
                        menuwidget.popup(None,None,None,ev.button,ev.time)

                button.connect("clicked",on_click)
                button.connect("button-press-event",on_press)
                hbox.pack_start(button,1,1,0)
                widgets.tooltips.set_tip(button,_("view %s settings")%name)

                widget.pack_start(hbox,0,0,0)
 
            self.name_server.lock.acquire()
            try:
                list = [ ]
                for item in self.name_server.nicknames.items():
                    if item[1] is not self.name_server.me:
                        if item[1].watch:
                            dist = item[1].distance
                            if dist == None: dist = 100.0
                        else:
                            dist = 101.0
                        if item[1].online:
                            top_sorter = 0
                        else:
                            top_sorter = 1
                        list.append(((top_sorter,dist),item[0],item[1]))
                list.sort()
            finally:
                self.name_server.lock.release()

            for item in list:
                item[2].lock.acquire()
                try:
                    name    = item[2].nickname
                    online  = item[2].online
                    status  = item[2].status.get('chat',(1,''))
                finally:
                    item[2].lock.release()

                addendum = ''
                if status[0] and status[1]:
                    addendum = '\n('+name+' '+status[1]+')'
                elif not status[0] and status[1]:
                    addendum = '\n('+name+_(' is quiet: ')+status[1]+')'
                
                hbox = gtk.HBox(0,0)
 
                checker = widgets.Toggle_icon('>', 3)
                checker.set_relief(gtk.RELIEF_NONE)
                def on_toggle(checker, name=name,self=self):
                    self.chat.lock.acquire()
                    if checker.get_active():
                        if name not in self.chat.channel:
                            self.chat.channel.append(name)
                    else:
                        if name in self.chat.channel:
                            self.chat.channel.remove(name)
                    self.chat.lock.release()
                    self.chat.fterm.view.grab_focus()
                    self.chat.set_prompt()
                checker.connect("toggled", on_toggle)
                self.chat.lock.acquire()
                checker.set_active(name in self.chat.channel)
                self.chat.lock.release()
                hbox.pack_start(checker,0,0,0)
                widgets.tooltips.set_tip(checker,_("talk to ")+name+addendum,"")
                    
                button = widgets.Text_button(name) 
                button.set_relief(gtk.RELIEF_NONE)
                def on_click(button, name=name,self=self):
                    self.name_server.lock.acquire()
                    try:
                        if self.name_server.nicknames.has_key(name):
                            self.edit_acquaintance(
                                self.name_server.nicknames[name],self.name_server)
                    finally:
                        self.name_server.lock.release()

                def on_press(button, ev, self=self, name=name):
                    if ev.button==1:
                        on_click(button,name,self)
                        return
                    
                    menu = chatgtk.name_context_menu(self.chat,name)
                    menuwidget = gtk.Menu()
                    for (text, action) in menu:
                        mi = gtk.MenuItem(text)
                        mi.connect("activate", action)
                        mi.show()
                        menuwidget.append(mi)
                    menuwidget.popup(None,None,None,ev.button,ev.time)
                    
                button.connect("clicked",on_click)
                button.connect("button-press-event",on_press)
                hbox.pack_start(button,1,1,0)
                widgets.tooltips.set_tip(button,_("view %s's details")%name+addendum)
                
                if online:
                    if status[0]:
                        #button.set_style(self.blue_style)
                        button.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("blue"))
                    else:
                        #button.set_style(self.green_style)
                        button.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("chartreuse4"))
                    
                widget.pack_start(hbox,0,0,0)
             
            widget.show_all()
            for child in self.userlist_viewport.get_children():
                self.userlist_viewport.remove(child)
            self.userlist_viewport.add(widget)

        #gtk.idle_add(refresh_userlist_task, self)
        gtk.timeout_add(0,refresh_userlist_task,self)



    def config_dialog(self, _b):

        window = gtk.Window()
        window.set_transient_for(self.window)        
        window.set_title(_("Configuration"))

        window.set_border_width(10)
        window.set_resizable(gtk.FALSE)

        vbox = gtk.VBox(gtk.FALSE, 10)
        window.add(vbox)

        notebook = gtk.Notebook()
        vbox.pack_start(notebook, gtk.TRUE, gtk.TRUE, 0)

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label(_('Identity')))

        label = widgets.Helpful_label(_('Username:'),\
            _('A short distinctive name that people can refer to you '+\
            'by. For example your initials or the name of your favourite '+\
            'movie character.\n\n'+\
            'Examples: pfh, jsmith, sonic'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        name_entry = gtk.Entry()
        name_entry.set_text(self.config['name'])
        page_vbox.pack_start(name_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(_('Real name:'),\
            _('Your actual real life name.\n\n' +\
            'Example: John Smith'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        human_name_entry = gtk.Entry()
        human_name_entry.set_text(self.config['human-name'])
        page_vbox.pack_start(human_name_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(_('About yourself:'),\
            _('Some information about yourself, such as who you are, '+\
            'what you do. Also maybe the URL of your homepage.\n\n' +\
            'Example: I am a chicken wrangler in the outer mongolian highlands. '+\
            'I like Buffy. Visit my homepage at http://wranglers.mo/~bongle/'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        description_entry = gtk.TextView()
        buffer = description_entry.get_buffer()
        buffer.insert(buffer.get_end_iter(), self.config['description'])
        description_entry.set_editable(gtk.TRUE)
        description_entry.set_wrap_mode(gtk.WRAP_WORD)
        description_entry.set_size_request(300,100)

        # thomasV: the following lines seem to cause random crashes (bug #3681)
        # could be a gtk bug. crash occurs on logout, with the following message:
        # (circle:28327): Gtk-CRITICAL **: file gtktexttag.c : line 1932 (gtk_text_attributes_ref): assertion `values != NULL' failed
        
        # I comment them out until somebody figures out why:        
        #scrolly = gtk.ScrolledWindow()
        #scrolly.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        #scrolly.set_size_request(300,100)
        #scrolly.add(description_entry)        
        #page_vbox.pack_start(scrolly, gtk.FALSE, gtk.FALSE, 0)

        # Let us use this instead:
        page_vbox.pack_start(description_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(_('Signature:'),\
            _('This is a graphical representation of your public key. '+\
            'People can use it to check that you are really you and not an imposter '+\
            'when they search for you.\n\n'+\
            'If you, say, put this on your web-page, people will be able to confirm that '+\
            'they are talking to the person who made that web-page on circle.\n\n'+\
            'Click on the picture to generate a postscript version for printing or putting on teeshirts (Linux and BSD only).\n\n' +\
            'Note: you would only bother doing this if you are a security nut.'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        signature = widgets.Signature(self.name_server.public_key_name)
        # Proof of @R43: @I22.  (Assumes that self.name_server instanceof
        # Name_server.)

        #tag: latest addition
        page_vbox.pack_start(signature, gtk.FALSE, gtk.FALSE, 0)

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Directories'))

        label = widgets.Helpful_label(
            _('Public directory:'),\
            _('A directory containing files you want to share with everybody. '+\
              'Specify the directory relative to your home directory.'+\
              'If you want to make several directories public, separate them by commas.'+\
              'The first item of this list will be used to store downloaded files\n\n'+\
              'Example: public_dir, /mnt/hd2/mp3'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        public_entry = widgets.File_entry(self,\
            _('Public directory'),
            _('Please select your public directory.'),
            self.daemon.config['public_dir'],1,self.window)
        page_vbox.pack_start(public_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(
            _('Download directory:'),\
            _('The directory that is used to store downloaded files. '+\
              'Specify the directory relative to your home directory.'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        download_entry = widgets.File_entry(self,\
            _('Download directory'),
            _('Please select your download directory.'),
            self.daemon.config['download_dir'],1,self.window)
        page_vbox.pack_start(download_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(\
            _('Private directory :'),\
            _('A directory containing files you want to share only with people you trust.' +\
              'Specify the directory relative to your home directory.'+\
              'This directory can be a subdirectory of your public directory.\n\n'+\
              'Examples: shared/private, /mnt/hd2/mp3/private_music'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        private_entry = widgets.File_entry(self,\
            _('Private directory'),
            _('Please select your private directory.'),
            self.daemon.config['private_dir'],1,self.window)
        page_vbox.pack_start(private_entry, gtk.FALSE, gtk.FALSE, 0)

        if sys.platform == 'win32' or \
             not os.path.isdir('/var/cache/apt/archives'):
            publish_apt_cache_checkbox = None
        else:
            publish_apt_cache_checkbox = gtk.CheckButton(_('Make apt cache public'))
            publish_apt_cache_checkbox.set_active(self.daemon.config['publish_apt'])
            enclosure = widgets.Helpful_label(publish_apt_cache_checkbox,\
                _('Make /var/cache/apt/archives public.\n\n'+\
                    'This will let people use your cached Debian packages, if they use '+\
                    'the Circle apt methods, reducing the load on official Debian servers.'))
            page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        #
        # active services
        #
        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        #do not append this page for 0.40
        #notebook.append_page(page_vbox, gtk.Label('Services'))
        
        file_sharing_checkbox = gtk.CheckButton(_('Enable file sharing'))
        file_sharing_checkbox.set_active(self.config['file_sharing'])
        enclosure = widgets.Helpful_label(file_sharing_checkbox,_(''))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        auctions_checkbox = gtk.CheckButton(_('Enable auctions'))
        auctions_checkbox.set_active(self.config['auctions'])
        enclosure = widgets.Helpful_label(auctions_checkbox,_(''))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        use_gossip_checkbox = gtk.CheckButton(_('Enable gossip'))
        use_gossip_checkbox.set_active(self.config['use_gossip'])
        enclosure = widgets.Helpful_label(use_gossip_checkbox,_('note: uses a lot of bandwidth'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        #
        # options
        #
        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Options'))
        
        tips_checkbox = gtk.CheckButton(_('Show tip on startup'))
        tips_checkbox.set_active(self.config['show_tips'])
        enclosure = widgets.Helpful_label(tips_checkbox,_('If this checkbox '\
             +'is checked a random tip will be displayed on startup.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        
        gossip_checkbox = gtk.CheckButton(_('Fetch gossip on startup'))
        gossip_checkbox.set_active(self.config['show_gossip'])
        enclosure = widgets.Helpful_label(gossip_checkbox,_('If this checkbox '\
             +'is checked new gossips will be fetched on startup.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        
        poll_gossip_checkbox = gtk.CheckButton(_('Fetch gossip every hour'))
        poll_gossip_checkbox.set_active(self.config['poll_gossip'])
        enclosure = widgets.Helpful_label(
            poll_gossip_checkbox,
            _('If this checkbox is checked new gossips will be fetched every hour. '
              +'Do not select this option if you want to save traffic. '
              +'For this option to take effect, you need to restart your Circle client.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        beep_on_message_checkbox = gtk.CheckButton(_('Enable that annoying beep on message arrival'))
        beep_on_message_checkbox.set_active(self.config['beep_on_message'])
        enclosure = widgets.Helpful_label(beep_on_message_checkbox,\
                                         _('If this checkbox is clicked circle will make a beep noise when ever a new message arrives, and you aren\'t quiet.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        
        auto_list_channels = gtk.CheckButton(_('Automatically subscribe to channels'))
        auto_list_channels.set_active(self.config['auto_list_channels'])
        enclosure = widgets.Helpful_label(auto_list_channels,\
            _('If this checkbox is checked and someone sends a message in multiple channels, at least one of which you\'re listening to, then Circle will automatically subscribe you to all the recipient channels.  This gives you the ability to easily listen and talk to these channels without having to find the channel first.  With this checkbox unchecked, this behavior will not happen, thus keeping your channel list free of potentially useless channel listings.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        

        augmented_text_checkbox = gtk.CheckButton(_('Color text based on typing intensity'))
        augmented_text_checkbox.set_active(self.config['augmented_text'])
        enclosure = widgets.Helpful_label(augmented_text_checkbox,\
            _('If this checkbox is checked the heaviness with which you '\
              +'type chat messages will determine the color of the text.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        
        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Daemon'))
        
        stay_alive_checkbox = gtk.CheckButton(_('Keep running the daemon after I logout'))
        stay_alive_checkbox.set_active(self.daemon.config['stay_alive'])
        enclosure = widgets.Helpful_label(
            stay_alive_checkbox,
            _('If this checkbox is checked, circle '\
              +'will keep running after you log off, as a daemon. This '\
              +'helps maintain the circle network and does not use much bandwidth.'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        
        keep_sharing_checkbox = gtk.CheckButton(_('Keep sharing my files after I logout'))
        keep_sharing_checkbox.set_active(self.daemon.config['keep_sharing'])
        enclosure = widgets.Helpful_label(
            keep_sharing_checkbox,_(
            'If this checkbox is checked your daemon will keep publishing '\
            +'the files in your public directory after you log off. Do not '\
            +'activate this option if you want to save your bandwidth'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)        

        daemon_http_checkbox = gtk.CheckButton(_('HTTP server'))
        daemon_http_checkbox.set_active(self.daemon.config['http'])
        enclosure = widgets.Helpful_label(
            daemon_http_checkbox,_(
            'If this checkbox is checked your daemon will accept http requests '\
            +'on port 29621. Check http://localhost:29621/ in your browser'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)        

        bug_report_checkbox = gtk.CheckButton(_('bug reports'))
        bug_report_checkbox.set_active(self.config['report_bugs'])
        enclosure = widgets.Helpful_label(
            bug_report_checkbox,_(
            'If this checkbox is checked your circle client will post bug '\
            +'reports to channel #traceback if a traceback occurs while you are online'))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)        

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Colors'))        

        def change_color_dialog(self,drawing_area):
            color=drawing_area.get_style().base[0]
            dialog = gtk.ColorSelectionDialog("Changing color")
            colorsel = dialog.colorsel
            colorsel.set_previous_color(color)
            colorsel.set_current_color(color)
            colorsel.set_has_palette(gtk.TRUE) 
            response = dialog.run()            
            if response == gtk.RESPONSE_OK:
                color = colorsel.get_current_color()
                drawing_area.modify_bg(gtk.STATE_NORMAL, color)
                drawing_area.modify_base(gtk.STATE_NORMAL, color)
            dialog.destroy()

        def on_expose(widget,event):
            gtk.gdk.Drawable.draw_rectangle(widget.window, widget.get_style().base_gc[0],1, \
                                            event.area[0],event.area[1],event.area[2],event.area[3])
            
        table = gtk.Table(8,2,gtk.FALSE)
        table.set_row_spacings(15)
        table.set_col_spacings(30)
        page_vbox.add(table)
        i=0
        
        label = gtk.Label(_('Background :'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)    
        da_bg_color = gtk.DrawingArea()
        da_bg_color.set_size_request(40, 20)
        da_bg_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['background_color']
        col = da_bg_color.get_colormap().alloc_color(r,g,b)
        da_bg_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_bg_color)
        def on_click_background(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_bg_color)
                return gtk.TRUE
            return gtk.FALSE        
        da_bg_color.connect("event", on_click_background)
        da_bg_color.connect("expose_event",on_expose)
        i=i+1

        label = gtk.Label(_('Text :'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_text_color = gtk.DrawingArea()
        da_text_color.set_size_request(40, 20)
        da_text_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['text_color']
        col = da_text_color.get_colormap().alloc_color(r,g,b)
        da_text_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_text_color)
        def on_click_text(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_text_color)
                return gtk.TRUE
            return gtk.FALSE        
        da_text_color.connect("event", on_click_text)
        da_text_color.connect("expose_event",on_expose)
        i=i+1
       
        label = gtk.Label(_('Links :'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_links_color = gtk.DrawingArea()
        da_links_color.set_size_request(40, 20)
        da_links_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['links_color']
        col = da_links_color.get_colormap().alloc_color(r,g,b)
        da_links_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_links_color)
        def on_click_links(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_links_color)
                return gtk.TRUE
            return gtk.FALSE
        da_links_color.connect("event", on_click_links)
        da_links_color.connect("expose_event",on_expose)
        i=i+1
       
        label = gtk.Label(_('People :'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_people_color = gtk.DrawingArea()
        da_people_color.set_size_request(40, 20)
        da_people_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['people_color']
        col = da_people_color.get_colormap().alloc_color(r,g,b)
        da_people_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_people_color)
        def on_click_people(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_people_color)
                return gtk.TRUE
            return gtk.FALSE
        da_people_color.connect("event", on_click_people)
        da_people_color.connect("expose_event",on_expose)
        i=i+1       

        label = gtk.Label(_('Quiet prompt:'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_quiet_color = gtk.DrawingArea()
        da_quiet_color.set_size_request(40, 20)
        da_quiet_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['quiet_color']
        col = da_quiet_color.get_colormap().alloc_color(r,g,b)
        da_quiet_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_quiet_color)
        def on_click_quiet(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_quiet_color)
                return gtk.TRUE
            return gtk.FALSE
        da_quiet_color.connect("event", on_click_quiet)
        da_quiet_color.connect("expose_event",on_expose)
        i=i+1
        
        label = gtk.Label(_('Files :'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_files_color = gtk.DrawingArea()
        da_files_color.set_size_request(40, 20)
        da_files_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['files_color']
        col = da_files_color.get_colormap().alloc_color(r,g,b)
        da_files_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_files_color)
        def on_click_files(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_files_color)
                return gtk.TRUE
            return gtk.FALSE
        da_files_color.connect("event", on_click_files)
        da_files_color.connect("expose_event",on_expose)
        i=i+1

        label = gtk.Label(_('Active text:'))
        table.attach(label,0,1,i,i+1,0,0)
        frame = gtk.Frame()
        table.attach(frame,1,2,i,i+1,0,0)
        da_local_files_color = gtk.DrawingArea()
        da_local_files_color.set_size_request(40, 20)
        da_local_files_color.set_events(gtk.gdk.BUTTON_PRESS_MASK)
        (r, g, b) = self.config['active_color']
        col = da_local_files_color.get_colormap().alloc_color(r,g,b)
        da_local_files_color.modify_base(gtk.STATE_NORMAL, col)
        frame.add(da_local_files_color)
        def on_click_local_files(w,e,_self=self):
            if e.type==gtk.gdk.BUTTON_PRESS:
                change_color_dialog(_self,da_local_files_color)
                return gtk.TRUE
            return gtk.FALSE
        da_local_files_color.connect("event", on_click_local_files)
        da_local_files_color.connect("expose_event",on_expose)
        i=i+1

        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        button = gtk.Button(_("Cancel"))
        button.connect("clicked",lambda _b, _window=window: _window.destroy())
        
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)
        
        button = gtk.Button(_("Commit changes"))
        
        def ok_button(_b, _self=self,_window=window):

            _self.config['name']        = string.strip(widgets.get_utext(name_entry))
            _self.config['human-name']  = string.strip(widgets.get_utext(human_name_entry))

            buffer = description_entry.get_buffer()
            _self.config['description'] = string.strip(widgets.get_uslice(buffer.get_start_iter(),buffer.get_end_iter()))

            _self.daemon.config['public_dir'] = string.strip(utility.force_string(public_entry.get_text()))
            if _self.daemon.config['public_dir']:
                if _self.daemon.config['public_dir'][:2] == '~/':
                    _self.daemon.config['public_dir'] = _self.daemon.config['public_dir'][2:]

            _self.daemon.config['download_dir'] = utility.force_string(download_entry.get_text())
            if _self.daemon.config['download_dir']:
                if _self.daemon.config['download_dir'][:2] == '~/':
                    _self.daemon.config['download_dir'] = _self.daemon.config['download_dir'][2:]

            _self.daemon.config['private_dir'] = utility.force_string(private_entry.get_text())
            if _self.daemon.config['private_dir']:
                if _self.daemon.config['private_dir'][:2] == '~/':
                    _self.daemon.config['private_dir'] = _self.daemon.config['private_dir'][2:]

            if publish_apt_cache_checkbox:
                _self.daemon.config['publish_apt'] = publish_apt_cache_checkbox.get_active()

            _self.config['beep_on_message']     = beep_on_message_checkbox.get_active()
            _self.config['show_tips']           = tips_checkbox.get_active()
            _self.config['show_gossip']         = gossip_checkbox.get_active()
            _self.config['poll_gossip']         = poll_gossip_checkbox.get_active()
            _self.config['auto_list_channels']  = auto_list_channels.get_active()            
            _self.config['augmented_text']      = augmented_text_checkbox.get_active()
            _self.config['report_bugs']         = bug_report_checkbox.get_active()
            _self.daemon.config['http']         = daemon_http_checkbox.get_active()
            _self.daemon.set_http()
            _self.daemon.config['stay_alive']   = stay_alive_checkbox.get_active()
            _self.daemon.config['keep_sharing'] = keep_sharing_checkbox.get_active()
         
            c = da_text_color.get_style().base[0]
            _self.config['text_color']   = (c.red,c.green,c.blue)
            c = da_bg_color.get_style().base[0]
            _self.config['background_color'] = (c.red,c.green,c.blue)
            c = da_people_color.get_style().base[0]
            _self.config['people_color'] = (c.red,c.green,c.blue)
            c = da_files_color.get_style().base[0]
            _self.config['files_color'] = (c.red,c.green,c.blue)
            c = da_links_color.get_style().base[0]
            _self.config['links_color'] = (c.red,c.green,c.blue)
            c = da_quiet_color.get_style().base[0]
            _self.config['quiet_color'] = (c.red,c.green,c.blue)
            c = da_local_files_color.get_style().base[0]
            _self.config['active_color'] = (c.red,c.green,c.blue)
            
            _self.file_server.set_roots(self.daemon.config)
            _self.chat.fterm.apply_colors()
            
            utility.set_config("configuration", _self.config)
            utility.set_config("daemon", _self.daemon.config)
    
            try:
                _self.name_server.set_name(
                    _self.config['name'],
                    _self.config['human-name'],
                    _self.config['description'])
            except error.Error:
                _self.show_error(sys.exc_info()[1])
                
            _self.sync_config()
            _window.destroy()
            
        button.connect("clicked",ok_button) 
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'Configure')
        button.grab_default()


        
    def sell_dialog(self):
        
        window = gtk.Window()
        window.set_transient_for(self.window)        
        window.set_title(_("Sell item"))

        window.set_border_width(10)
        window.set_resizable(gtk.FALSE)
        vbox = gtk.VBox(gtk.FALSE, 10)
        window.add(vbox)

        notebook = gtk.Notebook()
        vbox.pack_start(notebook, gtk.TRUE, gtk.TRUE, 0)

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label(_('Description')))

        label = widgets.Helpful_label(_('Category'),\
            _('Category of item to sell'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)        
        category_entry = gtk.Entry()
        page_vbox.pack_start(category_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(_('Title'),\
            _('title of auction (256 char)'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        
        title_entry = gtk.Entry()
        page_vbox.pack_start(title_entry, gtk.FALSE, gtk.FALSE, 0)


        label = widgets.Helpful_label(_('Description:'),\
            _('Detailed description of the item you want to sell. Try to be as precise as posible'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        description_entry = gtk.TextView()
        buffer = description_entry.get_buffer()
        description_entry.set_editable(gtk.TRUE)
        description_entry.set_wrap_mode(gtk.WRAP_WORD)
        description_entry.set_size_request(300,100)

        #same bug as above...
        #scrolly = gtk.ScrolledWindow()
        #scrolly.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
        #scrolly.set_size_request(300,100)
        #scrolly.add(description_entry)        
        #page_vbox.pack_start(scrolly, gtk.FALSE, gtk.FALSE, 0)

        # Let us use this instead:
        page_vbox.pack_start(description_entry, gtk.FALSE, gtk.FALSE, 0)

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Pictures'))

        label = widgets.Helpful_label(
            _('Main picture:'),\
            _('A png file'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        public_entry = widgets.File_entry(self,\
            _('Public directory'),
            _('Please select your public directory.'),
            self.daemon.config['public_dir'],1,window)
        page_vbox.pack_start(public_entry, gtk.FALSE, gtk.FALSE, 0)

        label = widgets.Helpful_label(
            _('Additional views of the object'),\
            _('Additional views of the object.'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        page_vbox = gtk.VBox(gtk.FALSE, 10)
        page_vbox.set_border_width(10)
        notebook.append_page(page_vbox, gtk.Label('Options'))

        label = widgets.Helpful_label(_('Initial price'),\
            _('title of auction (256 bytes)'))
        page_vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        
        price_entry = gtk.Entry()
        page_vbox.pack_start(price_entry, gtk.FALSE, gtk.FALSE, 0)
        
        type_checkbox = gtk.CheckButton(_('private auction'))
        enclosure = widgets.Helpful_label(type_checkbox,_('blah '))
        page_vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)
        
        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)
        button = gtk.Button(_("Cancel"))
        button.connect("clicked",lambda _b, _window=window: _window.destroy())
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)
        button = gtk.Button(_("Submit"))

        def ok_button(_b, _self=self,_window=window):

            title    = string.strip(widgets.get_utext(title_entry))
            category = string.strip(widgets.get_utext(category_entry))
           
            buffer = description_entry.get_buffer()
            description = string.strip(widgets.get_uslice(buffer.get_start_iter(),buffer.get_end_iter()))
            type = type_checkbox.get_active()

            try:
                _self.auction_server.publish_auction(
                    title,category,description,0)
            except error.Error:
                _self.show_error(sys.exc_info()[1])

            _window.destroy()

            
        button.connect("clicked",ok_button) 
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'auction')
        button.grab_default()
        

    def open_window(self):
        
        self.window_pos = utility.get_config("window",None)
        if not self.window_pos:
            self.window_pos = (700,500,1,1,1)

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        #self.window.set_wmclass('main','the_circle')
        self.window.set_default_size(self.window_pos[0],self.window_pos[1])
        self.set_title()
    
        self.show_window(self.window,'main',0)
        self.window_shown = 1

    def set_title(self, title = None):
        if not title:
            title = _("The Circle ")+__init__.__version__
        self.window.set_title(title)

    def set_window_child(self, child, allow_close):
        child.show_all()
        
        for old_child in self.window.get_children():
            self.window.remove(old_child)

        self.current_window_child = child
        self.window.add(child)
        
        if not self.window_shown:
            self.show_window(self.window,'main',0)
            self.window_shown = 1

    def _make_catbar(self):
        vbox = gtk.VBox(gtk.FALSE, 0)

        drawing = gtk.DrawingArea()
        vbox.pack_start(drawing, gtk.TRUE, gtk.TRUE, 0)
        def expose(widget,event):
            gtk.gdk.Drawable.draw_rectangle(
                widget.window, widget.get_style().black_gc,1,
                event.area[0],event.area[1],event.area[2],event.area[3])
        drawing.connect("expose_event",expose)

        try:
            pixmap = gtk.Image()
            pixmap.set_from_file(utility.find_file("neko.xpm"))
            vbox.pack_start(pixmap, gtk.FALSE, gtk.FALSE, 0)
        except error.Error:
            pass

        return vbox
 
    def become_message_window(self, message):
        # not used anymore
        
        hbox = gtk.HBox(gtk.FALSE, 0)

        catbar = self._make_catbar()
        hbox.pack_start(catbar, gtk.FALSE, gtk.FALSE, 0)
        
        vbox_inner = gtk.VBox(gtk.FALSE, 0)
        hbox.pack_start(vbox_inner, gtk.TRUE, gtk.TRUE, 10)

        align = gtk.Alignment(0.5,0.5,0,0)
        vbox_inner.pack_start(align, gtk.TRUE, gtk.TRUE, 0)

        text = widgets.Text(400, 0)
        text.write('\n'+message+'\n')
        align.add(text.addee())

        progress = gtk.ProgressBar()
        vbox_inner.pack_start(progress, gtk.FALSE, gtk.FALSE, 10)

        self.set_window_child(hbox, 0)

        progress.hide()

        def set_text(message, text=text):
            text.clear()
            text.write('\n'+message+'\n')
            #text.queue_draw() # probably superfluous

        def set_progress(amount, progress=progress):
            progress.set_fraction(amount)
            progress.show()

        #return lambda message, label=label: label.set_text(message)
        return (set_text, set_progress)

    def add_menu_item(self,menu_name,name,action,*args):
        """Add a menu item to a menu. If the menu does not exist it will
             also be created.

             If the menu item has an equivalen chat command, add that command
             to the name preceded by a colon, eg 'Log out:/logout'
        
             Action will be called with the menu item object, followed by
             *args """

        if not self.menus.has_key(menu_name):
            menu = gtk.Menu()
            menu_item = gtk.MenuItem(menu_name)
            menu_item.set_submenu(menu)
            self.menu_bar.insert(menu_item,len(self.menus)-1) # Don't add after Help menu
            menu_item.show_all()
            self.menus[menu_name] = menu

        name_parts = string.split(name,':')

        if len(name_parts) == 1:
            menu_item = gtk.MenuItem(name)
        else:
            menu_item = gtk.MenuItem()

            hbox = gtk.HBox(gtk.FALSE, 20)
            menu_item.add(hbox)

            hbox.pack_start(gtk.Label(name_parts[0]), gtk.FALSE, gtk.FALSE, 0)
            hbox.pack_end(gtk.Label(name_parts[1]), gtk.FALSE, gtk.FALSE, 0)
        
        apply(menu_item.connect,("activate",action)+args)
        menu_item.show()
        self.menus[menu_name].append(menu_item)

        return menu_item

    def add_menu_separator(self,menu_name):
        """Add a separator to a menu."""
        menu_item = gtk.MenuItem()
        menu_item.show()
        self.menus[menu_name].append(menu_item)
        
    def update(self):
        """this should run in the gtk thread"""
        check_is_gtkthread()

        #update the widgets
        self.drawing.hashtable_running = self.node.hashtable_running
        self.drawing.my_angle = hash.float_hash(self.node.name)*2.0*math.pi
        self.drawing.others_angle = map(
            lambda p: hash.float_hash(p.name)*2.0*math.pi,
            self.node.peers.values())
        self.drawing.queue_draw()

        self.published_label.set_text(_(' %d files published ')% len(self.file_server.paths))
        self.connect_label.set_text(
            _('Running on port %d\nConnected to %d peers')
            % (self.node.address[1],len(self.node.peers)))

        self.music_manager.update()
        self.download_manager.update()
        
        #check if we are still running
        if not self.running:
            allocation = self.window.get_allocation()
            utility.set_config(
                "window",(allocation[2],allocation[3],
                          self.menu_bar.flags() & gtk.VISIBLE,
                          self.userlist_bin.flags() & gtk.VISIBLE,
                          self.notebook.get_property('show-tabs')))
            gtk.mainquit()

        
        return self.running



    def create_main_window(self):

        main_vbox = gtk.VBox(gtk.FALSE, 5)


        #
        # notebook
        #
        self.notebook = notebook = gtk.Notebook()
        self.notebook.set_property('homogeneous',1)
        main_vbox.pack_start(notebook, gtk.TRUE, gtk.TRUE, 0)
       
        #
        # Network section
        #
        network_hbox = gtk.HBox(gtk.FALSE, 5)
        notebook.append_page(network_hbox, gtk.Label(_('Network')))

        left_vbox = gtk.VBox(gtk.FALSE, 5)
        network_hbox.pack_start(left_vbox, gtk.FALSE, gtk.FALSE, 0)

        self.connect_label = gtk.Label('')
        self.connect_label.set_alignment(0.5,0)
        left_vbox.pack_start(self.connect_label, gtk.FALSE,gtk.FALSE,5)

        button = gtk.Button()
        button.connect("clicked",self.menu_browse_peers)
        button.set_relief(gtk.RELIEF_NONE)
        left_vbox.pack_start(button, gtk.FALSE, gtk.FALSE, 0)
        widgets.tooltips.set_tip(button,_("Browse current peers"),"")
        self.drawing = widgets.Network_topology()
        button.add(self.drawing)

        padding = gtk.Label('')
        left_vbox.pack_start(padding, gtk.FALSE, gtk.FALSE, 5)

        #button = gtk.Button(_("Browse current peers"))
        #button.connect("clicked",self.menu_browse_peers)
        #left_vbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)

        button = gtk.Button(_("Connect to peer manually"))
        button.connect("clicked",self.greet_dialog)
        button.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)

        button = gtk.Button(_("Connect to previous peers"))
        button.connect("clicked", lambda x: self.node.greet_known_peers())
        button.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)

        button = gtk.Button(_("Exit"))
        button.connect("clicked", self.menu_exit)
        button.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_end(button, gtk.FALSE, gtk.TRUE, 0)

        button = gtk.Button(_("Configure..."))
        button.connect("clicked", self.config_dialog)
        button.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_end(button, gtk.FALSE, gtk.TRUE, 0)

        #button.grab_default()
        
        padding = gtk.Label('')
        network_hbox.pack_start(padding, gtk.FALSE, gtk.FALSE, 5)
        
        monitor_vbox = gtk.VBox(gtk.FALSE, 5)
        network_hbox.pack_start(monitor_vbox, gtk.FALSE, gtk.FALSE, 0)
        self.monitor_func = node_monitor.monitor_node(self.node,self.file_server,self,monitor_vbox)
        self.node.add_monitor(self.monitor_func)

        #
        # Chat section
        #
        self.chat_tab = gtk.VBox(gtk.FALSE, 0)
        self.chat_tab_label =  gtk.Label(_('Chat'))
        notebook.append_page(self.chat_tab, self.chat_tab_label)

        # menubar
        self.menu_bar = menu_bar = gtk.MenuBar()
        self.chat_tab.pack_start(menu_bar, gtk.FALSE, gtk.FALSE, 0)
        
        menu = gtk.Menu()
        menu_item = gtk.MenuItem(_('Help'))
        menu_item.set_submenu(menu)
        menu_bar.append(menu_item)

        self.menus = { _('Help'): menu }

        self.add_menu_item(_('Circle'),_('Configure'),self.config_dialog)
        self.add_menu_item(_('Circle'),_('Log out')+':/exit',self.menu_exit)

        self.add_menu_item(_('Commands'),_('Clear window')+':ctrl-L',
                           lambda m,self=self: self.chat.do('/clear'))
        self.add_menu_item(_('Commands'),_('Toggle quiet')+':/quiet',
                           lambda m,self=self: self.chat.do('/quiet'))
        self.add_menu_item(_('Commands'),_('Read unread messages')+':/read',
                           lambda m,self=self: self.chat.do('/read'))        
        self.add_menu_item(_('Commands'),_('Repeat last messages')+':/repeat',
                           lambda m,self=self: self.chat.do('/repeat 10'))
        self.add_menu_separator(_('Commands'))
        self.add_menu_item(_('Commands'),_('Tip')+':/tip',lambda m,self=self: self.chat.do('/tip'))
        self.add_menu_item(_('Commands'),_('Help on commands')+':/help',self.menu_chat_commands)
        self.add_menu_separator(_('Commands'))

        self.add_menu_item(_('Channels'),_('Browse people'),self.menu_browse_all)
        self.add_menu_item(_('Channels'),_('Browse channels'),self.menu_browse_channels)
        self.add_menu_item(_('Channels'),_('Create new channel...'),self.menu_create_channel)

        self.add_menu_item(_('Help'),_('Getting started'),self.menu_getting_started)
        self.add_menu_item(_('Help'),_('Running Circle as a daemon'),self.menu_daemon_howto)
        self.add_menu_item(_('Help'),_('Frequently Asked Questions'),self.menu_faq)
        self.add_menu_separator(_('Help'))
        self.add_menu_item(_('Help'),_('Submit a bug report'),self.menu_bug_report)
        self.add_menu_item(_('Help'),_('Developer documentation'),self.menu_pydoc)
        self.add_menu_separator(_('Help'))
        self.add_menu_item(_('Help'),_('Homepage'),self.menu_homepage)
        self.add_menu_item(_('Help'),_('About'),self.menu_about)
        #end menu


        self.top_hbox = top_hbox = gtk.HBox(gtk.FALSE, 0)
        self.chat_tab.pack_start(top_hbox, gtk.FALSE, gtk.FALSE, 0)

        vbox = gtk.VBox(gtk.FALSE, 5)
        top_hbox.pack_start(vbox, gtk.TRUE, gtk.TRUE, 0)


        #self.info_label = gtk.Label('')
        #self.info_label.set_alignment(0,0)
        #vbox.pack_end(self.info_label, gtk.FALSE, gtk.FALSE, 0)

        #info_hbox = gtk.HBox(gtk.FALSE, 5)
        #vbox.pack_end(info_hbox, gtk.FALSE, gtk.FALSE, 0)

        #self.info_files_button = gtk.Button()
        #self.info_files_button.set_relief(gtk.RELIEF_NONE)
        #self.info_files_button.connect('clicked',lambda b, self=self: searcher.search_browse_files(self.node.address, self.node,self))
        #info_hbox.pack_start(self.info_files_button, gtk.FALSE, gtk.FALSE, 0)
        #self.info_files_label = gtk.Label('')
        #self.info_files_button.add(self.info_files_label)
        #self.info_net_label = gtk.Label('')
        #info_hbox.pack_start(self.info_net_label, gtk.FALSE, gtk.FALSE, 0)



        hbox = gtk.HBox(gtk.FALSE, 0)
        self.chat_tab.pack_start(hbox, gtk.TRUE, gtk.TRUE, 0)

        hbox.pack_start(self.chat.fterm.widget, gtk.TRUE, gtk.TRUE, 0)

        vbox = gtk.VBox(gtk.FALSE, 0)
        hbox.pack_start(vbox, gtk.FALSE, gtk.FALSE, 0)

        button1 = gtk.Button()
        button1.set_relief(gtk.RELIEF_NONE)
        vbox.pack_start(button1, gtk.FALSE, gtk.FALSE, 0)
        arrow1 = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_IN);
        button1.add(arrow1)
        widgets.tooltips.set_tip(button1,_("show/hide tabs"),"")

        button3 = gtk.Button()
        button3.set_relief(gtk.RELIEF_NONE)
        vbox.pack_start(button3, gtk.FALSE, gtk.FALSE, 0)
        arrow3 = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_IN);
        button3.add(arrow3)
        widgets.tooltips.set_tip(button3,_("show/hide menu"),"")        
        
        button2 = gtk.Button()
        button2.set_relief(gtk.RELIEF_NONE)
        vbox.pack_start(button2, gtk.FALSE, gtk.FALSE, 0)
        arrow2 = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_IN);
        button2.add(arrow2)
        widgets.tooltips.set_tip(button2,_("show/hide people"),"")

        scroll_bar = gtk.VScrollbar(self.chat.fterm.widget.get_vadjustment())
        vbox.pack_start(scroll_bar, gtk.TRUE, gtk.TRUE, 0)

        self.userlist_widget = gtk.ScrolledWindow()
        self.userlist_widget.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        self.userlist_viewport = gtk.Viewport()
        self.userlist_widget.add(self.userlist_viewport)
        
        self.userlist_bin = userlist_bin = gtk.Alignment(0,0,1,1) # gtk.Bin broken
        userlist_bin.add(self.userlist_widget)
        hbox.pack_start(userlist_bin, gtk.FALSE, gtk.FALSE, 0)

        def arrow1_click(button, arrow1=arrow1, notebook=notebook):
            if notebook.get_property('show-tabs'):
                notebook.set_show_tabs(0)
                notebook.set_current_page(1)
                arrow1.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
            else:
                notebook.set_show_tabs(1)
                arrow1.set(gtk.ARROW_UP, gtk.SHADOW_IN)
        button1.connect("clicked",arrow1_click)

        def arrow3_click(button, arrow3=arrow3, menu_bar=menu_bar, top_hbox=top_hbox):
            if menu_bar.flags() & gtk.VISIBLE:
                menu_bar.hide()
                top_hbox.hide()
                arrow3.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
            else:
                menu_bar.show()
                top_hbox.show()
                arrow3.set(gtk.ARROW_UP, gtk.SHADOW_IN)
        button3.connect("clicked",arrow3_click)

        def arrow2_click(button, arrow2=arrow2,userlist_bin=userlist_bin):
            if userlist_bin.flags() & gtk.VISIBLE:
                userlist_bin.hide()
                arrow2.set(gtk.ARROW_LEFT, gtk.SHADOW_IN)
            else:
                userlist_bin.show()
                arrow2.set(gtk.ARROW_RIGHT, gtk.SHADOW_IN)
        button2.connect("clicked",arrow2_click)
        

        def on_delete(_w, _e, self=self):
            """method destroy of window is called in self.update()"""
            if self.running:
                self.shutdown()
            return gtk.TRUE #don't close now        
        self.window.connect("delete_event",on_delete)

        #
        # Files section
        #
        files_vbox = gtk.VBox(gtk.FALSE, 5)
        notebook.append_page(files_vbox, gtk.Label(_('Files')))
        
        first_hbox = gtk.HBox(gtk.FALSE, 0)
        files_vbox.pack_start(first_hbox, gtk.FALSE, gtk.FALSE, 0)

        local_button = gtk.Button(_("Browse my files"))
        first_hbox.pack_start(local_button, gtk.FALSE, gtk.FALSE, 5)        
        local_button.connect("clicked", lambda m,self=self: searcher.search_browse_files(
            self.node.address, self.node,self,search_notebook))

        self.published_label = gtk.Label('')
        first_hbox.pack_start(self.published_label, gtk.FALSE,gtk.FALSE,0)

        search_hbox = gtk.HBox(gtk.FALSE, 0)
        files_vbox.pack_start(search_hbox, gtk.FALSE, gtk.FALSE, 0)
       
        search_hbox.pack_start(gtk.Label(_('Search for files: ')), gtk.FALSE, gtk.FALSE, 5)
        search_entry = gtk.Entry()
        search_entry.set_size_request(200,20)

        search_hbox.pack_start(search_entry,gtk.FALSE)

        #button = gtk.Button(_(" Find person "))
        #button.connect("clicked", self.search, 1)
        #search_hbox.pack_start(button, gtk.FALSE, gtk.FALSE, 0)
        search_button = gtk.Button(_("Search "))
        search_hbox.pack_start(search_button, gtk.FALSE, gtk.FALSE, 5)

        switch_button = gtk.Button(_("Options"))
        search_hbox.pack_start(switch_button, gtk.FALSE, gtk.FALSE, 5)

        options_hbox = gtk.HBox(gtk.FALSE, 0)
        files_vbox.pack_start(options_hbox, gtk.FALSE, gtk.FALSE, 0)
        options_hbox.pack_start(gtk.Label(_('Search options: ')), gtk.FALSE, gtk.FALSE, 5)

        def select_option(w,data,_self=self):
            _self.search_type=data
            
        button = gtk.RadioButton(None, "text    ")
        button.connect("toggled", select_option,"text")
        button.set_active(gtk.FALSE)
        options_hbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)
        button.show()

        button = gtk.RadioButton(button, "audio    ")
        button.connect("toggled", select_option, "audio")
        button.set_active(gtk.FALSE)
        options_hbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)
        button.show()

        button = gtk.RadioButton(button, "video    ")
        button.connect("toggled", select_option, "video")
        options_hbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)
        button.set_active(gtk.FALSE)
        button.show()

        button = gtk.RadioButton(button, "images    ")
        button.connect("toggled", select_option, "image")
        button.set_active(gtk.FALSE)
        options_hbox.pack_start(button, gtk.FALSE, gtk.TRUE, 0)
        button.show()

        any_button = gtk.RadioButton(button, "any   ")
        any_button.connect("toggled", select_option, '')
        any_button.set_active(gtk.TRUE)
        options_hbox.pack_start(any_button, gtk.FALSE, gtk.TRUE, 0)
        any_button.show()

        search_notebook = gtk.Notebook()
        files_vbox.pack_start(search_notebook, gtk.TRUE, gtk.TRUE, 0)

        def mysearch(_b,entry=search_entry,_self=self,_search_notebook=search_notebook):
            
            try:
                mime= _self.search_type
                text = widgets.get_utext(entry)
                text = string.strip(text)
                searcher.search_for_files(text,_self.node,_self,_search_notebook,mime)
                entry.set_text('')
            except error.Error, err:
                _self.show_error(err,_self.window)

        def entry_enter(_e, event, _self=self):
            if event.keyval == 65293: # enter keyval
                mysearch(_e)
                search_notebook.grab_focus()
        search_entry.connect("key-press-event",entry_enter)
        search_button.connect("clicked", mysearch)

        def switch(_e):
            if self.options_visible:
                self.options_visible = 0
                self.options_hbox.hide()
                any_button.set_active(gtk.TRUE)
                self.search_type=''
            else:
                self.options_visible = 1
                self.options_hbox.show()
               
        switch_button.connect("clicked", switch)

        
        #
        # Downloads
        #        
        downloads_vbox = gtk.VBox(gtk.FALSE, 5)
        notebook.append_page(downloads_vbox, gtk.Label(_('Downloads')))
        self.download_manager = download_manager.Download_manager(self,downloads_vbox)


        #
        # Playlist
        #
        playlist_vbox = gtk.VBox(gtk.FALSE, 5)
        notebook.append_page(playlist_vbox, gtk.Label(_('Playlist')))
        self.music_manager = playlist.Music_manager(self,playlist_vbox)

        
        #
        # Gossip
        #
        gossip_hbox = gtk.HBox(gtk.FALSE, 5)
        notebook.append_page(gossip_hbox, gtk.Label(_('Gossip')))

        gossip_hbox.pack_start(gtk.Label(''), gtk.FALSE, gtk.FALSE, 5)

        left_vbox = gtk.VBox(gtk.FALSE, 5)
        gossip_hbox.pack_start(left_vbox, gtk.FALSE, gtk.FALSE, 0)
        
        left_vbox.pack_start(gtk.Label(''), gtk.FALSE, gtk.FALSE, 5)
        button1 = gtk.Button(_("Fetch gossip"))
        button1.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_start(button1, gtk.FALSE, gtk.TRUE, 0)
        
        button2 = gtk.Button(_("Post gossip..."))
        button2.connect("clicked",lambda m,self=self: self.prompt_for_wodge())
        button2.set_flags(gtk.CAN_DEFAULT)
        left_vbox.pack_start(button2, gtk.FALSE, gtk.TRUE, 0)
        
        gossip_hbox.pack_start(gtk.Label(''), gtk.FALSE, gtk.FALSE, 5)
         
        gossip_vbox = gtk.VBox(gtk.FALSE, 0)
        gossip_hbox.pack_start(gossip_vbox, gtk.TRUE, gtk.TRUE, 0)
        
        self.gossip_scrolly = gtk.ScrolledWindow()
        self.gossip_scrolly.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        
        gossip_vbox.pack_start(self.gossip_scrolly, gtk.TRUE, gtk.TRUE, 0)
        def on_key(widget, event, adj=self.gossip_scrolly.get_vadjustment()):
            if event.keyval == 65362: # Up
                adj.set_value(adj.value - adj.step_increment)
            elif event.keyval == 65364: # Down
                adj.set_value(adj.value + adj.step_increment)
            elif event.keyval == 65365: # Page Up
                adj.set_value(adj.value - adj.page_increment)
            elif event.keyval == 65366 or event.keyval == ord(' '): # Page Down
                adj.set_value(adj.value + adj.page_increment)
            else:
                return 1
            
        self.gossip_scrolly.connect("key-press-event",on_key)
        
        
        def fetch_gossip(_self=self,scrolly=self.gossip_scrolly):
            
            scrolly_children = scrolly.get_children()
            if scrolly_children:
                scrolly.remove(scrolly_children[0])
            message = gtk.Label(_('Fetching gossip...'))
            scrolly.add_with_viewport(message)
            message.show()            
            self.gossip.request_update(
                lambda: self.construct_gossip_list(scrolly,None,None,None))
        
        button1.connect("clicked",fetch_gossip)
        self.construct_gossip_list(self.gossip_scrolly,None,None,None)
        
        
        #
        # Auctions
        #
        auctions_vbox = gtk.VBox(gtk.FALSE, 5)
        #notebook.append_page(auctions_vbox, gtk.Label(_('Auctions')))

        # menubar for auctions
        auctions_menu_bar = gtk.MenuBar()
        auctions_vbox.pack_start(auctions_menu_bar, gtk.FALSE, gtk.FALSE, 0)
        
        menu = gtk.Menu()
        menu_item = gtk.MenuItem(_('Help'))
        menu_item.set_submenu(menu)
        auctions_menu_bar.append(menu_item)

        #self.menus = { _('Help'): menu }
        #self.add_menu_item(_('Buy'),_('Observed items'),self.config_dialog)
        #self.add_menu_item(_('Buy'),_('I am bidding'),self.menu_exit)
        #self.add_menu_item(_('Sell'),_('Sell item'),lambda m,self=self: self.sell_dialog())
        #self.add_menu_item(_('Sell'),_('List of items'),self.menu_chat_commands)
        #self.add_menu_item(_('Help'),_('Getting started'),self.menu_getting_started)
        #end menu
        
        search_hbox = gtk.HBox(gtk.FALSE, 0)
        auctions_vbox.pack_start(search_hbox, gtk.FALSE, gtk.FALSE, 0)
       
        search_hbox.pack_start(gtk.Label(_('Search for: ')), gtk.FALSE, gtk.FALSE, 5)
        auction_entry = gtk.Entry()
        auction_entry.set_size_request(200,20)
        search_hbox.pack_start(auction_entry,gtk.FALSE)
        
        search_button = gtk.Button(_("Go!"))
        search_hbox.pack_start(search_button, gtk.FALSE, gtk.FALSE, 5)

        auction_notebook = gtk.Notebook()
        auctions_vbox.pack_start(auction_notebook, gtk.TRUE, gtk.TRUE, 0)

        def auction_search(_b,_auction_entry=auction_entry,_self=self,_search_notebook=auction_notebook):
            import search
            try:
                text = widgets.get_utext(_auction_entry)
                text = string.strip(text)
                searcher.search_for_auctions(text,_self.node,_self,_search_notebook)
                _auction_entry.set_text('')
            except error.Error, err:
                _self.show_error(err,_self.window)

        def auction_entry_enter(_e, event, _self=self):
            if event.keyval == 65293: # enter keyval
                auction_search(_e)
        auction_entry.connect("key-press-event",auction_entry_enter)
        search_button.connect("clicked", auction_search)

        #
        # end notebook
        #


        self.set_window_child(main_vbox,1)

        if not self.window_pos[2]:
            arrow3_click(button3)

        if len(self.window_pos)>4:
            if not self.window_pos[4]:
                arrow1_click(button1)
            
        if not self.window_pos[3]:
            arrow2_click(button2)

        self.chat.fterm.view.grab_focus()
        self.options_visible = 0
        self.options_hbox = options_hbox
        self.options_hbox.hide()
        self.timeout_add(200, self.update)


    def menu_browse_peers(self, _b=None):
        list = [ ]
        self.node.lock.acquire()
        for peer in self.node.peers.values():
            list.append(peer.address)
        self.node.lock.release()
        searcher.search_show_sources(list, self.node,self, _('Current peers'))

    def menu_browse_all(self, _b=None):
        try:
            searcher.search_for_all_people(self.node,self)
        except error.Error:
            self.show_error(sys.exc_info()[1])

    def menu_create_channel(self, _b=None):
        window = gtk.Window()
        window.set_border_width(10)        
        window.set_default_size(300,10)
        window.set_title(_('Create a channel'))

        window.set_transient_for(self.window)
        window.set_resizable(gtk.FALSE)

        vbox = gtk.VBox(gtk.FALSE, 5)
        window.add(vbox)

        label = widgets.Helpful_label(_('Name of channel to create:     '),\
            _("This should be the name of the channel you wish to create, "+\
            "for example #circle-devel or #trek"))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
       
        entry = gtk.Entry()
        vbox.pack_start(entry, gtk.FALSE, gtk.FALSE, 0)

        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        button = gtk.Button(_("Cancel"))
        button.connect("clicked",\
            lambda _b, _window=window: _window.destroy())
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        def create(_b, _entry=entry, _window=window, _self=self):
            try:
                chnl=widgets.get_utext(_entry)
                if not chnl:
                    return
                if chnl[0]!='#':
                    chnl='#'+chnl;
                self.chat.channel_sub(chnl)
                _window.destroy()
            except error.Error:
                _self.show_error(sys.exc_info()[1])
        
        button = gtk.Button(_("Create"))
        button.connect("clicked",create)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'create channel')

        button.grab_default()
        
    def menu_browse_channels(self, _b=None):
        try:
            searcher.search_for_all_channels(self.node,self)
        except error.Error:
            _self.show_error(sys.exc_info()[1])
 

        
    def menu_exit(self, _b=None):
        self.shutdown()

    def menu_getting_started(self, _b=None):
        try:
            utility.browse_file('html/getting_started.html')
        except error.Error, err:
            self.show_error(err)
    
    def menu_chat_commands(self, _b=None):
        self.chat.show_xml_file("ixml/help.xml")

    def menu_daemon_howto(self, _b=None):
        try:
            utility.browse_file('html/daemon_howto.html')
        except error.Error, err:
            self.show_error(err)

    def menu_faq(self, _b=None):
        try:
            utility.browse_file('html/technical_faq.html')
        except error.Error, err:
            self.show_error(err)

    def menu_homepage(self, _b=None):
        try:
            utility.browse_url('html/http://thecircle.org.au/')
        except error.Error, err:
            self.show_error(err)
    
    def menu_pydoc(self, _b=None):
        try:
            utility.browse_modules()
        except error.Error, err:
            self.show_error(err)

    def menu_about(self, _b=None):
        try:
            utility.browse_file('html/about.html')
        except error.Error, err:
            self.show_error(err)
            
    def menu_bug_report(self, _b=None):
        try:
            utility.browse_url('http://savannah.nongnu.org/bugs/?group=circle')
        except error.Error, err:
            self.show_error(err)

    def search(self, _b, mode):
        try:
            text = widgets.get_utext(self.search_entry)
            text = string.strip(text)

            #maybe_name = circle_urls.text_to_name_if_md5sum(text)
            #if maybe_name != None:
            #  searcher.search_for_name(maybe_name, _('Files with specified md5sum:'), self.node, self)
            #if text[:12] == 'circle-file:':
            
            try:
                searcher.search_for_name(hash.url_to_hash(text),_('Files matching url'), self.node,self)
            except error.Error:
                if mode == 1:
                    if text == '':
                        self.menu_browse_all()
                    else:
                        searcher.search_for_people(text, self.node,self)
                else:
                    searcher.search_for_files(text, self.node,self)

            self.search_entry.set_text('')
        except error.Error, err:
            self.show_error(err)

    def start_plug_ins(self):
        plug_in_dir = os.path.join(utility.config_dir,'plug-ins')
        if not os.path.isdir(plug_in_dir):
            os.mkdir(plug_in_dir)
        
        names = os.listdir(plug_in_dir)
        self.plug_ins = [ ]
        for name in names:
            if name[-3:] == '.py':
                realname = os.path.join(plug_in_dir,name)

                module = { 'app' : self, 'node' : self.node, 'sys': sys};
                import circlelib;
                module['sys'].path.append(os.path.abspath(os.path.dirname(circlelib.__file__)));
                execfile(realname,module)

                if module.has_key('start'):
                    module['start']()
                self.plug_ins.append(module)
    
    def stop_plug_ins(self):
        for plug_in in self.plug_ins:
            if plug_in.has_key('stop'):
                plug_in['stop']()


    def sync_config(self):
        name = self.config['name']
        name = string.lower(name)
        name = string.replace(name, " ","")
        name = string.replace(name, "-","")
        self.config['name'] = name
    
        self.name_server.set_name(
            self.config['name'],
            self.config['human-name'],
            self.config['description'])

        utility.set_config("configuration", self.config)


    def play_music_now(self,info,downloader=None,field=None):
        try:
            self.music_manager.append_song(info,1,downloader,field)
        except error.Error,err:
            self.show_error(err)

    def play_music_later(self,info,downloader=None,field=None):
        try:
            self.music_manager.append_song(info,0,downloader,field)
        except error.Error,err:
            self.show_error(err)

    def show_error(self, error, window=None, action=None):  
        """ Open a GTK window to display the message. """

        mywindow = gtk.Window()
        if window:
            mywindow.set_transient_for(window)
        mywindow.set_title('Problem')
        mywindow.set_border_width(10)

        vbox = gtk.VBox(0, 0)
        mywindow.add(vbox)

        align = gtk.Alignment(0,0,0,0)
        vbox.pack_start(align, 0,0,0)

        label = gtk.Label(error.message + '\n\n')
        label.set_justify(gtk.JUSTIFY_LEFT)
        align.add(label)

        button = gtk.Button("Close")
        button.connect("clicked",lambda _b,_window=mywindow: _window.destroy())
        vbox.pack_end(button, 0,0,0)

        if action:
            mywindow.connect("destroy",action)
        
        self.show_window(mywindow, 'problem')
        #mywindow.show()


    def greet_dialog(self,_b):

        window = gtk.Window()
        window.set_border_width(10)        
        window.set_default_size(60,10)
        window.set_title('Connect manually')

        window.set_transient_for(self.window)
        window.set_resizable(gtk.FALSE)

        vbox = gtk.VBox(gtk.FALSE, 5)
        window.add(vbox)

        label = widgets.Helpful_label(_('Address of peer to connect to:'),\
            _("If all has gone well, you will not need to use this dialog box at "+\
            "all. You should see a number of arcs in the circle diagram. This "+\
            "indicates that you are connected to the network. If not, you need "+\
            "to give the address of a peer to connect to. Circle will then ask it about "+\
            "other peers and thus connect to the network.\n\n"+\
            "Give the location of the peer you wish to connect to. This can be either "+\
            "a hostname or an IP address. It can be optionally followed by a "+\
            "colon and a port number.\n\n"+
            "Examples: 130.194.67.43, hawthorn.csse.monash.edu.au, "+\
            " hawthorn.csse.monash.edu.au:29610"))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        
        entry = gtk.Entry()
        vbox.pack_start(entry, gtk.FALSE, gtk.FALSE, 0)

        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        def greet(_b, _entry=entry, _self=self, _window=window):
            
            check.check_assertion(hasattr(_self.node, 'address'))  #=@R39  fixme callers
            
            try:
                address = utility.parse_address(_self.node.address, widgets.get_utext(_entry))
                # Proof of @R19: 
                # fixme: Prove that _self.node.address won't be written to
                # while parse_address is being run.  Also prove @R19.
                # Proof that is_af_inet_address(address): @E9.
                self.node.probe(address)
                _window.destroy()
            except error.Error:
                _self.show_error(sys.exc_info()[1])
        
        button = gtk.Button(_("Connect"))
        button.connect("clicked",greet)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'greet')


    def dialog_install_file(self, title, text, help_text, option, sem):

        window = gtk.Window()
        window.set_border_width(10)        
        window.set_default_size(300,10)
        window.set_title(title)

        window.set_transient_for(self.window)
        window.set_resizable(gtk.FALSE)

        vbox = gtk.VBox(gtk.FALSE, 5)
        window.add(vbox)

        label = widgets.Helpful_label(text, help_text)
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        def on_cancel(_b, _window=window,sem=sem,app=self):
            app.config[option]=0
            sem.release()
            _window.destroy()

        def on_ok(_b, _window=window,sem=sem):
            sem.release()
            _window.destroy()

        button = gtk.Button(_("Cancel"))
        button.connect("clicked",on_cancel)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)
        
        button = gtk.Button(_("Install"))
        button.connect("clicked",on_ok)
        button.set_flags(gtk.CAN_DEFAULT)
        hbox.pack_end(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'Install file')
        button.grab_default()


    def download_directory_dialog(self,root):

        window = gtk.Window()
        window.set_border_width(10)        
        window.set_default_size(60,10)
        window.set_title('Download directory')
        window.set_transient_for(self.window)
        window.set_resizable(gtk.FALSE)
        vbox = gtk.VBox(gtk.FALSE, 5)
        window.add(vbox)

        checkbox = gtk.CheckButton(_('Download subdirectories'))
        checkbox.set_active(0)
        enclosure = widgets.Helpful_label(checkbox,_('use with care'))
        vbox.pack_start(enclosure.packee(), gtk.FALSE, gtk.FALSE, 10)

        label = widgets.Helpful_label(
            _('Destination:'),\
            _('Where to download this directory'))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
 
        entry = widgets.File_entry(self,\
            _('Destination'),
            _('Select a directory where to download.'),
            self.daemon.config['public_dir'],1,self.window)
        vbox.pack_start(entry, gtk.FALSE, gtk.FALSE, 0)

        hbox = gtk.HBox(gtk.FALSE, 5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        def download(_b, _entry=entry, _checkbox = checkbox,_self=self, _window=window):
            try:
                dest_dir = widgets.get_utext(_entry)
                subdirs = _checkbox.get_active()
                root.download(self,dest_dir,subdirs)
                _window.destroy()
            except error.Error:
                _self.show_error(sys.exc_info()[1])
        
        button = gtk.Button(_("Download"))
        button.connect("clicked",download)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)
        button.set_flags(gtk.CAN_DEFAULT)

        button2 = gtk.Button(_("Cancel"))
        button2.connect("clicked",lambda x: window.destroy())
        hbox.pack_start(button2, gtk.TRUE, gtk.TRUE, 0)
        
        self.show_window(window, 'Download directory')



    #
    # name_server stuff: acquaintances
    #

    def edit_acquaintance(self, acq, ns):
        acq.lock.acquire()
        try:
            if acq.editor_open:
                return

            window = gtk.Window()
            window.set_border_width(10)
            window.set_resizable(gtk.FALSE)
            window.set_title(_('Acquaintance: %s')%acq.nickname)
            def on_destroy(_w, _acq=acq):
                _acq.editor_open = 0
            window.connect("destroy",on_destroy)

            vbox = gtk.VBox(gtk.FALSE, 5)
            window.add(vbox)

            text = widgets.Text(400)
            str = _('Name: ') + acq.info.get('human-name','') + \
                        '\n' +_('Username: ') + acq.info['name'] + \
                        '\n\n' + acq.info.get('description','') + '\n'
            text.write(str, self)

            if acq.info.has_key('timezone'):
                text.write(time.strftime(
                    _('\nTheir current time is %I:%M %p'),
                    time.gmtime(time.time()-acq.info['timezone'])))

            if acq.online:
                if acq.connect_time is not None:
                    up_minutes = int((time.time()-acq.connect_time)/60.0)
                    text.write(_('\nOnline for %d:%02d') % (int(up_minutes/60),up_minutes%60))
                def action(address=acq.address,app=acq.name_server.app,node=acq.name_server.node):
                    searcher.search_browse_files(address,node,app)
                def curr_addr_task(acq, text=text,action=action,address=acq.address):
                    name = utility.hostname_of_ip(address[0])
                    self.idle_add(text.write, _('\nCurrent address: '))
                    self.idle_add(text.write, name + ':' + `address[1]`,
                                 acq.name_server.app, action)
                utility.Task(curr_addr_task, acq).start()
            elif acq.watched:
                text.write(_('\nCurrently offline.'))
            else:
                text.write(_('\nCurrent status unknown.'))
                
            vbox.pack_start(text.packee(), gtk.FALSE, gtk.FALSE, 0)
            
            al = gtk.Alignment(1,1,0,0)
            vbox.pack_start(al, gtk.FALSE, gtk.FALSE, 0)
            signature = widgets.Signature(acq.name)
            # Proof of @R43: @I21.
            al.add(signature)

            label = widgets.Helpful_label(_('Nickname:'),
            _('This field is initially set to the nickname choosen by "%s" '+\
            'once it is set, however, it remains the same so that you have '+\
            'have a familiar frame of reference to talk to.\n"%s" currently '+
            'uses the nickname "%s".\n')
                 % (acq.nickname, acq.nickname, acq.info['name']))
            vbox.pack_start(label, gtk.FALSE, gtk.FALSE, 0)

            nick = gtk.Entry()
            nick.set_text(acq.nickname)
            vbox.pack_start(nick, gtk.FALSE, gtk.FALSE, 0)

            if ns.app.file_server.private_directory!='':
                drm = gtk.CheckButton(_("Allow this person to download files from my private directory"))
                drm.set_active(acq.drm)
                vbox.pack_start(drm, gtk.FALSE, gtk.FALSE, 0)
            else:
                drm=None

            distance = gtk.CheckButton(_("Trust this person's gossip as:"))
            distance.set_active(acq.distance != None)
            vbox.pack_start(distance, gtk.FALSE, gtk.FALSE, 0)

            if acq.distance == None:
                initial_value = 1.0
            else:
                initial_value = acq.distance
            distance_adj = gtk.Adjustment(initial_value,
                                          lower=0,
                                          upper=20.5,
                                          step_incr=0.5,
                                          page_incr=0.5,
                                          page_size=0.5)

            distance_scale = gtk.HScale(distance_adj)
            vbox.pack_start(distance_scale, gtk.FALSE, gtk.FALSE, 0)

            distance_label = gtk.Label('')
            vbox.pack_start(distance_label, gtk.FALSE, gtk.FALSE, 0)

            def value_changed(adjustment, label=distance_label):
                adjustment.set_value(int(adjustment.value*2+0.5)/2.0)
                label.set_text('')
                for item in settings.distance_descriptions:
                    if adjustment.value >= item[0]:
                        label.set_text(item[1])
                #label.set_active(gtk.TRUE)

            distance_adj.connect("value_changed",value_changed)
            value_changed(distance_adj)

            if acq.distance != None:
                alignment = gtk.Alignment(1,0,0,0)
                vbox.pack_start(alignment, gtk.FALSE, gtk.FALSE, 0)

                hbox_gossip = gtk.HBox(gtk.FALSE, 5)
                alignment.add(hbox_gossip)

                gossip_1 = gtk.Button(_(" View postings "))
                gossip_1.connect("clicked",lambda button,acq=acq,
                                 ns=ns: ns.app.show_gossip(sender=acq,update=1))
                hbox_gossip.pack_start(gossip_1, gtk.FALSE, gtk.FALSE, 0)
                gossip_2 = gtk.Button(_(" View their perspective "))
                gossip_2.connect("clicked",lambda button, acq=acq,
                                 ns=ns: ns.app.show_gossip(perspective=acq,update=1))
                hbox_gossip.pack_start(gossip_2, gtk.FALSE, gtk.FALSE, 0)

                gossip_3 = gtk.Button(_(" Browse their files "))
                def action(button, address=acq.address,
                           app=acq.name_server.app,
                           node=acq.name_server.node):
                    searcher.search_browse_files(address,node,app)

                gossip_3.connect("clicked",action)
                
                hbox_gossip.pack_start(gossip_3, gtk.FALSE, gtk.FALSE, 0)

                def distance_changed(ignore=None, ns=ns,distance=distance,
                                     gossip_1=gossip_1,gossip_2=gossip_2):
                    active = distance.get_active()
                    for btn in (gossip_1, gossip_2):
                        btn.set_sensitive(active and (ns.app.gossip is not None))
                distance.connect("toggled",distance_changed)
                distance_changed()
            
            vbox.pack_start(gtk.HSeparator(), gtk.FALSE, gtk.FALSE, 0)

            watch = gtk.CheckButton(_('Watch what this person is doing'))
            watch.set_active(acq.watch)
            vbox.pack_start(watch, gtk.FALSE, gtk.FALSE, 0)
            remember = gtk.CheckButton(_('Remember this person between sessions'))
            remember.set_active(acq.remember)
            vbox.pack_start(remember, gtk.FALSE, gtk.FALSE, 0)

            hbox = gtk.HBox(gtk.FALSE, 5)
            vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

            button = gtk.Button(_("OK"))
            def on_ok(_b, _acq=acq,_ns=ns,_nick=nick,_window=window,
                      _watch=watch,_remember=remember,_distance=distance,
                      _distance_adj=distance_adj, _drm=drm):
                try:
                    _ns.change_nickname(_acq,widgets.get_utext(_nick))
                except error.Error, err:
                    self.show_error(err)
                    return
                _acq.lock.acquire()
                try:
                    _acq.watch    = _watch.get_active()
                    _acq.remember = _remember.get_active()

                    if _drm:
                        _acq.drm = _drm.get_active()
                        if _acq.online:
                            if _drm.get_active():
                                ns.app.node.trusted_addresses.append(_acq.address)
                            else:
                                while _acq.address in ns.app.node.trusted_addresses:
                                    ns.app.node.trusted_addresses.remove(_acq.address)
                            

                    if _distance.get_active():
                        _acq.distance = _distance_adj.value
                    else:
                        _acq.distance = None
                        
                finally: 
                    _acq.lock.release()

                if _watch.get_active():
                    _acq.start_watching(_ns.node)

                _window.destroy()

                # Just in case we crash before stopping
                _ns.save()

                _ns.acquaintance_status_changed(_acq, 'edit')

            button.connect("clicked",on_ok)
            hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)
            
            button = gtk.Button(_("Cancel"))
            button.connect("clicked",lambda _b,_window=window:_window.destroy())
            hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)
            
            def on_changed(_w, _remember=remember):
                _remember.set_active(gtk.TRUE)
            nick.connect("changed",on_changed)
            distance.connect("toggled",lambda widget, on_changed=on_changed :
                             widget.get_active() and on_changed(widget))
            distance_adj.connect("value_changed",on_changed)

            self.show_window(window, 'acquaintance')
            acq.editor_open = 1
        finally:
            acq.lock.release()


    #
    # auction stuff: bid dialog
    #

    def edit_auction(self, auction):

        window = gtk.Window()
        window.set_border_width(10)
        window.set_resizable(gtk.FALSE)
        window.set_title(_('Auction: %s')%auction.get('title'))
        vbox = gtk.VBox(gtk.FALSE, 5)
        window.add(vbox)

        text = widgets.Text(400)
        str = _('Title: ') + auction.get('title')+ '\n'\
              +_('Description:') + auction.get('description')+ '\n'
            
        text.write(str, self)
        vbox.pack_start(text,gtk.TRUE,gtk.TRUE)
        self.show_window(window, 'Auction')



    #####################################################################
    #
    #   gossip related  stuff
    #

    def prompt_for_wodge(self,in_reply_to=None):
        # Reverse order in this dialog to match gossip window
        
        window = gtk.Window()
        window.set_default_size(500,500)
        window.set_border_width(10)
        window.set_title(_('Post gossip'))
 
        vbox = gtk.VBox(gtk.FALSE,5)
        window.add(vbox)

        label = widgets.Helpful_label(_('Topics discussed:'),\
            _('Topics that your post relates too, separated by commas. '+\
            'You should supply several general topics, plus one specifically '+\
            'relating to your post.\n\n'+\
            'For example, if your post is about a GIMP kernel module, type:\n'+\
            '  linux kernel, gimp, gimp linux kernel module'))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        topics = gtk.Entry()
        vbox.pack_start(topics, gtk.FALSE, gtk.FALSE, 0)

        if in_reply_to:
            topics.set_text(string.join(in_reply_to.wodge.get('topics',[ ]),', '))

        label = widgets.Helpful_label(_('Text:'),\
            _('Your actual post.\n\n'+\
            'Your text will be formatted automatically, so you don\'t need to press ' +\
            'enter at the end of each line. Also, people will be able to click on ' +\
            'any URLs in the text.'))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        
        #text = gtk.Entry()
        text = gtk.TextView()
        buffer = text.get_buffer()
        text.set_editable(gtk.TRUE)
        text.set_wrap_mode(gtk.WRAP_WORD)

        if in_reply_to:
            if in_reply_to.wodge['human-name']:
                str = in_reply_to.wodge['human-name'] + _(' wrote that ')
            else:
                str = _('An anonymous author wrote that ')
            str = str + '"' + in_reply_to.wodge['subject'] + '"\n\n' 
            buffer.insert(buffer.get_end_iter(), str)
        
        scrolly = gtk.ScrolledWindow()
        scrolly.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolly.add(text)
        vbox.pack_start(scrolly, gtk.TRUE, gtk.TRUE, 0)

        label = widgets.Helpful_label(_('One line summary:'),\
            _('A short summary of your post.'))
        vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        subject = gtk.Entry()
        vbox.pack_start(subject, gtk.FALSE, gtk.FALSE, 0)


        #al = gtk.Alignment(0,0,0,0)
        #vbox.pack_start(al, gtk.FALSE, gtk.FALSE, 0)
        #label = gtk.Label('Trust distance:')
        #label.set_justify(gtk.JUSTIFY_LEFT)
        #al.add(label)
        
        #label = widgets.Helpful_label('Trust distance:',\
        #  'How much you yourself trust what you are saying in your post. '+\
        #  'A low distance implies high trust and vice versa. So if you believe '+\
        #  'the contents of your post highly, set the distance close to zero. But '+\
        #  'if you don\'t believe it so much, for example you are just passing on '+\
        #  'a rumour, set the distance to a larger value.',self.app.tooltips)
        #vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)

        #distance_adj = gtk.Adjustment(0.5 ,0.0,2.5,0.5,0.5,0.5)

        #distance_scale = gtk.HScale(distance_adj)
        #vbox.pack_start(distance_scale, gtk.FALSE, gtk.FALSE, 0)

        anonymous = gtk.CheckButton(_("Anonymous"))
        vbox.pack_start(anonymous, gtk.FALSE, gtk.FALSE, 0)

        # ... not quite there yet, gossip is only gotten hourly...
        #if not self.any_gossip_gets:
        #  label = gtk.Label('Note: No-one has requested gossip from you yet in this session.\n'+\
#                     'This might be because none of your friends are online, or because you are\n'+\
#                     'new to the Circle network and no one has added you to their trusted gossip\n'+\
#                     'sources.\n'+\
#                     '\n'+\
#                     'This post will only propagate once you and people who trust your news are\n'+\
#                     'online at the same time.')
#      label.set_alignment(0,0)
#      label.set_justify(gtk.JUSTIFY_LEFT)
#      vbox.pack_start(label, gtk.FALSE, gtk.FALSE, 0)

        hbox = gtk.HBox(gtk.FALSE,5)
        vbox.pack_end(hbox, gtk.FALSE, gtk.FALSE, 0)

        def on_post(button, self=self,topics=topics,subject=subject,text=text,window=window,anonymous=anonymous,in_reply_to=in_reply_to):
            try:
                topic_list_unstripped = string.split(widgets.get_utext(topics),',')
                topic_list = [ ]
                for item in topic_list_unstripped:
                    str = string.lower(string.strip(item))
                    if str:
                        topic_list.append(str)

                buffer = text.get_buffer()
                body = widgets.get_uslice(buffer.get_start_iter(),buffer.get_end_iter())
                self.gossip.post_wodge(
                    topic_list,widgets.get_utext(subject),
                    body,0.0,anonymous.get_active(),in_reply_to)
            except error.Error, err:
                self.show_error(err,window)
                return
            window.destroy()

        button = gtk.Button(_("Post"))
        button.connect("clicked",on_post)
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)

        button = gtk.Button(_("Cancel"))
        button.connect("clicked",lambda _b, _window=window: _window.destroy()) 
        hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)

        self.show_window(window, 'post_gossip')

    def show_gossip(self, topic=None, sender=None, perspective=None, update =0):
        window = gtk.Window()
        window.set_default_size(500,500)
        window.set_border_width(10)
 
        scrolly = gtk.ScrolledWindow()
        scrolly.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)

        window.add(scrolly)
        title = 'Gossip:'
        if topic:
            title += ' topic '+topic
        if sender:
            title += ' postings by '+ sender.nickname
            sender = sender.name
        if perspective:
            title += ' '+perspective.nickname+'\'s perspective'
            perspective = perspective.name
        window.set_title(title)
        self.show_window(window, 'Gossip')
        self.construct_gossip_list(scrolly, topic, sender, perspective,update)

    def construct_gossip_list(self, scrolly,topic,person,perspective,update=0):

        list = self.gossip.sorted_wodges(perspective)    
        vbox_inner = gtk.VBox(gtk.FALSE,0)

        filtered_list = [ ]
        for item in list:
            if topic != None and topic not in item[1].wodge.get('topics',[ ]):
                continue

            if person != None and item[1].wodge.get('name') != person:
                continue

            filtered_list.append(item)

        n_items = 0
        n_open  = 0
        for item in filtered_list:
            if n_items >= 100:
                break
            if n_open  >= 20:
                break

            #utility.threadnice_flush_events()

            wodge = item[1].wodge

            n_items = n_items + 1

            hbox_item = gtk.HBox(gtk.FALSE,0)
            vbox_inner.pack_start(hbox_item, gtk.FALSE, gtk.FALSE, 0)

            button = gtk.Button()
            button.set_relief(gtk.RELIEF_NONE)
            hbox_item.pack_start(button, gtk.FALSE, gtk.FALSE, 0)

            vbox_item = gtk.VBox(gtk.FALSE,0)
            hbox_item.pack_start(vbox_item, gtk.TRUE, gtk.TRUE, 0)

            title = widgets.Text(heading=1)
            title.write(string.strip(wodge['subject'][0:70]), self)
            vbox_item.pack_start(title.packee(), gtk.TRUE, gtk.TRUE, 0)

            if not item[1].collapsed:
                vbox_body = self.make_wodge_body(item[1],self.gossip)
                vbox_item.pack_start(vbox_body, gtk.TRUE, gtk.TRUE, 0)
                vbox_body.show_all()
                n_open = n_open+1
                arrow_direction = gtk.ARROW_UP
            else:
                arrow_direction = gtk.ARROW_DOWN

            arrow = gtk.Arrow(arrow_direction, gtk.SHADOW_IN)
            arrow.set_alignment(0.5,1)            
            button.add(arrow)
            vbox_item.show_all()

            def on_toggle(
                collapsed,wodge=item[1],hbox_item=hbox_item,arrow=arrow,vbox_item=vbox_item,self=self):
                #if down[0]:
                if not collapsed:
                    arrow.set(gtk.ARROW_UP, gtk.SHADOW_IN)
                    vbox_body = self.make_wodge_body(wodge,self.gossip)
                    vbox_item.pack_start(vbox_body, gtk.TRUE, gtk.TRUE, 0)
                    vbox_body.show_all()
                else:
                    arrow.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
                    vbox_item.get_children()[1].destroy()
                hbox_item.queue_resize()

            item[1].add_togglee(on_toggle)
            button.connect("clicked",lambda b,item=item: item[1].toggle())
            button.connect(
                "destroy",lambda b,item=item,on_toggle=on_toggle: item[1].remove_togglee(on_toggle))

        scrolly_children = scrolly.get_children()        
        if scrolly_children:
            scrolly.remove(scrolly_children[0])

        if n_items:
            scrolly.add_with_viewport(vbox_inner)
            vbox_inner.show_all()
        else:
            message = widgets.Text(200, heading=0)
            message.write(
                _('\nNo gossip available.\n\n'
                  +'To use gossip, you must first nominate some '
                  +'people whose gossip you would like to hear. '
                  +'Click on the name of someone on your contact list,'
                  +' and tick the "Trust this person\'s gossip" box.'))
            scrolly.add_with_viewport(message)
            message.show()


    def make_wodge_body(self, wodge, gossip):
        
        vbox_body = gtk.VBox(gtk.FALSE,0)
        
        text_widget = widgets.Text()
        text_widget.write('\n'+_('Topics: '))
        wodge_topics = wodge.wodge.get('topics',[ ])
        for i in range(len(wodge_topics)):
            text_widget.write(
                wodge_topics[i],gossip.app,
                lambda gossip=gossip,topic=wodge_topics[i]: self.show_gossip(topic))
            if i < len(wodge_topics)-1:
                text_widget.write(', ')
        
        if wodge.wodge['human-name']:
            opinion_list = [ ]
            decay = wodge.decay()
            for pair in wodge.opinions.items():
                acq = self.name_server.acquaintances.get(pair[0])
                if acq:
                    distance = acq.distance
                    if distance != None:
                        opinion_list.append((distance+decay+pair[1], acq.nickname, decay+pair[1]))
            opinion_list.sort()
            
            str = ''
            for item2 in opinion_list[:5]:
                str = str + item2[1] + ' ' + '%.1f'%item2[2] + ', '
            if len(opinion_list) > 5:
                str = str + ' ...'
            else:
                str = str[:-2]
            
            #str = 'Posted ' + time.strftime('%d %b %Y',time.localtime(wodge['post-time'])) + ' by ' + wodge['human-name'] + 
            text_widget.write(_('\nPosted ') + time.strftime(_('%d %b %Y'),
                           time.localtime(wodge.wodge['post-time'])) + _(' by '))
            text_widget.write(wodge.wodge['human-name'],self,
                lambda gossip=gossip,wodge=wodge.wodge: searcher.search_for_name(
                hash.hash_of('identity-offline '+wodge['name']),'Wodge poster', self.node, self)
            )
            
            str = '\n\n' + utility.force_unicode(wodge.wodge['text']) + \
                  _('\n\nTrust distance:\n(')+utility.force_unicode(str)+')'
            text_widget.write('\n'+str, self)
        else:
            str = wodge.wodge['text'] + _('\n\nTrust distance:\n' + \
                        '(this is an anonymous post, you can help make it harder to track by reducing its distance)') 
            text_widget.write('\n'+str, self)

        text_widget.write('\n')

        #str = 'Topics: '+string.join(wodge.get('topics',[ ]),', ')+'\n'+str

        #vbox_item.pack_start(text_widget.packee(), gtk.TRUE, gtk.TRUE, 0)
        vbox_body.pack_start(text_widget.packee(), gtk.TRUE, gtk.TRUE, 0)

        hbox_body = gtk.HBox(gtk.FALSE,0)
        vbox_body.pack_start(hbox_body, gtk.FALSE, gtk.FALSE, 5)

        distance = wodge.distance(self.name_server)
        if distance < 20:
            max = 20
        else:
            max = distance
        distance_adj = gtk.Adjustment(value=distance,
                                      lower=0.0,
                                      upper=max + 0.5,
                                      step_incr=0.5,
                                      page_incr=0.5,
                                      page_size=0.5)

        distance_scale = gtk.HScale(distance_adj)
        distance_scale.connect("scroll-event", lambda *_: 1)
        #vbox_item.pack_start(distance_scale, gtk.FALSE, gtk.FALSE, 0)
        hbox_body.pack_start(distance_scale, gtk.TRUE, gtk.TRUE, 0)

        def value_changed(adjustment, gossip=gossip,wodge=wodge):
            #gossip.lock.acquire()
            wodge.initial_distance = adjustment.value - wodge.decay()
            #gossip.lock.release()
        distance_adj.connect("value_changed",value_changed)

        alignment = gtk.Alignment(0,1,0,0)
        hbox_body.pack_start(alignment, gtk.FALSE, gtk.FALSE, 10)
        reply = gtk.Button(_(' Reply '))
        alignment.add(reply)
        def on_reply(button, wodge_object=wodge, self=self):
            self.prompt_for_wodge(wodge_object)
        reply.connect("clicked",on_reply)

        alignment = gtk.Alignment(0,1,0,0)
        hbox_body.pack_start(alignment, gtk.FALSE, gtk.FALSE, 10)
        delete = gtk.Button(_(' Delete '))
        alignment.add(delete)
        def on_delete(button, wodge_object=wodge, self=self):
            self.gossip.gossip.remove(wodge_object)
            self.construct_gossip_list(self.gossip_scrolly,None,None,None)
        delete.connect("clicked",on_delete)

        return vbox_body



class Random_gtk:

    def __init__(self, transient_for=None):
        self.buffer = ''
        self.window = gtk.Window()
        self.window.set_title(_('Entropy collection'))
        self.window.set_modal(gtk.TRUE)
        if transient_for:
            self.window.set_transient_for(transient_for)
        self.window.set_border_width(10)
        self.window.connect("delete_event", lambda _w,_e: gtk.TRUE)
        self.window.connect("key-press-event", self.event)
        #self.window.set_events(gtk.KEY_PRESS_MASK)

        vbox = gtk.VBox(gtk.FALSE, 5)
        self.window.add(vbox)

        label = gtk.Label(_('Some random data is needed to generate a cryptographic identity for you.')+"\n")
        vbox.pack_start(label, gtk.FALSE, gtk.FALSE, 0)
        
        self.progress_label = gtk.Label('')
        vbox.pack_start(self.progress_label, gtk.FALSE, gtk.FALSE, 0)

        self.progress = gtk.ProgressBar()
        vbox.pack_start(self.progress, gtk.FALSE, gtk.FALSE, 0)

        self.window.show_all()

    #def callback(self, a,b):
    #  char = os.read(self.file.fileno(),1)
    #  self.buffer = self.buffer + char

    def event(self, widget,event):
        self.buffer = self.buffer + utility.rand_from_time()

    def finish(self):
        #input_remove(self.tag)
        #self.file.close()
            
        self.progress_label.set_text(_('Done'))
        while gtk.events_pending():
            gtk.mainiteration()
        time.sleep(2)
        
        self.window.destroy()
        
    def randfunc(self, n):
        """Return a random string of n bytes (sic: not bits)."""
        # Clear buffer so keypresses during calculation don't all arrive at
        # the same time
        while gtk.events_pending():
            gtk.mainiteration()
        self.buffer = ''
    
        self.progress_label.set_text(_('Please bang on the keyboard like a monkey.'))
        while len(self.buffer) < n:
            self.progress.set_fraction(float(len(self.buffer))/n)
            gtk.mainiteration()
        
        try:
            return self.buffer[:n]
        finally:
            #self.buffer = self.buffer[n:]
            self.progress_label.set_text(_('Calculating...'))
            self.progress.set_fraction(1.0)
            while gtk.events_pending():
                gtk.mainiteration()






# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
