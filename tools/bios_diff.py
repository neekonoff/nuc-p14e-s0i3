#!/usr/bin/env python3
"""Work with AMISCE text dumps (SCELNX_64 /o /s <file>). Never writes to the BIOS itself.

  bios_diff.py diff A B
      what differs between two dumps (A -> B)

  bios_diff.py nondefault DUMP
      which questions differ from their "BIOS Default" column

  bios_diff.py script CURRENT REFERENCE OUT [TOKEN ...]
      build an AMISCE script that brings the current state to the reference dump.
      Without TOKENs: every difference; with TOKENs: only those questions.
      CURRENT must be a dump taken in the current boot - HIICrc32 and the question
      blocks are copied from it.

  bios_diff.py defaults CURRENT OUT TOKEN [TOKEN ...]
      build a script that returns the listed questions to their "BIOS Default" value.
      ALL instead of a list: every non-default question; -TOKEN excludes a question.

Then, from the directory with the utility:
  sudo ./SCELNX_64 /cs OUT /o cmp.txt                 compare with NVRAM, nothing is written
  sudo ./SCELNX_64 /i /s OUT /cpwd '<admin password>'  write; then power the machine off and on
"""
import re
import sys


def parse(path):
    txt = open(path, encoding='latin-1').read().replace('\r', '')
    blocks = re.split(r'\n(?=Setup Question\s*=)', txt)
    res, order = {}, []
    for b in blocks[1:]:
        b = re.split(r'\n(?=// Setup Question)', b)[0]
        name = re.search(r'Setup Question\s*=\s*(.*)', b).group(1).strip()
        tok = re.search(r'Token\s*=\s*([0-9A-Fa-f]+)', b)
        off = re.search(r'Offset\s*=\s*([0-9A-Fa-f]+)', b)
        mo = re.search(r'^\s*(?:Options\s*=)?\s*\*(\[[0-9A-Fa-f]+\][^\n/]*)', b, re.M)
        if mo:
            val = mo.group(1).strip()
        else:
            mv = re.search(r'^Value\s*=\s*([^\t\n/]*)', b, re.M)
            val = ('V=' + mv.group(1).strip()) if mv else None
        d = re.search(r'BIOS Default\s*=\s*(.*)', b)
        key = (tok.group(1) if tok else '?', off.group(1) if off else '?', name)
        if key not in res:
            order.append(key)
        res[key] = dict(val=val, dflt=d.group(1).strip() if d else None, block=b)
    return res, order


def code(v):
    """Value used for comparison: option code or number."""
    if v is None:
        return None
    v = v[2:] if v.startswith('V=') else v
    m = re.match(r'\[([0-9A-Fa-f]+)\]', v)
    return m.group(1).upper() if m else v.strip()


def show(v):
    return '-' if v is None else (v[2:] if v.startswith('V=') else v)


def cmd_diff(a_path, b_path):
    a, oa = parse(a_path)
    b, ob = parse(b_path)
    n = 0
    for k in oa:
        if k in b and code(a[k]['val']) != code(b[k]['val']):
            n += 1
            print('T%5s | %-44s | %-26s -> %-26s' % (k[0], k[2][:44], show(a[k]['val'])[:26], show(b[k]['val'])[:26]))
    print('differences: %d; only in first: %d; only in second: %d' % (
        n, len([k for k in oa if k not in b]), len([k for k in ob if k not in a])))


def cmd_nondefault(path):
    cur, order = parse(path)
    n = 0
    for k in order:
        v, d = cur[k]['val'], cur[k]['dflt']
        if v is None or d is None or code(v) == code(d):
            continue
        n += 1
        print('T%5s | %-44s | %-26s | default: %s' % (k[0], k[2][:44], show(v)[:26], d[:26]))
    print('differ from BIOS Default: %d' % n)


