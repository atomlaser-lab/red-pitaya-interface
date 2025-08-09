import sys
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
# Define socket acceptance wrapper
#
sel = selectors.DefaultSelector()

def acceptWrapper(sock):
    conn, addr = sock.accept()
    if not suppress_output:
        print("Client (%s, %s) connected" % addr)
    conn.setblocking(False)
    message = libserver.Message(sel,conn,addr,suppress_output)
    sel.register(conn,selectors.EVENT_READ,data=message)


lsock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
lsock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
lsock.bind((host,port))
lsock.listen()
print("Listening on", (host,port))
lsock.setblocking(False)
sel.register(lsock,selectors.EVENT_READ,data=None)

try:
    while True:
        events = sel.select(timeout=None)
        for key,mask in events:
            if key.data is None:
                acceptWrapper(key.fileobj)
            else:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print("main: error: exception for {}:\n{}".format(message.addr,traceback.format_exc()))
                    message.close()

except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()
