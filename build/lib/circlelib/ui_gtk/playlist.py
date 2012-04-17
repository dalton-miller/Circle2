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



import popen2, os, select, time, re, string
import gtk
from circlelib import settings, error, utility, check
import circle_gtk

#------------------------------  mp3_info

t_bitrate = [
  [
    [0,32,48,56,64,80,96,112,128,144,160,176,192,224,256],
    [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160],
    [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160]
    ],
  [
    [0,32,64,96,128,160,192,224,256,288,320,352,384,416,448],
    [0,32,48,56,64,80,96,112,128,160,192,224,256,320,384],
    [0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]
    ]
  ]
        
t_sampling_freq = [
  [22050, 24000, 16000],
  [44100, 48000, 32000]
  ]

frequency_tbl = {0:22050,1:24000,2:16000,3:44100,4:48000,5:32000,6:64000}

def getword(fp, off):
  fp.seek(off, 0)
  word = fp.read(4)
  return word

def get_l4 (s):
    return reduce (lambda a,b: ((a<<8) + b), map (long, map (ord, s)))

def get_xing_header (f):
    where = f.tell()
    try:
        f.seek(0)
        b = f.read(8192)
        i = string.find (b, 'Xing')
        if i > 0:
            # 32-bit fields; "Xing", flags, frames, bytes, 100 toc
            i = i + 4
            flags	= get_l4 (b[i:i+4]); i = i + 4
            frames	= get_l4 (b[i:i+4]); i = i + 4
            bytes	= get_l4 (b[i:i+4]); i = i + 4
            return flags, frames, bytes
        else:
            return None
    finally:
        f.seek (where)

MPG_MD_STEREO           = 0
MPG_MD_JOINT_STEREO     = 1
MPG_MD_DUAL_CHANNEL     = 2
MPG_MD_MONO             = 3

def get_newhead (word):
  word = get_l4 (word)
  if (word & (1<<20)):
    if (word & (1<<19)):
      lsf = 0
    else:
      lsf = 1
    mpeg25 = 0
  else:
    lsf = 1
    mpeg25 = 1
  lay = 4 - ((word>>17)&3)
  if mpeg25:
    sampling_frequency = 6 + ((word>>10) & 3)
  else:
    sampling_frequency = ((word>>10)&3) + (lsf * 3)
  error_protection 	= ((word>>16)&1) ^ 1
  bitrate_index 	= (word>>12) & 0xf
  padding 		= ((word >> 9) & 0x1)
  extension 		= ((word >> 8) & 0x1)
  mode	 		= ((word >> 6) & 0x3)
  mode_ext 		= ((word >> 4) & 0x3)
  copyright 		= ((word >> 3) & 0x1)
  original 		= ((word >> 2) & 0x1)
  emphasis 		= word & 0x3

  if mode == MPG_MD_MONO:
    stereo = 1
  else:
    stereo = 2

  return locals()
  import pprint
  pprint.pprint (locals())
  
def get_head(word):
  #if len(word) != 4:
  #  return {}
  #l = ord(word[0])<<24|ord(word[1])<<16|ord(word[2])<<8|ord(word[3])
  
  l = long(get_l4(word))

  id = (l>>19) & 1
  layer = (l>>17) & 3
  protection_bit = (l>>16) & 1
  bitrate_index = (l>>12) & 15
  sampling_freq = (l>>10) & 3
  padding_bit = (l>>9) & 1
  private_bit = (l>>8) & 1
  mode = (l>>6) & 3
  mode_extension = (l>>4) & 3
  copyright = (l>>3) & 1
  original = (l>>2) & 1
  emphasis = (l>>0) & 1
  version_index = (l>>19) & 3
  bytes = l

  try:
    bitrate = t_bitrate[id][3-layer][bitrate_index]
  except IndexError:
    bitrate = 0

  try:
    fs = t_sampling_freq[id][sampling_freq]
  except IndexError:
    fs = 0

  return vars()


