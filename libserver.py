"""Module for server and client connections"""
import selectors
import json
import struct
import socket

import appcontroller

class ServerConnection:
    def __init__(self, selector: selectors.DefaultSelector, sock: socket.socket, addr: tuple, suppress_messages: bool=False):
        """Creates an instance of the ServerConnection class
        
        Arguments:
        selector: selectors.DefaultSelector -- Selector to use for handling I/O
        sock: socket.socket -- Socket used for communication
        addr: tuple -- Tuple returned by socket.socket.connect()
        suppress_messages: bool -- Set to true to suppress messages. Useful for debugging
        """
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.keep_alive = False
        self.suppress_messages = suppress_messages
        self._reset()

    def _reset(self):
        """Resets message properties to default values"""
        self._recv_buffer = b""
        self._send_buffer = b""
        self.header_len = None
        self.header = None
        self.msg_len = None
        self.msg = None
        self.fpga_response = None
        self.response = None
        self.response_created = False

    def _set_selector_events_mask(self, mode: str):
        """Sets the selector's event mask to r, w, or rw/wr
        
        Arguments
        mode: str -- Either "r", "w", or "rw" | "wr" for read, write, and read/write
        """
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw" or mode == "wr":
            events = selectors.EVENT_WRITE | selectors.EVENT_READ
        else:
            raise ValueError("Invalid events mask mode {}".format(repr(mode)))
        self.selector.modify(self.sock,events,data=self)

    def _read(self):
        """Internal read function, reads up to 4096 bytes from socket and adds to buffer"""
        try:
            # Socket should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable
            pass
        else:
            if data:
                # If valid data is received, add it to recv buffer
                self._recv_buffer += data
            else:
                # If false, then the client has disconnected
                raise RuntimeError("Peer closed.")

    def _write(self):
        """Internal write function

        When finished, sets selector events mask to "r" and resets communication properties
        """
        if self._send_buffer:
            # If there is valid data in the send buffer
            try:
                # Should be ready to write, sent is number of bytes sent
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable
                pass
            else:
                # Retains only data from index sent to end of array of bytes
                self._send_buffer = self._send_buffer[sent:]    
                if not self.suppress_messages:
                    print("Bytes sent: %d, Bytes Remaining: %d" % (sent, len(self._send_buffer)))
                # Close when the buffer is empty - binary data is true if not empty
                if sent and not self._send_buffer:
                    if self.keep_alive:
                        self._set_selector_events_mask("r")
                        self._reset()
                    else:
                        self.close()

    def read(self):
        """Processes header and message data from client
        
        This function is called repeatedly by socket event loop. 
        """
        self._read()

        # First step is to process header length
        if self.header_len is None:
            self.process_proto_header()

        # Second step is to process the header
        if self.msg_len is None:
            self.process_header()

        # Last step is to process the message
        if self.msg is None:
            self.process_request()

    def write(self):
        """Writes data to client
        
        This function is called repeatedly until a response is ready to be sent
        """
        # If message has been received
        if self.msg:
            # If the response hasn't been created (None is converted into boolean False)
            if not self.response_created:
                self.create_response()
        self._write()

    def close(self):
        """Closes the socket connection"""
        if not self.suppress_messages:
            print("Closing connection (%s, %s)" % self.addr,end='\n\n')
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print("Error: selector.unregister() exception for {}: {}".format(self.addr,repr(e)))
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_proto_header(self):
        """This function retrieves the header from the client's message"""
        proto_len = 2
        if len(self._recv_buffer) >= proto_len:
            self.header_len = struct.unpack("<H",self._recv_buffer[:proto_len])[0]
            self._recv_buffer = self._recv_buffer[proto_len:]

    def process_header(self):
        """This function processes the client's header"""
        if len(self._recv_buffer) >= self.header_len:
            self.header = json.loads(self._recv_buffer[:self.header_len].decode('ascii'))
            self.msg_len = self.header["length"]

            if ("keep_alive" in self.header):
                self.keep_alive = self.header["keep_alive"]
            else:
                self.keep_alive = False
            if not self.suppress_messages:
                print("Header received by server:")
                print(self.header)
            self._recv_buffer = self._recv_buffer[self.header_len:]

    def process_request(self):
        """Processes the client'smessage
        
        Executes received message and sends data as appropriate back to client
        """
        if len(self._recv_buffer) >= self.msg_len:
            self.msg = self._recv_buffer[:self.msg_len]
            pmsg = []
            for d in struct.iter_unpack("<I",self._recv_buffer[:self.msg_len]):
                pmsg.append(d[0])
            if ("print" in self.header) and (self.header["print"]):
                print("Message:",self.msg)
                print("\n".join("%08x"%item for item in pmsg))
            
            self._recv_buffer = self._recv_buffer[self.msg_len:]
            
            # Write data using io-controller
            self.fpga_response = appcontroller.remote_exec(pmsg,self.header)
            if not self.suppress_messages:
                print("Header written to client:")
            # At end of reading of data, set class to write mode
            self._set_selector_events_mask("w")

    def create_response(self):
        """Creates a response to send to the client"""
        # Make header
        json_str = json.dumps(self.fpga_response.make_header())
        if not self.suppress_messages:
            print(json_str)
        tmp = json_str.encode('ascii')
        self._send_buffer = struct.pack("<H",len(tmp)) + tmp
        # Append data
        self._send_buffer += self.fpga_response.data
        self.response_created = True
              
    def process_events(self, mask):
        """Executes the correct method based on the selector mask"""
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()


