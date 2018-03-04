
from OpenOCD import OpenOCD
import CMSIS
import sys

#-------------------------------------------------------------------------------------------------

dump = OpenOCD.HexView

#-------------------------------------------------------------------------------------------------

def DebugSession_DMA(ocd):

    DMAInit                 = 0x0800267E
    DMACmd                  = 0x08002570
    DMAGetCurrDataCounter   = 0x08002678 

    KnownCallers = {
        0x08002e81: "MasterCRCtoRAM",
        0x08005001: "Calc_CRC_0_Wrap (Begin)",
        0x08005043: "Calc_CRC_0_Wrap (End)",
        0x080050d3: "Calc_CRC_0",
        0x08005203: "Calc_CRC_1",
        0x08002359: "Calc_CRC_2",
        0x08002f07: "Calc_CRC_3",
        0x08002c17: "Calc_CRC_4",
        0x080030bb: "Calc_CRC_5",
        0x08002d47: "Calc_CRC_6",
        0x08007a7d: "Calc_CRC_7",
        0x08002b09: "DMACopyWord_0",
        0x08002b91: "DMACopyWord_1",
        0x08002a7f: "DMACopyWord_2",
        0x080029f3: "Get_DesignID_0",
        0x08001c61: "Get_DesignID_1",
        0x08001d99: "Calc_CRC_7_Wrap (Begin)",
        0x08001e81: "Calc_CRC_7_Wrap (End)",
        0x08001b73: "DMACopy_32bytes_0",
        0x08001be7: "DMACopy_32bytes_1",
    }

    bpDMAInit               = ocd.BP(DMAInit, Enable = True)
    bpDMACmd                = ocd.BP(DMACmd)
    bpDMAGetCurrDataCounter = ocd.BP(DMAGetCurrDataCounter)
    bpDMACompleted          = ocd.BP(0)

    pc = ocd.Reg('pc')
    r1 = ocd.Reg('r1')
    lr = ocd.Reg('lr')

    dma = CMSIS.DMA_InitTypeDef()
    
    while True:
        r = ocd.Resume()
        r = ocd.Readout()

        Addr = pc.Read()        

        if bpDMAInit.Addr == Addr: 
            #
            # BP on DMA_Init
            #
            if bpDMACmd.Enabled:
                Name = 'WARNING! BP on DMA_Cmd not disabled!'
                Msg = CMSIS.DMA_Dump(Name, ocd, dma, Caller)
                print(Msg)
                bpDMACmd.Disable()

            if bpDMAGetCurrDataCounter.Enabled:
                Name = 'WARNING! BP on DMA_GetCurrDataCounter not disabled!'
                Msg = CMSIS.DMA_Dump(Name, ocd, dma, Caller)
                print(Msg)
                bpDMAGetCurrDataCounter.Disable()

            if bpDMACompleted.Enabled:
                Name = 'WARNING! completion BP still not triggered!'
                Msg = CMSIS.DMA_Dump(Name, ocd, dma, Caller)
                print(Msg)
                bpDMACompleted.Disable()

            CMSIS.ReadStruct(ocd, r1.Read(), dma)

            Caller = lr.Read()

            M2M = CMSIS.DMA_M2M_Enable == dma.M2M
            CRC = CMSIS.REG_CRC_BASE == (dma.PeripheralBaseAddr & (~0xFF))

            if M2M or CRC:                
                bpDMACmd.Enable()
            else:
                Name = '  ???'
                Msg = CMSIS.DMA_Dump(Name, ocd, dma, lr.Read())
                print(Msg)
        
        if bpDMACmd.Addr == Addr:
            NewState = r1.Read()
            if 0 != NewState:
                MemSize, MemInc = CMSIS.DMA_GetSize_Memory(dma)
                if MemSize > 32:
                    #
                    # Need to wait while operation competed
                    #
                    bpDMAGetCurrDataCounter.Enable()
                else:
                    bpDMACompleted.Addr = lr.Read() & (~1)
                    bpDMACompleted.Enable()
                bpDMACmd.Disable()

        if bpDMAGetCurrDataCounter.Addr == Addr:
            bpDMAGetCurrDataCounter.Disable()
            bpDMACompleted.Addr = 0x04 + (lr.Read() & (~1)) # wait-cycle end
            bpDMACompleted.Enable()

        if bpDMACompleted.Addr == Addr:
            bpDMACompleted.Disable()

            KnownCaller = KnownCallers.get(Caller)
            ResetCRCUnit = CRC and 0x08 == (dma.PeripheralBaseAddr & 0xFF)

            if KnownCaller or ResetCRCUnit:
                print('-------------------------------------------------------------------------------------------------') 
            if KnownCaller:
                print(KnownCaller)

            Name = '  CRC' if CRC else '  M2M' if M2M else '  ???'
            Msg = CMSIS.DMA_Dump(Name, ocd, dma, Caller)
            print(Msg)                                 

            MemSize, MemInc = CMSIS.DMA_GetSize_Memory(dma)
            if MemSize > 4 and MemSize < 0x100:
                #
                # Dump DMA contents
                #
                if MemSize <= 32:
                    #
                    # No normal wait was performed, execute some code while DMA
                    #
                    for x in range(0, MemSize):
                        ocd.Step()

                Data = ocd.ReadMem(dma.MemoryBaseAddr, MemSize)
                OpenOCD.HexView(Data, dma.MemoryBaseAddr, '  ')

#-------------------------------------------------------------------------------------------------