def is_mp3(h):
  if not (h['bitrate_index'] == 0 or \
	  h['version_index'] == 1 or \
	  (( (h['bytes']>>16) & 0xFFE0) != 0xFFE0) or (not h['fs']) or (not h['bitrate'])):
    return 1
  return 0


def get_v2head(fp):
  fp.seek(0,0)
  word = fp.read(3)
  if word != "ID3": return 0

  bytes = fp.read(2)
  major_version = ord(bytes[0])
  minor_version = ord(bytes[1])

  version = "ID3v2.%d.%d" % (major_version, minor_version)
  bytes = fp.read(1)
  unsync = (ord(bytes)>>7) & 1
  ext_header = (ord(bytes)>>6) & 1
  experimental = (ord(bytes)>>5) & 1

  bytes = fp.read(4)
  tagsize = 0

  for i in range(4):
    tagsize = tagsize + ord(bytes[3-i])*128*i

  if ext_header:
    ext_header_size = ext_header_size + 10
    bytes = fp.read(4)

  return vars()


def mp3_info(path):

    info = {}
    if os.stat(path)[6] == 0:
        return {}

    f = open(path,'rb')
    f.seek(-128,2)
    id3block = f.read(128)
    f.close()

    if id3block[0:3] == 'TAG':
        def strip_zeros(str):
            index = string.find(str,'\000')
            if index == -1:
                return string.strip(str)
            return string.strip(str[0:index])
        info['music_title']  = utility.force_unicode(strip_zeros(id3block[3:33]))
        info['music_artist'] = utility.force_unicode(strip_zeros(id3block[33:63]))
        info['music_album']  = utility.force_unicode(strip_zeros(id3block[63:93]))

    off = 0
    eof = 0
    h = 0
    i = 0
    tot = 4096

    fp = open(path)
    word = getword(fp, off)

    if off==0:
        id3v2 = get_v2head(fp)
        if id3v2:
            off = off + id3v2['tagsize']
            tot = tot + off
            word = getword(fp, off)

    while 1:
        h = get_head(word)
        #h=get_newhead(word)
        if not h: break
        off=off+1
        word = getword(fp, off)
        if off>tot: 
            #print "BAD FILE", path, os.stat(path)[6]
            return info
        if is_mp3(h): break

    fp.seek(0, 2)
    eof = fp.tell()
    try:
        fp.seek(-128, 2)
    except IOError, reason:
        return info
    fp.close()
  
    if h['id']:
        h['mean_frame_size'] = (144000. * h['bitrate']) / h['fs']
    else:
        h['mean_frame_size'] = (72000. * h['bitrate']) / h['fs']

    #h['layer'] = h['mode']
    h['freq_idx'] = 3*h['id'] + h['sampling_freq']

    h['length'] = ((1.0*eof-off) / h['mean_frame_size']) * ((115200./2)*(1.+h['id']))/(1.0*h['fs'])

    #time is in secs/100
    info['time'] = int(h['length']);
    
    #info['version'] = h['id']
    #info['STEREO'] = not(h['mode'] == 3)
    #if h['layer'] >= 0:
    #    if h['layer'] == 3:
    #        info['layer'] = 2
    #    else:
    #        info['layer'] = 3
    #else:
    #    info['layer'] = ''
    #info['MODE'] = h['mode']
    #info['COPYRIGHT'] = h['copyright']
    if h['bitrate'] >=0:
        info['bitrate'] = h['bitrate']

    if h['freq_idx'] >= 0:
        info['frequency'] = frequency_tbl[h['freq_idx']]

    return info


#------------------------ ogg_info

def ogg_info(path):
    info = {}
    try:
        import ogg.vorbis
        vf = ogg.vorbis.VorbisFile(path)
        info['time'] = int( vf.time_total(0)*100)
        vc = vf.comment()
        vi = vf.info()
        info['frequency'] = vi.rate
        info['bitrate'] = vf.bitrate(0)/1024

        for key, val in vc.items():
            if key == 'TITLE':
                info['music_title']  = utility.force_unicode(val)
            elif key == 'ARTIST':
                info['music_artist'] = utility.force_unicode(val)
            elif key == 'ALBUM':
                info['music_album']  = utility.force_unicode(val)
    finally:
        return info


