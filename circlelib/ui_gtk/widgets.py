# Custom GTK widgets

#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Paul Francis Harrison
#    gtk-2 port Copyright (C) 2003 Nathan Hurst
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

# TODO: feedback on link click

if __name__ == '__main__':
    import pygtk
    pygtk.require('2.0')

import gtk, pango

import sys, string, re, os, os.path, math, tempfile

from circlelib import check, error, hash, settings, utility

# Create a tooltip for general use

tooltips = gtk.Tooltips()
#tooltips.set_delay(1000) # deprecated, though I can't see why
tooltips.enable()

# Unicode utilities

def get_uslice(iter1,iter2):
    """ Get a slice from a text buffer, force unicode. """
    slice = iter1.get_buffer().get_slice(iter1,iter2)
    if type(slice) != type(u''):
        slice = unicode(slice,'utf8')
    return slice

def get_utext(widget):
    text = widget.get_text()
    if type(text) != type(u''):
        text = unicode(text,'utf8')
    return text

# Block-of-text widget

def insert_one_tag_into_buffer(buffer, name, *params):
    tag = gtk.TextTag(name)
    while(params):
        tag.set_property(params[0], params[1])
        params = params[2:]
    table = buffer.get_tag_table()
    table.add(tag)

def strip_symbol(s):
    while s and s[0] in '([{<':
        s = s[1:]
    while s and s[-1] in ')]}>.,!?':
        s = s[:-1]
    return s

class Text(gtk.TextView):
    def __init__(self, width=None, heading=0):
        gtk.TextView.__init__(self)

        if width:
            self.set_size_request(width,-1)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_editable(gtk.FALSE)
        self.set_cursor_visible(gtk.FALSE)

        if heading:
            self.set_left_margin(5)
            self.set_right_margin(5)
        else:
            self.set_left_margin(15)
            self.set_right_margin(15)

        self._buffer = self.get_buffer()

        tag = gtk.TextTag("default")
        tag.connect("event", self._on_click)

        # gtk doesn't like empty tags
        tag.set_property("editable", gtk.FALSE)

        if heading:
            tag.set_property("weight", pango.WEIGHT_BOLD)

        table = self._buffer.get_tag_table()
        table.add(tag)

        insert_one_tag_into_buffer(self._buffer, "link",
            "foreground", "blue",
            "underline", pango.UNDERLINE_SINGLE)

        self.clear()

    def addee(self):
        return self

    def packee(self):
        return self
    
    def _on_click(self, texttag, widget, event, iter):
        if event.type != gtk.gdk.BUTTON_RELEASE:
            return

        insert = self._buffer.get_iter_at_mark(self._buffer.get_insert()).get_offset()
        selection_bound = self._buffer.get_iter_at_mark(self._buffer.get_selection_bound()).get_offset()
        if insert != selection_bound:
            return
        
        position = iter.get_offset()

        for action in self.actions:
            if action[0] <= position < action[1]:
                # selection can be formed if we take too long dealing
                # with the click, so just schedule action, don't do immediately
                #utility.mainthread_call(action[2])
                #gtk.idle_add(action[2])
                gtk.timeout_add(0,action[2])
                break

    def clear(self):
        self.actions = [ ]
        self._buffer.delete(self._buffer.get_start_iter(), self._buffer.get_end_iter())

    def write(self, text, app=None, action=None):
        text = utility.force_unicode(text)
    
        symbols = re.split(r'( |\n|\t)', text)
        for symbol in symbols:
            this_action = action
            tags = ['default']
            stripped_symbol = strip_symbol(symbol)

            if not this_action and \
               (stripped_symbol[:5] == 'http:' or \
                stripped_symbol[:4] == 'ftp:' or \
                stripped_symbol[:4] == 'www.'):
                def this_action(symbol=stripped_symbol):
                    try:
                        utility.browse_url(symbol)
                    except error.Error,err:
                        app.show_error(err)

            if not this_action and \
               stripped_symbol[:12] == 'circle-file:' and app:
                def this_action(symbol=stripped_symbol,app=app):
                    try:
                        import search
                        search.search_for_name(hash.url_to_hash(symbol),'Files matching url', app.node,app)
                    except error.Error,err:
                        app.show_error(err)

            if this_action:
                tags.append('link')
                position = self._buffer.get_end_iter().get_offset()
                self.actions.append(
                  (position, position+len(symbol), this_action)
                )
            apply(self._buffer.insert_with_tags_by_name,[self._buffer.get_end_iter(), symbol]+tags)

