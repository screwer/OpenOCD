'''
OpenOCD telnet-protocol python wrapper.

Written by Artamonov Dmitry <screwer@gmail.com>

This program is free software. It comes without any warranty, to the extent permitted by applicable law.
You can redistribute it and/or modify it under the terms of the WTFPL, Version 2, as published by Sam Hocevar.
See http://www.wtfpl.net/ for more details
'''
#-------------------------------------------------------------------------------------------------


import telnetlib
import re
import struct

#-------------------------------------------------------------------------------------------------

def write_raw_sequence(tn, seq):
    sock = tn.get_socket()
    if sock is not None:
        sock.send(seq)

#-------------------------------------------------------------------------------------------------

class OpenOCD:
    def __init__(self, Host="localhost", Port=4444):
        self.tn = telnetlib.Telnet(Host, Port)
        #write_raw_sequence(self.tn, telnetlib.IAC + telnetlib.WILL + telnetlib.ECHO)
        self.Readout()

    #
    # Communication functions
    #
    def Readout(self):
        s = ''
        Lines = []
        while True:
            s += self.tn.read_some()
            l = s.splitlines()
            if len(l) > 1:
                for s in l[:-1]:
                    if len(s) > 0:
                        Lines.append(s)
                s = l[-1]
            if s == '> ':
                return Lines

    def Exec(self, Cmd, *args):
        Text = Cmd
        for arg in args:
            if arg:
                Text += ' ' + arg
        Text += '\n'
        self.tn.write(Text)
        return self.Readout()


    #
    # Static Helpers
    #
    @staticmethod
    def ValueHex(n):
        return "0x%x" % n if isinstance(n, (int, long)) else str(n)

    @staticmethod
    def ValueHex32(n):
        return "0x%08x" % n if isinstance(n, (int, long)) else str(n)

    @staticmethod
    def ValueDec(n):
        return "%d" % n if isinstance(n, (int, long)) else str(n)

    @staticmethod
    def ImageFormat(Bin, IHex, Elf, S19):
        FOpt = int(Bin) + int(IHex) + int(Elf) + int(S19)
        #if 0 == FOpt:
        #    raise ValueError('Wrong format option (not specified)')

        if FOpt > 1:
            raise ValueError('Wrong format option (multiple specified)')

        Opt = 'bin' if Bin else 'ihex' if IHex else 'elf' if Elf else 's19' if S19 else None
        return Opt

    @staticmethod
    def ToRWA(Read, Write, Access):
        return 0 if Read else 1 if Write else 2

    @staticmethod
    def FromRWA(Value):
        return 'r' if 0 == Value else 'w' if 1 == Value else 'a'

    @staticmethod
    def HexView(Data, Addr, Prefix=''):
        Size = len(Data)
        n = -(Addr & 0x0F)
        Addr = Addr & (~0x0F)
        while n < Size:        
            Bytes = ''
            Text = ''

            for i in range(0, 16):
                Byte = None if n < 0 or n >= Size else ord(Data[n:n+1])
                if Byte is not None:
                    Bytes += '%02x' % Byte
                    Text += chr(Byte) if Byte > 32 and Byte < 128 else '.'
                else:
                    Bytes += '  '
                    Text += ' '
            
                if i == 7:
                    Bytes += ' | '
                    Text += ' '
                else:
                    Bytes += ' '
                n += 1

            Msg = '%s0x%08x %s%s' % (Prefix, Addr, Bytes, Text)
            Addr += 0x10
            print(Msg)

    #
    # Resume the target at its current code position, or the optional address if it is provided. OpenOCD will wait 5 seconds for the target to resume.
    #
    def Resume(self):
        return self.Exec('resume')

    #
    # Single-step the target at its current code position, or the optional address if it is provided.
    #
    def Step(self, Addr=None):
        AddrHex = None if Addr is None else OpenOCD.ValueHex(Addr)
        return self.Exec('step', AddrHex)

    #
    # The halt command first sends a halt request to the target, wait up to MS milliseconds, for the target to halt (and enter debug mode).
    # Using 0 as the MS parameter prevents OpenOCD from waiting.
    #
    def Halt(self, MS=100):
        return self.Exec('halt', ValueDec(MS))

    #
    # Perform as hard a reset as possible, using SRST if possible. All defined targets will be reset, and target events will fire during the reset sequence.
    #
    # The optional parameter specifies what should happen after the reset. If there is no parameter, a reset run is executed. The other options will not work on all systems.
    #   'Run'  - Let the target run
    #   'Halt' - Immediately halt the target
    #   'Init' - Immediately halt the target, and execute the reset-init script
    #
    def Reset(self, Run = False, Halt = False, Init = False):
        if int(Run) + int(Halt) + int(Init) > 1:
            raise ValueError('Wrong reset option (multiple specified)')

        Opt = 'run' if Run else 'halt' if Halt else 'init' if Init else None
        return self.Exec('reset', Opt)

    #
    # Requesting target halt and executing a soft reset. This is often used when a target cannot be reset and halted.
    # The target, after reset is released begins to execute code.
    # OpenOCD attempts to stop the CPU and then sets the program counter back to the reset vector.
    # Unfortunately the code that was executed may have left the hardware in an unknown state.
    #
    def SoftResetHalt(self):
        return self.Exec('soft_reset_halt')

    #
    # Registers handling
    #
    class RegOCD:
        def __init__(self, OCD, Name, Force=False):
            self.OCD = OCD
            self.Name = str(Name)
            self.Force = Force # not supported yet

        #
        # Read register value
        #
        def Read(self):
            r = self.OCD.Exec('reg', self.Name)
            if len(r) < 2:
                return None

            w = r[1].split()
            if w[0] != self.Name:
                return None
            return long(w[2], 16)

        #
        # Write value to the register
        #
        def Write(self, Value):
            if not Name:
                raise ValueError('Cannot write to all registers')

            r = self.OCD.Exec('reg', self.Name, OpenOCD.ValueHex(Value))
            pass
    
    #
    # Access a single register by number or by its name.
    # The target must generally be halted before access to CPU core registers is allowed.
    # Depending on the hardware, some other registers may be accessible while the target is running.
    #
    def Reg(self, Name):
        return self.RegOCD(self, Name)

    #
    # Enum available registers (empty 'reg' command wrapper)
    # Returns register array or by-name dictionary, depending on Dict parameter.
    #
    def Regs(self, Dict=False):

        class RegInfo:
            def __init__(self, Index, Name, Width):
                self.Index = Index
                self.Name = Name
                self.Width = Width

        All = {} if Dict else []
        reReg = re.compile('\\((?P<index>\\d+)\\)\\s+(?P<name>\\w+)\\s+\\(/(?P<width>\\d+)\\)')
        for s in self.Exec('reg'):
            r = reReg.match(s)
            if r:
                Index = r.group('index')
                Name  = r.group('name')
                Width = long(r.group('width'))
                Info = RegInfo(Index, Name, Width)
                if Dict:
                    All[Info.Name] = Info
                else:
                    All.append(Info)
        return All

    #
    # Memory reading
    #
    def ReadMem_(self, Verb, Addr):
        AddrHex = OpenOCD.ValueHex32(Addr)
        r = self.Exec(Verb, AddrHex)
        if len(r) < 2:
            return None
    
        w = r[1].split()
        if w[0] != AddrHex + ':':
            return None
        return long(w[1], 16)

    def ReadMem32(self, Addr):
        return self.ReadMem_('mdw', Addr)

    def ReadMem16(self, Addr):
        return self.ReadMem_('mdh', Addr)
    
    def ReadMem8(self, Addr):
        return self.ReadMem_('mdb', Addr)

    def ReadMem(self, Addr, Size):
        Data = ''
        while 0 != Size:
            BlockSize = min(4, Size)
            if 0 != (Addr & 1):
                BlockSize = 1
            elif 0 != (Addr & 2):
                BlockSize = min(2, Size)

            if 4 == BlockSize:
                Value = self.ReadMem32(Addr)
                Data += struct.pack('<L', Value)
            elif 2 == BlockSize:
                Value = self.ReadMem16(Addr)
                Data += struct.pack('<H', Value)
            else:
                Value = self.ReadMem8(Addr)
                Data += struct.pack('<B', Value)
            Addr += BlockSize
            Size -= BlockSize
        return Data

    #
    # Memory writing
    #
    def WriteMem_(self, Verb, Addr, Value):
        AddrHex = OpenOCD.ValueHex(Addr)
        ValueHex = OpenOCD.ValueHex(Value)
        r = self.Exec(Verb, AddrHex, ValueHex)

    def WriteMem32(self, Addr, Value):
        self.WriteMem_('mww', Addr, Value)

    def WriteMem16(self, Addr, Value):
        self.WriteMem_('mwh', Addr, Value)

    def WriteMem8(self, Addr, Value):
        self.WriteMem_('mwb', Addr, Value)

    def WriteMem(self, Addr, Data):
        Offset = 0
        Size = len(Data)
        while Offset < Size:
            Remainder = (Size - Offset)
            BlockSize = min(4, Remainder)
            if 0 != (Addr & 1):
                BlockSize = 1
            elif 0 != (Addr & 2):
                BlockSize = min(2, Remainder)

            if 4 == BlockSize:
                Value, = struct.unpack_from('<L', Data, Offset)
                self.WriteMem32(Addr, Value)
            elif 2 == BlockSize:
                Value, = struct.unpack_from('<H', Data, Offset)
                self.WriteMem16(Addr, Value)
            else:
                Value, = struct.unpack_from('<B', Data, Offset)
                self.WriteMem8(Addr, Value)
            Addr += BlockSize
            Offset += BlockSize

    #
    # Breakpoints
    #
    class BpOCD:
        def __init__(self, OCD, Addr, Len, HW=False):
            self.OCD = OCD
            self.Addr = Addr
            self.Len = Len
            self.HW = HW
            self.Enabled = False
        
        def Enable(self):
            AddrHex = OpenOCD.ValueHex(self.Addr)
            LenDec = OpenOCD.ValueDec(self.Len)
            r = self.OCD.Exec('bp', AddrHex, LenDec, 'hw' if self.HW else None)
            self.Enabled = True # TODO: check Exec result
            return r

        def Disable(self):
            AddrHex = OpenOCD.ValueHex(self.Addr)
            r = self.OCD.Exec('rbp', AddrHex)
            self.Enabled = False # TODO: check Exec result
            return r

    def BP(self, Addr, Len=2, HW=True, Enable=False):
        bp = self.BpOCD(self, Addr, Len, HW)
        if Enable:
            bp.Enable()
        return bp
    
    def BPs(self):
        All = []
        reBP = re.compile('Breakpoint.*: 0x(?P<addr>[0-9a-fA-F]+), 0x(?P<size>[0-9a-fA-F]+).*')
        for s in self.Exec('bp'):
            r = reBP.match(s)
            if r:
                Addr = long(r.group('addr'), 16)
                Size = long(r.group('size'), 16)
                bp = self.BpOCD(self, Addr, Size)
                All.append(bp)
        return All

    def RemoveBPs(self):
        for bp in self.BPs():
            bp.Disable()

    #
    # Watchpoints
    #
    class WpOCD:
        def __init__(self, OCD, Addr, Len, RWA=None, Value=None, Mask=None):
            self.OCD = OCD
            self.Addr = Addr
            self.Len = Len
            self.RWA = RWA
            self.Value = Value
            self.Mask = Mask if Mask is not None else 0xffffffff if Value is not None else None

        def Enable(self):
            AddrHex = OpenOCD.ValueHex(self.Addr)
            LenDec  = OpenOCD.ValueDec(self.Len)
            ValueHex = None if self.Value is None else OpenOCD.ValueHex(self.Value)
            MaskHex  = None if self.Mask is None else OpenOCD.ValueHex(self.Mask)
            r = self.OCD.Exec('wp', AddrHex, LenDec, OpenOCD.FromRWA(self.RWA), ValueHex, MaskHex)
            if len(r) > 2:
                raise ValueError(r[1])

        def Disable(self):
            AddrHex = OpenOCD.ValueHex(self.Addr)
            return self.OCD.Exec('rwp', AddrHex)

    def WP(self, Addr, Len=4, Read=None, Write=None, Access=None, Value=None, Mask=None, Enable=False):
        RWA = OpenOCD.ToRWA(Read, Write, Access)
        wp = self.WpOCD(self, Addr, Len, RWA, Value, Mask)
        if Enable:
            wp.Enable()
        return wp

    def WPs(self):
        All = []
        reWP = re.compile('address: 0x(?P<addr>[0-9a-fA-F]+), len: 0x(?P<len>[0-9a-fA-F]+), r/w/a: (?P<rwa>\\d), value: 0x(?P<value>[0-9a-fA-F]+), mask: 0x(?P<mask>[0-9a-fA-F]+)')
        for s in self.Exec('wp'):
            r = reWP.match(s)
            if r:
                Addr  = long(r.group('addr'), 16)
                Len   = long(r.group('len'))
                RWA   = long(r.group('rwa'))
                Value = long(r.group('value'), 16)
                Mask  = long(r.group('mask'), 16)

                wp = self.WpOCD(self, Addr, Len, RWA, Value, Mask)
                All.append(wp)
        return All

        return All

    def RemoveWPs(self):
        for wp in self.WPs():
            wp.Disable()


    #
    # Image handling
    #
    class ImageOCD:
        def __init__(self, OCD):
            self.OCD = OCD
        #
        # Dump size bytes of target memory starting at address to the binary file named filename.
        #
        def Dump(self, Filename, Addr, Size):
            FileNameQ = '"%s"' % Filename
            AddrHex = OpenOCD.ValueHex(Addr)
            SizeHex = OpenOCD.ValueHex(Size)
            return self.OCD.Exec('dump_image', FileNameQ, AddrHex, SizeHex)

        #
        # If no parametes specified - Loads an image stored in memory by preceeded FastLoad to the current target.
        # Otherwise storing the image in memory and uploading the image to the target can be a way to upload e.g. multiple debug sessions when the binary does not change. 
        #
        def FastLoad(self, Filename=None, Addr=None, Bin=False, IHex=False, Elf=False, S19=False):
            if not Filename and not Addr:
                return self.OCD.Exec('fast_load')

            FileNameQ = '"%s"' % Filename
            AddrHex = OpenOCD.ValueHex(Addr)
            Format = OpenOCD.ImageFormat(Bin, IHex, Elf, S19)
            return self.OCD.Exec('fast_load_image', FileNameQ, AddrHex, Format)

        #
        # Load image from file filename to target memory offset by address from its load address.
        # The file format may optionally be specified (bin, ihex, elf, or s19).
        #
        # In addition the following arguments may be specifed:
        #   MinAddr - ignore data below min_addr (this is w.r.t. to the target's load address + address)
        #   MaxLength - maximum number of bytes to load.
        #
        def Load(self, Filename, Addr, Bin=False, IHex=False, Elf=False, S19=False, MinAddr=None, MaxLength=None):
            FileNameQ = '"%s"' % Filename
            AddrHex = OpenOCD.ValueHex(Addr)
            Format = OpenOCD.ImageFormat(Bin, IHex, Elf, S19)
            MinAddrHex = None if MinAddr is None else OpenOCD.ValueHex(MinAddr)
            MaxLengthHex = None if MaxLength is None else OpenOCD.ValueHex(MaxLength)
            return self.OCD.Exec('load_image', FileNameQ, AddrHex, Format, MinAddrHex, MaxLengthHex)

        #
        # Displays image section sizes and addresses as if filename were loaded into target memory starting at address (defaults to zero).
        # #The file format may optionally be specified (bin, ihex, or elf)
        #
        def Test(self, Filename, Addr=None, Bin=False, IHex=False, Elf=False, S19=False, MinAddr=None):
            FileNameQ = '"%s"' % Filename
            AddrHex = None if Addr is None else OpenOCD.ValueHex(Addr)
            Format = OpenOCD.ImageFormat(Bin, IHex, Elf, S19)
            return self.OCD.Exec('test_image', FileNameQ, AddrHex, Format)

        #
        # Verify filename against target memory starting at address.
        # The file format may optionally be specified (bin, ihex, or elf)
        # This will first attempt a comparison using a CRC checksum, if this fails it will try a binary compare.
        #
        def Verify(self, Filename, Addr, Bin=False, IHex=False, Elf=False, S19=False, MinAddr=None):
            FileNameQ = '"%s"' % Filename
            AddrHex = OpenOCD.ValueHex(Addr)
            Format = OpenOCD.ImageFormat(Bin, IHex, Elf, S19)
            return self.OCD.Exec('verify_image', FileNameQ, AddrHex, Format)

        #
        # Verify filename against target memory starting at address.
        # The file format may optionally be specified (bin, ihex, or elf)
        # This perform a comparison using a CRC checksum only
        #
        def VerifyChecksum(self, Filename, Addr, Bin=False, IHex=False, Elf=False, S19=False, MinAddr=None):
            FileNameQ = '"%s"' % Filename
            AddrHex = OpenOCD.ValueHex(Addr)
            Format = OpenOCD.ImageFormat(Bin, IHex, Elf, S19)
            return self.OCD.Exec('verify_image_checksum', FileNameQ, AddrHex, Format)

    def Image(self):
        return self.ImageOCD(self)

    #
    # NOR flash command group (command valid any time)
    #
    class FlashOCD:
        def __init__(self, OCD):
            self.OCD = OCD

        #
        # Display table with information about flash banks. (command valid any time)
        #
        def Banks():
            pass

        #
        # Erase flash sectors starting at address and continuing for length bytes.
        # If 'pad' is specified, data outside that range may also be erased:
        # the start address may be decreased, and length increased, so that all of the first and last sectors are erased.
        # If 'unlock' is specified, then the flash is unprotected before erasing. 
        #
        def EraseAddress(Addr, Length, Pad=None, Unlock=False):
            pass

        #
        # Check erase state of all blocks in a flash bank.
        #
        def EraseCheck(BankId):
            pass

        #
        # Erase a range of sectors in a flash bank.
        #
        def EraseSector(BankId, FirstSectorNum, LastSectorNum):
            pass

        #
        # Fill N bytes with 8-bit value, starting at word address. (Noautoerase.)
        #
        def Fill8(Addr, Value8, N):
            pass

        #
        # Fill N halfwords with 16-bit value, starting at word address. (Noautoerase.)
        #
        def Fill16(Addr, Value16, N):
            pass

        #
        # Fill N words with 16-bit value, starting at word address. (Noautoerase.)
        #
        def Fill32(Addr, Value32, N):
            pass

        #
        # Returns information about a flash bank.
        #
        def Info(BankId):
            pass

        #
        # Returns a list of details about the flash banks. (command valid anytime)
        #
        def List():
            pass

        #
        # Set default flash padded value
        #
        def SetPadValue(BankId, Value):
            pass

        #
        # Identify a flash bank.
        #
        def Probe(BankId):
            pass

        #
        # Turn protection on or off for a range of protection blocks or sectors in a given flash bank.
        # See 'Info' output for a list of blocks.
        #
        def Protect(BankId, FirstBlock, LastBlock=None, On=False):
            pass

        #
        # Read binary data from flash bank to file, starting at specified byte offset from the beginning of the bank.
        #
        def ReadBank(BankId, Filename, Offset, Length):
            pass
        
        #
        # Read binary data from flash bank and file, starting at specified byte offset from the beginning of the bank.
        # Compare the contents.
        #
        def VerifyBank(BankId, Filename, Offset, Length):
            pass

        #
        # Write binary data from file to flash bank, starting at specified byte offset from the beginning of the bank.
        #
        def WriteBank(BankId, Filename, Offset):
            pass

        def WriteImage(Filename, Erase=False, Unlock=False, Offset=None, Bin=False, IHex=False, Elf=False, S19=False):
            pass

    def Flash():
        return FlashOCD(self)

#-------------------------------------------------------------------------------------------------

