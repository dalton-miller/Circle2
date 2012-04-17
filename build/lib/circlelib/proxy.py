# UDP Proxy

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Paul Francis Harrison
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

import sys, os, string, socket, select, cPickle, popen2, time

import utility, settings, check
from error import Error

proxy_program = """
import os,socket,sys,string,select,cPickle

sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

try:
  SOL_SOCKET = socket.SOL_SOCKET
except:
  SOL_SOCKET = 1
try:
  MSG_DONTWAIT = socket.MSG_DONTWAIT
except:
  MSG_DONTWAIT = 64
try:
  SO_SNDBUF = socket.SO_SNDBUF
except:
  SO_SNDBUF = 7
try:
  SO_RCVBUF = socket.SO_RCVBUF
except:
  SO_RCVBUF = 8

for port in """+`settings.default_ports`+""":
    try:
        sock.bind(('',port))
        break
    except:
        pass
else:
    sock.bind(('',socket.INADDR_ANY))

for i in range(20,12,-1):
    try:
        sock.setsockopt(SOL_SOCKET,SO_SNDBUF,1<<i)
        sock.setsockopt(SOL_SOCKET,SO_RCVBUF,1<<i)
        break
    except socket.error:
        pass

try:
    sock.setsockopt(0,11,1)
except:
    pass
            
if sys.platform == 'linux2':
    sock.setsockopt(0,10,0)

print 'PORT',sock.getsockname()[1]
sys.stdout.flush()

def do_error():
    try:
        message, address = sock.recvfrom(65536,0x2000 | MSG_DONTWAIT)
    except:
        return
    cPickle.dump((1,address,message),sys.stdout,1)
    sys.stdout.flush()

while 1:
    result = select.select([sock, sys.stdin],[ ],[sock])
    if sys.stdin in result[0]:
        request = cPickle.load(sys.stdin) 
        if not request:
            sys.exit(0)
        for i in range(100):
            try:
                sock.sendto(request[1],request[0])
            except:
                do_error()
                continue
            break
    elif sock in result[0]:
        try:
            message, address = sock.recvfrom(65536,MSG_DONTWAIT)
            cPickle.dump((0,address,message),sys.stdout,1)
            sys.stdout.flush()
        except:
            do_error()
    elif sock in result[2]:
        do_error()
"""
#    queue = [ ]
#    while select.select([sys.stdin],[ ],[ ],0)[0]:
#      queue.append( cPickle.load(sys.stdin) )
#    for request in queue:
#      if not request:
#        sys.exit(0)
#      try:
#        sock.sendto(request[1],request[0])
#      except:
#        pass


#proxy_program = string.replace(proxy_program,"\n","\\n")

def _make_connection_win32(host, password):
    split = string.split(host,'@') 
    
    command = 'plink '+split[-1]
    if len(split) == 2:
	command = command + ' -l "' + split[0] + '"'
	
    command = command + ' -pw "'+password+'"'
	
    # Ensure host key in cache	
    os.system(command + " echo Connected")
	    
    command = command + " -batch python -u -c 'exec input()'"
    try:
        read_stdout, write_stdin = popen2.popen2(command,mode='b')
        time.sleep(0.1)
        write_stdin.write(repr(proxy_program)+'\n')
    except:
        raise Error('Could not start plink.')
        
    write_stdin.flush()

    return read_stdout, write_stdin



def _make_connection_text(host, password):
    if sys.platform == 'win32':
        raise Error("Can't use the proxy with text mode Win32.")
        
    command = "ssh "+host+" python -u -c \"'exec input()'\""
    try:
        read_stdout, write_stdin = popen2.popen2(command,mode='b')
        time.sleep(0.1)
    except:
        raise Error('Could not start SSH.')
    
    write_stdin.write(repr(proxy_program)+'\n')
    write_stdin.flush()

    return read_stdout, write_stdin


def _make_connection_daemon(host, password):
    if sys.platform == 'win32':
        raise Error("Can't use the proxy with Windows.")
        
    command = "ssh "+host+" python -u -c \"'exec input()'\""
    try:
        read_stdout, write_stdin = popen2.popen2(command,mode='b')
        time.sleep(0.1)
    except:
        raise Error('Could not start SSH.')
    
    write_stdin.write(repr(proxy_program)+'\n')
    write_stdin.flush()

    return read_stdout, write_stdin



class Proxy(utility.Synchronous):
    def __init__(self, host,password=None, transient_for=None):
        utility.Synchronous.__init__(self)

        if sys.platform == 'win32':
            self.read_stdout, self.write_stdin = _make_connection_win32(host,password)
        else:
            self.read_stdout, self.write_stdin = _make_connection_daemon(host,password)
        
        #On win32 newline is \n\r, confusion ensues
        #line = self.read_stdout.readline()
        line = ''
        while 1:
            char = self.read_stdout.read(1)
            if char == '\n' or not char:
                break
            line = line + char
    
        if line[:5] != 'PORT ':
            self.write_stdin.close()
            self.read_stdout.close()

            if sys.platform == 'win32':
                message = 'Attempt to start the proxy failed.\n\n' + \
                                    'Check the username, server name and password.\n\n' + \
                                    '(see "Help" for more information)'
            else:
                message = 'Attempt to start the proxy failed.\n\n'+\
                                    'Check your username, server name and password.'
            raise Error(message)

        self.address = ('127.0.0.1', string.atoi(line[5:]))

        self.broken = 0
        self.running = 1
        
        check.check_is_af_inet_address(self.address)  #=@E3

    def recvfrom(self):
        """ Returns (is_error, address, message).
                Only one thread should call this at a time!"""
        if self.broken:
            raise Error("proxy broken")
                
        try:
            result = cPickle.load(self.read_stdout)
        except:
            self.become_broken()
        return result

    def sendto(self, message, address):
        self.lock.acquire()
        try:
            if self.broken:
                raise Error("proxy broken")

            try:
                cPickle.dump((address,message),self.write_stdin,1)
                self.write_stdin.flush()
            except:
                self.become_broken()
        finally:
            self.lock.release()

    def stop(self):
        self.lock.acquire()
        try:
            self.running = 0
            cPickle.dump(None,self.write_stdin,1)
            self.write_stdin.close()
            self.read_stdout.close()
        finally:
            self.lock.release()

    def become_broken(self):
        self.lock.acquire()
        try:
            if not self.broken and self.running:
                error = Error('The connection to the firewall has gone down, or the proxy has crashed.\n\n'+\
                                            'Circle is now disconnected from the network. Sorry.')
                utility.mainthread_call(error.show)
            self.broken = 1

            raise Error('proxy broken')
        finally:
            self.lock.release()


# vim: set expandtab :
