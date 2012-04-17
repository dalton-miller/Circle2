# -*- coding: latin-1 -*-  
# note: the above line is necessary for unicode reasons

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

""" Utility functions and classes


    Task_managers:

      The Circle application is divided into a number of objects that
      handle specific aspects of its operation: maintaining the hashtable,
      serving files, maintaining the contact list, etc. There are also some
      more transient objects, such as for downloading files or retrieving
      from the hashtable. These are all "Task_managers".

      A Task_manager is an object that is responsible for a particular
      job. In doing this it might need to start several threads (called
      Tasks). It may also run a polling function regularly (eg to maintain
      an up to date list of files in the file_server).	The polling
      function is run as a separate task (not the main thread).

      Most Tasks are transient. That is, they do a particular job then
      go away.

      Task_managers are a subclass of Synchronous. Synchronous just
      provides a lock object. This lock is used internally by the task
      manager to provide locking.  (Some code also uses the lock from
      the outside, this is bad and should be phased out)

    Typical task manager:

        def my_manager_thingy_task(self, blarg):
	    # do something

	class My_manager(Task_manager):
	    def start(self):
		Task_manager.start(self)

		# set up some stuff
		self.start_poller(60,    60*60, my_poll_function, self)
                #   initial_interval, interval,             func, *param
            
	    def stop(self):
		# shut down some stuff
		
		Task_manager.stop(self)

            def thingy(self, blarg):
	        Task(my_manager_thingy_task, self, blarg).start()

        ...
        my_manager = My_manager()
	my_manager.start()

	# do some stuff

	my_manager.stop()
       


    Notes on threading:

        <please document>


    """

from __future__ import generators
import sys, os, threading, string, cPickle, time, traceback, pprint, socket, random, Queue
import types, re

import check
import error
import settings, safe_pickle
import __init__
if hasattr(settings, '_'):
    from settings import _


daemon_action_lock = threading.RLock()
daemon_action_list = [ ]
# Each element is (time:float, func:is_callable, paramlist, t_plus:float).

# lightweight threads
# each element is (time:float, thread:generator)
thread_list = [ ]
thread_lock = threading.RLock()

chat_obj=None

def report_bug(type,value,tb):
    """report the traceback to a channel"""
    traceback.print_exception(type,value,tb)
    try:
        tr = traceback.format_exception(type,value,tb)
        if chat_obj and chat_obj.app.config['report_bugs']:
            str= string.join(tr)
            str = '\nCircle version ' + __init__.__version__+', on '+sys.platform+', python '+ sys.version + '\n'+str
            chat_obj.show('A crash occured, reporting to #traceback.\n')
            chat_obj.send_message(['#traceback'],str)
    except:
        print "could not report bug"
        

def _daemon_action_timeout(called_from_idle = 1):
    """ (internal) Check for and run any pending actions. """

    while 1:
        daemon_action_lock.acquire()
        try:
            if not daemon_action_list or daemon_action_list[0][0] > time.time():
                break
            head = daemon_action_list.pop(0)
        finally:
            daemon_action_lock.release()
        try:
            if apply(head[1],head[2]):
                apply(schedule_mainthread, (head[3], head[1]) + head[2])
        except:
            apply(report_bug,sys.exc_info())
            
    while 1:
        thread_lock.acquire()
        try:
            if not thread_list or thread_list[0][0] > time.time():
                break
            item = thread_list.pop(0)
            thread = item[1]
            stack = item[2]
        finally:
            thread_lock.release()
        try:
            start_thread(thread,stack)
        except:
            apply(report_bug,sys.exc_info())
    
    return 1



