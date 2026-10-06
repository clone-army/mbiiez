"""Map loading-screen pictures (levelshots/<map>.jpg|tga|png) from the game's
pk3s, for the public page's server cards. Only levelshots are ever read, by
a plain map name; TGAs are turned into PNGs so browsers can show them."""
import os
import re
import struct
import threading
import zipfile
import zlib

from mbiiez import settings

_lock = threading.Lock()
_index = {"sig": None, "shots": {}}
_cache = {}
_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_EXT = (".jpg", ".jpeg", ".png", ".tga")


def _pk3s():
    base = str(settings.locations.mbii_path)
    try:
        names = sorted((f for f in os.listdir(base) if f.lower().endswith(".pk3")), key=str.lower)
    except OSError:
        return []
    return [os.path.join(base, f) for f in names]


def _signature(paths):
    sig = []
    for path in paths:
        try:
            st = os.stat(path)
            sig.append((path, st.st_size, int(st.st_mtime)))
        except OSError:
            pass
    return tuple(sig)


def _shots():
    paths = _pk3s()
    sig = _signature(paths)
    with _lock:
        if _index["sig"] == sig:
            return _index["shots"]
    shots = {}
    # The game reads pk3s in name order and a later one wins.
    for path in paths:
        try:
            with zipfile.ZipFile(path) as z:
                for member in z.namelist():
                    low = member.lower()
                    if low.startswith("levelshots/") and low.endswith(_EXT) and low.count("/") == 1:
                        shots[low[11:].rsplit(".", 1)[0]] = (path, member)
        except (zipfile.BadZipFile, OSError):
            continue
    with _lock:
        _index.update(sig=sig, shots=shots)
        _cache.clear()
    return shots


def levelshot(mapname):
    """(bytes, mimetype) of a map's levelshot, or None."""
    if not _NAME.match(str(mapname or "")):
        return None
    key = mapname.lower()
    shots = _shots()
    with _lock:
        if key in _cache:
            return _cache[key]
    hit = shots.get(key)
    out = None
    if hit:
        try:
            with zipfile.ZipFile(hit[0]) as z:
                data = z.read(hit[1])
            low = hit[1].lower()
            if low.endswith(".tga"):
                png = tga_to_png(data)
                out = (png, "image/png") if png else None
            else:
                out = (data, "image/png" if low.endswith(".png") else "image/jpeg")
            out = _smaller(out) if out else None
        except (zipfile.BadZipFile, OSError, KeyError):
            out = None
    with _lock:
        if len(_cache) > 256:
            _cache.clear()
        _cache[key] = out
    return out


def _smaller(shot, width=960):
    """Scaled down to a card's size when Pillow is installed (levelshots are
    often 1-2 MB); as it is otherwise."""
    try:
        from PIL import Image
        import io
    except ImportError:
        return shot
    try:
        img = Image.open(io.BytesIO(shot[0])).convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80, optimize=True, progressive=True)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return shot


def tga_to_png(data):
    """A TGA (true colour or grey, plain or run-length) as PNG bytes."""
    if len(data) < 18:
        return None
    idlen, cmtype, itype = data[0], data[1], data[2]
    w, h = struct.unpack_from("<HH", data, 12)
    bpp, desc = data[16], data[17]
    if cmtype or itype not in (2, 3, 10, 11) or not w or not h or w * h > 4096 * 4096:
        return None
    px = bpp // 8
    if px not in (1, 3, 4):
        return None
    pos = 18 + idlen
    need = w * h * px
    if itype in (2, 3):
        raw = data[pos:pos + need]
    else:
        out = bytearray()
        while len(out) < need and pos < len(data):
            c = data[pos]
            pos += 1
            count = (c & 0x7f) + 1
            if c & 0x80:
                out += data[pos:pos + px] * count
                pos += px
            else:
                out += data[pos:pos + px * count]
                pos += px * count
        raw = bytes(out[:need])
    if len(raw) < need:
        return None
    rgba = bytearray(w * h * 4)
    if px == 1:
        rgba[0::4] = raw
        rgba[1::4] = raw
        rgba[2::4] = raw
        rgba[3::4] = b"\xff" * (w * h)
    else:
        rgba[0::4] = raw[2::px]
        rgba[1::4] = raw[1::px]
        rgba[2::4] = raw[0::px]
        rgba[3::4] = raw[3::px] if px == 4 else b"\xff" * (w * h)
    stride = w * 4
    rows = [rgba[y * stride:(y + 1) * stride] for y in range(h)]
    if not desc & 0x20:
        rows.reverse()  # stored bottom row first
    body = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(body, 6)) + chunk(b"IEND", b""))
