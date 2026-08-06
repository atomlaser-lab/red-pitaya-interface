import math
import struct
from enum import Enum
import collections
from abc import ABC, abstractmethod

import libserver

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

def typecast(value : int, out_type : ParamType):
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
    DEFAULT_ADDR_OFFSET = 0x40000000
    MAX_ADDR = 0x3fffffff

    def __init__(self, addr: int | str, conn : libserver.ClientConnection, *, read_only: bool=False, offset : int=DEFAULT_ADDR_OFFSET):
        """Creates an instance of DeviceRegister
        
        Arguments:
        addr : int | str -- Register address. If string, must be a hexadecimal number
        conn: libserver.ClientConnection -- client connection object
        **read_only (bool) -- Read only (true) or not (false)
        **offset (int) -- Address offset, which selects which AXI bus to use
        """
        self.set_addr(addr)
        self.conn = conn
        self.value = 0
        self.read_only = read_only
        self.offset = offset

    def set_addr(self, addr: int | str):
        """Sets the register address with error checking
        
        Arguments:
        addr : int | str -- Register address. If string, must be a hexadecimal number
        """
        if isinstance(addr,str):
            addr = int(addr,16)

        if addr < 0 or addr > self.MAX_ADDR:
            raise ValueError("Address is out of range")
        else:
            self.addr = addr

    def set(self, value : int, bits : list[int]):
        """Sets the register value based on the bit range
        
        Arguments:
        value : int -- the value to set
        bits : list[int] -- a two-element list with the start and stop bits (inclusive)
        """
        tmp = self.value
        if tmp is None:
            tmp = 0
        # tmp = typecast(tmp & 0xFFFFFFFF,ParamType.UINT32)
        tmp = tmp & 0xFFFFFFFF
        upper_mask = (1 << bits[1] + 1) - 1
        lower_mask = (1 << bits[0]) - 1
        mask = upper_mask ^ lower_mask
        # value = typecast(value & 0xFFFFFFFF,ParamType.UINT32)
        value = value & 0xFFFFFFFF
        value = value << bits[0]
        tmp = tmp & ~mask
        self.value = (value & mask) | tmp

    def get(self,bits : list[int]) -> int:
        """Returns the value within a given bit range
        
        Arguments:
        bits : list[int] -- a two-element list with the start and stop bits (inclusive)
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
            self.conn.write(data, mode="write")
        return self

    def get_write_data(self) -> list[int]:
        """Returns the list of data to write to device"""
        if self.read_only:
            data = None
        else:
            data = [self.offset + self.addr, self.value]
        return data

    def read(self):
        """Reads data from device"""
        self.conn.write(self.offset + self.addr, mode="read")
        self.value = self.conn.recv_data

    def __str__(self):
        s = (
            "DeviceRegister object with properties:\n" \
            "   Address: 0x{0.addr:08x}\n" \
            "   Value: 0x{0.value:08x}\n" \
            "   Read-only: {0.read_only!r}\n" \
            "   Offset: 0x{0.offset:08x}"
            ).format(self)
        return s

class DeviceRegisterList(collections.UserList):
    def __init__(self):
        self.data = []

    def __setitem__(self, key, value):
        if isinstance(value,DeviceRegister):
            return super().__setitem__(key, value)
        else:
            raise ValueError("Values can only be of type DeviceRegister")

    def append(self, value, /):
        if isinstance(value,DeviceRegister):
            return super().append(value)
        else:
            raise ValueError("Values can only be of type DeviceRegister")

    def extend(self, value, /):
        if isinstance(value,DeviceRegisterList):
            return super().extend(value)
        else:
            raise ValueError("Values can only be of type DeviceRegisterList")

    def insert(self, index, value, /):
        if isinstance(value,DeviceRegisterList):
            return super().insert(index, value)
        else:
            raise ValueError("Values can only be of type DeviceRegisterList")

    def set(self, value : int, bits : list):
        for idx, bbits in enumerate(bits):
            self.data[idx].set(value & 0xFFFFFFFF, bbits)
            value = value >> 32

    def get(self, bits : list):
        value = 0x0000000000000000
        for idx, bbits in enumerate(bits):
            tmp = self.data[idx].get(bbits)
            value += tmp << (32 * idx)
        return value

    def write(self):
        write_data = self.get_write_data()
        self.data[0].conn.write(write_data, mode="write")
        return self
    
    def read(self):
        read_data = self.get_read_data()
        self.data[0].conn.write(read_data, mode="read")
        return self

    def get_write_data(self):
        write_data = []
        for item in self.data:
            if not item.read_only:
                write_data.extend(item.get_write_data())
        return write_data

    def get_read_data(self):
        read_data = []
        for item in self.data:
            read_data.extend(item.get_read_data())
        return read_data


class DeviceParameter:

    def __init__(self, bits : list, regs_in : DeviceRegister, ptype : ParamType=ParamType.UINT32,
                 *, to_int=None, from_int=None, lower_limit=None, upper_limit=None):
        if isinstance(regs_in, DeviceRegister) or isinstance(regs_in, DeviceRegisterList):
            self._regs = regs_in
        else:
            raise TypeError("Register can only be a single DeviceRegister or a DeviceRegisterList")
        
        self.set_bits(bits)

        self.value = 0
        self._uint_value = 0

        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        if to_int is None:
            self.to_int = lambda x: int(x)
        if from_int is None:
            self.from_int = lambda x: x

        if isinstance(ptype,ParamType):
            self._type = ptype
        else:
            raise ValueError("Type must be of type ParamType")

        if isinstance(self._regs,DeviceRegisterList) and len(self._regs) > 1 and not((self._type == ParamType.UINT64) or (self._type == ParamType.INT64) or (self._type == ParamType.UINT32)):
            raise ValueError("When the number of registers is larger than 1, type must be UINT64, INT64, or UINT32")


    def set_bits(self,bits : list):
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

    def check(self,v=None,**kwargs):
        """Checks value against limits
        
        Arguments:
        v : Any -- value to check against. If none provided, uses current value
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

    def set(self,v,**kwargs):
        """Sets the parameter value, computes integer value, and changes register"""

        self.check(v)
        self.value = v
        if self._type is ParamType.UINT64 or self._type is ParamType.INT64:
            self._uint_value = self.value & 0xFFFFFFFFFFFFFFFF
        else:
            self._uint_value = self.value & 0xFFFFFFFF
        # self._uint_value = typecast(self.to_int(v),self._type)

        self._regs.set(self._uint_value,self._bits)

    def get(self,**kwargs):
        """Returns the parameter value from the register"""
        self._uint_value = typecast(self._regs.get(self._bits), self._type)
        self.value = self.from_int(self._uint_value)
        return self.value

    def read(self, **kwargs):
        """Reads data from server and stores new parameter value"""
        self._regs.read()
        self.get(**kwargs)

    def write(self):
        """Writes parameter value to register and then to server"""
        self._regs.write()

    def __str__(self):
        s = (
            "DeviceParameter object with properties:\n" \
            "   Bit range: {0._bits}\n" \
            "   Type: {0._type.name}\n" \
            "   Physical value: {0.value}\n" \
            "   UINT value: 0x{0._uint_value:0x}\n" \
            "   Limits: [{0.lower_limit}, {0.upper_limit}]"
            ).format(self)
        return s
            
        