def schedule_mainthread(t_plus, func, *parameters):
    """ Schedule an action: 
    after t_plus milliseconds, func will be called in the main thread with
    the parameters given. 
                
    If func returns true, it will be called again after another t_plus
    milliseconds"""
    check.check_has_type(t_plus, types.FloatType)
    check.check_is_callable(func)
    
    daemon_action_lock.acquire()
    try:
        new_time = time.time() + t_plus/1000.0
        action_item = (new_time,
                       func,
                       parameters,
                       t_plus)

        pos = bisect(daemon_action_list,
                     lambda elem, new_time=new_time: new_time < elem[0])
        
        daemon_action_list.insert(pos, action_item)
    finally:
        daemon_action_lock.release()


def start_thread(thread,stack=None):    
    """
    Start a lightweight thread using a generator.
    The stack of calling threads is passed as an argument
    
    There are different types of 'yield':
    
    yield 'sleep', n            : thread will resume in n seconds
    yield 'wait', func          : thread will yield until func returns
    yield 'call', (node,ticket) : rpc call. thread will yield until the reply is available
    yield 'wake'                : currently not used
    
    """

    try:
        type,params = thread.next()
    except StopIteration:
        if stack:
            father = stack[0]
            try:
                father_stack = stack[1:]
            except:
                father_stack = None
            start_thread(father,father_stack)
        return
    #except SystemError,err:
    #    print "System Error",err,thread,stack
    #    return
    #except:
    #    print "other exception",thread,stack
    #    return

    if type == 'sleep':
        sleep_time = params
        new_time = time.time() + sleep_time
        item = (new_time, thread, stack)
        pos = bisect(thread_list,lambda elem, new_time=new_time: new_time < elem[0])
        thread_list.insert(pos, item)
        
    elif type == 'call':
        node, ticket = params
        node.calling_threads[ticket]=(thread,stack)
        start_thread(node.pending_calls[ticket])

    elif type== 'wait':
        child = params
        if stack:
            child_stack = (thread,) + stack
        else:
            child_stack = (thread,)
        start_thread(child,child_stack)

    elif type == 'wake':
        node, state = params
        state.wake_queuers(node)

    else:
        raise error.Error('unknown yield type %s'%type)



# queue: processes wait for access to a ressource
#
#


def bisect(a, too_high):
    """Return the first index i in a such that too_high(a[i]) is true; or
       len(a) if too_high(x) is true for all elements x in a.

       The usual use for this function is deciding where to insert element;
       e.g. my_list.insert(bisect(my_list, lambda elem,x=x: x < elem), x)

       Requires: a is monotonic non-decreasing in the truth of too_high;
       i.e. exists[pos] ((all[j in [0, pos)] not too_high(a[j]))
                         and all[j in [pos, len(a))] too_high(a[j])).
       Put another way:
       all[(i,j) s.t. i <= j] too_high(a[i]) implies too_high(a[j]).

       Note that this more or less requires that neither a nor too_high change
       during execution (say due to writes from another thread).
       
       Ensures: The return value equals pos above.  I.e.:
             (all[j in [0, ret)]      not too_high(a[j]))
         and (all[j in [ret, len(a))] too_high(a[j])).
    """
    check.check_has_type(a, types.ListType)
    check.check_is_callable(too_high)
    
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo+hi) >> 1
        if too_high(a[mid]):
            hi = mid
        else:
            lo = mid+1

    check.check_assertion((0 <= lo) and (lo <= len(a)))
    ## Check sortedness:
    #for elem in a[:lo]:
    #    if too_high(elem):
    #        check.show_bug('utility.bisect: unsorted input list (or bug in bisect code)')
    #for elem in a[lo:]:
    #    if not too_high(elem):
    #        check.show_bug('utility.bisect: unsorted input list (or bug in bisect code)')
    
    return lo


def mainthread_call(func,*parameters):
    """ Do an action as soon as possible. """
    apply(schedule_mainthread, (0.0, func) + parameters)



# so long for the threading stuff
###########################################################################
    

def rand_from_time():
    import struct
    
    str = struct.pack('d',time.time())
    value = 0
    for char in str:
        value = value ^ ord(char)
    return chr(value)