# Human hashable representation of a name
        
def mid_point(a,b):
    return ((a[0]+b[0])/2.0,(a[1]+b[1])/2.0)

def bezier_curve(*list):
    for i in range(6):
        new_list = [ list[0] ]

        for j in range(0,len(list)-1):
            new_list.append( mid_point(list[j],list[j+1]) )

        new_list.append(list[-1])
        list = new_list

    return list

def quadratic(p0, p1, p2):
        x0, y0 = p0
        x1, y1 = p1
        x2, y2 = p2

        return "%f %f lineto %f %f %f %f %f %f curveto\n" % (x0, y0,
                              x0 + 2*(x1 - x0)/3.0,
                              y0 + 2*(y1 - y0)/3.0,
                              x1 + 1*(x2 - x1)/3.0,
                              y1 + 1*(y2 - y1)/3.0,
                              x2, y2)
    
class Signature(gtk.Button):
    height = 100
    width  = height * 3

    # FIXME: In python2.1, this results in 6.  In future python versions
    # it will result in 6.25, which means signatures look different
    # depending on python version, which reduces the efficacy of using
    # signatures for authentication.  One fix is to force to integer
    # division (explicit floor operation); though from the code it would
    # appear that 6.25 is the value that we actually want here.
    # Same comments apply to on_click below.  (Should these be using
    # common code?)

    # [pfh] added int( ), will maintain backward compatability

    step   = int( (width-height) / (settings.name_bytes*2) )
    
    def __init__(self, name):
        check.check_is_name(name)  #=@R43
        
        gtk.Button.__init__(self)
        self.connect_after("expose-event",self.on_expose)
        #self.connect_after("draw",self.on_expose)
        #self.add_events(GDK.BUTTON_PRESS_MASK)
        #self.connect("button_press_event",self.on_click, name)
        self.set_relief(gtk.RELIEF_NONE)
        self.connect("clicked",self.on_click, name)
        self.set_size_request(self.width,self.height)

        if sys.platform == 'win32':
            self.set_sensitive(gtk.FALSE)

        points = [ ]
        for i in range(settings.name_bytes*2):
            if i & 1 :
                x = ord(name[i >> 1]) >> 4
            else:
                x = ord(name[i >> 1]) & 0xf
            a = ([0.0, 1.25, 1.75, 3.0][x & 3]+1)/5.0
            b = ([0.0, 2.0, 2.5, 3.0][x >> 2]+1)/5.0
            points.append( (i*self.step + a*self.height,b*self.height) )

        self.lines = bezier_curve(points[0],points[1],mid_point(points[1],points[2]))[:-1]

        for i in range(1,len(points)-1):
            self.lines.extend(bezier_curve(mid_point(points[i-1],points[i]),points[i],mid_point(points[i],points[i+1]))[:-1])
        
        self.lines.extend(bezier_curve(mid_point(points[-3],points[-2]),points[-2],points[-1]))
    
    def on_expose(self, widget,event=None):
        alloc = widget.get_allocation()
        new_lines = [ ]
        for item in self.lines:
          new_lines.append((int(item[0]+alloc[0]),int(item[1]+alloc[1])))

        gtk.gdk.Drawable.draw_lines(widget.window,
                                    widget.get_style().fg_gc[0],
                                    new_lines)

    def on_click(self, widget, name):
        height = 100
        width  = height * 3
        
        step   = int( (width-height) / (settings.name_bytes*2) )
        
        fname = tempfile.mktemp() # because we want to run gv on the file,
        # we need to manage the file ourselves.  This could open us to
        # a symlink vuln.
        
        f = open(fname, "wt")
        
        f.write("""%%!PS-Adobe-2.0 EPSF-2.0
%%%%Title: signature
%%%%Creator: Circle
%%%%CreationDate: 
%%%%For: 
%%%%Orientation: Portrait
%%%%BoundingBox: 0 0 %f %f
%%%%Pages: 0
%%%%BeginSetup
%%%%EndSetup
%%%%Magnification: 1.0000
%%%%EndComments

/Times-Roman findfont
10 scalefont
setfont

newpath
2 2 moveto
(circle-person:%s) show

0 %f translate
1 -1 scale

newpath
""" % (width, height, string.join(map(lambda a:hex(ord(a))[2:], name), ''), height))
        
        points = [ ]
        for i in range(settings.name_bytes*2):
                if i & 1 :
                        x = ord(name[i >> 1]) >> 4
                else:
                        x = ord(name[i >> 1]) & 0xf
                a = ([0.0, 1.25, 1.75, 3.0][x & 3]+1)/5.0
                b = ([0.0, 2.0, 2.5, 3.0][x >> 2]+1)/5.0
                points.append( (i*self.step + a*self.height,b*self.height) )
        
        f.write("%f %f moveto\n" % (points[0][0], points[0][1]))
        f.write(quadratic(points[0],points[1],mid_point(points[1],points[2])))

        for i in range(1,len(points)-1):
            f.write(quadratic(mid_point(points[i-1],points[i]),points[i],mid_point(points[i],points[i+1])))
                
        f.write(quadratic(mid_point(points[-3],points[-2]),points[-2],points[-1]))
        f.write("stroke")
        f.close()
        
        try:
            os.system("( gv %s ; rm %s ) &" % (fname,fname))
        except OSError:
            pass