def DebugSession_Task(ocd):

    TaskCreate = 0x08005D90
    bpTaskCreate = ocd.BP(TaskCreate, Enable = True)

    class Task:
        def __init__(self, Name, Functions):
            self.Name = Name
            self.Functions = Functions

        def GetAddrName(self, Addr):
            for i in xrange(0, len(self.Functions)):
                f = self.Functions[i]
                if f.IsInside(Addr):
                    if 0 == i:
                        return self.Name
                    Name += ':' + (f.Name if f.Name else 'sub_%08x' % f.AddrStart)
                    return Name
            return None

    class Function:
        def __init__(self, AddrStart, AddrEnd, Name=None):
            self.AddrStart = AddrStart
            self.AddrEnd = AddrEnd
            self.Name = Name

        def IsInside(self, Addr):
            return self.AddrStart <= Addr and Addr < self.AddrEnd

    KnownTasks = {
        Task("TaskInit",            [Function(0x8001154, 0x8001264),]),
        Task("EnterRegCode",        [Function(0x800350C, 0x80036DC),]),
        Task("TaskUnk_0",           [Function(0x80090F4, 0x80091B4),]),
        Task("TaskUnk_1",           [Function(0x8007B58, 0x8007C00),]),
        Task("TaskGetDesignID_1",   [Function(0x8001C14, 0x8001D30),]),
        Task("Task_CRC_7",          [Function(0x8001D40, 0x8001F2C),]),
        Task("TaskUnk_2",           [Function(0x8007860, 0x8007920),]),
        Task("TaskUnk_3",           [Function(0x8007928, 0x80079F0),]),
    }

    def FindTaskName(Addr):
        for Task in KnownTasks:
            Name = Task.GetAddrName(Addr)
            if Name:
                return Name
        return None

    pc = ocd.Reg('pc')
    lr = ocd.Reg('lr')
    r0 = ocd.Reg('r0')
    r1 = ocd.Reg('r1')
    r2 = ocd.Reg('r2')
    r3 = ocd.Reg('r3')

    while True:
        r = ocd.Resume()
        r = ocd.Readout()

        Addr = pc.Read()        

        if bpTaskCreate.Addr == Addr:
            Arg0 = r0.Read()
            Arg1 = r1.Read()
            Arg2 = r2.Read()
            Arg3 = r3.Read()
            Caller = lr.Read()

            ParentTaskName = FindTaskName(Caller)
            if ParentTaskName:
                ParentTaskName += ":0x%08x" % Caller
            else:
                ParentTaskName = "0x%08x" % Caller

            
            ChildTaskName = FindTaskName(Arg0)
            if not ChildTaskName:
                ChildTaskName = "0x%08x" % Arg0

            sArg1 = '0x%08x' % Arg1 if Arg1 else 'NULL'
            print('%s create task %s, Arg:%s Stack:0x%08x Priority:%d'  % (ParentTaskName, ChildTaskName, sArg1, Arg2, Arg3))

#-------------------------------------------------------------------------------------------------

def DebugSession_RegCode(ocd):

    CalcRegCode = 0x80058E0
    CalcRegCode2 = 0x80059B0
    bpCalcRegCode = ocd.BP(CalcRegCode, Enable = True)
    bpCalcRegCode2 = ocd.BP(CalcRegCode2, Enable = True)
    bpCalcCompleted = ocd.BP(0)

    pc = ocd.Reg('pc')
    lr = ocd.Reg('lr')
    r0 = ocd.Reg('r0')
    r1 = ocd.Reg('r1')
    r2 = ocd.Reg('r2')

    while True:
        r = ocd.Resume()
        r = ocd.Readout()

        Addr = pc.Read()        

        if bpCalcRegCode.Addr == Addr or bpCalcRegCode2 == Addr:

            Name = 'CalcRegCode' if bpCalcRegCode.Addr == Addr else 'CalcRegCode2'

            Arg0 = r0.Read()
            Arg1 = r1.Read()
            Arg2 = r2.Read()
            Caller = lr.Read()

            bpCalcCompleted.Disable()
            bpCalcCompleted.Addr = Caller & (~1)
            bpCalcCompleted.Enable()

        if bpCalcCompleted.Addr == Addr:
            Code = r0.Read()
            print("lr=0x%08x %s(0x%08x, 0x%08x, 0x%08x) => 0x%08x" % (Caller, Name, Arg0, Arg1, Arg2, Code))

#-------------------------------------------------------------------------------------------------

def DebugSession_DumpSettings(ocd):

    LoadSettingsDone = 0x080052F0
    SettingsSRAMAddr = 0x200002F0
    SettingsSize = 0x03AE
    bpLoadSettingsDone = ocd.BP(0x80052F0, Enable = True)

    r = ocd.Resume()
    r = ocd.Readout()

    pc = ocd.Reg('pc')
    Addr = pc.Read()

    if bpLoadSettingsDone.Addr == Addr:
        img = ocd.Image()
        img.Dump('settings.eeprom', SettingsSRAMAddr, SettingsSize)
            
#-------------------------------------------------------------------------------------------------

def DebugSession():

    ocd = OpenOCD()
    ocd.Reset(Init=True)

    ocd.RemoveBPs()
    ocd.RemoveWPs()

    pass

    #DebugSession_DMA(ocd)
    #DebugSession_Task(ocd)
    #DebugSession_RegCode(ocd)
    DebugSession_DumpSettings(ocd)

    pass

#-------------------------------------------------------------------------------------------------

DebugSession()
