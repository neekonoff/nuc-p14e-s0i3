# What the firmware does when `Enable TCO Timer` is disabled

Before changing the option I wanted to know two things: that the firmware really turns the ACPI PM
timer off, and that the PM timer I/O port keeps working afterwards. Linux and the firmware itself
may read that port, and a timer that stopped counting could hang the boot. Intel's FSP documentation
says microcode emulation "must be enabled" when the timer is disabled, without saying who does it.

The answer is in FSP-S: one policy bit controls both.

## Reproducing

The BIOS package is `HBADLMIV.0065.zip`; the capsule inside is `HBADLMIV.0065.CAP`
(sha256 `4dbb7fcb8fc761a0...`).

```
python3 tools/fw/ffs.py find HBADLMIV.0065.CAP           # FSP-S volume at 0xa1459d
python3 tools/fw/unfv.py HBADLMIV.0065.CAP 0xa1459d out  # 14 EFI-compressed modules
python3 tools/fw/dis.py out/80a845ac-210f-43b0-995b-477be41ab4e8_a18155.bin 0x18aed 0x0a i386 0x1b
```

Offsets below are file offsets in the unpacked module `80a845ac-210f-43b0-995b-477be41ab4e8`
(243 KB, the main silicon init module). The config block GUID `93826157-dc85-4e34-aed9-6ea10df9e3a7`
is fetched from the silicon policy PPI `aebffa01-7edc-49ff-8d88-cb848c5e8670`.

## 1. PMC init: the bit is clear, so the timer is disabled

```
18ad6: mov    edx,0x34b10                  ; config block GUID
18adb: call   0x59c6                       ; GetConfigBlock
18ae0: mov    eax,DWORD PTR [ebp-0xc]
18ae4: test   DWORD PTR [eax+0x24],0x400   ; policy bit 10
18aeb: jne    0x18af7
18aed: mov    DWORD PTR ds:0xfe0018fc,0x2  ; PWRMBASE+0x18FC = ACPI_TIM_DIS
```

## 2. CPU init: the same bit sets a flag

```
1bb00: mov    edx,0x34b10                  ; the same config block
1bb05: call   0x59c6
1bb0a: mov    eax,DWORD PTR [ebp-0xc]
1bb10: test   DWORD PTR [eax+0x24],0x400
1bb17: jne    0x1bb20
1bb19: mov    BYTE PTR ds:0x3a298,0x1
```

## 3. The per-CPU routine programs MSR 0x121 when the flag is set

The routine runs on the boot processor and is then dispatched to the application processors.

```
1b645: cmp    BYTE PTR ds:0x3a298,0x0
1b64c: je     0x1b653
1b64e: call   0x1b119
```

```
1b120: mov    edi,0xfe0018ec               ; PMC register that tells the crystal frequency
1b125: mov    edi,DWORD PTR [edi]
1b127: test   edi,0x20000
1b12d: je     0x1b136
1b12f: mov    edi,0x2fba2e26               ; 19.2 MHz
1b134: jmp    0x1b14c
1b136: and    edi,0x100000
1b13c: neg    edi
1b13e: sbb    edi,edi
1b140: and    edi,0xf1ae8bc1
1b146: add    edi,0x262e8b52               ; 24 MHz, or 0x17dd1713 for 38.4 MHz
...
1b157: or     esi,0x1311808                ; delay 0x13 << 20 | enable bit 16 | I/O port 0x1808
...
1b173: mov    ecx,0x121
1b178: wrmsr
```

MSR `0x121` is the PM timer emulation MSR. The high half is `2^32 * 3579545 / crystal frequency`:
`0x17DD1713` for 38.4 MHz, `0x262E8B52` for 24 MHz, `0x2FBA2E26` for 19.2 MHz. The low half
`0x01311808` enables emulation for I/O port `0x1808`, which is the PM timer port of this platform
(`ACPI: PM-Timer IO Port: 0x1808` in the kernel log). This is the same value coreboot programs in
`enable_pm_timer_emulation()`.

On this machine `PWRMBASE + 0x18EC` reads `0x24510300`: bit 17 clear, bit 20 set, so the 38.4 MHz
factor is used.

## Conclusion

With `Enable TCO Timer = Disabled` the firmware disables the hardware ACPI PM timer and enables its
microcode emulation on every core. After the change Linux still registers the `acpi_pm` clocksource,
which confirms that the port keeps counting.
