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
from circlelib import settings, error, utility, check


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


        
# vim: set expandtab :
