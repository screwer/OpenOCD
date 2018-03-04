'''
CMSIS definitions data format parsers.

Written by Artamonov Dmitry <screwer@gmail.com>

This program is free software. It comes without any warranty, to the extent permitted by applicable law.
You can redistribute it and/or modify it under the terms of the WTFPL, Version 2, as published by Sam Hocevar.
See http://www.wtfpl.net/ for more details
'''

from ctypes import *

#-------------------------------------------------------------------------------------------------

REG_CRC_BASE    = 0x40023000
REG_CRC_DR      = REG_CRC_BASE

#-------------------------------------------------------------------------------------------------
#
# DMA_InitTypeDef
#

DMA_DIR_PeripheralDST           = 0x00000010
DMA_DIR_PeripheralSRC           = 0x00000000

DMA_PeripheralInc_Enable        = 0x00000040
DMA_PeripheralInc_Disable       = 0x00000000

DMA_MemoryInc_Enable            = 0x00000080
DMA_MemoryInc_Disable           = 0x00000000

DMA_PeripheralDataSize_Byte     = 0x00000000
DMA_PeripheralDataSize_HalfWord = 0x00000100
DMA_PeripheralDataSize_Word     = 0x00000200

DMA_MemoryDataSize_Byte         = 0x00000000
DMA_MemoryDataSize_HalfWord     = 0x00000400
DMA_MemoryDataSize_Word         = 0x00000800

DMA_Mode_Circular               = 0x00000020
DMA_Mode_Normal                 = 0x00000000

DMA_M2M_Enable                  = 0x00004000
DMA_M2M_Disable                 = 0x00000000


class DMA_InitTypeDef(Structure):
    _fields_ = [
        ('PeripheralBaseAddr',  c_ulong),
        ('MemoryBaseAddr',      c_ulong),
        ('DIR',                 c_ulong),
        ('BufferSize',          c_ulong),
        ('PeripheralInc',       c_ulong),
        ('MemoryInc',           c_ulong),
        ('PeripheralDataSize',  c_ulong),
        ('MemoryDataSize',      c_ulong),
        ('Mode',                c_ulong),
        ('Priority',            c_ulong),
        ('M2M',                 c_ulong),
    ]

#-------------------------------------------------------------------------------------------------

def ReadStruct(OCD, Addr, Struct):
    Size = sizeof(Struct)
    Raw = OCD.ReadMem(Addr, Size)
    memmove(addressof(Struct), Raw, Size)    

#-------------------------------------------------------------------------------------------------

def DMA_GetSize_Memory(DmaInit):
    Inc = 1 if DMA_MemoryDataSize_Byte == DmaInit.MemoryDataSize else 2 if DMA_MemoryDataSize_HalfWord == DmaInit.MemoryDataSize else 4
    Size = (DmaInit.BufferSize * Inc) if DMA_MemoryInc_Disable != DmaInit.MemoryInc else Inc
    return (Size, Inc)

#-------------------------------------------------------------------------------------------------

def DMA_GetSize_Peripheral(DmaInit):

    Inc = 1 if DMA_PeripheralDataSize_Byte == DmaInit.PeripheralDataSize else 2 if DMA_PeripheralDataSize_HalfWord == DmaInit.PeripheralDataSize else 4
    Size = (DmaInit.BufferSize * Inc) if DMA_PeripheralInc_Disable != DmaInit.PeripheralInc else Inc
    return (Size, Inc)

#-------------------------------------------------------------------------------------------------

def DMA_Dump(Name, OCD, DmaInit, Caller=None):

    MemSize, MemInc = DMA_GetSize_Memory(DmaInit)
    PerSize, PerInc = DMA_GetSize_Peripheral(DmaInit)

    MemData = '           '
    PerData = '           '
    if DMA_DIR_PeripheralSRC != DmaInit.DIR:
        Dir = '<='
        if MemSize <= 4:
            Word = OCD.ReadMem32(DmaInit.MemoryBaseAddr)
            MemData = '*({:08x})'.format(Word)
    else:
        Dir = '=>'
        if PerSize <= 4:
            Word = OCD.ReadMem32(DmaInit.PeripheralBaseAddr)
            PerData = '*({:08x})'.format(Word)

    Inc  = 'P%d' % PerInc
    Inc += '+' if DMA_PeripheralInc_Disable != DmaInit.PeripheralInc else '.'

    Inc += 'M%d' % MemInc
    Inc += '+' if DMA_MemoryInc_Disable != DmaInit.MemoryInc else '.'

    LR = ('0x%08x' % Caller) if Caller else '???'

    Msg = '%s DMA LR:%s P:0x%08x %s (%s) M:0x%08x %s [0x%04x] %s' % (Name, LR, DmaInit.PeripheralBaseAddr, PerData, Dir, DmaInit.MemoryBaseAddr, MemData, DmaInit.BufferSize, Inc)
    return Msg

#-------------------------------------------------------------------------------------------------

