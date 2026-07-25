classdef(Abstract) DeviceSubModule < handle
    %DeviceSubModule Abstract class to define common functions
    properties(SetAccess=protected)
        parent
    end

    methods(Abstract)
        setDefaults(self);
        print(self,width);
    end

    methods
        function d = getWriteData(self)
            %GETWRITEDATA Returns the data to write
            %
            %   R = GETWRITEDATA(SELF) Returns the data to be written R for
            %   submodule SELF
            p = properties(self);
            d = [];
            for nn = 1:numel(p)
                if isa(self.(p{nn}),'DeviceRegister') || isa(self.(p{nn}),'DeviceSubModule')
                    d = [d;self.(p{nn}).getWriteData]; %#ok<*AGROW>
                end
            end
        end

        function [d,Rread] = getReadData(self)
            %GETREADDATA Returns addresses and data to write
            %
            %   [d,Rread] = GETREADDATA(SELF) Returns the data to be read d
            %   and associated registers Rread for submodule SELF
            p = properties(self);
            Rread = DeviceRegister.empty;
            d = [];
            for nn = 1:numel(p)
                if isa(self.(p{nn}),'DeviceRegister') || isa(self.(p{nn}),'DeviceSubModule')
                    [dtmp,Rtmp] = self.(p{nn}).getReadData;
                    d = [d;dtmp];
                    tmp = [Rread;Rtmp(:)];
                    Rread = tmp;
                end
            end
        end

        function self = get(self)
            %GET Retrieves parameter values from associated registers
            %
            %   SELF = GET(SELF) Retrieves values for parameters associated
            %   with object SELF
            if numel(self) > 1
                for nn = 1:numel(self)
                    self(nn).get;
                end
            else
                p = properties(self);
                for nn = 1:numel(p)
                    if isa(self.(p{nn}),'DeviceParameter') || isa(self.(p{nn}),'DeviceSubModule')
                        self.(p{nn}).get;
                    end
                end
            end
        end
        function s = struct(self)
            %STRUCT Creates a struct from the object
            if numel(self) > 1
                for nn = 1:numel(self)
                    self(nn).struct;
                end
            else
                p = properties(self);
                for nn = 1:numel(p)
                    if isa(self.(p{nn}),'DeviceSubModule')
                        s.(p{nn}) = self.(p{nn}).struct;
                    end
                end
            end
        end
        
        function self = loadstruct(self,s)
            %LOADSTRUCT Loads a struct into the object
            if numel(self) > 1
                for nn = 1:numel(self)
                    self(nn).loadstruct;
                end
            else
            p = properties(self);
                for nn = 1:numel(p)
                    if isfield(s,p{nn})
                        if isa(self.(p{nn}),'DeviceSubModule')
                            try
                                self.(p{nn}).loadstruct(s.(p{nn}));
                            catch
                                
                            end
                        end
                    end
                end
            end
        end
    end
end