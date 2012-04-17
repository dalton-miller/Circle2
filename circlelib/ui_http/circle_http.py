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
   HTTP interface to Circle
   start, stop and status are called by the daemon.   
"""

import os, sys, threading, time, traceback, string
import math, types, socket, random, select
from circlelib import __init__, check, error, hash, node, settings, utility, safe_pickle, file_server

http_mode=''
http_port = settings.default_http_port
http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def stop():
    global http_mode,http_port,http_socket
    http_mode = ''
    http_socket.shutdown(0)
    http_socket.close()
    return "http stopped"

def start(mode,daemon):
    global http_mode,http_port,http_socket
    http_mode = mode
    try:
        if http_mode == 'local':
            http_socket.bind(('localhost',http_port))
        elif http_mode == 'remote':
            http_socket.bind(('',http_port))            
        http_socket.listen(5)                                    
    except:
        return _('socket already in use')
        
    daemon.http_running = 1
    utility.Task(http_server_task,daemon).start()                                        
    return status()

def status():
    global http_mode,http_port,http_socket
    if http_mode:
        str = _('  Accepting %s http requests on port %d\n')\
                 %(http_mode,http_port)
        str += _('  Check http://localhost:%d/ \n')\
                  %(http_port)
    else:
        str = ''
    return str


def http_server_task(daemon):
    global http_mode,http_port,http_socket

    while daemon.running:
        try:
            (clientsocket, address) = http_socket.accept()
        except:
            break
        output = clientsocket.makefile("wt")
        input = clientsocket.makefile("rt")
        line = input.readline()
        try:
            request = line.split()[1]
        except:
            print "could not understand request by %s"%utility.hostname_of_ip(address[0])
            continue

        strtime = time.asctime()
        if request[1:13]=='circle-find/':
            utility.Task(find_task,daemon,request[13:],input,output,clientsocket).start()
            print "Request: people matching \"%s\" by %s, on %s" \
                  %(request[13:],utility.hostname_of_ip(address[0]),strtime)
        elif request[1:15]=='circle-search/':
            utility.Task(search_task,daemon,request[15:],input,output,clientsocket).start()
            print "Request: files matching \"%s\" by %s, on %s" \
                  %(request[15:],utility.hostname_of_ip(address[0]),strtime)
        elif request[1:13]=='circle-file/':
            utility.Task(get_file_task,daemon,request[13:35],input,output,clientsocket).start()
        else:
            utility.Task(search_task,daemon,'',input,output,clientsocket).start()
 
    http_socket.close()



def stress(str,key):
    if key.__len__() == 0:
        return str
    try:
        i=str.lower().find(key)
    except:
        return ""
    if i!=-1: 
        return str[0:i]+"<b>"+str[i:i+key.__len__()]+"</b>"+stress(str[i+key.__len__():],key)
    else:
        return str


def url(ref,circle_url,filename,port):
    return "<a href =\"http://localhost:%d/circle-file/%s/%s\">%s</a>"\
           %(port,circle_url[12:],filename,ref)


def mime_header(fname):
    # we determine the type from extension
    # we should rather use the 'mime' field of data,
    # but it seems to be broken for the moment...

    extension = string.split(string.split(fname,'.')[-1],'-')[0]
    lext = string.lower(extension)
    if lext in ['html','htm']:
        return "Content-type: text/html\n"
    if lext == 'pdf':
        return "content-type: application/pdf\n"
    if lext == 'ps':
        return "content-type: application/postscript\n"
    elif lext == 'mp3':
        return "content-type: audio/mp3\n"
    elif lext== 'ogg':
        return "content-type: audio/ogg\n"
    elif lext== 'png':
        return "content-type: image/png\n"
    elif lext in ['jpg','jpeg']:
        return "content-type: image/jpeg\n"
    elif lext== 'gif':
        return "content-type: image/gif\n"
    elif lext== 'xbm':
        return "content-type: image/xbm\n"
    elif lext== 'bmp':
        return "content-type: image/bmp\n"
    elif lext in ['mpg','mpeg']:
        return "content-type: video/mpeg\n"
    elif lext== 'avi':
        return "content-type: video/avi\n"
    else:
        return ""



def search_task(daemon,query,input,output,connection):
    global http_mode,http_port,http_socket
    global http_socket

    file=open(utility.find_file("ui_http/search.html"))
    str=file.read()
    file.close()    
    if http_mode=='local':
        image_tag = "<img src=\"file://"+utility.find_file("pixmaps/circle-logo.png")\
                    +"\" title=\"\" alt=\"\" border=0 style=\"width: 150px; height: 50px;\"> "
        hostname = 'localhost'
    else:
        image_tag = "<img src=\"http://thecircle.org.au/circle-logo.png\" "\
                    +" title=\"\" alt=\"\" border=0 style=\"width: 150px; height: 50px;\"> "
        hostname = 'thecircle.dyndns.org'

    for char in '+-_.,?()![]':
        query = query.replace(char," ")
    query=query.lower()
    list=query.split()
    if list:
        key=list[0]
    else:
        key=''

    try:        
        output.write('HTTP/1.1 200 OK\n')
        output.write('content-type: text/html\n')
        output.write('Cache-control: max-age=60\n')
        output.write('\n')
        output.write(str%(hostname,http_port,hostname,http_port,image_tag))
        output.flush()
        if key.__len__()<3:
            output.write("<p>Keyword %s too short: must be at least 3 characters<p></body></html>"%key)
            input.close()
            output.close()
            connection.close()
            return    
    except:
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

                try:
                    output.write("<p class=g><t>\n")
                    output.write(url(stress(ref,key),\
                                     hash.hash_to_url(item[1]['name']),filename,http_port))
                    output.write("<br><font size=-1>")

                    if music:
                        line=0
                        if item[1].has_key('music_artist'):
                            artist_str="Artist:"+stress(utility.force_string(item[1]['music_artist']),key)
                            output.write(artist_str)
                            line=1
                        if item[1].has_key('music_album'):
                            if item[1]['music_album']!='':
                                album_str=" Album:"+stress(utility.force_string(item[1]['music_album']),key)
                                output.write(album_str)
                                line=1
                        if line:
                            output.write("<br>")

                    #line=0
                    #if item[1].has_key('rate'):
                    #    output.write("Rate:"+item[1]['rate']+".")
                    #    line=1
                    #if item[1].has_key('freq'):
                    #    output.write("   Frequency:"+item[1]['freq']+".")
                    #    line=1
                    #if item[1].has_key('misc'):
                    #    output.write("   --  "+item[1]['misc'])
                    #    line=1
                    #if line:
                    #    output.write("<br>")

                    output.write("File name: "+stress(filename,key))
                    output.write("<br>")
                    if item[1].has_key('mime'):
                        if item[1]['mime'] != 'unknown':
                            output.write('Mime: '+item[1]['mime'].replace(' \x08',''))
                            output.write("<br>")

                    if item[1].has_key('generic'):
                        output.write(item[1]['generic'].replace('\x08',''))
                        output.write("<br>")
                    else:
                        for i in item[1].items():
                            if i[0] not in ['keywords',
                                            'mime','length',
                                            'name','filename',
                                            'type','music_album',
                                            'music_artist','music_title']:
                                output.write(i[0]+':'+stress(i[1],key)+'  ')
                                output.write("<br>")

                    output.write("<font color=#008000>"+hash.hash_to_url(item[1]['name'])+" -  "\
                                 +utility.human_size(item[1]['length'])+"- </font>")

                    #output.write("<font color=#656565>Sources:<a href="">Sources</a></font>")
                    output.write("</font></p>\n")
                except:
                    return

        time.sleep(0.5)
        try:
            output.flush()
        except:
            return
    pipe.stop()
    try:
        if not results:
            output.write("<br><br><p>Your search: <b>"+key+"</b> did not match any document.</p>")
        else:
            if restricted:
                output.write("<p><br>Displaying only 100 results for <b>%s</b></p>" % key)
            else:
                output.write("<p><br>Found %d files matching <b>%s</b></p>" % (results.__len__(),key))
            output.write("<hr><p class=g align=\"right\"></font size=-1>"\
                         +utility.force_string(random.choice(settings.gratuitous_plugs))+"</font></p><hr>")
        output.write("</body></html>")
        input.close()
        output.close()
        connection.close()
    except:
        pass
    print "returned %d files for \"%s\""%(results.__len__(), query)
    sys.stdout.flush()


def find_task(daemon,query,input,output,connection):
    global http_mode,http_port,http_socket


    file=open(utility.find_file("ui_http/search.html"))
    str=file.read()
    file.close()

    if http_mode=='local':
        image_tag = "<img src=\"file://"+utility.find_file("pixmaps/circle-logo.png")\
                    +"\" title=\"\" alt=\"\" border=0 style=\"width: 150px; height: 50px;\"> "
        hostname = 'localhost'
    else:
        image_tag = "<img src=\"http://thecircle.org.au/circle-logo.png\" "\
                    +" title=\"\" alt=\"\" border=0 style=\"width: 150px; height: 50px;\"> "
        hostname = 'thecircle.dyndns.org'

    try:
        output.write('HTTP/1.1 200 OK\n')
        output.write('content-type: text/html\n')
        output.write('Cache-control: max-age=60\n')
        output.write('\n')
        output.write(str%(hostname,http_port,hostname,http_port,image_tag))
        output.flush()
    except:
        return
    
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
                str = "circle-person:"+string.join(map(lambda a:hex(ord(a))[2:], name), '')

                try:
                    output.write("<p class=g><t><b>\n")
                    output.write(item['name'])
                    output.write(" ("+utility.force_string(item['human-name'])+")")
                    output.write("</b><br>")
                    if item['description']:
                        output.write(
                                "<font size=-1>"+utility.force_string(item['description'])+"<br></font>")
                    output.write("<font color=#008000 size=-1> "+str+"</font></p>\n")
                except:
                    return
                
        time.sleep(0.5)
        try:
            output.flush()
        except:
            return
        

    pipe.stop()
    try:
        if not results:
            output.write("<br><br><p>Your search: <b>"+key+"</b> did not match any circle user.</p>")
        else:
            if results.__len__()==1:
                what = "one identity"
            else:
                what = "%d identities"%results.__len__()
            if query:
                msg = "Returned " + what + " matching <b>\"" + query + "\"</b>."
            else:
                msg = "Returned " + what +"."
            output.write("<p><br>"+msg+"</p>")
            output.write("<hr><p class=g align=\"right\"></font size=-1>"\
                         +utility.force_string(random.choice(settings.gratuitous_plugs))+"</font></p><hr>")
            
        output.write("</body></html>")
        input.close()
        output.close()
        connection.close()
    except:
        return
    print "returned %d people for \"%s\""%(results.__len__(), query)
    sys.stdout.flush()


def get_file_task(daemon,url,input,output,connection):
    global http_mode,http_port,http_socket

    try:
        name=hash.url_to_hash("circle-file:"+url)    
        salt_name=name+daemon.node.salt
    except:
        output.write(_('error: Not a circle URL.\n')+url)
        input.close()
        output.close()
        connection.close()
        return

    if daemon.node.data.has_key(salt_name):
        
        data=daemon.node.data.get(salt_name)[0]
        filename=daemon.file_server.paths.get(name)[0]

        output.write('HTTP/1.1 200 OK\n')
        output.write(mime_header(filename))
        output.write('Content-length: %d'%data['length']+'\n')
        output.write('\n')
        output.flush()
        try:
            file = open(filename,'r')
            while 1:
                chunk=file.read(1024*1024)
                if chunk=='':
                    break
                output.write(chunk)
                output.flush()
            file.close()
        except:
            output.write(_('file access error.\n'))
                
    else:
        pipe = daemon.node.retrieve(name)
        list = pipe.read_until_finished()
        if not list:
            output.write(_('<html><head></head><body>Could not locate file.\n</body></html>'))
            input.close()
            output.close()
            connection.close()
            return
        data = list[0][1]
        output.write('HTTP/1.1 200 OK\n')
        output.write(mime_header(data['filename']))
        output.write('Content-length: %d'%data['length']+'\n')
        output.write('\n')
        output.flush()

        links = [ ]
        for item in list:
            links.append(item[0])

        if daemon.config['public_dir']:
            downloader = file_server.Circle_Downloader(daemon.node, data,links,daemon.config['public_dir'])
            daemon.file_server.downloaders.append(downloader)
            downloader.files.append(output)  #downloader will write to it and close it...
            downloader.start()

            while downloader.running:
                try:
                    output.flush()
                except:
                    downloader.stop()
                time.sleep(0.3)

            if downloader.success:
                daemon.node.publish(name,data)
                daemon.file_server.paths[name] = (downloader.filename,os.path.getmtime(downloader.filename))
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





# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
