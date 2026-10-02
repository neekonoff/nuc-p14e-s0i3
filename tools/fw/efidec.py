#!/usr/bin/env python3
"""EFI / Tiano decompression in pure Python.

A port of the UEFI Decompress algorithm as implemented in EDK II
(MdePkg/Library/BaseUefiDecompressLib, Copyright (c) Intel Corporation,
SPDX-License-Identifier: BSD-2-Clause-Patent). Used here to unpack the
EFI-compressed PEI modules of Intel FSP-S.

  from efidec import decompress
  data, pbit = decompress(section_payload)   # payload starts with the 8-byte size header
"""
BITBUFSIZ = 32
MAXMATCH = 256
THRESHOLD = 3
CODE_BIT = 16
NC = 0xff + MAXMATCH + 2 - THRESHOLD
CBIT = 9
MAXPBIT = 5
TBIT = 5
MAXNP = (1 << MAXPBIT) - 1
NT = CODE_BIT + 3
NPT = MAXNP if MAXNP > NT else NT
M32 = 0xFFFFFFFF


class Bad(Exception):
    pass


class Dec:
    def __init__(self, src, pbit):
        self.comp = int.from_bytes(src[0:4], 'little')
        self.orig = int.from_bytes(src[4:8], 'little')
        self.src = src[8:8 + self.comp]
        self.inp = 0
        self.bitbuf = 0
        self.sub = 0
        self.bitcount = 0
        self.compsize = self.comp
        self.blocksize = 0
        self.pbit = pbit
        self.left = [0] * (2 * NC - 1)
        self.right = [0] * (2 * NC - 1)
        self.clen = [0] * NC
        self.ptlen = [0] * NPT
        self.ctable = [0] * 4096
        self.pttable = [0] * 256
        self.out = bytearray()

    def fill(self, n):
        self.bitbuf = (self.bitbuf << n) & M32
        while n > self.bitcount:
            n -= self.bitcount
            self.bitbuf |= (self.sub << n) & M32
            if self.compsize > 0:
                self.compsize -= 1
                self.sub = self.src[self.inp] if self.inp < len(self.src) else 0
                self.inp += 1
            else:
                self.sub = 0
            self.bitcount = 8
        self.bitcount -= n
        self.bitbuf |= self.sub >> self.bitcount

    def getbits(self, n):
        v = self.bitbuf >> (BITBUFSIZ - n) if n else 0
        self.fill(n)
        return v

    def make_table(self, nchar, bitlen, tablebits, table):
        count = [0] * 17
        weight = [0] * 17
        start = [0] * 18
        for i in range(nchar):
            if bitlen[i] > 16:
                raise Bad('bitlen')
            count[bitlen[i]] += 1
        for i in range(1, 17):
            start[i + 1] = (start[i] + (count[i] << (16 - i))) & 0xFFFF
        if start[17] != 0:
            raise Bad('start17')
        jubits = 16 - tablebits
        for i in range(1, tablebits + 1):
            start[i] >>= jubits
            weight[i] = 1 << (tablebits - i)
        i = tablebits + 1
        while i <= 16:
            weight[i] = 1 << (16 - i)
            i += 1
        idx = start[tablebits + 1] >> jubits
        if idx != 0:
            idx3 = 1 << tablebits
            for k in range(idx, idx3):
                table[k] = 0
        avail = nchar
        mask = 1 << (15 - tablebits)
        maxlen = 1 << tablebits
        for ch in range(nchar):
            ln = bitlen[ch]
            if ln == 0 or ln >= 17:
                continue
            nextcode = (start[ln] + weight[ln]) & 0xFFFF
            if ln <= tablebits:
                if nextcode > maxlen:
                    raise Bad('tbl')
                for k in range(start[ln], nextcode):
                    table[k] = ch
            else:
                idx3 = start[ln]
                # pointer: (array, index)
                arr, pi = table, idx3 >> jubits
                n = ln - tablebits
                while n != 0:
                    if arr[pi] == 0 and avail < (2 * NC - 1):
                        self.right[avail] = self.left[avail] = 0
                        arr[pi] = avail
                        avail += 1
                    if arr[pi] < (2 * NC - 1):
                        if idx3 & mask:
                            arr, pi = self.right, arr[pi]
                        else:
                            arr, pi = self.left, arr[pi]
                    idx3 = (idx3 << 1) & 0xFFFF
                    n -= 1
                arr[pi] = ch
            start[ln] = nextcode

    def read_pt_len(self, nn, nbit, special):
        number = self.getbits(nbit)
        if number == 0:
            c = self.getbits(nbit)
            for i in range(256):
                self.pttable[i] = c
            for i in range(nn):
                self.ptlen[i] = 0
            return
        idx = 0
        while idx < number and idx < NPT:
            c = self.bitbuf >> (BITBUFSIZ - 3)
            if c == 7:
                mask = 1 << (BITBUFSIZ - 1 - 3)
                while mask & self.bitbuf:
                    mask >>= 1
                    c += 1
            self.fill(3 if c < 7 else c - 3)
            self.ptlen[idx] = c
            idx += 1
            if idx == special:
                c = self.getbits(2)
                while c > 0 and idx < NPT:
                    self.ptlen[idx] = 0
                    idx += 1
                    c -= 1
        while idx < nn and idx < NPT:
            self.ptlen[idx] = 0
            idx += 1
        self.make_table(nn, self.ptlen, 8, self.pttable)

    def read_c_len(self):
        number = self.getbits(CBIT)
        if number == 0:
            c = self.getbits(CBIT)
            for i in range(NC):
                self.clen[i] = 0
            for i in range(4096):
                self.ctable[i] = c
            return
        idx = 0
        while idx < number and idx < NC:
            c = self.pttable[self.bitbuf >> (BITBUFSIZ - 8)]
            if c >= NT:
                mask = 1 << (BITBUFSIZ - 1 - 8)
                while True:
                    c = self.right[c] if (mask & self.bitbuf) else self.left[c]
                    mask >>= 1
                    if c < NT:
                        break
            self.fill(self.ptlen[c])
            if c <= 2:
                if c == 0:
                    c = 1
                elif c == 1:
                    c = self.getbits(4) + 3
                else:
                    c = self.getbits(CBIT) + 20
                while c > 0 and idx < NC:
                    self.clen[idx] = 0
                    idx += 1
                    c -= 1
            else:
                self.clen[idx] = c - 2
                idx += 1
        for i in range(idx, NC):
            self.clen[i] = 0
        self.make_table(NC, self.clen, 12, self.ctable)

    def decode_c(self):
        if self.blocksize == 0:
            self.blocksize = self.getbits(16)
            self.read_pt_len(NT, TBIT, 3)
            self.read_c_len()
            self.read_pt_len(MAXNP, self.pbit, -1)
        self.blocksize -= 1
        j = self.ctable[self.bitbuf >> (BITBUFSIZ - 12)]
        if j >= NC:
            mask = 1 << (BITBUFSIZ - 1 - 12)
            while True:
                j = self.right[j] if (self.bitbuf & mask) else self.left[j]
                mask >>= 1
                if j < NC:
                    break
        self.fill(self.clen[j])
        return j

    def decode_p(self):
        v = self.pttable[self.bitbuf >> (BITBUFSIZ - 8)]
        if v >= MAXNP:
            mask = 1 << (BITBUFSIZ - 1 - 8)
            while True:
                v = self.right[v] if (self.bitbuf & mask) else self.left[v]
                mask >>= 1
                if v < MAXNP:
                    break
        self.fill(self.ptlen[v])
        pos = v
        if v > 1:
            pos = (1 << (v - 1)) + self.getbits(v - 1)
        return pos

    def run(self):
        self.fill(BITBUFSIZ)
        out = self.out
        orig = self.orig
        while len(out) < orig:
            c = self.decode_c()
            if c < 256:
                out.append(c)
            else:
                n = c - (256 - THRESHOLD)
                di = len(out) - self.decode_p() - 1
                if di < 0:
                    raise Bad('dataidx')
                for _ in range(n):
                    if len(out) >= orig:
                        break
                    out.append(out[di])
                    di += 1
        return bytes(out)


def decompress(src):
    """Try EFI (PBit=4) first, then Tiano (PBit=5)."""
    last = None
    for pbit in (4, 5):
        try:
            d = Dec(src, pbit)
            if d.orig > 0x4000000 or d.comp > len(src):
                raise Bad('header')
            return d.run(), pbit
        except (Bad, IndexError) as e:
            last = e
    raise Bad(str(last))
