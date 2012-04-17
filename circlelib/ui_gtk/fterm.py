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

#
#    Base fields library
#
#



import gtk, pango, threading, types, re, string
import widgets, circle_gtk
from circlelib import check, utility, error



def _augment(buffer, offset,augmentation):
    iter = buffer.get_iter_at_offset(offset)
    for item in augmentation:
        next_iter = iter.copy()
        next_iter.forward_char()
        buffer.apply_tag_by_name("aug"+str(ord(item)/16), iter, next_iter)
        iter = next_iter


class Field:
  
    def __init__(self, fterm, start=None, end=None, next=None):
        """Field.__init__:
	    fterm:  a reference back to the owning FieldTerm object
	    start: offset of the start of the field
	    end:   offset of the end of the field
            next:  the next field in the list.

	    action: this function is called when a
            mouse button is clicked in this field.
        """
	if (start is not None or end is not None):
	    check.check_has_type(start, types.IntType)
	    check.check_has_type(end, types.IntType)

        fterm.lock.acquire()
        try:
	    self.text=''
            self.fterm = fterm
            self.closed = 0
            self.attr = {}
            self.active = 0

            if start is not None:
                self.start = start
                self.end   = end
            else:
                self.start = fterm.prompt_start
                self.end   = fterm.prompt_start

            if next is not None:
                self.next = next
                self.prev = next.prev
                next.prev = self
                if self.prev:
                    self.prev.next = self
            else:
                self.next = None
                self.prev = fterm.last_field
                if fterm.last_field is not None:
                    fterm.last_field.next=self

                if fterm.first_field is None:
                    fterm.first_field = self
                fterm.last_field=self
                
        finally:
            fterm.lock.release()
    

    def on_click(self,handler,widget,event):
        return gtk.FALSE

    def set_active(self,active):
        if active:
            self.show(self.text)
            self.active=1
        else:
            Field.show(self,self.text,['grey'])
            self.active=0

    def context_menu(self,app):
        return []

    def popup_menu(self,widget,event,app,pos_func=None):
        menu = self.context_menu(app)
        menuwidget = gtk.Menu()
        for (text, action) in menu:
            mi = gtk.MenuItem(text)
            mi.connect("activate", action)
            mi.show()
            menuwidget.append(mi)
        #event.button
        # todo: should be able to popup where cursor is...
        menuwidget.popup(None,None,pos_func,3,event.time)



    def offset_successors(self,change):
        # Update these now so apply-tag event is not confused
        self.fterm.prompt_end = self.fterm.prompt_end + change
        self.fterm.prompt_start = self.fterm.prompt_start + change

        #offset all fields after me
        item = self.next
        while item is not None:
            item.start = item.start + change
            item.end   = item.end   + change
            item = item.next
        

    def show_gtk(self,str,tags=[],augmentation=None):
        """display text in the field. to be called from gtk thread only"""
        
        check.check_has_type(str, types.StringType)

        circle_gtk.check_is_gtkthread()
        if self.closed:
            return
        if type(tags) != type([]):
            tags = [tags]
        if tags == []:
            tags = [ "black" ]
        if type(str) == type(''):
            str = unicode(str,'ascii','replace')
            
        self.text = str
        change = len(str) - (self.end - self.start)
        self.offset_successors(change)
        
        self.gtk_show(str,tags,augmentation,self.start, self.end)
        self.end = self.end + change


    def show(self,str,tags=[],augmentation=None):
        """display text in the field. to be called from non gtk threads"""
        
        if self.closed:
            return
        if type(tags) != type([]):
            tags = [tags]
        
        if tags == []:
            tags = [ "grey" ]
        
        if type(str) == type(''):
            str = unicode(str,'ascii','replace')

        self.text = str
        change = len(str) - (self.end - self.start)
        self.offset_successors(change)

        #gtk.idle_add(self.gtk_show,str,tags,augmentation,self.start, self.end)
        gtk.timeout_add(0,self.gtk_show,str,tags,augmentation,self.start, self.end)
                
        self.end = self.end + change

    def apply_tags(self,tags):
        circle_gtk.check_is_gtkthread()
        for tag in tags + ['clickable']:
            self.fterm.buffer.apply_tag_by_name(
                tag,
                self.fterm.buffer.get_iter_at_offset(self.start),
                self.fterm.buffer.get_iter_at_offset(self.end))

    def remove_tags(self,tags):
        circle_gtk.check_is_gtkthread()
        for tag in tags:
            self.fterm.buffer.remove_tag_by_name(
                tag,
                self.fterm.buffer.get_iter_at_offset(self.start),
                self.fterm.buffer.get_iter_at_offset(self.end))
       

    def gtk_show(self,str,tags,augmentation, start, end):
        """Internal function: never use it, always use show """
        circle_gtk.check_is_gtkthread()
        self.fterm.lock.acquire()
        cursor_was_visible = self.fterm.is_cursor_visible()
        if start != end:
            self.fterm.buffer.delete(
                self.fterm.buffer.get_iter_at_offset(start),
                self.fterm.buffer.get_iter_at_offset(end))
        # insert_with_tags_by_name broken, so do it ourselves
        self.fterm.buffer.insert(
            self.fterm.buffer.get_iter_at_offset(start),str)
        self.fterm.buffer.remove_all_tags(
            self.fterm.buffer.get_iter_at_offset(start),
            self.fterm.buffer.get_iter_at_offset(start+len(str)))
        for tag in tags + ['clickable']:
            self.fterm.buffer.apply_tag_by_name(
                tag,
                self.fterm.buffer.get_iter_at_offset(start),
                self.fterm.buffer.get_iter_at_offset(start+len(str)))
        if augmentation:
            _augment(self.fterm.buffer, start, augmentation)

        #apply(self.fterm.buffer.insert_with_tags_by_name,
        #    [ self.fterm.buffer.get_iter_at_offset(self.start),
            #  str ] + tags)

        if cursor_was_visible:
            self.fterm.force_cursor_onscreen()
        self.fterm.lock.release()


    def close(self):
        """ close field.
        deprecated?
        """

        return

        #do not close clickable fields...
        if self.on_click is not None:
            return

        self.closed=1
	self.fterm.lock.acquire()

        if self==self.fterm.first_field:
            self.fterm.first_field=self.next
        if self==self.fterm.last_field:
            self.fterm.last_field=self.prev
        if self.prev:
            self.prev.next= self.next
        if self.next:
            self.next.prev = self.prev                
        self.fterm.lock.release()


