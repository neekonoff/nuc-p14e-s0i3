#!/usr/bin/env python3
"""Find and unpack LZMA-compressed sections of a BIOS image/capsule, recursively (read-only).

  fwscan.py IMAGE OUTDIR

Every unpacked blob is saved to OUTDIR; raw.bin is the image itself. Useful for the DXE volume.
FSP-S modules are EFI-compressed instead - use unfv.py for those.
"""
import lzma, sys, os, hashlib, struct
src = sys.argv[1]; out = sys.argv[2]
os.makedirs(out, exist_ok=True)
data = open(src, 'rb').read()
blobs = [('raw', data)]
seen = set()
def scan(name, buf, depth):
    found = 0
    pos = 0
    while True:
        i = buf.find(b'\x5d\x00\x00', pos)
        if i < 0: break
        pos = i + 1
        if i + 13 > len(buf): break
        dict_size = struct.unpack_from('<I', buf, i + 1)[0]
        usize = struct.unpack_from('<Q', buf, i + 5)[0]
        if dict_size not in (1 << 16, 1 << 20, 1 << 21, 1 << 22, 1 << 23, 1 << 24, 1 << 25, 1 << 26):
            continue
        if not (0x1000 <= usize <= 0x8000000):
            continue
        try:
            d = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
            res = d.decompress(buf[i:i + 0x4000000], max_length=usize)
        except Exception:
            continue
        if len(res) < 0x1000: continue
        h = hashlib.md5(res).hexdigest()
        if h in seen: continue
        seen.add(h)
        nm = '%s_%x' % (name, i)
        blobs.append((nm, res)); found += 1
        print('  ' * depth + 'LZMA at %s+0x%x -> %d bytes' % (name, i, len(res)))
        if depth < 3:
            scan(nm, res, depth + 1)
    return found
print('capsule size', len(data))
scan('raw', data, 0)
for nm, b in blobs:
    open(os.path.join(out, nm + '.bin'), 'wb').write(b)
print('blobs:', len(blobs), 'total bytes', sum(len(b) for _, b in blobs))
