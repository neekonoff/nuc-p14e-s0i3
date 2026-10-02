#!/usr/bin/env python3
"""Print PE header facts of an unpacked firmware module: machine, entry point, image base, sections.

  pe.py MODULE.bin

Modules written by unfv.py start with a 4-byte section header; it is skipped automatically.
"""
import struct, sys
def pe_info(path):
    b = open(path, 'rb').read()
    base = 4 if b[4:6] == b'MZ' else 0          # skip EFI section header
    e_lfanew = struct.unpack_from('<I', b, base + 0x3c)[0]
    pe = base + e_lfanew
    assert b[pe:pe+4] == b'PE\0\0', b[pe:pe+4]
    machine, nsec = struct.unpack_from('<HH', b, pe + 4)
    optsz = struct.unpack_from('<H', b, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from('<H', b, opt)[0]
    entry = struct.unpack_from('<I', b, opt + 16)[0]
    imgbase = struct.unpack_from('<I', b, opt + 28)[0] if magic == 0x10b else struct.unpack_from('<Q', b, opt + 24)[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        name = b[so:so+8].rstrip(b'\0').decode('latin-1')
        vsz, va, rsz, raw = struct.unpack_from('<IIII', b, so + 8)
        secs.append((name, va, vsz, raw, rsz)); so += 40
    return dict(base=base, machine=machine, magic=magic, entry=entry, imgbase=imgbase, secs=secs, data=b)
def off2rva(info, off):
    o = off - info['base']
    for name, va, vsz, raw, rsz in info['secs']:
        if raw <= o < raw + rsz: return o - raw + va
    return o
def rva2off(info, rva):
    for name, va, vsz, raw, rsz in info['secs']:
        if va <= rva < va + max(vsz, rsz): return rva - va + raw + info['base']
    return rva + info['base']
if __name__ == '__main__':
    i = pe_info(sys.argv[1])
    print('machine %#x magic %#x entry %#x imagebase %#x fileoff_base %d' % (i['machine'], i['magic'], i['entry'], i['imgbase'], i['base']))
    for s in i['secs']: print('  sec %-8s va %#x vsz %#x raw %#x rsz %#x' % s)
