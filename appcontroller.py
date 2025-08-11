import subprocess
import struct

RAW_DATA_FILE = "SavedData.bin"
WRITE_DATA_FILE = "data-to-write.bin"

def write(data,header):
    response = {"err":False,"errMsg":"","data":b''}

    if ("debug" in header) and (header["debug"]):
        #
        # This is for debugging purposes only
        #
        response["errMsg"] = "Message received"
        return response     

    elif header["mode"] == "write":
        #
        # Write data using the "monitor" utility.  An array of data comprising
        # interleaved addresses and data can be sent
        #
        for i in range(0,len(data),2):
            addr = data[i]
            cmd = ['monitor',format(addr),'0x' + '{:0>8x}'.format(data[i+1])]
            if ("print" in header) and (header["print"]):
                print("Command: ",cmd)
            result = subprocess.run(cmd,stdout=subprocess.PIPE)
            if result.returncode != 0:
                break
            else:
                tmp = result.stdout.decode('ascii').rstrip()
                if len(tmp) > 0:
                    response["data"] += struct.pack("<I",int(tmp,16))

    elif header["mode"] == "read":
        #
        # Read data using the "monitor" utility. An array of addresses
        # can be sent
        #
        for i in range(0,len(data)):
            addr = data[i]
            cmd = ['monitor',format(addr)]
            if ("print" in header) and (header["print"]):
                print("Command: ",cmd)
            result = subprocess.run(cmd,stdout=subprocess.PIPE)
            if result.returncode != 0:
                break
            else:
                tmp = result.stdout.decode('ascii').rstrip()
                if len(tmp) > 0:
                    response["data"] += struct.pack("<I",int(tmp,16))


    elif header["mode"] == "command":
        #
        # If there is data to write (len(data) > 1), then write that to a file
        #
        if len(data) > 1:
            fid = open(WRITE_DATA_FILE,"wb")
            newData = []
            for i in range(1,len(data)):
                fid.write(struct.pack("<I",data[i]))
            fid.close()
        #
        # Otherwise, parse the command
        #
        cmd = header["cmd"]
        if ("print" in header) and (header["print"]):
            print("Command: ",cmd)
        result = subprocess.run(cmd,stdout=subprocess.PIPE)

        if result.returncode == 0:
            #
            # When there is no error
            #
            if (("return_mode" in header) == False) or header["return_mode"] == "terminal":
                #
                # Read the data from the terminal as text and then convert it
                # into binary
                #
                data = result.stdout.decode('ascii').rstrip()
                if len(data) > 0:
                    buf = struct.pack("<I",int(data,16))
                else:
                    buf = b''
                response["data"] += buf

            elif header["return_mode"] == "file":
                #
                # Read data from the standard saved data file as binary
                #
                if ("file_name" in header):
                    fid = open(header["file_name"],"rb")
                else:
                    fid = open(RAW_DATA_FILE,"rb")

                response["data"] = fid.read()
                fid.close()

    elif header["mode"] == "read_file":
        if "file_name" in header:
            fid = open(header["file_name"],"rb")
        else:
            response = {"err":True,"errMsg":"No filename given for read_file operation","data":b''}
            return response

        if ("file_start_byte" in header):
            fid.seek(header["file_start_byte"])

        if "file_num_bytes" in header:
            response["data"] = fid.read(header["file_num_bytes"])
        else:
            response["data"] = fid.read()
        fid.close()
        result = None
    
    
    if (result != None) and result.returncode != 0:
        response = {"err":True,"errMsg":"Bus error","data":b''}

    return response
        


    
        
