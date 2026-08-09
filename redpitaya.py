"""Module for specifying class for interfacing with device

The assumption here is that the FPGA stores its parameters
in 32-bit registers, where multiple parameters might exist
within a single register, and where a parameter might also
span several registers. 

Available classes:
DeviceRegister -- Represents device registers and provides
    an interface for setting and getting register values
    and for reading/writing the register from the device

DeviceRegisterList -- A list of DeviceRegister instances
    mainly to provide a useful semantic way of accessing
    DeviceRegister methods on multiple registers at once

DeviceParameter -- Represents a parameter on the FPGA, 
    and provides an interface for setting/getting values
    from the associated register, as well as for converting
    the "physical" values (like volts) to the internal FPGA
    representation

DeviceParameterList -- The same as DeviceRegisterList, but for
    DeviceParameter objects

DeviceSubModule -- Represents sub-modules within the FPGA
    design, which can contain their own registers and parameters
"""
import math
import struct
from enum import Enum, Flag
import collections
from abc import ABC, abstractmethod

import libserver

class JumperSetting(Flag):
    """Represents the LV or HV ADC input jumper settings"""
    LV = 0
    HV = 1

class ParamType(Enum):
    """Enumerated class for struct to C-style types"""
    UINT8 = "B"
    INT8 = "b"
    UINT16 = "H"
    INT16 = "h"
    UINT32 = "I"
    INT32 = "i"
    UINT64 = "Q"
    INT64 = "q"

def typecast(value: int, out_type: ParamType) -> int:
    """Casts a value to a particular type
    
    Need to have a function that converts an integer to a particular
    representation and bit width. Pretty sure this isn't the best way
    to do this

    Arguments
    value : int -- Value to convert
    out_type : ParamType -- Output type to cast to

    Returns integer value with the correct representation
    """
    match out_type:
        case ParamType.UINT8 | ParamType.INT8:
            mask = 0xFF
            in_type = ParamType.UINT8
        case ParamType.UINT16 | ParamType.INT16:
            mask = 0xFFFF
            in_type = ParamType.UINT16
        case ParamType.UINT32 | ParamType.INT32:
            mask = 0xFFFFFFFF
            in_type = ParamType.UINT32
        case ParamType.UINT64 | ParamType.INT64:
            mask = 0xFFFFFFFFFFFFFFFF
            in_type = ParamType.UINT64
    s_out = "<{}".format(out_type.value)
    s_in = "<{}".format(in_type.value)
    return struct.unpack(s_out,struct.pack(s_in,value & mask))[0]


