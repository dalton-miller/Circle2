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
   Circle daemon code

   Note about the architecture:

   The core of circle runs in the main thread
   The user interface runs in a separate thread

   The daemon is part of the core.
   The daemon contains : node, cache, file_server.
   
   name_server and chat are part of the core,
   but they do not belong to the daemon:
   they are created only when the gui is used.
   
   chat objects depend on the interface:
   there is a chat_text for the text interface, and chat_gtk for the gtk interface
   
"""

import os, sys, threading, time, traceback, string
import math, types, socket, random, select

import __init__
import check
import error
import hash
import node
import settings
import utility
import cache
import file_server

from ui_http import circle_http
import proxy

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





class Circle_daemon(utility.Task_manager):

        
    def status(self):
        
        self.node.lock.acquire()
        port    = self.node.address[1]
        n_peers = len(self.node.peers)
        n_bytes = self.node.network_usage
        self.node.lock.release()
                    
        self.file_server.lock.acquire()
        n_files = len(self.file_server.paths)
        self.file_server.lock.release()
        
        status = _('Circle daemon running on port %d:\n')%port
        if self.config.get('public_dir'):
            status += _('  Public directory: ')\
                      + self.config['public_dir']+'\n'
        else:
            status += _('  No public directory\n')
        if self.config.get('publish_apt'):
            status += _('  Apt cache published if available\n')
        else:
            status += _('  Apt cache not published\n')
        status += _('  %d files published (this may take a while to update)\n')%n_files\
                  + _('  Connected to %d peers, ') % n_peers\
                  + _('hashtable is %s\n') % (("inactive","active (%d links)"%len(self.node.links))[self.node.hashtable_running])\
                  + _('  Total network usage %s\n') % utility.human_size(n_bytes)

        if self.http_running:
            #import circle_http
            status = status + circle_http.status()
        return status

    def set_http(self):
        #import circle_http
        str = circle_http.status()
        if self.config.get('http') == 0:
            if self.http_running:
                str = circle_http.stop()
            return str
        elif self.config.get('http') == 2:
            if not self.http_running:            
                str = circle_http.start('local',self)
            return str
        elif self.config.get('http') == 1:
            if not self.http_running:            
                str = circle_http.start('remote',self)
            return str



    def run(self, initial_command = None, proxy_mode='none'):
        """ This is the daemon mainloop. """

        self.thread_list= utility.thread_list
        
        if ( proxy_mode == 'always' or \
             (proxy_mode == 'auto' and node.need_proxy()) ):
            print _("Circle needs to run a proxy (see documentation).")
            print
            print _("SSH to where (username@machine.name)? "),
            proxy_host = sys.stdin.readline().strip()
            proxy_obj = proxy.Proxy(proxy_host)
        else:
            proxy_obj = None

        if sys.platform == 'win32' or initial_command == 'no-fork\n':
            fork = 0
            initial_command = 'gtk\n'
        else:
            fork = 1

        if fork:
            branch = os.fork()
        else:
            branch = 0
            
        if not branch:
            # Note: 'print' statements are not allowed within this branch of the fork

            #os.setsid()
            sys.stdin.close()
            dev_null = open('/dev/null','wt')
            sys.stdout.close()
            sys.stderr.close()
            sys.stdout = dev_null
            sys.stderr = dev_null

            if fork:
                com_sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                com_sock_file = os.path.join(utility.config_dir,'daemon_socket')
                try:
                    os.unlink(com_sock_file) 
                except OSError:
                    pass            
                com_sock.bind(com_sock_file)
                com_sock.listen(5)
        
            self.start()
            self.node = node.Node()
            self.node.start(proxy_obj)

            self.file_server = file_server.File_server(self.node)
            self.cache = cache.Cache(self.node)
            self.interface = None

            self.config = utility.get_config('daemon', { })
            for pair in [('public_dir', ''),
                         ('private_dir', ''),
                         ('download_dir', ''),
                         ('stay_alive', 1),
                         ('http', 0),
                         ('publish_apt', 0),
                         ('keep_sharing', 0)]:

                if not self.config.has_key(pair[0]):
                    self.config[pair[0]] = pair[1]

            self.file_server.set_roots(self.config)            
            self.file_server.start()
            self.cache.start()

            #if fork:
            #    def signal_handler(signal, frame):                    
            #        raise error.Error('signal')
            #else:
            #    def signal_handler(signal, frame): 
            #        print _("Received signal %d.") % signal

            #for s in exit_signals:
            #    signal.signal(s, signal_handler)                

            self.accept_gtk = 1
            self.stopping = 0
            self.http_running = 0
            self.set_http()
            self.interface_running = 0

            if not fork:
                from ui_gtk import circle_gtk
                self.gtk_interface_requested = 1
                utility.Task(circle_gtk.gui_task,self,fork).start()
                output = sys.stdout
            else:
                self.gtk_interface_requested = 0
                gui_task_launched = 0                
                while not self.stopping:
                    # at this point it cannot be 'text'
                    if initial_command:
                        command = initial_command
                        initial_command = None
                        #if command == 'text\n':                        
                        input = sys.stdin
                        output = sys.stdout                        
                        connection = None
                    else:
                        try:
                            while not select.select([com_sock],[],[],0.1)[0]:
                                if self.stopping: break
                                try:                            
                                    utility._daemon_action_timeout()
                                except:
                                    apply(utility.report_bug,sys.exc_info())

                            #if stopping we need to exit the 2nd loop too:
                            if self.stopping: break

                            connection = com_sock.accept()[0]
                            input  = connection.makefile("rt")
                            output = connection.makefile("wt")
                            command = input.readline()
                        except:
                            apply(utility.report_bug,sys.exc_info())
                            continue

                    if command == 'quit\n':
                        if self.interface_running:
                            output.write('Shutting down interface...\n')
                            self.interface.shutdown()
                        self.stopping = 1
                        break

                    if command == 'shutdown\n':
                        if self.interface_running:
                            output.write('Shutting down interface...')
                            self.interface.shutdown()
                        else:
                            output.write('No interface running.')

                    elif command == 'sync config\n':
                        self.config = utility.get_config('daemon',{})
                        self.file_server.set_roots(self.config)
                        output.write(_("Active circle daemon has updated its settings."))

                    elif command == 'status\n':
                        str = self.status()
                        output.write(str)

                    elif command == 'activate\n':
                        self.node.activate_hashtable()
                        output.write("Hashtable activated")

                    elif command == 'gtk\n':


                        if not self.accept_gtk:
                            output.write("cannot run gtk interface: problem with gtk threads")
                        else:
                            if not gui_task_launched:
                                from ui_gtk import circle_gtk
                                utility.Task(circle_gtk.gui_task,self,fork).start()
                                gui_task_launched = 1
                                
                            if not self.interface_running:
                                self.gtk_interface_requested = 1
                            else:
                                output.write("Circle interface already running")

                    elif command == 'text\n':

                        def text_task(self, input, output):
                            from ui_text import circle_text
                            import settings
                            settings.terminal_encoding = sys.getdefaultencoding()
                            self.interface = circle_text.Circle_text(self,input,output)
                            self.interface.run_main()
                            self.interface_running = 0
                            #try:
                            input.close()
                            if connection:
                                connection.close()
                            output.close()
                            #except:
                            #    pass
                        if not self.interface_running:
                            self.interface_running = 1
                            output.write('Starting text interface\n')
                            utility.Task(text_task,self,input,output).start()
                        else:
                            output.write("Circle interface already running")                
                            input.close()
                            if connection:
                                connection.close()
                            output.close()
                    elif command == 'debug\n':
                        for item in threading.enumerate():
                            output.write(repr(item)+'\n\n')
                    elif command[0:6] == 'search':
                        utility.Task(
                            search_task,self,command[7:-1],input,output,connection).start()
                    elif command[0:4] == 'find':
                        utility.Task(
                            find_task,self,command[5:-1],input,output,connection).start()
                    elif command[0:4] == 'get ':
                        utility.Task(
                            get_file_task,self,command[4:38],input,output,connection).start()
                    elif command == 'http local\n':
                        self.config['http'] = 2
                        output.write(self.set_http())
                    elif command == 'http remote\n':
                        self.config['http'] = 1
                        output.write(self.set_http())
                    elif command == 'http stop\n':
                        self.config['http'] = 0
                        output.write(self.set_http())
                    elif command[0:7] == 'connect':
                        try:
                            address = utility.parse_address(self.node.address, command[8:-1])
                            self.node.probe(address)
                        except:
                            output.write(sys.exc_info()[1])

                    else:
                        output.write(_('Huh?'))

                    if command.split()[0] not in ['search','find','get','text']:
                        try:
                            input.close()
                            connection.close()
                            output.close()
                        except:
                            pass

            if self.accept_gtk and self.gtk_interface_requested:
                #print "waiting for interface..."
                while self.gtk_interface_requested:
                    utility._daemon_action_timeout()
                    time.sleep(0.01)                 
                #print "interface is down"
                    
            #utility.threadnice_mainloop_stop()
            #except error.Error: # signal, eg ^C, SIGTERM
            #    pass
                
            for s in exit_signals:
                signal.signal(s, signal.SIG_IGN)

            self.cache.stop()
            self.file_server.stop()

            if self.node.hashtable_running:
                initial_links = len(self.node.links)
                self.node.deactivate_hashtable()
                while self.node.hashtable_offloaders or self.node.links:
                    utility._daemon_action_timeout()
                    time.sleep(0.01)
                    output.write("offloading : %.1f%% \r" % 
                        ((initial_links-len(self.node.links))*100.0 /
                        initial_links ))
                    output.flush()

            # todo: ensure that this terminates
            # node.stop() needs to be called, interrupt is bad
            if self.interface:
                if self.interface.name_server.disconnect_threads:
                    print "disconnecting identity..."
                while self.interface.name_server.disconnect_threads:
                    time.sleep(0.01)
                    utility._daemon_action_timeout()

            print "stopping node"
            self.node.stop()
            if fork:
                com_sock.close()
                os.unlink(com_sock_file)

            if self.http_running:
                circle_http.stop()
            
            if self.stopping:
                self.running=0
                try:
                    if fork:
                        output.write(_('Circle daemon stopped.'))
                        input.close()
                        output.flush()
                        output.close()
                        connection.close()
                except:
                    pass

            self.stop()
        else:
            print _("Circle daemon started.")



def search_task(daemon,query,input,output,connection):

    for char in '+-_.,?()![]':
        query = query.replace(char," ")
    query=query.lower()
    list=query.split()
    if list:
        key=list[0]
    else:
        key=''

    if key.__len__()<3:
        output.write("Keyword %s too short: must be at least 3 characters"%key)            
        input.close()
        output.close()
        connection.close()
        return    
        
    pipe = daemon.node.retrieve(hash.hash_of(key))
    results = []
    restricted = 0
    while not pipe.finished() and not restricted:
        for item in pipe.read_all():

            if results.__len__()==100:
                restricted = 1
                break
            
            if item[1]['name'] not in results:
                results.append(item[1]['name'])
                filename = utility.force_string(item[1]['filename'])
                extension = string.split(string.split(filename,'.')[-1],'-')[0]
                lext = string.lower(extension)
                if lext in ['mp3','ogg']:
                    music=1
                else:
                    music=0
                if item[1].has_key('music_title'):
                    ref = utility.force_string(item[1]['music_title'])
                    if ref.strip()=='':
                        ref= filename
                else:
                    ref = utility.force_string(item[1]['filename'])

                length = item[1].get('length')
                if not length:
                    sl=''
                else:
                    sl = utility.human_size(length)
                output.write(hash.hash_to_url(item[1]['name'])+" \t"\
                             +sl+" \t"+filename+'\n')

        time.sleep(0.5)
        try:
            output.flush()
        except:
            return
    if not results:
        try:
            output.write("No document matching \""+key+"\"")          
        except:
            pass
    else:
        if results.__len__()==1:
            msg = "1 file found."
        else:
            msg = "%d files found."%results.__len__()
        output.write(msg)

        
    pipe.stop()
    try:
        input.close()
        output.close()
        connection.close()
    except:
        pass
    #sys.stdout.flush()


def find_task(daemon,query,input,output,connection):

    import safe_pickle

    for char in '+-_.,?()![]':
        query = query.replace(char," ")
    query=query.lower()
    list=query.split()
    if list:
        key=list[0]
        pipe = daemon.node.retrieve(hash.hash_of('identity-name '+key), settings.identity_redundancy)
    else:
        pipe = daemon.node.retrieve(hash.hash_of('service identity'), settings.identity_redundancy)
        
    results = []
    while not pipe.finished():

        list = pipe.read_all()
        prev_pair = None
        for pair in list:
            if pair == prev_pair:
                continue
            link, item = prev_pair = pair

            try:
                item = utility.check_and_demangle_item(item)
            except:
                continue

            if item['key'] not in results:
                results.append(item['key'])
                name = hash.hash_of(safe_pickle.dumps(item['key']))
                check.check_is_name(name)
                str = hash.hash_to_person(name)
                output.write(
                    str+'   '+item['name']+" ("+utility.force_string(item['human-name'])+")\n")
                
        time.sleep(0.5)
        try:
            output.flush()
        except:
            return
        
    if not results:
        try:
            output.write("No user matching \""+key+"\"")
        except:
            pass
    else:
        if results.__len__()==1:
            msg = "1 user found."
        else:
            msg = "%d users found."%results.__len__()
        output.write(msg)

    pipe.stop()
    try:
        input.close()
        output.close()
        connection.close()
    except:
        #connection reset by peer...
        pass


def get_file_task(daemon,url,input,output,connection):
    try:
        name=hash.url_to_hash(url)    
        salt_name=name+daemon.node.salt
    except:
        output.write(_('error: Not a circle URL :')+url)
        input.close()
        output.close()
        connection.close()
        return

    if daemon.file_server.paths.get(name):
        #if daemon.node.data.has_key(salt_name)
        filename=daemon.file_server.paths.get(name)[0]
        output.write('File already in your directory: '+filename)
    else:
        pipe = daemon.node.retrieve(name)
        list = pipe.read_until_finished()
        if not list:
            output.write(_('Could not locate file.\n'))
            input.close()
            output.close()
            connection.close()
            return
        data = list[0][1]

        links = [ ]
        for item in list:
            links.append(item[0])

        if daemon.config.get('public_dir'):
            downloader = file_server.Circle_Downloader(daemon.node, data,links,daemon.config['public_dir'])
            daemon.file_server.downloaders.append(downloader)
            downloader.start()

            while downloader.running:
                output.write(downloader.basename + (" : %.1f%% \r" % (
                    (downloader.get_bytes_downloaded()+1)*100.0 /
                    (downloader.get_bytes_total()+1) )))
                try:
                    output.flush()
                except:
                    downloader.stop()
                time.sleep(0.3)
            try:
                output.write(downloader.basename + (" : %.1f%% \r" % (
                    (downloader.get_bytes_downloaded()+1)*100.0 /
                    (downloader.get_bytes_total()+1) )))             
                output.close()
            except:
                pass
                
            if downloader.success:
                daemon.node.publish(name,data)
                daemon.file_server.paths[name]=(downloader.filename,os.path.getmtime(downloader.filename))
        else:
            output.write(_(' You need to define a public directory'\
                           +' where the Circle daemon will download files\n'
                           +' Type \'circle publish <directory>\' in a terminal\n'))
    try:
        output.close()
        input.close()
        connection.close()
    except:
        pass
