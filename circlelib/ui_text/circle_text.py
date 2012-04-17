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
   Circle text interface
   runs in a separate thread.
   
"""

import os, sys, threading, time, traceback, string
import math, types, socket, random, select

from circlelib import check, error, hash, node, settings, utility, __init__


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




class Random_dev:
    """This is something of a hack.  Version 1.22 for a version
       that's differently bad.  For the moment I've simply commented
       out all the bits that are specific to gtk/text, choosing instead
       not to tell the user anything, and do blocking I/O.  Instead,
       should use non-blocking I/O, and update the progress indication
       between reads."""
    def __init__(self, ignored_input, ingnored_output):
        flags = os.O_RDONLY;
        #flags = flags | os.O_NONBLOCK
        # Uncomment the below if you think there might be a system that has
        # something like /dev/random and a non-zero os.O_BINARY value.
        # (Unfortunately, Python2.1 on Unix doesn't even define O_BINARY as zero,
        # which is why it must be in a try block.)
        #try:
        #    flags = flags | os.O_BINARY
        #except:
        #    pass
        self.fildes = os.open(dev_random_path, flags)
        self.buffer = ''
        #self.tag = gtk.input_add(self.file, 1, self.callback)
    
    #def callback(self, a,b):
    #    bytes = os.read(self.file.fileno(), self.needed_len - len(self.buffer))
    #    self.buffer = self.buffer + bytes
    
    def finish(self):
        #gtk.input_remove(self.tag)
        #self.file.close()
        os.close(self.fildes)
    
    def randfunc(self, n):
        """Return a random string of n bytes (sic: not bits)."""
        check.check_has_type(n, types.IntType)
        
        str = curr = os.read(self.fildes, n)
        remaining = n - len(str)
        shown = 0
        while remaining >= 0 and curr != '':
            if not shown:
                #utility.stdin_echo(0)
                print (_("Stalled while reading from %s; please generate some\n"
                         + "randomness by moving the mouse around (assuming you're\n"
                         + "running Circle locally) or typing randomly at the keyboard.")
                       % dev_random_path)
                shown = 1
            curr = os.read(self.fildes, remaining)
            str += curr
            remaining -= len(curr)
        if shown:
            #utility.stdin_echo(1)
            print _("\n\nHave enough randomness now, thanks.\n")
        check.check_assertion(remaining == 0)
        # If the above fails then either the random device is behaving
        # strangely (randomly?), or there's a bug in this code.
        # Either way, we'd prefer to die with check_assertion (and hopefully
        # have the bug reported) than silently continue with a broken
        # random number generation for cryptography.
        check.check_assertion(len(str) == n)
        return str
        
        #self.needed_len = n
        #self.progress_label.set_text('Please bang on the keyboard like a monkey.')
        #while len(self.buffer) < n:
        #    self.progress.update(float(len(self.buffer))/n)
        #    gtk.mainiteration()
        #
        #try:
        #    return self.buffer[:n]
        #finally:
        #    self.buffer = self.buffer[n:]
        #    self.progress_label.set_text('Calculating...')
        #    self.progress.update(1.0)
        #    while gtk.events_pending():
        #        gtk.mainiteration()





class Random_text:
    def __init__(self, input, output, ignore=None):
        self.input = input
        self.output = output
        self.output.write('Some random data is needed to generate a cryptographic identity for you.\n')

    def finish(self):
        self.output.write("\r"+_("Done.")+
                (" "*len(_("Please bang on the keyboard like a monkey.")))+"\n")
        self.output.flush()

    def randfunc(self, n):
        buffer = ''
        self.output.write("\r"+_("Please bang on the keyboard like a monkey."))
        self.output.flush()
        while select.select([self.input],[ ],[ ],0)[0]:
            self.input.read(1)

        while len(buffer) < n:
            self.input.read(1)
            buffer = buffer + utility.rand_from_time()
        
        while select.select([self.input],[ ],[ ],0)[0]:
            self.input.read(1)

        self.output.write("\r"+ _("Calculating...") +
                (" "*len(_("Please bang on the keyboard like a monkey."))))
        self.output.flush()
        return buffer

# Filename to check for cryptography-quality random device.
dev_random_path = "/dev/random"
# Select Random class.
have_dev_random = 0
try:
    if os.access(dev_random_path, os.R_OK) \
       and stat.S_ISCHR(os.stat(dev_random_path)[stat.ST_MODE]):
        have_dev_random = 1
except:
    pass
    
if have_dev_random:
    Random = Random_dev
else:
    Random = Random_text




class Circle_text:

    config_keys = [
        ('name', 'username'),
        ('human-name', 'name'),
        ('description', 'finger')
    ]

    def __init__(self,daemon,input,output):
    
        self.config = utility.get_config("configuration", { })
        self.running = 1
        self.daemon = daemon
        self.open_windows = [ ]

        self.input = input
        self.output = output
        #self.connection = connection

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
                     ('local_files_color',(41120,8224,61680)),
                     ('quiet_color',(26727, 44310, 14828)),
                     ('beep_on_message', 1),
                     ('show_tips', 1),
                     ('show_gossip', 1),
                     ('auto_list_channels', 1),
                     ('augmented_text', 0)]:
            if not self.config.has_key(pair[0]):
                self.config[pair[0]] = pair[1]

        self.config_dialog_open = 0



    def run_main(self):

        #if not no_connect and \
        #   ( proxy_mode == 'always' or \
        #     (proxy_mode == 'auto' and node.need_proxy()) ):
        #    print _("Circle needs to run a proxy (see documentation).")
        #    print
        #    print _("SSH to where (username@machine.name)? "),
        #    proxy_host = sys.stdin.readline().strip()
        #else:
        #    proxy_host = None

        from circlelib import cache, channels, name_server, file_server
        import chat_text

        self.node        = self.daemon.node
        self.cache       = self.daemon.cache
        self.file_server = self.daemon.file_server
        
        self.name_server = name_server.Name_server(self,self.node,lambda : Random(self.input,self.output))
        self.chat = chat_text.Chat_text(self)
        self.channels = channels.Channels(self)
        self.gossip = None

        try:
            self.name_server.set_name(
                self.config['name'],
                self.config['human-name'],
                self.config['description'])
        except error.Error, err:
            print err.message
            return

        #if not self.node.is_connected():
        #    print _("Couldn't find any peers, exiting.")
        #    return

        # signals work only in main thread
        # this has to be done by the caller
        #def signal_handler(signal, frame): 
        #    raise error.Error(_('Signal %d received, exiting.') % signal)
        #def sigint_handler(signal, frame):
        #    raise error.Error('sigint')        
        #for s in exit_signals:
        #    signal.signal(s, signal_handler)
        #if s:
        #    signal.signal(signal.SIGINT, sigint_handler)
        
        self.quit_message = None        
        self.output.write( _('Type /help for instructions.\n'))

        def monitor(str, self=self): 
            pass #self.chat.show(str+'\n')
        
        self.name_server.start(monitor)
        self.channels.start()
        self.chat.start()
        self.chat.do('/listen')
        #self.chat.do('/who')

        while 1:
            try:
                self.chat.text_mainloop()
            except error.Error, err:
                if err.message == 'sigint':
                    if self.chat.command_text or self.chat.command_text_lines:
                        continue
                else:
                    self.chat.show('\n\n'+err.message+'\n\n')            
            except IOError:
                pass
            break

        self.chat.show('Disconnecting...')
        self.chat.stop()
        self.channels.stop()
        self.name_server.stop(self.quit_message)

        # Saving the configuration may seem pointless given that we
        # don't currently allow changing self.config in text mode
        # (AFAIK), but it at least ensures that a suitable template
        # file is created that the user can later edit with a text
        # editor.
        utility.set_config("configuration", self.config)
        self.output.write(_("Text interface stopped."))
        self.output.flush()


    def shutdown(self, message=None, continue_running=0):
        """ This only sets the running flag to 0.
            update will trigger the shutdown in the gtk thread.
            This can be called from any thread.
        """
        check.check_is_opt_text(message)
        self.continue_running = continue_running
        self.quit_message = message
        self.running = 0


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


    def refresh_userlist(self):
        return






# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