class Player(utility.Task_manager):
    """Abstract player class"""
    def __init__(self,filename,downloader,size,field):

        utility.Task_manager.__init__(self)
        self.filename=filename
        self.downloader=downloader
        self.fraction=0
        self.size=size
        self.playing=0
        self.paused=0
        self.finished=0
        self.time_elapsed = 0
        self.time_remaining = 0
        self.stalled = 0
        self.field = field

    def start_playing(self):
        if self.field:
            gtk.timeout_add(0,self.field.remove_tags,['files'])
            gtk.timeout_add(0,self.field.apply_tags,['active'])

    def stop_playing(self):
        if self.field:
            gtk.timeout_add(0,self.field.remove_tags,['active'])
            gtk.timeout_add(0,self.field.apply_tags,['files'])

    def fast_fwd(self):
        pass

    def back(self):
        pass

    def seek(self,fraction):
        pass



class OggPlayer(Player):
    
    def __init__(self, filename,downloader,size,field):
        """Play the given file on the current device."""
        Player.__init__(self,filename,downloader,size,field)
        import ogg.vorbis
        
        if not os.path.isfile(self.filename):
            raise error.Error, "Incorrect filename."

        if os.path.getsize(self.filename)<8192:
            self.vf = None
            self.vi = None
            self.vc = None
        else:
            import ogg.vorbis
            self.vf = ogg.vorbis.VorbisFile(self.filename)
            self.vc = self.vf.comment()
            self.vi = self.vf.info()
        
        
    def start_playing(self):
        """Start playing."""
        Player.start_playing(self)

        if not os.path.isfile(self.filename):
            return

        self.lock.acquire()
        self.paused=0
        self.open_audio()
        self.lock.release()
              
        if os.path.getsize(self.filename)>=8192:
            import ogg.vorbis
            self.vf = ogg.vorbis.VorbisFile(self.filename)        
            self.vc = self.vf.comment()
            self.vi = self.vf.info()
       
        def play_task(self=self):
            """pause if there is not enough data"""
            import ogg.vorbis
            pause_time=3
            while self.playing:
                if not os.path.isfile(self.filename):
                    break
                
                if self.vf:
                    if not self.paused:
                        try:
                            (buff, bytes, bit) = self.vf.read(4096)
                            if bytes:
                                self.write(buff, bytes)                                
                            else:
                                if not self.downloader:
                                    self.finished=1
                                    break
                                if not self.downloader.running:
                                    self.finished=1
                                    break
                                self.stalled = 1
                                time.sleep(pause_time)
                                self.stalled = 0
                                pause_time = pause_time*1.5                           
                        except:
                            break
                    else:
                        time.sleep(0.2)
                else:
                    if os.path.getsize(self.filename)<80000 and os.path.getsize(self.filename)<self.size:                        
                        time.sleep(0.5)
                    else:
                        self.vf = ogg.vorbis.VorbisFile(self.filename)
                        self.vc = self.vf.comment()
                        self.vi = self.vf.info()
                        
            self.stop_playing()

        if not self.playing:
            self.playing = 1
            utility.Task(play_task,self).start()

    def stop_playing(self):
        Player.stop_playing(self)
        self.lock.acquire()
        self.playing = 0
        self.fraction= 0
        self.close_audio()
        self.lock.release()
        if self.vf:
            self.vf.time_seek(0)

    def pause(self):
        self.lock.acquire()
        self.paused = not self.paused
        self.lock.release()

    def fast_fwd(self):
        t=self.vf.time_tell()
        self.vf.time_seek(t+10.0)

    def back(self):
        t=self.vf.time_tell()
        self.vf.time_seek(t-10.0)

    def seek(self,fraction):
        import ogg.vorbis
        self.vf = ogg.vorbis.VorbisFile(self.filename)
        try:
            if self.time:            
                self.vf.time_seek(int(fraction*float(self.time)))
            else:
                self.vf.raw_seek(int(fraction*float(self.size)))
        except:
            self.vf.time_seek(int(self.vf.time_total(0)))


    def update(self):
        if self.vf:
            self.time_elapsed =  self.vf.time_tell()
            if self.time:
                self.time_remaining = self.time - self.time_elapsed
        if self.vf and self.vf.time_total(0)>0:
            self.fraction= float(self.vf.raw_tell())/float(self.size)
        if self.fraction>1.0:
            self.fraction = 1.0
        if self.fraction<0.0:
            self.fraction = 0.0



