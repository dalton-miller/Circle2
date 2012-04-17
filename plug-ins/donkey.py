# Circle interface to Overnet

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

# TODO :
#        Use free software edonkey client: http://www.freesoftware.fsf.org/mldonkey/
#        handle edonkey files with the player
#        interface to mldonkey 
#        checksum the binary file after it is downloaded
# 

import os, sys, string, threading
from types import *
from utility import Task_manager
from error import Error
import file_server
import utility
import widgets
import time



overnet_version="0.51.2"

def stop():
    app.overnet.stop()
 
def donkey_retrieve_task(pipe,donkey):
    
    donkey.results = [ ]
    donkey.waiting_results = 1
    donkey.reading_results = 0

    time_0=time.time()
    while donkey.waiting_results:
        time.sleep(0.3)
        if time.time()-time_0>60.0:
            donkey.waiting_results=0
        

    donkey.lock.acquire()
    donkey.reading_results = 1
    donkey.lock.release()

    donkey.tell('vr\n')
    time.sleep(3)

    donkey.lock.acquire()
    donkey.reading_results=0
    donkey.lock.release()

    for item in donkey.results:
        ss2 = item.split('\t')      #all fields
        ss = ss2[0].split(' ',1)    #name and number, first field
        if len(ss2)>1:
            pipe.write((('overnet',donkey),{ \
                        'keywords' : [ donkey.key ], \
                        'length' : int(ss2[1]), \
                        'type' : 'file', \
                        'mime' : utility.force_string(ss2[2].lower().replace('\n','')),\
                        'name' : utility.force_string('file:'+ss[0][1:-1]), \
                        'index' : ss[0][1:-1], \
                        'filename' : ss[1] \
                       }))