# Title label with drop-down help

class Helpful_label(gtk.HBox):
    def __init__(self, title, help, width=None):
        gtk.HBox.__init__(self, gtk.FALSE, 0)
        self.text_packed  = 0
        self.text_visible = 0

        vbox = gtk.VBox(gtk.FALSE,0)
        self.pack_start(vbox, gtk.TRUE, gtk.TRUE, 0)

        if type(title) == type(''):
            label = gtk.Label(title)
            label.set_alignment(0,0)
        else:
            # It's a widget
            label = title
        vbox.pack_start(label, gtk.TRUE, gtk.TRUE, 0)

        text = Text(width, heading=0)
        text.write('\n'+help+'\n')

        button = gtk.Button()
        button.set_relief(gtk.RELIEF_NONE)
        tooltips.set_tip(button,"help","")
        self.pack_start(button, gtk.FALSE, gtk.FALSE, 0)

        arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_IN)
        arrow.set_alignment(0.5, 1)
        button.add(arrow)

        def on_click(button, self=self,text=text,vbox=vbox,arrow=arrow):
            if not self.text_packed:
                vbox.pack_start(text, gtk.TRUE, gtk.TRUE, 0)
                self.text_packed = 1
            if not self.text_visible:
                text.show_all()
                self.text_visible = 1
                arrow.set(gtk.ARROW_UP,gtk.SHADOW_IN)
            else:
                text.hide()
                self.text_visible = 0
                arrow.set(gtk.ARROW_DOWN,gtk.SHADOW_IN)
        button.connect("clicked",on_click)

    def packee(self):
        return self


# A widget for navigating a directory and selecting files.

