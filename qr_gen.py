# Автономный генератор QR-кодов (ISO/IEC 18004 Byte Mode, Level L, Version 1–4) в SVG без внешних зависимостей

_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]

# (version, size, data_codewords_L, ec_codewords_L, alignment_positions)
_VERSIONS = [
    (1, 21, 19, 7, []),
    (2, 25, 34, 10, [6, 18]),
    (3, 29, 55, 15, [6, 22]),
    (4, 33, 80, 20, [6, 26]),
    (5, 37, 108, 26, [6, 30]),
]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_encode(data: list, ec_len: int) -> list:
    gen = [1]
    for i in range(ec_len):
        nxt = [0] * (len(gen) + 1)
        factor = _GF_EXP[i]
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _gf_mul(g, factor)
        gen = nxt
    res = list(data) + [0] * ec_len
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j in range(1, len(gen)):
                res[i + j] ^= _gf_mul(gen[j], coef)
    return res[len(data) :]


def _make_matrix(ver_info, codewords: list) -> list:
    _ver, size, _dc, _ec, align_pos = ver_info
    mat = [[None] * size for _ in range(size)]
    is_func = [[False] * size for _ in range(size)]

    def _set(r, c, val):
        if 0 <= r < size and 0 <= c < size:
            mat[r][c] = bool(val)
            is_func[r][c] = True

    def _finder(r0, c0):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if 0 <= rr < size and 0 <= cc < size:
                    in_outer = 0 <= r <= 6 and 0 <= c <= 6
                    on_border = r in (0, 6) or c in (0, 6)
                    in_center = 2 <= r <= 4 and 2 <= c <= 4
                    _set(rr, cc, in_outer and (on_border or in_center))

    _finder(0, 0)
    _finder(0, size - 7)
    _finder(size - 7, 0)

    for i in range(8, size - 8):
        _set(6, i, i % 2 == 0)
        _set(i, 6, i % 2 == 0)

    for r in align_pos:
        for c in align_pos:
            if (r == 6 and c == 6) or (r == 6 and c == size - 7) or (r == size - 7 and c == 6):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    _set(r + dr, c + dc, max(abs(dr), abs(dc)) in (0, 2))

    _set(size - 8, 8, True)

    for i in range(9):
        if i != 6:
            _set(8, i, False)
            _set(i, 8, False)
    for i in range(8):
        _set(8, size - 1 - i, False)
        _set(size - 1 - i, 8, False)

    bits = []
    for cw in codewords:
        for b in range(7, -1, -1):
            bits.append((cw >> b) & 1)

    bit_idx = 0
    up = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not is_func[r][c]:
                    val = bits[bit_idx] if bit_idx < len(bits) else 0
                    bit_idx += 1
                    # Mask 0: (r + c) % 2 == 0
                    if (r + c) % 2 == 0:
                        val ^= 1
                    mat[r][c] = bool(val)
        up = not up
        col -= 2

    # Format info: EC Level L (01) + Mask 0 (000) -> 5 bits = 01000 -> BCH + mask 101010000010010 = 0x77C4 (111011111000100)
    fmt = 0x77C4
    for i in range(6):
        b = bool((fmt >> (14 - i)) & 1)
        mat[8][i] = b
        mat[size - 1 - i][8] = b
    mat[8][7] = bool((fmt >> 8) & 1)
    mat[size - 7][8] = bool((fmt >> 8) & 1)
    mat[8][8] = bool((fmt >> 7) & 1)
    mat[7][8] = bool((fmt >> 6) & 1)
    for i in range(6):
        b = bool((fmt >> (5 - i)) & 1)
        mat[5 - i][8] = b
        mat[8][size - 6 + i] = b
    mat[8][size - 7] = bool((fmt >> 6) & 1)
    return mat


def make_qr_svg(text: str, box_px: int = 190) -> str:
    raw = text.encode("utf-8")
    ver_info = None
    for v in _VERSIONS:
        if len(raw) + 2 <= v[2]:
            ver_info = v
            break
    if ver_info is None:
        raw = raw[: _VERSIONS[-1][2] - 2]
        ver_info = _VERSIONS[-1]

    _ver, size, data_cap, ec_len, _align = ver_info
    bit_str = "0100" + format(len(raw), "08b") + "".join(format(b, "08b") for b in raw)
    if len(bit_str) + 4 <= data_cap * 8:
        bit_str += "0000"
    while len(bit_str) % 8 != 0:
        bit_str += "0"
    codewords = [int(bit_str[i : i + 8], 2) for i in range(0, len(bit_str), 8)]
    pad_bytes = [0xEC, 0x11]
    idx = 0
    while len(codewords) < data_cap:
        codewords.append(pad_bytes[idx % 2])
        idx += 1
    ec = _rs_encode(codewords, ec_len)
    mat = _make_matrix(ver_info, codewords + ec)

    quiet = 2
    total = size + quiet * 2
    rects = []
    for r in range(size):
        for c in range(size):
            if mat[r][c]:
                rects.append(f'<rect x="{c + quiet}" y="{r + quiet}" width="1" height="1"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
        f'width="{box_px}" height="{box_px}" shape-rendering="crispEdges">'
        f'<rect width="{total}" height="{total}" fill="#ffffff" rx="2"/>'
        f'<g fill="#0f172a">{"".join(rects)}</g></svg>'
    )
