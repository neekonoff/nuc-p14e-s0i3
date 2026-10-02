# AMISCE (AMI Setup Control Environment)

## Why these binaries are here

AMISCE is AMI's proprietary utility. It is included for one reason: on this end-of-life Intel platform
it is the only way to change the hidden BIOS option that prevents S0i3, the version that works is
very hard to find, and without it the fix described in this repository cannot be applied.

The files are unmodified copies from a firmware tools package that Lenovo distributes for its
ThinkSystem SR590 V2 servers (`lnvgy_fw_uefi_xwe160d-1.14_anyos_32-64_tools.zip`,
sha256 `ef5d198d1b2a8f7cb444972259a61f8a29e5e0ad46b0fc82de75313fbdb0612b`). They are provided so that
owners can repair hardware they own, not for any commercial purpose. All rights belong to AMI.
Rights holders who want the files removed can open an issue.

## Что это и зачем выложено

AMISCE — закрытая утилита AMI. Выложена по одной причине: на этой снятой с поддержки платформе Intel
скрытую настройку BIOS, мешающую S0i3, больше нечем поменять, рабочую версию утилиты очень трудно
найти, а без неё описанное здесь исправление не применить. Файлы — неизменённые копии из пакета,
который Lenovo распространяет для серверов ThinkSystem SR590 V2. Выложены для ремонта собственного
железа, не для коммерческого использования. Все права принадлежат AMI.

## Files

| File | Version | sha256 | Status on NUC P14E + NUC 12 Compute Element |
|---|---|---|---|
| `SceLnx/SCELNX_64` | 5.05.06.0007 | `b5218752a7b6d330f1e29ff2ea48b7ed76f40d61e86b66dcc0670023b21ab806` | works: reads and writes, no kernel module needed |
| `SceWin/SCEWIN_64.exe` + `amigendrv64.sys` | from the same package | `eee4dac2fa002471b74552437e96bcec6b7180bf4248ad691ea26a8502d706ce` | not tested |
| `SceEfi/SceEfi64.efi` | from the same package | `d24cd6a0650ede8274fcff31fca1e0d595be499f4b888e14eb1273f13ebd3e7f` | reads; writing fails with "Error in writing variable PchSetup to NVRAM" |

Usage is described in [../docs/amisce.md](../docs/amisce.md). Lenovo's note in the package says to add
`/ni` when importing; on this board the import works without it.
