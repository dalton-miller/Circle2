#!/usr/bin/python

import zipfile, py_compile, StringIO, base64, sys, os

file = StringIO.StringIO()
zip = zipfile.PyZipFile(file, "w", zipfile.ZIP_DEFLATED)

zip.write("circle", "circle")
zip.write("plink.exe", "plink.exe")

for name in os.listdir("circlelib"):
    if name[-3:] == '.py' or \
       name[-5:] == '.html' or \
       name in ['magic.circle', 'magic.linux']:
        full_name = os.path.join('circlelib', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/crypto"):
    if name[-3:] == '.py':
        full_name = os.path.join('circlelib/crypto', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/ui_gtk"):
    if name[-3:] == '.py':
        full_name = os.path.join('circlelib/ui_gtk', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/ui_http"):
    if name[-3:] == '.py' or name[-5:] =='.html':
        full_name = os.path.join('circlelib/ui_http', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/ui_text"):
    if name[-3:] == '.py':
        full_name = os.path.join('circlelib/ui_text', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/pixmaps"):
    if name[-4:] in ['.xpm','.png']: 
        full_name = os.path.join('circlelib/pixmaps', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/html"):
    if name[-5:] in ['.html']: 
        full_name = os.path.join('circlelib/html', name)
        zip.write(full_name, full_name)

for name in os.listdir("circlelib/ixml"):
    if name[-4:] in ['.xml']: 
        full_name = os.path.join('circlelib/ixml', name)
        zip.write(full_name, full_name)
zip.close()

zip_str = base64.encodestring(file.getvalue())
file.close()

file = open("circle-dist.pyw","wb")

file.write("""#!/usr/bin/python

import base64, StringIO, zipfile, tempfile, sys, os, string

str = \"\"\"
"""+zip_str+"""\"\"\"

file = StringIO.StringIO(base64.decodestring(str))
del str

zip = zipfile.ZipFile(file,"r")
                                                                                
tempdir = tempfile.mktemp()
os.makedirs(tempdir,0700)
                                                                                
filenames = [ item.filename for item in zip.infolist() ]
                                                                                
for filename in filenames:
    full_name = os.path.join(tempdir,filename)
    path = os.path.split(full_name)[0]
    if not os.path.exists(path):
        os.makedirs(os.path.split(full_name)[0])
    file = open(full_name,"wb")
    file.write(zip.read(filename))
    file.close()
                                                                                
zip.close()
file.close()

del zip
del file

os.chdir(tempdir)
os.spawnv(os.P_WAIT, sys.executable, [sys.executable, 'circle'] + sys.argv[1:] + ['no-fork'])
os.chdir("..")

def remove_all(filename):
    if os.path.isdir(filename):
        for item in os.listdir(filename):
            remove_all(os.path.join(filename,item))
        os.rmdir(filename)
    else:
        os.remove(filename)
                                                                                
remove_all(tempdir)
""")

file.close()