class LADPlayer(OggPlayer):
    """Ogg player that uses the linuxaudiodev module. """

    def __init__(self,f,downloader,size,field):
        OggPlayer.__init__(self,f,downloader,size,field)

    def open_audio(self):
        import linuxaudiodev
        self.dev = linuxaudiodev.open('w')
        self.dev.setparameters(44100, 16, 2, linuxaudiodev.AFMT_S16_NE)
        
    def close_audio(self):
        if self.vf:
            self.dev.close()
    
    def write(self, buff, bytes):

        try:
            while self.dev.obuffree() < bytes:
                time.sleep(0.2)
            if self.playing:
                self.dev.write(buff[:bytes])

        except:
            pass
            


class Mp3Player(Player):
    """Uses mpg321 in the Remote control mode"""

    def __init__(self,f,downloader,size,field):
        Player.__init__(self,f,downloader,size,field)

        mp3_player = utility.popen("which mpg321").readline()
        if not mp3_player:
            mp3_player = utility.popen("which mpg123").readline()            
        if mp3_player:
            self.cmdline = "%s -R dummy" % string.strip(mp3_player)
        else:
            raise error.Error("No mp3 player found. Please install mpg123 or mpg321.")
            
        self.stop_request = 0


    def fast_fwd(self):
        if self.playing:
            self.w.write('J +150\n')
            self.w.flush()

            
    def back(self):
        if self.playing:
            self.w.write('J -150\n')
            self.w.flush()
            

    def seek(self,fraction):
        if self.playing:
            i = int(fraction*float(self.frames_elapsed+self.frames_remaining)
                    * float(self.size)/float(self.current_size))
            if i < self.frames_elapsed+self.frames_remaining:
                try:
                    self.w.write('J %d\n'%i)
                    self.w.flush()
                except:
                    print "cannot seek"
                    

    def start_playing(self):
        Player.start_playing(self)

        def play_task(self):
            pause_time = 0.1            
            self.control = popen2.Popen3(self.cmdline,1)
            self.r, self.w, self.e = self.control.fromchild, self.control.tochild, self.control.childerr
            self.paused = 0
            self.stalled = 0
            
            while not self.stop_request and self.playing:
                
                if not os.path.isfile(self.filename):
                    break
                if os.path.getsize(self.filename)<80000:
                    time.sleep(0.2)
                    continue
                if select.select([self.e],[],[],0)[0]:
                    error_msg=self.e.readline()
                    #if error_msg:
                    #    print "err:",error_msg
                fn = ''
                try:
                    if select.select([self.r],[],[],1)[0]:
                        fn=self.r.readline()
                except:
                    print "error during readline, breaking"
                    break
                
                if fn:                    
                    fn=fn.split()
                    if fn:
                        if fn[0]=='@R':
                            self.w.write('L %s\n'% self.filename)
                            try:
                                self.current_size = os.path.getsize(self.filename)
                                self.w.flush()
                            except:
                                self.stop_request=1
                                break
                            
                        elif fn[0]=='@F':
                            try:
                                self.frames_elapsed   = int(fn[1])
                                self.frames_remaining = int(fn[2])
                                self.time_elapsed    = float(fn[3])
                                self.time_remaining  = float(fn[4])
                            except:
                                pass
                            
                        elif fn[0]=='@P':
                            if fn[1]=='0':
                                if self.current_size == self.size:
                                    self.finished = 1
                                    self.stop_request = 1
                                    break
                                self.stalled = 1
                                try:
                                    time.sleep(pause_time)
                                    pause_time = pause_time * 1.5
                                    self.current_size = os.path.getsize(self.filename)
                                    self.w.write('L %s\n'% self.filename)
                                    self.w.flush()
                                    self.w.write('J %d\n'% (self.frames_elapsed))
                                    self.w.flush()
                                    self.stalled=0
                                except:
                                    self.stop_request = 1
                                        
            self.stop_request=0
            self.stop_playing()

        if not self.playing:
            self.playing = 1
            utility.Task(play_task,self).start()

    def pause(self):
        if self.playing:
            self.w.write('P\n')
            self.w.flush()
            self.paused = not self.paused

    def stop_playing(self):
        Player.stop_playing(self)
        if self.playing:
            self.playing = 0
            self.fraction = 0
            self.paused = 0
            try:
                self.w.write('Q\n')
                self.w.flush()
            except:
                pass
            try:
                os.kill(self.control.pid, 2)
                pid, r = os.waitpid(self.control.pid, 0)
                #print "killed child. returned",r
            except:
                try:
                    os.kill(self.control.pid, 9)
                    pid, r = os.waitpid(self.control.pid, 0)
                    #print "killed child. returned",r
                except:
                    print "problem"




    def update(self):
        if self.time_elapsed+self.time_remaining != 0.0:
            self.fraction=self.time_elapsed / (self.time_elapsed+self.time_remaining)\
                           * float(self.current_size)/float(self.size)
        if self.fraction>1.0:
            self.fraction = 1.0
        if self.fraction<0.0:
            self.fraction = 0.0
        return 0