class DeviceParameterList(collections.UserList):

    def __init__(self):
        self.data = []

    def __setitem__(self, key, value):
        if isinstance(value,DeviceParameter):
            return super().__setitem__(key,value)
        else:
            raise ValueError("Values can only be of type DeviceParameter")

    def append(self, value, /):
        if isinstance(value,DeviceParameter):
            return super().append(value)
        else:
            raise ValueError("Values can only be of type DeviceParameter")

    def extend(self, value, /):
        if isinstance(value,DeviceParameterList):
            return super().extend(value.data)
        else:
            raise ValueError("Values can only be of type DeviceParameterList")

    def insert(self, index, value, /):
        if isinstance(value,DeviceParameterList):
            return super().insert(value.data)
        else:
            raise ValueError("Values can only be of type DeviceParameterList")

    def set(self, values, /):
        if not isinstance(values,list):
            values = [values] * len(self.data)
        elif len(values) != len(self):
            raise IndexError("Length of values different from length of this parameter list")

        for k, v in enumerate(values):
            self.data[k].set(v)

    def write(self):
        for item in self.data:
            item.write()

    def get(self):
        r = []
        for item in self.data:
            r.append(item.get())
        return r

    def read(self):
        for item in self.data:
            item.read()

    def __str__(self):
        s = ""
        for item in self.data:
            s += str(item) + "\n\n"
        return s


class DeviceSubModule(ABC):

    # def __init__(self):
    #     self._parent = None

    @abstractmethod
    def set_defaults(self):
        """Set default values"""
        pass

    def get_write_data(self):
        # p = self.__dict__
        d = []
        for value in self.__dict__.values():
            if hasattr(value,"get_write_data"):
                d.extend(value.get_write_data())
        return d

    def get_read_data(self) -> tuple:
        d = []
        R = []
        for value in self.__dict__.values():
            if hasattr(value,"get_read_data"):
                d.append(value.get_read_data())
                R.append(value)
        return (d, R)

    def get(self):
        for value in self.__dict__.values():
            if hasattr(value,"get"):
                value.get()