class Tree(gtk.ScrolledWindow):
    def __init__(self, initial_path,query_func,repr_func,on_selection_change=None):
        self.query_func = query_func
        self.repr_func = repr_func
        #self.on_selection_change = on_selection_change

        self.current_path = initial_path
        self.is_selected = 0
        self.paths = [ ]
        self.in_refresh = 0

        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
        self.list_widget = gtk.CList()
        self.list_widget.set_selection_mode(gtk.SELECTION_SINGLE)
        self.add(self.list_widget)

        self.refresh_display()

        def on_select(list, index,column,event, self=self):
            if self.in_refresh:
                return
            self.is_selected = 1
            self.current_path = self.paths[index]
            self.refresh_display()
            if on_selection_change:
                on_selection_change(self.current_path)
        def on_unselect(list, index,column,event, self=self):
            if self.in_refresh:
                return
            if self.paths[index] == self.current_path:
                self.is_selected = 0
            if on_selection_change:
                on_selection_change(None)
 
        self.list_widget.connect("select-row",on_select)
        self.list_widget.connect("unselect-row",on_unselect)


    def on_delete(self,item):
        
        # no need to remove it from list.
        # refresh_display does everything
        # self.list_widget.remove()
        self.refresh_display()
        self.list_widget.unselect_all()
        

    def get_selection(self):
        if not self.is_selected:
            return None
        else:
            return self.current_path

    def refresh_display(self):
        #if self.flags(gtk.DESTROYED):
        #    return

        self.in_refresh = 1

        result = self.query_func(self.current_path)
        if result != None:
            path = self.current_path
        else:
            path = self.current_path[:-1]
            result = self.query_func(path)
            if result == None: result = [ ]

        old_paths = self.paths
        self.paths = [ ]
        items = [ ]
        for i in range(len(path)):
            self.paths.append(path[:i+1])
            items.append( ('  '*i+self.repr_func(path[i]), black) )

        for item in result:
            self.paths.append(path + [item])
            items.append(('  '*len(path)+' '+self.repr_func(item),black))

        #adjustment = self.list_widget.get_vadjustment()
        #if adjustment.lower == adjustment.upper:
        #    old_point = None
        #else:
        #    old_point =  (adjustment.value-adjustment.lower)/(adjustment.upper-adjustment.lower) 

        self.list_widget.freeze()
        self.list_widget.unselect_all()
        
        if self.is_selected:

            index = old_paths.index(self.current_path)
            try:
                new_index = self.paths.index(self.current_path)
            except:
                new_index = 0

            while index > new_index:
                #Try to avoid losing scroll position
                self.list_widget.append([''])
                self.list_widget.remove(0)
                index = index - 1
            while index < new_index:
                self.list_widget.insert(0, [''])
                index = index + 1
            
            self.list_widget.select_row(index,0)
        
        while self.list_widget.rows < len(self.paths):
            self.list_widget.append([''])
        while self.list_widget.rows > len(self.paths):
            self.list_widget.remove(self.list_widget.rows-1)

        for i in range(len(items)):
            self.list_widget.set_text(i,0,items[i][0])
            self.list_widget.set_foreground(i,items[i][1])


        #if old_point != None:
            #pass#adjustment.set_value(old_point*(adjustment.upper-adjustment.lower)+adjustment.lower)

        self.list_widget.thaw()

        self.in_refresh = 0

    def packee(self):
        return self

green = gtk.gdk.color_parse("green")
black = gtk.gdk.color_parse("black")

def File_selector_widget(initial_path, only_directories=0):
    def query_func(path, only_directories=only_directories):
        path = apply(os.path.join,path)
        
        if sys.platform == 'win32' and path == '':
            list = [ ]
            for i in range(24):
                item = chr(ord('C')+i)+':\\'
                if os.path.exists(item):
                    list.append(item)

            return list

        if os.path.isdir(path):
            try:
                list = filter(lambda x: x[:1] != '.', os.listdir(path))
            except:
                return [ ]
            if only_directories:
                list = filter(lambda x,path=path: os.path.isdir(os.path.join(path,x)), list)
            list.sort()
            return list
        else:
            return None

    initial_path = os.path.abspath(initial_path)
    path = [ ]
    while 1:
        initial_path, name = os.path.split(initial_path)
        if not name:
            break
        path.insert(0,name)
    path.insert(0,initial_path)

    if sys.platform == 'win32':
        path.insert(0,'')
    
    return Tree(path, query_func, lambda x: x or 'My computer')

def File_selector_window(initial_path, only_directories, title,text,ok_action,parent_window=None):
    window = gtk.Window()
    window.set_title(title)
    window.set_default_size(400,500)
    window.set_border_width(10)
    if parent_window:
        window.set_transient_for(parent_window)

    vbox = gtk.VBox(gtk.FALSE,5)
    window.add(vbox)

    label = gtk.Label(text)
    label.set_alignment(0,0)
    label.set_justify(gtk.JUSTIFY_LEFT)
    vbox.pack_start(label, gtk.FALSE,gtk.FALSE,0)

    selector = File_selector_widget(initial_path,only_directories)
    vbox.pack_start(selector, gtk.TRUE, gtk.TRUE, 5)

    hbox = gtk.HBox(gtk.FALSE,5)
    vbox.pack_start(hbox, gtk.FALSE, gtk.FALSE, 0)

    button = gtk.Button('OK')
    def ok_clicked(b, window=window,selector=selector,ok_action=ok_action):
        path = selector.get_selection() 
        if not path:
            return
        window.destroy()
        if ok_action:
            ok_action(apply(os.path.join,path))
    button.connect("clicked",ok_clicked)
    hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)

    button = gtk.Button('Cancel')
    button.connect("clicked",lambda b,window=window: window.destroy())
    hbox.pack_start(button, gtk.TRUE, gtk.TRUE, 0)

    return window