def check_and_demangle_item(item):
    """Return demangled item if it is a valid mangled item,
       otherwise throw an exception (not necessarily of class error.Error).
       Ensures: either an exception is thrown or ret is a dictionary
       whose keys include 'type'."""

    # note: not sure if this ough to be here...

    import crypto.RSA
    import hash
    import safe_pickle

    item_type = item['type']
    if item_type == 'identity offline demangled':
        raise error.Error('impostor')
    
    elif item_type == 'identity offline':
        demangle = safe_pickle.loads(item['package'])
        if not crypto.RSA.construct(demangle['key']).verify(
            hash.hash_of(item['package']),item['signature']):
            raise error.Error('bad signature')

        demangle['type'] = 'identity offline demangled'
        return demangle
    else:
        return item




# popen has some weird interaction with threads or something
# A small delay seems to fix it (but it would be nice to know what the problem is!)

def popen(*args, **kwargs):
    result = os.popen(*args, **kwargs)
    time.sleep(0.5)

    return result


def is_subdir(path1,path2):
    # is path1 a subdirectory of path2?
    # (path2 is shorter...)
    
    if sys.platform.find('win') >= 0:
        sep='\\'
    else:
        sep='/'
    
    p1=path1.split(sep)
    while '' in p1:
        p1.remove('')
    p2=path2.split(sep)
    while '' in p2:
        p2.remove('')
    if len(p2)>len(p1):
        return 0
    for i in range(len(p2)):
        if p1[i] != p2[i]:
            return 0
    return 1



# Unicode
# TODO: is there a preferred system encoding?

def force_unicode(str):
    """ Make a string unicode, if not already. """
    
    if type(str) == type(''):
        return unicode(str,settings.terminal_encoding,'replace')
    else:
        return str

def force_string(str):
    """ Make a string just a string, if not already. """
    
    if type(str) == type(u''):
        return str.encode(settings.terminal_encoding,'replace')
    else:
        return str


def remove_accents(s):
    """ remove accents from a string
        this is in order to generate keys
    """
    s = force_unicode(s)
    s=string.replace(s,u'á','a') 
    s=string.replace(s,u'à','a') 
    s=string.replace(s,u'â','a') 
    s=string.replace(s,u'ä','a') 
    s=string.replace(s,u'é','e') 
    s=string.replace(s,u'è','e') 
    s=string.replace(s,u'ê','e') 
    s=string.replace(s,u'í','i') 
    s=string.replace(s,u'ì','i') 
    s=string.replace(s,u'î','i') 
    s=string.replace(s,u'ú','u') 
    s=string.replace(s,u'û','u') 
    s=string.replace(s,u'ù','u') 
    s=string.replace(s,u'ü','u') 
    s=string.replace(s,u'ó','o') 
    s=string.replace(s,u'ò','o') 
    s=string.replace(s,u'ö','o') 
    s=string.replace(s,u'ô','o') 
    s=string.replace(s,u'ß','ss') 

    return s

def complete(prefix,list):
    """auto-completion for nicknames"""
    completions = []
    root = prefix
    for item in list:
        if item.find(prefix) == 0 :
            completions.append(item)
    if completions:
        root=completions[0]
        for i in range(len(root)):
            for item in completions[1:]:
                if root[:i+1] != item[:i+1]:
                    root=root[:i]
                    break

    return (root, completions)




# Lists

def split_list(str):
    """ Split a comma or space separated string. """

    return string.split(string.replace(str,',',' '))

# Alerts

def beep():
    """ Produce a beep. """

    if sys.platform == 'win32':
        import winsound
        winsound.PlaySound('SystemAsterisk',winsound.SND_ALIAS | winsound.SND_ASYNC)
    elif settings.gtk_loaded():
        import gtk
        gtk.gdk.beep()
    else:
        sys.stdout.write(chr(7))
        sys.stdout.flush()

# DNS queries

def hostname_of_ip(ip):
    """ Perform a DNS lookup on an IP address. """

    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.error:
        return ip

