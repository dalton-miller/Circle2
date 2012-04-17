"""Modules of The Circle

     The Circle is a decentralized file sharing / chat / news application.

     These modules are used by the scripts circle and circled.

     Coding style:

         - variable_names_like_this
         - Class_names_like_this
         - four spaces for each indent
         - KISS
	 - `!=', not `<>' (*see (python2)Operators, in the Texinfo documentation).
     
     Threading idiom:
         
	 See utility module documentation.

     Notes on writing plug-ins:

         circle loads all plug-ins located in the .circle/plug-ins directory
         on startup. Plug-ins are just python files (ending in .py).

         - two special variables are defined before each plug-in is loaded:
                 app is the application object
                 node is the network node object

         - on startup the start() function will be called, if it is defined

         - on shutdown the stop() function will be called, if it is defined

	 - use app.chat.register to register commands

	 - use app.add_menu_item to register menu items
     
     Notes on using the Circle hashtable in separate applications:
        
         # Also see 
	 #  - documentation of node.py
	 #  - circleget program

         # Create a node
         import circlelib.node
         node = circlelib.node.Node()
         
         # If you don't need a proxy, do this
         node.start()

         # otherwise do this (proxy host is a string username@hostname)
         #   node.start(proxy_host)

         # Wait for it to connect
         while node.is_connecting():
             time.sleep(0.1)

         if not node.is_connected():
             complain bitterly

         # < do some stuff with the node >

         # Finally
         node.stop()
"""

__version__ = "0.41c"

