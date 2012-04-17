#! /bin/sh
# Regression checking for pychecker warnings.

#    Copyright (C) 2002  Monash University
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of version 2 of the GNU General Public License
#    as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# allcheck.py puts its output to allpychk2, and does a fuzzy diff
# against allpychk.  It doesn't try to write over allpychk, but once
# you are happy with the allcheck.sh output (i.e. 

if [ $# != 0 ]; then
  echo "Usage: $0" >&2
  exit 2
fi

mydir=`dirname "$0"`
cd "$mydir"
my_cwd=`/bin/pwd`

fifo=fifo
if [ -p "$fifo" ]; then
  :
else
  mkfifo "$fifo"
fi

files=$(for d in circlelib circlelib/crypto; do cut -d/ -f2,3 "$d"/CVS/Entries | grep -v /- | grep '\.py/' | sed "s|/.*||;s|^|$my_cwd/$d/|";done)
files_sed=$(echo "$files" | sed 's,\(.*/\)\(.*\),s%^\2:%\1\2:%,')
# TODO: Use the cvs diff to recalculate line numbers instead.
if [ -e allpychk ]; then
  pychecker $files | sed "s%^$my_cwd/%%" | sed "$files_sed" | tr %\\0 \\0%|sed 's/^$/%/'|tr '%\n' '\n%'|sort|tr -d \\n | tr '%\0' '\n%' > allpychk2
  sed 's%\([:(]\)[0-9]\+\([:)]\)%\1#\2%g' < allpychk > "$fifo" &
  sed 's%\([:(]\)[0-9]\+\([:)]\)%\1#\2%g' < allpychk2 | diff -du "$fifo" - || [ $? = 1 ]
else
  pychecker $files |sed "s%^$my_cwd/%%" > allpychk
  cat allpychk
fi

if [ x"$fifo" = xfifo ]; then
  rm -f "$fifo"
fi