# URL viewing

original_directory = os.getcwd()
gnome_initted = 0

def find_file(filename):
    full_filename = os.path.join(
       original_directory, 
       os.path.dirname(__file__),
       filename)

    if not os.path.isfile(full_filename):
        raise error.Error('File does not exist.')

    return full_filename

def browse_url(url):
    global gnome_initted

    if sys.platform == 'win32':
        try:
            import webbrowser
            webbrowser.open_new(url)
        except:
            raise error.Error('Opening a browser failed.')
    elif settings.gtk_loaded():
        try:
            import gnome
        except:
            gnome = None

        if gnome and not gnome_initted:
            gnome.program_init('circle',__init__.__version__)
            gnome_initted = 1

        if gnome:
            gnome.url_show(url)
        else:
            if not os.fork():
                try:
                    os.execlp('gnome-moz-remote','gnome-moz-remote','--newwin',url)
                except:
                    try:
                        os.execlp('mozilla','mozilla',url)
                    except:
                        raise error.Error('Opening a browser failed.')
    else:
        try:
            #if not os.fork():
                #os.execlp('lynx','lynx',url)
            os.system("lynx "+quote_for_shell(url))
        except:
            raise error.Error('Opening a browser failed.')


def browse_file(file,section=''):
    browse_url('file://'+find_file(file)+section)

def play_file(filename):
    extension = string.split(filename, ".")[-1]
    lext = string.lower(extension)

    if lext in ['html', 'htm']:
        browse_file(filename)

    elif lext in ['pdf']:
        if not os.fork():
            os.execlp('xpdf','xpdf',filename)

    
    

# pydoc

pydoc_url = None

def browse_modules():
    class Server(threading.Thread):
        def run(self):
            global pydoc_url
            try:
                import pydoc
            except:
                pydoc_url = -1
                return

            def ready(server):
                global pydoc_url
                pydoc_url = server.url
            for i in xrange(1024,65535):
                try:
                    pydoc.serve(i,ready)
                    break
                except:
                    pass
            else:
                pydoc_url = -1

    if not pydoc_url:
        server = Server()
        server.setDaemon(1)
        server.start()

    while not pydoc_url:
        time.sleep(0.5)
                
    if not type(pydoc_url) == type(''):
        raise error.Error("Could not start pydoc server.")

    browse_url(pydoc_url+'circlelib') 


# Synchronized access objects

class Hold:
    """ Object that holds a lock while it exists.

        eg

        def my_func():
          H = Hold(lock)
          do some stuff
          # Lock is automagically released when function exits

        Caveats: do not use if your function could raise an error
                 without a finally: del S,
                 the Hold survives in the traceback.
    """

    def __init__(self, lock):
        self._lock = lock
        lock.acquire()

    def __del__(self):
        # Lock may have been free'd before holder
        # or even threading lock may have been free'd before threads RLock
        try:
            self._lock.release()
        except:
            pass

class Synchronous:
    """ Synchronized access objects"""
    def __init__(self):
        self.lock = threading.RLock()

        # RLock allows a given thread to acquire the lock multiple times,
        # so we use a stack rather than a single string.
        self.lock_acquired_by = [ ]

    def is_locked_by_this_thread(self):
        return self.lock._is_owned()
    
    def sync(self):
        """create a Hold on the lock
        
           Caveat: do not use for sections that might raise an error,
                   without a finally: del S
        """
        return Hold(self.lock)

    def syncly(self, func, *args, **kwargs):
        """call a function while holding the lock

           eg
             still_running = self.syncly(lambda: self.running)
        """
        S = self.sync()
        return func(*args, **kwargs)
    
    def acquire_lock(self, acquirer_name):
        """acquirer_name is an arbitrary object (typically a string), intended
           to be useful for debugging."""
        
        self.lock.acquire()
        self.lock_acquired_by.append(acquirer_name)

    def release_lock(self, acquirer_name):
        """acquirer_name should be equal to the value passed in the
           corresponding acquire_lock call."""
        
        check.check_assertion(self.lock_acquired_by != [])
        
        curr_acquirer = self.lock_acquired_by.pop()
        check.check_assertion(acquirer_name == curr_acquirer)
        self.lock.release()