class DeviceRegister:
    # The default address for AXI buses on Zynq devices
    DEFAULT_ADDR_OFFSET = 0x40000000
    MAX_ADDR = 0x3fffffff

    def __init__(self, addr: int | str, conn: libserver.ClientConnection, *, read_only: bool=False, offset: int=DEFAULT_ADDR_OFFSET):
        """Creates an instance of DeviceRegister
        
        Arguments:
        addr: int | str -- Register address. If string, must be a hexadecimal number
        conn: libserver.ClientConnection -- client connection object
        **read_only: bool -- Read only (true) or not (false)
        **offset: int -- Address offset, which selects which AXI bus to use
        """
        self.set_addr(addr)
        self._conn = conn
        self.value = 0
        self.read_only = read_only
        self.offset = offset & 0xFFFFFFFF

    def set_addr(self, addr: int | str):
        """Sets the register address with error checking
        
        Arguments:
        addr: int | str -- Register address. If string, must be a hexadecimal number
        """
        if isinstance(addr,str):
            addr = int(addr,16)

        if addr < 0 or addr > self.MAX_ADDR:
            raise ValueError("Address is out of range")
        else:
            self.addr = addr

    def set(self, value: int, bits: list[int]):
        """Sets the register value based on the bit range
        
        Arguments:
        value : int -- the value to set
        bits : list[int] -- a two-element sorted list with the start and stop bits (inclusive)
        """
        tmp = self.value
        if tmp is None:
            tmp = 0

        tmp = tmp & 0xFFFFFFFF
        upper_mask = (1 << bits[1] + 1) - 1
        lower_mask = (1 << bits[0]) - 1
        mask = upper_mask ^ lower_mask

        value = value & 0xFFFFFFFF
        value = value << bits[0]
        tmp = tmp & ~mask
        self.value = (value & mask) | tmp

    def get(self, bits: list[int]) -> int:
        """Returns the value within a given bit range
        
        Arguments:
        bits : list[int] -- a two-element sorted list with the start and stop bits (inclusive)
        """
        mask = 0xFFFFFFFF
        upper_mask = (1 << bits[1] + 1) - 1
        lower_mask = (1 << bits[0]) - 1
        mask = mask & (upper_mask ^ lower_mask)
        return (self.value & mask) >> bits[0]
    
    def write(self):
        """Write value to register on device"""
        data = self.get_write_data()
        if data is not None:
            self._conn.write(data, mode="write")
        return self

    def get_write_data(self) -> list[int]:
        """Returns the list of data to write to device
        
        Data is returned as [address to write to, data to write]
        If register is read-only, then returns an empty list
        """
        if self.read_only:
            data = []
        else:
            data = [self.offset + self.addr, self.value]
        return data

    def get_read_data(self) -> tuple:
        """Returns a tuple of data to read from device
        
        Returns ([address to read], [this register])
        """
        return ([self.offset + self.addr], [self])

    def read(self):
        """Reads data from device"""
        self._conn.write(self.get_read_data()[0], mode="read")
        self.value = self.conn.recv_data[0]

    def print(self, name: str, width: int=20) -> str:
        """Returns am abbreviated string representing the register value
        
        Arguments
        name: str -- The name to use for this register
        width: int -- The width of the name field
        """
        return f"{name:{width}}: {self.value:#010x}\n"

    def __str__(self):
        """Returns a string representation of this object"""
        s = (
            "DeviceRegister object with properties:\n" \
            "   Address:   {0.addr:#010x}\n" \
            "   Value:     {0.value:#010x}\n" \
            "   Read-only: {0.read_only!r}\n" \
            "   Offset:    {0.offset:#010x}"
            ).format(self)
        return s

