import os
import sys
import time

sys.path.insert(0,'.')
import circlelib

if 'release' in sys.argv:
  name = 'Circle-'+circlelib.__version__
else:
  name = 'Circle'

  for t in time.gmtime()[:3]:
    name += "-" + str(t)

path_installer = '..\\Installer\\'
path_circle = '.\\'

# Using cygwin zip
if os.path.isdir("c:\\cygwin\\bin"):
  unix_path = "c:\\cygwin\\bin\\"
else:
  unix_path = "g:\\unix\\bin"

if os.path.isdir('packaged'):
  path_dest = 'packaged'
else:
  path_dest = 'f:\\circle'

path_zip = unix_path
rm = unix_path + 'rm'

os.system("copy circle circle.py")
# This is F... Dangerous
os.system(rm + " -rf "+name)

os.system(rm + " -f *.pyc")
os.system(rm + " -f circlelib\*.pyc")
os.system(rm + " -f circlelib\crypto\*.pyc")
os.system(rm + " -f *.pyo")
os.system(rm + " -f circlelib\*.pyo")
os.system(rm + " -f circlelib\crypto\*.pyo")


extras = [ ]
for item in os.listdir('circlelib'):
    if item[-5:] == '.html' or item[-4:] == '.xpm' or item in ['magic.linux','magic.circle']:
        extras.append((item,'circlelib\\'+item,'BINARY'))

for item in os.listdir('.'):
    if item == 'putty.exe' or item == 'plink.exe' or item == 'COPYING':
        extras.append((item,item,'BINARY'))

extras.sort()

#a = Analysis([path_installer+'support\\useUnicode.py', path_circle+'circle.py'],
a = Analysis([path_installer+'support\\useUnicode.py', 
                   path_installer+'support\\_mountzlib.py', 
                   path_circle+'circle.py'],
             pathex=[],excludes=['Tkinter'])
pyz = PYZ(a.pure)

exe = EXE( pyz,
          a.scripts,
          #a.binaries,
          #extras,
          name='circle.exe',
	  icon='circlelib\neko.ico',
          debug=0,
          console=1,
          exclude_binaries=1)

dist = COLLECT(exe,a.binaries,extras,name=name)

os.system(path_zip+"zip -r "+name+".zip "+name)
os.system("copy "+name+".zip "+path_dest)
os.system(rm + " -f "+ name + ".zip")
#os.system(rm + " -rf "+ name)
os.system(rm + " -rf circle.exe")

os.system(rm + " -rf buildcircle.spec")
os.system(rm + " -rf buildcircle")
#os.system(rm + " -f warn*")
