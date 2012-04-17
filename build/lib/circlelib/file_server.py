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

    File_server

    Note about unicode:
    
    filenames are not converted to unicode because we need to access the file
    all the rest is converted to unicode


    Note about files and flags:
    
    files that are not published do not have a 'name'
    ('name' referes to the md5 hash)
    files that do not have a 'name' must
    have a 'local_path' in order to be accessed
    local_path means that they are local (i.e. on 127.0.0.1)
    when I list a users's files, he hashes them and provide a 'name'


    Note: the overnet code is broken

    Todo: file transfers : use TCP rather than UDP

"""

from __future__ import generators
import os,sys,threading,md5,string,time
import types, os
from settings import *
from error import Error
import os

import mp3, check, utility, hash

# Flags for file scan
# flags_local is for when I list my own files (no hash)
# flags_fast is for when I list somebody's files

flags_full    = { 'keywords':1, 'filename':1, 'name':1, 'mime':1, 'local':0,
                  'subdirectories':1, 'max':None }
flags_deb     = { 'keywords':0, 'filename':0, 'name':1, 'mime':0, 'local':0,
                  'subdirectories':0, 'max':100 }
flags_fast    = { 'keywords':0, 'filename':1, 'name':1, 'mime':0, 'local':0,
                  'subdirectories':1, 'max':None }
flags_local   = { 'keywords':0, 'filename':1, 'name':0, 'mime':0, 'local':1,
                  'subdirectories':1, 'max':None }

# File access locking

files_locked = [ ]
files_locked_lock = threading.RLock()

sources_locked = [ ]
sources_locked_lock = threading.RLock()

def acquire_file_lock(filename,for_writing=0):
    files_locked_lock.acquire()
    try:
        filename = os.path.abspath(filename)
        if for_writing and os.path.exists(filename): 
            return 0

        try:
            if filename in files_locked:
                #print 'already locked:',filename
                return 0
        except:
            print 'error',filename, files_locked

        files_locked.append(filename)
        return 1
    finally:
        files_locked_lock.release()

def release_file_lock(filename):
    files_locked_lock.acquire()
    try:
        filename = os.path.abspath(filename)
        files_locked.remove(filename)
    finally:
        files_locked_lock.release()

# Downloading files

def circle_downloader_thread(dl):
    try:
        while 1:            
            position, length = dl.get_ticket()

            while 1:
                try:
                    link = dl.get_link()
                except Error:
                    return

                if not link:
                    yield 'sleep',2
                    continue
 
                try:
                    ticket, template, wait = dl.node.call(
                        link, ('download chunk',dl.data['name'],position,length))
                    if wait: yield 'call',(dl.node,ticket)
                    str = dl.node.get_reply(ticket, template)
                except Error, err:
                    if err.message == 'access denied':
                        dl.access_denied = 1
                    dl.link_failed(link)
                    continue
                break

            dl.link_succeeded(link)
 
            dl.lock.acquire()
            dl.chunks[position] = str
            dl.bytes_downloaded = dl.bytes_downloaded + length

            running = dl.running
            dl.lock.release()

            if not running:
                break
    except Error: 
        pass
 
def circle_downloader_refresh_sources_thread(self):
    check.check_isinstance(self, Downloader)    
    wait_time = 60
    while 1:
        pipe = self.node.retrieve(self.data['name'],1,1)

        list = [ ]
        while 1:
            list.extend(pipe.read_all())
            if pipe.finished():
                break
            if not self.running:
                return
            yield 'sleep',1
            
        pipe.stop()
        
        for item in list:
            if item not in self.links:
                self.links.append(item)

        self.lock_sources()
        
        for i in xrange(wait_time):
            if not self.running:
                return
            yield 'sleep',1

        wait_time = wait_time+60
        
 
class Downloader(utility.Task_manager):
    def __init__(self, data, directory):

        utility.Task_manager.__init__(self)
        self.data = data
        self.directory = directory
        self.bytes_downloaded = 0L
        self.comment = ''
        self.remaining_time = 0.0
        self.success=0
        self.fields = [ ] #list of chat fields to update
        
        if not directory:
            raise Error('No download directory configured yet.')

        #here we get rid of unicode for filename
        self.filename = os.path.join(
            self.directory,
            os.path.basename(utility.force_string(self.data['filename'])))
        self.basename = os.path.basename(self.filename)

    def start(self):
        utility.Task_manager.start(self)
        self.position = 0
        self.length_remaining = self.data['length']
        utility.schedule_mainthread(500.0, self.update) 
        self.update()
  

    def stop(self):
        if not self.running:
            return

        utility.Task_manager.stop(self, 1)

    def get_bytes_downloaded(self):
        return self.bytes_downloaded

    def get_bytes_total(self):
        return self.data['length']

    def get_speed(self):
        """Some sort of average bytes per second."""
        pass
    
    def get_remaining_time(self):
        tot_seconds = self.remaining_time
        if not(tot_seconds >= 0.0):
            return ''
        if tot_seconds < 60*60.0:
            return _('%dmin%02ds') % divmod(int(tot_seconds), 60)
        elif tot_seconds < 48*60*60.0:
            return _('%dh%02dmin') % divmod(int(tot_seconds) / 60, 60)
        else:
            tot_days = tot_seconds / (24.0 * 60 * 60)
            if tot_days < 100:
                return _('%d days') % int(tot_days)
            else:
                return _('(months)')

    def get_sources(self):
        pass

    def cancel_download(self):
        pass

    def update(self):
        pass


class Circle_Downloader(Downloader):

    def __init__(self, node, data,links, directory, no_overload=0, on_complete=None):
        Downloader.__init__(self, data, directory)

        self.node = node
        self.links = links[:]
        self.authorized_links = [ ]
        
        self.chunks = { }
        self.bytes_written    = 0L
        self.speed_sum = 0
        self.speed_sum_weights = 0.01
        self.on_completion = on_complete
        self.no_overload = no_overload
        self.access_denied = 0

        self.lock_sources()

        if not acquire_file_lock(self.filename,1):
            #raise Error('That file is already in your download directory.')
            i = 1
            while not acquire_file_lock(self.filename + "-%d"%i,1):
                i = i + 1
            self.comment = '\n\nNote: not overwriting existing ' + os.path.basename(self.filename)
            self.filename = self.filename + "-%d"%i

        try:
            self.files = [ open(self.filename,'wb') ]
        except:
            raise Error("Couldn't open the file to write to.")
    

    def lock_sources(self):
        self.lock.acquire()
        if self.no_overload:
            for s in self.links:
                if not s in sources_locked:
                    sources_locked_lock.acquire()
                    sources_locked.append(s)
                    self.authorized_links.append(s)
                    sources_locked_lock.release()
            for s in self.authorized_links:
                if not s in self.links:
                    sources_locked_lock.acquire()
                    self.authorized_links.remove(s)
                    sources_locked.remove(s)
                    sources_locked_lock.release()
        else:
            self.authorized_links = self.links[:]
        self.lock.release()
                

    def get_sources(self):
        if len(self.links) ==0:
            if self.access_denied:
                return "access denied, waiting"
            else:
                return "waiting for source"
        elif len(self.authorized_links) == 0:
            return "queued"
        elif len(self.authorized_links) == 1:
            return "1 source"
        else:
            return "%d sources" % len(self.authorized_links) 

    def get_speed(self):
        """Some sort of average bytes per second.
           (Circle_Downloader uses a form of exponential smoothing.)"""
        return self.speed_sum / self.speed_sum_weights

    def start(self):
        self.last_update_time = time.time()
        Downloader.start(self)
        for i in range(download_threads):
            utility.start_thread(circle_downloader_thread(self))

        utility.start_thread(circle_downloader_refresh_sources_thread(self))


    def get_ticket(self):
        try:
            self.lock.acquire()

            if self.length_remaining == 0:
                raise Error('finished')

            if self.length_remaining < download_chunk:
                fetch_length = self.length_remaining
            else:
                fetch_length = download_chunk
            
            result = (self.position, fetch_length)
            self.length_remaining = self.length_remaining - fetch_length
            self.position = self.position + fetch_length
        finally:
            self.lock.release()

        return result

    def get_link(self):
        self.lock.acquire()
        try:
            if not self.authorized_links:
                if not self.running:
                    raise Error("abort")
                else:
                    return None # just twiddle your thumbs for a bits...

            link = self.authorized_links.pop(0)
            self.authorized_links.append(link)
            return link
        finally:
            self.lock.release()

    def link_failed(self, link):
        self.lock.acquire()
        if link in self.links:
            self.links.remove(link)
        self.lock.release()
        self.lock_sources()

    def link_succeeded(self, link):
        pass

    def cancel(self):
        # nyi for Circle downloader, but Donkey_Downloader does handle this method.
        pass

    def stop(self):
        if not self.running:
            return

        Downloader.stop(self)
        for file in self.files:
            try:
                file.close()
            except:
                pass
        if self.bytes_written < self.data['length']:
            try:
                os.unlink(self.filename)
            except OSError:
                pass
            #if self.links == [ ]:
            #  Error('Ran out of sources while downloading ' + self.data['filename']).show()
            self.success = 0
        else:
            self.success = 1
        release_file_lock(self.filename)

        if self.no_overload:
            sources_locked_lock.acquire()
            for l in self.authorized_links:
                sources_locked.remove(l)
            sources_locked_lock.release()
        
        if self.on_completion:
            self.on_completion(self)



    def update(self):
        if not self.running:
            return 0

        self.lock.acquire()
        try:
            total=0
            while self.chunks.has_key(self.bytes_written):
                chunk = self.chunks[self.bytes_written]
                del self.chunks[self.bytes_written]
                try:
                    for file in self.files:
                        file.write(chunk)
                except:
                    self.stop()
                    return 0

                self.bytes_written = self.bytes_written + len(chunk)
                total=total+len(chunk)

            # Update the weighted average for "speed", where speed is taken to
            # be the number of half-bytes read in this update.
            # (Why is this, is update called every 0.5 seconds?  This assumption
            # should probably be modified given that we can't guarantee that it's
            # 0.5 seconds since the last update; TODO.)
            # The weights used are 1.0 for this update, 0.9 for the previous
            # one, 0.81 for the update before that, etc. (0.9**i for the i'th
            # most recent update).  This is more accurate than the simple
            # implementation of exponential smoothing that doesn't keep track
            # of how much weight of real data we have.
            #self.speed_sum = 0.9 * self.speed_sum + (2 * total)
            
            # Updated to use real time between updates.
            time_now = time.time()

            if time_now != self.last_update_time:
                self.speed_sum = 0.9 * self.speed_sum + (total / (time_now - self.last_update_time))
                self.speed_sum_weights = 0.9 * self.speed_sum_weights + 1.0

            self.last_update_time = time_now
            
            done = (self.bytes_written == self.data['length'])
            if self.speed_sum != 0:
                # This is a hack with no theoretical basis.
                self.remaining_time \
                  = (0.8 * (self.remaining_time - 0.4)
                     + (0.2 * (self.data['length'] - self.bytes_downloaded)
                        / self.get_speed()))
        finally: 
            self.lock.release()
        
        if done:
            self.stop()
            
        return 1





#########################################################################
#
# File server
#
#
#

class File:
    # Members:
    #   is_dir
    #   mtime
    #   info 
    #   hash
    #   length
    #   names
    pass

def build_file(path, mtime,flags,server):
    
    file = File()
    file.is_dir = 0
    file.mtime = mtime

    # basename = utility.force_unicode(os.path.basename(path))
    # do not convert to unicode, because published data should not
    # depend on the terminal encoding of the client
    basename = os.path.basename(path)
    
    file.length = os.stat(path)[6]
    file.names = [ ]
    file.info = {
        'type'     : 'file',
        'filename' : basename,
        'length'   : file.length,
    }

    if flags.get('name'):
        if server.cache.has_key((path,mtime)):
            file.hash, file.length = server.cache[(path,mtime)]
        else:
            try:
                f = open(path,'rb')
                m = md5.new()
                file.length = 0L
                while 1:
                    str = f.read(1<<20)
                    if str == '': break
                    m.update(str)
                    file.length = file.length + len(str)
                f.close()
                file.hash = m.digest()
            except IOError:
                raise Error('bad file')
            server.cache[(path,mtime)] = (file.hash, file.length)
            
        file.info['name'] = file.hash
        file.names.append(file.hash)

    if flags.get('local'):
        file.info['local_path'] = path
    
    str = utility.remove_accents(string.lower(basename))
    keywords = [ ]
    
    if flags.get('filename'):
        keywords.append(str)

    if flags.get('keywords'):
        for char in '+-_.,?!()[]':
            str = string.replace(str,char," ")

        keywords.extend(string.split(str))         

    if flags.get('mime'):
        list = {}
        if string.lower(path[-4:]) =='.mp3':
            list = mp3.mp3_info(path)
        elif string.lower(path[-4:]) =='.ogg':
            list = mp3.ogg_info(path)
        if list:
            for (k,v) in list.items():
                file.info[k] = v

        if file.info.get('music_title'):
            keywords.extend(string.split(
                utility.remove_accents(string.lower(file.info['music_title']))))
        if file.info.get('music_artist'):
            keywords.extend(string.split(
                utility.remove_accents(string.lower(file.info['music_artist']))))

    file.info['keywords'] = [ ]

    if flags.get('mime'):
        import classify
        try:        
            information = classify.classifier.information(path)
            for key in information.keys():
                if information[key] == None:
                    #print "[Harmless warning] Can not classify : ", path
                    continue
    
                if len(information[key]) >= min_search_keyword_len:
                    file.info[key] = information[key]
        except:
            sys.stderr.write("Exception caught while classifying file.\n")

        
    for word in keywords:
        word=utility.force_string(word)
        if len(word) >= min_search_keyword_len and word not in file.info['keywords']:
            file.info['keywords'].append(word)
            if flags.get('name'):
                file.names.append(hash.hash_of(word))


    # publish immediately...
    if flags.get('name'):
        if not server.entries.has_key(path):
            for name in file.names:
                server.node.publish(name, file.info)
        elif server.entries[path].mtime != mtime:
            #first unpublish outdated info
            print "unpublishing outdated:",path
            server.node.unpublish(file.info)
            for name in file.names:
                server.node.publish(name, file.info)

        server.entries[path]    = file
        server.paths[file.hash] = (path, file.mtime)
        server.names[path]      = file.hash




    return file

class Directory:
    # Members:
    #   is_dir
    #   mtime
    #   info 
    #   files
    pass

def build_directory(path, mtime, flags, server):
    dir = Directory()
    dir.mtime = mtime
    dir.is_dir = 1
    dir.names = [ ]
    basename = os.path.basename(path)

    dir.info = {
        'type'     : 'directory',
        'filename' : basename,
        'length'   : 0L,
        'path'     : string.split(path,'/')
    }
    #print dir.info['path']
    names = os.listdir(path)
    
    #for i in range(len(names)):
    #    names[i] = utility.force_unicode(names[i])

    # Option to limit number of files published
    # TODO: make it work with subdirectories
    if flags['max'] != None:
        names = names[:flags['max']]
        

    if flags.get('name'):
        if server.cache.has_key((path,mtime)):
            dir.hash, dir.length = server.cache[(path,mtime)]
        else:
            dir.length = 0
            dir.hash = hash.hash_of('basename')
            server.cache[(path,mtime)] = (dir.hash, dir.length)
            
        dir.info['name'] = dir.hash
        dir.names.append(dir.hash)



    if not flags.get('name'):
        dir.info['local_path'] = path

    str = utility.remove_accents(string.lower(basename))
    keywords = [ ]    
    if flags.get('filename'):
        keywords.append(str)
    if flags.get('keywords'):
        for char in '+-_.,?!()[]':
            str = string.replace(str,char," ")
        keywords.extend(string.split(str))         

    dir.info['keywords'] = [ ]

    dir.files = [ ]
    for item in names:
        if item[0] != '.':
            dir.files.append(os.path.join(path,item))

    #for the moment do not publish directories
    return dir

    for word in keywords:
        word=utility.force_string(word)
        if len(word) >= min_search_keyword_len and word not in dir.info['keywords']:
            dir.info['keywords'].append(word)
            if flags.get('name'):
                dir.names.append(hash.hash_of(word))

    # publish directory...
    # todo: publish after all files have been hashed,
    # generate name from their hash
    if flags.get('name'):
        if not server.entries.has_key(path):
            for name in dir.names:
                server.node.publish(name, dir.info)
        elif server.entries[path].mtime != mtime:
            #first unpublish outdated info
            #print "unpublishing outdated dir"
            server.node.unpublish(dir.info)
            for name in dir.names:
                server.node.publish(name, dir.info)

        server.entries[path]    = dir
        server.paths[dir.hash] = (path, dir.mtime)
        server.names[path]      = dir.hash

    return dir

def build_entry(path, last_entry, flags, server):
    try:
        if not acquire_file_lock(path):
            return None
        try:
            mtime = os.path.getmtime(path)
            if last_entry and mtime == last_entry.mtime:
                if not last_entry.is_dir:
                    server.cache[(path,mtime)] = (last_entry.hash, last_entry.length)
                return last_entry

            if os.path.isdir(path):
                if os.path.basename(path) != '.':
                    result = build_directory(path, mtime, flags, server)
            else:
                # TODO: flocking
                #now = time.time()
                #if mtime > now-10 and mtime <= now:
                #  raise Error('File being updated')
                try:
                    result = build_file(path, mtime,flags,server)
                except:
                    return None

            result.mtime = mtime
            return result
        finally:
            release_file_lock(path)
    except OSError:
        print 'warning: no such file', path
        pass
    except IOError:
        print 'warning: bad shit going on', path
        pass
    

def file_server_poll_thread(server):
    """
    polling thread
    the cache should cache everything, not only the hash
    """
    #roots = [ ]
    
    #cache = utility.get_config("hash_cache",{ })
    yield 'sleep',30
    while server.running:

        roots = server.roots
        new_entries = { }
        new_paths   = { }
        new_names   = { }
        todo = [ ]
        for item in roots:
            todo.append((os.path.abspath(item[0]),item[1]))

        running = 1
        n_new = 0

        while todo and n_new < 20:
            
            running = server.running
            if not running:
                break
            item = todo.pop()
            if new_entries.has_key(item[0]):
                continue
            result = build_entry(item[0],server.entries.get(item[0],None),item[1],server)
            yield 'sleep',0.01
            if result:
                new_entries[item[0]] = result
                if result.is_dir:
                    for file in result.files:
                        if item[1].get('subdirectories') or \
                               not os.path.isdir(file):
                            todo.append((file,item[1]))
                else:
                    new_paths[result.hash] = (item[0], result.mtime)
                    new_names[item[0]]     = result.hash
                    if not server.cache.has_key((item[0],result.mtime)):
                        n_new = n_new + 1

        if not running:
            return

        # here we unpublish files that might
        # have been removed since last poll
        for key in server.entries.keys():
            if not server.entries[key].is_dir:
                if not new_entries.has_key(key):
                    server.node.unpublish(server.entries[key].info)

        server.paths   = new_paths
        server.names   = new_names
        server.entries = new_entries
        server.fresh = 1
        yield 'sleep',30


            
class File_server(utility.Task_manager):
    
    def __init__(self, node):
        utility.Task_manager.__init__(self)

        self.paths          = { }  # hash -> (path, mtime)
        self.names          = { }  # path -> hash
        self.entries        = { }  # path -> entry object
        self.cache          = { }  # (path, mtime) -> name

        self.roots          = [ ]        
        self.private_directory = ''
        
        self.private_paths  = { }  # hash -> (path, mtime). this is for the /giveto command
        self.node           = node
        
        self.downloaders    = [ ] # parallels list
        self.fresh          = 0  

    def start(self):
        self.cache = utility.get_config("hash_cache",{ })
        utility.Task_manager.start(self)        
        self.node.add_handler('download chunk', self, ('name', 'integer', 'integer'), types.StringType)
        self.node.add_handler('files available', self)
        utility.start_thread(file_server_poll_thread(self))
        

    def stop(self):

        self.change_activity('interrupting downloads')
        for downloader in self.downloaders:
            downloader.stop()
        self.change_activity('removing handlers')
        self.node.remove_handler('download chunk')
        self.node.remove_handler('files available')
        self.change_activity('')
        self.change_activity('saving hash cache')
        utility.set_config("hash_cache", self.cache)
        self.change_activity('')
        utility.Task_manager.stop(self)

        infos = []
        for entry in self.entries.values():
            if not entry.is_dir:
                infos.append(entry.info)
        self.change_activity('unpublishing %d file infos' % len(infos))
        self.node.unpublish_set(infos)


    def set_roots(self, config):

        roots = [ ]
        self.private_directory = ''

        if config.get('public_dir','') != '':
            list = map(string.strip,string.split(config['public_dir'],','))
            if list:
                roots.extend(list)

        if config.get('download_dir','') != '':
            list = map(string.strip,string.split(config['download_dir'],','))
            if list:
                #config['download_dir'] = list[0]
                roots.extend(list)

        if config.get('private_dir','') != '':
            list = map(string.strip,string.split(config['private_dir'],','))
            if list:
                self.private_directory = list[0]
                roots.extend(list)
                
        for i in range(len(roots)):
            roots[i] = (utility.force_string(roots[i]), flags_full)            

        if config.get('publish_apt',''):
            roots.append(('/var/cache/apt/archives',flags_deb))
                
        # avoid redundancy (prefixes) in the roots list
        np_roots = [ ]
        for root in roots:
            ok = 1
            for np_root in np_roots:
                if utility.is_subdir(root[0],np_root[0]):
                    ok = 0
                elif utility.is_subdir(np_root[0],root[0]):
                    np_roots.remove(np_root)
            if ok:
                np_roots.append(root)

        self.lock.acquire()
        #self.roots.append(os.path.abspath(path))
        #self.roots.append((path,flags))
        self.roots = np_roots
        self.fresh = 0
        self.lock.release()

    def move_file(self, leaf, dest_root):
        """Move a local file and keep file server in sync"""
        old_path = leaf.item['local_path']
        new_path = os.path.join(dest_root.item['local_path'],os.path.split(old_path)[1])
        os.rename(old_path,new_path)
        leaf.item['local_path'] = new_path
        leaf.father.children.remove(leaf)
        leaf.father = dest_root
        dest_root.children.append(leaf)


        #todo: sync file server            

    def remove_file(self, name, path=None):
        """Remove a file and keep file server in sync"""

        if self.paths.has_key(name):
            if not path:
                path=self.paths[name][0]
            self.lock.acquire()
            try:
                os.unlink(path)
            except OSError:
                print "error deleting"+path
                pass
            
            self.paths.__delitem__(name)
            if self.names.has_key(path):
                self.names.__delitem__(path)
            if self.entries.has_key(path):
                self.node.unpublish(self.entries[path].info)
                self.entries.__delitem__(path)
            self.lock.release()

  
    def add_private(self, path):
        """
        builds a private entry (not published)
        used by the /give command
        
        """
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            raise Error('bad file')

        entry = build_file(path,os.path.getmtime(path),flags_full, self)
        self.private_paths[entry.hash] = (path, mtime)
        return entry.info


    def handle(self, request, address, call_id):
        check.check_matches(request, (types.StringType,))
        check.check_is_af_inet_address(address)

        if request[0] == 'download chunk':
            path, mtime = self.paths.get(request[1],(None,None))
            if not path:
                path, mtime = self.private_paths.get(request[1],(None,None))
                
            try:
                if not path or \
                     os.path.getmtime(path) != mtime:
                    return Error("no such file")
                file = open(path,'rb') 
            except IOError:
                return Error("no such file")

            if address[0] !='127.0.0.1'\
                   and address not in self.node.trusted_addresses \
                   and self.private_directory != ''\
                   and utility.is_subdir(path,self.private_directory):
                return Error("access denied")

            try:
                file.seek(request[2])
                return file.read(request[3])
            finally:
                file.close()

        elif request[0] == 'files available':

            if len(request) == 3:
                # this returns the keys of
                # all published files from all directories
                # regardless of the directory structure
                list = self.paths.keys()
            else:
                list = [ ]
                access_denied = 0
                directory_found = 0

                string_request = []
                for str in request[3]:
                    string_request.append(utility.force_string(str))

                if not self.roots:
                    return Error('No public directory')
                request_dir = apply(
                    os.path.join,
                    [os.path.abspath(self.roots[0][0])] + string_request)

                if address[0]=='127.0.0.1':
                    flags = flags_local
                else:
                    flags = flags_fast            
                    
                if os.path.exists(request_dir):
                    directory_found = 1

                if address[0]!='127.0.0.1' \
                       and address not in self.node.trusted_addresses\
                       and self.private_directory != ''\
                       and utility.is_subdir(request_dir,self.private_directory):
                    access_denied = 1
                    
                if not directory_found:
                    return Error("no such directory: %s"%request_dir)
                elif access_denied:
                    return Error("access denied")
                
                entry = build_entry(request_dir,None,flags,self)
                
                if entry:
                    if not entry.is_dir:
                        return Error("not a directory: "+request_dir)
                    for file in entry.files:
                        entry_2 = build_entry(file,None,flags,self)
                        if entry_2:
                            info = entry_2.info.copy()
                            info['path'] = request[3] + [ info['filename'] ]
                            list.append(info)

            return list[request[1]:request[2]]


    def retrieve_downloaders(self):
        
        def list_downloaders(pipe,self):
            for d in self.downloaders:
                if d.links:
                    for link in d.links:
                        pipe.write((link,d.data))
                else:
                    pipe.write(('no source',d.data))
            
        pipe = utility.Pipe()
        pipe.start(list_downloaders,self)
        return pipe

    def download(self, item, sources, path, no_overload=0):
        """Download a file. Not for directories. Returns None if the file is already
        being downloaded, or already in our directory. If no_overload is true, we will
        wait until no other downloader is downloading from the same source.
        """

        name=item.get('name')
        if self.paths.has_key(name):
            #if field: field.show(_('local copy exists.\n'),['grey'])
            return None

        for d in self.downloaders:
            if d.data['name']==name:
                #if field: d.fields.append(field)
                return None
        
        # Immediately add a downloaded file to our list
        def on_complete(downloader,self=self):
            if downloader.success:
                self.lock.acquire()
                self.paths[downloader.data['name']] = (downloader.filename,
                                                       os.path.getmtime(downloader.filename))
                self.lock.release()
            for d in self.downloaders:
                if d != downloader:
                    d.lock_sources()
        downloader = Circle_Downloader(self.node,item,sources,path,no_overload, on_complete)
            
        self.downloaders.append(downloader)
        downloader.start()
        return downloader


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