class Music_manager:

    def __init__(self,app,main_vbox):

        self.app=app
        self.playlist=[]
        self.selected_row = -1
        self.playing_row = -1
        self.player = None

        #self.keep_downloading_button = gtk.CheckButton("Keep downloading file")
        #vbox.pack_start(self.keep_downloading_button)
        #self.keep_downloading_button.set_active(1)

        #left_vbox = gtk.VBox(gtk.FALSE, 5)
        #main_hbox.pack_start(left_vbox,gtk.FALSE,gtk.TRUE)
        #left_vbox.show()

        #vbox2 = gtk.VBox(gtk.FALSE, 5)
        #hbox2.pack_start(vbox2,gtk.FALSE)
        #vbox2.show()
       
        #self.name_label = gtk.Label("")
        #self.name_label.set_alignment(0,0.5)
        #main_vbox.pack_start(self.name_label,gtk.FALSE)
        #self.name_label.show()

        # hbox for bar and controls
        dd_hbox = gtk.HBox(gtk.FALSE, 5)
        main_vbox.pack_start(dd_hbox,gtk.FALSE)
        dd_hbox.show()

        # vbox for bar and controls
        dd_vbox = gtk.VBox(gtk.FALSE, 5)
        dd_hbox.pack_start(dd_vbox,gtk.TRUE, gtk.FALSE)
        dd_vbox.show()

        self.title_label = gtk.Label("")
        #self.title_label.set_alignment(0.2,0.5)
        dd_vbox.pack_start(self.title_label,gtk.FALSE)
        self.title_label.show()

        #self.artist_label = gtk.Label("")
        #self.artist_label.set_alignment(0,0.5)
        #main_vbox.pack_start(self.artist_label,gtk.FALSE)
        #self.artist_label.show()

        #self.album_label = gtk.Label("")
        #self.album_label.set_alignment(0,0.5)
        #main_vbox.pack_start(self.album_label,gtk.FALSE)
        #self.album_label.show()

        self.bitstream_label = gtk.Label("")
        #self.bitstream_label.set_alignment(0.8,0.5)
        dd_vbox.pack_start(self.bitstream_label,gtk.FALSE)
        self.bitstream_label.show()

        # hbox for bar
        bar_hbox = gtk.HBox(gtk.FALSE, 5)
        dd_vbox.pack_start(bar_hbox,gtk.TRUE)
        bar_hbox.show()

        self.progress = gtk.ProgressBar()
        bar_hbox.pack_start(self.progress,gtk.TRUE,gtk.FALSE)
        self.progress.set_size_request(368,20)
        def on_press(w,e,self=self):
            fraction = float(e.x)/float(w.get_allocation().width)
            if self.player:
                self.player.seek(fraction)
                
        self.progress.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK)
        self.progress.connect("button_press_event", on_press)

        # hbox for controls        
        ctrl_hbox = gtk.HBox(gtk.FALSE, 3)
        dd_vbox.pack_start(ctrl_hbox,gtk.TRUE,gtk.FALSE)
        ctrl_hbox.show()

        prev_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-prev.png"))
        prev_button.add(image)
        prev_button.set_size_request(50,25)
        ctrl_hbox.pack_start(prev_button,gtk.FALSE)
        prev_button.connect("clicked", self.prev_music)
        prev_button.show()

        rewind_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-rewind.png"))
        rewind_button.add(image)
        rewind_button.set_size_request(50,25)
        ctrl_hbox.pack_start(rewind_button,gtk.FALSE)
        rewind_button.connect("clicked", self.back_music)
        rewind_button.show()
                
        play_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-play.png"))
        play_button.add(image)
        play_button.set_size_request(50,25)
        ctrl_hbox.pack_start(play_button,gtk.FALSE)
        play_button.connect("clicked", self.play_music)
        play_button.show()

        pause_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-pause.png"))
        pause_button.add(image)
        pause_button.set_size_request(50,25)
        ctrl_hbox.pack_start(pause_button,gtk.FALSE)
        pause_button.connect("clicked", self.pause_music)
        pause_button.show()

        ffwd_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-ffwd.png"))
        ffwd_button.add(image)
        ffwd_button.set_size_request(50,25)
        ctrl_hbox.pack_start(ffwd_button,gtk.FALSE)
        ffwd_button.connect("clicked", self.ffwd_music)
        ffwd_button.show()
                
        next_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-next.png"))
        next_button.add(image)
        next_button.set_size_request(50,25)
        ctrl_hbox.pack_start(next_button,gtk.FALSE)
        next_button.connect("clicked", self.next_music)
        next_button.show()

        stop_button = gtk.Button()
        image = gtk.Image()
        image.set_from_file(utility.find_file("pixmaps/media-stop.png"))
        stop_button.add(image)
        stop_button.set_size_request(50,25)
        ctrl_hbox.pack_start(stop_button,gtk.FALSE)
        stop_button.connect("clicked", self.stop_music)
        stop_button.show()
                                
        playlist_label = gtk.Label(" ")
        playlist_label.set_alignment(0.1,0)
        main_vbox.pack_start(playlist_label,gtk.FALSE)
        playlist_label.show()

        self.scrolly = gtk.ScrolledWindow()
        self.scrolly.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
        main_vbox.pack_start(self.scrolly, gtk.TRUE,gtk.TRUE,0)
        self.scrolly.show()
        #self.scrolly.set_size_request(350,70)

        self.list = gtk.CList(3)
        self.list.set_column_min_width(0,350)
        self.list.set_column_width(1,20)
        self.list.set_column_width(2,40)
        self.list.set_selection_mode(gtk.SELECTION_SINGLE)
        self.scrolly.add(self.list)
        self.list.show()

        # hbox for buttons
        self.bottom_hbox = gtk.HBox(gtk.FALSE, 5)
        
        play_button = gtk.Button("Play")
        self.bottom_hbox.pack_start(play_button,gtk.TRUE)
        play_button.connect("clicked", self.play_row)
        play_button.show()

        close_button = gtk.Button("Discard")
        self.bottom_hbox.pack_start(close_button,gtk.TRUE)
        close_button.connect("clicked", self.on_delete)
        close_button.show()

        clear_button = gtk.Button("Clear")
        self.bottom_hbox.pack_start(clear_button,gtk.TRUE)
        clear_button.connect("clicked", self.clear)
        clear_button.show()

        def on_unselect(list,index,column,event,self=self):
            main_vbox.remove(self.bottom_hbox)            
        self.list.connect("unselect-row",on_unselect)

        def on_select(list,index,column,event,self=self):
            self.selected_row = index
            #self.update_info()
            main_vbox.pack_end(self.bottom_hbox, 0,0,0)
            self.bottom_hbox.show()            
        self.list.connect("select-row",on_select)

        


    def update(self):
        """called from the main update function"""

        circle_gtk.check_is_gtkthread()

        for i in range(len(self.playlist)):
            player = self.playlist[i]
            downloader = player.downloader
            if downloader!=None:
                if not downloader.success:
                    filename=player.filename
                    if os.path.exists(filename):
                        str = " %d%%" % (float(100*os.path.getsize(filename)) / self.playlist[i].size)
                        self.list.set_text(i,2,str)
                else:
                    self.list.set_text(i,2,'100%')
                    player.downloader=None

        if self.player:
            if self.player.finished:
                i = self.playlist.index(player)
                self.list.set_text(i,1,' ')
                
                for player in self.playlist:
                    if not player.finished:
                        self.player = player
                        self.playing_row = self.playlist.index(player)                        
                        self.start_music()
                        break
                else:
                    self.player= None
                    self.playing_row = -1
                    
        if self.player and self.app.running:
            self.player.update()
            self.progress.set_fraction(self.player.fraction)
            if self.player.time:
                str = "%d:%02d   /   %d:%02d "\
                      % (int(self.player.time_elapsed/60),
                         int(self.player.time_elapsed%60),\
                         int((self.player.time + 0.5 - self.player.time_elapsed)/60),\
                         int((self.player.time + 0.5 - self.player.time_elapsed)%60) )
            else:
                str = "%d:%02d   /   ?? "% (int(self.player.time_elapsed/60),
                                            int(self.player.time_elapsed%60))
            if self.player.stalled :
                str = str + "   (stalled...)"
            self.progress.set_text(str)
        else:
            self.progress.set_fraction(0) 
            self.progress.set_text("")
            self.update_info()




    def clear(self,e=None):
        self.stop_music()
        for i in range(len(self.playlist)):
            self.list.remove(0)
        self.playlist = []
        self.player = None
        self.selected_row = -1
        self.playing_row = -1


    def update_info(self):
        circle_gtk.check_is_gtkthread()
        
        if self.playing_row!=-1 and self.playlist:
            player = self.playlist[self.playing_row]
        else:
            player= self.player
            
        if player:
            filename=os.path.basename(player.filename)
            title = player.info.get('music_title')
            artist = player.info.get('music_artist')
            album =  player.info.get('music_album')
            frequency = player.info.get('frequency')
            bitrate = player.info.get('bitrate')
            time = player.info.get('time')
        else:
            filename=''
            title=''
            artist=''
            album=''
            frequency=''
            bitrate=''
            time=''

        if title:
            str = title+' by '+artist
        else:
            str = filename
            
        self.title_label.set_text(utility.force_unicode(str))
        self.title_label.show()

        str=""
        if frequency:
            str= str + "%dHz "%frequency
        if bitrate:
            str = str + "    %dkb/s"%bitrate
        if time:
            str = str + "    %dmin%02ds "% ((time/100/60),((time/100)%60))
        
        self.bitstream_label.set_text(str)
        self.bitstream_label.show()
        

    def start_music(self):
        """
        start a new song.
        playing_row must be set and valid
        """
        circle_gtk.check_is_gtkthread()
        
        if self.player:
            if self.player.playing:
                self.player.stop_playing()

        if self.playing_row != -1:
            self.progress.set_fraction(0)
            self.player = self.playlist[self.playing_row]
            self.player.finished = 0 
            self.list.set_text(self.playing_row,1,'*')
            self.player.start_playing()
            self.update_info()



            

    # the following methods are for the buttons of the bar
    # and for the menus in chat window
    # player must be set
    
    def stop_music(self, e=None):
        circle_gtk.check_is_gtkthread()
        if self.player:
            self.player.stop_playing()
            self.player.finished = 1
            self.progress.set_fraction(0) 
            
    def play_music(self, e=None):
        """plays the selected song"""
        if self.player:
            if self.player.playing:
                return        
        self.play_row()

    def play_row(self, e=None):
        """plays the selected row of the list"""
        if not self.playlist:
            return
        if self.selected_row == -1:
            return
        self.playing_row = self.selected_row
        self.stop_music()
        self.start_music()
 
    def pause_music(self,e=None):
        if self.player:
            self.player.pause()

    def ffwd_music(self,e=None):
        if self.player:
            self.player.fast_fwd()
    
    def back_music(self,e=None):
        if self.player:
            self.player.back()

    def prev_music(self,e=None):
        self.stop_music()
        self.playing_row -=1
        if self.playing_row < 0:
            self.playing_row = 0
        self.start_music()
    
    def next_music(self,e=None):
        self.stop_music()
        self.playing_row +=1
        if self.playing_row>len(self.playlist)-1:
            self.playing_row=len(self.playlist)-1
        self.start_music()

        
    
    def append_song(self, info, play_now, downloader=None, field=None):
        """
        appends song.
        if play_now, stops current player and starts this one.
        method called by other classes
        """
        circle_gtk.check_is_gtkthread()

        if info.get('local_path'):
            f = info['local_path']
        else:
            f = downloader.filename

        size = info.get('length')
        # first check if already in playlist
        for i in range(len(self.playlist)):
            if self.playlist[i].filename == f:
                self.selected_row=i
                self.playing_row=i
                self.playlist[i].field=field
                if play_now:
                    if self.player != self.playlist[i]:
                        self.stop_music()
                        self.player = self.playlist[i]
                        self.play_row()
                    else:
                        if not self.player.playing:
                            self.play_row()
                return
            
        if play_now:
            self.stop_music()
            self.player=None

        mime=info.get('mime')        
        extension = string.split(f, ".")[-1]
        lext = string.lower(extension)

        if mime=='audio/x-mp3' or lext == 'mp3':
            player=Mp3Player(f,downloader,size,field)
        elif mime=='audio/x-ogg' or lext == 'ogg':
            try:
                import ogg.vorbis
                import linuxaudiodev
            except:
                raise error.Error('I do not know how to play ogg files.\n'+
                            'Please install the python libraries for Ogg Vorbis:\n'+
                            'http://www.andrewchatham.com/pyogg/')
            try:
                player=LADPlayer(f,downloader,size,field)
            except:
                raise error.Error('Cannot play %s: file not found'%f)

        else:
            raise error.Error('Cannot play : unrecognized file format')
        
        player.info = info
        if info.get('time'):
            player.time = float(info['time'])/100
        else:
            player.time = None            

        if play_now:
            self.playlist.insert(0,player)
            self.list.insert(0,[utility.force_unicode(os.path.basename(f)),'*',''])
            self.list.set_text(0,1,'0')
            self.selected_row=0
            self.playing_row=0
            self.play_row()
        else:
            self.playlist.append(player)
            self.list.append([utility.force_unicode(os.path.basename(f)),'-',''])
            

    

    def on_delete(self,event):
        if self.selected_row != -1:
            #downloader=self.playlist[self.selected_row].downloader
            #if downloader != None:
            #    if downloader.running:
            #        downloader.stop()
                    
            if self.player == self.playlist[self.selected_row]:                
                self.stop_music()
                self.player = None

            self.playlist.remove(self.playlist[self.selected_row])
            self.list.remove(self.selected_row)
            self.selected_row = -1


        
# vim: set expandtab :
