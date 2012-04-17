#!/usr/bin/env python2.2
#-*- coding: utf-8 -*-
#@+leo-ver=4
#@+node:@file telephony.py
#@@first
#@@first
#@@path /home/rodrigob/.circle/plug-ins
#@@language python
#@@color
#@+at
# This is a plugin for TheCircle, thecircle.org.au
# It aims to allow voice and video conferences between users.
# It install hooks that allow triggering GnomeMeeting/NetMeeting sessions 
# between TheCircle peers.
# Rodrigo Benenson. 2003-2004.
#@-at
#@@c

#@+at
# 22/11/03 Talk with ThomasV. Study in detail speex and *meeting. RodrigoB.
# 23/11/03 Create the file. Working. RodrigoB.
# 25/11/03 Doing the simple gtk dialogs. Solved the plugins import problem. 
# Creating the handler. RodrigoB.
# 27/11/03 Minor works. RodrigoB.
# 30/11/03 Working to get a test ambient. Finishing base code. Problems with 
# test system. RodrigoB.
# 03/12/03 Documenting the local bug. RodrigoB.
# 06/12/03 Debugging. First working session. RodrigoB.
# 07/12/03 First remote test. Debugging. RodrigoB & ThomasV.
# 08/12/03 More remote tests. Debugging. RodrigoB & ThomasV.
# 11/12/03 Implementing field usage during initialization. RodrigoB.
# 
# Todo
# ----
# 
# - Trick to add and entry in the user's menu "Meet" << Add hooks system to 
# TheCircle (conceptually easy, like Leo, but inverted pull-push logic)
#     circlelib/chatgtk.py:1302:        menu.append((_("View %s's 
# details")%name, details))
#     def name_context_menu(widget,ev,chat,name):
#     """name should be an acquaintance nickname"""
# 
#@-at
#@@c



import os, os.path
import threading
import gtk
import utility
import check
from utility import Task

#@+others
#@+node:Plugins documentation
#@+at
#  Notes on writing plug-ins:
# 
#      circle loads all plug-ins located in the .circle/plug-ins directory
#      on startup. Plug-ins are just python files (ending in .py).
# 
#      - two special variables are defined before each plug-in is loaded:
#              app is the application object
#              node is the network node object
# 
#      - on startup the start() function will be called, if it is defined
# 
#      - on shutdown the stop() function will be called, if it is defined
# 
#      - use app.chat.register to register commands
# 
#      - use app.add_menu_item to register menu items
#@-at
#@@c

#@+at
# register(self, name, min_param, max_param, function)
#     Register a command.
#     A command takes a certain number of parameters separated by spaces,
#     up to max_param, and not less than min_param. The last parameter may
#     contain spaces.
# 
#     function may assert that its argument matches ['text'] (i.e. is
#     a list of items each of type string or unicode) and that the
#     length of this list is in the range [min_param, max_param].
# 
#     E.g.:
#     def mycommand(chat, params):
#         check.check_matches(params, ['text'])
#         check.check_assertion(1 <= len(params) <= 2)
#         str = 'You typed ' + params[0]
#         if len(params) == 2:
#             str += '; ' + params[1]
#         chat.show(str + '
# ')
#     app.chat.register('mycommand', 1, 2, mycommand)
#@-at
#@@c

#@+at
# add_menu_item(self, menu_name, name, action, *args)
#     Add a menu item to a menu. If the menu does not exist it will
#     also be created.
#     If the menu item has an equivalen chat command, add that command
#     to the name preceded by a colon, eg 'Log out:/logout'
#     Action will be called with the menu item object, followed by
#     *args
#@-at
#@@c