class DeviceRegisterList(collections.UserList):
    def __init__(self):
        """Creates an instance of the class, representing a list of DeviceRegister objects"""
        self.data = []

    def __setitem__(self, key: int, value: DeviceRegister):
        """Sets the value of the internal list at a given index
        
        Arguments
        key: int -- The key to set
        value: DeviceRegister -- the value to set
        """
        if isinstance(value,DeviceRegister):
            return super().__setitem__(key, value)
        else:
            raise ValueError("Values can only be of type DeviceRegister")

    def append(self, value: DeviceRegister, /):
        """Appends a value to the internal list
        
        Arguments
        value: DeviceRegister -- the value to append
        """
        if isinstance(value,DeviceRegister):
            return super().append(value)
        else:
            raise ValueError("Values can only be of type DeviceRegister")

    def extend(self, value, /):
        """Extends the internal list
        
        Arguments
        value: DeviceRegisterList -- the list to append to the internal list
        """
        if isinstance(value,DeviceRegisterList):
            return super().extend(value.data)
        else:
            raise ValueError("Values can only be of type DeviceRegisterList")

    def insert(self, index: int, value, /):
        """Inserts a new list at the given index
                
        Arguments
        index: int -- the index at which to insert
        value: DeviceRegisterList -- the list to insert
        """
        if isinstance(value,DeviceRegisterList):
            return super().insert(index, value.data)
        else:
            raise ValueError("Values can only be of type DeviceRegisterList")

    def set(self, value: int, bits: list):
        """Sets the register values
        
        Arguments
        value: int -- The integer value to set
        bits: list -- A list of 2-element lists of bits to use for setting the value
        """
        for idx, bbits in enumerate(bits):
            self.data[idx].set(value & 0xFFFFFFFF, bbits)
            value = value >> 32

    def get(self, bits: list) -> int:
        """Returns the value broken across all registers
        
        Arguments
        bits: list -- A list of 2-element lists of bits to use for getting the value

        Returns an integer
        """
        value = 0x0000000000000000
        for idx, bbits in enumerate(bits):
            tmp = self.data[idx].get(bbits)
            value += tmp << (32 * idx)
        return value

    def write(self):
        """Writes all register data to device
        
        This assumes that every register is associated with the same
        ClientConnection object, which it should be
        """
        write_data = self.get_write_data()
        self.data[0]._conn.write(write_data, mode="write")
        return self
    
    def read(self):
        """Reads all register data from device
                
        This assumes that every register is associated with the same
        ClientConnection object, which it should be
        """
        read_data = self.get_read_data()
        self.data[0]._conn.write(read_data[0], mode="read")
        return self

    def get_write_data(self) -> list:
        """Gets all the write data from every register
        
        Returns a list of write data, interleaved as [address to write to, data to write]
        """
        write_data = []
        for item in self.data:
            if not item.read_only:
                write_data.extend(item.get_write_data())
        return write_data

    def get_read_data(self) -> list:
        """Gets all the read data from every register
        
        Returns ([addresses to read], [the registers])
        """
        d = []
        R = []
        for item in self.data:
            tmp = item.get_read_data()
            d.extend(tmp[0])
            R.extend(tmp[1])
        return (d, R)

    def print(self, name, width=20):
        """Returns am abbreviated string representing the registers' values
                
        Arguments
        name: str -- The name to use for these registers
        width: int -- The width of the name fields
        """
        s = ""
        for key, item in enumerate(self.data):
            s += item.print(f"{name} {key}", width)
        return s

    def __str__(self):
        """Returns a string representation of this object"""
        s = ""
        for item in self.data:
            s += str(item) + "\n\n"
        return s


