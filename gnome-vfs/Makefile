CFLAGS=`pkg-config --cflags glib-2.0 gnome-vfs-module-2.0` 
LIBS=`pkg-config --libs glib-2.0 gnome-vfs-module-2.0`
VIEW_CFLAGS=`pkg-config --cflags gtk+-2.0 gnome-vfs-2.0`
VIEW_LIBS=`pkg-config --libs gtk+-2.0 gnome-vfs-2.0`

PREFIX=`pkg-config --variable=prefix gnome-vfs-module-2.0`

BINDIR=$(PREFIX)/bin
CONFDIR=/etc/gnome-vfs-2.0/modules
MODDIR=$(PREFIX)/lib/gnome-vfs-2.0/modules
APPDIR=$(PREFIX)/share/application-registry

CC=gcc

all:
	@echo "type make install"

circle-vfs.so: circle-vfs.c
	$(CC) -g $(CFLAGS) -fPIC -Wall -c circle-vfs.c
	$(CC) -g $(LIBS) -shared -Wl,-soname,circle-vfs.so -o circle-vfs.so circle-vfs.o

clean:
	rm -f *.so *.o

install-common:
	install -d $(CONFDIR)
	install -d $(MODDIR)
	install circle-method.conf $(CONFDIR)

install: circle-vfs.so install-common
	install circle-vfs.so $(MODDIR)/libcircle-method.so

uninstall:
	rm -f $(CONFDIR)/circle-method.conf
	rm -f $(MODDIR)/libcircle-method.so

