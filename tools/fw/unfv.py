#!/usr/bin/env python3
"""Decompress the EFI/Tiano-compressed sections of one firmware volume (read-only).

  unfv.py IMAGE FV_OFFSET OUTDIR

Every compressed section is written to OUTDIR/<file guid>_<file offset>.bin. The output still
starts with the 4-byte section header of the inner PE32/TE section.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from efidec import Bad, decompress  # noqa: E402
from ffs import walk_fv             # noqa: E402


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    b = open(sys.argv[1], 'rb').read()
    fv = int(sys.argv[2], 0)
    out = sys.argv[3]
    os.makedirs(out, exist_ok=True)
    ok = bad = 0
    for o, size, typ, g, secs in walk_fv(b, fv):
        ui = [s[4] for s in secs if s[3] == 'UI']
        for d, so, ss, st, info, ds, de in secs:
            if st != 'COMPRESSION':
                continue
            want = struct.unpack_from('<I', b, so + 4)[0]
            try:
                res, pbit = decompress(b[ds:de])
            except Bad:
                res = b''
            if len(res) != want:
                bad += 1
                print('FAILED file %#x %s' % (o, g))
                continue
            ok += 1
            open(os.path.join(out, '%s_%x.bin' % (g, o)), 'wb').write(res)
            print('file %#x type %#x %s %s -> %#x bytes' % (o, typ, g, ui[0] if ui else '', len(res)))
    print('decompressed %d, failed %d' % (ok, bad))


if __name__ == '__main__':
    main()