class Active_Field(Field):
    def __init__(self, fterm, start=None, end=None, next=None):
        Field.__init__(self, fterm, start, end, next)
        self.active=1



class Field_Tabular:
  def __init__(self,chat,rows,first_field):
    """
    that object should possess one field as anchor
    it should also be able to order its lines

    """
    self.first_field=first_field
    self.last_field=chat.get_field_after(first_field)
    
  def show_line(line_items):
    pass

  def get_field_at(index):
    pass
  
  


class FTerm:
    """
    field-based terminal
    the most convenient way to display something is to send xml formatted input
    """


    def get_insertion_offset(self):
        insertion_mark = self.buffer.get_insert()
        return self.buffer.get_iter_at_mark(insertion_mark).get_offset()

    def is_cursor_visible(self):
        insertion_mark = self.buffer.get_insert()
        y, height = self.view.get_line_yrange(
            self.buffer.get_iter_at_mark(insertion_mark) )
        visible = self.view.get_visible_rect()

        return y <= visible.y+visible.height and y+height >= visible.y

    def force_cursor_onscreen(self):
	self.view.scroll_to_mark(self.buffer.get_insert(),0,gtk.FALSE,0,0)

    def on_begin_user_action(self, buffer):
        self.buffer_user_active = 1

    def on_end_user_action(self, buffer):
        self.buffer_user_active = 0

    def enter_direct_mode(self):
        self.set_prompt('')
        self.mode='direct_mode'

    def enter_command_mode(self):
        self.mode='command_mode'

    def on_key_press(self, _w,_e):
        self.key_presses[_e.keyval] = (_e.time, self.get_insertion_offset() - self.prompt_end)
        

        if _e.string and not _e.string.isalpha():
            self._reaugment_word(self.get_insertion_offset())

        if _e.keyval == 65383: # Menu
            field= self.last_field
            while field:
                if field.start <= self.get_insertion_offset() < field.end:
                    if field.active:
                        def pos_func(x):
                            mark = self.buffer.get_insert()
                            iter = self.buffer.get_iter_at_mark(mark)
                            r    = self.view.get_iter_location(iter)
                            x,y  = self.view.buffer_to_window_coords(gtk.TEXT_WINDOW_WIDGET,r.x,r.y)
                            xx,yy = self.handler.app.window.get_position()
                            xxx,yyy = self.view.window.get_position()
                            return xxx+xx+x,yyy+yy+y+30,gtk.TRUE
                        field.popup_menu(_w,_e,self.handler.app,pos_func)
                        return gtk.TRUE
                    else:
                        return gtk.FALSE
                field=field.prev
            return gtk.FALSE

            
        if _e.keyval == 65293: # Enter

            if self.mode == 'edit_mode':
                self.mode = 'command_mode'
                text = widgets.get_uslice(
                    self.buffer.get_iter_at_offset(self.edited_field.start),
                    self.buffer.get_iter_at_offset(self.edited_field.end))

                self.edited_field.on_edit(text)
                self.view.emit_stop_by_name("key-press-event")
                return

            if self.completion_field:
                self.completion_field.show_gtk('')
                self.completion_field = None
            offset = self.get_insertion_offset()
            if offset < self.prompt_end:
                self.buffer.place_cursor(self.buffer.get_end_iter())
                self.view.emit_stop_by_name("key-press-event")
                return

            if widgets.get_uslice(
                 self.buffer.get_iter_at_offset(offset-1),
                 self.buffer.get_iter_at_offset(offset)
               ) == '\\':
                return

            command = widgets.get_uslice(self.buffer.get_iter_at_offset(self.prompt_end),
                                         self.buffer.get_end_iter())
            command_aug = self.augmentation
            if command:
                self.history[-1] = command
                self.history.append('')
                self.history_position = len(self.history)-1

	    self.prompt_start = self.buffer.get_end_iter().get_offset()
	    self.prompt_end = self.prompt_start
            self.augmentation = ''
            self.show('\n') # note: gtk_show was needed here
	    self.buffer.place_cursor(self.buffer.get_end_iter())
            
            #command = string.replace(command,'\\\n','\n')
            min_index = 0
            while 1:
                index = command.find('\\\n')
                if index < min_index: break
                min_index = index
                command = command[:index] + command[index+1:]
                command_aug = command_aug[:index] + command_aug[index+1:]
            
            self.view.emit_stop_by_name("key-press-event")

            #handler might be chat, or a shell...
            self.handler.handle_user_entry(command, command_aug)
            return
 
        if _e.state & 5: # Ctrl

            prefix = widgets.get_uslice(
              self.buffer.get_iter_at_offset(self.prompt_end),
              self.buffer.get_end_iter())
            self.handler.handle_control_key(prefix,_e)
            #return gtk.TRUE
            
        if _e.keyval == 65289:    #tabulation
          
            # auto-completions
            # todo: the info used here should not belong to the tfield object
            # completions should be registered, like commands
            
            prefix = widgets.get_uslice(self.buffer.get_iter_at_offset(self.prompt_end),
                                        self.buffer.get_end_iter())
            return self.handler.handle_tabulation_key(prefix,_e)


        
        position = self.get_insertion_offset() - self.prompt_end
        if position >= 0 and _e.keyval in [65362, 65364]:
            command = widgets.get_uslice(self.buffer.get_iter_at_offset(self.prompt_end),
                                        self.buffer.get_end_iter())
	    
            if string.find(command[:position],'\n') == -1 and \
               _e.keyval == 65362: # Up arrow
                if self.history_position > 0:
                    self.history[self.history_position] = command
                    self.history_position = self.history_position - 1
		    str = self.history[self.history_position]
                    self.buffer.delete(
                        self.buffer.get_iter_at_offset(self.prompt_end),
                        self.buffer.get_end_iter())
                    self.buffer.insert(self.buffer.get_end_iter(), str)
		    self.force_cursor_onscreen()
                return 1

            if string.find(command[position:],'\n') == -1 and \
                 _e.keyval == 65364: # Down arrow
                if self.history_position < len(self.history)-1:
                    self.history[self.history_position] = command
                    self.history_position = self.history_position + 1
                    str = self.history[self.history_position]
                    self.buffer.delete(
                        self.buffer.get_iter_at_offset(self.prompt_end),
                        self.buffer.get_end_iter())
                    self.buffer.insert(self.buffer.get_end_iter(), str)
                    self.buffer.place_cursor(self.buffer.get_iter_at_offset(self.prompt_end))
		    self.force_cursor_onscreen()
                return 1

    def on_key_release(self, _w,_e):
        if not self.app.config['augmented_text']:
            return

        if not self.key_presses.has_key(_e.keyval):
            return

        press_time, offset = self.key_presses[_e.keyval]
        del self.key_presses[_e.keyval]

        string = utility.force_unicode(_e.string)
        if not string or \
           ord(string) < 32:
             return

        if offset < 0 or offset >= len(self.augmentation):
            return

        if string.isalpha():
            interval = (_e.time - press_time) / 1000.0
            level = int( interval*4 *255)
            if level < 0: level = 0
            if level > 255: level = 255
        else:
            level = 128

        tag = "aug" + str(level/16)
        iter1 = self.buffer.get_iter_at_offset(self.prompt_end+offset)
        iter2 = iter1.copy()
        iter2.forward_char()
        self.augmentation = self.augmentation[:offset] + \
                            chr(level) + \
                            self.augmentation[offset+1:]
        self.buffer.remove_all_tags(iter1,iter2)
        self.buffer.apply_tag_by_name(tag,iter1,iter2)

    def on_scroll(self, widget, event):
        adj = self.widget.get_vadjustment()
        if event.direction == gtk.gdk.SCROLL_UP:
            adj.set_value(adj.value - adj.step_increment)
        if event.direction == gtk.gdk.SCROLL_DOWN:
            adj.set_value(adj.value + adj.step_increment)
        
    def on_mark_set(self, buffer, iter, mark):
        if mark.get_name() == 'insert' and \
           self.prompt_start <= self.buffer.get_iter_at_mark(mark).get_offset() < self.prompt_end:
            self.buffer.move_mark(mark, self.buffer.get_iter_at_offset(self.prompt_end))


    def on_click(self, tag, widget, event, iter):

        if event.type != gtk.gdk.BUTTON_RELEASE and event.type != gtk.gdk.BUTTON_PRESS :            
            return gtk.FALSE

        # Is there a selection? If yes, we won't deal with it.
        insert = self.buffer.get_iter_at_mark(
            self.buffer.get_insert()).get_offset()
        selection_bound = self.buffer.get_iter_at_mark(
            self.buffer.get_selection_bound()).get_offset()
        if insert != selection_bound:
            return gtk.FALSE

        # test if we clicked in a field
        field= self.last_field
        while field:
            if field.start <= iter.get_offset() < field.end:
                if field.active:
                    return field.on_click(self.handler,widget,event)
                else:
                    return gtk.FALSE
            field=field.prev

        # Is there a dragged item?
        if event.type == gtk.gdk.BUTTON_RELEASE and event.button == 2 and self.drag:
            self.paste_file_field(self.drag)
            self.drag = None
            self.view.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
            return gtk.TRUE
            
        return gtk.FALSE
    
    def on_delete(self, _w,start,end):
        if self.buffer_user_active\
               and self.mode == 'command_mode'\
               and start.get_offset() < self.prompt_end:
            self.buffer.emit_stop_by_name("delete-range")
            return

        if self.mode == 'edit_mode':
            if start.get_offset() < self.edited_field.start:
                self.buffer.emit_stop_by_name("delete-range")
                return
            if end.get_offset() > self.edited_field.end:
                self.buffer.emit_stop_by_name("delete-range")
                return
            change = - end.get_offset() + start.get_offset()
            self.edited_field.offset_successors(change)
            self.edited_field.end += change
            
        if self.mode == 'command_mode':
            start_offset = start.get_offset() - self.prompt_end
            end_offset = end.get_offset() - self.prompt_end
            if start_offset < 0:
                return
            self.augmentation = self.augmentation[:start_offset] + \
                                self.augmentation[end_offset:]


    def insert_at_end(self,str):
        self.lock.acquire()
        self.buffer.insert(self.buffer.get_end_iter(),str)
        self.lock.release()                        


    def delete_line(self):
        self.lock.acquire()
        self.buffer.delete(self.buffer.get_iter_at_offset(
          self.prompt_end),self.buffer.get_end_iter())
        self.lock.release()                        


    def _on_insert_helper(self, offset, str, length):
        offset = offset - self.prompt_end
        if offset < 0:
            return

        self.augmentation = self.augmentation[:offset] + \
                            chr(128)*len(str) + \
                            self.augmentation[offset:]

    def _reaugment_word(self, word_end_offset):
        if not self.app.config['augmented_text']:
            return

        word_start_offset = word_end_offset

        # TODO: do purely with iters?
        while widgets.get_uslice(
                  self.buffer.get_iter_at_offset(word_start_offset-1),
                  self.buffer.get_iter_at_offset(word_start_offset)
              ).isalpha():
            word_start_offset -= 1

        if word_start_offset == word_end_offset:
            return

        iter1 = self.buffer.get_iter_at_offset(word_start_offset) 
        iter2 = self.buffer.get_iter_at_offset(word_end_offset) 

        word_start_offset -= self.prompt_end
        word_end_offset -= self.prompt_end
        length = word_end_offset - word_start_offset

        sum = 0
        for char in self.augmentation[word_start_offset:word_end_offset]:
            sum += ord(char)

        average = sum / length
        tag = "aug" + str(average/16)

        self.augmentation = self.augmentation[:word_start_offset] + \
                            chr(average) * length + \
                            self.augmentation[word_end_offset:]
        
        self.buffer.remove_all_tags(iter1,iter2)
        self.buffer.apply_tag_by_name(tag,iter1,iter2)

    def on_insert(self, _w, iter, str, length):
        str = utility.force_unicode(str)

        if not self.buffer_user_active:
            self._on_insert_helper(iter.get_offset(),str,length)
	    return

        if self.mode == 'direct_mode':
            self.buffer.emit_stop_by_name("insert-text")
            self.handler.handle_direct_mode(str)

        elif self.mode == 'command_mode':
            if iter.get_offset() < self.prompt_end:
                self.buffer.emit_stop_by_name("insert-text")
                self.buffer.place_cursor(self.buffer.get_iter_at_offset(self.prompt_end))
                self.buffer.insert(self.buffer.get_iter_at_offset(self.prompt_end), str)
                return
            self._on_insert_helper(iter.get_offset(),str,length)

        elif self.mode == 'edit_mode':
            if iter.get_offset() < self.edited_field.start:
                self.buffer.emit_stop_by_name("insert-text")
                self.buffer.place_cursor(self.buffer.get_iter_at_offset(self.edited_field.start))
                return
            if iter.get_offset() > self.edited_field.end:
                self.buffer.emit_stop_by_name("insert-text")
                self.buffer.place_cursor(self.buffer.get_iter_at_offset(self.edited_field.start))
                return
            change = len(str)
            self.edited_field.offset_successors(change)
            self.edited_field.end += change
        else:
            print "unknown mode"

    def on_draw(self, widget, event):
        self.widget_visible = (event.state != gtk.gdk.VISIBILITY_FULLY_OBSCURED)
        if self.widget_visible:
            #self.n_unseen_messages = 0
            self.app.set_title()

    def on_apply_tag(self, widget, tag, iter1, iter2):
        if tag.get_property('name')[:3] != 'aug' and \
           iter1.get_offset() >= self.prompt_end:
            self.buffer.emit_stop_by_name("apply-tag")
    
    def create_tags (self):
        def insert_one_tag_into_buffer(buffer, name, *params):
            tag = gtk.TextTag(name)
            while(params):
                tag.set_property(params[0], params[1])
                params = params[2:]
            table = buffer.get_tag_table()
            table.add(tag)

        
        insert_one_tag_into_buffer(self.buffer,
                                   "italic",
                                   "style", pango.STYLE_ITALIC)
        insert_one_tag_into_buffer(self.buffer,
                                   "bold",
                                   "weight", pango.WEIGHT_BOLD)  
        insert_one_tag_into_buffer(self.buffer,
                                   "indented",
                                   "left-margin", 25)  
        insert_one_tag_into_buffer(self.buffer,
                                   "monospace",
                                   "font-desc", pango.FontDescription('monospace'))  

        insert_one_tag_into_buffer(self.buffer,
                                   "softly",
                                   "foreground", "gray30")
        insert_one_tag_into_buffer(self.buffer,
                                   "grey",
                                   "foreground", "gray40")  
        insert_one_tag_into_buffer(self.buffer,
                                   "light_grey",
                                   "foreground", "grey50")  
        insert_one_tag_into_buffer(self.buffer,
                                   "quiet",
                                   "foreground", "chartreuse4")  
        insert_one_tag_into_buffer(self.buffer,
                                   "people",
                                   "foreground", "blue")  
        insert_one_tag_into_buffer(self.buffer,
                                   "files",
                                   "foreground", "blue")  
        insert_one_tag_into_buffer(self.buffer,
                                   "links",
                                   "foreground", "blue")  
        insert_one_tag_into_buffer(self.buffer,
                                   "black",
                                   "foreground", "black")  
        insert_one_tag_into_buffer(self.buffer,
                                   "active",
                                   "foreground", "purple")  
        insert_one_tag_into_buffer(self.buffer,
                                   "red",
                                   "foreground", "red")  
        insert_one_tag_into_buffer(self.buffer,
                                   "error",
                                   "foreground", "purple")  
        insert_one_tag_into_buffer(self.buffer,
                                   "hilite",
                                   "background", "DarkSeaGreen1")  
        insert_one_tag_into_buffer(self.buffer,
                                   "not_editable",
                                   "editable", gtk.FALSE)


        for i in range(16):
            r = max(0, 255*(i-8)/7)
            g = max(0, 196*(8-i)/8)
            b = max(0, 196*(8-i)/8)
            insert_one_tag_into_buffer(self.buffer,
                                       "aug"+str(i),
                                       "foreground", "#%02x%02x%02x"%(r,g,b))  
 
        tag = gtk.TextTag("clickable")

        # gtk may not like empty tags (?)
        tag.set_property("editable", gtk.TRUE)

        tag.connect("event", self.on_click)
        table = self.buffer.get_tag_table()
        table.add(tag)


    def reset_tabs(self):
        circle_gtk.check_is_gtkthread()
        self.tabs.set_tab(0,pango.TAB_LEFT,50)
        self.tabs.set_tab(1,pango.TAB_LEFT,60)
        self.tabs.set_tab(2,pango.TAB_LEFT,80)
        self.tabs.set_tab(3,pango.TAB_LEFT,70)
        self.view.set_tabs(self.tabs)
        self.maxlen=2


    # field management
    def get_field(self, constructor=Field):
        """Creates and returns a new field located at the end of the list"""
        return constructor(self)

    def get_field_from_text(self,begin,end,constructor=Field):
        """field in the command line. use with caution"""
        return constructor(self, begin, end)

    def get_field_before(self,field, constructor = Field):
        """Creates and returns a new field located before field"""
        return constructor(self, field.start, field.start, field)

    def get_field_after(self,field, constructor = Field):
        """Creates and returns a new field located after field"""
        return constructor(self, field.end, field.end, field.next)

    def show(self,str,tags='grey',augmentation=None):
        """This function creates and shows a new field at the end of the field list
        """
        field = self.get_field(Field)
        field.show(str,tags,augmentation)
        return field

    def show_before(self,field,str,type=Field):
        """This function creates and shows a new field immediately before field.
        """
        previous=self.get_field_before(field,type)
        if previous:
            previous.show(str)
            previous.close()
        return previous

    def show_after(self,field,str,type=Field):
        """This function creates and shows a new field immediately after field.
        """
        next=self.get_field_after(field,type)
        if next:
            next.show(str)
            next.close()
        return next




    def show_xml(self,str,before_field=None):
        """
        ixml parser.
        Should do nothing in text mode.
        uses markers:
        <file>, <channel>, <link>, <person>, <field>

        <field> means no type, just some text

        use references for fields:
        
        <field ref='xxx'> blah</field> for a dynamic field
        options: ref, before, after
        example:
        <field ref='zz' before='yy'> fgfgf </field>
        <file ref='zz' url='??'> gg </file>

        """

        #before_field indicates where we are going to write
        if before_field:
            index = self.get_field_before(before_field)
        else:
            index = self.get_field()
        
        first_field = self.get_field_before(index)
        last_field = index
        
        while 1:
            match = re.search('<\s*[^<>"\s]*(\s*[^<>"\s]*="[^<>"]*")*\s*>',str)
            if not match:
                break
            match_start, match_end = match.span()
            rest = str[match_end:]

            inside = str[match_start+1:match_end-1]
            type = inside.split()[0]
            field_type = self.markers[type]
            list = re.findall('[^<>"\s]*="[^<>"]*"',inside)
            
            match2 = re.search('</'+type+'>',rest)
            if not match2:
                raise error.Error("parsing error: %s %s %s"%(str,rest))
                break
            match2_start, match2_end = match2.span()

            #show the text that is before
            self.show_before(index,str[:match_start])

            options = {}
            for item in list:
                name,value = item.split('=')
                options[name]=value[1:-1]
            
            if not options.has_key('ref'):
                if options.has_key('before'):
                    field = self.get_field_before(self.ref_field[options['before']],field_type)
                elif options.has_key('after'):
                    field = self.get_field_after(self.ref_field[options['after']],field_type)
                else:
                    field = self.get_field_before(index,field_type)
            else:
                key = options['ref']
                if self.ref_field.has_key(key):
                    field = self.ref_field[key]
                    if options.has_key('before'):
                        print "warning: unexpected tag 'before', ignoring"
                    if options.has_key('after'):
                        print "warning: unexpected tag 'after', ignoring"
                else:
                    if options.has_key('before'):
                        field = self.get_field_before(self.ref_field[options['before']],field_type)
                    elif options.has_key('after'):
                        field = self.get_field_after(self.ref_field[options['after']],field_type)
                    else:
                        field = self.get_field_before(index,field_type)
                    self.ref_field[key]=field

            #make sure the object is copied...
            for o in options.keys():
                field.attr[o]=options[o]
            
            if type == 'link':
                field.page_begin = first_field
                field.page_end   = last_field

            if field.attr.has_key('tags'):
                tags = field.attr['tags']
            else:
                tags = []

            if field.attr.has_key('augmentation'):

                augmentation = field.attr['augmentation']
                value = 0L
                for i in range(len(augmentation)):
                    value = (value<<4) + eval('0x'+augmentation[i])
                str = ''
                for i in range(len(augmentation)/2):
                    str = chr(value & 0xff) + str 
                    value = value >> 8
                augmentation = str
            else:
                augmentation = None

            field.show(rest[:match2_start],tags,augmentation)

            #here the loop goes on with the rest
            str = rest[match2_end:]
            
        self.show_before(index,str,Field)



    def __init__(self,app,handler):
      
        self.app = app
        self.handler=handler
        self.lock = threading.RLock()

        #the list of fields
        self.first_field = None
        self.last_field = None
        #maybe not needed, fields by name
        self.ref_field = {}

        self.history = [ '' ] # Command history
        self.history_position = 0

        #self.lock.acquire()
        self.completion_field = None
        
	self.prompt_end = 0
	self.prompt_start = 0
        self.drag = None       # drag and drop object
        
	self.buffer_user_active = 0 # Are we processing events from a user action?
        self.augmentation = '' # Key press intencity for chars in user entry area
        self.key_presses = { } # When and where were keys pressed (use in key release to update augmentation)

        self.sw = gtk.ScrolledWindow(None, None)
        self.sw.set_policy(gtk.POLICY_AUTOMATIC,
                           gtk.POLICY_NEVER)
	self.sw.set_size_request(100,100)
        #self.sw.add_mask(gtk.gdk.BUTTON_PRESS_EVENT)
        
        self.view = gtk.TextView()
        self.view.set_left_margin(5)
        self.view.set_right_margin(5)
        self.view.set_wrap_mode(gtk.WRAP_WORD)

        self.tabs=pango.TabArray(4,1)
        self.reset_tabs()

        self.mode = 'command_mode'
        # can be command_mode or edit_mode or direct_mode
        # in direct_mode, the shell will do everything

        self.buffer = self.view.get_buffer()
        self.create_tags() # build up the tag table for this buffer
        
        self.sw.add(self.view)
        self.widget = self.sw
        
        self.view.connect("key-press-event",self.on_key_press)
        self.view.connect("key-release-event",self.on_key_release)
        self.view.connect("scroll-event",self.on_scroll)

        #this is for clicking in empty regions:
        #self.view.connect("event", self.on_click)

	self.buffer.connect("begin-user-action",self.on_begin_user_action)
	self.buffer.connect("end-user-action",self.on_end_user_action)
        self.buffer.connect("delete-range",self.on_delete)
        self.buffer.connect("insert-text",self.on_insert)
        self.buffer.connect("mark-set",self.on_mark_set)
        
        #self.buffer.connect("apply-tag",self.on_apply_tag)
        
        self.widget_visible = 1
        
        self.view.connect("visibility-notify-event",self.on_draw)
        self.view.set_events(gtk.gdk.VISIBILITY_NOTIFY_MASK)

        self.apply_colors()

        self.markers = {}
        self.register_marker('field',Field)


    def register_marker(self,marker,field_obj):
        self.markers[marker]= field_obj


    def apply_colors(self):

        self.lock.acquire()        
        (r, g, b) = self.app.config['background_color']
        col = self.view.get_colormap().alloc_color(r,g,b)
        self.view.modify_base(gtk.STATE_NORMAL,col)

        (r, g, b) = self.app.config['text_color']
        col = self.view.get_colormap().alloc_color(r,g,b)
        self.view.modify_text(gtk.STATE_NORMAL,col)

        self.lock.release()

        def apply_color(self,color_name):
            (r,g,b) = self.app.config[color_name+'_color']
            tag = self.buffer.get_tag_table().lookup(color_name)
            tag.set_property("foreground", "#%02x%02x%02x"%(r>>8,g>>8,b>>8))
            
        apply_color(self,"people")
        apply_color(self,"files")
        apply_color(self,"links")
        apply_color(self,"quiet")
        apply_color(self,"active")

        (r_text,g_text,b_text) = self.app.config['text_color']
        (r_bg  ,g_bg  ,b_bg  ) = self.app.config['background_color']
        
        r = (int(r_text *0.6 + r_bg *0.4))
        g = (int(g_text *0.6 + g_bg *0.4)) 
        b = (int(b_text *0.6 + b_bg *0.4)) 
        tag = self.buffer.get_tag_table().lookup("grey")
        tag.set_property("foreground", "#%02x%02x%02x"%(r>>8,g>>8,b>>8))

        r = (int(r_text *0.3 + r_bg *0.7)) 
        g = (int(g_text *0.3 + g_bg *0.7))
        b = (int(b_text *0.3 + b_bg *0.7)) 
        tag = self.buffer.get_tag_table().lookup("light_grey")
        tag.set_property("foreground", "#%02x%02x%02x"%(r>>8,g>>8,b>>8))

        for i in range(16):
            r = max(0, (r_text >>8) + 255*(i-8)/7)
            r = min(255,r)
            g = max(0, (g_text >>8) + 196*(8-i)/8)
            g = min(255,g)
            b = max(0, (b_text >>8) + 196*(8-i)/8)
            b = min(255,b)
            tag= self.buffer.get_tag_table().lookup("aug"+str(i))
            tag.set_property("foreground", "#%02x%02x%02x"%(r,g,b))


        

    def clear(self):
        self.lock.acquire()
        #self.view.set_iter(self.view.get_length())
        self.buffer.delete(self.buffer.get_start_iter(),
                           self.buffer.get_end_iter())
        
        item=self.first_field
        while item is not None:
            item.closed=1
            item=item.next
        self.first_field = None
        self.last_field = None
        self.completion_field = None
        self.prompt_start = 0
        self.prompt_end = 0

        self.file_list = []
        self.file_list_nickname=''
        self.file_list_path=''
        
        self.lock.release()
        self.show("\n")
        self.reset_tabs()
        for player in self.app.music_manager.playlist:
            player.field= None

    def delete_fields(self,field_start,field_end):
        """delete an interval of fields"""
        self.lock.acquire()
        start_iter=self.buffer.get_iter_at_offset(field_start.start)
        end_iter=self.buffer.get_iter_at_offset(field_end.end)
        change=field_end.end-field_start.start
        self.buffer.delete(start_iter,end_iter)

        prev = field_start.prev
        next = field_end.next
        if prev:
            prev.next=next
        else:
            self.first_field=next
        if next:
            next.prev=prev
        else:
            self.last_field=prev
            
        item=next
        while item:
            item.start = item.start - change
            item.end   = item.end   - change
            item=item.next

        item=field_start
        field_end.next=None
        while item:
            item.closed=1
            item=item.next
            
        self.prompt_start = self.prompt_start-change
        self.prompt_end = self.prompt_end-change
        self.lock.release()

    def edit_field(self,field):
        # place the cursor in the field,
        # do not let it out of the area until validation
        self.edited_field = field
        self.edited_field.apply_tags(["active"])
        self.mode = 'edit_mode'
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(self.edited_field.start))


    def set_prompt(self,str,tags=[]):

        prompt_start = self.prompt_start
        field = Field(self, self.prompt_start, self.prompt_end)

        #field = self.get_field()
        #self.fields.append(field)
        # Proof of @R45: as per @L1.
        # Proof of @R47: self isinstance Chat_gtk; @I26,@I27.
        # Proof of @R46: index unspecified, its default is None.
        
        field.show(str+' ', tags) #!start, end might change
        #field.start = field.end
        #field.gtk_show(' ', ['aug8'])
        field.close()
        
        self.lock.acquire()
        self.prompt_start = prompt_start
        self.prompt_end = field.end
        self.lock.release()



    def set_tabs(self,length):
        """The first column is the title or filename (variable width)
           The second is the size for files (width 70)
           The third is the mimetype (width 90)
        """
        
        circle_gtk.check_is_gtkthread()
        if length>self.maxlen:
            self.maxlen=length
            if self.maxlen>90:
                self.maxlen=90
            self.tabs.set_tab(0,pango.TAB_LEFT,self.maxlen*7)
            self.tabs.set_tab(1,pango.TAB_LEFT,self.maxlen*7+70)
            self.tabs.set_tab(2,pango.TAB_LEFT,self.maxlen*7+70+90)
            self.view.set_tabs(self.tabs)


    def insert_field(self,orig_field,str,constructor):

        begin = self.get_insertion_offset()
        if self.prompt_end > begin:
            begin=self.prompt_end
        end = begin + len(str)

        buffer = self.buffer
        iter = buffer.get_iter_at_offset(begin)
        buffer.insert_with_tags_by_name(iter,str,"files")
        
        field = self.get_field_from_text(begin,end,constructor)
        field.show(str)
        return field



# vim: expandtab:shiftwidth=4:tabstop=8:softtabstop=4 :