#@+at
# node.add_handler(self, msg_name, how, param_tmpl = (), result_tmpl = 'any'):
#     """Add a handler for a specific message.
# 
#      msg_name: what message type to handle (i.e. request[0])
#      how : a class instance with a method defined thus:
#              handle(self, request, address, call_id)
#          where
#              request is the actual message
#              address is the address of the caller
#              call_id is (with address) a unique identifier of the message
#          and returning the reply.
# 
#          Note: because UDP is an unreliable protocol, the handler might
#              be called more than once for the one message (if the reply
#              packet was dropped). Use (address,call_id) to check for repeats
#              if this is a problem.
#          """
#@-at
#@@c
#@nonl
#@-node:Plugins documentation
#@+node:start/stop the plugin
#@+at
# Plugin initialization/finishing, routines
#@-at
#@@c

#@+at
# Two variables are already defined (magic trick):
#     - app,  is the application  object
#     - node, is the network node object
#@-at
#@@c

#@+others
#@+node:meet (deprecated test code)

def meet(chat, params):
    """
    Expect the user name as a param.
    """
    # should reques the user identifier too <<<
    #check.check_matches(params, ['text'])
    #check.check_assertion(1 <= len(params) <= 1)
    name_of_requester = params[0]
    t_message = "Do you accept a voice session " + (name_of_requester and "with %s "%name_of_requester) + "?"
    
    def to_do():
        d = gtk.MessageDialog(parent=app.window, flags=0, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, message_format= t_message);
        # trick to get the result
        ret = d.run()
        d.destroy()
        ret = {-8:"Yes", -9:"No", -4:"Abort", -5:"Ok", -6:"Cancel"}.get(ret, ret) # strange but work				
        app.chat.show("The result of the query is %s" % ret + '\n')	
        return
        
    utility.mainthread_call(to_do)
    return
#@nonl
#@-node:meet (deprecated test code)
#@-others

def start():
    """
    Called at the initialization of this plugin
    """    
    
    # check app existence  -:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-
    t_field = app.chat.get_field()
    
    t_string = "Starting telephony plugin. "
    if os.name == "posix":
        p = os.popen("which gnomemeeting"); s = p.read(); p.close()
        
        if os.path.basename(s) == "gnomemeeting\n":
            t_string += "Detected required software at %s\n" % s
        else:
            t_string += "Could not find GnomeMeeting, please install it. Telephony plugin disabled.\n"
            return
        
    else:
       t_string += "Can not check required software, will supose that NetMeeting is installed.\n"
    
    t_field.show(t_string, ["light_grey"])
    t_field.close()
    
    # register the command	 -:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-
    #app.chat.register('meet', 1, 1, meet)
    app.chat.register('meet', 1, 1, request_meeting)
    
    # add the node handler -:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-
    node.add_handler("start meeting", TelephonyHandler()) #add_handler(self, msg_name, how, param_tmpl = (), result_tmpl = 'any')
    
    # add the "users menu" entry -:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-
    # how to to that ?
    
    return

def stop():
    """
    Called at the end of the execution of thecircle, to shutdown this plugin
    """
    # nothing special to do
    return
#@-node:start/stop the plugin
#@+node:request meeting
#@+at
# Routines associated with the emisor/receiver meeting initialization sequence
#@-at
#@@c

    
def request_meeting(chat, params):
    """
    Request a meeting with the user "nickname".
    This function is attached to the chat command "/meet"
    
    Send a request to the receiver. If he/she accept, then a local meeting call will be emited.
    
    node.call receiver query="start meeting"
    if return yes: start a call to the receiver
    else: show the error message (rejected, or technical failure)
    """

    check.check_matches(params, ['text'])
    check.check_assertion(1 <= len(params) <= 1)
    nickname = params[0]

    if not app.name_server.nicknames.has_key(nickname):
        app.chat.show("Unknown user '%s' at the local names server.\n"% nickname)	
        return
        
    server_acq = app.name_server.nicknames[nickname] # we are the "client", the receiver is the "server".
    
    if server_acq.address == node.address:
	app.chat.show("You can not meet yourself, sorry.\n")	
	return
    
    if not server_acq.online:
        app.chat.show("The user '%s' is not online.\n"% nickname)	
        return
    

    Task(request_meeting_task, server_acq).start()
    
    return
    
    