class Donkey(Task_manager):
    """ class Donkey. """

    def __init__(self,app):

        Task_manager.__init__(self)
        self.node = app.node
        self.app  = app
        self.pid = None
        self.results = [ ]
        self.key = None
        self.downloads = [ ]
        self.running = 0
        self.connected = 0
        self.connecting = 0
        self.reading_message = 0
        self.message = ''
        self.exit=0
        
        self.reading_results = 0
        self.reading_downloads = 0
        self.reading_status = 0
        self.waiting_results = 0

        self.tempdir=os.path.join(self.app.config['download'],'.edonkey_temp/')
        self.client_file    =os.path.join(utility.config_dir,'overnet'+overnet_version)
        self.connected = 1

        #if os.path.isdir(self.tempdir):
        #    list = os.listdir(self.tempdir)
        #    for item in list:
        #        if item[-4:]=='.met' and not list.count(item[:-4]):
        #            os.unlink(os.path.join(self.tempdir,item))

        #    for item in list:
        #        if item[-5:]=='.part' and not list.count(item+'.met'):
        #            os.unlink(os.path.join(self.tempdir,item))
        
    def display_message(self,msg,color='grey'):
        if self.app.chat.running:
            utility.mainthread_call(self.app.chat.show,msg,color)

    def start(self):

        def poll_downloads(self):

            if not self.reading_results and not self.reading_status and not self.reading_downloads:
                self.lock.acquire() #  otherwise downloads get written in results... 
                self.vd()
                self.reading_downloads = 1
                self.lock.release()

            return self.running

        def read_messages_task(self):
            buffer = ""
            while self.running:
                try:
                    str=""
                    c=""
                    while c != '\n':
                        c = os.read(self.shell_master,1)
                        str=str+c
                except:
                    self.running=0
                    return

                str = string.replace(str,'\r','')
                str = string.replace(str,'> ','')
                str = string.replace(str,chr(7),'')

                str = unicode(str,'latin-1')
                #print "overnet:",str

                if not self.reading_downloads:
                    if self.reading_message:
                        self.message = self.message + str

                if self.reading_status:
                    self.status+=str
                    if string.find(str,'Users') != -1:
                        self.reading_status=0
                    
                if string.find(str,'Invalid Result number') != -1:
                    raise Error('eDonkey error: '+str)

                if string.find(str,'Connected to:') != -1:
                    self.display_message('overnet client c'+str[1:],'grey')
                    if self.connecting:
                        self.reading_message = 1
                        self.message = ''
                    else:
                        self.reading_message = 0
                    self.connecting = 0
                    self.connected = 1

                elif string.find(str,'Connecting to') != -1 and self.connecting:
                    self.display_message( 'overnet client c'+str[1:],'grey')
                elif string.find(str,'Disconnected') != -1:
                    self.display_message( 'overnet client disconnected.\n','red')
                    self.connected = 0

                if self.waiting_results:
                    if str[0:16] == 'Results returned' or str[0:11] == 'Got results':
                        self.waiting_results = 0

                if self.reading_results:
                    if str[0:1] == '(':
                        self.results.append(str)
                    else:
                        self.tell(' ')

                    #if str[0:11] == 'press space':
                    #    print "overnet: pressing space"
                    #    self.lock.acquire()
                    #    self.tell(' ')
                    #    self.lock.release()
                    #    #time.sleep(0.01)

                if self.reading_downloads:
                    if string.find(str,'File Name') != -1:
                        self.downloads = [ ]

                    if string.find(str,'Total') != -1:
                        self.lock.acquire()
                        self.reading_downloads = 0
                        self.lock.release()

                        for downloader in self.app.file_server.downloaders:
                            if downloader.node==self and not downloader.neverseen:
                                downloader.lock.acquire()
                                downloader.success=1
                                downloader.lock.release()

                        for item in self.downloads:
                            number = self.downloads.index(item)
                            has_downloader=0
                            for downloader in self.app.file_server.downloaders:
                                if string.find(item,downloader.data['filename']) == -1:
                                    continue
                                else:
                                    downloader.lock.acquire()
                                    downloader.number = number
                                    downloader.success=0
                                    downloader.neverseen=0
                                    has_downloader=1
                                    try:                                    
                                        downloader.bytes_downloaded = int(self.downloads[number+1].split('\t')[4][:-1])*1024
                                        downloader.speed_kBs    = float(self.downloads[number+1].split('\t')[5]) 
                                        downloader.availability = self.downloads[number+1].split('\t')[6]
                                        downloader.status       = self.downloads[number+1].split('\t')[2]
                                        downloader.lock.release()
                                    except:
                                        break

                            if not has_downloader:
                                try:
                                    data=( { 'keywords' : [ '?' ], \
                                             'length' : int(self.downloads[number+1].split('\t')[3][:-1])*1024, \
                                             'type' : 'file', \
                                             'name' : 'file:?', \
                                             'index' : '?', \
                                             'filename' : self.downloads[number].split(' ',1)[1][:-2] \
                                             })
                                except:
                                    data=None
                                if data:
                                    downloader = file_server.Donkey_Downloader(self,data,self.app.config['download'])
                                    downloader.lock.acquire()
                                    downloader.number = number
                                    downloader.success=0
                                    downloader.neverseen=0
                                    downloader.lock.release()
                                    utility.mainthread_call(self.app.download_manager.assert_visible)
                                    self.app.file_server.downloaders.append(downloader)
                                    utility.mainthread_call(downloader.start)

                    if str.find('Downloading:') != -1:
                        str=None
                    if str:
                        self.downloads.append(str)

        if self.running:
            return
        Task_manager.start(self)
        self.running=1
        self.results = [ ]
        self.downloads = [ ]
        self.reading_results = 0
        self.reading_downloads = 0
        self.waiting_results = 0

        self.shell_master, self.shell_slave = os.openpty()

        import termios
        try:
            termios.ECHO
            TERMIOS = termios
        except:
            import TERMIOS

        attr = termios.tcgetattr(self.shell_master)
        attr[3] = attr[3] & ~TERMIOS.ECHO
        termios.tcsetattr(self.shell_master,TERMIOS.TCSANOW,attr)

        attr = termios.tcgetattr(self.shell_slave)
        attr[3] = attr[3] & ~TERMIOS.ECHO
        termios.tcsetattr(self.shell_slave,TERMIOS.TCSANOW,attr)

        try:
            self.pid = os.fork()
        except:
            raise Error('eDonkey : cannot fork')
            return


        if not self.pid:
            time.sleep(1)
            os.chdir(utility.config_dir)
            os.dup2(self.shell_slave, 0) 
            os.dup2(self.shell_slave, 1) 
            os.dup2(self.shell_slave, 2)

            os.execlp('/bin/sh','/bin/sh','-c',self.client_file)
            os._exit(0)

    
        self.set_options()
        self.connect()
        self.display_message('overnet client running.\n','grey')

        utility.schedule_mainthread(500.0,poll_downloads,self)
        utility.Task(read_messages_task,self).start()

    def stop(self):
        if not self.running:
            return

        if self.app.chat.running:
            self.display_message('waiting for overnet client to finish...\n','grey')

        def timeout(self=self):
            result = os.waitpid(self.pid,os.WNOHANG)
            if result[0] == self.pid:
                self.lock.acquire()
                self.pid = None
                self.lock.release()
                return 0
            return 1

        utility.schedule_mainthread(250.0, timeout)

        while self.pid != None:
            self.tell('q\n')
            time.sleep(0.3)
            self.tell('y\n')
            time.sleep(0.3)
            
        os.close(self.shell_master)
        os.close(self.shell_slave)
            
        self.connected=0
        self.running = 0
        if self.app.chat.running:
            self.display_message('overnet client stopped.\n','grey')

        for downloader in self.app.file_server.downloaders:
            if downloader.node==self:
                downloader.stop()

        Task_manager.stop(self)

    def connect(self):
        self.connecting=1
        self.tell('c\n')

    def disconnect(self):
        self.tell('x\n')
        self.connected=0
        self.connecting=0

    def vm(self):
        self.tell('vm\n')        

    def download(self,number):
        self.tell( 'd %s\n'%number)

    def cancel_download(self,number):
        self.lock.acquire() 
        self.tell('m %s c\n'%number)
        time.sleep(0.5)  #this prevents the temporary reapparition in the downloads list...
        self.lock.release() 

    def set_options(self):
        self.tell('in %s\n'%self.app.config['download'])
        self.tell('temp %s\n'%self.tempdir)
        self.tell('name circle_user_(http://thecircle.org.au)\n')
        #self.tell('verbose\n')
        #self.tell('asr\n')

    def vp (self):
        self.tell('vp\n')

    def vf (self):
        self.tell('vf\n')

    def help(self):
        self.tell('?\n')        

    def vd(self):
        self.tell('vd\n')

    def retrieve(self,key,pipe):
        self.tell('temp %s\n'%self.tempdir)
        self.key = key
        if self.running and self.connected: 
            self.tell('s %s\n'%self.key)
            pipe.start(donkey_retrieve_task,self)
        
    def tell(self,command):
        if self.running and self.pid != None:
            os.write(self.shell_master,command)

    def edonkey_menu(self,field,app,widget,ev):
        import gtk
        menu = []

        if self.connected:
            def disconnect(data,self=self):
                self.disconnect()
            menu.append(("Disconnect",disconnect))
            def view_message(data,self=self):
                utility.mainthread_call(self.app.chat.show,self.message)
            menu.append(("View greetings from server",view_message))
        else:
            if self.connecting:
                def retry(data,self=self):
                    self.disconnect()
                    time.sleep(0.1)
                    self.connect()
                menu.append(("Try another server",retry))
                def abort(data,self=self):
                    self.disconnect()
                    self.display_message( 'eDonkey client disconnected.\n','red')
                menu.append(("Abort connection",abort))
            else:
                def connect(data,self=self):
                    self.connect()
                menu.append(("Reconnect",connect))

        menuwidget = gtk.Menu()
        for (text, action) in menu:
            mi = gtk.MenuItem(text)
            mi.connect("activate", action)
            mi.show()
            menuwidget.append(mi)
        menuwidget.popup(None,None,None,ev.button,ev.time)

    def overnet_menu(self,field,app):
        import gtk
        menu = []

        def view_status(data,self=self):
            self.reading_status=1
            self.status=''
            time.sleep(0.05)
            self.tell('g\n')
            time.sleep(0.1)
            self.reading_status=0
            utility.mainthread_call(self.app.chat.show_after,self.chat_field,'overnet status : \n'+self.status)

        menu.append(("View status",view_status))

        def boot(data,_self=self):
            import gtk
            
            window = gtk.Window()
            window.set_border_width(10)        
            window.set_default_size(300,10)
            window.set_title(_('Connect to peer'))

            window.set_transient_for(_self.app.window)
            window.set_resizable(gtk.FALSE)

            vbox = gtk.VBox(gtk.FALSE, 5)
            window.add(vbox)

            label = widgets.Helpful_label(_('Address of overnet node to boot from.'),\
                                         _("In order to use Overnet for the first time, you need to enter the adress and port number of an active Overnet node. Example: 192.168.0.4:7893  Overnet nodes addresses can be found on the web, see for example http://members.lycos.co.uk/appbyhp/connect.html"))
            vbox.pack_start(label.packee(), gtk.FALSE, gtk.FALSE, 0)
        
            entry = gtk.Entry()
            vbox.pack_start(entry, gtk.FALSE,gtk.FALSE,0)

            hbox = gtk.HBox(gtk.FALSE,5)
            vbox.pack_end(hbox, gtk.FALSE,gtk.FALSE,0)

            button = gtk.Button(_("Cancel"))
            button.connect("clicked",\
                           lambda _b, _window=window: _window.destroy())
            button.set_flags(gtk.CAN_DEFAULT)
            hbox.pack_end(button, gtk.TRUE,gtk.TRUE,0)

            def greet(_b, _entry=entry, _window=window, _self=_self):
                _self.tell('boot %s\n'%widgets.get_utext(_entry).replace(':',' '))
                _window.destroy()
        
            button = gtk.Button(_("Connect"))
            button.connect("clicked",greet)
            button.set_flags(gtk.CAN_DEFAULT)
            hbox.pack_end(button, gtk.TRUE,gtk.TRUE,0)

            utility.show_window(window, 'greet')
            button.grab_default()
            
        menu.append(("Boot",boot))

        menuwidget = gtk.Menu()
        for (text, action) in menu:
            mi = gtk.MenuItem(text)
            mi.connect("activate", action)
            mi.show()
            menuwidget.append(mi)
        #menuwidget.popup(None,None,None,ev.button,ev.time)
        view_status(None,self)


