#!/usr/bin/python2

if __name__ == '__main__':
    import pygtk
    pygtk.require('2.0')

import gtk
import dircache, os, os.path

from circlelib import utility, check

class Viewer(gtk.VBox):
        def load_image(self):
		self.image = gtk.Image()
                self.image.set_size_request(10,10)

		self.image_orig = gtk.Image()
		self.image_orig.set_from_file(self.fname)
                self.pb = self.image_orig.get_pixbuf()

                self.width = 0
                self.height = 0
                
		self.pack_start(self.image)
                self.image.show()
		#self.update(self.image, None)

	def update(self, widget=None, event=None):
		if not self.image: return 0

		w = self.pb.get_width()
		h = self.pb.get_height()

		alloc = self.image.get_allocation()
		mw,mh = float(alloc.width),float(alloc.height)

                if mw == self.width and mh == self.height:
                    return 1
                self.width, self.height = mw, mh
                
                s = 1.0
		if w > mw:
			s = mw/w
		if h*s > mh:
			s = mh/h
		self.image.set_from_pixbuf(self.pb.scale_simple(int(w*s),int(h*s), gtk.gdk.INTERP_BILINEAR))
		return 1
		
        def timeout(self):
		#check.check_is_gtkthread()
                try:
                        fs = os.path.getsize(self.fname)
                except OSError:
                        return 0
                if(self.size <= fs):
                        self.progress.hide()
                        self.load_image()
                        return 0
                
		self.previoussize = fs
                self.progress.set_fraction(float(fs) / self.size)
                return self.visible

        def create_browser_window(self):
                gtk.VBox.__init__(self, gtk.FALSE, 0)

                self.previoussize = 0
                self.image = None
                self.pb = None
                if self.size <= os.path.getsize(self.fname):
                        self.load_image()
                else:
                        gtk.timeout_add(300, self.timeout)
                        self.progress = gtk.ProgressBar()
                        self.pack_start(self.progress, 1,0)

        def on_destroy(self, _):
                self.visible = 0
                
        def __init__(self, fname, size):
                gtk.VBox.__init__(self)
                self.fname = fname
                self.size = size
                self.visible = 1
                self.create_browser_window()
		self.connect("size-allocate", self.update)
                self.connect("destroy", self.on_destroy)
        
class imageviewer(gtk.Window):
	def __init__(self, info, downloader=None,field=None):

		if info.get('local_path'):
			f = info['local_path']
		else:
			f = downloader.filename

		s = info.get('length')
		gtk.Window.__init__(self)
		title = os.path.basename(f)

		self.set_name(title)
		self.set_title(title)

		self.set_default_size(400, 400)
		browser = Viewer(f, s)
		self.add(browser)

		if downloader != None:
		    self.keep_file_button = gtk.CheckButton("Keep file after displaying")
		    browser.pack_start(self.keep_file_button, expand=gtk.FALSE)
		    self.keep_file_button.show()

		self.show_all()

def main(fname):
        win = imageviewer(fname, 0)
        win.connect("destroy", gtk.mainquit)
        gtk.mainloop()

if __name__ == '__main__':
	import sys
	if len(sys.argv) > 1:
		main(sys.argv[1])


# vim: set expandtab :