class ClientConnection:
    def __init__(self, target: tuple[str,int], keep_alive: bool=False, timeout: float=30):
        """Creates a ClientConnection instance
            
        Arguments:
        target -- a tuple of an IPv4 address (string) and port (int)
        keep_alive -- Keep connection alive after data is received? (bool)
        timeout -- Timeout of socket connection in seconds (float)
        """
        if not isinstance(target, tuple):
            target = (target, 6666)
        self.target = target
        self.keep_alive = keep_alive
        self.timeout = timeout
        self._args = {}
        self.sock = None
        self._reset()

    def _reset(self):
        """Reset message properties to default values"""
        self._recv_buffer = b""
        self._send_buffer = b""
        self.header_len = None
        self.header = dict()
        self.msg_len = None
        self.msg = None
        self.recv_data = []
        self.recv_done = False

    def _open(self):
        """Opens a new connection to the server"""
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.target)
        except ConnectionRefusedError:
            print("Connection refused. Server is likely not running")
        except Exception as e:
            raise e

    def _close(self):
        """Closes the connection to the server"""
        self.sock.close()
        self.sock = None

    def write(self, data: list[int]=[0], **kwargs):
        """Write data to server
        
        Arguments
        data: list[int] -- List of uint32-compatible integer values to send to server
        **kwargs -- The resulting dictionary is added to the header sent to the server
        """
        self._reset()
        if data is None:
            raise ValueError("Cannot write 'None' to server")
        # Each uint32-compatible integer value is 4 bytes
        self.header["length"] = 4*len(data)
        self.header["keep_alive"] = self.keep_alive
        # Append optional keyword arguments to header
        for key, value in kwargs.items():
            self.header[key] = value
        # The _args property contains fixed header values for all transactions
        for key, value in self._args.items():
            self.header[key] = value
        # Header is a JSON-formatted string
        self.header = json.dumps(self.header)
        self.header_len = len(self.header)
        self._send_buffer = struct.pack("<H",self.header_len)
        self._send_buffer += self.header.encode("ascii")
        self._send_buffer += struct.pack(f"<{len(data)}I",*data)

        # Write data
        self._write()
        # Read response
        while not self.recv_done:
            self.read()
        # Check for errors
        if self.header["err"]:
            raise ConnectionError("Connection returned error: {}".format(self.header["msg"]))
        # Close the socket connection
        if not self.keep_alive:
            self._close()

    def read(self):
        """Processes header and message data 
        
        This function is called repeatedly.
        """
        self._read()

        # First step is to process header length
        if self.header_len is None:
            self.process_proto_header()

        # Second step is to process the header
        if self.msg_len is None:
            self.process_header()

        # Last step is to process the message
        if self.msg is None:
            self.process_request()

    def _read(self):
        """Internal read function, reads up to 2**16 bytes from socket"""
        try:
            # Socket should be ready to read
            data = self.sock.recv(2**16)
        except BlockingIOError:
            # Resource temporarily unavailable
            pass
        else:
            if data:
                # If valid data is received, add it to recv buffer
                self._recv_buffer += data
            else:
                # If false, then the client has disconnected
                raise RuntimeError("Timeout?")


    def _write(self):
        """Internal write function"""
        if self.sock is None:
            self._open()

        while self._send_buffer:
            try:
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable
                pass
            else:
                # Retains only data from index sent to end of byte array
                self._send_buffer = self._send_buffer[sent:]
                if sent and not self._send_buffer:
                    # If all data has been sent, reset the message headers
                    # and return
                    self._reset()
                    break

    def process_proto_header(self):
        """This function retrieves the header from the server's message"""
        proto_len = 2
        if len(self._recv_buffer) >= proto_len:
            self.header_len = struct.unpack("<H",self._recv_buffer[:proto_len])[0]
            self._recv_buffer = self._recv_buffer[proto_len:]

    def process_header(self):
        """This function processes the server's header"""
        if len(self._recv_buffer) >= self.header_len:
            self.header = json.loads(self._recv_buffer[:self.header_len].decode('ascii'))
            self.msg_len = self.header["length"]
            self._recv_buffer = self._recv_buffer[self.header_len:]

    def process_request(self):
        """Processes the server's message"""
        if len(self._recv_buffer) >= self.msg_len:
            self.msg = self._recv_buffer[:self.msg_len]
            self.recv_data = []
            for d in struct.iter_unpack("<I",self._recv_buffer[:self.msg_len]):
                self.recv_data.append(d[0])
            
            self._recv_buffer = self._recv_buffer[self.msg_len:]
            self.recv_done = True