class DeviceParameter:
    def __init__(self, bits: list, regs_in: DeviceRegister | DeviceRegisterList, ptype: ParamType=ParamType.UINT32,
                 *, to_int=None, from_int=None, lower_limit=None, upper_limit=None, units: str=""):
        """Creates an instance of DeviceParameter
        
        Arguments
        bits: list -- The bit range that this parameter is associated with.
            Is either a 2-element list or a list of 2-element lists, where the length
            of the latter list is the same as the number of registers
        regs_in: DeviceRegister | DeviceRegisterList -- Registers associated with this parameter
        ptype: ParamType -- How the parameter value should be translated to an integer representation
        to_int -- Function converting a physical value (like volts) to an integer
        from_int -- Function converting an integer to a physical value (like volts)
        lower_limit -- Lower physical limit for parameter
        upper_limit -- Upper physical limit for parameter
        units: str -- The units of the physical parameter. This is for display purposes only!
        """
        if isinstance(regs_in, (DeviceRegister, DeviceRegisterList)):
            self._regs = regs_in
        else:
            raise TypeError("Register can only be a single DeviceRegister or a DeviceRegisterList")
        
        self.set_bits(bits)

        self.value = 0
        self._uint_value = 0
        self.units = units

        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        if to_int is None:
            self.to_int = lambda x: int(x)
        else:
            self.to_int = to_int
        if from_int is None:
            self.from_int = lambda x: x
        else:
            self.from_int = from_int

        if isinstance(ptype,ParamType):
            self._type = ptype
        else:
            raise ValueError("Type must be of type ParamType")

        if (isinstance(self._regs,DeviceRegisterList) 
                and len(self._regs) > 1 
                and not((self._type == ParamType.UINT64) or (self._type == ParamType.INT64) or (self._type == ParamType.UINT32))):
            raise ValueError("When the number of registers is larger than 1, type must be UINT64, INT64, or UINT32")


    def set_bits(self, bits: list):
        """Sets the bit ranges associated with this parameter
        
        Arguments
        bits: list -- A list of bit ranges. For a single register, this should
            be a 2-element list. For multiple registers, it must be a list of 
            2-element lists
        """
        if isinstance(bits[0],list):
            # Is bits a list of lists?
            if len(self._regs) != len(bits):
                raise ValueError("Number of bit ranges must be the same as the number of registers")
            else:
                for bbits in bits:
                    if len(bbits) > 2:
                        raise ValueError("Bit ranges must be a 2-element list")
                    for bit in bbits:
                        if bit < 0 or bit > 31:
                            raise ValueError("Bits must be in the range [0,31]")
                    bbits.sort()
        else:
            if len(bits) != 2:
                raise ValueError("Bit ranges must be a 2-element list")
            for bit in bits:
                if bit < 0 or bit > 31:
                    raise ValueError("Bits must be in the range [0,31]")
            bits.sort()

        self._bits = bits

    def get_num_bits(self) -> int:
        """Returns the total number of bits used for this parameter"""
        if isinstance(self._bits[0],list):
            return sum((bit[1] - bit[0] + 1 for bit in self._bits))
        else:
            return self._bits[1] - self._bits[0] + 1

    def check(self, v=None, **kwargs):
        """Checks value against limits
        
        Arguments:
        v: Any -- value to check against. If none provided, uses current value
        """
        if v is None:
            v = self.value

        # Check against set limits if not a string
        if not isinstance(v,str):
            if self.lower_limit is not None and v < self.lower_limit:
                raise ValueError("Value {} is less than lower limit of {}".format(v,self.lower_limit))
            if self.upper_limit is not None and v > self.upper_limit:
                raise ValueError("Value {} is greater than upper limit of {}".format(v,self.upper_limit))

        # Check size of integer value against number of bits
        tmp = self.to_int(v,**kwargs)
        if tmp != 0:
            tmp = math.fabs(tmp)
            tmp = math.ceil(math.fabs(math.log2(tmp)))
        if tmp > self.get_num_bits():
            raise ValueError("Value {} requires at least {} bits, {} specified".format(v,tmp,self.get_num_bits()))

        return self

    def set(self, v, **kwargs):
        """Sets the parameter value, computes integer value, and changes register
        
        Arguments
        v: Any -- the value to set

        Returns itself
        """

        self.check(v)
        self.value = v
        self._uint_value = int(self.to_int(self.value))
        if self._type is ParamType.UINT64 or self._type is ParamType.INT64:
            self._uint_value = self._uint_value & 0xFFFFFFFFFFFFFFFF
        else:
            self._uint_value = self._uint_value & 0xFFFFFFFF

        self._regs.set(self._uint_value,self._bits)
        return self

    def get(self, **kwargs):
        """Returns the parameter value from the register"""
        self._uint_value = typecast(self._regs.get(self._bits), self._type)
        self.value = self.from_int(self._uint_value)
        return self.value

    def read(self, **kwargs):
        """Reads data from server and stores new parameter value
        
        Returns the instance"""
        self._regs.read()
        return self

    def write(self):
        """Writes parameter value to register and then to server"""
        self._regs.write()
        return self

    def print(self, name: str, width: int=20, formatstr: str="d"):
        """Returns a string giving a summary of the parameter value
        
        Arguments
        name: str -- The name to use
        width: int -- The width of the printed name field
        formatstr: str -- The format specifier for the parameter value
        """
        return f"{name:{width}}: {self.value:{formatstr}} {self.units}\n"

    def __str__(self):
        s = (
            "DeviceParameter object with properties:\n" \
            "   Bit range:      {0._bits}\n" \
            "   Type:           {0._type.name}\n" \
            "   Physical value: {0.value} {0.units}\n" \
            "   UINT value:     0x{0._uint_value:0x}\n" \
            "   Limits:         [{0.lower_limit}, {0.upper_limit}]"
            ).format(self)
        return s
            
        
