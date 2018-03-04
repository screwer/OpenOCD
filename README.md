# OpenOCD

This library allows to control OpenOCD debug server via it's telnet connection port.

## Getting Started

TODO: Write more detailed documentation.

The main purpose is automated debug scripts.


### Typcal usage scenario
```
    from OpenOCD import OpenOCD

    ocd = OpenOCD()
    ocd.Reset(Init=True)

    ocd.RemoveBPs() # remove all (previous) installed BreakPoints
    ocd.RemoveWPs() # remove all (previous) installed WatchPoints

    [set need break/watch points and other automated debug session prerequisites]

    while True:
        r = ocd.Resume()    # run until stop condition
        r = ocd.Readout()   # read all OpenOCD output

        [read registers, change some of them and other debug logic here]


```

### Examples

Rich example of library functions usage is 'dbgbot', tool i wrote for reverse Iron Soldering Station firmare, based on STM32 MCU.

### Known Bugs

Some FLASH-oriented methods are unfinished.