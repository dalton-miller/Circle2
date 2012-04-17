#!/usr/bin/python2

if __name__ == '__main__':
    import pygtk
    pygtk.require('2.0')
    
import gtk
import random
import math
import sys

import os.path,sys,re,string
import dircache,os,time

import widgets
from circlelib import utility, check


class Text_Viewer(gtk.Window):
    def timeout(self):

        #check.check_is_gtkthread()
        if not self.running:
            return 0

        try:
            fs = os.path.getsize(self.fname)
        except OSError:
            return 0

        if fs == 0: return 1
        if not self.file:
            self.file = open(self.fname, "r")
        self.text.write(self.file.read())
        if self.size > fs:
            #print "downloaded %d of %d" % (fs, self.size)
            return 1

        #print "finished download"

        return 0

    def delete_event(self, win, event=None):
        win.hide()
        # don't destroy window -- just leave it hidden

        self.running = 0

        return gtk.TRUE

    def __init__(self, info, downloader=None, field=None):

        if info.get('local_path'):
            fname = info['local_path']
        else:
            fname = downloader.filename
        size = info.get('length')
        self.running = 1

        gtk.Window.__init__(self)
        title = os.path.basename(fname)
        self.fname = fname
        self.size = size
        self.set_name(title)
        self.set_title(title)
        self.set_default_size(500,500)

        self.vbox = gtk.VBox(gtk.FALSE, 0)

        self.text = widgets.Text()
        sw = gtk.ScrolledWindow(None, None)
        sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.text)
        self.vbox.pack_start(sw)

        self.file = None
        self.timeout()
        gtk.timeout_add(300, self.timeout)

        self.add(self.vbox)

        if downloader != None:
            self.keep_file_button = gtk.CheckButton("Keep file after viewing")
            self.vbox.pack_start(self.keep_file_button, expand=gtk.FALSE)
            self.keep_file_button.show()

        self.show_all()


class External_Viewer:
    """
    Use an external application to play a file
    this requires that the download is complete
    (although not all applications require this... xine does not)
    note: we should not use a window here
    """
    
    def timeout(self):
        if not self.running:
            return 0
        try:
            fs = os.path.getsize(self.fname)
        except OSError:
            return 0

        if fs == 0:
            return 1
        if not self.file:
            self.file = open(self.fname, "r")
        if self.size > fs:
            return 1

        self.running=0
        utility.play_file(self.fname)
        return 0

    def __init__(self, info, downloader=None,field=None):
        self.running = 1
        size = info.get('length')
        if info.get('local_path'):
            fname = info['local_path']
        else:
            fname = downloader.filename

        title = os.path.basename(fname)
        self.fname = fname
        self.size = size
        self.file = None
        self.timeout()
        utility.schedule_mainthread(300.0, self.timeout)

def main(fname):
    win = textviewer(fname, 0)
    win.connect("destroy", gtk.mainquit)
    gtk.mainloop()

if __name__ == '__main__': main(sys.argv[1])


# vim: set expandtab :