# Task Management

task_lock = threading.RLock()
task_count = 0
pending_task_queue = Queue.Queue(0)
pending_low_priority_task_queue = Queue.Queue(0)


class Task(threading.Thread):
    def __init__(self, function, manager, *parameters):
        self.function = function
        self.manager = manager
        self.parameters = parameters

	self.pid = None
        
        threading.Thread.__init__(self)

        self.setDaemon(1)

    def __repr__(self):
        if not self.function:
            return '<Task (completed)>'
        else:
            return '<Task '+`self.pid`+' '+self.function.__name__+' '+`self.parameters`+'>'

    def start_no_overload(self, low_priority = 0):
        global task_count

        self.include_in_count = 1

        self.manager.lock.acquire()

        #if len(self.manager.tasks) >= max_task_manager_threads:
        #if threading.activeCount() >= max_active_threads:
        if task_count >= settings.max_active_threads:
            self.manager.task_queue.put(1) #(self)
            if low_priority:
                pending_low_priority_task_queue.put(self)
            else:
                pending_task_queue.put(self)
            self.manager.lock.release()
            return
        
        self.manager.tasks.append(self)
        self.manager.lock.release()

        task_lock.acquire()
        task_count = task_count + 1
        task_lock.release()

        threading.Thread.start(self)

    def start(self, include_in_count=1):
        global task_count

        self.include_in_count = include_in_count
        
        self.manager.lock.acquire()
        self.manager.tasks.append(self)
        self.manager.lock.release()

        if include_in_count:
            task_lock.acquire()
            task_count = task_count + 1
            task_lock.release()

        threading.Thread.start(self)

    def run(self):
        global task_count

	self.pid = os.getpid()

        try:
            try:
                apply(self.function,(self.manager,) + self.parameters)
            except:
                apply(report_bug,sys.exc_info())
        
            if not self.include_in_count:
                return

            self.manager.lock.acquire()
            try:
                self.manager.tasks.remove(self)

                #if threading.activeCount() > max_active_threads:
                if task_count > settings.max_active_threads:
                    task_lock.acquire()
                    task_count = task_count - 1
                    task_lock.release()
                    return

                try:
                    #got = self.manager.task_queue.get(0)
                    got = pending_task_queue.get(0)
                except Queue.Empty:
                    try:
                        got = pending_low_priority_task_queue.get(0)
                    except Queue.Empty:
                        task_lock.acquire()
                        task_count = task_count - 1
                        task_lock.release()
                        return
            finally:
                self.manager.lock.release()

            got.manager.lock.acquire()
            got.manager.tasks.append(got)
            got.manager.task_queue.get(0)
            got.manager.lock.release()

            threading.Thread.start(got)

        finally:
            self.function = None
            self.parameters = None
            self.manager = None



class Task_manager(Synchronous):
    def __init__(self):
        Synchronous.__init__(self)
        self.tasks   = [ ]
        self.task_queue = Queue.Queue(0)
        self.running = 0
        self.thread_activity = ''
        self.activity_start_time = 0.0
    
    def start(self):
        S = self.sync()
        self.running = 1

    def stop(self, fast=0):
        #self.change_activity('clearing running flag')
        S = self.sync()
        self.running = 0
        del S
        self.change_activity('')

        if fast:
            return

        #self.change_activity('waiting on tasks')
        while 1:
            while not self.task_queue.empty():
                time.sleep(0.5)

            S = self.sync()
            if len(self.tasks):
                head = self.tasks[0]
            else:
                head = None
            del S

            if not head: 
                break

            head.join()
            
            # In case it died
            S = self.sync()
            if head in self.tasks:
                self.tasks.remove(head)
            del S
        #self.change_activity('')

    def change_activity(self, msg):
        check.check_has_type(msg, types.StringType)

        #if msg:
        #    print msg
        now_time = time.time()
        if self.thread_activity:
            durn = int(now_time - self.activity_start_time)
            if durn >= 60:
                print self, 'Activity took %d seconds: %s' % (durn, self.thread_activity)
        
        self.thread_activity = msg
        self.activity_start_time = now_time
    


