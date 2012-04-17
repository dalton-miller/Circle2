#! /bin/sh
fifo=fifo
if [ -p "$fifo" ]; then
  :
else
  mkfifo "$fifo"
fi

# TODO: Use the cvs diff to recalculate line numbers instead.
while [ $# != 0 ]; do
  pyfile="$1"
  shift
  case "$pyfile" in
    *.py) ;;
    *) echo "Usage: $0 [python-files...]" >&2; exit 2 ;;
  esac
  b=`basename "$pyfile" .py`
  d=`dirname "$pyfile"`
  echo
  echo "$pyfile"
  if [ -e "$d"/pychk-"$b" ]; then
    pychecker "$pyfile" > "$d"/pychk-"$b"2
    echo "pychecker $pyfile returned $?"
    sed 's/:[0-9]\+/:#/g' < "$d"/pychk-"$b" > "$fifo" &
    sed 's/:[0-9]\+/:#/g' < "$d"/pychk-"$b"2 | diff -du "$fifo" - || [ $? = 1 ]
  else
    pychecker "$pyfile" > "$d"/pychk-"$b"
    echo "pychecker $pyfile returned $?"
    cat "$d"/pychk-"$b"
  fi
done

if [ x"$fifo" = xfifo ]; then
  rm "$fifo"
fi
