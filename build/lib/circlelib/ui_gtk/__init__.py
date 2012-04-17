"""
   Circle GTK user interface

   The GUI runs in its own thread.
   All GTK actions must be called from this thread.
   This may be checked by calling: check_is_gtkthread()

   When the GUI is started, it instanciates name_server and chat.
   However, those objects belong to the 'core' and they run in
   the main thread.

   When 'core' threads need to do GUI actions,
   they must call the timeout_add method of the GUI:

   timeout_add(timeout,function,params)

"""
