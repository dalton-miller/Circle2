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

import gtk
import sys
from circlelib import utility, check


class Download_manager:
    """
    This is just the downloads window.
    I guess I do not need a class for that,
    a function that raises the window would do it
    """
    
    def __init__(self, app, vbox):
        import gtk

        self.app=app
        self.file_server = app.file_server
        self.vbox = vbox

        scrolly = gtk.ScrolledWindow()
        scrolly.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        vbox.pack_start(scrolly, 1,1,0)
        scrolly.show()

        self.list = gtk.CList(2)
        self.list.set_column_width(0,250)
        self.list.set_selection_mode(gtk.SELECTION_SINGLE)
        scrolly.add(self.list)
        self.list.show()

        self.hbox = gtk.HBox(0,5)
        self.cancel_button = gtk.Button('Cancel download')
        self.hbox.pack_start(self.cancel_button, 1,1,0)

        self.play_button = gtk.Button('Play')
        self.hbox.pack_start(self.play_button, 1,1,0)

        def on_select(list,index,column,event,self=self):
            self.selected_row = index
            self.cancel_button.show()
            self.play_button.show()
            self.vbox.pack_end(self.hbox, 0,0,0)
            self.hbox.show()
        self.list.connect("select-row",on_select)

        def on_unselect(list,index,column,event,self=self):
            self.vbox.remove(self.hbox)            
        self.list.connect("unselect-row",on_unselect)

        def on_cancel(button, self=self):
            downloader=self.file_server.downloaders[self.selected_row]
            downloader.cancel_download()
            downloader.stop()
            self.on_complete(self.selected_row)
        self.cancel_button.connect("clicked",on_cancel)

        def on_play(button, self=self):
            downloader=self.file_server.downloaders[self.selected_row]
            self.app.music_manager.append_song(downloader.data,1,downloader,None)
        self.play_button.connect("clicked",on_play)        


    #todo: keep displaying the line with 'done' and some stats
    def on_complete(self,row):
        self.list.remove(row)
        del self.file_server.downloaders[row]
        if not self.list:
            self.vbox.remove(self.hbox)

    
           

    def update(self):
        for i in range(len(self.file_server.downloaders)):
            downloader= self.file_server.downloaders[i]
            if self.list.rows <i+1:
                self.list.append([downloader.basename,''])
            
            if not downloader.running:
                for field in downloader.fields:
                    if downloader.success:
                        field.show(_('done.\n'),['grey'])
                    else:
                        field.show(_('canceled.\n'),['grey'])
                    field.close()
                self.on_complete(i)
                break
            else:
                old_stats =  self.list.get_text(i,1)
                new_stats = ((" %d%% " % ((downloader.get_bytes_downloaded()+1)*100
                                          / (downloader.get_bytes_total()+1)))
                             + 'of ' + utility.human_size(downloader.get_bytes_total())
                             + '  ' + utility.human_size(downloader.get_speed()) + '/s'
                             + ' '  + downloader.get_remaining_time()
                             + '  (' + downloader.get_sources()) +')'

                if new_stats != old_stats:
                    self.list.set_text(i,1,new_stats)

                str= ("%d%% " % ((downloader.get_bytes_downloaded()+1)
                                 *100/ (downloader.get_bytes_total()+1)))
                if not downloader.authorized_links:
                    str = str +' '+ downloader.get_sources()
                else:
                    str = str + ' ' + utility.human_size(downloader.get_speed()) + '/s'\
                          + '\t'  + downloader.get_remaining_time()
                str = str + '\n'
                for field in downloader.fields:
                    if field.text != str:
                        field.show(str,['grey'])

        return 1
        

