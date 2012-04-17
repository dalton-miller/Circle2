#! /usr/bin/env python

import string,sys,os

if sys.version_info < (2,2):
    print "Circle requires Python version 2.2 or higher.\n"
    print "See the README for details."
    sys.exit(1)

if sys.platform == 'win32':
    print "This install script is for linux"
    print "See the README for details"
    sys.exit(1)

try:
    from distutils.core import setup, Extension
    from distutils.command.install_data import install_data
except:
    print "\nCould not load the distutils modules. Have you installed them?\n"
    print "(on Debian systems you need to install the python2.X-dev package)\n"
    sys.exit(1)

import circlelib

class modified_install_data(install_data):
    def finalize_options(self):
        self.set_undefined_options('install',('install_lib','install_dir'))
        install_data.finalize_options(self)

xmlfiles = []
list = os.listdir('circlelib/ixml')
for i in list:
    if i[-3:]== 'xml':
        xmlfiles.append('circlelib/ixml/'+i)

setup(name = 'Circle',
      version = circlelib.__version__,
      description = 'Decentralized P2P application',
      author = 'Paul Harrison, Nathan Hurst, Peter Moulder, Jiri Baum and others',
      author_email = 'thomasV1@gmx.de',
      url = 'http://thecircle.org.au/',
      license = 'GPL',
      long_description =
"""
An application for instant messaging, sharing files, and exchanging news,
based around the idea of a decentralized hash.""",
      platforms = ['Linux'],

      cmdclass = { 'install_data': modified_install_data },

      packages = ['circlelib','circlelib.crypto','circlelib.ui_gtk',\
                  'circlelib.ui_http','circlelib.ui_text'],
      scripts = ['circle'],

      data_files = [
        ('circlelib',
         ['circlelib/magic.circle',
          'circlelib/magic.linux']),
        ('circlelib/html',
         ['circlelib/html/about.html',
          'circlelib/html/chat_commands.html',
          'circlelib/html/daemon_howto.html',
          'circlelib/html/technical_faq.html',
          'circlelib/html/getting_started.html']),
        ('circlelib/pixmaps',
         ['circlelib/pixmaps/diagram-bg.xpm',
          'circlelib/pixmaps/diagram-bg-red.xpm',
          'circlelib/pixmaps/media-play.png',
          'circlelib/pixmaps/media-pause.png',
          'circlelib/pixmaps/media-stop.png',
          'circlelib/pixmaps/media-prev.png',
          'circlelib/pixmaps/media-next.png',
          'circlelib/pixmaps/media-ffwd.png',
          'circlelib/pixmaps/media-rewind.png']),
        ('circlelib/ixml',xmlfiles),
        ('/usr/share/pixmaps',['circle-icon.png']),
	('/usr/share/applications',['circle.desktop'])
      ]
)

