#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2002  Paul Francis Harrison
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

"""Apt method code
"""

import sys, time, signal, select, os, popen2, string, md5, sha

from error import Error
import node, utility, file_server, hash

the_node = None
the_manager = None

def read_unit(file):
    lines = [ ]
    try:
        while 1:
            line = file.readline()
            if line[-1:] == '\n':
                line = line[:-1]
            if not line:
                break
            lines.append(line)
    except IOError:
        pass
    return lines

def write_unit(file, lines):
    try:
        for line in lines:
            file.write(line)
            file.write('\n')
        file.write('\n')
        file.flush()
    except IOError:
        pass

def unpack_unit(lines):
    result = { }
    for line in lines[1:]:
        list = string.split(line,': ')
        if len(list) < 2:
            continue
        result[list[0]] = list[1]
    return result

def ensure_node_started(param):
    global the_node, the_manager

    the_manager.lock.acquire()
    try:
	if the_node:
	    if the_node.is_connected():
	        return
	    raise Error('no peers')

	write_unit(sys.stdout, [
	    '102 Status',
	    'URI: '+param['URI'],
	    'Message: Joining the Circle'
	])

	the_node = node.Node()

	the_node.start()
	the_node.deactivate_hashtable()

	for i in range(40):
	    if not the_node.is_connecting():
		break
	    time.sleep(0.1)
	
        if not the_node.is_connected():
	    raise Error('no peers')
    finally:
        the_manager.lock.release()

def to_hex(str):
    result = ''
    for char in str:
        result = result + ('%02x'%ord(char))
    return result

def from_hex(str):
    return hash.hex_md5_to_hash(str) 

def get_md5(filename):
    head = string.split(filename,"_")[0]

    file = utility.popen("apt-cache show "+head)
    lines = file.readlines()
    file.close()

    entry_filename = None
    entry_hash = None

    for line in lines:
      list = string.split(string.strip(line),maxsplit=1)
      if not list:
        if entry_filename and entry_hash:
          if os.path.basename(filename) == filename:
	      return from_hex(entry_hash)
	entry_filename = None
	entry_hash = None

      elif list[0] == 'Filename:':
          entry_filename = list[1]
      elif list[0] == 'MD5sum:':
          entry_hash = list[1]

    raise Error('no entry for file')

def fetch(param):
    global the_node, the_manager
    if param['URI'][-4:] != '.deb':
        raise Error('not a package')
    
    head, tail = os.path.split(param['URI'])

    hash_from_cache = get_md5(tail)

    the_manager.lock.acquire()
    write_unit(sys.stdout, [
        '102 Status',
        'URI: '+param['URI'],
        'Message: Searching the Circle'
    ])
    the_manager.lock.release()

    #pipe = the_node.retrieve(hash.hash_of(string.lower(tail)))
    pipe = the_node.retrieve(hash_from_cache)
    #list = pipe.read_until_finished()

    list = [ ]
    t1 = time.time()
    for i in range(50):
        list.extend(pipe.read_all())
        if pipe.finished():
            break
        time.sleep(0.1)
    t2 = time.time()
    pipe.stop()
    
    if len(list) < 1:
        raise Error('no sources')

    for item in list[1:]:
        if item[1]['length'] != list[0][1]['length'] or \
             item[1]['name']  != list[0][1]['name']:
            raise Error('confused')
             
    sources = [ ]
    for item in list:
        sources.append(item[0])
    
    head, tail = os.path.split(param['Filename'])

    data = {
        'type' : 'file',
        'filename' : tail,
        'name' : list[0][1]['name'],
        'length' : list[0][1]['length']
    }

    # No resume yet
    try:
        os.unlink(param['Filename'])
    except OSError:
        pass

    downloader = file_server.Circle_Downloader(the_node, data,sources,head)
    downloader.start()

    # Tell user we have a hit, download is starting in the background
    #write_unit(sys.stdout, [
    #  '102 Status',
    #  'URI: '+param['URI'],
    #  'Message: Found %d sources' % len(sources)
    #])

    #time.sleep(1)

    sys.stderr.write('\nFetching %s from %d sources on the Circle.\n' % (tail,len(sources)))

    the_manager.lock.acquire()
    write_unit(sys.stdout, [
        '200 URI Start',
        'URI: '+param['URI'],
        'Size: %d' % data['length']
    ])
    the_manager.lock.release()
    
    while downloader.running:
        utility.threadnice_mainloop_iteration()
        time.sleep(1)

        if not downloader.links:
            downloader.stop()
            raise Error("ran out of sources")

    the_md5 = md5.new()
    the_sha = sha.new()
    file = open(param['Filename'],"rb")
    while 1:
        block = file.read(65536)
        if not block:
            break
        the_md5.update(block)
        the_sha.update(block)
    file.close()
        
    the_manager.lock.acquire()
    write_unit(sys.stdout, [
        '201 URI Done',
        'URI: '+param['URI'],
        'Filename: '+param['Filename'],
        'Size: %d' % data['length'],
        'MD5-Hash: '+to_hex(the_md5.digest()),
        'SHA1-Hash: '+to_hex(the_sha.digest())
    ])
    the_manager.lock.release()

    # No last modified!

def fetch_task(manager, unit, child_stdin):
    param = unpack_unit(unit)
    try:
	ensure_node_started(param)
	fetch(param)
    except Error:
	manager.lock.acquire()
	write_unit(child_stdin, unit)
	manager.lock.release()
                
def pass_through(stdin_unbuffered, child_stdout, child_stdin):
    while 1:
        result = select.select([stdin_unbuffered,child_stdout],[],[stdin_unbuffered,child_stdout])

        if result[2]:
            break

        if stdin_unbuffered in result[0]:
            unit = read_unit(stdin_unbuffered)
	    if not unit:
	      break
            write_unit(child_stdin, unit)

        if child_stdout in result[0]:
            write_unit(sys.stdout, read_unit(child_stdout))

def signal_handler(signal,frame):
    raise Error('SIGINT')

def run():
    global the_node, the_manager

    the_manager = utility.Task_manager()

    signal.signal(signal.SIGINT, signal_handler)

    stdin_unbuffered = os.fdopen(os.dup(0),"rt",0)

    head, tail = os.path.split(sys.argv[0])
    child_name = os.path.join(head,tail[1:])
    child_stdout, child_stdin = popen2.popen2(child_name,0)
    time.sleep(0.1)

    try:
        the_node = None
        utility.threadnice_mainloop_start()

        try:
            while 1:
                result = select.select([stdin_unbuffered,child_stdout],[],[stdin_unbuffered,child_stdout])

                if result[2]:
                    break

                if child_stdout in result[0]:
		    the_manager.lock.acquire()
                    write_unit(sys.stdout, read_unit(child_stdout))
		    the_manager.lock.release()

                if stdin_unbuffered in result[0]:
		    the_manager.lock.acquire()
                    unit = read_unit(stdin_unbuffered)
		    the_manager.lock.release()
                    if not unit:
                        break

                    command = unit[0][:3]
                    if command == '600':
		        utility.Task(fetch_task, the_manager, unit, child_stdin).start()
                    else:
		        the_manager.lock.acquire()
                        write_unit(child_stdin, unit)
		        the_manager.lock.release()

        finally:
            utility.threadnice_mainloop_stop()
            if the_node:
                the_node.stop()
                the_node = None
            the_manager.stop()
    except Error, err:
        if err.message != 'SIGINT':
            try:
                pass_through(stdin_unbuffered, child_stdout, child_stdin)
            except Error:
                pass

