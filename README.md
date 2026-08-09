# Red Pitaya TCP/IP Interface

This is a simple TCP/IP interface used for communicating with a Red Pitaya (RP) board using MATLAB or Python on the client side and Python for the socket server on the RP.  All of the projects that I have made for the RP use this system, since it is reasonably quick and robust.  The idea is that for a particular FPGA image, the user will have several parameters that they wish to change, organized into registers, and the user will want to adjust the parameters without having to worry about the mapping of parameters to registers.  Communication between the RP operating system and the programmable logic is done via a memory-mapped interface, which is assumed to have a memory offset of 0x40000000.  For basic reading and writing, the system makes use of the supplied `monitor` utility, so it should be compatible with a wide range of FPGA images.

For some examples as to how to use these classes in a real device, [this basic Red Pitaya project](https://github.com/ryan-james-thomas/basic-red-pitaya-design) is the best way to get started. Other public projects that use this interface are:
  - [A simple data acquisition project](https://github.com/ryan-james-thomas/red-pitaya-data-acquisition)
  - [A digital bias controller for optical I/Q phase modulators](https://github.com/atomlaser-lab/iq-bias-control)
  - [A laser servo controller](https://github.com/atomlaser-lab/digital-laser-servo)

## Set up

Clone this repository to your computer, and then add the folder to your MATLAB path or your Python environment.  Copy the Python files and the 'get_ip.sh' file to the RP.  They should be located in their own directory called 'server'.  You can use either `scp` (from a terminal on your computer) or your favourite GUI (I recommend WinSCP for Windows).  Use the supplied `setup.sh` file to transfer the files to the RP's '/root/server/' directory as 
```
./setup.sh root@rp-{MAC}.local
```
where `{MAC}` is the MAC address of your RP, written on the ethernet connector. You can also use the IP address of your device instead of the host name.

Next, change the execution privileges of `get_ip.sh` using `chmod a+x get_ip.sh`.  Check that running `./get_ip.sh` produces a single IP address (you may need to install dos2unix using `apt install dos2unix` and then run `dos2unix get_ip.sh` to make it work).  `get_ip.sh` assumes that you have connected the RP to the network using ethernet, so you will need to modify it to grab the WiFi address if that is how you are connecting the device. If it doesn't produce a single IP address, run the command `ip addr` and look for an IP address that isn't `127.0.0.1` (which is the local loopback address).  There may be more than one IP address -- you're looking for one that has tags 'global' and 'dynamic'.  Here is the output from one such device:
```
root@rp-f0919a:~# ip addr
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 00:26:32:f0:91:9a brd ff:ff:ff:ff:ff:ff
    inet 169.254.176.82/16 brd 169.254.255.255 scope link eth0
       valid_lft forever preferred_lft forever
    inet 192.168.1.109/24 brd 192.168.1.255 scope global dynamic eth0
       valid_lft 77723sec preferred_lft 77723sec
3: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1
    link/sit 0.0.0.0 brd 0.0.0.0
```
In this case the one we want is the address '192.168.1.109'.  In this case, `get_ip.sh` will work because it looks for an IP address with the 'global' tag.  If you have your RP connectly directly to your PC, then you will need to use the relevant IP address: in the above example, it is the address '169.254.176.82'.  

To run the Python server from any directory, run the command
```
python3 /root/server/appserver.py
```
if the server code is located in `/root/server/`: this will use `get_ip.sh` to get the IP address, and the server will be opened on port 6666. If you want to specify the hostname and/or port, run
```
python3 /root/server/appserver.py --host <host> --p <port>
```
By default, the program prints information about client connections and transfers which can be useful for debugging issues. If you want to suppress those messages, add an additional `-s` flag to the invocation. 

Once the server is running, you can move it to the background by using CTRL-Z to suspend it and then using the command `bg` to move it to the background.  If you need to move it back to the foreground, use `fg`.  To stop the server, use CTRL-C.

## MATLAB use

Use of the MATLAB classes is best done within another class that represents the FPGA configuration, but it can also be done manually.  The first step is to create a `ConnectionClient` object using
```
conn = ConnectionClient(<host_address>, <port>);
```
where `<host_address>` is the host address, either an IP address or a domain name like 'rp-f02b12.local', and `<port>` is the server port, by default 6666.

Next, we create a register object using
```
reg = DeviceRegister(<addr>, conn, <read_only>, <addr_offset>);
```
where `<addr>` is the memory address, without the overall memory offset of typically 0x40000000, and `<read_only>` is an optional boolean value indicating if the register is read-only in the FPGA logic; if it is neglected, then it is set to false. `<addr_offset>` can be used to specify a custom memory offset, which can be used if you have multiple memory-mapped interfaces or if you want to separate sub-modules in your design. You can switch the order of `<read_only>` and `<addr_offset>` in the constructor call so long as `<addr_offset>` is a uint32 integer: this is best done by providing the offset as a hex literal, such as `0x40000000`.

Finally, we create a parameter object using
```
p = DeviceParameter(<bit range>, reg, <type>, <units>);
```
where `<bit range>` is the bit range (inclusive) that the parameter occupies in the register, and `<type>` is the data type of the parameter.  Only 'uint32', 'int8', 'int16', and 'int32' types are allowed.  The reason 'uint8' and similar aren't allowed is that they are basically the same, from a conversion point of view, to 'uint32'.  If `<type>` is not provided it defaults to 'uint32'. `<units>` is used simply for display purposes and can be omitted.

The best way to illustrate how to use these classes is through an example.  Let us suppose that there is one register comprising two parameters, which control a pulse generator's period and pulse width.  We can define our classes as below
```
conn = ConnectionClient('rp-f02b12.local');
reg = DeviceRegister(0,conn);
period = DeviceParameter([0,15],reg,'uint32');
width = DeviceParameter([16,31],reg);
```
We can set the period and width values using the `set` method:
```
period.set(50);
width.set(25);
```
which will set their internal values so that `period.value == 50` and `width.value == 25`.  When we run the `.set()` methods for the parameters, they automatically update the associated bits in the associated register without modifying the other bits.  There is also an `integerValue` field, which is the integer value that is actually written to the device.  It is useful to separate the true, physical, value, `value`, from the integer value for semantic reasons.  For instance, it is probably more user-friendly to specify the period and width in seconds rather than clock edges (as above).  Suppose that `CLK = 125e6` is the clock frequency in Hz; then, we can set conversion functions for the period and width as
```
period.setFunctions('to',@(x) x*CLK,'from',@(x) x/CLK);
width.setFunctions('to',@(x) x*CLK,'from',@(x) x/CLK);
```
where the 'to' and 'from' functions convert to and from integer values, respectivey.  We can also set limits
```
period.setLimits('lower',1e-6,'upper',100e-6);
width.setLimits('lower',1e-6,'upper',100e-6);
```
which are clearly set relative to the true values.  A full set up of the parameters, now including the parameter units, might then look like
```
period = DeviceParameter([0,15],reg,'uint32','s')...
    .setLimits('lower',1e-6,'upper',100e-6)...
    .setFunctions('to',@(x) x*CLK,'from',@(x) x/CLK);

width = DeviceParameter([16,31],reg,'uint32','s')...
    .setLimits('lower',1e-6,'upper',100e-6)...
    .setFunctions('to',@(x) x*CLK,'from',@(x) x/CLK);
```
where we have used the fact that these methods return the object to chain methods together.

To write these parameters to the device, we can write the entire register using `reg.write()` which calls on the appropriate methods in `ConnectionClient`.  We can also use the `write()` method for the DeviceParameters, such as `period.write()` or `width.write()`, but these just call the underlying register write method.

To read from the device, we can call `reg.read()` which will update the stored register value in MATLAB with what was on the FPGA.  It will *not*, however, update the associated parameter values.  Those have to be done manually using the `.get()` method, such as `period.get()` or `width.get()`.  You can also read the parameter values using `period.read()` or `width.read()`.  

## Python use

Similarly to the MATLAB use case, it is best to use these classes as part of another class that represents the FPGA design, but they can be invoked manually. 

Again, the first step is to create a `ClientConnection` object using
```
import libserver

conn = libserver.ClientConnection((<host name>, <port>))
```
for the server host name and port. You can also just specify the port as a string instead of as part of a tuple.

Next, we create a register object using
```
from redpitaya import *
reg = DeviceRegister(<addr>, conn, read_only=<read only>, offset=<addr offset>)
```
for optional arguments `read_only` and `offset`: these default to `False` and `0x40000000`, respectively.

Finally, create a parameter object using
```
p = DeviceParameter(<bit range>, reg, <type>, <units>)
```
where `<bit range>` is a two-element list of bit values, and `<type>` is one of `ParamTypes` enumerated values (`UINT` and `INT` 8 through 64). 

Again, the physical value of the parameter should be separated from its integer representation, so we want to have conversion functions and limits. These can be set in the original parameter constructor. Below is a complete example of setting up an equivalent program as to the MATLAB example:
```
import libserver
from redpitaya import *
CLK = 125e6

conn = libserver.ClientConnection(('rp-f02b12.local', 6666))
reg = DeviceRegister(0, conn)
period = DeviceParameter([0,15], reg, ParamType.uint16,
    to_int=lambda x: x*CLK
    from_int=lambda x: x/CLK
    lower_limit=1e-6
    upper_limit=100e-6
)
width = DeviceParameter([16,31], reg, ParamType.uint16,
    to_int=lambda x: x*CLK
    from_int=lambda x: x/CLK
    lower_limit=1e-6
    upper_limit=100e-6
)
```
Similar `write()` and `read()` methods exist for registers and parameters.

## TCP/IP message format

The TCP/IP message (from both client and server) is sent as raw binary data broken into three sections.  The first two bytes are the length of the message header (not including the header length bytes).  The message header is a JSON-formatted ASCII string containing various bits of information, such as the length of the data payload ('length'), whether to keep the connection alive after processing ('keep_alive'), the mode which can be 'write', 'read', or 'command', as well as a shell command to run ('cmd').  Finally, after the header is the data payload.  When the mode is 'write', the payload is interpreted as alternate 32-bit memory addresses and 32-bit data to write, and when the mode is 'read' the payload is interpreted as just 32-bit memory addresses.  When the mode is 'command' the shell command under the field 'cmd' is executed.  This command should be provided in MATLAB as a cell array with arguments as different cells, so that, as an example, the command `./saveData -n 100 -t 2 -s 0` is formatted as `{'./saveData','-n','100','-t','2','-s','0'}`. In Python, this should be formatted as a list. If data with a length larger than 1 is provided, then that is written to a file first. This is useful if you want to write data to a file and then use that data in the FPGA by invoking a shell command.

Data is returned by the server in the same binary format but with a header consisting of fields `err` (true if an error has occurred), `msg` (a message about the error or other operations), and `length` (the length of the data payload). The data payload then follows as 32-bit integers.