# Pipe task

class Pipe:
    def __init__(self):
        self.queue = [ ]
        self.threads = 0

    def start(self,function,*parameters):
        self.running = 1
        apply(function,(self,)+parameters)
        
    def stop(self):
        self.running = 0

    def finished(self):
        return self.queue == [ ] and self.threads == 0

    def write(self, item):
        self.queue.append(item)

    def read_all(self):
        try:
            return self.queue
        finally:
            # pjm: This looks like a dodgy hack; shouldn't we at least
            # return [ ] for this case?
            # (Or indeed initialize self.queue to [ ] in the constructor.)
            self.queue = [ ]

    def read_until_finished(self):
        """ Read pipe until finished, then stop pipe.
        used only by circled get and circleget.  """

        list = [ ]
        while not self.finished():
            list.extend(self.read_all())
            time.sleep(1.0)
        self.stop()

        return list

# Config files

if sys.platform == 'win32':
    config_dir = os.path.abspath(
        os.path.join(os.getenv('USERPROFILE',''),
	'circle_config')
    )
else:
    if os.environ.get('USER',os.environ.get('LOGNAME','root')) == 'root':
        config_dir = '/etc/circle'
    else:
        config_dir = os.path.join(os.environ['HOME'], '.circle')

if not os.path.isdir(config_dir):
    os.mkdir(config_dir, 0700)

def get_checked_config(name, tmpl, default):
    """Ensures @E13: (ret is default) or check.matches(ret, tmpl)."""
    check.check_has_type(name, types.StringType)
    check.check_is_template(tmpl)
    
    try:
        ret = try_get_config(name)
    except:
        return default
    if not check.matches(ret, tmpl):
        print (_("Garbled config file `%s'; expecting something matching template `%s'.")
               % (name, str(tmpl)))
        ret = default
    
    if ret is not default: check.check_matches(ret, tmpl)
    return ret

def get_config(name, default):
    try:
        ret = try_get_config(name)
    except:
        ret = default
    return ret

def try_get_config(name):
    file_name = os.path.join(config_dir, name)
    os.chmod(file_name, 0600) # Only rw by user

    file = open(file_name,"rt")
    contents = file.read()
    file.close()

    try:
        return eval(contents)
    except:
        # Might be an old style config file
        return cPickle.loads(contents)

def set_config(name, value, fast=0):
    """ Write a config file.

            Writes to a new file then moves it, in order to ensure config files can
            not be corrupted."""
    file_name = os.path.join(config_dir,name)

    file = open(file_name+'.new','wt')
    # Note: there is a window of opportunity between open and chmod,
    # but we don't really care given that the config_dir is created with
    # mode 0700.
    try:
        os.chmod(file_name+'.new', 0600) # Only rw by user
    except OSError:
        pass

    #cPickle.dump(value, file, 1)    
    if fast:
        file.write(repr(value))
    else:
        pprint.pprint(value, file)
    file.close()

    try:
        if os.path.isfile(file_name):
            os.unlink(file_name)
        os.rename(file_name+'.new',file_name)
    except OSError:
        pass

# Random bytes

