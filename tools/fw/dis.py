#!/usr/bin/env python3
"""Disassemble a slice of a raw binary with objdump (read-only).

  dis.py FILE TARGET_OFFSET [BYTES_AFTER] [i386|x64] [BYTES_BEFORE]

Without BYTES_BEFORE the listing starts at the nearest `push ebp; mov ebp, esp` before the target,
which gives correct instruction alignment for most 32-bit functions.
"""
import subprocess
import sys
import tempfile


def dis(path, start, end, mode='i386'):
    b = open(path, 'rb').read()
    arch = ['-m', 'i386'] + (['-M', 'intel,x86-64'] if mode == 'x64' else ['-M', 'intel'])
    with tempfile.NamedTemporaryFile(suffix='.bin') as tmp:
        tmp.write(b[start:end])
        tmp.flush()
        out = subprocess.run(['objdump', '-D', '-b', 'binary'] + arch + ['--adjust-vma=%d' % start, tmp.name],
                             capture_output=True, text=True).stdout.splitlines()[7:]
    for line in out:
        p = line.split('\t')
        if len(p) >= 3:
            print(p[0].strip(), p[2][:90])


def prologue(path, offset, patterns=('558bec', '5589e5')):
    b = open(path, 'rb').read()
    return max(b.rfind(bytes.fromhex(p), 0, offset) for p in patterns)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not 2 <= len(a) <= 5:
        print(__doc__)
        sys.exit(2)
    path = a[0]
    target = int(a[1], 0)
    after = int(a[2], 0) if len(a) > 2 else 0x80
    mode = a[3] if len(a) > 3 else 'i386'
    start = target - int(a[4], 0) if len(a) > 4 else prologue(path, target)
    print('start %#x target %#x' % (start, target))
    dis(path, start, target + after, mode)
