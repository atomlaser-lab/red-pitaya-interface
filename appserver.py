"""Starts an instance of a socket server for communicating with the FPGA"""
import socket
import selectors
import traceback
import subprocess
import os
import argparse

import libserver

#
# Parse input arguments
#
parser = argparse.ArgumentParser(prog='appserver',description='Starts an instance of a socket server for communicating with the FPGA')
parser.add_argument('-i','--host',nargs='?',help='IP address for server')
parser.add_argument('-p','--port',nargs='?',default=6666,help='Port to listen on')
parser.add_argument('-s','--suppress-output',action='store_true',help='Suppress output messages')

args = parser.parse_args()

if args.host == None:
    sfile = os.path.dirname(os.path.abspath(__file__)) + '/get_ip.sh'
    r = subprocess.run([sfile],stdout=subprocess.PIPE)
    host = r.stdout.decode('ascii').rstrip()
    if len(host) == 0:
        r = subprocess.run([sfile,'-t','inet'],stdout=subprocess.PIPE)
        host = r.stdout.decode('ascii').rstrip()
else:
    host = args.host

port = args.port    #Default is 6666 from argparse
suppress_output = args.suppress_output  #Default is false

#
# Selectors uses the system select() function to poll file objects for events.
# 
sel = selectors.DefaultSelector()
#
# Define socket acceptance function when a client connects to the socket server
#
def accept_wrapper(sock):
    conn, addr = sock.accept()
    if not suppress_output:
        print("Client (%s, %s) connected" % addr)
    conn.setblocking(False)
    server_conn = libserver.ServerConnection(sel,conn,addr,suppress_output)
    sel.register(conn,selectors.EVENT_READ,data=server_conn)

#
# This creates the actual socket server that listens for client connections
#
lsock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
lsock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
lsock.bind((host,port))
lsock.listen()
print("Listening on", (host,port))
lsock.setblocking(False)
# Register this socket server with selectors so that we can respond to new client connections
sel.register(lsock,selectors.EVENT_READ,data=None)

try:
    while True:
        # Find all registered connections with an event - can be new connections or actions by existing connections
        events = sel.select(timeout=None)
        for key,mask in events:
            if key.data is None:
                # If there is no data, then it must be a new connection
                accept_wrapper(key.fileobj)
            else:
                # Else, process that message
                server_conn = key.data
                try:
                    server_conn.process_events(mask)
                except Exception:
                    print("main: error: exception for {}:\n{}".format(server_conn.addr,traceback.format_exc()))
                    server_conn.close()

except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()
