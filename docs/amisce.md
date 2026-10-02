# Writing hidden BIOS settings on this board

The Setup UI of the NUC 12 Compute Element shows a small part of the settings: the `Advanced` and
`Chipset` branches are suppressed in the firmware. The settings still exist and are honoured.

## What works and what does not

| Way | Result |
|---|---|
| AMISCE `SCELNX_64` 5.05.06.0007, from Linux | reads and writes every setup option (about 4,250 at default settings) |
| `iSetupCfg` from Intel "NUC Tools" (an OEM build of the same utility) | only about 180 questions that have a Map String; `Enable TCO Timer` is not among them |
| AMISCE 5.03 / 5.04 builds | do not start on this firmware, or fail to write |
| AMISCE EFI build from the UEFI Shell | accepts the password, then fails: "Error in writing variable PchSetup to NVRAM" |
| `efivarfs`, `setup_var.efi` | `WRITE_PROTECTED` / read-only file system |
| Smokeless UMAF | shows the hidden forms, cannot save them, and left the BIOS needing a reset |

So the only working path is AMISCE 5.05 from the running OS, with the BIOS administrator password.
The password must exist: set one in Setup first. Secure Boot was disabled throughout.

## Getting AMISCE

AMISCE is AMI's proprietary utility. The builds used here are in [../amisce/](../amisce/), together
with the reason they are included. They come from Lenovo's ThinkSystem SR590 V2 UEFI tools package:

```
lnvgy_fw_uefi_xwe160d-1.14_anyos_32-64_tools.zip
  sha256 ef5d198d1b2a8f7cb444972259a61f8a29e5e0ad46b0fc82de75313fbdb0612b
  Sce/SceLnx/SCELNX_64     version 5.05.06.0007
  sha256 b5218752a7b6d330f1e29ff2ea48b7ed76f40d61e86b66dcc0670023b21ab806
```

It runs from Linux as root and needs no kernel module.

## Commands

```
sudo ./SCELNX_64 /o /s now.txt                      # export every question to a text script
sudo ./SCELNX_64 /cs script.txt /o cmp.txt          # compare a script with NVRAM, writes nothing
sudo ./SCELNX_64 /i /s script.txt /cpwd '<password>' # import
```

A minimal import script contains a header and only the questions to change:

```
// Script File Name : tco.txt
HIICrc32= 56EC11A8

Setup Question	= Enable TCO Timer
Help String	= Enable/Disable TCO timer. When disabled, it disables PCH ACPI timer, stops TCO timer, and ACPI WDAT table will not be published.
Token	=B7E	// Do NOT change this line
Offset	=11
Width	=01
BIOS Default=[01]Enabled
Options	=*[00]Disabled	// Move "*" to the desired Option
         [01]Enabled
```

`tools/bios_diff.py script` builds such a file from your own dump.

## Pitfalls

- A script without the `// Script File Name` line fails with "Script file error".
- `HIICrc32` must match the firmware's current HII database. Take it from a dump made in the same
  boot; it can change between boots.
- Questions are addressed by `Token`; `Offset` is informational. Token numbers differ between BIOS
  versions: on 0052 token `B7E` belongs to a different option. Check the question name.
- After an import the utility prints "Power cycle reset required": power the machine off and on.
- `ERROR:64 - HII Database needs reset` appears in the boot that follows saving changes in Setup: the
  firmware has not published its setup database (the `HiiDB` EFI variable holds zeros). Enter Setup
  again, change nothing, leave without saving and let the OS boot.
- With `Fast Boot` enabled the keyboard does not work before the OS starts. Setup is reached through
  the power button menu: power off, hold the power button for three seconds and release it before
  the fourth.
- The firmware rewrites part of `PchSetup` on every boot for this chassis (PCIe root port 9 is
  disabled, `L1 Substates` of one port is forced to `L1.1`). Writing those is pointless. Other
  `PchSetup` fields, `Enable TCO Timer` among them, persist.
- There are two resets. F9 in Setup loads the `StdDefaults` table from NVRAM. The power button menu
  (hold the power button until it blinks) offers F5, a reset to build-time defaults; the administrator
  password survives it.
- Two traps met on the way: `Native ASPM = Enabled` breaks sleep entirely (the CPU stays in package
  C8), and `Clock1` is the reference clock of the I219 Ethernet PHY, not an unused output - leave the
  PCIe clock settings at `Platform-POR`.
