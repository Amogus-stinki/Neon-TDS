#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEON BASTION 2  -  a neon tower defense in 3D  (one file, plays offline or over Wi-Fi)

How to run:   python neon_bastion.py
Needs:        pygame-ce  (or pygame 2)   ->   pip install pygame-ce

Your progress is saved in neon_bastion_save.json next to this file.
"""
import sys
import os
import math
import random
import json
import array
import time
import socket
import functools
import struct
import zlib
import datetime
import re
import hashlib
import hmac
import threading
import subprocess
import select

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:
    print("NEON BASTION needs pygame.  Install it with:   pip install pygame-ce")
    try:
        input("Press Enter to close...")
    except Exception:
        pass
    sys.exit(1)

VERSION = "2.4.0"
CODE_NAME = "neon_bastion.py"            # the file an update replaces
_NB_EXT = globals().get("_NB_EXT")       # set when the .exe is running a newer neon_bastion.py that sits next to it


def ver_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip().split(".")[:4])
    except Exception:
        return (0,)


def version_in(text):
    """the version number written in a copy of this game's code (or None)"""
    m = re.search(r'^VERSION = "([0-9]+(?:\.[0-9]+){1,3})"', text, re.M)
    return m.group(1) if m else None


def _boot_newer():
    """The .exe has the game built in.  If a NEWER neon_bastion.py sits next to the .exe (you dropped it there, or it
    was fetched from your other PC), run that one instead - so the .exe never has to be made again."""
    if not getattr(sys, "frozen", False) or _NB_EXT or os.environ.get("NB_NO_UPDATE"):
        return
    p = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), CODE_NAME)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            src = fh.read()
        v = version_in(src)
        if not v or ver_tuple(v) <= ver_tuple(VERSION):
            return
        code = compile(src, p, "exec")
    except Exception:
        return
    try:
        exec(code, {"__name__": "__main__", "__file__": p, "_NB_EXT": p, "__builtins__": __builtins__})
    except SystemExit:
        raise
    except Exception:
        # the newer file is broken: put it aside and carry on with the built-in game
        try:
            os.replace(p, os.path.join(os.path.dirname(p), "neon_bastion_broken.py"))
        except Exception:
            pass
        return
    sys.exit(0)


_boot_newer()
TITLE = "NEON BASTION"
W, H = 1280, 720
CELL = 40
COLS, ROWS = 26, 16
FW, FH = COLS * CELL, ROWS * CELL        # play field: 1040 x 640
CLIFF_H = 26.0                           # how tall a cliff is
ROAD_W = 17.0                            # half the width of the road
TAU = math.tau

# ---------------------------------------------------------------- colours
WHITE = (240, 244, 255)
GREY = (150, 160, 190)
DIM = (92, 102, 140)
CYAN = (0, 229, 255)
PINK = (255, 80, 170)
GOLD = (255, 206, 84)
RED = (255, 70, 90)
GREEN = (80, 255, 150)
PURPLE = (170, 110, 255)
ORANGE = (255, 150, 60)
BLUE = (90, 150, 255)
YELLOW = (255, 240, 90)
MINT = (120, 255, 220)
MAGENTA = (255, 90, 255)
GHOST = (200, 210, 255)
BG = (8, 9, 22)
PANEL = (13, 16, 34)
LINE = (40, 50, 96)

PLAYER_COLORS = [("CYAN", CYAN), ("PINK", PINK), ("GOLD", GOLD), ("LIME", GREEN), ("VIOLET", PURPLE), ("ORANGE", ORANGE),
                 ("SKY", BLUE), ("MINT", MINT), ("RED", RED), ("MAGENTA", MAGENTA), ("SUN", YELLOW), ("WHITE", WHITE)]
CORE_SKINS = ["DIAMOND", "HEX", "STAR", "ORB"]

GFX = {"glow": True}


# ---------------------------------------------------------------- keys you can change (OPTIONS > CONTROLS)
# ONE table for every keyboard action in a match:  (group title, column on the CONTROLS page, [(action, label, default key), ...])
KEY_GROUPS = [
    ("YOU", 0, [("up", "Walk forward", pygame.K_w), ("left", "Walk left", pygame.K_a), ("down", "Walk back", pygame.K_s),
                ("right", "Walk right", pygame.K_d), ("sprint", "Sprint (hold)", pygame.K_LSHIFT), ("jump", "Jump", pygame.K_SPACE)]),
    ("ABILITY PERKS", 0, [("abil1", "Ability 1", pygame.K_q), ("abil2", "Ability 2", pygame.K_r)]),
    ("PEOPLE", 0, [("talk", "Talk to someone", pygame.K_z), ("chat", "Chat", pygame.K_RETURN)]),
    ("TOWERS", 1, [("slot1", "Pick tower 1", pygame.K_1), ("slot2", "Pick tower 2", pygame.K_2), ("slot3", "Pick tower 3", pygame.K_3),
                   ("slot4", "Pick tower 4", pygame.K_4), ("slot5", "Pick tower 5", pygame.K_5), ("slot6", "Pick tower 6", pygame.K_6),
                   ("upgrade", "Upgrade", pygame.K_e), ("sell", "Sell", pygame.K_x), ("mode", "Change target", pygame.K_t),
                   ("tabil", "Tower ability", pygame.K_f)]),
    ("WAVES", 2, [("start", "Start wave", pygame.K_g), ("skip", "Skip wave", pygame.K_n), ("speed", "Game speed", pygame.K_TAB),
                  ("pause", "Pause menu", pygame.K_p)]),
    ("CAMERA", 2, [("view", "2D / 3D view", pygame.K_v), ("zoom_in", "Zoom in", pygame.K_EQUALS), ("zoom_out", "Zoom out", pygame.K_MINUS),
                   ("cam_left", "Camera left", pygame.K_LEFT), ("cam_right", "Camera right", pygame.K_RIGHT),
                   ("cam_up", "Camera up", pygame.K_UP), ("cam_down", "Camera down", pygame.K_DOWN)]),
]
KEY_ORDER = [a for _g in KEY_GROUPS for a, _l, _k in _g[2]]
KEY_DEFAULTS = dict((a, k) for _g in KEY_GROUPS for a, _l, k in _g[2])
KEY_LABELS = dict((a, l) for _g in KEY_GROUPS for a, l, _k in _g[2])
# spare keys that also work while an action still has its default key (and nothing else uses the spare one)
KEY_EXTRA = {"chat": (pygame.K_KP_ENTER,), "zoom_in": (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_PAGEUP),
             "zoom_out": (pygame.K_KP_MINUS, pygame.K_PAGEDOWN)}
# sentences written in other places (what people on the map say, what a tower's card says) that name a key:
# (the words as they are written, the same words with the action in place of the key)
KEY_TEXT = [("press E to upgrade it. X sells it", "press %(upgrade)s to upgrade it. %(sell)s sells it"),
            ("Press F for CALL TO ARMS", "Press %(tabil)s for CALL TO ARMS")]
# keys that always do the same thing and cannot be given away
KEY_FIXED = tuple(getattr(pygame, n) for n in ("K_ESCAPE", "K_F11", "K_LGUI", "K_RGUI", "K_LSUPER", "K_RSUPER", "K_LMETA", "K_RMETA", "K_CAPSLOCK",
                                                "K_NUMLOCK", "K_SCROLLLOCK", "K_SCROLLOCK", "K_PRINTSCREEN", "K_PRINT", "K_MENU", "K_MODE",
                                                "K_PAUSE", "K_SYSREQ", "K_POWER") if hasattr(pygame, n))
KEY_NAMES = {pygame.K_SPACE: "SPACE", pygame.K_RETURN: "ENTER", pygame.K_KP_ENTER: "NUM ENTER", pygame.K_TAB: "TAB", pygame.K_BACKSPACE: "BACKSPACE",
             pygame.K_LSHIFT: "L-SHIFT", pygame.K_RSHIFT: "R-SHIFT", pygame.K_LCTRL: "L-CTRL", pygame.K_RCTRL: "R-CTRL",
             pygame.K_LALT: "L-ALT", pygame.K_RALT: "R-ALT", pygame.K_UP: "UP", pygame.K_DOWN: "DOWN", pygame.K_LEFT: "LEFT", pygame.K_RIGHT: "RIGHT",
             pygame.K_PAGEUP: "PAGE UP", pygame.K_PAGEDOWN: "PAGE DOWN", pygame.K_HOME: "HOME", pygame.K_END: "END", pygame.K_INSERT: "INSERT",
             pygame.K_DELETE: "DELETE", pygame.K_EQUALS: "=", pygame.K_MINUS: "-", pygame.K_PLUS: "+", pygame.K_COMMA: ",", pygame.K_PERIOD: ".",
             pygame.K_SLASH: "/", pygame.K_BACKSLASH: "\\", pygame.K_SEMICOLON: ";", pygame.K_QUOTE: "'", pygame.K_LEFTBRACKET: "[",
             pygame.K_RIGHTBRACKET: "]", pygame.K_BACKQUOTE: "`", pygame.K_KP_PLUS: "NUM +", pygame.K_KP_MINUS: "NUM -",
             pygame.K_KP_MULTIPLY: "NUM *", pygame.K_KP_DIVIDE: "NUM /", pygame.K_KP_PERIOD: "NUM ."}
for _i in range(10):
    KEY_NAMES[getattr(pygame, "K_KP%d" % _i)] = "NUM %d" % _i
for _i in range(1, 13):
    KEY_NAMES[getattr(pygame, "K_F%d" % _i)] = "F%d" % _i


def key_ok(k):
    """can this key be given to an action?"""
    if not isinstance(k, int) or isinstance(k, bool) or k in KEY_FIXED:
        return False
    return 8 <= k <= 127 or 0x40000039 <= k <= 0x400000E7     # the keys with a letter on them, or arrows / F keys / keypad / shift and friends


def key_name(k):
    """a short name you can read for a key: E, SPACE, L-SHIFT"""
    nm = KEY_NAMES.get(k)
    if nm:
        return nm
    if isinstance(k, int) and 33 <= k < 127:
        return chr(k).upper()
    try:
        nm = pygame.key.name(k).upper()
    except Exception:
        nm = ""
    return nm[:10] or "KEY %s" % k


def clean_keys(got):
    """-> {action: key} with every action in it.  Missing or broken entries get their default; no key is used twice."""
    got = got if isinstance(got, dict) else {}
    out, used, todo = {}, set(), []
    for a in KEY_ORDER:
        k = got.get(a)
        if key_ok(k) and k not in used:
            out[a] = k
            used.add(k)
        else:
            todo.append(a)
    for a in todo:
        spare = [KEY_DEFAULTS[a]] + [KEY_DEFAULTS[b] for b in KEY_ORDER] + [getattr(pygame, "K_F%d" % i) for i in range(1, 11)]
        for k in spare:
            if k not in used:
                out[a] = k
                used.add(k)
                break
    return out


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mix_col(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def scale_col(c, k):
    return (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)))


def ease_out(t):
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def poly(x, y, r, n, rot=0.0):
    return [(x + math.cos(rot + i * TAU / n) * r, y + math.sin(rot + i * TAU / n) * r) for i in range(n)]


def star_pts(x, y, r, n, rot=0.0, inner=0.45):
    out = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else r * inner
        a = rot + i * math.pi / n
        out.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    return out


# ---------------------------------------------------------------- text
_fonts = {}
_text_cache = {}
_glow_text_cache = {}
_glow_cache = {}
_panel_cache = {}
_ring_cache = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        f = _fonts[size] = pygame.font.Font(None, size)
    return f


def text_surf(txt, size, col):
    key = (txt, size, col)
    sf = _text_cache.get(key)
    if sf is None:
        if len(_text_cache) > 1200:
            _text_cache.clear()
        sf = _text_cache[key] = font(size).render(txt, True, col)
    return sf


def draw_text(s, txt, size, col, x, y, align="c"):
    sf = text_surf(str(txt), size, col)
    r = sf.get_rect()
    if align == "c":
        r.center = (int(x), int(y))
    elif align == "l":
        r.midleft = (int(x), int(y))
    else:
        r.midright = (int(x), int(y))
    s.blit(sf, r)
    return r


def draw_glow_text(s, txt, size, col, x, y):
    key = (txt, size, col)
    got = _glow_text_cache.get(key)
    if got is None:
        if len(_glow_text_cache) > 80:
            _glow_text_cache.clear()
        base = font(size).render(txt, True, col)
        w, h = base.get_size()
        pad = max(10, size // 3)
        big = pygame.Surface((w + pad * 2, h + pad * 2))
        big.fill((0, 0, 0))
        big.blit(font(size).render(txt, True, scale_col(col, 0.5)), (pad, pad))
        small = pygame.transform.smoothscale(big, (max(1, big.get_width() // 7), max(1, big.get_height() // 7)))
        blur = pygame.transform.smoothscale(small, big.get_size())
        got = _glow_text_cache[key] = (base, blur, pad)
    base, blur, pad = got
    r = base.get_rect(center=(int(x), int(y)))
    if GFX["glow"]:
        s.blit(blur, (r.x - pad, r.y - pad), special_flags=pygame.BLEND_RGB_ADD)
        s.blit(blur, (r.x - pad, r.y - pad), special_flags=pygame.BLEND_RGB_ADD)
    s.blit(base, r)
    return r


def wrap(txt, size, width):
    f = font(size)
    out, line = [], ""
    for word in txt.split(" "):
        test = (line + " " + word).strip()
        if f.size(test)[0] <= width or not line:
            line = test
        else:
            out.append(line)
            line = word
    if line:
        out.append(line)
    return out


# ---------------------------------------------------------------- glow + panels
def glow(s, x, y, r, col, k=1.0):
    """soft additive light"""
    if not GFX["glow"]:
        return
    r = int(r)
    if r > 96:
        r = min(320, r // 16 * 16)
    else:
        r = max(8, r // 4 * 4)
    if x + r < 0 or y + r < 0 or x - r > W or y - r > H:
        return
    c = (min(255, int(col[0] * k)) >> 4, min(255, int(col[1] * k)) >> 4, min(255, int(col[2] * k)) >> 4)
    key = (r, c)
    g = _glow_cache.get(key)
    if g is None:
        if len(_glow_cache) > 400:
            _glow_cache.clear()
        if r > 64:
            # big glows are a small one stretched: quick to make
            small = _glow_cache.get((64, c))
            if small is None:
                small = _make_glow(64, c)
                _glow_cache[(64, c)] = small
            g = pygame.transform.smoothscale(small, (r * 2, r * 2))
        else:
            g = _make_glow(r, c)
        _glow_cache[key] = g
    s.blit(g, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


def _make_glow(r, c):
    g = pygame.Surface((r * 2, r * 2))
    n = max(4, r // 2)
    for i in range(n, 0, -1):
        f = i / n
        a = (1 - f) ** 2 * 0.6 * 16
        pygame.draw.circle(g, (min(255, int(c[0] * a)), min(255, int(c[1] * a)), min(255, int(c[2] * a))), (r, r), int(r * f) + 1)
    return g


def panel(s, rect, fill=PANEL, alpha=230, border=LINE, rad=12, bw=2):
    if alpha >= 255:
        pygame.draw.rect(s, fill, rect, border_radius=rad)
    else:
        key = (rect.w, rect.h, fill, alpha, rad)
        p = _panel_cache.get(key)
        if p is None:
            if len(_panel_cache) > 200:
                _panel_cache.clear()
            p = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            pygame.draw.rect(p, fill + (alpha,), p.get_rect(), border_radius=rad)
            _panel_cache[key] = p
        s.blit(p, rect.topleft)
    if bw:
        pygame.draw.rect(s, border, rect, bw, border_radius=rad)


def range_ring(s, x, y, r, col):
    r = int(r)
    key = (r, col)
    g = _ring_cache.get(key)
    if g is None:
        if len(_ring_cache) > 120:
            _ring_cache.clear()
        g = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(g, col + (26,), (r + 2, r + 2), r)
        pygame.draw.circle(g, col + (150,), (r + 2, r + 2), r, 2)
        _ring_cache[key] = g
    s.blit(g, (int(x) - r - 2, int(y) - r - 2))


def draw_star(s, x, y, r, on, col=GOLD):
    pts = star_pts(x, y, r, 5, -math.pi / 2, 0.42)
    if on:
        pygame.draw.polygon(s, col, pts)
    else:
        pygame.draw.polygon(s, (30, 36, 66), pts)
        pygame.draw.polygon(s, DIM, pts, 1)


# ---------------------------------------------------------------- sound (made from maths, no files needed)
SR = 22050


def _tone(dur, f0, f1=None, wave="sq", vol=0.5, decay=2.0, noise=0.0):
    if f1 is None:
        f1 = f0
    n = max(1, int(SR * dur))
    out = array.array("h")
    ph = 0.0
    rnd = random.Random(int(f0 * 7 + dur * 1000))
    for i in range(n):
        t = i / n
        ph += (f0 + (f1 - f0) * t) / SR
        p = ph % 1.0
        if wave == "sq":
            v = 0.7 if p < 0.5 else -0.7
        elif wave == "saw":
            v = 2 * p - 1
        elif wave == "tri":
            v = 4 * abs(p - 0.5) - 1
        else:
            v = math.sin(TAU * p)
        if noise:
            v = v * (1 - noise) + rnd.uniform(-1, 1) * noise
        env = (1 - t) ** decay * min(1.0, i / 80.0)
        out.append(int(clamp(v * env * vol, -1, 1) * 30000))
    return out


def _cat(*arrs):
    out = array.array("h")
    for a in arrs:
        out.extend(a)
    return out


def _music():
    """a short dark loop: bass + arpeggio"""
    bpm = 104
    step = 60.0 / bpm / 2
    ns = int(SR * step)
    chords = [(110.0, (220.0, 261.6, 329.6)), (87.3, (174.6, 220.0, 261.6)), (98.0, (196.0, 246.9, 293.7)), (82.4, (164.8, 196.0, 246.9))]
    out = array.array("h")
    sin = math.sin
    for bass, arp in chords:
        for i in range(8):
            f = arp[(i * 2) % 3] * (2 if i % 4 == 3 else 1)
            for k in range(ns):
                t = k / ns
                tt = k / SR
                v = sin(TAU * bass * tt) * 0.30 * (1 - t * 0.5 if i % 2 == 0 else 0.45)
                v += (4 * abs((f * tt) % 1.0 - 0.5) - 1) * 0.16 * (1 - t) ** 1.5
                out.append(int(v * min(1.0, k / 200.0) * min(1.0, (ns - k) / 200.0) * 24000))
    return out


class Audio:
    def __init__(self):
        global SR
        self.ok = False
        self.snd = {}
        self.last = {}
        self.vol = 0.7
        self.mvol = 0.35
        self.music = None
        self.mch = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            freq, fmt, ch = pygame.mixer.get_init()
            if fmt != -16:
                return
            SR = freq
            self.ch = ch
            pygame.mixer.set_num_channels(24)
            self.build()
            self.ok = True
        except Exception:
            self.ok = False

    def make(self, arr):
        if self.ch == 2:
            st = array.array("h")
            for v in arr:
                st.append(v)
                st.append(v)
            arr = st
        return pygame.mixer.Sound(buffer=arr.tobytes())

    def build(self):
        T = _tone
        defs = {
            "click": T(.05, 900, 600, "sq", .22),
            "place": T(.13, 300, 720, "tri", .5),
            "upgrade": _cat(T(.07, 520, None, "tri", .45), T(.07, 780, None, "tri", .45), T(.14, 1040, None, "tri", .45)),
            "sell": T(.16, 700, 240, "tri", .4),
            "error": T(.13, 160, 120, "sq", .3),
            "shoot": T(.06, 1150, 480, "sq", .13),
            "scatter": T(.09, 520, 200, "saw", .18, 2.0, .5),
            "mortar": T(.18, 230, 90, "sin", .4),
            "boom": T(.34, 130, 40, "sin", .55, 2.4, .65),
            "rail": T(.24, 1900, 280, "saw", .26),
            "zap": T(.12, 1500, 700, "sq", .17, 2.0, .4),
            "pop": T(.06, 420, 150, "tri", .2, 2.0, .3),
            "leak": T(.32, 210, 70, "sq", .5),
            "wave": _cat(T(.10, 440, None, "sq", .3), T(.10, 554, None, "sq", .3), T(.2, 659, None, "sq", .3)),
            "clear": _cat(T(.09, 523, None, "tri", .4), T(.09, 659, None, "tri", .4), T(.09, 784, None, "tri", .4), T(.22, 1047, None, "tri", .4)),
            "card": T(.22, 600, 1250, "sin", .4),
            "freeze": T(.42, 2100, 380, "sin", .3, 1.6, .2),
            "strike": T(.55, 95, 34, "sin", .8, 2.0, .6),
            "boss": _cat(T(.3, 110, 70, "saw", .5), T(.5, 82, 50, "saw", .5)),
            "emp": T(.36, 300, 1600, "sq", .26, 1.4, .3),
            "clock": T(.3, 400, 1400, "saw", .28, 1.2),
            "win": _cat(T(.12, 523, None, "tri", .45), T(.12, 659, None, "tri", .45), T(.12, 784, None, "tri", .45), T(.12, 1047, None, "tri", .45), T(.4, 1319, None, "tri", .45)),
            "quack": _cat(T(.07, 620, 880, "saw", .35, 1.0), T(.10, 760, 480, "saw", .35, 1.5)),
            "meow": _cat(T(.12, 700, 1100, "tri", .4, 0.6), T(.22, 1100, 600, "tri", .4, 1.4)),
            "ding": T(.5, 1760, None, "sin", .4, 3.0),
            "chat": T(.05, 1300, 1700, "sin", .25),
            "talk": _cat(T(.04, 500, 640, "sq", .16), T(.04, 640, 520, "sq", .16), T(.05, 560, 700, "sq", .16)),
            "levelup": _cat(T(.1, 660, None, "tri", .4), T(.1, 880, None, "tri", .4), T(.1, 1100, None, "tri", .4), T(.3, 1320, 1760, "tri", .4)),
            "bubble": T(.1, 500, 1400, "sin", .25, 1.0),
            "slash": T(.09, 1500, 300, "saw", .2, 1.5, .5),
            "crash": T(.5, 160, 30, "saw", .6, 1.6, .7),
            "secret": _cat(T(.09, 784, None, "tri", .4), T(.09, 988, None, "tri", .4), T(.09, 1175, None, "tri", .4), T(.09, 1568, None, "tri", .4), T(.35, 2093, None, "sin", .4)),
            "jump": T(.17, 250, 640, "sin", .32, 1.3),                                  # boing
            "land": T(.08, 170, 80, "sin", .3, 2.0, .25),
            "censor": _cat(T(.17, 150, 128, "sq", .46, 0.35, .22), T(.15, 118, 42, "sin", .85, 1.7, .2)),      # a curse word was blocked: buzz + thunk
            "censor2": _cat(T(.11, 176, 150, "tri", .3, 0.6, .1), T(.10, 104, 52, "sin", .42, 2.0)),       # ...in someone else's message (softer)
            "lose": _cat(T(.2, 392, None, "saw", .4), T(.2, 330, None, "saw", .4), T(.2, 262, None, "saw", .4), T(.6, 196, 98, "saw", .4)),
        }
        for k, arr in defs.items():
            self.snd[k] = self.make(arr)
        self.music = self.make(_music())

    def play(self, name, vol=1.0, gap=45):
        if not self.ok or self.vol <= 0.001:
            return
        now = pygame.time.get_ticks()
        if now - self.last.get(name, -9999) < gap:
            return
        self.last[name] = now
        sd = self.snd.get(name)
        if sd is not None:
            sd.set_volume(clamp(self.vol * vol, 0, 1))
            sd.play()

    def set_music(self, v):
        self.mvol = v
        if not self.ok or self.music is None:
            return
        try:
            self.music.set_volume(v * 0.5)
            if v > 0.001 and self.mch is None:
                self.mch = self.music.play(loops=-1)
            elif v <= 0.001 and self.mch is not None:
                self.mch.stop()
                self.mch = None
        except Exception:
            pass


# ---------------------------------------------------------------- save file
def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


SAVE_NAME = "neon_bastion_save.json"
DEFAULT_SAVE = {
    "version": 2,
    "name": "",
    "settings": {"sfx": 0.7, "music": 0.35, "shake": True, "glow": True, "numbers": True, "ehp": True, "auto": False, "fps": False, "fullscreen": False,
                 "view3d": True, "ranges": True, "boxes": True, "detail": 2, "names": True, "sens": 1.0},
    "color": 0, "skin": 0, "diff": "normal",
    "coins": 0, "xp": 0,
    "owned": ["blaster", "blade", "rail"],
    "loadout": ["blaster", "blade", "rail"],
    "perks": ["overcharge"], "eq_perks": ["overcharge"],     # normal perks: owned / equipped (they stack)
    "abils": ["sword"], "eq_abils": ["sword"],               # ability perks: owned / equipped (2 at most)
    "tperks": [], "eq_tperks": {},                           # tower perks: owned / {tower: perk}
    "paint": {},                                             # tower -> paint number
    "etowers": {},                                           # event tower -> "og" or "ripoff"
    "events": {},                                            # secret event -> the time you unlocked it
    "edone": {},                                             # event -> times beaten
    "quests": {},                                            # side quest progress
    "npcs": [],                                              # npcs you talked to
    "titles": ["rookie"], "title": "rookie",
    "seen": [],                                              # videos watched, tips shown
    "stars": {},        # "map:difficulty" -> best stars
    "best": {},         # "map:difficulty" -> best wave reached
    "stats": {"kills": 0, "games": 0, "wins": 0, "towers": 0, "bosses": 0, "mpwins": 0, "talks": 0},
    "upd_code": "",     # the update code this PC shares with your other PC ("" = updates over Wi-Fi are off)
    "upd_ip": "",       # the other PC's address, if you typed it in
    "upd_last": "",     # where the other PC was the last time it answered
    "keys": {},         # action -> key (pygame key code), see KEY_GROUPS.  Anything missing gets its default.
}
OLD_DIFF = {"easy": "normal", "normal": "hard", "hard": "insane"}
OLD_MAPS = {"0": "first", "1": "horizon", "2": "cross", "3": "core"}


def save_path():
    return os.environ.get("NB_SAVE") or os.path.join(base_dir(), SAVE_NAME)


def load_save():
    data = json.loads(json.dumps(DEFAULT_SAVE))
    try:
        with open(save_path(), "r", encoding="utf-8") as fh:
            got = json.load(fh)
        if isinstance(got, dict):
            old = got.get("version", 1) == 1
            for k, v in got.items():
                if k == "version":
                    continue
                if k in data and isinstance(data[k], dict) and isinstance(v, dict):
                    data[k].update(v)
                elif k in data and type(v) is type(data[k]):
                    data[k] = v
            if old:                     # a save from version 1: keep the progress, move it to the new names
                if isinstance(got.get("perk"), str):
                    data["eq_perks"] = [got["perk"]]
                if isinstance(got.get("abil"), str):
                    data["eq_abils"] = [got["abil"]]
                data["diff"] = OLD_DIFF.get(got.get("diff"), "normal")
                for key in ("stars", "best"):
                    conv = {}
                    for k, v in (got.get(key) or {}).items():
                        a, _, b = str(k).partition(":")
                        if a in OLD_MAPS and b in OLD_DIFF and isinstance(v, int):
                            conv["%s:%s" % (OLD_MAPS[a], OLD_DIFF[b])] = v
                    data[key] = conv
    except Exception:
        pass
    try:
        data["color"] = clamp(int(data["color"]), 0, len(PLAYER_COLORS) - 1)
        data["skin"] = clamp(int(data["skin"]), 0, len(CORE_SKINS) - 1)
    except Exception:
        data["color"] = data["skin"] = 0
    if data["diff"] not in ("normal", "hard", "insane"):
        data["diff"] = "normal"
    data["name"] = clean_name(data["name"])
    data["keys"] = clean_keys(data.get("keys"))
    return data


def clean_name(txt, n=14):
    out = "".join(ch for ch in str(txt) if 32 <= ord(ch) < 127)
    return out.strip()[:n]


def write_save(data):
    try:
        path = save_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, path)
    except Exception:
        pass


# ---------------------------------------------------------------- chat: the word filter
# Words that must not show up in chat are swapped for comic symbols.  The lists live in ONE place: the three strings below
# (words with a space between them), plus an optional file "neon_bastion_words.txt" next to the game:
#     word      a whole word (endings like -s, -ed, -ing count too)
#     *word     a strong one: it also counts INSIDE a longer word
#     +word     an innocent word that must never be blocked (with its endings)
# The filter also reads words written with look-alike signs (0 o, 1 i or l, 3 e, 4 a, 5 s, 7 t, @ a, $ s, ! i), with
# held-down letters, and spelled out with dots, spaces or dashes between the letters.
# (the two lists are stored letter-shifted, so nobody reads a page of swear words by opening this file)
def _r13(txt):
    return "".join(chr((ord(c) - 97 + 13) % 26 + 97) if "a" <= c <= "z" else c for c in txt)


CURSE_WORDS = _r13("nefr nff onfgneq ovngpu obare ogpu ohyypenc puvax pbpx pbba phz qnza qvpx qvpxurnq qvyqb qbhpur qbhpuront qlxr rssvat snt sntf spx spxvat sxvat shx tbqqnza tbbx tgsb ubbxre wvmm xvxr xlf yzsnb cnxv cvff cevpx chffl ergneq fxnax fgsh gvg gvggvrf genaal gjng jnax jnaxre jrgonpx jgs")
CURSE_STEMS = _r13("nefrubyr nffubyr onqnff ovbgpu ovgpu phag qhzonff snttbg sngnff spx shpx shx wnpxnff zbgures avttn avttre cuhpx fuvg fulg fyhg fznegnff juber")
CURSE_ALLOW = "assess cocker cocky cumin niggle niggling pricked pricking scunthorpe shiitake shitake snigger titer"
WORDS_NAME = "neon_bastion_words.txt"
CHAT_MAX = 80                            # how many letters you can type in one chat line
CEN_A, CEN_B = "\x01", "\x02"            # in a chat line: what stands between these two was blocked (drawn bold and red)
GRAWL = "!@#$%&*?^"
_LEET = {"0": "o", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
_CEN = {"whole": None, "stem": None, "allow": set(), "ok": None, "n": 0}
_SPACED = re.compile(r"(?<![a-z])[a-z](?:[ ._\-*,'/]{1,2}[a-z](?![a-z])){2,}")
_TOKEN = re.compile(r"[a-z]+")
_RAWGRAWL = re.compile("[" + re.escape(GRAWL) + "]{4,}")
_ENDINGS = r"(?:s|es|ed|d|er|r|ers|rs|ing|in|ings|y|ies|z)?"


def _stretch(word, strong=False):
    """a pattern for the word that also takes held-down letters: 'boo' fits 'boo' and 'booooo' but not 'bo'.
    A strong word takes any doubled letter too ('bboo'); a normal one needs a letter three times or more, so that
    a different word that only doubles a letter is left alone"""
    out, i = [], 0
    while i < len(word):
        j = i
        while j < len(word) and word[j] == word[i]:
            j += 1
        ch = re.escape(word[i])
        if j - i > 1:
            out.append(ch + "{%d,}" % (j - i))
        elif strong:
            out.append(ch + "+")
        else:
            out.append(ch + "(?:" + ch + "{2,})?")
        i = j
    return "".join(out)


def set_curse_words(whole="", stems="", allow=""):
    """tell the filter which words to block (three strings, words with a space between them)"""
    def words(txt):
        return sorted(set(w for w in re.split(r"[^a-z]+", str(txt).lower()) if len(w) >= 2), key=lambda w: (-len(w), w))
    ws, ss = words(whole), words(stems)
    pats = [_stretch(w) for w in ws] + [_stretch(w, True) for w in ss]
    _CEN["whole"] = re.compile("(?:" + "|".join(pats) + ")" + _ENDINGS) if pats else None
    _CEN["stem"] = re.compile("|".join(_stretch(w, True) for w in ss)) if ss else None
    _CEN["allow"] = set(words(allow))
    _CEN["ok"] = re.compile("(?:" + "|".join(re.escape(w) for w in words(allow)) + ")" + _ENDINGS) if words(allow) else None
    _CEN["n"] = len(ws) + len(ss)


def load_curse_words():
    """the lists above, plus the words file next to the game if there is one"""
    whole, stems, allow = [CURSE_WORDS], [CURSE_STEMS], [CURSE_ALLOW]
    try:
        path = os.environ.get("NB_WORDS") or os.path.join(base_dir(), WORDS_NAME)
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for ln in fh.read(200000).splitlines()[:5000]:
                ln = ln.split("#")[0].strip().lower()
                if ln.startswith("*"):
                    stems.append(ln[1:])
                elif ln.startswith("+"):
                    allow.append(ln[1:])
                elif ln:
                    whole.append(ln)
    except Exception:
        pass
    set_curse_words(" ".join(whole), " ".join(stems), " ".join(allow))


def _wordch(ch):
    return "a" <= ch <= "z" or ch in _LEET or ch == "1"


def _cnorm(low, one):
    """letters that were swapped for look-alikes become letters again:  0 o   1 i (or l)   3 e   4 a   5 s   7 t   @ a   $ s   ! i"""
    out = []
    n = len(low)
    for i, ch in enumerate(low):
        if "a" <= ch <= "z":
            out.append(ch)
        elif ch == "1":
            out.append(one)
        elif ch in _LEET:
            out.append(_LEET[ch])
        elif ch == "!" and 0 < i < n - 1 and _wordch(low[i - 1]) and _wordch(low[i + 1]):
            out.append("i")         # only in the middle of a word: "wow!" stays "wow"
        else:
            out.append(ch if ch == " " or not ch.isalpha() else " ")
    return "".join(out)


def curse_spans(text):
    """-> [(start, end)]: the parts of this text that are blocked words"""
    whole, stem, okre = _CEN["whole"], _CEN["stem"], _CEN["ok"]
    if whole is None or not text:
        return []
    low = text.lower()
    hits = []
    for one in ("i", "l"):
        nt = _cnorm(low, one)
        for m in _TOKEN.finditer(nt):
            a, b = m.span()
            raw = low[a:b]
            if not any("a" <= ch <= "z" for ch in raw):         # only numbers and signs ("455", "$100"): never a word
                continue
            if okre is not None and (okre.fullmatch(m.group()) or okre.fullmatch(raw)):
                continue
            if whole.fullmatch(m.group()) or (stem is not None and stem.search(m.group())):
                hits.append((a, b))
        # spelled out with dots, spaces or dashes between single letters
        for m in _SPACED.finditer(nt):
            a, b = m.span()
            joined = "".join(ch for ch in m.group() if "a" <= ch <= "z")
            if not any("a" <= ch <= "z" for ch in low[a:b]) or (okre is not None and okre.fullmatch(joined)):
                continue
            if whole.fullmatch(joined) or (stem is not None and stem.search(joined)):
                hits.append((a, b))
    hits.sort()
    out = []
    for a, b in hits:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def grawlix(word, n=0):
    """comic symbols instead of a word: as long as the word (4 at least), and always the same ones for the same word"""
    h = zlib.crc32(str(word).lower().encode("utf-8", "ignore")) & 0x7FFFFFFF
    out, last = [], ""
    for _ in range(max(4, n or len(word))):
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        ch = GRAWL[(h >> 16) % len(GRAWL)]
        if ch == last:
            ch = GRAWL[(GRAWL.index(ch) + 1) % len(GRAWL)]
        out.append(ch)
        last = ch
    return "".join(out)


def rich_parts(txt):
    """a chat line -> [(text, blocked?)]"""
    out = []
    for i, bit in enumerate(str(txt).replace(CEN_B, CEN_A).split(CEN_A)):
        if bit:
            out.append((bit, i % 2 == 1))
    return out


def _censor_plain(txt):
    out, pos, n = [], 0, 0
    spans = curse_spans(txt)
    for m in _RAWGRAWL.finditer(txt):               # symbols that arrived without their marks (somebody stripped them on the way)
        if len(set(m.group())) >= 3 and not any(a < m.end() and m.start() < b for a, b in spans):
            spans.append(m.span())
    for a, b in sorted(spans):
        out.append(txt[pos:a])
        word = txt[a:b]
        out.append(CEN_A + (word if not any(ch.isalnum() for ch in word) else grawlix(word)) + CEN_B)
        pos = b
        n += 1
    out.append(txt[pos:])
    return "".join(out), n


def censor(txt):
    """-> (the text with every blocked word swapped for symbols and marked, how many there are).
    Safe to run twice: what is already marked stays as it is."""
    out, n = [], 0
    for bit, marked in rich_parts(txt):
        if marked:
            if any(ch.isalnum() or ch == " " for ch in bit):      # marked but still readable: never trust it
                bit = grawlix(bit)
            out.append(CEN_A + bit + CEN_B)
            n += 1
        else:
            t2, k = _censor_plain(bit)
            out.append(t2)
            n += k
    return "".join(out), n


def clean_chat(txt, n=80):
    """a chat line that is safe to keep: plain letters, at most n of them, and the marks around blocked words in pairs"""
    out, left, inside = [], n, False
    for ch in str(txt)[:600]:
        if ch == CEN_A and not inside:
            inside = True
            out.append(ch)
        elif ch == CEN_B and inside:
            inside = False
            out.append(ch)
        elif 32 <= ord(ch) < 127 and left > 0:
            out.append(ch)
            left -= 1
    if inside:
        out.append(CEN_B)
    return "".join(out).replace(CEN_A + CEN_B, "").strip()


def safe_name(txt, n=14):
    """a player's name as OTHER people may see it: a name with a blocked word in it becomes PLAYER"""
    nm = clean_name(txt, n)
    return "PLAYER" if (nm and censor(nm)[1]) else nm


load_curse_words()


# ---------------------------------------------------------------- chat: text with blocked words in it
_bfonts = {}
_rich_cache = {}
CEN_RED = (255, 62, 70)
CEN_BOX = (96, 8, 20)


def font_b(size):
    f = _bfonts.get(size)
    if f is None:
        f = _bfonts[size] = pygame.font.Font(None, size)
        f.set_bold(True)
    return f


def rich_len(txt):
    return len(txt) - txt.count(CEN_A) - txt.count(CEN_B)


def rich_width(txt, size):
    w = 0
    for bit, marked in rich_parts(txt):
        w += (font_b(size).size(bit)[0] + 8) if marked else font(size).size(bit)[0]
    return w


def rich_cut(txt, n):
    """the first n letters of a chat line (the marks do not count and stay in pairs)"""
    out, inside = [], False
    for ch in txt:
        if ch == CEN_A:
            inside = True
        elif ch == CEN_B:
            inside = False
        elif n <= 0:
            break
        else:
            n -= 1
        out.append(ch)
    if inside:
        out.append(CEN_B)
    return "".join(out)


def rich_wrap(txt, size, width):
    """like wrap(), for chat lines"""
    out, line = [], ""
    for word in txt.split(" "):
        test = (line + " " + word).strip()
        if rich_width(test, size) <= width or not line:
            line = test
        else:
            out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def draw_rich(s, txt, size, col, x, y, k=1.0):
    """draw a chat line from (x, y) to the right.  Blocked words are bold, bright red, on a dark red box.  -> where it ends"""
    x = int(x)
    for bit, marked in rich_parts(txt):
        if not marked:
            x = draw_text(s, bit, size, col, x, y, "l").right
            continue
        key = (bit, size, round(k, 1))
        sf = _rich_cache.get(key)
        if sf is None:
            if len(_rich_cache) > 300:
                _rich_cache.clear()
            t = font_b(size).render(bit, True, scale_col(CEN_RED, k))
            sf = pygame.Surface((t.get_width() + 6, t.get_height() + 2), pygame.SRCALPHA)
            pygame.draw.rect(sf, scale_col(CEN_BOX, k) + (255,), sf.get_rect(), border_radius=4)
            pygame.draw.rect(sf, scale_col(CEN_RED, k * 0.75) + (255,), sf.get_rect(), 1, border_radius=4)
            sf.blit(t, (3, 1))
            _rich_cache[key] = sf
        s.blit(sf, (x + 1, int(y) - sf.get_height() // 2))
        x += sf.get_width() + 2
    return x


def rich_split(txt, n):
    """a chat line cut after n letters -> (the first part, the rest), both with their marks in pairs"""
    head = rich_cut(txt, n)
    inside, seen, i = False, 0, 0
    while i < len(txt) and (seen < n or txt[i] == CEN_B):
        ch = txt[i]
        if ch == CEN_A:
            inside = True
        elif ch == CEN_B:
            inside = False
        else:
            seen += 1
        i += 1
    tail = txt[i:]
    return head, (CEN_A + tail if inside else tail)


def chat_wrap(txt, size, width):
    """rich_wrap(), and a word that is too long for one line is cut into pieces"""
    out = []
    for ln in rich_wrap(txt, size, width):
        while rich_width(ln, size) > width and rich_len(ln) > 1:
            n = rich_len(ln) - 1
            while n > 1 and rich_width(rich_cut(ln, n), size) > width:
                n -= 1
            head, ln = rich_split(ln, n)
            out.append(head)
        if ln:
            out.append(ln)
    return out


# ======================================================================
#  GAME DATA  -  towers, perks, enemies, maps.  Change numbers here.
# ======================================================================
def _lv(base, *ups):
    """each level = the level before it + the changes"""
    out = [dict(base)]
    for u in ups:
        d = dict(out[-1])
        d.update(u)
        out.append(d)
    return out


# place: "G" ground only, "C" cliff only, "B" both, "P" on the road (path towers)
# need = player level to unlock, price = coins to buy, cost = cash to place in a game
TOWERS = {
    "blaster": dict(lore="Standard-issue Bastion turret. Every commander's first friend.",
                    name="BLASTER", col=CYAN, place="G", atk="RANGED", tier="EARLY", need=1, price=0,
                    desc="Fast little shots. Weak alone, deadly in numbers. Twin barrels at max level.",
                    lv=_lv(dict(cost=250, dmg=10, cd=0.45, rng=130),
                           dict(cost=150, dmg=16, cd=0.43),
                           dict(cost=350, dmg=27, cd=0.40, rng=140),
                           dict(cost=800, dmg=50, cd=0.36, rng=150),
                           dict(cost=1800, dmg=56, cd=0.30, rng=160, twin=1))),
    "blade": dict(lore="Salvaged from the first Siege. It still remembers every cut.",
                  name="BLADE", col=PINK, place="G", atk="MELEE", tier="EARLY", need=1, price=0,
                  desc="Melee. A spinning blade that cuts whatever is right next to it. Tiny reach, big hits.",
                  lv=_lv(dict(cost=300, dmg=17, cd=1.00, rng=66, cleave=2),
                         dict(cost=200, dmg=26, cd=0.95),
                         dict(cost=450, dmg=44, cd=0.85, cleave=3),
                         dict(cost=1000, dmg=66, cd=0.75),
                         dict(cost=2400, dmg=105, cd=0.60, rng=72, cleave=4))),
    "rail": dict(lore="Built to watch the horizon. It has never blinked.",
                 name="RAIL", col=GOLD, place="C", atk="RANGED", tier="EARLY", need=1, price=0,
                 desc="Cliff sniper. Slow, huge range, and its shots ignore armor. Max level pierces a whole line.",
                 lv=_lv(dict(cost=400, dmg=42, cd=2.2, rng=250),
                        dict(cost=300, dmg=70, cd=2.1),
                        dict(cost=700, dmg=130, cd=1.9, rng=275),
                        dict(cost=1800, dmg=225, cd=1.7, rng=300),
                        dict(cost=4200, dmg=370, cd=1.5, rng=330, line=1))),
    "scatter": dict(lore="Loud, messy, and proud of it.",
                    name="SCATTER", col=ORANGE, place="G", atk="RANGED", tier="EARLY", need=2, price=250, aoe=True,
                    desc="Shotgun cone. Shreds swarms that bunch up. Pellets pierce at higher levels.",
                    lv=_lv(dict(cost=350, dmg=9, n=5, cd=1.00, rng=100, pierce=0),
                           dict(cost=250, dmg=11, n=6, cd=0.95),
                           dict(cost=550, dmg=14, n=7, cd=0.85, rng=108, pierce=1),
                           dict(cost=1200, dmg=20, n=8, cd=0.75),
                           dict(cost=2600, dmg=27, n=10, cd=0.65, rng=122, pierce=2))),
    "guardian": dict(lore="It asked for one job: stand in the road. It has never moved since.",
                     name="GUARDIAN", col=(120, 200, 255), place="P", atk="PATH", tier="EARLY", need=3, price=400,
                     desc="PATH TOWER. Stands on the road, blocks enemies and fights them hand to hand. Explodes when it falls, and gets back up after the wave.",
                     lv=_lv(dict(cost=350, hp=260, dmg=20, cd=0.80, rng=46, cleave=2, block=2, boom=90, brad=62),
                            dict(cost=250, hp=420, dmg=32, boom=150),
                            dict(cost=600, hp=760, dmg=58, cd=0.72, cleave=3, block=3, boom=280, brad=68),
                            dict(cost=1400, hp=1400, dmg=110, boom=560),
                            dict(cost=3200, hp=2800, dmg=220, cd=0.60, cleave=4, block=4, boom=1200, brad=78))),
    "cryo": dict(lore="Runs on coolant borrowed from the core itself.",
                 name="CRYO", col=BLUE, place="G", atk="SUPPORT", tier="EARLY", need=4, price=550, aoe=True,
                 desc="Slows every enemy in its field and chips them. Max level flash-freezes the lot.",
                 lv=_lv(dict(cost=300, slow=0.25, dmg=3, cd=1.0, rng=95),
                        dict(cost=200, slow=0.32, dmg=5, rng=105),
                        dict(cost=450, slow=0.40, dmg=9, rng=115),
                        dict(cost=900, slow=0.47, dmg=15, rng=125),
                        dict(cost=1900, slow=0.55, dmg=26, rng=135, frz=0.8))),
    "mortar": dict(lore="The cliffs shake a little every time it speaks.",
                   name="MORTAR", col=GREEN, place="C", atk="RANGED", tier="MID", need=5, price=700, aoe=True,
                   desc="Cliff artillery. Lobs shells that explode on groups. Max level leaves fire behind.",
                   lv=_lv(dict(cost=600, dmg=40, cd=2.8, rng=230, splash=55),
                          dict(cost=400, dmg=62, cd=2.7, splash=60),
                          dict(cost=900, dmg=105, cd=2.5, rng=250, splash=66),
                          dict(cost=2000, dmg=185, cd=2.3, rng=270, splash=74),
                          dict(cost=4200, dmg=300, cd=2.0, rng=295, splash=84, burn=1))),
    "harvester": dict(lore="Turns stray neon into cash. Nobody asks how.",
                      name="HARVESTER", col=YELLOW, place="G", atk="ECONOMY", tier="EARLY", need=6, price=900,
                      desc="Does not fight. Pays you cash after every wave. You can own 4 in a game.",
                      lv=_lv(dict(cost=400, income=60),
                             dict(cost=350, income=130),
                             dict(cost=800, income=260),
                             dict(cost=1700, income=500),
                             dict(cost=3500, income=950))),
    "sentinel": dict(lore="An old arena pilot's ship, bolted down and still fighting.",
                     name="SENTINEL", col=MINT, place="B", atk="BOTH", tier="MID", need=7, price=1100,
                     desc="Shoots at range AND swings a blade at anything close. Goes on ground or cliffs.",
                     lv=_lv(dict(cost=700, dmg=22, cd=0.60, rng=140, mdmg=40, mcd=1.2, mrng=66, cleave=2),
                            dict(cost=500, dmg=33, cd=0.57, mdmg=62),
                            dict(cost=1100, dmg=55, cd=0.52, rng=150, mdmg=108, cleave=3),
                            dict(cost=2300, dmg=108, cd=0.46, rng=160, mdmg=215),
                            dict(cost=4800, dmg=205, cd=0.40, rng=175, mdmg=450, mcd=1.0, cleave=4))),
    "mechanic": dict(lore="Fixes anything. Complains the whole time.",
                     name="MECHANIC", col=(90, 255, 150), place="B", atk="SUPPORT", tier="MID", need=8, price=1400,
                     desc="Support. Its drones repair path towers in its field and shake stuns off towers faster. From level 3 it rebuilds fallen path towers mid-wave.",
                     lv=_lv(dict(cost=600, heal=14, cleanse=0.30, rng=120),
                            dict(cost=450, heal=24),
                            dict(cost=1000, heal=42, cleanse=0.45, rng=135, revive=12),
                            dict(cost=2100, heal=75, revive=9),
                            dict(cost=4200, heal=140, cleanse=0.70, rng=155, revive=6))),
    "bulwark": dict(lore="A wall with opinions.",
                    name="BULWARK", col=(200, 210, 230), place="P", atk="PATH", tier="MID", need=9, price=1700,
                    desc="PATH TOWER. A huge spiked wall. Holds a whole crowd and hurts everything that hits it. Explodes when it falls, back after the wave.",
                    lv=_lv(dict(cost=600, hp=700, thorns=5, block=4, boom=70, brad=60),
                           dict(cost=450, hp=1150, thorns=8, block=5),
                           dict(cost=1000, hp=2100, thorns=15, block=6, boom=160),
                           dict(cost=2200, hp=3900, thorns=28, block=7),
                           dict(cost=4800, hp=7500, thorns=55, block=9, boom=400, brad=70))),
    "tesla": dict(lore="Its inventor was last seen as a very bright flash.",
                  name="TESLA", col=PURPLE, place="G", atk="RANGED", tier="MID", need=10, price=2100, aoe=True,
                  desc="Chain lightning that jumps between enemies. Double damage to shields.",
                  lv=_lv(dict(cost=800, dmg=32, cd=1.00, rng=120, chain=3),
                         dict(cost=550, dmg=45, cd=0.95, chain=4),
                         dict(cost=1200, dmg=72, cd=0.90, rng=130, chain=5),
                         dict(cost=2600, dmg=140, cd=0.82, chain=6),
                         dict(cost=5200, dmg=255, cd=0.70, rng=145, chain=8))),
    "summoner": dict(lore="It never leaves the core. Its goons never come back to it.",
                     name="SUMMONER", col=(255, 196, 110), place="G", atk="SUMMON", tier="MID", need=11, price=1500, aoe=False,
                     desc="Does not shoot. Sends goons out of your core, up the road. A goon and an enemy that meet trade health: the weaker one is destroyed.",
                     # ghp = goon health, cd = seconds between goons, cap = goons alive at once (per tower), gspd = how fast they walk
                     # (balanced with bal_summon.py: about as good for its price as a gun tower early on, a little behind at the top)
                     lv=_lv(dict(cost=450, ghp=60, cd=4.8, cap=3, gspd=48, rng=0),
                            dict(cost=350, ghp=120, cd=4.4, cap=4, gspd=50),
                            dict(cost=700, ghp=220, cd=4.1, gspd=52),
                            dict(cost=1400, ghp=440, cd=3.8, cap=5, gspd=54),
                            dict(cost=2800, ghp=920, cd=3.4, cap=6, gspd=56))),
    "hydra": dict(lore="Every missile is named. It will not tell you the names.",
                  name="HYDRA", col=(255, 170, 60), place="B", atk="RANGED", tier="MID", need=12, price=2500, aoe=True,
                  desc="Missile battery. Fires a salvo of homing rockets at different targets, each with a small blast. Ground or cliffs.",
                  lv=_lv(dict(cost=1000, dmg=26, n=2, cd=1.60, rng=185, splash=34),
                         dict(cost=700, dmg=38),
                         dict(cost=1500, dmg=60, n=3, rng=200, splash=38),
                         dict(cost=3200, dmg=110, cd=1.45),
                         dict(cost=6500, dmg=190, n=5, cd=1.30, rng=220, splash=44))),
    "beacon": dict(lore="Lit the day the Bastion was founded. It has never gone out.",
                   name="BEACON", col=WHITE, place="B", atk="SUPPORT", tier="MID", need=14, price=3000,
                   desc="Range support. Towers in its field see further. From level 3 it also unmasks Phantoms.",
                   lv=_lv(dict(cost=900, rbuff=0.10, rng=110),
                          dict(cost=600, rbuff=0.14),
                          dict(cost=1300, rbuff=0.18, rng=125, reveal=1),
                          dict(cost=2600, rbuff=0.22),
                          dict(cost=5000, rbuff=0.28, rng=140))),
    "reactor": dict(lore="Technically a safety violation. Technically a tower.",
                    name="REACTOR", col=(120, 255, 90), place="P", atk="PATH", tier="LATE", need=16, price=3600, aoe=True,
                    desc="PATH TOWER. A fragile core that burns everything near it, then goes off like a bomb when it breaks. Back after the wave.",
                    lv=_lv(dict(cost=900, hp=150, aura=16, rng=70, block=1, boom=300, brad=85),
                           dict(cost=650, hp=220, aura=28, boom=520),
                           dict(cost=1400, hp=340, aura=50, rng=78, boom=1000, brad=95),
                           dict(cost=3000, hp=540, aura=100, boom=2100),
                           dict(cost=6000, hp=900, aura=210, rng=88, boom=4500, brad=115))),
    "commander": dict(lore="Never fires a shot. Wins wars anyway.",
                      name="COMMANDER", col=RED, place="G", atk="SUPPORT", tier="LATE", need=18, price=4500,
                      desc="Fire-rate support. Towers in its field attack 7% faster. Press F for CALL TO ARMS: 15% for a while. More at max level.",
                      lv=_lv(dict(cost=1200, pas=0.07, act=0.15, dur=10, acd=40, rng=110),
                             dict(cost=800, rng=120, dur=12),
                             dict(cost=1700, pas=0.08, act=0.17),
                             dict(cost=3400, rng=135, dur=14),
                             dict(cost=6500, pas=0.10, act=0.22, rng=150))),
    "graviton": dict(lore="It is not pulling them back. It is pushing everything else forward.",
                     name="GRAVITON", col=(150, 90, 255), place="G", atk="SUPPORT", tier="LATE", need=20, price=6000, aoe=True,
                     desc="Every few seconds it yanks every enemy in its field backwards along the road and crushes them a little. Bosses only slow down.",
                     lv=_lv(dict(cost=2200, pull=42, dmg=40, cd=4.5, rng=120),
                            dict(cost=1500, pull=50, dmg=70),
                            dict(cost=3200, pull=60, dmg=140, cd=4.1, rng=130),
                            dict(cost=6000, pull=74, dmg=300, cd=3.8),
                            dict(cost=11000, pull=95, dmg=650, cd=3.4, rng=145))),
    "prism": dict(lore="Grown, not built. It gets angrier the longer it stares.",
                  name="PRISM", col=MAGENTA, place="G", atk="RANGED", tier="LATE", need=22, price=8000,
                  desc="A beam that gets hotter the longer it holds one target. Weak early, melts bosses when maxed.",
                  lv=_lv(dict(cost=1500, dps=28, rng=140),
                         dict(cost=1100, dps=48),
                         dict(cost=2400, dps=115, rng=150),
                         dict(cost=5000, dps=300, rng=160),
                         dict(cost=11000, dps=900, rng=170, split=1))),
    "annihilator": dict(lore="Banned in nine sectors. This is the tenth.",
                        name="ANNIHILATOR", col=(255, 120, 90), place="G", atk="RANGED", tier="LATE", need=25, price=11000, aoe=True, box=19,
                        desc="The big gun. Very slow, very expensive, erases whatever it hits and stuns the rest.",
                        lv=_lv(dict(cost=3000, dmg=240, cd=4.0, rng=200, splash=70, stun=0.3),
                               dict(cost=2200, dmg=420, cd=3.8),
                               dict(cost=4800, dmg=800, cd=3.5, rng=220, splash=80),
                               dict(cost=10000, dmg=1900, cd=3.2),
                               dict(cost=20000, dmg=4000, cd=2.8, rng=250, splash=95, stun=0.5))),
    # ---- event towers: you cannot buy these. Beat the event level to get them.
    "pumpkin": dict(lore="Carved once a year. Angry all year.",
                    name="JACK-O-CANNON", col=(255, 128, 22), place="B", atk="RANGED", tier="EVENT", need=1, price=0, aoe=True, event="haunted",
                    desc="Lobs pumpkins that burst and SCARE enemies: they turn around and run back the way they came for a moment.",
                    lv=_lv(dict(cost=1000, dmg=48, cd=2.4, rng=215, splash=58, fear=0.8),
                           dict(cost=700, dmg=74),
                           dict(cost=1500, dmg=125, cd=2.2, rng=230, splash=66, fear=1.1),
                           dict(cost=3200, dmg=225),
                           dict(cost=6400, dmg=380, cd=1.8, rng=250, splash=80, fear=1.6))),
    "snow": dict(lore="He is not jolly. He is cold and he wants everyone to know.",
                 name="SNOWBLOWER", col=(190, 230, 255), place="G", atk="RANGED", tier="EVENT", need=1, price=0, aoe=True, event="winter",
                 desc="Sprays a cone of snow. Everything in it slows down more and more until it freezes solid.",
                 lv=_lv(dict(cost=900, dps=22, rng=115, chill=0.35),
                        dict(cost=600, dps=36),
                        dict(cost=1300, dps=66, rng=125, chill=0.45),
                        dict(cost=2800, dps=130),
                        dict(cost=5600, dps=270, rng=145, chill=0.60))),
    "duck": dict(lore="Squeaks when it fires. Squeaks when it doesn't.",
                 name="RUBBER DUCK", col=(255, 214, 40), place="B", atk="RANGED", tier="EVENT", need=1, price=0, event="pond",
                 desc="Blows bubbles. Enemies caught in one float helplessly for a moment. Gets fancier with every level.",
                 lv=_lv(dict(cost=800, dmg=50, cd=1.10, rng=140, lift=0.5, n=1),
                        dict(cost=550, dmg=76, lift=0.6),
                        dict(cost=1200, dmg=130, cd=1.0, rng=150, lift=0.7),
                        dict(cost=2600, dmg=250, cd=0.9, lift=0.85),
                        dict(cost=5200, dmg=380, cd=0.8, rng=165, lift=1.0, n=2))),
    "toaster": dict(lore="Setting 7 is illegal.",
                    name="TOASTER", col=(255, 160, 80), place="G", atk="RANGED", tier="EVENT", need=1, price=0, aoe=True, event="kitchen",
                    desc="Pops burning toast onto the road. Every slice explodes and leaves a little fire. More slots, more toast.",
                    lv=_lv(dict(cost=900, dmg=34, n=2, cd=2.2, rng=200, splash=46, burn=1),
                           dict(cost=600, dmg=52),
                           dict(cost=1300, dmg=90, cd=2.0, rng=215, splash=52),
                           dict(cost=2800, dmg=160, n=3),
                           dict(cost=5600, dmg=250, n=4, cd=1.7, rng=235, splash=62))),
    "cat": dict(lore="asdfghjkl;",
                name="KEYBOARD CAT", col=(255, 150, 220), place="G", atk="MELEE", tier="EVENT", need=1, price=0, event="glitch",
                desc="Melee. Smacks things off the table: every swipe knocks enemies BACKWARDS along the road.",
                lv=_lv(dict(cost=1000, dmg=44, cd=1.6, rng=78, kb=30, cleave=3),
                       dict(cost=700, dmg=68, kb=34),
                       dict(cost=1500, dmg=120, cd=1.4, cleave=4, kb=42),
                       dict(cost=3200, dmg=230, cd=1.25, kb=50),
                       dict(cost=6400, dmg=440, cd=1.1, rng=90, cleave=6, kb=62))),
    "stonks": dict(lore="Not financial advice.",
                   name="STONKS", col=(60, 235, 130), place="G", atk="ECONOMY", tier="EVENT", need=1, price=0, event="market",
                   desc="Pays cash after every wave, but the market decides how much: anywhere from a quarter to more than double. You can own 2.",
                   lv=_lv(dict(cost=500, income=80),
                          dict(cost=400, income=170),
                          dict(cost=900, income=330),
                          dict(cost=1900, income=640),
                          dict(cost=3800, income=1200))),
    "brick": dict(lore="It never needed a charger. Not once.",
                  name="THE BRICK", col=(150, 230, 130), place="P", atk="PATH", tier="EVENT", need=1, price=0, event="quarry",
                  desc="PATH TOWER. An indestructible old phone. Does not attack. Does not care. Blocks the road almost forever.",
                  lv=_lv(dict(cost=900, hp=3000, block=3, boom=200, brad=70),
                         dict(cost=600, hp=5000),
                         dict(cost=1300, hp=9000, block=4, boom=500),
                         dict(cost=2800, hp=16000),
                         dict(cost=5500, hp=30000, block=5, boom=1500, brad=90))),
}
TOWER_ORDER = list(TOWERS)
SHOP_TOWERS = [k for k in TOWER_ORDER if not TOWERS[k].get("event")]
EVENT_TOWERS = [k for k in TOWER_ORDER if TOWERS[k].get("event")]
MAXLV = 4
PLACE_NAME = {"G": "GROUND", "C": "CLIFF", "B": "GROUND + CLIFF", "P": "ON THE ROAD"}
PLACE_SHORT = {"G": "GROUND", "C": "CLIFF", "B": "ANY", "P": "ROAD"}
PLACE_COL = {"G": GREY, "C": GOLD, "B": MINT, "P": (120, 200, 255)}
TARGET_MODES = ["FIRST", "LAST", "STRONG", "CLOSE"]
HARVESTER_MAX = 4
SUMMONER_MAX = 4            # Summoners per player (4 at top level are 24 goons on the road)
STONKS_MAX = 2
PATH_MAX = 4                # path towers per player
DEFAULT_MODE = {"prism": 2}      # starts on STRONG
CLIFF_RANGE = 0.10          # every tower on a cliff sees this much further
SUPPORT_KINDS = ("beacon", "commander", "mechanic")
NOFIGHT = ("beacon", "commander", "mechanic", "harvester", "stonks", "summoner")     # towers that never aim or shoot themselves
PAINTS = [None, CYAN, PINK, GOLD, GREEN, PURPLE, ORANGE, BLUE, MINT, RED, MAGENTA, YELLOW, WHITE, (255, 120, 90), (120, 255, 90), (90, 110, 255)]
PAINT_NAMES = ["FACTORY", "CYAN", "PINK", "GOLD", "LIME", "VIOLET", "ORANGE", "SKY", "MINT", "RED", "MAGENTA", "SUN", "WHITE", "CORAL", "ACID", "COBALT"]


def tower_cap(nplayers):
    """how many towers each player may have on the field"""
    return (20, 14, 11, 9)[clamp(nplayers, 1, 4) - 1]


def loadout_slots(level):
    return 5 if level < 8 else 6


def perk_slots(level):
    return 1 if level < 6 else 2 if level < 14 else 3


def abil_slots(level):
    return 1 if level < 10 else 2


def is_path(kind):
    return TOWERS[kind]["place"] == "P"


def tower_stats(kind, L):
    """the lines shown for one level of a tower"""
    if kind in ("harvester", "stonks"):
        return [("CASH / WAVE", "+%d" % L["income"] if kind == "harvester" else "~%d" % L["income"])]
    if kind == "summoner":
        return [("GOON HEALTH", "%d" % L["ghp"]), ("NEW GOON", "every %.1fs" % L["cd"]), ("GOONS AT ONCE", "%d" % L["cap"]), ("GOON SPEED", "%d" % L["gspd"])]
    if kind == "beacon":
        out = [("RANGE BOOST", "+%d%%" % round(L["rbuff"] * 100)), ("FIELD", "%d" % L["rng"])]
        if L.get("reveal"):
            out.append(("UNMASKS", "Phantoms"))
        return out
    if kind == "commander":
        return [("ATTACK SPEED", "+%d%%" % round(L["pas"] * 100)), ("CALL TO ARMS", "+%d%%/%ds" % (round(L["act"] * 100), L["dur"])),
                ("FIELD", "%d" % L["rng"])]
    if kind == "mechanic":
        out = [("REPAIR", "%d / s" % L["heal"]), ("STUNS", "-%d%%" % round(L["cleanse"] * 100)), ("FIELD", "%d" % L["rng"])]
        if L.get("revive"):
            out.append(("REBUILDS IN", "%ds" % L["revive"]))
        return out
    if kind == "cryo":
        out = [("SLOW", "%d%%" % round(L["slow"] * 100)), ("DAMAGE", "%d / s" % L["dmg"]), ("RANGE", "%d" % L["rng"])]
        if L.get("frz"):
            out.append(("FREEZE", "%.1fs" % L["frz"]))
        return out
    if kind == "prism":
        return [("BEAM DPS", "%d - %d" % (L["dps"], L["dps"] * 3)), ("RANGE", "%d" % L["rng"])]
    if kind == "snow":
        return [("SNOW DPS", "%d" % L["dps"]), ("CHILL", "%d%% / s" % round(L["chill"] * 100)), ("RANGE", "%d" % L["rng"])]
    if kind == "graviton":
        return [("PULL BACK", "%d" % L["pull"]), ("DAMAGE", "%d" % L["dmg"]), ("COOLDOWN", "%.1fs" % L["cd"]), ("RANGE", "%d" % L["rng"])]
    if is_path(kind):
        out = [("HEALTH", "%d" % L["hp"]), ("BLOCKS", "%d" % L["block"])]
        if "dmg" in L:
            out.append(("DAMAGE", "%d / %.2fs" % (L["dmg"], L["cd"])))
        if "thorns" in L:
            out.append(("THORNS", "%d" % L["thorns"]))
        if "aura" in L:
            out.append(("BURN", "%d / s" % L["aura"]))
        out.append(("EXPLOSION", "%d" % L["boom"]))
        return out
    out = []
    if kind in ("scatter", "hydra", "toaster") or L.get("n", 1) > 1:
        out.append(("DAMAGE", "%d x%d" % (L["dmg"], L["n"])))
    elif L.get("twin"):
        out.append(("DAMAGE", "%d x2" % L["dmg"]))
    else:
        out.append(("DAMAGE", "%d" % L["dmg"]))
    out.append(("COOLDOWN", "%.2fs" % L["cd"]))
    out.append(("RANGE", "%d" % L["rng"]))
    if kind == "sentinel":
        out.append(("BLADE", "%d / %.1fs" % (L["mdmg"], L["mcd"])))
    if "splash" in L:
        out.append(("BLAST", "%d" % L["splash"]))
    if "chain" in L:
        out.append(("JUMPS", "%d" % L["chain"]))
    if "cleave" in L and kind in ("blade", "cat"):
        out.append(("HITS", "%d" % L["cleave"]))
    if "kb" in L:
        out.append(("KNOCKBACK", "%d" % L["kb"]))
    if "fear" in L:
        out.append(("SCARE", "%.1fs" % L["fear"]))
    if "lift" in L:
        out.append(("BUBBLE", "%.1fs" % L["lift"]))
    return out


def tower_dps(kind, L):
    if kind == "prism":
        return L["dps"] * 2.0
    if kind == "snow":
        return L["dps"]
    if "aura" in L:
        return L["aura"]
    if "dmg" not in L or kind in ("cryo", "graviton"):
        return 0.0
    d = L["dmg"] * L.get("n", 1) * (2 if L.get("twin") else 1) / L["cd"]
    if kind == "sentinel":
        d += L["mdmg"] / L["mcd"]
    return d


# ---------------------------------------------------------------- perks
# normal perks: they stack.  How many you can wear grows with your level.
PERKS = {
    "overcharge": dict(name="OVERCHARGE", cat="ATTACK", need=1, price=0, mods={"dmg": 0.10}, desc="All your towers deal +10% damage."),
    "longsight": dict(name="LONG SIGHT", cat="RANGE", need=2, price=200, mods={"rng": 0.10}, desc="All your towers get +10% range."),
    "warchest": dict(name="WAR CHEST", cat="SUPPORT", need=4, price=400, mods={"startcash": 150, "bounty": 0.12},
                     desc="Start with +150 cash and earn +12% hit cash."),
    "closeq": dict(name="CLOSE QUARTERS", cat="RANGE", need=5, price=500, mods={"melee": 0.25}, desc="Melee swings and path towers reach 25% further."),
    "rapid": dict(name="RAPID CYCLE", cat="ATTACK", need=7, price=700, mods={"rate": 0.08}, desc="Attack cooldowns are 8% shorter."),
    "ironroad": dict(name="IRON ROAD", cat="SUPPORT", need=9, price=900, mods={"pathhp": 0.35}, desc="Your path towers have +35% health."),
    "eagle": dict(name="EAGLE EYE", cat="RANGE", need=11, price=1100, mods={"cliffrng": 0.20}, desc="Your towers on cliffs get +20% more range."),
    "insurance": dict(name="INSURANCE", cat="SUPPORT", need=12, price=1200, mods={"corehp": 20}, desc="The core starts with +20 health."),
    "engineer": dict(name="ENGINEER", cat="SUPPORT", need=13, price=1400, mods={"discount": 0.08, "recycle": 0.15},
                     desc="Everything costs 8% less and selling refunds 15% more."),
    "critical": dict(name="CRITICAL EYE", cat="ATTACK", need=15, price=1700, mods={"crit": 0.10}, desc="+10% chance for any hit to deal double damage."),
    "quick": dict(name="QUICK HANDS", cat="SUPPORT", need=17, price=2000, mods={"charge": 0.20}, desc="Your abilities recharge 20% faster."),
    "signal": dict(name="SIGNAL BOOST", cat="RANGE", need=19, price=2300, mods={"aura": 0.20}, desc="Your support towers' fields are 20% bigger."),
    "executioner": dict(name="EXECUTIONER", cat="ATTACK", need=21, price=2700, mods={"bossdmg": 0.35}, desc="+35% damage to bosses and elites."),
    "demolition": dict(name="DEMOLITION", cat="ATTACK", need=23, price=3200, mods={"splash": 0.20}, desc="Blasts and chain lightning reach 20% further."),
}
PERK_ORDER = list(PERKS)
CAT_COL = {"ATTACK": RED, "RANGE": GOLD, "SUPPORT": GREEN, "DEFENSE": BLUE, "ABILITY": PURPLE, "TOWER": CYAN}

# ability perks: press Q or R, click anywhere on the field.  Two at most.
ABILS = {
    "sword": dict(name="SWORD OF JUSTICE", need=1, price=0, cd=30, rad=105, col=GOLD,
                  desc="A giant blade falls from the sky and smashes everything in its circle."),
    "cryobomb": dict(name="CRYO BOMB", need=3, price=300, cd=30, rad=140, col=BLUE,
                     desc="Freezes every enemy in a big circle for 3 seconds."),
    "napalm": dict(name="NAPALM RAIN", need=6, price=600, cd=30, rad=100, col=ORANGE,
                   desc="Sets the ground on fire for 6 seconds. Best on a corner."),
    "repair": dict(name="EMERGENCY REPAIR", need=8, price=900, cd=40, rad=150, col=(90, 255, 150),
                   desc="Rebuilds and heals every path tower in the circle and shakes off stuns."),
    "blackhole": dict(name="BLACK HOLE", need=11, price=1500, cd=40, rad=130, col=PURPLE,
                      desc="Drags enemies backwards along the road for 3 seconds."),
    "laser": dict(name="ORBITAL LASER", need=14, price=2400, cd=35, rad=48, col=RED,
                  desc="A beam from orbit burns one small spot for 4 seconds. Park it on a boss."),
    "overdrive": dict(name="OVERDRIVE FIELD", need=18, price=3400, cd=45, rad=140, col=CYAN,
                      desc="Every tower in the circle attacks 35% faster for 8 seconds."),
}
ABIL_ORDER = list(ABILS)

# tower perks: each one fits exactly one tower.  One per tower.
TPERKS = {
    "triple": dict(name="TRIPLE TAP", tower="blaster", desc="Every third shot fires an extra shot."),
    "whirl": dict(name="WHIRLWIND", tower="blade", desc="Hits 2 more enemies per swing and reaches 10% further."),
    "hollow": dict(name="HOLLOW POINT", tower="rail", desc="+40% damage to enemies above 80% health."),
    "dragon": dict(name="DRAGON'S BREATH", tower="scatter", desc="Pellets set enemies on fire."),
    "laststand": dict(name="LAST STAND", tower="guardian", desc="Below 30% health it deals double damage and takes 30% less."),
    "perma": dict(name="PERMAFROST", tower="cryo", desc="Enemies in its field take +15% damage from everything."),
    "cluster": dict(name="CLUSTER SHELLS", tower="mortar", desc="Every shell scatters 3 smaller blasts."),
    "compound": dict(name="COMPOUND INTEREST", tower="harvester", desc="Pays 4% more for every wave it has been standing (up to double)."),
    "duelist": dict(name="DUELIST", tower="sentinel", desc="A blade hit makes its gun fire 30% faster for 2 seconds."),
    "medic": dict(name="FIELD MEDIC", tower="mechanic", desc="Repairs 50% faster and its field is 15% bigger."),
    "spiked": dict(name="SPIKED PLATING", tower="bulwark", desc="Thorns hit twice as hard."),
    "overvolt": dict(name="OVERVOLT", tower="tesla", desc="2 more jumps, and jumps do not lose damage."),
    "swarm": dict(name="SWARM MISSILES", tower="hydra", desc="One more rocket in every salvo."),
    "spotter": dict(name="SPOTTER", tower="beacon", desc="Towers in its field also deal +8% damage."),
    "chainr": dict(name="CHAIN REACTION", tower="reactor", desc="The explosion is 35% bigger and stuns for 1.5 seconds."),
    "drums": dict(name="WAR DRUMS", tower="commander", desc="Call to Arms lasts 40% longer and recharges 20% faster."),
    "horizon": dict(name="EVENT HORIZON", tower="graviton", desc="Pulls enemies 30% further back."),
    "focus": dict(name="FOCUS LENS", tower="prism", desc="The beam heats up twice as fast."),
    "after": dict(name="AFTERSHOCK", tower="annihilator", desc="Every blast leaves a burning crater."),
}
for _k, _p in TPERKS.items():
    _n = TOWERS[_p["tower"]]["need"]
    _p["need"] = _n + 1
    _p["price"] = int(round((150 + _n * 70) / 50.0)) * 50
TPERK_ORDER = list(TPERKS)
TPERK_OF = {}
for _k, _p in TPERKS.items():
    TPERK_OF[_p["tower"]] = _k

# ---------------------------------------------------------------- cards (pick 1 of 3 every 5 waves)
MODS0 = dict(dmg=0.0, rate=0.0, rng=0.0, cliffrng=0.0, crit=0.0, bossdmg=0.0, finisher=0.0, burn=0.0, splash=0.0, melee=0.0, aura=0.0,
             pathhp=0.0, corehp=0, aegis=0, gravity=0.0, harden=0.0, regen=0,
             bounty=0.0, discount=0.0, recycle=0.0, charge=0.0, startcash=0, cash=0)
GLOBAL_MODS = ("corehp", "aegis", "gravity", "regen")
CARDS = [
    ("ATTACK", "OVERDRIVE", "dmg", (.06, .10, .15), "Your towers deal +{p}% damage"),
    ("ATTACK", "HAIR TRIGGER", "rate", (.04, .07, .10), "Attack cooldowns are {p}% shorter"),
    ("ATTACK", "CRITICAL MASS", "crit", (.05, .08, .12), "+{p}% chance to deal double damage"),
    ("ATTACK", "FINISHER", "finisher", (.20, .35, .50), "+{p}% damage to enemies under 30% health"),
    ("ATTACK", "INCENDIARY", "burn", (.08, .12, .18), "Hits set enemies on fire for +{p}% damage"),
    ("ATTACK", "LONG REACH", "rng", (.04, .06, .09), "Your towers get +{p}% range"),
    ("ATTACK", "BIG BANG", "splash", (.10, .16, .24), "Blasts and chain lightning reach {p}% further"),
    ("DEFENSE", "REINFORCE", "corehp", (10, 15, 25), "+{v} max core health, repaired right now"),
    ("DEFENSE", "AEGIS", "aegis", (1, 2, 3), "A shield blocks the first {v} leak(s) of every wave"),
    ("DEFENSE", "GRAVITY WELL", "gravity", (.12, .18, .25), "Enemies near the core move {p}% slower"),
    ("DEFENSE", "HARDENED", "harden", (.30, .45, .60), "Your towers stay stunned {p}% shorter"),
    ("DEFENSE", "NANO REPAIR", "regen", (2, 4, 6), "Repair {v} core health after every wave"),
    ("DEFENSE", "ROADBLOCK", "pathhp", (.20, .30, .45), "Your path towers get +{p}% health"),
    ("SUPPORT", "WINDFALL", "cash", (300, 500, 800), "Get {v} cash right now"),
    ("SUPPORT", "BOUNTY", "bounty", (.10, .15, .22), "+{p}% hit cash"),
    ("SUPPORT", "DISCOUNT", "discount", (.05, .08, .12), "Towers and upgrades cost {p}% less"),
    ("SUPPORT", "RECYCLER", "recycle", (.10, .15, .25), "Selling refunds {p}% more"),
    ("SUPPORT", "QUICK CHARGE", "charge", (.12, .18, .25), "Abilities recharge {p}% faster"),
]
RARITY = [("COMMON", GREY), ("RARE", CYAN), ("EPIC", GOLD)]
CARD_EVERY = 5


# ---------------------------------------------------------------- enemies
ENEMIES = {
    "grunt": dict(name="GRUNT", hp=30, spd=50, r=10, col=PINK, leak=2, info="Basic foot soldier."),
    "runner": dict(name="RUNNER", hp=17, spd=108, r=8, col=YELLOW, leak=2, info="Fast and fragile."),
    "swarm": dict(name="SWARM", hp=8, spd=80, r=6, col=ORANGE, leak=1, info="Tiny. Comes in big packs. Use AOE."),
    "tank": dict(name="TANK", hp=170, spd=31, r=15, col=PURPLE, leak=6, armor=3, info="Slow and armored. Small hits bounce off."),
    "shield": dict(name="SHIELDER", hp=48, spd=47, r=12, col=BLUE, leak=4, shield=40, info="Its shield grows back. Tesla breaks it."),
    "splitter": dict(name="SPLITTER", hp=78, spd=45, r=13, col=GREEN, leak=4, info="Splits into three minis when it dies."),
    "mini": dict(name="MINI", hp=18, spd=84, r=7, col=GREEN, leak=1, info="What is left of a Splitter."),
    "healer": dict(name="MENDER", hp=88, spd=45, r=12, col=MINT, leak=4, info="Heals enemies around it. Kill it first."),
    "blinker": dict(name="BLINKER", hp=52, spd=57, r=10, col=MAGENTA, leak=4, info="Teleports forward along the road. Jumps over path towers."),
    "phantom": dict(name="PHANTOM", hp=66, spd=64, r=11, col=GHOST, leak=4, info="Fades out so towers lose it. A Beacon unmasks it."),
    "elite": dict(name="ELITE", hp=420, spd=39, r=17, col=GOLD, leak=10, armor=5, info="Tough, and it speeds up everything nearby."),
    "jugger": dict(name="JUGGERNAUT", hp=760, spd=27, r=19, col=RED, leak=12, armor=9, info="A walking wall. Smashes path towers. Bring heavy hitters."),
    "overseer": dict(name="THE OVERSEER", hp=1500, spd=25, r=30, col=RED, leak=20, armor=3, boss=True,
                     info="Calls reinforcements and raises a shield wall."),
    "queen": dict(name="HIVE QUEEN", hp=1300, spd=30, r=28, col=ORANGE, leak=20, armor=1, boss=True,
                  info="Lays swarms the whole way and molts into a sprint."),
    "titan": dict(name="THE TITAN", hp=2300, spd=20, r=34, col=PURPLE, leak=20, armor=5, boss=True,
                  info="EMP pulses switch your towers off. Fortifies when hurt."),
    "architect": dict(name="THE ARCHITECT", hp=3000, spd=23, r=32, col=CYAN, leak=20, armor=4, boss=True,
                      info="Final boss. Hacks towers, blinks forward and goes into overdrive."),
    # event bosses borrow a brain (ai) and a body (model) and dress up
    "pumpking": dict(name="THE PUMPKIN KING", hp=2300, spd=21, r=34, col=(255, 128, 22), leak=20, armor=4, boss=True, ai="titan", model="titan",
                     info="Halloween boss. EMP pulses and a very large hat."),
    "frostlord": dict(name="THE FROST TYRANT", hp=1500, spd=25, r=30, col=(150, 220, 255), leak=20, armor=3, boss=True, ai="overseer", model="overseer",
                      info="Christmas boss. Calls reinforcements wearing festive hats."),
    "megaduck": dict(name="MEGA DUCK", hp=1300, spd=28, r=30, col=(255, 214, 40), leak=20, armor=1, boss=True, ai="queen", model="megaduck",
                     info="It has sunglasses and it is not afraid to use them."),
    "headchef": dict(name="THE HEAD CHEF", hp=1500, spd=25, r=30, col=WHITE, leak=20, armor=3, boss=True, ai="overseer", model="overseer",
                     info="Sends the whole kitchen staff at you."),
    "bluescreen": dict(name="BLUE SCREEN", hp=3000, spd=23, r=32, col=(60, 110, 255), leak=20, armor=4, boss=True, ai="architect", model="architect",
                       info="A fatal error has occurred. It is you."),
    "bear": dict(name="THE BEAR", hp=2300, spd=22, r=34, col=(255, 70, 90), leak=20, armor=5, boss=True, ai="titan", model="titan",
                 info="The market is down. Way down."),
    "wrecker": dict(name="THE WRECKING BALL", hp=2300, spd=22, r=34, col=(255, 210, 40), leak=20, armor=6, boss=True, ai="titan", model="titan",
                    info="Hits path towers like they owe it money."),
}
# kind: (first wave, cost, weight, seconds between spawns)
WAVE_UNITS = {
    "grunt": (1, 5, 3, 0.55), "runner": (2, 5, 2, 0.38), "swarm": (3, 2, 2, 0.20), "tank": (4, 20, 2, 1.5),
    "shield": (6, 13, 2, 0.8), "splitter": (8, 15, 2, 0.9), "healer": (11, 17, 1, 1.7), "elite": (12, 55, 1, 3.0),
    "blinker": (13, 12, 2, 0.7), "phantom": (15, 13, 2, 0.7), "jugger": (18, 90, 1, 4.0),
}
ENEMY_ORDER = ["grunt", "runner", "swarm", "tank", "shield", "splitter", "healer", "elite", "blinker", "phantom", "jugger",
               "overseer", "queen", "titan", "architect"]

# ---------------------------------------------------------------- difficulty + balance knobs
DIFFS = {
    "normal": dict(name="NORMAL", waves=20, hp=0.78, hpw=0.008, spd=1.0, cash=650, core=100, early=0, coins=300, per=5, xp=8, xpwin=120, first=150, boss=25000, col=GREEN),
    "hard": dict(name="HARD", waves=30, hp=0.95, hpw=0.04, spd=1.0, cash=600, core=100, early=0, coins=600, per=8, xp=12, xpwin=250, first=300, boss=50000, col=GOLD),
    "insane": dict(name="INSANE", waves=30, hp=1.0, hpw=0.07, spd=1.08, cash=700, core=60, early=2, coins=1000, per=12, xp=16, xpwin=400, first=600, boss=100000, col=RED),
    "event": dict(name="EVENT", waves=25, hp=0.95, hpw=0.0, spd=1.0, cash=650, core=100, early=1, coins=800, per=8, xp=14, xpwin=350, first=0, boss=40000, col=MAGENTA),
}
DIFF_ORDER = ["normal", "hard", "insane"]
HP_A, HP_B = 0.22, 0.016     # enemy health grows with the wave number: 1 + A*w + B*w*w
BOSS_HP, BOSS_POW = 0.36, 1.25     # boss health = base * BOSS_HP * (wave growth ** BOSS_POW); the FINAL boss uses the difficulty's own number
FINAL_SPD = 0.85             # the final boss walks a little slower than a normal boss
FINAL_TIME = 85.0            # ...and never crosses a map faster than this many seconds
ZOOM_MIN, ZOOM_MAX = 230.0, 1500.0      # how close and how far the 3D camera can go
SKIP_WAIT = 5.0             # a wave has to run this long before it can be skipped
MP_HP = 0.75                 # every extra player makes enemies this much tougher
MP_WAVE_DELAY = 2.0          # with friends nobody readies up: the next wave starts by itself this long after the last one ended
MP_FIRST_DELAY = 6.0         # ...but the very first wave of a match waits this long, so everyone can look around
GOON_R = 8.0                 # how big a Summoner's goon is (it meets an enemy when they are closer than both sizes together)
WALK_K = 0.32                # walking animation: how far the legs swing (radians) per unit of road walked
ACT_TIME = 0.45              # how long one attack swing of an enemy takes to play (looks only)
CORPSE_TIME, CORPSE_BOSS, CORPSE_MAX = 0.45, 1.2, 40      # how long a killed enemy's body stays, a boss's, and how many at once
MAX_LEVEL = 40


def hp_mult(w):
    return 1 + HP_A * (w - 1) + HP_B * (w - 1) ** 2


def wave_budget(w):
    return 50 + 14 * w + 0.5 * w * w


# HIT CASH: a hit pays $1..$5 by how much of the enemy's health (and shield) it takes off in one go
HIT_STEPS = (0.10, 0.25, 0.50, 0.75)     # less than 10% = $1, less than 25% = $2, less than 50% = $3, less than 75% = $4, more = $5
HIT_MAX = 5
HIT_TICK = 0.05                          # steady damage: every 5% of an enemy's health melted is one $1 hit...
BOSS_WAVE_PAY = 1.5
HIT_TICK_BOSS = 0.01                     # ...every 1% on a boss


def kill_cash(w):
    return 110 + 32 * w


def wave_bonus(w):
    return 200 + 34 * w


def xp_need(level):
    return 60 + 30 * level


def level_of(xp):
    lv = 1
    while lv < MAX_LEVEL and xp >= xp_need(lv):
        xp -= xp_need(lv)
        lv += 1
    return lv, xp


def level_coins(level):
    """coins you get for reaching this level"""
    return 100 + 40 * level


RANKS = [(1, "ROOKIE"), (4, "CADET"), (8, "GUARD"), (12, "SENTINEL"), (16, "WARDEN"), (20, "COMMANDER"), (25, "ARCHON"), (30, "LEGEND"), (36, "MYTHIC")]


def rank_of(level):
    out = RANKS[0][1]
    for need, name in RANKS:
        if level >= need:
            out = name
    return out


# ---------------------------------------------------------------- how each kind of place looks
def _th(sky, ground, apron, grid, accent, cliff, amb=None, horizon=None, props=(), inner=(), decal=None, water=(10, 50, 90), road=(9, 10, 22)):
    return dict(sky=sky, ground=ground, apron=apron, grid=grid, accent=accent, cliff=cliff, amb=amb, horizon=horizon,
                props=props, inner=inner, decal=decal, water=water, road=road)


THEMES = {
    "GRID": _th(((4, 6, 22), (26, 12, 58)), (10, 13, 32), (7, 9, 22), (26, 36, 82), CYAN, (26, 46, 88), "motes", "sun",
                (("datatower", 3), ("pylon", 3), ("runestone", 1), ("satellite", 1)), (("tuft", 1),), "circuit"),
    "VOID": _th(((2, 2, 10), (18, 8, 44)), (9, 7, 24), (5, 4, 14), (32, 24, 66), PURPLE, (42, 32, 88), "stars", "planet",
                (("floatrock", 4), ("monolith", 3), ("runestone", 2)), (("rock", 1),), "rings"),
    "INFERNO": _th(((18, 4, 4), (84, 26, 10)), (30, 12, 10), (20, 8, 8), (72, 28, 16), ORANGE, (88, 42, 26), "embers", "glow",
                   (("volcano", 2), ("spike", 5), ("vent", 2)), (("rock", 1),), "cracks", (210, 76, 18)),
    "CORRUPTED": _th(((2, 10, 8), (6, 40, 30)), (8, 22, 18), (4, 12, 10), (16, 56, 44), GREEN, (22, 72, 56), "glitch", None,
                     (("glitchcube", 5), ("pillar", 3), ("datatower", 1)), (("tuft", 1),), "glitch"),
    "FROST": _th(((6, 12, 34), (46, 80, 124)), (30, 44, 70), (22, 32, 54), (62, 86, 124), (150, 220, 255), (72, 104, 146), "snow", "aurora",
                 (("pine", 6), ("icecrystal", 2), ("snowmound", 3)), (("snowmound", 1), ("tuft", 1)), "dots"),
    "CITY": _th(((4, 4, 18), (48, 16, 70)), (14, 14, 26), (8, 8, 16), (38, 38, 68), PINK, (46, 42, 78), "motes", "city",
                (("building", 8), ("lamp", 2), ("billboard", 2), ("car", 1)), (), "tiles"),
    "DUNES": _th(((22, 10, 44), (200, 96, 62)), (60, 42, 30), (44, 30, 22), (98, 72, 48), GOLD, (124, 88, 58), "dust", "sun",
                 (("pyramid", 2), ("cactus", 4), ("obelisk", 2), ("bones", 2), ("rock", 2)), (("rock", 1), ("bones", 1)), "dunes"),
    "FOREST": _th(((2, 10, 14), (10, 56, 44)), (10, 28, 24), (6, 18, 16), (20, 62, 50), (60, 235, 150), (28, 78, 62), "spores", None,
                  (("holotree", 7), ("mushroom", 3), ("rock", 1)), (("mushroom", 2), ("tuft", 2)), "dots"),
    "ABYSS": _th(((2, 6, 20), (8, 44, 76)), (8, 26, 44), (6, 30, 56), (20, 62, 92), (80, 220, 255), (30, 82, 112), "bubbles", None,
                 (("coral", 5), ("lighthouse", 1), ("buoy", 3), ("rock", 2)), (("rock", 1),), "waves"),
    "CRYSTAL": _th(((8, 2, 16), (44, 14, 66)), (20, 14, 36), (12, 8, 24), (60, 40, 98), (255, 110, 230), (72, 50, 112), "motes", None,
                   (("crystals", 6), ("stalagmite", 4)), (("rock", 1),), "facets"),
    "SKY": _th(((18, 36, 96), (120, 170, 232)), (36, 52, 92), (104, 150, 214), (72, 98, 152), (255, 240, 150), (72, 98, 152), "clouds", "sun",
               (("cloud", 6), ("island", 4)), (), None),
    "FACTORY": _th(((10, 8, 8), (58, 40, 26)), (30, 28, 30), (20, 18, 20), (66, 60, 58), (255, 150, 40), (82, 74, 72), "embers", "glow",
                   (("chimney", 4), ("tank", 3), ("crate", 3), ("pipe", 2)), (("crate", 1),), "tiles", (220, 110, 24)),
    "SUNSET": _th(((30, 6, 54), (255, 104, 124)), (14, 8, 30), (10, 6, 22), (130, 44, 150), (255, 80, 200), (62, 32, 94), None, "sun",
                  (("palm", 6), ("billboard", 1), ("car", 2), ("pylon", 1)), (), None),
    "BOARD": _th(((2, 8, 6), (8, 44, 24)), (6, 30, 20), (4, 18, 12), (20, 92, 52), (120, 255, 90), (20, 86, 52), "glitch", None,
                 (("datatower", 3), ("pillar", 2), ("satellite", 2), ("glitchcube", 2)), (), "circuit"),
    "HALLOWEEN": _th(((6, 2, 14), (54, 18, 66)), (20, 14, 30), (12, 8, 20), (52, 32, 72), (255, 128, 22), (62, 42, 86), "embers", "moon",
                     (("deadtree", 5), ("tombstone", 5), ("pumpkinprop", 4), ("lantern", 2)), (("pumpkinprop", 2), ("tombstone", 1)), "dots"),
    "XMAS": _th(((4, 10, 32), (34, 66, 118)), (70, 90, 122), (54, 70, 100), (112, 132, 164), (255, 70, 90), (112, 142, 184), "snow", "aurora",
                (("pine", 5), ("candycane", 3), ("gift", 4), ("snowman", 2)), (("gift", 1), ("snowmound", 2)), "dots"),
    "POND": _th(((10, 30, 54), (96, 176, 206)), (30, 92, 62), (20, 72, 112), (52, 124, 86), (255, 214, 40), (62, 132, 92), "bubbles", "sun",
                (("lilypad", 5), ("reeds", 4), ("duckprop", 3), ("rock", 1)), (("tuft", 2),), "dots", (24, 84, 130)),
    "KITCHEN": _th(((40, 30, 24), (124, 98, 72)), (62, 58, 62), (92, 62, 42), (92, 86, 92), (255, 160, 80), (152, 152, 168), None, None,
                   (("pot", 3), ("fork", 3), ("cheese", 2), ("crate", 1)), (), "checker"),
    "GLITCH": _th(((0, 0, 0), (22, 0, 34)), (6, 6, 10), (0, 0, 0), (120, 0, 120), (255, 0, 255), (42, 42, 54), "glitch", None,
                  (("sign404", 4), ("glitchcube", 5), ("pillar", 1)), (), "glitch"),
    "MARKET": _th(((2, 8, 6), (6, 44, 26)), (8, 18, 14), (4, 10, 8), (20, 62, 42), (60, 235, 130), (24, 66, 46), "motes", None,
                  (("candle", 8), ("ticker", 2), ("building", 2)), (), "chart"),
    "QUARRY": _th(((20, 16, 14), (116, 94, 72)), (60, 52, 46), (44, 38, 34), (98, 86, 76), (255, 210, 40), (122, 106, 92), "dust", "sun",
                  (("bricks", 4), ("crane", 2), ("cone", 3), ("rock", 3), ("crate", 2)), (("rock", 1), ("cone", 1)), "cracks"),
}

# ---------------------------------------------------------------- maps
# paths are corner points in grid squares (26 x 16), cliffs and water are rectangles (col, row, col, row).
# marks = big scenery you cannot build on.  npcs = people you can talk to.  secrets = things you can click.
MAPS = [
    dict(id="first", name="FIRST LIGHT", theme="GRID", need=1, title="LIGHTBRINGER", desc="One winding road. A good place to learn.",
         paths=[[(-1, 3), (6, 3), (6, 11), (13, 11), (13, 4), (20, 4), (20, 12), (24, 12)]],
         cliffs=[(8, 5, 11, 8), (15, 7, 18, 10), (1, 6, 3, 9), (22, 6, 24, 9)],
         bosses=["titan", "queen", "overseer"],
         npcs=[dict(name="SARGE", at=(2, 12), hat="cap", col=GREEN, lines=[
             "New here? Blasters are cheap. Put three by the first bend.",
             "Rails only go on cliffs. Worth the climb.",
             "Point at a tower and press E to upgrade it. X sells it. No clicking needed.",
             "The fisher at Tidewater lost something yellow around here. Check the corners of the map."]),
             dict(name="PIP", at=(17, 1), hat="antenna", col=CYAN, lines=[
                 "I am a drone. I count things. You have built... not enough towers.",
                 "The core hums in B flat. Nobody asked, but now you know.",
                 "A boss shows up every 10 waves. Save your ability for it."])],
         secrets=[dict(id="duck1", prop="duckprop", at=(24, 1.5))]),
    dict(id="frost", name="FROSTBITE PASS", theme="FROST", need=2, title="ICEBREAKER", desc="Icy switchbacks. The road zigzags right past your guns.",
         paths=[[(-1, 13), (5, 13), (9, 4), (13, 12), (17, 4), (21, 12), (24, 6)]],
         cliffs=[(6, 1, 7, 3), (10, 8, 12, 14), (12, 1, 14, 3), (16, 9, 18, 14), (20, 1, 22, 4), (1, 6, 3, 9), (23, 10, 25, 13)],
         bosses=["overseer", "queen", "titan"],
         marks=[dict(id="bigpine", prop="bigpine", at=(4.5, 8), rad=24), dict(id="stove", prop="stove", at=(13, 6), rad=14)],
         npcs=[dict(name="LOST ELF", at=(2, 2), hat="elf", col=GREEN, quest="pine", lines=[
             "I fell off a sleigh. Long story.",
             "See the big pine? It looks so bare. Three towers standing around it would look just like presents...",
             "Do that and I will show you the way to the Winter Works, even out of season."]),
             dict(name="OLD COLD", at=(22, 14.2), hat="hood", col=BLUE, lines=[
                 "That stove has not been warm in years. The chef at Crossfire keeps asking about it.",
                 "Cryo towers love it here. So do I."])]),
    dict(id="horizon", name="EVENT HORIZON", theme="VOID", need=3, title="VOIDWALKER", desc="A long spiral into the dark. The core sits in the middle.",
         paths=[[(-1, 2), (21, 2), (21, 13), (4, 13), (4, 6), (16, 6), (16, 10), (10, 10)]],
         cliffs=[(7, 3, 11, 4), (18, 7, 19, 10), (6, 8, 8, 11), (23, 5, 24, 9), (0, 8, 2, 11)],
         bosses=["overseer", "titan", "queen"], hp=1.45,
         npcs=[dict(name="GRAVEKEEPER", at=(13, 8), hat="hood", col=PURPLE, quest="knock", lines=[
             "It is never the season here. Unless you knock.",
             "Three knocks on the lonely tombstone. Not two. Not four.",
             "The Hollow opens for those who knock. Out of season its prize is only a copy, mind."])],
         secrets=[dict(id="tomb", prop="tombstone", at=(1, 5), v=2)]),
    dict(id="city", name="NEON CITY", theme="CITY", need=4, title="STREET LEGEND", desc="Streets and rooftops. Rooftops count as cliffs.",
         paths=[[(-1, 7), (4, 7), (4, 2), (11, 2), (11, 12), (18, 12), (18, 3), (23, 3), (23, 9)]],
         cliffs=[(6, 4, 9, 7), (6, 9, 9, 13), (13, 4, 16, 10), (20, 5, 21, 10), (1, 2, 2, 5), (13, 14, 16, 15), (0, 9, 2, 12), (20, 12, 24, 14)],
         bosses=["queen", "overseer", "titan"],
         npcs=[dict(name="BROKER", at=(14, 1), hat="top", col=GOLD, quest="stonks", lines=[
             "Buy high. Sell higher. That is the whole secret.",
             "Tell you what. Show me 25,000 cash in one match. Just holding it. Then we talk.",
             "The market is open to people who can hold a bag."]),
             dict(name="TAXI", at=(21, 1), hat="cap", col=YELLOW, lines=[
                 "Rooftops count as cliffs here. Great view, great range.",
                 "I do not drive on that road. Have you seen what walks on it?"])]),
    dict(id="dune", name="DUNE RUNNER", theme="DUNES", need=5, title="SANDSTORM", desc="One giant Z across the desert. Long straight lanes.",
         paths=[[(-1, 2), (19, 2), (7, 13), (23, 13)]],
         cliffs=[(3, 4, 8, 7), (15, 8, 19, 10), (21, 4, 24, 8), (1, 10, 4, 14), (11, 15, 14, 15), (9, 0, 12, 0)],
         bosses=["titan", "overseer", "queen"],
         npcs=[dict(name="MASON", at=(1.5, 8.4), hat="hard", col=ORANGE, quest="brick", lines=[
             "They do not build them like they used to.",
             "Walls fall. Good walls fall five times in one match and are still there at the end.",
             "Lose five path towers in one game and the Quarry will hear about it."])]),
    dict(id="cross", name="CROSSFIRE", theme="INFERNO", need=6, title="FIREWALKER", desc="Two gates, one road. Hold the middle.",
         paths=[[(-1, 2), (8, 2), (8, 8), (16, 8), (16, 3), (22, 3), (22, 12)],
                [(-1, 13), (8, 13), (8, 8), (16, 8), (16, 3), (22, 3), (22, 12)]],
         cliffs=[(2, 5, 5, 10), (10, 3, 13, 6), (10, 10, 14, 12), (18, 6, 20, 10)],
         bosses=["overseer", "queen", "titan"],
         npcs=[dict(name="CHEF UNIT 7", at=(19, 13.5), hat="chef", col=WHITE, quest="toast", lines=[
             "My toast never burns right. I need a cold stove and a LOT of fire.",
             "There is a stove freezing in Frostbite Pass. Rain napalm on it. For science. For breakfast.",
             "Do it and my kitchen is yours."])]),
    dict(id="grove", name="HOLO GROVE", theme="FOREST", need=7, title="GROVEKEEPER", desc="A winding trail through holographic trees.",
         paths=[[(-1, 5), (3, 5), (6, 2), (10, 2), (12, 6), (9, 10), (12, 14), (17, 14), (19, 9), (16, 5), (20, 2), (24, 5)]],
         cliffs=[(1, 8, 5, 12), (7, 4, 9, 7), (13, 8, 16, 11), (13, 1, 16, 2), (21, 7, 24, 11), (5, 13, 8, 15), (19, 13, 23, 15)],
         bosses=["queen", "titan", "overseer"],
         npcs=[dict(name="DRUID.EXE", at=(1.5, 1.5), hat="hood", col=GREEN, lines=[
             "The trees are holograms. The mushrooms are real. Do not eat either.",
             "Something yellow is floating up north between the trees. It squeaks.",
             "Tesla towers love a crowd. So do Menders, sadly."])],
         secrets=[dict(id="duck2", prop="duckprop", at=(12.4, 0.2))]),
    dict(id="tide", name="TIDEWATER", theme="ABYSS", need=8, title="TIDEBREAKER", desc="A long road around two deep pools. You cannot build on water.",
         paths=[[(12, -1), (12, 2), (3, 2), (3, 13), (22, 13), (22, 4), (16, 4), (16, 9), (11, 9)]],
         cliffs=[(12, 5, 14, 7), (5, 0, 9, 0), (0, 6, 1, 10), (24, 6, 25, 10), (11, 11, 15, 11), (18, 0, 22, 1)],
         water=[(6, 5, 9, 11), (18, 6, 20, 11)],
         bosses=["overseer", "titan", "queen"], hp=1.2,
         npcs=[dict(name="OLD FISHER", at=(10.3, 6.5), hat="cap", col=BLUE, quest="ducks", lines=[
             "Somebody keeps dropping rubber ducks around the sector. Three of them.",
             "One is right here in the water. One is in a grove. One is where everybody starts.",
             "Find all three and they will take you to their pond. Click them when you see them."])],
         secrets=[dict(id="duck3", prop="duckprop", at=(7.5, 8))]),
    dict(id="crystal", name="CRYSTAL CAVERN", theme="CRYSTAL", need=9, title="GEMCUTTER", desc="A short road and cliffs everywhere. No time to think.",
         paths=[[(-1, 8), (7, 8), (7, 4), (14, 4), (14, 11), (20, 11), (20, 7), (24, 7)]],
         cliffs=[(1, 3, 4, 6), (1, 10, 5, 13), (9, 6, 12, 9), (9, 11, 12, 13), (16, 5, 18, 9), (16, 13, 21, 14), (22, 9, 24, 12), (9, 0, 13, 2), (16, 1, 22, 4)],
         bosses=["titan", "queen", "architect"], hp=0.8,
         npcs=[dict(name="GEMMA", at=(6, 1), hat="crown", col=MAGENTA, lines=[
             "Short road. No time to think. I love it here.",
             "Cliffs everywhere. Bring Rails and Mortars, or bring tissues."])]),
    dict(id="sky", name="SKY BRIDGE", theme="SKY", need=11, title="SKYWARDEN", desc="Two lanes that cross in the middle of the sky.",
         paths=[[(-1, 2), (7, 2), (17, 12), (22, 12), (22, 8)],
                [(-1, 13), (7, 13), (17, 3), (22, 3), (22, 8)]],
         cliffs=[(1, 5, 5, 10), (10, 1, 14, 3), (10, 12, 14, 14), (18, 6, 20, 9), (24, 5, 25, 10)],
         bosses=["queen", "overseer", "titan"], hp=0.8,
         npcs=[dict(name="CAPTAIN NIMBUS", at=(12.3, 4.7), hat="cap", col=WHITE, lines=[
             "Two lanes, one crossing. Whatever you build in the middle works twice.",
             "Do not look down."])]),
    dict(id="foundry", name="THE FOUNDRY", theme="FACTORY", need=13, title="IRONHEART", desc="Three gates feed one conveyor. Block the merge.",
         paths=[[(-1, 2), (6, 2), (6, 8), (14, 8), (14, 12), (22, 12), (22, 7)],
                [(-1, 13), (6, 13), (6, 8), (14, 8), (14, 12), (22, 12), (22, 7)],
                [(18, -1), (18, 4), (10, 4), (10, 8), (14, 8), (14, 12), (22, 12), (22, 7)]],
         cliffs=[(2, 5, 4, 10), (8, 10, 12, 13), (12, 1, 16, 2), (16, 6, 20, 10), (24, 3, 25, 10), (8, 5, 8, 6)],
         bosses=["overseer", "titan", "architect"],
         npcs=[dict(name="FOREMAN", at=(2, 11.4), hat="hard", col=ORANGE, lines=[
             "Three gates. THREE. Who approved this?",
             "Put path towers at the merge. Trust me."])]),
    dict(id="sunset", name="SUNSET STRIP", theme="SUNSET", need=15, title="SUNCHASER", desc="The longest road in the sector. Drive fast, shoot faster.",
         paths=[[(-1, 3), (21, 3), (21, 8), (4, 8), (4, 13), (20, 13)]],
         cliffs=[(3, 5, 8, 6), (11, 5, 18, 6), (7, 10, 12, 11), (15, 10, 22, 11), (23, 4, 25, 7), (0, 9, 2, 12)],
         bosses=["titan", "queen", "overseer"], hp=1.35,
         npcs=[dict(name="DJ SUNDOWN", at=(12, 1), hat="cap", col=PINK, lines=[
             "Longest road in the sector. Great for Mortars. Great for sunsets.",
             "Somebody typed MEOW on the Motherboard once. The Motherboard answered."])]),
    dict(id="board", name="MOTHERBOARD", theme="BOARD", need=17, title="OVERCLOCKED", desc="Two traces run side by side, then split. Guard the gap.",
         paths=[[(-1, 3), (5, 3), (9, 7), (14, 7), (17, 4), (22, 4), (22, 9)],
                [(-1, 13), (5, 13), (9, 9), (14, 9), (17, 12), (22, 12), (22, 9)]],
         cliffs=[(1, 6, 5, 10), (10, 2, 14, 4), (10, 12, 14, 14), (18, 6, 20, 10), (24, 6, 25, 11), (7, 0, 9, 1), (7, 14, 9, 15)],
         bosses=["queen", "titan", "architect"], hp=0.85,
         npcs=[dict(name="GL1TCH", at=(7, 8), hat="antenna", col=MAGENTA, quest="meow", lines=[
             "th3 c4t w4lks on th3 k3yb04rd.",
             "s4y its n4me in ch4t. h3re. on th1s b04rd.",
             "(It means: type MEOW in the chat. Press ENTER to chat.)"])]),
    dict(id="core", name="CORRUPTED CORE", theme="CORRUPTED", need=20, title="ARCHITECT'S END", desc="They come from both sides. The Architect is waiting.",
         paths=[[(-1, 2), (4, 2), (4, 13), (9, 13), (9, 4), (12, 4), (12, 8)],
                [(26, 13), (21, 13), (21, 2), (16, 2), (16, 11), (12, 11), (12, 8)]],
         cliffs=[(6, 4, 7, 10), (18, 5, 19, 11), (13, 6, 15, 8), (0, 5, 2, 9), (23, 4, 25, 8)],
         bosses=["queen", "titan", "architect"], hp=0.75, cash=200,
         npcs=[dict(name="THE LAST ENGINEER", at=(10, 1), hat="hard", col=CYAN, lines=[
             "This is where it started. The Architect built the Bastion. Then it changed its mind.",
             "It hacks towers. Spread them out, and bring a Mechanic."])]),
    # ---- event levels
    dict(id="haunted", name="HAUNTED HOLLOW", theme="HALLOWEEN", need=1, event="haunted", skin="halloween", desc="A graveyard road. Everything here wears a hat.",
         paths=[[(-1, 8), (4, 8), (4, 3), (10, 3), (10, 12), (16, 12), (16, 5), (21, 5), (21, 11), (24, 11)]],
         cliffs=[(6, 5, 8, 10), (12, 5, 14, 10), (18, 7, 19, 12), (1, 3, 2, 6), (1, 10, 7, 13), (12, 14, 18, 15), (23, 6, 25, 9), (12, 1, 18, 2)],
         bosses=["queen", "overseer", "pumpking"],
         npcs=[dict(name="JACK", at=(7, 1.3), hat="top", col=ORANGE, lines=[
             "Welcome to the Hollow. Mind the hats.",
             "The King comes last. He is mostly hat."])]),
    dict(id="winter", name="WINTER WORKS", theme="XMAS", need=1, event="winter", skin="xmas", desc="The toy factory has been taken over. The elves are furious.",
         paths=[[(26, 3), (8, 3), (4, 7), (8, 11), (19, 11), (19, 7), (13, 7)]],
         cliffs=[(9, 5, 11, 9), (14, 5, 17, 5), (14, 9, 17, 9), (21, 5, 24, 9), (0, 1, 2, 4), (0, 10, 3, 13), (10, 13, 17, 14), (10, 0, 16, 1)],
         bosses=["queen", "titan", "frostlord"],
         marks=[dict(id="xpine", prop="bigpine", at=(22, 13.2), rad=24)],
         npcs=[dict(name="FOREMAN FROST", at=(5.5, 13.5), hat="elf", col=RED, lines=[
             "Production is behind. The enemies are wearing our hats.",
             "Snow slows them. Fire melts the fun. Use both."])]),
    dict(id="pond", name="DUCK POND", theme="POND", need=1, event="pond", skin="pond", desc="A peaceful pond. Was a peaceful pond.",
         paths=[[(-1, 3), (20, 3), (20, 12), (5, 12), (5, 7), (12, 7)]],
         cliffs=[(7, 5, 10, 5), (14, 5, 18, 7), (1, 6, 3, 11), (22, 5, 24, 11), (8, 14, 16, 15), (4, 0, 12, 1)],
         water=[(8, 9, 17, 10)],
         bosses=["overseer", "titan", "megaduck"],
         npcs=[dict(name="QUACKMASTER", at=(14.5, 1.2), hat="crown", col=YELLOW, lines=[
             "Quack.", "Quack quack.", "(He says the big one comes last. He says it has sunglasses.)"])]),
    dict(id="kitchen", name="THE KITCHEN", theme="KITCHEN", need=1, event="kitchen", skin="kitchen", desc="Everything here is food or a weapon. Sometimes both.",
         paths=[[(-1, 12), (6, 12), (6, 3), (12, 3), (12, 12), (18, 12), (18, 3), (24, 3)]],
         cliffs=[(1, 5, 4, 10), (8, 5, 10, 10), (14, 5, 16, 10), (20, 5, 23, 10), (8, 14, 16, 15), (1, 0, 4, 1)],
         bosses=["queen", "titan", "headchef"],
         npcs=[dict(name="SOUS CHEF", at=(21.5, 13.5), hat="chef", col=WHITE, lines=[
             "Everything here is either food or a weapon. Sometimes both.",
             "The counters are cliffs. Chef says no feet on the counters. Towers are fine."])]),
    dict(id="glitch", name="404", theme="GLITCH", need=1, event="glitch", skin="glitch", desc="map_name_missing. road_shape_missing. good_luck_found.",
         paths=[[(-1, 1), (8, 1), (3, 8), (13, 8), (8, 14), (20, 14), (15, 6), (24, 6)]],
         cliffs=[(10, 2, 14, 5), (0, 10, 4, 13), (19, 8, 23, 11), (18, 1, 22, 3), (12, 10, 14, 12), (0, 4, 1, 6)],
         bosses=["titan", "queen", "bluescreen"], hp=1.2,
         npcs=[dict(name="N0NE", at=(17, 4.6), hat="antenna", col=MAGENTA, lines=[
             "404: dialogue not found.", "404: second dialogue also not found.", "200: OK fine. The cat lives here. Do not touch its keyboard."])]),
    dict(id="market", name="STONK MARKET", theme="MARKET", need=1, event="market", skin="market", desc="The road is a price chart. It only goes up. Mostly.",
         paths=[[(-1, 13), (4, 13), (7, 9), (10, 12), (14, 5), (17, 9), (21, 2), (24, 2)]],
         cliffs=[(1, 8, 3, 10), (8, 4, 11, 7), (12, 10, 15, 14), (18, 10, 22, 13), (15, 1, 18, 3), (22, 5, 24, 9), (4, 1, 8, 2)],
         bosses=["overseer", "queen", "bear"], hp=0.9,
         npcs=[dict(name="ANALYST", at=(2, 3), hat="top", col=GREEN, lines=[
             "Line goes up. Line goes down. Enemies go forward.",
             "This is not financial advice. This is a warning."])]),
    dict(id="quarry", name="THE QUARRY", theme="QUARRY", need=1, event="quarry", skin="quarry", desc="Hard hats required. Path towers recommended.",
         paths=[[(-1, 2), (10, 2), (10, 7), (3, 7), (3, 13), (16, 13), (16, 7), (22, 7), (22, 12)]],
         cliffs=[(5, 4, 8, 5), (5, 9, 13, 11), (12, 4, 14, 5), (18, 9, 20, 12), (18, 2, 23, 5), (0, 9, 1, 12), (24, 8, 25, 13), (12, 15, 20, 15)],
         bosses=["titan", "overseer", "wrecker"],
         npcs=[dict(name="GRAVEL GUS", at=(13, 0.6), hat="hard", col=YELLOW, lines=[
             "It never needed a charger. Not once.",
             "The Wrecking Ball hates walls. Build walls anyway."])]),
]
# ---------------------------------------------------------------- the shape of every map (v2.2: real height)
# A road point is (column, row), (column, row, level) or (column, row, level, "b").  The level carries on until a point
# changes it; between two points on different levels the road is a ramp.  "b" = the stretch after it is a bridge.
# cliffs are (column, row, column, row, level).  Later ones override earlier ones; land beside a road is never higher than it.
# buff = towers that feel at home here: {tower: {"dmg" / "rng" / "rate" / "income" / "hp": how much extra}}
MAP_GEO = {
    "first": dict(
        hp=0.88,
        desc="One winding road that ends on a hill. A good place to learn.",
        paths=[[(-1, 3), (6, 3), (6, 11), (13, 11), (13, 4), (20, 4), (20, 7, 0), (20, 9, 1), (20, 12, 1), (23, 12, 1)]],
        cliffs=[(17, 10, 25, 15, 1), (22, 14, 25, 15, 2), (8, 5, 11, 9, 1), (9, 6, 10, 8, 2), (15, 6, 18, 9, 1), (16, 7, 17, 8, 2), (1, 5, 4, 9, 1), (2, 6, 3, 8, 2),
                (22, 5, 24, 6, 2), (0, 13, 3, 15, 1), (8, 13, 11, 15, 1), (9, 14, 10, 15, 2), (9, 0, 12, 0, 1)],
        npc_at=[(2, 11), (17, 1)],
        buff={"blaster": {"dmg": 0.15}, "blade": {"dmg": 0.15}, "rail": {"dmg": 0.15}}),
    "frost": dict(
        desc="Icy switchbacks between three peaks. The road zigzags right past your guns.",
        cliffs=[(10, 9, 12, 15, 1), (10, 11, 12, 15, 2), (11, 13, 12, 15, 3), (6, 0, 8, 3, 1), (6, 0, 7, 1, 2), (12, 0, 14, 3, 1), (13, 0, 13, 1, 2),
                (16, 9, 18, 15, 1), (16, 11, 18, 15, 2), (17, 13, 17, 15, 3), (20, 0, 22, 4, 1), (20, 0, 22, 1, 2), (1, 5, 3, 9, 1), (1, 6, 2, 8, 2),
                (23, 10, 25, 14, 1), (24, 12, 25, 14, 2)],
        buff={"cryo": {"rng": 0.25}, "snow": {"dmg": 0.25}, "mortar": {"rng": 0.15}}),
    "horizon": dict(
        desc="A long spiral down into the dark. The core sits at the bottom.",
        paths=[[(-1, 2, 2), (21, 2, 2), (21, 4, 2), (21, 6, 1), (21, 13, 1), (4, 13, 1), (4, 11, 1), (4, 9, 0), (4, 6, 0), (16, 6), (16, 10), (10, 10)]],
        cliffs=[(0, 0, 25, 3, 2), (19, 0, 25, 5, 2), (0, 4, 25, 4, 1), (19, 6, 25, 15, 1), (0, 11, 25, 15, 1), (0, 5, 2, 10, 1), (18, 7, 19, 10, 1),
                (6, 8, 8, 10, 1), (23, 8, 25, 12, 2), (0, 14, 6, 15, 2), (12, 15, 18, 15, 2)],
        npc_at=[(13, 8)],
        buff={"graviton": {"rng": 0.25}, "rail": {"rng": 0.15}, "prism": {"dmg": 0.15}}),
    "city": dict(
        hp=1.2,
        desc="Streets, rooftops and an overpass: the road crosses over itself.",
        paths=[[(-1, 7), (20, 7), (20, 12), (12, 12), (12, 11, 0), (12, 9, 1), (12, 5, 1), (12, 3, 0), (12, 2), (23, 2), (23, 5)]],
        cliffs=[(1, 1, 4, 5, 2), (2, 2, 3, 4, 3), (6, 1, 10, 5, 1), (7, 2, 9, 4, 2), (14, 4, 18, 5, 1), (15, 4, 17, 4, 2), (14, 9, 18, 10, 2), (1, 9, 5, 10, 1),
                (2, 9, 4, 10, 2), (1, 13, 9, 15, 1), (3, 14, 6, 15, 2), (4, 15, 5, 15, 3), (14, 14, 25, 15, 1), (16, 15, 22, 15, 2), (22, 7, 25, 10, 2),
                (23, 8, 24, 9, 3), (14, 0, 21, 0, 1), (7, 9, 10, 10, 1)],
        buff={"rail": {"dmg": 0.2}, "mortar": {"dmg": 0.2}, "sentinel": {"rng": 0.15}}),
    "dune": dict(
        desc="One giant Z across the desert, past a stepped pyramid. Long straight lanes.",
        cliffs=[(2, 5, 8, 11, 1), (3, 6, 7, 10, 2), (4, 7, 6, 9, 3), (16, 5, 22, 11, 1), (18, 6, 21, 9, 2), (23, 3, 25, 9, 1), (9, 0, 12, 0, 1), (11, 15, 16, 15, 1),
                (9, 4, 13, 7, 1), (10, 4, 11, 5, 2), (13, 9, 15, 11, 1), (1, 0, 5, 0, 1), (19, 15, 24, 15, 1),
                (0, 15, 3, 15, 1), (22, 0, 25, 0, 2)],
        npc_at=[(1, 13)],
        buff={"rail": {"rng": 0.25}, "mortar": {"rng": 0.2}, "annihilator": {"rng": 0.15}}),
    "cross": dict(
        hp=0.92,
        cash=100,
        desc="Two gates, one road. The north gate comes down off the lava shelf. Hold the middle.",
        paths=[[(-1, 2, 1), (4, 2, 1), (6, 2, 0), (8, 2, 0), (8, 8), (16, 8), (16, 3), (22, 3), (22, 12)],
               [(-1, 13), (8, 13), (8, 8), (16, 8), (16, 3), (22, 3), (22, 12)]],
        cliffs=[(0, 0, 5, 4, 1), (0, 0, 2, 0, 2), (10, 3, 13, 6, 1), (11, 4, 12, 5, 2), (10, 10, 14, 13, 1), (11, 11, 13, 12, 2), (12, 11, 12, 12, 3),
                (18, 6, 20, 10, 1), (19, 7, 19, 9, 2), (24, 5, 25, 13, 1), (17, 13, 20, 15, 1), (10, 0, 14, 0, 1)],
        water=[(2, 6, 5, 10)],
        buff={"mortar": {"dmg": 0.2}, "toaster": {"dmg": 0.25}, "reactor": {"hp": 0.3}}),
    "grove": dict(
        hp=1.1,
        desc="A winding trail through holographic trees, and a bridge over the stream.",
        paths=[[(-1, 5), (3, 5), (6, 2), (10, 2), (12, 6), (9, 10), (12, 14), (14, 14, 0), (16, 14, 1), (21, 14, 1), (21, 12, 1), (21, 10, 0), (21, 6), (16, 6),
                (16, 2), (23, 2), (23, 5)]],
        cliffs=[(20, 11, 25, 15, 1), (23, 13, 25, 15, 2), (16, 12, 17, 15, 1), (1, 8, 5, 12, 1), (2, 9, 4, 11, 2), (7, 4, 9, 7, 1), (13, 8, 16, 11, 1),
                (14, 9, 15, 10, 2), (0, 0, 2, 2, 1), (5, 13, 8, 15, 1), (6, 14, 7, 15, 2), (24, 7, 25, 10, 2), (18, 3, 20, 4, 1), (13, 0, 15, 0, 1)],
        water=[(18, 9, 19, 15)],
        secret_at=[(11.5, 0.2)],
        buff={"harvester": {"income": 0.25}, "blade": {"dmg": 0.25}, "guardian": {"hp": 0.3}}),
    "tide": dict(
        hp=0.9,
        desc="A long road around the lagoon, then out along the pier. The core is on the island.",
        paths=[[(12, -1), (12, 2), (3, 2), (3, 13), (22, 13), (22, 4), (17, 4), (17, 5, 0), (17, 7, 1), (17, 8, 1), (11, 8, 1)]],
        cliffs=[(10, 7, 12, 9, 1), (15, 6, 18, 9, 1), (5, 0, 9, 0, 1), (0, 6, 1, 10, 1), (24, 6, 25, 10, 2), (18, 0, 23, 1, 1), (19, 0, 21, 0, 2), (5, 15, 12, 15, 1),
                (14, 0, 16, 1, 1), (24, 12, 25, 15, 1)],
        water=[(6, 5, 9, 11), (10, 5, 14, 6), (10, 10, 14, 11), (13, 7, 14, 9), (19, 6, 20, 11)],
        npc_at=[(1, 12)],
        buff={"duck": {"dmg": 0.3}, "tesla": {"dmg": 0.2}, "cryo": {"rng": 0.15}}),
    "crystal": dict(
        cash=100,
        desc="A short road through a canyon of crystal terraces. No time to think.",
        paths=[[(-1, 8), (7, 8), (7, 4), (14, 4), (14, 11), (20, 11), (20, 10, 0), (20, 8, 1), (20, 7, 1), (24, 7, 1)]],
        cliffs=[(1, 3, 5, 6, 1), (1, 3, 4, 5, 2), (1, 3, 2, 4, 3), (1, 10, 5, 14, 1), (1, 11, 4, 14, 2), (1, 13, 2, 14, 3), (9, 6, 12, 9, 1), (10, 7, 11, 8, 2),
                (9, 11, 12, 14, 1), (9, 12, 11, 14, 2), (10, 13, 10, 14, 3), (16, 6, 18, 9, 1), (16, 6, 17, 8, 2), (16, 13, 21, 15, 1), (17, 14, 20, 15, 2),
                (22, 9, 25, 13, 1), (9, 0, 13, 2, 1), (10, 0, 12, 1, 2), (11, 0, 11, 0, 3), (16, 0, 25, 4, 1), (18, 0, 24, 2, 2), (20, 0, 22, 1, 3), (19, 5, 25, 8, 1)],
        buff={"prism": {"dmg": 0.25}, "beacon": {"rng": 0.2}, "tesla": {"dmg": 0.15}}),
    "sky": dict(
        cash=150, hp=0.72,
        desc="Islands in the sky joined by bridges. One lane crosses right over the other.",
        paths=[[(-1, 3, 1), (6, 3, 1, "b"), (9, 3, 1), (10, 3, 1), (10, 4, 1, "b"), (10, 11, 1), (10, 12, 1), (12, 12, 1, "b"), (17, 12, 1), (22, 12, 1), (22, 8, 1)],
               [(-1, 13, 1), (4, 13, 1), (4, 11, 1), (4, 9, 2), (4, 7, 2), (6, 7, 2, "b"), (13, 7, 2), (15, 7, 2), (15, 4, 2), (17, 4, 2), (19, 4, 1), (22, 4, 1), (22, 8, 1)]],
        cliffs=[(0, 1, 6, 5, 1), (0, 0, 3, 1, 2), (9, 1, 12, 4, 1), (8, 11, 12, 14, 1), (9, 13, 11, 14, 2), (17, 10, 24, 14, 1), (20, 3, 24, 9, 1), (0, 11, 5, 15, 1),
                (0, 14, 2, 15, 2), (2, 6, 6, 9, 2), (13, 2, 17, 8, 2), (14, 1, 16, 2, 3), (23, 13, 24, 14, 2), (24, 5, 25, 7, 2)],
        npc_at=[(1, 8)],
        buff={"rail": {"rng": 0.2}, "sentinel": {"dmg": 0.2}, "hydra": {"dmg": 0.15}}),
    "foundry": dict(
        cash=200,
        desc="Three gates feed one conveyor: two on the floor, one on the gantry above. Block the merge.",
        paths=[[(-1, 2), (6, 2), (6, 8), (14, 8), (14, 12), (22, 12), (22, 7)],
               [(-1, 13), (6, 13), (6, 8), (14, 8), (14, 12), (22, 12), (22, 7)],
               [(18, -1, 1, "b"), (18, 4, 1, "b"), (12, 4, 1), (10, 4, 0), (10, 8), (14, 8), (14, 12), (22, 12), (22, 7)]],
        cliffs=[(8, 10, 12, 13, 1), (9, 11, 11, 12, 2), (12, 0, 16, 2, 1), (13, 0, 15, 1, 2), (16, 6, 20, 10, 1), (17, 7, 19, 9, 2), (24, 3, 25, 10, 2), (0, 7, 0, 8, 1),
                (8, 15, 20, 15, 1), (20, 0, 25, 1, 1)],
        water=[(2, 5, 4, 10)],
        buff={"mechanic": {"rng": 0.3}, "bulwark": {"hp": 0.3}, "scatter": {"dmg": 0.2}}),
    "sunset": dict(
        hp=1.05,
        desc="The longest road in the sector, with a raised highway through the middle. Drive fast, shoot faster.",
        paths=[[(-1, 3), (21, 3), (21, 5, 0), (21, 7, 1), (21, 8, 1), (19, 8, 1, "b"), (6, 8, 1), (4, 8, 1), (4, 9, 1), (4, 11, 0), (4, 13), (20, 13)]],
        cliffs=[(3, 5, 8, 6, 1), (11, 5, 18, 6, 1), (7, 10, 12, 11, 1), (15, 10, 22, 11, 1), (23, 4, 25, 7, 2), (0, 10, 2, 12, 1), (0, 5, 1, 7, 2), (20, 7, 22, 9, 1),
                (3, 7, 5, 9, 1), (8, 15, 16, 15, 1), (6, 0, 10, 1, 1), (14, 0, 18, 1, 1), (15, 0, 17, 0, 2)],
        buff={"blaster": {"rate": 0.2}, "scatter": {"rate": 0.2}, "hydra": {"rate": 0.15}}),
    "board": dict(
        cash=150, hp=0.68,
        desc="Two traces on a circuit board. One jumps over the other on a wire bridge.",
        paths=[[(-1, 3), (10, 3), (10, 12), (18, 12), (18, 8), (22, 8)],
               [(-1, 12), (4, 12), (4, 11, 0), (4, 9, 1), (4, 7, 1), (6, 7, 1, "b"), (14, 7, 1), (14, 5, 1), (14, 3, 0), (22, 3), (22, 8)]],
        cliffs=[(12, 9, 16, 10, 1), (13, 9, 15, 10, 2), (6, 9, 8, 10, 1), (16, 5, 20, 6, 1), (17, 5, 19, 6, 2), (0, 5, 2, 10, 1), (0, 6, 1, 9, 2), (6, 14, 16, 15, 1),
                (8, 15, 14, 15, 2), (20, 10, 25, 14, 1), (22, 11, 24, 13, 2), (23, 12, 23, 12, 3), (1, 0, 7, 1, 1), (24, 0, 25, 5, 2), (3, 6, 5, 8, 1), (13, 6, 15, 8, 1),
                (6, 5, 8, 5, 1), (12, 0, 20, 1, 1)],
        npc_at=[(7, 13)],
        buff={"tesla": {"dmg": 0.25}, "commander": {"rng": 0.2}, "cat": {"dmg": 0.25}}),
    "core": dict(
        cash=250, hp=0.62,
        desc="They come from both sides and climb the pyramid. The Architect is waiting.",
        paths=[[(-1, 2), (4, 2), (4, 13), (8, 13), (8, 4), (12, 4, 0), (12, 8, 2)],
               [(26, 13), (21, 13), (21, 2), (16, 2), (16, 12), (12, 12, 0), (12, 8, 2)]],
        cliffs=[(10, 6, 14, 10, 1), (11, 7, 13, 9, 2), (6, 4, 6, 11, 1), (18, 4, 19, 11, 1), (18, 6, 19, 9, 2), (0, 5, 2, 10, 1), (0, 6, 1, 9, 2), (23, 4, 25, 10, 1),
                (24, 5, 25, 9, 2), (10, 0, 14, 1, 1), (10, 14, 14, 15, 1), (0, 14, 2, 15, 2), (23, 0, 25, 1, 2)],
        npc_at=[(10, 2)],
        buff={"annihilator": {"dmg": 0.15}, "graviton": {"rng": 0.2}, "commander": {"rng": 0.2}}),
    "haunted": dict(
        desc="A graveyard road that climbs to the crypt. Everything here wears a hat.",
        paths=[[(-1, 8), (4, 8), (4, 3), (10, 3), (10, 12), (16, 12), (16, 5), (21, 5), (21, 7, 0), (21, 9, 1), (21, 11, 1), (24, 11, 1)]],
        cliffs=[(19, 9, 25, 14, 1), (23, 13, 25, 15, 2), (6, 5, 8, 10, 1), (7, 6, 7, 9, 2), (12, 5, 14, 10, 1), (13, 6, 13, 9, 2), (1, 2, 2, 6, 1), (1, 10, 7, 13, 1),
                (2, 11, 5, 12, 2), (12, 14, 18, 15, 1), (12, 0, 18, 1, 1), (14, 0, 16, 0, 2), (18, 7, 19, 7, 1), (23, 6, 25, 7, 2)],
        buff={"pumpkin": {"dmg": 0.3}, "blade": {"dmg": 0.2}, "tesla": {"dmg": 0.15}}),
    "winter": dict(
        desc="The toy factory has been taken over. The core is on the island in the frozen pond.",
        paths=[[(26, 3), (8, 3), (4, 7), (8, 11), (19, 11), (19, 9, 0), (19, 7, 1), (13, 7, 1)]],
        cliffs=[(12, 6, 14, 8, 1), (18, 6, 20, 8, 1), (21, 5, 24, 9, 1), (22, 6, 23, 8, 2), (0, 0, 2, 4, 1), (0, 10, 3, 13, 1), (0, 11, 2, 13, 2), (10, 13, 17, 14, 1),
                (12, 14, 15, 14, 2), (10, 0, 16, 1, 1), (12, 0, 14, 0, 2)],
        water=[(11, 5, 17, 5), (11, 9, 17, 9), (11, 6, 11, 8), (15, 6, 17, 8)],
        buff={"snow": {"dmg": 0.3}, "cryo": {"rng": 0.25}, "sentinel": {"dmg": 0.15}}),
    "pond": dict(
        desc="A peaceful pond. Was a peaceful pond. A wooden bridge leads to the core.",
        paths=[[(-1, 3), (20, 3), (20, 12), (5, 12), (5, 10, 0), (5, 8, 1), (5, 7, 1), (12, 7, 1)]],
        cliffs=[(11, 6, 13, 8, 1), (4, 6, 6, 8, 1), (1, 6, 2, 11, 1), (22, 5, 24, 11, 1), (23, 6, 24, 10, 2), (8, 14, 16, 15, 1), (10, 15, 14, 15, 2), (4, 0, 12, 1, 1),
                (6, 0, 10, 0, 2)],
        water=[(7, 5, 18, 5), (7, 9, 18, 10), (7, 6, 10, 8), (14, 6, 18, 8)],
        buff={"duck": {"dmg": 0.3}, "harvester": {"income": 0.25}, "stonks": {"income": 0.25}}),
    "kitchen": dict(
        desc="Down off the counter, across the floor, up onto the table. Everything here is food or a weapon.",
        paths=[[(-1, 12, 2), (2, 12, 2), (5, 12, 0), (6, 12, 0), (6, 3), (12, 3), (12, 12), (18, 12), (18, 7, 0), (18, 5, 1), (18, 3, 1), (24, 3, 1)]],
        cliffs=[(0, 10, 2, 15, 2), (16, 1, 25, 5, 1), (22, 0, 25, 0, 2), (1, 4, 4, 8, 1), (2, 5, 3, 7, 2), (8, 5, 10, 10, 1), (9, 6, 9, 9, 2), (14, 5, 16, 10, 1),
                (15, 7, 15, 9, 2), (20, 7, 23, 10, 1), (21, 8, 22, 9, 2), (8, 14, 16, 15, 1), (1, 0, 4, 1, 1)],
        buff={"toaster": {"dmg": 0.3}, "mortar": {"dmg": 0.15}, "scatter": {"dmg": 0.2}}),
    "glitch": dict(
        cliffs=[(10, 2, 14, 5, 1), (11, 3, 13, 4, 3), (0, 10, 4, 13, 2), (19, 8, 23, 11, 1), (20, 9, 22, 10, 3), (18, 1, 22, 3, 2), (12, 10, 14, 12, 1), (13, 11, 13, 11, 3),
                (0, 4, 1, 6, 3), (24, 12, 25, 15, 2), (5, 11, 6, 12, 1), (4, 4, 4, 5, 2), (16, 9, 16, 10, 2), (22, 0, 25, 0, 1), (9, 15, 11, 15, 3)],
        buff={"cat": {"dmg": 0.3}, "tesla": {"dmg": 0.2}, "prism": {"dmg": 0.15}}),
    "market": dict(
        desc="The road is a price chart. It only goes up. The core is at the all-time high.",
        paths=[[(-1, 13), (4, 13), (4, 10), (9, 10), (9, 12), (13, 12, 0), (13, 10, 1), (13, 6, 1), (17, 6, 1), (17, 8, 1), (19, 8, 1), (21, 8, 2), (21, 4, 2), (21, 2, 3),
                (24, 2, 3)]],
        cliffs=[(10, 5, 20, 11, 1), (20, 3, 25, 9, 2), (20, 0, 25, 3, 3), (15, 8, 15, 11, 2), (10, 6, 11, 9, 2), (23, 5, 25, 7, 3), (19, 4, 19, 6, 3), (15, 3, 19, 4, 2),
                (1, 7, 2, 11, 1), (6, 5, 7, 8, 1), (6, 6, 6, 7, 2), (15, 12, 18, 14, 1), (16, 13, 17, 14, 2), (9, 2, 11, 4, 1), (10, 3, 10, 3, 2), (22, 11, 24, 14, 1),
                (6, 12, 7, 15, 1), (11, 14, 11, 15, 1), (0, 9, 0, 11, 2)],
        buff={"stonks": {"income": 0.3}, "harvester": {"income": 0.2}, "rail": {"dmg": 0.15}}),
    "quarry": dict(
        desc="Down the terraces into the pit. Hard hats required. Path towers recommended.",
        paths=[[(-1, 2, 2), (10, 2, 2), (10, 3, 2), (10, 5, 1), (10, 7, 1), (3, 7, 1), (3, 9, 1), (3, 11, 0), (3, 13), (16, 13), (16, 7), (22, 7), (22, 12)]],
        cliffs=[(0, 0, 25, 3, 2), (0, 4, 13, 9, 1), (18, 2, 25, 4, 2), (18, 9, 20, 11, 1), (24, 8, 25, 13, 1), (12, 15, 20, 15, 1), (5, 9, 13, 11, 1), (19, 5, 20, 5, 1),
                (0, 10, 1, 12, 1), (13, 4, 14, 5, 2)],
        buff={"brick": {"hp": 0.4}, "bulwark": {"hp": 0.25}, "guardian": {"dmg": 0.2}}),
}

# fine tuning, found by letting the bot play every level: how tough enemies are on each map, per difficulty
MAP_DHP = {
    'first': {'normal': 1.1, 'hard': 0.93, 'insane': 0.78},
    'frost': {'normal': 1.06, 'hard': 1.22, 'insane': 1.02},
    'horizon': {'normal': 1.24, 'hard': 1.11, 'insane': 1.11},
    'city': {'normal': 1.24, 'hard': 1.61, 'insane': 1.33},
    'dune': {'normal': 1.24, 'hard': 1.33, 'insane': 1.33},
    'cross': {'normal': 1.19, 'hard': 1.22, 'insane': 0.93},
    'grove': {'normal': 1.02, 'hard': 0.78, 'insane': 0.78},
    'tide': {'normal': 0.91, 'hard': 0.78, 'insane': 0.78},
    'crystal': {'normal': 1.19, 'hard': 1.22, 'insane': 1.22},
    'sky': {'normal': 1.14, 'hard': 0.85, 'insane': 0.66},
    'foundry': {'normal': 1.24, 'hard': 1.22, 'insane': 0.93},
    'sunset': {'normal': 1.19, 'hard': 0.78, 'insane': 1.02},
    'board': {'normal': 1.24, 'hard': 0.93, 'insane': 0.85},
    'core': {'normal': 1.1, 'hard': 1.11, 'insane': 1.02},
    'haunted': {'event': 1.4},
    'winter': {'event': 1.53},
    'pond': {'event': 1.4},
    'kitchen': {'event': 1.26},
    'glitch': {'event': 1.26},
    'market': {'event': 1.53},
    'quarry': {'event': 1.05},
}

BUFF_WORDS = {"dmg": "damage", "rng": "range", "rate": "fire rate", "income": "income", "hp": "health"}


def buff_text(b):
    return "  ".join("+%d%% %s" % (round(v * 100), BUFF_WORDS[k]) for k, v in b.items())


MAP_BY_ID = {}
for _m in MAPS:
    _g = MAP_GEO.get(_m["id"], {})
    for _k in ("desc", "paths", "cliffs", "water", "buff", "cash", "hp", "dhp"):
        if _k in _g:
            _m[_k] = _g[_k]
    if _m["id"] in MAP_DHP:
        _m["dhp"] = dict(MAP_DHP[_m["id"]])
    for _j, _at in enumerate(_g.get("npc_at", ())):
        _m["npcs"][_j]["at"] = _at
    for _j, _at in enumerate(_g.get("secret_at", ())):
        _m["secrets"][_j]["at"] = _at
for _i, _m in enumerate(MAPS):
    _m["i"] = _i
    MAP_BY_ID[_m["id"]] = _m
    for _j, _n in enumerate(_m.get("npcs", ())):
        _n["id"] = "%s.%d" % (_m["id"], _j)
MAIN_MAPS = [m for m in MAPS if not m.get("event")]

# ---------------------------------------------------------------- events
# season = ((month, day) start, (month, day) end).  Secret events last EVENT_DAYS from the moment you unlock them.
EVENT_DAYS = 7
EVENTS = {
    "haunted": dict(name="HAUNTED HOLLOW", kind="season", season=((10, 1), (11, 7)), label="HALLOWEEN", tower="pumpkin", title="pumpkin", col=(255, 128, 22),
                    hint="Somebody on EVENT HORIZON knows another way in."),
    "winter": dict(name="WINTER WORKS", kind="season", season=((12, 1), (1, 7)), label="CHRISTMAS", tower="snow", title="frost", col=(255, 70, 90),
                   hint="Somebody in FROSTBITE PASS knows another way in."),
    "pond": dict(name="DUCK POND", kind="secret", tower="duck", title="duck", col=(255, 214, 40), hint="A fisher has lost something."),
    "kitchen": dict(name="THE KITCHEN", kind="secret", tower="toaster", title="chef", col=(255, 160, 80), hint="A chef is hungry."),
    "glitch": dict(name="404", kind="secret", tower="cat", title="catperson", col=(255, 0, 255), hint="s0m3th1ng is wr0ng w1th a b04rd."),
    "market": dict(name="STONK MARKET", kind="secret", tower="stonks", title="stonks", col=(60, 235, 130), hint="A broker respects one thing only."),
    "quarry": dict(name="THE QUARRY", kind="secret", tower="brick", title="brick", col=(255, 210, 40), hint="A mason misses the old walls."),
}
EVENT_ORDER = list(EVENTS)
QUEST_EVENT = {"knock": "haunted", "pine": "winter", "ducks": "pond", "toast": "kitchen", "meow": "glitch", "stonks": "market", "brick": "quarry"}
STONKS_GOAL = 25000
BRICK_GOAL = 5


def in_season(ev, today=None):
    e = EVENTS[ev]
    if e["kind"] != "season":
        return False
    today = today or datetime.date.today()
    (m0, d0), (m1, d1) = e["season"]
    a, b, c = (m0, d0), (today.month, today.day), (m1, d1)
    if a <= c:
        return a <= b <= c
    return b >= a or b <= c


def season_left(ev, today=None):
    """days until this season ends (only meaningful while it is on)"""
    today = today or datetime.date.today()
    (m1, d1) = EVENTS[ev]["season"][1]
    end = datetime.date(today.year, m1, d1)
    if end < today:
        end = datetime.date(today.year + 1, m1, d1)
    return (end - today).days


def event_state(save, ev, now=None, today=None):
    """-> (state, seconds or days left).  state: 'season' (the real thing), 'live' (secret, inside its week),
    'late' (playable, but the prize is a RIPOFF) or 'locked'"""
    now = now if now is not None else time.time()
    e = EVENTS[ev]
    if e["kind"] == "season" and in_season(ev, today):
        return "season", season_left(ev, today)
    t0 = save["events"].get(ev)
    if t0 is None:
        return "locked", 0
    if e["kind"] == "secret":
        left = t0 + EVENT_DAYS * 86400 - now
        if left > 0:
            return "live", left
    return "late", 0


# ---------------------------------------------------------------- titles
TITLES = {
    "rookie": ("ROOKIE", "Everyone starts here."),
    "defender": ("DEFENDER", "Win any game."),
    "veteran": ("VETERAN", "Beat every map on Normal."),
    "hardliner": ("HARDLINER", "Beat every map on Hard."),
    "insane": ("TRULY INSANE", "Beat every map on Insane."),
    "flawless": ("FLAWLESS", "Win on Insane without the core taking a scratch."),
    "team": ("TEAM PLAYER", "Win a Wi-Fi game with a friend."),
    "chatter": ("CHATTERBOX", "Talk to 12 different people on the maps."),
    "legend": ("LEGEND", "Reach level 30."),
    "pumpkin": ("PUMPKIN SLAYER", "Beat HAUNTED HOLLOW."),
    "frost": ("FROSTBREAKER", "Beat WINTER WORKS."),
    "duck": ("DUCK LORD", "Beat DUCK POND."),
    "chef": ("MASTER CHEF", "Beat THE KITCHEN."),
    "catperson": ("CAT PERSON", "Beat 404."),
    "stonks": ("DIAMOND HANDS", "Beat STONK MARKET."),
    "brick": ("UNBREAKABLE", "Beat THE QUARRY."),
    "secrets": ("SECRET KEEPER", "Unlock every secret event."),
}
for _m in MAIN_MAPS:
    TITLES["m_" + _m["id"]] = (_m["title"], "Beat %s on Insane." % _m["name"])
TITLE_ORDER = ["rookie", "defender"] + ["m_" + m["id"] for m in MAIN_MAPS] + ["veteran", "hardliner", "insane", "flawless", "team", "chatter", "legend",
                                                                           "pumpkin", "frost", "duck", "chef", "catperson", "stonks", "brick", "secrets"]


# ======================================================================
#  3D ENGINE  -  a small software renderer.  No extra libraries needed.
#  World: x goes right, y goes down the map, z goes up.
# ======================================================================
R_DARK, R_MAIN, R_LITE, R_METAL, R_WHITE, R_ALT, R_BLACK = 0, 1, 2, 3, 4, 5, 6
NROLES = 7
SPRITE_KEY = (3, 1, 2)                   # the see-through colour of the little pictures of unmoving things
LIGHT = (-0.42, -0.56, 0.71)
M_AIM, M_SPIN, M_BOB, M_RECOIL = 1, 2, 4, 8
# two more ways a group of parts can move (legs that walk, arms that hit).  They reuse three numbers of the group:
#   M_STEP:   speed = where in the stride this leg is (radians), bobs = how far it swings forward and back, boba = how high it lifts
#   M_STRIKE: bobs = how far it thrusts forward, boba = how high it rises, while the model's attack swing plays
M_STEP, M_STRIKE = 16, 32
CLOSE = 30.0            # anything nearer to the camera than this is drawn the careful (clipped) way
_X0, _Y0, _X1, _Y1 = -120.0, -120.0, W + 120.0, H + 120.0
_FAR = 3000.0


def clip_poly2d(pts):
    """cut a shape on the screen down to (a little more than) the window, so huge shapes stay correct and fast"""
    for ax, lim, less in ((0, _X0, False), (0, _X1, True), (1, _Y0, False), (1, _Y1, True)):
        if len(pts) < 3:
            return []
        out = []
        a = pts[-1]
        ain = (a[ax] <= lim) if less else (a[ax] >= lim)
        for b in pts:
            bin_ = (b[ax] <= lim) if less else (b[ax] >= lim)
            if ain != bin_:
                t = (lim - a[ax]) / (b[ax] - a[ax])
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            if bin_:
                out.append(b)
            a, ain = b, bin_
        pts = out
    return pts if len(pts) >= 3 else []


def clip_seg(x0, y0, x1, y1):
    """cut a line on the screen down to the window (or None when it misses it)"""
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - _X0), (dx, _X1 - x0), (-dy, y0 - _Y0), (dy, _Y1 - y0)):
        if p == 0:
            if q < 0:
                return None
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return None
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return None
                if t < t1:
                    t1 = t
    return (x0 + dx * t0, y0 + dy * t0, x0 + dx * t1, y0 + dy * t1)


class Cam:
    """a camera: perspective (3D) or flat (2D / icons)"""

    def __init__(self):
        self.x = self.y = 0.0
        self.z = 500.0
        self.yaw = -math.pi / 2
        self.pitch = 0.9
        self.F = 900.0
        self.ortho = False
        self.scale = 1.0
        self.cx, self.cy = W / 2.0, H / 2.0
        self.near = 6.0
        self.setup()

    def setup(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        self.f = (cy * cp, sy * cp, -sp)
        self.r = (-sy, cy, 0.0)
        self.u = (sp * cy, sp * sy, cp)

    def look(self, tx, ty, tz, dist, yaw, pitch):
        self.yaw, self.pitch = yaw, pitch
        self.setup()
        f = self.f
        self.x, self.y, self.z = tx - f[0] * dist, ty - f[1] * dist, tz - f[2] * dist

    def flat(self, cx, cy, wx, wy, scale):
        """top-down view: world point (wx, wy) lands on screen point (cx, cy)"""
        self.ortho = True
        self.scale = scale
        self.cx, self.cy = cx, cy
        self.yaw, self.pitch = -math.pi / 2, math.pi / 2
        self.x, self.y, self.z = wx, wy, 3000.0
        self.setup()

    def icon(self, cx, cy, scale, yaw, pitch=0.62):
        self.ortho = True
        self.scale = scale
        self.cx, self.cy = cx, cy
        self.yaw, self.pitch = yaw, pitch
        self.setup()
        f = self.f
        self.x, self.y, self.z = -f[0] * 2000, -f[1] * 2000, -f[2] * 2000

    def pt(self, x, y, z):
        """world point -> (screen x, screen y, pixels per unit) or None when it is behind the camera"""
        dx, dy, dz = x - self.x, y - self.y, z - self.z
        f = self.f
        d = dx * f[0] + dy * f[1] + dz * f[2]
        if self.ortho:
            k = self.scale
        else:
            if d < self.near:
                return None
            k = self.F / d
        r, u = self.r, self.u
        return (self.cx + (dx * r[0] + dy * r[1]) * k, self.cy - (dx * u[0] + dy * u[1] + dz * u[2]) * k, k)

    def depth(self, x, y, z):
        f = self.f
        return (x - self.x) * f[0] + (y - self.y) * f[1] + (z - self.z) * f[2]

    def ray(self, sx, sy):
        r, u, f = self.r, self.u, self.f
        a, b = sx - self.cx, self.cy - sy
        if self.ortho:
            k = 1.0 / self.scale
            return (self.x + (r[0] * a + u[0] * b) * k, self.y + (r[1] * a + u[1] * b) * k, self.z + u[2] * b * k), f
        F = self.F
        return (self.x, self.y, self.z), (f[0] * F + r[0] * a + u[0] * b, f[1] * F + r[1] * a + u[1] * b, f[2] * F + u[2] * b)

    def pick(self, sx, sy, h=0.0):
        """where the mouse ray meets the flat plane at height h"""
        o, d = self.ray(sx, sy)
        if d[2] > -1e-6:
            return None
        t = (h - o[2]) / d[2]
        if t < 0:
            return None
        return (o[0] + d[0] * t, o[1] + d[1] * t)


# ---------------------------------------------------------------- building models
class Model:
    def __init__(self):
        self.groups = []
        self.fixed = []         # extra fixed colours (roles 7, 8, ...)
        self.top = 20.0         # height, for labels
        self.rad = 14.0
        self.nfaces = 0


def _norm(v):
    d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / d, v[1] / d, v[2] / d)


def _part_bb(p):
    """the box a part of a model fits in: (x0, y0, z0, x1, y1, z1)"""
    k = p[1]
    if k == 0 or k == 2:
        vs = p[2]
        return (min(v[0] for v in vs), min(v[1] for v in vs), min(v[2] for v in vs), max(v[0] for v in vs), max(v[1] for v in vs), max(v[2] for v in vs))
    c = p[0]
    r = p[2] if k == 1 else 0.5
    return (c[0] - r, c[1] - r, c[2] - r, c[0] + r, c[1] + r, c[2] + r)


def _part_order(parts, bbs, cd):
    """the order to draw the parts of a model in, seen from direction cd (model -> camera).
    Far parts first - but a part is never drawn before something that it stands in front of or on top of.
    (Sorting by the middle of each part alone gets that wrong for a small part on a big one.)"""
    n = len(parts)
    dep = [p[0][0] * cd[0] + p[0][1] * cd[1] + p[0][2] * cd[2] for p in parts]      # bigger = nearer the camera
    after = [[] for _ in range(n)]
    need = [0] * n
    for i in range(n):
        a = bbs[i]
        for j in range(i + 1, n):
            b = bbs[j]
            fi = fj = False
            for ax in (0, 1, 2):
                c = cd[ax]
                if -0.1 < c < 0.1:
                    continue
                eps = min(3.0, 0.35 * min(a[ax + 3] - a[ax], b[ax + 3] - b[ax])) + 0.05
                if a[ax + 3] <= b[ax] + eps:
                    if c > 0:
                        fj = True
                    else:
                        fi = True
                elif b[ax + 3] <= a[ax] + eps:
                    if c > 0:
                        fi = True
                    else:
                        fj = True
            if fi and not fj:
                after[j].append(i)
                need[i] += 1
            elif fj and not fi:
                after[i].append(j)
                need[j] += 1
    order = []
    left = set(range(n))
    while left:
        free = [i for i in left if need[i] <= 0] or list(left)
        i = min(free, key=lambda k: (dep[k], k))
        left.discard(i)
        order.append(parts[i])
        for j in after[i]:
            need[j] -= 1
    return order


def _group_cmp(a, b):
    """which part-group of a model is drawn first: the lower one when one sits on top of the other, else the far one"""
    if a[8] <= b[7] + 1.5:
        return -1 if a[10] else 1
    if b[8] <= a[7] + 1.5:
        return 1 if a[10] else -1
    return -1 if a[0] > b[0] else 1 if a[0] < b[0] else 0


class MB:
    """model builder.  Local space: +x is forward (where it aims), z is up."""

    def __init__(self):
        self.m = Model()
        self.parts = None
        self.fixmap = {}
        self.group()

    def done(self, top=None, rad=None):
        m = self.m
        groups = []
        hi = 1.0
        for g in m.groups:
            parts = g[7]
            if not parts:
                continue
            bbs = [_part_bb(p) for p in parts]
            # (..., parts, draw-order cache, part boxes, lowest z, highest z, the box all of it fits in, its glows)
            box = (min(b[0] for b in bbs), min(b[1] for b in bbs), min(b[2] for b in bbs), max(b[3] for b in bbs), max(b[4] for b in bbs), max(b[5] for b in bbs))
            groups.append(g + ({}, bbs, box[2], box[5], box, tuple(p for p in parts if p[1] == 3)))
            for p in parts:
                hi = max(hi, p[0][2] + g[4])
        m.groups = groups
        m.top = top if top is not None else hi * 1.5
        if rad:
            m.rad = rad
        return m

    def group(self, mode=0, speed=0.0, px=0.0, py=0.0, pz=0.0, bobs=2.0, boba=2.0):
        """start a new group of parts.  mode = M_AIM | M_SPIN | M_BOB | M_RECOIL | M_STEP | M_STRIKE (see the top of this part)"""
        self.parts = []
        self.m.groups.append((mode, speed, px, py, pz, bobs, boba, self.parts))
        return self

    def role(self, r):
        if isinstance(r, int):
            return r
        i = self.fixmap.get(r)
        if i is None:
            i = self.fixmap[r] = NROLES + len(self.m.fixed)
            self.m.fixed.append(r)
        return i

    def mesh(self, verts, faces, role, edge=True, two=False, orient=True):
        """faces = lists of vertex numbers.  Normals are worked out so they point away from the middle
        (orient=False keeps the way the corners are listed: used for flat things that have to face up)."""
        roles = [self.role(x) for x in role] if isinstance(role, list) else [self.role(role)] * len(faces)
        n = float(len(verts))
        c = (sum(v[0] for v in verts) / n, sum(v[1] for v in verts) / n, sum(v[2] for v in verts) / n)
        out = []
        for fi, idx in enumerate(faces):
            role = roles[fi]
            a, b, d = verts[idx[0]], verts[idx[1]], verts[idx[2]]
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = d[0] - a[0], d[1] - a[1], d[2] - a[2]
            nx, ny, nz = _norm((uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx))
            fc = [sum(verts[i][k] for i in idx) / len(idx) for k in range(3)]
            if orient and not two and (fc[0] - c[0]) * nx + (fc[1] - c[1]) * ny + (fc[2] - c[2]) * nz < 0:
                nx, ny, nz = -nx, -ny, -nz
            out.append((tuple(idx), nx, ny, nz, nx * a[0] + ny * a[1] + nz * a[2], role, edge))
            if two:
                out.append((tuple(idx), -nx, -ny, -nz, -(nx * a[0] + ny * a[1] + nz * a[2]), role, edge))
        self.parts.append((c, 0, [tuple(v) for v in verts], out))
        self.m.nfaces += len(out)
        return self

    def box(self, x, y, z, hx, hy, h, role, taper=1.0, rot=0.0, edge=True, bottom=False):
        ca, sa = math.cos(rot), math.sin(rot)
        vs = []
        for k, zz in ((1.0, z), (taper, z + h)):
            for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
                lx, ly = dx * k, dy * k
                vs.append((x + lx * ca - ly * sa, y + lx * sa + ly * ca, zz))
        fs = [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        if bottom:
            fs.append((0, 3, 2, 1))
        return self.mesh(vs, fs, role, edge)

    def prism(self, n, x, y, z, r, h, role, rtop=None, rot=0.0, edge=True, bottom=False):
        if rtop is None:
            rtop = r
        vs = [(x + math.cos(rot + i * TAU / n) * r, y + math.sin(rot + i * TAU / n) * r, z) for i in range(n)]
        fs = []
        if rtop <= 0.01:
            vs.append((x, y, z + h))
            fs = [(i, (i + 1) % n, n) for i in range(n)]
        else:
            vs += [(x + math.cos(rot + i * TAU / n) * rtop, y + math.sin(rot + i * TAU / n) * rtop, z + h) for i in range(n)]
            fs = [tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        if bottom:
            fs.append(tuple(range(n - 1, -1, -1)))
        return self.mesh(vs, fs, role, edge)

    def crystal(self, x, y, z, r, h, role, n=4, rot=0.0, mid=0.5, edge=True):
        """two pyramids stuck together: a gem"""
        zm = z + h * mid
        vs = [(x + math.cos(rot + i * TAU / n) * r, y + math.sin(rot + i * TAU / n) * r, zm) for i in range(n)]
        vs += [(x, y, z + h), (x, y, z)]
        fs = [(i, (i + 1) % n, n) for i in range(n)] + [(i, (i + 1) % n, n + 1) for i in range(n)]
        return self.mesh(vs, fs, role, edge)

    def bar(self, p0, p1, r, role, n=4, r1=None, edge=True, rot=0.0):
        """a stick between two points (barrels, masts, arms)"""
        if r1 is None:
            r1 = r
        ax = _norm((p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]))
        up = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)
        sd = _norm((ax[1] * up[2] - ax[2] * up[1], ax[2] * up[0] - ax[0] * up[2], ax[0] * up[1] - ax[1] * up[0]))
        u2 = (sd[1] * ax[2] - sd[2] * ax[1], sd[2] * ax[0] - sd[0] * ax[2], sd[0] * ax[1] - sd[1] * ax[0])
        vs = []
        for p, rr in ((p0, r), (p1, r1)):
            for i in range(n):
                a = rot + (i + 0.5) * TAU / n
                c, s = math.cos(a) * rr, math.sin(a) * rr
                vs.append((p[0] + sd[0] * c + u2[0] * s, p[1] + sd[1] * c + u2[1] * s, p[2] + sd[2] * c + u2[2] * s))
        fs = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        fs.append(tuple(range(n, 2 * n)))
        fs.append(tuple(range(n - 1, -1, -1)))
        return self.mesh(vs, fs, role, edge)

    def slab(self, pts, role, edge=True):
        """a flat shape you can see from both sides (blades, flags, panels)"""
        return self.mesh(pts, [tuple(range(len(pts)))], role, edge, True)

    def ball(self, x, y, z, r, role):
        self.parts.append(((x, y, z), 1, r, self.role(role)))
        return self

    def line(self, pts, role, width=1, closed=False):
        n = float(len(pts))
        c = (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)
        self.parts.append((c, 2, [tuple(p) for p in pts], self.role(role), width, closed))
        return self

    def ring(self, x, y, z, r, role, n=14, width=1, tilt=0.0, trot=0.0):
        pts = []
        ct, st = math.cos(tilt), math.sin(tilt)
        cr, sr = math.cos(trot), math.sin(trot)
        for i in range(n):
            a = i * TAU / n
            px, py, pz = math.cos(a) * r, math.sin(a) * r * ct, math.sin(a) * r * st
            pts.append((x + px * cr - py * sr, y + px * sr + py * cr, z + pz))
        np_ = 8 if n >= 12 else 4 if n >= 8 else 1
        if np_ == 1 or r < 5:
            return self.line(pts, role, width, True)
        # a ring goes around things, so it is cut into arcs: the far arcs are drawn behind, the near ones in front
        for k in range(np_):
            i0, i1 = k * n // np_, (k + 1) * n // np_
            self.line([pts[i % n] for i in range(i0, i1 + 1)], role, width, False)
        return self

    def glow(self, x, y, z, r, role, k=1.0):
        self.parts.append(((x, y, z), 3, r, self.role(role), k))
        return self


# ---------------------------------------------------------------- colours for models
_pal_cache = {}
_SHADES = (0.34, 0.46, 0.60, 0.76, 0.90, 1.0)


def _ramp(col, emissive=False):
    if emissive:
        return tuple(scale_col(col, 0.80 + 0.04 * i) for i in range(6))
    return tuple(scale_col(col, k) for k in _SHADES)


def palette(col, fixed=(), flash=False, dim=1.0, ghost=False):
    """what each colour role looks like for a thing painted `col`.  -> list of (6 shades, edge colour)"""
    key = (col, tuple(fixed), flash, dim, ghost)
    p = _pal_cache.get(key)
    if p is None:
        if len(_pal_cache) > 700:
            _pal_cache.clear()
        if flash:
            w = _ramp((255, 255, 255), True)
            p = [(w, (255, 255, 255))] * (NROLES + len(fixed))
        else:
            c = col if dim >= 1.0 else scale_col(col, dim)
            base = [
                (_ramp(mix_col((30, 36, 62), c, 0.16)), scale_col(c, 0.62)),
                (_ramp(mix_col((14, 16, 30), c, 0.62)), mix_col(c, WHITE, 0.25)),
                (_ramp(mix_col(c, WHITE, 0.25), True), mix_col(c, WHITE, 0.7)),
                (_ramp((104, 114, 150)), (176, 186, 220)),
                (_ramp((236, 242, 255), True), (255, 255, 255)),
                (_ramp(mix_col((40, 30, 10), GOLD, 0.8)), (255, 236, 150)),
                (_ramp((16, 18, 34)), scale_col(c, 0.45)),
            ]
            for fc in fixed:
                fc2 = fc if dim >= 1.0 else scale_col(fc, dim)
                base.append((_ramp(mix_col((10, 10, 16), fc2, 0.93)), mix_col(fc2, WHITE, 0.35)))
            if ghost:
                base = [(tuple(scale_col(x, 0.35) for x in r), scale_col(e, 0.7)) for r, e in base]
            p = base
        _pal_cache[key] = p
    return p


def model_pose(m):
    """What a picture of a whole model has to know (worked out once per model):
    (how far it reaches sideways, lowest point, highest point, its one spin speed or 0, bob speed, bob height, its glows,
    has it legs, has it striking parts) - or False when it moves in too many ways at once to be kept as pictures."""
    p = getattr(m, "pose", None)
    if p is not None:
        return p
    spins, bobs, glows = set(), set(), []
    rad, z0, z1 = 4.0, 0.0, 4.0
    step = strike = False
    for g in m.groups:
        mode = g[0]
        if mode & 2:
            spins.add(g[1])
        if mode & 4:
            bobs.add((g[5], g[6]))
        ex = ez = 0.0
        if mode & 16:
            step = True
            ex, ez = abs(g[5]), abs(g[6])
        if mode & 32:
            strike = True
            if not mode & 4:
                ex, ez = max(ex, abs(g[5])), max(ez, abs(g[6]))
        b = g[12]
        r = max(math.hypot(b[0], b[1]), math.hypot(b[3], b[4]), math.hypot(b[0], b[4]), math.hypot(b[3], b[1])) + math.hypot(g[2], g[3]) + ex
        rad = max(rad, r)
        z0 = min(z0, b[2] + g[4] - (abs(g[6]) if mode & 4 else 0.0))
        z1 = max(z1, b[5] + g[4] + ez + (abs(g[6]) if mode & 4 else 0.0))
        for part in g[13]:
            c = part[0]
            glows.append((c[0] + g[2], c[1] + g[3], c[2] + g[4], part[2], part[3], part[4], bool(mode & 1)))
    if len(spins) > 1 or len(bobs) > 1:
        m.pose = False
    else:
        bs, ba = list(bobs)[0] if bobs else (0.0, 0.0)
        m.pose = (rad, z0, z1, list(spins)[0] if spins else 0.0, bs, ba, tuple(glows), step, strike)
    return m.pose


# ---------------------------------------------------------------- drawing
class R3D:
    def __init__(self):
        self.cam = Cam()
        self.s = None
        self.edges = True
        self.faces = 0
        self.sprites = {}           # pictures of the parts of things that do not move (see hold)
        self.poses = {}             # pictures of whole walkers in one pose (see walker)
        self.icam = Cam()
        self.sig = None
        self.still = 0
        self.cache_on = False

    def begin(self, s, cam):
        self.s = s
        self.cam = cam
        self.faces = 0

    def hold(self, cam, uid=None):
        """Call once per frame for the camera a match is seen through.  While that camera does not turn or zoom, the
        parts of things that never move (scenery, plinths, the bodies of towers) are drawn ONCE into little pictures
        and pasted from then on - that is what pays for the detailed models.  Walking about (the camera only slides)
        keeps a picture good until the thing has shifted a few degrees in view; then it is drawn again."""
        sig = (uid, cam.ortho, cam.r, cam.u, cam.f, round(cam.F, 3), round(cam.scale, 4), round(cam.z, 1))
        if sig != self.sig:
            self.sig = sig
            self.sprites.clear()
            self.still = 0
        else:
            self.still += 1
        if len(self.sprites) > 1600:
            self.sprites.clear()
        self.cache_on = self.still >= 2

    def model(self, m, pal, x, y, z, ang=0.0, t=0.0, sc=1.0, recoil=0.0, edges=True, walk=0.0, act=0.0, cache=None):
        """walk = how far through its stride a walker is (radians), act = how far through an attack swing (0 = not attacking .. 1).
        cache = a name for this very thing standing in this very spot (or None): lets its unmoving parts be pasted, see hold()"""
        cam = self.cam
        s = self.s
        scx, scy = cam.cx, cam.cy
        r0, r1, r2 = cam.r
        u0, u1, u2 = cam.u
        f0, f1, f2 = cam.f
        ortho = cam.ortho
        F = cam.F
        ks = cam.scale
        near = cam.near
        dx, dy, dz = x - cam.x, y - cam.y, z - cam.z
        if cache is not None and self.cache_on:
            hit = self.sprites.get((cache, edges))
            if hit is not None:
                # the whole thing is one picture: is it still good from here?
                tx = r0 * dx + r1 * dy + r2 * dz
                ty = u0 * dx + u1 * dy + u2 * dz
                if ortho:
                    s.blit(hit[0], (scx + tx * ks + hit[1], scy - ty * ks + hit[2]))
                    self.faces += hit[3]
                    return
                tz = f0 * dx + f1 * dy + f2 * dz
                if tz > near:
                    k = F / tz
                    if abs(k - hit[4]) < hit[4] * 0.03 and abs(tx / tz - hit[5]) < 0.07 and abs(ty / tz - hit[6]) < 0.07:
                        s.blit(hit[0], (scx + tx * k + hit[1], scy - ty * k + hit[2]))
                        self.faces += hit[3]
                        return
        LX, LY, LZ = LIGHT
        polygon = pygame.draw.polygon
        cos, sin = math.cos, math.sin
        edges = edges and self.edges
        glist = []
        for g in m.groups:
            mode = g[0]
            a = 0.0
            if mode & 1:
                a = ang
            if mode & 2:
                a += t * g[1]
            c0, s0 = cos(a), sin(a)
            ox, oy, oz = dx + g[2] * sc, dy + g[3] * sc, dz + g[4] * sc
            if mode & 4:
                oz += sin(t * g[5]) * g[6] * sc
            if mode & 8 and recoil:
                ox -= cos(ang) * recoil * 4.0 * sc
                oy -= sin(ang) * recoil * 4.0 * sc
            if mode > 15:
                if mode & 16:
                    # a leg: forward and back along the way the model faces, lifted on the way forward
                    ph = walk + g[1]
                    k = sin(ph) * g[5] * sc
                    ox += cos(ang) * k
                    oy += sin(ang) * k
                    k = cos(ph)
                    if k > 0:
                        oz += k * g[6] * sc
                if mode & 32 and act:
                    # an arm (or a head, a ram, a claw): out and back once per attack
                    k = sin(math.pi * act) * sc
                    ox += cos(ang) * k * g[5]
                    oy += sin(ang) * k * g[5]
                    oz += k * g[6]
            zb = oz + (g[10] + g[11]) * 0.5 * sc
            glist.append((f0 * ox + f1 * oy + f2 * zb, c0, s0, ox, oy, oz, g[7], oz + g[10] * sc, oz + g[11] * sc, g, oz + g[11] * sc < 0 or ortho))
        if len(glist) > 1:
            glist.sort(key=_group_key)
        nf = 0
        for gl in glist:
            c0, s0, ox, oy, oz, parts = gl[1:7]
            g = gl[9]
            gd = f0 * ox + f1 * oy + f2 * oz
            ca, sa = c0 * sc, s0 * sc
            m00, m01, m02 = r0 * ca + r1 * sa, -r0 * sa + r1 * ca, r2 * sc
            m10, m11, m12 = u0 * ca + u1 * sa, -u0 * sa + u1 * ca, u2 * sc
            m20, m21, m22 = f0 * ca + f1 * sa, -f0 * sa + f1 * ca, f2 * sc
            tx = r0 * ox + r1 * oy + r2 * oz
            ty = u0 * ox + u1 * oy + u2 * oz
            tz = gd
            if ortho:
                clx, cly, clz = -(f0 * c0 + f1 * s0), -(-f0 * s0 + f1 * c0), -f2
            else:
                clx, cly, clz = (-ox * c0 - oy * s0) / sc, (ox * s0 - oy * c0) / sc, -oz / sc
            Lx, Ly = LX * c0 + LY * s0, -LX * s0 + LY * c0
            spr = None
            if cache is not None and g[0] == 0 and self.cache_on:
                ckey = (cache, id(g), edges)
                hit = self.sprites.get(ckey)
                if ortho:
                    k0 = ks
                    nx0 = ny0 = 0.0
                elif tz > near:
                    k0 = F / tz
                    nx0, ny0 = tx / tz, ty / tz
                    if hit is not None and not (abs(k0 - hit[4]) < hit[4] * 0.03 and abs(nx0 - hit[5]) < 0.07 and abs(ny0 - hit[6]) < 0.07):
                        hit = None          # it has shifted too far in view since its picture was made: make a new one
                else:
                    k0 = 0.0
                    hit = None
                gx0, gy0 = scx + tx * k0, scy - ty * k0     # where this group's own middle is on the screen
                if hit is None and k0 > 0.0:
                    # the first time since the camera stopped: draw this group into its own little picture
                    x0, y0, z0, x1, y1, z1 = g[12]
                    lox = loy = 1e9
                    hix = hiy = -1e9
                    for vx in (x0, x1):
                        for vy in (y0, y1):
                            for vz in (z0, z1):
                                if ortho:
                                    k = ks
                                else:
                                    zc = m20 * vx + m21 * vy + m22 * vz + tz
                                    if zc < CLOSE * 1.5:
                                        lox = None
                                        break
                                    k = F / zc
                                px = scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k
                                py = scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k
                                if px < lox:
                                    lox = px
                                if px > hix:
                                    hix = px
                                if py < loy:
                                    loy = py
                                if py > hiy:
                                    hiy = py
                            if lox is None:
                                break
                        if lox is None:
                            break
                    if lox is not None:
                        bx, by = int(lox) - 4, int(loy) - 4
                        bw, bh = int(hix) - bx + 5, int(hiy) - by + 5
                        if bw <= 460 and bh <= 460 and bx < W and by < H and bx + bw > 0 and by + bh > 0:
                            spr = pygame.Surface((bw, bh))
                            spr.fill(SPRITE_KEY)
                            spr.set_colorkey(SPRITE_KEY)
                            s_main, scx_main, scy_main, nf_main = s, scx, scy, nf
                            s, scx, scy = spr, scx - bx, scy - by
                if hit is not None:
                    s.blit(hit[0], (gx0 + hit[1], gy0 + hit[2]))
                    nf += hit[3]
                    if g[13] and GFX["glow"]:
                        for part in g[13]:
                            vx, vy, vz = part[0]
                            zc = m20 * vx + m21 * vy + m22 * vz + tz
                            if ortho:
                                k = ks
                            elif zc < near:
                                continue
                            else:
                                k = F / zc
                            glow(s, scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k, scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k, part[2] * k * sc, pal[part[3]][1], part[4])
                    continue
            if len(parts) > 1:
                # the right order only depends on where the camera is around the model, so it is worked out once per direction
                key = (int(math.atan2(cly, clx) * 3.8197 + 12.5), int(math.atan2(clz, math.sqrt(clx * clx + cly * cly)) * 5.0 + 8.5))
                order = g[8].get(key)
                if order is None:
                    ya, pa = (key[0] - 12) / 3.8197, (key[1] - 8) / 5.0
                    order = g[8][key] = _part_order(parts, g[9], (cos(ya) * cos(pa), sin(ya) * cos(pa), sin(pa)))
            else:
                order = parts
            for part in order:
                kind = part[1]
                if kind == 0:
                    pts = []
                    ok = True
                    for vx, vy, vz in part[2]:
                        if ortho:
                            k = ks
                        else:
                            zc = m20 * vx + m21 * vy + m22 * vz + tz
                            if zc < CLOSE:
                                ok = False
                                break
                            k = F / zc
                        pts.append((scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k, scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k))
                    if not ok:
                        # part of it is right next to (or behind) the camera: cut every face properly
                        cs = [(m00 * vx + m01 * vy + m02 * vz + tx, m10 * vx + m11 * vy + m12 * vz + ty, m20 * vx + m21 * vy + m22 * vz + tz) for vx, vy, vz in part[2]]
                        if max(c[2] for c in cs) < near:
                            continue
                        for idx, nx, ny, nz, d0, role, edge in part[3]:
                            if nx * clx + ny * cly + nz * clz - d0 <= 0:
                                continue
                            p = self.cs_shape([cs[i] for i in idx])
                            if p:
                                sh = int((nx * Lx + ny * Ly + nz * LZ + 1.0) * 2.99)
                                fills, ecol = pal[role]
                                polygon(s, fills[sh], p)
                                if edge and edges:
                                    polygon(s, ecol, p, 1)
                                nf += 1
                        continue
                    for idx, nx, ny, nz, d0, role, edge in part[3]:
                        if ortho:
                            if nx * clx + ny * cly + nz * clz < 0.02:
                                continue
                        elif nx * clx + ny * cly + nz * clz - d0 <= 0:
                            continue
                        sh = int((nx * Lx + ny * Ly + nz * LZ + 1.0) * 2.99)
                        fills, ecol = pal[role]
                        p = [pts[i] for i in idx]
                        polygon(s, fills[sh], p)
                        if edge and edges:
                            polygon(s, ecol, p, 1)
                        nf += 1
                else:
                    vx, vy, vz = part[0]
                    zc = m20 * vx + m21 * vy + m22 * vz + tz
                    if ortho:
                        k = ks
                    elif zc < near:
                        continue
                    else:
                        k = F / zc
                    if kind == 1:
                        px = scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k
                        py = scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k
                        rr = part[2] * k * sc
                        fills, ecol = pal[part[3]]
                        if rr < 1.6:
                            s.fill(fills[4], (px - 1, py - 1, 2, 2))
                        else:
                            pygame.draw.circle(s, fills[3], (px, py), rr)
                            if rr > 3:
                                pygame.draw.circle(s, fills[5], (px - rr * 0.22, py - rr * 0.26), rr * 0.62)
                                if edges:
                                    pygame.draw.circle(s, ecol, (px, py), rr, 1)
                        nf += 1
                    elif kind == 2:
                        pts = []
                        ok = True
                        for vx, vy, vz in part[2]:
                            if ortho:
                                k = ks
                            else:
                                zc = m20 * vx + m21 * vy + m22 * vz + tz
                                if zc < CLOSE:
                                    ok = False
                                    break
                                k = F / zc
                            pts.append((scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k, scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k))
                        if ok:
                            if len(pts) > 1:
                                pygame.draw.lines(s, pal[part[3]][1], part[5], pts, part[4])
                        else:
                            cs = [(m00 * vx + m01 * vy + m02 * vz + tx, m10 * vx + m11 * vy + m12 * vz + ty, m20 * vx + m21 * vy + m22 * vz + tz) for vx, vy, vz in part[2]]
                            col = pal[part[3]][1]
                            for i in range(len(cs) - 1):
                                self.cs_line(cs[i], cs[i + 1], col, part[4])
                            if part[5] and len(cs) > 2:
                                self.cs_line(cs[-1], cs[0], col, part[4])
                    elif GFX["glow"] and spr is None:
                        px = scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k
                        py = scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k
                        glow(s, px, py, part[2] * k * sc, pal[part[3]][1], part[4])
            if spr is not None:
                # the picture is done: keep it, paste it, and put the glows (which shine THROUGH things) on top
                s, scx, scy = s_main, scx_main, scy_main
                self.sprites[ckey] = (spr, bx - gx0, by - gy0, nf - nf_main, k0, nx0, ny0)
                if len(m.groups) == 1 and not g[13] and not (g[2] or g[3] or g[4]):
                    self.sprites[(cache, edges)] = self.sprites[ckey]      # the whole thing is this one picture
                s.blit(spr, (bx, by))
                if g[13] and GFX["glow"]:
                    for part in g[13]:
                        vx, vy, vz = part[0]
                        zc = m20 * vx + m21 * vy + m22 * vz + tz
                        if ortho:
                            k = ks
                        elif zc < near:
                            continue
                        else:
                            k = F / zc
                        glow(s, scx + (m00 * vx + m01 * vy + m02 * vz + tx) * k, scy - (m10 * vx + m11 * vy + m12 * vz + ty) * k, part[2] * k * sc, pal[part[3]][1], part[4])
        self.faces += nf

    def pose_picture(self, m, pal, scale, yaw, pitch, ang, t, edges, walk, act):
        """a whole model drawn into a little see-through picture.  -> (picture, where its feet are in it: x, y) or None if too big"""
        pose = model_pose(m)
        rad, z0, z1 = pose[0], pose[1], pose[2]
        cp, sp = math.cos(pitch), math.sin(pitch)
        up = z1 * cp + rad * sp
        down = -z0 * cp + rad * sp
        bw, bh = int(2 * rad * scale) + 10, int((up + down) * scale) + 10
        if bw > 340 or bh > 340:
            return None
        ax, ay = bw / 2.0, 5 + up * scale
        spr = pygame.Surface((bw, bh))
        spr.fill(SPRITE_KEY)
        spr.set_colorkey(SPRITE_KEY)
        ic = self.icam
        ic.icon(ax, ay, scale, yaw, pitch)
        was = (self.s, self.cam, self.cache_on, GFX["glow"], self.faces)
        self.s, self.cam, self.cache_on, GFX["glow"] = spr, ic, False, False
        try:
            self.model(m, pal, 0.0, 0.0, 0.0, ang, t, 1.0, 0.0, edges, walk, act)
        finally:
            self.s, self.cam, self.cache_on, GFX["glow"], self.faces = was
        return spr, ax, ay

    def walker(self, m, pal, x, y, z, ang, t, edges=True, walk=0.0, act=0.0):
        """Things that come in crowds (enemies, goons).  One of them is drawn into a little picture and every other one
        that is in the same pose, turned the same way and about as far away gets that picture pasted: a crowd of fifty
        costs about as much as five.  Models that spin and bob in several ways at once are simply drawn."""
        cam = self.cam
        pose = model_pose(m)
        if pose is False or cam.ortho:
            return self.model(m, pal, x, y, z, ang, t, 1.0, 0.0, edges, walk, act)
        q = cam.pt(x, y, z)
        if q is None:
            return
        k = q[2]
        if k > 3.4 or k < 0.2:
            return self.model(m, pal, x, y, z, ang, t, 1.0, 0.0, edges, walk, act)
        rad, z0, z1, spin, bs, ba, glows, step, strike = pose
        kb = int(math.log(k) * 13.0 + 100.0)
        ab = int(((ang - cam.yaw) % TAU) * (36 / TAU) + 0.5) % 36
        pb = int(cam.pitch * 16.0)
        wb = int((walk % TAU) * (8 / TAU)) if step else 0
        cb = 0 if (act <= 0 or not strike) else 1 + min(3, int(act * 4.0))
        if spin:
            sb = int(((t * spin) % TAU) * (24 / TAU))
            ts = (sb + 0.5) * (TAU / 24) / spin
        else:
            sb = 0
            ts = 0.0
        key = (id(m), id(pal), kb, ab, pb, wb, cb, sb, edges)
        hit = self.poses.get(key)
        if hit is None:
            if len(self.poses) > 1500:
                self.poses.clear()
            hit = self.pose_picture(m, pal, math.exp((kb - 99.5) / 13.0), 0.0, (pb + 0.5) / 16.0, ab * (TAU / 36), ts, edges,
                                    (wb + 0.5) * (TAU / 8) if step else 0.0, (cb - 0.5) / 4.0 if cb else 0.0)
            self.poses[key] = hit if hit is not None else False
        if not hit:
            return self.model(m, pal, x, y, z, ang, t, 1.0, 0.0, edges, walk, act)
        dy = 0.0
        if bs:
            dy = (math.sin(ts * bs) - math.sin(t * bs)) * ba * k * math.cos(cam.pitch)
        self.s.blit(hit[0], (q[0] - hit[1], q[1] - hit[2] + dy))
        self.faces += 1
        if glows and GFX["glow"]:
            ca, sa = math.cos(ang), math.sin(ang)
            for gx, gy, gz, gr, role, gk, aimed in glows:
                if aimed:
                    gx, gy = gx * ca - gy * sa, gx * sa + gy * ca
                g2 = cam.pt(x + gx, y + gy, z + gz)
                if g2 is not None:
                    glow(self.s, g2[0], g2[1], min(260, gr * g2[2]), pal[role][1], gk)

    # ---- shapes given in camera space (x right, y up, z forward)
    def cs_shape(self, cs):
        """a camera-space shape -> screen points, cut at the camera and at the window edges ([] when nothing is left)"""
        cam = self.cam
        near = cam.near
        lo = min(c[2] for c in cs)
        if lo < near:
            cl = []
            n = len(cs)
            for i in range(n):
                a, b = cs[i], cs[(i + 1) % n]
                ina, inb = a[2] >= near, b[2] >= near
                if ina:
                    cl.append(a)
                if ina != inb:
                    t = (near - a[2]) / (b[2] - a[2])
                    cl.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near))
            cs = cl
            if len(cs) < 3:
                return []
        F = cam.F
        sx, sy = cam.cx, cam.cy
        out = [(sx + c[0] * F / c[2], sy - c[1] * F / c[2]) for c in cs]
        if lo < CLOSE or max(max(abs(p[0]), abs(p[1])) for p in out) > _FAR:
            out = clip_poly2d(out)
        return out

    def cs_line(self, a, b, col, width=1):
        cam = self.cam
        near = cam.near
        if a[2] < near:
            if b[2] < near:
                return
            t = (near - a[2]) / (b[2] - a[2])
            a = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near)
        elif b[2] < near:
            t = (near - b[2]) / (a[2] - b[2])
            b = (b[0] + (a[0] - b[0]) * t, b[1] + (a[1] - b[1]) * t, near)
        F = cam.F
        x0, y0 = cam.cx + a[0] * F / a[2], cam.cy - a[1] * F / a[2]
        x1, y1 = cam.cx + b[0] * F / b[2], cam.cy - b[1] * F / b[2]
        if not (_X0 <= x0 <= _X1 and _Y0 <= y0 <= _Y1 and _X0 <= x1 <= _X1 and _Y0 <= y1 <= _Y1):
            sg = clip_seg(x0, y0, x1, y1)
            if sg is None:
                return
            x0, y0, x1, y1 = sg
        pygame.draw.line(self.s, col, (x0, y0), (x1, y1), width)

    def to_cs(self, pts3):
        cam = self.cam
        cx, cy, cz = cam.x, cam.y, cam.z
        r, u, f = cam.r, cam.u, cam.f
        out = []
        for p in pts3:
            dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
            out.append((dx * r[0] + dy * r[1], dx * u[0] + dy * u[1] + dz * u[2], dx * f[0] + dy * f[1] + dz * f[2]))
        return out

    # ---- loose shapes in the world
    def poly(self, pts3, col, edge=None, width=0):
        """a filled shape; cut properly when part of it is behind the camera or far off the screen"""
        cam = self.cam
        if cam.ortho:
            out = []
            for p in pts3:
                q = cam.pt(p[0], p[1], p[2])
                out.append((q[0], q[1]))
        else:
            out = self.cs_shape(self.to_cs(pts3))
        if len(out) < 3:
            return
        if col is not None:
            pygame.draw.polygon(self.s, col, out, width)
        if edge is not None:
            pygame.draw.polygon(self.s, edge, out, 1)
        self.faces += 1

    def line(self, a, b, col, width=1):
        cam = self.cam
        if cam.ortho:
            p, q = cam.pt(a[0], a[1], a[2]), cam.pt(b[0], b[1], b[2])
            pygame.draw.line(self.s, col, (p[0], p[1]), (q[0], q[1]), width)
            return
        cs = self.to_cs((a, b))
        self.cs_line(cs[0], cs[1], col, width)

    def lines(self, pts3, col, width=1, closed=False):
        cam = self.cam
        if cam.ortho:
            out = []
            for p in pts3:
                q = cam.pt(p[0], p[1], p[2])
                out.append((q[0], q[1]))
            if len(out) > 1:
                pygame.draw.lines(self.s, col, closed, out, width)
            return
        cs = self.to_cs(pts3)
        n = len(cs)
        if n < 2:
            return
        if min(c[2] for c in cs) >= CLOSE:
            F = cam.F
            sx, sy = cam.cx, cam.cy
            out = [(sx + c[0] * F / c[2], sy - c[1] * F / c[2]) for c in cs]
            if max(max(abs(p[0]), abs(p[1])) for p in out) <= _FAR:
                pygame.draw.lines(self.s, col, closed, out, width)
                return
        for i in range(n - 1):
            self.cs_line(cs[i], cs[i + 1], col, width)
        if closed and n > 2:
            self.cs_line(cs[-1], cs[0], col, width)

    def ring(self, x, y, z, r, col, width=2, n=28, fill=None):
        if r <= 0.5:
            return
        step = TAU / n
        pts = [(x + math.cos(i * step) * r, y + math.sin(i * step) * r, z) for i in range(n)]
        if fill is not None:
            self.poly(pts, fill)
        self.lines(pts, col, width, True)

    def dot(self, x, y, z, r, col, glowk=0.0):
        q = self.cam.pt(x, y, z)
        if q is None:
            return
        rr = r * q[2]
        if rr < 1.3:
            self.s.fill(col, (q[0] - 1, q[1] - 1, 2, 2))
        else:
            pygame.draw.circle(self.s, col, (q[0], q[1]), rr)
        if glowk:
            glow(self.s, q[0], q[1], rr * 4, col, glowk)

    def glow(self, x, y, z, r, col, k=1.0):
        q = self.cam.pt(x, y, z)
        if q is not None and -200 < q[0] < W + 200 and -200 < q[1] < H + 200:
            glow(self.s, q[0], q[1], min(260, r * q[2]), col, k)

    def text(self, txt, size, col, x, y, z, dy=0):
        q = self.cam.pt(x, y, z)
        if q is not None and -100 < q[0] < W + 100 and -50 < q[1] < H + 50:
            draw_text(self.s, txt, size, col, q[0], q[1] + dy)
            return q
        return None


def _first(t):
    return t[0]


_group_key = functools.cmp_to_key(_group_cmp)


# ======================================================================
#  TOWER MODELS  -  every tower has 5 designs, one per level
# ======================================================================
def _pad(b, lv, r=13.0, n=6, box=15.0):
    """the base a tower stands on.  It grows with the level, but never past the tower's boundary box
    (so two towers standing side by side never poke into each other)."""
    rot = math.pi / 4 if n == 4 else 0.0
    if lv == 0:
        b.prism(n, 0, 0, 0, r, 3, R_DARK, rot=rot)
        return 3.0
    if lv == 1:
        b.prism(n, 0, 0, 0, r + 1, 3, R_DARK, rot=rot)
        b.prism(n, 0, 0, 3, r - 3, 2, R_MAIN, rot=rot)
        return 5.0
    if lv == 2:
        b.prism(n, 0, 0, 0, r + 1.5, 3, R_DARK, rot=rot)
        b.prism(n, 0, 0, 3, r - 2, 3, R_MAIN, rtop=r - 4, rot=rot)
        return 6.0
    if lv == 3:
        b.prism(n, 0, 0, 0, r + 2, 3, R_DARK, rot=rot)
        b.prism(n, 0, 0, 3, r - 1, 3, R_METAL, rtop=r - 3.5, rot=rot)
        b.ring(0, 0, 3.3, r + 0.6, R_LITE, 12, 2)
        return 6.0
    b.prism(n, 0, 0, 0, r + 3 if n == 4 else min(r + 3, box), 3, R_DARK, rot=rot)
    b.prism(n, 0, 0, 3, r, 2, R_ALT, rot=rot)
    b.prism(n, 0, 0, 5, r - 2, 3, R_MAIN, rtop=r - 4.5, rot=rot)
    b.ring(0, 0, 1.0, min(r + 6, box + 0.5), R_LITE, 14, 2)
    return 8.0


def _yzring(b, x, z, r, role, width=2):
    b.ring(x, 0, z, r, role, 8, width, math.pi / 2, math.pi / 2)


def tm_blaster(b, lv):
    z = _pad(b, lv)
    if lv >= 2:
        b.box(0, 7.5, z, 3.5, 1.6, 5, R_DARK)
        b.box(0, -7.5, z, 3.5, 1.6, 5, R_DARK)
    b.group(M_AIM | M_RECOIL)
    b.prism(8, 0, 0, z, 7.5 + lv * 0.4, 6, R_MAIN, rtop=6)
    b.box(-1, 0, z + 6, 4.5, 4, 3.5, R_DARK)
    L = 17 + lv * 1.5
    if lv < 4:
        b.bar((3, 0, z + 5.5), (L, 0, z + 5.5), 1.6 + lv * 0.25, R_LITE, 4)
    else:
        for o in (-3.4, 3.4):
            b.bar((3, o, z + 5.5), (L, o, z + 5.5), 1.9, R_LITE, 4)
    if lv >= 1:
        b.box(L - 2.5, 0, z + 3.3, 1.5, 2.8 + (3.2 if lv == 4 else 0), 4.4, R_METAL)
    if lv >= 3:
        b.box(-5, 0, z + 9.5, 2.5, 2, 2.6, R_LITE)
    if lv >= 4:
        b.ring(0, 0, z + 17, 9, R_ALT, 12, 2)
        b.glow(L, 0, z + 5.5, 9, R_LITE, 0.6)


def tm_blade(b, lv):
    z = _pad(b, lv, 11)
    b.prism(6, 0, 0, z, 3.5, 5 + lv, R_METAL)
    b.group(M_AIM)
    n = (2, 2, 3, 3, 4)[lv]
    L = 15 + lv * 1.6
    zz = z + 4 + lv * 0.6
    for i in range(n):
        a = i * TAU / n
        ca, sa = math.cos(a), math.sin(a)
        b.slab([(ca * 3, sa * 3, zz), (ca * L - sa * 1.2, sa * L + ca * 1.2, zz), (ca * (L - 4) + sa * 4.6, sa * (L - 4) - ca * 4.6, zz)], R_LITE)
    if lv >= 2:
        for i in range(n):
            a = (i + 0.5) * TAU / n
            ca, sa = math.cos(a), math.sin(a)
            L2 = L * 0.6
            b.slab([(ca * 2, sa * 2, zz + 3.5), (ca * L2 - sa, sa * L2 + ca, zz + 3.5), (ca * (L2 - 3) + sa * 3.5, sa * (L2 - 3) - ca * 3.5, zz + 3.5)], R_MAIN)
    if lv >= 3:
        b.prism(6, 0, 0, zz + 1, 2.6, 6, R_MAIN, rtop=0)
    if lv >= 4:
        b.crystal(0, 0, zz + 8, 3, 7, R_ALT)
        b.ring(0, 0, zz, L + 1.5, R_ALT, 16, 1)


def tm_rail(b, lv):
    z = _pad(b, lv, 11, 4)
    b.prism(4, 0, 0, z, 4, 5, R_METAL, rot=math.pi / 4)
    b.group(M_AIM | M_RECOIL)
    zz = z + 5
    b.box(-2, 0, zz, 7, 3, 4.5, R_MAIN)
    L = 21 + lv * 1.2
    b.bar((5, 0, zz + 2.4), (L, 0, zz + 2.4), 1.3 + lv * 0.15, R_LITE, 4)
    if lv >= 1:
        b.box(-1, 0, zz + 4.5, 3.5, 1.3, 2.2, R_DARK)
    if lv >= 2:
        b.slab([(-9, 0, zz + 1), (-15, 0, zz + 8), (-8, 0, zz + 5)], R_MAIN)
    if lv >= 3:
        for x in (11, 17):
            _yzring(b, x, zz + 2.4, 3.4, R_WHITE)
    if lv >= 4:
        b.box((5 + L) / 2, 0, zz + 4.4, (L - 7) / 2, 0.8, 0.9, R_ALT)
        _yzring(b, L - 3, zz + 2.4, 3.4, R_ALT)
        b.glow(L, 0, zz + 2.4, 11, R_LITE, 0.8)


def tm_scatter(b, lv):
    z = _pad(b, lv, 13)
    b.group(M_AIM | M_RECOIL)
    b.prism(6, 0, 0, z, 9 + lv * 0.3, 5.5, R_MAIN, rtop=7.5)
    nb = (3, 3, 3, 4, 5)[lv]
    for i in range(nb):
        a = -0.4 + 0.8 * i / (nb - 1)
        ca, sa = math.cos(a), math.sin(a)
        b.bar((4 * ca, 4 * sa, z + 3.6), ((13 + lv) * ca, (13 + lv) * sa, z + 3.6), 1.8, R_LITE, 4)
    if lv >= 1:
        b.box(-6, 0, z + 5.5, 3, 4, 3, R_DARK)
    if lv >= 2:
        b.prism(8, -6, 0, z + 8.5, 3, 1.5, R_METAL)
    if lv >= 3:
        b.box(3.5, 0, z + 5.5, 1, 7, 3.2, R_METAL)
    if lv >= 4:
        b.ring(0, 0, z + 14, 8, R_ALT, 12, 2)


ICE = (170, 225, 255)


def tm_cryo(b, lv):
    z = _pad(b, lv, 12)
    k = (1, 2, 3, 4, 6)[lv]
    for i in range(k):
        a = i * TAU / k + 0.4
        b.prism(4, math.cos(a) * 9, math.sin(a) * 9, z, 2.4, 6 + lv, ICE, rtop=0, rot=a)
    b.group(M_SPIN | M_BOB, 0.9, 0, 0, z + 8 + lv, 2.2, 1.6)
    b.crystal(0, 0, 0, 5 + lv * 0.8, 13 + lv * 1.5, R_LITE, 6)
    if lv >= 2:
        b.ring(0, 0, 6.5, 8 + lv, R_WHITE, 12, 1)
    if lv >= 4:
        b.ring(0, 0, 8.5, 13, R_ALT, 12, 2, 0.5)
    b.glow(0, 0, 7, 16, R_LITE, 0.5)


def tm_mortar(b, lv):
    z = _pad(b, lv, 13, 4)
    b.box(0, 0, z, 9, 9, 5, R_DARK, 0.85)
    if lv >= 2:
        b.box(-8, 9, 0, 3, 2.5, 4 + z, R_METAL)
    if lv >= 3:
        b.box(-8, -9, 0, 3, 2.5, 4 + z, R_METAL)
    b.group(M_AIM | M_RECOIL)
    b.prism(8, 0, 0, z + 5, 5.5, 3, R_MAIN)
    for o in ((-3.6, 3.6) if lv == 4 else (0,)):
        ex, ez = 9 + lv, z + 17 + lv * 1.5
        b.bar((-2, o, z + 6), (ex, o, ez), 3.0 + (0 if lv == 4 else lv * 0.3), R_METAL, 6, 3.5 + (0 if lv == 4 else lv * 0.3))
        b.ball(ex, o, ez, 2.0, R_LITE)
    if lv >= 1:
        b.box(-5, 0, z + 8, 2, 4.6, 2.4, R_LITE)
    if lv >= 4:
        b.ring(0, 0, z + 28, 9, R_ALT, 12, 2)


def tm_harvester(b, lv):
    z = _pad(b, lv, 13)
    b.prism(6, 0, 0, z, 6, 4, R_METAL, rtop=4)
    n = (2, 2, 4, 4, 6)[lv]
    for i in range(n):
        a = i * TAU / n + 0.3
        ca, sa = math.cos(a), math.sin(a)
        r0, r1, w = 6, 15 + lv * 0.5, 3.6
        z0, z1 = z + 3, z + 7 + lv
        b.slab([(ca * r0 - sa * w, sa * r0 + ca * w, z0), (ca * r0 + sa * w, sa * r0 - ca * w, z0),
                (ca * r1 + sa * w, sa * r1 - ca * w, z1), (ca * r1 - sa * w, sa * r1 + ca * w, z1)], R_MAIN)
    b.group(M_SPIN | M_BOB, 1.6, 0, 0, z + 9, 2.5, 1.2)
    b.crystal(0, 0, 0, 4 + lv * 0.5, 9 + lv, R_ALT, 4)
    if lv >= 3:
        b.ring(0, 0, 4.5, 7 + lv, R_ALT, 12, 1)
    b.glow(0, 0, 5, 14, R_ALT, 0.5)


def tm_sentinel(b, lv):
    z = _pad(b, lv, 12)
    b.group(M_AIM)
    b.box(0, -3.5, z, 2.5, 2, 6, R_DARK)
    b.box(0, 3.5, z, 2.5, 2, 6, R_DARK)
    b.box(0, 0, z + 6, 4.5, 6 + lv * 0.3, 7 + lv * 0.4, R_MAIN, 0.9)
    b.box(1, 0, z + 13 + lv * 0.4, 2.5, 2.5, 3.5, R_LITE)
    for o in ((8, 10.5) if lv == 4 else (8,)):
        b.bar((0, o, z + 10), (15 + lv, o, z + 10), 1.7 + lv * 0.15, R_METAL, 4)
    b.slab([(2, -8, z + 9), (16 + lv * 1.5, -8, z + 12), (14 + lv * 1.5, -8, z + 8)], R_LITE)
    if lv >= 2:
        b.box(0, 8, z + 11, 3, 2.2, 3, R_DARK)
        b.box(0, -8, z + 11, 3, 2.2, 3, R_DARK)
    if lv >= 3:
        b.slab([(-4, 3, z + 12), (-11, 6, z + 20), (-4, 5, z + 8)], R_MAIN)
        b.slab([(-4, -3, z + 12), (-11, -6, z + 20), (-4, -5, z + 8)], R_MAIN)
    if lv >= 4:
        b.box(4.8, 0, z + 8, 0.6, 3, 3, R_ALT)
        b.ring(0, 0, z + 22, 7, R_ALT, 12, 2)


def tm_tesla(b, lv):
    z = _pad(b, lv, 12, 8)
    n = (2, 3, 3, 4, 5)[lv]
    b.prism(6, 0, 0, z, 3, 6 + n * 5, R_METAL)
    for i in range(n):
        b.prism(8, 0, 0, z + 5 + i * 5, 10 - i * 1.4, 1.6, R_MAIN)
    top = z + 6 + n * 5
    b.ball(0, 0, top + 3, 3.5 + lv * 0.5, R_LITE)
    b.glow(0, 0, top + 3, 16, R_LITE, 0.7)
    if lv >= 3:
        b.group(M_SPIN, 2.5, 0, 0, top + 3)
        b.ball(9, 0, 0, 1.6, R_WHITE)
        b.ball(-9, 0, 0, 1.6, R_WHITE)
        if lv >= 4:
            b.ring(0, 0, 0, 9, R_ALT, 12, 2)


def tm_beacon(b, lv):
    z = _pad(b, lv, 11)
    h = 22 + lv * 4
    b.prism(4, 0, 0, z, 3.5, h, R_METAL, rtop=1.6, rot=math.pi / 4)
    if lv >= 2:
        for sx, sy in ((7, 7), (-7, 7), (7, -7), (-7, -7)):
            b.line([(sx, sy, z), (0, 0, z + h * 0.6)], R_MAIN, 2)
    b.ball(0, 0, z + h + 3, 3.5 + lv * 0.4, R_LITE)
    b.glow(0, 0, z + h + 3, 20, R_LITE, 0.8)
    b.group(M_SPIN, 1.2, 0, 0, z + h + 3)
    b.ring(0, 0, 0, 8 + lv, R_LITE, 12, 2)
    b.slab([(7 + lv, -3, -2), (7 + lv, 3, -2), (10 + lv, 3, 2.5), (10 + lv, -3, 2.5)], R_MAIN)
    if lv >= 1:
        b.slab([(-7 - lv, -3, -2), (-7 - lv, 3, -2), (-10 - lv, 3, 2.5), (-10 - lv, -3, 2.5)], R_MAIN)
    if lv >= 3:
        b.ring(0, 0, 0, 11 + lv, R_WHITE, 12, 1, 0.6)
    if lv >= 4:
        b.ring(0, 0, 6, 6, R_ALT, 10, 2)


def tm_commander(b, lv):
    z = _pad(b, lv, 13, 4)
    b.box(0, 0, z, 7, 7, 5 + lv, R_DARK, 0.8)
    zt = z + 5 + lv
    fh = zt + 16 + lv * 2
    b.bar((0, 0, zt), (0, 0, fh), 0.8, R_METAL, 4)
    b.slab([(0, 0, fh), (0, 10 + lv, fh - 2), (0, 10 + lv, fh - 8), (0, 0, fh - 7)], R_LITE)
    if lv >= 2:
        b.slab([(0, 0, fh - 9), (0, -8 - lv, fh - 10), (0, -8 - lv, fh - 15), (0, 0, fh - 14)], R_MAIN)
    if lv >= 3:
        for sx, sy in ((5.5, 5.5), (-5.5, -5.5), (5.5, -5.5), (-5.5, 5.5)):
            b.ball(sx, sy, zt + 1.5, 1.5, R_LITE)
    b.group(M_SPIN, 1.0, 0, 0, fh + 5)
    r = 4.5 + lv * 0.6
    b.slab([(math.cos(i * math.pi / 5 + math.pi / 2) * (r if i % 2 == 0 else r * 0.45), 0, math.sin(i * math.pi / 5 + math.pi / 2) * (r if i % 2 == 0 else r * 0.45)) for i in range(10)],
           R_ALT if lv >= 4 else R_LITE)
    if lv >= 4:
        b.ring(0, 0, 0, r + 3, R_ALT, 12, 2)
    b.glow(0, 0, 0, 12, R_LITE, 0.5)


def tm_prism(b, lv):
    z = _pad(b, lv, 12, 3)
    for i in range(3):
        a = i * TAU / 3 + 0.5
        b.bar((math.cos(a) * 10, math.sin(a) * 10, z), (math.cos(a) * 5, math.sin(a) * 5, z + 7 + lv), 1.2, R_METAL, 4)
    b.group(M_SPIN | M_BOB, 1.4, 0, 0, z + 9 + lv, 2.0, 1.5)
    b.crystal(0, 0, 0, 5.5 + lv * 0.9, 14 + lv * 2, R_LITE, 3)
    if lv >= 2:
        ns = 2 if lv < 4 else 4
        for i in range(ns):
            a = i * TAU / ns
            b.crystal(math.cos(a) * 11, math.sin(a) * 11, 4, 1.8, 5, R_WHITE, 3)
    if lv >= 3:
        b.ring(0, 0, 7 + lv, 10, R_LITE, 12, 1)
    if lv >= 4:
        b.ring(0, 0, 7 + lv, 13.5, R_ALT, 14, 2, 0.4)
    b.glow(0, 0, 7 + lv, 20, R_LITE, 0.7)


def tm_annihilator(b, lv):
    z = _pad(b, lv, 17, 4, 19.0)
    b.box(0, 0, z, 12, 12, 5, R_DARK, 0.9)
    b.group(M_AIM | M_RECOIL)
    b.box(-2, 0, z + 5, 8, 7, 7 + lv * 0.4, R_MAIN, 0.85)
    L = 22 + lv * 1.2
    r = 3.6 + lv * 0.5
    b.bar((4, 0, z + 9), (L, 0, z + 9), r, R_METAL, 6)
    b.bar((L, 0, z + 9), (L + 4, 0, z + 9), r + 1.4, R_LITE, 6)
    if lv >= 1:
        b.box(-9, 0, z + 6, 2.5, 5, 5, R_DARK)
    if lv >= 2:
        b.bar((-6, 8.5, z + 8), (4, 8.5, z + 8), 2.2, R_METAL, 6)
        b.bar((-6, -8.5, z + 8), (4, -8.5, z + 8), 2.2, R_METAL, 6)
    if lv >= 3:
        for x in (12, 19):
            _yzring(b, x, z + 9, r + 2, R_LITE)
    if lv >= 4:
        b.box(8, 0, z + 12.5 + lv * 0.4, 9, 1.2, 1.2, R_ALT)
        b.ring(0, 0, z + 24, 12, R_ALT, 14, 2)
        b.glow(L + 4, 0, z + 9, 16, R_LITE, 0.9)


def tm_hydra(b, lv):
    z = _pad(b, lv, 13)
    b.prism(6, 0, 0, z, 5, 5, R_METAL)
    b.group(M_AIM | M_RECOIL)
    pods = (1, 1, 2, 2, 3)[lv]
    for o in {1: (0,), 2: (-5.5, 5.5), 3: (-9.5, 0, 9.5)}[pods]:
        b.bar((-6, o, z + 6), (8, o, z + 13), 4.0 + (lv % 2) * 0.5, R_MAIN, 4)
        b.ball(8.4, o - 1.5, z + 14.4, 1.1, R_LITE)
        b.ball(8.4, o + 1.5, z + 14.4, 1.1, R_LITE)
        b.ball(9.2, o - 1.5, z + 12.2, 1.1, R_LITE)
        b.ball(9.2, o + 1.5, z + 12.2, 1.1, R_LITE)
    if lv >= 3:
        b.slab([(-8, -4, z + 14), (-8, 4, z + 14), (-11, 4, z + 20), (-11, -4, z + 20)], R_METAL)
    if lv >= 4:
        b.ring(0, 0, z + 24, 9, R_ALT, 12, 2)


def tm_graviton(b, lv):
    z = _pad(b, lv, 13, 8)
    n = 3 + (1 if lv >= 2 else 0) + (1 if lv >= 4 else 0)
    for i in range(n):
        a = i * TAU / n
        b.bar((math.cos(a) * 11, math.sin(a) * 11, z), (math.cos(a) * 8, math.sin(a) * 8, z + 14 + lv * 2), 1.3, R_METAL, 4)
    b.group(M_SPIN | M_BOB, -1.8, 0, 0, z + 13 + lv, 1.7, 1.2)
    b.ball(0, 0, 0, 5 + lv * 0.7, R_BLACK)
    b.ring(0, 0, 0, 8 + lv, R_LITE, 14, 2, 0.35)
    if lv >= 1:
        b.ring(0, 0, 0, 11 + lv, R_MAIN, 14, 1, -0.5, 1.0)
    if lv >= 3:
        b.ring(0, 0, 0, 13 + lv, R_WHITE, 14, 1, 1.1, 2.0)
    if lv >= 4:
        b.ring(0, 0, 0, 18, R_ALT, 16, 2, 0.2)
    b.glow(0, 0, 0, 22, R_LITE, 0.5)


MEDIC = (90, 255, 150)


def tm_mechanic(b, lv):
    z = _pad(b, lv, 12, 4)
    b.box(0, 0, z, 7, 7, 7 + lv * 0.6, R_DARK, 0.9)
    zt = z + 7 + lv * 0.6
    b.box(0, 0, zt, 5, 1.6, 1, MEDIC)
    b.box(0, 0, zt, 1.6, 5, 1, MEDIC)
    if lv >= 2:
        b.bar((-5, -5, zt), (-5, -5, zt + 9 + lv), 0.6, R_METAL, 4)
        b.ball(-5, -5, zt + 10 + lv, 1.2, R_LITE)
    b.group(M_SPIN, 1.5, 0, 0, zt + 7)
    drones = (1, 1, 2, 2, 3)[lv]
    for i in range(drones):
        a = i * TAU / drones
        x, y = math.cos(a) * 11, math.sin(a) * 11
        b.ball(x, y, 0, 2.2, R_WHITE)
        b.ring(x, y, 1.8, 3.2, R_LITE, 6, 1)
    if lv >= 4:
        b.ring(0, 0, 0, 11, R_ALT, 14, 2)


# ---- path towers stand on the road and face the enemies
def tm_guardian(b, lv):
    b.group(M_AIM)
    s = 1 + lv * 0.08
    b.box(0, -3 * s, 0, 2.2 * s, 1.8 * s, 7 * s, R_DARK)
    b.box(0, 3 * s, 0, 2.2 * s, 1.8 * s, 7 * s, R_DARK)
    b.box(0, 0, 7 * s, 3.5 * s, 5.5 * s, 8 * s, R_MAIN, 0.85)
    b.prism(6, 0, 0, 15 * s, 2.6 * s, 3.5 * s, R_LITE)
    b.slab([(5 * s, -9 * s, 4 * s), (5 * s, -3 * s, 4 * s), (5 * s, -3 * s, 13 * s), (5 * s, -6 * s, 15 * s), (5 * s, -9 * s, 13 * s)], R_METAL)
    b.slab([(3 * s, 7 * s, 9 * s), (17 * s + lv, 7 * s, 13 * s), (15 * s + lv, 7 * s, 9 * s)], R_LITE)
    if lv >= 2:
        b.box(0, 6.5 * s, 13 * s, 2.6 * s, 2 * s, 2.6 * s, R_METAL)
        b.box(0, -6.5 * s, 13 * s, 2.6 * s, 2 * s, 2.6 * s, R_METAL)
    if lv >= 3:
        b.slab([(-2 * s, 0, 18.5 * s), (3 * s, 0, 18.5 * s), (-4 * s, 0, 24 * s)], R_LITE)
    if lv >= 4:
        b.slab([(-3.6 * s, -5 * s, 15 * s), (-3.6 * s, 5 * s, 15 * s), (-7 * s, 6 * s, 2 * s), (-7 * s, -6 * s, 2 * s)], R_ALT)
        b.ring(0, 0, 25 * s, 5 * s, R_ALT, 10, 2)


def tm_bulwark(b, lv):
    b.group(M_AIM)
    wd = 13 + lv * 1.2
    h = 13 + lv * 2
    b.box(0, 0, 0, 4, wd, h, R_DARK, 0.92)
    b.box(4.6, 0, 2, 1, wd - 2, h - 5, R_MAIN)
    n = (2, 3, 3, 4, 5)[lv]
    for i in range(n):
        y = (i - (n - 1) / 2.0) * (2 * wd - 8) / max(1, n - 1)
        b.bar((5, y, h * 0.5), (12 + lv, y, h * 0.5), 2.2, R_LITE, 4, 0.2)
    if lv >= 1:
        b.box(0, -wd + 3, h, 3, 2.5, 3, R_METAL)
        b.box(0, wd - 3, h, 3, 2.5, 3, R_METAL)
    if lv >= 3:
        b.box(0, 0, h, 3, 3, 5, R_METAL)
    if lv >= 4:
        b.line([(5.8, -wd + 2, h - 3), (5.8, wd - 2, h - 3)], R_ALT, 3)
        b.ring(0, 0, h + 9, 6, R_ALT, 10, 2)


def tm_reactor(b, lv):
    b.prism(8, 0, 0, 0, 11 + lv * 0.5, 3, R_DARK)
    for i in range(4):
        a = i * TAU / 4 + math.pi / 4
        b.bar((math.cos(a) * 9, math.sin(a) * 9, 3), (math.cos(a) * 7, math.sin(a) * 7, 16 + lv * 2), 1.1, R_METAL, 4)
    if lv >= 3:
        b.ring(0, 0, 16 + lv * 2, 7, R_METAL, 8, 2)
    b.group(M_BOB, 0, 0, 0, 10 + lv, 3.0, 1.0)
    b.ball(0, 0, 0, 5 + lv * 0.8, R_LITE)
    b.glow(0, 0, 0, 24, R_LITE, 0.9)
    b.group(M_SPIN, 2.0, 0, 0, 10 + lv)
    b.ring(0, 0, 0, 8 + lv, R_WHITE, 12, 2, 0.5)
    if lv >= 2:
        b.ring(0, 0, 0, 9 + lv, R_MAIN, 12, 1, -0.9, 1.3)
    if lv >= 4:
        b.ring(0, 0, 0, 13, R_ALT, 14, 2, 1.3, 2.2)


# ---- event towers
BRICK_C = (70, 84, 112)
BRICK_SCREEN = (150, 230, 130)


def tm_brick(b, lv):
    b.group(M_AIM)
    s = 1 + lv * 0.1
    body = R_ALT if lv >= 4 else BRICK_C
    b.box(0, 0, 0, 4 * s, 7 * s, 21 * s, body)
    b.slab([(4.2 * s, -5 * s, 12 * s), (4.2 * s, 5 * s, 12 * s), (4.2 * s, 5 * s, 19 * s), (4.2 * s, -5 * s, 19 * s)], BRICK_SCREEN)
    for i in range(3 if lv < 2 else 4):
        zz = (3 + i * 2.4) * s
        b.line([(4.2 * s, -5 * s, zz), (4.2 * s, 5 * s, zz)], R_METAL, 2)
    b.box(-1, 5 * s, 21 * s, 1.3, 1.3, 4, (40, 48, 64))
    if lv >= 2:
        b.ring(0, 0, 10 * s, 9 * s, R_LITE, 4, 2)
    if lv >= 4:
        b.ring(0, 0, 27 * s, 6 * s, R_ALT, 10, 2)


DUCK_Y = (255, 214, 40)
DUCK_O = (255, 140, 30)


def tm_duck(b, lv):
    z = _pad(b, lv, 12)
    b.group(M_AIM)
    s = 1 + lv * 0.07
    b.ball(-1, 0, z + 7 * s, 8 * s, DUCK_Y)
    b.ball(-8 * s, 0, z + 9.5 * s, 3.5 * s, DUCK_Y)
    b.ball(5 * s, 0, z + 16 * s, 5.2 * s, DUCK_Y)
    b.bar((9 * s, 0, z + 15 * s), (14.5 * s, 0, z + 14.5 * s), 2 * s, DUCK_O, 4, 1.2 * s)
    if lv < 2:
        b.ball(8.4 * s, -2.6 * s, z + 17.6 * s, 1.1, R_BLACK)
        b.ball(8.4 * s, 2.6 * s, z + 17.6 * s, 1.1, R_BLACK)
    else:
        b.slab([(9.6 * s, -4.6 * s, z + 16.6 * s), (9.6 * s, 4.6 * s, z + 16.6 * s), (9.6 * s, 4.6 * s, z + 18.8 * s), (9.6 * s, -4.6 * s, z + 18.8 * s)], (10, 10, 16))
    if lv == 1:
        b.slab([(8 * s, -3 * s, z + 12.5 * s), (8 * s, 0, z + 11.5 * s), (8 * s, 3 * s, z + 12.5 * s), (8 * s, 3 * s, z + 10 * s), (8 * s, 0, z + 11 * s), (8 * s, -3 * s, z + 10 * s)], (230, 40, 60))
    if lv == 3:
        b.prism(8, 5 * s, 0, z + 20.6 * s, 5.4 * s, 0.8, (16, 16, 24))
        b.prism(8, 5 * s, 0, z + 21.4 * s, 3.6 * s, 4.6 * s, (16, 16, 24))
    if lv >= 4:
        b.prism(6, 5 * s, 0, z + 20.6 * s, 3.4 * s, 3.2 * s, R_ALT, rtop=4.6 * s)
        b.ring(-1, 0, z + 8 * s, 9.5 * s, R_ALT, 12, 2, 0.5)


TOAST = (214, 160, 90)


def tm_toaster(b, lv):
    z = _pad(b, lv, 13, 4)
    wide = 6.5 + (3.5 if lv >= 2 else 0)
    hh = 10 + lv * 0.5
    b.box(0, 0, z, 6, wide, hh, R_ALT if lv >= 4 else R_METAL, 0.93)
    ys = (-2.6, 2.6) if lv < 2 else (-6.6, -2.2, 2.2, 6.6)
    for y in ys:
        b.box(0, y, z + hh, 4, 1.1, 0.3, R_BLACK, edge=False)
    b.box(0, wide + 0.8, z + 5, 1.2, 0.8, 1.5, R_LITE)
    if lv >= 1:
        b.ball(6.2, 0, z + 3, 1.3, R_LITE)
    if lv >= 3:
        b.glow(0, 0, z + hh, 14, (255, 140, 40), 0.7)
    b.group(M_BOB, 0, 0, 0, z + hh - 1, 3.5, 2.4)
    for y in ys:
        b.box(0, y, 0, 3.5, 0.7, 5, TOAST)
    if lv >= 4:
        b.ring(0, 0, 12, 8, R_ALT, 12, 2)


CAT_G = (156, 156, 172)


def tm_cat(b, lv):
    z = _pad(b, lv, 13)
    b.group(M_AIM)
    b.box(-3, 0, z, 6, 4.5, 7, CAT_G, 0.9)
    b.box(3, 0, z + 7, 3.6, 3.8, 5.5, CAT_G)
    b.prism(3, 3, -2.6, z + 12.5, 1.7, 2.8, CAT_G, rtop=0)
    b.prism(3, 3, 2.6, z + 12.5, 1.7, 2.8, CAT_G, rtop=0)
    if lv < 2:
        b.ball(6.7, -1.7, z + 10.6, 0.9, R_LITE)
        b.ball(6.7, 1.7, z + 10.6, 0.9, R_LITE)
    else:
        b.slab([(6.8, -3.4, z + 9.8), (6.8, 3.4, z + 9.8), (6.8, 3.4, z + 11.6), (6.8, -3.4, z + 11.6)], (10, 10, 16))
    b.bar((-9, 0, z + 2), (-13, 3, z + 11), 1.0, CAT_G, 4)
    b.box(11.5, 0, z, 3.2, 7.5, 1.2, R_BLACK)
    cols = (R_LITE, R_LITE) if lv < 3 else ((255, 60, 90), (80, 255, 150), (90, 150, 255))
    for i, c in enumerate(cols):
        x = 9.6 + i * (3.8 / max(1, len(cols) - 1))
        b.line([(x, -6.5, z + 1.4), (x, 6.5, z + 1.4)], c, 2)
    b.box(7.5, -2.5, z + 1.2, 2, 1, 1.2, CAT_G)
    b.box(7.5, 2.5, z + 1.2, 2, 1, 1.2, CAT_G)
    if lv >= 1:
        b.ring(2, 0, z + 7.3, 3.6, R_LITE, 8, 2)
    if lv >= 3:
        b.ring(3, 0, z + 9.5, 4.6, (16, 16, 24), 8, 3, math.pi / 2, math.pi / 2)
    if lv >= 4:
        b.prism(5, 3, 0, z + 12.6, 2.4, 2.4, R_ALT, rtop=3.3)
        b.ring(0, 0, z + 19, 7, R_ALT, 12, 2)


STONK_G = (60, 235, 130)
STONK_R = (255, 70, 90)


def tm_stonks(b, lv):
    z = _pad(b, lv, 13, 4)
    n = 3 + lv // 2
    for i in range(n):
        x = -8 + i * (16.0 / (n - 1))
        h = 4 + i * (3 + lv * 0.8)
        if i == 1:
            h *= 0.6
        b.box(x, 4, z, 1.6, 2.4, h, STONK_R if i == 1 else STONK_G)
    top = z + 18 + lv * 2
    b.line([(-10, -4, z + 5), (-4, -4, z + 10), (0, -4, z + 7), (8, -4, top)], STONK_G, 3)
    b.slab([(8, -4, top + 3), (10.5, -4, top - 2.5), (5, -4, top - 1)], STONK_G)
    if lv >= 4:
        b.prism(6, 8, -4, top + 4, 1.8, 6, R_WHITE)
        b.prism(6, 8, -4, top + 10, 1.8, 3.5, STONK_R, rtop=0)
        b.glow(8, -4, top + 3, 9, (255, 160, 60), 0.9)
    b.group(M_SPIN | M_BOB, 1.5, -3, 0, z + 20 + lv * 2, 2, 1.2)
    b.crystal(0, 0, 0, 3 + lv * 0.3, 6 + lv * 0.5, R_ALT, 6)
    b.glow(0, 0, 3, 10, R_ALT, 0.5)


PUMP_O = (255, 128, 22)
PUMP_G = (70, 170, 60)
PUMP_Y = (255, 232, 90)
WITCH = (120, 60, 190)


def tm_pumpkin(b, lv):
    z = _pad(b, lv, 12)
    b.group(M_AIM | M_RECOIL)
    s = 1 + lv * 0.07
    b.ball(0, 0, z + 8 * s, 9 * s, PUMP_O)
    f = 8.9 * s
    for sg in (-1, 1):
        b.slab([(f, sg * 4.2 * s, z + 9.5 * s), (f, sg * 1.2 * s, z + 9.5 * s), (f, sg * 2.7 * s, z + 12.8 * s)], PUMP_Y)
    b.slab([(f, -4.6 * s, z + 6.6 * s), (f, -2 * s, z + 5.2 * s), (f, 0, z + 6.6 * s), (f, 2 * s, z + 5.2 * s), (f, 4.6 * s, z + 6.6 * s), (f, 0, z + 3.4 * s)], PUMP_Y)
    b.glow(6 * s, 0, z + 8 * s, 15, PUMP_Y, 0.6)
    if lv < 2:
        b.box(0, 0, z + 16.5 * s, 1.2, 1.2, 3, PUMP_G)
    else:
        b.prism(8, 0, 0, z + 16 * s, 7.5 * s, 0.9, WITCH)
        b.prism(8, 0, 0, z + 16.9 * s, 4.4 * s, 9.5 * s, WITCH, rtop=0)
    if lv >= 1:
        b.slab([(0, 1, z + 17 * s), (-5, 5, z + 18 * s), (-3, 1, z + 15.5 * s)], PUMP_G)
    if lv >= 3:
        b.ring(0, 0, z + 2.5, 10 * s, PUMP_G, 10, 2)
    if lv >= 4:
        b.ring(0, 0, z + 18.4 * s, 4.2 * s, R_ALT, 8, 3)
        b.ring(0, 0, z + 29 * s, 6, R_ALT, 10, 2)


SNOW_W = (236, 244, 255)


def tm_snow(b, lv):
    z = _pad(b, lv, 12)
    b.group(M_AIM)
    s = 1 + lv * 0.06
    b.ball(0, 0, z + 6 * s, 7 * s, SNOW_W)
    b.ball(0, 0, z + 15 * s, 5 * s, SNOW_W)
    b.ball(0, 0, z + 22 * s, 3.6 * s, SNOW_W)
    b.bar((3 * s, 0, z + 22 * s), (8.5 * s, 0, z + 21.6 * s), 1.0 * s, DUCK_O, 4, 0.15)
    b.ball(3.0 * s, -1.4 * s, z + 23.3 * s, 0.7, R_BLACK)
    b.ball(3.0 * s, 1.4 * s, z + 23.3 * s, 0.7, R_BLACK)
    b.bar((4 * s, 5.5 * s, z + 13 * s), (15 * s + lv, 5.5 * s, z + 14 * s), 2.2 * s, R_METAL, 6, 3.0 * s)
    b.ring(0, 0, z + 19 * s, 4.2 * s, (230, 40, 60), 10, 3)
    if lv >= 2:
        b.ball(4.8 * s, 0, z + 15 * s, 0.9, R_BLACK)
        b.ball(6.6 * s, 0, z + 7 * s, 0.9, R_BLACK)
    if lv >= 3:
        b.prism(8, 0, 0, z + 25 * s, 4.4 * s, 0.7, (16, 16, 24))
        b.prism(8, 0, 0, z + 25.7 * s, 2.9 * s, 4.2 * s, (16, 16, 24))
    if lv >= 4:
        b.line([(-5 * s, -5 * s, z + 8 * s), (-7 * s, -7 * s, z + 24 * s), (-4 * s, -8 * s, z + 27 * s)], (255, 70, 90), 3)
        b.ring(0, 0, z + 33 * s, 5, R_ALT, 10, 2)


def tm_summoner(b, lv):
    """(a stand-in until the real model is drawn) a little barracks gate with a banner, and a gold crystal turning above it"""
    z = _pad(b, lv, 13)
    h = 13 + lv * 1.5
    for o in (-6.5, 6.5):
        b.box(0, o, z, 2.2, 2.2, h, R_DARK, 0.85)
        if lv >= 2:
            b.prism(4, 0, o, z + h + 2.6, 1.8, 4 + lv, R_METAL, rtop=0, rot=math.pi / 4)
    b.box(0, 0, z + h, 3, 9.5, 2.6, R_MAIN)
    b.slab([(0.3, -4, z + h), (0.3, 4, z + h), (0.3, 4, z + h - 7 - lv), (0.3, 0, z + h - 10 - lv), (0.3, -4, z + h - 7 - lv)], R_LITE)
    if lv >= 1:
        b.box(4.5, 0, z, 2.5, 4, 1.2, R_METAL)
    b.group(M_SPIN | M_BOB, 1.2, 0, 0, z + h + 6 + (lv if lv >= 2 else 0), 2.2, 1.0)
    b.crystal(0, 0, 0, 3 + lv * 0.4, 7 + lv, R_ALT, 4)
    if lv >= 3:
        b.ring(0, 0, 3.5 + lv * 0.5, 6 + lv, R_ALT, 12, 1 if lv == 3 else 2)
    b.glow(0, 0, 4, 12, R_ALT, 0.5)


TOWER_MODELS = {
    "blaster": tm_blaster, "blade": tm_blade, "rail": tm_rail, "scatter": tm_scatter, "cryo": tm_cryo, "mortar": tm_mortar,
    "harvester": tm_harvester, "sentinel": tm_sentinel, "tesla": tm_tesla, "beacon": tm_beacon, "commander": tm_commander,
    "prism": tm_prism, "annihilator": tm_annihilator, "hydra": tm_hydra, "graviton": tm_graviton, "mechanic": tm_mechanic,
    "guardian": tm_guardian, "bulwark": tm_bulwark, "reactor": tm_reactor, "brick": tm_brick, "duck": tm_duck,
    "toaster": tm_toaster, "cat": tm_cat, "stonks": tm_stonks, "pumpkin": tm_pumpkin, "snow": tm_snow, "summoner": tm_summoner,
}
_tower_models = {}


def tower_model(kind, lv):
    key = (kind, lv)
    m = _tower_models.get(key)
    if m is None:
        b = MB()
        TOWER_MODELS[kind](b, lv)
        m = _tower_models[key] = b.done()
    return m


# ======================================================================
#  ENEMY MODELS, HATS, THE CORE, GATES, NPCS AND SCENERY
# ======================================================================
SANTA = (232, 44, 62)
HARDHAT = (255, 210, 40)


def em_grunt(b):
    b.group(M_AIM)
    b.prism(3, 0, 0, 2, 9.5, 6, R_MAIN)
    b.prism(3, -1, 0, 8, 5.5, 3.5, R_DARK, rtop=2.5)
    b.ball(5.5, 0, 8.5, 1.7, R_LITE)
    return 12, 0, 5


def em_runner(b):
    b.group(M_AIM)
    b.mesh([(10, 0, 3), (-7, -5.5, 2), (-7, 5.5, 2), (-3, 0, 7)], [(0, 1, 3), (0, 3, 2), (1, 2, 3), (0, 2, 1)], R_MAIN)
    b.slab([(-4, 0, 5), (-11, 0, 10), (-8, 0, 3)], R_LITE)
    return 8, -2, 3.5


def em_swarm(b):
    b.group(M_AIM)
    b.ball(0, 0, 5, 5, R_MAIN)
    b.ball(3.4, 0, 6.2, 1.5, R_LITE)
    return 10, 0, 3


def em_tank(b):
    b.group(M_AIM)
    b.box(0, -12, 0, 12, 2.4, 5, R_BLACK)
    b.box(0, 12, 0, 12, 2.4, 5, R_BLACK)
    b.prism(6, 0, 0, 1.5, 13, 7, R_DARK)
    b.box(-1, 0, 8.5, 6, 6, 5, R_MAIN, 0.85)
    b.bar((4, 0, 11), (17, 0, 11), 1.7, R_LITE, 4)
    return 14, -1, 6


def em_shield(b):
    b.group(M_AIM)
    b.box(0, 0, 2, 7.5, 7.5, 11, R_MAIN, 0.9, math.pi / 4)
    b.ball(0, 0, 15.5, 3, R_LITE)
    b.ring(0, 0, 8, 10.5, R_LITE, 8, 1)
    return 18.5, 0, 4


def em_splitter(b):
    b.group(M_SPIN | M_BOB, 1.2, 0, 0, 3, 2.4, 1.5)
    b.crystal(0, 0, 0, 10.5, 21, R_MAIN, 4)
    b.ring(0, 0, 10.5, 12, R_LITE, 8, 1)
    return 24, 0, 4.5


def em_mini(b):
    b.group(M_SPIN | M_BOB, 2.0, 0, 0, 2, 3.0, 1.0)
    b.crystal(0, 0, 0, 5.5, 11, R_MAIN, 4)
    return 13, 0, 3


def em_healer(b):
    b.group(M_AIM)
    b.prism(8, 0, 0, 2, 9, 8, R_MAIN, rtop=7.5)
    b.box(0, 0, 10, 6, 1.8, 1.4, R_WHITE)
    b.box(0, 0, 10, 1.8, 6, 1.4, R_WHITE)
    b.group(M_SPIN, 1.6, 0, 0, 15)
    b.ring(0, 0, 0, 8, R_LITE, 10, 2)
    return 12, 0, 5


def em_blinker(b):
    b.group(M_SPIN | M_BOB, 3.2, 0, 0, 3, 3.0, 1.2)
    b.box(0, 0, 0, 10, 2.3, 4.5, R_MAIN)
    b.box(0, 0, 0, 2.3, 10, 4.5, R_MAIN)
    b.ball(0, 0, 6.5, 3, R_LITE)
    return 12, 0, 4


def em_phantom(b):
    b.group(M_AIM | M_BOB, 0, 0, 0, 2, 2.4, 1.6)
    b.prism(8, 0, 0, 0, 8.5, 14, R_MAIN, rtop=3.2)
    b.ball(0, 0, 17, 4.6, R_LITE)
    b.ball(3.6, -1.6, 18, 1.0, R_BLACK)
    b.ball(3.6, 1.6, 18, 1.0, R_BLACK)
    return 23, 0, 4


def em_elite(b):
    b.group(M_AIM)
    b.prism(5, 0, 0, 2, 14.5, 12, R_MAIN, rtop=11)
    b.prism(5, 0, 0, 14, 8, 4.5, R_DARK)
    b.ball(7.5, 0, 16.5, 2.4, R_LITE)
    for i in range(5):
        a = i * TAU / 5 + 0.3
        b.prism(3, math.cos(a) * 6.5, math.sin(a) * 6.5, 18.5, 1.8, 5, R_ALT, rtop=0)
    return 19, 0, 6


def em_jugger(b):
    b.group(M_AIM)
    b.box(0, 0, 2, 11, 12, 15, R_DARK, 0.9)
    b.box(0, -14.5, 9, 6, 4, 7, R_MAIN)
    b.box(0, 14.5, 9, 6, 4, 7, R_MAIN)
    b.box(5, 0, 17, 4, 4.5, 4.5, R_LITE)
    b.box(10.4, 0, 5, 1, 9, 9, R_METAL)
    b.bar((4, -15, 8), (14, -15, 4), 3.2, R_METAL, 4)
    b.bar((4, 15, 8), (14, 15, 4), 3.2, R_METAL, 4)
    return 21.5, 5, 5


def em_overseer(b):
    b.group(M_AIM | M_BOB, 0, 0, 0, 8, 1.3, 2.5)
    b.prism(8, 0, 0, 0, 24, 9, R_DARK, rtop=19)
    b.prism(8, 0, 0, 9, 19, 7, R_MAIN, rtop=9)
    b.ball(15, 0, 9, 7.5, R_LITE)
    b.ball(20.5, 0, 9.5, 3.2, R_BLACK)
    b.glow(18, 0, 9, 26, R_LITE, 0.8)
    b.group(M_SPIN, 0.9, 0, 0, 12)
    b.ring(0, 0, 0, 30, R_LITE, 16, 2)
    for i in range(4):
        a = i * TAU / 4
        b.bar((math.cos(a) * 28, math.sin(a) * 28, -8), (math.cos(a) * 28, math.sin(a) * 28, 20), 1.6, R_METAL, 4)
    return 28, 0, 9


def em_queen(b):
    b.group(M_AIM)
    b.ball(-13, 0, 17, 18, R_MAIN)
    b.ball(8, 0, 14, 11, R_MAIN)
    b.ball(20, 0, 15, 7.5, R_LITE)
    b.bar((24, -4, 13), (33, -2, 9), 1.6, R_METAL, 4, 0.3)
    b.bar((24, 4, 13), (33, 2, 9), 1.6, R_METAL, 4, 0.3)
    for sx in (-2, 8, 16):
        for sg in (-1, 1):
            b.line([(sx, sg * 8, 12), (sx + 2, sg * 22, 16), (sx + 4, sg * 28, 0)], R_METAL, 2)
    for i, (ex, ey) in enumerate(((-18, 8), (-10, -9), (-22, -5), (-14, 2))):
        b.ball(ex, ey, 32 - i, 3.4, R_WHITE)
    b.prism(5, 20, 0, 22, 3.6, 3.6, R_ALT, rtop=5)
    return 28, 20, 5


def em_titan(b):
    b.group(M_AIM)
    b.box(0, -9, 0, 6, 5, 16, R_DARK)
    b.box(0, 9, 0, 6, 5, 16, R_DARK)
    b.box(0, 0, 16, 10, 15, 18, R_MAIN, 0.9)
    b.box(3, 0, 34, 5, 5, 6.5, R_LITE)
    b.box(0, -20, 26, 7, 6, 9, R_METAL)
    b.box(0, 20, 26, 7, 6, 9, R_METAL)
    b.bar((0, -21, 26), (8, -22, 8), 4.5, R_DARK, 4)
    b.bar((0, 21, 26), (8, 22, 8), 4.5, R_DARK, 4)
    b.ball(10.5, 0, 26, 4.4, R_LITE)
    b.glow(11, 0, 26, 22, R_LITE, 0.8)
    return 41, 3, 6


def em_architect(b):
    b.group(M_SPIN | M_BOB, 0.8, 0, 0, 12, 1.5, 3.0)
    b.crystal(0, 0, 0, 15, 36, R_LITE, 4)
    b.ring(0, 0, 18, 24, R_WHITE, 16, 2, 0.5)
    b.ring(0, 0, 18, 28, R_MAIN, 16, 2, -0.8, 1.2)
    b.ring(0, 0, 18, 32, R_LITE, 16, 1, 1.3, 2.4)
    b.glow(0, 0, 18, 44, R_LITE, 0.9)
    b.group(M_SPIN, -1.5, 0, 0, 22)
    for i in range(4):
        a = i * TAU / 4
        b.box(math.cos(a) * 30, math.sin(a) * 30, -4, 4, 4, 8, R_MAIN, 1.0, a)
    return 50, 0, 7


def em_megaduck(b):
    b.group(M_AIM)
    b.ball(-3, 0, 20, 22, DUCK_Y)
    b.ball(-24, 0, 26, 9, DUCK_Y)
    b.ball(14, 0, 44, 14, DUCK_Y)
    b.bar((24, 0, 42), (39, 0, 40), 5.5, DUCK_O, 4, 3.4)
    b.slab([(27, -12, 45), (27, 12, 45), (27, 12, 51), (27, -12, 51)], (10, 10, 16))
    return 58, 14, 9


ENEMY_MODELS = {
    "grunt": em_grunt, "runner": em_runner, "swarm": em_swarm, "tank": em_tank, "shield": em_shield, "splitter": em_splitter,
    "mini": em_mini, "healer": em_healer, "blinker": em_blinker, "phantom": em_phantom, "elite": em_elite, "jugger": em_jugger,
    "overseer": em_overseer, "queen": em_queen, "titan": em_titan, "architect": em_architect, "megaduck": em_megaduck,
}
_enemy_models = {}


def _hat(b, skin, x, z, r):
    """event enemies dress up"""
    if skin == "halloween":
        b.prism(8, x, 0, z, r * 1.6, 0.9, WITCH)
        b.prism(8, x, 0, z + 0.9, r * 0.95, r * 2.2, WITCH, rtop=0)
    elif skin == "xmas":
        b.prism(8, x, 0, z, r * 1.15, 1.4, SNOW_W)
        b.prism(8, x, 0, z + 1.4, r * 0.95, r * 1.9, SANTA, rtop=0)
        b.ball(x, 0, z + 1.4 + r * 1.9, r * 0.4, SNOW_W)
    elif skin == "pond":
        b.ball(x, 0, z + r * 0.7, r * 0.8, DUCK_Y)
        b.bar((x + r * 0.6, 0, z + r * 0.7), (x + r * 1.5, 0, z + r * 0.6), r * 0.3, DUCK_O, 4, r * 0.15)
    elif skin == "kitchen":
        b.prism(8, x, 0, z, r * 0.8, r * 1.0, SNOW_W)
        b.ball(x, 0, z + r * 1.4, r * 1.05, SNOW_W)
    elif skin == "glitch":
        b.box(x, 0, z + 2, r * 0.6, r * 0.6, r * 1.2, (255, 0, 255))
        b.box(x, 0, z + 2 + r * 1.2, r * 0.6, r * 0.6, r * 0.4, (10, 10, 16))
    elif skin == "market":
        b.slab([(x, -r * 0.8, z + r * 2.0), (x, r * 0.8, z + r * 2.0), (x, 0, z + r * 0.5)], STONK_R)
    elif skin == "quarry":
        b.prism(8, x, 0, z, r * 1.25, 0.8, HARDHAT)
        b.prism(8, x, 0, z + 0.8, r * 0.95, r * 0.9, HARDHAT, rtop=r * 0.5)


def enemy_model(kind, skin=None):
    key = (kind, skin)
    m = _enemy_models.get(key)
    if m is None:
        b = MB()
        top, hx, hr = ENEMY_MODELS[kind](b)
        if skin:
            b.group(M_AIM)
            _hat(b, skin, hx, top, hr)
        m = _enemy_models[key] = b.done(top + (hr * 2.4 if skin else 2))
    return m


# ---------------------------------------------------------------- a Summoner's goon
_goon_models = {}


def goon_model(lv=0):
    """(a stand-in until the real model is drawn) a little soldier with a spear.  Its legs walk (M_STEP) and its spear arm
    jabs (M_STRIKE).  It gets a helmet, a shield and a crest as its Summoner levels up."""
    lv = int(clamp(lv, 0, 4))
    m = _goon_models.get(lv)
    if m is None:
        b = MB()
        s = 1.0 + 0.07 * lv
        for ph, o in ((0.0, -2.1), (math.pi, 2.1)):
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 2.2, 1.6)
            b.box(0, o * s, 0, 1.5, 1.2, 5, R_DARK)
        b.group(M_AIM)
        b.box(0, 0, 5, 2.7 * s, 3.7 * s, 6 * s, R_MAIN, 0.82)
        hz = 5 + 6 * s
        b.ball(0.4, 0, hz + 2.3, 2.5, R_WHITE)
        if lv >= 1:
            b.prism(6, 0, 0, hz + 3.2, 2.9, 1.8, R_METAL if lv < 4 else R_ALT, rtop=1.6)
        if lv >= 2:
            b.slab([(3.2 * s, 2.0, 5.5), (3.2 * s, 6.5 * s, 5.5), (3.2 * s, 6.5 * s, 11.5 * s), (3.2 * s, 2.0, 11.5 * s)], R_LITE)
        if lv >= 3:
            b.slab([(-2, 0, hz + 4.6), (2, 0, hz + 4.6), (1, 0, hz + 8), (-3, 0, hz + 7.4)], R_ALT)
        b.group(M_AIM | M_STRIKE, 0.0, 0, 0, 0, 4.5, 0.8)
        b.bar((-1, -4.3 * s, 8.5 * s), (9 + lv, -4.3 * s, 9.5 * s), 0.6, R_METAL, 4)
        b.prism(4, 9 + lv, -4.3 * s, 9.5 * s - 0.9, 1.3, 1.8, R_ALT, rtop=0)
        m = _goon_models[lv] = b.done(hz + 7 + (3 if lv >= 3 else 0))
    return m


# ---------------------------------------------------------------- core, gate, npc, sword
_misc_models = {}


def core_model(skin):
    key = ("core", skin)
    m = _misc_models.get(key)
    if m is None:
        b = MB()
        b.prism(8, 0, 0, 0, 24, 4, R_DARK)
        b.prism(8, 0, 0, 4, 18, 3, R_MAIN, rtop=14)
        for i in range(4):
            a = i * TAU / 4 + math.pi / 4
            b.bar((math.cos(a) * 20, math.sin(a) * 20, 4), (math.cos(a) * 17, math.sin(a) * 17, 20), 1.6, R_METAL, 4)
            b.ball(math.cos(a) * 17, math.sin(a) * 17, 21.5, 2, R_LITE)
        b.group(M_SPIN | M_BOB, 0.8, 0, 0, 14, 1.6, 2.5)
        if skin == 0:
            b.crystal(0, 0, 0, 11, 30, R_LITE, 4)
        elif skin == 1:
            b.crystal(0, 0, 0, 12, 26, R_LITE, 6)
        elif skin == 2:
            b.crystal(0, 0, 0, 12, 28, R_LITE, 3)
            b.crystal(0, 0, 0, 12, 28, R_LITE, 3, math.pi / 3)
        else:
            b.ball(0, 0, 15, 11, R_LITE)
        b.glow(0, 0, 15, 46, R_LITE, 0.9)
        b.group(M_SPIN, -1.3, 0, 0, 29)
        b.ring(0, 0, 0, 18, R_LITE, 16, 2, 0.45)
        b.ring(0, 0, 0, 22, R_WHITE, 16, 1, -0.8, 1.4)
        m = _misc_models[key] = b.done(52)
    return m


def gate_model():
    m = _misc_models.get("gate")
    if m is None:
        b = MB()
        b.group(M_AIM)
        b.box(0, -24, 0, 4, 4, 34, R_DARK, 0.85)
        b.box(0, 24, 0, 4, 4, 34, R_DARK, 0.85)
        b.box(0, 0, 34, 4, 28, 5, R_MAIN, 0.9)
        b.ball(0, -24, 37, 3, R_LITE)
        b.ball(0, 24, 37, 3, R_LITE)
        b.ring(0, 0, 17, 16, R_LITE, 14, 2, math.pi / 2, math.pi / 2)
        b.ring(0, 0, 17, 11, R_WHITE, 12, 1, math.pi / 2, math.pi / 2)
        b.glow(0, 0, 17, 34, R_LITE, 0.7)
        m = _misc_models["gate"] = b.done(44)
    return m


def npc_model(hat):
    key = ("npc", hat)
    m = _misc_models.get(key)
    if m is None:
        b = MB()
        b.group(M_AIM | M_BOB, 0, 0, 0, 0, 2.0, 0.8)
        b.prism(8, 0, 0, 0, 6, 11, R_MAIN, rtop=3)
        b.ball(0, 0, 14.5, 4.2, R_WHITE)
        b.ball(3.4, -1.5, 15.3, 0.8, R_BLACK)
        b.ball(3.4, 1.5, 15.3, 0.8, R_BLACK)
        if hat == "cap":
            b.prism(8, 0, 0, 17.6, 4.4, 2, R_LITE, rtop=3.4)
            b.box(4, 0, 17.6, 2.5, 3, 0.6, R_LITE)
        elif hat == "top":
            b.prism(8, 0, 0, 17.8, 5.6, 0.7, R_BLACK)
            b.prism(8, 0, 0, 18.5, 3.5, 5, R_BLACK)
        elif hat == "chef":
            b.prism(8, 0, 0, 17.8, 3.4, 3.4, SNOW_W)
            b.ball(0, 0, 22.5, 4.2, SNOW_W)
        elif hat == "hood":
            b.prism(8, 0, 0, 13, 5.6, 8, R_DARK, rtop=1)
        elif hat == "antenna":
            b.bar((0, 0, 18), (0, 0, 26), 0.5, R_METAL, 4)
            b.ball(0, 0, 26.5, 1.4, R_LITE)
        elif hat == "elf":
            b.prism(8, 0, 0, 17.6, 4.2, 9, (60, 200, 90), rtop=0)
            b.ball(0, 0, 27, 1.2, SANTA)
        elif hat == "hard":
            b.prism(8, 0, 0, 17.4, 5.4, 0.8, HARDHAT)
            b.prism(8, 0, 0, 18.2, 4.2, 3, HARDHAT, rtop=2.4)
        elif hat == "crown":
            b.prism(6, 0, 0, 17.8, 3.4, 3.4, R_ALT, rtop=4.6)
        m = _misc_models[key] = b.done(30)
    return m


def blade_model():
    """the Sword of Justice: point at z=0, hilt high above"""
    m = _misc_models.get("justice")
    if m is None:
        b = MB()
        for rot in (0.0, math.pi / 2):
            ca, sa = math.cos(rot), math.sin(rot)

            def P(a, z):
                return (ca * a, sa * a, z)
            b.slab([P(0, 0), P(11, 34), P(11, 190), P(-11, 190), P(-11, 34)], R_WHITE if rot == 0.0 else R_ALT)
        b.box(0, 0, 190, 30, 5, 9, R_ALT)
        b.bar((0, 0, 199), (0, 0, 240), 4.5, R_METAL, 6)
        b.crystal(0, 0, 238, 9, 20, R_LITE, 6)
        b.glow(0, 0, 100, 90, R_ALT, 0.8)
        m = _misc_models["justice"] = b.done(260)
    return m


# ---------------------------------------------------------------- scenery
def _prop(name, v):
    b = MB()
    f = 1.0 + 0.22 * v
    if name == "pylon":
        b.prism(4, 0, 0, 0, 3.5, 26 * f, R_DARK, rtop=1.5, rot=math.pi / 4)
        b.ball(0, 0, 28 * f, 2.6, R_LITE)
        b.glow(0, 0, 28 * f, 16, R_LITE, 0.6)
    elif name == "datatower":
        h = (60, 96, 140)[v]
        b.box(0, 0, 0, 13, 13, h, R_DARK, 0.92)
        for i in range(1 + v):
            zz = h * (0.3 + 0.25 * i)
            b.ring(0, 0, zz, 15, R_LITE, 4, 2, 0, math.pi / 4)
        b.bar((0, 0, h), (0, 0, h + 18), 0.8, R_METAL, 4)
        b.ball(0, 0, h + 19, 1.8, R_LITE)
    elif name == "building":
        h = (46, 78, 120)[v]
        wx, wy = (16, 22, 14)[v], (20, 14, 14)[v]
        b.box(0, 0, 0, wx, wy, h, R_DARK)
        for i in range(2 + v):
            zz = h * (i + 1) / (3.2 + v)
            b.line([(-wx, wy + 0.3, zz), (wx, wy + 0.3, zz)], R_LITE, 2)
            b.line([(wx + 0.3, -wy, zz), (wx + 0.3, wy, zz)], R_MAIN, 2)
        if v == 2:
            b.box(0, 0, h, 5, 5, 10, R_MAIN)
    elif name == "lamp":
        b.bar((0, 0, 0), (0, 0, 24), 0.8, R_METAL, 4)
        b.bar((0, 0, 24), (7, 0, 26), 0.7, R_METAL, 4)
        b.ball(7.5, 0, 25, 2.2, R_LITE)
        b.glow(7.5, 0, 25, 18, R_LITE, 0.7)
    elif name == "billboard":
        b.bar((-10, 0, 0), (-10, 0, 22), 1.0, R_METAL, 4)
        b.bar((10, 0, 0), (10, 0, 22), 1.0, R_METAL, 4)
        b.slab([(-16, 0, 20), (16, 0, 20), (16, 0, 38), (-16, 0, 38)], R_MAIN)
        b.line([(-12, 0.4, 26), (0, 0.4, 33), (5, 0.4, 27), (12, 0.4, 34)], R_LITE, 3)
    elif name == "monolith":
        h = 40 * f
        b.box(0, 0, 0, 7, 3, h, R_BLACK, 0.9, 0.4 * v)
        b.line([(math.cos(0.4 * v) * 0 + 0, 3.3, 4), (0, 3.3, h - 4)], R_LITE, 2)
    elif name == "floatrock":
        b.group(M_BOB | M_SPIN, 0.15, 0, 0, 22 + 8 * v, 0.7, 4.0)
        b.crystal(0, 0, 0, 10 * f, 16 * f, R_DARK, 5, 0.3, 0.7)
        b.ring(0, 0, 11 * f, 13 * f, R_MAIN, 10, 1, 0.3)
    elif name == "tombstone":
        b.box(0, 0, 0, 6, 2, 12 * f, (120, 124, 140), 0.9)
        b.line([(-3, 2.2, 9 * f), (3, 2.2, 9 * f)], R_LITE, 2)
        b.line([(0, 2.2, 5 * f), (0, 2.2, 11 * f)], R_LITE, 2)
    elif name == "volcano":
        r = 30 * f
        b.prism(7, 0, 0, 0, r, 30 * f, (70, 36, 30), rtop=r * 0.35)
        b.prism(7, 0, 0, 30 * f, r * 0.33, 0.6, (255, 150, 40))
        b.glow(0, 0, 32 * f, 40, (255, 120, 30), 0.9)
    elif name == "spike":
        b.prism(5, 0, 0, 0, 7 * f, 22 * f, (84, 44, 36), rtop=0, rot=v)
        if v:
            b.prism(4, 7, 3, 0, 4, 11 * f, (84, 44, 36), rtop=0)
    elif name == "vent":
        b.prism(6, 0, 0, 0, 7, 4, (60, 34, 30), rtop=5)
        b.ball(0, 0, 4, 3.2, (255, 150, 40))
        b.glow(0, 0, 5, 20, (255, 120, 30), 0.8)
    elif name == "glitchcube":
        b.group(M_BOB | M_SPIN, 0.5 + 0.3 * v, 0, 0, 14 + 9 * v, 1.2, 4.0)
        b.box(0, 0, 0, 6 * f, 6 * f, 12 * f, R_MAIN, 1.0, 0.5, True, True)
        b.ring(0, 0, 6 * f, 11 * f, R_LITE, 4, 1, 0.6)
    elif name == "pillar":
        h = (16, 28, 40)[v]
        b.prism(6, 0, 0, 0, 5.5, h, R_DARK, rtop=4.5)
        b.prism(6, 0, 0, h, 6.5, 2, R_MAIN)
    elif name == "pine":
        b.prism(6, 0, 0, 0, 2.2, 7, (90, 70, 60))
        for i in range(3):
            b.prism(7, 0, 0, 6 + i * 8 * f, (13 - i * 3.4) * f, 11 * f, (60, 190, 150) if i % 2 == 0 else (90, 215, 180), rtop=0, rot=i * 0.4)
        b.prism(7, 0, 0, 6 + 2 * 8 * f + 6 * f, 4 * f, 5 * f, SNOW_W, rtop=0)
    elif name == "bigpine":
        b.prism(6, 0, 0, 0, 4, 12, (90, 70, 60))
        for i in range(4):
            b.prism(8, 0, 0, 10 + i * 15, 26 - i * 5.5, 20, (50, 180, 130) if i % 2 == 0 else (80, 210, 165), rtop=0, rot=i * 0.4)
        b.crystal(0, 0, 76, 5, 11, R_ALT, 5)
        b.glow(0, 0, 81, 24, GOLD, 0.9)
        for i in range(10):
            a = i * 2.4
            rr = 22 - i * 1.7
            b.ball(math.cos(a) * rr, math.sin(a) * rr, 14 + i * 5.6, 1.6, (SANTA, GOLD, CYAN, GREEN)[i % 4])
    elif name == "icecrystal":
        b.crystal(0, 0, 0, 6 * f, 22 * f, ICE, 5, 0.4 * v, 0.3)
        b.crystal(7, 3, 0, 3.5, 12 * f, ICE, 4, 0.9, 0.3)
        b.glow(0, 0, 10 * f, 22, ICE, 0.4)
    elif name == "snowmound":
        b.ball(0, 0, 1, 9 * f, SNOW_W)
        b.ball(8, 4, 0, 6 * f, SNOW_W)
    elif name == "stove":
        b.box(0, 0, 0, 9, 7, 12, (70, 84, 112))
        b.box(0, 0, 12, 9.6, 7.6, 1.2, (40, 48, 64))
        b.bar((-5, 0, 13), (-5, 0, 30), 1.8, (40, 48, 64), 6)
        b.slab([(9.2, -4, 2), (9.2, 4, 2), (9.2, 4, 8), (9.2, -4, 8)], (10, 10, 16))
        b.ring(3, 0, 13.4, 3, ICE, 8, 2)
    elif name == "cactus":
        b.prism(6, 0, 0, 0, 3.4, 20 * f, (60, 190, 110))
        b.bar((0, 0, 9), (7, 0, 9), 2, (60, 190, 110), 4)
        b.bar((7, 0, 9), (7, 0, 17), 2, (60, 190, 110), 4)
        if v:
            b.bar((0, 0, 13), (-6, 0, 13), 1.8, (60, 190, 110), 4)
            b.bar((-6, 0, 13), (-6, 0, 20), 1.8, (60, 190, 110), 4)
    elif name == "pyramid":
        r = (26, 38, 52)[v]
        b.prism(4, 0, 0, 0, r, r * 0.9, (190, 150, 90), rtop=0, rot=math.pi / 4 + 0.2 * v)
        b.ring(0, 0, r * 0.45, r * 0.52, R_LITE, 4, 2, 0, math.pi / 4 + 0.2 * v)
    elif name == "obelisk":
        b.prism(4, 0, 0, 0, 4, 30 * f, (190, 150, 90), rtop=2.4, rot=math.pi / 4)
        b.prism(4, 0, 0, 30 * f, 2.4, 4, R_ALT, rtop=0, rot=math.pi / 4)
    elif name == "bones":
        b.bar((-8, -3, 1), (8, 3, 1), 1.2, SNOW_W, 4)
        b.bar((-6, 5, 1), (5, -6, 1), 1.2, SNOW_W, 4)
        b.ball(9, 4, 2, 2.4, SNOW_W)
    elif name == "holotree":
        b.prism(5, 0, 0, 0, 2.4, 14 * f, (70, 60, 90))
        b.group(M_BOB, 0, 0, 0, 13 * f, 1.0 + 0.2 * v, 1.2)
        b.crystal(0, 0, 0, 10 * f, 20 * f, (60, 235, 150) if v != 1 else (80, 220, 255), 6, 0.3 * v, 0.35)
        b.glow(0, 0, 9 * f, 22, (60, 235, 150), 0.4)
    elif name == "mushroom":
        b.prism(6, 0, 0, 0, 1.8, 7 * f, SNOW_W)
        b.prism(8, 0, 0, 7 * f, 7 * f, 4 * f, (255, 90, 200) if v != 1 else (90, 220, 255), rtop=1.5)
        b.glow(0, 0, 8 * f, 16, (255, 90, 200) if v != 1 else (90, 220, 255), 0.6)
    elif name == "coral":
        c = ((255, 110, 150), (255, 170, 80), (150, 110, 255))[v]
        b.bar((0, 0, 0), (0, 0, 14 * f), 2, c, 4)
        b.bar((0, 0, 7 * f), (7, 3, 16 * f), 1.5, c, 4)
        b.bar((0, 0, 9 * f), (-6, -4, 19 * f), 1.5, c, 4)
        b.bar((0, 0, 5 * f), (-3, 7, 12 * f), 1.3, c, 4)
    elif name == "lighthouse":
        b.prism(8, 0, 0, 0, 10, 50, SNOW_W, rtop=6.5)
        b.ring(0, 0, 18, 9.2, SANTA, 8, 4)
        b.ring(0, 0, 34, 7.8, SANTA, 8, 4)
        b.prism(8, 0, 0, 50, 8, 2, R_DARK)
        b.ball(0, 0, 56, 4.5, R_LITE)
        b.prism(8, 0, 0, 60, 7, 6, SANTA, rtop=0)
        b.glow(0, 0, 56, 50, GOLD, 0.9)
    elif name == "buoy":
        b.group(M_BOB, 0, 0, 0, 0, 1.4 + 0.3 * v, 1.5)
        b.ball(0, 0, 3, 5, SANTA)
        b.bar((0, 0, 6), (0, 0, 16), 0.7, R_METAL, 4)
        b.ball(0, 0, 17, 1.6, R_LITE)
    elif name == "crystals":
        c = ((255, 110, 230), (110, 220, 255), (150, 255, 170))[v]
        b.crystal(0, 0, 0, 7 * f, 30 * f, c, 5, 0.3, 0.25)
        b.crystal(9, 4, 0, 4.5, 18 * f, c, 4, 1.0, 0.25)
        b.crystal(-7, 6, 0, 3.8, 14 * f, c, 4, 0.5, 0.25)
        b.crystal(-3, -8, 0, 3.4, 11 * f, c, 4, 0.2, 0.25)
        b.glow(0, 0, 12 * f, 30, c, 0.5)
    elif name == "stalagmite":
        b.prism(6, 0, 0, 0, 8 * f, 26 * f, (84, 80, 120), rtop=0, rot=v)
    elif name == "island":
        b.group(M_BOB, 0, 0, 0, 30 + 10 * v, 0.5 + 0.1 * v, 4.0)
        b.prism(7, 0, 0, -24 * f, 2, 24 * f, (110, 96, 120), rtop=18 * f, bottom=True)
        b.prism(7, 0, 0, 0, 18 * f, 3, (90, 210, 130))
        b.prism(5, 4, 2, 3, 1.4, 8, (90, 70, 60))
        b.prism(6, 4, 2, 10, 6, 10, (60, 190, 110), rtop=0)
    elif name == "cloud":
        b.group(M_BOB, 0, 0, 0, 60 + 14 * v, 0.4, 3.0)
        b.ball(0, 0, 0, 12 * f, SNOW_W)
        b.ball(13, 2, -2, 9 * f, SNOW_W)
        b.ball(-12, -2, -3, 8 * f, SNOW_W)
    elif name == "chimney":
        h = (44, 66, 90)[v]
        b.prism(8, 0, 0, 0, 8, h, (104, 84, 80), rtop=5.5)
        b.ring(0, 0, h, 6, (255, 150, 40), 8, 3)
        b.group(M_BOB, 0, 0, 0, h + 10, 0.8, 5.0)
        b.ball(2, 0, 0, 6, (96, 100, 120))
        b.ball(-3, 2, 9, 8, (76, 80, 100))
    elif name == "tank":
        b.prism(8, 0, 0, 0, 14 * f, 18 * f, R_METAL)
        b.prism(8, 0, 0, 18 * f, 14 * f, 5, R_DARK, rtop=5)
        b.ring(0, 0, 9 * f, 14.6 * f, (255, 150, 40), 8, 3)
    elif name == "crate":
        b.box(0, 0, 0, 6 * f, 6 * f, 10 * f, (150, 110, 70), 1.0, 0.3 * v)
        if v:
            b.box(9, 5, 0, 4, 4, 7, (150, 110, 70), 1.0, 0.8)
    elif name == "palm":
        b.bar((0, 0, 0), (4, 0, 26 * f), 1.8, (150, 110, 70), 5, 1.2)
        for i in range(5):
            a = i * TAU / 5 + v
            ca, sa = math.cos(a), math.sin(a)
            b.slab([(4, 0, 26 * f), (4 + ca * 10 - sa * 3, sa * 10 + ca * 3, 27 * f), (4 + ca * 19, sa * 19, 20 * f), (4 + ca * 10 + sa * 3, sa * 10 - ca * 3, 27 * f)], (60, 220, 150))
    elif name == "car":
        c = ((255, 80, 170), (0, 229, 255), (255, 206, 84))[v]
        b.box(0, 0, 2, 11, 5, 4, c, 0.95)
        b.box(-1, 0, 6, 5.5, 4.4, 3.4, (20, 24, 44), 0.8)
        for sx in (-7, 7):
            for sy in (-5.4, 5.4):
                b.ball(sx, sy, 2.2, 2.2, R_BLACK)
        b.ball(11.2, -3, 4, 0.9, R_WHITE)
        b.ball(11.2, 3, 4, 0.9, R_WHITE)
    elif name == "pumpkinprop":
        b.ball(0, 0, 4.5 * f, 5.5 * f, PUMP_O)
        b.box(0, 0, 9.5 * f, 0.9, 0.9, 2, PUMP_G)
        b.glow(0, 0, 5, 14, PUMP_Y, 0.5)
    elif name == "deadtree":
        c = (96, 80, 110)
        b.bar((0, 0, 0), (2, 1, 22 * f), 2.4, c, 5, 1.4)
        b.bar((2, 1, 14 * f), (12, 3, 26 * f), 1.3, c, 4, 0.4)
        b.bar((1, 0, 10 * f), (-10, -4, 22 * f), 1.3, c, 4, 0.4)
        b.bar((2, 1, 22 * f), (-2, 6, 34 * f), 1.0, c, 4, 0.3)
    elif name == "lantern":
        b.bar((0, 0, 0), (0, 0, 16), 0.7, R_METAL, 4)
        b.ball(0, 0, 18, 2.6, PUMP_Y)
        b.glow(0, 0, 18, 22, PUMP_O, 0.8)
    elif name == "candycane":
        b.line([(0, 0, 0), (0, 0, 18 * f), (2, 0, 22 * f), (6, 0, 22 * f), (8, 0, 18 * f)], SANTA, 4)
        b.line([(0, 0, 4), (0, 0, 8)], SNOW_W, 4)
        b.line([(0, 0, 12), (0, 0, 16)], SNOW_W, 4)
    elif name == "gift":
        c = (SANTA, (60, 200, 90), (90, 150, 255))[v]
        b.box(0, 0, 0, 6 * f, 6 * f, 9 * f, c, 1.0, 0.4 * v)
        b.ring(0, 0, 4.5 * f, 8.6 * f, GOLD, 4, 3, 0, math.pi / 4 + 0.4 * v)
        b.ball(0, 0, 10.5 * f, 2, GOLD)
    elif name == "snowman":
        b.ball(0, 0, 5, 6, SNOW_W)
        b.ball(0, 0, 13, 4.2, SNOW_W)
        b.ball(0, 0, 19, 3, SNOW_W)
        b.bar((2.5, 0, 19), (6, 0, 18.8), 0.8, DUCK_O, 4, 0.1)
    elif name == "lilypad":
        b.prism(9, 0, 0, 0.3, 9 * f, 0.6, (60, 200, 110), rot=v)
        if v == 1:
            b.ball(2, 1, 2.4, 2.2, (255, 150, 200))
    elif name == "reeds":
        for i in range(4):
            x, y = (i % 2) * 4 - 2, (i // 2) * 4 - 2
            b.bar((x, y, 0), (x + 1, y, 16 + i * 3), 0.6, (90, 200, 110), 4)
            b.ball(x + 1, y, 17 + i * 3, 1.3, (150, 110, 70))
    elif name == "duckprop":
        b.group(M_BOB | M_SPIN, 0.4, 0, 0, 0, 2.0, 0.8)
        b.ball(-1, 0, 4, 5, DUCK_Y)
        b.ball(3, 0, 9.5, 3.2, DUCK_Y)
        b.bar((5.4, 0, 9), (8.6, 0, 8.6), 1.2, DUCK_O, 4, 0.7)
        b.ball(4.8, -1.6, 10.4, 0.6, R_BLACK)
        b.ball(4.8, 1.6, 10.4, 0.6, R_BLACK)
    elif name == "fork":
        b.bar((0, 0, 0), (0, 0, 40), 1.6, R_METAL, 4)
        b.slab([(-6, 0, 38), (6, 0, 38), (6, 0, 46), (-6, 0, 46)], R_METAL)
        for x in (-5, -1.7, 1.7, 5):
            b.bar((x, 0, 46), (x, 0, 62), 0.9, R_METAL, 4)
    elif name == "pot":
        b.prism(8, 0, 0, 0, 14 * f, 14 * f, R_METAL)
        b.prism(8, 0, 0, 14 * f, 14.8 * f, 1.5, R_DARK)
        b.bar((14 * f, 0, 10 * f), (24 * f, 0, 12 * f), 1.6, R_BLACK, 4)
        b.group(M_BOB, 0, 0, 0, 20 * f, 1.5, 3.0)
        b.ball(0, 0, 0, 4, SNOW_W)
        b.ball(5, 3, 6, 3, SNOW_W)
    elif name == "cheese":
        b.mesh([(-12, -8, 0), (12, -8, 0), (12, 8, 0), (-12, 8, 0), (12, -8, 14), (12, 8, 14)],
               [(0, 1, 4), (3, 5, 2), (0, 4, 5, 3), (1, 2, 5, 4), (0, 3, 2, 1)], (255, 214, 60))
    elif name == "sign404":
        b.bar((0, 0, 0), (0, 0, 18), 0.9, R_METAL, 4)
        b.slab([(-12, 0, 16), (12, 0, 16), (12, 0, 28), (-12, 0, 28)], (255, 0, 255))
        b.slab([(-12, 0, 16), (0, 0, 16), (0, 0, 22), (-12, 0, 22)], (10, 10, 16))
        b.slab([(0, 0, 22), (12, 0, 22), (12, 0, 28), (0, 0, 28)], (10, 10, 16))
    elif name == "candle":
        up = v != 1
        c = STONK_G if up else STONK_R
        h = (22, 34, 50)[v]
        b.bar((0, 0, 0), (0, 0, h + 14), 0.6, c, 4)
        b.box(0, 0, 6, 4.5, 4.5, h, c)
    elif name == "ticker":
        b.bar((-14, 0, 0), (-14, 0, 26), 1.0, R_METAL, 4)
        b.bar((14, 0, 0), (14, 0, 26), 1.0, R_METAL, 4)
        b.slab([(-18, 0, 24), (18, 0, 24), (18, 0, 36), (-18, 0, 36)], (10, 14, 20))
        b.line([(-15, 0.4, 27), (-8, 0.4, 31), (-3, 0.4, 28), (4, 0.4, 33), (9, 0.4, 30), (15, 0.4, 34)], STONK_G, 3)
    elif name == "bricks":
        c = (190, 96, 70)
        for i in range(3 + v):
            b.box((i % 2) * 5 - 2, (i // 2) * 7 - 3, (i // 3) * 5, 6, 3, 5, c, 1.0, 0.2 * i)
    elif name == "crane":
        b.bar((0, 0, 0), (0, 0, 70), 2.4, HARDHAT, 4)
        b.bar((-14, 0, 68), (44, 0, 68), 1.8, HARDHAT, 4)
        b.line([(36, 0, 68), (36, 0, 38)], R_METAL, 2)
        b.box(36, 0, 30, 4, 4, 8, R_METAL)
        b.box(-12, 0, 60, 5, 4, 8, R_DARK)
    elif name == "cone":
        b.prism(4, 0, 0, 0, 4.6, 1, (255, 120, 30), rot=math.pi / 4)
        b.prism(8, 0, 0, 1, 3.2, 9, (255, 120, 30), rtop=0.6)
        b.ring(0, 0, 5, 2.2, SNOW_W, 8, 3)
    elif name == "rock":
        b.crystal(0, 0, -3 * f, 9 * f, 13 * f, (84, 88, 112), 5, 0.7 * v, 0.6)
    elif name == "tuft":
        for i in range(3):
            a = i * 2.1 + v
            b.line([(math.cos(a) * 2, math.sin(a) * 2, 0), (math.cos(a) * 5, math.sin(a) * 5, 7 + i * 2)], R_LITE, 2)
    elif name == "runestone":
        b.prism(5, 0, 0, 0, 6, 16 * f, (70, 74, 110), rtop=3.6, rot=0.6 * v)
        b.ring(0, 0, 8 * f, 5.4, R_LITE, 5, 2, 0, 0.6 * v)
        b.glow(0, 0, 9 * f, 16, R_LITE, 0.4)
    elif name == "satellite":
        b.bar((0, 0, 0), (0, 0, 14), 1.4, R_METAL, 4)
        b.prism(8, 3, 0, 13, 1.5, 6, R_DARK, rtop=10)
        b.ball(3, 0, 20, 1.6, R_LITE)
    elif name == "pipe":
        b.bar((-22, 0, 6), (22, 0, 6), 4, R_METAL, 6)
        b.ring(-10, 0, 6, 5, (255, 150, 40), 8, 3, math.pi / 2, math.pi / 2)
        b.ring(10, 0, 6, 5, (255, 150, 40), 8, 3, math.pi / 2, math.pi / 2)
    else:
        b.box(0, 0, 0, 5, 5, 10, R_MAIN)
    return b.done()


_prop_models = {}


def prop_model(name, v=0):
    key = (name, v)
    m = _prop_models.get(key)
    if m is None:
        m = _prop_models[key] = _prop(name, v)
    return m
# ======================================================================
#  MK II MODELS  -  the detailed towers, enemies and goons, and the map themes that dress them
#  (the old simple models above stay: they are used on LOW detail and when you are zoomed far out)
# ======================================================================
def lathe(b, x, y, prof, n, roles, rot=0.0, edge=True):
    """a turned shape: prof = [(radius, height), ...] from the bottom up"""
    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        role = roles[i] if isinstance(roles, list) else roles
        b.prism(n, x, y, z0, r0, z1 - z0, role, rtop=r1, rot=rot, edge=edge)


def hull(b, x0, x1, hw, z, h, role, nose=0.0, tail=0.0, topw=None, edge=True, y=0.0):
    """an armoured body: a box whose front and back slope in and whose top is narrower"""
    tw = hw if topw is None else topw
    vs = [(x0, y - hw, z), (x1, y - hw, z), (x1, y + hw, z), (x0, y + hw, z),
          (x0 + tail, y - tw, z + h), (x1 - nose, y - tw, z + h), (x1 - nose, y + tw, z + h), (x0 + tail, y + tw, z + h)]
    b.mesh(vs, [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], role, edge)


def pips(b, lv, R, z=0.5):
    """one lit pip on the rim for every level"""
    for i in range(lv + 1):
        a = -math.pi / 2 + (i - lv / 2.0) * 0.30
        b.ball(math.cos(a) * (R + 0.3), math.sin(a) * (R + 0.3), z + 0.7, 0.95, R_WHITE)


def pad2(b, lv, r=13.0, n=8, box=15.0):
    """the plinth: dark deck, metal clamps, a neon seam, level pips, and it gets richer as the tower levels up"""
    R = min(r + 1.5, box - 0.5)
    rot = TAU / (2 * n)
    lathe(b, 0, 0, [(R, 0), (R, 2.2), (R - 1.7, 3.4)], n, [R_BLACK, R_DARK], rot)
    b.ring(0, 0, 2.35, R + 0.25, R_LITE, 16, 1)
    for i in range(4):
        a = TAU / 8 + i * TAU / 4
        b.box(math.cos(a) * (R - 1.2), math.sin(a) * (R - 1.2), 0, 2.4, 1.5, 4.3, R_METAL, 0.8, a)
    z = 3.4
    if lv >= 1:
        lathe(b, 0, 0, [(R - 3.2, z), (R - 3.8, z + 1.5)], n, R_MAIN, rot)
        z += 1.5
    if lv >= 3:
        lathe(b, 0, 0, [(R - 5.0, z), (R - 5.4, z + 1.2)], n, R_METAL, rot)
        z += 1.2
    pips(b, lv, R)
    if lv >= 4:
        b.ring(0, 0, 0.8, min(R + 2.0, box + 0.6), R_ALT, 16, 2)
    th = getattr(b, "theme", None)
    if th:
        dress_base(b, th, R, lv)
    return z


def halo(b, z, r, n=3):
    """max level: a slow crown of gold shards turning above the tower"""
    b.group(M_SPIN | M_BOB, 0.9, 0, 0, z, 1.6, 0.8)
    b.ring(0, 0, 0, r, R_ALT, 16, 2)
    for i in range(n):
        a = i * TAU / n
        b.crystal(math.cos(a) * r, math.sin(a) * r, -1.6, 1.3, 3.2, R_ALT, 3)


# ====================================================================== TOWERS
def tm2_blaster(b, lv):
    z = pad2(b, lv)
    lathe(b, 0, 0, [(6.6, z), (5.6, z + 2.2)], 8, R_METAL, TAU / 16)
    z += 2.2
    b.group(M_AIM | M_RECOIL)
    lathe(b, 0, 0, [(7.8, z), (6.8, z + 2.1)], 8, R_BLACK)
    zt = z + 2.1
    hh = 5.2 + lv * 0.25
    hull(b, -7.6, 7.2, 5.4, zt, hh, R_MAIN, nose=4.4, tail=1.6, topw=4.0)
    for s in (-1, 1):
        b.box(0.2, s * 6.5, zt + 0.5, 5.6, 1.0, 4.0, R_DARK, 0.86)
        b.line([(-4.6, s * 7.65, zt + 2.7), (5.0, s * 7.65, zt + 2.7)], R_LITE, 2)
    zb = zt + 2.9
    L = 18.5 + lv * 1.2
    offs = [0.0] if lv < 2 else [-2.7, 2.7] if lv < 4 else [-3.4, 0.0, 3.4]
    b.box(5.6, 0, zb - 2.5, 1.3, 2.6 + abs(offs[0]), 5.0, R_METAL)
    for o in offs:
        zz = zb + (1.2 if (lv >= 4 and o == 0.0) else 0.0)
        b.bar((4.5, o, zz), (10.5, o, zz), 2.3, R_DARK, 4)
        b.bar((10.5, o, zz), (L, o, zz), 1.3, R_METAL, 6)
        b.bar((L - 0.4, o, zz), (L + 2.4, o, zz), 1.9, R_LITE, 6)
    b.prism(6, -2.6, 0, zt + hh, 2.7, 1.0, R_DARK)
    b.box(-8.7, 0, zt + 0.8, 1.5, 4.0, 3.8, R_DARK)
    b.line([(-10.3, -3.0, zt + 3.0), (-10.3, 3.0, zt + 3.0)], R_LITE, 2)
    if lv >= 1:
        b.ball(1.8, 2.5, zt + hh + 0.9, 1.25, R_WHITE)
    if lv >= 2:
        for s in (-1, 1):
            b.bar((-3.5, s * 5.0, zt + hh - 0.5), (-1.0, s * 5.6, zt + hh + 2.6), 0.9, R_METAL, 4)
    if lv >= 3:
        b.line([(-6.0, -3.4, zt + hh), (-7.6, -3.4, zt + hh + 9.5)], R_METAL, 1)
        b.ball(-7.6, -3.4, zt + hh + 9.8, 0.8, R_LITE)
        b.glow(L + 2.4, 0, zb, 7, R_LITE, 0.5)
    if lv >= 4:
        b.line([(-6.0, -4.0, zt + hh + 0.1), (2.8, -4.0, zt + hh + 0.1), (2.8, 4.0, zt + hh + 0.1), (-6.0, 4.0, zt + hh + 0.1)], R_ALT, 2, True)
        halo(b, zt + hh + 13, 8.5)


def tm2_rail(b, lv):
    z = pad2(b, lv, 11.5)
    # bipod: two struts from the plinth up to the cradle
    for s in (-1, 1):
        b.bar((6.5, s * 7.5, 2.5), (1.5, s * 2.6, z + 5.0), 0.9, R_METAL, 4)
    lathe(b, 0, 0, [(4.8, z), (3.8, z + 4.4)], 6, R_METAL)
    b.group(M_AIM | M_RECOIL)
    zz = z + 4.4
    L = 23.0 + lv * 1.3
    hull(b, -9.0, 4.5, 3.6, zz, 4.6, R_MAIN, nose=1.2, tail=2.2, topw=2.6)          # breech
    for s in (-1, 1):
        b.box((4.5 + L) / 2, s * 1.9, zz + 1.2, (L - 4.5) / 2, 0.7, 2.4, R_DARK)     # the two rails
    b.box((4.5 + L) / 2, 0, zz + 2.1, (L - 4.5) / 2, 0.75, 0.7, R_LITE, edge=False)   # the charge between them
    nc = 2 + (lv + 1) // 2
    for i in range(nc):
        x = 7.5 + (L - 10.5) * i / max(1, nc - 1)
        b.box(x, 0, zz + 0.5, 0.8, 3.3, 3.8, R_WHITE if (lv >= 3 and i == nc - 1) else R_METAL)   # coil frames
    b.box(-10.5, 0, zz + 0.6, 1.6, 3.0, 3.4, R_DARK)                                 # capacitor
    for s in (-1, 0, 1):
        b.slab([(-12.1, s * 2.2, zz + 1.0), (-15.5 - lv * 0.4, s * 2.2, zz + 5.5 + lv * 0.5), (-12.1, s * 2.2, zz + 4.2)], R_MAIN if s else R_LITE)
    if lv >= 1:
        b.bar((-5.0, 0, zz + 5.6), (2.0, 0, zz + 5.6), 0.9, R_DARK, 6)                # scope
        b.ball(2.3, 0, zz + 5.6, 0.9, R_WHITE)
    if lv >= 2:
        b.line([(-9.0, -3.7, zz + 2.4), (4.0, -3.7, zz + 2.4)], R_LITE, 2)
        b.line([(-9.0, 3.7, zz + 2.4), (4.0, 3.7, zz + 2.4)], R_LITE, 2)
    if lv >= 3:
        b.glow(L, 0, zz + 2.1, 8, R_LITE, 0.6)
    if lv >= 4:
        for i in range(nc):
            x = 7.5 + (L - 10.5) * i / max(1, nc - 1)
            b.line([(x, -3.4, zz + 4.4), (x, 3.4, zz + 4.4)], R_ALT, 2)
        b.ball(-10.5, 0, zz + 5.4, 1.7, R_WHITE)
        b.glow(-10.5, 0, zz + 5.4, 7, R_LITE, 0.7)
        halo(b, zz + 15, 7.5)


def tm2_mortar(b, lv):
    z = pad2(b, lv, 13)
    # shell rack on the deck
    ns = 2 + lv // 2
    for i in range(ns):
        y = (i - (ns - 1) / 2.0) * 3.2
        b.prism(4, -8.5, y, z, 1.4, 3.6, R_METAL)
        b.prism(4, -8.5, y, z + 3.6, 1.4, 2.0, R_LITE, rtop=0)
    b.group(M_AIM | M_RECOIL)
    lathe(b, 0, 0, [(7.4, z), (7.4, z + 1.6), (6.0, z + 2.6)], 8, [R_BLACK, R_DARK], TAU / 16)
    zz = z + 2.6
    for s in (-1, 1):                                                            # trunnion cheeks
        b.mesh([(-5.0, s * 4.6, zz), (4.5, s * 4.6, zz), (1.5, s * 4.6, zz + 8.5), (-3.0, s * 4.6, zz + 8.5),
                (-5.0, s * 6.0, zz), (4.5, s * 6.0, zz), (1.5, s * 6.0, zz + 8.5), (-3.0, s * 6.0, zz + 8.5)],
               [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], R_MAIN)
        b.ball(-0.6, s * 6.3, zz + 6.2, 1.2, R_WHITE)
    el = 0.95                                                                    # the tube points up and forward
    ca, sa = math.cos(el), math.sin(el)
    tubes = [0.0] if lv < 4 else [-2.5, 2.5]
    rr = 3.1 + lv * 0.2 if lv < 4 else 2.7
    Lt = 15.0 + lv * 0.9
    for o in tubes:
        p0 = (-3.2, o, zz + 2.2)
        p1 = (p0[0] + ca * Lt, o, p0[2] + sa * Lt)
        pm = (p0[0] + ca * Lt * 0.45, o, p0[2] + sa * Lt * 0.45)
        b.bar(p0, pm, rr + 0.8, R_DARK, 6)
        b.bar(pm, p1, rr, R_METAL, 6)
        b.bar((p1[0] - ca * 1.6, o, p1[2] - sa * 1.6), (p1[0] + ca * 0.6, o, p1[2] + sa * 0.6), rr + 0.7, R_LITE, 6)
        if lv >= 2:
            b.ball(p1[0] + ca * 0.4, o, p1[2] + sa * 0.4, rr * 0.62, R_WHITE)
    if lv >= 1:
        for s in (-1, 1):                                                        # recoil pistons
            b.bar((4.8, s * 3.2, zz + 0.6), (-3.2 + ca * Lt * 0.5, s * 3.2, zz + 2.2 + sa * Lt * 0.5), 0.75, R_METAL, 4)
        b.box(-6.0, 0, zz, 1.6, 3.6, 3.0, R_DARK)
        b.line([(-7.7, -2.6, zz + 2.2), (-7.7, 2.6, zz + 2.2)], R_LITE, 2)
    if lv >= 3:
        b.line([(3.0, 5.6, zz + 8.5), (3.0, 5.6, zz + 15.5)], R_METAL, 1)
        b.slab([(3.0, 5.6, zz + 15.5), (6.6, 5.6, zz + 14.2), (3.0, 5.6, zz + 12.9)], R_LITE)
        b.glow(-3.2 + ca * Lt, 0, zz + 2.2 + sa * Lt, 8, R_LITE, 0.5)
    if lv >= 4:
        b.ring(0, 0, zz - 0.4, 8.2, R_ALT, 16, 2)
        halo(b, zz + 24, 8.0)


def tm2_cryo(b, lv):
    z = pad2(b, lv, 13)
    # coolant tanks and pipes on the deck
    nt = 2 + (lv >= 2) + (lv >= 3)
    for i in range(nt):
        a = math.pi / 4 + i * TAU / 4
        x, y = math.cos(a) * 9.0, math.sin(a) * 9.0
        lathe(b, x, y, [(2.3, z), (2.3, z + 4.5 + lv * 0.4), (1.2, z + 5.6 + lv * 0.4)], 4, [R_METAL, R_WHITE], a)
        b.line([(x * 0.75, y * 0.75, z + 3.2), (x * 0.3, y * 0.3, z + 6.0)], R_LITE, 2)
    lathe(b, 0, 0, [(5.6, z), (4.4, z + 3.0), (3.0, z + 4.2)], 6, [R_DARK, R_MAIN])
    zz = z + 4.2
    # claw pylons that cradle the crystal
    nc = 3 if lv < 3 else 4
    H = 11.0 + lv * 1.6
    for i in range(nc):
        a = i * TAU / nc + (0.5 if nc == 3 else TAU / 8)
        ca, sa = math.cos(a), math.sin(a)
        b.bar((ca * 4.0, sa * 4.0, zz - 1.0), (ca * 8.2, sa * 8.2, zz + H * 0.55), 1.25, R_METAL, 4)
        b.line([(ca * 8.2, sa * 8.2, zz + H * 0.55), (ca * 4.6, sa * 4.6, zz + H)], R_LITE, 3)
        b.ball(ca * 8.2, sa * 8.2, zz + H * 0.55, 1.2, R_METAL)
        b.ball(ca * 4.6, sa * 4.6, zz + H, 1.0, R_WHITE)
    b.ring(0, 0, zz + 0.4, 10.5 + lv * 0.4, R_LITE, 16, 1)
    b.group(M_SPIN | M_BOB, 0.7, 0, 0, zz + 2.0, 1.8, 1.2)
    cr = 4.2 + lv * 0.55
    b.crystal(0, 0, 0, cr, cr * 2.5, R_LITE, 6)
    b.crystal(0, 0, cr * 0.3, cr * 0.5, cr * 1.9, R_WHITE, 4, TAU / 8)
    b.glow(0, 0, cr * 1.25, cr * 2.6, R_LITE, 0.55)
    if lv >= 2:
        for i in range(3):
            a = i * TAU / 3
            b.crystal(math.cos(a) * (cr + 3.6), math.sin(a) * (cr + 3.6), cr * 0.9 + (i % 2) * 2.0, 1.3 + (lv >= 4) * 0.5, 4.2 + (lv >= 4) * 1.6, R_WHITE, 3)
    if lv >= 4:
        halo(b, zz + H + 9, 8.5)


def tm2_tesla(b, lv):
    z = pad2(b, lv, 13)
    # four grounding posts
    for i in range(4):
        a = TAU / 8 + i * TAU / 4
        x, y = math.cos(a) * 9.6, math.sin(a) * 9.6
        b.line([(x, y, z - 1.0), (x, y, z + 6.0 + lv * 1.5)], R_METAL, 3)
        b.ball(x, y, z + 6.9 + lv * 1.5, 1.4, R_LITE if lv >= 2 else R_WHITE)
    # the coil: fat insulator discs with glowing necks between them
    zo = 30.0 + 5.0 * lv                    # where the ball of lightning sits: the game starts its arcs here
    nd = (3, 3, 4, 4, 5)[lv]
    dz = (zo - 7.4 - z) / nd
    zz = z
    for i in range(nd):
        k = 1.0 - 0.42 * i / max(1, nd - 1)
        b.prism(6, 0, 0, zz, 6.6 * k, 1.9, R_MAIN, rtop=5.4 * k)
        b.prism(6, 0, 0, zz + 1.9, 2.6 * k + 0.8, dz - 1.9, R_LITE if i % 2 == 0 else R_DARK, rot=TAU / 12)
        zz += dz
    # the toroid and the ball of lightning
    lathe(b, 0, 0, [(3.0, zz), (7.2, zz + 1.2), (7.2, zz + 3.0), (3.0, zz + 4.2)], 6, [R_METAL, R_WHITE if lv >= 3 else R_METAL, R_METAL])
    b.ball(0, 0, zo, 3.0 + lv * 0.25, R_WHITE)
    b.glow(0, 0, zo, 9 + lv * 1.5, R_LITE, 0.7)
    # frozen arcs
    for i in range(1 + lv // 2):
        a = TAU / 8 + i * TAU / 4 * 2
        x, y = math.cos(a) * 9.6, math.sin(a) * 9.6
        b.line([(x, y, z + 7.5 + lv * 1.5), (x * 0.72, y * 0.72 + 1.2, (z + zo) * 0.5 + 1), (x * 0.38 - 1.0, y * 0.38, zo - 4.5), (0.6, 0.4, zo - 2.0)], R_WHITE, 1)
    if lv >= 3:
        b.group(M_SPIN, 1.6, 0, 0, zo)
        for i in range(3):
            a = i * TAU / 3
            b.ball(math.cos(a) * 7.0, math.sin(a) * 7.0, 0, 1.0, R_WHITE)
        b.ring(0, 0, 0, 7.0, R_LITE, 16, 1)
    if lv >= 4:
        halo(b, zo + 8, 7.5)


def tm2_guardian(b, lv):
    """a knight that stands ON the road"""
    b.group(M_AIM)
    k = 1.0 + lv * 0.045
    def P(x, y, zv):
        return (x * k, y * k, zv * k)
    for s in (-1, 1):                                                            # legs
        b.box(0.8 * k, s * 2.9 * k, 0, 2.6 * k, 1.9 * k, 1.5 * k, R_BLACK)                  # foot
        b.box(-0.2 * k, s * 2.9 * k, 1.5 * k, 1.7 * k, 1.6 * k, 4.6 * k, R_METAL, 0.85)      # shin
        b.box(0.2 * k, s * 2.9 * k, 6.1 * k, 2.0 * k, 1.8 * k, 3.4 * k, R_DARK, 1.1)         # thigh
        b.box(1.6 * k, s * 2.9 * k, 5.4 * k, 0.8 * k, 1.5 * k, 1.6 * k, R_MAIN)              # knee plate
    b.box(0, 0, 9.3 * k, 2.6 * k, 4.4 * k, 2.0 * k, R_DARK, 0.9)                             # hips
    hull(b, -2.8 * k, 3.2 * k, 3.6 * k, 11.3 * k, 6.2 * k, R_MAIN, nose=-0.4 * k, tail=-0.2 * k, topw=5.2 * k)   # chest
    b.line([P(3.5, -2.6, 15.6), P(3.5, 2.6, 15.6)], R_LITE, 2)
    b.ball(3.4 * k, 0, 13.4 * k, 1.1 * k, R_WHITE)                                           # heart light
    for s in (-1, 1):                                                            # shoulders
        b.prism(6, 0, s * 6.6 * k, 15.4 * k, 2.6 * k, 2.6 * k, R_MAIN if lv < 3 else R_METAL, rtop=1.6 * k)
        if lv >= 2:
            b.prism(4, 0, s * 6.9 * k, 18.0 * k, 0.9 * k, 2.6 * k, R_LITE, rtop=0)
    b.box(0.4 * k, 0, 17.5 * k, 1.9 * k, 1.8 * k, 3.3 * k, R_METAL, 0.85)                    # head
    b.slab([P(2.35, -1.3, 19.0), P(2.35, 1.3, 19.0), P(2.35, 1.6, 19.9), P(2.35, -1.6, 19.9)], R_WHITE)    # visor
    if lv >= 1:
        b.slab([P(-1.2, 0, 20.8), P(1.8, 0, 20.8), P(-0.2, 0, 23.6 + lv * 0.5), P(-2.6, 0, 22.4)], R_LITE)    # crest
    # shield arm (left) - a tall tower shield held forward
    sw, sh = 4.3 + lv * 0.25, 12.5 + lv * 0.5
    sx, sy = 5.6, -6.9
    b.bar(P(0, -6.6, 14.6), P(4.6, -6.9, 11.0), 1.3 * k, R_DARK, 4)
    b.mesh([P(sx, sy - sw, 4.5), P(sx, sy + sw, 4.5), P(sx, sy + sw, 4.5 + sh * 0.72), P(sx, sy, 4.5 + sh), P(sx, sy - sw, 4.5 + sh * 0.72),
            P(sx + 1.1, sy - sw + 0.6, 5.2), P(sx + 1.1, sy + sw - 0.6, 5.2), P(sx + 1.1, sy + sw - 0.6, 4.2 + sh * 0.7), P(sx + 1.1, sy, 3.8 + sh), P(sx + 1.1, sy - sw + 0.6, 4.2 + sh * 0.7)],
           [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (0, 1, 6, 5), (1, 2, 7, 6), (2, 3, 8, 7), (3, 4, 9, 8), (4, 0, 5, 9)], [R_DARK, R_MAIN, R_METAL, R_METAL, R_METAL, R_METAL, R_METAL])
    b.line([P(sx + 1.25, sy, 6.4), P(sx + 1.25, sy, 3.2 + sh)], R_LITE, 2)
    b.line([P(sx + 1.25, sy - sw + 1.4, 4.4 + sh * 0.5), P(sx + 1.25, sy + sw - 1.4, 4.4 + sh * 0.5)], R_LITE, 2)
    # sword arm (right)
    b.bar(P(0, 6.6, 14.6), P(4.0, 7.2, 10.6), 1.3 * k, R_DARK, 4)
    b.bar(P(3.4, 7.2, 10.2), P(6.2, 7.2, 11.2), 0.8 * k, R_METAL, 4)
    Ls = 12.0 + lv * 1.2
    b.slab([P(6.0, 7.2, 10.2), P(6.0 + Ls, 7.2, 11.0 + Ls * 0.28), P(6.0 + Ls - 3.4, 7.2, 13.3 + Ls * 0.28), P(6.4, 7.2, 12.4)], R_LITE)
    b.slab([P(5.6, 5.4, 10.8), P(6.8, 5.4, 11.3), P(6.8, 9.0, 11.3), P(5.6, 9.0, 10.8)], R_METAL)
    if lv >= 3:
        b.slab([P(-3.0, -3.4, 17.0), P(-3.0, 3.4, 17.0), P(-6.5, 4.6, 4.0), P(-6.5, -4.6, 4.0)], R_MAIN)      # cape
        b.glow((6.0 + Ls) * k, 7.2 * k, (11 + Ls * 0.28) * k, 6, R_LITE, 0.5)
    if lv >= 4:
        b.line([P(-3.05, -3.4, 16.9), P(-6.55, -4.6, 4.0), P(-6.55, 4.6, 4.0), P(-3.05, 3.4, 16.9)], R_ALT, 2)
        b.ring(0, 0, 0.6, 9.5 * k, R_ALT, 16, 2)
        b.group(M_SPIN | M_BOB, 0.9, 0, 0, 27.5 * k, 1.6, 0.6)
        b.ring(0, 0, 0, 4.2, R_ALT, 12, 2)


TOWERS2 = {"blaster": tm2_blaster, "rail": tm2_rail, "mortar": tm2_mortar, "cryo": tm2_cryo, "tesla": tm2_tesla, "guardian": tm2_guardian}


def _mk2_themes():
    # NEON BASTION mk II - the map theme kits: what towers and enemies are MADE of on each map, and how they are dressed.
    #   THEMES2[key]                        key = a key of nb.THEMES (one per map, all 21), in the order the maps come in the game
    #   dress_base(b, th, R, lv)            called by pad2() once the plinth is built (R = its radius, lv = tower level 0..4)
    #   dress_enemy(b, th, top, hx, hr, r)  called after an enemy is built (top / hx / hr = its head anchor, r = its radius)
    # A theme REMAPS three material roles for everything built on that map (see class TB): R_METAL, R_DARK, R_BLACK.
    # The tower's own colour (R_MAIN / R_LITE) and its shape never change, so a Blaster is still a Blaster.
    #
    # Things worth knowing when this is merged into the game:
    # - dress_base() leaves the builder in the group it found it in, even when a theme has a moving bit (at most ONE animated
    #   group per theme: VOID, CORRUPTED, ABYSS, FACTORY, KITCHEN, GLITCH).  It does that by putting b.parts back (_resume), so the
    #   tower's own parts land in exactly the same groups as without a theme.  Moving bits are hinged at the rim, where they are,
    #   so the renderer sorts them against the tower properly.
    # - It reads the number of sides of the plinth off the builder (_sides: the Prism stands on a hexagon), so tiles and stripes
    #   sit flat on the wall of any plinth, and everything is placed relative to R, so the Annihilator's big plinth works too.
    # - Cost: balls, lines and glows are NOT free in the software renderer (each costs about as much as one visible face, a
    #   16-point ring as much as four), so the kits keep those down as well: at most ~48 faces and ~37 other parts on a tower,
    #   ~20 faces on an enemy, and swarmers / minis (r <= 7) get a cut-down hat of under 10 faces.

    TAU = math.pi * 2
    R_DARK, R_MAIN, R_LITE, R_METAL, R_WHITE, R_ALT, R_BLACK = 0, 1, 2, 3, 4, 5, 6
    M_AIM, M_SPIN, M_BOB, M_RECOIL = 1, 2, 4, 8

    SNOW = (236, 244, 255)
    ICE = (150, 215, 255)
    THEMES2 = {
        "GRID": dict(name="FIRST LIGHT", metal=(104, 114, 150), dark=(32, 44, 72), black=(16, 18, 34), ground=(16, 22, 52), sub="standard issue, data pylons, holo markers"),
        "FROST": dict(name="FROSTBITE PASS", metal=(188, 214, 236), dark=(48, 70, 104), black=(28, 40, 64), ground=(40, 58, 92), sub="snow caps, ice shards, frosted steel"),
        "VOID": dict(name="EVENT HORIZON", metal=(134, 112, 196), dark=(34, 22, 62), black=(15, 10, 32), ground=(26, 18, 58), sub="obsidian and runes, floating rune stones, star glints"),
        "CITY": dict(name="NEON CITY", metal=(206, 212, 230), dark=(30, 30, 52), black=(16, 16, 30), ground=(30, 30, 54), sub="chrome, neon piping, neon signs"),
        "DUNES": dict(name="DUNE RUNNER", metal=(186, 124, 58), dark=(150, 112, 70), black=(112, 82, 50), ground=(96, 68, 44), sub="sandstone decks, bronze, desert cloth"),
        "INFERNO": dict(name="CROSSFIRE", metal=(92, 74, 78), dark=(44, 26, 26), black=(26, 14, 14), ground=(60, 24, 16), sub="basalt, black iron, lava in the cracks"),
        "FOREST": dict(name="HOLO GROVE", metal=(120, 138, 92), dark=(78, 54, 36), black=(50, 34, 24), ground=(18, 54, 42), sub="bark and moss, vines, glowing mushrooms"),
        "ABYSS": dict(name="TIDEWATER", metal=(198, 158, 74), dark=(20, 62, 80), black=(12, 40, 56), ground=(14, 44, 70), sub="brass and coral, barnacles, bubbles"),
        "CRYSTAL": dict(name="CRYSTAL CAVERN", metal=(170, 150, 210), dark=(58, 34, 92), black=(36, 20, 60), ground=(40, 26, 70), sub="amethyst decks, crystals growing, out of everything"),
        "SKY": dict(name="SKY BRIDGE", metal=(236, 192, 86), dark=(206, 214, 234), black=(146, 164, 206), ground=(62, 94, 156), sub="white marble and gold, cloud puffs, little wings"),
        "FACTORY": dict(name="THE FOUNDRY", metal=(172, 92, 48), dark=(64, 56, 56), black=(38, 31, 31), ground=(52, 40, 34), sub="rusty iron, rivets and pipes, a smoking stack"),
        "SUNSET": dict(name="SUNSET STRIP", metal=(228, 230, 246), dark=(150, 34, 124), black=(62, 18, 86), ground=(74, 26, 96), sub="hot pink and chrome, palm trees, a neon sun"),
        "BOARD": dict(name="MOTHERBOARD", metal=(202, 208, 216), dark=(20, 96, 60), black=(10, 60, 38), ground=(10, 50, 30), sub="PCB green, gold traces, chips and capacitors"),
        "CORRUPTED": dict(name="CORRUPTED CORE", metal=(86, 130, 112), dark=(12, 46, 37), black=(6, 25, 20), ground=(10, 38, 30), sub="bad sectors, glitch cubes, broken data"),
        "HALLOWEEN": dict(name="HAUNTED HOLLOW", metal=(212, 206, 186), dark=(58, 34, 84), black=(32, 18, 48), ground=(40, 26, 56), sub="bone and witch purple, pumpkins, candles"),
        "XMAS": dict(name="WINTER WORKS", metal=(208, 50, 62), dark=(24, 86, 58), black=(14, 54, 40), ground=(56, 76, 110), sub="red and pine green, fairy lights, candy canes"),
        "POND": dict(name="DUCK POND", metal=(190, 162, 104), dark=(42, 112, 78), black=(24, 78, 108), ground=(28, 86, 74), sub="bamboo and pond green, lily pads, ducklings"),
        "KITCHEN": dict(name="THE KITCHEN", metal=(210, 214, 224), dark=(148, 98, 60), black=(30, 30, 38), ground=(74, 66, 66), sub="steel and butcher block, checkered tiles, cutlery"),
        "GLITCH": dict(name="404", metal=(240, 20, 240), dark=(24, 24, 34), black=(5, 5, 10), ground=(34, 8, 44), sub="missing textures, error bars, texture_not_found"),
        "MARKET": dict(name="STONK MARKET", metal=(224, 186, 80), dark=(30, 38, 58), black=(12, 17, 28), ground=(12, 36, 26), sub="pinstripe and gold, candle charts, coin stacks"),
        "QUARRY": dict(name="THE QUARRY", metal=(240, 190, 48), dark=(120, 106, 94), black=(78, 68, 60), ground=(74, 64, 56), sub="cut stone, digger yellow, cones and pickaxes"),
    }


    # ---------------------------------------------------------------------- helpers
    def _sides(b, R):
        """how many sides the plinth has.  pad2() turns the plinth before it calls dress_base, so it is the first solid
        in the builder; most plinths are octagons, the Prism stands on a hexagon.  8 if we cannot tell."""
        try:
            for p in b.m.groups[0][7]:
                if p[1] == 0:
                    n = sum(1 for v in p[2] if abs(v[2]) < 0.01 and abs(math.hypot(v[0], v[1]) - R) < 0.05)
                    return n if 5 <= n <= 12 else 8
        except Exception:
            pass
        return 8


    def _wr(R, a, n=8):
        """how far out the plinth wall is in direction a (an n-gon with a flat facing +x)"""
        d = (a + math.pi / n) % (TAU / n) - math.pi / n
        return R * math.cos(math.pi / n) / math.cos(d)


    def _wall(R, a, n=8, off=0.12):
        """-> f(u, z): a point on the flat of the plinth wall that faces direction a (u = sideways along the wall)"""
        ra = R * math.cos(math.pi / n) + off
        ca, sa = math.cos(a), math.sin(a)
        return lambda u, z: (ca * ra - sa * u, sa * ra + ca * u, z)


    def _plane(x, y, a):
        """-> f(u, z): a point on an upright plane through (x, y) whose sideways direction is a"""
        ca, sa = math.cos(a), math.sin(a)
        return lambda u, z: (x + ca * u, y + sa * u, z)


    def _checks(b, P, u0, u1, z0, z1, n, role):
        """n x 2 checkerboard tiles drawn as ONE flat shape (the tiles touch at their corners), 2 faces"""
        zm, du = (z0 + z1) * 0.5, (u1 - u0) / float(n)
        pts = [P(u0, zm)]
        for i in range(n):
            ua, ub = u0 + i * du, u0 + (i + 1) * du
            zz = z0 if i % 2 == 0 else z1
            pts += [P(ua, zz), P(ub, zz), P(ub, zm)]
        b.slab(pts, role, False)


    def _zebra(b, P, u0, u1, z0, z1, n, role, lean=0.9, fill=0.5):
        """n slanted warning stripes drawn as ONE flat shape, 2 faces"""
        du = (u1 - u0) / float(n)
        pts = []
        for i in range(n):
            ua = u0 + i * du
            pts += [P(ua, z0), P(ua + lean, z1), P(ua + lean + du * fill, z1), P(ua + du * fill, z0)]
        b.slab(pts, role, False)


    def _mtex(b, x, y, z, s, rot, c1, c2):
        """a missing-texture cube (edge 2s): two half-height blocks whose sides swap colours, 10 faces"""
        b.box(x, y, z, s, s, s, [c2, c1, c2, c1, c2], 1.0, rot)
        b.box(x, y, z + s, s, s, s, [c1, c2, c1, c2, c1], 1.0, rot)


    def _tube(b, x, y, z0, z1, r, n, role, rot=0.0):
        """n upright faces and no lids: for things that are stacked on each other"""
        vs = [(x + math.cos(rot + i * TAU / n) * r, y + math.sin(rot + i * TAU / n) * r, zz) for zz in (z0, z1) for i in range(n)]
        b.mesh(vs, [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)], role)


    def _disc(b, x, y, z, r, n, role, rot=0.0):
        """a flat n-sided plate (hat brims, lily pads), 2 faces"""
        b.slab([(x + math.cos(rot + i * TAU / n) * r, y + math.sin(rot + i * TAU / n) * r, z) for i in range(n)], role)


    def _resume(b, parts):
        """go back to the group that was being built before the floating bits got groups of their own.
        The plinth and whatever the tower puts on it afterwards stay ONE static group, so they still sort as one."""
        if parts is not None:
            b.parts = parts
        else:
            b.group()


    # ---------------------------------------------------------------------- towers
    def dress_base(b, th, R, lv):
        """the plinth of a tower, dressed for the map.  Budget: about 45 faces (balls, lines, rings and glows are free)."""
        n = _sides(b, R)
        hw = R * math.sin(math.pi / n)      # half the width of one flat of the wall
        FL = TAU / n                        # the flats face 0, FL, 2 FL ...

        def at(a, r):
            return math.cos(a) * r, math.sin(a) * r

        def wr(a):
            return _wr(R, a, n)

        def rim(a, d=1.1):          # on the sloping rim of the plinth (its surface is at z = 3.0 there)
            return at(a, wr(a) - d)

        def gnd(a, d=1.4):          # on the ground just outside the plinth
            return at(a, wr(a) + d)

        def wall(a, off=0.12):      # the flat of the wall nearest to direction a
            return _wall(R, round(a / FL) * FL, n, off)

        def band(z, off, role, width=2):    # a stripe that follows the wall all the way round, `off` away from it (two flats to a line)
            rv = R + off / math.cos(math.pi / n)
            for j in range(0, n, 2):
                b.line([at(FL / 2 + (j + i - 1) * FL, rv) + (z,) for i in range(min(3, n - j + 1))], role, width)
        parts0 = getattr(b, "parts", None)
        if th == "GRID":
            for a, h in ((0.3, 6.0), (3.45, 8.0)):              # two slim data pylons
                x, y = gnd(a, 1.3)
                b.prism(4, x, y, 0, 1.3, h, R_METAL, rtop=0.75, rot=a)
                b.ring(x, y, h * 0.74, 1.35, R_LITE, 6, 1)
                b.line([(x, y, h), (x, y, h + 2.0)], R_METAL, 1)
                b.ball(x, y, h + 2.3, 0.85, R_LITE)
                b.glow(x, y, h + 2.3, 4.5, R_LITE, 0.5)
            x, y = rim(1.3)                                     # a holo marker
            b.prism(6, x, y, 3.0, 1.5, 0.7, R_METAL, rtop=1.1)
            b.ring(x, y, 4.6, 1.7, R_LITE, 8, 1)
            b.crystal(x, y, 4.9, 1.1, 2.8, R_LITE, 4)
            b.glow(x, y, 6.3, 5, R_LITE, 0.45)
            for a in (5.95, 1.75, 2.0, 2.75):                   # data traces in the floor
                w = wr(a)
                x0, y0 = at(a, w + 0.15)
                x1, y1 = at(a, w + 1.2)
                x2, y2 = at(a + 0.1, w + 2.0)
                b.line([(x0, y0, 0.12), (x1, y1, 0.12), (x2, y2, 0.12)], R_LITE, 1)
                b.ball(x2, y2, 0.2, 0.4, R_WHITE)
        elif th == "FROST":
            for i in range(4):                                  # snow on the clamps
                a = TAU / 8 + i * TAU / 4
                x, y = at(a, R - 1.2)
                b.box(x, y, 4.3, 2.6, 1.8, 1.3, SNOW, 0.55, a, False)
            for a, h in ((0.5, 7.0), (2.3, 5.0), (3.6, 8.5), (5.3, 4.5)):
                x, y = at(a, R - 0.6)
                b.crystal(x, y, 1.0, 1.6, h, ICE, 3, a, 0.3)
            x, y = at(1.3, R - 2.0)                             # a drift
            b.ball(x, y, 2.9, 2.5, SNOW)
            b.ball(x + 1.7, y - 1.5, 2.7, 1.8, SNOW)
        elif th == "VOID":
            RUNE, OBS = (196, 124, 255), (58, 40, 104)
            k = hw / 5.5
            for a in (0.0, TAU / 4, TAU / 2):                   # runes cut into the wall
                P = wall(a)
                b.line([P(-3.6 * k, 0.4), P(-3.6 * k, 1.9), P(-2.4 * k, 1.5), P(-3.6 * k, 1.1), P(-2.4 * k, 0.4)], RUNE, 2)
                b.line([P(-0.8 * k, 1.9), P(0.8 * k, 0.4), P(0, 1.15), P(0.8 * k, 1.9), P(-0.8 * k, 0.4)], RUNE, 2)
                b.line([P(2.4 * k, 0.4), P(3.0 * k, 1.9), P(3.6 * k, 0.4)], RUNE, 2)
            b.ring(0, 0, 0.15, R + 1.5, RUNE, 16, 1)            # a summoning circle
            for a, zz in ((0.9, 9.0), (2.0, 12.5), (3.9, 10.5), (5.3, 6.5)):     # star glints
                x, y = at(a, R - 0.2)
                b.line([(x, y, zz - 0.9), (x, y, zz + 0.9), (x, y, zz), (x - 0.6, y, zz), (x + 0.6, y, zz), (x, y, zz), (x, y - 0.6, zz), (x, y + 0.6, zz)], R_WHITE, 1)
            b.glow(0, 0, 1.0, R + 6, RUNE, 0.25)
            for a, k, spin in ((3.3, 1.05, False), (0.12, 1.25, True)):       # rune stones floating over the rim, each with two shards;
                x, y = rim(a, 0.3)                                              # the big one turns slowly (the only moving part)
                zz = 8.2 if spin else 7.4
                if spin:
                    b.group(M_SPIN | M_BOB, 0.9, x, y, zz, 1.4, 0.6)
                    x, y, zz = 0.0, 0.0, 0.0
                b.prism(4, x, y, zz - 1.9 * k, 1.3 * k, 3.8 * k, OBS, rtop=0.8 * k, rot=a)
                for s in (-1, 1):
                    b.line([(x + s * 1.15 * k, y - 0.45 * k, zz - 1.0 * k), (x + s * 1.05 * k, y + 0.4 * k, zz - 0.1 * k), (x + s * 0.98 * k, y - 0.4 * k, zz + 0.9 * k)], RUNE, 2)
                    b.crystal(x + s * 2.1 * k, y, zz - 0.7 * k + s * 0.5, 0.55 * k, 1.9 * k, RUNE, 3, s)
                b.glow(x, y, zz, 4.5 * k, RUNE, 0.4)
            _resume(b, parts0)
        elif th == "CORRUPTED":
            G1, G2, GD = (80, 255, 165), (24, 160, 104), (12, 62, 48)
            for a, k in ((0.2, 1.0), (3.35, 0.8)):              # stacks of glitch cubes, each one knocked out of line
                x, y = gnd(a, 1.5 * k)
                tx, ty = -math.sin(a) * k, math.cos(a) * k
                b.box(x, y, 0, 1.45 * k, 1.45 * k, 2.6 * k, GD, 1.0, a)
                b.box(x + tx * 0.8, y + ty * 0.8, 2.6 * k, 1.15 * k, 1.15 * k, 2.2 * k, G2, 1.0, a + 0.5)
                b.line([(x - tx * 2.6, y - ty * 2.6, 1.3 * k), (x + tx * 2.9, y + ty * 2.9, 1.3 * k)], G1, 2)
            for a, h in ((5.9, 6.0), (1.05, 8.0), (2.85, 7.0), (3.75, 5.0)):   # corrupted data streaming upwards
                x, y = at(a, R + 0.3)
                b.line([(x, y, 0.2), (x, y, h * 0.5)], G1, 2)
                b.line([(x, y, h * 0.68), (x, y, h)], G1, 2)
            for a0, a1, zz, dr in ((5.75, 6.2, 0.8, 0.5), (0.5, 1.0, 1.5, 0.9), (1.7, 2.2, 0.6, 0.7), (2.5, 3.0, 1.7, 0.5)):   # torn scan lines
                x0, y0 = at(a0, R + dr)
                x1, y1 = at(a1, R + dr)
                b.line([(x0, y0, zz), (x1, y1, zz)], G1, 1)
            b.glow(0, 0, 1.0, R + 6, G1, 0.2)
            x, y = at(3.6, R + 0.2)                             # broken blocks hovering: one stuck in mid-air ...
            b.box(x, y, 5.6, 0.85, 0.85, 1.45, G1, 1.0, 4.5)
            b.line([(x - 1.5, y + 0.3, 6.4), (x + 1.7, y + 0.3, 6.4)], G1, 1)
            px, py = at(0.85, R + 0.2)                          # ... and two that bob (one group, hinged between them)
            b.group(M_BOB, 0, px, py, 6.0, 1.9, 0.7)
            for a, zz, k in ((0.45, 0.6, 1.0), (1.25, -0.8, 1.2)):
                x, y = at(a, R + 0.2)
                b.box(x - px, y - py, zz - 0.8 * k, 0.95 * k, 0.95 * k, 1.6 * k, G1 if k < 1.1 else G2, 1.0, a + k)
                b.line([(x - px - 1.6 * k, y - py + 0.3, zz), (x - px + 1.9 * k, y - py + 0.3, zz)], G1, 1)
            _resume(b, parts0)
        elif th == "DUNES":
            for a in (0.2, 2.9):                                # sandstone blocks
                x, y = at(a, R - 0.2)
                b.box(x, y, 0, 2.5, 2.2, 3.0, (196, 156, 104), 0.9, a)
                b.box(x, y, 3.0, 1.9, 1.7, 2.2, (176, 136, 88), 0.9, a + 0.4)
            x, y = at(4.4, R - 0.8)                             # a pole with a strip of cloth
            b.bar((x, y, 2.0), (x, y, 15.0), 0.5, (120, 84, 50), 3)
            b.slab([(x, y, 14.6), (x - 5.5, y - 1.5, 13.2), (x - 4.0, y - 0.8, 11.6), (x, y, 10.6)], (214, 74, 48))
            for a in (1.2, 3.7, 5.6):                           # sand blown up against the wall
                x, y = at(a, R + 0.1)
                b.prism(5, x, y, 0, 2.8, 1.2, (214, 176, 118), rtop=1.1, rot=a, edge=False)
        elif th == "INFERNO":
            LAVA = (255, 120, 24)
            for a in (0.3, 1.9, 3.4, 5.0):
                x0, y0 = at(a, R + 0.3)
                x1, y1 = at(a + 0.18, R - 2.6)
                x2, y2 = at(a - 0.1, R - 4.4)
                b.line([(x0, y0, 1.0), (x0, y0, 2.4), (x1, y1, 3.5), (x2, y2, 3.6)], LAVA, 2)
            for a, h in ((1.1, 7.5), (2.6, 5.0), (4.2, 9.0), (5.7, 6.0)):
                x, y = at(a, R + 0.2)
                b.prism(4, x, y, 0, 1.7, h, (58, 36, 34), rtop=0, rot=a)
            b.glow(0, 0, 1.0, R + 7, LAVA, 0.35)
        elif th == "FOREST":
            VINE, LEAF, CAP = (60, 200, 110), (90, 235, 140), (120, 255, 200)
            pts = [(math.cos(i * 0.5) * (R + 0.5), math.sin(i * 0.5) * (R + 0.5), 0.6 + (i % 3) * 0.9) for i in range(13)]
            b.line(pts, VINE, 2)
            for i in (1, 4, 7, 10):
                x, y, zz = pts[i]
                b.slab([(x, y, zz), (x * 1.12, y * 1.12, zz + 2.6), (x * 1.02 + 1.4, y * 1.02 + 1.0, zz + 1.6)], LEAF)
            for a, k in ((0.9, 1.0), (3.9, 0.75), (5.4, 0.6)):
                x, y = at(a, R - 0.4)
                b.bar((x, y, 2.0), (x, y, 2.0 + 4.6 * k), 0.75 * k, (220, 214, 190), 3)
                b.prism(6, x, y, 2.0 + 4.6 * k, 2.6 * k, 1.5 * k, CAP, rtop=0.6 * k)
                b.glow(x, y, 2.0 + 5.2 * k, 5 * k, CAP, 0.5)
        elif th == "ABYSS":
            CORAL, CORAL2 = (255, 120, 130), (255, 170, 90)
            for a, c, k in ((0.4, CORAL, 1.0), (2.5, CORAL2, 0.8), (4.6, CORAL, 0.9)):
                x, y = at(a, R - 0.2)
                b.bar((x, y, 1.0), (x, y, 1.0 + 5.0 * k), 0.85 * k, c, 3)
                for da in (-0.9, 0.9):
                    dx, dy = math.cos(a + da) * 2.6 * k, math.sin(a + da) * 2.6 * k
                    b.bar((x, y, 1.0 + 3.0 * k), (x + dx, y + dy, 1.0 + 7.5 * k), 0.65 * k, c, 3, 0.3 * k)
                b.ball(x, y, 1.0 + 5.3 * k, 0.75 * k, c)
            for a in (1.3, 1.7, 3.5, 5.6):                      # barnacles
                x, y = at(a, R + 0.1)
                b.ball(x, y, 2.0, 0.9, (150, 170, 160))
            b.group(M_BOB, 0, 0, 0, 0, 1.2, 3.0)                # bubbles
            for a, zz in ((0.9, 7), (2.9, 12), (4.9, 9.5), (3.8, 14.5)):
                x, y = at(a, R - 1.0)
                b.ball(x, y, zz, 0.7, SNOW)
            _resume(b, parts0)
        elif th == "CRYSTAL":
            C1, C2 = (255, 120, 235), (190, 130, 255)
            for a, k in ((0.5, 1.0), (2.4, 0.8), (3.9, 1.15), (5.4, 0.7)):
                x, y = at(a, R - 0.3)
                b.crystal(x, y, 0.5, 1.9 * k, 9.5 * k, C1, 3, a, 0.3)
                b.prism(3, x + 1.8 * k, y - 1.2 * k, 0.4, 1.2 * k, 5.5 * k, C2, rtop=0, rot=a + 1)
                b.prism(3, x - 1.4 * k, y + 1.4 * k, 0.4, 1.0 * k, 4.0 * k, C1, rtop=0, rot=a + 2)
            b.glow(0, 0, 2.0, R + 5, C1, 0.25)
        elif th == "CITY":
            PINKN, CYANN, HAZ, POLE = (255, 60, 190), (60, 230, 255), (255, 210, 40), (150, 156, 180)
            for a in (0.0, TAU / 4, TAU / 2, 3 * TAU / 4):      # hazard stripes on the wall
                _zebra(b, wall(a), -0.8 * hw, 0.72 * hw, 0.3, 1.6, 4, HAZ)
            band(3.5, -1.9, PINKN)                              # neon piping: a tube round the deck, one round the foot, risers on the clamps
            band(0.25, 1.4, CYANN)
            for i in range(4):
                a = TAU / 8 + i * TAU / 4
                x0, y0 = at(a, R + 1.25)
                x1, y1 = at(a, R + 0.8)
                x2, y2 = at(a, R - 3.1)
                b.line([(x0, y0, 0.25), (x1, y1, 4.45), (x2, y2, 4.45)], CYANN, 2)
            a = 1.72                                            # the big sign: two posts and a board with neon writing
            x, y = rim(a, 0.7)
            P = _plane(x, y, a + math.pi / 2)
            for u in (-4.2, 4.2):
                b.line([P(u, 3.0), P(u, 9.0)], POLE, 2)
            b.slab([P(-4.6, 9.0), P(4.6, 9.0), P(4.6, 14.4), P(-4.6, 14.4)], (26, 22, 44))
            b.line([P(-4.6, 9.0), P(4.6, 9.0), P(4.6, 14.4), P(-4.6, 14.4)], PINKN, 3, True)
            b.line([P(-3.5, 12.2), P(-2.5, 13.3), P(-1.5, 12.2), P(-0.5, 13.3), P(0.5, 12.2), P(1.5, 13.3), P(2.5, 12.2), P(3.5, 13.3)], CYANN, 2)
            b.line([P(-3.5, 10.4), P(1.5, 10.4)], PINKN, 3)
            b.line([P(2.5, 10.4), P(3.5, 10.4)], HAZ, 3)
            b.glow(x, y, 11.6, 9, PINKN, 0.45)
            x, y = rim(3.25, 0.7)                               # a tall strip sign
            P = _plane(x, y, 3.25 + math.pi / 2)
            b.bar((x, y, 3.0), (x, y, 13.4), 0.4, POLE, 4)
            b.slab([P(0.4, 5.2), P(3.0, 5.2), P(3.0, 13.0), P(0.4, 13.0)], (26, 22, 44))
            b.line([P(0.4, 5.2), P(3.0, 5.2), P(3.0, 13.0), P(0.4, 13.0)], CYANN, 2, True)
            for zz, c in ((11.4, PINKN), (9.7, HAZ), (8.0, PINKN), (6.3, CYANN)):
                b.line([P(1.0, zz), P(2.4, zz)], c, 3)
            b.ball(x, y, 13.9, 0.9, (255, 60, 60))
            b.glow(x, y, 9.5, 7, CYANN, 0.35)
        elif th == "SKY":
            CLOUD, MARB, GOLDC, BLUE = (244, 248, 255), (232, 236, 248), (255, 214, 90), (96, 170, 255)
            for a, k in ((0.02, 1.0), (1.55, 0.85), (3.15, 0.9), (4.4, 0.6)):     # cloud puffs round the foot
                w = wr(a)
                for da, dr, zz, rr in ((0.0, 0.9, 1.7, 2.1), (0.2, 0.6, 1.2, 1.6), (-0.19, 0.7, 1.1, 1.5)):
                    x, y = at(a + da, w + dr * k)
                    b.ball(x, y, zz * k, rr * k, CLOUD)
            for i in range(4):                                  # a pair of little wings on every clamp
                a = TAU / 8 + i * TAU / 4
                x, y = at(a, R - 1.2)
                ox, oy = math.cos(a), math.sin(a)
                for s in (-1, 1):                               # spread along the rim, three feathers each
                    tx, ty = -math.sin(a) * s, math.cos(a) * s
                    b.slab([(x + tx * t + ox * o, y + ty * t + oy * o, zz) for t, o, zz in ((0.8, 1.0, 4.5), (5.0, 1.4, 7.6), (3.9, 0.6, 6.6), (4.4, 0.0, 6.9),
                                                                                           (3.2, -0.4, 5.9), (3.5, -1.1, 6.0), (0.8, -0.9, 4.5))], R_WHITE)
            x, y = rim(1.5, 0.9)                                # a pennant on a golden pole
            b.bar((x, y, 3.0), (x, y, 15.2), 0.42, GOLDC, 4)
            b.ball(x, y, 15.7, 0.8, GOLDC)
            b.slab([(x, y, 15.0), (x + 4.6, y - 2.2, 13.6), (x, y, 12.2)], BLUE)
            x, y = gnd(3.2, 0.7)                                # a marble column
            b.prism(6, x, y, 0, 1.5, 6.4, MARB, rtop=1.25)
            b.prism(6, x, y, 6.4, 1.9, 0.9, GOLDC)
        elif th == "FACTORY":
            RUSTC, SOOT, HAZ, EMB, RIV = (182, 100, 52), (84, 60, 50), (255, 200, 40), (255, 140, 30), (196, 156, 124)
            for i in range(0, n, 2):                            # rivets
                for da in (-0.13, 0.13):
                    x, y = at(FL / 2 + i * FL + da, R + 0.05)
                    b.ball(x, y, 1.75, 0.55, RIV)
            for a in (0.0, TAU / 4, TAU / 2):                   # hazard stripes
                _zebra(b, wall(a), -0.83 * hw, 0.76 * hw, 0.25, 1.35, 5, HAZ)
            x, y = rim(3.5, 1.0)                                # the stack, with something hot inside
            b.prism(6, x, y, 3.0, 2.0, 6.8, SOOT, rtop=1.5)
            b.prism(6, x, y, 9.8, 1.95, 1.2, RUSTC)
            b.ball(x, y, 11.0, 1.25, EMB)
            b.glow(x, y, 11.4, 6.5, EMB, 0.6)
            xa, ya = gnd(1.15, 1.3)                             # a pipe up out of the floor and into the nearest clamp
            xb, yb = at(TAU / 8, R - 1.4)
            b.bar((xa, ya, 0), (xa, ya, 5.6), 0.8, RUSTC, 5)
            b.ball(xa, ya, 5.6, 1.15, RUSTC)
            b.bar((xa, ya, 5.6), (xb, yb, 5.0), 0.8, RUSTC, 5)
            b.bar((xb, yb, 4.3), (xb, yb, 5.6), 1.15, SOOT, 5)
            b.ring(xa, ya, 2.6, 1.3, RIV, 6, 2)
            b.group(M_BOB, 0, x, y, 13.2, 1.3, 0.8)             # smoke
            b.ball(0.3, 0.0, 0.0, 1.35, (128, 118, 116))
            b.ball(-0.6, 0.5, 1.9, 1.0, (156, 148, 146))
            _resume(b, parts0)
        elif th == "SUNSET":
            PINKN, SUN1, SUN2, SUN3, PALM, TRUNK = (255, 70, 190), (255, 222, 80), (255, 150, 70), (255, 84, 150), (40, 226, 170), (150, 74, 112)
            for zz, c in ((0.4, PINKN), (1.0, SUN2), (1.6, SUN1)):       # the wall is striped like the sky
                band(zz, 0.25, c)
            for a, k in ((3.5, 1.0), (0.2, 0.62)):              # palms
                x0, y0 = gnd(a, 1.0)
                x1, y1 = rim(a, 1.4)
                zt = 3.0 + 8.4 * k
                b.bar((x0, y0, 0), (x1, y1, zt), 0.8 * k, TRUNK, 3, 0.5 * k)
                for i in range(5):
                    f = a + 0.4 + i * TAU / 5
                    dx, dy = math.cos(f) * k, math.sin(f) * k
                    sx, sy = -dy * 0.8, dx * 0.8
                    b.slab([(x1, y1, zt - 0.1), (x1 + dx * 2.0 + sx, y1 + dy * 2.0 + sy, zt + 1.3 * k), (x1 + dx * 4.2, y1 + dy * 4.2, zt - 1.1 * k),
                            (x1 + dx * 2.0 - sx, y1 + dy * 2.0 - sy, zt + 0.9 * k)], PALM)
                b.ball(x1 + 0.5 * k, y1 - 0.4 * k, zt - 0.7 * k, 0.65 * k, SUN2)
            a = 1.75                                            # the neon sun: sliced, like on every album cover
            x, y = rim(a, 0.6)
            P = _plane(x, y, a + math.pi / 2)
            rs, zb = 4.2, 8.2

            def sw(h):
                return math.sqrt(max(0.0, rs * rs - h * h))
            for u in (-3.0, 3.0):
                b.line([P(u, 3.0), P(u, zb)], R_METAL, 2)
            b.line([P(-5.0, zb - 0.5), P(5.0, zb - 0.5)], PINKN, 2)
            for h0, h1, c in ((0.0, 0.6, SUN3), (1.05, 1.75, SUN3), (2.1, 2.9, SUN2)):
                b.slab([P(-sw(h0), zb + h0), P(sw(h0), zb + h0), P(sw(h1), zb + h1), P(-sw(h1), zb + h1)], c)
            b.slab([P(-sw(3.15), zb + 3.15), P(sw(3.15), zb + 3.15), P(sw(3.75), zb + 3.75), P(0.9, zb + 4.12), P(0, zb + 4.2),
                    P(-0.9, zb + 4.12), P(-sw(3.75), zb + 3.75)], SUN1)
            b.glow(x, y, zb + 2.0, 10, SUN3, 0.5)
        elif th == "BOARD":
            TRACE, CHIP, SOLD, CAPB = (255, 206, 70), (24, 26, 32), (220, 226, 234), (58, 112, 255)
            for a0 in (5.85, 1.25, 2.85):                       # gold traces off the deck, down the wall and away, three to a bus
                for j in range(3):
                    a = a0 + j * 0.17
                    w = wr(a)
                    xa, ya = at(a, w - 2.0)
                    xb, yb = at(a, w + 0.12)
                    xc, yc = at(a, w + 1.0 + j * 0.3)
                    xd, yd = at(a + 0.1, w + 1.5 + j * 0.3)
                    b.line([(xa, ya, 3.5), (xb, yb, 2.3), (xb, yb, 0.15), (xc, yc, 0.15), (xd, yd, 0.15)], TRACE, 2)
                    if j != 1:
                        b.ball(xd, yd, 0.35, 0.6, SOLD)
            for i in range(0, n, 2):                            # solder balls
                x, y = at(FL / 2 + i * FL, R + 0.1)
                b.ball(x, y, 2.3, 0.7, SOLD)
            for a, k in ((0.3, 0.9), (3.35, 1.05), (4.45, 0.8)):   # chips
                x, y = gnd(a, 0.3 + 1.25 * k)
                b.box(x, y, 0.3, 1.2 * k, 1.9 * k, 1.2, CHIP, 0.92, a)
                for s in (-1, 1):                               # its legs: one comb down each side
                    ex, ey = math.cos(a) * s * 1.65 * k, math.sin(a) * s * 1.65 * k
                    pts = []
                    for j in (-1, 0, 1):
                        px, py = x - math.sin(a) * j * 1.2 * k, y + math.cos(a) * j * 1.2 * k
                        leg = [(px + ex * 0.6, py + ey * 0.6, 1.0), (px + ex, py + ey, 0.1)]
                        pts += leg if j != 0 else leg[::-1]
                    b.line(pts, SOLD, 1)
            for a, k, c in ((1.02, 1.0, CAPB), (1.9, 0.75, CHIP), (3.05, 0.85, CAPB)):     # capacitors
                x, y = rim(a, 1.0)
                b.prism(6, x, y, 3.0, 1.35 * k, 4.4 * k, c)
                b.ring(x, y, 3.0 + 4.4 * k + 0.05, 1.0 * k, SOLD, 6, 2)
                b.line([(x - 0.7 * k, y, 3.05 + 4.4 * k), (x + 0.7 * k, y, 3.05 + 4.4 * k)], SOLD, 2)
        elif th == "HALLOWEEN":
            PUMP, FLAME = (255, 128, 22), (255, 214, 90)
            for a, k in ((0.7, 1.0), (4.4, 0.7)):
                x, y = at(a, R - 0.2)
                b.ball(x, y, 2.2 + 2.4 * k, 2.8 * k, PUMP)
                b.bar((x, y, 2.2 + 4.8 * k), (x + 0.5, y, 2.2 + 6.4 * k), 0.55 * k, (60, 140, 60), 3)
                b.ball(x + math.cos(a + 2.6) * 2.3 * k, y + math.sin(a + 2.6) * 2.3 * k, 2.4 + 2.6 * k, 0.75 * k, FLAME)
                b.glow(x, y, 2.2 + 2.4 * k, 7 * k, PUMP, 0.5)
            for a in (2.4, 3.2, 5.6):
                x, y = at(a, R - 0.6)
                b.bar((x, y, 2.2), (x, y, 5.6), 0.6, (236, 230, 210), 4)
                b.crystal(x, y, 5.6, 0.65, 2.0, FLAME, 3, 0, 0.35)
                b.glow(x, y, 6.6, 3.5, FLAME, 0.6)
        elif th == "XMAS":
            RED, GRN, YEL, BLU = (236, 48, 66), (70, 214, 100), (255, 214, 70), (96, 156, 255)
            for i in range(4):                                  # snow on the clamps
                a = TAU / 8 + i * TAU / 4
                x, y = at(a, R - 1.2)
                b.box(x, y, 4.3, 2.3, 1.6, 1.1, SNOW, 0.55, a, False)
            band(2.05, 0.4, (30, 96, 64), 1)                    # fairy lights: a wire and a bulb every so often
            for i in range(11):
                a = -math.pi / 2 + 0.8 + i * (TAU - 1.6) / 10.0
                x, y = at(a, wr(a) + 0.55)
                c = (RED, YEL, GRN, BLU)[i % 4]
                b.ball(x, y, 1.5 + (i % 2) * 0.3, 0.85, c)
                if i % 3 == 0:
                    b.glow(x, y, 1.6, 3.0, c, 0.45)
            a = 1.15                                            # a candy cane
            x, y = gnd(a, 1.2)
            for j in range(3):
                _tube(b, x, y, j * 2.9, (j + 1) * 2.9, 0.82, 4, RED if j % 2 == 0 else SNOW, a)
            tx, ty = math.cos(a + math.pi), math.sin(a + math.pi)
            b.bar((x, y, 8.6), (x + tx * 1.5, y + ty * 1.5, 10.6), 0.74, SNOW, 3)
            b.bar((x + tx * 1.5, y + ty * 1.5, 10.6), (x + tx * 3.3, y + ty * 3.3, 9.2), 0.74, RED, 3)
            b.ball(x + tx * 1.5, y + ty * 1.5, 10.6, 0.8, SNOW)
            x, y = gnd(0.1, 1.5)                                # a present
            b.box(x, y, 0, 1.4, 1.4, 2.5, GRN, 1.0, 0.5)
            ca, sa = math.cos(0.5) * 1.45, math.sin(0.5) * 1.45
            b.line([(x - ca, y - sa, 0.1), (x - ca, y - sa, 2.55), (x + ca, y + sa, 2.55), (x + ca, y + sa, 0.1)], RED, 3)
            b.line([(x + sa, y - ca, 0.1), (x + sa, y - ca, 2.55), (x - sa, y + ca, 2.55), (x - sa, y + ca, 0.1)], RED, 3)
            b.ball(x - 0.5, y, 3.1, 0.7, RED)
            b.ball(x + 0.5, y, 3.1, 0.7, RED)
        elif th == "POND":
            PAD, REED, CAT, DUCK, BEAK, LILY = (86, 206, 104), (150, 214, 96), (122, 76, 44), (255, 214, 40), (255, 140, 30), (255, 150, 206)

            def pad(x, y, rr, rot):                             # a lily pad: a disc with a bite out of it
                b.slab([(x + math.cos(rot + i * TAU / 9) * rr, y + math.sin(rot + i * TAU / 9) * rr, 0.15) for i in range(1, 9)] + [(x, y, 0.15)], PAD)
            for a, d, rr in ((4.95, 1.6, 1.6), (4.35, 1.4, 1.2), (6.05, 1.4, 1.3), (0.3, 1.6, 1.5), (2.85, 1.6, 1.5)):
                x, y = gnd(a, d)
                pad(x, y, rr, a + 2.0)
            x, y = gnd(4.95, 1.6)
            b.ball(x + 0.3, y + 0.2, 0.7, 0.85, LILY)
            b.ball(x + 0.3, y + 0.2, 1.1, 0.45, (255, 240, 170))
            for a0, hs in ((1.22, (12.5, 9.5, 14.5)), (3.42, (11.0, 13.5))):      # cattails
                for j, h in enumerate(hs):
                    a = a0 + j * 0.16
                    x, y = gnd(a, 0.9 + (j % 2) * 0.6)
                    lx, ly = math.cos(a) * 0.9, math.sin(a) * 0.9
                    b.line([(x, y, 0), (x + lx * 0.4, y + ly * 0.4, h * 0.5), (x + lx, y + ly, h)], REED, 2)
                    b.bar((x + lx * 0.72, y + ly * 0.72, h * 0.78), (x + lx * 0.96, y + ly * 0.96, h * 0.97), 0.68, CAT, 3)
                x, y = gnd(a0 - 0.1, 1.0)
                b.slab([(x - 0.5, y, 0), (x + 0.5, y, 0), (x + math.cos(a0) * 2.0, y + math.sin(a0) * 2.0, 7.5)], REED)
            a = 7 * TAU / 8                                     # a duckling sitting on a clamp
            x, y = at(a, R - 1.2)
            tx, ty = -math.sin(a), math.cos(a)
            b.ball(x, y, 5.5, 1.6, DUCK)
            b.ball(x + tx * 1.1, y + ty * 1.1, 7.3, 1.05, DUCK)
            b.bar((x + tx * 1.9, y + ty * 1.9, 7.2), (x + tx * 3.0, y + ty * 3.0, 7.0), 0.45, BEAK, 3, 0.2)
            b.ball(x + tx * 1.55 + math.cos(a) * 0.75, y + ty * 1.55 + math.sin(a) * 0.75, 7.6, 0.24, (10, 10, 16))
            b.slab([(x - tx * 1.1, y - ty * 1.1, 5.6), (x - tx * 2.5, y - ty * 2.5, 6.9), (x - tx * 1.3, y - ty * 1.3, 6.6)], DUCK)
        elif th == "KITCHEN":
            TILE, STEEL, COPPER, CHEESE = (242, 242, 238), (220, 224, 234), (214, 122, 68), (255, 208, 60)
            for i in range(n):                                  # checkered tiles all round the wall
                _checks(b, wall(i * FL), -0.94 * hw, 0.94 * hw, 0.2, 2.1, 6, TILE)
            a = 1.78                                            # a fork and a spoon standing up
            x, y = rim(a, 0.9)
            P = _plane(x, y, a + math.pi / 2)
            b.slab([P(-0.35, 3.0), P(0.35, 3.0), P(0.35, 9.4), P(1.3, 10.4), P(1.3, 14.4), P(0.86, 14.4), P(0.86, 11.2), P(0.22, 11.2), P(0.22, 14.4),
                    P(-0.22, 14.4), P(-0.22, 11.2), P(-0.86, 11.2), P(-0.86, 14.4), P(-1.3, 14.4), P(-1.3, 10.4), P(-0.35, 9.4)], STEEL)
            a = 2.9
            x, y = rim(a, 0.9)
            P = _plane(x, y, a + math.pi / 2)
            b.slab([P(-0.35, 3.0), P(0.35, 3.0), P(0.35, 9.6), P(1.2, 10.5), P(1.5, 12.0), P(1.2, 13.5), P(0, 14.3), P(-1.2, 13.5), P(-1.5, 12.0), P(-1.2, 10.5), P(-0.35, 9.6)], STEEL)
            x, y = rim(0.28, 1.2)                               # a copper pot with something on the boil
            b.prism(7, x, y, 3.0, 2.1, 2.5, COPPER)
            b.prism(7, x, y, 5.5, 2.25, 0.5, STEEL, rtop=1.3)
            b.ball(x, y, 6.3, 0.55, (40, 40, 48))
            tx, ty = -math.sin(0.28), math.cos(0.28)
            for s in (-1, 1):
                b.line([(x + tx * s * 2.0, y + ty * s * 2.0, 4.9), (x + tx * s * 3.0, y + ty * s * 3.0, 4.9)], (40, 40, 48), 3)
            a = 3.3                                             # a wedge of cheese
            x, y = gnd(a, 1.4)
            ca, sa = math.cos(a), math.sin(a)
            v = [(x - sa * 2.1, y + ca * 2.1), (x + sa * 2.1 - ca * 1.3, y - ca * 2.1 - sa * 1.3), (x + sa * 2.1 + ca * 1.3, y - ca * 2.1 + sa * 1.3)]
            b.mesh([(px, py, 0.0) for px, py in v] + [(px, py, 2.6) for px, py in v], [(3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)], CHEESE)
            b.ball(x + sa * 1.0 + ca * 1.1, y - ca * 1.0 + sa * 1.1, 1.4, 0.5, (214, 150, 30))
            b.ball(x - sa * 0.4 + ca * 0.7, y + ca * 0.4 + sa * 0.7, 1.0, 0.38, (214, 150, 30))
            x, y = rim(0.28, 1.2)
            b.group(M_BOB, 0, x, y, 8.2, 1.6, 0.8)              # steam
            b.ball(0.2, 0.1, 0.0, 0.85, SNOW)
            b.ball(-0.5, -0.2, 1.7, 0.6, SNOW)
            _resume(b, parts0)
        elif th == "GLITCH":
            MAG, BLK, CY, ERR = (255, 0, 255), (8, 8, 14), (60, 240, 255), (255, 60, 70)
            for a in (0.0, TAU / 4, 3 * TAU / 8, 5 * TAU / 8):   # the wall did not load on some sides
                _checks(b, wall(a), -0.9 * hw, 0.9 * hw, 0.2, 2.1, 5, MAG)
            x, y = gnd(0.3, 1.5)                                # missing-texture blocks
            _mtex(b, x, y, 0, 1.35, 0.6, MAG, BLK)
            x, y = gnd(0.02, 1.0)
            b.box(x, y, 0, 0.85, 0.85, 1.7, [BLK, MAG, BLK, MAG, BLK], 1.0, 0.2)
            for a, zz, w, c in ((1.0, 5.0, 4.5, CY), (5.75, 4.4, 3.4, ERR), (2.9, 8.6, 3.8, MAG), (3.6, 2.9, 4.2, CY)):   # error bars: rows that slid sideways
                x, y = at(a, R + 0.2)
                tx, ty = -math.sin(a) * w * 0.5, math.cos(a) * w * 0.5
                b.slab([(x - tx, y - ty, zz), (x + tx, y + ty, zz), (x + tx, y + ty, zz + 0.7), (x - tx, y - ty, zz + 0.7)], c, False)
                b.line([(x + tx * 1.2, y + ty * 1.2, zz + 1.1), (x + tx * 2.0, y + ty * 2.0, zz + 1.1)], R_WHITE, 1)
            a = 1.75                                            # a warning sign that is not attached to anything
            x, y = rim(a, 0.6)
            P = _plane(x, y, a + math.pi / 2)
            b.slab([P(-2.6, 9.0), P(2.6, 9.0), P(0, 13.6)], (255, 214, 40))
            b.line([P(0, 12.2), P(0, 10.6)], BLK, 3)
            b.line([P(0, 10.0), P(0, 9.6)], BLK, 3)
            x, y = rim(3.4, 0.4)
            b.group(M_SPIN | M_BOB, 0.8, x, y, 8.0, 1.7, 0.9)  # one that never stops loading
            _mtex(b, 0, 0, -1.3, 1.3, 0.0, MAG, BLK)
            _resume(b, parts0)
        elif th == "MARKET":
            UP, DN, COIN = (60, 235, 130), (255, 70, 90), (255, 206, 70)
            for a0, cs in ((5.86, ((0.3, 2.3, UP), (1.6, 3.1, DN), (2.2, 5.6, UP))), (2.72, ((0.3, 3.4, UP), (1.5, 3.2, DN), (2.6, 6.4, UP)))):
                for j, (lo, hi, c) in enumerate(cs):            # candles: a little price chart, going up
                    a = a0 + j * 0.3
                    x, y = at(a, wr(a) + 1.3)
                    b.box(x, y, lo, 0.95, 0.95, hi - lo, c, 1.0, a)
                    b.line([(x, y, max(0.0, lo - 1.0)), (x, y, hi + 1.3)], c, 1)
            x, y = rim(1.0, 1.0)                                # a stack of coins, and a few that fell off
            b.prism(6, x, y, 3.0, 1.75, 3.2, COIN)
            for zz in (4.1, 5.2, 6.25):
                b.ring(x, y, zz, 1.82, (150, 104, 20), 6, 1)
            x2, y2 = rim(1.32, 0.9)
            b.prism(6, x2, y2, 3.0, 1.75, 1.1, COIN)
            b.ring(x2, y2, 4.15, 1.82, (150, 104, 20), 6, 1)
            a = 1.85                                            # the ticker: up and to the right
            x, y = rim(a, 0.6)
            P = _plane(x, y, a + math.pi / 2)
            b.line([P(4.2, 3.0), P(4.2, 7.0), P(2.4, 9.6), P(1.0, 8.2), P(-2.0, 12.4)], UP, 3)
            b.slab([P(-3.6, 14.6), P(-0.9, 13.3), P(-2.9, 11.3)], UP)
            b.glow(x, y, 11.0, 7, UP, 0.4)
        elif th == "QUARRY":
            ST1, ST2, HAZ, CONE, WOOD, IRON = (158, 144, 128), (128, 114, 102), (255, 210, 40), (255, 122, 30), (150, 100, 56), (70, 72, 84)
            for a in (TAU / 4, TAU / 2, 0.0):                   # hazard stripes
                _zebra(b, wall(a), -0.83 * hw, 0.76 * hw, 0.25, 1.9, 5, HAZ)
            a = 3.3                                             # cut blocks
            x, y = gnd(a, 1.45)
            b.box(x, y, 0, 1.4, 1.9, 2.5, ST1, 0.92, a + 0.12)
            b.box(x + 0.2, y + 0.3, 2.5, 1.15, 1.4, 1.9, ST2, 0.9, a + 0.7)
            x, y = gnd(6.05, 1.35)
            b.box(x, y, 0, 1.25, 1.5, 2.1, ST2, 0.9, 6.05 + 0.25)
            x, y = at(7 * TAU / 8, R - 1.2)                     # a traffic cone on a clamp
            b.box(x, y, 4.3, 1.5, 1.5, 0.4, CONE, 1.0, 7 * TAU / 8)
            b.prism(5, x, y, 4.7, 1.2, 4.3, CONE, rtop=0.3)
            b.ring(x, y, 7.0, 0.82, SNOW, 6, 3)
            xa, ya = gnd(1.1, 1.5)                              # a pickaxe leaning on the rim
            xb, yb = rim(1.3, 0.8)
            b.bar((xa, ya, 0), (xb, yb, 10.0), 0.55, WOOD, 3)
            tx, ty = -math.sin(1.2), math.cos(1.2)
            for s in (-1, 1):
                b.bar((xb, yb, 9.6), (xb + tx * s * 3.7, yb + ty * s * 3.7, 8.2), 0.8, IRON, 3, 0.12)


    # ---------------------------------------------------------------------- enemies
    def dress_enemy(b, th, top, hx, hr, r):
        """what the enemies wear on this map.  Budget: about 20 faces; swarmers and minis (r <= 7) come in dozens,
        so they get a cut-down version of the same hat (under 10 faces)."""
        b.group(M_AIM)
        tiny = r <= 7
        if th == "GRID":
            if not tiny:
                b.box(hx - hr * 0.35, 0, top - 0.1, hr * 0.55, hr * 0.55, hr * 0.35, R_METAL)
            b.line([(hx - hr * 0.35, 0, top + hr * 0.25), (hx - hr * 0.7, 0, top + hr * 1.9)], R_METAL, 1)
            b.ball(hx - hr * 0.7, 0, top + hr * 2.05, hr * 0.3, R_LITE)
            b.line([(hx + hr * 1.02, -hr * 0.75, top - hr * 0.7), (hx + hr * 1.02, hr * 0.75, top - hr * 0.7)], R_LITE, 3)
            b.glow(hx + hr, 0, top - hr * 0.7, hr * 1.8, R_LITE, 0.45)
        elif th == "FROST":
            if tiny:
                b.ball(hx, 0, top - hr * 0.15, hr * 0.85, SNOW)
            else:
                b.prism(6, hx, 0, top - 0.3, hr * 1.05, hr * 0.5, SNOW, rtop=hr * 0.45, edge=False)
                for dy, h in ((-hr * 0.9, hr * 1.5), (hr * 0.9, hr * 1.2)):
                    b.prism(3, hx - hr * 1.3, dy, top - hr * 0.75, hr * 0.46, h, ICE, rtop=0, rot=0.5)
            b.crystal(hx - hr * 1.3, 0, top - hr * 0.9, hr * 0.46, hr * 2.0, ICE, 3, 0.5, 0.3)
        elif th == "VOID":
            RUNE = (196, 124, 255)
            b.ring(hx, 0, top + hr * 0.55, hr * 1.5, RUNE, 10, 2)
            for a, h in ((0.6, 1.6), (2.7, 2.0), (4.6, 1.4))[:1 if tiny else 3]:
                b.crystal(hx + math.cos(a) * hr * 1.5, math.sin(a) * hr * 1.5, top - hr * 0.3, hr * 0.38, hr * h, RUNE, 3, a)
            b.ball(hx, 0, top + hr * 1.5, hr * 0.26, R_WHITE)
        elif th == "CORRUPTED":
            G1, G2, GD = (80, 255, 165), (24, 160, 104), (12, 62, 48)
            b.box(hx - hr * 0.2, hr * 0.3, top - hr * 0.3, hr * 0.7, hr * 0.7, hr * 1.0, G2, 1.0, 0.4)
            if not tiny:
                b.box(hx + hr * 0.3, -hr * 0.5, top + hr * 1.1, hr * 0.45, hr * 0.45, hr * 0.7, G1, 1.0, 1.0)
                b.box(hx - hr * 1.5, -hr * 0.2, top - hr * 1.1, hr * 0.5, hr * 0.5, hr * 0.8, GD, 1.0, 0.7)
            b.line([(hx + hr * 1.06, -hr * 1.1, top - hr * 0.55), (hx + hr * 1.06, hr * 0.3, top - hr * 0.55)], G1, 2)
            b.line([(hx + hr * 1.06, -hr * 0.2, top - hr * 0.9), (hx + hr * 1.06, hr * 1.3, top - hr * 0.9)], G1, 2)
        elif th == "DUNES":
            CL = (222, 196, 150)
            if tiny:
                b.prism(5, hx, 0, top - hr * 0.35, hr * 1.1, hr * 1.1, CL, rtop=hr * 0.4)
            else:
                b.prism(8, hx, 0, top - hr * 0.35, hr * 1.15, hr * 0.7, CL, rtop=hr * 0.85)
                b.prism(8, hx, 0, top + hr * 0.35, hr * 0.85, hr * 0.5, CL, rtop=hr * 0.3)
            b.slab([(hx - hr, 0, top + hr * 0.1), (hx - hr * 3.4, hr * 0.5, top - hr * 0.2), (hx - hr * 3.0, -hr * 0.3, top - hr * 1.1), (hx - hr, 0, top - hr * 0.5)], (214, 74, 48))
        elif th == "INFERNO":
            HORN = (60, 38, 36)
            for s in (-1, 1):
                if tiny:
                    b.slab([(hx - hr * 0.3, s * hr * 0.6, top - hr * 0.3), (hx + hr * 0.5, s * hr * 0.9, top - hr * 0.3), (hx + hr * 0.9, s * hr * 1.9, top + hr * 1.4)], HORN)
                else:
                    b.bar((hx, s * hr * 0.8, top - hr * 0.2), (hx + hr * 0.9, s * hr * 1.9, top + hr * 1.4), hr * 0.36, HORN, 4, hr * 0.05)
            b.glow(hx, 0, top - hr * 0.2, hr * 3.2, (255, 120, 24), 0.5)
            b.line([(hx - hr, -hr * 0.6, top - hr * 1.4), (hx - hr * 1.1, 0, top - hr * 0.6), (hx - hr, hr * 0.6, top - hr * 1.6)], (255, 120, 24), 2)
        elif th == "FOREST":
            LEAF = (90, 235, 140)
            for s in (-1, 1):
                b.slab([(hx, s * hr * 0.3, top - hr * 0.1), (hx - hr * 0.6, s * hr * 1.6, top + hr * 1.9), (hx - hr * 1.2, s * hr * 0.4, top + hr * 0.5)], LEAF)
            b.slab([(hx, 0, top), (hx - hr * 0.3, 0, top + hr * 2.5), (hx - hr * 1.3, 0, top + hr * 0.6)], (60, 200, 110))
            if tiny:
                b.ball(hx - hr * 1.2, 0, top - hr * 0.2, hr * 0.45, (120, 255, 200))
            else:
                b.prism(7, hx - hr * 1.2, 0, top - hr * 0.5, hr * 0.7, hr * 0.5, (120, 255, 200), rtop=hr * 0.2)
        elif th == "ABYSS":
            b.ball(hx + hr * 0.2, 0, top - hr * 0.5, hr * 1.25, (200, 236, 255))
            b.ring(hx + hr * 0.2, 0, top - hr * 1.3, hr * 1.2, (198, 158, 74), 10, 2)
            b.slab([(hx - hr * 0.8, 0, top + hr * 0.3), (hx - hr * 2.6, 0, top + hr * 1.6), (hx - hr * 2.4, 0, top - hr * 0.8)], (255, 120, 130))
        elif th == "CRYSTAL":
            C1, C2 = (255, 120, 235), (190, 130, 255)
            b.crystal(hx - hr * 1.0, 0, top - hr * 1.0, hr * 0.55, hr * 2.8, C1, 3, 0.6, 0.3)
            if tiny:
                b.prism(3, hx - hr * 1.0, hr * 0.7, top - hr * 0.7, hr * 0.5, hr * 1.5, C2, rtop=0, rot=0.6)
            else:
                b.crystal(hx - hr * 1.0, -hr * 0.8, top - hr * 1.0, hr * 0.5, hr * 2.2, C1, 3, 0.6, 0.3)
                b.crystal(hx - hr * 1.0, hr * 0.7, top - hr * 1.0, hr * 0.5, hr * 1.6, C2, 3, 0.6, 0.3)
        elif th == "CITY":
            b.slab([(hx + hr * 0.8, 0, top - hr * 0.1), (hx - hr * 0.2, 0, top + hr * 1.7), (hx - hr * 1.6, 0, top + hr * 1.2), (hx - hr * 1.4, 0, top - hr * 0.1)], (255, 60, 190))
            b.line([(hx + hr * 1.05, -hr * 0.9, top - hr * 0.75), (hx + hr * 1.05, hr * 0.9, top - hr * 0.75)], (60, 230, 255), 3)
            if not tiny:
                b.glow(hx, 0, top + hr * 0.7, hr * 2.4, (255, 60, 190), 0.4)
        elif th == "SKY":
            GOLDC = (255, 214, 90)
            b.ring(hx, 0, top + hr * 0.9, hr * 0.95, GOLDC, 10, 2)
            for s in (-1, 1):                                   # little wings (white: they catch the sun)
                b.slab([(hx + hr * dx, s * hr * dy, top + hr * dz) for dx, dy, dz in ((0.3, 0.8, -0.7), (-0.2, 3.0, 0.6), (-0.7, 2.3, 0.2), (-1.2, 2.7, 0.35),
                                                                                     (-1.4, 1.9, -0.1), (-2.0, 2.1, 0.0), (-1.3, 0.8, -0.8))], R_WHITE)
        elif th == "FACTORY":
            RUSTC, SOOT, EMB = (182, 100, 52), (62, 54, 56), (255, 140, 30)
            b.box(hx + hr * 0.8, 0, top - hr * 1.75, hr * 0.38, hr * 1.0, hr * 1.9, SOOT, 0.82)        # a welding mask
            b.line([(hx + hr * 1.2, -hr * 0.62, top - hr * 0.75), (hx + hr * 1.2, hr * 0.62, top - hr * 0.75)], EMB, 3)
            b.ball(hx + hr * 0.5, 0, top + hr * 0.55, hr * 0.3, (255, 240, 170))
            if not tiny:
                b.prism(6, hx - hr * 0.15, 0, top - hr * 0.1, hr * 1.0, hr * 0.5, RUSTC, rtop=hr * 0.6)    # a hard hat with a lamp
                b.bar((hx - hr * 1.15, hr * 0.5, top - hr * 1.2), (hx - hr * 1.45, hr * 0.5, top + hr * 1.1), hr * 0.3, RUSTC, 4)      # an exhaust
                b.ball(hx - hr * 1.5, hr * 0.5, top + hr * 1.35, hr * 0.34, EMB)
            b.glow(hx + hr * 1.2, 0, top - hr * 0.75, hr * 1.8, EMB, 0.5)
        elif th == "SUNSET":
            SH = (14, 10, 26)
            if tiny:
                b.line([(hx + hr * 1.1, -hr * 1.0, top - hr * 0.8), (hx + hr * 1.1, hr * 1.0, top - hr * 0.8)], SH, 4)
            else:
                b.box(hx + hr * 0.75, 0, top - hr * 1.1, hr * 0.42, hr * 1.12, hr * 0.6, SH)            # shades
            b.line([(hx + hr * 1.2, -hr * 0.95, top - hr * 0.62), (hx + hr * 1.2, -hr * 0.3, top - hr * 0.95)], R_WHITE, 2)
            for i, c in enumerate(((255, 222, 80), (255, 150, 70), (255, 84, 150), (255, 70, 190))):      # a mohawk the colours of the sky
                if tiny and i % 2:
                    continue
                x0 = hx + hr * (0.75 - i * 0.55)
                b.slab([(x0, 0, top - hr * 0.15), (x0 - hr * (1.1 if tiny else 0.6), 0, top - hr * 0.15), (x0 - hr * 0.15, 0, top + hr * (1.7 - i * 0.18))], c)
        elif th == "BOARD":
            ALU = (196, 204, 216)
            if tiny:
                for dy in (-0.6, 0.0, 0.6):                     # three fins
                    b.slab([(hx - hr * 0.9, dy * hr, top - hr * 0.1), (hx + hr * 0.7, dy * hr, top - hr * 0.1), (hx + hr * 0.7, dy * hr, top + hr * 1.2),
                            (hx - hr * 0.9, dy * hr, top + hr * 1.2)], ALU)
            else:
                b.box(hx - hr * 0.1, 0, top - 0.1, hr * 0.9, hr * 0.95, hr * 0.28, ALU)                 # a heat sink
                for dy in (-0.68, 0.0, 0.68):
                    b.box(hx - hr * 0.1, dy * hr, top + hr * 0.18, hr * 0.85, hr * 0.14, hr * 1.15, ALU)
            b.line([(hx - hr * 1.02, -hr * 0.4, top - hr * 0.2), (hx - hr * 1.02, -hr * 0.4, top - hr * 1.0), (hx - hr * 1.02, hr * 0.5, top - hr * 1.5)], (255, 206, 70), 2)
            b.ball(hx + hr * 1.0, hr * 0.55, top - hr * 0.3, hr * 0.2, (120, 255, 90))
        elif th == "HALLOWEEN":
            WITCH = (120, 60, 190)
            if tiny:
                _disc(b, hx, 0, top + 0.5, hr * 1.6, 6, WITCH)
                b.prism(5, hx, 0, top + 0.5, hr * 0.95, hr * 2.2, WITCH, rtop=0)
            else:
                b.prism(8, hx, 0, top, hr * 1.6, 0.9, WITCH)
                b.prism(8, hx, 0, top + 0.9, hr * 0.95, hr * 2.2, WITCH, rtop=0)
            b.ring(hx, 0, top + 1.3, hr * 1.0, (255, 128, 22), 8, 2)
        elif th == "XMAS":
            SANTA = (232, 44, 62)
            if tiny:
                _disc(b, hx, 0, top + hr * 0.2, hr * 1.2, 6, SNOW)
                b.prism(5, hx - hr * 0.1, 0, top + hr * 0.2, hr * 0.98, hr * 2.1, SANTA, rtop=0)
            else:
                b.prism(8, hx, 0, top - 0.1, hr * 1.2, hr * 0.5, SNOW)
                b.prism(8, hx - hr * 0.1, 0, top - 0.1 + hr * 0.5, hr * 0.98, hr * 1.9, SANTA, rtop=0)
            b.ball(hx - hr * 0.1, 0, top + hr * 2.45, hr * 0.42, SNOW)
        elif th == "POND":
            DUCK, BEAK = (255, 214, 40), (255, 140, 30)
            b.ball(hx - hr * 0.15, 0, top + hr * 0.6, hr * 0.9, DUCK)
            b.ball(hx + hr * 0.55, 0, top + hr * 1.55, hr * 0.58, DUCK)
            b.bar((hx + hr * 0.95, 0, top + hr * 1.5), (hx + hr * 1.75, 0, top + hr * 1.38), hr * 0.28, BEAK, 3, hr * 0.12)
            for s in (-1, 1):
                b.ball(hx + hr * 0.85, s * hr * 0.36, top + hr * 1.75, hr * 0.13, (10, 10, 16))
                if not tiny:
                    b.slab([(hx + hr * 0.2, s * hr * 0.92, top + hr * 0.9), (hx - hr * 1.0, s * hr * 1.0, top + hr * 0.95), (hx - hr * 0.3, s * hr * 0.95, top + hr * 0.2)], (240, 190, 30))
            b.slab([(hx - hr * 0.8, 0, top + hr * 0.5), (hx - hr * 1.65, 0, top + hr * 1.45), (hx - hr * 0.85, 0, top + hr * 1.2)], DUCK)
        elif th == "KITCHEN":
            b.prism(5 if tiny else 8, hx, 0, top - 0.1, hr * 0.82, hr * 1.0, SNOW)
            b.ball(hx, 0, top + hr * 1.35, hr * 1.0, SNOW)
            for s in (-1, 1):
                b.ball(hx - hr * 0.1, s * hr * 0.62, top + hr * 1.2, hr * 0.8, SNOW)
        elif th == "GLITCH":
            MAG, BLK = (255, 0, 255), (8, 8, 14)
            if tiny:
                b.box(hx, 0, top + hr * 0.25, hr * 0.62, hr * 0.62, hr * 1.24, [BLK, MAG, BLK, MAG, BLK], 1.0, 0.5)
            else:
                _mtex(b, hx, 0, top + hr * 0.25, hr * 0.62, 0.5, MAG, BLK)
            b.line([(hx + hr * 1.06, -hr * 1.3, top - hr * 0.55), (hx + hr * 1.06, hr * 0.4, top - hr * 0.55)], (60, 240, 255), 2)
            b.line([(hx + hr * 1.06, -hr * 0.3, top - hr * 0.95), (hx + hr * 1.06, hr * 1.4, top - hr * 0.95)], MAG, 2)
        elif th == "MARKET":
            up = int(r) % 2 == 1                                # most of them are here to crash the market; a few are bullish
            c = (60, 235, 130) if up else (255, 70, 90)
            z0, s = top + hr * 0.4, (1 if up else -1)
            zc = z0 + hr * 1.0
            for k in (0, 1):                                    # an arrow over the head, crossed so it shows from every side
                dx, dy = (0.0, 1.0) if k == 0 else (1.0, 0.0)
                b.slab([(hx - dx * hr * 0.3, -dy * hr * 0.3, zc - s * hr * 1.0), (hx + dx * hr * 0.3, dy * hr * 0.3, zc - s * hr * 1.0),
                        (hx + dx * hr * 0.3, dy * hr * 0.3, zc), (hx + dx * hr * 0.95, dy * hr * 0.95, zc), (hx, 0, zc + s * hr * 1.0),
                        (hx - dx * hr * 0.95, -dy * hr * 0.95, zc), (hx - dx * hr * 0.3, -dy * hr * 0.3, zc)], c)
            xf = hx + hr * 1.15                                 # and a tie
            b.slab([(xf, -hr * 0.22, top - hr * 1.2), (xf, hr * 0.22, top - hr * 1.2), (xf, hr * 0.4, top - hr * 2.3), (xf, 0, top - hr * 2.75), (xf, -hr * 0.4, top - hr * 2.3)], (224, 186, 80))
        elif th == "QUARRY":
            HARD = (255, 210, 40)
            _disc(b, hx + hr * 0.15, 0, top + hr * 0.1, hr * 1.35, 8, HARD)                             # the brim
            b.prism(5 if tiny else 8, hx, 0, top - 0.1, hr * 0.98, hr * 1.2, HARD, rtop=hr * 0.5)
            b.line([(hx + hr * 0.85, 0, top + hr * 0.3), (hx, 0, top + hr * 1.2), (hx - hr * 0.85, 0, top + hr * 0.3)], (190, 140, 20), 2)
            b.ball(hx + hr * 0.95, 0, top + hr * 0.55, hr * 0.26, R_WHITE)
    return THEMES2, dress_base, dress_enemy


THEMES2, dress_base, dress_enemy = _mk2_themes()


def _mk2_towers_a():
    # NEON BASTION mk II tower models, set A:
    #   blade, scatter, harvester, sentinel, mechanic, bulwark, hydra, beacon, reactor, commander
    # Same builder, helpers and style as c_models.py (the six approved mk II towers).


    def _pol(a, r, z=0.0):
        return (math.cos(a) * r, math.sin(a) * r, z)


    def _fan(b, x0, x1, w0, w1, z, h, role, nose=0.0, tail=0.0, k=0.75):
        """an armoured body that is narrow at the back (x0, half width w0) and wide at the front (x1, half width w1)"""
        vs = [(x0, -w0, z), (x1, -w1, z), (x1, w1, z), (x0, w0, z),
              (x0 + tail, -w0 * k, z + h), (x1 - nose, -w1 * k, z + h), (x1 - nose, w1 * k, z + h), (x0 + tail, w0 * k, z + h)]
        b.mesh(vs, [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], role)


    # ====================================================================== BLADE
    def tm2_blade(b, lv):
        """a rotor of hooked blades on a motor housing; the whole rotor is the aiming group (the game spins it)"""
        z = pad2(b, lv, 11.5)
        hz = 6.0 + lv * 0.45
        lathe(b, 0, 0, [(6.2, z), (4.8, z + 2.8), (3.3, z + hz)], 8, [R_DARK, R_METAL], TAU / 16)      # motor housing
        b.ring(0, 0, z + 2.95, 5.05, R_LITE, 12, 2)
        for i in range(3):                                                           # power studs feeding the motor
            a = TAU / 4 + i * TAU / 3
            x, y = math.cos(a) * 10.3, math.sin(a) * 10.3
            hs = 3.0 + lv * 0.5
            b.prism(4, x, y, 3.4, 1.4, hs, R_METAL, rtop=0.9, rot=a)
            b.ball(x, y, 3.4 + hs + 0.6, 0.95, R_LITE if lv >= 1 else R_WHITE)
            if lv >= 1:
                b.line([(x, y, 3.4 + hs), _pol(a, 7.4, z + 0.5), _pol(a, 5.1, z + 2.7)], R_LITE, 2)
        zh = z + hz
        b.group(M_AIM)
        b.prism(8, 0, 0, zh, 4.1, 2.0, R_DARK, rtop=3.3, rot=TAU / 16)                # hub
        b.ring(0, 0, zh + 0.25, 4.3, R_LITE, 12, 2)
        n = (2, 3, 3, 4, 4)[lv]
        L = 14.5 + lv * 1.25
        zb = zh + 1.0
        for i in range(n):
            a = i * TAU / n
            ca, sa = math.cos(a), math.sin(a)

            def Q(u, v, dz=0.0):
                return (ca * u - sa * v, sa * u + ca * v, zb + dz)
            b.bar(Q(2.6, -0.9, -0.95), Q(L * 0.58, -2.0, -0.95), 0.95, R_METAL, 4, 0.6)             # the arm under the blade
            edge = [(2.8, 1.5), (L * 0.38, 0.7), (L * 0.62, 0.3), (L * 0.82, 1.5), (L * 0.95, 5.0)]  # the cutting edge: a sickle hooking into the spin
            back = [(L, 0.4), (L * 0.82, -2.7), (L * 0.52, -3.6), (2.8, -1.7)]
            b.slab([Q(u, v) for u, v in edge + back], R_LITE)
            b.line([Q(u, v, 0.12) for u, v in edge], R_ALT if lv >= 4 else R_WHITE, 2)
        if lv < 2:
            b.ball(0, 0, zh + 2.5, 2.0, R_WHITE)
        else:
            zs = zh + 2.0
            b.prism(6, 0, 0, zs, 2.5, 3.0, R_METAL, rtop=2.0)                         # spindle for the second tier
            L2 = L * 0.6
            for i in range(n):                                                        # upper claws, raked upward
                a = (i + 0.5) * TAU / n
                ca, sa = math.cos(a), math.sin(a)
                b.slab([(ca * 2.0 - sa * 1.3, sa * 2.0 + ca * 1.3, zs + 1.2), (ca * L2 - sa * 2.2, sa * L2 + ca * 2.2, zs + 4.4 + lv * 0.3),
                        (ca * 4.6 + sa * 1.9, sa * 4.6 - ca * 1.9, zs + 1.6)], R_MAIN)
            if lv < 3:
                b.ball(0, 0, zs + 3.5, 1.7, R_WHITE)
            else:
                b.prism(6, 0, 0, zs + 3.0, 2.0, 5.0, R_LITE, rtop=0)                  # spike
                b.glow(0, 0, zb, 12, R_LITE, 0.4)
            if lv >= 4:
                b.crystal(0, 0, zs + 8.4, 1.9, 5.0, R_ALT, 4)
                b.ring(0, 0, zb + 0.1, L + 1.2, R_ALT, 16, 1)
                halo(b, zs + 20, 8.0)


    # ====================================================================== SCATTER
    def tm2_scatter(b, lv):
        """a shotgun turret: a fan of barrels under a heat shield"""
        z = pad2(b, lv, 13)
        lathe(b, 0, 0, [(7.2, z), (6.2, z + 2.0)], 8, R_METAL, TAU / 16)
        z += 2.0
        b.group(M_AIM | M_RECOIL)
        b.prism(8, 0, 0, z, 8.2, 1.8, R_DARK, rtop=7.4, rot=TAU / 16)
        zt = z + 1.8
        hh = 5.2 + lv * 0.25
        wf = 7.0 + lv * 0.35
        _fan(b, -7.4, 5.4, 4.0, wf, zt, hh, R_MAIN, nose=3.2, tail=1.4, k=0.74)
        zb = zt + 2.7
        nb_ = (3, 3, 3, 4, 5)[lv]
        sp = (0.36, 0.36, 0.38, 0.44, 0.50)[lv]
        Lb = 15.0 + lv * 0.8
        b.box(5.0, 0, zb - 2.3, 1.2, wf - 0.5, 4.0, R_DARK)                            # mantlet the barrels come out of
        for i in range(nb_):
            a = -sp + 2 * sp * i / (nb_ - 1)
            ca, sa = math.cos(a), math.sin(a)
            b.bar((ca * 6.2, sa * 6.2, zb), (ca * Lb, sa * Lb, zb), 1.3, R_METAL, 4)
            b.bar((ca * (Lb - 0.3), sa * (Lb - 0.3), zb), (ca * (Lb + 2.3), sa * (Lb + 2.3), zb), 1.85, R_LITE, 4)
        b.line([_pol(-sp + 2 * sp * i / 6.0, 12.6, zb + 1.05) for i in range(7)], R_METAL, 3)        # muzzle brace
        for s in (-1, 1):
            b.line([(-6.2, s * 4.25, zt + 2.6), (4.2, s * (wf - 0.55), zt + 2.6)], R_LITE, 2)
        b.line([(-5.6, -2.9, zt + hh + 0.1), (1.6, -4.9, zt + hh + 0.1), (1.6, 4.9, zt + hh + 0.1), (-5.6, 2.9, zt + hh + 0.1)],
               R_ALT if lv >= 4 else R_LITE, 2, True)
        if lv < 2:
            b.ball(-2.4, 0, zt + hh + 0.9, 1.5, R_WHITE)
        if lv >= 1:
            b.slab([_pol(-sp - 0.12, 6.4, zb + 1.75), _pol(-sp - 0.12, 10.4, zb + 1.75), _pol(0, 11.0, zb + 1.75),
                    _pol(sp + 0.12, 10.4, zb + 1.75), _pol(sp + 0.12, 6.4, zb + 1.75)], R_MAIN)       # heat shield over the fan
            b.box(-8.4, 0, zt + 0.6, 1.4, 3.3, 3.6, R_DARK)                                           # shell hopper
            b.line([(-9.9, -2.4, zt + 3.0), (-9.9, 2.4, zt + 3.0)], R_LITE, 2)
        if lv >= 2:
            b.prism(8, -2.4, 0, zt + hh, 3.0, 1.5, R_DARK)                                            # drum magazine
            for i in range(6):
                x, y, _ = _pol(i * TAU / 6, 2.0)
                b.ball(-2.4 + x, y, zt + hh + 1.7, 0.75, R_LITE)
            for s in (-1, 1):
                b.box(-1.2, s * (4.0 + wf) * 0.5 + s * 0.9, zt + 0.3, 5.2, 0.8, 3.9, R_DARK, 0.86, s * math.atan2(wf - 4.0, 12.8))
        if lv >= 3:
            b.line([(0.6, -3.4, zt + hh + 0.9), (2.4, -3.4, zt + hh + 0.9)], R_METAL, 4)             # sight
            b.ball(2.6, -3.4, zt + hh + 0.9, 0.9, R_WHITE)
            b.line([(-5.0, 2.4, zt + hh), (-6.4, 2.6, zt + hh + 8.0)], R_METAL, 1)
            b.ball(-6.4, 2.6, zt + hh + 8.3, 0.8, R_LITE)
            b.glow(Lb + 2, 0, zb, 9, R_LITE, 0.5)
        if lv >= 4:
            b.line([_pol(-sp - 0.12 + (2 * sp + 0.24) * i / 6.0, 10.5 + (0.6 if i == 3 else 0.0), zb + 1.9) for i in range(7)], R_ALT, 2)
            halo(b, zt + hh + 13, 8.5)


    # ====================================================================== HARVESTER
    def tm2_harvester(b, lv):
        """a refinery: collector petals, cash tanks piped into the core, and a gold crystal turning above it"""
        z = pad2(b, lv, 13)
        lathe(b, 0, 0, [(6.2, z), (5.0, z + 2.8), (3.3, z + 4.2)], 8, [R_DARK, R_METAL], TAU / 16)
        b.ring(0, 0, z + 2.95, 5.25, R_LITE, 12, 2)
        zc = z + 4.2
        n = (3, 3, 4, 4, 6)[lv]
        a0 = {3: TAU / 4, 4: TAU / 8, 6: 0.0}[n]
        r0, r1, w0, w1 = 4.4, 13.0, 1.6, 3.7
        z0, z1 = zc - 0.3, zc + 0.9 + lv * 0.2
        for i in range(n):                                                           # collector petals
            a = a0 + i * TAU / n
            ca, sa = math.cos(a), math.sin(a)

            def Q(r, w, zz):
                return (ca * r - sa * w, sa * r + ca * w, zz)
            b.bar(Q(3.4, 0, zc - 1.3), Q(r1 - 0.8, 0, z1 - 0.9), 0.8, R_METAL, 4)
            b.slab([Q(r0, -w0, z0), Q(r0, w0, z0), Q(r1, w1, z1), Q(r1, -w1, z1)], R_MAIN)
            k = 0.17 + (z1 - z0) / (r1 - r0) * 0.0
            b.line([Q(r0 + 1.2, 0, z0 + (z1 - z0) * 1.2 / (r1 - r0) + k), Q(r1 - 0.8, 0, z1 - (z1 - z0) * 0.8 / (r1 - r0) + k)], R_LITE, 2)
            if lv >= 1:
                f = 0.62
                rr, ww, zz = r0 + (r1 - r0) * f, w0 + (w1 - w0) * f - 0.4, z0 + (z1 - z0) * f + k
                b.line([Q(rr, -ww, zz), Q(rr, ww, zz)], R_LITE, 2)
            if lv >= 4:
                b.line([Q(r1, -w1, z1 + 0.1), Q(r1, w1, z1 + 0.1)], R_ALT, 3)
            b.ball(ca * (r1 + 0.2), sa * (r1 + 0.2), z1 + 0.5, 0.85, R_WHITE)
        gaps = [a0 + (i + 0.5) * TAU / n for i in range(n)]                          # cash tanks stand between the petals
        pick = ([0], [0, 2], [1, 3], [1, 3, 0], [2, 0, 4])[lv]
        tb = min(z, 4.9)
        for j in pick:
            x, y, _ = _pol(gaps[j], 9.0)
            b.prism(6, x, y, tb, 2.0, z + 3.6 - tb, R_METAL)
            b.ball(x, y, z + 4.3, 1.75, R_ALT)
            b.line([(x * 0.8, y * 0.8, z + 2.6), (x * 0.5, y * 0.5, z + 2.9)], R_ALT, 3)
        if lv >= 2:
            b.box(0.0, -6.3, z, 1.5, 1.1, 2.4, R_DARK)                                # pump
            b.ball(0.0, -7.2, z + 1.5, 0.8, R_WHITE)
        b.group(M_SPIN | M_BOB, 1.4, 0, 0, zc + 3.0 + lv * 0.5, 2.3, 1.0)
        cr = 3.4 + lv * 0.45
        b.crystal(0, 0, 0, cr, cr * 2.5, R_ALT, 6)
        b.glow(0, 0, cr * 1.25, cr * 3.0, R_ALT, 0.55)
        if lv >= 2:
            b.crystal(0, 0, cr * 0.45, cr * 0.48, cr * 1.6, R_WHITE, 4, TAU / 8)
        if lv >= 1:
            b.ring(0, 0, cr * 1.25, cr + 2.6, R_ALT, 16, 1)
            for i in range(2 + (lv >= 3)):
                x, y, _ = _pol(i * TAU / (2 + (lv >= 3)), cr + 2.6)
                b.ball(x, y, cr * 1.25, 0.9, R_WHITE)
        if lv >= 3:
            b.ring(0, 0, cr * 1.25, cr + 4.4, R_LITE, 16, 1, 0.45)
        if lv >= 4:
            halo(b, zc + 3.0 + lv * 0.5 + cr * 2.5 + 6.5, 7.0)


    # ====================================================================== SENTINEL
    def tm2_sentinel(b, lv):
        """a bolted-down gunship: cannon on one shoulder, a great blade on the other"""
        z = pad2(b, lv, 12)
        lathe(b, 0, 0, [(5.8, z), (4.6, z + 2.4)], 6, R_METAL)
        z += 2.4
        b.group(M_AIM | M_RECOIL)
        b.prism(8, 0, 0, z, 6.1, 1.5, R_BLACK, rtop=5.5, rot=TAU / 16)
        zt = z + 1.5
        hh = 6.6 + lv * 0.35
        hull(b, -5.2, 5.0, 4.8, zt, hh, R_MAIN, nose=3.0, tail=1.0, topw=3.5)        # torso

        def G(t, s):
            return (5.0 - 3.0 * t + 0.2, s * (4.8 - 1.3 * t) * 0.86, zt + hh * t + 0.05)
        b.slab([G(0.5, -1), G(0.5, 1), G(0.84, 1), G(0.84, -1)], R_WHITE)             # canopy
        b.line([G(0.16, -1), G(0.16, 1)], R_LITE, 2)
        b.box(-1.1, 0, zt + hh, 2.0, 1.9, 2.3, R_DARK, 0.85)                           # head
        b.line([(1.0, -1.4, zt + hh + 1.3), (1.0, 1.4, zt + hh + 1.3)], R_LITE, 2)
        zg = zt + hh * 0.6
        yg = 6.9
        Lg = 14.5 + lv * 0.9
        # the gun (right shoulder)
        b.box(0.8, yg, zg - 1.7, 4.6, 1.9, 3.4, R_DARK)
        b.line([(-3.6, yg + 2.0, zg), (5.2, yg + 2.0, zg)], R_LITE, 2)
        for dz in ((-1.05, 1.05) if lv >= 4 else (0.0,)):
            rb = 0.95 if lv >= 4 else 1.2
            b.bar((5.4, yg, zg + dz), (Lg, yg, zg + dz), rb, R_METAL, 4)
            b.bar((Lg - 0.3, yg, zg + dz), (Lg + 2.3, yg, zg + dz), rb + 0.5, R_LITE, 4)
        # the blade arm (left shoulder)
        b.box(-0.4, -6.6, zg - 1.0, 2.6, 1.7, 3.2, R_DARK, 0.82)
        b.bar((0.4, -7.2, zg + 0.5), (4.4, -9.2, zg - 0.5), 1.25, R_METAL, 4)
        Lb = 15.0 + lv * 1.4

        def B(u, w, dz=0.0):
            return (4.0 + u, -9.2 - w * 0.9 + u * 0.1, zg - 0.5 - w * 0.4 + u * 0.05 + dz)
        b.slab([B(0, -1.0), B(Lb * 0.7, -1.3), B(Lb, 0.6), B(Lb * 0.84, 2.7), B(Lb * 0.5, 3.6), B(0.8, 2.3)], R_LITE)      # a great falchion
        b.line([B(0.8, 2.3, 0.15), B(Lb * 0.5, 3.6, 0.15), B(Lb * 0.84, 2.7, 0.15), B(Lb, 0.6, 0.15)], R_ALT if lv >= 4 else R_WHITE, 2)
        b.bar(B(-0.6, -0.9, 0.7), B(Lb * 0.62, -1.2, 0.7), 0.75, R_METAL, 4, 0.45)                                           # its spine
        if lv < 1:
            b.line([(-4.82, -3.2, zt + hh * 0.5), (-4.82, 3.2, zt + hh * 0.5)], R_LITE, 2)    # exhaust slit on the bare back
        if lv >= 1:
            b.box(3.7, -9.9, zg - 1.9, 0.6, 2.7, 1.5, R_METAL)                         # crossguard
            b.box(-6.3, 0, zt + 0.8, 1.3, 3.4, hh - 1.6, R_DARK)                       # engine pack
            b.line([(-7.7, -2.6, zt + hh - 2.2), (-7.7, 2.6, zt + hh - 2.2)], R_LITE, 2)
        if lv >= 2:
            b.prism(4, 0.2, yg, zg + 1.7, 1.5, 2.6, R_LITE, rtop=0, rot=TAU / 8)        # shoulder spikes
            b.prism(4, -0.4, -6.6, zg + 2.2, 1.5, 2.8, R_LITE, rtop=0, rot=TAU / 8)
            b.slab([(-2.8, 0, zt + hh + 2.3), (0.4, 0, zt + hh + 2.3), (-1.8, 0, zt + hh + 5.2 + lv * 0.4), (-4.0, 0, zt + hh + 4.0)], R_LITE)    # crest
        if lv >= 3:
            for s in (-1, 1):                                                          # wings
                b.slab([(-5.0, s * 2.4, zt + hh - 0.4), (-12.4, s * 6.6, zt + hh + 7.5 + lv * 0.5), (-5.8, s * 4.6, zt + 1.6)], R_MAIN)
                b.line([(-5.0, s * 2.4, zt + hh - 0.3), (-12.4, s * 6.6, zt + hh + 7.6 + lv * 0.5)], R_ALT if lv >= 4 else R_LITE, 2)
                b.ball(-7.7, s * 1.8, zt + 2.0, 1.0, R_WHITE)
            b.glow(4.0 + Lb, -8.5, zg + 0.4, 6, R_LITE, 0.5)
        if lv >= 4:
            b.line([G(0.44, -1.12), G(0.44, 1.12), G(0.9, 1.12), G(0.9, -1.12)], R_ALT, 2, True)
            b.ring(0, 0, zt - 0.2, 6.6, R_ALT, 16, 2)
            halo(b, zt + hh + 16, 8.0)


    # ====================================================================== MECHANIC
    def tm2_mechanic(b, lv):
        """a field workshop: crane arm welding at the dock, repair drones circling overhead"""
        z = pad2(b, lv, 12)
        H = 5.6 + lv * 0.4
        hull(b, -6.6, 3.6, 5.0, z, H, R_DARK, nose=1.4, tail=0.6, topw=4.2)           # the workshop
        zr = z + H
        b.box(-1.9, 0, zr, 3.9, 3.8, 0.9, R_MAIN, 0.94)                                # roof
        zx = zr + 0.98
        b.slab([(-4.7, -0.9, zx), (0.9, -0.9, zx), (0.9, 0.9, zx), (-4.7, 0.9, zx)], R_WHITE)       # the repair cross
        b.slab([(-2.8, -2.8, zx), (-1.0, -2.8, zx), (-1.0, 2.8, zx), (-2.8, 2.8, zx)], R_WHITE)

        def G(t, s):
            return (3.6 - 1.4 * t + 0.16, s * 2.7, z + H * t)
        b.slab([G(0.06, -1), G(0.06, 1), G(0.8, 1), G(0.8, -1)], R_LITE)               # shutter door
        b.line([G(0.32, -1), G(0.32, 1)], R_BLACK, 1)
        b.line([G(0.56, -1), G(0.56, 1)], R_BLACK, 1)
        b.prism(6, 6.3, 0, z, 1.9, 0.7, R_METAL)                                       # the dock
        b.ring(6.3, 0, z + 0.8, 1.5, R_LITE, 8, 2)
        # crane
        mx, my = -4.9, 2.9
        zm = zr + 7.4 + lv * 0.7
        b.bar((mx, my, zr + 0.9), (mx, my, zm), 0.9, R_METAL, 4)
        b.ball(mx, my, zm + 0.2, 1.3, R_LITE)
        e = (4.2, 1.4, zm + 1.6)
        b.bar((mx, my, zm), e, 0.8, R_MAIN, 4)
        b.ball(e[0], e[1], e[2], 1.05, R_WHITE)
        w = (7.0, 0.3, zm - 3.4)
        b.bar(e, w, 0.65, R_METAL, 4)
        b.line([(w[0] - 0.7, w[1] + 0.5, w[2] - 1.6), w, (w[0] + 0.3, w[1] - 0.6, w[2] - 1.6)], R_METAL, 2)
        b.ball(6.8, 0.2, w[2] - 2.0, 0.8, R_WHITE)                                     # welding spark
        b.glow(6.8, 0.2, w[2] - 2.0, 5 + lv, R_LITE, 0.6)
        b.box(0.2, -6.8, min(z, 4.9), 1.7, 1.1, 1.9, R_MAIN)                            # toolbox
        b.line([(-1.2, -7.95, min(z, 4.9) + 1.3), (1.6, -7.95, min(z, 4.9) + 1.3)], R_LITE, 2)
        b.prism(6, -2.6, 6.9, min(z, 4.9), 1.5, 4.2, R_METAL)                           # gas bottle
        b.ball(-2.6, 6.9, min(z, 4.9) + 4.6, 1.2, R_WHITE)
        if lv >= 1:
            b.bar((-5.4, -3.0, zr + 0.6), (-5.4, -3.0, zr + 4.6), 0.9, R_METAL, 4)     # exhaust stack
            b.ball(-5.4, -3.0, zr + 4.9, 0.7, R_BLACK)
        if lv >= 2:
            b.box(-3.6, -6.9, min(z, 4.9), 1.2, 1.1, 2.6, R_DARK)                       # parts crate
            b.prism(8, 6.3, 0, z + 0.7, 1.5, 0.8, R_MAIN, rot=TAU / 16)                 # a gear on the dock
            b.line([(-5.6, 4.4, zr), (-6.2, 4.6, zr + 10 + lv)], R_METAL, 1)
            b.ball(-6.2, 4.6, zr + 10.4 + lv, 0.9, R_LITE)
        if lv >= 3:
            s0 = (1.0, -3.2, zr + 0.9)                                                  # second, smaller arm
            s1 = (3.0, -4.6, zr + 4.6)
            s2 = (6.2, -2.2, zr + 2.2)
            b.bar(s0, s1, 0.7, R_METAL, 4)
            b.bar(s1, s2, 0.55, R_MAIN, 4)
            b.ball(s1[0], s1[1], s1[2], 0.9, R_LITE)
            b.ball(s2[0], s2[1], s2[2] - 0.3, 0.7, R_WHITE)
        if lv >= 4:
            b.line([(-5.6, -3.6, zr + 1.0), (1.8, -3.6, zr + 1.0), (1.8, 3.6, zr + 1.0), (-5.6, 3.6, zr + 1.0)], R_ALT, 2, True)
        # the drones
        zd = zm + 4.5
        b.group(M_SPIN | M_BOB, 1.3, 0, 0, zd, 2.4, 0.9)
        nd = (1, 2, 2, 3, 3)[lv]
        for i in range(nd):
            a = i * TAU / nd
            ca, sa = math.cos(a), math.sin(a)
            x, y = ca * 9.8, sa * 9.8
            b.prism(6, x, y, -0.9, 1.9, 1.5, R_METAL, rtop=1.2, rot=a)
            b.ball(x, y, 1.0, 1.0, R_LITE)
            for s in (-1, 1):
                rx, ry = x - sa * 2.9 * s, y + ca * 2.9 * s
                b.line([(x, y, 0.3), (rx, ry, 0.6)], R_METAL, 2)
                b.ring(rx, ry, 0.8, 1.8, R_WHITE, 8, 1)
            b.line([(x, y, -0.9), (x - ca * 0.6, y - sa * 0.6, -2.7)], R_METAL, 1)
            b.ball(x - ca * 0.6, y - sa * 0.6, -2.9, 0.6, R_WHITE)
        if lv >= 4:
            b.ring(0, 0, 0.2, 9.8, R_ALT, 16, 2)
            halo(b, zd + 10, 6.0)


    # ====================================================================== BULWARK
    def tm2_bulwark(b, lv):
        """a spiked rampart across the road (wide along y, spikes facing +x)"""
        b.group(M_AIM)
        wd = 12.5 + lv * 1.0
        h = 14.0 + lv * 1.7
        b.box(0.4, 0, 0, 5.2, wd + 0.4, 2.2, R_BLACK, 0.95)                             # footing
        b.box(-7.4, 0, 0, 1.8, wd * 0.62, 1.4, R_BLACK)
        hull(b, -3.6, 3.4, wd - 1.2, 2.2, h - 2.2, R_DARK, nose=0.8, tail=1.8, topw=wd - 1.6)       # the wall
        hull(b, 3.0, 4.4, wd - 2.3, 3.6, h - 6.6, R_MAIN, nose=0.6, tail=0.0, topw=wd - 2.7)        # armour plate
        b.line([(5.75, -wd + 1.0, 1.2), (5.75, wd - 1.0, 1.2)], R_LITE, 2)
        for s in (-1, 1):                                                             # end pillars
            b.box(0.2, s * wd, 0, 4.4, 1.9, h + 2.0, R_METAL, 0.86)
            b.line([(4.15, s * wd, 2.0), (3.85, s * wd, h)], R_LITE, 2)
            if lv >= 1:
                b.prism(4, 0.2, s * wd, h + 2.0, 2.7, 3.2, R_MAIN, rtop=0, rot=TAU / 8)
            else:
                b.ball(0.2, s * wd, h + 2.9, 1.2, R_WHITE)
        n = (3, 3, 4, 4, 5)[lv]
        step = 2.0 * (wd - 4.6) / (n - 1)
        zs = 3.6 + (h - 6.6) * 0.56
        Ls = 11.5 + lv * 0.7
        for i in range(n):                                                            # the great spikes
            y = (i - (n - 1) / 2.0) * step
            b.bar((4.0, y, zs), (7.6, y, zs), 2.2, R_METAL, 4, 1.45)
            b.bar((7.6, y, zs), (Ls, y, zs), 1.45, R_LITE, 4, 0.1)
            b.line([(4.5, y, zs + 2.2), (4.2, y, h - 3.2)], R_LITE, 1)
        if lv >= 2:
            for i in range(n - 1):                                                    # a lower row of teeth
                y = (i - (n - 2) / 2.0) * step
                b.bar((4.3, y, 5.0), (8.6, y, 4.4), 1.3, R_METAL, 4, 0.1)
        nc = (3, 3, 4, 4, 5)[lv]
        for i in range(nc):                                                           # battlements
            y = (i - (nc - 1) / 2.0) * 2.0 * (wd - 4.8) / (nc - 1)
            b.box(0.4, y, h, 2.1, 1.5, 2.0, R_METAL)
            if lv >= 3:
                b.prism(4, 0.4, y, h + 2.0, 1.2, 2.6, R_LITE, rtop=0, rot=TAU / 8)
        b.line([(2.65, -wd + 2.4, h + 0.1), (2.65, wd - 2.4, h + 0.1)], R_ALT if lv >= 4 else R_LITE, 3 if lv >= 4 else 2)
        nbt = 2 if lv < 3 else 3
        for i in range(nbt):                                                          # buttresses behind
            y = (i - (nbt - 1) / 2.0) * wd * (0.95 if nbt == 2 else 0.62)
            b.bar((-2.4, y, h * 0.74), (-7.6, y, 1.2), 1.3, R_METAL, 4)
        b.line([(-3.6 + 1.8 * 0.72 - 0.12, -wd + 3.0, 2.2 + (h - 2.2) * 0.72), (-3.6 + 1.8 * 0.72 - 0.12, wd - 3.0, 2.2 + (h - 2.2) * 0.72)], R_LITE, 2)   # seam along the back
        if lv >= 1:
            for s in (-1, 1):
                b.ball(4.75, s * (wd - 3.4), h - 3.6, 0.7, R_WHITE)                    # rivet lamps
                b.ball(4.9, s * (wd - 3.4), 4.6, 0.7, R_WHITE)
        if lv >= 4:
            zc = h - 2.6
            b.slab([(4.5, -2.3, zc + 2.2), (4.5, 2.3, zc + 2.2), (4.6, 2.3, zc), (4.7, 0, zc - 2.4), (4.6, -2.3, zc)], R_ALT)      # crest
            b.ring(0, 0, 0.6, wd + 3.0, R_ALT, 16, 2)
            halo(b, h + 11, 6.0)


    # ====================================================================== HYDRA
    def _aimed(el, yaw, c):
        """a point-maker for something that points up by `el` and sideways by `yaw` from the middle c: P(along, across, up)"""
        ca, sa, cy, sy = math.cos(el), math.sin(el), math.cos(yaw), math.sin(yaw)

        def P(t, s=0.0, u=0.0):
            return (c[0] + ca * cy * t - sy * s - sa * cy * u, c[1] + ca * sy * t + cy * s - sa * sy * u, c[2] + sa * t + ca * u)
        return P


    def _pod(b, c, el, yaw, hl, hs):
        """one rocket pod: a square box pointing up and forward with four rockets in its mouth"""
        P = _aimed(el, yaw, c)
        b.bar(P(-hl), P(hl), hs * 1.414, R_MAIN, 4)
        b.bar(P(hl - 0.5), P(hl + 0.8), (hs + 0.4) * 1.414, R_DARK, 4)
        q = hs * 0.5
        for sd in (-q, q):
            for u in (-q, q):
                x, y, zz = P(hl + 0.95, sd, u)
                b.ball(x, y, zz, q * 0.66, R_LITE)
                b.ring(x, y, zz, q * 0.92, R_WHITE, 8, 1, math.pi / 2 - el, math.pi / 2 + yaw)
        for sd in (-1, 1):
            b.line([P(-hl, sd * hs, hs + 0.1), P(hl - 0.6, sd * hs, hs + 0.1)], R_LITE, 2)
        b.line([P(-hl * 0.45, -hs, hs + 0.1), P(-hl * 0.45, hs, hs + 0.1)], R_BLACK, 2)
        x, y, zz = P(-hl - 0.3)
        b.ball(x, y, zz, hs * 0.55, R_LITE)                                            # exhaust


    def tm2_hydra(b, lv):
        """a missile battery: rocket pods fanned out like heads, heavy rockets on the outriggers"""
        z = pad2(b, lv, 13)
        lathe(b, 0, 0, [(6.6, z), (5.4, z + 2.2)], 8, R_METAL, TAU / 16)
        x, y, _ = _pol(TAU / 4 + 0.5, 10.2)                                           # a spare rocket on the deck
        b.prism(6, x, y, 3.4, 1.2, 3.4 + lv * 0.3, R_METAL)
        b.prism(6, x, y, 6.8 + lv * 0.3, 1.2, 2.0, R_LITE, rtop=0)
        if lv >= 3:
            x, y, _ = _pol(TAU / 4 + 1.2, 10.4)
            b.ball(x, y, 4.4, 1.3, R_LITE)
            b.ball(x + 1.6, y + 1.5, 4.3, 1.1, R_METAL)
        z += 2.2
        b.group(M_AIM | M_RECOIL)
        b.prism(8, 0, 0, z, 7.0, 1.6, R_BLACK, rtop=6.2, rot=TAU / 16)
        zt = z + 1.6
        hull(b, -4.2, 4.4, 3.4, zt, 4.2, R_MAIN, nose=1.4, tail=3.0, topw=2.6)        # pedestal
        b.line([(4.5, -2.7, zt + 1.5), (4.5, 2.7, zt + 1.5)], R_LITE, 2)
        b.ball(3.75, 0, zt + 3.0, 0.9, R_WHITE)
        pods = (1, 1, 2, 2, 3)[lv]
        hs = 2.6
        lay = {1: ((0.0, 0.0, 0.0),), 2: ((-3.9, -0.14, 0.0), (3.9, 0.14, 0.0)), 3: ((-6.9, -0.2, 0.0), (0.0, 0.0, 1.7), (6.9, 0.2, 0.0))}[pods]
        W = abs(lay[0][0]) + hs
        yw = abs(lay[0][1])
        Wb = W + (2.9 if lv >= 1 else 0.5)
        b.box(0.8, 0, zt + 4.2, 1.6, Wb, 1.4, R_DARK)                                  # cross beam
        el = 0.5
        zp = zt + 8.4
        for o, yaw, up in lay:
            _pod(b, (0.5, o, zp + up), el, yaw, 7.8, hs)
            if up:
                b.box(0.8, 0, zt + 5.6, 1.2, 2.2, 1.7, R_METAL)
        if lv >= 1:
            for s in (-1, 1):                                                          # heavy rockets outboard
                P = _aimed(el, s * yw, (0.9, s * (W + 1.9), zt + 6.4))
                b.bar(P(-5.6), P(3.6), 1.5, R_METAL, 4)
                b.bar(P(3.6), P(6.4), 1.5, R_LITE, 4, 0.1)
                for sd in (-1, 1):
                    b.line([P(-3.6, sd * 1.0, 0), P(-5.8, sd * 2.3, 0), P(-5.6, sd * 1.0, 0)], R_LITE, 2)
                x, y, zz = P(-5.9)
                b.ball(x, y, zz, 0.8, R_WHITE)
        if lv >= 2:
            b.box(-3.3, 0, zt, 1.3, 2.6, 2.2, R_DARK)                                  # fire control
            b.line([(-4.65, -1.9, zt + 1.5), (-4.65, 1.9, zt + 1.5)], R_LITE, 2)
            b.line([(0.5, 0, zp + 2.7 + lay[len(lay) // 2][2] * (pods == 3)), (-0.8, 0, zp + 10.0)], R_METAL, 1)
            b.ball(-0.8, 0, zp + 10.3, 0.85, R_LITE)
        if lv >= 3:
            b.slab([(-8.0, -W - 0.4, zp - 5.8), (-8.0, W + 0.4, zp - 5.8), (-10.6, W + 0.4, zp + 0.6), (-10.6, -W - 0.4, zp + 0.6)], R_METAL)    # blast shield
            for f in (-0.5, 0.0, 0.5):                                                 # its ribs
                b.line([(-8.12, f * (W + 0.4), zp - 5.5), (-10.6, f * (W + 0.4), zp + 0.3)], R_BLACK, 2)
            b.line([(-9.42, -W - 0.1, zp - 2.6), (-9.42, W + 0.1, zp - 2.6)], R_LITE, 2)
            b.line([(-8.0, -W - 0.4, zp - 5.8), (-5.4, -W + 1.2, zt + 0.2)], R_METAL, 2)
            b.line([(-8.0, W + 0.4, zp - 5.8), (-5.4, W - 1.2, zt + 0.2)], R_METAL, 2)
            b.glow(0.5 + math.cos(el) * 9.0, 0, zp + math.sin(el) * 9.0, 9, R_LITE, 0.45)
        if lv >= 4:
            b.line([(-10.65, -W - 0.4, zp + 0.6), (-10.65, W + 0.4, zp + 0.6)], R_ALT, 3)
            b.ring(0, 0, zt - 0.2, 7.4, R_ALT, 16, 2)
            halo(b, zp + 15.5, 8.5)


    # ====================================================================== BEACON
    def tm2_beacon(b, lv):
        """a striped lighthouse mast; the lantern head and its radar dishes turn"""
        z = pad2(b, lv, 11.5)
        lathe(b, 0, 0, [(5.8, z), (4.6, z + 2.4), (3.6, z + 3.4)], 8, [R_DARK, R_MAIN], TAU / 16)
        zb = z + 3.4
        H = 14.0 + lv * 2.6
        ns = (2, 2, 3, 4, 4)[lv]
        for i in range(ns):                                                           # the striped mast
            f0, f1 = i / float(ns), (i + 1) / float(ns)
            b.prism(6, 0, 0, zb + H * f0, 3.4 - 1.3 * f0, H * (f1 - f0), R_MAIN if i % 2 else R_DARK, rtop=3.4 - 1.3 * f1)
            if i:
                b.ring(0, 0, zb + H * f0, 3.5 - 1.3 * f0, R_ALT if lv >= 4 else R_LITE, 6, 2)
        nf = 3
        for i in range(nf):                                                           # buttress fins
            a = TAU / 12 + i * TAU / nf
            rf = 8.8 if lv < 3 else 7.3
            b.slab([_pol(a, 3.4, zb - 0.6), _pol(a, rf, z), _pol(a, 2.9, zb + 5.0 + lv)], R_METAL)
            b.ball(math.cos(a) * rf, math.sin(a) * rf, z + 0.6, 0.8, R_WHITE)
        zt = zb + H
        b.prism(6, 0, 0, zt, 2.5, 1.0, R_DARK, rtop=4.8)                                # gallery
        b.ring(0, 0, zt + 1.9, 4.8, R_METAL, 12, 1)
        for i in range(6):
            x, y, _ = _pol(i * TAU / 6, 4.8)
            b.line([(x, y, zt + 1.0), (x, y, zt + 1.9)], R_METAL, 1)
        if lv >= 2:
            for i in range(4):                                                        # guy wires
                a = i * TAU / 4
                x, y, _ = _pol(a, 10.6)
                b.prism(4, x, y, 3.4, 1.3, 1.6, R_METAL, rtop=0, rot=a)
                b.line([(x, y, 4.6), (math.cos(a) * 2.5, math.sin(a) * 2.5, zb + H * 0.72)], R_METAL, 1)
        # the lantern head turns
        zl = zt + 1.0
        b.group(M_SPIN, 1.1, 0, 0, zl)
        b.prism(6, 0, 0, 0, 2.8, 3.4, R_WHITE)
        b.prism(6, 0, 0, 3.4, 3.9, 2.6, R_MAIN, rtop=0)
        b.glow(0, 0, 1.7, 13 + lv * 2, R_LITE, 0.7)

        def dish(sg, k):
            x0 = sg * 6.6
            b.line([(sg * 2.6, 0, 1.7), (x0, 0, 1.7)], R_METAL, 3)
            b.bar((x0, 0, 1.7), (x0 + sg * 1.8 * k, 0, 1.7), 0.8, R_MAIN, 6, 3.7 * k)
            b.line([(x0 + sg * 1.8 * k, 0, 1.7), (x0 + sg * 4.0 * k, 0, 1.7)], R_METAL, 1)
            b.ball(x0 + sg * 4.2 * k, 0, 1.7, 0.85, R_LITE)
        dish(1, 1.0 + lv * 0.06)
        if lv >= 1:
            dish(-1, 0.8)
        else:
            b.line([(-2.6, 0, 1.7), (-5.6, 0, 1.7)], R_METAL, 3)
            b.ball(-6.0, 0, 1.7, 1.3, R_METAL)
        if lv < 3:
            b.line([(0, 0, 6.0), (0, 0, 8.8)], R_METAL, 1)
            b.ball(0, 0, 9.1, 0.8, R_LITE)
        else:
            b.crystal(0, 0, 6.2, 1.8, 4.8, R_LITE, 4)                                  # the eye that unmasks phantoms
            b.ring(0, 0, 1.7, 9.5 + lv * 0.5, R_WHITE, 16, 1, 0.5)
            b.glow(0, 0, 8.3, 7, R_WHITE, 0.6)
        if lv >= 4:
            b.ring(0, 0, 3.5, 4.1, R_ALT, 12, 2)
            halo(b, zl + 16, 7.0)


    # ====================================================================== REACTOR
    def tm2_reactor(b, lv):
        """a containment cage on the road with the core burning inside it"""
        b.group(M_AIM)
        R = 11.0 + lv * 0.5
        lathe(b, 0, 0, [(R, 0), (R, 1.6), (R - 2.2, 2.8)], 8, [R_BLACK, R_DARK], TAU / 16)
        b.ring(0, 0, 1.75, R + 0.25, R_ALT if lv >= 4 else R_LITE, 16, 2 if lv >= 4 else 1)
        b.prism(8, 0, 0, 2.8, 5.2, 2.0, R_METAL, rtop=3.8, rot=TAU / 16)               # emitter socket
        b.ring(0, 0, 4.9, 3.9, R_LITE, 12, 2)
        zc = 12.0 + lv * 1.0
        rc = 4.4 + lv * 0.6
        cap = lv >= 2
        ztop = zc + rc + (3.4 if cap else 2.0)
        for i in range(4):                                                            # the cage
            a = TAU / 8 + i * TAU / 4
            x, y, _ = _pol(a, R - 2.5)
            b.box(x, y, 1.6, 2.0, 1.5, 2.6, R_METAL, 0.8, a)
            e = _pol(a, rc + 5.0, zc)
            t = _pol(a, 3.0 if cap else rc + 1.2, ztop)
            b.bar(_pol(a, R - 2.7, 3.8), e, 1.25, R_METAL, 4)
            b.bar(e, t, 1.0, R_MAIN, 4, 0.5)
            b.ball(e[0], e[1], e[2], 1.3, R_LITE)
            if not cap:
                b.ball(t[0], t[1], t[2] + 0.3, 0.9, R_WHITE)
        for i in range(2 if lv < 1 else 4):                                           # coolant vents
            a = TAU / 4 + i * (TAU / 2 if lv < 1 else TAU / 4)
            x, y, _ = _pol(a, R - 3.3)
            b.box(x, y, 1.6, 1.5, 2.5, 2.8, R_DARK, 0.8, a)
            b.line([_pol(a - 0.2, R - 2.0, 3.6), _pol(a + 0.2, R - 2.0, 3.6)], R_LITE, 2)
        if cap:
            b.prism(8, 0, 0, ztop - 0.5, 3.8, 1.4, R_DARK, rtop=3.0, rot=TAU / 16)
            b.prism(6, 0, 0, ztop - 2.3, 0.5, 1.8, R_LITE, rtop=2.2)
            b.ball(0, 0, ztop + 1.5, 1.1, R_WHITE)
        if lv >= 3:
            b.ring(0, 0, zc, rc + 5.0, R_ALT if lv >= 4 else R_METAL, 16, 2)             # hoop
            for i in range(4):                                                        # fuel rods
                a = i * TAU / 4
                x, y, _ = _pol(a, R - 6.2)
                b.prism(6, x, y, 2.8, 0.9, 2.6 + (i % 2) * 0.8, R_LITE)
        if lv >= 4:
            b.prism(4, 0, 0, ztop + 0.9, 1.3, 3.4, R_ALT, rtop=0)
        # the core
        b.group(M_BOB, 0, 0, 0, zc, 3.0, 0.8)
        b.ball(0, 0, 0, rc, R_LITE)
        b.ball(0, 0, 0, rc * 0.55, R_WHITE)
        b.glow(0, 0, 0, 19 + lv * 2, R_LITE, 0.9)
        if lv >= 1:
            b.ring(0, 0, 0, rc + 0.5, R_WHITE, 12, 1, math.pi / 2, 0.4)
            b.ring(0, 0, 0, rc + 0.5, R_WHITE, 12, 1, math.pi / 2, 0.4 + math.pi / 2)
        # the rings
        b.group(M_SPIN, 2.0, 0, 0, zc)
        r1 = rc + 3.4
        b.ring(0, 0, 0, r1, R_WHITE, 16, 2, 0.5)
        if lv >= 1:
            b.ball(r1, 0, 0, 0.9, R_WHITE)
            b.ball(-r1, 0, 0, 0.9, R_WHITE)
        if lv >= 2:
            b.ring(0, 0, 0, r1 + 1.3, R_MAIN, 16, 1, -0.9, 1.3)
        if lv >= 3:
            for i in range(3):
                x, y, _ = _pol(i * TAU / 3 + 0.5, r1 + 2.6)
                b.crystal(x, y, -1.8 + i * 0.9, 1.0, 3.4, R_WHITE, 4)
        if lv >= 4:
            b.ring(0, 0, 0, r1 + 2.6, R_ALT, 16, 2, 1.3, 2.2)
            halo(b, ztop + 9, 6.0)


    # ====================================================================== COMMANDER
    def tm2_commander(b, lv):
        """a command bunker: war banner, drum, horns and aerials, with the star turning on top of the standard"""
        z = pad2(b, lv, 13)
        H = 5.0 + lv * 0.5
        hull(b, -6.4, 6.4, 5.8, z, H, R_DARK, nose=1.6, tail=1.6, topw=4.7)           # the bunker
        zr = z + H
        b.box(0, 0, zr, 4.5, 4.3, 1.2, R_MAIN, 0.92)
        zt = zr + 1.2
        b.line([(6.4 - 1.6 * 0.6 + 0.12, -3.6, z + H * 0.6), (6.4 - 1.6 * 0.6 + 0.12, 3.6, z + H * 0.6)], R_LITE, 3)     # vision slit
        for sx in (-1, 1):
            for sy in (-1, 1):                                                        # corner bastions
                b.box(sx * 6.3, sy * 5.6, min(z, 4.9), 1.6, 1.6, z + H + 0.9 - min(z, 4.9), R_METAL, 0.84)
                if lv >= 3:
                    b.ball(sx * 6.3, sy * 5.6, z + H + 1.7, 1.15, R_LITE)
        px = -2.0
        fh = zt + 13.0 + lv * 1.7
        b.bar((px, 0, zt), (px, 0, fh), 0.7, R_METAL, 4)                               # the standard
        bw = 9.0 + lv * 0.8
        wv = [(px, 0.5), (px - 1.3, bw * 0.5), (px + 0.5, bw)]                          # the banner waves: two panels
        b.slab([(wv[0][0], wv[0][1], fh - 0.5), (wv[1][0], wv[1][1], fh - 1.0), (wv[1][0], wv[1][1], fh - 7.3), (wv[0][0], wv[0][1], fh - 7.5)], R_LITE)
        b.slab([(wv[1][0], wv[1][1], fh - 1.0), (wv[2][0], wv[2][1], fh - 1.5), (wv[2][0] - 0.9, wv[2][1] - 2.4, fh - 4.3), (wv[2][0], wv[2][1], fh - 7.1),
                (wv[1][0], wv[1][1], fh - 7.3)], R_LITE)
        for dx in (-0.2, 0.2):
            for dz in (0.0, 1.9):
                b.line([(px - 0.35 + dx, 1.4, fh - 6.1 + dz), (px - 0.8 + dx, 2.8, fh - 3.9 + dz), (px - 1.15 + dx, 4.0, fh - 6.1 + dz)], R_BLACK, 2)
        if lv >= 4:
            for dx in (-0.2, 0.2):
                b.line([(wv[0][0] + dx, wv[0][1], fh - 0.5), (wv[1][0] + dx, wv[1][1], fh - 1.0), (wv[2][0] + dx, wv[2][1], fh - 1.5), (wv[2][0] - 0.9 + dx, wv[2][1] - 2.4, fh - 4.3),
                        (wv[2][0] + dx, wv[2][1], fh - 7.1), (wv[1][0] + dx, wv[1][1], fh - 7.3), (wv[0][0] + dx, wv[0][1], fh - 7.5)], R_ALT, 2)
        # war drum
        dxp, dyp = 2.5, 1.7
        b.prism(8, dxp, dyp, zt, 2.7, 2.4, [R_WHITE] + [R_METAL] * 8, rot=TAU / 16)
        b.ring(dxp, dyp, zt + 2.45, 2.8, R_LITE, 10, 2)
        b.line([(dxp + 0.6, dyp - 0.4, zt + 2.7), (dxp + 2.6, dyp - 2.4, zt + 4.9)], R_METAL, 2)
        b.ball(dxp + 0.6, dyp - 0.4, zt + 2.9, 0.65, R_LITE)
        # horn
        def horn(sy):
            p0 = (1.6, sy * 2.6, zt + 0.9)
            p1 = (6.8, sy * 4.9, zt + 3.8)
            b.bar(p0, p1, 0.55, R_METAL, 6, 2.3)
            b.ball(p1[0] + 0.3, p1[1] + sy * 0.12, p1[2] + 0.15, 1.5, R_LITE)
            b.line([(p0[0], p0[1], zt), p0], R_METAL, 2)
        horn(-1)
        if lv >= 1:
            b.line([(-6.3, -5.6, z + H + 0.9), (-6.9, -5.9, z + H + 10.0 + lv)], R_METAL, 1)        # aerial
            b.ball(-6.9, -5.9, z + H + 10.3 + lv, 0.8, R_LITE)
            b.box(-2.6, -2.6, zt, 1.3, 1.1, 1.7, R_DARK)                                              # radio set
            b.ball(-1.9, -3.7, zt + 1.0, 0.5, R_WHITE)
        if lv >= 2:
            b.prism(6, px, 0, zt, 2.1, 2.2, R_METAL, rtop=1.3)                                       # standard socket
            b.slab([(px, -0.5, fh - 8.6), (px, -6.8 - lv * 0.6, fh - 9.4), (px, -6.8 - lv * 0.6, fh - 12.4), (px, -0.5, fh - 12.0)], R_MAIN)
            b.line([(-6.3, 5.6, z + H + 0.9), (-6.6, 5.9, z + H + 7.0)], R_METAL, 1)
            b.slab([(-6.0, 4.6, z + H + 6.0), (-7.6, 6.4, z + H + 6.0), (-8.2, 7.0, z + H + 8.4), (-6.6, 5.2, z + H + 8.4)], R_METAL)   # dish
            b.ball(-5.9, 6.6, z + H + 7.6, 0.6, R_LITE)
        if lv >= 3:
            horn(1)
            b.prism(8, 2.6, -1.9 + 0.0, zt, 1.5, 1.6, [R_WHITE] + [R_METAL] * 8, rot=TAU / 16)        # second drum
            b.slab([(px, 0.5, fh + 0.2), (px, 5.0, fh + 0.9), (px, 0.5, fh + 1.6)], R_WHITE)          # pennant
        if lv >= 4:
            b.line([(-4.1, -3.9, zt + 0.1), (4.1, -3.9, zt + 0.1), (4.1, 3.9, zt + 0.1), (-4.1, 3.9, zt + 0.1)], R_ALT, 2, True)
        # the star
        r = 3.2 + lv * 0.4
        b.group(M_SPIN, 1.0, px, 0, fh + (2.0 if lv >= 3 else 0.6) + r)
        b.slab([(math.cos(i * math.pi / 5 + math.pi / 2) * (r if i % 2 == 0 else r * 0.45), 0,
                 math.sin(i * math.pi / 5 + math.pi / 2) * (r if i % 2 == 0 else r * 0.45)) for i in range(10)], R_ALT if lv >= 4 else R_LITE)
        b.glow(0, 0, 0, 9 + lv, R_LITE, 0.5)
        if lv >= 2:
            b.ring(0, 0, 0, r + 1.6, R_ALT if lv >= 4 else R_LITE, 12, 1 + (lv >= 4))
        if lv >= 4:
            halo(b, fh + 2.0 + 2 * r + 5.5, 7.0)


    TOWERS2A = {"blade": tm2_blade, "scatter": tm2_scatter, "harvester": tm2_harvester, "sentinel": tm2_sentinel, "mechanic": tm2_mechanic,
                "bulwark": tm2_bulwark, "hydra": tm2_hydra, "beacon": tm2_beacon, "reactor": tm2_reactor, "commander": tm2_commander}
    return TOWERS2A


def _mk2_towers_b():
    # NEON BASTION mk II models, set B: graviton, prism, annihilator, the event towers (pumpkin, snow, duck, toaster, cat,
    # stonks, brick), the new SUMMONER tower and the goon it sends out.
    # Same builder and same rules as c_models.py (the style guide):  tm2_<kind>(b, lv)  with lv 0..4,  gm2_goon(b, lv) -> (top, hx, hr)

    M_STEP, M_STRIKE = 16, 32

    # fixed colours of the event towers (the same ones the old models use)
    DUCK_Y, DUCK_Y2, DUCK_O = (255, 214, 40), (238, 184, 24), (255, 150, 30)
    PUMP_O, PUMP_G, PUMP_Y, WITCH = (255, 128, 22), (70, 170, 60), (255, 232, 90), (120, 60, 190)
    SNOW_W, CARROT, RED, COAL = (236, 244, 255), (255, 140, 30), (230, 40, 60), (16, 16, 24)
    TOAST, CRUST, BURNT = (232, 186, 112), (150, 92, 44), (70, 44, 30)
    CAT_G, CAT_W, CAT_P, CAT_S = (156, 156, 172), (236, 236, 244), (255, 130, 170), (104, 104, 124)
    STONK_G, STONK_R = (60, 235, 130), (255, 70, 90)
    BRICK_C, BRICK_K, BRICK_SCREEN, BRICK_INK = (70, 84, 112), (176, 186, 206), (150, 230, 130), (26, 60, 34)
    WOOD, WAX, FLAME, VOID, WATER, BUBBLE = (120, 84, 50), (236, 230, 210), (255, 214, 90), (10, 6, 24), (60, 160, 250), (200, 236, 255)
    RAINBOW = ((255, 70, 70), (255, 170, 50), (255, 240, 80), (90, 255, 140), (80, 170, 255), (190, 110, 255))


    # ====================================================================== helpers
    def xring(b, x, y, z, r, role, n=10, width=2):
        """a ring standing in the y-z plane (round a barrel)"""
        b.ring(x, y, z, r, role, n, width, math.pi / 2, math.pi / 2)


    def ext(b, axis, pts, a0, a1, role, caps=None, k=1.0, cap0=True, cap1=True, skip=(), edge=True):
        """push a flat convex outline along an axis.  axis "x": pts are (y, z);  "y": (x, z);  "z": (x, y).
        k shrinks the far end, skip = numbers of the side faces to leave out (the one nobody sees)"""
        n = len(pts)
        cu, cv = sum(p[0] for p in pts) / float(n), sum(p[1] for p in pts) / float(n)

        def V(u, v, a):
            return (a, u, v) if axis == "x" else (u, a, v) if axis == "y" else (u, v, a)
        vs = [V(u, v, a0) for u, v in pts] + [V(cu + (u - cu) * k, cv + (v - cv) * k, a1) for u, v in pts]
        fs, rs = [], []
        for i in range(n):
            if i not in skip:
                fs.append((i, (i + 1) % n, n + (i + 1) % n, n + i))
                rs.append(role)
        cr = role if caps is None else caps
        if cap0:
            fs.append(tuple(range(n - 1, -1, -1)))
            rs.append(cr)
        if cap1:
            fs.append(tuple(range(n, 2 * n)))
            rs.append(cr)
        b.mesh(vs, fs, rs, edge)


    def blob(b, x, y, z, rx, ry, rz, role, n=6, lats=(0.85, 1.65, 2.5), rot=0.0, edge=True):
        """a low-poly egg round (x, y, z), open underneath: n * len(lats) faces"""
        vs = [(x, y, z + rz)]
        for la in lats:
            s, c = math.sin(la), math.cos(la)
            for i in range(n):
                a = rot + i * TAU / n
                vs.append((x + math.cos(a) * rx * s, y + math.sin(a) * ry * s, z + rz * c))
        fs = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
        for j in range(len(lats) - 1):
            o = 1 + j * n
            fs += [(o + i, o + (i + 1) % n, o + n + (i + 1) % n, o + n + i) for i in range(n)]
        b.mesh(vs, fs, role, edge)


    def plate(b, pts, role, facing, edge=True):
        """a flat shape that lies against something, so only one side is ever seen: ONE face, looking the way `facing` points"""
        a, c, d = pts[0], pts[1], pts[2]
        u, v = (c[0] - a[0], c[1] - a[1], c[2] - a[2]), (d[0] - a[0], d[1] - a[1], d[2] - a[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if n[0] * facing[0] + n[1] * facing[1] + n[2] * facing[2] < 0:
            pts = pts[::-1]
        b.mesh(list(pts), [tuple(range(len(pts)))], role, edge, False, False)


    def xgem(b, x0, xm, x1, y, z, r, role, n=4, rot=0.0):
        """a gem lying along x"""
        vs = [(xm, y + math.cos(rot + i * TAU / n) * r, z + math.sin(rot + i * TAU / n) * r) for i in range(n)] + [(x1, y, z), (x0, y, z)]
        b.mesh(vs, [(i, (i + 1) % n, n) for i in range(n)] + [(i, (i + 1) % n, n + 1) for i in range(n)], role)


    def flame(b, x, y, z, r, h, glow=True):
        b.crystal(x, y, z, r, h, R_LITE, 4, 0.6, 0.3)
        b.ball(x, y, z + h * 0.3, r * 0.55, R_WHITE)
        if glow:
            b.glow(x, y, z + h * 0.4, r * 3.4, R_LITE, 0.6)


    # ====================================================================== GRAVITON
    def tm2_graviton(b, lv):
        """a gravity engine: a singularity with its accretion disc, held over a well by claw pylons"""
        z = pad2(b, lv, 13)
        # the well
        lathe(b, 0, 0, [(4.4, z), (5.4, z + 1.5), (8.4, z + 3.0)], 8, [R_DARK, R_MAIN], TAU / 16)
        zt = z + 3.0
        b.slab([(math.cos(i * TAU / 8 + TAU / 16) * 7.3, math.sin(i * TAU / 8 + TAU / 16) * 7.3, zt + 0.06) for i in range(8)], VOID, False)
        for r_, w in ((5.6, 1), (3.6, 1), (1.7, 2)):
            b.ring(0, 0, zt + 0.12, r_, R_LITE, 12, w)
        b.glow(0, 0, zt + 0.5, 9, R_LITE, 0.45)
        # the pylons
        n = 3 + (lv >= 2) + (lv >= 4)
        H = 8.0 + lv * 1.0
        zs = z + 14.5 + lv * 1.3
        rs = 4.2 + lv * 0.45
        for i in range(n):
            a = i * TAU / n + (math.pi if n % 2 else TAU / 8)
            ca, sa = math.cos(a), math.sin(a)
            b.box(ca * 10.8, sa * 10.8, z - 1.0, 1.5, 1.9, H + 1.0, R_METAL, 0.62, a)
            b.bar((ca * 10.8, sa * 10.8, z + H - 0.4), (ca * 7.4, sa * 7.4, z + H + 3.4), 1.25, R_MAIN, 4, 0.35)
            b.ball(ca * 7.2, sa * 7.2, z + H + 3.7, 0.9, R_WHITE)
            b.line([(ca * 11.3, sa * 11.3, z + 0.6), (ca * 11.0, sa * 11.0, z + H - 1.2)], R_LITE, 2)
            if lv >= 1:
                b.line([(ca * 7.0, sa * 7.0, z + H + 3.8), (ca * (rs + 0.6), sa * (rs + 0.6), zs - 0.5)], R_LITE, 1)
        # the singularity
        b.group(M_SPIN | M_BOB, -1.4, 0, 0, zs, 1.7, 1.0)
        tl = 0.30
        ct, st = math.cos(tl), math.sin(tl)

        def D(a, r_):
            return (math.cos(a) * r_, math.sin(a) * r_ * ct, math.sin(a) * r_ * st)
        r0, r1 = rs + 1.5, rs + 4.4 + lv * 0.25
        for i in range(6):                                    # the accretion disc, in six plates so it goes round the ball properly
            a0, a1 = i * TAU / 6, (i + 1) * TAU / 6
            b.slab([D(a0, r0), D(a1, r0), D(a1, r1), D(a0, r1)], R_LITE)
        b.ball(0, 0, 0, rs, VOID)
        b.ring(0, 0, 0, rs + 0.9, R_WHITE, 12, 2, tl)
        b.glow(0, 0, 0, rs * 3.4, R_LITE, 0.5)
        if lv >= 1:
            b.ring(0, 0, 0, rs + 6.4, R_MAIN, 14, 1, -0.75, 1.0)
            b.ball(math.cos(1.0) * (rs + 6.4), math.sin(1.0) * (rs + 6.4), 0, 1.0, R_WHITE)
        if lv >= 2:                                           # captured rocks
            for i in range(2 + (lv >= 4)):
                a = 0.5 + i * TAU / (2 + (lv >= 4))
                b.crystal(math.cos(a) * (rs + 7.2), math.sin(a) * (rs + 7.2), -2.4 + i * 1.6, 1.3, 3.0, R_METAL, 4, a, 0.4)
        if lv >= 3:
            b.ring(0, 0, 0, rs + 5.6, R_WHITE, 14, 1, 1.15, 2.2)
        if lv >= 4:
            b.ring(0, 0, 0, rs + 8.2, R_ALT, 16, 2, 0.16)
            halo(b, zs + rs + 8.5, 7.5)


    # ====================================================================== PRISM
    def tm2_prism(b, lv):
        """white light in, a rainbow out of the prism, one hot beam out of the lens"""
        z = pad2(b, lv, 12, 6)
        zh = z + 8.4 + lv * 0.4                                # top of the tripod
        for i in range(3):
            a = i * TAU / 3 + math.pi
            ca, sa = math.cos(a), math.sin(a)
            b.bar((ca * 9.6, sa * 9.6, z - 0.9), (ca * 2.2, sa * 2.2, zh - 1.2), 1.1, R_METAL, 4)
            b.ball(ca * 9.6, sa * 9.6, z + 0.3, 1.5, R_DARK)
        lathe(b, 0, 0, [(3.3, zh - 3.4), (2.5, zh)], 6, R_DARK)
        b.ring(0, 0, zh - 3.3, 4.0, R_LITE, 12, 1)
        # the head: a turntable with the lamp behind, THE prism in the middle and the lens in front
        b.group(M_AIM)
        pr = 4.3 + lv * 0.3                                    # the prism: a triangle standing up, one corner to the lamp
        ph = 7.6 + lv * 0.5
        zp = zh + 1.9
        top = zp + ph + 1.0                                    # the highest part sits just over the prism ...
        zl = top / 1.21                                        # ... which puts the beam (it leaves at 0.55 x model top) here: through the lens
        b.prism(8, 0, 0, zh, 4.9 + lv * 0.2, 1.1, R_MAIN, rot=TAU / 16)
        b.prism(3, 0, 0, zh + 1.1, pr + 0.9, 0.8, R_ALT if lv >= 4 else R_DARK, rot=math.pi)
        tri = [(-pr, 0.0), (pr * 0.5, -pr * 0.866), (pr * 0.5, pr * 0.866)]
        ext(b, "z", tri, zp, zp + ph, R_LITE, R_WHITE, k=0.86, cap0=False)
        xf = pr * 0.5 * (1.0 - 0.14 * (zl - zp) / ph) + 0.1    # its front face, at the height of the beam

        def G(f, u, t, d=0.1):
            """a point on side f of the prism (0 and 2 meet at the lamp, 1 is the front): u along it, t up it"""
            (u0, v0), (u1, v1) = tri[f], tri[(f + 1) % 3]
            k_ = 1.0 - 0.14 * t
            nx, ny = (-0.5, -0.866) if f == 0 else (1.0, 0.0) if f == 1 else (-0.5, 0.866)
            return ((u0 + (u1 - u0) * u) * k_ + nx * d, (v0 + (v1 - v0) * u) * k_ + ny * d, zp + ph * t)
        for f in range(3):                                     # light catching in the glass
            b.line([G(f, 0.20, 0.62), G(f, 0.42, 0.90)], R_WHITE, 2)
            b.line([G(f, 0.30, 0.58), G(f, 0.46, 0.78)], R_WHITE, 1)
        # lamp house behind it, on its arm
        xb = -pr - 3.4
        b.bar((-2.6, 0, zh + 0.6), (xb, 0, zl - 2.2), 0.8, R_METAL, 4)
        b.box(xb, 0, zl - 2.0, 1.9, 2.3, 4.0, R_DARK, 0.9)
        b.ball(xb + 1.9, 0, zl, 1.1, R_WHITE)
        b.line([(xb + 2.2, 0, zl), (-pr * (1.0 - 0.14 * (zl - zp) / ph) + 0.3, 0, zl)], R_WHITE, 2)
        # the rainbow and the lens that pulls it together again
        xl = pr * 0.5 + 7.2 + lv * 0.2
        lr = 2.5 + lv * 0.2
        for i, c in enumerate(RAINBOW):
            b.line([(xf, (i - 2.5) * 0.25, zl), (xl - 0.2, (i - 2.5) * lr * 0.32, zl + (i - 2.5) * lr * 0.1)], c, 2)
        b.bar((3.4, 0, zh + 0.6), (xl + 0.4, 0, zl - lr - 0.4), 0.8, R_METAL, 4)
        b.bar((xl, 0, zl), (xl + 1.1, 0, zl), lr, R_WHITE, 6, rot=TAU / 12)
        xring(b, xl + 0.5, 0, zl, lr + 0.7, R_LITE, 12, 2)
        xe = xl + 1.1
        if lv < 2:                                             # a spark of light over the prism
            b.ball(0, 0, top, 0.9, R_WHITE)
            b.glow(0, 0, top, 4, R_LITE, 0.6)
        if lv >= 1:                                            # a second, tighter lens on two rails
            xe = xl + 4.6
            b.bar((xe - 1.0, 0, zl), (xe, 0, zl), lr * 0.62, R_LITE, 6, rot=TAU / 12)
            for s in (-1, 1):
                b.line([(xl + 0.6, s * (lr + 0.2), zl), (xe - 0.5, s * (lr * 0.62 + 0.3), zl)], R_ALT if lv >= 4 else R_METAL, 2)
            b.line([(xl + 1.1, 0, zl), (xe - 1.0, 0, zl)], R_WHITE, 1)
        if lv >= 3:                                            # cooling fins: it runs hot
            for i in range(3):
                y = (i - 1) * 1.5
                b.slab([(xb - 1.6, y, zl - 1.4), (xb - 1.6, y, zl + 2.2), (xb - 4.2 - (i == 1) * 1.2, y, zl + 3.6), (xb - 3.4, y, zl - 0.6)], R_LITE if i == 1 else R_MAIN)
            xring(b, xe + 2.4, 0, zl, lr * 0.5, R_WHITE, 8, 2)
            b.glow(xe + 1.0, 0, zl, 8, R_LITE, 0.6)
        if lv >= 4:
            for u, v in tri:                                   # gold on the edges of the prism
                b.line([(u * 1.02, v * 1.02, zp), (u * 0.88, v * 0.88, zp + ph)], R_ALT, 2)
            xring(b, xl + 0.5, 0, zl, lr + 1.3, R_ALT, 12, 2)
            b.glow(0, 0, zl, 9, R_LITE, 0.5)
            halo(b, top, pr + 3.4, 4)
        elif lv >= 2:                                          # shards of light circling over it
            b.group(M_SPIN | M_BOB, 1.4, 0, 0, top, 2.0, 0.5)
            ns = 2 + (lv >= 3)
            for i in range(ns):
                a = i * TAU / ns
                b.crystal(math.cos(a) * (pr + 1.6), math.sin(a) * (pr + 1.6), -2.2, 1.2, 4.4, R_WHITE, 3, a)
            b.ring(0, 0, 0, pr + 1.6, R_LITE, 14, 1)


    # ====================================================================== ANNIHILATOR
    def tm2_annihilator(b, lv):
        """THE BIG GUN.  Its footprint is 19, not 15."""
        z = pad2(b, lv, 17, 8, 19.0)
        lathe(b, 0, 0, [(12.0, z), (12.0, z + 1.4), (10.4, z + 2.4)], 8, [R_BLACK, R_METAL], TAU / 16)   # traverse ring
        if lv >= 1:                                            # energy cells on the deck
            for s in (-1, 1):
                x, y = -11.0, s * 11.0
                lathe(b, x, y, [(2.3, z - 1.2), (2.3, z + 4.2 + lv * 0.5)], 5, R_METAL, s * 0.6)
                b.ball(x, y, z + 4.6 + lv * 0.5, 1.8, R_LITE)
                b.line([(x + 1.5, y - s * 1.5, z + 3.0), (-7.0, s * 7.0, z + 2.6)], R_LITE, 2)
        zt = z + 2.4
        b.group(M_AIM | M_RECOIL)
        hh = 8.2 + lv * 0.3
        hull(b, -12.0, 9.5, 7.4, zt, hh, R_MAIN, nose=5.0, tail=2.6, topw=5.4)
        for s in (-1, 1):                                      # side armour
            b.box(-1.5, s * 8.7, zt + 0.4, 7.4, 1.3, 5.6, R_DARK, 0.84)
            b.line([(-7.6, s * 10.2, zt + 3.4), (4.6, s * 10.2, zt + 3.4)], R_LITE, 2)
        zb = zt + 6.0 + lv * 0.15                              # the bore
        r = 3.3 + lv * 0.3
        L = 23.0 + lv * 0.8
        b.bar((3.0, 0, zb), (11.0, 0, zb), r + 1.7, R_DARK, 6, rot=TAU / 12)       # mantlet
        b.bar((11.0, 0, zb), (L, 0, zb), r, R_METAL, 8)                             # the barrel
        b.bar((L - 0.6, 0, zb), (L + 4.2, 0, zb), r + 1.5, R_LITE, 8)               # the muzzle
        plate(b, [(L + 4.26, math.cos(i * TAU / 8) * r * 0.95, zb + math.sin(i * TAU / 8) * r * 0.95) for i in range(8)], R_BLACK, (1, 0, 0), False)   # the bore
        b.box(-12.6, 0, zt + 0.8, 2.3, 5.4, hh - 2.6, R_DARK)                       # breech block
        for i in (-1, 0, 1):
            b.line([(-15.0, i * 3.0, zt + 1.8), (-15.0, i * 3.0, zt + hh - 2.6)], R_LITE, 2)
        if lv >= 1:
            b.box(-4.0, 0, zt + hh, 3.0, 3.2, 1.6, R_DARK, 0.8)                     # top housing
            b.ball(-0.8, 0, zt + hh + 1.0, 1.2, R_WHITE)
        if lv >= 2:                                            # charge tanks along the sides
            for s in (-1, 1):
                b.bar((-8.5, s * 8.7, zt + 7.6), (3.5, s * 8.7, zt + 7.6), 2.0, R_METAL, 5, rot=TAU / 4)
                b.ball(3.8, s * 8.7, zt + 7.6, 1.4, R_LITE)
                b.line([(3.8, s * 8.7, zt + 7.6), (8.0, s * (r + 1.2), zb + 1.0)], R_LITE, 2)
            xring(b, 14.0, 0, zb, r + 1.5, R_LITE, 12, 2)
        if lv >= 3:                                            # more coils and a finned muzzle
            xring(b, 18.5, 0, zb, r + 1.5, R_WHITE, 12, 2)
            for i in range(4):
                a = TAU / 8 + i * TAU / 4
                ca, sa = math.cos(a), math.sin(a)
                b.slab([(L - 3.5, ca * r, zb + sa * r), (L + 3.0, ca * (r + 1.2), zb + sa * (r + 1.2)), (L + 4.6, ca * (r + 4.2), zb + sa * (r + 4.2)),
                        (L - 1.0, ca * (r + 3.4), zb + sa * (r + 3.4))], R_MAIN)
            b.glow(L + 4.2, 0, zb, 10, R_LITE, 0.6)
        if lv >= 4:
            b.box(13.0, 0, zb + r - 0.2, 8.5, 1.0, 1.1, R_ALT)                      # the gold spine
            xring(b, L - 1.4, 0, zb, r + 2.2, R_ALT, 12, 2)
            plate(b, [(L + 4.32, math.cos(i * TAU / 8) * r * 0.62, zb + math.sin(i * TAU / 8) * r * 0.62) for i in range(8)], R_WHITE, (1, 0, 0), False)
            b.glow(L + 4.4, 0, zb, 16, R_LITE, 0.9)
            halo(b, zt + hh + 13, 11.0)


    # ====================================================================== JACK-O-CANNON
    def tm2_pumpkin(b, lv):
        """a grinning jack-o-lantern with an iron cannon for a cigar"""
        z = pad2(b, lv, 12)
        for i in range(1 + (lv >= 1) + (lv >= 3)):             # candles on the deck
            x, y = ((-7.6, 7.6), (-7.6, -7.6), (-10.6, 0.0))[i]
            h = 3.0 + (i % 2) * 1.6 + (i == 2) * 3.0
            b.prism(5, x, y, z - 0.8, 0.95, h + 0.8, WAX)
            b.ball(x, y, z + h + 0.8, 0.75, R_WHITE)
            b.glow(x, y, z + h + 1.0, 3.6, PUMP_Y, 0.6)
        for i in range(1 + lv // 2):                           # ammunition
            x, y = ((7.2, -8.0), (7.2, 8.0), (9.6, -5.6))[i]
            b.ball(x, y, z + 1.0, 1.9, PUMP_O)
            b.line([(x, y, z + 2.7), (x - 0.3, y + 0.3, z + 3.7)], PUMP_G, 2)
        b.group(M_AIM | M_RECOIL)
        k = 1.0 + lv * 0.045
        R = 8.3 * k
        z1, z2, z3 = z + 2.3 * k, z + 9.0 * k, z + 11.6 * k
        lathe(b, 0, 0, [(4.6 * k, z), (R, z1), (R, z2), (5.3 * k, z3)], 8, PUMP_O)
        sn, cs = math.sin(TAU / 16), math.cos(TAU / 16)

        def F(s, u, v, d=0.15):
            """a point on one of the two front panels: u from the front edge sideways, v from the bottom up"""
            x = R + (R * math.cos(TAU / 8) - R) * u + cs * d
            y = (R * math.sin(TAU / 8)) * u + sn * d
            return (x, s * y, z1 + (z2 - z1) * v)
        for s in (-1, 1):
            plate(b, [F(s, 0.16, 0.56), F(s, 0.93, 0.66), F(s, 0.74, 0.97)], R_WHITE, (1, 0, 0), False)                      # eye
            plate(b, [F(s, 0.30, 0.40), F(s, 0.45, 0.30), F(s, 0.60, 0.42), F(s, 0.75, 0.33), F(s, 0.95, 0.52),
                      F(s, 0.78, 0.14), F(s, 0.62, 0.24), F(s, 0.46, 0.09), F(s, 0.30, 0.16)], R_WHITE, (1, 0, 0), False)    # half the grin
        b.glow(R, 0, (z1 + z2) / 2, 13, PUMP_Y, 0.55)
        # the cannon
        zc = z1 + (z2 - z1) * 0.24
        p0, p1 = (R - 2.2, 0, zc), (R + 6.4 + lv * 0.4, 0, zc + 3.0 + lv * 0.2)
        b.bar(p0, p1, 2.3, R_BLACK, 6, rot=TAU / 12)
        b.bar((p1[0] - 1.6, 0, p1[2] - 0.75), (p1[0] + 0.5, 0, p1[2] + 0.24), 3.0, R_ALT if lv >= 4 else R_METAL, 6, rot=TAU / 12)
        b.ball(p1[0] + 0.5, 0, p1[2] + 0.25, 2.0, PUMP_O)                                                      # one in the pipe
        b.ball(p1[0] + 2.2, 0.7, p1[2] + 1.0, 0.45, PUMP_Y)
        b.ball(p1[0] + 2.2, -0.7, p1[2] + 1.0, 0.45, PUMP_Y)
        if lv < 2:                                             # stalk
            b.bar((0, 0, z3), (-1.6, 0.8, z3 + 3.4), 1.3, PUMP_G, 5, 0.7)
        else:                                                  # witch hat, with a crooked tip
            b.prism(8, 0, 0, z3 + 0.1, 7.4 * k, 0.8, WITCH)
            b.prism(8, 0, 0, z3 + 0.9, 4.3 * k, 5.2 * k, WITCH, rtop=2.2 * k)
            b.bar((0, 0, z3 + 0.9 + 5.2 * k), (-3.6 * k, 0.8, z3 + 0.4 + 9.6 * k), 2.2 * k, WITCH, 5, 0.15)
            b.ring(0, 0, z3 + 1.5, 4.5 * k, R_ALT if lv >= 4 else PUMP_O, 8, 3)
            b.box(4.2 * k, 0, z3 + 0.9, 0.5, 1.5, 1.9, R_ALT if lv >= 4 else PUMP_Y, rot=0)
        if lv >= 1:                                            # leaf and a curl of vine
            b.slab([(-1.0, 1.5, z3 + 0.2), (-4.4, 6.6, z3 + 1.6), (-6.0, 3.0, z3 - 0.4), (-3.2, 1.0, z3 - 0.2)], PUMP_G)
            b.line([(-2.0, -2.0, z3), (-5.0, -4.6, z3 + 1.6), (-7.2, -4.0, z3 + 0.2), (-7.6, -5.8, z3 - 1.4), (-9.0, -5.4, z3 - 2.2)], PUMP_G, 2)
        if lv >= 3:                                            # bat wings
            for s in (-1, 1):
                b.slab([(-1.5, s * R * 0.92, z + 6.0 * k), (-2.5, s * (R + 6.6), z + 13.0 * k), (-3.0, s * (R + 5.6), z + 9.4 * k),
                        (-3.2, s * (R + 4.6), z + 7.4 * k), (-3.0, s * (R + 3.0), z + 8.6 * k), (-2.6, s * (R + 1.6), z + 5.2 * k), (-1.5, s * R * 0.92, z + 3.6 * k)], WITCH)
            b.ring(0, 0, z + 0.6, R + 1.0, PUMP_G, 12, 2)
        if lv >= 4:
            halo(b, z3 + 10.6 * k + 6.0, 6.5)


    # ====================================================================== SNOWBLOWER
    def tm2_snow(b, lv):
        """a snowman manning a snow gun"""
        z = pad2(b, lv, 12)
        b.prism(7, -3.6, 0, z - 0.2, 7.6, 1.5, SNOW_W, rtop=5.2, edge=False)       # a drift to stand in
        for i in range((lv >= 1) + 2 * (lv >= 3)):                                 # ice on the deck
            x, y, h = ((6.4, -8.6, 6.0), (7.2, 8.4, 4.6), (-10.4, -5.4, 7.6))[i]
            b.crystal(x, y, z - 0.6, 1.5, h, ICE, 4, 0.4 + i, 0.3)
        if lv >= 4:                                                                # a candy cane
            x, y = -9.6, 6.0
            b.line([(x, y, z), (x, y, z + 8.2), (x + 0.5, y + 1.0, z + 9.6), (x + 1.4, y + 2.0, z + 9.2), (x + 1.6, y + 2.4, z + 8.0)], RED, 4)
            for q in range(4):
                b.line([(x, y, z + 1.0 + q * 2.0), (x, y, z + 1.9 + q * 2.0)], R_WHITE, 4)
        b.group(M_AIM)
        k = 1.0 + lv * 0.045
        sx = -4.2
        b.ball(sx, 0, z + 5.6 * k, 6.1 * k, SNOW_W)
        b.ball(sx, 0, z + 13.2 * k, 4.6 * k, SNOW_W)
        zhd = z + 19.2 * k
        b.ball(sx + 0.3, 0, zhd, 3.4 * k, SNOW_W)
        b.bar((sx + 3.2 * k, 0, zhd - 0.1), (sx + 8.2 * k, 0, zhd - 0.8), 0.95 * k, CARROT, 4, 0.1)
        for s in (-1, 1):
            b.ball(sx + 2.8 * k, s * 1.35 * k, zhd + 1.2 * k, 0.62 * k, COAL)
        for i in range(4):
            b.ball(sx + 3.0 * k, (i - 1.5) * 0.85 * k, zhd - 1.7 * k + abs(i - 1.5) * 0.35 * k, 0.3 * k, COAL)
        # scarf
        zn = z + 16.5 * k
        b.ring(sx + 0.1, 0, zn, 3.5 * k, RED, 10, 4)
        b.slab([(sx - 0.6, 3.1 * k, zn + 0.6), (sx - 3.6, 6.4 * k, zn - 4.6 * k), (sx - 1.6, 6.6 * k, zn - 5.6 * k), (sx + 1.0, 3.2 * k, zn - 0.6)], RED)
        # the gun
        zg = z + 8.0 * k
        b.box(4.6, 0, z, 2.6, 3.0, zg - z - 2.2, R_DARK, 0.8)
        for s in (-1, 1):
            b.ball(4.6, s * 3.9 * k, zg + 0.4, 1.2, R_METAL)
        rb = 3.2 * k
        xm, xf = 9.4 + lv * 0.3, 13.4 + lv * 0.5
        b.bar((0.4, 0, zg), (xm, 0, zg + 1.2), rb, R_MAIN, 8)
        b.bar((xm, 0, zg + 1.2), (xf, 0, zg + 1.75), rb, R_METAL, 8, rb + 1.8)
        xring(b, xf + 0.1, 0, zg + 1.75, rb + 1.9, R_ALT if lv >= 4 else R_LITE, 12, 2)
        b.ball(xf - 0.6, 0, zg + 1.7, rb + 0.3, SNOW_W)
        b.prism(6, 4.6, 0, zg + rb + 0.5, 1.5, 2.8, R_METAL, rtop=3.1)             # hopper full of snow
        b.ball(4.6, 0, zg + rb + 3.6, 2.5, SNOW_W)
        for s in (-1, 1):                                                          # twig arms on the handles
            b.line([(sx + 2.4, s * 3.6 * k, z + 13.8 * k), (0.6, s * 4.6 * k, z + 12.0 * k), (2.6, s * 3.4 * k, zg + rb * 0.8)], WOOD, 3)
            b.line([(0.6, s * 4.6 * k, z + 12.0 * k), (0.2, s * 6.0 * k, z + 13.4 * k)], WOOD, 2)
        # hat
        zh = zhd + 2.5 * k
        HAT = (30, 30, 46)
        if lv < 2:                                                                 # a bucket
            b.prism(6, sx + 0.1, 0, zh, 2.9 * k, 2.9 * k, R_METAL, rtop=2.2 * k)
            b.ring(sx + 0.1, 0, zh + 0.5, 3.0 * k, R_LITE, 6, 2)
        else:                                                                      # a proper top hat
            b.prism(8, sx + 0.1, 0, zh, 4.0 * k, 0.7, HAT)
            b.prism(8, sx + 0.1, 0, zh + 0.7, 2.7 * k, 4.2 * k, HAT, rtop=2.9 * k)
            b.ring(sx + 0.1, 0, zh + 1.5, 2.9 * k, R_ALT if lv >= 4 else RED, 8, 4)
        if lv >= 1:                                                                # coal buttons and a snow tank on its back
            for q in range(2):
                b.ball(sx + 4.4 * k, 0, z + (12.0 + q * 2.4) * k, 0.6 * k, COAL)
            b.box(sx - 5.0 * k, 0, z + 9.6 * k, 1.5, 2.6, 5.6, R_MAIN, 0.9)
            b.line([(sx - 5.0 * k, 2.6, z + 10.4 * k), (sx - 2.0, 5.4 * k, z + 8.0 * k), (1.0, 3.4 * k, zg - 1.0)], R_METAL, 3)
        if lv >= 3:                                                                # two side nozzles and holly on the hat
            for s in (-1, 1):
                b.bar((2.0, s * (rb + 2.0), zg + 0.2), (xm + 1.0, s * (rb + 2.6), zg + 1.4), 1.4, R_METAL, 4, 1.9)
                b.ball(xm + 1.1, s * (rb + 2.6), zg + 1.4, 1.5, SNOW_W)
            b.slab([(sx + 2.6 * k, 0.4, zh + 1.2), (sx + 3.6 * k, 2.4, zh + 2.2), (sx + 2.2 * k, 2.6, zh + 1.0)], PUMP_G)
            b.ball(sx + 2.9 * k, 0.2, zh + 1.5, 0.6, RED)
            b.glow(xf, 0, zg + 1.75, 9, SNOW_W, 0.5)
        if lv >= 4:
            halo(b, zh + 4.9 * k + 5.5, 6.0)


    # ====================================================================== RUBBER DUCK
    def tm2_duck(b, lv):
        """gets fancier with every level: bow tie, shades, top hat and pipe, and finally a crown"""
        z = pad2(b, lv, 12)
        b.slab([(math.cos(i * TAU / 12) * 10.0, math.sin(i * TAU / 12) * 10.0, z + 0.12) for i in range(12)], WATER, False)   # its pond
        b.ring(0, 0, z + 0.2, 10.0, R_WHITE, 12, 1)
        b.ring(0, 0, z + 0.25, 8.6, BUBBLE, 12, 1)
        b.group(M_AIM)
        k = 1.0 + lv * 0.05
        zb = z + 4.9 * k
        blob(b, -1.0 * k, 0, zb, 8.3 * k, 6.5 * k, 5.4 * k, DUCK_Y, 6, (0.8, 1.6, 2.55))                       # body
        b.bar((-6.6 * k, 0, zb + 2.0 * k), (-10.6 * k, 0, zb + 6.0 * k), 2.5 * k, DUCK_Y, 4, 0.3 * k)            # tail
        for s in (-1, 1):                                                                                      # wings
            y = s * 5.75 * k
            b.slab([(-5.6 * k, y, zb - 0.4 * k), (-1.0 * k, y, zb - 1.4 * k), (2.8 * k, y, zb + 0.6 * k), (1.8 * k, y, zb + 2.8 * k), (-3.0 * k, y, zb + 3.2 * k),
                    (-7.0 * k, y * 1.04, zb + 3.0 * k)], DUCK_Y2)
        hx, zhd = 4.4 * k, zb + 8.0 * k
        blob(b, hx, 0, zhd, 4.6 * k, 4.4 * k, 4.2 * k, DUCK_Y, 6, (0.85, 1.65, 2.5))                            # head
        x0, x1, zk = hx + 3.4 * k, hx + 8.6 * k, zhd - 0.9 * k                                                 # beak
        b.mesh([(x0, -2.5 * k, zk - 1.3 * k), (x0, 2.5 * k, zk - 1.3 * k), (x0, 2.5 * k, zk + 1.5 * k), (x0, -2.5 * k, zk + 1.5 * k),
                (x1, -1.7 * k, zk - 0.9 * k), (x1, 1.7 * k, zk - 0.9 * k), (x1, 1.7 * k, zk - 0.1 * k), (x1, -1.7 * k, zk - 0.1 * k)],
               [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], DUCK_O)
        ex, ez = hx + 3.3 * k, zhd + 1.5 * k
        if lv < 2:
            for s in (-1, 1):
                b.ball(ex, s * 2.4 * k, ez, 0.85 * k, COAL)
                b.ball(ex + 0.5 * k, s * 2.2 * k, ez + 0.4 * k, 0.3 * k, R_WHITE)
        else:                                                                      # shades
            xs = hx + 4.5 * k
            for s in (-1, 1):
                b.slab([(xs, s * 0.4 * k, ez + 1.1 * k), (xs, s * 3.9 * k, ez + 1.1 * k), (xs, s * 3.5 * k, ez - 1.0 * k), (xs, s * 0.9 * k, ez - 1.0 * k)], COAL)
                b.line([(xs + 0.1, s * 1.2 * k, ez + 0.6 * k), (xs + 0.1, s * 2.4 * k, ez + 0.6 * k)], R_LITE, 2)
                b.line([(xs, s * 3.9 * k, ez + 0.9 * k), (hx + 0.5 * k, s * 4.2 * k, ez + 0.6 * k)], COAL, 2)
            b.line([(xs, -0.5 * k, ez + 0.9 * k), (xs, 0.5 * k, ez + 0.9 * k)], COAL, 3)
        if lv >= 1:                                                                # bow tie
            xt, zt = hx + 3.2 * k, zhd - 3.9 * k
            for s in (-1, 1):
                b.slab([(xt, 0, zt), (xt + 0.3, s * 3.0 * k, zt + 1.5 * k), (xt + 0.3, s * 3.0 * k, zt - 1.5 * k)], RED)
            b.ball(xt + 0.2, 0, zt, 0.8 * k, RED)
        ztop = zhd + 3.3 * k
        if lv == 3:                                                                # top hat
            b.prism(8, hx, 0, ztop, 4.6 * k, 0.7, COAL)
            b.prism(8, hx, 0, ztop + 0.7, 3.0 * k, 4.4 * k, COAL, rtop=3.3 * k)
            b.ring(hx, 0, ztop + 1.5, 3.2 * k, RED, 8, 4)
        if lv >= 3:                                                                # bubble pipe
            px, py, pz = x1 - 0.6 * k, 1.9 * k, zk - 1.0 * k
            b.bar((px - 2.0 * k, py - 0.6 * k, pz + 0.3 * k), (px + 3.4 * k, py + 1.0 * k, pz - 1.2 * k), 0.5 * k, WOOD, 4)
            b.prism(6, px + 3.6 * k, py + 1.1 * k, pz - 1.6 * k, 1.0 * k, 2.2 * k, WOOD, rtop=1.6 * k)
        if lv >= 4:                                                                # crown, chain, and a duckling along for the ride
            b.prism(6, hx, 0, ztop - 0.2, 2.9 * k, 2.2 * k, R_ALT, rtop=3.7 * k)
            for i in range(6):
                a = i * TAU / 6
                b.prism(3, hx + math.cos(a) * 3.6 * k, math.sin(a) * 3.6 * k, ztop + 2.0 * k, 0.9 * k, 2.4 * k, R_ALT, rtop=0, rot=a)
                b.ball(hx + math.cos(a + TAU / 12) * 3.5 * k, math.sin(a + TAU / 12) * 3.5 * k, ztop + 1.0 * k, 0.5 * k, RED if i % 2 else R_WHITE)
            b.ring(hx - 0.4 * k, 0, zhd - 3.6 * k, 4.6 * k, R_ALT, 10, 3)
        if lv >= 2:                                                                # duckling on its back
            dx, dz = -4.0 * k, zb + 6.5 * k
            b.ball(dx, 0, dz, 1.9 * k, DUCK_Y)
            b.ball(dx + 1.3 * k, 0, dz + 2.2 * k, 1.35 * k, DUCK_Y)
            b.ball(dx + 2.6 * k, 0, dz + 2.0 * k, 0.6 * k, DUCK_O)
            b.ball(dx + 2.1 * k, 0.7 * k, dz + 2.7 * k, 0.28 * k, COAL)
            b.ball(dx + 2.1 * k, -0.7 * k, dz + 2.7 * k, 0.28 * k, COAL)
        # bubbles
        b.group(M_AIM | M_BOB, 0, 0, 0, zk + 1.0, 2.2, 0.8)
        for i in range(2 + lv):
            x, y, zz, r_ = ((5.0, 0.6, 2.0, 1.7), (7.6, -2.0, 5.0, 1.2), (3.6, 2.6, 6.4, 0.9), (8.6, 1.8, 8.4, 1.5), (5.6, -1.0, 10.4, 0.8), (9.6, -0.8, 1.2, 0.7))[i]
            b.ball(x1 + x, y, zz, r_, BUBBLE)
            b.ball(x1 + x - r_ * 0.3, y, zz + r_ * 0.35, r_ * 0.3, R_WHITE)
        if lv >= 4:
            halo(b, ztop + 4.6 * k + 6.0, 6.5)


    # ====================================================================== TOASTER
    def tm2_toaster(b, lv):
        """chrome, a lever, a face, and toast that jumps (the toast is the part that recoils)"""
        z = pad2(b, lv, 13)
        ns = (2, 2, 3, 4, 4)[lv]
        hy = 1.7 + ns * 1.55
        hx = 6.4 + lv * 0.15
        hh = 9.4 + lv * 0.45
        zb = z + 1.4
        b.box(0, 0, z, hx + 0.7, hy + 0.7, 1.4, R_ALT if lv >= 4 else R_BLACK, 0.96)               # crumb tray
        c = 2.4
        ext(b, "y", [(-hx, zb), (hx, zb), (hx, zb + hh - c), (hx - c, zb + hh), (-hx + c, zb + hh), (-hx, zb + hh - c)], -hy, hy, R_METAL, skip=(0,))   # the shell
        zt = zb + hh
        ys = [(i - (ns - 1) / 2.0) * 3.1 for i in range(ns)]
        for y in ys:                                                               # slots, glowing inside
            b.slab([(-hx + c + 0.3, y - 0.85, zt + 0.06), (hx - c - 0.3, y - 0.85, zt + 0.06), (hx - c - 0.3, y + 0.85, zt + 0.06), (-hx + c + 0.3, y + 0.85, zt + 0.06)], COAL, False)
            b.line([(-hx + c + 0.6, y, zt + 0.1), (hx - c - 0.6, y, zt + 0.1)], R_LITE, 2)
        for s in (-1, 1):                                                          # shine on the chrome, a coloured band
            b.line([(-hx + 1.2, s * (hy + 0.1), zb + 1.2), (hx - 1.2, s * (hy + 0.1), zb + 1.2)], R_ALT if lv >= 4 else R_MAIN, 3)
            b.line([(-hx + 2.0, s * (hy + 0.1), zb + hh - 3.4), (-hx + 4.6, s * (hy + 0.1), zb + hh - 1.2)], R_WHITE, 2)
            b.line([(-hx + 3.4, s * (hy + 0.1), zb + hh - 3.8), (-hx + 5.4, s * (hy + 0.1), zb + hh - 2.0)], R_WHITE, 1)
        # the business end: lever, and a face
        fx = hx + 0.12
        b.line([(fx, 0, zb + 1.6), (fx, 0, zb + hh - 3.4)], COAL, 4)
        b.box(hx + 1.2, 0, zb + hh * 0.36, 1.2, 1.7, 1.1, R_ALT if lv >= 4 else R_LITE)
        ey = min(hy - 1.6, 3.4)
        for s in (-1, 1):
            b.ball(fx, s * ey, zb + hh * 0.64, 1.05, COAL)
            b.ball(fx + 0.6, s * ey - 0.3, zb + hh * 0.64 + 0.4, 0.36, R_WHITE)
        b.line([(fx, -ey * 0.7, zb + 2.4), (fx, -ey * 0.3, zb + 1.7), (fx, ey * 0.3, zb + 1.7), (fx, ey * 0.7, zb + 2.4)], COAL, 2)
        b.ball(1.5, -hy - 0.3, zb + 3.2, 1.2, R_LITE)                              # browning dial
        b.line([(1.5, -hy - 1.5, zb + 3.2), (1.5, -hy - 1.5, zb + 4.3)], COAL, 2)
        # round the kitchen
        b.line([(-hx, 1.6, zb + 0.9), (-hx - 1.6, 2.6, z + 0.2), (-hx - 3.0, 0.4, z + 0.2), (-hx - 2.2, -3.0, z + 0.2), (-hx - 3.6, -5.0, z + 0.2)], COAL, 3)   # cord and plug
        b.box(-hx - 4.0, -5.8, z - 0.4, 0.9, 1.3, 1.6, R_METAL, rot=0.6)
        if lv >= 1:                                                                # butter, and the knife still in it
            ux, uy = hx + 3.4, 5.4
            b.box(ux, uy, z - 0.4, 1.7, 2.2, 0.9, CAT_W, 0.9, 0.35)
            b.box(ux, uy, z + 0.5, 0.9, 1.4, 1.0, (255, 226, 110), 0.9, 0.35)
            b.line([(ux, uy, z + 1.4), (ux + 0.6, uy + 2.0, z + 3.4)], R_METAL, 3)
        if lv >= 2:                                                                # a plate with one they burnt earlier
            px, py = (0.0, -hy - 5.0) if hy + 8.6 < 14.5 else (hx + 4.6, -5.5)
            b.prism(8, px, py, z - 0.3, 3.2, 0.9, CAT_W, rtop=3.8)
            b.box(px, py, z + 0.6, 2.2, 2.2, 0.7, BURNT, rot=0.5)
        if lv >= 3:                                                                # jam
            jx, jy = -hx - 3.6, 5.6
            b.prism(6, jx, jy, z - 0.6, 1.9, 3.8, RED)
            b.prism(6, jx, jy, z + 3.2, 2.1, 0.9, R_ALT if lv >= 4 else R_METAL)
            b.glow(0, 0, zt, 13, FLAME, 0.5)
        # the toast
        amp = 1.5
        b.group(M_BOB | M_RECOIL, 0, 0, 0, zt + 0.2 + amp, 3.4, amp)
        for i, y in enumerate(ys):
            ext(b, "y", [(-3.5, 0), (3.5, 0), (3.5, 3.6), (2.5, 5.0), (-2.5, 5.0), (-3.5, 3.6)], y - 0.6, y + 0.6, CRUST, TOAST, skip=(0,))
            if lv >= 1:
                b.line([(-1.6, y + 0.66, 1.2), (1.6, y + 0.66, 3.4)], CRUST, 2)
                b.line([(-1.6, y - 0.66, 1.2), (1.6, y - 0.66, 3.4)], CRUST, 2)
            if lv >= 3:                                                            # and it is on fire
                for q, (fx_, fh) in enumerate(((-1.6, 3.0), (0.9, 4.2))):
                    if (q + i) % 2 == 0 or lv >= 4:
                        b.slab([(fx_ - 1.1, y, 5.0), (fx_ + 1.1, y, 5.0), (fx_ + 0.3, y, 5.0 + fh)], R_LITE)
                b.ball(-0.2, y, 5.5, 0.7, R_WHITE)
        if lv >= 3:
            b.glow(0, 0, 6.0, 12, FLAME, 0.6)
        if lv >= 4:
            halo(b, zt + 14.5, 7.0)


    # ====================================================================== KEYBOARD CAT
    def tm2_cat(b, lv):
        """a cat on a keyboard, one paw up, about to smack something off the table"""
        z = pad2(b, lv, 13)
        zk = z
        if lv >= 1:                                                                # the desk
            b.box(0, 0, z - 0.2, 10.4, 11.6, 1.0, R_DARK, 0.97)
            zk = z + 0.8
        b.box(0, 0, zk, 6.6, 10.6, 1.3, R_BLACK, 0.95)                             # the keyboard
        RGB = ((255, 60, 90), (255, 200, 60), (80, 255, 150), (90, 150, 255), (200, 110, 255))
        for i in range(5):
            x = -5.0 + i * 2.5
            b.line([(x, -9.6, zk + 1.4), (x, 9.6, zk + 1.4)], RGB[i] if lv >= 3 else R_LITE, 2)
        b.line([(-6.3, -10.1, zk + 1.35), (6.3, -10.1, zk + 1.35), (6.3, 10.1, zk + 1.35), (-6.3, 10.1, zk + 1.35)], R_ALT if lv >= 4 else R_MAIN, 1, True)
        # a mug, right on the edge
        mx, my = 9.0, 7.6
        zm = zk if lv >= 1 else z
        b.prism(6, mx, my, zm - (0.0 if lv >= 1 else 0.3), 1.7, 3.6, CAT_W)
        b.line([(mx, my + 1.6, zm + 2.8), (mx, my + 2.9, zm + 2.2), (mx, my + 2.9, zm + 1.2), (mx, my + 1.6, zm + 0.8)], CAT_W, 2)
        b.ball(mx, my, zm + 3.5, 1.1, WOOD)
        if lv >= 2:                                                                # a plant: next
            px, py = 8.6, -8.0
            b.prism(6, px, py, zk, 1.5, 2.6, (200, 110, 70), rtop=2.0)
            for q in range(3):
                a = q * TAU / 3 + 0.4
                b.slab([(px, py, zk + 2.6), (px + math.cos(a) * 2.6, py + math.sin(a) * 2.6, zk + 6.4), (px + math.cos(a + 0.9) * 1.6, py + math.sin(a + 0.9) * 1.6, zk + 4.2)], PUMP_G)
        if lv >= 3:                                                                # the mouse it already dealt with
            b.box(-8.6, 8.4, zk, 1.2, 1.7, 1.2, R_METAL, 0.7, 0.5)
            b.line([(-7.4, 8.9, zk + 0.4), (-6.0, 9.6, zk + 0.3), (-6.8, 10.6, zk + 0.3)], COAL, 2)
            b.ball(-8.9, 8.2, zk + 1.3, 0.5, R_LITE)
        # the cat
        b.group(M_AIM)
        k = 1.0 + lv * 0.04
        zc = zk + 1.3
        hull(b, -6.2 * k, 2.2 * k, 4.3 * k, zc, 5.0 * k, CAT_G, nose=1.6 * k, tail=2.4 * k, topw=3.0 * k)       # haunches
        b.prism(6, 1.2 * k, 0, zc, 3.5 * k, 8.4 * k, CAT_G, rtop=2.6 * k)                                       # chest
        b.slab([(4.3 * k, -1.7 * k, zc + 1.0 * k), (4.3 * k, 1.7 * k, zc + 1.0 * k), (3.6 * k, 1.5 * k, zc + 7.0 * k), (3.6 * k, -1.5 * k, zc + 7.0 * k)], CAT_W, False)
        zh = zc + 8.2 * k
        hull(b, -1.6 * k, 5.6 * k, 4.0 * k, zh, 5.4 * k, CAT_G, nose=1.4 * k, tail=0.8 * k, topw=3.3 * k)       # head
        b.box(5.6 * k, 0, zh + 0.5 * k, 0.9 * k, 1.9 * k, 1.9 * k, CAT_W, 0.8)                                  # muzzle
        b.ball(6.5 * k, 0, zh + 2.2 * k, 0.55 * k, CAT_P)
        for s in (-1, 1):
            b.prism(3, 1.2 * k, s * 2.5 * k, zh + 5.3 * k, 1.8 * k, 3.0 * k, CAT_G, rtop=0, rot=s * 0.5)        # ear
            b.line([(1.9 * k, s * 2.5 * k, zh + 5.6 * k), (1.5 * k, s * 2.5 * k, zh + 7.4 * k)], CAT_P, 3)
            for q in (-1, 0, 1):                                                                              # whiskers
                b.line([(5.9 * k, s * 1.6 * k, zh + 1.4 * k), (6.2 * k, s * 5.4 * k, zh + (1.4 + q * 1.0) * k)], R_WHITE, 1)
            b.line([(-1.4 * k, s * 0.4, zh + 5.45 * k), (-0.4 * k, s * 2.9 * k, zh + 5.45 * k)], CAT_S, 3)      # tabby stripes
            b.line([(-4.4 * k, s * 0.3, zc + 5.05 * k), (-3.8 * k, s * 2.9 * k, zc + 5.05 * k)], CAT_S, 3)
            b.line([(-2.2 * k, s * 0.3, zc + 5.05 * k), (-1.6 * k, s * 2.9 * k, zc + 5.05 * k)], CAT_S, 3)
        ex, ez = 5.0 * k, zh + 3.5 * k
        if lv < 2:
            for s in (-1, 1):
                b.ball(ex, s * 2.0 * k, ez, 0.95 * k, R_LITE)
                b.line([(ex + 0.9 * k, s * 2.0 * k, ez - 0.7 * k), (ex + 0.9 * k, s * 2.0 * k, ez + 0.7 * k)], COAL, 2)
        else:                                                                      # deal-with-it shades
            b.slab([(ex + 0.6 * k, -3.9 * k, ez + 0.9 * k), (ex + 0.6 * k, 3.9 * k, ez + 0.9 * k), (ex + 0.75 * k, 3.3 * k, ez - 0.9 * k), (ex + 0.75 * k, 0.5 * k, ez - 0.9 * k),
                    (ex + 0.7 * k, 0, ez - 0.2 * k), (ex + 0.75 * k, -0.5 * k, ez - 0.9 * k), (ex + 0.75 * k, -3.3 * k, ez - 0.9 * k)], COAL)
            b.line([(ex + 0.8 * k, 1.0 * k, ez + 0.4 * k), (ex + 0.8 * k, 2.2 * k, ez + 0.4 * k)], R_LITE, 2)
            b.line([(ex + 0.8 * k, -2.8 * k, ez + 0.4 * k), (ex + 0.8 * k, -1.6 * k, ez + 0.4 * k)], R_LITE, 2)
        # tail
        b.bar((-5.6 * k, 0, zc + 1.6 * k), (-9.4 * k, 1.6 * k, zc + 6.6 * k), 1.05 * k, CAT_G, 4)
        b.bar((-9.4 * k, 1.6 * k, zc + 6.6 * k), (-7.6 * k, 2.6 * k, zc + 11.6 * k), 1.0 * k, CAT_G, 4, 0.6 * k)
        b.ball(-7.5 * k, 2.6 * k, zc + 12.0 * k, 0.9 * k, CAT_W)
        # the paw that stays down and the paw that does the work
        b.bar((2.6 * k, 2.4 * k, zc + 5.6 * k), (4.4 * k, 2.6 * k, zc + 0.8 * k), 1.1 * k, CAT_G, 4)
        b.ball(5.0 * k, 2.6 * k, zc + 0.9 * k, 1.25 * k, CAT_W)
        p1 = (9.4 * k + lv * 0.3, -4.6 * k, zc + 8.8 * k)
        b.bar((2.4 * k, -3.0 * k, zc + 6.4 * k), p1, 1.2 * k, CAT_G, 4)
        b.ball(p1[0] + 0.6 * k, p1[1], p1[2] + 0.2 * k, 1.6 * k, CAT_W)
        if lv >= 1:                                                                # collar with a bell; claws out
            b.ring(1.6 * k, 0, zh - 0.1 * k, 3.1 * k, R_ALT if lv >= 4 else R_LITE, 8, 3)
            b.ball(4.4 * k, 0, zh - 0.7 * k, 0.8 * k, R_ALT)
            for q in (-1, 0, 1):
                b.line([(p1[0] + 1.8 * k, p1[1] + q * 0.9 * k, p1[2] + 0.6 * k), (p1[0] + 3.4 * k, p1[1] + q * 1.3 * k, p1[2] - 0.4 * k)], R_WHITE, 2)
        if lv >= 3:                                                                # headphones, and the swipe leaves a trail
            HP = (40, 40, 60)
            xring(b, 1.9 * k, 0, zh + 2.6 * k, 4.9 * k, HP, 8, 4)
            for s in (-1, 1):
                b.box(1.9 * k, s * 4.5 * k, zh + 1.2 * k, 1.5 * k, 0.7 * k, 2.8 * k, R_MAIN)
                b.ball(1.9 * k, s * 5.3 * k, zh + 2.6 * k, 0.8 * k, R_LITE)
            t0 = p1[2] + 0.4
            b.slab([(p1[0] + 3.0, p1[1] - 1.5, t0), (p1[0] + 4.4, p1[1] + 2.4, t0 - 0.6), (p1[0] + 3.4, p1[1] + 6.4, t0 - 1.6), (p1[0] + 0.6, p1[1] + 9.2, t0 - 2.8),
                    (p1[0] + 2.2, p1[1] + 6.0, t0 - 1.8), (p1[0] + 2.8, p1[1] + 2.4, t0 - 0.9)], R_LITE)
        if lv >= 4:                                                                # crown between the ears
            b.prism(5, 1.6 * k, 0, zh + 5.4 * k, 1.5 * k, 1.9 * k, R_ALT, rtop=2.3 * k)
            b.ball(1.6 * k, 0, zh + 7.9 * k, 0.8 * k, RED)
            halo(b, zh + 15.0 * k, 6.5)


    # ====================================================================== STONKS
    def tm2_stonks(b, lv):
        """a trading terminal: the big board, the bar chart, a ticker going round and a coin that never stops spinning"""
        z = pad2(b, lv, 13)
        bx = -6.6
        bw = 9.6 + lv * 0.25
        bh = 12.0 + lv * 1.3
        z0 = z + 2.8
        b.box(bx, 0, z - 0.6, 1.5, 6.2, 3.5, R_METAL, 0.72)                        # the foot of the board
        b.box(bx, 0, z0, 0.9, bw, bh, R_BLACK)
        fx = bx + 0.98
        trim = R_ALT if lv >= 4 else R_METAL
        b.line([(fx, -bw + 0.4, z0 + 0.4), (fx, bw - 0.4, z0 + 0.4), (fx, bw - 0.4, z0 + bh - 0.4), (fx, -bw + 0.4, z0 + bh - 0.4)], trim, 2, True)
        for q in (0.33, 0.66):
            b.line([(fx, -bw + 0.6, z0 + bh * q), (fx, bw - 0.6, z0 + bh * q)], R_DARK, 1)
        nc = 5 + lv                                                                # candles
        for i in range(nc):
            y = -bw + 1.6 + (2 * bw - 3.2) * i / (nc - 1.0)
            up = i % 3 != 1
            m = z0 + bh * (0.16 + 0.50 * i / (nc - 1.0)) + (0.0 if up else -bh * 0.05)
            b.line([(fx, y, m - bh * 0.09), (fx, y, m + bh * 0.11)], STONK_G if up else STONK_R, 1)
            b.line([(fx, y, m - bh * 0.04), (fx, y, m + bh * 0.06)], STONK_G if up else STONK_R, 4)
        ztop = z0 + bh
        yl = bw - 1.6
        b.line([(fx + 0.05, -bw + 1.0, z0 + bh * 0.42), (fx + 0.05, -bw * 0.5, z0 + bh * 0.60), (fx + 0.05, -bw * 0.2, z0 + bh * 0.50), (fx + 0.05, bw * 0.25, z0 + bh * 0.78),
                (fx + 0.05, bw * 0.48, z0 + bh * 0.70), (fx + 0.05, yl, ztop + 1.4)], R_MAIN, 3)                   # the line goes up, and out of the top
        b.slab([(fx + 0.05, yl + 0.9, ztop + 4.2), (fx + 0.05, yl + 2.1, ztop + 0.4), (fx + 0.05, yl - 1.9, ztop + 1.6)], R_LITE)
        # the bar chart
        nb_ = 3 + (lv >= 2) + (lv >= 4)
        for i in range(nb_):
            y = (i - (nb_ - 1) / 2.0) * (14.4 / nb_) * 1.05
            h = 2.6 + i * (2.3 + lv * 0.3) * 3.0 / (nb_ - 1.0) * 0.72
            red = i == 1
            if red:
                h *= 0.62
            b.box(-1.4, y, z, 1.6, 1.6, h, STONK_R if red else STONK_G, 0.94)
            b.ball(-1.4, y, z + h + 0.9, 0.7, R_WHITE if i == nb_ - 1 else (STONK_R if red else STONK_G))
        # the desk
        hull(b, 3.6, 9.4, 6.4, z - 0.3, 3.0, R_DARK, nose=3.2, tail=0.4, topw=5.6)
        for q in range(3):
            xq = 6.9 + q * 0.85
            zq = z + 2.75 - (q + 0.25) * 0.8
            b.line([(xq, -4.6, zq), (xq, 4.6, zq)], R_LITE if q == 0 else R_MAIN, 2)
        b.line([(4.4, 5.2, z + 2.8), (5.0, 7.6, z + 1.6), (6.8, 8.8, z + 0.3), (9.0, 8.4, z + 0.2), (10.0, 6.6, z + 0.2)], R_WHITE, 3)   # ticker tape
        if lv >= 1:                                                                # a second screen
            b.box(2.4, -6.6, z + 2.4, 0.5, 2.9, 4.2, R_BLACK, rot=-0.45)
            b.line([(2.4, -6.6, z), (2.4, -6.6, z + 2.4)], R_METAL, 3)
            b.line([(3.5, -8.3, z + 3.4), (3.2, -7.0, z + 4.6), (2.6, -5.8, z + 4.0), (2.1, -4.8, z + 5.8)], R_MAIN, 2)
        if lv >= 2:                                                                # a dish for the market feed
            dx, dy = bx, -bw + 1.2
            b.line([(dx, dy, ztop), (dx, dy, ztop + 2.2)], R_METAL, 3)
            b.prism(5, dx, dy, ztop + 2.0, 0.8, 1.6, R_METAL, rtop=2.6)
            b.ball(dx, dy, ztop + 4.4, 0.6, R_LITE)
        if lv >= 3:                                                                # it is a bull market
            hx_, hy_ = bx + 0.2, -1.6
            b.box(hx_, hy_, ztop, 1.5, 1.9, 2.8, R_ALT if lv >= 4 else R_METAL, 0.72)
            for s in (-1, 1):
                b.bar((hx_, hy_ + s * 1.6, ztop + 2.3), (hx_, hy_ + s * 3.9, ztop + 3.2), 0.8, R_WHITE, 3, rot=TAU / 4)
                b.bar((hx_, hy_ + s * 3.9, ztop + 3.2), (hx_ + 0.6, hy_ + s * 4.3, ztop + 5.9), 0.8, R_WHITE, 3, 0.1)
                b.ball(hx_ + 1.3, hy_ + s * 0.9, ztop + 1.9, 0.42, STONK_R)
            b.ring(hx_ + 1.5, hy_, ztop + 0.6, 0.9, R_ALT, 6, 2, math.pi / 2, math.pi / 2)
        if lv >= 4:                                                                # ...to the moon
            rx, ry, rz = fx + 0.6, yl + 0.2, ztop + 5.6
            b.prism(5, rx, ry, rz, 1.5, 4.6, R_WHITE)
            b.prism(5, rx, ry, rz + 4.6, 1.5, 3.0, STONK_R, rtop=0)
            for q in range(3):
                a = q * TAU / 3 + 0.5
                b.slab([(rx + math.cos(a) * 1.4, ry + math.sin(a) * 1.4, rz + 2.2), (rx + math.cos(a) * 3.2, ry + math.sin(a) * 3.2, rz - 1.0), (rx + math.cos(a) * 1.4, ry + math.sin(a) * 1.4, rz)], STONK_R)
            b.ball(rx, ry, rz - 0.8, 1.2, FLAME)
            b.glow(rx, ry, rz - 1.2, 8, (255, 160, 60), 0.9)
        # the ticker
        b.group(M_SPIN, 0.7, 0, 0, z - 1.2)
        rt = 13.2
        for i in range(4):
            a0 = i * TAU / 4
            b.line([(math.cos(a0 + q * 0.14) * rt, math.sin(a0 + q * 0.14) * rt, 0) for q in range(4)], R_LITE, 3)
            b.line([(math.cos(a0 + 0.62 + q * 0.14) * rt, math.sin(a0 + 0.62 + q * 0.14) * rt, 0) for q in range(3)], R_MAIN, 3)
            a = a0 + 1.25
            ca, sa = math.cos(a), math.sin(a)
            up = i != 1
            dz = 1.1 if up else -1.1
            b.slab([(ca * rt - sa * 1.0, sa * rt + ca * 1.0, -dz), (ca * rt + sa * 1.0, sa * rt - ca * 1.0, -dz), (ca * rt, sa * rt, dz)], STONK_G if up else STONK_R)
        # the coin
        b.group(M_SPIN | M_BOB, 1.6, 2.6, 0.0, max(ztop * 0.72, z + 13.0 + lv), 2.0, 1.0)
        cr_ = 3.0 + lv * 0.25
        b.bar((0, -0.55, 0), (0, 0.55, 0), cr_, R_ALT, 8)
        for s in (-1, 1):
            b.line([(-s * 0.9, s * 0.62, 1.3), (s * 0.9, s * 0.62, 0.9), (-s * 0.9, s * 0.62, -0.9), (s * 0.9, s * 0.62, -1.3)], R_WHITE, 2)
            b.line([(0, s * 0.62, 1.9), (0, s * 0.62, -1.9)], R_WHITE, 1)
        b.glow(0, 0, 0, cr_ * 2.6, R_ALT, 0.5)
        if lv >= 4:
            halo(b, ztop + 16.5, 6.6)


    # ====================================================================== THE BRICK (path tower: no plinth, one body)
    def tm2_brick(b, lv):
        """an indestructible old phone, standing on the road"""
        b.group(M_AIM)
        k = 1.0 + lv * 0.07
        hx, hy, c = 4.1 * k, 6.9 * k, 1.3 * k
        zb, zt = 2.0 * k, 24.0 * k
        b.box(0, 0, 0, hx + 1.6 * k, hy + 1.7 * k, 2.2 * k, R_BLACK, 0.9)                                      # its charging cradle
        b.line([(hx + 1.5 * k, -hy * 0.6, 1.3 * k), (hx + 1.5 * k, hy * 0.6, 1.3 * k)], R_LITE, 2)
        ext(b, "z", [(-hx, -hy + c), (-hx + c, -hy), (hx - c, -hy), (hx, -hy + c), (hx, hy - c), (hx - c, hy), (-hx + c, hy), (-hx, hy - c)], zb, zt, BRICK_C, k=0.93, cap0=False)
        px = hx - 0.15 * k
        b.box(px, 0, zb + 1.2 * k, 0.45 * k, hy - 1.7 * k, zt - zb - 2.6 * k, R_ALT if lv >= 4 else R_METAL)   # face plate
        fx = px + 0.5 * k
        # the tiny screen, and what it thinks of all this
        sw, s0, s1 = 4.0 * k, 16.0 * k, 21.0 * k
        plate(b, [(fx, -sw, s0), (fx, sw, s0), (fx, sw, s1), (fx, -sw, s1)], R_LITE, (1, 0, 0), False)
        b.line([(fx, -sw, s0), (fx, sw, s0), (fx, sw, s1), (fx, -sw, s1)], COAL, 2, True)
        g = fx + 0.06
        zm = (s0 + s1) / 2 - 0.2 * k
        if lv < 3:                                                                 # -_-
            for s in (-1, 1):
                b.line([(g, s * 1.0 * k, zm + 0.5 * k), (g, s * 2.6 * k, zm + 0.5 * k)], BRICK_INK, 3)
            b.line([(g, -0.9 * k, zm - 1.1 * k), (g, 0.9 * k, zm - 1.1 * k)], BRICK_INK, 3)
        else:                                                                      # >_<  it has had enough
            for s in (-1, 1):
                b.line([(g, s * 2.7 * k, zm + 1.2 * k), (g, s * 1.1 * k, zm + 0.4 * k), (g, s * 2.7 * k, zm - 0.3 * k)], BRICK_INK, 3)
            b.line([(g, -1.0 * k, zm - 1.3 * k), (g, 1.0 * k, zm - 1.3 * k)], BRICK_INK, 3)
        for q in range(4):                                                         # full signal, full battery, always
            b.line([(g, (-3.5 + q * 0.6) * k, s1 - 1.3 * k), (g, (-3.5 + q * 0.6) * k, s1 - (1.1 - q * 0.25) * k)], BRICK_INK, 2)
        b.line([(g, 2.2 * k, s1 - 0.9 * k), (g, 3.5 * k, s1 - 0.9 * k)], BRICK_INK, 3)
        for q in (-1, 0, 1):                                                       # earpiece
            b.line([(fx, -1.6 * k, s1 + (1.2 + q * 0.5) * k), (fx, 1.6 * k, s1 + (1.2 + q * 0.5) * k)], COAL, 2)
        # keys
        def key(y, zz, hw, h, d, role):                                            # a key: 4 faces (nobody sees it from underneath)
            ext(b, "x", [(y - hw, zz), (y + hw, zz), (y + hw, zz + h), (y - hw, zz + h)], fx - 0.2 * k, fx + d, role, cap0=False, skip=(0,))
        key(0, 13.3 * k, 2.4 * k, 1.5 * k, 0.5 * k, R_LITE)
        for s in (-1, 1):
            key(s * 3.7 * k, 13.4 * k, 0.9 * k, 1.3 * k, 0.45 * k, STONK_R if s > 0 else STONK_G)
        for r_ in range(4):
            for q in (-1, 0, 1):
                key(q * 2.9 * k, (10.6 - r_ * 2.3) * k, 1.1 * k, 1.35 * k, 0.5 * k, BRICK_K)
        # aerial, side buttons, belt clip
        ax, ay = -0.9 * k, 4.6 * k
        b.bar((ax, ay, zt - 0.6 * k), (ax, ay, zt + (6.0 + lv * 0.6) * k), 1.35 * k, R_ALT if lv >= 4 else R_BLACK, 6, 1.05 * k)
        b.ball(ax, ay, zt + (6.6 + lv * 0.6) * k, 1.1 * k, R_LITE)
        b.box(0, -hy - 0.3 * k, 15.0 * k, 1.3 * k, 0.4 * k, 3.6 * k, R_METAL)
        b.box(-hx - 0.3 * k, 0, 10.0 * k, 0.5 * k, 2.4 * k, 7.0 * k, R_METAL, 0.85)
        b.line([(-hx - 0.1 * k, -hy + 2.0 * k, 8.0 * k), (-hx - 0.1 * k, hy - 2.0 * k, 8.0 * k)], COAL, 2)
        if lv >= 1:                                                                # rubber bumpers on the feet, signal
            for sx_ in (-1, 1):
                for sy in (-1, 1):
                    b.box(sx_ * (hx - 0.6 * k), sy * (hy - 0.5 * k), zb - 0.2 * k, 1.5 * k, 1.5 * k, 3.6 * k, R_DARK, 0.85)
            for q in range(1 + (lv >= 3)):
                xring(b, ax, ay, zt + (6.6 + lv * 0.6) * k, (2.6 + q * 1.8) * k, R_LITE, 8, 1)
        if lv >= 2:                                                                # shoulder guards and armour rails
            for sy in (-1, 1):
                b.box(0, sy * (hy - 0.6 * k) * 0.93, zt - 3.2 * k, hx * 0.93 + 0.5 * k, 1.4 * k, 3.6 * k, R_DARK, 0.9)
                b.box(0, sy * (hy + 0.25 * k), 7.5 * k, 2.4 * k, 0.5 * k, 5.0 * k, R_METAL)
        if lv >= 3:                                                                # second aerial, battery pack
            b.bar((ax, -ay, zt - 0.6 * k), (ax, -ay, zt + 3.4 * k), 0.9 * k, R_METAL, 5, 0.6 * k)
            b.ball(ax, -ay, zt + 3.9 * k, 0.8 * k, R_WHITE)
            b.box(-hx - 0.9 * k, 0, 3.0 * k, 0.9 * k, 4.6 * k, 5.6 * k, R_DARK, 0.9)
            b.line([(-hx - 1.9 * k, -3.0 * k, 5.8 * k), (-hx - 1.9 * k, 3.0 * k, 5.8 * k)], R_LITE, 2)
        if lv >= 4:                                                                # gold where it shows
            e = 0.12
            for sy in (-1, 1):
                b.line([(hx + e, sy * (hy - c), zb), (hx * 0.93 + e, sy * (hy - c) * 0.93, zt)], R_ALT, 2)
                b.line([(-hx - e, sy * (hy - c), zb), (-hx * 0.93 - e, sy * (hy - c) * 0.93, zt)], R_ALT, 2)
            b.ring(0, 0, 0.6, (hy + 3.4 * k), R_ALT, 16, 2)
            halo(b, zt + 12.5 * k, 6.0)


    # ====================================================================== SUMMONER (new)
    def tm2_summoner(b, lv):
        """a war shrine: the gate the goons are called through, a banner, a brazier, a horn"""
        z = pad2(b, lv, 13)
        gw = 5.0 + lv * 0.35                                   # half the width of the gateway
        hp = 10.5 + lv * 1.25                                  # height of the pillars
        gx = -1.6
        py = gw + 1.6
        gold = R_ALT if lv >= 4 else R_METAL
        b.box(gx, 0, z - 0.2, 2.6, py + 2.3, 1.5, R_METAL, 0.94)                    # threshold
        b.box(gx + 4.2, 0, z - 0.4, 1.8, gw + 0.4, 1.0, R_DARK, 0.9)                # step
        zp = z + 1.3
        for s in (-1, 1):
            b.box(gx, s * py, zp, 1.7, 1.7, hp, R_MAIN, 0.84)                       # pillars
            for q in range(3):
                zz = zp + hp * (0.2 + q * 0.24)
                b.line([(gx + 1.62 - q * 0.08, s * py - 0.7, zz), (gx + 1.60 - q * 0.08, s * py + 0.7, zz + (0.9 if q % 2 else -0.9))], R_LITE, 2)
            if lv >= 1:
                b.box(gx, s * py, zp + hp, 2.0, 2.0, 1.3, gold, 1.12)               # capitals
        zt = zp + hp + (1.3 if lv >= 1 else 0.0)
        pk = 4.4 + lv * 0.45
        ow = py + 2.3
        ext(b, "x", [(-ow, zt), (ow, zt), (ow, zt + 1.5), (0, zt + 1.5 + pk), (-ow, zt + 1.5)], gx - 1.5, gx + 1.5, R_DARK, R_MAIN, skip=(0,))   # the gable
        b.line([(gx + 1.56, -ow, zt + 1.5), (gx + 1.56, 0, zt + 1.5 + pk), (gx + 1.56, ow, zt + 1.5)], R_ALT if lv >= 4 else R_LITE, 2)
        b.crystal(gx + 1.6, 0, zt + 0.7, 1.3, 3.0, R_LITE, 4, TAU / 8)              # keystone
        # the portal
        b.slab([(gx, -gw - 0.2, zp - 0.2), (gx, gw + 0.2, zp - 0.2), (gx, gw + 0.2, zt), (gx, -gw - 0.2, zt)], R_LITE, False)
        zm = (zp + zt) / 2.0
        for e in (-0.12, 0.12):
            for q, (r_, role) in enumerate(((0.80, R_WHITE), (0.50, R_WHITE), (0.22, R_WHITE))):
                pts = [(gx + e, math.cos(i * TAU / 10 + q) * gw * r_, zm + math.sin(i * TAU / 10 + q) * (zt - zp) * 0.5 * r_) for i in range(10)]
                b.line(pts, role, 1 + (q == 2), True)
        b.glow(gx, 0, zm, gw * 2.4, R_LITE, 0.6)
        if lv >= 2:                                            # somebody is already on the way through
            gz = zp - 0.2
            for e in (-0.2, 0.2):
                plate(b, [(gx + e, -1.5, gz), (gx + e, 1.5, gz), (gx + e, 1.9, gz + 4.6), (gx + e, 0.9, gz + 4.9), (gx + e, 0.9, gz + 6.6), (gx + e, 0, gz + 7.4),
                          (gx + e, -0.9, gz + 6.6), (gx + e, -0.9, gz + 4.9), (gx + e, -1.9, gz + 4.6)], R_WHITE, (e, 0, 0), False)
        # the war banner
        bx_, by_ = -8.4, -8.6
        zf = zt + pk + 4.0 + lv * 0.6
        b.bar((bx_, by_, z - 1.0), (bx_, by_, zf), 0.55, R_METAL, 3)
        b.ball(bx_, by_, zf + 0.7, 0.95, gold if lv >= 4 else R_LITE)
        bl = 9.0 + lv * 0.9
        fw = 2.8 + lv * 0.12
        b.line([(bx_ + 0.1, by_ - fw - 0.5, zf - 1.0), (bx_ + 0.1, by_ + fw + 0.5, zf - 1.0)], gold, 3)
        b.slab([(bx_ + 0.3, by_ - fw, zf - 1.0), (bx_ + 0.3, by_ + fw, zf - 1.0), (bx_ + 0.6, by_ + fw, zf - 1.0 - bl), (bx_ + 0.5, by_, zf + 1.4 - bl), (bx_ + 0.6, by_ - fw, zf - 1.0 - bl)], R_MAIN)
        zc = zf - 1.0 - bl * 0.42
        plate(b, [(bx_ + 0.75, by_, zc + 2.2), (bx_ + 0.75, by_ + 1.7, zc), (bx_ + 0.75, by_, zc - 2.2), (bx_ + 0.75, by_ - 1.7, zc)], R_LITE, (1, 0, 0), False)
        if lv >= 4:
            b.line([(bx_ + 0.4, by_ - fw, zf - 1.0), (bx_ + 0.7, by_ - fw, zf - 1.0 - bl), (bx_ + 0.6, by_, zf + 1.4 - bl), (bx_ + 0.7, by_ + fw, zf - 1.0 - bl), (bx_ + 0.4, by_ + fw, zf - 1.0)], R_ALT, 2)
        # the brazier
        fx_, fy = 7.4, 8.0
        b.prism(4, fx_, fy, z - 0.8, 1.3, 4.0, R_METAL, rtop=0.5)
        b.prism(6, fx_, fy, z + 3.0, 1.3, 1.7, R_DARK, rtop=2.7)
        flame(b, fx_, fy, z + 4.3, 1.7, 4.4 + lv * 0.3)
        if lv >= 1:                                            # shields against the pillars
            for s in (-1, 1):
                xs, ys = gx + 2.3, s * py
                plate(b, [(xs, ys - 1.9, zp + 4.6), (xs, ys + 1.9, zp + 4.6), (xs + 0.9, ys + 1.9, zp + 1.8), (xs + 1.4, ys, zp + 0.1), (xs + 0.9, ys - 1.9, zp + 1.8)], R_METAL, (1, 0, 0.3))
                b.ball(xs + 0.6, ys, zp + 3.0, 0.75, gold if lv >= 4 else R_LITE)
        if lv >= 2:                                            # the horn, on its rest
            hx_, hy_ = 7.6, -7.8
            b.bar((hx_ - 2.2, hy_ - 2.4, z + 3.4), (hx_ - 0.4, hy_ - 0.2, z + 3.6), 0.6, gold, 4, 1.1)
            b.bar((hx_ - 0.4, hy_ - 0.2, z + 3.6), (hx_ + 1.4, hy_ + 2.6, z + 5.4), 1.1, R_WHITE, 4, 2.1)
            b.line([(hx_ - 0.6, hy_ - 1.0, z - 0.4), (hx_ - 0.7, hy_ - 0.6, z + 3.0)], R_METAL, 3)
            b.line([(hx_ + 0.4, hy_ + 1.4, z - 0.4), (hx_ + 0.3, hy_ + 0.9, z + 3.4)], R_METAL, 3)
            b.line([(gx + 1.3, -3.4, zt + 0.5), (gx + 1.3, 3.4, zt + 0.5)], gold, 2)                              # spears crossed behind
        if lv >= 3:                                            # torches on the pillars, crossed swords on the gable
            for s in (-1, 1):
                p0, p1 = (gx, s * (py + 1.5), zp + hp * 0.55), (gx + 0.6, s * (py + 3.2), zp + hp * 0.55 + 2.6)
                b.bar(p0, p1, 0.55, R_METAL, 3, 0.95)
                b.ball(p1[0], p1[1], p1[2] + 0.9, 1.25, R_LITE)
                b.ball(p1[0], p1[1], p1[2] + 2.0, 0.7, R_WHITE)
                b.glow(p1[0], p1[1], p1[2] + 1.2, 5, R_LITE, 0.6)
                b.line([(gx + 1.62, s * 4.6, zt + 1.9), (gx + 1.62, -s * 2.6, zt + 1.2 + pk * 0.55)], R_WHITE, 2)
        # the summoning stone over the gate
        zs = zt + 1.5 + pk + 3.4
        if lv >= 4:
            for s in (-1, 1):                                  # wings on the gable
                b.slab([(gx - 0.4, s * 1.0, zt + pk + 0.6), (gx - 0.8, s * 7.4, zt + pk + 4.4), (gx - 0.8, s * 6.0, zt + pk + 1.6), (gx - 0.6, s * 4.4, zt + pk - 0.6)], R_ALT)
            halo(b, zs + 0.6, 6.0)
            b.crystal(0.0, 0, -3.0, 1.8, 5.4, R_LITE, 4)
            b.glow(0.0, 0, -0.3, 8, R_LITE, 0.6)
        elif lv >= 2:
            b.group(M_SPIN | M_BOB, 1.1, gx, 0, zs, 1.8, 0.7)
            b.crystal(0, 0, -2.4, 1.5 + (lv >= 3) * 0.3, 4.8, R_LITE, 4)
            b.ring(0, 0, 0, 3.4, R_WHITE, 8, 1)
            b.glow(0, 0, 0, 7, R_LITE, 0.6)


    # ====================================================================== THE GOON (the Summoner's soldier)
    def gm2_goon(b, lv):
        """a little knight on our side: he walks along +x, the sword arm strikes, armour gets heavier with the level"""
        gold = R_ALT if lv >= 4 else R_METAL
        for s, ph in ((-1, 0.0), (1, math.pi)):                                    # legs
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 3.0, 1.5)
            b.box(0.6, s * 2.0, 0, 1.7, 1.15, 1.3, R_BLACK)
            b.box(0.0, s * 2.0, 1.3, 1.1, 1.05, 3.6, R_METAL, 0.85)
            if lv >= 3:
                b.box(1.05, s * 2.0, 3.0, 0.5, 1.0, 1.5, gold)
        b.group(M_AIM)
        if lv < 2:
            b.box(0, 0, 4.6, 1.9, 2.9, 1.7, R_DARK, 0.9)                           # belt
        else:
            hull(b, -2.4, 2.4, 3.5, 4.3, 2.2, R_DARK, nose=0.9, tail=0.9, topw=2.6)     # skirt of plates
        hull(b, -2.2, 2.5, 2.7, 6.2, 4.6, R_MAIN, nose=-0.3, tail=-0.2, topw=3.5)   # cuirass: broad at the shoulders
        b.line([(2.85, -1.7, 10.0), (2.7, 0, 7.6), (2.85, 1.7, 10.0)], R_LITE, 2)
        b.box(0.3, 0, 10.8, 1.7, 1.7, 3.0, R_METAL, 0.8)                           # helmet
        b.line([(2.0, -1.15, 12.5), (2.0, 1.15, 12.5)], R_WHITE, 2)
        b.line([(2.03, 0, 12.5), (2.08, 0, 11.2)], R_WHITE, 2)
        ph_ = 15.8 + lv * 0.25
        b.slab([(-1.0, 0, 13.7), (1.5, 0, 13.7), (0.9, 0, ph_), (-1.8, 0, ph_ - 0.3), (-3.2, 0, 12.8)], R_LITE)      # plume
        # shield arm
        b.bar((0, -3.7, 9.9), (2.6, -4.3, 7.4), 0.95, R_DARK, 4)
        sw, sh = 2.5 + lv * 0.2, 6.2 + lv * 0.35
        sx, sy, sz = 3.7, -4.5, 4.2
        if lv < 2:
            b.slab([(sx, sy - sw, sz + sh), (sx, sy + sw, sz + sh), (sx, sy + sw, sz + sh * 0.4), (sx, sy, sz), (sx, sy - sw, sz + sh * 0.4)], R_MAIN)
        else:
            b.mesh([(sx, sy - sw, sz + sh), (sx, sy + sw, sz + sh), (sx, sy + sw, sz + sh * 0.4), (sx, sy, sz), (sx, sy - sw, sz + sh * 0.4),
                    (sx + 0.9, sy - sw + 0.5, sz + sh - 0.5), (sx + 0.9, sy + sw - 0.5, sz + sh - 0.5), (sx + 0.9, sy + sw - 0.5, sz + sh * 0.42), (sx + 0.9, sy, sz + 0.7), (sx + 0.9, sy - sw + 0.5, sz + sh * 0.42)],
                   [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9), (0, 1, 6, 5), (1, 2, 7, 6), (2, 3, 8, 7), (3, 4, 9, 8), (4, 0, 5, 9)], [R_DARK, R_MAIN, gold, gold, gold, gold, gold])
            sx += 0.95
        b.line([(sx + 0.08, sy, sz + 1.0), (sx + 0.08, sy, sz + sh - 0.6)], R_LITE, 2)
        b.line([(sx + 0.08, sy - sw + 0.6, sz + sh * 0.66), (sx + 0.08, sy + sw - 0.6, sz + sh * 0.66)], R_LITE, 2)
        if lv >= 4:
            b.ball(sx + 0.3, sy, sz + sh * 0.66, 0.85, R_ALT)
        if lv >= 1:                                                                # shoulder plates
            for s in (-1, 1):
                b.box(0, s * 3.9, 9.9, 1.7, 1.4, 1.6, gold if lv >= 4 else R_METAL, 0.65)
        if lv >= 3:                                                                # cape
            b.slab([(-2.5, -2.6, 10.6), (-2.5, 2.6, 10.6), (-4.8, 3.4, 3.5), (-4.8, -3.4, 3.5)], R_MAIN)
            if lv >= 4:
                b.line([(-2.55, -2.6, 10.6), (-4.85, -3.4, 3.5), (-4.85, 3.4, 3.5), (-2.55, 2.6, 10.6)], R_ALT, 2)
        if lv >= 4:                                                                # a crowned helm
            b.ring(0.3, 0, 13.3, 1.9, R_ALT, 8, 3)
        # sword arm
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 4.0, 1.5)
        b.bar((0, 3.7, 9.9), (3.2, 4.5, 8.6), 0.95, R_DARK, 4)
        b.ball(3.5, 4.5, 8.6, 1.05, R_METAL)
        L = 9.0 + lv * 0.6
        dx, dz = 0.50, 0.866
        hx_, hz = 3.6, 8.8
        b.line([(hx_ - dz * 1.5, 4.5, hz + dx * 1.5 + 0.9), (hx_ + dz * 1.5, 4.5, hz - dx * 1.5 + 0.9)], gold, 3)     # crossguard
        b.slab([(hx_ - dz * 0.75 + dx * 1.0, 4.5, hz + dx * 0.75 + dz * 1.0), (hx_ + dz * 0.75 + dx * 1.0, 4.5, hz - dx * 0.75 + dz * 1.0),
                (hx_ + dz * 0.6 + dx * (L - 1.6), 4.5, hz - dx * 0.6 + dz * (L - 1.6)), (hx_ + dx * L, 4.5, hz + dz * L),
                (hx_ - dz * 0.6 + dx * (L - 1.6), 4.5, hz + dx * 0.6 + dz * (L - 1.6))], R_LITE)
        b.slab([(hx_ + dx * 1.0, 4.5 - 0.42, hz + dz * 1.0), (hx_ + dx * (L - 1.0), 4.5 - 0.3, hz + dz * (L - 1.0)),
                (hx_ + dx * (L - 1.0), 4.5 + 0.3, hz + dz * (L - 1.0)), (hx_ + dx * 1.0, 4.5 + 0.42, hz + dz * 1.0)], R_WHITE, False)    # its ridge
        b.ball(hx_ - dx * 1.2, 4.5, hz - dz * 1.2, 0.6, gold)
        if lv >= 3:
            b.glow(hx_ + dx * L, 4.5, hz + dz * L, 4, R_LITE, 0.5)
        return 13.8, 0.3, 2.1


    TOWERS2B = {"graviton": tm2_graviton, "prism": tm2_prism, "annihilator": tm2_annihilator, "pumpkin": tm2_pumpkin, "snow": tm2_snow, "duck": tm2_duck,
                "toaster": tm2_toaster, "cat": tm2_cat, "stonks": tm2_stonks, "brick": tm2_brick, "summoner": tm2_summoner}
    GOONS2B = {"goon": gm2_goon}
    return TOWERS2B, gm2_goon


def _mk2_enemies():
    # NEON BASTION mk II enemies: all 17, animatable.
    #
    # Every function is em2_<model>(b) -> (top, hx, hr): the height of the top of its head, the x of the head and a
    # head radius (the map theme puts its headgear there).  Everything walks along +x, z is up.
    #
    # Animation groups (see MODELS_BRIEF.md):
    #   walkers   legs (2 x M_AIM | M_STEP, left = phase 0, right = pi), body (M_AIM), striking parts (M_AIM | M_STRIKE)
    #   hoverers  M_AIM | M_BOB body; a striking part that has to bob with its body is M_AIM | M_BOB | M_STRIKE and
    #             carries the SAME two numbers as the body's bob (bob speed doubles as thrust, bob height as lift)
    #   group order is always: legs, body, striking part, spinner
    #
    # How the renderer orders groups: all groups of an enemy share one origin, so the only thing it can go by is height -
    # the group whose middle is lower is drawn first.  Arms and fists hang low but have to be drawn OVER the body, so
    # those groups get an invisible marker high up (_over) that lifts their middle above the body's.

    M_STEP, M_STRIKE = 16, 32
    DUCK_Y = (255, 214, 40)
    DUCK_Y2 = (236, 188, 26)
    DUCK_O = (255, 150, 30)
    DUCK_O2 = (226, 108, 22)
    SHADES = (14, 14, 24)


    # ---------------------------------------------------------------------- helpers
    def _over(b, z):
        """an invisible marker at height z: it only moves the middle of the group, so the group is drawn after lower ones"""
        b.line([(0.0, 0.0, z)], R_BLACK)


    def _leg(b, x, y, z0, h, w, role=R_DARK, foot=R_BLACK):
        b.box(x + w * 0.35, y, 0, w * 1.35, w * 0.95, z0 + 1.2, foot)
        b.box(x, y, z0 + 1.2, w, w * 0.9, h, role, 0.8)


    def _solid(b, x, y, prof, n, role, rot=0.0, sx=1.0, sy=1.0, alt=None, cap=None, edge=True):
        """a turned shape as ONE convex part.  prof = [(radius, height), ...] from the bottom up; radius 0 at an end is a point.
        role: one role or one per band; alt: the role of every second facet (a cut gem); cap: the role of the flat top"""
        vs, rings = [], []
        for r, z in prof:
            if r <= 0.01:
                rings.append([len(vs)])
                vs.append((x, y, z))
            else:
                rings.append(list(range(len(vs), len(vs) + n)))
                vs += [(x + math.cos(rot + i * TAU / n) * r * sx, y + math.sin(rot + i * TAU / n) * r * sy, z) for i in range(n)]
        fs, rl = [], []
        for k in range(len(prof) - 1):
            a, c = rings[k], rings[k + 1]
            ro = role[k] if isinstance(role, list) else role
            for i in range(n):
                j = (i + 1) % n
                if len(a) == 1:
                    fs.append((a[0], c[i], c[j]))
                elif len(c) == 1:
                    fs.append((a[i], a[j], c[0]))
                else:
                    fs.append((a[i], a[j], c[j], c[i]))
                rl.append(alt if alt is not None and (i + k) % 2 else ro)
        if len(rings[-1]) > 1:
            fs.append(tuple(rings[-1]))
            rl.append(cap if cap is not None else role[-1] if isinstance(role, list) else role)
        b.mesh(vs, fs, rl, edge)


    def _gem(b, p0, p1, r, role, n=4, mid=0.5, rot=0.0, alt=None):
        """a crystal between two points, so it can lean"""
        ax = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        d = math.sqrt(ax[0] ** 2 + ax[1] ** 2 + ax[2] ** 2) or 1.0
        ax = (ax[0] / d, ax[1] / d, ax[2] / d)
        up = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)
        sd = (ax[1] * up[2] - ax[2] * up[1], ax[2] * up[0] - ax[0] * up[2], ax[0] * up[1] - ax[1] * up[0])
        k = math.sqrt(sd[0] ** 2 + sd[1] ** 2 + sd[2] ** 2) or 1.0
        sd = (sd[0] / k, sd[1] / k, sd[2] / k)
        u2 = (sd[1] * ax[2] - sd[2] * ax[1], sd[2] * ax[0] - sd[0] * ax[2], sd[0] * ax[1] - sd[1] * ax[0])
        pm = [p0[i] + (p1[i] - p0[i]) * mid for i in range(3)]
        vs = []
        for i in range(n):
            a = rot + i * TAU / n
            c, s = math.cos(a) * r, math.sin(a) * r
            vs.append((pm[0] + sd[0] * c + u2[0] * s, pm[1] + sd[1] * c + u2[1] * s, pm[2] + sd[2] * c + u2[2] * s))
        vs += [tuple(p1), tuple(p0)]
        fs = [(i, (i + 1) % n, n) for i in range(n)] + [(i, (i + 1) % n, n + 1) for i in range(n)]
        rl = [alt if alt is not None and i % 2 else role for i in range(n)] * 2
        b.mesh(vs, fs, rl)


    # ====================================================================== PART 1: the nine from the concept, animatable
    def em2_grunt(b):
        """a little trooper: legs, chest plate, visor, a rifle and a backpack aerial"""
        for s, ph in ((1, 0.0), (-1, math.pi)):
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 2.4, 1.2)
            _leg(b, 0.0, s * 2.7, 0, 4.2, 1.5)
        b.group(M_AIM)
        hull(b, -3.2, 3.4, 3.7, 5.2, 5.4, R_MAIN, nose=0.9, tail=0.5, topw=4.5)
        b.line([(3.0, -2.6, 8.6), (3.0, 2.6, 8.6)], R_LITE, 2)
        b.box(0.5, 0, 10.6, 2.3, 2.5, 3.0, R_DARK, 0.85)
        b.slab([(2.85, -1.9, 11.5), (2.85, 1.9, 11.5), (2.75, 1.6, 12.7), (2.75, -1.6, 12.7)], R_LITE)
        b.bar((-0.5, -4.9, 9.2), (1.8, -5.0, 6.6), 1.0, R_DARK, 4)
        b.box(-4.0, 0, 6.2, 1.1, 2.4, 3.6, R_METAL)
        b.line([(-4.2, 1.6, 9.8), (-5.2, 1.6, 15.0)], R_METAL, 1)
        b.ball(-5.2, 1.6, 15.2, 0.6, R_LITE)
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 2.6, 0.8)          # the rifle arm jabs
        b.bar((-0.5, 4.9, 9.2), (1.5, 5.0, 7.0), 1.0, R_DARK, 4)
        b.bar((0.5, 5.0, 7.0), (8.0, 4.6, 7.4), 0.85, R_METAL, 4)
        b.ball(8.2, 4.6, 7.4, 0.8, R_WHITE)
        _over(b, 17.5)
        return 13.6, 0.5, 2.6


    def em2_runner(b):
        """a hover dart: needle hull, swept wings, canopy, twin thrusters"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 2.2, 5.0, 0.7)
        N, L, R_, TL, TR, T, B = (12.5, 0, 3.4), (-3, -4.4, 3.6), (-3, 4.4, 3.6), (-8.5, -2.2, 4.2), (-8.5, 2.2, 4.2), (-2.5, 0, 7.0), (-1.5, 0, 1.4)
        b.mesh([N, L, R_, TL, TR, T, B], [(0, 1, 5), (0, 5, 2), (1, 3, 5), (5, 3, 4), (5, 4, 2), (0, 6, 1), (0, 2, 6), (1, 6, 3), (6, 4, 3), (2, 4, 6)], R_MAIN)
        for s in (-1, 1):
            b.slab([(0.5, s * 3.6, 3.7), (-9.5, s * 8.8, 5.2), (-7.0, s * 3.4, 4.0)], R_LITE)
            b.bar((-7.5, s * 1.9, 3.7), (-11.0, s * 1.9, 3.7), 1.25, R_METAL, 6)
            b.ball(-11.3, s * 1.9, 3.7, 1.0, R_WHITE)
        b.slab([(-4.0, 0, 6.2), (-10.5, 0, 10.5), (-8.5, 0, 4.6)], R_MAIN)
        b.crystal(3.6, 0, 3.9, 1.5, 3.0, R_WHITE, 4, 0, 0.4)
        b.glow(-11.5, 0, 3.7, 7, R_LITE, 0.6)
        return 9.5, -2, 2.6


    def em2_swarm(b):
        """a wasp drone: there are always dozens, so it stays simple"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 3.0, 9.0, 0.8)
        b.ball(-1.0, 0, 2.4, 3.6, R_MAIN)
        b.ball(2.6, 0, 3.0, 2.3, R_DARK)
        b.ball(4.2, 0, 3.4, 1.0, R_WHITE)
        for s in (-1, 1):
            b.slab([(0.5, s * 1.5, 5.0), (-5.5, s * 7.5, 7.6), (-4.5, s * 2.0, 5.2)], R_LITE)
        b.bar((-4.0, 0, 2.2), (-8.2, 0, 1.2), 1.1, R_METAL, 4, 0.1)
        return 9.5, 0, 2.4


    def em2_tank(b):
        """tracks, sloped armour, fenders, a turret with a muzzle brake, a hatch and exhausts.  The turret kicks when it rams."""
        b.group(M_AIM)
        for s in (-1, 1):
            hull(b, -13.0, 13.0, 2.7, 0, 5.6, R_BLACK, nose=3.0, tail=3.0, y=s * 10.6)
            for wx in (-8.5, -3.0, 2.5, 8.0):
                b.ball(wx, s * 13.2, 2.5, 1.7, R_METAL)
            b.box(0, s * 10.6, 5.6, 10.0, 2.7, 1.0, R_MAIN)                      # the fender lies right on the track
            b.slab([(10.0, s * 7.9, 6.6), (10.0, s * 13.3, 6.6), (12.4, s * 13.3, 3.6), (12.4, s * 7.9, 3.6)], R_MAIN)   # mudguard
            b.line([(-9.5, s * 13.4, 6.1), (9.5, s * 13.4, 6.1)], R_LITE, 2)
        hull(b, -11.5, 12.0, 8.0, 2.4, 6.0, R_DARK, nose=5.5, tail=2.0, topw=6.6)
        for s in (-1, 1):
            b.bar((-11.0, s * 4.0, 7.2), (-14.0, s * 4.0, 9.6), 1.1, R_METAL, 4)
            b.ball(-14.3, s * 4.0, 9.9, 0.9, R_LITE)
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 3.2, 0.0)
        lathe(b, -1.5, 0, [(7.2, 8.4), (7.2, 9.6), (5.8, 13.0)], 8, [R_DARK, R_MAIN], TAU / 16)
        b.box(4.6, 0, 9.4, 1.4, 3.2, 3.2, R_METAL)
        b.bar((5.5, 0, 11.0), (17.0, 0, 11.0), 1.5, R_METAL, 6)
        b.bar((16.5, 0, 11.0), (19.5, 0, 11.0), 2.2, R_LITE, 6)
        b.prism(8, -3.5, 2.2, 13.0, 2.2, 0.9, R_METAL)
        b.ball(-3.5, 2.2, 14.6, 0.9, R_WHITE)
        b.line([(-5.0, -3.5, 13.0), (-6.5, -3.5, 19.5)], R_METAL, 1)
        return 14.0, -3.5, 2.6


    def em2_shield(b):
        """the Shielder: a hovering emitter core that carries a curved wall of hard light in front of it"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 2.0, 2.2, 1.0)
        lathe(b, -1.0, 0, [(3.4, 0), (6.2, 3.0), (6.2, 7.5), (4.0, 11.0)], 6, [R_DARK, R_MAIN, R_DARK])
        b.ball(-1.0, 0, 13.4, 2.6, R_WHITE)
        b.glow(-1.0, 0, 13.4, 8, R_LITE, 0.6)
        for s in (-1, 1):
            b.bar((-1.0, s * 5.5, 6.5), (5.5, s * 8.5, 7.5), 0.9, R_METAL, 4)
            b.ball(5.8, s * 8.6, 7.5, 1.1, R_LITE)
        for i in range(3):                                   # three panels on an arc
            a0, a1 = -0.78 + i * 0.52, -0.78 + (i + 1) * 0.52
            p = lambda a, zz: (math.cos(a) * 11.0, math.sin(a) * 11.0, zz)
            b.slab([p(a0, 0.5), p(a1, 0.5), p(a1, 15.0 - abs(i - 1) * 2.0), p(a0, 15.0 - abs(i - 1) * 2.0)], R_LITE)
        b.ring(-1.0, 0, 5.2, 7.2, R_LITE, 12, 1)
        return 18.0, -1, 2.8


    def em2_healer(b):
        """the Mender: a round medic drone with a white cross, repair arms, an injector and a turning ring of light"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 3.0, 2.0, 1.0)
        lathe(b, 0, 0, [(3.5, 0), (7.4, 2.4), (7.4, 4.4), (5.2, 7.6)], 8, [R_DARK, R_WHITE, R_MAIN], TAU / 16)
        b.box(0, 0, 7.6, 4.6, 1.3, 1.1, R_WHITE)
        b.box(0, 0, 7.6, 1.3, 4.6, 1.1, R_WHITE)
        b.ball(6.6, 0, 3.6, 1.5, R_LITE)
        for i in range(3):
            a = math.pi + (i - 1) * 1.0
            ca, sa = math.cos(a), math.sin(a)
            b.line([(ca * 5.0, sa * 5.0, 1.5), (ca * 8.5, sa * 8.5, -2.2)], R_METAL, 2)
            b.ball(ca * 8.7, sa * 8.7, -2.5, 0.9, R_LITE)
        b.glow(0, 0, 0.0, 9, R_LITE, 0.5)
        b.group(M_AIM | M_BOB | M_STRIKE, 0, 0, 0, 3.0, 2.0, 1.0)      # the injector under its nose: bobs with the body, jabs
        b.bar((4.6, 0, 1.2), (9.6, 0, -1.6), 0.9, R_METAL, 3, 0.5)
        b.ball(10.0, 0, -1.8, 1.0, R_WHITE)
        b.group(M_SPIN | M_BOB, 1.6, 0, 0, 13.5, 2.0, 1.0)
        b.ring(0, 0, 0, 8.4, R_LITE, 14, 2)
        for i in range(2):
            b.crystal(math.cos(i * math.pi) * 8.4, math.sin(i * math.pi) * 8.4, -1.5, 1.2, 3.0, R_WHITE, 4)
        return 9.0, 0, 3.0


    def em2_elite(b):
        """the Elite: a commander in heavy plate with a gold crown, a cape and a glaive"""
        for s, ph in ((1, 0.0), (-1, math.pi)):
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 3.2, 1.6)
            _leg(b, 0.0, s * 4.4, 0, 6.6, 2.4, R_METAL)
            b.box(1.9, s * 4.4, 5.2, 1.0, 2.2, 2.4, R_ALT)
        b.group(M_AIM)
        b.box(0, 0, 8.0, 3.6, 6.4, 2.6, R_DARK, 0.9)
        hull(b, -4.4, 4.8, 5.4, 10.6, 8.4, R_MAIN, nose=-0.6, tail=-0.4, topw=7.4)
        b.line([(5.3, -4.4, 16.8), (5.3, 4.4, 16.8)], R_ALT, 2)
        b.ball(5.2, 0, 13.6, 1.7, R_WHITE)
        b.glow(5.2, 0, 13.6, 7, R_LITE, 0.5)
        for s in (-1, 1):
            b.prism(6, 0, s * 9.4, 17.4, 3.8, 3.4, R_METAL, rtop=2.2)
            b.prism(4, 0, s * 9.8, 20.8, 1.3, 3.6, R_ALT, rtop=0)
            b.bar((0, s * 9.4, 17.0), (3.5, s * 10.2, 10.0), 1.9, R_DARK, 4)
        b.box(0.6, 0, 19.0, 2.8, 2.7, 4.4, R_METAL, 0.85)
        b.slab([(3.5, -2.0, 20.6), (3.5, 2.0, 20.6), (3.4, 2.4, 21.9), (3.4, -2.4, 21.9)], R_LITE)
        for i in range(5):
            a = (i - 2) * 0.62
            b.prism(3, 0.6 + math.cos(a) * 2.4, math.sin(a) * 2.4, 23.4, 1.0, 3.2 + (i == 2) * 1.6, R_ALT, rtop=0)
        # the cape stops above the knees: the legs are drawn before the body, a longer cape would cover them from the front
        b.slab([(-4.5, -5.0, 18.6), (-4.5, 5.0, 18.6), (-10.5, 7.0, 8.4), (-10.5, -7.0, 8.4)], R_MAIN)
        b.line([(-4.55, -5.0, 18.6), (-10.55, -7.0, 8.4), (-10.55, 7.0, 8.4), (-4.55, 5.0, 18.6)], R_ALT, 2)
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 2.5, 4.0)          # the glaive: it slides up through the fist and stabs
        b.bar((4.0, 10.6, 1.0), (4.0, 10.6, 27.0), 0.7, R_METAL, 4)
        b.slab([(4.0, 10.6, 25.5), (9.5, 10.6, 30.5), (4.0, 10.6, 34.5), (2.4, 10.6, 29.5)], R_LITE)
        _over(b, 40.0)
        return 27.0, 0.6, 3.6


    def em2_jugger(b):
        """the Juggernaut: a walking wall - piston legs, a furnace in its chest, slab shoulders, two wrecking fists"""
        for s, ph in ((1, 0.0), (-1, math.pi)):
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 3.4, 1.8)
            b.box(1.5, s * 7.0, 0, 5.2, 3.8, 2.6, R_BLACK)
            b.box(0, s * 7.0, 2.6, 3.4, 3.2, 6.4, R_METAL, 0.85)
            b.box(2.2, s * 7.0, 6.0, 1.4, 3.6, 3.4, R_MAIN)
        b.group(M_AIM)
        for s in (-1, 1):
            b.bar((0.5, s * 14.4, 15.5), (8.2, s * 15.8, 9.2), 2.5, R_MAIN, 4, 3.0)
        hull(b, -9.5, 9.5, 11.0, 9.0, 12.5, R_DARK, nose=3.0, tail=1.5, topw=9.5)
        b.box(8.3, 0, 11.5, 1.2, 5.0, 6.5, R_METAL)
        b.ball(9.6, 0, 14.6, 2.6, R_WHITE)
        b.glow(9.8, 0, 14.6, 13, R_LITE, 0.8)
        for s in (-1, 1):
            b.mesh([(-6, s * 11.2, 16.5), (6.5, s * 11.2, 16.5), (5.0, s * 11.2, 25.5), (-4.5, s * 11.2, 25.5),
                    (-6, s * 16.0, 14.0), (6.5, s * 16.0, 14.0), (5.0, s * 15.0, 23.5), (-4.5, s * 15.0, 23.5)],
                   [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], R_MAIN)
            b.line([(6.6, s * 11.6, 17.5), (6.6, s * 15.6, 15.5)], R_LITE, 2)
        b.box(2.0, 0, 21.5, 3.4, 3.6, 4.0, R_MAIN, 0.8)
        b.slab([(5.45, -2.6, 22.6), (5.45, 2.6, 22.6), (5.2, 2.2, 24.2), (5.2, -2.2, 24.2)], R_LITE)
        for s in (-1, 1):
            b.bar((-7.0, s * 5.0, 21.0), (-8.5, s * 5.0, 29.0), 1.5, R_METAL, 6)
            b.ball(-8.6, s * 5.0, 29.6, 1.3, R_LITE)
        # the fists hang lower than the body and wide of it, so the renderer draws them before it from every side (lowest
        # group first); the arms stay on the body and the piston rod behind each fist bridges the gap when it punches
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 5.5, 1.0)
        for s in (-1, 1):
            b.box(10.4, s * 15.9, 2.2, 4.2, 4.0, 7.6, R_METAL, 0.9)
            b.line([(14.4, s * 12.6, 6.4), (14.4, s * 19.2, 6.4)], R_LITE, 3)
            b.bar((0.6, s * 15.9, 6.4), (6.6, s * 15.9, 6.4), 1.3, R_METAL, 4)
        return 26.0, 2.0, 4.2


    def em2_titan(b):
        """THE TITAN: a colossus - armoured legs, a reactor in its chest, cannon shoulders, a horned head"""
        for s, ph in ((1, 0.0), (-1, math.pi)):
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 5.0, 2.5)
            b.box(2.0, s * 10.0, 0, 8.0, 6.0, 4.0, R_BLACK)
            b.box(0, s * 10.0, 4.0, 5.2, 5.0, 9.0, R_METAL, 0.85)
            b.box(3.4, s * 10.0, 9.5, 2.0, 5.6, 5.0, R_MAIN)
            b.box(0, s * 10.0, 13.0, 6.0, 5.6, 7.0, R_DARK, 1.1)
            b.line([(5.5, s * 6.0, 6.0), (5.5, s * 14.0, 6.0)], R_LITE, 2)
        b.group(M_AIM)
        b.box(0, 0, 18.0, 6.5, 13.0, 4.5, R_DARK, 0.9)
        hull(b, -10.5, 11.0, 13.5, 22.5, 16.0, R_MAIN, nose=-1.5, tail=-1.0, topw=17.0)
        b.ball(11.6, 0, 28.5, 4.6, R_WHITE)
        b.glow(12.0, 0, 28.5, 26, R_LITE, 0.9)
        for k in (-1, 1):
            b.line([(12.6, k * 7.0, 24.5), (12.6, k * 7.0, 36.5)], R_LITE, 3)
        for s in (-1, 1):
            b.mesh([(-8, s * 17.0, 34.0), (9, s * 17.0, 34.0), (7, s * 17.0, 45.0), (-6, s * 17.0, 45.0),
                    (-8, s * 25.0, 31.0), (9, s * 25.0, 31.0), (7, s * 23.0, 42.0), (-6, s * 23.0, 42.0)],
                   [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], R_METAL)
        b.box(3.0, 0, 38.5, 5.0, 5.0, 7.0, R_DARK, 0.8)
        b.slab([(8.1, -3.6, 40.5), (8.1, 3.6, 40.5), (7.6, 3.0, 43.0), (7.6, -3.0, 43.0)], R_LITE)
        for s in (-1, 1):
            b.bar((1.0, s * 4.5, 44.0), (-3.0, s * 9.5, 53.0), 1.6, R_ALT, 4, 0.2)
        for i in range(4):
            b.slab([(-10.6, 0, 26.0 + i * 3.6), (-17.0 + i, 0, 30.0 + i * 3.6), (-10.6, 0, 29.0 + i * 3.6)], R_LITE)
        for s in (-1, 1):
            b.bar((2.0, s * 21.0, 44.0), (20.0, s * 21.0, 47.0), 2.6, R_DARK, 6)
            b.bar((19.0, s * 21.0, 46.8), (23.0, s * 21.0, 47.5), 3.4, R_LITE, 6)
            b.bar((0, s * 21.5, 31.0), (7.0, s * 23.5, 16.6), 4.2, R_DARK, 6)
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 6.5, 1.5)          # the fists (see the Juggernaut)
        for s in (-1, 1):
            b.box(8.5, s * 24.0, 9.0, 4.6, 4.4, 8.0, R_METAL)
            b.line([(13.3, s * 21.0, 13.0), (13.3, s * 27.0, 13.0)], R_LITE, 3)
            b.bar((-3.5, s * 24.0, 12.6), (4.5, s * 24.0, 12.6), 1.7, R_METAL, 4)
        return 46.0, 3.0, 5.5


    # ====================================================================== PART 2: the eight new ones
    def em2_splitter(b):
        """the Splitter: three crystal pods strapped into one frame, turning slowly - break the frame and you get three Minis"""
        b.group(M_SPIN | M_BOB, 0.8, 0, 0, 3.0, 2.4, 1.2)
        b.ball(0, 0, 9.0, 2.6, R_WHITE)                              # the charge that holds them together
        b.glow(0, 0, 9.0, 13, R_LITE, 0.7)
        b.bar((0, 0, 7.0), (0, 0, 19.2), 1.0, R_METAL, 4)            # the frame: a spine, a hub with three arms, a strap
        b.prism(6, 0, 0, 13.4, 3.0, 2.2, R_DARK, rtop=2.2)
        b.ball(0, 0, 20.2, 1.5, R_LITE)
        for i in range(3):
            a = i * TAU / 3
            ca, sa = math.cos(a), math.sin(a)
            _gem(b, (ca * 3.6, sa * 3.6, 0.0), (ca * 8.8, sa * 8.8, 21.0), 4.6, R_MAIN, 4, 0.45, TAU / 8)
            b.ball(ca * 8.9, sa * 8.9, 12.4, 1.25, R_WHITE)          # every pod has its own eye
            b.bar((ca * 1.8, sa * 1.8, 14.6), (ca * 6.4, sa * 6.4, 16.6), 0.9, R_METAL, 4)
            b.box(ca * 9.5, sa * 9.5, 8.2, 0.9, 2.7, 2.4, R_METAL, 1.0, a)
            b.ball(ca * 3.0, sa * 3.0, 0.6, 1.0, R_LITE)             # three little thrusters
        b.ring(0, 0, 9.4, 10.2, R_METAL, 12, 3)
        b.ring(0, 0, 9.4, 12.0, R_LITE, 12, 1)
        return 21.6, 0, 2.6


    def em2_mini(b):
        """what is left of a Splitter: one crystal pod with its eye, a thruster and a snapped bit of the strap"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 2.5, 3.0, 1.0)
        _gem(b, (-1.6, 0, 0.0), (2.4, 0, 12.5), 4.4, R_MAIN, 4, 0.45, TAU / 8)
        b.ball(3.5, 0, 7.4, 1.3, R_WHITE)
        b.box(-3.5, 0, 4.4, 0.9, 2.5, 2.4, R_METAL)
        for s in (-1, 1):
            b.line([(-3.5, s * 2.5, 5.6), (-2.2, s * 4.8, 5.9)], R_METAL, 2)
        b.bar((-2.0, 0, 2.6), (-5.4, 0, 1.0), 1.1, R_METAL, 4, 0.7)
        b.ball(-5.7, 0, 0.9, 0.9, R_LITE)
        return 12.0, 1.8, 2.0


    def em2_blinker(b):
        """the Blinker: a teleporter drone - two half shells with a gap of raw energy, inside spinning phase rings"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 3.0, 3.0, 1.2)
        r6 = TAU / 12
        _solid(b, 0, 0, [(0, -2.0), (6.6, 2.4), (6.6, 4.0)], 6, [R_DARK, R_MAIN], r6, cap=R_LITE)       # lower half, a glowing dish
        b.ball(0, 0, 6.8, 2.9, R_WHITE)
        b.glow(0, 0, 6.8, 12, R_LITE, 0.8)
        for i in range(3):                                            # arcs jumping the gap
            a = r6 + i * TAU / 3
            ca, sa = math.cos(a), math.sin(a)
            b.line([(ca * 6.4, sa * 6.4, 4.0), (ca * 4.6, sa * 4.6, 6.8), (ca * 6.4, sa * 6.4, 9.6)], R_LITE, 2)
        _solid(b, 0, 0, [(6.6, 9.6), (6.6, 11.2), (2.4, 14.2)], 6, [R_MAIN, R_DARK], r6, cap=R_METAL)   # upper half
        b.ball(5.2, 0, 12.2, 1.2, R_WHITE)
        for s in (-1, 1):
            b.line([(-0.6, s * 1.4, 14.2), (-2.8, s * 3.0, 18.4)], R_METAL, 1)
            b.ball(-2.9, s * 3.1, 18.7, 0.7, R_LITE)
        b.group(M_SPIN | M_BOB, 3.0, 0, 0, 9.8, 3.0, 1.2)
        b.ring(0, 0, 0, 10.2, R_LITE, 14, 2)
        for i in range(4):                                            # the old cross, now four phase vanes on the ring
            a = i * TAU / 4
            b.box(math.cos(a) * 10.2, math.sin(a) * 10.2, -1.0, 1.7, 0.7, 2.0, R_MAIN, 1.0, a)
        b.ring(0, 0, 0, 12.2, R_WHITE, 14, 1, 0.45)
        _over(b, 15.0)
        return 17.2, 0, 2.6


    def em2_phantom(b):
        """the Phantom: a hooded wraith - a floating cloak with a ragged hem, a pale face with two dark eyes, bone hands"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 2.0, 2.4, 1.6)
        n = 7
        b.prism(n, -0.5, 0, 3.0, 7.8, 10.2, R_MAIN, rtop=3.8)
        for i, ln in enumerate((2.4, 4.4, 2.8, 5.2, 5.0, 2.6, 4.2)):  # the hem: torn strips, longer at the back
            a0, a1 = i * TAU / n, (i + 1) * TAU / n
            am = (a0 + a1) * 0.5
            b.slab([(-0.5 + math.cos(a0) * 7.8, math.sin(a0) * 7.8, 3.0), (-0.5 + math.cos(a1) * 7.8, math.sin(a1) * 7.8, 3.0),
                    (-1.6 + math.cos(am) * 8.4, math.sin(am) * 8.4, 3.0 - ln)], R_MAIN)
        b.prism(6, -0.4, 0, 12.0, 5.8, 2.2, R_DARK, rtop=4.2, rot=TAU / 12)
        _solid(b, -0.4, 0, [(4.2, 13.6), (4.8, 17.0), (0, 21.8)], 6, R_MAIN, TAU / 12)       # the hood
        # the face: a pale mask in the opening of the hood (flat and just in front of it, so it always sorts right)
        b.slab([(4.5, -2.1, 17.2), (4.5, 2.1, 17.2), (4.5, 2.4, 15.3), (4.5, 1.1, 13.5), (4.5, -1.1, 13.5), (4.5, -2.4, 15.3)], R_LITE)
        for s in (-1, 1):
            b.ball(4.75, s * 1.0, 15.9, 0.72, R_BLACK)
            b.bar((0.4, s * 4.8, 12.8), (5.4, s * 5.6, 9.8), 1.5, R_MAIN, 4, 1.0)
        b.glow(0, 0, 2.0, 12, R_LITE, 0.45)
        b.group(M_AIM | M_BOB | M_STRIKE, 0, 0, 0, 2.0, 2.4, 1.6)     # the bone hands: bob with the cloak, claw forward
        for s in (-1, 1):
            b.ball(6.0, s * 5.7, 9.5, 0.8, R_WHITE)
            for k in (-1, 0, 1):
                b.line([(6.0, s * 5.7, 9.5), (8.2, s * (5.7 + k * 1.3), 9.0 + (k == 0) * 0.4), (9.0, s * (5.7 + k * 1.2), 7.2)], R_WHITE, 1)
        _over(b, 25.0)
        return 20.6, -0.4, 3.0


    def em2_overseer(b):
        """THE OVERSEER: a floating command citadel - one giant eye, two floating jaws, a ring of pylons, an antenna crown"""
        b.group(M_AIM | M_BOB, 0, 0, 0, 10.0, 1.3, 2.0)
        r8 = TAU / 16
        _solid(b, 0, 0, [(5.5, 0), (22.0, 7.0), (25.0, 9.0), (25.0, 12.0), (18.0, 16.0)], 8, [R_DARK, R_BLACK, R_MAIN, R_DARK], r8)
        b.ball(0, 0, -0.5, 4.2, R_LITE)                              # the lifter under the keel
        b.glow(0, 0, -3.0, 34, R_LITE, 0.9)
        b.ring(0, 0, 10.5, 25.6, R_LITE, 16, 2)
        for i in range(4):                                           # bastions on the deck
            a = TAU / 8 + i * TAU / 4
            ca, sa = math.cos(a), math.sin(a)
            b.box(ca * 19.5, sa * 19.5, 13.4, 2.8, 2.8, 6.2, R_METAL, 0.75, a)
            b.ball(ca * 19.5, sa * 19.5, 20.6, 1.4, R_LITE)
        b.prism(6, -2.0, 0, 16.0, 11.5, 8.0, R_MAIN, rtop=9.5)       # the keep
        b.ring(-2.0, 0, 20.5, 10.9, R_LITE, 12, 1)
        b.prism(6, -2.0, 0, 24.0, 7.6, 5.0, R_DARK, rtop=6.2, rot=TAU / 12)
        b.prism(6, -2.0, 0, 29.0, 4.6, 3.0, R_METAL, rtop=3.2)
        for i in range(5):                                           # the antenna crown
            a = math.pi + (i - 2) * 0.62
            ca, sa = math.cos(a), math.sin(a)
            b.line([(-2.0 + ca * 6.0, sa * 6.0, 29.0), (-2.0 + ca * 9.5, sa * 9.5, 38.0 + (i == 2) * 5.0)], R_METAL, 2 if i == 2 else 1)
            b.ball(-2.0 + ca * 9.6, sa * 9.6, 38.6 + (i == 2) * 5.0, 1.1, R_LITE)
        hull(b, 15.0, 27.5, 9.6, 3.6, 12.6, R_DARK, nose=2.5, tail=0.0, topw=7.4)      # the eye socket
        b.ball(26.5, 0, 9.6, 8.2, R_LITE)
        b.ball(33.0, 0, 9.9, 3.6, R_BLACK)
        b.ball(35.2, 1.4, 11.5, 1.0, R_WHITE)
        b.glow(30.0, 0, 9.6, 26, R_LITE, 0.8)
        b.box(25.6, 0, 16.2, 4.6, 8.6, 2.4, R_MAIN, 0.8)             # the armoured brow
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 8.0, 1.5)          # the jaws hover on their own and snap forward
        for s in (-1, 1):
            b.bar((15.0, s * 12.0, 8.0), (29.0, s * 10.5, 6.0), 3.6, R_METAL, 4, 2.8)
            b.bar((28.0, s * 10.5, 6.0), (39.0, s * 3.6, 4.0), 2.8, R_MAIN, 4, 0.4)
            b.ball(15.0, s * 12.0, 8.0, 2.6, R_LITE)
            b.line([(20.0, s * 14.4, 8.6), (28.0, s * 13.0, 7.2)], R_LITE, 2)
        b.group(M_SPIN | M_BOB, 0.9, 0, 0, 22.0, 1.3, 2.0)       # the ring of pylons
        b.ring(0, 0, 0, 32.0, R_LITE, 16, 2)
        for i in range(4):
            a = i * TAU / 4
            ca, sa = math.cos(a) * 32.0, math.sin(a) * 32.0
            b.bar((ca, sa, -8.0), (ca, sa, 6.0), 2.3, R_METAL, 4)
            b.prism(4, ca, sa, 6.0, 2.6, 5.0, R_MAIN, rtop=0, rot=a + TAU / 8)
            b.ball(ca, sa, -8.6, 1.5, R_LITE)
        _over(b, 30.0)
        return 42.0, -2.0, 4.6


    def em2_queen(b):
        """THE HIVE QUEEN: a giant insect - mandibles, a crowned head, six legs, a huge abdomen full of glowing eggs, wings"""
        legs = ((13.0, 4.0, 9.0), (8.0, 0.5, 0.5), (3.0, -4.0, -9.0))     # hip x, knee dx, foot dx
        for gi, ph in ((0, 0.0), (1, math.pi)):                  # two tripods: front-left + mid-right + rear-left, and the others
            b.group(M_AIM | M_STEP, ph, 0, 0, 0, 4.0, 2.6)
            for li, (lx, kdx, fdx) in enumerate(legs):
                s = 1 if (li + gi) % 2 == 0 else -1
                knee = (lx + kdx, s * 15.5, 19.0)
                b.bar((lx, s * 5.5, 12.5), knee, 1.6, R_DARK, 4, 1.2)
                b.bar(knee, (lx + fdx, s * 21.5, 0.0), 1.4, R_METAL, 4, 0.35)
                b.ball(knee[0], knee[1], knee[2], 1.7, R_MAIN)
        b.group(M_AIM)
        hull(b, 1.0, 17.0, 7.0, 9.5, 9.0, R_MAIN, nose=2.5, tail=1.0, topw=5.0)          # thorax
        hull(b, 15.5, 26.0, 5.2, 10.5, 8.0, R_DARK, nose=3.5, tail=0.5, topw=3.6)        # head
        for s in (-1, 1):
            b.ball(23.2, s * 4.5, 15.6, 2.3, R_LITE)
            b.line([(22.0, s * 2.0, 18.5), (28.0, s * 5.0, 25.5), (33.5, s * 6.5, 23.0)], R_METAL, 2)
        b.prism(5, 19.5, 0, 18.5, 2.8, 3.0, R_ALT, rtop=4.0)
        segs = (((1.0, 15.0), (-7.0, 18.0), 7.5, 11.0, R_MAIN), ((-7.0, 18.0), (-16.0, 20.5), 11.5, 13.0, R_DARK),
                ((-16.0, 20.5), (-25.0, 21.0), 13.0, 11.0, R_MAIN), ((-25.0, 21.0), (-32.0, 19.0), 10.5, 5.5, R_DARK))
        for (x0, z0), (x1, z1), ra, rb, role in segs:
            b.bar((x0, 0, z0), (x1, 0, z1), ra, role, 7, rb)
        b.bar((-31.5, 0, 19.0), (-39.0, 0, 13.5), 3.0, R_ALT, 4, 0.3)                    # sting
        for ex, ey, ez, er in ((-3.0, 6.6, 22.6, 2.8), (-11.5, 9.4, 27.4, 3.4), (-20.5, 9.2, 28.6, 3.4), (-28.5, 5.6, 25.4, 2.8)):
            for s in (-1, 1):
                b.ball(ex, s * ey, ez, er, R_WHITE)
        b.glow(-15.0, 0, 26.0, 30, R_LITE, 0.6)
        for s in (-1, 1):
            b.slab([(9.0, s * 2.5, 19.0), (-7.0, s * 11.5, 28.5), (-34.0, s * 8.0, 37.0), (-11.0, s * 2.0, 34.5)], R_LITE)   # wings, folded back
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 4.5, 1.0)          # the mandibles bite
        for s in (-1, 1):
            b.bar((23.0, s * 3.4, 11.5), (31.5, s * 6.4, 9.0), 1.9, R_METAL, 4, 1.4)
            b.bar((31.0, s * 6.4, 9.0), (36.5, s * 1.4, 7.4), 1.4, R_WHITE, 4, 0.2)
        return 21.5, 19.5, 4.0


    def em2_architect(b):
        """THE ARCHITECT: a cut crystal the size of a house, three rings at three speeds, four armoured blocks in a low orbit,
        a crown of shards in a high one and a gold halo"""
        b.group(M_SPIN | M_BOB, -0.7, 0, 0, 12.0, 1.5, 3.0)      # low orbit: the blocks and the wide ring
        for i in range(4):
            a = TAU / 8 + i * TAU / 4
            ca, sa = math.cos(a) * 29.0, math.sin(a) * 29.0
            b.box(ca, sa, -9.0, 4.6, 5.6, 10.0, R_DARK, 0.85, a)
            b.box(ca, sa, 1.0, 3.5, 4.4, 2.0, R_MAIN, 0.8, a)
            b.crystal(ca, sa, 3.6, 2.3, 6.4, R_LITE, 4, a)
            b.line([(ca * 1.17, sa * 1.17, -7.0), (ca * 1.15, sa * 1.15, -1.0)], R_LITE, 3)
        b.ring(0, 0, 2.0, 32.5, R_MAIN, 16, 2, 0.2)
        b.group(M_SPIN | M_BOB, 0.45, 0, 0, 12.0, 1.5, 3.0)      # the core
        b.glow(0, 0, 20.0, 50, R_LITE, 0.9)
        _solid(b, 0, 0, [(0, 0), (15.0, 17.0), (15.5, 23.0), (5.5, 40.0)], 8, [R_LITE, R_WHITE, R_LITE], alt=R_MAIN, cap=R_WHITE)
        b.ring(0, 0, 20.0, 21.5, R_WHITE, 16, 2, 0.9)
        b.group(M_SPIN | M_BOB, 1.2, 0, 0, 12.0, 1.5, 3.0)       # high orbit: the shards, the third ring, the halo
        b.ring(0, 0, 22.0, 26.5, R_LITE, 16, 2, -0.6, 2.0)
        for i, (rr, zz, hh, rd) in enumerate(((21.0, 30.0, 8.0, 2.2), (24.0, 37.0, 6.0, 1.7), (19.5, 33.0, 9.5, 2.5), (23.0, 28.0, 5.5, 1.6), (20.5, 38.0, 7.0, 2.0), (25.0, 32.0, 6.5, 1.8))):
            a = i * TAU / 6 + 0.3
            ca, sa = math.cos(a), math.sin(a)
            _gem(b, (ca * rr, sa * rr, zz), (ca * (rr + 2.0), sa * (rr + 2.0), zz + hh), rd, R_LITE, 3, 0.4)
        b.ring(0, 0, 47.0, 9.0, R_ALT, 16, 2)
        for i in range(3):
            a = i * TAU / 3
            b.crystal(math.cos(a) * 9.0, math.sin(a) * 9.0, 44.6, 1.7, 4.8, R_ALT, 4)
        return 52.0, 0, 5.0


    def em2_megaduck(b):
        """MEGA DUCK: a rubber duck the size of a bus, in sunglasses, with an angry brow and a tiny crown.
        The whole head pecks (QUACK)."""
        b.group(M_AIM)
        b.ring(0, 0, 0.6, 30.0, (150, 225, 255), 16, 1)              # it brings its own puddle
        b.ring(0, 0, 0.6, 24.0, (150, 225, 255), 16, 1)
        _solid(b, -3.0, 0, [(9.0, 1.5), (17.0, 6.0), (20.0, 14.0), (19.0, 23.0), (13.0, 30.0), (6.0, 33.0)], 8, DUCK_Y, TAU / 16, sx=1.22)
        b.bar((-22.0, 0, 22.0), (-35.0, 0, 35.0), 7.5, DUCK_Y, 5, 0.8)                  # tail
        for s in (-1, 1):
            hull(b, -17.0, 7.0, 3.0, 11.0, 10.0, DUCK_Y2, nose=7.0, tail=2.0, topw=1.2, y=s * 19.8)     # wings
        b.group(M_AIM | M_STRIKE, 0, 0, 0, 0, 4.5, 0.0)          # the head: it sits on top of the body, so it always sorts right
        # the head has an edge down the middle of its face, so each lens of the shades lies flat on one facet
        _solid(b, 13.0, 0, [(8.0, 30.0), (12.5, 35.0), (14.0, 42.0), (12.5, 50.0), (7.0, 55.0)], 8, DUCK_Y)
        hull(b, 22.5, 41.0, 7.5, 40.6, 3.6, DUCK_O, nose=4.0, tail=0.0, topw=5.6)       # the beak, a little open
        hull(b, 22.5, 37.5, 5.6, 36.6, 2.6, DUCK_O2, nose=3.0, tail=0.0, topw=5.0)
        b.box(28.0, 0, 39.2, 4.0, 4.4, 1.4, (60, 16, 20))
        ca, sa = math.cos(TAU / 16), math.sin(TAU / 16)
        for s in (-1, 1):                                            # shades
            cx, cy = 13.0 + ca * 12.9, s * sa * 12.9
            b.box(cx, cy, 44.2, 0.8, 3.8, 5.4, SHADES, 0.85, s * TAU / 16)
            g = lambda u, z: (cx + ca * 1.0 - sa * u, cy + s * (sa * 1.0 + ca * u), z)
            b.line([g(-1.8, 48.4), g(1.2, 45.6)], R_WHITE, 1)                            # a glint
            b.line([(cx - sa * 3.6, cy + s * ca * 3.6, 48.6), (13.4, s * 13.0, 48.4)], SHADES, 2)
            b.slab([(26.0, s * 0.6, 49.8), (20.8, s * 7.4, 52.8), (19.8, s * 6.2, 54.6), (24.7, s * 0.6, 51.8)], SHADES)   # the angry brow
        b.line([(26.6, -1.4, 48.4), (27.0, 0, 48.4), (26.6, 1.4, 48.4)], SHADES, 2)
        b.prism(5, 13.0, 0, 55.0, 3.2, 2.2, R_ALT, rtop=4.2)         # a very small crown
        for i in range(5):
            a = i * TAU / 5
            b.prism(3, 13.0 + math.cos(a) * 3.7, math.sin(a) * 3.7, 57.2, 1.1, 2.8, R_ALT, rtop=0)
        return 55.6, 13.0, 4.0


    ENEMIES2 = {"grunt": em2_grunt, "runner": em2_runner, "swarm": em2_swarm, "tank": em2_tank, "shield": em2_shield,
                "splitter": em2_splitter, "mini": em2_mini, "healer": em2_healer, "blinker": em2_blinker, "phantom": em2_phantom,
                "elite": em2_elite, "jugger": em2_jugger, "overseer": em2_overseer, "queen": em2_queen, "titan": em2_titan,
                "architect": em2_architect, "megaduck": em2_megaduck}
    return ENEMIES2


MK2_TOWERS = dict(TOWERS2)
MK2_TOWERS.update(_mk2_towers_a())
_tb, gm2_goon = _mk2_towers_b()
MK2_TOWERS.update(_tb)
MK2_ENEMIES = _mk2_enemies()
MK2 = {"on": True, "theme": None}        # what is being drawn right now: detailed models or not, and for which map theme
FAR_K = 0.62                             # things drawn smaller than this (pixels per unit) use the simple old models
_mk2_models = {}
_tower_model1, _enemy_model1, _goon_model1 = tower_model, enemy_model, goon_model


class TB(MB):
    """a model builder that knows which map it is building for: the theme swaps the metal, the dark armour and the deck"""

    def __init__(self, theme=None):
        MB.__init__(self)
        self.theme = theme if theme in THEMES2 else None
        T = THEMES2.get(self.theme)
        self.remap = {R_METAL: T["metal"], R_DARK: T["dark"], R_BLACK: T["black"]} if T else {}

    def role(self, r):
        if isinstance(r, int):
            r = self.remap.get(r, r)
        return MB.role(self, r)


def tower_model(kind, lv, far=False):
    fn = MK2_TOWERS.get(kind)
    if fn is None or far or not MK2["on"]:
        return _tower_model1(kind, lv)
    th = MK2["theme"] if MK2["theme"] in THEMES2 else None
    key = (kind, lv, th)
    m = _mk2_models.get(key)
    if m is None:
        b = TB(None)
        fn(b, lv)
        m = b.done()
        if th:
            top = m.top                 # labels, health bars and beams sit where they do without the decorations
            b = TB(th)
            fn(b, lv)
            m = b.done(top)
        if len(_mk2_models) > 900:
            _mk2_models.clear()
        _mk2_models[key] = m
    return m


def _walker_model(key, fn, th, r, arg=None, dress=True):
    m = _mk2_models.get(key)
    if m is None:
        b = TB(th)
        top, hx, hr = fn(b) if arg is None else fn(b, arg)
        if th and dress:
            dress_enemy(b, th, top, hx, hr, r)
        m = b.done()
        m.top = max(top + (hr * 2.4 if th and dress else 2.0), m.top / 1.5 + 3.0)
        if len(_mk2_models) > 900:
            _mk2_models.clear()
        _mk2_models[key] = m
    return m


def enemy_model(kind, skin=None, far=False):
    fn = MK2_ENEMIES.get(kind)
    if fn is None or far or not MK2["on"]:
        return _enemy_model1(kind, skin)
    th = MK2["theme"] if MK2["theme"] in THEMES2 else None
    return _walker_model(("e", kind, th), fn, th, ENEMIES.get(kind, {}).get("r", 12))


def goon_model(lv=0, far=False):
    """goons are ours: on a themed map they get the map's materials but none of the enemies' headgear"""
    if far or not MK2["on"]:
        return _goon_model1(lv)
    th = MK2["theme"] if MK2["theme"] in THEMES2 else None
    return _walker_model(("g", lv, th), gm2_goon, th, 8, lv, False)


# ======================================================================
#  THE SCENE  -  draws a whole match in 3D (or flat from above)
# ======================================================================
_land_models = {}


def _land_parts(b, h, nh, col, acc):
    """one raised square: a top, and a wall down to whatever is next to it on each side (north, east, south, west)"""
    a = CELL / 2.0
    lv = h / STEP
    top = mix_col(col, WHITE, 0.04 + 0.07 * (lv - 1))
    side = scale_col(mix_col(col, acc, 0.12), 0.72)
    vs = [(-a, -a, h), (a, -a, h), (a, a, h), (-a, a, h)]
    faces = [(0, 1, 2, 3)]
    roles = [top]
    edges = ((0, 1), (1, 2), (2, 3), (3, 0))
    low = []
    for i, (p, q) in enumerate(edges):
        if nh[i] < h:
            k = len(vs)
            vs += [(vs[p][0], vs[p][1], nh[i]), (vs[q][0], vs[q][1], nh[i])]
            faces.append((p, q, k + 1, k))
            roles.append(side)
            low.append((i, p, q, k, k + 1))
    b.mesh(vs, faces, roles, False)
    dim = scale_col(acc, 0.45)
    for i, p, q, k0, k1 in low:
        b.line([vs[p], vs[q]], R_LITE, 2)
        b.line([vs[k0], vs[k1]], dim, 1)
        if nh[(i + 3) % 4] < h:
            b.line([vs[k0], vs[p]], dim, 1)
    b.line([(-a + 8, a - 8, h + 0.1), (a - 8, -a + 8, h + 0.1)], mix_col(top, WHITE, 0.10), 1)


def land_model(h, nh, col, acc):
    key = (h, nh, col, acc)
    m = _land_models.get(key)
    if m is None:
        if len(_land_models) > 400:
            _land_models.clear()
        b = MB()
        _land_parts(b, h, nh, col, acc)
        m = _land_models[key] = b.done(h)
    return m


def clip_rect(pts, x0, y0, x1, y1):
    """cut a flat shape down to a rectangle"""
    for ax, lim, less in ((0, x0, False), (0, x1, True), (1, y0, False), (1, y1, True)):
        if len(pts) < 3:
            return []
        out = []
        a = pts[-1]
        ain = (a[ax] <= lim) if less else (a[ax] >= lim)
        for b in pts:
            bin_ = (b[ax] <= lim) if less else (b[ax] >= lim)
            if ain != bin_:
                t = (lim - a[ax]) / (b[ax] - a[ax])
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            if bin_:
                out.append(b)
            a, ain = b, bin_
        pts = out
    return pts if len(pts) >= 3 else []


def _face_up(poly):
    """list the corners so that the shape faces up"""
    a, b, c = poly[0], poly[1], poly[2]
    if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
        poly = poly[::-1]
    return poly


def build_cells(w):
    """every square of the map that is not plain floor -> {square: [model, top, hide info]}
    hide info = (highest point, ramp or None, bridge deck height or None), used to draw things in the right order"""
    th = w.theme
    acc = th["accent"]
    edge_c = scale_col(acc, 0.75)
    road_c = th["road"]
    bank_c = scale_col(mix_col(th["cliff"], acc, 0.12), 0.62)
    steel_c = mix_col((70, 76, 104), acc, 0.15)
    hm = w.hmap
    decals = {}         # square -> ([border shapes], [road shapes], [arrows])
    solids = {}         # square -> [(kind, a, b, across)]
    boxes = {}          # square -> height of a full-square block of road (a corner on a bank or bridge)

    def add_flat(poly, z, layer):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        for c in range(int((min(xs) + 0.01) // CELL), int((max(xs) - 0.01) // CELL) + 1):
            for r in range(int((min(ys) + 0.01) // CELL), int((max(ys) - 0.01) // CELL) + 1):
                cut = clip_rect(poly, c * CELL, r * CELL, c * CELL + CELL, r * CELL + CELL)
                if cut:
                    decals.setdefault((c, r), ([], [], []))[layer].append((cut, z))

    for cell, pieces in w.road_cells.items():
        for kind, a, b, n, pi, si in pieces:
            if kind == 1:
                for wd, layer, dz in ((ROAD_W + 3.0, 0, 0.06), (ROAD_W, 1, 0.3)):
                    add_flat([(a[0] + n[0] * wd, a[1] + n[1] * wd), (b[0] + n[0] * wd, b[1] + n[1] * wd), (b[0] - n[0] * wd, b[1] - n[1] * wd), (a[0] - n[0] * wd, a[1] - n[1] * wd)], a[2] + dz, layer)
            else:
                solids.setdefault(cell, []).append((kind, a, b, n, pi, si))
    for x, y, z, kind, cell in w.road_joints:
        if kind == 1:
            for wd, layer, dz in ((ROAD_W + 3.0, 0, 0.06), (ROAD_W, 1, 0.3)):
                add_flat([(x + math.cos(k * TAU / 10) * wd, y + math.sin(k * TAU / 10) * wd) for k in range(10)], z + dz, layer)
        elif kind == 2:
            boxes[cell] = z
    out = {}
    for cell in set(hm) | set(decals) | set(solids) | set(boxes):
        c, r = cell
        h = hm.get(cell, 0.0)
        cx, cy = (c + 0.5) * CELL, (r + 0.5) * CELL
        nh = (hm.get((c, r - 1), 0.0), hm.get((c + 1, r), 0.0), hm.get((c, r + 1), 0.0), hm.get((c - 1, r), 0.0))
        if cell not in decals and cell not in solids and cell not in boxes:
            out[cell] = [land_model(h, nh, th["cliff"], acc), h, (h, None, None), None]
            continue
        b = MB()
        bdeck = MB()            # bridge decks
        top = h
        ramp = None
        deck = None
        if h > 0:
            _land_parts(b, h, nh, th["cliff"], acc)
        if cell in decals:
            bd, rd, ar = decals[cell]
            vs, faces, roles = [], [], []
            for lst, col in ((bd, edge_c), (rd, road_c)):
                for poly, z in lst:
                    poly = _face_up(poly)
                    k = len(vs)
                    vs += [(p[0] - cx, p[1] - cy, z) for p in poly]
                    faces.append(tuple(range(k, k + len(poly))))
                    roles.append(col)
                    top = max(top, z)
            if faces:
                b.mesh(vs, faces, roles, False, False, False)
        if cell in boxes and cell not in solids:
            z = boxes[cell]
            a = CELL / 2.0
            b.box(0, 0, h, a, a, z - h, bank_c, edge=False)
            b.mesh([(-a, -a, z + 0.06), (a, -a, z + 0.06), (a, a, z + 0.06), (-a, a, z + 0.06)], [(0, 1, 2, 3)], edge_c, False, False, False)
            wd = ROAD_W
            b.mesh([(math.cos(k * TAU / 10) * wd, math.sin(k * TAU / 10) * wd, z + 0.3) for k in range(10)], [tuple(range(10))], road_c, False, False, False)
            top = max(top, z)
        groups = {}
        for kind, a, bb, n, pi, si in solids.get(cell, ()):
            groups.setdefault((pi, si, kind), []).append((a, bb, n))
        for (pi, si, kind), lst in groups.items():
            n = lst[0][2]
            ux, uy = n[1], -n[0]                     # the way the road runs
            lst.sort(key=lambda q: q[0][0] * ux + q[0][1] * uy)
            a, bb = lst[0][0], lst[-1][1]
            if kind == 3 and cell in boxes:
                pass
            wd = ROAD_W + 3.0
            za, zb = a[2], bb[2]
            if kind == 3:
                ba, b2 = za - 4.0, zb - 4.0
                deck = (za + zb) / 2.0
                col = steel_c
            else:
                ba = b2 = h
                col = bank_c
            ax, ay, bx, by = a[0] - cx, a[1] - cy, bb[0] - cx, bb[1] - cy
            vs = [(ax + n[0] * wd, ay + n[1] * wd, za), (ax - n[0] * wd, ay - n[1] * wd, za), (bx - n[0] * wd, by - n[1] * wd, zb), (bx + n[0] * wd, by + n[1] * wd, zb),
                  (ax + n[0] * wd, ay + n[1] * wd, ba), (ax - n[0] * wd, ay - n[1] * wd, ba), (bx - n[0] * wd, by - n[1] * wd, b2), (bx + n[0] * wd, by + n[1] * wd, b2)]
            bq = bdeck if kind == 3 else b
            bq.mesh(vs, [(0, 3, 7, 4), (1, 2, 6, 5), (0, 1, 5, 4), (3, 2, 6, 7), (0, 1, 2, 3)], [col, col, col, col, edge_c], False)
            wd = ROAD_W
            strip = _face3([(ax + n[0] * wd, ay + n[1] * wd, za + 0.3), (bx + n[0] * wd, by + n[1] * wd, zb + 0.3), (bx - n[0] * wd, by - n[1] * wd, zb + 0.3), (ax - n[0] * wd, ay - n[1] * wd, za + 0.3)])
            bq.mesh(strip, [(0, 1, 2, 3)], road_c, False, False, False)
            if kind == 3:
                for sg in (1, -1):
                    wd = ROAD_W + 3.0
                    bq.line([(ax + n[0] * wd * sg, ay + n[1] * wd * sg, za + 0.5), (bx + n[0] * wd * sg, by + n[1] * wd * sg, zb + 0.5)], R_LITE, 2)
                    bq.line([(ax + n[0] * wd * sg, ay + n[1] * wd * sg, ba), (bx + n[0] * wd * sg, by + n[1] * wd * sg, b2)], scale_col(acc, 0.5), 1)
            top = max(top, za, zb)
            if abs(za - zb) > 0.5:
                if abs(ux) > abs(uy):
                    ramp = (0, za, zb) if ax < bx else (0, zb, za)
                else:
                    ramp = (1, za, zb) if ay < by else (1, zb, za)
        m = b.done(top)
        md = bdeck.done(top)
        out[cell] = [m if m.groups else None, top, (top, ramp, deck), md if md.groups else None]
    return out


def _face3(poly):
    a, b, c = poly[0], poly[1], poly[2]
    if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
        poly = poly[::-1]
    return poly


def model_bound(m):
    """how far the model reaches from its own middle (worked out once)"""
    b = getattr(m, "bound", None)
    if b is None:
        b = 4.0
        for g in m.groups:
            ox, oy, oz = g[2], g[3], g[4]
            for p in g[7]:
                if p[1] == 0 or p[1] == 2:
                    for v in p[2]:
                        b = max(b, math.sqrt((v[0] + ox) ** 2 + (v[1] + oy) ** 2 + (v[2] + oz) ** 2))
                else:
                    c = p[0]
                    b = max(b, math.sqrt((c[0] + ox) ** 2 + (c[1] + oy) ** 2 + (c[2] + oz) ** 2) + (p[2] if p[1] == 1 else 0))
        m.bound = b
    return b


def hp_text(v):
    v = max(0, v)
    if v < 1000:
        return "%d" % math.ceil(v)
    if v < 10000:
        return "%.1fk" % (v / 1000.0)
    return "%dk" % (v / 1000.0)


_icon_cache = {}


def draw_icon(s, cam, r3, model, col, cx, cy, scale, t=0.0, spin=0.35, ang=None, pitch=0.55):
    """a little turning 3D model for the menus.  Small ones are kept as pictures (one per step of the turn)"""
    yaw = 2.4 + t * spin
    pal = palette(col, model.fixed)
    if scale <= 1.7 and model_pose(model) is not False:
        if spin:
            yb = int((yaw % TAU) * (90 / TAU))
            yaw = (yb + 0.5) * (TAU / 90)
            tq = (yaw - 2.4) / spin
        else:
            yb = int(t * 12) % 36
            tq = yb / 12.0
        key = (id(model), id(pal), round(scale, 2), yb, bool(spin), None if ang is None else round(ang, 2), round(pitch, 2))
        hit = _icon_cache.get(key)
        if hit is None:
            if len(_icon_cache) > 1400:
                _icon_cache.clear()
            hit = r3.pose_picture(model, pal, scale, yaw, pitch, yaw + math.pi + 0.5 if ang is None else ang, tq, True, 0.0, 0.0)
            _icon_cache[key] = hit if hit is not None else False
        if hit:
            s.blit(hit[0], (cx - hit[1], cy - hit[2]))
            return
    cam.icon(cx, cy, scale, yaw, pitch)
    r3.begin(s, cam)
    r3.model(model, pal, 0, 0, 0, yaw + math.pi + 0.5 if ang is None else ang, t)


class Scene:
    def __init__(self):
        self.r = R3D()
        self.icam = Cam()
        self.sky = {}
        self.bg2d = None
        self.bg2d_key = None
        self.prop_cache = {}
        self.prop_rev = -1
        self.me = None
        self.labels = []        # names, health bars and tags: drawn last so nothing covers them
        self.opt = {}

    def icon(self, s, model, col, cx, cy, scale, t=0.0, spin=0.35, ang=None):
        draw_icon(s, self.icam, self.r, model, col, cx, cy, scale, t, spin, ang)

    # ------------------------------------------------------------ picking
    def ground_pick(self, w, cam, mx, my):
        """where the mouse points on the land: the highest plateau the ray lands on, else the floor"""
        for L in w.levels:
            p = cam.pick(mx, my, L)
            if p is not None and w.height(p[0], p[1]) == L:
                return p
        g = cam.pick(mx, my, 0.0)
        if g is None:
            return None
        h = w.height(g[0], g[1])
        if h > 0:
            # the ray went in through a wall: use the top of that square
            p = cam.pick(mx, my, h)
            if p is not None:
                c, r = int(g[0] // CELL), int(g[1] // CELL)
                return (clamp(p[0], c * CELL + 1, c * CELL + CELL - 1), clamp(p[1], r * CELL + 1, r * CELL + CELL - 1))
        return g

    def pick_tower(self, w, cam, mx, my):
        best, bd = None, 1e9
        for t in w.towers + w.plans:
            a = cam.pt(t.x, t.y, t.z)
            if a is None:
                continue
            top = tower_model(t.kind, t.lv).top * 0.8
            b = cam.pt(t.x, t.y, t.z + top)
            if b is None:
                continue
            k = a[2]
            hw = k * (t.box + 4)
            y0, y1 = min(a[1], b[1]) - 4, max(a[1], b[1]) + hw * 0.55
            if y0 <= my <= y1:
                f = clamp((my - a[1]) / ((b[1] - a[1]) or 1), 0.0, 1.0)
                x = a[0] + (b[0] - a[0]) * f
                if abs(mx - x) <= hw:
                    d = cam.depth(t.x, t.y, t.z)
                    if d < bd:
                        best, bd = t, d
        return best

    def pick_enemy(self, w, cam, mx, my):
        best, bd = None, 1e9
        for e in w.enemies:
            if e.dead or e.hidden:
                continue
            q = cam.pt(e.x, e.y, e.r * 0.8)
            if q is None:
                continue
            rr = max(10.0, (e.r + 4) * q[2])
            d = (q[0] - mx) ** 2 + (q[1] - my) ** 2
            if d <= rr * rr and d < bd:
                best, bd = e, d
        return best

    def pick_thing(self, things, cam, mx, my, top=22.0, pad=10.0):
        for o in things:
            a = cam.pt(o["x"], o["y"], o["z"])
            b = cam.pt(o["x"], o["y"], o["z"] + top)
            if a is None or b is None:
                continue
            hw = a[2] * (o["rad"] + pad)
            if abs(mx - (a[0] + b[0]) / 2) <= hw and min(a[1], b[1]) - 6 <= my <= max(a[1], b[1]) + hw * 0.5:
                return o
        return None

    # ------------------------------------------------------------ the sky and the floor
    def sky_surf(self, th):
        key = th["sky"]
        sf = self.sky.get(key)
        if sf is None:
            sf = pygame.Surface((8, 360))
            top, bot = key
            for y in range(360):
                pygame.draw.line(sf, mix_col(top, bot, (y / 359.0) ** 1.6), (0, y), (8, y))
            sf = self.sky[key] = pygame.transform.scale(sf, (W, 360))
        return sf

    def backdrop(self, s, w, cam, t):
        th = w.theme
        if cam.ortho:
            s.fill(th["apron"])
            return
        tp = math.tan(clamp(cam.pitch, -1.4, 1.4))
        hy = int(clamp(cam.cy - cam.F * tp, -2000, 4000))
        s.fill(th["apron"])
        if hy > 0:
            s.fill(th["sky"][0], (0, 0, W, max(0, hy - 360)))
            s.blit(self.sky_surf(th), (0, hy - 360))
            hz = th["horizon"]
            acc = th["accent"]
            # everything in the sky sits at a fixed compass direction (north), so it slides when you turn
            da = (-math.pi / 2 - cam.yaw + math.pi) % TAU - math.pi
            if abs(da) < 1.3:
                sx = int(cam.cx + math.tan(da) * cam.F)
                if hz == "sun":
                    rr = 120
                    for i in range(6):
                        pygame.draw.circle(s, mix_col(mix_col(acc, PINK, 0.5), GOLD, i / 5.0), (sx, hy - 30), rr - i * 16)
                    for i in range(5):
                        yy = hy - 30 + 20 + i * 20
                        pygame.draw.rect(s, mix_col(th["sky"][0], th["sky"][1], 0.9), (sx - rr, yy, rr * 2, 3 + i * 2))
                    glow(s, sx, hy - 40, 240, mix_col(acc, GOLD, 0.5), 0.5)
                elif hz == "moon":
                    pygame.draw.circle(s, (240, 230, 200), (sx, hy - 150), 46)
                    pygame.draw.circle(s, mix_col(th["sky"][0], th["sky"][1], 0.35), (sx + 16, hy - 160), 40)
                    glow(s, sx, hy - 150, 160, (240, 230, 200), 0.4)
                elif hz == "planet":
                    pygame.draw.circle(s, scale_col(acc, 0.5), (sx, hy - 120), 70)
                    pygame.draw.circle(s, scale_col(acc, 0.3), (sx - 14, hy - 132), 58)
                    pygame.draw.ellipse(s, mix_col(acc, WHITE, 0.4), (sx - 120, hy - 136, 240, 34), 2)
                elif hz == "glow":
                    glow(s, sx, hy, 260, acc, 0.9)
                    glow(s, sx - 300, hy, 200, acc, 0.6)
                elif hz == "aurora":
                    for j in range(3):
                        pts = [(sx - 500 + i * 50, hy - 130 - j * 34 + math.sin(i * 0.7 + t * 0.6 + j) * 18) for i in range(21)]
                        pygame.draw.lines(s, mix_col((80, 255, 170), acc, j / 2.0), False, pts, 3 - j)
                elif hz == "city":
                    rnd = random.Random(5)
                    for i in range(40):
                        bw = rnd.randrange(18, 44)
                        bh = rnd.randrange(30, 150)
                        x = sx - 700 + i * 36
                        pygame.draw.rect(s, (10, 8, 22), (x, hy - bh, bw, bh))
                        if i % 3 == 0:
                            pygame.draw.line(s, acc, (x + 4, hy - bh + 6), (x + bw - 4, hy - bh + 6), 2)
            if hz in ("planet", "moon", "aurora", None) or th["amb"] == "stars":
                rnd = random.Random(9)
                off = int(cam.yaw * 400)
                for i in range(60):
                    x = (rnd.randrange(0, 2600) - off) % 2600 - 600
                    y = rnd.randrange(0, 400)
                    if 0 <= x < W and y < hy - 6:
                        s.fill(WHITE if i % 5 else acc, (x, y, 2, 2))
        pygame.draw.rect(s, th["apron"], (0, max(0, hy), W, H))
        if hy > 0:
            pygame.draw.line(s, scale_col(th["accent"], 0.5), (0, hy), (W, hy), 2)

    def ground(self, s, w, cam, t, detail):
        r = self.r
        th = w.theme
        acc = th["accent"]
        g2 = scale_col(th["grid"], 0.55)
        if not cam.ortho:
            for x in range(-480, FW + 481, 120):
                r.line((x, -360, 0), (x, FH + 360, 0), g2)
            for y in range(-360, FH + 361, 120):
                r.line((-480, y, 0), (FW + 480, y, 0), g2)
        r.poly([(0, 0, 0), (FW, 0, 0), (FW, FH, 0), (0, FH, 0)], th["ground"], scale_col(acc, 0.5))
        gc = th["grid"]
        for c in range(1, COLS):
            r.line((c * CELL, 0, 0), (c * CELL, FH, 0), gc)
        for c in range(1, ROWS):
            r.line((0, c * CELL, 0), (FW, c * CELL, 0), gc)
        d = th["decal"]
        if d and detail > 0:
            c1 = mix_col(th["ground"], th["grid"], 0.9)
            c2 = scale_col(acc, 0.45)
            for x, y, a, ln, v in w.decals:
                ca, sa = math.cos(a) * ln, math.sin(a) * ln
                if d == "circuit":
                    r.lines([(x, y, 0), (x + ca, y + sa, 0), (x + ca - sa * 0.5, y + sa + ca * 0.5, 0)], c2 if v > 0.6 else c1, 2)
                elif d == "cracks":
                    r.lines([(x, y, 0), (x + ca * 0.5 - sa * 0.3, y + sa * 0.5 + ca * 0.3, 0), (x + ca, y + sa, 0)], c2 if v > 0.5 else c1, 2)
                elif d == "rings":
                    r.ring(x, y, 0, ln, c1, 1, 10)
                elif d == "tiles" or d == "checker":
                    q = ln * 0.5
                    r.poly([(x - q, y - q, 0), (x + q, y - q, 0), (x + q, y + q, 0), (x - q, y + q, 0)], mix_col(th["ground"], (0, 0, 0), 0.25) if d == "checker" else None, c1)
                elif d == "glitch":
                    r.poly([(x, y, 0), (x + ln * 1.6, y, 0), (x + ln * 1.6, y + 5, 0), (x, y + 5, 0)], c2 if v > 0.7 else c1)
                elif d == "waves":
                    r.lines([(x - ln, y, 0), (x - ln * 0.5, y + 5, 0), (x, y, 0), (x + ln * 0.5, y + 5, 0), (x + ln, y, 0)], c1, 1)
                elif d == "dunes":
                    r.lines([(x - ln, y + 6, 0), (x, y, 0), (x + ln, y + 6, 0)], c1, 2)
                elif d == "chart":
                    r.lines([(x - ln, y, 0), (x - ln * 0.4, y - 10, 0), (x, y - 4, 0), (x + ln, y - 18, 0)], c2 if v > 0.5 else c1, 2)
                elif d == "facets":
                    r.lines([(x, y - ln * 0.5, 0), (x + ln * 0.5, y, 0), (x, y + ln * 0.5, 0), (x - ln * 0.5, y, 0)], c1, 1, True)
                else:
                    r.dot(x, y, 0, 1.5, c1)
        wc = th["water"]
        for (c, rr) in w.water:
            x, y = c * CELL, rr * CELL
            r.poly([(x, y, 0), (x + CELL, y, 0), (x + CELL, y + CELL, 0), (x, y + CELL, 0)], wc)
        self.road(w, cam, th)

    def road(self, w, cam, th):
        """the parts of the road that lie on the floor (raised parts belong to their squares)"""
        r = self.r
        acc = th["accent"]
        for wd, col in ((ROAD_W + 3.0, scale_col(acc, 0.75)), (ROAD_W, th["road"])):
            for a, b, n, cnt in w.road_ground:
                nx, ny = n[0] * wd, n[1] * wd
                r.poly([(a[0] + nx, a[1] + ny, 0.3), (b[0] + nx, b[1] + ny, 0.3), (b[0] - nx, b[1] - ny, 0.3), (a[0] - nx, a[1] - ny, 0.3)], col)
            for x, y, z, kind, cell in w.road_joints:
                if kind == 0:
                    r.poly([(x + math.cos(k * TAU / 10) * wd, y + math.sin(k * TAU / 10) * wd, 0.3) for k in range(10)], col)
        if w.corez < 0.5:
            cx, cy = w.core
            r.poly([(cx + math.cos(k * TAU / 12) * 34, cy + math.sin(k * TAU / 12) * 34, 0.4) for k in range(12)], th["road"], scale_col(acc, 0.75))

    def flow(self, w, cam, t, detail):
        """little arrows running down the road, and waves on the water"""
        r = self.r
        th = w.theme
        col = scale_col(th["accent"], 0.42)
        gap = 70 if detail > 1 else 140
        self.arrows = []        # arrows on raised road are drawn after the land they lie on
        for p in w.paths:
            d = (t * 46) % gap
            while d < p.length - 30:
                x, y, seg = p.at(d)
                a = p.angs[seg]
                ca, sa = math.cos(a), math.sin(a)
                z = 0.0 if p.flat else p.zat(d)
                pts = [(x - ca * 5 - sa * 7, y - sa * 5 + ca * 7, z + 0.6), (x + ca * 4, y + sa * 4, z + 0.6), (x - ca * 5 + sa * 7, y - sa * 5 - ca * 7, z + 0.6)]
                if z < 0.5:
                    r.lines(pts, col, 2)
                else:
                    self.arrows.append((x, y, z, pts, col))
                d += gap
        if w.water:
            wc = mix_col(th["water"], WHITE, 0.35)
            for (c, rr) in w.water:
                if (c + rr) % 2 == 0:
                    x, y = c * CELL, rr * CELL + 20 + math.sin(t * 1.5 + c) * 6
                    r.lines([(x + 4, y, 0.2), (x + 14, y + 3, 0.2), (x + 26, y, 0.2), (x + 36, y + 3, 0.2)], wc, 1)

    # ------------------------------------------------------------ everything
    def draw(self, s, w, cam, o):
        """draws a match.  While it does, the models are the ones for this map's theme (detailed unless detail is LOW)"""
        was = (MK2["on"], MK2["theme"])
        MK2["on"], MK2["theme"] = o.get("detail", 2) >= 1, w.map.get("theme")
        self.r.cache_on = False
        try:
            self.draw_all(s, w, cam, o)
        finally:
            MK2["on"], MK2["theme"] = was
            self.r.cache_on = False

    def draw_all(self, s, w, cam, o):
        """o = options: t, detail, me, hover, sel, ghost, aim, ranges, boxes, names, players, core_col, core_skin, seen, shake"""
        r = self.r
        self.me = o.get("me")
        t = o.get("t", w.time)
        detail = o.get("detail", 2)
        th = w.theme
        acc = th["accent"]
        shx = shy = 0
        if o.get("shake") and w.shake > 0:
            shx = int(random.uniform(-1, 1) * w.shake * 9)
            shy = int(random.uniform(-1, 1) * w.shake * 9)
        r.begin(s, cam)
        r.edges = detail > 0
        flat = cam.ortho
        # ---- the floor (in the flat view the floor never changes, so it is drawn once and kept)
        if flat:
            key = (w.uid, cam.scale, int(cam.cx), int(cam.cy), int(cam.x), int(cam.y), detail, len(w.cliffs), getattr(w, "rev", 0))
            if self.bg2d_key != key or self.bg2d is None:
                self.bg2d = pygame.Surface((W, H))
                r.begin(self.bg2d, cam)
                self.backdrop(self.bg2d, w, cam, t)
                self.ground(self.bg2d, w, cam, t, detail)
                for item in sorted(self.statics_flat(w), key=_first, reverse=True):
                    self.draw_static(item, 0.0)
                self.bg2d_key = key
                r.begin(s, cam)
            s.blit(self.bg2d, (shx, shy))
            cam.cx += shx
            cam.cy += shy
        else:
            cam.cx += shx
            cam.cy += shy
            self.backdrop(s, w, cam, t)
            self.ground(s, w, cam, t, detail)
        r.hold(cam, w.uid)
        self.flow(w, cam, t, detail)
        # ---- flat things on the floor (the ones on raised land wait until the land has been drawn)
        raised = w.maxh + w.maxroad > 0
        late = []
        for f in w.fields:
            z = w.top(f[0], f[1]) if raised else 0.0
            if z > 1.0 and not flat:
                late.append((0, f, z))
            else:
                self.flat_fx(0, f, z, t)
        for g in w.rings:
            if g[2] > 4.0 and raised and not flat:
                late.append((1, g, 0.0))
            else:
                self.flat_fx(1, g, 0.0, t)
        for c in w.casts:
            z = w.top(c["x"], c["y"]) if raised else 0.0
            if z > 1.0 and not flat:
                late.append((2, c, z))
            else:
                self.flat_fx(2, c, z, t)
        # ---- everything that stands up, far to near
        self.labels = []
        self.opt = o
        items = []
        f0, f1, f2 = cam.f
        cx, cy, cz = cam.x, cam.y, cam.z
        things = []             # (x, y, z, how wide, kind, object, stands on a road?)
        for tw in w.towers:
            things.append((tw.x, tw.y, tw.z, tw.box, 1, tw, tw.path))
        for tw in w.plans:
            things.append((tw.x, tw.y, tw.z, tw.box, 8, tw, tw.path))
        for e in w.enemies:
            if not e.dead:
                things.append((e.x, e.y, e.z, e.r if e.boss else 0.0, 2, e, True))
        for c in w.corpses:
            things.append((c[2], c[3], c[4], 0.0, 12, c, True))
        for g in w.goons:
            if not g.dead:
                things.append((g.x, g.y, g.z, 0.0, 13, g, True))
        for n in w.npcs:
            things.append((n["x"], n["y"], n["z"], 8.0, 3, n, False))
        if o.get("players") and not flat:
            for P in w.players:
                if P.here:
                    things.append((P.x, P.y, P.z, 8.0, 4, P, True))
        for c in w.casts:
            things.append((c["x"], c["y"], w.top(c["x"], c["y"]) if raised else 0.0, 0.0, 5, c, True))
        things.append((w.core[0], w.core[1], w.corez, 24.0, 6, None, True))
        for p in w.paths:
            gx, gy = clamp(p.pts[0][0], 6, FW - 6), clamp(p.pts[0][1], 6, FH - 6)
            things.append((gx, gy, p.zs[0], 14.0, 7, (gx, gy, p.angs[0], p.zs[0]), True))
        for k, ob, z in late:
            things.append((ob[0] if k < 2 else ob["x"], ob[1] if k < 2 else ob["y"], z if k != 1 else ob[2], 0.0, 9, (k, ob, z), True))
        if not flat:
            for a in self.arrows:
                things.append((a[0], a[1], a[2], 0.0, 10, a, True))
        if flat:
            # straight down: low things first, tall things on top
            for a in self.arrows:
                r.lines(a[3], a[4], 2)
            for x, y, z, rad, kind, ob, road in things:
                items.append((z, kind, len(items), kind, ob))
            items.sort()
        else:
            cliffs, props = self.statics(w, cam)
            for it in props:
                things.append((it[2], it[3], it[4], min(18.0, it[11] * 0.5), 0, it, False))
            # raised squares go far to near.  Everything else is slotted in just before the first square that stands
            # between it and the camera, so walls hide what is behind them and never what is in front
            cliffs.sort(key=_first, reverse=True)
            nc = len(cliffs)
            ci = {}
            for i, (d2, it) in enumerate(cliffs):
                ci[it[10]] = (i, it[12])
                if it[0] is not None:
                    items.append((i, 1, 0.0, i, 0, it))
                if it[13] is not None:
                    items.append((i, 3, 0.0, i, 11, it))        # the deck of a bridge: after whatever is under it
            maxh = max(w.maxh, w.maxroad)
            sq = len(items)
            for x, y, z, rad, kind, ob, road in things:
                dx, dy = cx - x, cy - y
                d2 = dx * dx + dy * dy
                slot = nc
                if ci and d2 > 1.0 and z < maxh - 1.0:
                    D = math.sqrt(d2)
                    ux, uy = dx / D, dy / D
                    rise = (cz - z) / D             # how fast the line to the camera climbs
                    reach = D if rise <= 0.001 else min(D, (maxh - z) / rise + 12.0)
                    start = 3.0
                    if road:
                        # it stands ON its square (a road, a ramp, a bridge): only the deck of a bridge above it can hide it
                        own = ci.get((int(x // CELL), int(y // CELL)))
                        if own is not None and own[1][2] is not None and z < own[1][2] - 10.0:
                            sq += 1
                            items.append((own[0], 2, -d2, sq, kind, ob))        # under a bridge: after the land, before the deck
                            continue
                        start = 30.0
                    sx, sy = -uy * rad * 0.85, ux * rad * 0.85
                    for ox, oy in (((0.0, 0.0), (sx, sy), (-sx, -sy)) if rad > 4 else ((0.0, 0.0),)):
                        s_ = start
                        while s_ <= reach:
                            px, py = x + ox + ux * s_, y + oy + uy * s_
                            ent = ci.get((int(px // CELL), int(py // CELL)))
                            if ent is not None and ent[0] < slot:
                                hide = ent[1]
                                hh = hide[0]
                                if hide[1] is not None:
                                    # a ramp: as high as the road is at this very spot
                                    ax_, z0, z1 = hide[1]
                                    f = ((px if ax_ == 0 else py) % CELL) / CELL
                                    hh = z0 + (z1 - z0) * f
                                if hh > z + 2.0 and z + rise * s_ < hh:
                                    slot = ent[0]
                            s_ += 9.0
                sq += 1
                items.append((slot, 0, -d2, sq, kind, ob))
            items.sort()
        hover, sel = o.get("hover"), o.get("sel")
        for item in items:
            kind, ob = item[-2], item[-1]
            if kind == 0:
                self.draw_static(ob, t)
            elif kind == 1:
                self.draw_tower(w, ob, t, ob is hover or ob is sel, detail)
            elif kind == 8:
                self.draw_plan(w, ob, t, ob is hover or ob is sel)
            elif kind == 9:
                self.flat_fx(ob[0], ob[1], ob[2], t)
            elif kind == 10:
                r.lines(ob[3], ob[4], 2)
            elif kind == 11:
                r.model(ob[13], ob[14], ob[2], ob[3], 0.0, 0.0, t, 1.0, 0.0, True)
            elif kind == 2:
                self.draw_enemy(w, ob, t, detail)
            elif kind == 3:
                self.draw_npc(ob, t, o)
            elif kind == 4:
                self.draw_player(w, ob, t, o)
            elif kind == 5:
                zb = w.top(ob["x"], ob["y"]) if raised else 0.0
                cam.z -= zb             # same as lifting the whole effect up onto the land it hit
                self.cast_tall(ob, t)
                cam.z += zb
            elif kind == 7:
                gm = gate_model()
                r.model(gm, palette(mix_col(acc, PINK, 0.5), gm.fixed), ob[0], ob[1], ob[3], ob[2], t)
            elif kind == 13:
                self.draw_goon(w, ob, t, detail)
            elif kind == 12:
                self.draw_corpse(w, ob, t, detail)
            else:
                m = core_model(o.get("core_skin", 0))
                col = o.get("core_col", CYAN)
                hf = w.hp / float(max(1, w.maxhp))
                if w.core_hit > 0:
                    pal = palette(col, m.fixed, True)
                else:
                    pal = palette(mix_col(RED, col, clamp(hf * 1.6, 0, 1)), m.fixed)
                if w.corez > 0.5:
                    r.poly([(w.core[0] + math.cos(k * TAU / 12) * 34, w.core[1] + math.sin(k * TAU / 12) * 34, w.corez + 0.5) for k in range(12)], th["road"], scale_col(acc, 0.75))
                r.model(m, pal, w.core[0], w.core[1], w.corez, 0, t)
                if w.aegis > 0:
                    r.ring(w.core[0], w.core[1], w.corez + 20, 30 + math.sin(t * 4) * 2, BLUE, 2, 16)
        # ---- shots, beams, sparks, numbers
        self.draw_shots(w, t)
        for b in w.bolts:
            k = b[1] / b[2]
            col = mix_col(b[3], WHITE, 0.5 * k)
            r.lines(b[0], scale_col(col, 0.4 + 0.6 * k), b[4] + 1)
            if b[4] >= 3:
                r.lines(b[0], WHITE, 1)
        fill = s.fill
        pt = cam.pt
        for p in w.parts:
            q = pt(p[0], p[1], p[2])
            if q is not None:
                k = p[6] / p[7]
                sz = max(2, int(p[9] * q[2] * (0.5 + k * 0.5)))
                fill(scale_col(p[8], 0.3 + 0.7 * k), (q[0] - sz * 0.5, q[1] - sz * 0.5, sz, sz))
        self.ambient(w, cam, t)
        # ---- circles and boxes
        self.overlays(w, cam, o, t)
        # ---- names, health bars and tags, on top of the 3D world
        rect = pygame.draw.rect
        for lb in self.labels:
            k = lb[0]
            if k == 0:
                draw_text(s, lb[1], lb[2], lb[3], lb[4], lb[5])
            elif k == 1:
                x, y, bw, bh, f, col = lb[1:]
                rect(s, (30, 10, 18), (x - bw / 2 - 1, y - 1, bw + 2, bh + 2))
                if f > 0:
                    rect(s, col, (x - bw / 2, y, max(1, int(bw * f)), bh))
            elif k == 3:
                pygame.draw.circle(s, lb[4], (lb[1], lb[2]), lb[3] + 1, 1)
            elif k == 4:
                # a goon's health: green in a gold frame, so it never looks like an enemy's
                x, y, bw, bh, f = lb[1:]
                rect(s, GOLD, (x - bw / 2 - 2, y - 2, bw + 4, bh + 4))
                rect(s, (6, 30, 20), (x - bw / 2 - 1, y - 1, bw + 2, bh + 2))
                if f > 0:
                    rect(s, GREEN, (x - bw / 2, y, max(1, int(bw * f)), bh))
            else:
                rr, col = lb[1], lb[2]
                rect(s, (8, 9, 22), rr, border_radius=6)
                rect(s, col, rr, 1, border_radius=6)
        for tx in w.texts:
            q = pt(tx[0], tx[1], tx[2])
            if q is not None and 0 < q[0] < W and 0 < q[1] < H:
                k = tx[5] / tx[6]
                draw_text(s, tx[3], tx[7], tx[4] if k > 0.35 else scale_col(tx[4], 0.3 + k * 2), q[0], q[1])

    def static_list(self, w):
        """cliffs, scenery and landmarks of THIS match: [model, colours, x, y, z, angle, size, top, show, plant spot, cliff square, reach]"""
        key = w.uid
        st = self.prop_cache.get(key)
        if st is None:
            self.prop_cache.clear()
            th = w.theme
            st = []
            for (c, rr), (m, top, hide, md) in build_cells(w).items():
                # [.., square, reach, hide info, bridge deck model, its colours]
                st.append([m, palette(th["accent"], m.fixed) if m else None, (c + 0.5) * CELL, (rr + 0.5) * CELL, 0.0, 0.0, 1.0, top, True, None, (c, rr), 30.0 + top * 0.6, hide,
                           md, palette(th["accent"], md.fixed) if md else None])
            for name, v, x, y, z, ang, sc in w.props + w.decor:
                m = prop_model(name, v)
                st.append([m, palette(th["accent"], m.fixed, False, 0.5 if sc < 1 else 1.0), x, y, z, ang, 1.0, 0.0, False, (x, y) if sc < 1 else None, None, model_bound(m) + 2, None])
            for mk in w.marks:
                m = prop_model(mk["prop"], mk["v"])
                st.append([m, palette(th["accent"], m.fixed), mk["x"], mk["y"], mk["z"], 0.6, 1.0, 0.0, False, None, None, model_bound(m) + 2, None])
            self.prop_cache[key] = st
            self.prop_rev = -1
        if getattr(w, "rev", 0) != self.prop_rev:
            # small plants and rocks vanish when you build on top of them
            self.prop_rev = getattr(w, "rev", 0)
            for it in st:
                if it[9] is not None:
                    x, y = it[9]
                    it[8] = None if any((t.x - x) ** 2 + (t.y - y) ** 2 < 26 * 26 for t in w.towers + w.plans) else False
        return st

    def statics(self, w, cam):
        """what the 3D camera can see: (cliffs as (ground distance, item), scenery items)"""
        st = self.static_list(w)
        cliffs, props = [], []
        f0, f1, f2 = cam.f
        u0, u1, u2 = cam.u
        cx, cy, cz = cam.x, cam.y, cam.z
        F = cam.F
        r0, r1 = cam.r[0], cam.r[1]
        hw, hh = W * 0.5 + 60, H * 0.5 + 100
        for it in st:
            if it[8] is None:
                continue
            dx, dy = it[2] - cx, it[3] - cy
            rad = it[11]
            dz = it[4] + rad * 0.4 - cz
            d = dx * f0 + dy * f1 + dz * f2
            if d < -rad:
                continue
            if d > rad:
                # all of it is in front of the camera: skip it when even its edge is off the screen
                if (abs(dx * r0 + dy * r1) - rad) * F > (d + rad) * hw:
                    continue
                if (abs(dx * u0 + dy * u1 + dz * u2) - rad) * F > (d + rad) * hh:
                    continue
            if it[10] is not None:
                cliffs.append((dx * dx + dy * dy, it))
            else:
                props.append(it)
        return cliffs, props

    def flat_fx(self, kind, ob, z, t):
        r = self.r
        if kind == 0:
            f = ob
            k = min(1.0, f[4] / 0.6)
            r.ring(f[0], f[1], z + 0.6, f[2], scale_col(f[6], 0.5 + 0.3 * math.sin(t * 9) * k), 2, 20)
            r.ring(f[0], f[1], z + 0.6, f[2] * 0.6, scale_col(f[6], 0.3 * k), 1, 14)
        elif kind == 1:
            g = ob
            u = 1 - g[5] / g[6]
            r.ring(g[0], g[1], g[2], g[3] + (g[4] - g[3]) * ease_out(u), scale_col(g[7], 1 - u * 0.8), g[8], 22)
        else:
            self.cast_floor(ob, t, z)

    def statics_flat(self, w):
        out = []
        for it in self.static_list(w):
            if it[8] is not None and -40 <= it[2] <= FW + 40 and -40 <= it[3] <= FH + 40:
                out.append((-(it[4] + it[7]), 0, it))
        return out

    def draw_static(self, it, t):
        if isinstance(it, tuple):
            it = it[2]
        if it[0] is not None:
            self.r.model(it[0], it[1], it[2], it[3], it[4], it[5], t, it[6], 0.0, True, cache=id(it))
        if len(it) > 13 and it[13] is not None and self.r.cam.ortho:
            self.r.model(it[13], it[14], it[2], it[3], 0.0, 0.0, t, 1.0, 0.0, True, cache=(id(it), 1))

    def draw_tower(self, w, tw, t, lit, detail):
        r = self.r
        cam = r.cam
        q = cam.pt(tw.x, tw.y, tw.z)
        if q is None or not (-80 < q[0] < W + 80 and -140 < q[1] < H + 80):
            return
        m = tower_model(tw.kind, tw.lv, q[2] < FAR_K or cam.ortho)
        col = tw.owner.tcol(tw.kind) if tw.owner is not None else TOWERS[tw.kind]["col"]
        s = r.s
        if tw.path and tw.down:
            r.model(m, palette(col, m.fixed, False, 0.35, True), tw.x, tw.y, tw.z, tw.ang, tw.t, 1.0, 0, False)
            r.ring(tw.x, tw.y, tw.z + 0.6, 16, RED, 1, 10)
            return
        if tw.stun > 0:
            pal = palette(col, m.fixed, False, 0.45)
        elif tw.path and tw.hit > 0:
            pal = palette(col, m.fixed, True)
        else:
            pal = palette(col, m.fixed)
        k = q[2]
        r.model(m, pal, tw.x, tw.y, tw.z, tw.ang, tw.t, 1.0, tw.recoil, k > 0.45, cache=(tw.id, id(m), id(pal)))
        top = tw.z + m.top
        if tw.stun > 0:
            for i in range(3):
                a = t * 7 + i * 2.1
                r.dot(tw.x + math.cos(a) * 12, tw.y + math.sin(a) * 12, tw.z + 18 + math.sin(a * 1.7) * 6, 1.6, PURPLE)
        if tw.act > 0:
            self.tring(w, tw.x, tw.y, tw.rng * (0.96 + 0.04 * math.sin(t * 8)), RED, 2)
        if tw.od > 0:
            r.ring(tw.x, tw.y, tw.z + 1, tw.box + 6 + math.sin(t * 10) * 2, CYAN, 2, 12)
        if tw.swing > 0.05:
            if tw.kind == "cryo":
                r.ring(tw.x, tw.y, tw.z + 1, tw.rng * (1 - tw.swing * 0.7), scale_col(ICE, 0.3 + 0.5 * tw.swing), 2, 24)
            elif tw.kind == "summoner":
                r.ring(tw.x, tw.y, tw.z + 1, tw.box * (1.9 - tw.swing), scale_col(GOLD, 0.3 + 0.6 * tw.swing), 2, 16)
            elif tw.kind in ("sentinel", "guardian", "cat"):
                rr = (tw.mrng if tw.kind == "sentinel" else tw.rng) * 0.9
                a0 = tw.ang - 1.2 + (1 - tw.swing) * 2.4
                r.lines([(tw.x + math.cos(a0 + i * 0.25) * rr, tw.y + math.sin(a0 + i * 0.25) * rr, tw.z + 12) for i in range(4)], WHITE, 3)
        if tw.beam:
            zz = tw.z + m.top * 0.55
            if tw.kind == "prism":
                for tg, wd in ((tw.tg, 2 + int(tw.ramp * 3)), (tw.tg2, 2)):
                    if tg is not None and not tg.dead:
                        r.line((tw.x, tw.y, zz), (tg.x, tg.y, tg.z + tg.r), col, wd + 2)
                        r.line((tw.x, tw.y, zz), (tg.x, tg.y, tg.z + tg.r), WHITE, max(1, wd - 1))
                        r.glow(tg.x, tg.y, tg.z + tg.r, 14 + tw.ramp * 10, col, 0.7)
            elif tw.kind == "mechanic":
                for p in w.towers:
                    if p.path and not p.down and p.hp < p.maxhp and (p.x - tw.x) ** 2 + (p.y - tw.y) ** 2 <= tw.rng * tw.rng:
                        r.line((tw.x, tw.y, zz), (p.x, p.y, p.z + 14), MEDIC, 2)
        if tw.path:
            f = clamp(tw.hp / max(1.0, tw.maxhp), 0, 1)
            b = cam.pt(tw.x, tw.y, top + 4)
            if b is not None:
                bw = max(22, min(90, int(34 * k)))
                self.labels.append((1, b[0], b[1] - 2, bw, 5, f, GREEN if f > 0.5 else GOLD if f > 0.25 else RED))
        if lit:
            b = cam.pt(tw.x, tw.y, top + (14 if tw.path else 6))
            if b is not None:
                lab = "MAX" if tw.lv >= MAXLV else "LV %d" % (tw.lv + 1)
                if self.me is not None and tw.owner is not None and tw.owner is not self.me:
                    lab = tw.owner.name + "  " + lab
                self.tag(lab, b[0], b[1] - 4, GOLD if tw.lv >= MAXLV else WHITE)

    def tag(self, lab, x, y, col, size=18):
        rr = pygame.Rect(0, 0, font(size).size(lab)[0] + 12, size + 2)
        rr.center = (clamp(x, rr.w // 2 + 2, W - rr.w // 2 - 2), clamp(y, 64, H - 12))
        self.labels.append((2, rr, col))
        self.labels.append((0, lab, size, col, rr.centerx, rr.centery))

    def draw_plan(self, w, tw, t, lit):
        """a tower that is waiting for its cash: see-through, with its price"""
        r = self.r
        cam = r.cam
        q = cam.pt(tw.x, tw.y, tw.z)
        if q is None or not (-80 < q[0] < W + 80 and -140 < q[1] < H + 80):
            return
        m = tower_model(tw.kind, 0)
        col = tw.owner.tcol(tw.kind) if tw.owner is not None else TOWERS[tw.kind]["col"]
        r.model(m, palette(col, m.fixed, False, 1.0, True), tw.x, tw.y, tw.z, tw.ang, tw.t)
        self.box(tw.x, tw.y, tw.z, tw.box, scale_col(GOLD, 0.6 + 0.4 * abs(math.sin(t * 3 + tw.id))))
        b = cam.pt(tw.x, tw.y, tw.z + m.top + 6)
        if b is not None:
            mine = self.me is None or tw.owner is self.me
            lab = "PLANNED  %d" % w.cost(tw.owner, tw.kind) if mine else "%s  PLANNED" % tw.owner.name
            if lit or q[2] > 0.5:
                self.tag(lab, b[0], b[1] - 4, GOLD if mine else GREY, 15)

    def draw_enemy(self, w, e, t, detail):
        r = self.r
        cam = r.cam
        z = e.z
        if e.lift > 0:
            z += 16 * min(1.0, e.lift * 3)
        q = cam.pt(e.x, e.y, z)
        if q is None or not (-60 < q[0] < W + 60 and -100 < q[1] < H + 60):
            return
        k = q[2]
        s = r.s
        if k * e.r < 3.2:
            pygame.draw.circle(s, e.col, (q[0], q[1] - e.r * k * 0.5), max(2, e.r * k))
            if e.hp < e.max:
                f = clamp(e.hp / e.max, 0, 1)
                self.labels.append((1, q[0], q[1] - e.r * k * 2 - 5, 12, 3, f, GREEN if f > 0.5 else GOLD if f > 0.25 else RED))
            return
        m = enemy_model(e.model, w.skin, k < FAR_K or cam.ortho)
        if e.flash > 0:
            pal = palette(e.col, m.fixed, True)
        elif e.hidden:
            pal = palette(e.col, m.fixed, False, 0.5, True)
        elif e.freeze > 0 and e.lift <= 0:
            pal = palette(mix_col(e.col, ICE, 0.7), m.fixed)
        elif w.skin == "glitch" and int(t * 9 + e.id) % 7 == 0:
            pal = palette((255, 0, 255), m.fixed)
        else:
            pal = palette(e.col, m.fixed)
        bob = 0.0 if e.cur <= 0 else abs(math.sin(e.t * 9)) * 1.6
        if e.act > 0:
            # it is hitting something: the whole body lunges forward and back (and models with arms swing them)
            act = clamp(1.0 - e.act / ACT_TIME, 0.0, 1.0)
            lg = math.sin(math.pi * act ** 0.7) * (2.5 + e.r * 0.22)
            r.walker(m, pal, e.x + math.cos(e.ang) * lg, e.y + math.sin(e.ang) * lg, z + bob, e.ang, e.t, k > 0.5 and not e.hidden, e.d * WALK_K, act)
        else:
            r.walker(m, pal, e.x, e.y, z + bob, e.ang, e.t, k > 0.5 and not e.hidden, e.d * WALK_K)
        if e.hidden:
            return
        if e.shield > 0:
            pygame.draw.circle(s, BLUE, (q[0], q[1] - e.r * k * 0.7), (e.r + 5) * k, 2)
        if e.lift > 0:
            pygame.draw.circle(s, (170, 230, 255), (q[0], q[1] - e.r * k * 0.7), (e.r + 7) * k, 2)
        elif e.slow > 0 and e.freeze <= 0:
            r.ring(e.x, e.y, e.z + 0.6, e.r + 3, ICE, 1, 10)
        if e.dr > 0:
            r.ring(e.x, e.y, e.z + 0.6, e.r + 8, GREY, 3, 12)
        if e.burn_t > 0 and int(t * 12 + e.id) % 2:
            r.dot(e.x, e.y, z + m.top * 0.7, 2.4, ORANGE)
        if e.fear > 0:
            b = cam.pt(e.x, e.y, z + m.top + 8)
            if b is not None:
                draw_text(s, "!", 22, PUMP_Y, b[0], b[1])
        show = self.opt.get("ehp", True)
        lit = e is self.opt.get("ehover")
        if lit:
            r.ring(e.x, e.y, e.z + 0.7, e.r + 5, WHITE, 2, 16)
        if (e.hp < e.max or show or lit) and (not e.boss or show or lit):
            b = cam.pt(e.x, e.y, z + m.top + 4)
            if b is not None:
                bw = max(14, min(120, int(e.r * 2.2 * k)))
                f = clamp(e.hp / e.max, 0, 1)
                self.labels.append((1, b[0], b[1] - 2, bw, 4, f, GREEN if f > 0.5 else GOLD if f > 0.25 else RED))
                if (show and k * e.r >= 5.5) or lit:
                    self.labels.append((0, hp_text(e.hp), 15 if (lit or e.boss) else 13, WHITE, b[0], b[1] - 11))

    def draw_goon(self, w, g, t, detail):
        """a Summoner's goon: a little soldier in its owner's colour with a green-and-gold health bar"""
        r = self.r
        cam = r.cam
        q = cam.pt(g.x, g.y, g.z)
        if q is None or not (-60 < q[0] < W + 60 and -100 < q[1] < H + 60):
            return
        k = q[2]
        s = r.s
        f = clamp(g.hp / max(1.0, g.max), 0, 1)
        if cam.ortho:
            # the flat view: a small gold diamond
            rr = max(4.0, g.r * k * 0.85)
            x, y = q[0], q[1]
            pts = [(x, y - rr), (x + rr, y), (x, y + rr), (x - rr, y)]
            pygame.draw.polygon(s, WHITE if g.flash > 0 else GOLD, pts)
            pygame.draw.polygon(s, (60, 40, 8), pts, 1)
            self.labels.append((4, x, y - rr - 7, max(14, int(g.r * 2.4 * k)), 3, f))
            return
        if k * g.r < 3.2:
            pygame.draw.circle(s, GOLD, (q[0], q[1] - g.r * k * 0.5), max(2, g.r * k))
            self.labels.append((4, q[0], q[1] - g.r * k * 2 - 6, 12, 3, f))
            return
        m = goon_model(g.lv, k < FAR_K)
        col = g.owner.tcol("summoner") if g.owner is not None else TOWERS["summoner"]["col"]
        if g.flash > 0:
            r.walker(m, palette(col, m.fixed, True), g.x, g.y, g.z, g.ang, g.t, k > 0.5, -g.d * WALK_K, clamp(1.0 - g.flash / 0.1, 0.0, 1.0))
        else:
            r.walker(m, palette(col, m.fixed), g.x, g.y, g.z, g.ang, g.t, k > 0.5, -g.d * WALK_K)
        r.ring(g.x, g.y, g.z + 0.6, g.r + 1, GOLD, 1, 10)
        b = cam.pt(g.x, g.y, g.z + m.top + 4)
        if b is not None:
            self.labels.append((4, b[0], b[1] - 2, max(14, min(70, int(g.r * 2.6 * k))), 4, f))
            if self.opt.get("ehp", True) and k * g.r >= 5.5:
                self.labels.append((0, hp_text(g.hp), 13, GOLD, b[0], b[1] - 12))

    def draw_corpse(self, w, c, t, detail):
        """something that was just killed: it flashes, twists over, sinks and shrinks away (a boss shudders first)"""
        r = self.r
        cam = r.cam
        name, col, x, y, z, ang, rad, age, life, boss, walk = c
        q = cam.pt(x, y, z)
        if q is None or not (-60 < q[0] < W + 60 and -100 < q[1] < H + 60):
            return
        k = q[2]
        u = clamp(age / life, 0.0, 1.0)
        if k * rad < 3.2:
            pygame.draw.circle(r.s, scale_col(col, 1.0 - 0.7 * u), (q[0], q[1] - rad * k * 0.5), max(1, rad * k * (1.0 - 0.45 * u)))
            return
        m = goon_model(name[1], k < FAR_K) if isinstance(name, tuple) else enemy_model(name, w.skin, k < FAR_K)
        if age < 0.08:
            pal = palette(col, m.fixed, True)
        else:
            pal = palette(col, m.fixed, False, int((1.0 - 0.72 * u) * 10) / 10.0)
        if boss:
            wob = math.sin(age * 24.0) * (1.0 - u)
            a = ang + wob * 0.28 + u * u * 1.2
            x += math.cos(ang + math.pi / 2) * wob * 3.0
            y += math.sin(ang + math.pi / 2) * wob * 3.0
        else:
            a = ang + u * 1.1
        r.model(m, pal, x, y, z - u * u * rad * 0.6, a, age * 2.0, 1.0 - 0.45 * u, 0, k > 0.5, walk)

    def draw_npc(self, n, t, o):
        r = self.r
        m = npc_model(n["hat"])
        me = o.get("orb")
        ang = 1.2
        if me is not None:
            ang = math.atan2(me[1] - n["y"], me[0] - n["x"])
        r.model(m, palette(n["col"], m.fixed), n["x"], n["y"], n["z"], ang, t + hash(n["id"]) % 7)
        q = r.cam.pt(n["x"], n["y"], n["z"] + 36)
        if q is not None and 0 < q[0] < W and 0 < q[1] < H:
            if o.get("names", True):
                self.labels.append((0, n["name"], 15, n["col"], q[0], q[1]))
            if n["id"] not in o.get("seen", ()):
                self.labels.append((0, "!", 26, GOLD, q[0], q[1] - 18 + math.sin(t * 4) * 3))

    def draw_player(self, w, P, t, o):
        r = self.r
        z = P.z + 15 + math.sin(t * 2.4 + P.id) * 2.5
        q = r.cam.pt(P.x, P.y, z)
        if q is None:
            return
        k = q[2]
        s = r.s
        g = r.cam.pt(P.x, P.y, P.z + 0.6)
        if g is not None:
            pygame.draw.ellipse(s, (0, 0, 0), (g[0] - 8 * k, g[1] - 3 * k, 16 * k, 6 * k))
        glow(s, q[0], q[1], 30 * k, P.col, 0.7)
        rr = max(3, 8.5 * k)
        pygame.draw.circle(s, scale_col(P.col, 0.75), (q[0], q[1]), rr)
        pygame.draw.circle(s, mix_col(P.col, WHITE, 0.55), (q[0] - rr * 0.25, q[1] - rr * 0.3), rr * 0.55)
        pygame.draw.circle(s, WHITE, (q[0], q[1]), rr, 1)
        r.ring(P.x, P.y, z, 13, P.col, 1, 12)
        if P is self.me:
            self.labels.append((3, q[0], q[1], rr, scale_col(P.col, 0.8)))
        if o.get("names", True) and -80 < q[0] < W + 80 and 0 < q[1] < H + 60:
            y = q[1] - min(rr, 60) - 14
            if P.title:
                self.labels.append((0, P.title, 13, GOLD, q[0], y))
                y -= 15
            self.labels.append((0, P.name, 18, WHITE, q[0], y))

    def draw_shots(self, w, t):
        r = self.r
        for sh in w.shots:
            k = sh.kind
            if k == "shell":
                u = clamp(sh.t / sh.T, 0, 1)
                x = sh.x0 + (sh.tx - sh.x0) * u
                y = sh.y0 + (sh.ty - sh.y0) * u
                zt = w.top(sh.tx, sh.ty) if w.maxh + w.maxroad > 0 else 0.0
                z = sh.z0 * (1 - u) + zt * u + math.sin(u * math.pi) * (90 + (40 if sh.big else 0))
                if sh.sub == "toaster":
                    r.dot(x, y, z, 4.5, TOAST)
                elif sh.sub == "pumpkin":
                    r.dot(x, y, z, 6, PUMP_O, 0.5)
                else:
                    r.dot(x, y, z, 7 if sh.big else 4, WHITE if sh.big else sh.col, 0.6)
                r.dot(x, y, zt + 0.5, 3, (0, 0, 0))
            elif k == "bubble":
                q = r.cam.pt(sh.x, sh.y, sh.z)
                if q is not None:
                    pygame.draw.circle(r.s, sh.col, (q[0], q[1]), max(2, 5 * q[2]), 1)
            elif k == "rocket":
                r.line((sh.x, sh.y, sh.z), (sh.x - sh.vx * 0.03, sh.y - sh.vy * 0.03, sh.z), WHITE, 3)
                r.line((sh.x - sh.vx * 0.03, sh.y - sh.vy * 0.03, sh.z), (sh.x - sh.vx * 0.07, sh.y - sh.vy * 0.07, sh.z), sh.col, 2)
            else:
                r.line((sh.x, sh.y, sh.z), (sh.x - sh.vx * 0.022, sh.y - sh.vy * 0.022, sh.z), sh.col, 3 if k == "bullet" else 2)

    def ambient(self, w, cam, t):
        kind = w.theme["amb"]
        if not kind or not w.amb:
            return
        fill = self.r.s.fill
        pt = cam.pt
        acc = w.theme["accent"]
        for a in w.amb:
            x, y, z, ph = a
            if kind == "snow":
                z = 160 - ((t * 26 + ph * 160) % 160)
                x += math.sin(t + ph * 9) * 8
                col = WHITE
            elif kind in ("embers", "bubbles", "spores"):
                z = (t * (22 if kind != "spores" else 8) + ph * 150) % 150
                x += math.sin(t * 1.4 + ph * 9) * 6
                col = ORANGE if kind == "embers" else (170, 230, 255) if kind == "bubbles" else acc
            elif kind == "glitch":
                if int(t * 5 + ph * 20) % 3:
                    continue
                x += (int(t * 3 + ph * 7) % 5) * 30
                col = acc
            elif kind == "dust":
                x += (t * 30 + ph * 300) % 300 - 150
                z = 6 + ph * 20
                col = mix_col(acc, WHITE, 0.3)
            elif kind == "clouds":
                continue
            else:
                z += math.sin(t * 0.8 + ph * 9) * 6
                col = acc if ph > 0.5 else WHITE
            q = pt(x, y, z)
            if q is not None and 0 <= q[0] < W and 0 <= q[1] < H:
                sz = 3 if q[2] > 1.0 else 2
                fill(col, (q[0], q[1], sz, sz))

    def cast_floor(self, c, t, z0=0.0):
        r = self.r
        k, ct, x, y, rad = c["kind"], c["t"], c["x"], c["y"], c["rad"]
        col = ABILS[k]["col"]
        zf = z0 + 0.7
        if k == "sword":
            if ct < 0.45:
                r.ring(x, y, zf, rad, col, 2, 30)
                r.ring(x, y, zf, rad * (1 - ct / 0.45), WHITE, 1, 24)
        elif k == "napalm" or k == "cryobomb" or k == "repair" or k == "overdrive":
            if ct < 0.35:
                r.ring(x, y, zf, rad * (ct / 0.35), col, 3, 28)
        elif k == "blackhole":
            for i in range(3):
                rr = rad * ((1.0 - ((t * 0.9 + i / 3.0) % 1.0)))
                r.ring(x, y, zf, rr, scale_col(col, 0.5 + 0.5 * (rr / rad)), 2, 22)
        elif k == "laser":
            r.ring(x, y, zf, rad * (0.9 + 0.1 * math.sin(t * 20)), col, 3, 18)

    def cast_tall(self, c, t):
        r = self.r
        k, ct, x, y, rad = c["kind"], c["t"], c["x"], c["y"], c["rad"]
        col = ABILS[k]["col"]
        if k == "sword":
            m = blade_model()
            if ct < 0.45:
                z = (1 - (ct / 0.45) ** 2) * 520
                r.model(m, palette(col, m.fixed), x, y, z, 0.5, t)
            elif ct < 1.3:
                r.model(m, palette(col, m.fixed), x, y, -18, 0.5, t)
                r.glow(x, y, 20, 120, col, 0.6)
            else:
                u = clamp((ct - 1.3) / 0.7, 0, 1)
                r.model(m, palette(col, m.fixed, False, 1 - u * 0.8, True), x, y, -18 + u * 60, 0.5 + u * 3, t, 1 - u * 0.6, 0, False)
                for i in range(5):
                    a = i * 1.3 + t * 3
                    r.dot(x + math.cos(a) * 20 * u * 3, y + math.sin(a) * 20 * u * 3, 60 + i * 34 + u * 80, 2.5, col, 0.4)
        elif k == "cryobomb" or k == "napalm" or k == "repair":
            if ct < 0.32:
                z = (1 - ct / 0.32) * 380
                r.dot(x, y, z, 9, col, 0.8)
                r.line((x, y, z), (x, y, z + 60), col, 2)
        elif k == "blackhole":
            if ct > 0.2:
                z = 26 + math.sin(t * 3) * 3
                q = r.cam.pt(x, y, z)
                if q is not None:
                    rr = 15 * q[2]
                    glow(r.s, q[0], q[1], rr * 4, col, 0.8)
                    pygame.draw.circle(r.s, (2, 2, 6), (q[0], q[1]), rr)
                    pygame.draw.circle(r.s, col, (q[0], q[1]), rr, 2)
                r.ring(x, y, z, 26, col, 2, 16)
        elif k == "laser":
            if 0.3 < ct < 4.3:
                wd = 5 + int(math.sin(t * 30) * 2)
                r.line((x, y, 0), (x, y, 900), col, wd + 6)
                r.line((x, y, 0), (x, y, 900), WHITE, wd)
                r.glow(x, y, 4, 70, col, 0.9)
            elif ct <= 0.3:
                r.line((x, y, 0), (x, y, 900), col, 1)

    def tring(self, w, x, y, rad, col, width=2):
        """a circle on the ground that follows the land: it steps up onto cliffs instead of cutting through them"""
        r = self.r
        if r.cam.ortho or not w.cliffs:
            r.ring(x, y, 0.8, rad, col, width, 40)
            return
        n = int(clamp(rad / 3.5, 28, 96))
        run = []
        ph = None
        hm = w.hmap
        for i in range(n + 1):
            a = i * TAU / n
            px, py = x + math.cos(a) * rad, y + math.sin(a) * rad
            h = hm.get((int(px // CELL), int(py // CELL)), 0.0)
            if h != ph and run:
                r.lines(run, col, width)
                run = []
            run.append((px, py, h + 0.8))
            ph = h
        r.lines(run, col, width)

    def overlays(self, w, cam, o, t):
        r = self.r
        me = o.get("me")
        shown = []
        for tw in (o.get("sel"), o.get("hover")):
            if tw is not None and tw not in shown and (tw in w.towers or tw in w.plans):
                shown.append(tw)
        for tw in shown:
            col = tw.owner.tcol(tw.kind) if tw.owner is not None else WHITE
            if o.get("ranges", True) and tw.rng > 0:
                self.tring(w, tw.x, tw.y, tw.rng, col, 2)
                if tw.kind == "sentinel" and tw.mrng > 0:
                    self.tring(w, tw.x, tw.y, tw.mrng, mix_col(col, WHITE, 0.4), 1)
            if o.get("boxes", True):
                self.box(tw.x, tw.y, tw.z, tw.box, WHITE if tw.owner is me else GREY)
        g = o.get("ghost")
        if g:
            kind, x, y, ok, col, rng, z = g
            m = tower_model(kind, 0)
            ang = -math.pi / 2
            if is_path(kind):
                ang = w.road_info(x, y)[5] + math.pi
            r.model(m, palette(col if ok else RED, m.fixed, False, 0.9 if ok else 0.6, True), x, y, z, ang, t)
            if o.get("ranges", True) and rng > 0:
                self.tring(w, x, y, rng, col if ok else RED, 2)
            if o.get("boxes", True):
                self.box(x, y, z, TOWERS[kind].get("box", 15), GREEN if ok else RED)
                if not is_path(kind):
                    for tw in w.towers + w.plans:
                        if not tw.path and abs(tw.x - x) < 90 and abs(tw.y - y) < 90:
                            self.box(tw.x, tw.y, tw.z, tw.box, GREY)
        a = o.get("aim")
        if a:
            ab, x, y, rad = a
            col = ABILS[ab]["col"]
            self.tring(w, x, y, rad, col, 2)
            r.ring(x, y, 0.8, rad * (0.2 + 0.8 * ((t * 1.2) % 1.0)), scale_col(col, 0.6), 1, 24)
            r.line((x - 10, y, 0.8), (x + 10, y, 0.8), WHITE, 1)
            r.line((x, y - 10, 0.8), (x, y + 10, 0.8), WHITE, 1)

    def box(self, x, y, z, h, col):
        self.r.lines([(x - h, y - h, z + 0.9), (x + h, y - h, z + 0.9), (x + h, y + h, z + 0.9), (x - h, y + h, z + 0.9)], col, 1, True)


# ======================================================================
#  THE FIELD  -  the map itself: roads, cliffs, where you may build.
#  Both the real game (World) and a Wi-Fi guest's copy (GuestWorld) use it.
# ======================================================================
STEP = CLIFF_H          # one level of height.  Plateaus and roads sit on level 0, 1, 2 or 3.


class Path:
    """a road.  Corner points are (column, row), (column, row, level) or (column, row, level, "b").
    The level stays the same until a point changes it; between two points of different level the road is a ramp.
    "b" makes the stretch AFTER that point a viaduct: open underneath instead of a solid bank."""

    def __init__(self, cells):
        self.pts = [((c[0] + 0.5) * CELL, (c[1] + 0.5) * CELL) for c in cells]
        self.zs = []
        self.via = []
        lv = 0
        for c in cells:
            if len(c) > 2:
                lv = c[2]
            self.zs.append(lv * STEP)
            self.via.append(len(c) > 3 and "b" in str(c[3]))
        self.cum = [0.0]
        self.angs = []
        for i in range(len(self.pts) - 1):
            a, b = self.pts[i], self.pts[i + 1]
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
            self.angs.append(math.atan2(b[1] - a[1], b[0] - a[0]))
        self.length = self.cum[-1]
        self.flat = max(self.zs) == 0
        self.open = []          # (how far along, open underneath?) for every short piece, filled in by the map

    def zat(self, d):
        """how high the road is, this far along"""
        if self.flat:
            return 0.0
        cum, zs = self.cum, self.zs
        if d <= 0:
            return zs[0]
        for i in range(len(cum) - 1):
            if d <= cum[i + 1]:
                return zs[i] + (zs[i + 1] - zs[i]) * (d - cum[i]) / (cum[i + 1] - cum[i])
        return zs[-1]

    def open_at(self, d):
        for d1, op in self.open:
            if d <= d1:
                return op
        return False

    def at(self, d):
        cum = self.cum
        if d <= 0:
            return self.pts[0][0], self.pts[0][1], 0
        for i in range(len(cum) - 1):
            if d <= cum[i + 1]:
                a, b = self.pts[i], self.pts[i + 1]
                t = (d - cum[i]) / (cum[i + 1] - cum[i])
                return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, i
        return self.pts[-1][0], self.pts[-1][1], len(cum) - 2

    def nearest(self, x, y):
        """-> (distance, how far along the road, road x, road y, segment)"""
        best = (1e9, 0.0, 0.0, 0.0, 0)
        pts, cum = self.pts, self.cum
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = clamp(((x - ax) * dx + (y - ay) * dy) / L2, 0.0, 1.0) if L2 else 0.0
            px, py = ax + dx * t, ay + dy * t
            d = math.hypot(x - px, y - py)
            if d < best[0]:
                best = (d, cum[i] + math.sqrt(L2) * t, px, py, i)
        return best


class Player:
    """one person in a match: their cash, perks and loadout"""

    def __init__(self, pid, spec):
        self.id = pid
        self.name = clean_name(spec.get("name") or "PLAYER %d" % (pid + 1)) or "PLAYER %d" % (pid + 1)
        self.col = tuple(spec.get("col") or PLAYER_COLORS[pid % len(PLAYER_COLORS)][1])
        self.title = str(spec.get("title") or "")[:24]
        self.level = int(spec.get("level") or 1)
        self.loadout = [k for k in (spec.get("loadout") or ["blaster", "blade", "rail"]) if k in TOWERS][:6] or ["blaster"]
        self.perks = [k for k in (spec.get("perks") or []) if k in PERKS][:3]
        self.abils = [k for k in (spec.get("abils") or ["sword"]) if k in ABILS][:2] or ["sword"]
        self.tperks = dict((k, v) for k, v in (spec.get("tperks") or {}).items() if v in TPERKS and TPERKS[v]["tower"] == k)
        self.paint = dict((k, tuple(v)) for k, v in (spec.get("paint") or {}).items() if k in TOWERS and v)
        self.rip = set(k for k in (spec.get("rip") or []) if k in TOWERS)
        self.mods = dict(MODS0)
        for k in self.perks:
            for mk, mv in PERKS[k]["mods"].items():
                self.mods[mk] += mv
        self.cash = 0.0
        self.cfrac = 0.0
        self.acd = [0.0, 0.0]
        self.cards = []
        self.offer = None
        self.ready = False
        self.skip = False       # voted to skip the wave
        self.here = True
        self.x = self.y = 0.0
        self.z = 0.0            # how high the orb is (it climbs ramps and plateaus)
        self.kills = 0
        self.dealt = 0.0
        self.built = 0

    def tname(self, kind):
        return TOWERS[kind]["name"] + (" RIPOFF" if kind in self.rip else "")

    def tcol(self, kind):
        return self.paint.get(kind) or TOWERS[kind]["col"]

    def spec(self):
        return dict(name=self.name, col=list(self.col), title=self.title, level=self.level, loadout=self.loadout, perks=self.perks, abils=self.abils,
                    tperks=self.tperks, paint=dict((k, list(v)) for k, v in self.paint.items()), rip=sorted(self.rip))


class Tower:
    def __init__(self, tid, kind, x, y, owner):
        self.id = tid
        self.kind = kind
        self.x, self.y = x, y
        self.z = 0.0
        self.owner = owner
        self.cliff = False
        self.hk = 1.0           # high ground: level 1 gives the cliff range bonus once, level 2 one and a half times, level 3 twice
        self.mb = None          # this map's buff for this kind of tower (or None)
        self.path = is_path(kind)
        self.box = TOWERS[kind].get("box", 15)
        self.lv = 0
        self.L = TOWERS[kind]["lv"][0]
        self.cd = 0.25
        self.mcd = 0.25
        self.ang = -math.pi / 2
        self.tg = None
        self.tg2 = None
        self.mode = DEFAULT_MODE.get(kind, 0)
        self.stun = 0.0
        self.kills = 0
        self.dealt = 0.0
        self.spent = 0
        self.t = 0.0
        self.recoil = 0.0
        self.swing = 0.0
        self.rng = float(self.L.get("rng", 0))
        self.mrng = 0.0
        self.rb = 0.0
        self.db = 0.0           # damage bonus from a Beacon with SPOTTER
        self.cmds = []
        self.mechs = []
        self.ramp = 0.0
        self.beam = False
        self.acd = 0.0          # ability cooldown left
        self.act = 0.0          # ability time left
        self.pulse = 0.0
        self.frz_t = 4.0
        self.born = 0.0
        self.tp = owner.tperks.get(kind) if owner is not None else None
        self.shots = 0
        self.duel = 0.0
        self.od = 0.0           # Overdrive Field time left
        self.waves = 0          # waves it has been standing (Harvester interest)
        # path towers
        self.hp = self.maxhp = 0.0
        self.down = False
        self.down_t = 0.0
        self.pd = {}            # road number -> how far along that road it stands
        self.block = []
        self.hit = 0.0
        self.ghost = False      # a planned tower that is still waiting for its cash


class Enemy:
    __slots__ = ("id", "kind", "pi", "d", "rem", "x", "y", "ang", "hp", "max", "spd", "cur", "armor", "r", "col", "bounty", "leak", "boss",
                 "shield", "smax", "sreg", "slow", "slow_t", "freeze", "burn", "burn_t", "burn_p", "flash", "t", "a1", "a2", "stage",
                 "dead", "hidden", "dr", "haste", "hmul", "hm", "name", "ai", "model", "atk", "block", "fear", "lift", "chill", "vuln", "fcd", "z", "tick", "act")

    def __init__(self, eid, kind, pi, d, hm, bounty, t0=0.0):
        e = ENEMIES[kind]
        self.z = 0.0             # how high the road is where it walks
        self.tick = 0.0          # steady damage (beams, auras) saved up towards its next $1 of hit cash
        self.act = 0.0           # seconds left of the attack swing it is playing (only for looks)
        self.id = eid
        self.kind = kind
        self.ai = e.get("ai", kind)
        self.model = e.get("model", kind)
        self.name = e["name"]
        self.pi = pi
        self.d = d
        self.rem = 9999.0
        self.x = self.y = -100.0
        self.ang = 0.0
        self.hm = hm
        self.max = self.hp = e["hp"] * hm
        self.spd = self.cur = e["spd"]
        self.armor = e.get("armor", 0) * (1 + (hm - 1) * 0.12) if not e.get("boss") else e.get("armor", 0) * 1.0
        self.r = e["r"]
        self.col = e["col"]
        self.bounty = bounty
        self.leak = e["leak"]
        self.boss = e.get("boss", False)
        self.shield = self.smax = e.get("shield", 0) * hm
        self.sreg = 0.0
        self.slow = self.slow_t = self.freeze = self.burn = self.burn_t = self.flash = 0.0
        self.burn_p = None
        self.t = t0
        self.a1 = 4.0
        self.a2 = 8.0
        self.stage = 0
        self.dead = False
        self.hidden = False
        self.dr = 0.0
        self.haste = 0.0
        self.hmul = 1.0
        self.atk = (3 + e["hp"] * 0.05) * max(1.0, hm) ** 0.7
        self.block = None
        self.fear = 0.0
        self.lift = 0.0
        self.chill = 0.0
        self.vuln = 0.0
        self.fcd = 0.0


class Goon:
    """a Summoner's little soldier: it walks from the core up the road, towards the gate, and trades health with the enemies it meets"""
    __slots__ = ("id", "tw", "tid", "owner", "pi", "d", "x", "y", "z", "ang", "hp", "max", "spd", "lv", "r", "flash", "t", "dead")

    def __init__(self, gid, tw, owner, pi, d, hp, spd, lv=0):
        self.id = gid
        self.tw = tw             # the Summoner it belongs to (None on a Wi-Fi guest's copy)
        self.tid = tw.id if tw is not None else 0
        self.owner = owner
        self.pi = pi             # which road
        self.d = d               # how far along the road, measured from the gate like an enemy's: it starts at the END and goes DOWN
        self.x = self.y = -100.0
        self.z = 0.0
        self.ang = 0.0
        self.max = self.hp = float(hp)
        self.spd = spd
        self.lv = lv
        self.r = GOON_R
        self.flash = 0.0
        self.t = 0.0
        self.dead = False


class Shot:
    __slots__ = ("kind", "x", "y", "z", "vx", "vy", "tg", "dmg", "src", "life", "col", "pierce", "hit", "crit",
                 "x0", "y0", "z0", "tx", "ty", "T", "t", "splash", "burn", "stun", "big", "fear", "lift", "sub", "spd")

    def __init__(self, kind, x, y, dmg, src, col, z=12.0):
        self.kind = kind
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = 0.0
        self.tg = None
        self.dmg = dmg
        self.src = src
        self.life = 2.0
        self.col = col
        self.pierce = 0
        self.hit = None
        self.crit = False
        self.x0, self.y0, self.z0, self.tx, self.ty = x, y, z, x, y
        self.T = 1.0
        self.t = 0.0
        self.splash = 0.0
        self.burn = 0
        self.stun = 0.0
        self.big = False
        self.fear = 0.0
        self.lift = 0.0
        self.sub = ""
        self.spd = 640.0


ORB_R = 9.0             # how big a player's orb is when it bumps into things
_field_count = [0]


class Field:
    def __init__(self, mapkey, fx=True):
        m = MAP_BY_ID[mapkey] if isinstance(mapkey, str) else MAPS[mapkey]
        _field_count[0] += 1
        self.uid = _field_count[0]      # every match gets its own number (drawing caches go by it)
        self.map = m
        self.mapi = m["i"]
        self.mapid = m["id"]
        self.fx = fx
        self.net = False
        self.fxlog = []
        self.theme = THEMES[m["theme"]]
        self.skin = m.get("skin")
        self.paths = [Path(p) for p in m["paths"]]
        self.core = self.paths[0].pts[-1]
        self.corez = self.paths[0].zs[-1]
        self.water = set()
        for c0, r0, c1, r1 in m.get("water", ()):
            for c in range(c0, c1 + 1):
                for r in range(r0, r1 + 1):
                    self.water.add((c, r))
        self.maxroad = max(max(p.zs) for p in self.paths)
        self.make_land(m)
        self.make_roads()
        # things standing on the map
        self.marks = []
        for mk in m.get("marks", ()):
            self.marks.append(dict(id=mk["id"], prop=mk["prop"], x=(mk["at"][0] + 0.5) * CELL, y=(mk["at"][1] + 0.5) * CELL, rad=mk.get("rad", 14), v=mk.get("v", 0), secret=False))
        for sc in m.get("secrets", ()):
            self.marks.append(dict(id=sc["id"], prop=sc["prop"], x=(sc["at"][0] + 0.5) * CELL, y=(sc["at"][1] + 0.5) * CELL, rad=10, v=sc.get("v", 0), secret=True))
        self.npcs = []
        for n in m.get("npcs", ()):
            self.npcs.append(dict(id=n["id"], name=n["name"], x=(n["at"][0] + 0.5) * CELL, y=(n["at"][1] + 0.5) * CELL, hat=n.get("hat"), col=n["col"],
                                  lines=n["lines"], quest=n.get("quest"), rad=9))
        for o in self.marks + self.npcs:
            o["z"] = self.height(o["x"], o["y"])
        self.towers = []
        self.plans = []                 # towers placed ahead of time: they turn real when their owner can pay
        self.enemies = []
        self.goons = []                 # the Summoners' soldiers
        self.corpses = []               # killed enemies, shown falling for a moment (only for looks)
        self.shots = []
        self.fields = []
        self.casts = []
        self.parts = []
        self.rings = []
        self.bolts = []
        self.texts = []
        self.ev = []                    # sounds for the game to play
        self.players = []
        self.shake = 0.0
        self.banner = None
        self.time = 0.0
        self.core_hit = 0.0
        self.numbers = True
        self.frnd = random.Random()     # randomness that is only for looks
        self.make_scenery()

    # ------------------------------------------------------------ the land and the roads on it
    def make_land(self, m):
        """how high every square is.  Plateaus are stacked in levels; land right next to a road is never higher than
        the road, so nothing ever hides the enemies."""
        hm = {}
        for rc in m["cliffs"]:
            c0, r0, c1, r1 = rc[:4]
            lv = rc[4] if len(rc) > 4 else 1
            for c in range(max(0, c0), min(COLS - 1, c1) + 1):
                for r in range(max(0, r0), min(ROWS - 1, r1) + 1):
                    if (c, r) in self.water:
                        continue
                    if lv <= 0:
                        hm.pop((c, r), None)
                    else:
                        hm[(c, r)] = lv * STEP
        self.rsamp = {}         # square -> road points in it (x, y, z, road number, how far along)
        for pi, p in enumerate(self.paths):
            d = 0.0
            while d <= p.length + 0.01:
                x, y, seg = p.at(d)
                self.rsamp.setdefault((int(x // CELL), int(y // CELL)), []).append((x, y, p.zat(d), pi, d))
                d += 10.0
        for (c, r) in list(hm):
            x, y = (c + 0.5) * CELL, (r + 0.5) * CELL
            zmin = None
            for cc in range(c - 2, c + 3):
                for rr in range(r - 2, r + 3):
                    for s in self.rsamp.get((cc, rr), ()):
                        if (s[0] - x) ** 2 + (s[1] - y) ** 2 < 47 * 47 and (zmin is None or s[2] < zmin):
                            zmin = s[2]
            if math.hypot(x - self.core[0], y - self.core[1]) < 66:
                zmin = self.corez if zmin is None else min(zmin, self.corez)
            if zmin is not None:
                h = min(hm[(c, r)], STEP * math.floor(zmin / STEP + 0.01))
                if h <= 0:
                    del hm[(c, r)]
                else:
                    hm[(c, r)] = h
        self.hmap = hm
        self.cliffs = set(hm)           # every raised square
        self.maxh = max(hm.values()) if hm else 0.0
        self.levels = sorted(set(hm.values()), reverse=True)
        # "cliff" means HIGHER THAN THE ROAD NEXT TO IT.  A plateau that is level with its road counts as ground,
        # so ground towers can stand beside a raised road and cliff towers get the squares that look down on one.
        allr = [s for lst in self.rsamp.values() for s in lst if -40 < s[0] < FW + 40 and -40 < s[1] < FH + 40]
        self.rel = {}
        for (c, r), h in hm.items():
            x, y = (c + 0.5) * CELL, (r + 0.5) * CELL
            best, bz = 1e18, 0.0
            for s in allr:
                d = (s[0] - x) ** 2 + (s[1] - y) ** 2
                if d < best:
                    best, bz = d, s[2]
            self.rel[(c, r)] = h - bz

    def road_below(self, pi, d, x, y, z):
        """does a lower stretch of road pass underneath this point?"""
        c, r = int(x // CELL), int(y // CELL)
        for cc in range(c - 1, c + 2):
            for rr in range(r - 1, r + 2):
                for s in self.rsamp.get((cc, rr), ()):
                    if s[2] < z - 15 and (s[0] - x) ** 2 + (s[1] - y) ** 2 < 30 * 30 and not (s[3] == pi and abs(s[4] - d) < 80):
                        return True
        return False

    def make_roads(self):
        """cut every road into short pieces and note what each one is:
        0 on the floor, 1 lying on a plateau, 2 a ramp or bank (solid underneath), 3 a bridge (open underneath)"""
        self.road_ground = []       # (point a, point b, across) long strips for the floor
        self.road_cells = {}        # square -> pieces that are above the floor: (kind, a, b, across, road, segment)
        self.road_joints = []       # (x, y, z, kind, square) round corners
        self.crossings = []         # (x, y) where one road goes over another
        seen = set()
        for pi, p in enumerate(self.paths):
            p.open = []
            pts = p.pts
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                L = p.cum[i + 1] - p.cum[i]
                ux, uy = (bx - ax) / L, (by - ay) / L
                n = max(1, int(round(L / 20.0)))
                za, zb = p.zs[i], p.zs[i + 1]
                run = None
                for j in range(n):
                    f0, f1 = j / float(n), (j + 1) / float(n)
                    x0, y0, x1, y1 = ax + (bx - ax) * f0, ay + (by - ay) * f0, ax + (bx - ax) * f1, ay + (by - ay) * f1
                    z0, z1 = za + (zb - za) * f0, za + (zb - za) * f1
                    mx, my, zm = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
                    cell = (int(mx // CELL), int(my // CELL))
                    th = self.hmap.get(cell, 0.0)
                    if zm < 0.6 and th <= 0:
                        kind = 0
                    elif abs(z0 - th) < 0.6 and abs(z1 - th) < 0.6:
                        kind = 1
                    elif p.via[i] or cell in self.water or self.road_below(pi, p.cum[i] + L * (f0 + f1) / 2, mx, my, zm):
                        kind = 3
                        if self.road_below(pi, p.cum[i] + L * (f0 + f1) / 2, mx, my, zm):
                            self.crossings.append((mx, my))
                    else:
                        kind = 2
                    p.open.append((p.cum[i] + L * f1, kind == 3))
                    key = (int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)), int(round(zm)))
                    if key in seen:
                        run = None
                        continue
                    seen.add(key)
                    if kind == 0:
                        # floor pieces are joined up into long strips
                        if run is not None and len(run) < 3:
                            pass
                        if run is not None and run[3] < 11:
                            run[1] = (x1, y1)
                            run[3] += 1
                        else:
                            run = [(x0, y0), (x1, y1), (-uy, ux), 1]
                            self.road_ground.append(run)
                    else:
                        run = None
                        self.road_cells.setdefault(cell, []).append((kind, (x0, y0, z0), (x1, y1, z1), (-uy, ux), pi, i))
            for i in range(1, len(pts)):
                x, y = pts[i]
                z = p.zs[i]
                cell = (int(x // CELL), int(y // CELL))
                th = self.hmap.get(cell, 0.0)
                key = ("j", int(round(x)), int(round(y)), int(round(z)))
                if key in seen:
                    continue
                seen.add(key)
                kind = 0 if (z < 0.6 and th <= 0) else 1 if abs(z - th) < 0.6 else 2
                self.road_joints.append((x, y, z, kind, cell))

    def roads_at(self, x, y, pad=1.0):
        """every stretch of road over this spot: [(height, open underneath?, how far from its middle line)]"""
        out = []
        lim = ROAD_W + 3 + pad
        for p in self.paths:
            pts, cum = p.pts, p.cum
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                t = clamp(((x - ax) * dx + (y - ay) * dy) / L2, 0.0, 1.0) if L2 else 0.0
                px, py = ax + dx * t, ay + dy * t
                if abs(x - px) <= lim and abs(y - py) <= lim and (x - px) ** 2 + (y - py) ** 2 <= lim * lim:
                    d = cum[i] + math.sqrt(L2) * t
                    out.append((p.zs[i] + (p.zs[i + 1] - p.zs[i]) * t, p.open_at(d), (x - px) ** 2 + (y - py) ** 2))
        return out

    def surf(self, x, y, zref):
        """the height of the surface you would stand on here.  Under a bridge there are two (the floor and the deck):
        you get the one nearest to the height you are already at."""
        base = self.hmap.get((int(x // CELL), int(y // CELL)), 0.0)
        decks = []
        if self.maxroad > 0.5:
            near = None             # the solid stretch of road this spot is closest to (two stretches overlap where they join)
            for z, op, d in self.roads_at(x, y):
                if op:
                    if z > base + 0.5:
                        decks.append(z)
                elif near is None or d < near[0]:
                    near = (d, z)
            if near is not None and near[1] > base + 0.5:
                base = near[1]
        best = base
        for z in decks:
            if z > base and abs(z - zref) < abs(best - zref):
                best = z
        return best

    def top(self, x, y):
        """the highest surface here (effects sit on it)"""
        base = self.hmap.get((int(x // CELL), int(y // CELL)), 0.0)
        if self.maxroad > 0.5:
            near = None
            top = base
            for z, op, d in self.roads_at(x, y, -2.0):
                if op:
                    top = max(top, z)
                elif near is None or d < near[0]:
                    near = (d, z)
            if near is not None:
                top = max(top, near[1])
            return top
        return base

    # ------------------------------------------------------------ geometry
    def road_dist(self, x, y):
        return min(p.nearest(x, y)[0] for p in self.paths)

    def road_info(self, x, y):
        """-> (distance, road number, how far along, road x, road y, direction)"""
        best = None
        for i, p in enumerate(self.paths):
            n = p.nearest(x, y)
            if best is None or n[0] < best[0] - 0.01:
                best = (n[0], i, n[1], n[2], n[3], p.angs[n[4]])
        return best

    def terrain(self, x, y):
        if not (0 <= x < FW and 0 <= y < FH):
            return None
        if self.road_dist(x, y) < ROAD_W:
            return "P"
        c = (int(x // CELL), int(y // CELL))
        if c in self.water:
            return "W"
        return "C" if self.rel.get(c, 0.0) >= 13.0 else "G"

    def height(self, x, y):
        """how high the land is here (roads on banks and bridges are not land)"""
        return self.hmap.get((int(x // CELL), int(y // CELL)), 0.0)

    def stand(self, t):
        """put a tower on the land: how high it stands, and what this map does for it"""
        if t.path:
            ri = self.road_info(t.x, t.y)
            t.z = self.paths[ri[1]].zat(ri[2])
            t.cliff = False
            t.hk = 1.0
        else:
            t.z = self.height(t.x, t.y)
            rel = self.rel.get((int(t.x // CELL), int(t.y // CELL)), 0.0)
            t.cliff = rel >= 13.0
            t.hk = 1.0 + 0.5 * max(0.0, rel / STEP - 1.0)
        t.mb = self.map.get("buff", {}).get(t.kind)

    def place_check(self, kind, x, y):
        """can a tower of this kind stand here?  -> (ok, why not, x, y) - path towers snap onto the road"""
        T = TOWERS[kind]
        h = T.get("box", 15)
        if T["place"] == "P":
            d, pi, dd, px, py, ang = self.road_info(x, y)
            if d > ROAD_W + 10:
                return False, "Path towers go ON the road", x, y
            p = self.paths[pi]
            if p.length - dd < 72:
                return False, "Too close to the core", px, py
            if dd < 56 or not (10 < px < FW - 10 and 10 < py < FH - 10):
                return False, "Too close to the gate", px, py
            for t in self.towers + self.plans:
                if t.path and (t.x - px) ** 2 + (t.y - py) ** 2 < 36 * 36:
                    return False, "Too close to another path tower", px, py
            for cx, cy in self.crossings:
                if (cx - px) ** 2 + (cy - py) ** 2 < 46 * 46:
                    return False, "Not where two roads cross", px, py
            return True, "", px, py
        if not (h <= x <= FW - h and h <= y <= FH - h):
            return False, "Outside the map", x, y
        if self.road_dist(x, y) < ROAD_W + h + 1:
            return False, "Too close to the road", x, y
        k = h * 0.92
        kinds = set()
        for dx, dy in ((0, 0), (-k, -k), (k, -k), (k, k), (-k, k)):
            c = (int((x + dx) // CELL), int((y + dy) // CELL))
            kinds.add("W" if c in self.water else self.hmap.get(c, 0.0))
        if "W" in kinds:
            return False, "Can't build on water", x, y
        if len(kinds) > 1:
            return False, "Half on a cliff: move it all the way on or off", x, y
        tr = "C" if self.rel.get((int(x // CELL), int(y // CELL)), 0.0) >= 13.0 else "G"
        if T["place"] != "B" and T["place"] != tr:
            return False, "%s only goes on %s" % (T["name"], "CLIFFS (land higher than the road)" if T["place"] == "C" else "GROUND (land level with the road)"), x, y
        for t in self.towers + self.plans:
            if not t.path and abs(t.x - x) < t.box + h and abs(t.y - y) < t.box + h:
                return False, "Too close to another tower", x, y
        if (x - self.core[0]) ** 2 + (y - self.core[1]) ** 2 < (36 + h) ** 2:
            return False, "Too close to the core", x, y
        for o in self.marks + self.npcs:
            if (x - o["x"]) ** 2 + (y - o["y"]) ** 2 < (o["rad"] + h) ** 2:
                return False, "Something is in the way", x, y
        return True, "", x, y

    def count(self, P, kind):
        return sum(1 for t in self.towers + self.plans if t.kind == kind and t.owner is P)

    def owned(self, P):
        return sum(1 for t in self.towers + self.plans if t.owner is P)

    def cap(self):
        return tower_cap(len(self.players))

    def limit_check(self, P, kind):
        """limits that do not depend on the spot"""
        if self.owned(P) >= self.cap():
            return "Tower limit reached (%d). Upgrade or sell one." % self.cap()
        if kind == "harvester" and self.count(P, kind) >= HARVESTER_MAX:
            return "Only %d Harvesters allowed" % HARVESTER_MAX
        if kind == "stonks" and self.count(P, kind) >= STONKS_MAX:
            return "Only %d Stonks allowed" % STONKS_MAX
        if kind == "summoner" and self.count(P, kind) >= SUMMONER_MAX:
            return "Only %d Summoners allowed" % SUMMONER_MAX
        if is_path(kind) and sum(1 for t in self.towers + self.plans if t.path and t.owner is P) >= PATH_MAX:
            return "Only %d path towers allowed" % PATH_MAX
        return ""

    def price(self, P, base):
        return int(round(base * (1 - min(0.5, P.mods["discount"])) / 5.0)) * 5

    def cost(self, P, kind):
        return self.price(P, TOWERS[kind]["lv"][0]["cost"])

    def up_cost(self, t):
        if t.lv >= MAXLV:
            return None
        return self.price(t.owner, TOWERS[t.kind]["lv"][t.lv + 1]["cost"])

    def sell_value(self, t):
        return int(t.spent * min(1.0, 0.6 + t.owner.mods["recycle"]))

    def wave_in(self):
        """with friends the next wave starts by itself: how many seconds until it does (0 when it is not counting down)"""
        if self.phase != "build" or len(self.players) < 2:
            return 0.0
        return max(0.0, MP_WAVE_DELAY - self.build_t)

    def place_goon(self, g):
        """work out where a goon stands from how far along its road it is"""
        p = self.paths[g.pi]
        g.x, g.y, seg = p.at(g.d)
        g.z = p.zat(g.d)
        g.ang = p.angs[seg] + math.pi

    def leak_of(self, e):
        """how much the core loses if this enemy gets through right now: exactly the health it has left"""
        if e.leak >= 999:
            return 999
        return max(1, int(math.ceil(e.hp - 0.001)))

    # ------------------------------------------------------------ walking around (orbs bump into things)
    def solid_rounds(self, towers=True):
        """round things an orb bumps into: (x, y, radius, height they stand at)"""
        out = [(self.core[0], self.core[1], 27.0, self.corez)]
        for o in self.marks:
            out.append((o["x"], o["y"], o["rad"] * 0.8, o["z"]))
        for o in self.npcs:
            out.append((o["x"], o["y"], 7.0, o["z"]))
        if towers:
            for t in self.towers:
                if not t.path:
                    out.append((t.x, t.y, t.box * 0.82, t.z))
        return out

    def walk_ok(self, x, y, z, r=ORB_R):
        """can an orb stand here at height z?  All of it has to be on (nearly) level ground: no walls, no drops"""
        surf = self.surf
        if abs(surf(x, y, z) - z) > 8.0:
            return False
        k = r * 0.7071
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r), (k, k), (-k, k), (k, -k), (-k, -k)):
            if abs(surf(x + dx, y + dy, z) - z) > 8.0:
                return False
        return True

    def blocked(self, x, y, r=ORB_R, towers=True, z=None):
        if z is None:
            z = self.surf(x, y, 0.0)
        if not self.walk_ok(x, y, z, r):
            return True
        for ox, oy, orad, oz in self.solid_rounds(towers):
            if abs(oz - z) < 16 and (x - ox) ** 2 + (y - oy) ** 2 < (r + orad) ** 2 - 0.01:
                return True
        return False

    def push_out(self, x, y, r=ORB_R, towers=True, z=0.0):
        """slide a round thing out of towers, landmarks and the core that stand on its level -> (x, y)"""
        rounds = [o for o in self.solid_rounds(towers) if abs(o[3] - z) < 16]
        for _ in range(4):
            moved = False
            for ox, oy, orad, oz in rounds:
                dx, dy = x - ox, y - oy
                d2 = dx * dx + dy * dy
                m = r + orad
                if d2 < m * m - 0.01:
                    d = math.sqrt(d2)
                    if d < 0.01:
                        dx, dy, d = 0.0, 1.0, 1.0
                    x, y = ox + dx / d * m, oy + dy / d * m
                    moved = True
            if not moved:
                break
        return x, y

    def free_spot(self, x, y, r=ORB_R, towers=True):
        """the nearest place to (x, y) where an orb fits"""
        x, y = clamp(x, -40, FW + 40), clamp(y, -40, FH + 40)
        if not self.blocked(x, y, r, towers):
            return x, y
        for d in range(8, 520, 8):
            for i in range(16):
                a = i * TAU / 16
                px, py = clamp(x + math.cos(a) * d, -40, FW + 40), clamp(y + math.sin(a) * d, -40, FH + 40)
                if not self.blocked(px, py, r, towers):
                    return px, py
        return x, y

    def walk(self, x, y, z, nx, ny, r=ORB_R, towers=True):
        """move an orb from (x, y, z) towards (nx, ny).  It slides along walls, climbs ramps and never steps off an edge.
        -> the new (x, y, z)"""
        surf = self.surf
        for tx, ty in ((nx, ny), (nx, y), (x, ny)):
            if tx == x and ty == y:
                continue
            tz = surf(tx, ty, z)
            if abs(tz - z) <= 8.0 and self.walk_ok(tx, ty, tz, r):
                px, py = self.push_out(tx, ty, r, towers, tz)
                if px != tx or py != ty:
                    pz = surf(px, py, tz)
                    if abs(pz - tz) > 8.0 or not self.walk_ok(px, py, pz, r):
                        continue
                    return px, py, pz
                return tx, ty, tz
        return x, y, z

    def spawn_spot(self, i=0, n=1):
        """where a player starts: beside the road, as near the middle of the map as it gets (the road always leads out)"""
        p = self.paths[0]
        cands = []
        d = 60.0
        while d < p.length - 90:
            x, y, seg = p.at(d)
            if 50 < x < FW - 50 and 50 < y < FH - 50:
                cands.append(((x - FW / 2.0) ** 2 + (y - FH / 2.0) ** 2, d))
            d += 20.0
        cands.sort()
        shift = (i - (n - 1) / 2.0) * 26.0
        for s, d in cands:
            x, y, seg = p.at(clamp(d + shift, 30.0, p.length - 60.0))
            a = p.angs[seg] + math.pi / 2
            for off in (36, -36, 46, -46):
                px, py = x + math.cos(a) * off, y + math.sin(a) * off
                if 10 < px < FW - 10 and 10 < py < FH - 10 and not self.blocked(px, py) and self.road_dist(px, py) > ROAD_W + ORB_R + 2:
                    return px, py
        return self.free_spot(FW / 2.0, FH / 2.0)

    def tower_at(self, x, y, pad=4):
        best, bd = None, 1e9
        for t in self.towers:
            d = max(abs(t.x - x), abs(t.y - y))
            if d < t.box + pad and d < bd:
                best, bd = t, d
        return best

    # ------------------------------------------------------------ scenery (only for looks, same on every computer)
    def make_scenery(self):
        rnd = random.Random(self.mapi * 7919 + 11)
        th = self.theme
        self.props = []         # (name, variant, x, y, z, angle, size)
        names = [n for n, w in th["props"] for _ in range(w)]
        if names:
            tries = 0
            while len(self.props) < 46 and tries < 600:
                tries += 1
                side = rnd.randrange(4)
                off = rnd.uniform(36, 250)
                if side == 0:
                    x, y = rnd.uniform(-240, FW + 240), -off
                elif side == 1:
                    x, y = rnd.uniform(-240, FW + 240), FH + off
                elif side == 2:
                    x, y = -off, rnd.uniform(-100, FH + 100)
                else:
                    x, y = FW + off, rnd.uniform(-100, FH + 100)
                if self.road_dist(x, y) < 64:
                    continue
                name = rnd.choice(names)
                big = name in ("datatower", "building", "volcano", "pyramid", "lighthouse", "chimney", "crane", "island", "cloud", "tank", "pot")
                if big and off < 90:
                    continue
                if any((x - p[2]) ** 2 + (y - p[3]) ** 2 < (70 if big else 34) ** 2 for p in self.props):
                    continue
                self.props.append((name, rnd.randrange(3), x, y, 0.0, rnd.uniform(0, TAU), 1.0))
        self.decor = []
        inner = [n for n, w in th["inner"] for _ in range(w)]
        if inner:
            tries = 0
            while len(self.decor) < 26 and tries < 300:
                tries += 1
                x, y = rnd.uniform(14, FW - 14), rnd.uniform(14, FH - 14)
                if self.road_dist(x, y) < ROAD_W + 24 or self.terrain(x, y) == "W":
                    continue
                h0 = self.height(x, y)
                if any(self.height(x + ax, y + ay) != h0 for ax, ay in ((-12, 0), (12, 0), (0, -12), (0, 12), (-9, -9), (9, -9), (9, 9), (-9, 9))):
                    continue
                if any((x - o["x"]) ** 2 + (y - o["y"]) ** 2 < 34 * 34 for o in self.marks + self.npcs):
                    continue
                if (x - self.core[0]) ** 2 + (y - self.core[1]) ** 2 < 64 * 64 or any((x - p[2]) ** 2 + (y - p[3]) ** 2 < 28 * 28 for p in self.decor):
                    continue
                self.decor.append((rnd.choice(inner), rnd.randrange(3), x, y, self.height(x, y), rnd.uniform(0, TAU), 0.6))
        # flat marks on the ground
        self.decals = []
        d = th["decal"]
        for _ in range(0 if d is None else 60):
            x, y = rnd.uniform(-160, FW + 160), rnd.uniform(-140, FH + 140)
            if 0 <= x < FW and 0 <= y < FH and (self.terrain(x, y) != "G" or self.road_dist(x, y) < ROAD_W + 6):
                continue
            a = rnd.choice((0.0, math.pi / 2)) if d in ("circuit", "tiles", "glitch", "chart", "checker") else rnd.uniform(0, TAU)
            self.decals.append((x, y, a, rnd.uniform(14, 44), rnd.random()))
        self.amb = [[rnd.uniform(-200, FW + 200), rnd.uniform(-150, FH + 150), rnd.uniform(4, 150), rnd.random()] for _ in range(46)] if th["amb"] else []

    # ------------------------------------------------------------ effects
    def sfx(self, name, vol=1.0):
        if self.fx:
            self.ev.append((name, vol))
        if self.net:
            self.fxlog.append(["s", name, vol])

    def burst(self, x, y, col, n=8, spd=120, life=0.5, size=3, z=10.0, lift=True):
        """z is the height above whatever is at (x, y): the floor, a plateau or a raised road"""
        if lift and self.maxh + self.maxroad > 0:
            z += self.top(x, y)
        if self.net:
            self.fxlog.append(["b", int(x), int(y), col, n, spd, life, size, int(z)])
        if not self.fx or len(self.parts) > 700:
            return
        rnd = self.frnd
        for _ in range(n):
            a = rnd.uniform(0, TAU)
            v = rnd.uniform(0.3, 1.0) * spd
            lf = life * rnd.uniform(0.5, 1.0)
            self.parts.append([x, y, z, math.cos(a) * v, math.sin(a) * v, rnd.uniform(0.1, 0.9) * spd, lf, lf, col, size])

    def ring(self, x, y, r0, r1, col, life=0.4, width=3, z=1.5, lift=True):
        if lift and self.maxh + self.maxroad > 0:
            z += self.top(x, y)
        if self.net:
            self.fxlog.append(["r", int(x), int(y), int(r0), int(r1), col, life, width, int(z)])
        if self.fx:
            self.rings.append([x, y, z, r0, r1, life, life, col, width])

    def text(self, x, y, txt, col, size=18, life=0.8, z=24.0, lift=True):
        if lift and self.maxh + self.maxroad > 0:
            z += self.top(x, y)
        if self.net:
            self.fxlog.append(["t", int(x), int(y), txt, col, size, life, int(z)])
        if self.fx and len(self.texts) < 80:
            self.texts.append([x, y, z, txt, col, life, life, size])

    def bolt(self, pts, col, life=0.14, width=2):
        """pts are (x, y, z)"""
        if self.net:
            self.fxlog.append(["l", [(int(p[0]), int(p[1]), int(p[2])) for p in pts], col, life, width])
        if self.fx:
            self.bolts.append([pts, life, life, col, width])

    def say(self, txt, col=WHITE, life=2.4):
        if self.net:
            self.fxlog.append(["y", txt, col, life])
        self.banner = [txt, col, life, life]

    def add_corpse(self, e, goon=False):
        """leave the body of a killed enemy (or goon) lying there for a moment.  Only for looks: nothing in the match reads this."""
        if not self.fx:
            return
        cs = self.corpses
        if len(cs) >= CORPSE_MAX:
            del cs[0]
        # [model, colour, x, y, z, angle, size, age, how long it stays, boss?, walk phase]
        if goon:
            col = e.owner.tcol("summoner") if e.owner is not None else TOWERS["summoner"]["col"]
            cs.append([("goon", e.lv), col, e.x, e.y, e.z, e.ang, e.r, 0.0, CORPSE_TIME, False, -e.d * WALK_K])
        else:
            cs.append([e.model, e.col, e.x, e.y, e.z, e.ang, e.r, 0.0, CORPSE_BOSS if e.boss else CORPSE_TIME, e.boss, e.d * WALK_K])

    def play_fx(self, log):
        """a Wi-Fi guest replays what the host saw"""
        for f in log:
            try:
                k = f[0]
                if k == "s":
                    self.ev.append((f[1], f[2]))
                elif k == "b":
                    self.burst(f[1], f[2], tuple(f[3]), f[4], f[5], f[6], f[7], f[8], False)
                elif k == "r":
                    self.ring(f[1], f[2], f[3], f[4], tuple(f[5]), f[6], f[7], f[8], False)
                elif k == "t":
                    self.text(f[1], f[2], str(f[3]), tuple(f[4]), f[5], f[6], f[7], False)
                elif k == "l":
                    self.bolt([tuple(p) for p in f[1]], tuple(f[2]), f[3], f[4])
                elif k == "y":
                    self.say(str(f[1]), tuple(f[2]), f[3])
            except Exception:
                pass

    def upd_fx(self, dt):
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 2.2)
        if self.core_hit > 0:
            self.core_hit -= dt
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None
        if self.parts:
            for p in self.parts:
                p[0] += p[3] * dt
                p[1] += p[4] * dt
                p[2] += p[5] * dt
                p[3] *= 0.96
                p[4] *= 0.96
                p[5] -= 260 * dt
                if p[2] < 0.5:
                    p[2] = 0.5
                    p[5] = -p[5] * 0.4
                p[6] -= dt
            self.parts = [p for p in self.parts if p[6] > 0]
        if self.rings:
            for r in self.rings:
                r[5] -= dt
            self.rings = [r for r in self.rings if r[5] > 0]
        if self.bolts:
            for b in self.bolts:
                b[1] -= dt
            self.bolts = [b for b in self.bolts if b[1] > 0]
        if self.texts:
            for t in self.texts:
                t[2] += 30 * dt
                t[5] -= dt
            self.texts = [t for t in self.texts if t[5] > 0]
        if self.corpses:
            for c in self.corpses:
                c[7] += dt
            self.corpses = [c for c in self.corpses if c[7] < c[8]]


# ======================================================================
#  THE WORLD  -  everything that happens in a match (no drawing here)
# ======================================================================
class World(Field):
    def __init__(self, mapkey, diff="normal", specs=None, seed=None, fx=True):
        Field.__init__(self, mapkey, fx)
        if self.map.get("event"):
            diff = "event"
        self.diff = diff
        self.D = DIFFS[diff]
        # how tough enemies are on this map: its own number, times a fine-tuning number for this difficulty
        self.maphp = self.map.get("hp", 1.0) * self.map.get("dhp", {}).get(diff, 1.0)
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rnd = random.Random(self.seed)
        self.players = [Player(i, s) for i, s in enumerate(specs or [{}])]
        n = len(self.players)
        self.mp = 1 + MP_HP * (n - 1)
        self.gm = dict(corehp=0, aegis=0, gravity=0.0, regen=0)        # things every player shares
        for i, P in enumerate(self.players):
            P.cash = float(self.D["cash"] + P.mods["startcash"] + self.map.get("cash", 0))
            self.gm["corehp"] += P.mods["corehp"]
            P.x, P.y = self.spawn_spot(i, n)
            P.z = self.surf(P.x, P.y, 0.0)
            P.skip = False
        self.maxhp = self.hp = self.D["core"] + self.gm["corehp"]
        self.aegis = 0
        self.wave = 0
        self.nwaves = self.D["waves"]
        self.phase = "build"            # build / wave / cards / over
        self.queue = []
        self.qi = 0
        self.wt = 0.0
        self.cur = None
        self.card_t = 0.0
        # with friends the next wave starts by itself when build_t reaches MP_WAVE_DELAY (the first wave of a match waits a little longer)
        self.build_t = (MP_WAVE_DELAY - MP_FIRST_DELAY) if n > 1 else 0.0
        self.after_cards = "build"      # where the match goes once everyone has picked a card
        self.cleared = 0                # the last wave that was really beaten (skipping does not count)
        self.skips = 0
        self.playtime = 0.0
        self.result = None
        self.stars = 0
        self.boss = None
        self.reveals = []
        self.ptowers = []
        self.stats = dict(kills=0, earned=0, built=0, leaks=0, bosses=0, ptfalls=0, hitcash=0)
        self.flags = set()              # side quest things that happened in this match
        self.guide = []                 # what the bot did, for the strat videos
        self.next_id = 1
        self.rev = 0                    # goes up whenever the set of towers changes
        self.next = self.make_wave(1)

    def hostiles(self):
        return len(self.enemies) + (len(self.queue) - self.qi if self.phase == "wave" else 0)

    def nid(self):
        self.next_id += 1
        return self.next_id

    # ------------------------------------------------------------ building
    def why_not(self, P, kind, x, y):
        lim = self.limit_check(P, kind)
        if lim:
            return lim
        ok, why, _, _ = self.place_check(kind, x, y)
        return "" if ok else why

    def plan(self, P, kind, x, y):
        """place a tower ahead of time.  It is a ghost that does nothing until its owner can pay for it."""
        if self.phase == "over" or kind not in P.loadout or self.limit_check(P, kind):
            return None
        ok, why, x, y = self.place_check(kind, x, y)
        if not ok:
            return None
        t = Tower(self.nid(), kind, x, y, P)
        t.ghost = True
        t.t = self.frnd.uniform(0, 6)
        self.stand(t)
        L0 = TOWERS[kind]["lv"][0]
        t.rng = L0.get("rng", 0) * (1 + P.mods["rng"] + ((CLIFF_RANGE * t.hk + P.mods["cliffrng"]) if t.cliff else 0))
        if t.path:
            ri = self.road_info(x, y)
            t.ang = ri[5] + math.pi
            t.z = self.paths[ri[1]].zat(ri[2])
        self.plans.append(t)
        self.rev += 1
        self.sfx("click")
        self.ring(x, y, 6, 30, GOLD, 0.3, 2, 1.5)
        return t

    def cancel_plan(self, P, t):
        if t in self.plans and t.owner is P:
            self.plans.remove(t)
            self.rev += 1
            self.sfx("sell", 0.6)
            return True
        return False

    def upd_plans(self):
        """turn planned towers into real ones, oldest first, as soon as their owner has the cash"""
        for t in list(self.plans):
            P = t.owner
            if not P.here:
                self.plans.remove(t)
                self.rev += 1
            elif P.cash >= self.cost(P, t.kind):
                self.plans.remove(t)
                self.rev += 1
                if self.build(P, t.kind, t.x, t.y) is not None:
                    self.text(t.x, t.y, "BUILT", GOLD, 18, 0.9, 44)

    def build(self, P, kind, x, y):
        if self.phase == "over" or kind not in P.loadout:
            return None
        c = self.cost(P, kind)
        if P.cash < c or self.limit_check(P, kind):
            return None
        ok, why, x, y = self.place_check(kind, x, y)
        if not ok:
            return None
        P.cash -= c
        t = Tower(self.nid(), kind, x, y, P)
        t.spent = c
        t.born = self.time
        t.t = self.frnd.uniform(0, 6)
        self.stand(t)
        if t.path:
            for i, p in enumerate(self.paths):
                nd = p.nearest(x, y)
                if nd[0] < 6:
                    t.pd[i] = nd[1]
                    t.ang = p.angs[nd[4]] + math.pi
                    t.z = p.zat(nd[1])
        self.towers.append(t)
        P.built += 1
        self.stats["built"] += 1
        self.recalc()
        if t.path:
            t.hp = t.maxhp
        self.sfx("place")
        col = P.tcol(kind)
        self.ring(x, y, 6, 44, col, 0.35, 3, 1.5)
        self.burst(x, y, col, 10, 110, 0.5, 3, 8)
        self.check_pine()
        return t

    def upgrade(self, P, t):
        if t is None or t.owner is not P or t not in self.towers or self.phase == "over":
            return False
        c = self.up_cost(t)
        if c is None or P.cash < c:
            return False
        P.cash -= c
        t.spent += c
        t.lv += 1
        t.L = TOWERS[t.kind]["lv"][t.lv]
        self.recalc()
        self.sfx("upgrade")
        self.ring(t.x, t.y, 8, 54, WHITE, 0.4, 3, 1.5)
        self.burst(t.x, t.y, P.tcol(t.kind), 14, 150, 0.5, 3, 12)
        self.text(t.x, t.y, "LEVEL %d" % (t.lv + 1) if t.lv < MAXLV else "MAX LEVEL", GOLD if t.lv == MAXLV else WHITE, 20, 0.8, 44)
        return True

    def sell(self, P, t):
        if t is None or t.owner is not P or t not in self.towers or self.phase == "over":
            return 0
        v = self.sell_value(t)
        P.cash += v
        self.remove_tower(t)
        self.sfx("sell")
        self.text(t.x, t.y, "+%d" % v, GOLD, 20, 0.8, 30)
        self.burst(t.x, t.y, GREY, 12, 120, 0.5, 3, 10)
        return v

    def remove_tower(self, t):
        if t in self.towers:
            self.towers.remove(t)
        for e in t.block:
            e.block = None
        t.block = []
        t.down = True
        if t.kind == "summoner" and self.goons:
            # its goons go with it
            for g in self.goons:
                if g.tw is t:
                    g.dead = True
                    self.burst(g.x, g.y, GREY, 5, 90, 0.4, 2, g.r)
            self.goons = [g for g in self.goons if not g.dead]
        self.recalc()

    def set_mode(self, P, t):
        if t is not None and t.owner is P and TOWERS[t.kind]["atk"] in ("RANGED", "MELEE", "BOTH"):
            t.mode = (t.mode + 1) % len(TARGET_MODES)
            return True
        return False

    def recalc(self):
        """work out every tower's range and which support towers reach it"""
        self.rev += 1
        sup = [t for t in self.towers if t.kind in SUPPORT_KINDS]
        for t in sup:
            m = t.owner.mods
            t.rb = t.db = 0.0
            t.rng = t.L["rng"] * (1 + m["aura"] + (0.15 if t.tp == "medic" else 0) + ((CLIFF_RANGE * t.hk + m["cliffrng"]) if t.cliff else 0) + (t.mb.get("rng", 0) if t.mb else 0))
            t.cmds = []
            t.mechs = []
        beacons = [t for t in sup if t.kind == "beacon"]
        cmds = [t for t in sup if t.kind == "commander"]
        mechs = [t for t in sup if t.kind == "mechanic"]
        self.reveals = [t for t in beacons if t.L.get("reveal")]
        self.ptowers = [t for t in self.towers if t.path]
        for t in self.towers:
            if t.kind in SUPPORT_KINDS:
                continue
            m = t.owner.mods
            rb = db = 0.0
            for b in beacons:
                if (b.x - t.x) ** 2 + (b.y - t.y) ** 2 <= b.rng * b.rng:
                    rb = max(rb, b.L["rbuff"])
                    if b.tp == "spotter":
                        db = 0.08
            t.rb, t.db = rb, db
            L = t.L
            if t.path:
                t.rng = L.get("rng", 0) * (1 + m["melee"] + (t.mb.get("rng", 0) if t.mb else 0))
                old = t.maxhp
                t.maxhp = L["hp"] * (1 + m["pathhp"] + (t.mb.get("hp", 0) if t.mb else 0))
                if old > 0 and t.maxhp > old and not t.down:
                    t.hp = min(t.maxhp, t.hp + (t.maxhp - old))
            else:
                k = 1 + m["rng"] + rb + ((CLIFF_RANGE * t.hk + m["cliffrng"]) if t.cliff else 0) + (t.mb.get("rng", 0) if t.mb else 0)
                if t.kind in ("blade", "cat"):
                    k += m["melee"] + (0.10 if t.tp == "whirl" else 0)
                t.rng = L.get("rng", 0) * k
                t.mrng = L.get("mrng", 0) * (k + m["melee"])
            t.cmds = [c for c in cmds if (c.x - t.x) ** 2 + (c.y - t.y) ** 2 <= c.rng * c.rng]
            t.mechs = [c for c in mechs if (c.x - t.x) ** 2 + (c.y - t.y) ** 2 <= c.rng * c.rng]

    def rate_buff(self, t):
        b = 0.0
        for c in t.cmds:
            if c.stun <= 0:
                v = c.L["act"] if c.act > 0 else c.L["pas"]
                if v > b:
                    b = v
        return b

    def cd_of(self, t, base):
        k = (1 - min(0.6, t.owner.mods["rate"])) * (1 - self.rate_buff(t))
        if t.mb:
            k *= 1 - t.mb.get("rate", 0)
        if t.od > 0:
            k *= 0.74
        if t.duel > 0:
            k *= 0.7
        return base * k

    def check_pine(self):
        """side quest: three towers around the big pine"""
        if self.mapid == "frost" and "pine" not in self.flags:
            for mk in self.marks:
                if mk["id"] == "bigpine" and sum(1 for t in self.towers if (t.x - mk["x"]) ** 2 + (t.y - mk["y"]) ** 2 < 92 * 92) >= 3:
                    self.flags.add("pine")
                    self.burst(mk["x"], mk["y"], GOLD, 40, 220, 1.0, 4, 60)
                    self.sfx("secret")

    def tower_ability(self, P, t):
        if t is None or t.owner is not P or t.kind != "commander" or t.acd > 0 or t.act > 0 or t.stun > 0 or self.phase != "wave":
            return False
        t.act = t.L["dur"] * (1.4 if t.tp == "drums" else 1.0)
        t.acd = t.L["acd"] * (1 - min(0.6, P.mods["charge"])) * (0.8 if t.tp == "drums" else 1.0)
        self.sfx("clock")
        self.ring(t.x, t.y, 10, t.rng, RED, 0.6, 4, 2)
        self.text(t.x, t.y, "CALL TO ARMS!", RED, 22, 1.2, 50)
        return True

    def use_ability(self, P, slot, x, y):
        if not (0 <= slot < len(P.abils)) or P.acd[slot] > 0 or self.phase != "wave":
            return False
        if not (-40 <= x <= FW + 40 and -40 <= y <= FH + 40):
            return False
        kind = P.abils[slot]
        a = ABILS[kind]
        P.acd[slot] = a["cd"] * (1 - min(0.6, P.mods["charge"]))
        self.casts.append(dict(kind=kind, x=x, y=y, t=0.0, hit=False, rad=a["rad"] * (1 + P.mods["splash"] * 0.5), P=P, id=self.nid()))
        self.sfx("card", 0.7)
        if kind == "napalm":
            for mk in self.marks:
                if mk["id"] == "stove" and (mk["x"] - x) ** 2 + (mk["y"] - y) ** 2 < (a["rad"] + 10) ** 2:
                    self.flags.add("toast")
        return True

    def ready(self, P):
        """a player asks for the next wave.  Alone: it starts.  With friends nobody has to ask: the next wave starts by itself
        (see MP_WAVE_DELAY), so this does nothing there."""
        if self.phase != "build":
            return False
        P.ready = True
        if len(self.players) > 1:
            return True
        return self.start_wave()

    def apply(self, pid, act):
        """one door for everything a player can do (the Wi-Fi host calls this for its guests)"""
        try:
            P = self.players[pid]
            k = act[0]
            if k == "build":
                kind, x, y = str(act[1]), float(act[2]), float(act[3])
                if self.build(P, kind, x, y) is not None:
                    return True
                # not enough cash yet: leave a ghost that builds itself later
                if len(act) > 4 and act[4] and kind in P.loadout and P.cash < self.cost(P, kind):
                    return self.plan(P, kind, x, y) is not None
                return False
            if k == "ready":
                return self.ready(P)
            if k == "skip":
                return self.vote_skip(P)
            if k == "card":
                return self.pick_card(P, int(act[1]))
            if k == "abil":
                return self.use_ability(P, int(act[1]), float(act[2]), float(act[3]))
            if k == "pos":
                P.x, P.y = clamp(float(act[1]), -60, FW + 60), clamp(float(act[2]), -60, FH + 60)
                P.z = clamp(float(act[3]), 0.0, 200.0) if len(act) > 3 else self.surf(P.x, P.y, P.z)
                return True
            t = None
            tid = int(act[1])
            for q in self.towers:
                if q.id == tid:
                    t = q
                    break
            if t is None and k == "sell":
                for q in self.plans:
                    if q.id == tid:
                        return self.cancel_plan(P, q)
            if k == "up":
                return self.upgrade(P, t)
            if k == "sell":
                return bool(self.sell(P, t))
            if k == "mode":
                return self.set_mode(P, t)
            if k == "tabil":
                return self.tower_ability(P, t)
        except Exception:
            return False
        return False

    # ------------------------------------------------------------ waves
    def boss_of(self, w):
        b = self.map["bosses"]
        if w == self.nwaves:
            return b[2]
        if w % 10 == 0:
            return b[(w // 10 - 1) % 2]
        return None

    def make_wave(self, w):
        rnd = random.Random(self.mapi * 977 + w * 31 + 7)
        early = self.D["early"]
        boss = self.boss_of(w)
        budget = wave_budget(w) * (0.5 if boss else 1.0)
        avail = [k for k, v in WAVE_UNITS.items() if w + early >= v[0]]
        picks = [k for k in avail if WAVE_UNITS[k][0] == w + early and w > 2][:1]
        pool = [k for k in avail if k not in picks]
        ng = 1 if w < 3 else 2 if w < 9 else 3
        while len(picks) < ng and pool:
            ws = [WAVE_UNITS[k][2] * (1.6 if WAVE_UNITS[k][0] > w * 0.45 else 1.0) for k in pool]
            k = rnd.choices(pool, ws)[0]
            picks.append(k)
            pool.remove(k)
        shares = [rnd.uniform(0.6, 1.4) for _ in picks]
        tot = sum(shares)
        groups = [[k, max(1, int(round(budget * sh / tot / WAVE_UNITS[k][1])))] for k, sh in zip(picks, shares)]
        total = sum(n for _, n in groups)
        cap = 30 + w * 1.3
        hpx = 1.0
        if total > cap:
            hpx = total / cap
            for g in groups:
                g[1] = max(1, int(round(g[1] / hpx)))
        ev = []
        npaths = len(self.paths)
        totcost = 0.0
        for gi, (k, n) in enumerate(groups):
            gap = WAVE_UNITS[k][3] * max(0.6, 1 - 0.012 * w)
            start = gi * rnd.uniform(2.0, 4.5)
            for i in range(n):
                ev.append([start + i * gap, k, (i + gi) % npaths, WAVE_UNITS[k][1]])
                totcost += WAVE_UNITS[k][1]
        kc = kill_cash(w) * (0.55 + 0.45 * len(self.players))
        for e in ev:
            e[3] = kc * e[3] / totcost
        if boss:
            ev.append([3.0, boss, rnd.randrange(npaths), wave_bonus(w)])
        ev.sort(key=lambda e: e[0])
        counts = {}
        for e in ev:
            counts[e[1]] = counts.get(e[1], 0) + 1
        return dict(ev=ev, counts=counts, boss=boss, hpx=hpx, w=w)

    def hm(self, w=None, hpx=1.0):
        w = w or max(1, self.wave)
        return hp_mult(w) * (self.D["hp"] + self.D["hpw"] * w) * self.maphp * hpx * self.mp

    def start_wave(self):
        if self.phase != "build":
            return False
        self.wave += 1
        self.cur = self.next
        self.next = self.make_wave(self.wave + 1) if self.wave < self.nwaves else None
        self.queue = self.cur["ev"]
        self.qi = 0
        self.wt = 0.0
        self.phase = "wave"
        self.build_t = 0.0
        for P in self.players:
            P.ready = False
            P.skip = False
        self.aegis = self.gm["aegis"]
        if self.cur["boss"]:
            self.say("BOSS WAVE:  " + ENEMIES[self.cur["boss"]]["name"], RED, 3.2)
            self.sfx("boss")
        else:
            self.say("WAVE %d" % self.wave, WHITE, 1.6)
            self.sfx("wave")
        return True

    def skip_why(self):
        """'' when the wave can be skipped right now, else the reason it cannot"""
        if self.phase != "wave" or self.cur is None:
            return "No wave is running"
        if self.cur["boss"]:
            return "Boss waves can't be skipped"
        if self.next is None or self.wave >= self.nwaves:
            return "This is the last wave"
        if self.wt < SKIP_WAIT:
            return "Skip opens in %ds" % math.ceil(SKIP_WAIT - self.wt)
        return ""

    def skip_votes(self):
        here = [q for q in self.players if q.here]
        return sum(1 for q in here if q.skip), len(here) // 2 + 1

    def vote_skip(self, P):
        """a player asks to skip the wave.  Alone: it happens.  With friends: more than half must agree."""
        if self.skip_why():
            return False
        P.skip = not P.skip if len(self.players) > 1 else True
        have, need = self.skip_votes()
        if have >= need:
            return self.skip_wave()
        return True

    def skip_wave(self):
        """pay this wave's bonus now and send the next wave in on top of whatever is still alive"""
        if self.skip_why():
            return False
        w = self.wave
        self.wave_pay(w, "WAVE SKIPPED")
        self.skips += 1
        # enemies of this wave that have not walked in yet still come, as strong as they were going to be
        hm = self.hm(w, self.cur["hpx"])
        rest = [[ev[0] - self.wt, ev[1], ev[2], ev[3], ev[4] if len(ev) > 4 else hm] for ev in self.queue[self.qi:]]
        self.wave += 1
        self.cur = self.next
        self.next = self.make_wave(self.wave + 1) if self.wave < self.nwaves else None
        self.queue = sorted(rest + [list(ev) for ev in self.cur["ev"]], key=_first)
        self.qi = 0
        self.wt = 0.0
        for q in self.players:
            q.skip = False
        if self.cur["boss"]:
            self.say("BOSS WAVE:  " + ENEMIES[self.cur["boss"]]["name"], RED, 3.2)
            self.sfx("boss")
        else:
            self.say("WAVE %d" % self.wave, WHITE, 1.6)
            self.sfx("wave")
        if w % CARD_EVERY == 0:
            for q in self.players:
                self.offer_cards(q, 0)
            self.phase = "cards"
            self.after_cards = "wave"
            self.card_t = 25.0
        return True

    def spawn(self, kind, pi, d=0.0, bounty=0.0, hm=None):
        E = ENEMIES[kind]
        final = False
        if hm is None:
            if E.get("boss"):
                if self.wave >= self.nwaves:
                    final = True
                    hm = self.D["boss"] * self.mp / float(E["hp"])
                else:
                    hm = hp_mult(self.wave) ** BOSS_POW * BOSS_HP * (self.D["hp"] + self.D["hpw"] * self.wave) * self.maphp * self.mp
            else:
                hm = self.hm(self.wave, self.cur["hpx"] if self.cur else 1.0)
        e = Enemy(self.nid(), kind, pi, d, hm, bounty, self.rnd.uniform(0, 4))
        if final:
            e.leak = 999
            # the last boss takes about the same time to arrive on every map, long road or short
            e.spd = min(e.spd * FINAL_SPD, self.paths[pi].length / (FINAL_TIME * (1 + 0.25 * (len(self.paths) - 1))))
            e.atk = (3 + E["hp"] * 0.05) * hp_mult(self.wave) ** 0.7
        if kind == "wrecker":
            e.atk *= 3
        e.spd *= self.D["spd"]
        p = self.paths[pi]
        e.x, e.y, seg = p.at(d)
        e.z = p.zat(d)
        e.ang = p.angs[seg]
        e.rem = p.length - d
        if kind == "blinker":
            e.a1 = self.rnd.uniform(2.5, 4.5)
        if e.boss:
            self.boss = e
            e.a1, e.a2 = 5.0, 9.0
        self.enemies.append(e)
        return e

    def wave_pay(self, w, label="WAVE CLEAR"):
        """the cash everyone gets for a wave (also paid early when a wave is skipped)"""
        base = wave_bonus(w)
        if self.cur and self.cur.get("boss") and self.cur.get("w") == w:
            base = int(base * BOSS_WAVE_PAY)        # a boss wave pays extra when it is over (there is no cash for the kill itself)
            if label == "WAVE CLEAR":
                label = "BOSS WAVE CLEAR"
        gains = dict((P.id, base) for P in self.players)
        for t in self.towers:
            t.waves += 1
            if t.kind == "harvester":
                inc = t.L["income"]
                if t.tp == "compound":
                    inc = int(inc * (1 + min(1.0, 0.04 * t.waves)))
                if t.mb:
                    inc = int(inc * (1 + t.mb.get("income", 0)))
                gains[t.owner.id] += inc
                self.text(t.x, t.y, "+%d" % inc, YELLOW, 20, 1.3, 34)
                self.burst(t.x, t.y, YELLOW, 8, 90, 0.5, 3, 14)
            elif t.kind == "stonks":
                f = self.rnd.choice((0.25, 0.5, 0.8, 1.0, 1.0, 1.4, 1.8, 2.4))
                inc = int(t.L["income"] * f * (1 + (t.mb.get("income", 0) if t.mb else 0)))
                gains[t.owner.id] += inc
                self.text(t.x, t.y, ("STONKS  +%d" if f >= 1 else "NOT STONKS  +%d") % inc, STONK_G if f >= 1 else STONK_R, 20, 1.6, 44)
                self.burst(t.x, t.y, STONK_G if f >= 1 else STONK_R, 10, 110, 0.6, 3, 20)
        for P in self.players:
            P.cash += gains[P.id]
        self.stats["earned"] += sum(gains.values())
        if self.gm["regen"] and self.hp < self.maxhp:
            self.hp = min(self.maxhp, self.hp + self.gm["regen"])
        self.text(self.core[0], self.core[1], "%s  +%d" % (label, base), GOLD, 24, 1.8, 70)

    def wave_clear(self):
        w = self.wave
        self.wave_pay(w)
        self.cleared = w
        for t in self.towers:
            if t.path:
                lost = int(round(t.maxhp - t.hp))
                if lost > 0:
                    self.text(t.x, t.y, "+%d" % lost, GREEN, 22, 1.6, 40)
                    self.burst(t.x, t.y, GREEN, 10, 90, 0.6, 3, 14)
                t.hp = t.maxhp
                t.down = False
                t.down_t = 0.0
                t.block = []
        for P in self.players:
            P.skip = False
        self.enemies = []
        self.boss = None
        if w >= self.nwaves:
            self.phase = "over"
            self.result = "win"
            frac = self.hp / float(self.maxhp)
            self.stars = 3 if frac >= 0.999 else 2 if frac >= 0.5 else 1
            self.say("TRIUMPH", GOLD, 4)
            self.sfx("win")
            return
        self.sfx("clear")
        if w % CARD_EVERY == 0:
            for P in self.players:
                self.offer_cards(P, 1 if w % 10 == 0 else 0)
            self.phase = "cards"
            self.card_t = 25.0
        else:
            self.phase = "build"
            self.build_t = 0.0

    def offer_cards(self, P, min_rar=0):
        rnd = self.rnd
        out = []
        for cat in ("ATTACK", "DEFENSE", "SUPPORT"):
            pool = [c for c in CARDS if c[0] == cat]
            c = rnd.choice(pool)
            roll = rnd.random()
            epic = 0.08 + self.wave * 0.006
            rar = 2 if roll < epic else 1 if roll < epic + 0.30 + self.wave * 0.006 else 0
            rar = max(rar, min_rar)
            v = c[3][rar]
            if c[2] == "cash":
                v = int(v * (1 + self.wave / 10.0) / 10) * 10
            txt = c[4].replace("{p}", str(int(round(v * 100))) if isinstance(v, float) else str(v)).replace("{v}", str(v))
            out.append(dict(cat=cat, name=c[1], key=c[2], val=v, rar=rar, text=txt))
        P.offer = out

    def pick_card(self, P, i):
        if self.phase != "cards" or not P.offer or not (0 <= i < len(P.offer)):
            return False
        c = P.offer[i]
        k, v = c["key"], c["val"]
        if k == "cash":
            P.cash += v
        elif k == "corehp":
            self.maxhp += v
            self.hp = min(self.maxhp, self.hp + v)
        elif k in GLOBAL_MODS:
            self.gm[k] += v
        else:
            P.mods[k] += v
        P.cards.append(c)
        P.offer = None
        self.recalc()
        self.sfx("card")
        if all(q.offer is None or not q.here for q in self.players):
            for q in self.players:
                q.offer = None
            self.phase = self.after_cards
            self.after_cards = "build"
            self.build_t = 0.0
        return True

    # ------------------------------------------------------------ damage
    def hurt(self, e, dmg, src=None, pierce=False, quiet=False, shieldx=1.0, crit=False, P=None, pay=True):
        if e.dead:
            return
        if src is not None:
            P = src.owner
            if src.mb:
                dmg *= 1 + src.mb.get("dmg", 0)         # this map suits this tower
        m = P.mods if P is not None else MODS0
        took = 0.0
        if m["bossdmg"] and (e.boss or e.kind in ("elite", "jugger")):
            dmg *= 1 + m["bossdmg"]
        if m["finisher"] and e.hp < e.max * 0.3:
            dmg *= 1 + m["finisher"]
        if e.vuln > 0:
            dmg *= 1.15
        if e.dr > 0:
            dmg *= 0.35
        if e.shield > 0:
            sd = dmg * shieldx
            e.sreg = 0.0
            if sd <= e.shield:
                e.shield -= sd
                e.flash = 0.05
                if src is not None:
                    src.dealt += sd
                if pay and P is not None:
                    self.hit_cash(e, P, sd, quiet)
                return
            if src is not None:
                src.dealt += e.shield
            dmg = (sd - e.shield) / shieldx
            took = e.shield
            e.shield = 0.0
            self.ring(e.x, e.y, e.r, e.r + 18, BLUE, 0.3, 3, 8)
        if e.armor and not pierce:
            dmg = max(dmg * 0.25, dmg - e.armor)
        e.hp -= dmg
        e.sreg = 0.0
        if src is not None:
            src.dealt += dmg
        if P is not None:
            P.dealt += dmg
            if pay:
                self.hit_cash(e, P, took + dmg, quiet)
        if not quiet:
            e.flash = 0.08
            if m["burn"]:
                b = dmg * m["burn"] / 2.0
                if b > e.burn or e.burn_t <= 0:
                    e.burn = b
                    e.burn_p = P
                e.burn_t = 2.0
            if not self.numbers:
                pass
            elif crit:
                self.text(e.x, e.y, "%d!" % dmg, GOLD, 22, 0.7, e.r * 2 + 10)
            elif dmg >= 20 and (self.fx or self.net) and self.frnd.random() < 0.6:
                self.text(e.x + self.frnd.uniform(-6, 6), e.y, "%d" % dmg, WHITE, 16, 0.55, e.r * 2 + 8)
        if e.hp <= 0:
            self.kill(e, src, P)

    def hit_cash(self, e, P, took, quiet):
        """HIT CASH: enemies pay when you HIT them, not when they die.  Every hit pays its owner $1 to $5:
        the bigger the bite it takes out of that enemy's health, the more.  A scratch is $1, most of its health is $5."""
        f = took / (e.max + e.smax)
        if quiet:
            # beams, auras, fields and other steady damage: every chunk of health they melt counts as one $1 hit
            e.tick += f / (HIT_TICK_BOSS if e.boss else HIT_TICK)
            if e.tick < 1.0:
                return
            n = int(e.tick)
            e.tick -= n
            pay = min(n, HIT_MAX)
        else:
            pay = HIT_MAX
            for i, lim in enumerate(HIT_STEPS):
                if f < lim:
                    pay = i + 1
                    break
        got = pay * (1 + P.mods["bounty"]) + P.cfrac
        whole = int(got)
        P.cfrac = got - whole
        P.cash += whole
        self.stats["earned"] += whole
        self.stats["hitcash"] += whole
        if pay >= HIT_MAX and not quiet and self.numbers and (self.fx or self.net) and self.frnd.random() < 0.5:
            self.text(e.x + self.frnd.uniform(-8, 8), e.y, "+%d" % whole, GOLD, 15, 0.6, e.r * 2 + 22)

    def roll(self, dmg, P):
        c = P.mods["crit"] if P is not None else 0
        if c and self.rnd.random() < c:
            return dmg * 2, True
        return dmg, False

    def kill(self, e, src=None, P=None):
        e.dead = True
        if e.block is not None:
            if e in e.block.block:
                e.block.block.remove(e)
            e.block = None
        self.stats["kills"] += 1
        if src is not None:
            src.kills += 1
            P = src.owner
        # (no cash for the kill itself: enemies pay per HIT, see hit_cash)
        if P is not None:
            P.kills += 1
        self.burst(e.x, e.y, e.col, 6 + e.r // 2, 140, 0.5, 3, e.r)
        self.sfx("pop", 0.6)
        if self.fx:
            self.add_corpse(e)          # its body falls over (only for looks)
        if self.net:
            self.fxlog.append(["c", e.id])
        if e.kind == "splitter":
            for i in range(3):
                self.spawn("mini", e.pi, max(0.0, e.d - i * 14), 0, e.hm)
        if e.boss:
            self.stats["bosses"] += 1
            self.shake = max(self.shake, 1.0)
            for i in range(4):
                self.ring(e.x, e.y, 10, 90 + i * 50, e.col, 0.5 + i * 0.15, 4)
            self.burst(e.x, e.y, e.col, 60, 320, 1.0, 4, 30)
            self.burst(e.x, e.y, WHITE, 30, 220, 0.8, 3, 30)
            self.say(e.name + " DESTROYED", GOLD, 3)
            self.sfx("strike")
            if e.ai == "queen":
                for i in range(2):
                    self.spawn("elite", e.pi, max(0.0, e.d - 20 - i * 30), 0, self.hm() * 0.5)
            if self.boss is e:
                self.boss = None

    def pick(self, t, rng, skip=None):
        best = None
        bv = 0.0
        r2 = rng * rng
        mode = t.mode
        x, y = t.x, t.y
        for e in self.enemies:
            if e.dead or e.hidden or e is skip:
                continue
            dx = e.x - x
            dy = e.y - y
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            if mode == 0:
                v = -e.rem
            elif mode == 1:
                v = e.rem
            elif mode == 2:
                v = e.max + e.smax - e.rem * 0.001
            else:
                v = -d2
            if best is None or v > bv:
                best = e
                bv = v
        return best

    def explode(self, x, y, rad, dmg, src, burn=0, stun=0.0, col=ORANGE, fear=0.0, P=None):
        own = src.owner if src is not None else P
        rad *= 1 + (own.mods["splash"] if own is not None else 0)
        for e in list(self.enemies):
            if e.dead:
                continue
            d = math.hypot(e.x - x, e.y - y)
            if d <= rad + e.r:
                dd, cr = self.roll(dmg * (1 - 0.5 * min(1.0, d / rad)), own)
                if stun and not e.boss:
                    e.freeze = max(e.freeze, stun)
                if fear and not e.boss and e.fcd <= 0:
                    e.fear = fear
                    e.fcd = fear + 6.0          # nothing stays scared forever
                self.hurt(e, dd, src, crit=cr, P=P)
        if burn:
            self.fields.append([x, y, rad, dmg * 0.12, 3.0, src, ORANGE, own])
        self.ring(x, y, 8, rad, col, 0.35, 4)
        self.burst(x, y, col, 14, 200, 0.5, 3, 8)
        self.burst(x, y, WHITE, 5, 120, 0.3, 3, 8)
        self.sfx("boom", 0.7 if rad < 80 else 1.0)
        self.shake = max(self.shake, 0.15 if rad < 80 else 0.35)

    # ------------------------------------------------------------ the main step
    def update(self, dt):
        self.time += dt
        self.upd_fx(dt)
        if self.phase == "over":
            return
        n = len(self.players)
        if self.phase == "cards":
            if n > 1:
                self.card_t -= dt
                if self.card_t <= 0:
                    for P in self.players:
                        if P.offer:
                            self.pick_card(P, self.rnd.randrange(3))
                            if self.phase != "cards":
                                break
            return
        self.playtime += dt
        if self.plans:
            self.upd_plans()
        if self.phase == "build" and n > 1:
            # with friends nobody readies up: the next wave just starts a moment after the last one ended
            self.build_t += dt
            if self.build_t >= MP_WAVE_DELAY:
                self.start_wave()
        if self.phase == "wave":
            self.wt += dt
            q = self.queue
            while self.qi < len(q) and q[self.qi][0] <= self.wt:
                ev = q[self.qi]
                self.spawn(ev[1], ev[2], 0.0, ev[3], ev[4] if len(ev) > 4 else None)
                self.qi += 1
            for P in self.players:
                if P.acd[0] > 0:
                    P.acd[0] -= dt
                if P.acd[1] > 0:
                    P.acd[1] -= dt
                if P.cash >= STONKS_GOAL:
                    self.flags.add("stonks")
        for e in self.enemies:
            if not e.dead:
                self.upd_enemy(e, dt)
        for t in self.towers:
            self.upd_tower(t, dt)
        if self.goons:
            self.upd_goons(dt)
        if self.shots:
            self.upd_shots(dt)
        if self.fields:
            for f in self.fields:
                f[4] -= dt
                r2 = f[2] * f[2]
                for e in self.enemies:
                    if not e.dead and (e.x - f[0]) ** 2 + (e.y - f[1]) ** 2 <= r2:
                        self.hurt(e, f[3] * dt, f[5], True, True, P=f[7])
                if self.fx and self.frnd.random() < dt * 14:
                    a = self.frnd.uniform(0, TAU)
                    rr = self.frnd.uniform(0, f[2])
                    self.parts.append([f[0] + math.cos(a) * rr, f[1] + math.sin(a) * rr, 2.0, 0, 0, 70, 0.5, 0.5, f[6], 3])
            self.fields = [f for f in self.fields if f[4] > 0]
        if self.casts:
            self.upd_casts(dt)
        if self.hp <= 0 and self.phase != "over":
            self.hp = 0
            self.phase = "over"
            self.result = "lose"
            self.say("CORE DESTROYED", RED, 4)
            self.sfx("lose")
            self.shake = 1.0
            self.burst(self.core[0], self.core[1], RED, 70, 340, 1.2, 4, 30)
            return
        self.enemies = [e for e in self.enemies if not e.dead]
        if self.phase == "wave" and self.qi >= len(self.queue) and not self.enemies:
            self.wave_clear()

    # ------------------------------------------------------------ enemies
    def upd_enemy(self, e, dt):
        e.t += dt
        if e.flash > 0:
            e.flash -= dt
        if e.dr > 0:
            e.dr -= dt
        if e.vuln > 0:
            e.vuln -= dt
        if e.lift > 0:
            e.lift -= dt
        if e.fcd > 0:
            e.fcd -= dt
        if e.act > 0:
            e.act -= dt
        if e.chill > 0:
            e.chill = max(0.0, e.chill - dt * 0.12)
        if e.burn_t > 0:
            e.burn_t -= dt
            self.hurt(e, e.burn * dt, None, True, True, P=e.burn_p, pay=False)
            if e.dead:
                return
        k = e.ai
        if k == "shield" and e.shield < e.smax:
            e.sreg += dt
            if e.sreg > 4.0:
                e.shield = min(e.smax, e.shield + e.smax * 0.2 * dt)
        elif k == "healer":
            e.a1 -= dt
            if e.a1 <= 0:
                e.a1 = 1.0
                done = False
                for o in self.enemies:
                    if o is not e and not o.dead and o.hp < o.max and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 < 9500:
                        o.hp = min(o.max, o.hp + o.max * (0.012 if o.boss else 0.06))
                        done = True
                if done:
                    self.ring(e.x, e.y, 8, 96, MINT, 0.4, 2)
        elif k == "blinker":
            e.a1 -= dt
            if e.a1 <= 0 and e.freeze <= 0:
                e.a1 = 4.0
                self.ring(e.x, e.y, 4, 26, MAGENTA, 0.3, 2)
                if e.block is not None:
                    if e in e.block.block:
                        e.block.block.remove(e)
                    e.block = None
                e.d = min(self.paths[e.pi].length - 30, e.d + 110)
        elif k == "phantom":
            hid = (e.t % 4.2) > 2.5
            if hid:
                for b in self.reveals:
                    if (b.x - e.x) ** 2 + (b.y - e.y) ** 2 <= b.rng * b.rng:
                        hid = False
                        break
            e.hidden = hid
        elif k == "elite":
            e.a1 -= dt
            if e.a1 <= 0:
                e.a1 = 0.5
                for o in self.enemies:
                    if o is not e and not o.boss and (o.x - e.x) ** 2 + (o.y - e.y) ** 2 < 10000:
                        o.haste = 0.7
                        o.hmul = 1.25
        elif e.boss:
            self.boss_ai(e, dt)
        back = False
        if e.freeze > 0:
            e.freeze -= dt
            sp = 0.0
        else:
            sp = e.spd
            if e.slow_t > 0:
                e.slow_t -= dt
                sp *= 1 - e.slow
            else:
                e.slow = 0.0
            if e.haste > 0:
                e.haste -= dt
                sp *= e.hmul
            if self.gm["gravity"] and e.rem < 190:
                sp *= 1 - self.gm["gravity"] * (0.5 if e.boss else 1)
            if e.fear > 0:
                e.fear -= dt
                back = True
        # path towers in the way
        bt = e.block
        if bt is not None:
            if bt.down or back:
                if e in bt.block:
                    bt.block.remove(e)
                e.block = None
            else:
                if e.freeze <= 0:
                    self.pt_hit(bt, e, e.atk * dt)
                    if e.act <= 0:
                        e.act = ACT_TIME        # swing (again)
                sp = 0.0
        elif self.ptowers and not back and sp > 0:
            for t in self.ptowers:
                if t.down:
                    continue
                dd = t.pd.get(e.pi)
                if dd is None:
                    continue
                gap = dd - e.d
                if -8 < gap < e.r + 13:
                    if e.boss:
                        self.pt_hit(t, e, e.atk * dt)
                        if e.act <= 0:
                            e.act = ACT_TIME
                        sp *= 0.6
                    elif len(t.block) < t.L["block"]:
                        e.block = t
                        t.block.append(e)
                        sp = 0.0
                    elif "thorns" in t.L:
                        self.pt_thorns(t, e, dt * 0.5)
                    break
        e.cur = sp
        if back:
            e.d = max(0.0, e.d - sp * dt)
        else:
            e.d += sp * dt
        p = self.paths[e.pi]
        if e.d >= p.length:
            self.leak(e)
            return
        e.x, e.y, seg = p.at(e.d)
        if not p.flat:
            e.z = p.zat(e.d)
        e.ang = p.angs[seg] + (math.pi if back else 0)
        e.rem = p.length - e.d

    def pt_thorns(self, t, e, dt):
        th = t.L.get("thorns")
        if th and t.stun <= 0:
            self.hurt(e, th * 3.0 * (2 if t.tp == "spiked" else 1) * (1 + t.owner.mods["dmg"]) * dt, t, True, True)

    def pt_hit(self, t, e, dmg):
        """an enemy hits a path tower"""
        if t.tp == "laststand" and t.hp < t.maxhp * 0.3:
            dmg *= 0.7
        t.hp -= dmg
        t.hit = 0.15
        self.pt_thorns(t, e, dmg / max(1.0, e.atk))
        if t.hp <= 0 and not t.down:
            self.pt_fall(t)

    def pt_fall(self, t):
        t.hp = 0.0
        t.down = True
        t.down_t = 0.0
        for e in t.block:
            e.block = None
        t.block = []
        self.stats["ptfalls"] += 1
        if self.stats["ptfalls"] >= BRICK_GOAL:
            self.flags.add("brick")
        L = t.L
        big = t.tp == "chainr"
        self.text(t.x, t.y, "DOWN!", RED, 22, 1.2, 40)
        self.sfx("crash", 0.8)
        self.explode(t.x, t.y, L["brad"] * (1.35 if big else 1.0), L["boom"] * (1 + t.owner.mods["dmg"]), t, 0, 1.5 if big else 0.0, t.owner.tcol(t.kind))
        self.ring(t.x, t.y, 10, L["brad"] * 1.3, WHITE, 0.5, 3)

    def leak(self, e):
        e.dead = True
        self.stats["leaks"] += 1
        cx, cy = self.core
        if self.aegis > 0 and not e.boss:
            self.aegis -= 1
            self.ring(cx, cy, 20, 70, BLUE, 0.4, 4, 20)
            self.text(cx, cy, "BLOCKED", BLUE, 20, 0.8, 70)
            return
        dmg = self.leak_of(e)
        self.hp -= dmg
        self.core_hit = 0.4
        self.shake = max(self.shake, 0.5)
        self.ring(cx, cy, 16, 80, RED, 0.4, 4, 4)
        self.burst(cx, cy, RED, 16, 200, 0.5, 3, 24)
        self.text(cx, cy, "-%d" % min(dmg, 999), RED, 24, 0.8, 70)
        self.sfx("leak")

    def summon(self, e, kinds):
        p = self.paths[e.pi]
        for i, k in enumerate(kinds):
            self.spawn(k, e.pi, clamp(e.d - self.rnd.uniform(e.r + 6, e.r + 70), 0, p.length - 20), 0, self.hm() * 0.8)
        self.ring(e.x, e.y, e.r, e.r + 60, e.col, 0.4, 3)

    def emp(self, towers, dur):
        for t in towers:
            d = dur * (1 - min(0.8, t.owner.mods["harden"]))
            cl = 0.0
            for mc in t.mechs:
                cl = max(cl, mc.L["cleanse"])
            d *= 1 - cl
            t.stun = max(t.stun, d)
            t.beam = False
            self.burst(t.x, t.y, PURPLE, 6, 80, 0.5, 3, 14)

    def boss_ai(self, e, dt):
        k = e.ai
        if e.freeze > 0:
            return
        e.a1 -= dt
        e.a2 -= dt
        top = e.r * 2 + 40
        if k == "overseer":
            if e.a1 <= 0:
                e.a1 = 7.5
                e.act = ACT_TIME
                self.summon(e, ["grunt", "grunt", "runner", "shield" if self.wave >= 10 else "grunt"])
                self.text(e.x, e.y, "REINFORCEMENTS", RED, 20, 1.2, top)
            if e.a2 <= 0:
                e.a2 = 15.0
                e.act = ACT_TIME
                e.smax = e.max * 0.06
                e.shield = e.smax
                self.ring(e.x, e.y, 60, e.r, BLUE, 0.5, 4, 10)
                self.text(e.x, e.y, "SHIELD WALL", BLUE, 20, 1.2, top)
        elif k == "queen":
            if e.a1 <= 0:
                e.a1 = 1.7
                e.act = ACT_TIME
                self.summon(e, ["swarm", "swarm"])
            if e.stage < 2 and e.hp < e.max * (0.66, 0.33)[e.stage]:
                e.stage += 1
                e.act = ACT_TIME
                self.summon(e, ["mini"] * 8)
                e.haste = 3.5
                e.hmul = 2.0
                self.say(e.name + " SPRINTS!", ORANGE, 2)
                self.sfx("emp")
        elif k == "titan":
            if e.a1 <= 0:
                e.a1 = 9.0
                e.act = ACT_TIME
                hit = [t for t in self.towers if (t.x - e.x) ** 2 + (t.y - e.y) ** 2 < 175 * 175]
                self.emp(hit, 3.0)
                self.ring(e.x, e.y, e.r, 175, PURPLE, 0.6, 5, 6)
                self.say("EMP PULSE!", PURPLE, 1.6)
                self.sfx("emp")
                self.shake = max(self.shake, 0.4)
            if e.a2 <= 0 and e.hp < e.max * 0.7:
                e.a2 = 14.0
                e.act = ACT_TIME
                e.dr = 3.5
                self.text(e.x, e.y, "FORTIFIED", GREY, 20, 1.4, top)
        elif k == "architect":
            st = 0 if e.hp > e.max * 0.66 else 1 if e.hp > e.max * 0.33 else 2
            if st != e.stage:
                e.stage = st
                self.say(e.name + ": " + ("REWRITE" if st == 1 else "OVERDRIVE"), CYAN, 2.4)
                self.ring(e.x, e.y, e.r, 240, CYAN, 0.7, 5, 6)
                self.sfx("boss")
                self.shake = max(self.shake, 0.5)
            if st == 2:
                e.haste = 0.3
                e.hmul = 1.45
            if e.a1 <= 0:
                e.act = ACT_TIME
                if st == 0:
                    e.a1 = 8.0
                    self.summon(e, ["shield", "shield", "tank"])
                else:
                    e.a1 = 7.0 if st == 1 else 6.0
                    pool = [t for t in self.towers if t.stun <= 0 and t.kind not in ("harvester", "stonks")]
                    self.rnd.shuffle(pool)
                    hit = pool[:3 + st]
                    for t in hit:
                        self.bolt([(e.x, e.y, e.z + 30), ((e.x + t.x) / 2 + self.frnd.uniform(-30, 30), (e.y + t.y) / 2 + self.frnd.uniform(-30, 30), 50), (t.x, t.y, t.z + 14)], CYAN, 0.5, 3)
                    self.emp(hit, 4.0)
                    self.text(e.x, e.y, "HACK", CYAN, 22, 1.2, top)
                    self.sfx("emp")
                    if st == 2:
                        self.summon(e, ["phantom", "phantom"])
            if e.a2 <= 0 and st >= 1:
                e.a2 = 10.0
                e.act = ACT_TIME
                self.ring(e.x, e.y, 6, 50, CYAN, 0.35, 3)
                e.d = min(self.paths[e.pi].length - 60, e.d + 90)

    # ------------------------------------------------------------ towers
    def upd_tower(self, t, dt):
        t.t += dt
        if t.recoil > 0:
            t.recoil = max(0.0, t.recoil - dt * 5)
        if t.swing > 0:
            t.swing = max(0.0, t.swing - dt * 3.5)
        if t.hit > 0:
            t.hit -= dt
        if t.od > 0:
            t.od -= dt
        if t.duel > 0:
            t.duel -= dt
        k = t.kind
        if k == "commander":
            if t.act > 0:
                t.act -= dt
            elif t.acd > 0 and self.phase == "wave":
                t.acd -= dt
        if t.path and t.down:
            # a Mechanic with rebuild in reach puts it back up mid-wave
            best = None
            for mc in t.mechs:
                rv = mc.L.get("revive")
                if rv and mc.stun <= 0 and (best is None or rv < best):
                    best = rv
            if best is not None:
                t.down_t += dt
                if t.down_t >= best:
                    t.down = False
                    t.down_t = 0.0
                    t.hp = t.maxhp * 0.5
                    self.text(t.x, t.y, "REBUILT", GREEN, 20, 1.2, 40)
                    self.ring(t.x, t.y, 6, 40, GREEN, 0.4, 3)
                    self.sfx("upgrade", 0.6)
            return
        if t.stun > 0:
            t.stun -= dt
            t.beam = False
            return
        if k == "mechanic":
            t.beam = False
            if self.ptowers:
                heal = t.L["heal"] * (1.5 if t.tp == "medic" else 1.0) * dt
                r2 = t.rng * t.rng
                for p in self.ptowers:
                    if not p.down and p.hp < p.maxhp and (p.x - t.x) ** 2 + (p.y - t.y) ** 2 <= r2:
                        p.hp = min(p.maxhp, p.hp + heal)
                        t.beam = True
            return
        if k == "summoner":
            self.upd_summoner(t, dt)
            return
        if k in NOFIGHT or k == "brick":
            return
        if t.cd > 0:
            t.cd -= dt
        if not self.enemies:
            t.beam = False
            t.ramp = 0.0
            return
        L = t.L
        P = t.owner
        dk = 1 + P.mods["dmg"] + t.db
        if k == "cryo":
            t.pulse -= dt
            hit = t.pulse <= 0
            r2 = t.rng * t.rng
            sl = min(0.8, L["slow"])
            got = False
            for e in self.enemies:
                if not e.dead and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                    s2 = sl * (0.5 if e.boss else 1.0)
                    if s2 > e.slow:
                        e.slow = s2
                    e.slow_t = 0.35
                    if t.tp == "perma":
                        e.vuln = 0.4
                    got = True
                    if hit:
                        self.hurt(e, L["dmg"] * dk, t, True, True)
            if hit:
                t.pulse = self.cd_of(t, L["cd"])
                if got:
                    t.swing = 1.0
            if L.get("frz"):
                t.frz_t -= dt
                if t.frz_t <= 0 and got:
                    t.frz_t = 6.0
                    for e in self.enemies:
                        if not e.dead and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                            e.freeze = max(e.freeze, L["frz"] * (0.3 if e.boss else 1.0))
                    self.ring(t.x, t.y, 10, t.rng, WHITE, 0.45, 4, 2)
                    self.sfx("freeze", 0.6)
            return
        if k == "reactor":
            r2 = t.rng * t.rng
            d = L["aura"] * dk * dt
            for e in self.enemies:
                if not e.dead and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                    self.hurt(e, d, t, True, True)
            return
        if k == "bulwark":
            return
        if k == "guardian":
            if t.cd <= 0:
                d = L["dmg"] * dk * (2 if (t.tp == "laststand" and t.hp < t.maxhp * 0.3) else 1)
                if self.melee(t, t.rng, d, L["cleave"]):
                    t.cd = self.cd_of(t, L["cd"])
            return
        if k == "blade":
            t.ang += dt * (2.5 + 14 * t.swing)
            if t.cd <= 0:
                if self.melee(t, t.rng, L["dmg"] * dk, L["cleave"] + (2 if t.tp == "whirl" else 0)):
                    t.cd = self.cd_of(t, L["cd"])
            return
        if k == "cat":
            if t.cd <= 0:
                got = self.melee(t, t.rng, L["dmg"] * dk, L["cleave"], True)
                if got:
                    t.cd = self.cd_of(t, L["cd"])
                    for e in got:
                        if not e.dead:
                            if e.block is not None:
                                if e in e.block.block:
                                    e.block.block.remove(e)
                                e.block = None
                            e.d = max(0.0, e.d - L["kb"] * (0.25 if e.boss else 1.0))
                    t.ang = math.atan2(got[0].y - t.y, got[0].x - t.x)
                    if self.frnd.random() < 0.3:
                        self.text(t.x, t.y, self.frnd.choice(("asdfgh", "jkl;", "qwerty", "meow", ";lkj", "zxcvb")), P.tcol("cat"), 16, 0.8, 34)
                        self.sfx("meow", 0.4)
            return
        if k == "graviton":
            if t.cd <= 0:
                r2 = t.rng * t.rng
                pull = L["pull"] * (1.3 if t.tp == "horizon" else 1.0)
                got = False
                for e in list(self.enemies):
                    if not e.dead and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                        got = True
                        if e.boss:
                            e.slow = max(e.slow, 0.5)
                            e.slow_t = 1.5
                        else:
                            if e.block is not None:
                                if e in e.block.block:
                                    e.block.block.remove(e)
                                e.block = None
                            e.d = max(0.0, e.d - pull)
                        self.hurt(e, L["dmg"] * dk, t, True)
                if got:
                    t.cd = self.cd_of(t, L["cd"])
                    t.swing = 1.0
                    self.ring(t.x, t.y, t.rng, 8, P.tcol(k), 0.45, 4, 2)
                    self.sfx("emp", 0.5)
            return
        if k == "prism":
            tg = t.tg
            if tg is None or tg.dead or tg.hidden or (tg.x - t.x) ** 2 + (tg.y - t.y) ** 2 > t.rng * t.rng:
                tg = t.tg = self.pick(t, t.rng)
                t.ramp = t.ramp * 0.5 if L.get("split") else 0.0
            if tg is None:
                t.beam = False
                t.ramp = 0.0
                return
            t.beam = True
            t.ang = math.atan2(tg.y - t.y, tg.x - t.x)
            t.ramp = min(1.0, t.ramp + dt / (1.0 if t.tp == "focus" else 2.0))
            dps = L["dps"] * dk * (1 + 2 * t.ramp) * L["dps"] / self.cd_of(t, L["dps"])
            self.hurt(tg, dps * dt, t, True, True)
            if L.get("split"):
                t2 = t.tg2
                if t2 is None or t2.dead or t2.hidden or t2 is tg or (t2.x - t.x) ** 2 + (t2.y - t.y) ** 2 > t.rng * t.rng:
                    t2 = t.tg2 = self.pick(t, t.rng, tg)
                if t2 is not None:
                    self.hurt(t2, dps * 0.7 * dt, t, True, True)
            else:
                t.tg2 = None
            if self.fx and self.frnd.random() < dt * 20:
                self.parts.append([tg.x, tg.y, tg.z + tg.r, self.frnd.uniform(-90, 90), self.frnd.uniform(-90, 90), 60, 0.3, 0.3, MAGENTA, 2])
            return
        if k == "snow":
            tg = t.tg
            if tg is None or tg.dead or tg.hidden or (tg.x - t.x) ** 2 + (tg.y - t.y) ** 2 > t.rng * t.rng:
                tg = t.tg = self.pick(t, t.rng)
            if tg is None:
                t.beam = False
                return
            t.beam = True
            want = math.atan2(tg.y - t.y, tg.x - t.x)
            da = (want - t.ang + math.pi) % TAU - math.pi
            t.ang += clamp(da, -dt * 6, dt * 6)
            ca, sa = math.cos(t.ang), math.sin(t.ang)
            r2 = t.rng * t.rng
            d = L["dps"] * dk * dt * L["dps"] / self.cd_of(t, L["dps"])
            for e in self.enemies:
                if e.dead:
                    continue
                px, py = e.x - t.x, e.y - t.y
                dd = px * px + py * py
                if dd > r2:
                    continue
                if dd > 400 and (px * ca + py * sa) < math.sqrt(dd) * 0.83:
                    continue
                self.hurt(e, d, t, True, True)
                e.slow = max(e.slow, 0.3 * (0.5 if e.boss else 1.0))
                e.slow_t = 0.4
                e.chill += (L["chill"] + 0.12) * dt
                if e.chill >= 1.0:
                    e.chill = -1.5              # thawed enemies take a lot longer to freeze again
                    e.freeze = max(e.freeze, 0.35 if e.boss else 1.2)
                    self.ring(e.x, e.y, 4, e.r + 14, WHITE, 0.3, 2, 6)
            if self.fx and self.frnd.random() < dt * 30:
                a = t.ang + self.frnd.uniform(-0.5, 0.5)
                v = self.frnd.uniform(160, 260)
                self.parts.append([t.x + ca * 16, t.y + sa * 16, t.z + 16, math.cos(a) * v, math.sin(a) * v, 20, 0.45, 0.45, SNOW_W, 3])
            return
        # ---- towers that aim and shoot
        if k == "sentinel":
            if t.mcd > 0:
                t.mcd -= dt
            if t.mcd <= 0 and self.melee(t, t.mrng, L["mdmg"] * dk, L["cleave"]):
                t.mcd = self.cd_of(t, L["mcd"])
                if t.tp == "duelist":
                    t.duel = 2.0
        tg = t.tg
        if tg is not None and (tg.dead or tg.hidden or (tg.x - t.x) ** 2 + (tg.y - t.y) ** 2 > t.rng * t.rng):
            tg = t.tg = None
        if t.cd <= 0 or tg is None:
            tg = t.tg = self.pick(t, t.rng)
        if tg is None:
            return
        want = math.atan2(tg.y - t.y, tg.x - t.x)
        da = (want - t.ang + math.pi) % TAU - math.pi
        t.ang += clamp(da, -dt * 14, dt * 14)
        if t.cd > 0:
            return
        t.ang = want
        t.cd = self.cd_of(t, L["cd"])
        t.recoil = 1.0
        ca, sa = math.cos(want), math.sin(want)
        col = P.tcol(k)
        zz = t.z + 14
        if k == "blaster" or k == "sentinel":
            offs = [-5, 5] if L.get("twin") else [0]
            if t.tp == "triple":
                t.shots += 1
                if t.shots % 3 == 0:
                    offs.append(0 if L.get("twin") else 4)
            for o in offs:
                s = Shot("bullet", t.x + ca * 16 - sa * o, t.y + sa * 16 + ca * o, L["dmg"] * dk, t, col, zz)
                s.tg = tg
                s.vx, s.vy = ca * 640, sa * 640
                self.add_shot(s)
            self.sfx("shoot", 0.5)
        elif k == "duck":
            first = True
            skip = None
            for _ in range(L.get("n", 1)):
                e2 = tg if first else self.pick(t, t.rng, skip)
                first = False
                if e2 is None:
                    break
                skip = e2
                s = Shot("bubble", t.x + ca * 14, t.y + sa * 14, L["dmg"] * dk, t, (170, 230, 255), zz + 4)
                s.tg = e2
                s.spd = 330.0
                s.lift = L["lift"]
                s.life = 3.0
                self.add_shot(s)
            self.sfx("quack", 0.5)
        elif k == "scatter":
            for i in range(L["n"]):
                a = want + self.rnd.uniform(-0.27, 0.27)
                s = Shot("pellet", t.x + ca * 14, t.y + sa * 14, L["dmg"] * dk, t, col, zz)
                sp = self.rnd.uniform(430, 520)
                s.vx, s.vy = math.cos(a) * sp, math.sin(a) * sp
                s.life = t.rng * 1.25 / sp
                s.pierce = L["pierce"]
                s.hit = set()
                if t.tp == "dragon":
                    s.burn = 1
                self.add_shot(s)
            self.sfx("scatter", 0.6)
        elif k == "rail":
            reach = t.rng * 1.15
            x1, y1 = t.x + ca * reach, t.y + sa * reach
            base = L["dmg"] * dk
            if t.tp == "hollow" and tg.hp > tg.max * 0.8:
                base *= 1.4
            dmg, cr = self.roll(base, P)
            z1 = 10.0
            if L.get("line"):
                for e in list(self.enemies):
                    if e.dead or e is tg:
                        continue
                    px, py = e.x - t.x, e.y - t.y
                    along = px * ca + py * sa
                    if 0 < along < reach and abs(py * ca - px * sa) < e.r + 7:
                        self.hurt(e, dmg * 0.5, t, True)
            else:
                x1, y1, z1 = tg.x, tg.y, tg.z + tg.r
            self.burst(tg.x, tg.y, GOLD, 6, 160, 0.3, 3, tg.r)
            self.hurt(tg, dmg, t, True, crit=cr)
            self.bolt([(t.x + ca * 18, t.y + sa * 18, zz), (x1, y1, z1)], col, 0.22, 4 if L.get("line") else 3)
            self.sfx("rail", 0.7)
        elif k == "tesla":
            cur = tg
            dmg = L["dmg"] * dk
            hitset = {tg}
            pts = [(t.x, t.y, t.z + 30 + t.lv * 5)]
            jump = 115 * (1 + P.mods["splash"])
            fall = 1.0 if t.tp == "overvolt" else 0.88
            for _ in range(L["chain"] + (2 if t.tp == "overvolt" else 0)):
                pts.append((cur.x + self.frnd.uniform(-4, 4), cur.y + self.frnd.uniform(-4, 4), cur.z + cur.r))
                d2, cr = self.roll(dmg, P)
                self.hurt(cur, d2, t, False, False, 2.0, cr)
                dmg *= fall
                nxt = None
                bd = jump * jump
                for e in self.enemies:
                    if e.dead or e.hidden or e in hitset:
                        continue
                    dd = (e.x - cur.x) ** 2 + (e.y - cur.y) ** 2
                    if dd < bd:
                        bd = dd
                        nxt = e
                if nxt is None:
                    break
                hitset.add(nxt)
                cur = nxt
            jag = [pts[0]]
            fr = self.frnd
            for i in range(1, len(pts)):
                a, b = pts[i - 1], pts[i]
                jag.append(((a[0] + b[0]) / 2 + fr.uniform(-10, 10), (a[1] + b[1]) / 2 + fr.uniform(-10, 10), (a[2] + b[2]) / 2 + fr.uniform(-4, 8)))
                jag.append(b)
            self.bolt(jag, col, 0.16, 3)
            self.sfx("zap", 0.6)
        elif k == "hydra":
            n = L["n"] + (1 if t.tp == "swarm" else 0)
            pool = [e for e in self.enemies if not e.dead and not e.hidden and e is not tg and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= t.rng * t.rng]
            pool.sort(key=lambda e: e.rem)
            tgs = [tg] + pool[:n - 1]
            for i in range(n):
                e2 = tgs[i % len(tgs)]
                s = Shot("rocket", t.x + ca * 8, t.y + sa * 8, L["dmg"] * dk, t, col, zz + 6)
                s.tg = e2
                s.spd = 380.0
                s.splash = L["splash"]
                s.life = 3.0
                a = want + (i - (n - 1) / 2.0) * 0.5
                s.vx, s.vy = math.cos(a) * 380, math.sin(a) * 380
                s.tx, s.ty = e2.x, e2.y
                self.add_shot(s)
            self.sfx("mortar", 0.5)
        elif k in ("mortar", "annihilator", "toaster", "pumpkin"):
            n = L.get("n", 1)
            tgs = [tg]
            if n > 1:
                pool = [e for e in self.enemies if not e.dead and not e.hidden and e is not tg and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= t.rng * t.rng]
                self.rnd.shuffle(pool)
                tgs += pool[:n - 1]
            for i in range(n):
                e2 = tgs[i % len(tgs)]
                dist = math.hypot(e2.x - t.x, e2.y - t.y)
                T = 0.5 + dist / 650.0
                p = self.paths[e2.pi]
                tx, ty, _ = p.at(min(p.length, e2.d + e2.cur * T))
                if i >= len(tgs):
                    tx += self.rnd.uniform(-22, 22)
                    ty += self.rnd.uniform(-22, 22)
                s = Shot("shell", t.x, t.y, L["dmg"] * dk, t, col, zz + 8)
                s.tx, s.ty, s.T = tx, ty, T + i * 0.08
                s.splash = L["splash"]
                s.burn = L.get("burn", 0) or (1 if t.tp == "after" else 0)
                s.stun = L.get("stun", 0.0)
                s.fear = L.get("fear", 0.0)
                s.big = k == "annihilator"
                s.sub = k if k in ("toaster", "pumpkin") else ("cluster" if t.tp == "cluster" else "")
                self.add_shot(s)
            self.sfx("ding" if k == "toaster" else "mortar", 0.5 if k == "toaster" else 1.0 if k == "annihilator" else 0.6)

    # ------------------------------------------------------------ the Summoner and its goons
    def goon_road(self):
        """the road a new goon should take: the one whose enemy is closest to the core (or the one the next enemy comes in on).
        -> road number, or None when there is nothing to fight"""
        best = None
        for e in self.enemies:
            if not e.dead and (best is None or e.rem < best.rem or (e.rem == best.rem and e.pi < best.pi)):
                best = e
        if best is not None:
            return best.pi
        if self.qi < len(self.queue):
            return self.queue[self.qi][2]
        return None

    def goon_hp(self, t):
        """how much health a new goon of this Summoner gets: damage perks and cards make goons tougher"""
        return t.L["ghp"] * (1 + t.owner.mods["dmg"] + t.db + (t.mb.get("hp", 0) if t.mb else 0))

    def upd_summoner(self, t, dt):
        """every few seconds, while a wave is running and there is something to fight, a goon walks out of the core"""
        if self.phase != "wave":
            return
        if t.cd > 0:
            t.cd -= dt
            if t.cd > 0:
                return
        L = t.L
        n = 0
        for g in self.goons:
            if g.tw is t:
                n += 1
        if n >= L["cap"]:
            return
        pi = self.goon_road()
        if pi is None:
            return
        t.cd += self.cd_of(t, L["cd"])
        P = t.owner
        p = self.paths[pi]
        g = Goon(self.nid(), t, P, pi, p.length, self.goon_hp(t), L["gspd"], t.lv)
        self.place_goon(g)
        self.goons.append(g)
        t.swing = 1.0
        self.ring(g.x, g.y, 6, 30, P.tcol("summoner"), 0.3, 2, 2)

    def upd_goons(self, dt):
        for g in self.goons:
            g.t += dt
            if g.flash > 0:
                g.flash -= dt
            g.d -= g.spd * dt
            if g.d <= 0:
                # it walked the whole road: out through the gate
                g.d = 0.0
                g.dead = True
                self.place_goon(g)
                self.burst(g.x, g.y, g.owner.tcol("summoner"), 5, 80, 0.4, 2, g.r)
                continue
            self.place_goon(g)
            # the nearest enemy it touches (on its own road: by how far along they are; on a road that crosses or joins: by where they stand)
            best = None
            bg = 0.0
            gr = g.r
            for e in self.enemies:
                if e.dead or e.hidden:
                    continue
                lim = gr + e.r
                if e.pi == g.pi:
                    gap = e.d - g.d
                    if gap < 0:
                        gap = -gap
                    if gap > lim:
                        continue
                else:
                    dx, dy = e.x - g.x, e.y - g.y
                    if dx > lim or dx < -lim or dy > lim or dy < -lim or abs(e.z - g.z) > 12.0:
                        continue
                    gap = math.sqrt(dx * dx + dy * dy)
                    if gap > lim:
                        continue
                if best is None or gap < bg or (gap == bg and e.id < best.id):
                    best, bg = e, gap
            if best is not None:
                self.goon_hit(g, best)
        self.goons = [g for g in self.goons if not g.dead]

    def goon_hit(self, g, e):
        """a goon and an enemy meet: they trade health.  Each loses what the weaker one had; the weaker one is destroyed."""
        tw = g.tw if (g.tw is not None and g.tw in self.towers) else None
        need = e.hp + e.shield
        amt = min(g.hp, need)
        self.hurt(e, amt, tw, True, P=g.owner)
        g.hp -= amt
        g.flash = 0.1
        if not e.dead and amt >= need and e.dr <= 0 and e.hp + e.shield < 1e-6:
            self.kill(e, tw, g.owner)       # (rounding left it a hair of health)
        self.burst((g.x + e.x) / 2, (g.y + e.y) / 2, WHITE, 3, 90, 0.25, 2, g.r)
        if g.hp <= 1e-6:
            g.hp = 0.0
            g.dead = True
            self.burst(g.x, g.y, g.owner.tcol("summoner"), 7, 120, 0.45, 3, g.r)
            self.sfx("pop", 0.4)
            if self.fx:
                self.add_corpse(g, True)

    def add_shot(self, s):
        self.shots.append(s)
        if self.net:
            self.fxlog.append(["h", s.kind, int(s.x), int(s.y), int(s.z), s.tg.id if s.tg is not None else 0, int(s.tx), int(s.ty), round(s.T, 2), list(s.col),
                               int(s.vx), int(s.vy), round(s.life, 2), 1 if s.big else 0, s.sub, int(s.spd)])

    def melee(self, t, rng, dmg, cleave, give=False):
        got = [e for e in self.enemies if not e.dead and not e.hidden and (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= (rng + e.r * 0.6) ** 2]
        if not got:
            return False
        if len(got) > cleave:
            got.sort(key=lambda e: e.rem)
            got = got[:cleave]
        for e in got:
            d2, cr = self.roll(dmg, t.owner)
            self.hurt(e, d2, t, crit=cr)
            self.burst(e.x, e.y, WHITE, 3, 90, 0.25, 2, e.r)
        t.swing = 1.0
        self.sfx("slash", 0.45)
        return got if give else True

    def upd_shots(self, dt):
        for s in self.shots:
            k = s.kind
            if k == "shell":
                s.t += dt
                if s.t >= s.T:
                    s.life = -1
                    self.explode(s.tx, s.ty, s.splash, s.dmg, s.src, s.burn, s.stun, s.col, s.fear)
                    if s.big:
                        self.shake = max(self.shake, 0.6)
                        self.ring(s.tx, s.ty, 10, s.splash * 1.5, WHITE, 0.5, 3)
                    if s.sub == "cluster":
                        for i in range(3):
                            a = self.rnd.uniform(0, TAU)
                            rr = s.splash * 0.8
                            self.explode(s.tx + math.cos(a) * rr, s.ty + math.sin(a) * rr, s.splash * 0.55, s.dmg * 0.3, s.src, 0, 0.0, s.col)
                    elif s.sub == "pumpkin":
                        self.burst(s.tx, s.ty, PUMP_O, 16, 180, 0.6, 4, 8)
                continue
            s.life -= dt
            if s.life <= 0:
                if k == "rocket":
                    self.explode(s.x, s.y, s.splash, s.dmg, s.src, 0, 0.0, s.col)
                continue
            if k in ("bullet", "bubble", "rocket"):
                tg = s.tg
                if tg is not None and not tg.dead:
                    dx, dy = tg.x - s.x, tg.y - s.y
                    d = math.hypot(dx, dy) or 0.01
                    step = s.spd * dt
                    if d <= step + tg.r:
                        s.life = -1
                        if k == "rocket":
                            self.explode(tg.x, tg.y, s.splash, s.dmg, s.src, 0, 0.0, s.col)
                        else:
                            dmg, cr = self.roll(s.dmg, s.src.owner)
                            if k == "bubble" and not tg.boss:
                                tg.freeze = max(tg.freeze, s.lift)
                                tg.lift = max(tg.lift, s.lift)
                                self.sfx("bubble", 0.4)
                            self.hurt(tg, dmg, s.src, crit=cr)
                        continue
                    if k == "rocket":
                        # rockets curve towards their target
                        wx, wy = dx / d * s.spd, dy / d * s.spd
                        f = min(1.0, dt * 6)
                        s.vx += (wx - s.vx) * f
                        s.vy += (wy - s.vy) * f
                    else:
                        s.vx, s.vy = dx / d * s.spd, dy / d * s.spd
                    s.x += s.vx * dt
                    s.y += s.vy * dt
                    s.z += (tg.z + tg.r - s.z) * min(1.0, step / d)
                    continue
                if k == "rocket":
                    # the target is gone: find another one nearby or blow up where it is
                    best, bd = None, 150 * 150
                    for e in self.enemies:
                        if not e.dead and not e.hidden:
                            dd = (e.x - s.x) ** 2 + (e.y - s.y) ** 2
                            if dd < bd:
                                best, bd = e, dd
                    if best is None:
                        s.life = -1
                        self.explode(s.x, s.y, s.splash, s.dmg, s.src, 0, 0.0, s.col)
                    else:
                        s.tg = best
                    continue
                if k == "bubble":
                    s.life = -1
                    continue
                s.tg = None
                s.kind = "pellet"
                s.hit = set()
                s.life = min(s.life, 0.35)
            s.x += s.vx * dt
            s.y += s.vy * dt
            for e in self.enemies:
                if e.dead or e in s.hit:
                    continue
                rr = e.r + 4
                if abs(e.x - s.x) < rr and abs(e.y - s.y) < rr:
                    dmg, cr = self.roll(s.dmg, s.src.owner)
                    self.hurt(e, dmg, s.src, crit=cr)
                    if s.burn and not e.dead:
                        b = s.dmg * 0.15
                        if b > e.burn or e.burn_t <= 0:
                            e.burn = b
                            e.burn_p = s.src.owner
                        e.burn_t = 2.0
                    s.hit.add(e)
                    s.pierce -= 1
                    if s.pierce < 0:
                        s.life = -1
                        break
        self.shots = [s for s in self.shots if s.life > 0]

    # ------------------------------------------------------------ ability perks
    def upd_casts(self, dt):
        for c in self.casts:
            c["t"] += dt
            k = c["kind"]
            t = c["t"]
            x, y, rad, P = c["x"], c["y"], c["rad"], c["P"]
            if k == "sword":
                if not c["hit"] and t >= 0.45:
                    c["hit"] = True
                    dmg = 110 * self.hm()
                    for e in list(self.enemies):
                        if not e.dead and math.hypot(e.x - x, e.y - y) <= rad + e.r:
                            self.hurt(e, dmg * (2.5 if e.boss else 1.0), None, True, crit=True, P=P)
                            if not e.boss:
                                e.freeze = max(e.freeze, 0.6)
                    self.ring(x, y, 10, rad, GOLD, 0.5, 6)
                    self.ring(x, y, 10, rad * 1.4, WHITE, 0.7, 2)
                    self.burst(x, y, GOLD, 40, 300, 0.8, 4, 6)
                    self.shake = max(self.shake, 0.8)
                    self.sfx("strike")
                c["dead"] = t > 2.0
            elif k == "cryobomb":
                if not c["hit"] and t >= 0.3:
                    c["hit"] = True
                    for e in self.enemies:
                        if not e.dead and math.hypot(e.x - x, e.y - y) <= rad + e.r:
                            e.freeze = max(e.freeze, 1.0 if e.boss else 3.0)
                    self.ring(x, y, 10, rad, BLUE, 0.6, 6)
                    self.burst(x, y, WHITE, 40, 260, 0.9, 3, 6)
                    self.sfx("freeze")
                c["dead"] = t > 1.0
            elif k == "napalm":
                if not c["hit"] and t >= 0.35:
                    c["hit"] = True
                    self.fields.append([x, y, rad, 16 * self.hm(), 6.0, None, ORANGE, P])
                    self.ring(x, y, 10, rad, ORANGE, 0.5, 5)
                    self.burst(x, y, ORANGE, 40, 240, 0.8, 4, 6)
                    self.sfx("boom")
                    self.shake = max(self.shake, 0.4)
                c["dead"] = t > 0.9
            elif k == "blackhole":
                if 0.25 < t < 3.25:
                    if not c["hit"]:
                        c["hit"] = True
                        self.sfx("emp")
                    for e in self.enemies:
                        if not e.dead and math.hypot(e.x - x, e.y - y) <= rad + e.r:
                            if e.boss:
                                e.slow = max(e.slow, 0.6)
                                e.slow_t = 0.2
                            else:
                                if e.block is not None:
                                    if e in e.block.block:
                                        e.block.block.remove(e)
                                    e.block = None
                                e.d = max(0.0, e.d - (e.cur + 75) * dt)
                    if self.fx and self.frnd.random() < dt * 40:
                        a = self.frnd.uniform(0, TAU)
                        self.parts.append([x + math.cos(a) * rad, y + math.sin(a) * rad, 20, -math.cos(a) * rad * 2.2, -math.sin(a) * rad * 2.2, 0, 0.4, 0.4, PURPLE, 3])
                c["dead"] = t > 3.6
            elif k == "repair":
                if not c["hit"] and t >= 0.3:
                    c["hit"] = True
                    for tw in self.towers:
                        if (tw.x - x) ** 2 + (tw.y - y) ** 2 <= rad * rad:
                            tw.stun = 0.0
                            if tw.path:
                                lost = int(tw.maxhp - tw.hp)
                                tw.hp = tw.maxhp
                                tw.down = False
                                tw.down_t = 0.0
                                if lost > 0:
                                    self.text(tw.x, tw.y, "+%d" % lost, GREEN, 22, 1.4, 40)
                    self.ring(x, y, 10, rad, ABILS[k]["col"], 0.6, 6)
                    self.burst(x, y, ABILS[k]["col"], 30, 200, 0.8, 3, 10)
                    self.sfx("upgrade")
                c["dead"] = t > 1.0
            elif k == "laser":
                if 0.3 < t < 4.3:
                    if not c["hit"]:
                        c["hit"] = True
                        self.sfx("rail")
                    d = 95 * self.hm() * dt
                    for e in self.enemies:
                        if not e.dead and math.hypot(e.x - x, e.y - y) <= rad + e.r:
                            self.hurt(e, d * (2.0 if e.boss else 1.0), None, True, True, P=P)
                    if self.fx and self.frnd.random() < dt * 30:
                        a = self.frnd.uniform(0, TAU)
                        self.parts.append([x, y, 3, math.cos(a) * 160, math.sin(a) * 160, 120, 0.4, 0.4, RED, 3])
                c["dead"] = t > 4.6
            elif k == "overdrive":
                if not c["hit"] and t >= 0.25:
                    c["hit"] = True
                    for tw in self.towers:
                        if (tw.x - x) ** 2 + (tw.y - y) ** 2 <= rad * rad:
                            tw.od = 8.0
                            self.burst(tw.x, tw.y, CYAN, 6, 90, 0.5, 3, 20)
                    self.ring(x, y, 10, rad, CYAN, 0.6, 6)
                    self.sfx("clock")
                c["dead"] = t > 1.0
        self.casts = [c for c in self.casts if not c.get("dead")]


# ======================================================================
#  THE BOT  -  plays by itself (title screen, strat videos, my own testing)
# ======================================================================
BOT_PATH = ("guardian", "bulwark", "reactor", "brick")
BOT_ECO = ("harvester", "stonks")
BOT_SUP = ("cryo", "beacon", "commander", "mechanic", "graviton")


class Bot:
    def __init__(self, world, seed=1, pid=0):
        self.w = world
        self.P = world.players[pid]
        self.rnd = random.Random(seed)
        self.t = 0.0
        self.wait = 0.0
        self.i = 0
        self.samples = []
        self.lanes = []         # the same points, one list per road
        self.pspots = []
        for pi, p in enumerate(world.paths):
            d = 0.0
            lane = []
            while d < p.length:
                x, y, _ = p.at(d)
                if 0 <= x < FW and 0 <= y < FH:
                    self.samples.append((x, y))
                    lane.append((x, y))
                    if int(d) % 40 == 0:
                        self.pspots.append((x, y, d / p.length))
                d += 20
            self.lanes.append(lane)
        self.lane_got = [0.0] * len(self.lanes)         # how much firepower each road already has
        self.spots = {"G": [], "C": []}
        for gx in range(20, FW, 20):
            for gy in range(20, FH, 20):
                if world.place_check("sentinel", gx, gy)[0]:
                    self.spots[world.terrain(gx, gy)].append((gx, gy))
        self.cov = {}
        self.lcov = {}

    def lane_cover(self, r, spot):
        """how many points of each road a tower with this range would cover from this spot"""
        key = (int(r // 20) * 20, spot)
        v = self.lcov.get(key)
        if v is None:
            r2 = key[0] * key[0]
            x, y = spot
            v = self.lcov[key] = [sum(1 for sx, sy in lane if (sx - x) ** 2 + (sy - y) ** 2 <= r2) for lane in self.lanes]
        return v

    def coverage(self, r):
        r = int(r // 20) * 20
        tab = self.cov.get(r)
        if tab is None:
            tab = self.cov[r] = {}
            r2 = r * r
            for lst in self.spots.values():
                for x, y in lst:
                    tab[(x, y)] = sum(1 for sx, sy in self.samples if (sx - x) ** 2 + (sy - y) ** 2 <= r2)
        return tab

    def free(self, kind):
        w = self.w
        T = TOWERS[kind]
        h = T.get("box", 15)
        pl = T["place"]
        out = []
        tw = [t for t in w.towers if not t.path]
        for tr in ("G", "C"):
            if pl != "B" and pl != tr:
                continue
            for s in self.spots[tr]:
                x, y = s
                ok = True
                for t in tw:
                    if abs(t.x - x) < t.box + h and abs(t.y - y) < t.box + h:
                        ok = False
                        break
                if ok and (h <= 15 or w.place_check(kind, x, y)[0]):
                    out.append(s)
        return out

    def best_spot(self, kind):
        w = self.w
        L = TOWERS[kind]["lv"][0]
        rnd = self.rnd
        if is_path(kind):
            atk = [t for t in w.towers if not t.path and t.kind not in NOFIGHT]
            best, bv = None, -1e9
            for x, y, f in self.pspots:
                if not w.place_check(kind, x, y)[0]:
                    continue
                v = sum(1 + t.lv for t in atk if (t.x - x) ** 2 + (t.y - y) ** 2 <= (t.rng or 100) ** 2) - abs(f - 0.55) * 3 + rnd.random() * 0.5
                if v > bv:
                    best, bv = (x, y), v
            return best
        cells = self.free(kind)
        if not cells:
            return None
        if kind in BOT_ECO or kind == "summoner":
            # it does not matter where these stand (a Summoner's goons come out of the core): keep them off the good gun spots
            tab = self.coverage(160)
            return min(cells, key=lambda c: (tab[c], c))
        if kind in ("beacon", "commander", "mechanic"):
            r2 = L["rng"] ** 2
            if kind == "mechanic":
                pool = [t for t in w.towers if t.path]
            else:
                pool = [t for t in w.towers if not t.path and t.kind not in NOFIGHT and (kind == "beacon" or t.kind != "cryo")]
            return max(cells, key=lambda c: (sum(1 + t.lv for t in pool if (t.x - c[0]) ** 2 + (t.y - c[1]) ** 2 <= r2), rnd.random()))
        rr = min(L.get("rng", 100), 270)
        tab = self.coverage(rr)
        if kind in ("sentinel", "blade", "cat"):
            near = self.coverage(60 if kind != "sentinel" else 66)
            close = [c for c in cells if near[c] >= 3]
            if close:
                cells = close
                tab = dict((c, tab[c] + near[c] * 2) for c in close)
        if len(self.lanes) > 1:
            # more than one road: do not leave one of them undefended.  A road with little firepower counts double.
            top = max(self.lane_got)
            wts = [2.2 if g < 0.6 * top or top == 0 else 1.0 for g in self.lane_got]
            if top == 0:
                wts = [1.0] * len(wts)
                # the very first tower: where it can see the most roads at once
                best = max(cells, key=lambda c: (min(self.lane_cover(rr, c)) * 3 + tab[c], rnd.random()))
            else:
                best = max(cells, key=lambda c: (sum(v * k for v, k in zip(self.lane_cover(rr, c), wts)), rnd.random()))
            return best
        return max(cells, key=lambda c: (tab[c], rnd.random()))

    def note(self, txt, x=None, y=None):
        self.w.guide.append((self.w.wave, txt, x, y))

    def step(self, dt):
        w = self.w
        P = self.P
        if w.phase == "over":
            return
        if w.phase == "cards":
            if P.offer:
                i = self.rnd.choice([0, 0, 0, 1, 2, 2])
                self.note("Card: " + P.offer[i]["name"])
                w.pick_card(P, i)
            return
        if w.phase == "build":
            self.wait += dt
            if self.wait > 1.2:
                self.wait = 0.0
                w.ready(P)
                if w.cur is not None:
                    for t in w.towers:
                        if t.kind == "rail" and t.owner is P:
                            t.mode = 2 if w.cur["boss"] else 0
        else:
            for slot, ab in enumerate(P.abils):
                if P.acd[slot] > 0 or not w.enemies:
                    continue
                rad = ABILS[ab]["rad"]
                if ab == "repair":
                    down = [t for t in w.ptowers if t.down or t.hp < t.maxhp * 0.35]
                    if down:
                        w.use_ability(P, slot, down[0].x, down[0].y)
                    continue
                if ab == "overdrive":
                    if len(w.enemies) > 8 and w.towers:
                        t = max(w.towers, key=lambda q: q.spent)
                        w.use_ability(P, slot, t.x, t.y)
                    continue
                best, bn = None, 0
                for e in w.enemies[::2]:
                    n = sum(1 for o in w.enemies if (o.x - e.x) ** 2 + (o.y - e.y) ** 2 < rad * rad) + (6 if e.boss else 0) + (4 if e.rem < 260 else 0)
                    if ab == "laser":
                        n = (8 if e.boss else 0) + (5 if e.kind in ("jugger", "elite") else 0)
                    if n > bn:
                        best, bn = e, n
                if best is not None and bn >= 5:
                    w.use_ability(P, slot, best.x, best.y)
            if len(w.enemies) > 6:
                for t in w.towers:
                    if t.kind == "commander" and t.acd <= 0 and t.owner is P:
                        w.tower_ability(P, t)
        self.t -= dt
        if self.t > 0:
            return
        self.t = 0.35
        for _ in range(3):
            if not self.spend():
                break

    def try_build(self, kind):
        w, P = self.w, self.P
        if P.cash < w.cost(P, kind) or w.limit_check(P, kind):
            return False
        s = self.best_spot(kind)
        if s and w.build(P, kind, s[0], s[1]):
            self.note("Place %s" % P.tname(kind), s[0], s[1])
            if len(self.lanes) > 1 and TOWERS[kind]["atk"] in ("RANGED", "MELEE", "BOTH"):
                rr = min(TOWERS[kind]["lv"][0].get("rng", 100), 270)
                dps = tower_dps(kind, TOWERS[kind]["lv"][0]) or 1.0
                for i, v in enumerate(self.lane_cover(rr, s)):
                    self.lane_got[i] += v * dps
            return True
        return False

    def spend(self):
        w, P = self.w, self.P
        lo = P.loadout
        mine = [t for t in w.towers if t.owner is P]
        atk = [k for k in lo if TOWERS[k]["atk"] in ("RANGED", "MELEE", "BOTH")]
        n_atk = sum(1 for t in mine if t.kind in atk)
        left = w.nwaves - w.wave
        spent = sum(t.spent for t in mine) or 1
        cap = w.cap()

        def cnt(k):
            return sum(1 for t in mine if t.kind == k)
        want = None
        ecos = [k for k in lo if k in BOT_ECO]
        eco = sum(t.spent for t in mine if t.kind in BOT_ECO)
        if ecos and left > 10 and n_atk >= 3 and eco < 0.26 * spent:
            hs = [t for t in mine if t.kind in BOT_ECO and t.lv < MAXLV]
            can = [k for k in ecos if not w.limit_check(P, k)]
            if can and (not hs or w.cost(P, can[0]) <= min(w.up_cost(t) for t in hs)):
                want = can[0]
            elif hs:
                t = min(hs, key=w.up_cost)
                if w.up_cost(t) <= P.cash:
                    if w.upgrade(P, t):
                        self.note("Upgrade %s to level %d" % (P.tname(t.kind), t.lv + 1), t.x, t.y)
                        return True
        if want is None:
            paths = [k for k in lo if k in BOT_PATH]
            npath = sum(1 for t in mine if t.path)
            if paths and n_atk >= 4 and npath < min(PATH_MAX, 1 + w.wave // 8) and not w.limit_check(P, paths[0]):
                want = paths[npath % len(paths)]
            elif "cryo" in lo and n_atk >= 4 and cnt("cryo") < (1 if w.wave < 12 else 2 if w.wave < 22 else 3):
                want = "cryo"
            elif "mechanic" in lo and npath >= 1 and w.wave >= 8 and cnt("mechanic") < 1:
                want = "mechanic"
            elif "commander" in lo and n_atk >= 8 and w.wave >= 14 and cnt("commander") < (1 if w.wave < 22 else 2):
                want = "commander"
            elif "beacon" in lo and n_atk >= 7 and w.wave >= 10 and cnt("beacon") < (1 if w.wave < 20 else 2):
                want = "beacon"
            elif "graviton" in lo and n_atk >= 8 and w.wave >= 16 and cnt("graviton") < (1 if w.wave < 24 else 2):
                want = "graviton"
            elif "summoner" in lo and n_atk >= 3 and cnt("summoner") < (1 if w.wave < 12 else 2 if w.wave < 22 else 3):
                want = "summoner"
            elif n_atk < min(4 + w.wave * 0.45, cap - 6) and len(mine) < cap:
                ok = [k for k in atk if TOWERS[k]["lv"][0]["cost"] <= max(P.cash, 320 + 110 * w.wave) and (TOWERS[k]["tier"] != "LATE" or w.wave >= 13)] or atk[:1]
                if ok:
                    ok.sort(key=lambda k: TOWERS[k]["lv"][0]["cost"])
                    want = ok[-1 - (self.i % min(len(ok), 3))] if len(ok) > 2 else ok[self.i % len(ok)]
        if want:
            if P.cash >= w.cost(P, want):
                got = self.try_build(want)
                if want in atk:
                    self.i += 1
                if got:
                    return True
            elif want in atk:
                return False
        best, bv = None, 0.0
        for t in mine:
            c = w.up_cost(t)
            if c is None or c > P.cash or t.kind in BOT_ECO:
                continue
            if t.kind in atk:
                aoe = 1.6 if TOWERS[t.kind].get("aoe") else 1.0
                v = (tower_dps(t.kind, TOWERS[t.kind]["lv"][t.lv + 1]) - tower_dps(t.kind, t.L)) * aoe / c
            elif t.kind == "summoner":
                # goon health per second is its firepower
                L1 = TOWERS[t.kind]["lv"][t.lv + 1]
                v = (L1["ghp"] / L1["cd"] - t.L["ghp"] / t.L["cd"]) / c
            elif t.path:
                v = 0.05 if c < P.cash * 0.4 else 0.0
            else:
                v = 0.03 if c < P.cash * 0.3 else 0.0
            v *= self.rnd.uniform(0.8, 1.2)
            if v > bv:
                best, bv = t, v
        if best is not None and w.upgrade(P, best):
            self.note("Upgrade %s to level %d" % (P.tname(best.kind), best.lv + 1), best.x, best.y)
            return True
        return False


# ======================================================================
#  WI-FI PLAY  -  one computer hosts, the others join.
#  The host runs the real game and tells everyone what is happening.
# ======================================================================
NET_PORT = 47800
BEACON_PORT = 47801
NET_MAGIC = "NEONBASTION2"
SNAP_HZ = 12.0


def net_pack(obj):
    data = zlib.compress(json.dumps(obj, separators=(",", ":")).encode("utf-8"), 1)
    return struct.pack("!I", len(data)) + data


def my_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class Conn:
    """one link to another computer"""

    def __init__(self, sock):
        self.sock = sock
        self.sock.setblocking(False)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        self.buf = b""
        self.out = b""
        self.dead = False
        self.last = time.time()

    def send(self, obj):
        if not self.dead:
            self.out += net_pack(obj)
            if len(self.out) > 4000000:
                self.close()

    def pump(self):
        """push out what is waiting, read what has arrived -> list of messages"""
        msgs = []
        if self.dead:
            return msgs
        try:
            if self.out:
                n = self.sock.send(self.out)
                self.out = self.out[n:]
        except (BlockingIOError, InterruptedError):
            pass
        except Exception:
            self.close()
            return msgs
        try:
            while True:
                data = self.sock.recv(65536)
                if not data:
                    self.close()
                    break
                self.buf += data
                if len(data) < 65536:
                    break
        except (BlockingIOError, InterruptedError):
            pass
        except Exception:
            self.close()
        while len(self.buf) >= 4:
            n = struct.unpack("!I", self.buf[:4])[0]
            if n > 8000000:
                self.close()
                break
            if len(self.buf) < 4 + n:
                break
            raw = self.buf[4:4 + n]
            self.buf = self.buf[4 + n:]
            try:
                m = json.loads(zlib.decompress(raw).decode("utf-8"))
                if isinstance(m, dict):
                    msgs.append(m)
                    self.last = time.time()
            except Exception:
                pass
        return msgs

    def close(self):
        self.dead = True
        try:
            self.sock.close()
        except Exception:
            pass


class Host:
    def __init__(self, name):
        self.name = name
        self.ok = False
        self.err = ""
        self.port = NET_PORT
        self.conns = {}         # player number -> Conn
        self.new = []           # connections that have not said hello yet
        self.beacon_t = 0.0
        self.ip = my_ip()
        self.lst = None
        self.udp = None
        for port in range(NET_PORT, NET_PORT + 6):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", port))
                s.listen(8)
                s.setblocking(False)
                self.lst = s
                self.port = port
                self.ok = True
                break
            except Exception as err:
                self.err = str(err)
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setblocking(False)
        except Exception:
            self.udp = None

    def beacon(self, dt, info):
        """shout on the Wi-Fi so friends see this game without typing anything"""
        self.beacon_t -= dt
        if self.beacon_t > 0 or self.udp is None:
            return
        self.beacon_t = 1.0
        msg = dict(info)
        msg.update(magic=NET_MAGIC, port=self.port, host=self.name, ver=VERSION)
        data = json.dumps(msg).encode("utf-8")
        targets = ["255.255.255.255", "127.0.0.1"]
        parts = self.ip.split(".")
        if len(parts) == 4:
            targets.append(".".join(parts[:3] + ["255"]))
        for addr in targets:
            try:
                self.udp.sendto(data, (addr, BEACON_PORT))
            except Exception:
                pass

    def accept(self):
        if self.lst is None:
            return
        try:
            while True:
                sock, addr = self.lst.accept()
                self.new.append(Conn(sock))
        except (BlockingIOError, InterruptedError):
            pass
        except Exception:
            pass

    def close(self):
        for c in list(self.conns.values()) + self.new:
            try:
                c.send(dict(t="bye"))
                c.pump()
            except Exception:
                pass
            c.close()
        self.conns = {}
        self.new = []
        for s in (self.lst, self.udp):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
        self.lst = self.udp = None
        self.ok = False


class Finder:
    """listens for games on the Wi-Fi"""

    def __init__(self):
        self.games = {}         # (ip, port) -> info
        self.sock = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            except Exception:
                pass
            s.bind(("", BEACON_PORT))
            s.setblocking(False)
            self.sock = s
        except Exception:
            self.sock = None

    def poll(self):
        now = time.time()
        if self.sock is not None:
            try:
                while True:
                    data, addr = self.sock.recvfrom(4096)
                    try:
                        m = json.loads(data.decode("utf-8"))
                    except Exception:
                        continue
                    if isinstance(m, dict) and m.get("magic") == NET_MAGIC:
                        m["ip"] = addr[0]
                        m["seen"] = now
                        self.games[(addr[0], int(m.get("port", NET_PORT)))] = m
            except (BlockingIOError, InterruptedError):
                pass
            except Exception:
                pass
        for k in [k for k, v in self.games.items() if now - v["seen"] > 4.0]:
            del self.games[k]
        best = {}
        for g in self.games.values():
            k = (g.get("host", ""), g.get("port"))
            if k not in best or best[k]["ip"].startswith("127."):
                best[k] = g
        return sorted(best.values(), key=lambda g: (g.get("host", ""), g["ip"]))

    def close(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except Exception:
            pass
        self.sock = None


def net_connect(ip, port):
    """-> (Conn, '') or (None, why)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip, port))
        return Conn(s), ""
    except Exception as err:
        return None, str(err)


# ---------------------------------------------------------------- what the host tells its guests
def _r1(v):
    return int(v * 10) / 10.0


def world_snap(w, pid, fx):
    """the state of the match, as small as it comfortably gets"""
    tw = []
    for t in w.towers:
        tw.append([t.id, t.kind, _r1(t.x), _r1(t.y), t.lv, t.owner.id, round(t.ang, 2), _r1(t.stun), _r1(t.act), _r1(t.acd), t.mode,
                   int(t.hp), int(t.maxhp), 1 if t.down else 0, 1 if t.beam else 0, t.tg.id if (t.tg is not None and not t.tg.dead) else 0,
                   t.tg2.id if (t.tg2 is not None and not t.tg2.dead) else 0, int(t.rng), int(t.mrng), _r1(t.od), round(t.rb, 2),
                   round(t.recoil, 1), round(t.swing, 1), t.kills, int(t.dealt), int(t.spent), round(t.ramp, 1), 1 if t.hit > 0 else 0, round(t.db, 2)])
    en = []
    for e in w.enemies:
        if e.dead:
            continue
        fl = (1 if e.hidden else 0) | (2 if e.freeze > 0 else 0) | (4 if e.slow > 0 else 0) | (8 if e.burn_t > 0 else 0) | (16 if e.fear > 0 else 0) | \
             (32 if e.dr > 0 else 0) | (64 if e.lift > 0 else 0) | (128 if e.flash > 0 else 0) | (256 if e.leak >= 999 else 0) | \
             (512 if e.act > ACT_TIME * 0.5 else 0)         # 512: it has just started an attack swing
        en.append([e.id, e.kind, e.pi, _r1(e.d), int(-e.cur if e.fear > 0 else e.cur), int(e.hp), int(e.max), int(e.shield), int(e.smax), fl])
    # goons: [id, road, how far along, health, full health, level, owner, speed, 1 if it was just hit, its Summoner's id]
    go = [[g.id, g.pi, _r1(g.d), int(math.ceil(g.hp)), int(math.ceil(g.max)), g.lv, g.owner.id, _r1(g.spd), 1 if g.flash > 0 else 0, g.tid]
          for g in w.goons if not g.dead]
    P = w.players[pid]
    return dict(t="snap", go=go, ph=w.phase, w=w.wave, hp=int(w.hp), mx=int(w.maxhp), ag=w.aegis, left=w.hostiles(), res=w.result, st=w.stars,
                tm=_r1(w.card_t if w.phase == "cards" else w.build_t), pt=int(w.playtime),
                nx=dict(counts=w.next["counts"], boss=w.next["boss"], w=w.next["w"]) if w.next else None,
                cur=w.cur["boss"] if w.cur else None,
                pl=[[int(q.cash), _r1(q.acd[0]), _r1(q.acd[1]), 1 if q.ready else 0, 1 if q.here else 0, int(q.x), int(q.y), q.kills, int(q.dealt),
                     round(q.mods["discount"], 3), round(q.mods["recycle"], 3), 1 if q.offer else 0, 1 if q.skip else 0, int(q.z)] for q in w.players],
                pn=[[t.id, t.kind, _r1(t.x), _r1(t.y), t.owner.id, round(t.ang, 2), int(t.rng)] for t in w.plans],
                sk=[w.skip_why()] + list(w.skip_votes()), cl=w.cleared,
                of=P.offer, cd=[[c["cat"], c["name"], c["rar"]] for c in P.cards],
                tw=tw, en=en, bs=w.boss.id if w.boss is not None else 0,
                ca=[[c["id"], c["kind"], int(c["x"]), int(c["y"]), _r1(c["t"]), int(c["rad"])] for c in w.casts],
                fi=[[int(f[0]), int(f[1]), int(f[2]), _r1(f[4]), list(f[6])] for f in w.fields],
                fx=fx, fl=sorted(w.flags), stt=w.stats, gm=w.gm)


class GuestWorld(Field):
    """a guest's copy of the host's match.  It only shows things; the host decides everything."""

    def __init__(self, mapkey, diff, specs):
        Field.__init__(self, mapkey, True)
        if self.map.get("event"):
            diff = "event"
        self.diff = diff
        self.D = DIFFS[diff]
        self.players = [Player(i, s) for i, s in enumerate(specs)]
        self.maxhp = self.hp = self.D["core"]
        self.aegis = 0
        self.wave = 0
        self.nwaves = self.D["waves"]
        self.phase = "build"
        self.card_t = self.build_t = 0.0
        self.playtime = 0.0
        self.result = None
        self.stars = 0
        self.boss = None
        self.next = None
        self.cur = None
        self.left = 0
        self.stats = dict(kills=0, earned=0, built=0, leaks=0, bosses=0, ptfalls=0)
        self.flags = set()
        self.gm = dict(corehp=0, aegis=0, gravity=0.0, regen=0)
        self.rev = 0
        self.tmap = {}
        self.emap = {}
        self.pmap = {}
        self.gmap = {}          # goons by id
        self.atk_on = set()     # enemies whose "attacking" flag was up in the last message
        self.got = False
        self.cleared = 0
        self.skip_info = ["No wave is running", 0, 1]

    def skip_why(self):
        return self.skip_info[0]

    def skip_votes(self):
        return self.skip_info[1], self.skip_info[2]

    def hostiles(self):
        return self.left

    def apply_snap(self, m):
        self.got = True
        self.phase = m["ph"]
        self.wave = m["w"]
        if m["hp"] < self.hp:
            self.core_hit = 0.4
        self.hp, self.maxhp, self.aegis = m["hp"], m["mx"], m["ag"]
        self.left = m["left"]
        self.result, self.stars = m["res"], m["st"]
        self.card_t = self.build_t = m["tm"]
        self.playtime = m["pt"]
        self.next = m["nx"]
        self.cur = dict(boss=m["cur"])
        self.stats = m["stt"]
        self.gm = m["gm"]
        self.flags = set(m["fl"])
        for q, d in zip(self.players, m["pl"]):
            q.cash, q.acd[0], q.acd[1], q.ready, q.here = d[0], d[1], d[2], bool(d[3]), bool(d[4])
            if not getattr(q, "synced", False):
                q.synced = True
                q.x, q.y = d[5], d[6]
                q.z = d[13] if len(d) > 13 else self.surf(q.x, q.y, 0.0)
            elif not getattr(q, "local", False):
                q.x += (d[5] - q.x) * 0.5
                q.y += (d[6] - q.y) * 0.5
                if len(d) > 13:
                    q.z += (d[13] - q.z) * 0.5
            q.kills, q.dealt = d[7], d[8]
            q.mods["discount"], q.mods["recycle"] = d[9], d[10]
            if not d[11]:
                q.offer = None
            q.skip = bool(d[12]) if len(d) > 12 else False
        sk = m.get("sk")
        if isinstance(sk, list) and len(sk) == 3:
            self.skip_info = [str(sk[0]), int(sk[1]), int(sk[2])]
        self.cleared = int(m.get("cl", self.cleared))
        # planned (ghost) towers
        seen = set()
        for d in m.get("pn", ()):
            t = self.pmap.get(d[0])
            if t is None:
                own = self.players[d[4]] if 0 <= d[4] < len(self.players) else self.players[0]
                t = self.pmap[d[0]] = Tower(d[0], d[1], d[2], d[3], own)
                t.ghost = True
                self.stand(t)
                t.ang, t.rng = d[5], d[6]
                self.plans.append(t)
                self.rev += 1
            seen.add(d[0])
        if len(seen) != len(self.plans):
            for t in self.plans:
                if t.id not in seen:
                    del self.pmap[t.id]
            self.plans = [t for t in self.plans if t.id in seen]
            self.rev += 1
        me = [q for q in self.players if getattr(q, "local", False)]
        if me:
            me[0].offer = m["of"]
            me[0].cards = [dict(cat=c[0], name=c[1], rar=c[2]) for c in m["cd"]]
        # enemies
        seen = set()
        atk = set()
        for d in m["en"]:
            e = self.emap.get(d[0])
            if e is None:
                e = self.emap[d[0]] = Enemy(d[0], d[1], d[2], d[3], 1.0, 0)
                self.enemies.append(e)
            seen.add(d[0])
            if abs(d[3] - e.d) > 40:
                e.d = d[3]
            else:
                e.d += (d[3] - e.d) * 0.4
            e.pi = d[2]
            e.cur = d[4]
            e.hp, e.max, e.shield, e.smax = d[5], max(1, d[6]), d[7], d[8]
            fl = d[9]
            e.hidden = bool(fl & 1)
            e.freeze = 0.3 if fl & 2 else 0.0
            e.slow = 0.3 if fl & 4 else 0.0
            e.burn_t = 0.3 if fl & 8 else 0.0
            e.fear = 0.3 if fl & 16 else 0.0
            e.dr = 0.3 if fl & 32 else 0.0
            e.lift = 0.4 if fl & 64 else 0.0
            if fl & 128:
                e.flash = 0.08
            if fl & 256:
                e.leak = 999
            if fl & 512:
                atk.add(e.id)
                if e.id not in self.atk_on:
                    e.act = ACT_TIME            # the flag just went up: play the swing here, on our own clock
        self.atk_on = atk
        if len(seen) != len(self.enemies):
            killed = set(f[1] for f in m["fx"] if f and f[0] == "c")       # the ones that were killed (the others got through)
            for e in self.enemies:
                if e.id not in seen:
                    e.dead = True
                    del self.emap[e.id]
                    if e.id in killed:
                        self.add_corpse(e)
            self.enemies = [e for e in self.enemies if not e.dead]
        # goons
        seen = set()
        for d in m.get("go", ()):
            g = self.gmap.get(d[0])
            if g is None:
                own = self.players[d[6]] if 0 <= d[6] < len(self.players) else self.players[0]
                g = self.gmap[d[0]] = Goon(d[0], None, own, d[1], d[2], d[4], d[7], d[5])
                g.tid = d[9]
                self.place_goon(g)
                self.goons.append(g)
            seen.add(d[0])
            if abs(d[2] - g.d) > 40:
                g.d = d[2]
            else:
                g.d += (d[2] - g.d) * 0.4
            g.pi, g.hp, g.max, g.lv, g.spd = d[1], d[3], max(1, d[4]), d[5], d[7]
            if d[8]:
                g.flash = 0.1
        if len(seen) != len(self.goons):
            left = set(d[0] for d in m["tw"])               # the towers that are still standing
            for g in self.goons:
                if g.id not in seen:
                    g.dead = True
                    del self.gmap[g.id]
                    if g.d > 12.0 and self.phase != "over" and g.tid in left:
                        self.add_corpse(g, True)        # it did not get to the gate and its Summoner was not sold: it fell
            self.goons = [g for g in self.goons if not g.dead]
        self.boss = self.emap.get(m["bs"])
        # towers
        seen = set()
        for d in m["tw"]:
            t = self.tmap.get(d[0])
            if t is None:
                own = self.players[d[5]] if 0 <= d[5] < len(self.players) else self.players[0]
                t = self.tmap[d[0]] = Tower(d[0], d[1], d[2], d[3], own)
                self.stand(t)
                t.t = self.frnd.uniform(0, 6)
                self.towers.append(t)
                self.rev += 1
            seen.add(d[0])
            if t.lv != d[4]:
                t.lv = d[4]
                t.L = TOWERS[t.kind]["lv"][t.lv]
            t.ang, t.stun, t.act, t.acd, t.mode = d[6], d[7], d[8], d[9], d[10]
            t.hp, t.maxhp, t.down, t.beam = d[11], d[12], bool(d[13]), bool(d[14])
            t.tg = self.emap.get(d[15])
            t.tg2 = self.emap.get(d[16])
            t.rng, t.mrng, t.od, t.rb = d[17], d[18], d[19], d[20]
            t.recoil = max(t.recoil, d[21])
            t.swing = max(t.swing, d[22])
            t.kills, t.dealt, t.spent, t.ramp = d[23], d[24], d[25], d[26]
            if d[27]:
                t.hit = 0.15
            t.db = d[28]
        if len(seen) != len(self.towers):
            for t in self.towers:
                if t.id not in seen:
                    del self.tmap[t.id]
            self.towers = [t for t in self.towers if t.id in seen]
            self.rev += 1
        self.casts = [dict(id=c[0], kind=c[1], x=c[2], y=c[3], t=c[4], rad=c[5]) for c in m["ca"]]
        self.fields = [[f[0], f[1], f[2], 0, f[3], None, tuple(f[4]), None] for f in m["fi"]]
        for f in m["fx"]:
            if f[0] == "h":
                self.guest_shot(f)
        self.play_fx(m["fx"])

    def guest_shot(self, f):
        try:
            s = Shot(f[1], f[2], f[3], 0, None, tuple(f[9]), f[4])
            s.tg = self.emap.get(f[5])
            s.tx, s.ty, s.T = f[6], f[7], f[8]
            s.vx, s.vy, s.life, s.big, s.sub, s.spd = f[10], f[11], f[12], bool(f[13]), f[14], f[15]
            self.shots.append(s)
        except Exception:
            pass

    def rate_buff(self, t):
        return 0.0

    def update(self, dt):
        """keep things moving smoothly between the host's messages"""
        self.time += dt
        self.upd_fx(dt)
        for e in self.enemies:
            e.t += dt
            if e.flash > 0:
                e.flash -= dt
            p = self.paths[e.pi]
            e.d = clamp(e.d + e.cur * dt, 0.0, p.length)
            e.x, e.y, seg = p.at(e.d)
            e.z = p.zat(e.d)
            e.ang = p.angs[seg] + (math.pi if e.cur < 0 else 0)
            e.rem = p.length - e.d
            if e.act > 0:
                e.act -= dt
        for g in self.goons:
            g.t += dt
            if g.flash > 0:
                g.flash -= dt
            g.d = clamp(g.d - g.spd * dt, 0.0, self.paths[g.pi].length)
            self.place_goon(g)
        for t in self.plans:
            t.t += dt
        for t in self.towers:
            t.t += dt
            if t.recoil > 0:
                t.recoil = max(0.0, t.recoil - dt * 5)
            if t.swing > 0:
                t.swing = max(0.0, t.swing - dt * 3.5)
            if t.hit > 0:
                t.hit -= dt
            if t.kind == "blade":
                t.ang += dt * (2.5 + 14 * t.swing)
        for c in self.casts:
            c["t"] += dt
        for s in self.shots:
            if s.kind == "shell":
                s.t += dt
                if s.t >= s.T:
                    s.life = -1
                continue
            s.life -= dt
            tg = s.tg
            if s.kind in ("bullet", "bubble", "rocket"):
                if tg is None or tg.dead:
                    s.life = -1
                    continue
                dx, dy = tg.x - s.x, tg.y - s.y
                d = math.hypot(dx, dy) or 0.01
                step = s.spd * dt
                if d <= step + tg.r:
                    s.life = -1
                    continue
                s.vx, s.vy = dx / d * s.spd, dy / d * s.spd
                s.z += (tg.r - s.z) * min(1.0, step / d)
            s.x += s.vx * dt
            s.y += s.vy * dt
        self.shots = [s for s in self.shots if s.life > 0]


# ---------------------------------------------------------------- updates from your other PC
# Two PCs that share an UPDATE CODE keep each other up to date over the Wi-Fi: the one with the newer version hands its
# neon_bastion.py to the other, which checks it, swaps it in and restarts.  Nothing leaves your own network.
# Without the code nothing is accepted: every offer is signed with a key made from the code, and the file must match it.
UPD_PORT = 47811
UPD_MAGIC = "NBUPD1"
CODE_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # no I, O, 0 or 1: they look alike
CODE_LEN = 8
UPD_MAX = 8 * 1024 * 1024                            # nothing bigger than this is ever accepted


def new_update_code():
    r = random.SystemRandom()
    return "".join(r.choice(CODE_ABC) for _ in range(CODE_LEN))


def clean_code(txt):
    return "".join(ch for ch in str(txt).upper() if ch in CODE_ABC)[:CODE_LEN]


def code_file():
    """the game file this copy runs from - the one an update replaces"""
    if _NB_EXT:
        return _NB_EXT
    if getattr(sys, "frozen", False):
        return os.path.join(base_dir(), CODE_NAME)       # the .exe: updates go next to it
    return os.path.abspath(__file__)


def code_source():
    """(version, the bytes of this game's code) to hand to your other PC - or None if this copy has no code file"""
    paths = [code_file()]
    if getattr(sys, "frozen", False) and not _NB_EXT:
        paths = [os.path.join(getattr(sys, "_MEIPASS", base_dir()), CODE_NAME)]     # the copy packed inside the .exe
    for p in paths:
        try:
            with open(p, "rb") as fh:
                data = fh.read()
            v = version_in(data.decode("utf-8"))
            if v and len(data) < UPD_MAX:
                return v, data
        except Exception:
            pass
    return None


def check_update(data, ver, mine=None):
    """is this really a newer, working copy of the game?  -> "" or what is wrong with it"""
    try:
        txt = data.decode("utf-8")
    except Exception:
        return "it is not text"
    if version_in(txt) != ver:
        return "its version number does not match"
    if ver_tuple(ver) <= ver_tuple(mine or VERSION):
        return "it is not newer"
    if "NEON BASTION" not in txt[:400]:
        return "it is not Neon Bastion"
    try:
        compile(txt, CODE_NAME, "exec")
    except Exception:
        return "it does not run"
    return ""


def my_ips():
    """every address this PC has on a network (a PC can have several: Wi-Fi, cable, virtual adapters)"""
    out = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in out and not ip.startswith("127.") and not ip.startswith("169.254."):
                out.append(ip)
    except Exception:
        pass
    ip = my_ip()
    if not ip.startswith("127."):
        if ip in out:
            out.remove(ip)
        out.insert(0, ip)
    return out[:6]


def clean_ip(txt):
    """a typed address -> "192.168.1.23", or "" if it is not one"""
    parts = str(txt).strip().split(".")
    try:
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return ".".join(str(int(p)) for p in parts)
    except Exception:
        pass
    return ""


class Updater:
    """shares this version with your other PC and looks for a newer one there.  Runs beside the game, never in its way.
    Either PC may start the talking: the older one can FETCH from the newer one, or the newer one can PUSH to the older one.
    So it works as long as the firewall of at least one of them lets the game be reached."""

    def __init__(self, code, version=None, source=None, extra=()):
        self.version = version or VERSION
        self.source = source or code_source      # call it -> (version, bytes) or None
        self.key = hashlib.pbkdf2_hmac("sha256", clean_code(code).encode("ascii"), b"neon-bastion-update", 200000)
        self.state = "idle"          # idle, looking, none, downloading, ready, error
        self.note = ""
        self.ready = None            # (version, bytes) once a newer copy was fetched and checked
        self.sent = []               # versions handed out (the game reads and empties this)
        self.last = 0.0              # when we last looked
        self.alive = True
        self.busy = False
        self.me = os.urandom(6).hex()        # so we never answer our own question
        self.peer = None             # (version, when, address) - the last time a PC with our code answered at all
        self.extra = [ip for ip in extra if ip]      # addresses to ask directly (typed in, or where the other PC was last time)
        self.hello = {}              # one-time numbers we handed out -> when (a PC that wants to push must sign one)
        self.pushed = {}             # (address, version) -> when we last pushed there
        self.badcode = 0.0           # when a PC answered that has a DIFFERENT update code
        self.ips = []                # the addresses we asked from, last time
        self.asked = 0               # how many questions went out, last time
        self.udp = self.tcp = None
        self.port = 0
        self.can_share = False
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            u.bind(("", UPD_PORT))
            self.udp = u
            for port in range(UPD_PORT, UPD_PORT + 6):
                try:
                    t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    t.bind(("", port))
                    t.listen(4)
                    self.tcp, self.port = t, port
                    break
                except Exception:
                    t.close()
            self.can_share = self.tcp is not None
        except Exception:
            self.udp = None
        if self.can_share:
            th = threading.Thread(target=self._serve, name="nb-update-share", daemon=True)
            th.start()

    def sign(self, nonce, ver, sha):
        return hmac.new(self.key, ("%s|%s|%s" % (nonce, ver, sha)).encode("utf-8"), hashlib.sha256).hexdigest()

    # ---- answering the other PC
    def _serve(self):
        while self.alive:
            try:
                rd, _, _ = select.select([self.udp, self.tcp], [], [], 0.5)
            except Exception:
                time.sleep(0.5)
                continue
            for s in rd:
                try:
                    if s is self.udp:
                        data, addr = s.recvfrom(2048)
                        m = json.loads(data.decode("utf-8"))
                        if not isinstance(m, dict) or m.get("magic") != UPD_MAGIC or m.get("t") != "ask":
                            continue
                        nonce = str(m.get("n", ""))[:64]
                        if len(nonce) < 8 or m.get("id") == self.me:
                            continue
                        src = self.source()
                        if src is None or ver_tuple(src[0]) <= ver_tuple(m.get("v", "0")):
                            # nothing newer to give: say hello, so the other PC can show that the link works -
                            # and hand it a one-time number, in case IT is newer and wants to push its version to us
                            now = time.time()
                            for k in [k for k, t0 in self.hello.items() if now - t0 > 30.0]:
                                del self.hello[k]
                            n2 = os.urandom(12).hex()
                            if len(self.hello) < 64:
                                self.hello[n2] = now
                            out = dict(magic=UPD_MAGIC, t="hi", v=self.version, n2=n2, port=self.port, mac=self.sign(nonce, self.version, "hi"))
                            s.sendto(json.dumps(out).encode("utf-8"), addr)
                            continue
                        sha = hashlib.sha256(src[1]).hexdigest()
                        out = dict(magic=UPD_MAGIC, t="have", v=src[0], size=len(src[1]), sha=sha, port=self.port, mac=self.sign(nonce, src[0], sha))
                        s.sendto(json.dumps(out).encode("utf-8"), addr)
                    else:
                        c, addr = s.accept()
                        try:
                            c.settimeout(0.5)
                            try:
                                first = c.recv(4096)        # a PC that fetches says nothing; one that pushes starts talking
                            except socket.timeout:
                                first = b""
                            if first:
                                self._take(c, first)
                            else:
                                c.settimeout(8.0)
                                src = self.source()
                                if src is not None:
                                    c.sendall(src[1])
                                    self.sent.append(src[0])
                        finally:
                            c.close()
                except Exception:
                    pass

    def _take(self, c, first):
        """the other PC is pushing a newer version to us: only if it signed one of OUR one-time numbers with our code"""
        buf = bytearray(first)
        c.settimeout(6.0)
        while b"\n" not in buf and len(buf) < 4096:
            part = c.recv(4096)
            if not part:
                return
            buf.extend(part)
        head, _, rest = bytes(buf).partition(b"\n")
        m = json.loads(head.decode("utf-8"))
        if not isinstance(m, dict) or m.get("magic") != UPD_MAGIC or m.get("t") != "push":
            return
        ver, sha, size, n2 = str(m.get("v", "")), str(m.get("sha", "")), m.get("size"), str(m.get("n2", ""))
        if not isinstance(size, int) or not 0 < size < UPD_MAX or ver_tuple(ver) <= ver_tuple(self.version):
            return
        if n2 not in self.hello or time.time() - self.hello[n2] > 30.0:
            return
        if not hmac.compare_digest(self.sign(n2, ver, sha), str(m.get("mac", ""))):
            return
        del self.hello[n2]                      # one use only
        if self.ready is not None or self.state == "downloading":
            return
        self.state, self.note = "downloading", ver
        data = bytearray(rest)
        while len(data) < size:
            part = c.recv(min(65536, size - len(data)))
            if not part:
                break
            data.extend(part)
        self._accept(bytes(data), ver, sha, size)
        try:
            c.sendall(b"ok\n" if self.ready is not None else b"no\n")
        except Exception:
            pass

    def _accept(self, data, ver, sha, size):
        """the last checks on a version that arrived, whichever way it came"""
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            self.state, self.note = "error", "the download was damaged"
            return
        why = check_update(data, ver, self.version)
        if why:
            self.state, self.note = "error", why
            return
        self.ready = (ver, data)
        self.state, self.note = "ready", ver

    # ---- asking the other PC
    def check(self):
        if self.busy or self.ready is not None or not self.alive:
            return
        self.busy = True
        if self.state != "downloading":
            self.state = "looking"
            self.note = ""
        th = threading.Thread(target=self._look, name="nb-update-look", daemon=True)
        th.start()

    def _look(self):
        try:
            self._look2()
        except Exception as ex:
            if self.ready is None:
                self.state, self.note = "error", "%s" % ex
        self.last = time.time()
        self.busy = False

    def _look2(self):
        nonce = os.urandom(12).hex()
        ask = json.dumps(dict(magic=UPD_MAGIC, t="ask", v=self.version, n=nonce, id=self.me)).encode("utf-8")
        # one socket per network this PC is on (a broadcast only leaves through ONE of them otherwise), plus a plain one
        socks = []
        ips = my_ips()
        self.ips = ips
        for ip in [None] + ips:
            try:
                q = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                q.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                if ip is not None:
                    q.bind((ip, 0))
                    tg = ["255.255.255.255", ip.rsplit(".", 1)[0] + ".255"]
                else:
                    tg = ["255.255.255.255", "127.0.0.1"] + list(self.extra)
                socks.append((q, tg))
            except Exception:
                pass
        offers = []
        his = []
        asked = 0
        try:
            for rnd in range(6):
                for q, tg in socks:
                    for a in tg:
                        try:
                            q.sendto(ask, (a, UPD_PORT))
                            asked += 1
                        except Exception:
                            pass
                t_end = time.time() + 0.45
                while time.time() < t_end:
                    try:
                        rd, _, _ = select.select([q for q, _ in socks], [], [], max(0.01, t_end - time.time()))
                    except Exception:
                        break
                    for q in rd:
                        try:
                            data, addr = q.recvfrom(2048)
                            m = json.loads(data.decode("utf-8"))
                        except Exception:
                            continue
                        if not isinstance(m, dict) or m.get("magic") != UPD_MAGIC or m.get("t") not in ("hi", "have"):
                            continue
                        ver = str(m.get("v", ""))[:16]
                        if m["t"] == "hi":
                            if not hmac.compare_digest(self.sign(nonce, ver, "hi"), str(m.get("mac", ""))):
                                self.badcode = time.time()
                                continue
                            self.peer = (ver, time.time(), addr[0])
                            if isinstance(m.get("port"), int) and 0 < m["port"] < 65536 and m.get("n2"):
                                his.append((ver, addr[0], m["port"], str(m["n2"])[:64]))
                            continue
                        sha, size, port = str(m.get("sha", "")), m.get("size"), m.get("port")
                        if not isinstance(size, int) or not isinstance(port, int) or not 0 < size < UPD_MAX or not 0 < port < 65536:
                            continue
                        if not hmac.compare_digest(self.sign(nonce, ver, sha), str(m.get("mac", ""))):
                            self.badcode = time.time()      # somebody with another update code: ignore the offer
                            continue
                        self.peer = (ver, time.time(), addr[0])
                        if ver_tuple(ver) > ver_tuple(self.version):
                            offers.append((ver_tuple(ver), ver, sha, size, addr[0], port))
                if offers or his:
                    break
        finally:
            self.asked = asked
            for q, _ in socks:
                try:
                    q.close()
                except Exception:
                    pass
        if offers and self.ready is None and self.state != "downloading":
            offers.sort()
            _, ver, sha, size, host, port = offers[-1]
            self.state, self.note = "downloading", ver
            c = socket.create_connection((host, port), timeout=6.0)
            try:
                c.settimeout(8.0)
                buf = bytearray()
                while len(buf) < size:
                    part = c.recv(min(65536, size - len(buf)))
                    if not part:
                        break
                    buf.extend(part)
            finally:
                c.close()
            self._accept(bytes(buf), ver, sha, size)
            return
        # nobody has anything newer for us.  Is the other PC OLDER?  Then push our version to it.
        src = self.source() if his else None
        for ver, host, port, n2 in his:
            if src is None or ver_tuple(src[0]) <= ver_tuple(ver) or time.time() - self.pushed.get((host, src[0]), 0) < 40.0:
                continue
            self.pushed[(host, src[0])] = time.time()
            try:
                sha = hashlib.sha256(src[1]).hexdigest()
                head = dict(magic=UPD_MAGIC, t="push", v=src[0], size=len(src[1]), sha=sha, n2=n2, mac=self.sign(n2, src[0], sha))
                c = socket.create_connection((host, port), timeout=6.0)
                try:
                    c.settimeout(10.0)
                    c.sendall(json.dumps(head).encode("utf-8") + b"\n" + src[1])
                    if c.recv(16).startswith(b"ok"):
                        self.sent.append(src[0])
                finally:
                    c.close()
            except Exception:
                pass
        if self.ready is None and self.state != "downloading":
            self.state = "none"

    def close(self):
        self.alive = False
        for s in (self.udp, self.tcp):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass


def install_update(data):
    """swap the new code in.  -> (the file written, "" or what went wrong)"""
    target = code_file()
    try:
        tmp = target + ".new"
        with open(tmp, "wb") as fh:
            fh.write(data)
        if os.path.exists(target):
            try:
                with open(target, "rb") as a, open(os.path.join(os.path.dirname(target), "neon_bastion_previous.py"), "wb") as b:
                    b.write(a.read())           # the version before, in case you ever want it back
            except Exception:
                pass
        os.replace(tmp, target)
        return target, ""
    except Exception as ex:
        return target, "%s" % ex


def relaunch():
    """start the game again (as the new version).  -> True if that worked"""
    try:
        env = dict(os.environ)
        if getattr(sys, "frozen", False):
            args = [sys.executable]
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"      # a fresh start for the one-file .exe, not a child of this one
            env.pop("_MEIPASS2", None)
        else:
            args = [sys.executable, code_file()]
        subprocess.Popen(args, cwd=base_dir(), env=env, close_fds=True)
        return True
    except Exception:
        return False


JUMP_V = 160.0          # a jump: how fast the orb leaves the ground...
JUMP_G = 582.0          # ...and how hard it is pulled back (22 high, a bit over half a second in the air)
SPRINT_K = 1.7          # how much faster you are while the sprint key is held


class PlayScene(Scene):
    """the match scene, plus one thing: an orb that jumps is drawn in the air while its shadow stays on the ground"""

    def draw_player(self, w, P, t, o):
        jz = getattr(P, "jz", 0.0)
        z0 = P.z
        if jz <= 0.5 and not getattr(P, "local", False) and P is not self.me:
            # somebody else: their height arrives with the jump already in it
            try:
                gz = w.surf(P.x, P.y, z0)
            except Exception:
                gz = z0
            if 4.0 < z0 - gz < 40.0:
                jz, z0 = z0 - gz, gz
        if jz <= 0.5:
            return Scene.draw_player(self, w, P, t, o)
        g = self.r.cam.pt(P.x, P.y, z0 + 0.6)
        if g is not None:
            k = g[2] * (1.0 - 0.35 * min(1.0, jz / 22.0))
            pygame.draw.ellipse(self.r.s, (0, 0, 0), (g[0] - 8 * k, g[1] - 3 * k, 16 * k, 6 * k))
        real = P.z
        P.z = z0 + jz
        try:
            return Scene.draw_player(self, w, P, t, o)
        finally:
            P.z = real


# ======================================================================
#  THE GAME  -  window, input, save file, little widgets
# ======================================================================
class Game:
    def __init__(self):
        try:
            pygame.mixer.pre_init(22050, -16, 1, 512, allowedchanges=0)
        except Exception:
            try:
                pygame.mixer.pre_init(22050, -16, 1, 512)
            except Exception:
                pass
        if sys.platform == "win32":
            # tell Windows not to stretch the window itself (that is what cut off the edges in fullscreen)
            try:
                import ctypes
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        pygame.init()
        self.save = load_save()
        self.fix_save()
        st = self.save["settings"]
        self.vk, self.vx, self.vy, self.vw, self.vh = 1.0, 0, 0, W, H
        self.win_size = (W, H)
        self.desk = (W, H)
        try:
            self.desk = tuple(pygame.display.get_desktop_sizes()[0])
        except Exception:
            pass
        self.screen = None
        self.make_window(bool(st["fullscreen"]))
        self.canvas = pygame.Surface((W, H)).convert()
        pygame.display.set_caption(TITLE)
        try:
            ic = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.polygon(ic, (10, 40, 60), [(16, 2), (29, 16), (16, 30), (3, 16)])
            pygame.draw.polygon(ic, CYAN, [(16, 2), (29, 16), (16, 30), (3, 16)], 3)
            pygame.draw.circle(ic, PINK, (16, 16), 4)
            pygame.display.set_icon(ic)
        except Exception:
            pass
        self.clock = pygame.time.Clock()
        self.audio = Audio()
        self.audio.vol = st["sfx"]
        self.audio.set_music(st["music"])
        GFX["glow"] = st["glow"]
        self.s = self.canvas            # the game always draws a 1280 x 720 picture; present() fits it to the window
        self.scene = PlayScene()
        self.cam = Cam()
        self.mfields = {}
        self.sel_guide = 0
        self.running = True
        self.state = "menu"
        self.back_to = "menu"
        self.time = 0.0
        self.dt = 1 / 60.0
        self.mouse = (0, 0)
        self.mrel = (0, 0)
        self.mdown = False
        self.rdown = False
        self.rdrag = 0.0
        self.click = False
        self.rclick = False
        self.pressed = set()
        self.held = set()
        self.typed = ""
        self.wheel = 0
        self.shift = False
        self.hover = {}
        self.lock = False
        self.fade = 1.0
        self.drag = None
        self.focus = None
        self.bk_t = 0.0
        # a match
        self.world = None
        self.me = 0
        self.net = None             # None, ("host", Host) or ("guest", Conn)
        self.net_t = 0.0
        self.pos_t = 0.0
        self.build = None
        self.sel = None
        self.hov = None
        self.aim = None
        self.speed = 1
        self.paused = False
        self.msg = None
        self.auto_t = 0.0
        self.over_t = 0.0
        self.card_t = 0.0
        self.cash_show = 0.0
        self.reward = None
        self.cyaw, self.cpitch, self.cdist = -math.pi / 2, 0.95, 620.0
        self.ctx, self.cty, self.ctz = FW / 2.0, FH / 2.0, 0.0
        self.cine = False
        self.fc = [FW / 2.0, FH + 200.0, 260.0, -math.pi / 2, 0.5]
        self.chat = []              # [name, colour, text, time, title, where it is drawn]   (name "" = a line from the game itself)
        self.chat_top = 300         # chat boxes stay below this (the details tab on the left ends here)
        self.jump_z = 0.0           # how high the orb is above the ground in a jump, and how fast it is rising
        self.jump_v = 0.0
        self.sprint_t = 0.0
        self.hov_p = None           # the player whose orb the mouse is on
        self.mp_neg = False
        self.rebind = None          # OPTIONS > CONTROLS: the action that is waiting for a key
        self.key_msg = ["", GREY, 0.0]
        self.key_rects = {}
        self.typing = None
        self.talk = None            # [npc, line number]
        self.knocks = 0
        self.gpos = None
        self.video = None
        self.over_net = False
        # menus
        self.sel_map = 0
        self.map_tab = 0
        self.view = "blaster"
        self.view_lv = 0
        self.perk_tab = 0
        self.tpage = 0
        self.help_tab = 0
        self.confirm = 0.0
        self.quit_confirm = 0.0
        self.toast = None
        self.toasts = []
        self.fps_show = 60.0
        self.name_buf = self.save["name"]
        self.ip_buf = ""
        self.finder = None
        self.room = None
        self.room_specs = {}
        self.ghost_why = ""
        self.hud_rects = []
        self.hov_slot = None
        self.mp_err = ""
        self.demo = None
        self.demo_bot = None
        self.demo_cam = 0.0
        self.new_demo()
        self.upd = None             # keeps this PC and your other PC on the same version (OPTIONS > UPDATES)
        self.upd_buf = ""
        self.upd_ip = self.save.get("upd_ip", "")
        self.upd_t = 0.0
        self.upd_step = 0
        self.upd_msg = ""
        self.upd_told = False
        self.start_updater()
        if not self.save["name"]:
            self.state = "name"
        self.check_titles(True)

    # ------------------------------------------------------------ save helpers
    def fix_save(self):
        sv = self.save
        sv["coins"] = max(0, int(sv["coins"]))
        sv["xp"] = max(0, int(sv["xp"]))
        lv = level_of(sv["xp"])[0]
        sv["owned"] = [k for k in SHOP_TOWERS if k in sv["owned"] or TOWERS[k]["price"] == 0]
        sv["etowers"] = dict((k, v) for k, v in sv["etowers"].items() if k in EVENT_TOWERS and v in ("og", "ripoff"))
        have = sv["owned"] + [k for k in EVENT_TOWERS if k in sv["etowers"]]
        lo = []
        for k in sv["loadout"]:
            if k in have and k not in lo and len(lo) < loadout_slots(lv):
                lo.append(k)
        sv["loadout"] = lo or ["blaster", "blade", "rail"]
        sv["perks"] = [k for k in PERK_ORDER if k in sv["perks"] or PERKS[k]["price"] == 0]
        eq = []
        for k in sv["eq_perks"]:
            if k in sv["perks"] and k not in eq and len(eq) < perk_slots(lv):
                eq.append(k)
        sv["eq_perks"] = eq or sv["perks"][:1]
        sv["abils"] = [k for k in ABIL_ORDER if k in sv["abils"] or ABILS[k]["price"] == 0]
        eq = []
        for k in sv["eq_abils"]:
            if k in sv["abils"] and k not in eq and len(eq) < abil_slots(lv):
                eq.append(k)
        sv["eq_abils"] = eq or sv["abils"][:1]
        sv["tperks"] = [k for k in TPERK_ORDER if k in sv["tperks"]]
        sv["eq_tperks"] = dict((k, v) for k, v in sv["eq_tperks"].items() if v in sv["tperks"] and TPERKS[v]["tower"] == k)
        pt = {}
        for k, v in sv["paint"].items():
            if k in TOWERS and isinstance(v, int) and 0 < v < len(PAINTS):
                pt[k] = v
        sv["paint"] = pt
        sv["titles"] = [k for k in TITLE_ORDER if k in sv["titles"] or k == "rookie"]
        if sv["title"] not in sv["titles"]:
            sv["title"] = "rookie"
        sv["events"] = dict((k, float(v)) for k, v in sv["events"].items() if k in EVENTS and isinstance(v, (int, float)))
        sv["npcs"] = [k for k in sv["npcs"] if isinstance(k, str)][:200]
        if not isinstance(sv["quests"].get("ducks"), list):
            sv["quests"]["ducks"] = []
        sv["keys"] = clean_keys(sv.get("keys"))

    def level(self):
        return level_of(self.save["xp"])[0]

    def pcol(self):
        return PLAYER_COLORS[self.save["color"]][1]

    def store(self):
        write_save(self.save)

    def have_towers(self):
        return self.save["owned"] + [k for k in EVENT_TOWERS if k in self.save["etowers"]]

    def tname(self, kind):
        return TOWERS[kind]["name"] + (" RIPOFF" if self.save["etowers"].get(kind) == "ripoff" else "")

    def tcol(self, kind):
        i = self.save["paint"].get(kind, 0)
        return PAINTS[i] if i else TOWERS[kind]["col"]

    def my_spec(self, loadout=None, perks=None, abils=None):
        sv = self.save
        lo = list(loadout or sv["loadout"])
        return dict(name=safe_name(sv["name"]) or "PLAYER", col=list(self.pcol()), title=TITLES[sv["title"]][0], level=self.level(), loadout=lo,
                    perks=list(perks if perks is not None else sv["eq_perks"]), abils=list(abils or sv["eq_abils"]),
                    tperks=dict((k, v) for k, v in sv["eq_tperks"].items() if k in lo),
                    paint=dict((k, list(PAINTS[i])) for k, i in sv["paint"].items() if k in lo and i),
                    rip=[k for k in lo if sv["etowers"].get(k) == "ripoff"])

    def goto(self, state):
        if state == "lobby":            # the lobby lives on the title screen now
            state = "menu"
        self.state = state
        self.fade = 1.0
        self.confirm = 0.0
        self.quit_confirm = 0.0
        self.focus = None
        self.rebind = None

    # ------------------------------------------------------------ keys (you can change them: OPTIONS > CONTROLS)
    def key_of(self, act):
        k = self.save["keys"].get(act)
        return k if k else KEY_DEFAULTS[act]

    def _kin(self, act, keys):
        k = self.save["keys"].get(act) or KEY_DEFAULTS[act]
        if k in keys:
            return True
        ex = KEY_EXTRA.get(act)
        if ex and k == KEY_DEFAULTS[act]:
            for e in ex:
                if e in keys and e not in self.save["keys"].values():
                    return True
        return False

    def kp(self, act):
        """was the key for this action pressed this frame?"""
        return self._kin(act, self.pressed)

    def kh(self, act):
        """is the key for this action held down?"""
        return self._kin(act, self.held)

    def kname(self, act):
        """the key for this action, as a short name to show: E, SPACE, L-SHIFT"""
        return key_name(self.key_of(act))

    def kmove(self, spaced=False):
        """the four walking keys in one word: WASD"""
        nm = [self.kname(a) for a in ("up", "left", "down", "right")]
        return "".join(nm) if (not spaced and all(len(n) == 1 for n in nm)) else " ".join(nm)

    def ktext(self, txt):
        """a sentence that names a key (see KEY_TEXT) -> the same sentence with the key you really use"""
        for old, new in KEY_TEXT:
            if old in txt:
                txt = txt.replace(old, new % dict((a, self.kname(a)) for a in KEY_ORDER))
        return txt

    def set_key(self, act, k):
        """give an action a new key.  If another action had that key the two swap.  -> the other action (or None)"""
        keys = self.save["keys"]
        old = self.key_of(act)
        other = None
        for a in KEY_ORDER:
            if a != act and self.key_of(a) == k:
                other = a
        keys[act] = k
        if other is not None:
            keys[other] = old
        self.save["keys"] = clean_keys(keys)
        return other

    def fit_size(self, txt, size, width, least=11):
        """the biggest text size (up to size) at which txt is no wider than width"""
        while size > least and font(size).size(txt)[0] > width:
            size -= 1
        return size

    # ------------------------------------------------------------ updates from your other PC
    def start_updater(self):
        if self.upd is not None:
            self.upd.close()
            self.upd = None
        code = clean_code(self.save.get("upd_code", ""))
        self.save["upd_code"] = code if len(code) == CODE_LEN else ""
        if self.save["upd_code"] and not os.environ.get("NB_NO_UPDATE"):
            try:
                self.upd = Updater(self.save["upd_code"], extra=[self.save.get("upd_ip", ""), self.save.get("upd_last", "")])
                self.upd.check()
            except Exception:
                self.upd = None

    def upd_tick(self):
        u = self.upd
        if u is None:
            return
        while u.sent:
            self.pop("Sent version %s to your other PC" % u.sent.pop(0), GREEN, 4.0)
        if u.peer is not None and not u.peer[2].startswith("127.") and u.peer[2] != self.save.get("upd_last"):
            # remember where the other PC was, and ask there directly next time (a broadcast does not get through everywhere)
            self.save["upd_last"] = u.peer[2]
            u.extra = [ip for ip in (self.save.get("upd_ip", ""), u.peer[2]) if ip]
            self.store()
        calm = self.state not in ("play", "room", "video", "name", "update") and self.net is None and self.world is None
        if u.ready is not None:
            if calm:
                self.upd_step, self.upd_t, self.upd_msg = 0, 0.0, ""
                self.goto("update")
            elif not self.upd_told:
                self.upd_told = True
                self.pop("Version %s is here. It installs when you are back on the main menu." % u.ready[0], GOLD, 6.0)
        elif calm and not u.busy and time.time() - u.last > 15.0:
            u.check()           # keep looking now and then: the other PC may be opened later

    def screen_update(self, s):
        self.draw_plain(s)
        u = self.upd
        ver = u.ready[0] if u is not None and u.ready is not None else "?"
        self.upd_t += self.dt
        if self.upd_step == 0:
            draw_glow_text(s, "UPDATING", 72, GREEN, W // 2, 280)
            draw_text(s, "Version %s  ->  version %s, from your other PC" % (VERSION, ver), 24, WHITE, W // 2, 360)
            draw_text(s, "The game restarts by itself in a moment.", 18, GREY, W // 2, 400)
            if self.upd_t > 1.2:
                if u is None or u.ready is None:
                    self.goto("menu")
                    return
                self.store()
                target, err = install_update(u.ready[1])
                if err:
                    self.upd_step, self.upd_msg = 1, err
                    u.ready = None
                    u.state, u.note = "error", "could not write %s" % os.path.basename(target)
                elif relaunch():
                    self.running = False
                else:
                    self.upd_step = 2
        elif self.upd_step == 1:
            draw_glow_text(s, "COULD NOT UPDATE", 60, RED, W // 2, 260)
            draw_text(s, "The new version arrived, but this folder would not let the game save it:", 20, WHITE, W // 2, 340)
            draw_text(s, self.upd_msg[:110], 16, GREY, W // 2, 372)
            draw_text(s, "Move the game to a folder like Documents or Desktop and try again.", 18, GREY, W // 2, 410)
            if self.button("upd_ok", pygame.Rect(W // 2 - 110, 470, 220, 54), "OK", CYAN, 26) or pygame.K_ESCAPE in self.pressed:
                self.goto("menu")
        else:
            draw_glow_text(s, "UPDATED", 72, GREEN, W // 2, 280)
            draw_text(s, "Version %s is installed. Close the game and open it again to play it." % ver, 22, WHITE, W // 2, 360)
            if self.button("upd_quit", pygame.Rect(W // 2 - 110, 430, 220, 54), "CLOSE", GREEN, 26) or pygame.K_ESCAPE in self.pressed:
                self.running = False

    def say(self, txt, col=RED, life=2.2):
        self.msg = [txt, col, life]

    def pop(self, txt, col=GOLD, life=3.2):
        """a little banner at the bottom of the screen; they queue up"""
        self.toasts.append([txt, col, life])

    def unlock_event(self, ev):
        sv = self.save
        if ev in sv["events"]:
            return False
        sv["events"][ev] = time.time()
        E = EVENTS[ev]
        self.audio.play("secret")
        if E["kind"] == "secret":
            self.pop("SECRET EVENT FOUND:  %s   (you have %d days to earn the real %s)" % (E["name"], EVENT_DAYS, TOWERS[E["tower"]]["name"]), E["col"], 6.0)
        else:
            self.pop("%s is open for you all year now   (out of season the prize is a RIPOFF)" % E["name"], E["col"], 6.0)
        self.chat_add("", E["col"], "Event unlocked: %s. Find it under EVENTS on the main menu." % E["name"])
        self.check_titles()
        self.store()
        return True

    def check_titles(self, quiet=False):
        sv = self.save
        got = set(sv["titles"])
        st = sv["stars"]
        want = {"rookie"}
        if sv["stats"]["wins"] > 0:
            want.add("defender")
        for m in MAIN_MAPS:
            if st.get("%s:insane" % m["id"]):
                want.add("m_" + m["id"])
        for d, tid in (("normal", "veteran"), ("hard", "hardliner"), ("insane", "insane")):
            if all(st.get("%s:%s" % (m["id"], d)) for m in MAIN_MAPS):
                want.add(tid)
        if any(st.get("%s:insane" % m["id"]) == 3 for m in MAIN_MAPS):
            want.add("flawless")
        if sv["stats"].get("mpwins", 0) > 0:
            want.add("team")
        if len(set(sv["npcs"])) >= 12:
            want.add("chatter")
        if self.level() >= 30:
            want.add("legend")
        for ev, E in EVENTS.items():
            if sv["edone"].get(ev):
                want.add(E["title"])
        if all(ev in sv["events"] for ev, E in EVENTS.items() if E["kind"] == "secret"):
            want.add("secrets")
        new = [k for k in TITLE_ORDER if k in want and k not in got]
        if new:
            sv["titles"] = [k for k in TITLE_ORDER if k in want or k in got]
            if not quiet:
                for k in new:
                    self.pop("NEW TITLE:  " + TITLES[k][0], GOLD, 4.0)
        return new

    def new_demo(self):
        m = random.choice(MAIN_MAPS)
        lo = random.sample(["blaster", "blade", "scatter", "sentinel", "tesla", "hydra", "guardian"], 3) + ["rail", "mortar", "cryo"]
        self.demo = World(m["id"], "normal", [dict(name="", loadout=lo, perks=["overcharge"], abils=[random.choice(ABIL_ORDER)])])
        self.demo.players[0].cash = 2500
        self.demo.numbers = False
        self.demo_bot = Bot(self.demo, random.randrange(999))
        self.demo_cam = random.uniform(0, TAU)

    # ------------------------------------------------------------ main loop
    def run(self):
        while self.running:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            self.frame(pygame.event.get(), dt)
        self.leave_net()
        self.store()
        if self.upd is not None:
            self.upd.close()
        pygame.quit()

    def frame(self, events, dt):
        self.dt = dt
        self.time += dt
        self.click = self.rclick = False
        self.pressed = set()
        self.typed = ""
        self.wheel = 0
        rx = ry = 0
        for ev in events:
            et = ev.type
            if et == pygame.QUIT:
                self.running = False
            elif et == pygame.MOUSEMOTION:
                pos = self.mpos(ev.pos)
                rx += pos[0] - self.mouse[0]
                ry += pos[1] - self.mouse[1]
                self.mouse = pos
            elif et == pygame.MOUSEBUTTONDOWN:
                self.mouse = self.mpos(ev.pos)
                if ev.button == 1:
                    self.click = True
                    self.mdown = True
                elif ev.button == 3:
                    self.rdown = True
                    self.rdrag = 0.0
            elif et == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    self.mdown = False
                    self.drag = None
                elif ev.button == 3:
                    if self.rdown and self.rdrag < 7:
                        self.rclick = True
                    self.rdown = False
            elif et == pygame.MOUSEWHEEL:
                # some mice and touchpads send many tiny steps, some send big jumps: both end up as smooth zoom
                v = getattr(ev, "precise_y", None)
                self.wheel += v if isinstance(v, float) and v != 0.0 else ev.y
            elif et == pygame.KEYDOWN:
                self.pressed.add(ev.key)
                self.held.add(ev.key)
                ch = getattr(ev, "unicode", "")
                if ch and len(ch) == 1 and 32 <= ord(ch) < 127:
                    self.typed += ch
                if ev.key == pygame.K_F11:
                    self.toggle_fullscreen()
            elif et == pygame.KEYUP:
                self.held.discard(ev.key)
            elif et == getattr(pygame, "WINDOWFOCUSLOST", -1):
                self.held.clear()
                self.rdown = False
        self.mrel = (rx, ry)
        self.wheel = clamp(self.wheel, -4.0, 4.0)
        # holding BACKSPACE keeps deleting
        if pygame.K_BACKSPACE in self.held:
            self.bk_t += dt
            if self.bk_t > 0.42:
                self.bk_t -= 0.05
                self.pressed.add(pygame.K_BACKSPACE)
        else:
            self.bk_t = 0.0
        if self.rdown:
            self.rdrag += abs(rx) + abs(ry)
        self.shift = pygame.K_LSHIFT in self.held or pygame.K_RSHIFT in self.held
        s = self.s
        if self.net and self.state != "play":
            self.net_idle()
        self.upd_tick()
        getattr(self, "screen_" + self.state)(s)
        if self.toast is None and self.toasts:
            self.toast = self.toasts.pop(0)
        if self.toast:
            self.toast[2] -= dt
            sz = 22 if len(self.toast[0]) < 70 else 18
            r = pygame.Rect(0, 0, font(sz).size(self.toast[0])[0] + 48, 42)
            r.midtop = (W // 2, 70)
            panel(s, r, PANEL, 240, self.toast[1], 10, 2)
            draw_text(s, self.toast[0], sz, WHITE, r.centerx, r.centery)
            if self.toast[2] <= 0:
                self.toast = None
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt * 4)
            if self.fade > 0.02:
                ov = pygame.Surface((W, H))
                ov.fill(BG)
                ov.set_alpha(int(255 * self.fade))
                s.blit(ov, (0, 0))
        if self.save["settings"]["fps"]:
            if dt > 0:
                self.fps_show += (1 / dt - self.fps_show) * 0.05
            draw_text(s, "%d FPS" % self.fps_show, 16, GREY, W - 8, H - 10, "r")
        self.present()

    # ------------------------------------------------------------ the window
    def make_window(self, full):
        """open the window again, windowed or fullscreen.  The picture is fitted to it by present()."""
        scr = None
        if full:
            try:
                scr = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except Exception:
                scr = None
        if scr is None:
            dw, dh = self.desk
            k = min((dw * 0.92) / W, (dh * 0.84) / H) if (dw >= 400 and dh >= 300) else 1.0
            k = 2.0 if k >= 2.0 else 1.5 if k >= 1.5 else 1.0 if k >= 1.0 else max(0.4, k)
            if os.environ.get("NB_WINDOW") == "1":
                k = 1.0
            try:
                scr = pygame.display.set_mode((int(W * k), int(H * k)), pygame.RESIZABLE)
            except Exception:
                scr = pygame.display.set_mode((W, H))
        self.screen = scr
        self.fit()

    def fit(self):
        """work out where the 1280 x 720 picture sits inside the window (as big as fits, never cut off)"""
        sw, sh = self.screen.get_size()
        self.win_size = (sw, sh)
        k = min(sw / float(W), sh / float(H))
        if 1.0 <= k < 1.04:
            k = 1.0
        elif 2.0 <= k < 2.06:
            k = 2.0
        k = max(0.1, k)
        self.vk = k
        self.vw, self.vh = max(1, int(round(W * k))), max(1, int(round(H * k)))
        self.vx, self.vy = (sw - self.vw) // 2, (sh - self.vh) // 2

    def mpos(self, pos):
        """where the mouse is on the 1280 x 720 picture"""
        if self.vk == 1.0 and not self.vx and not self.vy:
            return (int(pos[0]), int(pos[1]))
        return (int((pos[0] - self.vx) / self.vk), int((pos[1] - self.vy) / self.vk))

    def present(self):
        scr = pygame.display.get_surface()
        if scr is None:
            return
        if scr is not self.screen or scr.get_size() != self.win_size:
            self.screen = scr
            self.fit()
        if self.vw == W and self.vh == H:
            if self.vx or self.vy:
                scr.fill((0, 0, 0))
            scr.blit(self.canvas, (self.vx, self.vy))
        else:
            if self.vx or self.vy:
                scr.fill((0, 0, 0))
            try:
                dst = scr.subsurface((self.vx, self.vy, self.vw, self.vh))
                if self.vk == 2.0:
                    pygame.transform.scale(self.canvas, (self.vw, self.vh), dst)
                else:
                    pygame.transform.smoothscale(self.canvas, (self.vw, self.vh), dst)
            except Exception:
                scr.blit(pygame.transform.scale(self.canvas, (self.vw, self.vh)), (self.vx, self.vy))
        pygame.display.flip()

    def toggle_fullscreen(self):
        st = self.save["settings"]
        st["fullscreen"] = not st["fullscreen"]
        try:
            self.make_window(st["fullscreen"])
        except Exception:
            st["fullscreen"] = False
            self.make_window(False)

    # ------------------------------------------------------------ widgets
    def button(self, key, rect, label, col=CYAN, size=26, enabled=True, sub=None, fill=None, alpha=None):
        s = self.s
        hov = enabled and not self.lock and rect.collidepoint(self.mouse)
        h = self.hover.get(key, 0.0)
        h += ((1.0 if hov else 0.0) - h) * min(1.0, self.dt * 16)
        self.hover[key] = h
        c = col if enabled else (58, 64, 96)
        r = rect.inflate(int(h * 6), int(h * 4))
        if alpha is not None:
            panel(s, r, mix_col(fill or PANEL, c, 0.10 + 0.24 * h), alpha, mix_col(c, WHITE, h * 0.4), 10, 2)
        else:
            pygame.draw.rect(s, mix_col(fill or PANEL, c, 0.10 + 0.24 * h), r, border_radius=10)
            pygame.draw.rect(s, mix_col(c, WHITE, h * 0.4), r, 2, border_radius=10)
        tc = WHITE if enabled else DIM
        if sub:
            draw_text(s, label, size, tc, r.centerx, r.centery - 9 - (size - 26) // 5)
            draw_text(s, sub, 16, mix_col(c, WHITE, 0.3) if enabled else DIM, r.centerx, r.centery + 13 + (size - 26) // 2)
        else:
            draw_text(s, label, size, tc, r.centerx, r.centery)
        if hov and self.click:
            self.click = False
            self.audio.play("click")
            return True
        return False

    def slider(self, key, rect, val):
        s = self.s
        if self.click and rect.inflate(16, 20).collidepoint(self.mouse) and not self.lock:
            self.drag = key
            self.click = False
        if self.drag == key and self.mdown:
            val = clamp((self.mouse[0] - rect.x) / float(rect.w), 0.0, 1.0)
        pygame.draw.rect(s, (24, 30, 60), rect, border_radius=6)
        fr = pygame.Rect(rect.x, rect.y, int(rect.w * val), rect.h)
        pygame.draw.rect(s, CYAN, fr, border_radius=6)
        pygame.draw.circle(s, WHITE, (rect.x + int(rect.w * val), rect.centery), 10)
        return val

    def textbox(self, key, rect, txt, maxlen=14, hint="", size=28, allow=None):
        """a box you can type in.  Click it first.  -> the new text"""
        s = self.s
        on = self.focus == key
        if self.click and not self.lock:
            if rect.collidepoint(self.mouse):
                self.focus = key
                self.click = False
                on = True
            elif on:
                self.focus = None
                on = False
        if on:
            for ch in self.typed:
                if len(txt) < maxlen and (allow is None or ch in allow):
                    txt += ch
            if pygame.K_BACKSPACE in self.pressed:
                txt = txt[:-1]
        pygame.draw.rect(s, (16, 20, 44), rect, border_radius=8)
        pygame.draw.rect(s, CYAN if on else LINE, rect, 2, border_radius=8)
        if txt:
            r = draw_text(s, txt, size, WHITE, rect.x + 14, rect.centery, "l")
            cx = r.right + 3
        else:
            draw_text(s, hint, size - 6, DIM, rect.x + 14, rect.centery, "l")
            cx = rect.x + 14
        if on and (self.time * 2) % 2 < 1.2:
            pygame.draw.line(s, WHITE, (cx, rect.y + 8), (cx, rect.bottom - 8), 2)
        return txt

    def back_button(self, to=None):
        if self.button("back", pygame.Rect(28, 24, 120, 44), "< BACK", GREY, 24) or (pygame.K_ESCAPE in self.pressed and self.focus is None):
            self.goto(to or self.back_to)
            return True
        return False

    def header(self, title, wallet=True, col=CYAN):
        s = self.s
        draw_glow_text(s, title, 56, col, W // 2, 48)
        if wallet:
            self.wallet(W - 30, 34)

    TAB_GROUPS = (
        (("maps", "MAPS", GREEN, "PICK A MAP"), ("events", "EVENTS", ORANGE, "EVENTS"), ("videos", "TUTORIALS", PINK, "TUTORIALS")),
        (("towers", "TOWERS", CYAN, "TOWERS"), ("perks", "PERKS", PURPLE, "PERKS")),
        (("titles", "TITLES", GOLD, "TITLES"), ("customize", "COLOUR + CORE", CYAN, "COLOUR + CORE"), ("name", "NAME", MINT, "NAME")),
        (("settings", "SETTINGS", CYAN, "SETTINGS"), ("help", "HOW TO PLAY", MINT, "HOW TO PLAY"), ("changelog", "WHAT'S NEW", GOLD, "WHAT'S NEW"),
         ("updates", "UPDATES", GREEN, "UPDATES"), ("controls", "CONTROLS", PURPLE, "CONTROLS")),
    )

    def tab_header(self, cur, wallet=True):
        """the top of a screen that shares a tab with others: a row of tabs instead of one title.
        -> True when you just clicked over to another tab (the screen should stop drawing)"""
        s = self.s
        grp = None
        for gr in self.TAB_GROUPS:
            for t in gr:
                if t[0] == cur:
                    grp, me = gr, t
        if wallet:
            self.wallet(W - 30, 34)
        if grp is None:
            return False
        # inside a Wi-Fi room or a paused match only the page you asked for is shown
        if not (self.back_to in ("menu", "lobby") or (self.back_to == "room" and cur in ("towers", "perks"))):
            draw_glow_text(s, me[3], 56, me[2], W // 2, 48)
            return False
        ws = [max(150, font(24).size(t[1])[0] + 52) for t in grp]
        x = W // 2 - (sum(ws) + 10 * (len(ws) - 1)) // 2
        for (key, lab, col, _), w in zip(grp, ws):
            r = pygame.Rect(x, 24, w, 46)
            x += w + 10
            if key == cur:
                pygame.draw.rect(s, mix_col(PANEL, col, 0.22), r, border_radius=10)
                pygame.draw.rect(s, col, r, 2, border_radius=10)
                pygame.draw.rect(s, col, (r.x + 16, r.bottom + 5, r.w - 32, 3), border_radius=2)
                draw_text(s, lab, 25, WHITE, r.centerx, r.centery)
            elif self.button("tab_" + key, r, lab, mix_col(col, GREY, 0.55), 22):
                self.store()
                if key == "name":
                    self.name_buf = self.save["name"]
                self.goto(key)
                return True
        return False

    def wallet(self, x, y):
        s = self.s
        lv, into = level_of(self.save["xp"])
        r = draw_text(s, "%d" % self.save["coins"], 32, GOLD, x, y, "r")
        pygame.draw.circle(s, GOLD, (r.x - 16, y), 10)
        pygame.draw.circle(s, scale_col(GOLD, 0.5), (r.x - 16, y), 6)
        draw_text(s, "LEVEL %d" % lv, 20, WHITE, x, y + 28, "r")
        bar = pygame.Rect(x - 190, y + 22, 100, 10)
        pygame.draw.rect(s, (24, 30, 60), bar, border_radius=5)
        pygame.draw.rect(s, CYAN, (bar.x, bar.y, int(bar.w * min(1.0, into / float(xp_need(lv)))), bar.h), border_radius=5)

    def chip(self, txt, col, x, y, size=15):
        s = self.s
        w = font(size).size(txt)[0] + 14
        r = pygame.Rect(x, y - 10, w, 20)
        pygame.draw.rect(s, scale_col(col, 0.22), r, border_radius=6)
        pygame.draw.rect(s, col, r, 1, border_radius=6)
        draw_text(s, txt, size, col, r.centerx, r.centery)
        return r.right + 6

    def dim(self, s, a=150):
        ov = pygame.Surface((W, H))
        ov.fill((4, 5, 14))
        ov.set_alpha(a)
        s.blit(ov, (0, 0))

    def tower_icon(self, kind, cx, cy, scale=1.5, lv=0, spin=0.35, dimmed=False):
        m = tower_model(kind, lv)
        col = self.tcol(kind)
        if dimmed:
            col = scale_col(col, 0.35)
        self.scene.icon(self.s, m, col, cx, cy + m.top * scale * 0.22, scale, self.time, spin)

    def enemy_icon(self, kind, cx, cy, scale=1.2, skin=None):
        E = ENEMIES[kind]
        m = enemy_model(E.get("model", kind), skin)
        self.scene.icon(self.s, m, E["col"], cx, cy + m.top * scale * 0.2, scale, self.time, 0.5)

    def chat_add(self, name, col, text, title=""):
        """a new line for the chat.  name "" = the game itself is talking.  What a player says goes through the word filter.
        -> how many words were blocked in it"""
        n = 0
        if name:
            text, n = censor(clean_chat(text, CHAT_MAX + 16))
            name = safe_name(name) or "PLAYER"
        else:
            text = clean_name(text, 110)
        try:
            col = (int(col[0]), int(col[1]), int(col[2]))
        except Exception:
            col = WHITE
        self.chat.append([name, col, text, self.time, clean_name(title, 24), None])
        del self.chat[:-40]
        return n


    # ------------------------------------------------------------ starting a match
    def start_game(self, mapid, diff, specs=None, seed=None, me=0):
        """a match that runs on this computer (alone, or as the Wi-Fi host)"""
        self.world = World(mapid, diff, [self.safe_spec(sp) for sp in (specs or [self.my_spec()])], seed)
        self.world.net = self.net is not None and self.net[0] == "host"
        self.me = me
        self.begin_match()

    def start_guest(self, mapid, diff, specs, me):
        specs = [self.safe_spec(sp) for sp in specs]
        self.world = GuestWorld(mapid, diff, specs)
        self.me = clamp(me, 0, len(specs) - 1)
        self.world.players[self.me].local = True
        self.begin_match()

    def safe_spec(self, sp):
        """what a player brings into a match, with a name everybody may read"""
        sp = dict(sp) if isinstance(sp, dict) else {}
        if sp.get("name") and safe_name(sp.get("name")) != clean_name(sp.get("name")):
            sp["name"] = "PLAYER"
        return sp

    def begin_match(self):
        w = self.world
        sv = self.save
        self.build = None
        self.sel = None
        self.hov = None
        self.aim = None
        self.speed = 1
        self.paused = False
        self.reward = None
        self.auto_t = 0.0
        self.over_t = 0.0
        self.card_t = 0.0
        self.msg = None
        self.talk = None
        self.typing = None
        self.knocks = 0
        self.cine = False
        self.over_net = False
        self.hud_rects = []
        self.hov_slot = None
        P = w.players[self.me]
        self.cash_show = float(P.cash)
        self.cyaw, self.cpitch, self.cdist = -math.pi / 2, 0.98, 700.0
        self.cdist_t = 700.0            # the zoom glides towards this
        self.z2 = 1.0                   # zoom of the flat 2D view, and the spot it looks at
        self.p2 = [FW / 2.0, FH / 2.0]
        self.stuck_t = 0.0
        self.pass_t = 0.0
        self.hov_e = None
        self.hov_p = None
        self.jump_z = self.jump_v = 0.0
        self.sprint_t = 0.0
        self.mp_neg = False
        self.ctx, self.cty, self.ctz = P.x, P.y, 0.0
        w.numbers = sv["settings"]["numbers"]
        sv["stats"]["games"] += 1
        self.store()
        self.goto("play")
        if not self.net:
            self.chat = []
        if "tip_move" not in sv["seen"] and sv["settings"]["view3d"]:
            sv["seen"].append("tip_move")
            self.chat_add("", GREY, "%s moves you, %s sprints, %s jumps. Hold RIGHT mouse and drag to turn the camera." %
                          (self.kmove(), self.kname("sprint"), self.kname("jump")))
            self.chat_add("", GREY, "Scroll zooms. %s is the flat 2D view. Walk up to people with a ! and press %s to talk." %
                          (self.kname("view"), self.kname("talk")))

    def leave_net(self):
        if self.net:
            try:
                if self.net[0] == "host":
                    self.net[1].close()
                else:
                    self.net[1].close()
            except Exception:
                pass
        self.net = None
        if self.finder is not None:
            self.finder.close()
            self.finder = None
        self.room = None

    def act(self, *a):
        if self.net and self.net[0] == "guest":
            self.net[1].send(dict(t="act", a=list(a)))
            return True
        return self.world.apply(self.me, a)

    # ------------------------------------------------------------ things the player does
    def pick_build(self, kind):
        w = self.world
        P = w.players[self.me]
        self.aim = None
        self.sel = None
        if self.build == kind:
            self.build = None
            return
        lim = w.limit_check(P, kind)
        if lim:
            self.say(lim)
            self.audio.play("error")
        else:
            self.build = kind

    def target_tower(self, need_mine=True, ghost_ok=False):
        w = self.world
        t = self.sel if self.sel is not None else self.hov
        if t is None or (t not in w.towers and t not in w.plans):
            self.say("Point at one of your towers first", GREY)
            return None
        if need_mine and t.owner is not w.players[self.me]:
            self.say("That is %s's tower. Only they can manage it." % t.owner.name, GREY)
            return None
        if t.ghost and not ghost_ok:
            self.say("That one is only planned. It builds itself when you have %d cash.  (%s cancels it)" % (w.cost(t.owner, t.kind), self.kname("sell")), GOLD)
            return None
        return t

    def do_upgrade(self):
        w = self.world
        t = self.target_tower()
        if t is None:
            return
        c = w.up_cost(t)
        if c is None:
            self.say("%s is already max level" % t.owner.tname(t.kind), GOLD)
        elif t.owner.cash < c:
            self.say("Need %d cash to upgrade" % c)
            self.audio.play("error")
        else:
            self.act("up", t.id)

    def do_sell(self):
        t = self.target_tower(True, True)
        if t is not None:
            self.act("sell", t.id)
            if self.sel is t:
                self.sel = None

    def do_skip(self):
        w = self.world
        why = w.skip_why()
        if why:
            self.say(why, GREY)
            self.audio.play("error", 0.6)
        else:
            self.act("skip")

    def do_mode(self):
        t = self.target_tower()
        if t is not None:
            if TOWERS[t.kind]["atk"] in ("RANGED", "MELEE", "BOTH"):
                self.act("mode", t.id)
            else:
                self.say("%s does not pick targets" % t.owner.tname(t.kind), GREY)

    def do_ability(self):
        w = self.world
        P = w.players[self.me]
        t = self.sel if self.sel is not None else self.hov
        if t is None or t.kind != "commander" or t.owner is not P:
            ready = [c for c in w.towers if c.kind == "commander" and c.owner is P and c.acd <= 0 and c.act <= 0]
            t = ready[0] if ready else None
        if t is None:
            self.say("No tower ability ready (the Commander has one)", GREY)
        elif w.phase != "wave":
            self.say("Abilities only work during a wave", GREY)
        elif t.acd > 0 or t.act > 0:
            self.say("Call to Arms is recharging", GREY)
        else:
            self.act("tabil", t.id)

    def toggle_aim(self, slot):
        w = self.world
        P = w.players[self.me]
        if slot >= len(P.abils):
            self.say("No ability perk in that slot. Reach level 10 for a second one.", GREY)
        elif self.aim == slot:
            self.aim = None
        elif w.phase != "wave":
            self.say("Abilities only work during a wave", GREY)
        elif P.acd[slot] > 0:
            self.say("%s ready in %ds" % (ABILS[P.abils[slot]]["name"], math.ceil(P.acd[slot])), GREY)
        else:
            self.aim = slot
            self.build = None

    def set_speed(self, v=None):
        if self.net and self.net[0] == "guest":
            self.say("Only the host can change the speed", GREY)
            return
        self.speed = v if v else self.speed % 3 + 1

    def start_talk(self, n):
        sv = self.save
        self.talk = [n, 0]
        self.audio.play("talk")
        if n["id"] not in sv["npcs"]:
            sv["npcs"].append(n["id"])
            sv["stats"]["talks"] = sv["stats"].get("talks", 0) + 1
            self.check_titles()
            self.store()

    def next_talk(self):
        if self.talk is None:
            return
        self.talk[1] += 1
        if self.talk[1] >= len(self.talk[0]["lines"]):
            self.talk = None
        else:
            self.audio.play("talk", 0.7)

    def poke(self, o):
        """clicking a secret thing on the map"""
        sv = self.save
        w = self.world
        if o["id"].startswith("duck"):
            found = sv["quests"]["ducks"]
            if o["id"] not in found:
                found.append(o["id"])
                self.audio.play("quack")
                w.burst(o["x"], o["y"], DUCK_Y, 20, 160, 0.8, 4, 12)
                self.pop("QUACK!   (%d of 3 ducks found)" % len(found), DUCK_Y, 3.0)
                self.store()
                if len(found) >= 3:
                    self.unlock_event("pond")
            else:
                self.audio.play("quack", 0.6)
                self.say("You already found this duck. It looks proud.", DUCK_Y)
        elif o["id"] == "tomb":
            self.knocks += 1
            self.audio.play("error", 0.8)
            w.ring(o["x"], o["y"], 4, 30, PURPLE, 0.4, 2)
            if self.knocks == 3:
                if not self.unlock_event("haunted"):
                    self.say("...the Hollow is already open to you.", PURPLE)
            elif self.knocks < 3:
                self.say("knock" + " knock" * (self.knocks - 1) + "...", PURPLE)
            else:
                self.say("Not four.", PURPLE)

    def send_chat(self, text):
        text = clean_name(text, CHAT_MAX)
        if not text:
            return
        sv = self.save
        w = self.world
        name = safe_name(sv["name"]) or "YOU"
        title = TITLES[sv["title"]][0]
        # blocked words never leave this computer: they are swapped for symbols before the line is sent
        bad = self.chat_add(name, self.pcol(), text, title)
        sent = self.chat[-1][2]
        self.audio.play("censor" if bad else "chat")
        if self.net:
            if self.net[0] == "guest":
                self.net[1].send(dict(t="chat", text=sent))
            else:
                for c in self.net[1].conns.values():
                    c.send(dict(t="chat", name=name, col=list(self.pcol()), title=title, text=sent))
        if w is not None and "meow" in text.lower():
            self.audio.play("meow")
            if w.mapid == "board":
                self.unlock_event("glitch")

    # ------------------------------------------------------------ camera
    def view3d(self):
        return self.save["settings"]["view3d"]

    def set_camera(self, w, P):
        cam = self.cam
        cam.cx, cam.cy = W / 2.0, H / 2.0
        if self.cine:
            cam.ortho = False
            cam.x, cam.y, cam.z, cam.yaw, cam.pitch = self.fc
            cam.setup()
        elif self.view3d():
            cam.ortho = False
            k = min(1.0, self.dt * 9)
            self.ctx += (P.x - self.ctx) * k
            self.cty += (P.y - self.cty) * k
            self.ctz += (P.z + 6 - self.ctz) * k
            self.cdist += (self.cdist_t - self.cdist) * min(1.0, self.dt * 12)
            cam.cy = H / 2.0 + 30
            cam.look(self.ctx, self.cty, self.ctz, self.cdist, self.cyaw, self.cpitch)
        else:
            cam.flat(W / 2.0, 58 + 279, self.p2[0], self.p2[1], 0.87 * self.z2)

    def clamp2d(self):
        mx, my = FW / 2.0 * (1 - 1 / self.z2), FH / 2.0 * (1 - 1 / self.z2)
        self.p2[0] = clamp(self.p2[0], FW / 2.0 - mx, FW / 2.0 + mx)
        self.p2[1] = clamp(self.p2[1], FH / 2.0 - my, FH / 2.0 + my)

    def camera_input(self, w, P, free):
        kh = self.kh
        dt = self.dt
        sens = self.save["settings"]["sens"]
        rx, ry = self.mrel
        # zoom: the wheel, or the zoom keys
        zoom = self.wheel if not self.over_hud() else 0.0
        if free:
            if kh("zoom_in"):
                zoom += dt * 7
            if kh("zoom_out"):
                zoom -= dt * 7
        if self.cine:
            fc = self.fc
            if self.rdown or self.mdown:
                fc[3] += rx * 0.005 * sens
                fc[4] = clamp(fc[4] + ry * 0.004 * sens, -0.5, 1.5)
            cy, sy = math.cos(fc[3]), math.sin(fc[3])
            cp, sp = math.cos(fc[4]), math.sin(fc[4])
            v = (520.0 if (self.shift or kh("sprint")) else 200.0) * dt
            f = int(kh("up")) - int(kh("down"))
            sd = int(kh("right")) - int(kh("left"))
            up = int(kh("upgrade")) - int(kh("abil1"))
            fwd = f * v + zoom * 45.0       # the wheel flies forwards and backwards
            fc[0] += cy * cp * fwd - sy * sd * v
            fc[1] += sy * cp * fwd + cy * sd * v
            fc[2] = clamp(fc[2] - sp * fwd + up * v, 6.0, 1600.0)
            fc[0] = clamp(fc[0], -1200, FW + 1200)
            fc[1] = clamp(fc[1], -1200, FH + 1200)
            if kh("cam_left"):
                fc[3] -= 1.4 * dt
            if kh("cam_right"):
                fc[3] += 1.4 * dt
            if kh("cam_up"):
                fc[4] = clamp(fc[4] - 0.9 * dt, -0.5, 1.5)
            if kh("cam_down"):
                fc[4] = clamp(fc[4] + 0.9 * dt, -0.5, 1.5)
            return
        if not self.view3d():
            # the flat view: zoom towards the mouse, slide around with the walking keys / camera keys / right-drag
            if zoom:
                mx, my = self.mouse
                k0 = 0.87 * self.z2
                wx, wy = self.p2[0] + (mx - W / 2.0) / k0, self.p2[1] + (my - (58 + 279)) / k0
                self.z2 = clamp(self.z2 * (1.14 ** zoom), 1.0, 3.2)
                k1 = 0.87 * self.z2
                self.p2 = [wx - (mx - W / 2.0) / k1, wy - (my - (58 + 279)) / k1]
            if self.z2 > 1.001:
                k1 = 0.87 * self.z2
                if self.rdown:
                    self.p2[0] -= rx / k1
                    self.p2[1] -= ry / k1
                if free:
                    v = 520.0 / self.z2 * dt
                    self.p2[0] += (int(kh("right") or kh("cam_right")) - int(kh("left") or kh("cam_left"))) * v
                    self.p2[1] += (int(kh("down") or kh("cam_down")) - int(kh("up") or kh("cam_up"))) * v
            self.clamp2d()
            return
        if self.rdown:
            self.cyaw += rx * 0.006 * sens
            self.cpitch = clamp(self.cpitch + ry * 0.005 * sens, 0.3, 1.45)
        if zoom:
            self.cdist_t = clamp(self.cdist_t * (0.88 ** zoom), ZOOM_MIN, ZOOM_MAX)
        ox, oy = P.x, P.y
        want = 0.0
        tx, ty = P.x, P.y
        sprint = False
        if free:
            if kh("cam_left"):
                self.cyaw -= 1.6 * dt
            if kh("cam_right"):
                self.cyaw += 1.6 * dt
            if kh("cam_up"):
                self.cpitch = clamp(self.cpitch + 0.9 * dt, 0.3, 1.45)
            if kh("cam_down"):
                self.cpitch = clamp(self.cpitch - 0.9 * dt, 0.3, 1.45)
            f = int(kh("up")) - int(kh("down"))
            sd = int(kh("right")) - int(kh("left"))
            if f or sd:
                cy, sy = math.cos(self.cyaw), math.sin(self.cyaw)
                n = math.hypot(f, sd)
                sprint = kh("sprint")
                want = 210.0 * dt * (SPRINT_K if sprint else 1.0)
                v = want / n
                tx = clamp(P.x + (cy * f - sy * sd) * v, -40, FW + 40)
                ty = clamp(P.y + (sy * f + cy * sd) * v, -40, FH + 40)
        # orbs are solid: they slide along walls and towers, climb ramps, cross bridges and never step off an edge
        if want > 0:
            P.x, P.y, P.z = w.walk(P.x, P.y, P.z, tx, ty, ORB_R, self.pass_t <= 0)
        else:
            # standing still: a tower built on top of you nudges you aside
            px, py = w.push_out(P.x, P.y, ORB_R, self.pass_t <= 0, P.z)
            if (px != P.x or py != P.y) and w.walk_ok(px, py, w.surf(px, py, P.z)):
                P.x, P.y = px, py
            P.z = w.surf(P.x, P.y, P.z)
        if want > 0 and math.hypot(P.x - ox, P.y - oy) < want * 0.2:
            self.stuck_t += dt
            if self.stuck_t > 0.6:
                self.pass_t = 1.2       # boxed in by towers: squeeze through them rather than stay trapped
        else:
            self.stuck_t = 0.0
            if sprint:
                # sprinting leaves a short trail of sparks
                self.sprint_t -= dt
                if self.sprint_t <= 0:
                    self.sprint_t = 0.05
                    w.burst(ox, oy, mix_col(P.col, WHITE, 0.35), 1, 16, 0.38, 2, P.z + 5 + self.jump_z, False)
        if self.pass_t > 0 and not w.blocked(P.x, P.y, ORB_R, True, P.z):
            self.pass_t -= dt

    def do_jump(self, w, P):
        """a little hop: only for show (you cannot jump over anything), and never a second one in the air"""
        if self.jump_z <= 0.0 and self.jump_v == 0.0 and self.view3d():
            self.jump_v = JUMP_V
            self.audio.play("jump", 0.8)

    def jump_tick(self, w, P):
        if self.jump_v == 0.0 and self.jump_z <= 0.0:
            P.jz = 0.0
            return
        dt = min(self.dt, 0.05)
        self.jump_v -= JUMP_G * dt * 0.5
        self.jump_z += self.jump_v * dt
        self.jump_v -= JUMP_G * dt * 0.5
        if self.jump_z <= 0.0:
            self.jump_z = self.jump_v = 0.0
            self.audio.play("land", 0.7)
            w.ring(P.x, P.y, 5, 22, P.col, 0.3, 2, P.z + 1.5, False)
            w.burst(P.x, P.y, mix_col(P.col, WHITE, 0.5), 6, 55, 0.32, 2, P.z + 2, False)
        P.jz = self.jump_z

    # ------------------------------------------------------------ who is that?  (point at a player's orb)
    def pick_player(self, w, mx, my):
        """-> (the player whose orb is under the mouse, how many pixels away) or (None, 0)"""
        best, bd = None, 1e9
        for q in w.players:
            if not q.here:
                continue
            a = self.cam.pt(q.x, q.y, q.z + 15 + getattr(q, "jz", 0.0))
            if a is None:
                continue
            d = math.hypot(a[0] - mx, a[1] - my)
            if d <= max(26.0, 8.5 * a[2] + 8) and d < bd:
                best, bd = q, d
        return best, (bd if best is not None else 0.0)

    def pick_dist(self, ob, mx, my):
        """how far (in pixels) the mouse is from a tower or an enemy on the screen"""
        cam = self.cam
        if hasattr(ob, "owner"):
            a = cam.pt(ob.x, ob.y, ob.z)
            b = cam.pt(ob.x, ob.y, ob.z + tower_model(ob.kind, ob.lv).top * 0.8)
            if a is None or b is None:
                return 1e9
            dx, dy = b[0] - a[0], b[1] - a[1]
            f = clamp(((mx - a[0]) * dx + (my - a[1]) * dy) / ((dx * dx + dy * dy) or 1.0), 0.0, 1.0)
            return math.hypot(mx - (a[0] + dx * f), my - (a[1] + dy * f))
        a = cam.pt(ob.x, ob.y, ob.r * 0.8)
        return math.hypot(mx - a[0], my - a[1]) if a is not None else 1e9

    # ------------------------------------------------------------ with friends the waves start by themselves
    def mp_wave_left(self, w):
        """seconds until the next wave starts by itself (2 after a wave, 6 before the first one)"""
        d = float(globals().get("MP_WAVE_DELAY", 2.0))
        if "MP_WAVE_DELAY" in globals() and hasattr(w, "wave_in"):
            return w.wave_in() if w.phase == "build" else d       # the match rules know best
        if w.phase != "build":
            self.mp_neg = False
            return d
        if w.wave == 0:
            if w.build_t < 0:
                self.mp_neg = True      # the timer itself starts below zero for the longer first wait
            if not self.mp_neg:
                d = 6.0
                for nm in ("MP_FIRST_DELAY", "MP_FIRST_WAVE_DELAY", "MP_WAVE1_DELAY", "MP_START_DELAY"):
                    if nm in globals():
                        d = float(globals()[nm])
                        break
        return max(0.0, d - w.build_t)

    def mp_auto(self, w):
        """the host calls this every frame"""
        if len(w.players) < 2 or isinstance(w, GuestWorld):
            return
        left = self.mp_wave_left(w)
        if w.phase == "build" and left <= 0 and "MP_WAVE_DELAY" not in globals():
            w.start_wave()              # only when the match rules do not start the wave themselves

    def over_hud(self):
        mx, my = self.mouse
        for r in self.hud_rects:
            if r.collidepoint(mx, my):
                return True
        return False

    # ------------------------------------------------------------ input
    def play_input(self, w, P):
        K = pygame
        pr = self.pressed
        kp = self.kp
        if self.typing is not None:
            for ch in self.typed:
                if len(self.typing) < CHAT_MAX:
                    self.typing += ch
            if K.K_BACKSPACE in pr:
                self.typing = self.typing[:-1]
            if K.K_RETURN in pr or K.K_KP_ENTER in pr:
                self.send_chat(self.typing)
                self.typing = None
            elif K.K_ESCAPE in pr:
                self.typing = None
            self.camera_input(w, P, False)
            return
        if K.K_p in pr and self.shift:      # SHIFT + P is always the film camera
            self.cine = not self.cine
            if self.cine:
                cam = self.cam
                self.fc = [cam.x, cam.y, max(20.0, cam.z), cam.yaw, cam.pitch] if not cam.ortho else [FW / 2.0, FH + 260.0, 300.0, -math.pi / 2, 0.55]
                self.build = self.aim = None
            return
        if self.cine:
            if K.K_ESCAPE in pr:
                self.cine = False
            self.camera_input(w, P, True)
            return
        if kp("chat"):
            if self.talk:
                self.next_talk()
            else:
                self.typing = ""
            return
        if K.K_ESCAPE in pr:
            if self.talk:
                self.talk = None
            elif self.build or self.aim is not None or self.sel:
                self.build = None
                self.aim = None
                self.sel = None
            else:
                self.paused = True
                pr.discard(K.K_ESCAPE)      # or the menu would see the same key press and close again at once
            return
        if kp("pause"):
            self.paused = True
            pr.discard(self.key_of("pause"))
            return
        if kp("view"):
            st = self.save["settings"]
            st["view3d"] = not st["view3d"]
            self.pop("3D VIEW" if st["view3d"] else "2D VIEW  (top down)", CYAN, 1.4)
        self.camera_input(w, P, True)
        if kp("jump"):
            self.do_jump(w, P)
        if kp("skip"):
            self.do_skip()
        for i, kind in enumerate(P.loadout):
            if kp("slot%d" % (i + 1)):
                self.pick_build(kind)
        if kp("start"):
            if w.phase != "build":
                if not self.net:
                    self.set_speed()        # alone, while a wave runs, the same key changes the speed
            elif len(w.players) > 1:
                self.say("With friends the next wave starts by itself", GREY)
            else:
                self.act("ready")
        if kp("speed"):
            self.set_speed()
        if kp("abil1"):
            self.toggle_aim(0)
        if kp("abil2"):
            self.toggle_aim(1)
        if kp("tabil"):
            self.do_ability()
        if kp("upgrade"):
            self.do_upgrade()
        if kp("mode"):
            self.do_mode()
        if kp("sell"):
            self.do_sell()
        if kp("talk"):
            if self.talk:
                self.next_talk()
            else:
                best, bd = None, 110 * 110 if self.view3d() else 1e12
                for n in w.npcs:
                    d = (n["x"] - P.x) ** 2 + (n["y"] - P.y) ** 2
                    if d < bd:
                        best, bd = n, d
                if best is not None:
                    self.start_talk(best)
                else:
                    self.say("Nobody is close enough to talk to", GREY)
        if self.rclick:
            self.build = None
            self.aim = None
            self.sel = None
            self.talk = None
        if self.click and not self.over_hud():
            self.click = False
            g = self.gpos
            if self.talk:
                self.next_talk()
            elif self.aim is not None:
                if g is None:
                    self.say("Aim at the ground")
                else:
                    self.act("abil", self.aim, g[0], g[1])
                    self.aim = None
            elif self.build:
                kind = self.build
                if g is None:
                    return
                lim = w.limit_check(P, kind)
                ok, why, x, y = w.place_check(kind, g[0], g[1])
                if lim or not ok:
                    self.say(lim or why or "Can't build there")
                    self.audio.play("error")
                else:
                    if P.cash < w.cost(P, kind):
                        self.say("PLANNED: it builds itself as soon as you have %d cash.  (%s on it cancels)" % (w.cost(P, kind), self.kname("sell")), GOLD)
                    self.act("build", kind, x, y, 1)
                    if not self.shift:
                        self.build = None
            else:
                n = self.scene.pick_thing(w.npcs, self.cam, self.mouse[0], self.mouse[1], 22)
                sc = self.scene.pick_thing([m for m in w.marks if m["secret"]], self.cam, self.mouse[0], self.mouse[1], 14, 12)
                if self.hov is not None:
                    self.sel = None if self.sel is self.hov else self.hov
                elif n is not None:
                    self.start_talk(n)
                elif sc is not None:
                    self.poke(sc)
                else:
                    self.sel = None

    # ------------------------------------------------------------ Wi-Fi
    def host_pump(self, w):
        Hh = self.net[1]
        Hh.accept()
        for c in Hh.new:
            c.send(dict(t="no", why="That game has already started"))
            c.pump()
            c.close()
        Hh.new = []
        for pid, c in list(Hh.conns.items()):
            for m in c.pump():
                t = m.get("t")
                if t == "act":
                    a = m.get("a")
                    if isinstance(a, list) and a:
                        w.apply(pid, a)
                elif t == "chat":
                    text = clean_chat(m.get("text", ""), CHAT_MAX + 16)
                    if text and 0 <= pid < len(w.players):
                        q = w.players[pid]
                        bad = self.chat_add(q.name, q.col, text, q.title)       # filtered again here, whatever the sender did
                        text = self.chat[-1][2]
                        self.audio.play("censor2" if bad else "chat")
                        for p2, c2 in Hh.conns.items():
                            if p2 != pid:
                                c2.send(dict(t="chat", name=q.name, col=list(q.col), title=q.title, text=text))
            if c.dead:
                del Hh.conns[pid]
                if 0 <= pid < len(w.players):
                    q = w.players[pid]
                    q.here = False
                    q.ready = True
                    self.chat_add("", GREY, "%s left the game" % q.name)
                    if w.phase == "cards" and q.offer:
                        w.pick_card(q, 0)
        self.net_t -= self.dt
        if self.net_t <= 0:
            self.net_t = 1.0 / SNAP_HZ
            fx = w.fxlog
            w.fxlog = []
            # the others see your orb where it is drawn: in the air while you jump
            me = w.players[self.me] if 0 <= self.me < len(w.players) else None
            jz = self.jump_z if me is not None else 0.0
            if jz:
                me.z += jz
            try:
                for pid, c in Hh.conns.items():
                    c.send(world_snap(w, pid, fx))
            finally:
                if jz:
                    me.z -= jz

    def guest_pump(self, w, P):
        c = self.net[1]
        for m in c.pump():
            t = m.get("t")
            try:
                if t == "snap":
                    w.apply_snap(m)
                elif t == "chat":
                    self.got_chat(m)
                elif t == "bye":
                    c.close()
                elif t == "room":
                    self.room = m
                    self.me_room = int(m.get("you", 0))
                elif t == "start":
                    self.start_guest(m["map"], m["diff"], m["specs"], int(m["me"]))
                    return
            except Exception:
                pass
        if c.dead and not self.over_net:
            self.over_net = True
            if w.phase != "over":
                w.phase = "over"
                w.result = "lose"
                self.say("The host left the game", RED, 5)
        self.pos_t -= self.dt
        if self.pos_t <= 0 and not c.dead:
            self.pos_t = 0.1 if self.jump_z <= 0 else 0.03          # more often in the air, so the jump looks smooth to the others
            c.send(dict(t="act", a=["pos", int(P.x), int(P.y), int(P.z + self.jump_z)]))

    def got_chat(self, m):
        """a guest got a chat line from the host"""
        name = clean_name(m.get("name", "?")) or "?"
        bad = self.chat_add(name, tuple(m.get("col", WHITE))[:3], clean_chat(m.get("text", ""), CHAT_MAX + 16), str(m.get("title", ""))[:24])
        self.audio.play("censor2" if bad else "chat")

    # ------------------------------------------------------------ one frame of a match
    def screen_play(self, s):
        w = self.world
        if w is None:
            # no match to show (should not happen): go back to the lobby instead of crashing
            self.back_to = "lobby"
            self.goto("lobby")
            return
        st = self.save["settings"]
        P = w.players[self.me]
        guest = isinstance(w, GuestWorld)
        overlay = self.paused or w.phase == "over" or (w.phase == "cards" and P.offer)
        self.set_camera(w, P)
        mx, my = self.mouse
        self.gpos = None if (self.cine or overlay) else self.scene.ground_pick(w, self.cam, mx, my)
        self.hov = None
        self.hov_e = None
        self.hov_p = None
        if not overlay and not self.cine and not self.over_hud() and not self.build and self.aim is None:
            self.hov = self.scene.pick_tower(w, self.cam, mx, my)
            if self.hov is None:
                self.hov_e = self.scene.pick_enemy(w, self.cam, mx, my)
            if self.view3d():
                # a player's orb: it wins unless a tower or an enemy is closer to the mouse
                q, d = self.pick_player(w, mx, my)
                other = self.hov if self.hov is not None else self.hov_e
                if q is not None and (other is None or self.pick_dist(other, mx, my) > d):
                    self.hov_p = q
                    self.hov = None
                    self.hov_e = None
        if not overlay:
            self.play_input(w, P)
        self.jump_tick(w, P)
        # ---- the match moves on
        if guest:
            if self.net:
                self.guest_pump(w, P)
            w.update(self.dt)
        else:
            if self.net:
                self.host_pump(w)
            if not self.paused or self.net:
                for _ in range(self.speed):
                    w.update(min(self.dt, 1 / 30.0))
                self.mp_auto(w)
            if w.phase == "build" and st["auto"] and not self.net:
                self.auto_t += self.dt
                if self.auto_t > 3.0:
                    w.ready(P)
            else:
                self.auto_t = 0.0
        for name, vol in w.ev:
            self.audio.play(name, vol)
        del w.ev[:]
        for q in list(w.flags):
            ev = QUEST_EVENT.get(q)
            if ev and ev not in self.save["events"]:
                self.unlock_event(ev)
        if self.sel is not None and self.sel not in w.towers and self.sel not in w.plans:
            self.sel = None
        if self.hov is not None and self.hov not in w.towers and self.hov not in w.plans:
            self.hov = None
        if self.hov_e is not None and (self.hov_e.dead or self.hov_e not in w.enemies):
            self.hov_e = None
        if self.hov_p is not None and not self.hov_p.here:
            self.hov_p = None
        if w.phase == "over" and self.reward is None:
            self.finish_game()
        if w.phase != "cards":
            self.card_t = 0.0
        # ---- draw
        self.set_camera(w, P)
        o = dict(t=w.time, detail=st["detail"], me=P, hover=self.hov, sel=self.sel, ranges=st["ranges"], boxes=st["boxes"], names=st["names"],
                 players=True, core_col=w.players[0].col, core_skin=self.save["skin"], seen=self.save["npcs"], shake=st["shake"] and not self.paused,
                 orb=(P.x, P.y), ehp=st["ehp"], ehover=self.hov_e)
        if self.build and self.gpos is not None and not overlay:
            kind = self.build
            ok, why, x, y = w.place_check(kind, self.gpos[0], self.gpos[1])
            lim = w.limit_check(P, kind)
            good = ok and not lim
            poor = P.cash < w.cost(P, kind)
            if is_path(kind):
                ri = w.road_info(x, y)
                z = w.paths[ri[1]].zat(ri[2])
                rng = TOWERS[kind]["lv"][0].get("rng", 0)
            else:
                z = w.height(x, y)
                rel = w.rel.get((int(x // CELL), int(y // CELL)), 0.0)
                mbr = w.map.get("buff", {}).get(kind, {}).get("rng", 0)
                rng = TOWERS[kind]["lv"][0].get("rng", 0) * (1 + P.mods["rng"] + mbr + ((CLIFF_RANGE * (1.0 + 0.5 * max(0.0, rel / STEP - 1.0)) + P.mods["cliffrng"]) if rel >= 13 else 0))
            o["ghost"] = (kind, x, y, good, GOLD if (good and poor) else P.tcol(kind), rng, z)
            self.ghost_why = lim or ("" if ok else why)
        else:
            self.ghost_why = ""
        if self.aim is not None and self.gpos is not None and not overlay and self.aim < len(P.abils):
            ab = P.abils[self.aim]
            o["aim"] = (ab, self.gpos[0], self.gpos[1], ABILS[ab]["rad"] * (1 + P.mods["splash"] * 0.5))
        self.scene.draw(s, w, self.cam, o)
        self.hud_rects = []
        if self.cine:
            draw_text(s, "CINEMATIC   -   %s fly    %s / %s down / up    drag the mouse to look    SHIFT faster    SHIFT + P to leave" %
                      (self.kmove(), self.kname("abil1"), self.kname("upgrade")), 16, GREY, W // 2, H - 16)
            if w.phase == "over" and self.over_t > 3:
                self.cine = False
            self.draw_banner(s, w)
            return
        self.draw_banner(s, w)
        self.lock = bool(overlay)
        self.draw_hud(s, w, P)
        self.lock = False
        if w.phase == "cards" and P.offer:
            self.draw_cards(s, w, P)
        elif w.phase == "over":
            self.draw_over(s, w)
        elif self.paused:
            self.draw_pause(s, w)

    def draw_banner(self, s, w):
        b = w.banner
        if b:
            f = b[2] / b[3]
            y = 150 - ease_out(min(1.0, (1 - f) * 5)) * 20
            if f > 0.25:
                draw_glow_text(s, b[0], 60, b[1], W // 2, y)
            else:
                draw_text(s, b[0], 60, scale_col(b[1], 0.3 + f * 2), W // 2, y)
        e = w.boss
        if e is not None and not e.dead and not self.cine:
            r = pygame.Rect(W // 2 - 260, 66, 520, 16)
            pygame.draw.rect(s, (30, 10, 18), r, border_radius=6)
            f = clamp(e.hp / float(e.max), 0.0, 1.0)
            pygame.draw.rect(s, e.col, (r.x, r.y, int(r.w * f), r.h), border_radius=6)
            if e.shield > 0:
                pygame.draw.rect(s, BLUE, (r.x, r.y - 5, int(r.w * clamp(e.shield / max(1.0, e.smax), 0, 1)), 3))
            pygame.draw.rect(s, WHITE, r, 2, border_radius=6)
            draw_text(s, "%s    %d / %d" % (e.name, max(0, e.hp), e.max), 17, WHITE, r.centerx, r.bottom + 11)

    # ------------------------------------------------------------ the HUD
    def draw_hud(self, s, w, P):
        st = self.save["settings"]
        guest = isinstance(w, GuestWorld)
        hr = self.hud_rects
        # ---- top bar
        top = pygame.Rect(0, 0, W, 54)
        hr.append(top)
        panel(s, top, (8, 10, 24), 215, LINE, 0, 0)
        pygame.draw.line(s, LINE, (0, 54), (W, 54), 2)
        draw_text(s, "WAVE", 15, DIM, 18, 13, "l")
        r = draw_text(s, "%d" % w.wave, 34, WHITE, 18, 36, "l")
        draw_text(s, "/ %d" % w.nwaves, 20, GREY, r.right + 6, 39, "l")
        draw_text(s, w.D["name"], 15, w.D["col"], 66, 13, "l")
        self.cash_show += (P.cash - self.cash_show) * min(1.0, self.dt * 12)
        draw_text(s, "CASH", 15, DIM, 176, 13, "l")
        pygame.draw.polygon(s, GOLD, poly(186, 37, 10, 4, 0))
        pygame.draw.polygon(s, scale_col(GOLD, 0.45), poly(186, 37, 5, 4, 0))
        draw_text(s, "%d" % round(self.cash_show), 34, GOLD, 204, 36, "l")
        draw_text(s, "CORE", 15, DIM, 400, 13, "l")
        bar = pygame.Rect(400, 26, 300, 20)
        f = clamp(w.hp / float(max(1, w.maxhp)), 0.0, 1.0)
        pygame.draw.rect(s, (30, 12, 20), bar, border_radius=7)
        hc = GREEN if f > 0.5 else GOLD if f > 0.25 else RED
        if w.core_hit > 0:
            hc = WHITE
        pygame.draw.rect(s, hc, (bar.x, bar.y, int(bar.w * f), bar.h), border_radius=7)
        pygame.draw.rect(s, LINE, bar, 2, border_radius=7)
        draw_text(s, "%d / %d" % (max(0, w.hp), w.maxhp), 18, WHITE, bar.centerx, bar.centery)
        if w.gm["aegis"]:
            draw_text(s, "SHIELD %d" % w.aegis, 14, BLUE, bar.right, 13, "r")
        left = w.hostiles()
        draw_text(s, "HOSTILES", 15, DIM, 730, 13, "l")
        draw_text(s, "%d" % left, 34, PINK if left else DIM, 730, 36, "l")
        draw_text(s, "SPEED", 15, DIM, 850, 13, "l")
        if guest:
            draw_text(s, "host decides", 15, GREY, 850, 36, "l")
        else:
            for i in (1, 2, 3):
                rr = pygame.Rect(850 + (i - 1) * 50, 24, 44, 24)
                if self.button("spd%d" % i, rr, "%dx" % i, GOLD if self.speed == i else GREY, 20):
                    self.speed = i
        if self.button("vw", pygame.Rect(1012, 10, 62, 36), "3D" if st["view3d"] else "2D", CYAN, 20):
            st["view3d"] = not st["view3d"]
        if self.button("pause", pygame.Rect(1084, 10, 180, 36), "MENU  (ESC)", CYAN, 18):
            self.paused = True
        # ---- a little map, top right (the 3D view cannot always see everything)
        py0 = 70
        if st["view3d"]:
            MM = pygame.Rect(W - 232, 62, 220, 136)
            hr.append(MM)
            self.draw_radar(s, w, P, MM)
            py0 = 214
        # ---- other players
        if len(w.players) > 1:
            for i, q in enumerate(w.players):
                y = py0 + i * 22
                pygame.draw.circle(s, q.col if q.here else DIM, (W - 250, y), 6)
                draw_text(s, q.name + ("  (left)" if not q.here else ""), 16, WHITE if q is P else GREY, W - 238, y, "l")
                draw_text(s, "%d" % q.cash, 16, GOLD, W - 14, y, "r")
        # ---- loadout, bottom left
        mine = w.owned(P)
        cap = w.cap()
        draw_text(s, "TOWERS %d / %d" % (mine, cap), 14, RED if mine >= cap else GREY, 14, H - 108, "l")
        self.hov_slot = None
        for i, kind in enumerate(P.loadout):
            T = TOWERS[kind]
            r = pygame.Rect(12 + i * 86, H - 98, 80, 88)
            hr.append(r)
            cost = w.cost(P, kind)
            full = bool(w.limit_check(P, kind))
            afford = P.cash >= cost and not full
            hov = r.collidepoint(self.mouse) and not self.lock
            on = self.build == kind
            col = P.tcol(kind)
            panel(s, r, mix_col(PANEL, col, 0.30 if on else 0.16 if hov else 0.05), 232, WHITE if on else col if hov else LINE, 9, 2)
            self.tower_icon(kind, r.centerx, r.y + 36, 1.15, 0, 0.5 if (hov or on) else 0.0, not afford)
            kn = self.kname("slot%d" % (i + 1))
            draw_text(s, kn, self.fit_size(kn, 14, 46), GREY, r.x + 8, r.y + 10, "l")
            draw_text(s, PLACE_SHORT[T["place"]], 11, PLACE_COL[T["place"]], r.right - 6, r.y + 10, "r")
            draw_text(s, "%d" % cost, 19, GOLD if afford else RED if full else ORANGE, r.centerx, r.bottom - 12)
            if hov:
                self.hov_slot = kind
                if self.click:
                    self.click = False
                    self.audio.play("click")
                    self.pick_build(kind)
        # ---- details tab, left centre
        t = self.sel if self.sel is not None else self.hov
        if self.hov_slot or self.build:
            R = pygame.Rect(0, 150, 236, 300)
            hr.append(R)
            panel(s, R, PANEL, 236, LINE, 12, 2)
            self.draw_shop_info(s, w, P, self.hov_slot or self.build, R)
        elif t is not None and t.ghost:
            R = pygame.Rect(0, 150, 236, 176)
            hr.append(R)
            panel(s, R, PANEL, 236, GOLD, 12, 2)
            self.draw_plan_info(s, w, P, t, R)
        elif t is not None:
            mine_t = t.owner is P
            R = pygame.Rect(0, 150, 236, 330 if mine_t else 250)
            hr.append(R)
            panel(s, R, PANEL, 236, t.owner.tcol(t.kind), 12, 2)
            self.draw_tower_info(s, w, P, t, R)
        else:
            R = pygame.Rect(0, 150, 200, 132)
            panel(s, R, PANEL, 190, LINE, 12, 1)
            self.draw_run_info(s, w, P, R)
        self.chat_top = R.bottom + 8
        # ---- bottom right: next wave, abilities, start
        S = pygame.Rect(W - 202, H - 98, 190, 88)
        hr.append(S)
        if w.phase == "build":
            if len(w.players) > 1:
                # with friends nobody readies up: the next wave starts by itself
                left = self.mp_wave_left(w)
                panel(s, S, mix_col(PANEL, GREEN, 0.10), 232, GREEN, 10, 2)
                draw_text(s, "NEXT WAVE IN", 17, MINT, S.centerx, S.y + 17)
                draw_text(s, "%d" % math.ceil(left) if left > 0.02 else "GO!", 42, WHITE, S.centerx, S.y + 47)
                draw_text(s, "wave %d starts by itself" % (w.wave + 1), 13, GREY, S.centerx, S.bottom - 12)
            else:
                sub = self.kname("start") if not st["auto"] else "AUTO IN %.0f" % max(0, 3 - self.auto_t)
                pulse = GREEN if (self.time * 2) % 2 < 1.4 else MINT
                if self.button("start", S, "START WAVE %d" % (w.wave + 1), pulse, 22, True, sub, alpha=232):
                    self.act("ready")
        elif w.phase == "cards":
            self.button("start", S, "CARDS", GOLD, 22, False, "waiting for picks", alpha=232)
        else:
            why = w.skip_why()
            if not why:
                have, need = w.skip_votes()
                if len(w.players) > 1:
                    sub = "%s    votes %d / %d" % (self.kname("skip"), have, need)
                    lab = "SKIP VOTED" if P.skip else "SKIP WAVE %d" % w.wave
                else:
                    sub = "%s    +%d cash now" % (self.kname("skip"), wave_bonus(w.wave))
                    lab = "SKIP WAVE %d" % w.wave
                if self.button("start", S, lab, GOLD, 21, True, sub, alpha=232):
                    self.act("skip")
            else:
                sub = "BOSS WAVE: NO SKIPPING" if (w.cur and w.cur.get("boss")) else why.upper() if why.startswith("Skip") else "FINAL WAVE" if why.startswith("This") else ""
                self.button("start", S, "WAVE %d" % w.wave, GREY, 24, False, sub, alpha=232)
        for i in range(2):
            A = pygame.Rect(W - 382, H - 98 + i * 46, 172, 42)
            hr.append(A)
            if i >= len(P.abils):
                self.button("abil%d" % i, A, "ability slot 2: level 10", GREY, 14, False, alpha=200)
                continue
            a = ABILS[P.abils[i]]
            ready = P.acd[i] <= 0
            on = self.aim == i
            lab = "%s  %s" % (self.kname("abil%d" % (i + 1)), a["name"])
            sub = "CLICK THE FIELD" if on else "READY" if (ready and w.phase == "wave") else "WAITS FOR A WAVE" if ready else "%ds" % math.ceil(P.acd[i])
            if self.button("abil%d" % i, A, lab, WHITE if on else a["col"] if ready else GREY, self.fit_size(lab, 16, A.w - 14), True, None, alpha=232):
                self.toggle_aim(i)
            draw_text(s, sub, 12, WHITE if ready else GREY, A.centerx, A.bottom - 7)
            if not ready:
                f = clamp(P.acd[i] / a["cd"], 0, 1)
                pygame.draw.rect(s, a["col"], (A.x + 6, A.bottom - 4, int((A.w - 12) * (1 - f)), 3))
        N = pygame.Rect(W - 566, H - 98, 176, 88)
        hr.append(N)
        panel(s, N, PANEL, 226, LINE, 10, 2)
        nx = w.next
        if nx is None or w.phase == "over":
            draw_text(s, "FINAL WAVE", 18, GOLD, N.centerx, N.centery)
        else:
            if nx["boss"]:
                draw_text(s, "NEXT: %d  BOSS" % nx["w"], 15, RED, N.x + 10, N.y + 13, "l")
            else:
                draw_text(s, "NEXT: WAVE %d" % nx["w"], 15, GREY, N.x + 10, N.y + 13, "l")
            xx = N.x + 24
            for kind, n in list(nx["counts"].items())[:4]:
                boss = ENEMIES[kind].get("boss")
                self.enemy_icon(kind, xx, N.y + 46, 0.45 if boss else min(1.0, 11.0 / ENEMIES[kind]["r"]), w.skin)
                draw_text(s, "x%d" % n if not boss else "", 14, WHITE, xx, N.y + 74)
                xx += 42
        # ---- chat, talk and tips, bottom centre
        self.draw_chat(s, w, P)
        if self.hov_e is not None and not self.lock:
            self.draw_enemy_tip(s, w, self.hov_e)
        if self.hov_p is not None and not self.lock:
            self.draw_player_tip(s, w, P, self.hov_p)

    def draw_radar(self, s, w, P, R):
        th = w.theme
        panel(s, R, mix_col(th["ground"], (0, 0, 0), 0.3), 225, LINE, 6, 1)
        sx, sy = R.w / float(FW), R.h / float(FH)
        acc = th["accent"]
        for (c, r), h in w.hmap.items():
            s.fill(scale_col(th["cliff"], min(1.5, 0.6 + 0.25 * h / STEP)), (R.x + c * CELL * sx, R.y + r * CELL * sy, CELL * sx + 1, CELL * sy + 1))
        for (c, r) in w.water:
            s.fill(th["water"], (R.x + c * CELL * sx, R.y + r * CELL * sy, CELL * sx + 1, CELL * sy + 1))
        prev = s.get_clip()
        s.set_clip(R)
        for p in w.paths:
            pygame.draw.lines(s, scale_col(acc, 0.55), False, [(R.x + x * sx, R.y + y * sy) for x, y in p.pts], 3)
        for t in w.plans:
            pygame.draw.rect(s, GOLD, (R.x + t.x * sx - 2, R.y + t.y * sy - 2, 4, 4), 1)
        for t in w.towers:
            s.fill(t.owner.tcol(t.kind) if not (t.path and t.down) else DIM, (R.x + t.x * sx - 1, R.y + t.y * sy - 1, 3, 3))
        for e in w.enemies:
            if e.boss:
                pygame.draw.circle(s, e.col, (R.x + e.x * sx, R.y + e.y * sy), 4)
                pygame.draw.circle(s, WHITE, (R.x + e.x * sx, R.y + e.y * sy), 4, 1)
            else:
                s.fill(e.col if not e.hidden else DIM, (R.x + e.x * sx - 1, R.y + e.y * sy - 1, 2, 2))
        pygame.draw.circle(s, WHITE, (R.x + w.core[0] * sx, R.y + w.core[1] * sy), 4, 1)
        for q in w.players:
            if q.here:
                x, y = R.x + clamp(q.x, 0, FW) * sx, R.y + clamp(q.y, 0, FH) * sy
                pygame.draw.circle(s, q.col, (x, y), 4)
                if q is P:
                    pygame.draw.circle(s, WHITE, (x, y), 5, 1)
                    pygame.draw.line(s, WHITE, (x, y), (x + math.cos(self.cyaw) * 9, y + math.sin(self.cyaw) * 9), 1)
        s.set_clip(prev)
        if R.collidepoint(self.mouse) and not self.lock:
            draw_text(s, "click to go there", 12, GREY, R.centerx, R.bottom + 8)
            if self.click:
                self.click = False
                P.x, P.y = w.free_spot(clamp((self.mouse[0] - R.x) / sx, 0, FW), clamp((self.mouse[1] - R.y) / sy, 0, FH))
                P.z = w.surf(P.x, P.y, 0.0)
                self.ctx, self.cty = P.x, P.y

    def draw_orb(self, s, cx, cy, r, col, k=1.0):
        """a player's orb as a little picture (the same orb that rolls around in a match)"""
        c = scale_col(col, k)
        glow(s, cx, cy, r * 2.3, c, 0.55)
        pygame.draw.circle(s, scale_col(c, 0.75), (cx, cy), r)
        pygame.draw.circle(s, mix_col(c, scale_col(WHITE, k), 0.55), (cx - r * 0.25, cy - r * 0.3), r * 0.55)
        pygame.draw.circle(s, scale_col(WHITE, k), (cx, cy), r, 1)

    def chat_life(self, e):
        """how long a chat line stays on the screen: about 5 seconds, longer for long ones"""
        return (5.0 + rich_len(e[2]) / 14.0) if e[0] else (6.0 + len(e[2]) / 18.0)

    def draw_chat_box(self, s, e, x, y, wd, lvl, k, lines, shown):
        """one line of chat as a dialogue box, the way people on the map talk: the speaker's orb, name and title, the words.
        lvl 0 = the newest (big), 1 and 2 = older ones (smaller, dimmer).  shown = how many letters are typed out so far"""
        name, col, text = e[0], e[1], e[2]
        big = lvl == 0
        if not name:
            # the game itself: one plain line (or two)
            fs = 16 if big else 15
            r = pygame.Rect(x, y, wd, 11 + 17 * len(lines))
            panel(s, r, PANEL, int(225 * k), scale_col(mix_col(col, LINE, 0.55), k), 9, 1)
            pygame.draw.polygon(s, scale_col(col, k), poly(r.x + 14, r.y + 14, 5, 4, 0))
            for j, ln in enumerate(lines):
                draw_text(s, ln, fs, scale_col(mix_col(col, WHITE, 0.25), k), r.x + 28, r.y + 14 + j * 17, "l")
            return r
        fs, lh, head, tx = (19, 21, 30, 52) if big else (16, 17, 23, 40)
        r = pygame.Rect(x, y, wd, head + lh * len(lines) + (9 if big else 7))
        panel(s, r, PANEL, int(240 * k), scale_col(col, k), 12 if big else 10, 2)
        # the portrait: their orb in their colour
        pr = 14 if big else 10
        pc = (r.x + (26 if big else 20), r.y + (27 if big else 20))
        fr = pygame.Rect(0, 0, pr * 2 + 12, pr * 2 + 12)
        fr.center = pc
        pygame.draw.rect(s, scale_col((20, 25, 52), k), fr, border_radius=8)
        pygame.draw.rect(s, scale_col(mix_col(col, LINE, 0.5), k), fr, 1, border_radius=8)
        self.draw_orb(s, pc[0], pc[1], pr, col, k)
        nr = draw_text(s, name, 18 if big else 15, scale_col(col, k), r.x + tx, r.y + (16 if big else 13), "l")
        if e[4]:
            draw_text(s, e[4], 13 if big else 12, scale_col(GOLD, k), nr.right + 8, r.y + (17 if big else 14), "l")
        left = shown
        for j, ln in enumerate(lines):
            if left <= 0:
                break
            n = rich_len(ln)
            draw_rich(s, ln if left >= n else rich_cut(ln, left), fs, scale_col(WHITE, k), r.x + tx, r.y + head + lh * j + lh // 2 - 1, k)
            left -= n + 1
        return r

    def draw_chat_stack(self, s, P):
        """chat lives bottom left, above the tower bar: up to three boxes, the newest at the bottom.  -> how far right they reach"""
        x0, wd = 12, 364
        bottom = H - 122
        top = max(62, self.chat_top)
        now = self.time
        typing = self.typing is not None
        right = 0
        if typing:
            # the box you type in: the same family, with your own orb
            lines = chat_wrap("> " + self.typing, 19, wd - 66) or ["> "]
            r = pygame.Rect(x0, bottom - (39 + 21 * len(lines)), wd, 39 + 21 * len(lines))
            self.hud_rects.append(r)
            panel(s, r, PANEL, 244, CYAN, 12, 2)
            fr = pygame.Rect(0, 0, 40, 40)
            fr.center = (r.x + 26, r.y + 27)
            pygame.draw.rect(s, (20, 25, 52), fr, border_radius=8)
            pygame.draw.rect(s, mix_col(P.col, LINE, 0.5), fr, 1, border_radius=8)
            self.draw_orb(s, fr.centerx, fr.centery, 14, P.col)
            draw_text(s, P.name, 18, P.col, r.x + 52, r.y + 16, "l")
            draw_text(s, "ENTER sends    ESC cancels", 12, GREY, r.right - 12, r.y + 16, "r")
            tr = None
            for j, ln in enumerate(lines):
                tr = draw_text(s, ln, 19, WHITE, r.x + 52, r.y + 40 + 21 * j, "l")
            if (now * 2) % 2 < 1.2:
                cxp = (tr.right if (tr is not None and lines[-1]) else r.x + 52) + 3
                cyp = r.y + 40 + 21 * (len(lines) - 1)
                pygame.draw.line(s, WHITE, (cxp, cyp - 8), (cxp, cyp + 8), 2)
            bottom = r.y - 6
            right = r.right
        show = []
        for e in reversed(self.chat):
            if typing or now - e[3] < self.chat_life(e):
                show.append(e)
                if len(show) == 3:
                    break
        for lvl, e in enumerate(show):
            age = now - e[3]
            life = self.chat_life(e)
            w2 = wd - 26 * lvl
            big = lvl == 0
            if e[0]:
                lines = chat_wrap(e[2], 19 if big else 16, w2 - (64 if big else 50))[:4]
                if big and len(lines) > 3 and bottom - top < 123:
                    lines = lines[:3]       # a tall panel is open on the left: the newest line still has to fit under it
                h = (30 if big else 23) + (21 if big else 17) * len(lines) + (9 if big else 7)
            else:
                lines = wrap(e[2], 16 if big else 15, w2 - 40)[:3]
                h = 11 + 17 * len(lines)
            ty = bottom - h
            if ty < top:
                break
            # boxes glide to their place; a new one slides in from the left, an old one fades away to the left
            pos = e[5]
            if pos is None or now - pos[1] > 0.25:
                y = float(ty)
            else:
                y = pos[0] + (ty - pos[0]) * min(1.0, self.dt * 14)
            e[5] = (y, now)
            k = (1.0, 0.74, 0.54)[lvl]
            slide = (1.0 - ease_out(age / 0.22)) * -46
            if not typing and age > life - 0.6:
                f = clamp((life - age) / 0.6, 0.0, 1.0)
                k *= f
                slide -= (1.0 - f) * 30
            k *= min(1.0, 0.3 + age / 0.22)
            if k < 0.04:
                continue
            r = self.draw_chat_box(s, e, x0 + int(slide), int(y), w2, lvl, k, lines, int(age * 44) if e[0] else 999)
            right = max(right, r.right)
            bottom = ty - 6
        return right

    def draw_chat(self, s, w, P):
        cx = W // 2
        y = H - 112
        if self.talk:
            n, i = self.talk
            lines = wrap(self.ktext(n["lines"][i]), 20, 470)
            r = pygame.Rect(cx - 260, y - 44 - len(lines) * 22, 520, 44 + len(lines) * 22)
            self.hud_rects.append(r)
            panel(s, r, PANEL, 240, n["col"], 12, 2)
            draw_text(s, n["name"], 18, n["col"], r.x + 16, r.y + 16, "l")
            draw_text(s, "%d / %d    click, %s or %s" % (i + 1, len(n["lines"]), self.kname("talk"), self.kname("chat")), 13, GREY, r.right - 14, r.y + 16, "r")
            for j, ln in enumerate(lines):
                draw_text(s, ln, 20, WHITE, r.x + 16, r.y + 42 + j * 22, "l")
            y = r.y - 8
        chat_right = self.draw_chat_stack(s, P)
        # one line of help or a warning
        kn = self.kname
        txt, col = "", GREY
        if self.msg:
            self.msg[2] -= self.dt
            txt, col = self.msg[0], self.msg[1]
            if self.msg[2] <= 0:
                self.msg = None
        elif self.ghost_why:
            txt, col = self.ghost_why, RED
        elif self.aim is not None and self.aim < len(P.abils):
            txt = "Click the field to drop %s.   Right-click to cancel." % ABILS[P.abils[self.aim]]["name"]
        elif self.build:
            txt = "Click to place it anywhere that fits.   Hold SHIFT to place more.   Right-click to cancel."
            if is_path(self.build):
                txt = "PATH TOWER: click ON the road.   Right-click to cancel."
            if P.cash < w.cost(P, self.build):
                txt = "Not enough cash yet: click to PLAN it. It builds itself when you can pay.   Right-click to cancel."
                col = GOLD
        elif w.wave == 0 and not w.towers:
            txt = "Pick a tower at the bottom left (keys %s-%s), then click the ground next to the road." % (kn("slot1"), kn("slot%d" % len(P.loadout)))
        elif w.phase == "build" and w.wave < 3:
            txt = ("The next wave starts by itself." if len(w.players) > 1 else "%s starts the wave." % kn("start")) + \
                  "   Point at a tower:  %s upgrade   %s sell   %s target   %s ability.   %s chats." % (kn("upgrade"), kn("sell"), kn("mode"), kn("tabil"), kn("chat"))
        if txt:
            fs = self.fit_size(txt, 18, W - 40 - (chat_right + 8 if chat_right else 0), 13)
            r = pygame.Rect(0, 0, font(fs).size(txt)[0] + 28, 26)
            r.midbottom = (cx, min(y, H - 112) - 2)
            if chat_right and r.x < chat_right + 8:
                r.x = chat_right + 8        # never on top of the chat
            panel(s, r, (6, 7, 16), 215, col if col != GREY else LINE, 8, 1)
            draw_text(s, txt, fs, WHITE if col != GREY else GREY, r.centerx, r.centery)

    def draw_player_tip(self, s, w, P, q):
        """who is that?  A card for the player whose orb you point at: name, title, level and what they brought"""
        wd = 300
        rows = (len(q.loadout) + 1) // 2
        np_, na = max(1, len(q.perks)), max(1, len(q.abils))
        R = pygame.Rect(0, 0, wd, 58 + 18 + rows * 26 + 8 + 16 + max(np_, na) * 17 + 8 + 22)
        mx, my = self.mouse
        R.topleft = (clamp(mx + 20, 4, W - wd - 4), clamp(my - R.h - 12, 60, H - R.h - 4))
        panel(s, R, PANEL, 240, q.col, 10, 2)
        self.draw_orb(s, R.x + 28, R.y + 29, 13, q.col)
        nm = q.name + ("  (you)" if q is P else "")
        draw_text(s, nm, self.fit_size(nm, 20, wd - 150), WHITE, R.x + 52, R.y + 20, "l")
        if q.title:
            draw_text(s, q.title, 14, GOLD, R.x + 52, R.y + 40, "l")
        draw_text(s, "LEVEL %d" % q.level, 17, CYAN, R.right - 12, R.y + 20, "r")
        pygame.draw.line(s, scale_col(q.col, 0.45), (R.x + 10, R.y + 56), (R.right - 10, R.y + 56), 1)
        y = R.y + 68
        draw_text(s, "LOADOUT", 12, DIM, R.x + 12, y, "l")
        y += 22
        for i, kind in enumerate(q.loadout):
            cx, cy = R.x + 26 + (i % 2) * 144, y + (i // 2) * 26
            m = tower_model(kind, 0)
            self.scene.icon(s, m, q.tcol(kind), cx, cy + m.top * 0.6 * 0.22, 0.6, self.time, 0.0)
            tn = q.tname(kind)
            draw_text(s, tn, self.fit_size(tn, 15, 108), q.tcol(kind), cx + 18, cy, "l")
        y += rows * 26
        draw_text(s, "PERKS", 12, DIM, R.x + 12, y, "l")
        draw_text(s, "ABILITIES", 12, DIM, R.x + 156, y, "l")
        y += 17
        for i, k in enumerate(q.perks):
            pk = PERKS[k]
            pygame.draw.circle(s, CAT_COL[pk["cat"]], (R.x + 17, y + i * 17), 4)
            draw_text(s, pk["name"], self.fit_size(pk["name"], 15, 118), WHITE, R.x + 28, y + i * 17, "l")
        if not q.perks:
            draw_text(s, "none", 15, DIM, R.x + 12, y, "l")
        for i, k in enumerate(q.abils):
            ab = ABILS[k]
            pygame.draw.circle(s, ab["col"], (R.x + 161, y + i * 17), 4)
            draw_text(s, ab["name"], self.fit_size(ab["name"], 15, 118), WHITE, R.x + 172, y + i * 17, "l")
        n = len(q.tperks)
        draw_text(s, "TOWER PERKS", 12, DIM, R.x + 12, R.bottom - 15, "l")
        draw_text(s, "%d" % n if n else "none", 16, CYAN if n else DIM, R.x + 96, R.bottom - 15, "l")

    def draw_tower_info(self, s, w, P, t, R):
        T = TOWERS[t.kind]
        own = t.owner
        mine = own is P
        col = own.tcol(t.kind)
        nm = own.tname(t.kind)
        draw_text(s, nm, 20 if len(nm) < 14 else 16, col, R.x + 12, R.y + 18, "l")
        draw_text(s, "MAX" if t.lv >= MAXLV else "LV %d" % (t.lv + 1), 20, GOLD if t.lv >= MAXLV else WHITE, R.right - 12, R.y + 18, "r")
        y = R.y + 40
        if len(w.players) > 1 or not mine:
            pygame.draw.circle(s, own.col, (R.x + 18, y), 5)
            draw_text(s, "YOUR TOWER" if mine else "%s's tower" % own.name, 15, WHITE if mine else own.col, R.x + 28, y, "l")
            y += 20
        cur = tower_stats(t.kind, t.L)
        nxt = dict(tower_stats(t.kind, T["lv"][t.lv + 1])) if (t.lv < MAXLV and mine) else {}
        for lab, val in cur[:5]:
            draw_text(s, lab, 13, DIM, R.x + 12, y, "l")
            draw_text(s, val, 15, WHITE, R.x + 156, y, "r")
            nv = nxt.get(lab)
            if nv and nv != val:
                draw_text(s, nv, 14, GREEN, R.x + 162, y, "l")
            y += 18
        if t.path:
            f = clamp(t.hp / max(1.0, t.maxhp), 0, 1)
            bar = pygame.Rect(R.x + 12, y, R.w - 24, 12)
            pygame.draw.rect(s, (30, 12, 20), bar, border_radius=5)
            pygame.draw.rect(s, GREEN if f > 0.5 else GOLD if f > 0.25 else RED, (bar.x, bar.y, int(bar.w * f), bar.h), border_radius=5)
            draw_text(s, "DOWN - back after the wave" if t.down else "%d / %d" % (t.hp, t.maxhp), 12, WHITE, bar.centerx, bar.centery)
            y += 20
        tp = t.tp
        draw_text(s, "PERK", 13, DIM, R.x + 12, y, "l")
        draw_text(s, TPERKS[tp]["name"] if tp else "none", 15, CYAN if tp else DIM, R.x + 52, y, "l")
        y += 18
        bits = []
        if t.cliff:
            bits.append("HIGH GROUND" if t.hk > 1 else "CLIFF")
        if t.mb:
            bits.append("AT HOME " + buff_text(t.mb).upper())
        if t.rb:
            bits.append("RANGE +%d%%" % round(t.rb * 100))
        rb = w.rate_buff(t)
        if rb:
            bits.append("SPEED +%d%%" % round(rb * 100))
        if t.od > 0:
            bits.append("OVERDRIVE")
        if t.stun > 0:
            bits = ["STUNNED %.1fs" % t.stun]
        if bits:
            draw_text(s, "   ".join(bits), 13, PURPLE if t.stun > 0 else MINT, R.x + 12, y, "l")
            y += 17
        if T["atk"] in ("RANGED", "MELEE", "BOTH", "PATH", "SUMMON"):
            dm = t.dealt
            draw_text(s, "KILLS %d    DAMAGE %s" % (t.kills, "%.1fk" % (dm / 1000.0) if dm >= 1000 else "%d" % dm), 13, DIM, R.x + 12, y, "l")
            y += 17
        if not mine:
            if own.perks:
                draw_text(s, "OWNER'S PERKS", 13, DIM, R.x + 12, y + 2, "l")
                for i, k in enumerate(own.perks[:3]):
                    draw_text(s, PERKS[k]["name"], 14, CAT_COL[PERKS[k]["cat"]], R.x + 12, y + 20 + i * 16, "l")
            draw_text(s, "Only %s can manage this tower." % own.name, 13, GREY, R.x + 12, R.bottom - 16, "l")
            return
        by = R.bottom - 92
        if T["atk"] in ("RANGED", "MELEE", "BOTH"):
            lab = "%s   TARGET: %s" % (self.kname("mode"), TARGET_MODES[t.mode])
            if self.button("tmode", pygame.Rect(R.x + 10, by, R.w - 20, 28), lab, CYAN, self.fit_size(lab, 16, R.w - 34)):
                self.act("mode", t.id)
        elif t.kind == "commander":
            ready = t.acd <= 0 and t.act <= 0
            lab = "%s   CALL TO ARMS" % self.kname("tabil") if ready else "ACTIVE %ds" % math.ceil(t.act) if t.act > 0 else "RECHARGING %ds" % math.ceil(t.acd)
            if self.button("tabil", pygame.Rect(R.x + 10, by, R.w - 20, 28), lab, RED if ready else GREY, self.fit_size(lab, 16, R.w - 34), ready):
                self.sel = t
                self.do_ability()
        c = w.up_cost(t)
        U = pygame.Rect(R.x + 10, R.bottom - 56, 126, 46)
        if c is None:
            self.button("up", U, "MAX LEVEL", GOLD, 18, False)
        elif self.button("up", U, "%s  UPGRADE" % self.kname("upgrade"), GREEN if P.cash >= c else RED,
                         self.fit_size("%s  UPGRADE" % self.kname("upgrade"), 17, U.w - 10), True, "%d" % c):
            self.sel = t
            self.do_upgrade()
        lab = "%s  SELL" % self.kname("sell")
        if self.button("sell", pygame.Rect(U.right + 8, U.y, R.w - 20 - 134, 46), lab, ORANGE, self.fit_size(lab, 17, R.w - 164), True, "+%d" % w.sell_value(t)):
            self.act("sell", t.id)
            self.sel = None

    def draw_plan_info(self, s, w, P, t, R):
        own = t.owner
        mine = own is P
        nm = own.tname(t.kind)
        cost = w.cost(own, t.kind)
        draw_text(s, nm, 20 if len(nm) < 14 else 16, own.tcol(t.kind), R.x + 12, R.y + 18, "l")
        draw_text(s, "PLANNED", 16, GOLD, R.right - 12, R.y + 18, "r")
        y = R.y + 44
        if not mine:
            pygame.draw.circle(s, own.col, (R.x + 18, y), 5)
            draw_text(s, "%s's plan" % own.name, 15, own.col, R.x + 28, y, "l")
            return
        draw_text(s, "It cannot shoot yet.", 15, GREY, R.x + 12, y, "l")
        draw_text(s, "It builds itself when you have", 15, GREY, R.x + 12, y + 18, "l")
        draw_text(s, "%d cash" % cost, 20, GOLD, R.x + 12, y + 42, "l")
        f = clamp(own.cash / float(max(1, cost)), 0, 1)
        bar = pygame.Rect(R.x + 12, y + 60, R.w - 24, 8)
        pygame.draw.rect(s, (30, 12, 20), bar, border_radius=4)
        pygame.draw.rect(s, GOLD, (bar.x, bar.y, int(bar.w * f), bar.h), border_radius=4)
        if self.button("unplan", pygame.Rect(R.x + 10, R.bottom - 46, R.w - 20, 36), "%s   CANCEL PLAN" % self.kname("sell"), ORANGE, 17):
            self.act("sell", t.id)
            self.sel = None

    def draw_enemy_tip(self, s, w, e):
        """what you are pointing at: its health, and what happens to the core if it gets through"""
        lk = w.leak_of(e)
        final = lk >= 999
        deadly = final or lk >= w.hp
        lines = [(e.name, 17, e.col), ("HP  %d / %d" % (max(0, math.ceil(e.hp)), e.max), 16, WHITE)]
        if e.smax > 0:
            lines.append(("SHIELD  %d / %d" % (max(0, e.shield), e.smax), 14, BLUE))
        if final:
            lines.append(("LEAK:  ENDS THE RUN", 16, RED))
        else:
            lines.append(("LEAK NOW:  -%d CORE%s" % (lk, "   DEADLY" if deadly else ""), 16, RED if deadly else ORANGE if lk >= w.hp * 0.25 else GREEN))
        wd = max(font(sz).size(tx)[0] for tx, sz, c in lines) + 22
        R = pygame.Rect(0, 0, wd, 12 + 19 * len(lines))
        mx, my = self.mouse
        R.topleft = (clamp(mx + 18, 4, W - wd - 4), clamp(my - R.h - 10, 60, H - R.h - 4))
        panel(s, R, PANEL, 236, RED if deadly else LINE, 8, 2)
        for i, (tx, sz, c) in enumerate(lines):
            draw_text(s, tx, sz, c, R.x + 11, R.y + 16 + i * 19, "l")

    def draw_shop_info(self, s, w, P, kind, R):
        T = TOWERS[kind]
        nm = P.tname(kind)
        draw_text(s, nm, 20 if len(nm) < 14 else 16, P.tcol(kind), R.x + 12, R.y + 18, "l")
        draw_text(s, "%d" % w.cost(P, kind), 20, GOLD, R.right - 12, R.y + 18, "r")
        x = R.x + 12
        x = self.chip(T["tier"], CYAN, x, R.y + 42, 12)
        x = self.chip(T["atk"], PINK, x, R.y + 42, 12)
        if T.get("aoe"):
            x = self.chip("AOE", ORANGE, x, R.y + 42, 12)
        draw_text(s, "PLACE: " + PLACE_NAME[T["place"]], 14, PLACE_COL[T["place"]], R.x + 12, R.y + 64, "l")
        y = R.y + 84
        mb = w.map.get("buff", {}).get(kind)
        if mb:
            draw_text(s, "AT HOME HERE: " + buff_text(mb), 14, GOLD, R.x + 12, y, "l")
            y += 18
        for ln in wrap(self.ktext(T["desc"]), 14, R.w - 24)[:6]:
            draw_text(s, ln, 14, GREY, R.x + 12, y, "l")
            y += 15
        y = max(y + 6, R.y + 186)
        for lab, val in tower_stats(kind, T["lv"][0])[:4]:
            draw_text(s, lab, 13, DIM, R.x + 12, y, "l")
            draw_text(s, val, 15, WHITE, R.right - 12, y, "r")
            y += 18
        tp = P.tperks.get(kind)
        draw_text(s, "PERK", 13, DIM, R.x + 12, R.bottom - 16, "l")
        draw_text(s, TPERKS[tp]["name"] if tp else "none", 15, CYAN if tp else DIM, R.x + 52, R.bottom - 16, "l")

    def draw_run_info(self, s, w, P, R):
        y = R.y + 16
        draw_text(s, "PERKS", 13, DIM, R.x + 12, y, "l")
        y += 18
        for k in P.perks:
            p = PERKS[k]
            pygame.draw.circle(s, CAT_COL[p["cat"]], (R.x + 17, y), 4)
            draw_text(s, p["name"], 15, WHITE, R.x + 28, y, "l")
            y += 17
        if not P.perks:
            draw_text(s, "none", 15, DIM, R.x + 12, y, "l")
            y += 17
        nxt = (w.wave // CARD_EVERY + 1) * CARD_EVERY
        y += 4
        draw_text(s, "CARDS %d" % len(P.cards) + ("   next: wave %d" % nxt if nxt < w.nwaves else ""), 13, DIM, R.x + 12, y, "l")
        y += 17
        xx = R.x + 16
        for c in P.cards[-9:]:
            pygame.draw.circle(s, CAT_COL[c["cat"]], (xx, y), 5)
            pygame.draw.circle(s, RARITY[c["rar"]][1], (xx, y), 5, 1)
            xx += 16

    # ------------------------------------------------------------ overlays
    def draw_cards(self, s, w, P):
        self.card_t += self.dt
        self.dim(s, 170)
        draw_glow_text(s, "SUPPLY DROP", 64, GOLD, W // 2, 96)
        sub = "Wave %d cleared.  Pick one card.  (keys %s)" % (w.wave, " ".join(self.kname("slot%d" % (j + 1)) for j in range(3)))
        if len(w.players) > 1:
            sub += "    %ds" % max(0, w.card_t)
        draw_text(s, sub, 22, GREY, W // 2, 146)
        pick = None
        for i, c in enumerate(P.offer or []):
            u = ease_out(clamp((self.card_t - i * 0.12) / 0.35, 0, 1))
            col = CAT_COL[c["cat"]]
            r = pygame.Rect(0, 0, 270, 360)
            r.center = (W // 2 + (i - 1) * 300, 390 + int((1 - u) * 400))
            hov = r.collidepoint(self.mouse) and self.card_t > 0.6
            h = self.hover.get("card%d" % i, 0.0)
            h += ((1.0 if hov else 0.0) - h) * min(1.0, self.dt * 14)
            self.hover["card%d" % i] = h
            r.y -= int(h * 16)
            panel(s, r, mix_col(PANEL, col, 0.08 + 0.10 * h), 250, mix_col(col, WHITE, h * 0.5), 16, 3)
            glow(s, r.centerx, r.y + 120, 110, col, 0.35 + 0.3 * h)
            draw_text(s, c["cat"], 20, col, r.centerx, r.y + 28)
            rn, rc = RARITY[c["rar"]]
            draw_text(s, rn, 16, rc, r.centerx, r.y + 50)
            cx, cy = r.centerx, r.y + 124
            if c["cat"] == "ATTACK":
                pygame.draw.polygon(s, col, star_pts(cx, cy, 44, 4, self.time * 0.6, 0.3), 3)
                pygame.draw.circle(s, WHITE, (cx, cy), 7)
            elif c["cat"] == "DEFENSE":
                pts = [(cx - 34, cy - 38), (cx + 34, cy - 38), (cx + 34, cy + 6), (cx, cy + 42), (cx - 34, cy + 6)]
                pygame.draw.polygon(s, scale_col(col, 0.25), pts)
                pygame.draw.polygon(s, col, pts, 3)
                pygame.draw.line(s, WHITE, (cx, cy - 22), (cx, cy + 18), 3)
                pygame.draw.line(s, WHITE, (cx - 18, cy - 6), (cx + 18, cy - 6), 3)
            else:
                pygame.draw.polygon(s, scale_col(col, 0.25), poly(cx, cy, 42, 4, 0))
                pygame.draw.polygon(s, col, poly(cx, cy, 42, 4, 0), 3)
                pygame.draw.polygon(s, WHITE, poly(cx, cy, 18, 4, self.time), 2)
            draw_text(s, c["name"], 30, WHITE, r.centerx, r.y + 206)
            y = r.y + 250
            for ln in wrap(c["text"], 21, r.w - 36):
                draw_text(s, ln, 21, GREY, r.centerx, y)
                y += 24
            draw_text(s, self.kname("slot%d" % (i + 1)), 20, DIM, r.centerx, r.bottom - 20)
            if (hov and self.click) or (self.card_t > 0.6 and self.kp("slot%d" % (i + 1))):
                pick = i
        if pick is not None:
            self.click = False
            self.act("card", pick)
            if isinstance(w, GuestWorld):
                P.offer = None

    def finish_game(self):
        w, sv = self.world, self.save
        D = w.D
        win = w.result == "win"
        done = w.wave if win else min(max(0, w.wave - 1), w.cleared)      # skipped waves you did not survive do not count
        coins = D["per"] * done + (D["coins"] if win else 0)
        xp = D["xp"] * done + (D["xpwin"] if win else 0)
        key = "%s:%s" % (w.mapid, w.diff)
        notes = []
        if win and not sv["stars"].get(key) and D["first"]:
            coins += D["first"]
            notes.append("FIRST CLEAR BONUS  +%d" % D["first"])
        ev = w.map.get("event")
        if ev and win:
            E = EVENTS[ev]
            kind = E["tower"]
            real = event_state(sv, ev)[0] in ("season", "live")
            had = sv["etowers"].get(kind)
            if real and had != "og":
                sv["etowers"][kind] = "og"
                notes.append("EVENT TOWER EARNED:  " + TOWERS[kind]["name"])
            elif not real and had is None:
                sv["etowers"][kind] = "ripoff"
                notes.append("EVENT TOWER EARNED:  %s RIPOFF  (the event was over)" % TOWERS[kind]["name"])
            if not sv["edone"].get(ev):
                coins += 500
                notes.append("EVENT BONUS  +500")
            sv["edone"][ev] = sv["edone"].get(ev, 0) + 1
        lv0 = self.level()
        sv["xp"] += xp
        lv1 = self.level()
        bonus = sum(level_coins(l) for l in range(lv0 + 1, lv1 + 1))
        if bonus:
            notes.append("LEVEL UP BONUS  +%d" % bonus)
        sv["coins"] += coins + bonus
        if win:
            sv["stars"][key] = max(sv["stars"].get(key, 0), w.stars)
            sv["stats"]["wins"] += 1
            if len(w.players) > 1:
                sv["stats"]["mpwins"] = sv["stats"].get("mpwins", 0) + 1
        sv["best"][key] = max(sv["best"].get(key, 0), done)
        sv["stats"]["kills"] += w.players[self.me].kills if len(w.players) > 1 else w.stats["kills"]
        sv["stats"]["towers"] += w.players[self.me].built if not isinstance(w, GuestWorld) else 0
        sv["stats"]["bosses"] += w.stats["bosses"]
        new = []
        for group in (TOWERS, PERKS, ABILS, TPERKS):
            for v in group.values():
                if lv0 < v["need"] <= lv1 and not v.get("event"):
                    new.append(v["name"])
        for m in MAIN_MAPS:
            if lv0 < m["need"] <= lv1:
                new.append("MAP: " + m["name"])
        if lv0 < 8 <= lv1:
            new.append("6TH LOADOUT SLOT")
        for need, what in ((6, "2ND PERK SLOT"), (14, "3RD PERK SLOT"), (10, "2ND ABILITY SLOT")):
            if lv0 < need <= lv1:
                new.append(what)
        titles = [TITLES[k][0] for k in self.check_titles(True)]
        self.reward = dict(win=win, coins=coins + bonus, xp=xp, lv0=lv0, lv1=lv1, new=new, done=done, notes=notes, titles=titles)
        self.over_t = 0.0
        self.build = None
        self.aim = None
        self.sel = None
        self.talk = None
        self.fix_save()
        self.store()
        if lv1 > lv0:
            self.audio.play("levelup")

    def draw_over(self, s, w):
        self.over_t += self.dt
        if self.over_t < 1.3:
            return
        rw = self.reward
        u = ease_out((self.over_t - 1.3) / 0.4)
        self.dim(s, int(170 * u))
        R = pygame.Rect(0, 0, 700, 560)
        R.center = (W // 2, H // 2 + int((1 - u) * 40))
        col = GOLD if rw["win"] else RED
        panel(s, R, PANEL, 245, col, 18, 3)
        draw_glow_text(s, "TRIUMPH" if rw["win"] else "DEFEAT", 84, col, R.centerx, R.y + 60)
        draw_text(s, "%s   -   %s   -   %d / %d WAVES" % (w.map["name"], w.D["name"], rw["done"], w.nwaves), 22, GREY, R.centerx, R.y + 114)
        if rw["win"]:
            for i in range(3):
                draw_star(s, R.centerx + (i - 1) * 62, R.y + 160, 26, i < w.stars)
        else:
            draw_text(s, "The host left." if self.over_net else "The core fell on wave %d." % w.wave, 22, WHITE, R.centerx, R.y + 160)
        y = R.y + 210
        for lab, val in (("ENEMIES DESTROYED", "%d" % w.stats["kills"]), ("TOWERS BUILT", "%d" % w.stats["built"]),
                         ("LEAKS", "%d" % w.stats["leaks"]), ("TIME", "%d:%02d" % (w.playtime // 60, w.playtime % 60))):
            draw_text(s, lab, 18, DIM, R.x + 60, y, "l")
            draw_text(s, val, 20, WHITE, R.x + 310, y, "r")
            y += 26
        x = R.x + 380
        draw_text(s, "REWARDS", 18, DIM, x, R.y + 210, "l")
        draw_text(s, "+%d COINS" % rw["coins"], 30, GOLD, x, R.y + 242, "l")
        draw_text(s, "+%d XP" % rw["xp"], 30, CYAN, x, R.y + 276, "l")
        lv, into = level_of(self.save["xp"])
        bar = pygame.Rect(R.x + 60, R.y + 340, R.w - 120, 16)
        pygame.draw.rect(s, (24, 30, 60), bar, border_radius=7)
        pygame.draw.rect(s, CYAN, (bar.x, bar.y, int(bar.w * min(1.0, into / float(xp_need(lv)))), bar.h), border_radius=7)
        draw_text(s, "LEVEL %d" % lv, 20, WHITE, bar.x, bar.y - 16, "l")
        draw_text(s, "%d / %d XP" % (into, xp_need(lv)) if lv < MAX_LEVEL else "MAX LEVEL", 16, GREY, bar.right, bar.y - 16, "r")
        if rw["lv1"] > rw["lv0"]:
            draw_text(s, "LEVEL UP!", 28, GOLD if (self.time * 3) % 2 < 1.3 else WHITE, R.centerx, bar.y - 18)
        yy = bar.bottom + 20
        lines = [(n, GOLD) for n in rw["notes"]] + [("NEW TITLE:  " + t, PINK) for t in rw["titles"]]
        if rw["new"]:
            lines += [(ln, MINT) for ln in wrap("NOW IN THE SHOP:  " + ",  ".join(rw["new"]), 17, R.w - 80)[:2]]
        for txt, c in lines[:5]:
            draw_text(s, txt, 17, c, R.centerx, yy)
            yy += 20
        if self.over_t > 1.9:
            P = pygame.K_ESCAPE in self.pressed
            if self.net:
                host = self.net[0] == "host"
                gone = self.net[0] == "guest" and self.net[1].dead
                if gone:
                    if self.button("lobby", pygame.Rect(R.centerx - 125, R.bottom - 74, 250, 54), "MAIN MENU", CYAN, 26) or P:
                        self.world = None
                        self.leave_net()
                        self.goto("lobby")
                elif self.button("again", pygame.Rect(R.x + 60, R.bottom - 74, 270, 54), "BACK TO THE ROOM", col, 24):
                    self.world = None
                    if host:
                        self.room_broadcast()
                    self.goto("room")
                elif self.button("lobby", pygame.Rect(R.right - 330, R.bottom - 74, 270, 54), "LEAVE", RED, 26) or P:
                    self.world = None
                    self.leave_net()
                    self.goto("lobby")
            elif self.button("again", pygame.Rect(R.x + 60, R.bottom - 74, 270, 54), "PLAY AGAIN", col, 28):
                self.start_game(w.mapid, w.diff)
            elif self.button("lobby", pygame.Rect(R.right - 330, R.bottom - 74, 270, 54), "MAIN MENU", CYAN, 26) or P:
                self.world = None
                self.goto("lobby")

    def draw_pause(self, s, w):
        self.dim(s, 170)
        R = pygame.Rect(0, 0, 420, 500)
        R.center = (W // 2, H // 2)
        panel(s, R, PANEL, 245, CYAN, 18, 3)
        draw_glow_text(s, "MENU" if self.net else "PAUSED", 64, CYAN, R.centerx, R.y + 52)
        P = self.pressed
        if self.quit_confirm > 0:
            self.quit_confirm -= self.dt
        items = [("resume", "RESUME", GREEN)]
        if not self.net:
            items.append(("restart", "RESTART", GOLD))
        items += [("settings", "SETTINGS", CYAN), ("controls", "CONTROLS", PURPLE), ("help", "HOW TO PLAY", CYAN),
                  ("quit", "REALLY LEAVE? (no rewards)" if self.quit_confirm > 0 else "LEAVE THE GAME" if self.net else "QUIT TO MENU", RED)]
        for i, (key, lab, col) in enumerate(items):
            if self.button("p_" + key, pygame.Rect(R.x + 50, R.y + 98 + i * 62, R.w - 100, 50), lab, col, 22 if key == "quit" else 25):
                if key == "resume":
                    self.paused = False
                elif key == "restart":
                    self.start_game(w.mapid, w.diff)
                elif key in ("settings", "controls", "help"):
                    self.back_to = "play"
                    self.goto(key)
                elif self.quit_confirm > 0:
                    self.world = None
                    self.paused = False
                    self.leave_net()
                    self.goto("lobby")
                else:
                    self.quit_confirm = 3.0
                return
        if self.net:
            draw_text(s, "The match keeps running while this menu is open.", 15, GREY, R.centerx, R.bottom - 22)
        if pygame.K_ESCAPE in P or self.kp("pause"):
            self.paused = False


    # ------------------------------------------------------------ title screen
    def draw_demo(self, s, dim=165):
        d = self.demo
        for _ in range(2):
            d.update(min(self.dt, 1 / 30.0))
            self.demo_bot.step(min(self.dt, 1 / 30.0))
        del d.ev[:]
        if d.phase == "over" or d.wave > 14:
            self.new_demo()
            d = self.demo
        cam = self.cam
        cam.ortho = False
        cam.cx, cam.cy = W / 2.0, H / 2.0 + 40
        cam.look(FW / 2.0, FH / 2.0, 0, 880, self.demo_cam + self.time * 0.04, 0.72)
        self.scene.draw(s, d, cam, dict(t=d.time, detail=min(1, self.save["settings"]["detail"]), ranges=False, boxes=False, names=False, players=False,
                                        core_col=self.pcol(), core_skin=self.save["skin"], seen=[n["id"] for n in d.npcs]))
        self.dim(s, dim)

    def draw_plain(self, s):
        s.fill(BG)
        for x in range(0, W + 1, 40):
            pygame.draw.line(s, (12, 15, 36), (x, 0), (x, H))
        for y in range(0, H + 1, 40):
            pygame.draw.line(s, (12, 15, 36), (0, y), (W, y))
        ov = pygame.Surface((W, 160), pygame.SRCALPHA)
        for i in range(160):
            pygame.draw.line(ov, (4, 5, 14, int(150 * i / 160.0)), (0, i), (W, i))
        s.blit(ov, (0, H - 160))
        sn = self.season()
        if sn == "winter":
            rnd = random.Random(3)
            for i in range(50):
                x = (rnd.randrange(W) + math.sin(self.time * 0.7 + i) * 14) % W
                y = (rnd.randrange(H) + self.time * (18 + i % 5 * 6)) % H
                s.fill(WHITE if i % 3 else ICE, (x, y, 3, 3))
        elif sn == "haunted":
            rnd = random.Random(4)
            for i in range(26):
                x = (rnd.randrange(W) + self.time * (10 + i % 4 * 5)) % W
                y = rnd.randrange(H) + math.sin(self.time * 1.3 + i) * 10
                s.fill(PUMP_O if i % 2 else WITCH, (x, y, 3, 3))

    def season(self):
        """which seasonal event is on right now (or None)"""
        for ev in ("haunted", "winter"):
            if in_season(ev):
                return ev
        return None

    def screen_menu(self, s):
        """the title screen IS the main menu: six buttons over a live match, you and your loadout in the corners"""
        self.draw_demo(s, 120)
        sv = self.save
        t = self.time
        sn = self.season()
        c1, c2 = (CYAN, PINK) if sn is None else ((255, 128, 22), WITCH) if sn == "haunted" else ((255, 70, 90), (90, 235, 140))
        w1 = font(140).size("NEON")[0]
        w2 = font(140).size("BASTION")[0]
        x0 = W / 2 - (w1 + w2 + 34) / 2
        draw_glow_text(s, "NEON", 140, c1, x0 + w1 / 2, 122 + math.sin(t * 1.6) * 5)
        draw_glow_text(s, "BASTION", 140, c2, x0 + w1 + 34 + w2 / 2, 122 + math.sin(t * 1.6 + 1.2) * 5)
        draw_glow_text(s, "2", 80, GOLD, x0 + w1 + 34 + w2 + 34, 90 + math.sin(t * 1.6 + 2.0) * 5)
        draw_text(s, "T O W E R    D E F E N S E    I N    3 D", 22, GREY, W // 2, 204)
        if sn:
            E = EVENTS[sn]
            draw_text(s, "%s EVENT IS LIVE   -   %d days left" % (E["label"], season_left(sn)), 20, E["col"], W // 2, 234)
        draw_text(s, "v" + VERSION, 16, DIM, W - 16, 16, "r")
        lv, into = level_of(sv["xp"])
        buy = sum(1 for k in SHOP_TOWERS if k not in sv["owned"] and TOWERS[k]["need"] <= lv and TOWERS[k]["price"] <= sv["coins"])
        buy += sum(1 for k in PERK_ORDER if k not in sv["perks"] and PERKS[k]["need"] <= lv and PERKS[k]["price"] <= sv["coins"])
        buy += sum(1 for k in ABIL_ORDER if k not in sv["abils"] and ABILS[k]["need"] <= lv and ABILS[k]["price"] <= sv["coins"])
        live = [ev for ev in EVENT_ORDER if event_state(sv, ev)[0] in ("season", "live")]
        # ---- the six buttons.  Each one opens a page with tabs for everything that belongs together
        items = [("maps", "PLAY", self.pcol(), 40, 70, "maps  -  events%s  -  tutorials" % (" (%d live)" % len(live) if live else "")),
                 ("mp", "WI-FI PLAY", MINT, 25, 54, "host or join friends on your Wi-Fi"),
                 ("towers", "ARMORY", GOLD if buy else CYAN, 25, 54, "you can afford %d new thing%s!" % (buy, "" if buy == 1 else "s") if buy else "towers  -  perks  -  loadout"),
                 ("titles", "PROFILE", PURPLE, 25, 54, "name  -  titles  -  colour and core"),
                 ("settings", "OPTIONS", CYAN, 25, 54, "settings  -  help  -  what's new  -  updates"),
                 ("quit", "QUIT", RED, 22, 40, None)]
        y = 262
        for key, lab, col, size, h, sub in items:
            if self.button("m_" + key, pygame.Rect(W // 2 - 190, y, 380, h), lab, col, size, True, sub, alpha=232) or (key == "maps" and pygame.K_RETURN in self.pressed):
                self.back_to = "menu"
                self.goto(key)
            y += h + 10
        # ---- you (bottom left)
        A = 190
        L = pygame.Rect(36, 566, 380, 134)
        panel(s, L, PANEL, A, LINE, 14, 2)
        col = self.pcol()
        cx, cy = L.x + 50, L.y + 46
        glow(s, cx, cy, 52, col, 0.8)
        bob = math.sin(t * 2.4) * 3
        pygame.draw.circle(s, scale_col(col, 0.75), (cx, cy + bob), 20)
        pygame.draw.circle(s, mix_col(col, WHITE, 0.55), (cx - 6, cy - 6 + bob), 11)
        pygame.draw.circle(s, WHITE, (cx, cy + bob), 20, 1)
        draw_text(s, sv["name"] or "PLAYER", 25, WHITE, L.x + 88, L.y + 28, "l")
        draw_text(s, TITLES[sv["title"]][0], 15, GOLD, L.x + 88, L.y + 50, "l")
        draw_text(s, "LEVEL %d   %s" % (lv, rank_of(lv)), 17, GREY, L.x + 88, L.y + 71, "l")
        r = draw_text(s, "%d" % sv["coins"], 25, GOLD, L.right - 20, L.y + 28, "r")
        pygame.draw.circle(s, GOLD, (r.x - 15, L.y + 28), 9)
        pygame.draw.circle(s, scale_col(GOLD, 0.5), (r.x - 15, L.y + 28), 5)
        bar = pygame.Rect(L.x + 20, L.y + 92, L.w - 40, 10)
        pygame.draw.rect(s, (24, 30, 60), bar, border_radius=5)
        pygame.draw.rect(s, CYAN, (bar.x, bar.y, int(bar.w * min(1.0, into / float(xp_need(lv)))), bar.h), border_radius=5)
        draw_text(s, "%d / %d XP" % (into, xp_need(lv)) if lv < MAX_LEVEL else "MAX LEVEL", 14, GREY, L.x + 20, L.y + 116, "l")
        nxt = None
        for group in (TOWERS, PERKS, ABILS, TPERKS):
            for v in group.values():
                if v["need"] > lv and not v.get("event") and (nxt is None or v["need"] < nxt[0]):
                    nxt = (v["need"], v["name"])
        if nxt:
            draw_text(s, "next:  %s  at level %d" % (nxt[1], nxt[0]), 14, MINT, L.right - 20, L.y + 116, "r")
        # ---- what you bring (bottom right)
        R = pygame.Rect(W - 36 - 380, 566, 380, 134)
        panel(s, R, PANEL, A, LINE, 14, 2)
        draw_text(s, "LOADOUT", 14, DIM, R.x + 20, R.y + 18, "l")
        n = max(1, len(sv["loadout"]))
        step = min(58, (R.w - 60) / float(n))
        for i, kind in enumerate(sv["loadout"]):
            self.tower_icon(kind, R.x + 42 + i * step, R.y + 52, 1.0, 0, 0.5)
        prev = s.get_clip()
        s.set_clip(R.inflate(-16, 0))
        for yy, head, things in ((R.y + 94, "PERKS", [(PERKS[k]["name"], CAT_COL[PERKS[k]["cat"]]) for k in sv["eq_perks"]]),
                                 (R.y + 116, "ABILITIES", [("%s  %s" % ("QR"[i], ABILS[k]["name"]), ABILS[k]["col"]) for i, k in enumerate(sv["eq_abils"])])):
            draw_text(s, head, 13, DIM, R.x + 20, yy, "l")
            x = R.x + 96
            for txt, c in things:
                x = draw_text(s, txt, 14, c, x, yy, "l").right + 14
        s.set_clip(prev)

    def screen_lobby(self, s):
        # the old lobby moved onto the title screen
        self.goto("menu")
        self.screen_menu(s)

    def screen_quit(self, s):
        self.running = False

    # ------------------------------------------------------------ your name
    def screen_name(self, s):
        self.draw_plain(s)
        if self.save["name"]:
            # not the first start: this is the NAME tab of your profile
            if self.tab_header("name", False):
                return
            if self.button("back", pygame.Rect(28, 24, 120, 44), "< BACK", GREY, 24) or pygame.K_ESCAPE in self.pressed:
                self.name_buf = self.save["name"]
                self.goto(self.back_to)
                return
        draw_glow_text(s, "WHO ARE YOU?", 64, CYAN, W // 2, 190)
        draw_text(s, "Pick a username. It floats above your orb in a match, and your friends see it on Wi-Fi.", 22, GREY, W // 2, 250)
        self.focus = "name"
        self.name_buf = self.textbox("name", pygame.Rect(W // 2 - 220, 300, 440, 60), self.name_buf, 14, "type here", 40)
        self.focus = "name"
        ok = len(self.name_buf.strip()) >= 2
        # the orb, the way others will see it
        cx, cy = W // 2, 470
        col = self.pcol()
        glow(s, cx, cy, 70, col, 0.8)
        pygame.draw.circle(s, scale_col(col, 0.75), (cx, cy + math.sin(self.time * 2.4) * 4), 22)
        pygame.draw.circle(s, mix_col(col, WHITE, 0.55), (cx - 6, cy - 7 + math.sin(self.time * 2.4) * 4), 12)
        shown = safe_name(self.name_buf)
        draw_text(s, shown or "...", 26, WHITE, cx, cy - 58)
        if shown != clean_name(self.name_buf):
            draw_text(s, "That name has a word in it that is not OK here. Other players will see PLAYER.", 18, ORANGE, W // 2, 530)
        draw_text(s, TITLES[self.save["title"]][0], 16, GOLD, cx, cy - 38)
        if (self.button("name_ok", pygame.Rect(W // 2 - 130, 560, 260, 60), "THAT'S ME", GREEN, 30, ok) or (ok and pygame.K_RETURN in self.pressed)):
            self.save["name"] = clean_name(self.name_buf)
            self.name_buf = self.save["name"]
            self.store()
            self.goto("menu" if self.back_to not in ("lobby",) else "lobby")
        if not ok:
            draw_text(s, "At least 2 letters.", 18, DIM, W // 2, 640)

    # ------------------------------------------------------------ maps
    def map_field(self, m):
        """the real shape of a map (worked out once), for the little pictures in the menus"""
        f = self.mfields.get(m["id"])
        if f is None:
            f = self.mfields[m["id"]] = Field(m["id"], False)
        return f

    def draw_minimap(self, s, m, rect, col, locked=False):
        th = THEMES[m["theme"]]
        f = self.map_field(m)
        pygame.draw.rect(s, mix_col(th["ground"], (0, 0, 0), 0.2 if not locked else 0.6), rect, border_radius=6)
        sx, sy = rect.w / float(COLS), rect.h / float(ROWS)
        prev = s.get_clip()
        s.set_clip(rect)
        for (c, r) in f.water:
            s.fill(th["water"] if not locked else scale_col(th["water"], 0.5), (rect.x + c * sx, rect.y + r * sy, sx + 1, sy + 1))
        for (c, r), h in f.hmap.items():
            s.fill(scale_col(th["cliff"], (0.5 if locked else 1.0) * min(1.6, 0.7 + 0.3 * h / STEP)), (rect.x + c * sx, rect.y + r * sy, sx + 1, sy + 1))
        k = rect.w / float(FW)
        for p in f.paths:
            pts = [(rect.x + x * k, rect.y + y * k) for x, y in p.pts]
            pygame.draw.lines(s, scale_col(col, 0.35 if locked else 0.7), False, pts, 5)
            pygame.draw.lines(s, (9, 10, 22), False, pts, 3)
            if not locked:
                # raised stretches are lighter; bridges get a white tick
                for i in range(len(p.pts) - 1):
                    if p.zs[i] > 0 or p.zs[i + 1] > 0:
                        pygame.draw.line(s, mix_col((9, 10, 22), col, 0.45), pts[i], pts[i + 1], 3)
        if not locked:
            for x, y in f.crossings:
                pygame.draw.circle(s, WHITE, (rect.x + x * k, rect.y + y * k), 2)
        ex, ey = f.core
        pygame.draw.circle(s, col if not locked else DIM, (rect.x + ex * k, rect.y + ey * k), 4)
        s.set_clip(prev)
        pygame.draw.rect(s, LINE, rect, 1, border_radius=6)

    def screen_maps(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("maps"):
            return
        if self.back_button("lobby"):
            return
        lv = self.level()
        self.sel_map = clamp(self.sel_map, 0, len(MAIN_MAPS) - 1)
        for i, m in enumerate(MAIN_MAPS):
            r = pygame.Rect(34 + (i % 7) * 174, 96 + (i // 7) * 150, 166, 140)
            locked = lv < m["need"]
            th = THEMES[m["theme"]]
            on = self.sel_map == i
            hov = r.collidepoint(self.mouse)
            pygame.draw.rect(s, mix_col(PANEL, th["accent"], 0.20 if on else 0.08 if hov else 0.03), r, border_radius=10)
            pygame.draw.rect(s, WHITE if on else th["accent"] if hov and not locked else LINE, r, 2, border_radius=10)
            self.draw_minimap(s, m, pygame.Rect(r.x + 8, r.y + 8, r.w - 16, 84), th["accent"], locked)
            draw_text(s, m["name"], 16, WHITE if not locked else DIM, r.centerx, r.y + 104)
            if locked:
                draw_text(s, "LEVEL %d" % m["need"], 14, RED, r.centerx, r.y + 124)
            else:
                for j, d in enumerate(DIFF_ORDER):
                    st = sv["stars"].get("%s:%s" % (m["id"], d), 0)
                    draw_star(s, r.centerx - 24 + j * 24, r.y + 124, 8, st > 0, DIFFS[d]["col"])
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                self.sel_map = i
        m = MAIN_MAPS[self.sel_map]
        th = THEMES[m["theme"]]
        locked = lv < m["need"]
        D = pygame.Rect(34, 404, W - 68, 290)
        panel(s, D, PANEL, 255, th["accent"], 14, 2)
        self.draw_minimap(s, m, pygame.Rect(D.x + 20, D.y + 20, 406, 250), th["accent"], locked)
        x = D.x + 450
        draw_text(s, m["name"], 38, th["accent"], x, D.y + 36, "l")
        draw_text(s, m["desc"], 19, GREY, x, D.y + 70, "l")
        if m.get("buff"):
            draw_text(s, "AT HOME HERE:  " + "    ".join("%s %s" % (TOWERS[k]["name"], buff_text(b)) for k, b in m["buff"].items()), 15, GOLD, x, D.y + 96, "l")
        for j, d in enumerate(DIFF_ORDER):
            DD = DIFFS[d]
            r = pygame.Rect(x + j * 172, D.y + 122, 160, 92)
            on = sv["diff"] == d
            if self.button("diff_" + d, r, DD["name"], DD["col"] if on else GREY, 26, True, None, mix_col(PANEL, DD["col"], 0.2) if on else None):
                sv["diff"] = d
            draw_text(s, "%d waves" % DD["waves"], 15, WHITE if on else GREY, r.centerx, r.y + 16)
            draw_text(s, "win: %d coins" % (DD["coins"] + DD["per"] * DD["waves"]), 14, GOLD if on else DIM, r.centerx, r.bottom - 26)
            draw_text(s, "final boss %dk hp" % (DD["boss"] // 1000), 13, RED if on else DIM, r.centerx, r.bottom - 11)
        key = "%s:%s" % (m["id"], sv["diff"])
        best = sv["best"].get(key, 0)
        st = sv["stars"].get(key, 0)
        info = "Best: wave %d of %d" % (best, DIFFS[sv["diff"]]["waves"]) if best else "Not played yet"
        if not st and not locked:
            info += "      first clear bonus: +%d coins" % DIFFS[sv["diff"]]["first"]
        draw_text(s, info, 17, GREY, x, D.y + 238, "l")
        if st:
            for i in range(3):
                draw_star(s, x + 14 + i * 26, D.y + 264, 10, i < st)
            if sv["diff"] == "insane":
                draw_text(s, "title earned:  " + m["title"], 15, GOLD, x + 100, D.y + 264, "l")
        elif sv["diff"] == "insane":
            draw_text(s, "win here for the title:  " + m["title"], 15, DIM, x, D.y + 264, "l")
        B = pygame.Rect(D.right - 250, D.y + 122, 226, 98)
        if locked:
            self.button("deploy", B, "LOCKED", RED, 32, False, "reach level %d" % m["need"])
        elif self.button("deploy", B, "DEPLOY", GREEN, 40, True, "ENTER") or pygame.K_RETURN in self.pressed:
            self.store()
            self.start_game(m["id"], sv["diff"])
            return
        g = guide_of(m["id"], sv["diff"])
        if self.button("mguide", pygame.Rect(B.x, B.bottom + 8, B.w, 44), "WATCH THE TUTORIAL", PINK, 17, g is not None, "needs level %d" % g["need"] if g else None):
            self.start_video(m["id"], sv["diff"], "maps")

    # ------------------------------------------------------------ events
    def screen_events(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("events"):
            return
        if self.back_button("lobby"):
            return
        draw_text(s, "Beat an event level to earn its tower.  Seasons follow the calendar.  Secret events are hidden on the maps: talk to people.", 17, GREY, W // 2, 92)
        now = time.time()
        for i, ev in enumerate(EVENT_ORDER):
            E = EVENTS[ev]
            m = MAP_BY_ID[ev]
            state, left = event_state(sv, ev, now)
            r = pygame.Rect(34 + (i % 4) * 304, 116 + (i // 4) * 292, 296, 280)
            col = E["col"]
            known = state != "locked" or E["kind"] == "season"
            pygame.draw.rect(s, mix_col(PANEL, col, 0.10 if state in ("season", "live") else 0.03), r, border_radius=14)
            pygame.draw.rect(s, col if state in ("season", "live") else LINE, r, 2, border_radius=14)
            kind = E["tower"]
            have = sv["etowers"].get(kind)
            if known:
                draw_text(s, E["name"], 24, col, r.x + 16, r.y + 24, "l")
                self.draw_minimap(s, m, pygame.Rect(r.x + 16, r.y + 46, 150, 92), col, state == "locked")
            else:
                draw_text(s, "? ? ?", 24, DIM, r.x + 16, r.y + 24, "l")
                pygame.draw.rect(s, (10, 12, 26), (r.x + 16, r.y + 46, 150, 92), border_radius=6)
                draw_text(s, "?", 60, (30, 36, 66), r.x + 91, r.y + 92)
            self.chip("SEASON" if E["kind"] == "season" else "SECRET", col if known else DIM, r.right - 80, r.y + 24, 13)
            # the prize
            if known:
                self.tower_icon(kind, r.x + 232, r.y + 92, 1.5, 4 if have else 0, 0.5, not have)
                draw_text(s, TOWERS[kind]["name"] + (" RIPOFF" if have == "ripoff" else ""), 13, WHITE if have else GREY, r.x + 232, r.y + 136)
            else:
                draw_text(s, "prize: ?", 14, DIM, r.x + 232, r.y + 92)
            y = r.y + 160
            if state == "season":
                draw_text(s, "%s IS ON   -   %d day%s left" % (E["label"], left, "" if left == 1 else "s"), 16, GREEN, r.x + 16, y, "l")
                draw_text(s, "Win now for the REAL tower.", 14, GREY, r.x + 16, y + 20, "l")
            elif state == "live":
                d, h = int(left // 86400), int(left % 86400 // 3600)
                draw_text(s, "LIVE   -   %dd %dh left" % (d, h), 16, GREEN, r.x + 16, y, "l")
                draw_text(s, "Win before it ends for the REAL tower.", 14, GREY, r.x + 16, y + 20, "l")
            elif state == "late":
                draw_text(s, "OUT OF SEASON" if E["kind"] == "season" else "THE EVENT IS OVER", 16, GOLD, r.x + 16, y, "l")
                draw_text(s, "Still playable. The prize is a RIPOFF.", 14, GREY, r.x + 16, y + 20, "l")
            elif E["kind"] == "season":
                (m0, d0), (m1, d1) = E["season"]
                mn = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
                draw_text(s, "OUT OF SEASON   (%s %d - %s %d)" % (mn[m0], d0, mn[m1], d1), 15, DIM, r.x + 16, y, "l")
                draw_text(s, E["hint"], 13, GREY, r.x + 16, y + 20, "l")
            else:
                draw_text(s, "NOT FOUND YET", 16, DIM, r.x + 16, y, "l")
                for j, ln in enumerate(wrap("Rumour: " + E["hint"], 14, r.w - 32)[:2]):
                    draw_text(s, ln, 14, GREY, r.x + 16, y + 20 + j * 16, "l")
            done = sv["edone"].get(ev, 0)
            draw_text(s, ("Beaten %d time%s" % (done, "" if done == 1 else "s")) if done else "25 waves   -   800 coins   -   title: " + TITLES[E["title"]][0], 13, GOLD if done else DIM, r.x + 16, r.bottom - 68, "l")
            B = pygame.Rect(r.x + 16, r.bottom - 54, r.w - 32 - 96, 42)
            if state == "locked":
                self.button("ev_" + ev, B, "LOCKED", GREY, 20, False)
            elif self.button("ev_" + ev, B, "PLAY", col, 24):
                self.start_game(ev, "event")
                return
            if known and self.button("evg_" + ev, pygame.Rect(B.right + 8, B.y, 88, 42), "TUTORIAL", PINK, 13):
                self.start_video(ev, "event", "events")
        r = pygame.Rect(34 + 3 * 304, 116 + 292, 296, 280)
        panel(s, r, PANEL, 255, LINE, 14, 2)
        lines = ["HOW EVENTS WORK", "", "A tower earned while its event is", "on keeps its real name forever.", "",
                 "Earn it after the event is over", "and it is called a RIPOFF.", "Same tower, different name.", "",
                 "Secret events last %d days from" % EVENT_DAYS, "the moment you find them."]
        for i, ln in enumerate(lines):
            draw_text(s, ln, 20 if i == 0 else 15, GOLD if i == 0 else GREY, r.centerx, r.y + 30 + i * 21)

    # ------------------------------------------------------------ titles
    def screen_titles(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("titles", False):
            return
        if self.back_button("lobby"):
            return
        draw_text(s, "Your title shows under your name on the main menu, above your orb in a match, and to your friends on Wi-Fi.  Click one to wear it.", 17, GREY, W // 2, 92)
        for i, k in enumerate(TITLE_ORDER):
            name, how = TITLES[k]
            r = pygame.Rect(34 + (i % 4) * 304, 114 + (i // 4) * 73, 296, 66)
            have = k in sv["titles"]
            on = sv["title"] == k
            hov = r.collidepoint(self.mouse) and have
            pygame.draw.rect(s, mix_col(PANEL, GOLD, 0.22 if on else 0.10 if hov else 0.02), r, border_radius=10)
            pygame.draw.rect(s, GOLD if on else WHITE if hov else LINE, r, 2, border_radius=10)
            draw_text(s, name, 20, GOLD if on else WHITE if have else DIM, r.x + 14, r.y + 22, "l")
            draw_text(s, how, 13, GREY if have else DIM, r.x + 14, r.y + 46, "l")
            if on:
                draw_text(s, "WEARING", 12, GREEN, r.right - 12, r.y + 16, "r")
            elif not have:
                draw_text(s, "LOCKED", 12, DIM, r.right - 12, r.y + 16, "r")
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                sv["title"] = k
                self.store()

    # ------------------------------------------------------------ strat videos
    def screen_videos(self, s):
        """tutorials: pick a map, then a difficulty"""
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("videos", False):
            return
        if self.back_button("lobby"):
            return
        draw_text(s, "One for every map on every difficulty. The bot plays the whole match live with the cheapest setup that wins: watch where things go.", 17, GREY, W // 2, 88)
        lv = self.level()
        have = self.have_towers()
        self.sel_guide = clamp(self.sel_guide, 0, len(MAPS) - 1)
        for i, m in enumerate(MAPS):
            r = pygame.Rect(34 + (i % 7) * 174, 104 + (i // 7) * 98, 166, 92)
            th = THEMES[m["theme"]]
            on = self.sel_guide == i
            hov = r.collidepoint(self.mouse)
            pygame.draw.rect(s, mix_col(PANEL, th["accent"], 0.20 if on else 0.08 if hov else 0.03), r, border_radius=10)
            pygame.draw.rect(s, WHITE if on else th["accent"] if hov else LINE, r, 2, border_radius=10)
            self.draw_minimap(s, m, pygame.Rect(r.x + 8, r.y + 6, r.w - 16, 58), th["accent"])
            draw_text(s, m["name"], 14, WHITE, r.centerx, r.y + 77)
            if m.get("event"):
                draw_text(s, "EVENT", 10, MAGENTA, r.right - 8, r.y + 12, "r")
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                self.sel_guide = i
        m = MAPS[self.sel_guide]
        th = THEMES[m["theme"]]
        D = pygame.Rect(34, 404, W - 68, 290)
        panel(s, D, PANEL, 255, th["accent"], 14, 2)
        draw_text(s, m["name"], 30, th["accent"], D.x + 20, D.y + 28, "l")
        if m.get("buff"):
            draw_text(s, "AT HOME HERE:  " + "     ".join("%s %s" % (TOWERS[k]["name"], buff_text(b)) for k, b in m["buff"].items()), 15, GOLD, D.x + 20, D.y + 56, "l")
        diffs = ["event"] if m.get("event") else DIFF_ORDER
        cw = (D.w - 40 - 16 * (len(diffs) - 1)) // len(diffs) if len(diffs) > 1 else 560
        for j, d in enumerate(diffs):
            g = guide_of(m["id"], d)
            DD = DIFFS[d]
            r = pygame.Rect(D.x + 20 + j * (cw + 16), D.y + 74, cw, 204)
            pygame.draw.rect(s, mix_col(PANEL, DD["col"], 0.07), r, border_radius=12)
            pygame.draw.rect(s, scale_col(DD["col"], 0.7), r, 2, border_radius=12)
            draw_text(s, DD["name"], 24, DD["col"], r.x + 16, r.y + 22, "l")
            draw_text(s, "%d waves" % DD["waves"], 14, GREY, r.x + 16, r.y + 44, "l")
            if g is None:
                draw_text(s, "No tutorial yet.", 16, DIM, r.centerx, r.centery)
                continue
            ok = lv >= g["need"]
            draw_text(s, "NEEDS LEVEL %d" % g["need"], 18, GREEN if ok else RED, r.right - 16, r.y + 22, "r")
            draw_text(s, "you are level %d" % lv if not ok else "you can do this now", 13, GREY, r.right - 16, r.y + 44, "r")
            for q, kind in enumerate(g["loadout"]):
                self.tower_icon(kind, r.x + 34 + q * 46, r.y + 84, 0.82, 0, 0.0, kind not in have)
            draw_text(s, "PERKS", 12, DIM, r.x + 16, r.y + 122, "l")
            draw_text(s, ",  ".join(PERKS[k]["name"] for k in g["perks"]), 14, WHITE, r.x + 66, r.y + 122, "l")
            draw_text(s, "ABILITY", 12, DIM, r.x + 16, r.y + 142, "l")
            draw_text(s, ",  ".join(ABILS[k]["name"] for k in g["abils"]), 14, WHITE, r.x + 76, r.y + 142, "l")
            if g["tperks"]:
                draw_text(s, "+ %d tower perk%s" % (len(g["tperks"]), "" if len(g["tperks"]) == 1 else "s"), 13, CYAN, r.x + 16, r.y + 160, "l")
            if "g:" + g["key"] in sv["seen"]:
                draw_text(s, "WATCHED", 12, GREEN, r.x + 16, r.bottom - 22, "l")
            if self.button("gd_" + d, pygame.Rect(r.right - 146, r.bottom - 56, 130, 44), "WATCH", PINK, 22):
                self.start_video(m["id"], d, "videos")

    def start_video(self, mapid, diff, back="videos"):
        v = guide_of(mapid, diff)
        if v is None:
            self.pop("There is no tutorial for that one yet", GREY)
            return
        spec = dict(name="GUIDE", col=list(PINK), title="TUTORIAL", loadout=v["loadout"], perks=v["perks"], abils=v["abils"], tperks=v["tperks"])
        w = World(v["map"], v["diff"], [spec], seed=v["seed"])
        w.numbers = False
        self.video = dict(v=v, w=w, bot=Bot(w, v["seed"]), speed=2, shown=0, flat=True, done=False, acc=0.0, back=back)
        if "g:" + v["key"] not in self.save["seen"]:
            self.save["seen"].append("g:" + v["key"])
            self.store()
        self.goto("video")

    def screen_video(self, s):
        V = self.video
        v = V["v"]
        w = V["w"]
        P = w.players[0]
        if pygame.K_ESCAPE in self.pressed:
            self.video = None
            self.goto(V.get("back", "videos"))
            return
        if pygame.K_SPACE in self.pressed:
            V["speed"] = 0 if V["speed"] else 2
        # the bot plays at a fixed step so the same guide always plays out the same way
        V["acc"] += self.dt * V["speed"]
        n = 0
        while V["acc"] >= 1 / 30.0 and n < 16:
            V["acc"] -= 1 / 30.0
            n += 1
            w.update(1 / 30.0)
            V["bot"].step(1 / 30.0)
        if n >= 16:
            V["acc"] = 0.0
        for name, vol in w.ev:
            self.audio.play(name, vol * 0.5)
        del w.ev[:]
        while V["shown"] < len(w.guide):
            g = w.guide[V["shown"]]
            V["shown"] += 1
            if g[2] is not None:
                w.ring(g[2], g[3], 70, 12, GOLD, 1.2, 4, 2)
        cam = self.cam
        cam.cx, cam.cy = W / 2.0, H / 2.0
        if V["flat"]:
            cam.flat(W / 2.0 + 110, 60 + 300, FW / 2.0, FH / 2.0, 0.84)
        else:
            cam.ortho = False
            cam.cy = H / 2.0 + 30
            cam.look(FW / 2.0, FH / 2.0, 0, 860, -math.pi / 2 + math.sin(self.time * 0.15) * 0.6, 0.85)
        self.scene.draw(s, w, cam, dict(t=w.time, detail=self.save["settings"]["detail"], ranges=False, boxes=False, names=False, players=False,
                                        core_col=PINK, core_skin=0, seen=[n_["id"] for n_ in w.npcs]))
        self.draw_banner(s, w)
        # top bar
        top = pygame.Rect(0, 0, W, 54)
        panel(s, top, (8, 10, 24), 225, LINE, 0, 0)
        draw_text(s, "TUTORIAL:  " + v["title"], 20, PINK, 18, 18, "l")
        draw_text(s, "needs level %d" % v["need"], 15, GREY, 18, 40, "l")
        draw_text(s, "WAVE %d / %d" % (w.wave, w.nwaves), 24, WHITE, 560, 28, "l")
        draw_text(s, "CASH %d" % P.cash, 22, GOLD, 730, 28, "l")
        draw_text(s, "CORE %d / %d" % (max(0, w.hp), w.maxhp), 22, GREEN if w.hp > w.maxhp * 0.5 else RED, 880, 28, "l")
        for i, sp in enumerate((0, 1, 2, 4, 8)):
            if self.button("vsp%d" % sp, pygame.Rect(1030 + i * 48, 12, 44, 30), "II" if sp == 0 else "%dx" % sp, GOLD if V["speed"] == sp else GREY, 18):
                V["speed"] = sp
        # the plan, left
        L = pygame.Rect(0, 60, 258, H - 60)
        panel(s, L, PANEL, 232, LINE, 0, 0)
        y = L.y + 18
        draw_text(s, "LOADOUT", 14, DIM, 14, y, "l")
        y += 26
        for kind in v["loadout"]:
            self.tower_icon(kind, 30, y, 0.75, 0, 0.0)
            draw_text(s, TOWERS[kind]["name"], 16, TOWERS[kind]["col"], 56, y, "l")
            y += 30
        draw_text(s, "PERKS", 14, DIM, 14, y + 4, "l")
        y += 24
        for k in v["perks"]:
            draw_text(s, PERKS[k]["name"], 15, CAT_COL[PERKS[k]["cat"]], 14, y, "l")
            y += 18
        for k in v["abils"]:
            draw_text(s, ABILS[k]["name"], 15, ABILS[k]["col"], 14, y, "l")
            y += 18
        y += 8
        draw_text(s, "WHAT IT IS DOING", 14, DIM, 14, y, "l")
        y += 22
        rows = (H - y - 96) // 18
        for g in w.guide[-rows:]:
            col = WHITE if g is w.guide[-1] else GREY
            draw_text(s, "W%d" % max(1, g[0] + (1 if w.phase == "build" and False else 0)), 13, DIM, 14, y, "l")
            txt = g[1]
            while font(14).size(txt)[0] > 200 and len(txt) > 4:
                txt = txt[:-2]
            draw_text(s, txt, 14, col, 48, y, "l")
            y += 18
        for j, ln in enumerate(wrap(v["blurb"], 14, 236)[:4]):
            draw_text(s, ln, 14, MINT, 14, H - 78 + j * 16, "l")
        if self.button("vcam", pygame.Rect(W - 300, H - 60, 136, 44), "VIEW: 2D" if V["flat"] else "VIEW: 3D", CYAN, 20, alpha=232):
            V["flat"] = not V["flat"]
        if self.button("vback", pygame.Rect(W - 152, H - 60, 136, 44), "BACK", GREY, 22, alpha=232):
            self.video = None
            self.goto(V.get("back", "videos"))
            return
        if w.phase == "over":
            col = GOLD if w.result == "win" else RED
            r = pygame.Rect(0, 0, 560, 130)
            r.center = (W // 2 + 110, H // 2)
            panel(s, r, PANEL, 240, col, 16, 3)
            draw_glow_text(s, "TRIUMPH" if w.result == "win" else "DEFEAT", 60, col, r.centerx, r.y + 46)
            draw_text(s, "That is the whole strategy. Your turn." if w.result == "win" else "Even guides have bad days.", 18, GREY, r.centerx, r.y + 98)


    # ------------------------------------------------------------ towers: shop, loadout, paint
    def screen_towers(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("towers"):
            return
        if self.back_button():
            if self.back_to == "room":
                self.room_spec()
            return
        lv = self.level()
        slots = loadout_slots(lv)
        have = self.have_towers()
        if self.view not in TOWERS:
            self.view = "blaster"
        for i, kind in enumerate(TOWER_ORDER):
            T = TOWERS[kind]
            r = pygame.Rect(34 + (i % 7) * 120, 96 + (i // 7) * 108, 114, 102)
            owned = kind in have
            ev = T.get("event")
            locked = (lv < T["need"]) if not ev else not owned
            col = self.tcol(kind)
            on = self.view == kind
            hov = r.collidepoint(self.mouse)
            pygame.draw.rect(s, mix_col(PANEL, col, 0.24 if on else 0.12 if hov else 0.04), r, border_radius=10)
            pygame.draw.rect(s, WHITE if on else col if (hov or kind in sv["loadout"]) else LINE, r, 2, border_radius=10)
            self.tower_icon(kind, r.centerx, r.y + 40, 1.15, 0, 0.5 if (hov or on) else 0.0, locked)
            nm = T["name"]
            draw_text(s, nm, 14 if len(nm) < 12 else 12, WHITE if not locked else DIM, r.centerx, r.y + 74)
            if kind in sv["loadout"]:
                draw_text(s, "IN LOADOUT", 12, GREEN, r.centerx, r.y + 90)
            elif owned:
                draw_text(s, "OWNED" if sv["etowers"].get(kind) != "ripoff" else "RIPOFF", 12, GREY, r.centerx, r.y + 90)
            elif ev:
                draw_text(s, "EVENT", 12, EVENTS[ev]["col"], r.centerx, r.y + 90)
            elif locked:
                draw_text(s, "LEVEL %d" % T["need"], 12, RED, r.centerx, r.y + 90)
            else:
                draw_text(s, "%d COINS" % T["price"], 12, GOLD if sv["coins"] >= T["price"] else ORANGE, r.centerx, r.y + 90)
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                self.view = kind
        # ---- loadout bar
        draw_text(s, "YOUR LOADOUT   %d / %d" % (len(sv["loadout"]), slots), 16, DIM, 34, 548, "l")
        draw_text(s, "click a slot to take that tower out", 14, DIM, 866, 548, "r")
        for i in range(6):
            r = pygame.Rect(34 + i * 139, 562, 133, 76)
            if i >= slots:
                pygame.draw.rect(s, (10, 12, 26), r, border_radius=10)
                pygame.draw.rect(s, (24, 30, 56), r, 2, border_radius=10)
                draw_text(s, "LEVEL 8", 14, DIM, r.centerx, r.centery)
                continue
            if i < len(sv["loadout"]):
                kind = sv["loadout"][i]
                col = self.tcol(kind)
                hov = r.collidepoint(self.mouse)
                pygame.draw.rect(s, mix_col(PANEL, col, 0.22 if hov else 0.12), r, border_radius=10)
                pygame.draw.rect(s, col, r, 2, border_radius=10)
                self.tower_icon(kind, r.x + 34, r.y + 34, 1.0, 0, 0.0)
                nm = TOWERS[kind]["name"]
                draw_text(s, nm, 14 if len(nm) < 11 else 11, WHITE, r.x + 66, r.y + 28, "l")
                draw_text(s, "key %s" % self.kname("slot%d" % (i + 1)), 12, DIM, r.x + 66, r.y + 48, "l")
                if hov and self.click:
                    self.click = False
                    if len(sv["loadout"]) > 1:
                        sv["loadout"].remove(kind)
                        self.audio.play("sell")
                        self.store()
                    else:
                        self.audio.play("error")
            else:
                pygame.draw.rect(s, (12, 15, 32), r, border_radius=10)
                pygame.draw.rect(s, LINE, r, 2, border_radius=10)
                draw_text(s, "EMPTY", 14, DIM, r.centerx, r.centery)
        draw_text(s, "Bring a mix: something cheap for early waves, an AOE tower for swarms, a heavy hitter for bosses.", 14, DIM, 34, 660, "l")
        draw_text(s, "GROUND towers go on the floor, CLIFF towers on the raised plateaus, PATH towers on the road itself.", 14, DIM, 34, 680, "l")
        # ---- the tower you are looking at
        kind = self.view
        T = TOWERS[kind]
        D = pygame.Rect(880, 96, 366, 604)
        col = self.tcol(kind)
        panel(s, D, PANEL, 255, col, 16, 2)
        self.tower_icon(kind, D.x + 54, D.y + 50, 1.9, self.view_lv, 0.6)
        nm = self.tname(kind)
        draw_text(s, nm, 30 if len(nm) < 13 else 22 if len(nm) < 18 else 17, col, D.x + 108, D.y + 32, "l")
        x = D.x + 108
        x = self.chip(T["tier"] + (" GAME" if T["tier"] != "EVENT" else ""), CYAN, x, D.y + 62, 13)
        x = self.chip(T["atk"], PINK, x, D.y + 62, 13)
        if T.get("aoe"):
            self.chip("AOE", ORANGE, x, D.y + 62, 13)
        draw_text(s, "PLACE:  " + PLACE_NAME[T["place"]], 16, PLACE_COL[T["place"]], D.x + 108, D.y + 88, "l")
        y = D.y + 116
        for ln in wrap(self.ktext(T["desc"]), 15, D.w - 40)[:5]:
            draw_text(s, ln, 15, GREY, D.x + 20, y, "l")
            y += 17
        for i in range(MAXLV + 1):
            if self.button("vlv%d" % i, pygame.Rect(D.x + 20 + i * 66, D.y + 204, 60, 28), "MAX" if i == MAXLV else "LV %d" % (i + 1),
                           GOLD if self.view_lv == i else GREY, 17):
                self.view_lv = i
        L = T["lv"][self.view_lv]
        y = D.y + 250
        rows = tower_stats(kind, L)
        d = tower_dps(kind, L)
        if d and not is_path(kind):
            rows.append(("DAMAGE / SEC", "%d" % round(d)))
        rows.append(("COST TO PLACE" if self.view_lv == 0 else "UPGRADE COST", "%d cash" % L["cost"]))
        rows.append(("TOTAL SO FAR", "%d cash" % sum(v["cost"] for v in T["lv"][:self.view_lv + 1])))
        for lab, val in rows[:8]:
            draw_text(s, lab, 14, DIM, D.x + 20, y, "l")
            draw_text(s, val, 16, WHITE, D.right - 20, y, "r")
            y += 20
        for i, ln in enumerate(wrap('"' + T["lore"] + '"', 14, D.w - 40)[:2]):
            draw_text(s, ln, 14, mix_col(col, GREY, 0.55), D.x + 20, D.y + 418 + i * 15, "l")
        # paint
        draw_text(s, "PAINT", 13, DIM, D.x + 20, D.y + 458, "l")
        cur = sv["paint"].get(kind, 0)
        for i in range(len(PAINTS)):
            pc = PAINTS[i] or T["col"]
            r = pygame.Rect(D.x + 66 + i * 18, D.y + 449, 16, 18)
            pygame.draw.rect(s, pc, r, border_radius=4)
            if i == 0:
                pygame.draw.line(s, (10, 10, 16), (r.x + 3, r.bottom - 4), (r.right - 4, r.y + 3), 2)
            if cur == i:
                pygame.draw.rect(s, WHITE, r.inflate(4, 4), 2, border_radius=5)
            if r.collidepoint(self.mouse) and self.click:
                self.click = False
                self.audio.play("click")
                if i:
                    sv["paint"][kind] = i
                else:
                    sv["paint"].pop(kind, None)
                self.store()
        # tower perk
        tp = TPERK_OF.get(kind)
        PR = pygame.Rect(D.x + 14, D.y + 480, D.w - 28, 54)
        pygame.draw.rect(s, (16, 20, 42), PR, border_radius=10)
        if tp is None:
            draw_text(s, "Event towers have no perk. They are weird enough.", 14, DIM, PR.centerx, PR.centery)
        else:
            p = TPERKS[tp]
            eq = sv["eq_tperks"].get(kind) == tp
            pygame.draw.rect(s, CYAN if eq else LINE, PR, 1, border_radius=10)
            draw_text(s, "PERK:  " + p["name"], 15, CYAN if tp in sv["tperks"] else GREY, PR.x + 10, PR.y + 14, "l")
            for i, ln in enumerate(wrap(p["desc"], 12, PR.w - 126)[:2]):
                draw_text(s, ln, 12, GREY, PR.x + 10, PR.y + 31 + i * 12, "l")
            B = pygame.Rect(PR.right - 108, PR.y + 8, 100, PR.h - 16)
            if tp in sv["tperks"]:
                if self.button("tp_act", B, "ON" if eq else "PUT ON", GREEN if eq else CYAN, 17):
                    if eq:
                        sv["eq_tperks"].pop(kind, None)
                    else:
                        sv["eq_tperks"][kind] = tp
                    self.store()
            elif lv < p["need"]:
                self.button("tp_act", B, "LEVEL %d" % p["need"], RED, 15, False)
            elif sv["coins"] >= p["price"]:
                if self.button("tp_act", B, "BUY", GOLD, 18, True, "%d" % p["price"]):
                    sv["coins"] -= p["price"]
                    sv["tperks"].append(tp)
                    sv["eq_tperks"][kind] = tp
                    self.audio.play("upgrade")
                    self.pop("%s unlocked!" % p["name"], CYAN, 2.4)
                    self.fix_save()
                    self.store()
            else:
                self.button("tp_act", B, "%d" % p["price"], GOLD, 17, False, "coins")
        # buy / equip
        B = pygame.Rect(D.x + 20, D.bottom - 62, D.w - 40, 50)
        owned = kind in have
        ev = T.get("event")
        if ev and not owned:
            st = event_state(sv, ev)[0]
            self.button("t_act", B, "WIN %s TO EARN IT" % EVENTS[ev]["name"] if st != "locked" else "A SECRET EVENT GIVES THIS", EVENTS[ev]["col"], 17, False)
        elif lv < T["need"] and not owned:
            self.button("t_act", B, "UNLOCKS AT LEVEL %d" % T["need"], RED, 22, False)
        elif not owned:
            if sv["coins"] >= T["price"]:
                if self.button("t_act", B, "BUY   -   %d COINS" % T["price"], GOLD, 24):
                    sv["coins"] -= T["price"]
                    sv["owned"].append(kind)
                    if len(sv["loadout"]) < slots:
                        sv["loadout"].append(kind)
                    self.fix_save()
                    self.audio.play("upgrade")
                    self.pop("%s unlocked!" % T["name"], T["col"], 2.5)
                    self.store()
            else:
                self.button("t_act", B, "NEED %d COINS  (you have %d)" % (T["price"], sv["coins"]), GOLD, 18, False)
        elif kind in sv["loadout"]:
            if self.button("t_act", B, "TAKE OUT OF LOADOUT", ORANGE, 22, len(sv["loadout"]) > 1):
                sv["loadout"].remove(kind)
                self.audio.play("sell")
                self.store()
        elif len(sv["loadout"]) >= slots:
            self.button("t_act", B, "LOADOUT FULL  -  take one out first", GREY, 18, False)
        elif self.button("t_act", B, "ADD TO LOADOUT", GREEN, 24):
            sv["loadout"].append(kind)
            self.audio.play("place")
            self.store()

    # ------------------------------------------------------------ perks
    def perk_row(self, key, r, name, col, tag, desc, need, price, owned, equipped, small=False):
        s = self.s
        sv = self.save
        lv = self.level()
        pygame.draw.rect(s, mix_col(PANEL, col, 0.16 if equipped else 0.04), r, border_radius=12)
        pygame.draw.rect(s, col if equipped else LINE, r, 2, border_radius=12)
        x = self.chip(tag, col, r.x + 14, r.y + (18 if not small else 15), 13)
        draw_text(s, name, 22 if not small else 17, WHITE, x + 4, r.y + (19 if not small else 15), "l")
        for i, ln in enumerate(wrap(desc, 15 if not small else 13, r.w - 190)[:2 if not small else 1]):
            draw_text(s, ln, 15 if not small else 13, GREY, r.x + 14, r.y + (42 if not small else 35) + i * 15, "l")
        B = pygame.Rect(r.right - 152, r.y + 9, 142, r.h - 18)
        if equipped:
            if self.button(key, B, "ON", GREEN, 20, True, "click to take off" if not small else None):
                return "off"
        elif owned:
            if self.button(key, B, "PUT ON", CYAN, 20):
                return "equip"
        elif lv < need:
            self.button(key, B, "LEVEL %d" % need, RED, 18, False)
        elif sv["coins"] >= price:
            if self.button(key, B, "BUY", GOLD, 20, True, "%d coins" % price if not small else None) :
                return "buy"
            if small:
                draw_text(s, "%d" % price, 12, GOLD, B.centerx, B.bottom - 8)
        else:
            self.button(key, B, "%d COINS" % price, GOLD, 17, False)
        return None

    def screen_perks(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("perks"):
            return
        if self.back_button():
            if self.back_to == "room":
                self.room_spec()
            return
        lv = self.level()
        for i, name in enumerate(("NORMAL", "ABILITY", "TOWER")):
            if self.button("pk_tab%d" % i, pygame.Rect(34 + i * 190, 88, 180, 38), name, GOLD if self.perk_tab == i else GREY, 20):
                self.perk_tab = i
        tab = self.perk_tab
        if tab == 0:
            ns = perk_slots(lv)
            draw_text(s, "WEARING %d / %d      They all stack.  More slots at level 6 and 14." % (len(sv["eq_perks"]), ns), 17, GREY, 620, 107, "l")
            for i, k in enumerate(PERK_ORDER):
                p = PERKS[k]
                r = pygame.Rect(34 + (i // 7) * 610, 138 + (i % 7) * 80, 602, 74)
                act = self.perk_row("pk_" + k, r, p["name"], CAT_COL[p["cat"]], p["cat"], p["desc"], p["need"], p["price"], k in sv["perks"], k in sv["eq_perks"])
                if act == "buy":
                    sv["coins"] -= p["price"]
                    sv["perks"].append(k)
                    if len(sv["eq_perks"]) < ns:
                        sv["eq_perks"].append(k)
                    self.audio.play("upgrade")
                    self.pop("%s unlocked!" % p["name"], CAT_COL[p["cat"]], 2.4)
                elif act == "equip":
                    if len(sv["eq_perks"]) >= ns:
                        self.pop("All %d perk slots are full. Take one off first." % ns, RED, 2.4)
                        self.audio.play("error")
                    else:
                        sv["eq_perks"].append(k)
                        self.audio.play("place")
                elif act == "off":
                    if len(sv["eq_perks"]) > 0:
                        sv["eq_perks"].remove(k)
                        self.audio.play("sell")
                if act:
                    self.store()
        elif tab == 1:
            ns = abil_slots(lv)
            draw_text(s, "WEARING %d / %d      Keys %s and %s in a match.  Second slot at level 10." % (len(sv["eq_abils"]), ns, self.kname("abil1"), self.kname("abil2")), 17, GREY, 620, 107, "l")
            for i, k in enumerate(ABIL_ORDER):
                p = ABILS[k]
                r = pygame.Rect(34, 138 + i * 80, 602, 74)
                act = self.perk_row("ab_" + k, r, p["name"], p["col"], "%ds" % p["cd"], p["desc"], p["need"], p["price"], k in sv["abils"], k in sv["eq_abils"])
                if act == "buy":
                    sv["coins"] -= p["price"]
                    sv["abils"].append(k)
                    if len(sv["eq_abils"]) < ns:
                        sv["eq_abils"].append(k)
                    self.audio.play("upgrade")
                    self.pop("%s unlocked!" % p["name"], p["col"], 2.4)
                elif act == "equip":
                    if len(sv["eq_abils"]) >= ns:
                        if ns == 1:
                            sv["eq_abils"] = [k]
                            self.audio.play("place")
                        else:
                            self.pop("Both ability slots are full. Take one off first.", RED, 2.4)
                            self.audio.play("error")
                    else:
                        sv["eq_abils"].append(k)
                        self.audio.play("place")
                elif act == "off":
                    if len(sv["eq_abils"]) > 1:
                        sv["eq_abils"].remove(k)
                        self.audio.play("sell")
                    else:
                        self.pop("Keep at least one ability.", GREY, 2.0)
                if act:
                    self.store()
            I = pygame.Rect(650, 138, 596, 554)
            panel(s, I, PANEL, 255, LINE, 12, 2)
            lines = ["ABILITY PERKS", "",
                     "Ability perks are not towers. You do not place or upgrade them.",
                     "Press %s (or %s for your second one), aim the circle, and click." % (self.kname("abil1"), self.kname("abil2")),
                     "You can drop it anywhere, but the road is where the enemies are.",
                     "It hits everything inside, plays out, and is gone.",
                     "Then it recharges. The timer only runs while a wave is going.",
                     "You can wear two at most.", "",
                     "NORMAL PERKS", "",
                     "Always on for the whole match, and they STACK with each other:",
                     "ATTACK perks hit harder, RANGE perks reach further,",
                     "SUPPORT perks help your cash and your core.", "",
                     "TOWER PERKS", "",
                     "Each one fits exactly one tower and changes how it works.",
                     "One per tower. Other players can see them on your towers."]
            for i, ln in enumerate(lines):
                head = ln in ("ABILITY PERKS", "NORMAL PERKS", "TOWER PERKS")
                draw_text(s, ln, 20 if head else 17, GOLD if head else GREY, I.x + 26, I.y + 34 + i * 26, "l")
        else:
            draw_text(s, "One perk per tower.  You need the tower to make use of it.", 17, GREY, 620, 107, "l")
            have = self.have_towers()
            for i, k in enumerate(TPERK_ORDER):
                p = TPERKS[k]
                tw = p["tower"]
                r = pygame.Rect(34 + (i // 10) * 610, 138 + (i % 10) * 56, 602, 52)
                eq = sv["eq_tperks"].get(tw) == k
                act = self.perk_row("tp_" + k, r, p["name"], TOWERS[tw]["col"], TOWERS[tw]["name"], p["desc"], p["need"], p["price"], k in sv["tperks"], eq, True)
                if act == "buy":
                    sv["coins"] -= p["price"]
                    sv["tperks"].append(k)
                    sv["eq_tperks"][tw] = k
                    self.audio.play("upgrade")
                    self.pop("%s unlocked!%s" % (p["name"], "" if tw in have else "  (you still need the %s)" % TOWERS[tw]["name"]), CYAN, 3.0)
                elif act == "equip":
                    sv["eq_tperks"][tw] = k
                    self.audio.play("place")
                elif act == "off":
                    sv["eq_tperks"].pop(tw, None)
                    self.audio.play("sell")
                if act:
                    self.fix_save()
                    self.store()

    # ------------------------------------------------------------ your colour and your core
    def screen_customize(self, s):
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("customize", False):
            return
        if self.back_button():
            self.store()
            if self.back_to == "room":
                self.room_spec()
            return
        col = self.pcol()
        L = pygame.Rect(60, 110, 520, 560)
        panel(s, L, PANEL, 255, col, 16, 2)
        m = core_model(sv["skin"])
        self.scene.icon(s, m, col, L.centerx - 90, L.y + 330, 4.2, self.time, 0.5)
        cx, cy = L.centerx + 150, L.y + 250
        glow(s, cx, cy, 70, col, 0.8)
        bob = math.sin(self.time * 2.4) * 4
        pygame.draw.circle(s, scale_col(col, 0.75), (cx, cy + bob), 22)
        pygame.draw.circle(s, mix_col(col, WHITE, 0.55), (cx - 6, cy - 7 + bob), 12)
        pygame.draw.circle(s, WHITE, (cx, cy + bob), 22, 1)
        draw_text(s, sv["name"] or "PLAYER", 22, WHITE, cx, cy - 52)
        draw_text(s, TITLES[sv["title"]][0], 14, GOLD, cx, cy - 34)
        draw_text(s, "your core", 16, DIM, L.centerx - 90, L.bottom - 40)
        draw_text(s, "you, in a match", 16, DIM, cx, L.bottom - 40)
        R = pygame.Rect(620, 110, 600, 560)
        panel(s, R, PANEL, 255, LINE, 16, 2)
        draw_text(s, "YOUR COLOUR", 20, DIM, R.x + 30, R.y + 34, "l")
        for i, (name, c) in enumerate(PLAYER_COLORS):
            r = pygame.Rect(R.x + 30 + (i % 6) * 92, R.y + 60 + (i // 6) * 96, 80, 80)
            on = sv["color"] == i
            hov = r.collidepoint(self.mouse)
            pygame.draw.rect(s, scale_col(c, 0.35 if not (on or hov) else 0.6), r, border_radius=12)
            pygame.draw.rect(s, WHITE if on else c, r, 3 if on else 2, border_radius=12)
            pygame.draw.circle(s, c, r.center, 16)
            draw_text(s, name, 13, WHITE, r.centerx, r.bottom - 12)
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                sv["color"] = i
        draw_text(s, "CORE SHAPE", 20, DIM, R.x + 30, R.y + 280, "l")
        for i, name in enumerate(CORE_SKINS):
            r = pygame.Rect(R.x + 30 + i * 138, R.y + 304, 126, 150)
            on = sv["skin"] == i
            hov = r.collidepoint(self.mouse)
            pygame.draw.rect(s, mix_col(PANEL, col, 0.22 if on else 0.10 if hov else 0.03), r, border_radius=12)
            pygame.draw.rect(s, WHITE if on else LINE, r, 2, border_radius=12)
            self.scene.icon(s, core_model(i), col, r.centerx, r.y + 92, 1.5, self.time, 0.4)
            draw_text(s, name, 16, WHITE if on else GREY, r.centerx, r.bottom - 16)
            if hov and self.click:
                self.click = False
                self.audio.play("click")
                sv["skin"] = i
        draw_text(s, "Your colour is your orb, your core and your name on Wi-Fi.", 16, GREY, R.x + 30, R.bottom - 60, "l")
        draw_text(s, "To paint a tower, open TOWERS and pick a PAINT for it.", 16, GREY, R.x + 30, R.bottom - 36, "l")

    # ------------------------------------------------------------ settings
    def screen_settings(self, s):
        self.draw_plain(s)
        sv = self.save
        st = sv["settings"]
        if self.tab_header("settings", False):
            return
        if self.back_button():
            self.store()
            return
        P = pygame.Rect(60, 104, W - 120, 590)
        panel(s, P, PANEL, 255, LINE, 14, 2)
        x1, x2 = P.x + 40, P.x + 620
        draw_text(s, "SOUND", 18, GOLD, x1, P.y + 34, "l")
        draw_text(s, "Sound effects", 21, WHITE, x1, P.y + 76, "l")
        v = self.slider("s_sfx", pygame.Rect(x1 + 220, P.y + 68, 260, 16), st["sfx"])
        if v != st["sfx"]:
            st["sfx"] = v
            self.audio.vol = v
        draw_text(s, "Music", 21, WHITE, x1, P.y + 124, "l")
        v = self.slider("s_mus", pygame.Rect(x1 + 220, P.y + 116, 260, 16), st["music"])
        if v != st["music"]:
            st["music"] = v
            self.audio.set_music(v)
        draw_text(s, "CAMERA", 18, GOLD, x1, P.y + 180, "l")
        draw_text(s, "Turn speed", 21, WHITE, x1, P.y + 222, "l")
        st["sens"] = 0.3 + 1.7 * self.slider("s_sens", pygame.Rect(x1 + 220, P.y + 214, 260, 16), (st["sens"] - 0.3) / 1.7)
        rows1 = [("view3d", "3D view in a match", "Off = flat top-down view, players hidden.  (%s in a match)" % self.kname("view")),
                 ("shake", "Screen shake", ""),
                 ("names", "Name tags", "Names above players and people on the map.")]
        rows2 = [("ranges", "Range circles", "The circle that shows how far a tower reaches."),
                 ("boxes", "Boundary boxes", "The little square a tower takes up. Towers cannot overlap."),
                 ("numbers", "Damage numbers", ""),
                 ("ehp", "Enemy health numbers", "An enemy's HP is also the damage it does if it leaks."),
                 ("glow", "Glow effects", "Turn off if the game runs slowly."),
                 ("auto", "Auto-start waves", "Solo only: the next wave starts by itself."),
                 ("fps", "Show FPS", ""),
                 ("fullscreen", "Fullscreen", "F11 works any time.")]
        draw_text(s, "DISPLAY", 18, GOLD, x2, P.y + 34, "l")
        if self.button("st_keys", pygame.Rect(P.right - 290, P.y + 14, 250, 36), "CHANGE KEYS  >", PURPLE, 20):
            self.store()
            self.goto("controls")
            return
        for col_x, rows, y0 in ((x1, rows1, P.y + 270), (x2, rows2, P.y + 66)):
            for i, (key, lab, sub) in enumerate(rows):
                y = y0 + i * 62
                draw_text(s, lab, 21, WHITE, col_x, y + 8, "l")
                if sub:
                    draw_text(s, sub, 14, DIM, col_x, y + 30, "l")
                on = st[key]
                if self.button("st_" + key, pygame.Rect(col_x + 420, y - 6, 90, 36), "ON" if on else "OFF", GREEN if on else GREY, 20):
                    if key == "fullscreen":
                        self.toggle_fullscreen()
                    else:
                        st[key] = not on
                        if key == "glow":
                            GFX["glow"] = st[key]
        y = P.y + 270 + 3 * 62
        draw_text(s, "3D detail", 21, WHITE, x1, y + 8, "l")
        draw_text(s, "Lower it if a match runs slowly. LOW brings back the simple old models.", 14, DIM, x1, y + 30, "l")
        for i, name in enumerate(("LOW", "MEDIUM", "HIGH")):
            if self.button("st_det%d" % i, pygame.Rect(x1 + 250 + i * 90, y - 6, 84, 36), name, GOLD if st["detail"] == i else GREY, 17):
                st["detail"] = i
        if self.world is None:
            if self.confirm > 0:
                self.confirm -= self.dt
            if self.button("st_reset", pygame.Rect(x1, P.bottom - 62, 380, 42), "CLICK AGAIN TO ERASE EVERYTHING" if self.confirm > 0 else "RESET ALL PROGRESS", RED, 18):
                if self.confirm > 0:
                    keep = dict((k, sv[k]) for k in ("name", "upd_code", "upd_ip", "upd_last", "keys"))
                    self.save = json.loads(json.dumps(DEFAULT_SAVE))
                    self.save.update(keep)
                    self.fix_save()
                    self.store()
                    self.confirm = 0.0
                    self.pop("Progress erased.", RED, 2.5)
                else:
                    self.confirm = 3.0

    # ------------------------------------------------------------ controls: every key in a match can be changed
    def screen_controls(self, s):
        self.draw_plain(s)
        sv = self.save
        got = None
        if self.rebind is not None:
            # waiting for a key: ESC only cancels (it must not leave the page as well)
            if pygame.K_ESCAPE in self.pressed:
                self.pressed.discard(pygame.K_ESCAPE)
                self.rebind = None
                self.key_msg = ["Nothing changed.", GREY, 3.0]
            else:
                for k in sorted(self.pressed):
                    if k != pygame.K_F11:
                        got = k
                        break
        if self.tab_header("controls", False):
            return
        if self.back_button():
            self.store()
            return
        if got is not None and self.rebind is not None:
            act = self.rebind
            if not key_ok(got):
                self.key_msg = ["%s cannot be used.  Press another key." % key_name(got), RED, 3.5]
                self.audio.play("error")
            else:
                other = self.set_key(act, got)
                self.rebind = None
                self.audio.play("place")
                if other is not None:
                    self.key_msg = ["%s is now %s.   %s had that key, so it got %s instead." %
                                    (KEY_LABELS[act].upper(), key_name(got), KEY_LABELS[other].upper(), self.kname(other)), GOLD, 7.0]
                else:
                    self.key_msg = ["%s is now %s." % (KEY_LABELS[act].upper(), key_name(got)), GREEN, 4.0]
                self.store()
        P = pygame.Rect(40, 96, W - 80, 610)
        panel(s, P, PANEL, 255, LINE, 14, 2)
        draw_text(s, "Click a row, then press the key you want for it.   ESC cancels.", 17, GREY, P.x + 28, P.y + 26, "l")
        draw_text(s, "A key can only do one thing: take a key that is in use and the two swap.", 15, DIM, P.right - 28, P.y + 26, "r")
        cw = (P.w - 56 - 48) // 3
        ys = [P.y + 50, P.y + 50, P.y + 50]
        self.key_rects = {}                 # action -> its row on the screen
        for title, ci, rows in KEY_GROUPS:
            x = P.x + 28 + ci * (cw + 24)
            y = ys[ci]
            draw_text(s, title, 15, GOLD, x + 2, y + 12, "l")
            y += 26
            for act, lab, dk in rows:
                r = pygame.Rect(x, y, cw, 32)
                self.key_rects[act] = r
                on = self.rebind == act
                hov = r.collidepoint(self.mouse)
                mine = self.key_of(act) != dk
                pygame.draw.rect(s, mix_col(PANEL, GOLD if on else CYAN, 0.22 if on else 0.12 if hov else 0.03), r, border_radius=8)
                pygame.draw.rect(s, GOLD if on else CYAN if hov else LINE, r, 2 if on else 1, border_radius=8)
                draw_text(s, lab, 18, WHITE, r.x + 12, r.centery, "l")
                kb = pygame.Rect(r.right - 140, r.y + 3, 136, 26)
                pygame.draw.rect(s, (22, 28, 58), kb, border_radius=7)
                pygame.draw.rect(s, GOLD if on else MINT if mine else CYAN, kb, 1, border_radius=7)
                if on:
                    draw_text(s, "press a key...", 16, GOLD if (self.time * 2) % 2 < 1.3 else WHITE, kb.centerx, kb.centery)
                else:
                    draw_text(s, self.kname(act), 18, MINT if mine else WHITE, kb.centerx, kb.centery)
                if hov and self.click:
                    self.click = False
                    self.audio.play("click")
                    self.rebind = None if on else act
                    self.key_msg = ["", GREY, 0.0]
                y += 35
            ys[ci] = y + 8
        draw_text(s, "Always the same:   ESC  menu / cancel      F11  fullscreen      SHIFT + P  film camera      the mouse buttons", 15, DIM, P.x + 28, P.bottom - 82, "l")
        if self.button("key_reset", pygame.Rect(P.x + 28, P.bottom - 58, 280, 42), "RESET TO DEFAULTS", ORANGE, 20):
            sv["keys"] = clean_keys({})
            self.rebind = None
            self.key_msg = ["All keys are back to normal.", GREEN, 4.0]
            self.store()
        if self.rebind is not None and self.click:
            self.rebind = None              # clicked somewhere else: never mind
        km = self.key_msg
        if km[2] > 0:
            km[2] -= self.dt
            draw_text(s, km[0], self.fit_size(km[0], 18, P.w - 370, 13), km[1], P.x + 330, P.bottom - 37, "l")
        elif self.rebind is not None:
            draw_text(s, "Press the key for %s now." % KEY_LABELS[self.rebind].upper(), 18, GOLD, P.x + 330, P.bottom - 37, "l")
        elif any(self.key_of(a) != KEY_DEFAULTS[a] for a in KEY_ORDER):
            draw_text(s, "Green keys are ones you changed.", 15, DIM, P.x + 330, P.bottom - 37, "l")

    # ------------------------------------------------------------ help
    def screen_help(self, s):
        self.draw_plain(s)
        if self.tab_header("help", False):
            return
        if self.back_button():
            return
        tabs = ["BASICS", "TOWERS", "ENEMIES", "HOTKEYS", "WI-FI"]
        for i, name in enumerate(tabs):
            if self.button("h_%d" % i, pygame.Rect(W // 2 - 500 + i * 202, 96, 190, 42), name, GOLD if self.help_tab == i else GREY, 22):
                self.help_tab = i
        P = pygame.Rect(40, 154, W - 80, 540)
        panel(s, P, PANEL, 255, LINE, 14, 2)
        tab = self.help_tab
        kn = self.kname
        if tab == 0:
            lines = [
                (GOLD, "THE GOAL"),
                (GREY, "Enemies walk the glowing road to your core. Build towers to stop them. If the core's health hits 0, you lose."),
                (GREY, "Survive every wave to TRIUMPH. Normal has 20 waves, Hard and Insane have 30. A boss comes every 10 waves, and the FINAL"),
                (GREY, "boss ends the game if it reaches the core. Any other leak takes off the HEALTH THE ENEMY HAS LEFT: the number over its head."),
                (GREY, "CASH comes from HITTING enemies, not from kills: every hit pays $1 to $5, more the bigger the bite out of its health. Waves pay too."),
                (GOLD, "YOU AND THE CAMERA"),
                (GREY, "You are the orb with your name on it. %s moves you, %s sprints, %s jumps. Hold the RIGHT mouse button and drag to turn the camera." %
                 (self.kmove(), kn("sprint"), kn("jump"))),
                (GREY, "Scroll to zoom. %s is the flat 2D view (players are hidden there). SHIFT + P is cinematic mode: a free camera with no HUD." % kn("view")),
                (GOLD, "BUILDING"),
                (GREY, "Pick a tower at the bottom left, then click anywhere it fits: there is no grid. Not enough cash? It is PLANNED and builds itself later."),
                (GREY, "GROUND towers go on land level with the road, CLIFF towers on land HIGHER than the road beside it (higher = more range)."),
                (GREY, "PATH towers stand ON the road: they block enemies, have health, explode when they fall and come back after the wave."),
                (GREY, "Every map has three towers that are AT HOME there and get a bonus. Not sure how to beat a level? Watch its TUTORIAL."),
                (GOLD, "PERKS, ABILITIES AND CARDS"),
                (GREY, "Normal perks stack and are always on. %s and %s drop your ability perks anywhere on the field. %s fires a tower's own ability." %
                 (kn("abil1"), kn("abil2"), kn("tabil"))),
                (GREY, "Every 5 waves you pick 1 of 3 cards. They last for the rest of the match."),
                (GOLD, "PEOPLE AND SECRETS"),
                (GREY, "Every map has people with a ! above them. Walk up and press %s (or click them). Some of them know how to find secret events." % kn("talk")),
            ]
            y = P.y + 26
            for i, (col, ln) in enumerate(lines):
                if col == GOLD and i:
                    y += 8
                draw_text(s, ln, 21 if col == GOLD else 17, col, P.x + 30, y, "l")
                y += 27 if col == GOLD else 23
        elif tab == 1:
            for i, kind in enumerate(TOWER_ORDER):
                T = TOWERS[kind]
                x = P.x + 24 + (i % 2) * 604
                y = P.y + 32 + (i // 2) * 40
                self.tower_icon(kind, x + 14, y, 0.7, 0, 0.0)
                draw_text(s, T["name"], 16, T["col"], x + 40, y - 8, "l")
                draw_text(s, "%s - %s - %s%s" % (T["tier"], T["atk"], PLACE_SHORT[T["place"]], " - AOE" if T.get("aoe") else ""), 12, GOLD, x + 170, y - 8, "l")
                ln = wrap(self.ktext(T["desc"]), 13, 540)[0]
                draw_text(s, ln, 13, GREY, x + 40, y + 9, "l")
        elif tab == 2:
            for i, kind in enumerate(ENEMY_ORDER):
                E = ENEMIES[kind]
                x = P.x + 30 + (i % 2) * 600
                y = P.y + 36 + (i // 2) * 64
                self.enemy_icon(kind, x + 22, y + 4, min(1.2, 14.0 / E["r"]))
                draw_text(s, E["name"], 20, E["col"], x + 58, y - 10, "l")
                if E.get("boss"):
                    draw_text(s, "BOSS", 14, RED, x + 250, y - 10, "l")
                elif kind in WAVE_UNITS:
                    draw_text(s, "from wave %d" % WAVE_UNITS[kind][0], 14, DIM, x + 250, y - 10, "l")
                draw_text(s, E["info"], 16, GREY, x + 58, y + 10, "l")
        elif tab == 3:
            keys = [(self.kmove(True), "move your orb (3D view)     %s: sprint (hold)     %s: jump" % (kn("sprint"), kn("jump"))),
                    ("RIGHT MOUSE + DRAG", "turn the camera     SCROLL or %s / %s: zoom" % (kn("zoom_out"), kn("zoom_in"))),
                    ("%s - %s" % (kn("slot1"), kn("slot6")), "pick a tower from your loadout"), ("LEFT CLICK", "place / select     RIGHT CLICK or ESC: cancel"),
                    (kn("upgrade"), "UPGRADE the tower you are pointing at (no need to select it)"), (kn("sell"), "SELL the tower you are pointing at"),
                    (kn("tabil"), "tower ABILITY (Commander: Call to Arms)"),
                    ("%s  and  %s" % (kn("abil1"), kn("abil2")), "your ABILITY PERKS (then click the field)"),
                    (kn("mode"), "change a tower's target: first, last, strong, close"),
                    (kn("start"), "start the next wave (when you play alone)     %s: SKIP the wave (not on boss waves)" % kn("skip")),
                    (kn("speed"), "game speed 1x, 2x, 3x"), (kn("talk"), "talk to the nearest person     %s: chat" % kn("chat")),
                    (kn("view"), "switch between 3D and 2D"),
                    ("SHIFT + P", "cinematic mode (free camera)     %s or ESC: menu     F11: fullscreen" % kn("pause"))]
            draw_text(s, "Want other keys?  OPTIONS > CONTROLS changes every one of them.", 15, MINT, P.centerx, P.bottom - 14)
            for i, (k, d) in enumerate(keys):
                y = P.y + 30 + i * 35
                r = pygame.Rect(P.x + 50, y - 14, 250, 28)
                pygame.draw.rect(s, (22, 28, 58), r, border_radius=8)
                pygame.draw.rect(s, CYAN, r, 1, border_radius=8)
                draw_text(s, k, 18, WHITE, r.centerx, r.centery)
                draw_text(s, d, 19, GREY, P.x + 330, y, "l")
        else:
            lines = [
                (GOLD, "PLAYING WITH FRIENDS ON YOUR WI-FI"),
                (GREY, "Everyone needs this same version of the game, and has to be on the same Wi-Fi (or the same router)."),
                (GREY, "1.  One person opens WI-FI PLAY and clicks HOST A GAME."),
                (GREY, "2.  Everyone else opens WI-FI PLAY. The game shows up in the list by itself. Click JOIN."),
                (GREY, "3.  If it does not show up, type the host's address (shown on the host's screen) and click JOIN."),
                (GREY, "4.  The host picks the map and the difficulty and clicks START."),
                (GOLD, "IN A MATCH TOGETHER"),
                (GREY, "Up to 4 players. Everyone has their own cash, loadout, perks and cards. The core is shared."),
                (GREY, "You can only upgrade or sell your OWN towers. Point at a friend's tower to see whose it is, its level and its perk."),
                (GREY, "Enemies are tougher with more players. Press %s to chat. Point at a friend's orb to see who they are and what they brought." % kn("chat")),
                (GREY, "Nobody has to ready up: the next wave starts by itself, %g seconds after the last one ends (%g seconds before the first one)." %
                 (float(globals().get("MP_WAVE_DELAY", 2.0)), float(globals().get("MP_FIRST_DELAY", 6.0)))),
                (GREY, "Rude words in chat turn into red signs like %s. A grown-up can add words to the list: %s, next to the game." % (grawlix("oops", 5), WORDS_NAME)),
                (GOLD, "IF JOINING DOES NOT WORK"),
                (GREY, "The first time you host, Windows may ask if the game is allowed on the network. Say yes (private networks)."),
                (GREY, "Some school or guest Wi-Fi networks block computers from talking to each other. A phone hotspot usually works."),
            ]
            y = P.y + 30
            for i, (col, ln) in enumerate(lines):
                if col == GOLD and i:
                    y += 12
                draw_text(s, ln, 22 if col == GOLD else 18, col, P.x + 30, y, "l")
                y += 30 if col == GOLD else 27

    # ------------------------------------------------------------ changelog
    def screen_updates(self, s):
        """keep two PCs on the same version over the Wi-Fi"""
        self.draw_plain(s)
        sv = self.save
        if self.tab_header("updates", False):
            return
        if self.back_button():
            return
        P = pygame.Rect(140, 104, W - 280, 586)
        panel(s, P, PANEL, 255, LINE, 14, 2)
        x = P.x + 40
        draw_text(s, "UPDATES FROM YOUR OTHER PC", 24, GOLD, x, P.y + 36, "l")
        draw_text(s, "This PC has version %s." % VERSION, 18, WHITE, P.right - 40, P.y + 36, "r")
        for i, ln in enumerate(("Give both PCs the same UPDATE CODE once. After that, whenever one has a newer version, the other gets it by itself",
                                "the next time both have the game open on the same network: checked, installed, restarted. Saves stay put.")):
            draw_text(s, ln, 16, GREY, x, P.y + 68 + i * 22, "l")
        code = sv["upd_code"]
        u = self.upd
        if not code:
            A = pygame.Rect(x, P.y + 168, 440, 220)
            B2 = pygame.Rect(A.right + 40, A.y, 440, 220)
            for r, head, sub in ((A, "ON THE FIRST PC", "Make a code. It is shown here so you can type it on the other one."),
                                 (B2, "ON THE OTHER PC", "Type the code the first PC shows.")):
                panel(s, r, (14, 18, 40), 255, LINE, 12, 2)
                draw_text(s, head, 20, WHITE, r.centerx, r.y + 30)
                draw_text(s, sub, 14, GREY, r.centerx, r.y + 58)
            if self.button("up_make", pygame.Rect(A.centerx - 130, A.y + 110, 260, 60), "MAKE A CODE", GREEN, 26):
                sv["upd_code"] = new_update_code()
                self.store()
                self.start_updater()
            self.upd_buf = clean_code(self.textbox("upd_code", pygame.Rect(B2.centerx - 150, B2.y + 92, 300, 54), self.upd_buf, CODE_LEN, "8 letters", 30,
                                                   CODE_ABC + CODE_ABC.lower()))
            ok = len(self.upd_buf) == CODE_LEN
            if self.button("up_use", pygame.Rect(B2.centerx - 110, B2.y + 158, 220, 46), "USE THIS CODE", GREEN, 20, ok) or (ok and pygame.K_RETURN in self.pressed):
                sv["upd_code"] = self.upd_buf
                self.upd_buf = ""
                self.focus = None
                self.store()
                self.start_updater()
            y = P.y + 420
            tips = ("Anyone who knows the code could hand this PC a version, so keep it to your own PCs.",
                    "Updates are OFF until you set a code.",
                    "Windows will ask if the game may use the network. Say yes. The question can hide BEHIND the game: press F11 to look.")
        else:
            C = pygame.Rect(x, P.y + 116, P.w - 80, 112)
            panel(s, C, (14, 18, 40), 255, GREEN, 12, 2)
            draw_text(s, "YOUR UPDATE CODE", 14, DIM, C.centerx, C.y + 18)
            draw_glow_text(s, code[:4] + "  " + code[4:], 54, GREEN, C.centerx, C.y + 56)
            draw_text(s, "Type it once on your other PC:  OPTIONS  >  UPDATES  >  ON THE OTHER PC", 15, GREY, C.centerx, C.y + 94)
            st = u.state if u is not None else "off"
            now = time.time()
            seen = u is not None and u.peer is not None and now - u.peer[1] < 45.0
            bad = u is not None and now - u.badcode < 45.0
            msg, col = {"idle": ("Ready.", GREY),
                        "looking": ("Looking for your other PC" + "." * (1 + int(self.time * 3) % 3), CYAN),
                        "none": ("", GREY),
                        "downloading": ("Getting version %s..." % (u.note if u else ""), CYAN),
                        "ready": ("Version %s is here: it installs when you go back to the main menu." % (u.note if u else ""), GREEN),
                        "error": ("Could not update: %s." % (u.note if u else ""), RED),
                        "off": ("Updates are switched off for this run.", GREY)}.get(st, ("", GREY))
            if st == "none":
                if seen:
                    cmp = (ver_tuple(u.peer[0]) > ver_tuple(VERSION)) - (ver_tuple(u.peer[0]) < ver_tuple(VERSION))
                    msg, col = (("Both PCs have version %s. Nothing to do." % VERSION, GREY) if cmp == 0 else
                                ("This PC has the newer version. Sending it to the other one (%s)." % u.peer[0], CYAN) if cmp < 0 else
                                ("The other PC has version %s. Fetching it." % u.peer[0], CYAN))
                elif bad:
                    msg, col = "A PC answered, but its update code is DIFFERENT. Type the same code on both.", RED
                else:
                    msg, col = "No answer.  Asked %d times from %s." % (u.asked, ", ".join(u.ips) or "no network at all"), ORANGE
            ly = C.bottom + 28
            lx = C.centerx - 170
            pygame.draw.circle(s, GREEN if seen else RED if bad else (90, 96, 130), (lx, ly), 8)
            if seen:
                pygame.draw.circle(s, WHITE, (lx, ly), 8, 1)
                draw_text(s, "OTHER PC: CONNECTED   (version %s, at %s)" % (u.peer[0], u.peer[2]), 18, GREEN, lx + 18, ly, "l")
            else:
                draw_text(s, "OTHER PC: NOT SEEN YET", 18, GREY, lx + 18, ly, "l")
            draw_text(s, msg, 16, col, C.centerx, ly + 26)
            if u is not None and not u.can_share:
                draw_text(s, "This PC cannot be reached right now (is another copy of the game open?). It can still ask the other one.", 14, ORANGE, C.centerx, ly + 48)
            elif u is not None and code_source() is None:
                draw_text(s, "This .exe has no game file to hand out. Put neon_bastion.py next to it and it can.", 14, ORANGE, C.centerx, ly + 48)
            # addresses: the way around a network where the two PCs cannot find each other by themselves
            ay = ly + 84
            ips = my_ips() if int(self.time * 0.5) != getattr(self, "_ipt", None) else self._ips
            self._ipt, self._ips = int(self.time * 0.5), ips
            draw_text(s, "THIS PC'S ADDRESS", 13, DIM, x, ay - 12, "l")
            draw_text(s, "   ".join(ips[:3]) or "not on a network", 22, WHITE, x, ay + 12, "l")
            bx = P.centerx + 40
            draw_text(s, "OTHER PC'S ADDRESS", 13, DIM, bx, ay - 12, "l")
            draw_text(s, "only if they do not find each other", 13, DIM, bx + 240, ay + 12, "l")
            before = self.upd_ip
            self.upd_ip = self.textbox("upd_ip", pygame.Rect(bx, ay - 2, 226, 36), self.upd_ip, 15, "like 192.168.1.23", 21, "0123456789.")
            if self.upd_ip != before and (clean_ip(self.upd_ip) or not self.upd_ip):
                sv["upd_ip"] = clean_ip(self.upd_ip)
                self.store()
                if u is not None:
                    u.extra = [ip for ip in (sv["upd_ip"], sv["upd_last"]) if ip]
                    u.last = 0.0
            by = ay + 52
            if self.button("up_check", pygame.Rect(C.centerx - 250, by, 240, 46), "CHECK NOW", CYAN, 22, u is not None and not u.busy and u.ready is None):
                u.check()
            if self.confirm > 0:
                self.confirm -= self.dt
            if self.button("up_off", pygame.Rect(C.centerx + 10, by, 240, 46), "CLICK AGAIN TO FORGET" if self.confirm > 0 else "FORGET THE CODE", RED, 18):
                if self.confirm > 0:
                    sv["upd_code"] = ""
                    self.confirm = 0.0
                    self.store()
                    self.start_updater()
                else:
                    self.confirm = 3.0
            y = by + 70
            tips = ("New version?  Put the new neon_bastion.py on ONE PC, in place of the old one (next to the .exe if you use the .exe).",
                    "NOT SEEN?  1. Same code on both.  2. Both on the same Wi-Fi or router, not a guest network.",
                    "3. Windows Firewall: Windows Security > Firewall > Allow an app > Python (or NeonBastion): tick Private AND Public.",
                    "4. Still nothing: type the other PC's address (shown on ITS Updates page) into the box above, on both PCs.")
        for i, ln in enumerate(tips):
            draw_text(s, ln, 15, GREY, x, y + i * 23, "l")

    def screen_changelog(self, s):
        self.draw_plain(s)
        if self.tab_header("changelog", False):
            return
        if self.back_button():
            return
        P = pygame.Rect(100, 100, W - 200, 600)
        panel(s, P, PANEL, 255, LINE, 14, 2)
        y = P.y + 30
        for ver, lines in CHANGELOG:
            draw_text(s, ver, 24, GOLD, P.x + 30, y, "l")
            y += 28
            for ln in lines:
                pygame.draw.circle(s, CYAN, (P.x + 40, y), 3)
                draw_text(s, ln, 16, GREY, P.x + 54, y, "l")
                y += 21
            y += 10

    # ------------------------------------------------------------ Wi-Fi: find or host a game
    def screen_mp(self, s):
        self.draw_plain(s)
        sv = self.save
        self.header("WI-FI PLAY", False, MINT)
        if self.back_button("lobby" if self.back_to != "menu" else "menu"):
            self.leave_net()
            return
        if self.finder is None:
            self.finder = Finder()
        games = self.finder.poll()
        L = pygame.Rect(60, 110, 560, 570)
        panel(s, L, PANEL, 255, MINT, 16, 2)
        draw_text(s, "HOST", 28, MINT, L.x + 30, L.y + 40, "l")
        for i, ln in enumerate(("Start a game on this computer.", "Friends on the same Wi-Fi will see it", "in their list and can join with one click.")):
            draw_text(s, ln, 18, GREY, L.x + 30, L.y + 80 + i * 24, "l")
        if self.button("mp_host", pygame.Rect(L.x + 30, L.y + 170, L.w - 60, 80), "HOST A GAME", MINT, 36):
            self.host_room()
            return
        draw_text(s, "Your name:  %s" % (sv["name"] or "PLAYER"), 18, WHITE, L.x + 30, L.y + 290, "l")
        if not getattr(self, "myip", None):
            self.myip = my_ip()
        draw_text(s, "Your address:  %s" % self.myip, 18, GREY, L.x + 30, L.y + 318, "l")
        draw_text(s, "Up to 4 players.  Everyone needs version %s." % VERSION, 16, DIM, L.x + 30, L.y + 356, "l")
        if self.mp_err:
            for i, ln in enumerate(wrap(self.mp_err, 18, L.w - 60)[:3]):
                draw_text(s, ln, 18, RED, L.x + 30, L.y + 410 + i * 24, "l")
        R = pygame.Rect(660, 110, 560, 570)
        panel(s, R, PANEL, 255, CYAN, 16, 2)
        draw_text(s, "JOIN", 28, CYAN, R.x + 30, R.y + 40, "l")
        draw_text(s, "Games on your Wi-Fi:", 18, GREY, R.x + 30, R.y + 80, "l")
        if not games:
            dots = "." * (1 + int(self.time * 2) % 3)
            draw_text(s, "Looking" + dots, 20, DIM, R.x + 30, R.y + 130, "l")
            draw_text(s, "Nothing yet. Ask your friend to click HOST A GAME.", 16, DIM, R.x + 30, R.y + 160, "l")
        for i, g in enumerate(games[:5]):
            r = pygame.Rect(R.x + 24, R.y + 104 + i * 68, R.w - 48, 60)
            pygame.draw.rect(s, (16, 20, 44), r, border_radius=10)
            pygame.draw.rect(s, LINE, r, 1, border_radius=10)
            draw_text(s, "%s's game" % (safe_name(g.get("host", "?")) or "?"), 21, WHITE, r.x + 14, r.y + 20, "l")
            draw_text(s, "%s   -   %s player%s   -   %s" % (clean_name(str(g.get("map", "")), 20), g.get("n", 1), "" if g.get("n", 1) == 1 else "s",
                                                           "in a match" if g.get("busy") else "in the room"), 14, GREY, r.x + 14, r.y + 42, "l")
            if g.get("ver") != VERSION:
                self.button("mp_j%d" % i, pygame.Rect(r.right - 150, r.y + 9, 140, 42), "v" + str(g.get("ver")), RED, 16, False)
            elif self.button("mp_j%d" % i, pygame.Rect(r.right - 150, r.y + 9, 140, 42), "JOIN", GREEN, 24, not g.get("busy")):
                self.join_room(g["ip"], int(g.get("port", NET_PORT)))
                return
        draw_text(s, "Or type the host's address:", 18, GREY, R.x + 30, R.bottom - 110, "l")
        self.ip_buf = self.textbox("ip", pygame.Rect(R.x + 30, R.bottom - 86, 330, 52), self.ip_buf, 21, "192.168.1.23", 26, "0123456789.:")
        if self.button("mp_jip", pygame.Rect(R.x + 374, R.bottom - 86, 156, 52), "JOIN", GREEN, 26, len(self.ip_buf) >= 7) or \
                (self.focus == "ip" and pygame.K_RETURN in self.pressed and len(self.ip_buf) >= 7):
            ip, _, port = self.ip_buf.partition(":")
            self.join_room(ip, int(port) if port.isdigit() else NET_PORT)

    def host_room(self):
        self.leave_net()
        Hh = Host(safe_name(self.save["name"]) or "PLAYER")
        if not Hh.ok:
            self.mp_err = "Could not start hosting (%s). Is another copy of the game already hosting?" % Hh.err
            Hh.close()
            return
        self.net = ("host", Hh)
        self.mp_err = ""
        self.room = dict(map=MAIN_MAPS[clamp(self.sel_map, 0, len(MAIN_MAPS) - 1)]["id"], diff=self.save["diff"], players=[], ip=Hh.ip, port=Hh.port)
        self.room_specs = {0: self.my_spec()}
        self.chat = []
        self.chat_add("", GREY, "Room open. Friends on your Wi-Fi can join now.")
        self.goto("room")

    def join_room(self, ip, port):
        self.leave_net()
        c, err = net_connect(ip, port)
        if c is None:
            self.mp_err = "Could not reach %s (%s). Same Wi-Fi? Is the host still in the room?" % (ip, err)
            self.audio.play("error")
            return
        c.send(dict(t="hello", spec=self.my_spec(), ver=VERSION))
        self.net = ("guest", c)
        self.mp_err = ""
        self.room = None
        self.me = 0
        self.chat = []
        self.goto("room")

    def room_spec(self):
        """tell the room about a changed loadout"""
        if not self.net:
            return
        if self.net[0] == "host":
            self.room_specs[0] = self.my_spec()
            self.room_broadcast()
        else:
            self.net[1].send(dict(t="spec", spec=self.my_spec()))

    def room_broadcast(self):
        Hh = self.net[1]
        ids = [0] + sorted(Hh.conns)
        pl = []
        for pid in ids:
            sp = self.room_specs.get(pid) or {}
            pl.append(dict(id=pid, name=safe_name(sp.get("name", "?")) or "PLAYER", title=str(sp.get("title", ""))[:24], level=int(sp.get("level", 1)),
                           col=list(sp.get("col", WHITE))[:3], loadout=[k for k in sp.get("loadout", []) if k in TOWERS][:6]))
        self.room["players"] = pl
        for pid, c in Hh.conns.items():
            c.send(dict(t="room", map=self.room["map"], diff=self.room["diff"], players=pl, you=pid))

    def net_idle(self):
        """keeps the Wi-Fi alive while you are on another screen"""
        if not self.net:
            return
        w = self.world
        if self.net[0] == "host":
            Hh = self.net[1]
            if w is not None:
                self.host_pump(w)
                w.update(min(self.dt, 1 / 30.0))
                self.mp_auto(w)
                del w.ev[:]
                return
            busy = False
            Hh.beacon(self.dt, dict(map=MAP_BY_ID[self.room["map"]]["name"], n=1 + len(Hh.conns), busy=busy))
            Hh.accept()
            changed = False
            for c in list(Hh.new):
                for m in c.pump():
                    if m.get("t") == "hello":
                        Hh.new.remove(c)
                        if m.get("ver") != VERSION:
                            c.send(dict(t="no", why="The host has version %s, you have %s." % (VERSION, m.get("ver"))))
                            c.pump()
                            c.close()
                        elif len(Hh.conns) >= 3:
                            c.send(dict(t="no", why="That room is full (4 players)."))
                            c.pump()
                            c.close()
                        else:
                            pid = 1
                            while pid in Hh.conns:
                                pid += 1
                            Hh.conns[pid] = c
                            self.room_specs[pid] = self.safe_spec(m.get("spec"))
                            self.chat_add("", GREY, "%s joined" % (clean_name(self.room_specs[pid].get("name", "?")) or "A player"))
                            self.audio.play("chat")
                            changed = True
                        break
                if c.dead and c in Hh.new:
                    Hh.new.remove(c)
            for pid, c in list(Hh.conns.items()):
                for m in c.pump():
                    t = m.get("t")
                    if t == "spec" and isinstance(m.get("spec"), dict):
                        self.room_specs[pid] = self.safe_spec(m["spec"])
                        changed = True
                    elif t == "chat":
                        text = clean_chat(m.get("text", ""), CHAT_MAX + 16)
                        sp = self.room_specs.get(pid, {})
                        if text:
                            nm, cl, ttl = clean_name(sp.get("name", "?")) or "?", tuple(sp.get("col", WHITE))[:3], str(sp.get("title", ""))[:24]
                            bad = self.chat_add(nm, cl, text, ttl)              # filtered again here, whatever the sender did
                            text = self.chat[-1][2]
                            self.audio.play("censor2" if bad else "chat")
                            for p2, c2 in Hh.conns.items():
                                if p2 != pid:
                                    c2.send(dict(t="chat", name=nm, col=list(cl), title=ttl, text=text))
                if c.dead:
                    del Hh.conns[pid]
                    self.chat_add("", GREY, "%s left" % (clean_name(self.room_specs.get(pid, {}).get("name", "?")) or "A player"))
                    self.room_specs.pop(pid, None)
                    changed = True
            if changed:
                self.room_broadcast()
        else:
            c = self.net[1]
            if w is not None:
                self.guest_pump(w, w.players[self.me])
                w.update(self.dt)
                del w.ev[:]
                return
            for m in c.pump():
                t = m.get("t")
                try:
                    if t == "room":
                        self.room = m
                        self.me = int(m.get("you", 0))
                    elif t == "chat":
                        self.got_chat(m)
                    elif t == "no":
                        self.mp_err = str(m.get("why", "The host said no."))[:120]
                        c.close()
                    elif t == "start":
                        self.start_guest(m["map"], m["diff"], m["specs"], int(m["me"]))
                        return
                    elif t == "bye":
                        self.mp_err = "The host closed the room."
                        c.close()
                except Exception:
                    pass
            if c.dead:
                if not self.mp_err:
                    self.mp_err = "Lost the connection to the host."
                self.leave_net()
                self.back_to = "lobby"
                self.goto("mp")

    def room_start(self):
        """host: everybody into the match"""
        Hh = self.net[1]
        ids = [0] + sorted(Hh.conns)
        specs = [self.room_specs.get(pid) or {} for pid in ids]
        specs[0] = self.my_spec()
        # players are numbered 0, 1, 2... inside a match
        conns = {}
        for new, pid in enumerate(ids):
            if pid:
                conns[new] = Hh.conns[pid]
        nspec = {0: specs[0]}
        for new, pid in enumerate(ids):
            if pid:
                nspec[new] = self.room_specs.get(pid) or {}
        Hh.conns = conns
        self.room_specs = nspec
        seed = random.randrange(1 << 30)
        self.start_game(self.room["map"], self.room["diff"], specs, seed, 0)
        w = self.world
        real = [P.spec() for P in w.players]
        for pid, c in Hh.conns.items():
            c.send(dict(t="start", map=self.room["map"], diff=self.room["diff"], specs=real, me=pid))
        Hh.beacon_t = 0.0

    def screen_room(self, s):
        self.draw_plain(s)
        host = bool(self.net) and self.net[0] == "host"
        self.header("THE ROOM", False, MINT)
        if self.back_button("mp"):
            self.leave_net()
            self.back_to = "lobby"
            return
        if not self.net:
            self.goto("mp")
            return
        room = self.room
        if room is None:
            draw_text(s, "Knocking on the host's door" + "." * (1 + int(self.time * 2) % 3), 26, GREY, W // 2, 320)
            return
        if host and not room.get("players"):
            self.room_broadcast()
        m = MAP_BY_ID.get(room.get("map"), MAIN_MAPS[0])
        diff = room.get("diff", "normal")
        if diff not in DIFFS:
            diff = "normal"
        D = DIFFS[diff if not m.get("event") else "event"]
        th = THEMES[m["theme"]]
        # ---- players
        L = pygame.Rect(40, 100, 600, 420)
        panel(s, L, PANEL, 255, MINT, 16, 2)
        pl = room.get("players", [])
        draw_text(s, "PLAYERS   %d / 4" % len(pl), 18, DIM, L.x + 24, L.y + 26, "l")
        if host:
            draw_text(s, "your address:  %s" % room.get("ip", ""), 15, GREY, L.right - 24, L.y + 26, "r")
        for i in range(4):
            r = pygame.Rect(L.x + 20, L.y + 50 + i * 90, L.w - 40, 82)
            if i >= len(pl):
                pygame.draw.rect(s, (12, 15, 32), r, border_radius=12)
                pygame.draw.rect(s, (24, 30, 56), r, 1, border_radius=12)
                draw_text(s, "waiting for a friend" + "." * (1 + int(self.time * 2 + i) % 3), 17, DIM, r.centerx, r.centery)
                continue
            p = pl[i]
            col = tuple(p.get("col", WHITE))[:3]
            mine = p.get("id") == (0 if host else self.me)
            pygame.draw.rect(s, mix_col(PANEL, col, 0.14), r, border_radius=12)
            pygame.draw.rect(s, col if mine else LINE, r, 2, border_radius=12)
            cx, cy = r.x + 40, r.centery + math.sin(self.time * 2.4 + i) * 3
            glow(s, cx, cy, 40, col, 0.6)
            pygame.draw.circle(s, scale_col(col, 0.75), (cx, cy), 16)
            pygame.draw.circle(s, mix_col(col, WHITE, 0.55), (cx - 4, cy - 5), 9)
            draw_text(s, p.get("name", "?") + ("   (host)" if p.get("id") == 0 else ""), 22, WHITE, r.x + 74, r.y + 22, "l")
            draw_text(s, "%s   -   level %d" % (p.get("title", ""), p.get("level", 1)), 14, GOLD, r.x + 74, r.y + 44, "l")
            for j, kind in enumerate(p.get("loadout", [])[:6]):
                if kind in TOWERS:
                    m3 = tower_model(kind, 0)
                    self.scene.icon(s, m3, TOWERS[kind]["col"], r.x + 330 + j * 40, r.y + 44 + m3.top * 0.16, 0.72, self.time, 0.0)
            if mine:
                draw_text(s, "YOU", 13, GREEN, r.right - 12, r.y + 14, "r")
        # ---- the match
        R = pygame.Rect(680, 100, 560, 420)
        panel(s, R, PANEL, 255, th["accent"], 16, 2)
        self.draw_minimap(s, m, pygame.Rect(R.x + 20, R.y + 20, 250, 154), th["accent"])
        draw_text(s, m["name"], 28, th["accent"], R.x + 290, R.y + 40, "l")
        for i, ln in enumerate(wrap(m["desc"], 15, 250)[:3]):
            draw_text(s, ln, 15, GREY, R.x + 290, R.y + 70 + i * 18, "l")
        draw_text(s, "%s   -   %d waves" % (D["name"], D["waves"]), 20, D["col"], R.x + 290, R.y + 140, "l")
        n = max(1, len(pl))
        draw_text(s, "Enemies have +%d%% health with %d players. Final boss: %dk." % (round(MP_HP * (n - 1) * 100), n, D["boss"] * (1 + MP_HP * (n - 1)) // 1000), 15, GREY, R.x + 20, R.y + 196, "l")
        if host:
            lv = self.level()
            ok_maps = [mm for mm in MAIN_MAPS if mm["need"] <= lv]
            draw_text(s, "MAP", 15, DIM, R.x + 20, R.y + 232, "l")
            step = 0
            if self.button("rm_prev", pygame.Rect(R.x + 20, R.y + 246, 60, 44), "<", CYAN, 28):
                step = -1
            if self.button("rm_next", pygame.Rect(R.x + 90, R.y + 246, 60, 44), ">", CYAN, 28):
                step = 1
            if step:
                ids = [mm["id"] for mm in ok_maps]
                i = ids.index(room["map"]) if room["map"] in ids else 0
                room["map"] = ids[(i + step) % len(ids)]
                self.room_broadcast()
            draw_text(s, "DIFFICULTY", 15, DIM, R.x + 180, R.y + 232, "l")
            for j, d in enumerate(DIFF_ORDER):
                if self.button("rm_d" + d, pygame.Rect(R.x + 180 + j * 122, R.y + 246, 114, 44), DIFFS[d]["name"], DIFFS[d]["col"] if room["diff"] == d else GREY, 20):
                    room["diff"] = d
                    self.room_broadcast()
            if self.button("rm_start", pygame.Rect(R.x + 20, R.bottom - 100, R.w - 40, 80), "START", GREEN, 44, True, "%d player%s" % (n, "" if n == 1 else "s")):
                self.room_start()
                return
        else:
            draw_text(s, "The host picks the map and starts the match.", 18, GREY, R.x + 20, R.y + 250, "l")
            draw_text(s, "Waiting for the host" + "." * (1 + int(self.time * 2) % 3), 26, WHITE, R.centerx, R.bottom - 60)
        # ---- your loadout + chat
        B = pygame.Rect(40, 532, 600, 160)
        panel(s, B, PANEL, 255, LINE, 14, 2)
        draw_text(s, "YOU BRING", 15, DIM, B.x + 20, B.y + 22, "l")
        for j, kind in enumerate(self.save["loadout"]):
            self.tower_icon(kind, B.x + 46 + j * 62, B.y + 66, 1.0, 0, 0.0)
        draw_text(s, "  ".join(PERKS[k]["name"] for k in self.save["eq_perks"]) + "    " + "  ".join(ABILS[k]["name"] for k in self.save["eq_abils"]), 13, GREY, B.x + 20, B.y + 104, "l")
        for i, (key, lab) in enumerate((("towers", "TOWERS"), ("perks", "PERKS"), ("customize", "COLOUR"))):
            if self.button("rm_" + key, pygame.Rect(B.x + 20 + i * 190, B.bottom - 44, 180, 34), lab, CYAN, 18):
                self.back_to = "room"
                self.goto(key)
        C = pygame.Rect(680, 532, 560, 160)
        panel(s, C, PANEL, 255, LINE, 14, 2)
        y = C.bottom - 58
        prev = s.get_clip()
        s.set_clip(C.inflate(-8, -8))
        for e in reversed(self.chat[-5:]):
            name, col, text = e[0], e[1], e[2]
            if name:
                # the same look as chat in a match: the speaker's orb, their name, and blocked words in red
                self.draw_orb(s, C.x + 24, y, 6, col)
                nr = draw_text(s, name, 16, col, C.x + 38, y, "l")
                draw_rich(s, text, 16, WHITE, nr.right + 8, y)
            else:
                pygame.draw.polygon(s, col, poly(C.x + 24, y, 4, 4, 0))
                draw_text(s, text, 15, mix_col(col, WHITE, 0.25), C.x + 38, y, "l")
            y -= 21
        s.set_clip(prev)
        self.focus = "roomchat"
        if self.typing is None:
            self.typing = ""
        self.typing = self.textbox("roomchat", pygame.Rect(C.x + 12, C.bottom - 44, C.w - 24, 34), self.typing, 80, "type here and press ENTER to chat", 20)
        self.focus = "roomchat"
        if pygame.K_RETURN in self.pressed and self.typing.strip():
            self.send_chat(self.typing)
            self.typing = ""


CHANGELOG = [
    ("v2.4.0  -  MARK TWO", [
        "NEW LOOK: every tower (all 5 levels of each) and every enemy was rebuilt in detail, and all 21 maps dress them in their",
        "own style: snow and ice on Frostbite Pass, sandstone and bronze on Dune Runner, lava-cracked basalt on Crossfire...",
        "Enemies WALK now (legs, tracks, wings), fall apart when they die, and swing when they hit your path towers.",
        "NEW TOWER: the SUMMONER (level 11). It sends goons out of your core. A goon and an enemy that meet trade health.",
        "SPRINT (hold Shift) and JUMP (Space). Because of that, START WAVE moved to G.",
        "CHANGE YOUR KEYS: OPTIONS > CONTROLS. Every hint in the game shows the key you chose.",
        "Point at a player's orb to see their level, loadout and perks.",
        "CHAT looks like talking to the people on the maps, with your orb and name. Swear words turn into !$^&# with a buzz.",
        "With friends, the next wave starts by itself after 2 seconds. Nobody has to ready up any more.",
        "Zoomed far out, in the flat view and on LOW detail the simple old models are used, so slow PCs keep up.",
    ]),
    ("v2.3.2  -  FIND THE OTHER PC", [
        "Updates: either PC can start now. The older one fetches, or the newer one pushes - so it works when only one",
        "of them can be reached through its firewall. It also asks on every network adapter, not just one.",
        "OPTIONS > UPDATES shows this PC's address and takes the other PC's address, for networks where they cannot find each other.",
        "It says what went wrong: no answer at all, or a PC that answered with a different code. And a checklist for the firewall.",
    ]),
    ("v2.3.1  -  IS IT CONNECTED?", [
        "OPTIONS > UPDATES now shows a light: OTHER PC CONNECTED (and which version it has) or NOT SEEN YET.",
        "So you can tell the link between your two PCs works even when there is nothing to update.",
    ]),
    ("v2.3.0  -  HIT CASH", [
        "Enemies no longer pay when they die. They pay when you HIT them: $1 to $5 for every hit.",
        "The bigger the bite a hit takes out of that enemy's health, the more it pays: a scratch is $1, most of its health is $5.",
        "Beams, auras and burning fields count as a $1 hit for every 5% of an enemy's health they melt (every 1% on a boss).",
        "Fast towers earn from bosses and tanks, heavy hitters earn from the small stuff. An enemy that leaks has still paid for its hits.",
        "Wave pay starts higher, and a boss wave pays one and a half times when it is over.",
        "WAR CHEST and the BOUNTY card now give extra hit cash. Every level was played again by the bot and re-tuned.",
        "UPDATES (under OPTIONS): give your two PCs the same update code once. From then on the one with the newer version",
        "hands it to the other over your Wi-Fi: it is checked, installed and the game restarts. No more USB sticks.",
        "Using the .exe? A newer neon_bastion.py dropped next to NeonBastion.exe is used by itself: no need to make the .exe again.",
    ]),
    ("v2.2.1  -  ONE MENU", [
        "The lobby is gone: the title screen is the main menu now, with a live match behind it.",
        "Six buttons instead of fourteen. Things that belong together share one page with tabs at the top:",
        "PLAY = maps, events, tutorials.   ARMORY = towers, perks.   PROFILE = name, titles, colour and core.",
        "OPTIONS = settings, how to play, what's new.   You and your loadout sit in the bottom corners.",
    ]),
    ("v2.2.0  -  HIGH GROUND", [
        "Real height. Maps now have plateaus stacked up to three levels, roads that climb ramps, banks and bridges.",
        "Every map was rebuilt around it: an overpass in Neon City, sky islands joined by bridges, a pier out to an island,",
        "a spiral down into a pit, a pyramid to climb, a price chart that only goes up. No two play the same.",
        "CLIFF now means land higher than the road beside it. Land level with a raised road is GROUND. Higher cliffs see further.",
        "AT HOME: every map gives three towers a bonus (the map screen shows which).",
        "TUTORIALS: one for every map on every difficulty, played live with the cheapest setup that wins.",
        "Your orb walks up ramps, across bridges and under them. Things on bridges and under them are drawn in the right order.",
        "Rebalanced by playing every level with the bot: waves start gentler and end tougher, Hard and Insane need better gear.",
        "FIXED: Esc and P opened the pause menu and closed it again in the same instant.",
    ]),
    ("v2.1.1  -  NO FREE LEAKS", [
        "A leak now takes off exactly the health the enemy has left. The number over its head is the damage it will do.",
        "Weak enemies sting, strong ones end the run: finish them off before the core, or do not let them through at all.",
    ]),
    ("v2.1.0  -  CLEAN LINES", [
        "FIXED: starting a second match could draw the cliffs and scenery of the map you played before on top of the new one.",
        "FIXED: fullscreen. The picture is now fitted to your screen by the game itself, so nothing is cut off or shifted.",
        "FIXED: draw order. Parts of a tower no longer show through each other, and walls only hide what is behind them.",
        "FIXED: zoom. It glides, works with any mouse wheel or touchpad, and - and = zoom too. The 2D view can zoom and slide.",
        "Things no longer vanish at the screen edge or when the camera is close. Range circles climb over cliffs.",
        "Your orb is solid: it slides along cliffs, towers and landmarks instead of sinking into them.",
        "SKIP WAVE (N): take the wave bonus now and call the next wave early. Not on boss waves. With friends it is a vote.",
        "PLAN towers: place a tower you cannot afford yet. It waits as a ghost and builds itself when you have the cash.",
        "Enemy health numbers. Point at an enemy to see its health and how much it would hurt the core right now.",
        "The core has 100 health (60 on Insane).",
        "Scenery keeps well away from the road, and towers can no longer hang over the edge of it.",
    ]),
    ("v2.0.0  -  THE THIRD DIMENSION", [
        "Matches are in 3D now. You are an orb with your name on it: WASD to move, right mouse to turn, scroll to zoom.",
        "Prefer the old look? Press V (or use Settings) for a flat top-down 2D view. SHIFT + P is cinematic free camera.",
        "Free placement: no more grid. Every tower has a boundary box and a range circle (both can be hidden in Settings).",
        "Every tower has 5 different designs, one per level, and you can PAINT your towers in the tower shop.",
        "Wi-Fi play: host a game and friends on your Wi-Fi join with one click. Up to 4 players, with chat (ENTER).",
        "Path towers: Guardian, Bulwark and Reactor stand ON the road, have health, explode when they fall and come back.",
        "13 new towers (26 in all), 10 new maps (14 in all), tower perks, stackable normal perks and 2 ability slots.",
        "Events: Halloween and Christmas appear in season. 5 secret events are hidden behind side quests. Talk to people!",
        "Event towers: 7 silly ones. Earn one after its event is over and it is called a RIPOFF.",
        "Point at a tower to see its level. E upgrades and X sells the tower you point at, no selecting needed.",
        "New HUD: loadout bottom left, details tab on the left, chat and dialogue bottom centre.",
        "Difficulties are now Normal, Hard and Insane. Final bosses have 25k, 50k and 100k health. Insane pays 1000 coins.",
        "Titles to show off what you have beaten, strat videos played live by the bot, and a new shop price curve.",
    ]),
    ("v1.0.0  -  FIRST RELEASE", [
        "A neon tower defense in the style of Neon Siege: lobby, levels, coins, loadouts, perks, cards and bosses.",
    ]),
]

# ---------------------------------------------------------------- tutorials
# One for every map on every difficulty.  The bot plays them live, so each one is a setup that was checked to win.
# A tier = (level you need, loadout, perks, ability perks).  Tower perks: the ones you can own at that level.
GUIDE_TIERS = [
    (1, ["blaster", "blade", "rail"], ["overcharge"], ["sword"]),
    (2, ["blaster", "blade", "rail", "scatter"], ["overcharge"], ["sword"]),
    (3, ["blaster", "blade", "rail", "scatter", "guardian"], ["overcharge"], ["sword"]),
    (4, ["blaster", "rail", "scatter", "guardian", "cryo"], ["overcharge"], ["sword"]),
    (5, ["blaster", "rail", "guardian", "cryo", "mortar"], ["overcharge"], ["sword"]),
    (6, ["blaster", "rail", "cryo", "mortar", "harvester"], ["overcharge", "warchest"], ["sword"]),
    (7, ["blaster", "rail", "cryo", "mortar", "sentinel"], ["overcharge", "rapid"], ["sword"]),
    (8, ["blaster", "rail", "cryo", "mortar", "sentinel", "harvester"], ["overcharge", "rapid"], ["sword"]),
    (10, ["blaster", "rail", "cryo", "mortar", "sentinel", "harvester"], ["overcharge", "rapid"], ["sword", "napalm"]),
    (15, ["blaster", "rail", "cryo", "mortar", "sentinel", "harvester"], ["overcharge", "rapid", "critical"], ["sword", "laser"]),
    (21, ["blaster", "rail", "cryo", "mortar", "sentinel", "harvester"], ["overcharge", "critical", "executioner"], ["sword", "laser"]),
]
GUIDE_TIPS = [
    "Only the three starter towers. Blasters where the road bends, Rails on high ground, Blades right beside the road. Upgrade before you build more.",
    "The Scatter is your first buy. Put it where the road passes twice, so one tower works on two stretches.",
    "A Guardian on the road holds enemies still under your guns. Put it where the most towers can reach.",
    "Cryo slows everything near it. One next to your best damage spot is worth more than another gun.",
    "Mortars go on high ground and hit groups. Rails on STRONG handle the big ones. Cryo keeps them both busy.",
    "Build Harvesters early, while the waves are still easy. The cash they make pays for the late game.",
    "Sentinels shoot far and stab close, so they like corners. Two perks now: more damage and faster shots.",
    "Six towers, each with a job: Blaster to open, Rail for the strong, Mortar for groups, Cryo to slow, Sentinel for corners, Harvester for cash.",
    "A second ability perk: Napalm burns the swarms, the Sword stays for whatever slips through near the core.",
    "Three perks and the Orbital Laser. Keep the Laser for bosses and Juggernauts: anything that leaks with health left hurts badly.",
    "Executioner makes bosses, Elites and Juggernauts take a third more damage. On the hardest levels that is what gets the final boss down in time.",
]
# GUIDES-BEGIN  (map:difficulty -> (tier, the exact run that was checked to win))
GUIDES = {
    'first:normal': (0, 1), 'first:hard': (7, 1), 'first:insane': (9, 1), 'frost:normal': (0, 1), 'frost:hard': (8, 1),
    'frost:insane': (8, 2), 'horizon:normal': (0, 1), 'horizon:hard': (7, 1), 'horizon:insane': (9, 1), 'city:normal': (0, 1),
    'city:hard': (7, 1), 'city:insane': (8, 2), 'dune:normal': (0, 1), 'dune:hard': (5, 1), 'dune:insane': (9, 1),
    'cross:normal': (0, 1), 'cross:hard': (7, 1), 'cross:insane': (8, 1), 'grove:normal': (3, 1), 'grove:hard': (5, 1),
    'grove:insane': (8, 1), 'tide:normal': (3, 1), 'tide:hard': (5, 1), 'tide:insane': (9, 1), 'crystal:normal': (1, 1),
    'crystal:hard': (7, 1), 'crystal:insane': (9, 2), 'sky:normal': (1, 1), 'sky:hard': (5, 1), 'sky:insane': (10, 1),
    'foundry:normal': (0, 1), 'foundry:hard': (5, 1), 'foundry:insane': (9, 1), 'sunset:normal': (0, 1), 'sunset:hard': (3, 2),
    'sunset:insane': (8, 1), 'board:normal': (3, 1), 'board:hard': (5, 2), 'board:insane': (10, 1), 'core:normal': (5, 1),
    'core:hard': (8, 2), 'core:insane': (10, 1), 'haunted:event': (3, 1), 'winter:event': (3, 1), 'pond:event': (3, 1),
    'kitchen:event': (2, 2), 'glitch:event': (3, 1), 'market:event': (2, 1), 'quarry:event': (1, 1),
}
# GUIDES-END


def guide_of(mapid, diff):
    """the tutorial for this map and difficulty (or None)"""
    m = MAP_BY_ID[mapid]
    if m.get("event"):
        diff = "event"
    g = GUIDES.get("%s:%s" % (mapid, diff))
    if g is None:
        return None
    ti, seed = g
    need, lo, perks, abils = GUIDE_TIERS[ti]
    tp = dict((k, TPERK_OF[k]) for k in lo if k in TPERK_OF and TPERKS[TPERK_OF[k]]["need"] <= need)
    D = DIFFS[diff]
    blurb = GUIDE_TIPS[ti]
    if m.get("buff"):
        blurb += "  At home here: " + ", ".join(TOWERS[k]["name"] for k in m["buff"]) + "."
    return dict(key="%s:%s" % (mapid, diff), title="%s  -  %s" % (m["name"], D["name"]), map=mapid, diff=diff, loadout=lo, perks=perks, abils=abils, tperks=tp,
                seed=seed, need=max(need, m["need"]), blurb=blurb)


def main():
    try:
        Game().run()
    except SystemExit:
        raise
    except Exception:
        import traceback
        txt = traceback.format_exc()
        try:
            with open(os.path.join(base_dir(), "neon_bastion_crash.txt"), "w", encoding="utf-8") as fh:
                fh.write(txt)
        except Exception:
            pass
        print(txt)
        print("NEON BASTION crashed. The details were saved to neon_bastion_crash.txt next to the game.")
        try:
            pygame.quit()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