class File_entry(gtk.HBox):
    def __init__(self, app, title,text,default='', only_directories=0, window=None):
        self.wrap_window = window
        self.only_directories = only_directories
        self.title = title
        self.text = text
        self.app = app

        gtk.HBox.__init__(self, gtk.FALSE,5)

        self.entry = gtk.Entry()
        self.entry.set_text(default)
        self.pack_start(self.entry, gtk.TRUE, gtk.TRUE, 0)

        button = gtk.Button(" Select... ")
        self.pack_start(button, gtk.FALSE,gtk.FALSE,0)

        def on_clicked(b,self=self):
            def on_ok(path,self=self):
                self.entry.set_text(path)
            self.app.show_window(
                File_selector_window('.',self.only_directories,
                                     self.title,self.text,on_ok,self.wrap_window),'select')

        button.connect("clicked",on_clicked)

    def get_text(self):
        # Filenames read from and passed to the operating system are simple
        # strings, i.e. a sequence of bytes, not necessarily valid utf-8 or
        # unicode.  So the canonical representation of a filename within Circle
        # internals is also a string, to avoid munging things.
        #
        # At the time of writing, our self.entry widget can't display non-utf8
        # strings (we get a warning on stderr), but still faithfully returns
        # the original string correctly, which is the most important thing.
        # Ideally we'd use a widget designed to hold filenames.
        return self.entry.get_text()


#class Toggle_icon(gtk.ToggleButton):
#    def __init__(self, s, huh=None):
#        gtk.ToggleButton.__init__(self)
#        self.add(gtk.Label(s))

def Toggle_icon(char, extra_space=0):
    widget = gtk.ToggleButton()
                                                                                
    height = 18
    unit = int(height/6)
                                                                                
    width = unit*2+8+extra_space*2
                                                                                
    x1 = 4+extra_space
    x2 = unit+4+extra_space
    x3 = unit*2+4+extra_space
    y1 = -unit
    y2 = 0
    y3 = +unit
                                                                                
    if char == '>':
        poly = [(x1,y1),(x2,y1),(x3,y2),(x2,y3),(x1,y3),(x2,y2)]
    else:
        poly = [(x2,y1),(x3,y1),(x2,y2),(x3,y3),(x2,y3),(x1,y2)]
                                                                                
    widget.set_size_request(width,height)

    def on_expose(widget, event, poly=poly):
        style = widget.get_style()
        alloc = widget.get_allocation()

        new_poly = [ ]
        for item in poly:
          new_poly.append((item[0]+alloc[0],item[1]+alloc[1]+alloc[3]/2))
                                                                                
        if widget.get_active():
            gc = style.dark_gc[3]
        else:
            gc = style.dark_gc[0]
                                                                                
        gtk.gdk.Drawable.draw_polygon(widget.window,gc,1,new_poly)
        gtk.gdk.Drawable.draw_polygon(widget.window,gc,0,new_poly)
                                                                                
    widget.connect_after("expose-event",on_expose)
    return widget


def Text_button(str):
    # where is this defined??
    PANGO_SCALE = 1024

    widget = gtk.Button()

    layout = widget.create_pango_layout(str)
    size = layout.get_size()
    widget.set_size_request(size[0]/PANGO_SCALE+4,size[1]/PANGO_SCALE+4)

    def on_expose(widget, event, layout=layout):
        style = widget.get_style()
        alloc = widget.get_allocation()

        gtk.gdk.Drawable.draw_layout(widget.window,style.fg_gc[0],alloc[0]+2,alloc[1]+2,layout)

    widget.connect_after("expose-event",on_expose)
    return widget