def request_meeting_task(server_acq):
    """
    function that is called in a thread
    """    
    
    server_address  = server_acq.address # address is (ip, port)
    server_nickname = server_acq.nickname

    #app.chat.show( "Sending the request of %s to adress %s\n" % (server_nickname, server_address))	

#@+at
#     node.call(self, address, query, low_priority=0, n_retries=udp_retries):
#         """Perform a UDP remote procedure call, and return the result.
# 
#              This will raise an Error("no reply") if the address can not be 
# contacted.
#              It will also raise an Error if the remote computer replies with 
# an
#              Error object."""
#@-at
#@@c
    
    #node.call receiver query="start meeting"
    ret = node.call(server_address, ("start meeting",))
    
    #if return yes: start a call to the receiver
    if ret == 1:
        server_ip = server_address[0]
        url = "callto://%s" % server_ip
        t_message = "%s accepted your request, and is ready to receive your call. Starting the meeting session." % server_nickname
        start_meeting_software(url)
    #else: show the error message (rejected, or technical failure)
    elif ret == 0:
        t_message = "%s reject your meeting request." % server_nickname
    else: # ret == -1 or anything else
        t_message = "%s had a technical inconvenient. Meeting session could not start."% server_nickname

    # show the message
    utility.mainthread_call(app.chat.show, t_message + '\n')
    return
    


#@-node:request meeting
#@+node:class TelephonyHandler
class TelephonyHandler:
    """
    Handler class passed to node.py/node.add_handler
    """