class DeviceParameterList(collections.UserList):

    def __init__(self):
        """Creates an instance of the class, representing a list of DeviceParameter objects"""
        self.data = []

    def __setitem__(self, key, value):
        """Sets the value of the internal list at a given index
                
        Arguments
        key: int -- The key to set
        value: Deviceparameter -- the value to set
        """
        if isinstance(value,DeviceParameter):
            return super().__setitem__(key,value)
        else:
            raise ValueError("Values can only be of type DeviceParameter")

    def append(self, value, /):
        """Appends a value to the internal list
        
        Arguments
        value: DeviceParameter -- the value to append
        """
        if isinstance(value,DeviceParameter):
            return super().append(value)
        else:
            raise ValueError("Values can only be of type DeviceParameter")

    def extend(self, value, /):
        """Extends the internal list
        
        Arguments
        value: DeviceParameterList -- the list to append to the internal list
        """
        if isinstance(value,DeviceParameterList):
            return super().extend(value.data)
        else:
            raise ValueError("Values can only be of type DeviceParameterList")

    def insert(self, index: int, value, /):
        """Inserts a new list at the given index
        
        Arguments
        index: int -- the index at which to insert
        value: DeviceParameterList -- the list to insert
        """
        if isinstance(value,DeviceParameterList):
            return super().insert(index, value.data)
        else:
            raise ValueError("Values can only be of type DeviceParameterList")

    def set(self, values, /):
        """Sets the register values
        
        Arguments
        value -- The values to set. If a single value, the value is echoed across all parameters
        """
        if not isinstance(values,list):
            values = [values] * len(self.data)
        elif len(values) != len(self):
            raise IndexError("Length of values different from length of this parameter list")

        for k, v in enumerate(values):
            self.data[k].set(v)

    def write(self):
        """Writes all parameters to device"""
        for item in self.data:
            item.write()

    def get(self) -> list:
        """Retrieves parameter values
        
        Returns a list of parameter values
        """
        r = []
        for item in self.data:
            r.append(item.get())
        return r

    def read(self):
        """Reads parameter values from device"""
        for item in self.data:
            item.read()

    def print(self, name, width=20, formatstr="d"):
        """Returns a string giving a summary of the parameter values
        
        Arguments
        name: str -- The name to use
        width: int -- The width of the printed name field
        formatstr: str -- The format specifier for the parameter value
        """
        s = ""
        for key, item in enumerate(self.data):
            s += item.print(f"{name} {key}", width, formatstr)
        return s

    def __str__(self):
        s = ""
        for item in self.data:
            s += str(item) + "\n\n"
        return s


class DeviceSubModule(ABC):

    @abstractmethod
    def set_defaults(self):
        """Set default values"""
        pass

    @abstractmethod
    def print(self, width):
        """Prints information about the sub module"""
        pass

    def get_write_data(self) -> list:
        """Generates data for writing to the device
        
        Returns a list of interleaved [address to write to, data to write]
        """
        d = []
        for value in self.__dict__.values():
            if hasattr(value,"get_write_data"):
                d.extend(value.get_write_data())
        return d

    def get_read_data(self) -> tuple:
        """Returns a set of data for reading from device
        
        Returns a tuple of ([address to read from], [associated registers/device sub modules])
        """
        d = []
        R = []
        for value in self.__dict__.values():
            if hasattr(value,"get_read_data"):
                tmp = value.get_read_data()
                d.extend(tmp[0])
                R.extend(tmp[1])
        return (d, R)

    def get(self):
        """Converts register values to actual parameters"""
        for value in self.__dict__.values():
            if isinstance(value,(DeviceParameter, DeviceParameterList, DeviceSubModule)):
                value.get()