class Network_topology(gtk.Image):
    def __init__(self):
        gtk.Image.__init__(self)
        self.set_from_file(utility.find_file("pixmaps/diagram-bg.xpm"))
        self.connected = 0
        self.drawing_size = self.get_pixbuf().get_width()
        self.connect_after("expose-event",self.expose)
        self.my_angle = 0
        self.others_angle = [1,2, 3, 4]
        self.hashtable_running = 0

    def expose(self, widget,event):
        alloc = self.get_allocation()
        line_scale = self.drawing_size*15/32
        line_shift_x = alloc[0]+(alloc[2]+1)/2
        line_shift_y = alloc[1]+(alloc[3]+1)/2
        lines = [ ]

        if not self.others_angle and self.connected:
            self.connected = 0
            self.set_from_file(utility.find_file("pixmaps/diagram-bg-red.xpm"))
        if self.others_angle and not self.connected:
            self.connected = 1
            self.set_from_file(utility.find_file("pixmaps/diagram-bg.xpm"))
            
        
        for it in self.others_angle:
            it_p = complex(math.cos(it),math.sin(it))
            me_p = complex(math.cos(self.my_angle),math.sin(self.my_angle))

            if not self.hashtable_running:
                lines.append(
                    [ (int(it_p.real*line_scale+line_shift_x),int(it_p.imag*line_scale+line_shift_y)),
                      (int(it_p.real*line_scale*0.7+line_shift_x),int(it_p.imag*line_scale*0.7+line_shift_y)) ])
                continue

            chord_len = abs(it_p - me_p)
            if chord_len < 0.001:
                continue

            # Simpler code for drawing between almost-opposite points.
            if abs(it_p + me_p) * line_scale < 2 * 3.0:
                lines.append(
                    [ (int(me_p.real*line_scale+line_shift_x),int(me_p.imag*line_scale+line_shift_y)),
                      (int(it_p.real*line_scale+line_shift_x),int(it_p.imag*line_scale+line_shift_y)) ])
                continue

            n_bends = 8
            n_segments = n_bends + 1
            list = [ ]
            point = me_p
            tot_rot = (it_p / -me_p)
            rot = tot_rot ** (1.0/n_bends)

            delta = (chord_len * abs((rot - 1)
                                     / ((tot_rot * rot) - 1))
                     * -me_p)

            for i in range(n_segments + 1):
                list.append((int(point.real*line_scale+line_shift_x),\
                             int(point.imag*line_scale+line_shift_y)))
                point = point + delta
                delta = delta * rot

            lines.append(list)

        style = widget.get_style()
        
        for list in lines:
            gtk.gdk.Drawable.draw_lines(widget.window,style.light_gc[0],list)
        


# Status windows: not used anymore, but who knows...

class Status:
    def show(self, title,message, window=None, icon=None):
        import gtk

        self.window = gtk.Window()
        self.window.set_border_width(0)        
        self.window.set_default_size(300,10)
        if window:
            self.window.set_transient_for(window)
        self.window.set_title(title)

        hbox = gtk.HBox(0, 0)
        self.window.add(hbox)

        if icon:
            pixmap = gtk.Pixmap(self.window,find_file(icon))
            hbox.pack_start(pixmap, 0,0,0)

        align = gtk.Alignment(0,0,0,0)
        hbox.pack_start(align, 0,0,10)

        self.label = gtk.Label('\n' + message + '\n\n')
        self.label.set_justify(gtk.JUSTIFY_LEFT)
        align.add(self.label)

        #show_window(self.window, 'status')
        self.window.show()

    def close(self):
        self.window.destroy()

    def message(self, message):
        self.label.set_text('\n' + message + '\n\n')






    
# Here is a simple test we run if the module is run directly

if __name__ == '__main__':
    wind = gtk.Window()
    vbox = gtk.VBox(gtk.FALSE,5)
    
    widget = Helpful_label('Name:','Enter your name here.\n\neg: John Smith')
    vbox.pack_start(widget)

    widget = Text(50,1)
    widget.write("""Hello world! What a wonderful world.
    Supercalafragalisticexpialadociousiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii Yay Yay.\n\nYay!
    http://thecircle.org.au\n <({http://thecircle.org.au>)}""")
    gtk.timeout_add(3000, widget.write, """Hello world!
    What a wonderful world. Supercalafragalisticexpialadocious
    Yay Yay.\n\nYay!""")
    vbox.pack_start(widget)

    widget = Signature(hash.hash_of('bob'))
    vbox.pack_start(widget)
    # Proof of @R43: @E24.
    
    widget = File_selector_widget('/home/pfh',1)
    vbox.pack_start(widget)

    widget = Network_topology()
    widget.hashtable_running = 1
    vbox.pack_start(widget)
    
    widget = Toggle_icon('>')
    vbox.pack_start(widget)
    
    wind.add(vbox)
    #wind.set_size_request(400,400)

    #def action(path):
    #  print path

    #wind = File_selector_window('.',0, 'Selct a file','Please',action,None)
    
    vbox.pack_start(Text_button('hello'))

    wind.show_all()
    wind.connect("destroy", gtk.mainquit)
    wind.connect("delete_event", gtk.mainquit)
    gtk.mainloop()


# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
