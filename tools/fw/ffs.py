#!/usr/bin/env python3
"""Minimal UEFI firmware volume walker (read-only).

  ffs.py find IMAGE            list firmware volumes and Intel FSP components in a BIOS image/capsule
  ffs.py list IMAGE FV_OFFSET  list the files and sections of one firmware volume

Offsets are file offsets in IMAGE. Only what was needed for this analysis is implemented.
"""
import re
import struct
import sys
import uuid

STYPE = {0x01: 'COMPRESSION', 0x02: 'GUID_DEFINED', 0x10: 'PE32', 0x11: 'PIC', 0x12: 'TE',
         0x13: 'DXE_DEPEX', 0x14: 'VERSION', 0x15: 'UI', 0x17: 'FV_IMAGE', 0x19: 'RAW',
         0x1b: 'PEI_DEPEX', 0x1c: 'MM_DEPEX'}


def guid(b):
    return str(uuid.UUID(bytes_le=bytes(b)))


def sections(b, s, e, depth, out):
    """Collect (depth, offset, size, type, info, data_start, data_end) for a section stream."""
    o = s
    while o + 4 <= e:
        size = int.from_bytes(b[o:o + 3], 'little')
        typ = b[o + 3]
        hdr = 4
        if size == 0xFFFFFF:
            size = struct.unpack_from('<I', b, o + 4)[0]
            hdr = 8
        if size < hdr or o + size > e:
            break
        if typ == 0x02:
            g = guid(b[o + hdr:o + hdr + 16])
            doff, attr = struct.unpack_from('<HH', b, o + hdr + 16)
            out.append((depth, o, size, 'GUID_DEFINED', 'guid=%s dataoff=%#x attr=%#x' % (g, doff, attr),
                        o + doff, o + size))
        elif typ == 0x01:
            ul, ct = struct.unpack_from('<IB', b, o + hdr)
            out.append((depth, o, size, 'COMPRESSION', 'uncompressed=%#x type=%d' % (ul, ct),
                        o + hdr + 5, o + size))
        elif typ == 0x15:
            name = b[o + hdr:o + size].decode('utf-16le', 'ignore').rstrip('\0')
            out.append((depth, o, size, 'UI', name, None, None))
        else:
            out.append((depth, o, size, STYPE.get(typ, hex(typ)), '', o + hdr, o + size))
        o = s + ((o - s + size + 3) & ~3)          # sections are 4-byte aligned within the file


def walk_fv(b, fv):
    """Return [(offset, size, type, name_guid, sections)] for the firmware volume at offset fv."""
    fvlen = struct.unpack_from('<Q', b, fv + 0x20)[0]
    hlen = struct.unpack_from('<H', b, fv + 0x30)[0]
    ext = struct.unpack_from('<H', b, fv + 0x34)[0]
    o = fv + hlen
    if ext:
        o = fv + ext + struct.unpack_from('<I', b, fv + ext + 16)[0]
    o = fv + ((o - fv + 7) & ~7)
    files = []
    while o + 24 <= fv + fvlen:
        name = b[o:o + 16]
        if name == b'\xff' * 16:
            break
        typ = b[o + 18]
        attr = b[o + 19]
        size = int.from_bytes(b[o + 20:o + 23], 'little')
        hdr = 24
        if attr & 0x01 and size == 0:               # large file
            size = struct.unpack_from('<Q', b, o + 24)[0]
            hdr = 32
        if size < hdr or o + size > fv + fvlen:
            break
        secs = []
        if typ not in (0x01, 0xf0):                 # raw files and padding have no sections
            sections(b, o + hdr, o + size, 1, secs)
        files.append((o, size, typ, guid(name), secs))
        o = fv + ((o - fv + size + 7) & ~7)         # files are 8-byte aligned within the volume
    return files


def cmd_find(path):
    b = open(path, 'rb').read()
    for m in re.finditer(b'_FVH', b):
        o = m.start() - 0x28
        if o < 0:
            continue
        fvlen = struct.unpack_from('<Q', b, o + 0x20)[0]
        if 0x1000 <= fvlen <= len(b):
            print('FV   at %#9x  length %#x' % (o, fvlen))
    for m in re.finditer(b'FSPH', b):
        o = m.start()
        if struct.unpack_from('<I', b, o + 4)[0] > 0x100:
            continue
        rev = struct.unpack_from('<I', b, o + 12)[0]
        size, base = struct.unpack_from('<II', b, o + 24)
        comp = struct.unpack_from('<H', b, o + 34)[0]
        kind = {1: 'T', 2: 'M', 3: 'S'}.get((comp >> 12) & 0xf, '?')
        print('FSP-%s header at %#9x  id %s  rev %08x  size %#x  base %#x' % (
            kind, o, b[o + 16:o + 24].decode('latin-1'), rev, size, base))


def cmd_list(path, fv):
    b = open(path, 'rb').read()
    for o, size, typ, g, secs in walk_fv(b, fv):
        ui = [s[4] for s in secs if s[3] == 'UI']
        print('FILE %#x size %#x type %#x %s %s' % (o, size, typ, g, ui[0] if ui else ''))
        for d, so, ss, st, info, ds, de in secs:
            if st != 'UI':
                print('    ' * d + '%s @%#x size %#x %s' % (st, so, ss, info))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == 'find':
        cmd_find(a[1])
    elif len(a) == 3 and a[0] == 'list':
        cmd_list(a[1], int(a[2], 0))
    else:
        print(__doc__)
        sys.exit(2)