def set_value(block, target):
    b = block
    m = re.match(r'\[([0-9A-Fa-f]+)\]', show(target))
    if m:
        v = m.group(1)
        b = b.replace('*[', '[')
        b, n = re.subn(r'(Options\s*=)\[%s\]' % re.escape(v), r'\1*[%s]' % v, b)
        if n == 0:
            b, n = re.subn(r'(\n\s*)\[%s\]' % re.escape(v), r'\1*[%s]' % v, b, count=1)
    else:
        v = show(target)
        b, n = re.subn(r'^(Value\s*=)[^\t\n/]*', lambda mm: mm.group(1) + v, b, count=1, flags=re.M)
    if n != 1:
        raise SystemExit('cannot set value %r in block:\n%s' % (target, block))
    return b.rstrip('\n')


def cmd_script(cur_path, ref_path, out_path, tokens):
    cur, order = parse(cur_path)
    ref, _ = parse(ref_path)
    crc = re.search(r'HIICrc32\s*=\s*([0-9A-Fa-f]+)', open(cur_path, encoding='latin-1').read()).group(1)
    want = {t.upper() for t in tokens}
    absent = [k for k in ref if k not in cur]
    if len(absent) > 100:
        print('WARNING: %d reference questions are missing from the current dump - probably a different'
              ' BIOS version; tokens may have changed, look questions up by name' % len(absent))
    items, skipped = [], []
    for k in order:
        if want and k[0].upper() not in want:
            continue
        if k not in ref or ref[k]['val'] is None or cur[k]['val'] is None:
            if want:
                skipped.append(k)
            continue
        if code(ref[k]['val']) != code(cur[k]['val']):
            items.append(k)
    # the header must look exactly like this: name line, CRC line, empty line
    lines = ['// Script File Name : %s' % out_path, 'HIICrc32= %s' % crc, '']
    for k in items:
        lines.append(set_value(cur[k]['block'], ref[k]['val']))
        lines.append('')
        print('T%5s | %-44s | %-22s -> %s' % (k[0], k[2][:44], show(cur[k]['val'])[:22], show(ref[k]['val'])[:22]))
    for k in skipped:
        print('skipped T%s %s: not in the reference or has no value' % (k[0], k[2]))
    if not items:
        print('no differences, script not written')
        return
    open(out_path, 'w', encoding='latin-1').write('\n'.join(lines) + '\n')
    print('wrote %s: %d questions, HIICrc32 %s' % (out_path, len(items), crc))


def cmd_defaults(cur_path, out_path, tokens):
    cur, order = parse(cur_path)
    crc = re.search(r'HIICrc32\s*=\s*([0-9A-Fa-f]+)', open(cur_path, encoding='latin-1').read()).group(1)
    excl = {t[1:].upper() for t in tokens if t.startswith('-')}
    incl = {t.upper() for t in tokens if not t.startswith('-')}
    lines = ['// Script File Name : %s' % out_path, 'HIICrc32= %s' % crc, '']
    n = 0
    for k in order:
        v, d = cur[k]['val'], cur[k]['dflt']
        if v is None or d is None or code(v) == code(d):
            continue
        tok = k[0].upper()
        if tok in excl or ('ALL' not in incl and tok not in incl):
            continue
        lines.append(set_value(cur[k]['block'], d))
        lines.append('')
        n += 1
        print('T%5s | %-44s | %-22s -> %s' % (k[0], k[2][:44], show(v)[:22], d[:22]))
    if not n:
        print('nothing to change, script not written')
        return
    open(out_path, 'w', encoding='latin-1').write('\n'.join(lines) + '\n')
    print('wrote %s: %d questions, HIICrc32 %s' % (out_path, n, crc))


def main():
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == 'diff':
        cmd_diff(a[1], a[2])
    elif len(a) == 2 and a[0] == 'nondefault':
        cmd_nondefault(a[1])
    elif len(a) >= 4 and a[0] == 'script':
        cmd_script(a[1], a[2], a[3], a[4:])
    elif len(a) >= 4 and a[0] == 'defaults':
        cmd_defaults(a[1], a[2], a[3:])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
