G:
cd \progra*
cd python
C:
cd \cvs\installer

rem only need to be run once
g:python Configure.py

rem this spec is missing the magic files
rem g:python makespec.py --onefile --noconsole --debug ..\circle\circle.py

cd \cvs\circle
g:python ..\installer\build.py circle.spec

cd \
g:
cd \