def start():

    #this plug-in is broken-- return immediately
    return

    if sys.platform.find('linux')==-1:
        app.config['use_overnet'] = 0
        return

    if hasattr(app,'overnet') and app.overnet != None: 
        app.config['use_overnet'] = 0
        return    

    client_file = os.path.join(utility.config_dir,'overnet'+overnet_version)

    if not os.path.isfile(client_file):

        sem=threading.Semaphore()
        sem.acquire()
        utility.mainthread_call(app.dialog_install_file,'Install the Overnet client.', \
                                "The Overnet binary client was not found.\nIn order to connect to the Overnet network,\nyou need to have this file in your .circle directory.\nDo you want to download and install it now?",'If you click on \'Install\', a binary file will be downloaded from http://download.overnet.com/overnet'+overnet_version+'.tar.gz and installed it in your .circle directory. If you already have the overnet client, you may click on \'Cancel\' and to install it manually.  Note: The overnet client is not part of Circle, and it is proprietary software. Running malicious files from untrusted sources might damage your system. For more information about Overnet, visit http://www.overnet.com', 'use_overnet', sem)

        sem.acquire()
        sem.release()
        
        if not app.config['use_overnet']:
            app.overnet=None
            return
    
        utility.mainthread_call(app.chat.show,\
                                'Downloading the overnet client in '+client_file+' (this may take a while)...\n')
        try:
            import urllib
            urllib.urlretrieve('http://download.overnet.com/overnet'+overnet_version+'.tar.gz',\
                               client_file+'.tar.gz')
        except error.Error:
            utility.mainthread_call(app.chat.show,'Could not download the overnet client.\n')
            app.config['use_overnet']=0
            app.overnet=None
            return

        if os.path.isfile(client_file+'.tar.gz'):
            try:
                os.system('/bin/gunzip -f '+client_file+'.tar.gz')
                os.system('/bin/tar -x -C '+utility.config_dir+' -f '+client_file+'.tar')
                os.chmod(client_file,0755)
            except:
                pass

        # the flag might have changed while we downloaded
        if not app.config['use_overnet']:
            utility.mainthread_call(app.chat.show,\
                                    'Overnet client downloaded, I am not running it.\n')
            app.overnet=None
            return

        if not os.path.isfile(client_file):
            utility.mainthread_call(app.chat.show,'Could not download the overnet client.\n')
            app.config['use_overnet']=0
            app.overnet = None
            return

    def create_overnet(app=app):
        app.overnet = Donkey(app)
        app.overnet.start()
    utility.mainthread_call(create_overnet,app)



# vim: expandtab:shiftwidth=4 :
