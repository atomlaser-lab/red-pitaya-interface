classdef DeviceParameter < handle
    %DEVICEPARAMETER Class defining a parameter in the device
    properties
        bits        %Bit range in the device
        upperLimit  %Upper limit on value
        lowerLimit  %Lower limit on value
        type        %Data type of the parameter
        units       %The units of the physical parameter
    end
    
    properties(SetAccess = protected)
        regs                %Array of registers associated with this parameter
        value               %Human-readable value in real units
        intValue            %Integer value written for FPGA
        toIntegerFunction   %Function converting real values to integer values
        fromIntegerFunction %Function converting integer values to real values
    end
    
    methods
        function self = DeviceParameter(bits,regIn,type,units)
            %DEVICEPARAMETER Constructs an instance of the class
            %
            %   SELF = DEVICEPARAMETER(BITS,REGIN) uses the bit range BITS
            %   and input registers REGIN to define the parameter.  When
            %   REGIN is only one register (of type DEVICEREGISTER) then
            %   BITS should be a two-element vector.  When REGIN is
            %   of size N, then BITS should be an Nx2 matrix
            %
            %   SELF = DEVICEPARAMETER(__,TYPE) sets the data type of the
            %   parameter.  Can be 'uint32', 'int32', or 'int16'
            %
            if nargin == 0
                return
            end
            
            self.regs = regIn;
            self.bits = bits;
            
            if size(self.bits,1) ~= numel(self.regs)
                error('Number of registers must be the same as the number of bit ranges');
            end
            %
            % Default conversion functions just pass the value
            %
            self.toIntegerFunction = @(x) x;
            self.fromIntegerFunction = @(x) x;
            
            if nargin < 3
                self.type = 'uint32';
            elseif strcmp(type,'int32') || strcmp(type,'uint32') || strcmp(type,'uint64') || strcmp(type,'int16') || strcmp(type,'int8')
                self.type = type;
            else
                error('Type must be either ''uint64'', ''uint32'', ''int32'', or ''int16'' or ''int8''!');
            end

            if nargin < 4
                self.units = '';
            else
                self.units = units;
            end
            
            if numel(self.regs) > 1 && ~(strcmpi(self.type,'uint64') || strcmpi(self.type,'uint32'))
                error('When the number of registers is larger than 1, type must be ''uint32'' or ''uint64''!');
            end
        end
        
        function set.bits(self,bits)
            %SET.BITS Sets the bit ranges
            if mod(numel(bits),2) ~= 0 || any(bits(:) < 0) || any(bits(:) > 31) || size(bits,2) > 2
                error('Bits must be a 2-element vector with values in [0,31] or an Nx2 matrix with values in [0,31]');
            elseif numel(bits) == 2 && numel(self.regs) > 1 %#ok<MCSUP>
                error('If the number of associated registers is larger than 1 then bits must be an Nx2 matrix with values in [0,31]');
            else
                if numel(bits) == 2
                    self.bits = sort(bits(:)'); %#ok<TRSRT>
                else
                    self.bits = bits;
                end
            end  
        end
        
        function N = numbits(self)
            %NUMBITS Returns the number of bits associated with this
            %parameter
            N = sum(abs(diff(self.bits,1,2)),1) + 1;
        end
        
        function self = setFunctions(self,varargin)
            %SETFUNCTIONS Sets the toInteger and fromInteger functions for
            %converting physical values to integer values
            %
            %   SETFUNCTIONS(SELF,NAME,VALUE,...) sets the functions
            %   according to name/value pairs.  Allowed names are 'TO' or
            %   'FROM' corresponding to functions that convert to an
            %   integer value or from an integer value
            
            %Check register inputs
            if mod(numel(varargin),2) ~= 0
                error('You must specify functions as name/value pairs!');
            end
            
            for nn = 1:2:numel(varargin)
                if ~isa(varargin{nn+1},'function_handle')
                    error('Functions must be passed as function handles!');
                end
                s = lower(varargin{nn});
                switch s
                    case 'to'
                        self.toIntegerFunction = varargin{nn+1};
                    case 'from'
                        self.fromIntegerFunction = varargin{nn+1};
                end
            end
        end
        
        function self = setLimits(self,varargin)
            %SETLIMITS Sets the upper and lower limits on the physical
            %value
            %
            %   SETLIMITS(SELF,NAME,VALUE,...) sets the limits on this
            %   parameter according to name/value pairs.  Allowed names are
            %   'upper' and 'lower'.
            
            %Check register inputs
            if mod(numel(varargin),2)~=0
                error('You must specify functions as name/value pairs!');
            end
            
            for nn=1:2:numel(varargin)
                s = lower(varargin{nn});
                switch s
                    case 'lower'
                        self.lowerLimit = varargin{nn+1};
                    case 'upper'
                        self.upperLimit = varargin{nn+1};
                end
            end
        end

        function r = getLimits(self)
            %GETLIMITS Returns the lower and upper limits as an array
            r = [self.lowerLimit,self.upperLimit];
        end
        
        function r = toInteger(self,varargin)
            %TOINTEGER Converts the arguments to an integer
            r = self.toIntegerFunction(varargin{:});
            try
                r = round(r);
            catch
                
            end
        end
        
        function r = fromInteger(self,varargin)
            %FROMINTEGER Converts the arguments from an integer
            r = self.fromIntegerFunction(varargin{:});
        end
        
        function self = checkLimits(self,v)
            %CHECKLIMITS Checks the limits on the set value
            if ~isempty(self.lowerLimit) && isnumeric(self.lowerLimit) && (v < self.lowerLimit)
                error('Value is lower than the lower limit!');
            end
            
            if ~isempty(self.upperLimit) && isnumeric(self.upperLimit) && (v > self.upperLimit)
                error('Value is higher than the upper limit!');
            end
            
        end
        
        function self = set(self,v,varargin)
            %SET Sets the physical value of the parameter and converts it
            %to an integer as well
            %
            %   SET(SELF,VALUE) Sets the parameter to the value given by
            %   VALUE.  Converts to the integer representation and sets the
            %   appropriate bits in the registers
            %   
            %   If SELF is an array of elements, V must be an array of the
            %   same length, and SET will loop through the pairs of SELF
            %   and V
            if numel(self) > 1
                if isscalar(numel(v))
                    v = repmat(v,numel(self),1);
                end
                for nn = 1:min(numel(self),numel(v))
                    self(nn).set(v(nn),varargin{:});
                end
            else
                %
                % Check limits first, then convert to integer and check that
                % the value will fit in the registers
                %
                if ~ischar(v) && ~isstring(v)
                    self.checkLimits(v);
                end
                tmp = self.toInteger(v,varargin{:});
                if log2(abs(double(tmp))) > self.numbits
                    error('Value will not fit in bit range with %d bits',self.numbits);
                end
                %
                % Set the value and the integer value
                %
                self.value = v;
                self.intValue = tmp;
                %
                % Convert that integer value to the appropriate data type and
                % type cast it to an unsigned value of the right length
                %
                if islogical(self.intValue)
                    self.intValue = uint32(self.intValue);
                elseif strcmpi(self.type,'uint32')
                    self.intValue = typecast(uint32(self.intValue),'uint32');
                elseif strcmpi(self.type,'uint64')
                    self.intValue = typecast(uint64(self.intValue),'uint64');
                elseif strcmpi(self.type,'int32')
                    self.intValue = typecast(int32(self.intValue),'uint32');
                elseif strcmpi(self.type,'int16')
                    self.intValue = uint32(typecast(int16(self.intValue),'uint16'));
                elseif strcmpi(self.type,'int8')
                    self.intValue = uint32(typecast(int8(self.intValue),'uint8'));
                end
                %
                % Set the appropriate register values
                %
                if isscalar(self.regs)
                    self.regs.set(self.intValue,self.bits);
                else
                    tmp = uint64(self.intValue);
                    bit_min = 0;
                    for nn = 1:numel(self.regs)
                        % mask = uint64(intmax('uint32'));
                        bit_max = self.bits(nn,2) - self.bits(nn,1) + bit_min;
                        mask = bitxor(uint64(2^(bit_max + 1) - 1),uint64(2^bit_min - 1));
                        v = bitshift(bitand(tmp,mask),-32*(nn - 1));
                        self.regs(nn).set(v,self.bits(nn,:));
                        bit_min = bit_max + 1;
                        % tmp = bitshift(tmp,-abs(diff(self.bits(nn,:)))-1);
                    end
                end
            end
        end
        
        function r = get(self,varargin)
            %GET Gets the physical value of the parameter from the integer
            %value
            %
            %   R = GET(SELF) Returns the physical value of the parameter
            %   associated with DEVICEPARAMETER SELF
            
            if isscalar(self)
                if isscalar(self.regs)
                    %
                    % When there is only one register, read the data from the
                    % register according to the parameter data type
                    %
                    self.intValue = self.regs.get(self.bits);
                    if strcmpi(self.type,'int32')
                        v = typecast(self.intValue,'int32');
                    elseif strcmpi(self.type,'uint32')
                        v = typecast(self.intValue,'uint32');
                    elseif strcmpi(self.type,'int16')
                        v = typecast(uint16(self.intValue),'int16');
                    elseif strcmpi(self.type,'int8')
                        v = typecast(uint8(self.intValue),'int8');
                    end
                    self.value = self.fromInteger(double(v),varargin{:});
                else
                    %
                    % When there is more than one register, read the data from
                    % the registers in a loop
                    %
                    tmp = uint64(0);
                    for nn=numel(self.regs):-1:2
                        tmp = tmp + bitshift(uint64(self.regs(nn).get(self.bits(nn,:))),abs(diff(self.bits(nn-1,:)))+1);
                    end
                    tmp = tmp + uint64(self.regs(1).get(self.bits(1,:)));
                    self.intValue = tmp;
                    self.value = self.fromInteger(double(self.intValue),varargin{:});
                end
                r = self.value;
            else
                r = zeros(numel(self),1);
                for nn = 1:numel(self)
                    if nargout > 0
                        r(nn) = self(nn).get;
                    else
                        self(nn).get;
                    end
                end
            end
        end
        
        function self = read(self)
            %READ Reads data from the device through the action of the
            %DEVICEREGISTER read() method
            
            if isscalar(self)
                for nn = 1:numel(self.regs)
                    self.regs(nn).read;
                end
                self.get;
            else
                for nn = 1:numel(self)
                    self(nn).read;
                end
            end
        end
        
        function self = write(self)
            %WRITE writes the parameter to the device via the
            %DEVICEREGISTER write() method
            if isscalar(self)
                for nn=1:numel(self.regs)
                    self.regs(nn).write;
                end
            else
                for nn=1:numel(self)
                    self(nn).write;
                end
            end
        end
        
        function s = print(self,name,width,formatstr,units)
            %PRINT Prints the parameter value and name
            %
            %   STR = PRINT(SELF,NAME,WIDTH,FORMATSTR,UNITS) returns a
            %   string STR with the name and value of the parameter that is
            %   WIDTH wide.  UNITS is optional.  If no return argument is
            %   desired then the result is printed to the command line
            if nargin < 5
                units = self.units;
            end
            s = sprintf(['% ',num2str(width),'s: ',formatstr,' %s\n'],name,self.value,units);
            if nargout == 0
                fprintf(1,s);
            end
        end
        
        function disp(self)
            if isscalar(self)
                fprintf(1,'\t DeviceParameter with properties:\n');
                if size(self.bits,1) == 1
                    fprintf(1,'\t\t            Bit range: [%d,%d]\n',self.bits(1),self.bits(2));
                else
                    for nn=1:size(self.bits,1)
                        fprintf(1,'\t\t  Bit range for reg %d: [%d,%d]\n',nn-1,self.bits(nn,1),self.bits(nn,2)); 
                    end
                end
                if isnumeric(self.value) && isscalar(self)
                    fprintf(1,'\t\t       Physical value: %.4g %s\n',self.value, self.units);
                elseif isnumeric(self.value) && numel(self.value)<=10
                    fprintf(1,'\t\t       Physical value: [%s] %s\n',strtrim(sprintf('%.4g ',self.value)), self.units);
                elseif isnumeric(self.value) && numel(self.value)>10
                    fprintf(1,'\t\t       Physical value: [%dx%d %s] %s\n',size(self.value),class(self.value), self.units);
                elseif ischar(self.value)
                    fprintf(1,'\t\t       Physical value: %s\n',self.value);
                end
                if isscalar(self.intValue)
                    fprintf(1,'\t\t        Integer value: %d\n',self.intValue);
                elseif numel(self.value)<=10
                    fprintf(1,'\t\t        Integer value: [%s]\n',strtrim(sprintf('%d ',self.intValue)));
                elseif numel(self.value)>10
                    fprintf(1,'\t\t        Integer value: [%dx%d %s]\n',size(self.value),class(self.value));
                end
                if ~isempty(self.lowerLimit) && isnumeric(self.lowerLimit)
                    fprintf(1,'\t\t          Lower limit: %.4g\n',self.lowerLimit);
                end
                if ~isempty(self.upperLimit) && isnumeric(self.upperLimit)
                    fprintf(1,'\t\t          Upper limit: %.4g\n',self.upperLimit);
                end

                if ~isempty(self.toIntegerFunction)
                    fprintf(1,'\t\t   toInteger Function: %s\n',func2str(self.toIntegerFunction));
                end
                if ~isempty(self.fromIntegerFunction)
                    fprintf(1,'\t\t fromInteger Function: %s\n',func2str(self.fromIntegerFunction));
                end
            else
                for nn=1:numel(self)
                    self(nn).disp();
                    fprintf(1,'\n');
                end
            end
        end
        
        function s = struct(self)
            %STRUCT Creates a struct from the object
            if isscalar(self)
                s.bits = self.bits;
                s.upperLimit = self.upperLimit;
                s.lowerLimit = self.lowerLimit;
                s.type = self.type;
                s.value = self.value;
                s.units = self.units;
                s.toIntegerFunction = self.toIntegerFunction;
                s.fromIntegerFunction = self.fromIntegerFunction;
            else
                for nn = 1:numel(self)
                    s(nn) = self(nn).struct;
                end
            end
        end
        
        function self =  loadstruct(self,s)
            if isscalar(self)
                self.bits = s.bits;
                self.upperLimit = s.upperLimit;
                self.lowerLimit = s.lowerLimit;
                self.type = s.type;
                self.units = s.units;
                self.toIntegerFunction = s.toIntegerFunction;
                self.fromIntegerFunction = s.fromIntegerFunction;
                self.set(s.value);
            else
                for nn = 1:numel(self)
                    self(nn).loadstruct(s(nn));
                end
            end
        end
        
    end
    
end