def random_bytes(n):
    """ Make some random bytes, preferably of cryptographic quality.

            This function is used to generate random bytes for challenges
            and for the node's address in the circle.  It would be
            preferable to have a urandom equivalent for windows, but
            alas...

            Ensures @E14: (type(ret) == types.StringType)
            and (len(ret) == n)."""
    check.check_has_type(n, types.IntType)
    check.check_assertion(n >= 0)  #=@R27

    ret = ''
    if n != 0:
        try:
            file = open('/dev/urandom','rb')
            ret = file.read(n)
            file.close()
        except IOError:
            pass
        for i in range(n - len(ret)):
            ret = ret + chr(random.randrange(256))
    
    check.check_postcondition((type(ret) == types.StringType)
                              and (len(ret) == n), '@E14')
    return ret

# Describe a number of bytes in readable form

def human_size(n):
    """ Return a logarithm scaled n for humans to understand information sizes."""

    # While KiB, etc are technically correct, more people are familiar with KB, etc.
    # (Use KiB etc. where context makes the meaning clear.)
    
    if n < 1<<10:
        return "%d bytes" % n
    elif n < 1<<20:
        return "%.1fKB" % (n/float(1<<10))
    elif n < 1<<30:
        return "%.1fMB" % (n/float(1<<20))
    elif n < 1L<<40:
        return "%.1fGB" % (n/float(1<<30))
    else:
        return "%.1fTB" % (n/(2.0**40))


def english_list(list):
    if len(list) == 1:
        return list[0]
    else:
        return string.join(list[:-1],', ')+' and '+list[-1]



def parse_keywords(list):
    """parses a list of keywords"""
    keywords=[]
    anti_keywords=[]
    for item in list:
        if item[0:1]=='!':
            anti_keywords.append(item[1:])
        else:
            keywords.append(item)
    largest=''
    if keywords:
        for item in keywords:
            if len(item) > len(largest):
                largest = item
    if keywords:
        if anti_keywords:
            title=english_list(keywords).replace(' and',',')+' and not '\
                   +english_list(anti_keywords).replace(' and',',')
        else:
            title=english_list(keywords)
    else:
        title=''
    return largest,keywords,anti_keywords,title



# Set terminal properties

def stdin_echo(on):
    """ Set character echo on the terminal on or off (used in chat text mode). """

    import termios

    # TERMIOS deprecated in 2.x series
    try:
        termios.ECHO
        TERMIOS = termios
    except:
        import TERMIOS

    new = termios.tcgetattr(0)
    if on:
        new[3] = new[3] | TERMIOS.ECHO | TERMIOS.ICANON
    else:
        new[3] = new[3] & ~TERMIOS.ECHO & ~TERMIOS.ICANON
    termios.tcsetattr(0, TERMIOS.TCSADRAIN, new)
 

# Quoting for the shell

def quote_for_shell(str):
    str = string.replace(str,'\\','\\\\')
    str = string.replace(str,'$','\\$')
    str = string.replace(str,'"','\\"')
    return '"'+string.replace(str,'`','\\`')+'"'

def parse_address(local_address, str):
    check.check_is_af_inet_address(local_address)  #=@R19
    
    try:
        match = re.match(r"\s*(.+)\s*:\s*([0-9]+)\s*$", str)
        if match:
            ret = (socket.gethostbyname(match.group(1)),
                   string.atoi(match.group(2)))
        else:
            match = re.match(r"\s*([0-9]+)\s*$", str)
            if match:
                ret = (local_address[0],
                       string.atoi(match.group(1)))
            else:
                ret = (socket.gethostbyname(string.strip(str)),
                       settings.default_ports[0])
        
        check.check_is_af_inet_address(ret)  #=@E9
        # Proof: socket.gethostbyname returns a string, atoi returns an int,
        # settings.default_ports is a non-empty list of integers.
        # local_address is itself an af_inet_address (@R19), so its first
        # element is a string suitable for an af_inet_address.  local_address
        # is deeply immutable from @E11.
        return ret

    except:
        raise error.Error(_("Could not find peer.\n"+\
                            "Please give a valid IP address or machine name,\n"+\
                            "optionally followed by a colon and a port number"))

# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
