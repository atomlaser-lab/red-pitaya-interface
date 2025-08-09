classdef DeviceRegister < handle
    %DEVICEREGISTER Defines a class representing registers inside the
    %device
    properties
        addr        %The address of the register as a uint32 integer
        value       %The value of the register as a uint32 integer
        read_only   %Boolean value indicating if register is read-only
    end
    
    properties(Access = protected)
        addr_offset %Address offset
        conn        %A CONNECTIONCLIENT object to use for writing/reading data
    end
    
    properties(Constant)
        DEFAULT_ADDR_OFFSET = 0x40000000;   %Offset of all addresses
        MAX_ADDR = 0x3fffffff;              %Maximum address relative to offset
    end
    
    methods
        function self = DeviceRegister(addr,conn,read_only,addr_offset)
            %DEVICEREGISTER Constructs an object
            %
            %   SELF = DEVICEREGISTER(ADDR,CONN) creates an object with
            %   associated address and connection object.  The value of the
            %   register is initialized to 0. READ_ONLY property is set to false, 
            %   addr_offset is set to the default value
            %
            %   SELF = DEVICEREGISTER(ADDR,CONN,READ_ONLY) creates an object with
            %   associated address and connection object.  The value of the
            %   register is initialized to 0.  READ_ONLY property is set.
            %
            %   SELF = DEVICEREGISTER(ADDR,CONN,READ_ONLY,ADDR_OFFSET) also sets the
            %   addr_offset property.
            
            if nargin > 0
                self.addr = addr;
                self.value = uint32(0);
                if nargin > 1
                    self.conn = conn;
                end
            end
            if nargin < 3
                self.read_only = false;
            else
                self.read_only = read_only;
            end
            if nargin < 4
                self.addr_offset = DeviceRegister.DEFAULT_ADDR_OFFSET;
            else
                self.addr_offset = addr_offset;
            end
        end
    
        function set.addr(self,addr)
            %SET.ADDR Sets the address
            if ischar(addr)
                addr = hex2dec(addr);
            end

            if addr < 0 || addr > self.MAX_ADDR
                error('Address is out of range [%08x,%08x]',0,self.MAX_ADDR);
            else
                self.addr = uint32(addr);
            end
        end
        
        function self = set(self,v,bits)
            %SET Sets the value of the register in a given bit range
            %
            %   SELF = SET(SELF,V,BITS) Changes the value of the register
            %   SELF in the bit range given by BITS to V.
            tmp = self.value;
            mask = intmax('uint32');
            mask = bitshift(bitshift(mask,bits(2)-bits(1)+1-32),bits(1));
            v = bitshift(uint32(v),bits(1));
            self.value = bitor(bitand(tmp,bitcmp(mask)),v);
        end
        
        function v = get(self,bits)
            %GET Returns the value of the register in a given bit range
            %
            %   V = GET(SELF,BITS) returns the value V of the register SELF
            %   for bit range BITS (a 2 element vector) 
            mask = intmax('uint32');
            mask = bitshift(bitshift(mask,bits(2) - bits(1) + 1 - 32),bits(1));
            v = bitshift(bitand(self.value,mask),-bits(1));
        end
        
        function self = write(self)
            %WRITE Writes the value of the register to the device
            if isscalar(self)
                data = [self.addr_offset + self.addr,self.value];
                self.conn.write(data,'mode','write');
            else
                for nn = 1:numel(self)
                    self(nn).write;
                end
            end
        end
        
        function r = getWriteData(self)
            %GETWRITEDATA Returns the data to write
            %
            %   R = GETWRITEDATA(SELF) Returns the data to be written R for
            %   register SELF
            if isscalar(self)
                if self.read_only
                    r = [];
                else
                    r = [self.addr_offset + self.addr,self.value];
                end
            else
                r = [];
                for nn = 1:numel(self)
                    if ~self(nn).read_only
                        r(end + 1,:) = self(nn).getWriteData; %#ok<*AGROW>
                    end
                end
            end
        end
        
        function [r,self] = getReadData(self)
            %GETREADDATA Returns the data sent to the server to initiate a
            %read operation
            %
            %   [R,SELF] = GETREADDATA(SELF) Returns the data as R for
            %   register SELF
            if isscalar(self)
                r = self.addr_offset + self.addr;
            else
                r = zeros(numel(self),1);
                for nn = 1:numel(self)
                    r(nn,1) = self(nn).getReadData;
                end
            end
        end
        
        function self = read(self)
            %READ Reads the register value from the server/device
            %
            %   SELF = READ(SELF) reads the register value and stores it in
            %   the object SELF
            if isscalar(self)
                self.conn.write(self.addr_offset + self.addr,'mode','read');
                self.value = self.conn.recvMessage;
            else
                for nn=1:numel(self)
                    self(nn).read;
                end
            end
        end
        
        function varargout = print(self,name,width)
            %PRINT Prints a string describing the register value and
            %
            %   PRINT(SELF,NAME,WIDTH) prints a string describing the
            %   register with NAME having a width WIDTH
            
            if isscalar(self)
                s = sprintf(['% ',num2str(width),'s: %08x\n'],name,self.value);
            else
                for nn = 1:numel(self)
                    labelNew = sprintf('%s(%d)',name,nn - 1);
                    s{nn} = self(nn).print(labelNew,width); %#ok<AGROW>
                end
            end
            
            if iscell(s)
                str = '';
                for nn = 1:numel(s)
                    str = [str,s{nn}]; %#ok<AGROW>
                end
            else
                str = s;
            end
            
            if nargout == 0
                fprintf(1,'%s',str);
            else
                varargout{1} = str;
            end
        end
    
    end
    
end