#@+at
# Add a handler for a specific message.
# 
#  msg_name: what message type to handle (i.e. request[0])
#  how : a class instance with a method defined thus:
#          handle(self, request, address, call_id)
#             where
#                 request is the actual message
#                  address is the address of the caller
#                  call_id is (with address) a unique identifier of the 
# message
#          and returning the reply.
# 
#  Note: because UDP is an unreliable protocol, the handler might
#          be called more than once for the one message (if the reply
#        packet was dropped). Use (address,call_id) to check for repeats
#        if this is a problem.
#@-at
#@@c	
    
    answered_calls = []
    
    def handle(self, request, address, call_id):
        """
        Manage the "start meeting" command.
        Test command: !node.handlers["start meeting"][0].handle("start meeting", None, None)
        """
        
        if (address, call_id) in self.answered_calls:
            return None # omit repeated ansers
        

        assert request == ("start meeting",), "This handler does not manage request '%s' (type %s)" % (request, type(request))

                
        # obtain the caller name
        caller_name = "unknown" # better than None ?
        for t_acq in app.name_server.acquaintances.values():
            if t_acq.address == address:
                caller_name = t_acq.nickname 
                break # found the searched name

        
        #app.chat.show( "Received a meeting request by user %s\n" % caller_name)	
        print "Received a meeting request by user %s\n" % caller_name
        
        # use the dialog to obtain the result
        result_list = [None]
        ok = threading.Semaphore(); ok.acquire()
        utility.mainthread_call(self.receiver_dialog, result_list, ok, caller_name)
        ok.acquire(); ok.release() # will wait until the dialog release the semaphore
        
        ret = result_list[0] # result_list[0] now store the dialog result
        
        #app.chat.show( "Your response to the meeting request is %s\n" % ret)	
        print "The result of the request is %s\n" % {1:"Yes", 0:"No", -1:"Technical error"}.get(ret, ret) # strange but work				
                
        self.answered_calls.append((address, call_id))
        return ret # return back to the client the resulting value
        
    #@    @+others
    #@+node:receiver dialog
        
    def receiver_dialog(self, result_list, sem, name_of_requester=None):
        """
        Show a dialog to allow incoming meeting requests.
        This method is attached to the node handler of the query "start meeting"
        As it call gtk methods, should be run in the main_thread
        Recieve a result list and a semaphore. Use the semaphore to indicate when ready, and the result_list to return the result in the first element of the list.
        """
        
    #@+at
    # Do you accept a voice session with the_call_starter_name ? (need 
    # *meeting) [Yes]
    # (*meeting start opening)
    # *meeting is ready for incoming calls ? [Yes] [Fail]
    # 
    # and when the user accept, the starter, the circle client launch a 
    # *meeting call to the receiver that has confirmed to be ready.
    # 
    # Simple, easy and clean (but somewhat burocratic, how to know when the 
    # app is up and running ?)
    # 
    #@-at
    #@@c
    
        
        # Do you accept a voice session with the_call_starter_name ? (need *meeting) [Yes]
        t_message = "Do you accept a voice session " + (name_of_requester and ("with %s " % name_of_requester)) + "?"
        d = gtk.MessageDialog(parent=None, flags=0, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, message_format= t_message);
        d.show()
        ret = d.run() #ret values, YES = -8;NO = -9;ABORT = -4;OK = -5;CANCEL = -6;# gtk.BUTTONS_YES_NO; gtk.BUTTONS_OK_CANCEL
        d.destroy()
        
        print "The result of the query is %s\n" % {-8:"Yes", -9:"No", -4:"Abort", -5:"Ok", -6:"Cancel"}.get(ret, ret) # strange but work				
        
        if ret != -8: # if the user did not accepted
            # send a "user rejected" message back the meeting requester
            result_list[0] = 0
            sem.release()
            return
            
        #(*meeting start opening)
        app.chat.show("Launching the meeting software. Please wait a moment.\n")
        start_meeting_software()
        
        #*meeting is ready for incoming calls ? [Yes] [Fail]
        t_message = "Starting meeting software, please wait.\nWhen meeting software is ready for incoming calls, please press Ok.\n(Press Cancel if opening failed)"
        d = gtk.MessageDialog(parent=None, flags=0, type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO, message_format=t_message);
        d.show()
        ret = d.run()
        d.destroy()
        
        print "The result of the query is %s\n" % {-8:"Yes", -9:"No", -4:"Abort", -5:"Ok", -6:"Cancel"}.get(ret, ret) # strange but work				
        
        if ret != -8: # if the user presented a fail (not OK)
            # send a "could not open meeting software" message back the meeting requester
            result_list[0] = -1
            sem.release()
            return
    
        # send an, "all ready" message back the meeting requester
    
        result_list[0] = 1
        sem.release()
        return
    
    #@-node:receiver dialog
    #@-others
#@-node:class TelephonyHandler
#@+node:start meeting software
#@+at
# Helper function to launch the meeting software
#@-at
#@@c


def start_meeting_software(callto=None):
    """
    Initialize the meeting software, using command line commands.
    
    callto, a receiver meeting url (normally, callto://theip or callto://thednsname)
    
    Linux: gnomemeeting --call=callto://127.0.0.1
    Windows: rundll32.exe msconf.dll,CallToProtocolHandler callto://127.0.0.1
    """

    # how confirm correct execution ?

    if os.name == "posix":
        if callto:
            #command = "gnomemeeting --call=%s &"% callto # start a call
	    command = "gnomemeeting -c %s &"% callto # start a call
        else:
            command = "gnomemeeting &" # open it, to be able to receive calls
            
    elif os.name == "win32":
        if callto:
            command = "rundll32.exe msconf.dll,CallToProtocolHandler %s "% callto # start a call
        else:
            command = "rundll32.exe msconf.dll,CallToProtocolHandler callto:// &" # open it, to be able to receive calls

        
    else:
        raise "OS not managed, sorry."
    
    os.system(command) # start the process
            
    return
    
    
#@-node:start meeting software
#@-others
#@nonl
#@-node:@file telephony.py
#@-leo
