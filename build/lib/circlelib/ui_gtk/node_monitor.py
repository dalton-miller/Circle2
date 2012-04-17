#    The Circle - Decentralized resource discovery software
#    Copyright (C) 2001  Paul Francis Harrison
#    Copyright (C) 2002  Monash University
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

"""Monitor incoming network traffic graphically
"""

import gtk, time, math, os

# where is this defined??
PANGO_SCALE = 1024

from circlelib import error, utility, check

if hasattr(utility, '_'):
    from utility import _

decay_factor = 0.5

def advance(tuple):
    weight, then = tuple
    now = time.time()

    return (weight * math.pow(decay_factor,now-then)  ,now)


def monitor_node(node, file_server, app, vbox):
    """ Display a window for monitoring incoming network traffic 
    """

    stats = { } # (address, message) -> (weight, time)
    traffic_limit = [ 0.0 ]

    def monitor(is_outgoing, address, query, length,
                stats=stats, file_server=file_server):
        desc = query[0]

        if query[0] == 'download chunk':
            try:
                if (len(query) >= 2) and (check.is_name(query[1])):
                    desc = 'download ' + os.path.basename(file_server.paths[query[1]])
            except:
                pass
            
        key = (address, desc, is_outgoing)

        old = advance(stats.get(key,(0,0)))
        stats[key] = (old[0]+length*(1.0-decay_factor), old[1])


    usage_label = gtk.Label('')
    usage_label.set_alignment(0,1)
    vbox.pack_start(usage_label, gtk.FALSE,gtk.FALSE,0)

    padding_label = gtk.Label('')
    padding_label.set_alignment(0,0)
    vbox.pack_start(padding_label, gtk.FALSE,gtk.FALSE,0)

    drawing = gtk.DrawingArea()
    vbox.pack_start(drawing, gtk.TRUE,gtk.TRUE,0)

    hbox = gtk.HBox(gtk.FALSE,5)
    vbox.pack_start(hbox, gtk.FALSE,gtk.FALSE,0)

    hbox.pack_start(gtk.Label('Display traffic exceeding '), gtk.FALSE,gtk.FALSE,0)

    adjustment = gtk.Adjustment(0.1,0.0,99.9,0.1,1.0,1.0)
    spinner = gtk.SpinButton(adjustment, 0.1, 1)
    hbox.pack_start(spinner, gtk.FALSE,gtk.FALSE,0)

    def on_spinner(adjustment, traffic_limit=traffic_limit,spinner=spinner):
        traffic_limit[0] = spinner.get_value() * 1024.0
    adjustment.connect("value-changed",on_spinner)
    on_spinner(None)

    hbox.pack_start(gtk.Label('KB/s.'), gtk.FALSE,gtk.FALSE,0)

    def on_expose(drawing,event, stats=stats,traffic_limit=traffic_limit):
        style = drawing.get_style()
        width = drawing.get_allocation().width
        height = drawing.get_allocation().height

        list = [ ]
        for item in stats.items():
            value = advance(item[1])[0]
            if value < traffic_limit[0] or value < 1.0:
                try:
                    del stats[item[0]]
                except KeyError:
                    pass
            else:
                list.append((value,item[0]))
            
        gtk.gdk.Drawable.draw_rectangle(drawing.window,style.bg_gc[0],1,0,0,width,height)

        list.sort(lambda x,y: cmp(y,x))
        list = list[:10]

        sum = 0.0
        for item in list:
            sum = sum + item[0]

        if sum == 0.0:
            return

        sum_2 = 0.0
        heights = [ 0 ]
        for item in list:
            sum_2 = sum_2 + item[0]
            heights.append(int(sum_2/sum * height))

        pos = 0.0
        i = 0
        for i in range(len(list)):
            item = list[i]
            #if i % 2:
            if item[1][2]:
                gc = style.light_gc[0]
            else:
                gc = style.mid_gc[0]

            if heights[i] >= heights[i+1]-1:
                continue

            this_height = heights[i+1]-heights[i]-1
            if this_height < 1:
                break
                
            gtk.gdk.Drawable.draw_rectangle(drawing.window,gc,1, 0,heights[i],int(width/3),this_height)
            
            if item[1][2]:
                verb = 'To'
            else:
                verb = 'From'
            #drawing.draw_text(style.font,style.fg_gc[0],int(width/3)+10,style.font.ascent+heights[i],verb+' %s:%d '%item[1][0])
            #drawing.draw_text(style.font,style.fg_gc[0],int(width/3)+10,font_height+style.font.ascent+heights[i],item[1][1])
            # XXX: Should this be using utility.human_size ?
            #drawing.draw_text(style.font,style.fg_gc[0],10,style.font.ascent+heights[i],'%.1fkB/s'%(item[0]/1024.0))
            
            layout = drawing.create_pango_layout( verb+' %s:%d '%item[1][0]+'\n'+item[1][1] )
            if layout.get_size()[1]/PANGO_SCALE < heights[i+1]-heights[i]:
                gtk.gdk.Drawable.draw_layout(drawing.window, style.fg_gc[0],int(width/3)+10,heights[i],layout)
                layout = drawing.create_pango_layout('%.1fkB/s'% (item[0]/1024.0))
                gtk.gdk.Drawable.draw_layout(drawing.window, style.fg_gc[0],10,heights[i],layout)

    drawing.connect("expose_event",on_expose) 

    def update(drawing=drawing, usage_label=usage_label, node=node):

        usage_label.set_text(_('Network usage so far: ')
                             + utility.human_size(node.network_usage))
        
        if not drawing.flags() & gtk.VISIBLE:
            return 0

        drawing.queue_draw()
        return 1

    gtk.timeout_add(1000, update) # the fact that it is 1000 ms
                                  # is used in the computation of traffic
    
    return monitor


# vim: set expandtab :
