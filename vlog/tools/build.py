#!/usr/bin/env python3
"""하루치 브이로그를 storyboard.json 하나로 렌더링한다.

    python3 vlog/tools/build.py vlog/days/2026-11-12

결과물 (day/out/):
    vlog.mp4          보정 + 자막 + 음악/효과음이 들어간 완성본
    thumb_N.jpg       storyboard의 thumbnails 항목마다 1장
    post.txt          인스타 업로드용 캡션 + 해시태그
"""
import json, os, re, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # vlog/
FONT_DIR = os.path.join(ROOT, ".cache", "fonts")
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
SR = 48000


# ───────────────────────── helpers ─────────────────────────
def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (int(round(a * 255)),)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{r.stderr[-3000:]}")


def font(name, size):
    path = os.path.join(FONT_DIR, name)
    if not os.path.exists(path):
        sys.exit(f"폰트 없음: {path}\n먼저 `bash vlog/tools/setup.sh` 를 실행하세요.")
    return ImageFont.truetype(path, size)


# ───────────────────────── rich text (한글 + 컬러 이모지) ─────────────────────────
_efont = None
EMO_RE = re.compile(r"((?:[\U0001F000-\U0001FAFF☀-➿⬀-⯿][️‍♀♂]*)+)")


def _emoji(e, h):
    global _efont
    if _efont is None:
        _efont = ImageFont.truetype(EMOJI_FONT, 109, layout_engine=ImageFont.Layout.RAQM)
    im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), e, font=_efont, embedded_color=True)
    b = im.getbbox()
    if not b:
        return Image.new("RGBA", (1, h))
    im = im.crop((10, b[1], int(10 + _efont.getlength(e)), b[3]))
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def _runs(text):
    return [(p, bool(EMO_RE.fullmatch(p))) for p in EMO_RE.split(text) if p]


def measure(text, f):
    asc, desc = f.getmetrics()
    w = sum(_emoji(p, int(asc * 0.95)).width + 2 if e else f.getlength(p) for p, e in _runs(text))
    return w, asc + desc


def draw_rich(canvas, xy, text, f, fill, shadow=None, blur=6, stroke=0, stroke_fill=None):
    x, y = xy
    asc, _ = f.getmetrics()
    for p, is_e in _runs(text):
        if is_e:
            em = _emoji(p, int(asc * 0.95))
            canvas.alpha_composite(em, (int(x) + 1, int(y + asc * 0.08)))
            x += em.width + 2
            continue
        if shadow:
            sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).text((x, y + 2), p, font=f, fill=shadow, stroke_width=stroke, stroke_fill=shadow)
            canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
        ImageDraw.Draw(canvas).text((x, y), p, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += f.getlength(p)


def centered(canvas, y, text, f, fill, **kw):
    draw_rich(canvas, ((canvas.width - measure(text, f)[0]) / 2, y), text, f, fill, **kw)
    return measure(text, f)[1]


def wrap(text, f, maxw):
    if "\n" in text:  # storyboard에서 줄바꿈을 직접 지정한 경우
        return text.split("\n")
    if measure(text, f)[0] <= maxw:
        return [text]
    words, best = text.split(" "), None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        m = max(measure(a, f)[0], measure(b, f)[0])
        if best is None or m < best[0]:
            best = (m, [a, b])
    return best[1] if best else [text]


# ───────────────────────── badge 자막 (각진 배지 + 산세리프, 괄호 포인트는 명조) ─────────────────────────
NOTE_RE = re.compile(r"^(.*?)\s*([(<〈][^()<>〈〉]*[)>〉])\s*$")


def t_width(text, f, track):
    asc, _ = f.getmetrics()
    w = 0.0
    for p, is_e in _runs(text):
        w += _emoji(p, int(asc * 0.95)).width + 2 if is_e else sum(f.getlength(ch) + track for ch in p)
    return w - track


def t_draw(layer, x, y, text, f, fill, track, stroke=0, stroke_fill=None):
    """자간(track px)을 적용해 한 글자씩 그린다. 이모지는 컬러로."""
    asc, _ = f.getmetrics()
    d = ImageDraw.Draw(layer)
    for p, is_e in _runs(text):
        if is_e:
            em = _emoji(p, int(asc * 0.95))
            layer.alpha_composite(em, (int(x) + 1, int(y + asc * 0.08)))
            x += em.width + 2 + track
            continue
        for ch in p:
            d.text((x, y), ch, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
            x += f.getlength(ch) + track


def soft_shadow(im, layer, c, k):
    """레이어의 모양대로 은은한 그림자 (불투명도 25%, 블러 15)."""
    a = layer.split()[3].point(lambda v: int(v * c.get("shadow_opacity", 0.25)))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(c.get("shadow_blur", 15) * k / 1.5))
    im.alpha_composite(sh, (0, round(3 * k)))


def badge_line(im, cy, text, f, fg, bg, c, k):
    """가운데 정렬 각진 배지 한 줄. cy=배지 위쪽 y. 배지 높이를 돌려준다."""
    track = c.get("tracking", -2) * f.size / 100
    w = t_width(text, f, track)
    x0, y0, x1, y1 = f.getbbox("가Ag")
    th = y1 - y0
    px, py = c.get("pad_x", 0.42) * f.size, c.get("pad_y", 0.26) * f.size
    bw, bh = w + 2 * px, th + 2 * py
    bx = (im.width - bw) / 2
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    boxed = c.get("box", True)
    if boxed:
        ImageDraw.Draw(layer).rectangle((bx, cy, bx + bw, cy + bh), fill=bg)
        soft_shadow(im, layer, c, k)
    txt = Image.new("RGBA", im.size, (0, 0, 0, 0))  # 글자는 따로 그려서 합성 (외곽선이 배지를 덮어쓰지 않게)
    t_draw(txt, bx + px, cy + py - y0, text, f, fg, track,
           stroke=max(1, round(c.get("stroke", 10) / 10 * k * (0.5 if boxed else 0.8))),
           stroke_fill=hex_rgba(c.get("stroke_color", "#000000"), c.get("stroke_opacity", 0.12 if boxed else 0.35)))
    if not boxed:  # 박스가 없으면 글자 모양대로 그림자
        soft_shadow(im, txt, c, k)
    layer.alpha_composite(txt)
    im.alpha_composite(layer)
    return bh if boxed else th + c.get("line_gap", 0.18) * f.size
    return bh


def caption_badge(im, tag, text, c, W, H, tone=None):
    k = W / 720
    tones = c["tones"]
    fm = font(c["font_text"], round(c["size_text"] * k))
    ft = font(c["font_tag"], round(c["size_tag"] * k))
    fn = font(c["font_note"], round(c["size_note"] * k))
    main, note = text, ""
    m = NOTE_RE.match(text.replace("\n", "\x00"))
    if m:
        main, note = m.group(1).replace("\x00", "\n"), m.group(2)
    y = H * c["y"]
    if tag:
        t = tones[c.get("tag_tone", "taupe")]
        y += badge_line(im, y, tag, ft, hex_rgba(t["fg"]), hex_rgba(t["bg"], t.get("alpha", 1)), c, k) + c.get("gap", 6) * k
    t = tones[tone or c.get("text_tone", "beige")]
    for line in [l for l in main.split("\n") if l.strip()]:
        y += badge_line(im, y, line.strip(), fm, hex_rgba(t["fg"]), hex_rgba(t["bg"], t.get("alpha", 1)), c, k) + c.get("gap", 6) * k
    if note:  # 괄호 속 감성 포인트: 박스 없이 명조로 작게
        y += 4 * k
        track = c.get("tracking", -2) * fn.size / 100
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        t_draw(layer, (W - t_width(note, fn, track)) / 2, y, note, fn, hex_rgba(c.get("note_color", "#FBF8F3")), track,
               stroke=max(1, round(k * 0.8)), stroke_fill=hex_rgba("#3B342F", 0.6))
        soft_shadow(im, layer, dict(c, shadow_opacity=0.7, shadow_blur=10), k)
        im.alpha_composite(layer)


# ───────────────────────── captions ─────────────────────────
def caption_png(path, tag, text, P, W, H, tone=None):
    c, k = P["caption"], W / 720
    if c.get("style") == "badge":
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        caption_badge(im, tag, text, c, W, H, tone)
        im.save(path)
        return
    ft, fm = font(c["font_tag"], round(c["size_tag"] * k)), font(c["font_text"], round(c["size_text"] * k))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if c.get("style") == "minimal":  # 박스 없이 작은 명조: 위쪽 가운데 "7:40 / breakfast"
        sh = hex_rgba("#000000", c.get("shadow", 0.5))
        y = H * c["y"]
        if tag:
            y += centered(im, y, tag, ft, hex_rgba(c["color_tag"]), shadow=sh, blur=3 * k) + c.get("line_gap", 0) * k
        for l in (wrap(text, fm, c["max_text_width"] * k) if text else []):
            y += centered(im, y, l, fm, hex_rgba(c["color_text"]), shadow=sh, blur=3 * k) + c.get("line_gap", 0) * k
        im.save(path)
        return
    lines = wrap(text, fm, c["max_text_width"] * k) if text else []
    th = measure(tag, ft)[1] if tag else 0
    lh = measure("가", fm)[1] + 4 * k
    widths = [measure(l, fm)[0] for l in lines] + ([measure(tag, ft)[0]] if tag else [])
    if not widths:
        im.save(path); return
    bw = max(widths) + 2 * c["pad_x"] * k
    bh = 16 * k + th + (6 * k if tag and lines else 0) + lh * len(lines) + 12 * k
    x0, y0 = (W - bw) / 2, H * c["y"]
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=c["box_radius"] * k,
                                          fill=hex_rgba(c["box_color"], c["box_opacity"]))
    im.alpha_composite(box)
    y = y0 + 14 * k
    if tag:
        draw_rich(im, ((W - measure(tag, ft)[0]) / 2, y), tag, ft, hex_rgba(c["color_tag"]))
        y = y0 + 16 * k + th + 6 * k
    for l in lines:
        draw_rich(im, ((W - measure(l, fm)[0]) / 2, y), l, fm, hex_rgba(c["color_text"]))
        y += lh
    im.save(path)


# ───────────────────────── audio ─────────────────────────
class Mixer:
    def __init__(self, dur, seed):
        self.N = int(SR * dur)
        self.buf = np.zeros((self.N, 2))
        self.rng = np.random.default_rng(seed)

    def add(self, sig, t, gain=1.0, pan=0.0):
        i = int(t * SR)
        sig = sig[: max(0, self.N - i)]
        if len(sig) and i >= 0:
            self.buf[i:i + len(sig), 0] += sig * gain * np.sqrt((1 - pan) / 2)
            self.buf[i:i + len(sig), 1] += sig * gain * np.sqrt((1 + pan) / 2)


def lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); s = 0.0
    for i, v in enumerate(x):
        s = (1 - a) * v + a * s; y[i] = s
    return y


def hp(x, fc):
    return x - lp(x, fc)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


# 진행은 seed(=날짜)로 골라서 매일 조금씩 다른 곡이 나온다
PROGRESSIONS = [
    ([[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 62]], [41, 40, 38, 36]),  # Fmaj7 Em7 Dm7 Cadd9
    ([[48, 52, 55, 59], [45, 48, 52, 55], [50, 53, 57, 60], [43, 47, 50, 53]], [36, 33, 38, 31]),  # Cmaj7 Am7 Dm7 G7
    ([[50, 53, 57, 60], [43, 47, 50, 53], [48, 52, 55, 59], [45, 48, 52, 55]], [38, 31, 36, 33]),  # Dm7 G7 Cmaj7 Am7
    ([[53, 57, 60, 64], [55, 59, 62, 65], [52, 55, 59, 62], [45, 48, 52, 55]], [41, 43, 40, 33]),  # Fmaj7 G7 Em7 Am7
]
ARPS = [[0, 2, 1, 3, 2, 1, 3, 2], [0, 1, 2, 3, 2, 1, 2, 3], [0, 2, 3, 2, 1, 2, 3, 1]]


def lofi(mx, dur, bpm):
    rng = mx.rng
    beat = 60 / bpm
    bar = 4 * beat
    chords, roots = PROGRESSIONS[rng.integers(len(PROGRESSIONS))]
    arp = ARPS[rng.integers(len(ARPS))]

    def pluck(f, d=1.4, bright=0.5):
        n, p = int(SR * d), int(SR / f)
        buf = lp(rng.uniform(-1, 1, p), 2000 + 4000 * bright)
        out = np.empty(n)
        for i in range(n):
            v = buf[i % p]; out[i] = v
            buf[i % p] = 0.996 * 0.5 * (v + buf[(i + 1) % p])
        return out * np.linspace(1, 0.6, n)

    def epiano(f, d=2.0):
        t = np.arange(int(SR * d)) / SR
        env = np.exp(-t * 1.6) * (1 - np.exp(-t * 200))
        s = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) * np.exp(-t * 4) + 0.6 * np.sin(2 * np.pi * f * 1.003 * t)
        return s * env * (1 + 0.15 * np.sin(2 * np.pi * 4.5 * t))

    plucks = {}
    nbars = int(np.ceil(dur / bar))
    for b in range(nbars):
        tb, ci = b * bar, (b // 2) % len(chords)
        ch = chords[ci]
        for n in ch:
            mx.add(epiano(midi(n), 2.2), tb + 0.01 * rng.random(), 0.05, -0.2)
        mx.add(epiano(midi(roots[ci]), 2.0), tb, 0.14)
        for k in range(8):
            note = ch[arp[k]] + 12
            if note not in plucks:
                plucks[note] = pluck(midi(note))
            mx.add(plucks[note], tb + k * beat / 2 + (0.04 if k % 2 else 0), 0.16 * (0.8 + 0.2 * rng.random()), 0.35)

    t = np.arange(int(SR * 0.35)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)
    t = np.arange(int(SR * 0.25)) / SR
    snare = (hp(lp(rng.uniform(-1, 1, len(t)), 5000), 900) * 1.2 + 0.3 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 18)
    t = np.arange(int(SR * 0.06)) / SR
    hat = hp(rng.uniform(-1, 1, len(t)), 6000) * np.exp(-t * 70)
    for b in range(int(dur / beat) + 1):
        tt = b * beat
        if b % 4 == 0 or b % 8 == 6: mx.add(kick, tt, 0.55)
        if b % 4 == 2 and b >= 4: mx.add(snare, tt + 0.015, 0.22, 0.1)
        if b >= 2:
            mx.add(hat, tt, 0.05, -0.3); mx.add(hat, tt + beat / 2 + 0.04, 0.03, -0.3)

    for c in range(2):
        mx.buf[:, c] = lp(mx.buf[:, c], 3800)
    mx.buf = np.tanh(mx.buf * 1.3) / 1.3
    hiss = lp(rng.normal(0, 1, mx.N), 2500) * 0.004
    crackle = np.zeros(mx.N)
    idx = rng.choice(mx.N, int(9 * dur), replace=False)
    crackle[idx] = rng.uniform(-0.12, 0.12, len(idx))
    mx.buf += (hiss + lp(crackle, 3000))[:, None]


# ── ASMR 효과음: storyboard의 "sfx": [{"type": "...", "at": 0.3, "dur": 1.5}] ──
def sfx(mx, kind, t, dur):
    rng = mx.rng
    if kind == "leaves":  # 낙엽 바스락 + 발걸음
        n = int(SR * dur)
        x = hp(lp(rng.uniform(-1, 1, n), 7000), 1500)
        env = np.zeros(n)
        for _ in range(int(dur * 22)):
            i, L = rng.integers(0, max(1, n - 2400)), rng.integers(600, 2400)
            env[i:i + L] += np.hanning(L)[: n - i] * rng.uniform(0.3, 1)
        for s in np.arange(0.15, dur, 0.55):
            i, L = int(s * SR), int(0.25 * SR)
            env[i:i + L] += np.hanning(L)[: n - i] * 1.2
        mx.add(x * env * 0.5, t, 0.22, 0.2)
    elif kind == "footsteps":
        for s in np.arange(0, dur, 0.5):
            tt = np.arange(int(SR * 0.12)) / SR
            mx.add(lp(rng.uniform(-1, 1, len(tt)), 1200) * np.exp(-tt * 40), t + s, 0.25)
    elif kind == "cup":  # 컵/병 내려놓는 소리
        tt = np.arange(int(SR * 0.5)) / SR
        s = 0.8 * np.sin(2 * np.pi * 140 * tt) * np.exp(-tt * 30) + lp(rng.uniform(-1, 1, len(tt)), 1800) * np.exp(-tt * 60) \
            + 0.15 * np.sin(2 * np.pi * 1320 * tt) * np.exp(-tt * 25)
        mx.add(s, t, 0.35)
    elif kind == "keyboard":  # 타건음
        x = t
        while x < t + dur:
            tt = np.arange(int(SR * 0.03)) / SR
            c = (hp(rng.uniform(-1, 1, len(tt)), 2500) + 0.4 * np.sin(2 * np.pi * rng.uniform(1800, 2600) * tt)) * np.exp(-tt * 220)
            mx.add(c, x, rng.uniform(0.10, 0.18), rng.uniform(-0.4, 0.4))
            x += rng.uniform(0.07, 0.2) if rng.random() > 0.12 else 0.35
    elif kind == "ding":  # 엘리베이터 딩
        tt = np.arange(int(SR * 1.2)) / SR
        s = (np.sin(2 * np.pi * 1047 * tt) + 0.4 * np.sin(2 * np.pi * 2094 * tt)) * np.exp(-tt * 3.5) * (1 - np.exp(-tt * 300))
        mx.add(s, t, 0.08)
    elif kind == "shutter":  # 카메라 셔터
        for off in (0, 0.045):
            tt = np.arange(int(SR * 0.04)) / SR
            mx.add(hp(rng.uniform(-1, 1, len(tt)), 3000) * np.exp(-tt * 150), t + off, 0.12)
    elif kind == "pour":  # 커피 따르는 소리
        n = int(SR * dur)
        x = lp(hp(rng.uniform(-1, 1, n), 400), 2500) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * np.arange(n) / SR))
        mx.add(x * np.hanning(n), t, 0.18)
    elif kind == "pop":  # 뽁 (등장/포인트)
        tt = np.arange(int(SR * 0.18)) / SR
        f = 380 + 900 * np.exp(-tt * 40)
        mx.add(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 28), t, 0.35)
    elif kind == "whoosh":  # 휙 (장면 전환)
        n = int(SR * min(dur, 0.45))
        x = rng.uniform(-1, 1, n)
        env = np.sin(np.linspace(0, np.pi, n)) ** 2
        mx.add(hp(lp(x, 2500), 300) * env, t, 0.30, -0.3)
    elif kind == "sparkle":  # 반짝 (간식/라인업)
        for i, m in enumerate([88, 92, 95, 100]):
            tt = np.arange(int(SR * 0.5)) / SR
            s = np.sin(2 * np.pi * midi(m) * tt) * np.exp(-tt * 9) * (1 - np.exp(-tt * 400))
            mx.add(s, t + i * 0.06, 0.07, (i - 1.5) * 0.3)
    elif kind == "rustle":  # 과자 봉지 바스락
        n = int(SR * dur)
        x = hp(rng.uniform(-1, 1, n), 2500)
        env = np.zeros(n)
        for _ in range(int(dur * 14)):
            i, L = rng.integers(0, max(1, n - 3000)), rng.integers(500, 3000)
            env[i:i + L] += np.hanning(L)[: n - i] * rng.uniform(0.3, 1)
        mx.add(x * np.minimum(env, 1.2), t, 0.13, 0.15)
    elif kind == "crunch":  # 아삭/바삭 씹는 소리
        x = t
        while x < t + dur:
            tt = np.arange(int(SR * 0.09)) / SR
            c = lp(rng.uniform(-1, 1, len(tt)), 3500) * (rng.random(len(tt)) > 0.55) * np.exp(-tt * 35)
            mx.add(c, x, rng.uniform(0.25, 0.4))
            x += rng.uniform(0.28, 0.42)
    elif kind == "gulp":  # 꿀꺽
        for k in range(int(max(1, dur // 0.55))):
            tt = np.arange(int(SR * 0.16)) / SR
            f = 260 - 140 * tt / 0.16
            s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.16) ** 2
            mx.add(s + 0.3 * lp(rng.uniform(-1, 1, len(tt)), 600) * np.exp(-tt * 20), t + k * 0.55, 0.35)
    elif kind == "clink":  # 숟가락/접시 챙
        tt = np.arange(int(SR * 0.7)) / SR
        s = sum(a * np.sin(2 * np.pi * fr * tt) * np.exp(-tt * d) for fr, a, d in ((2350, 1, 7), (3720, .6, 9), (5480, .35, 12)))
        mx.add(s * (1 - np.exp(-tt * 900)), t, 0.07, 0.2)
    elif kind == "hanger":  # 옷걸이 딸깍
        for off, fr in ((0, 900), (0.07, 1250)):
            tt = np.arange(int(SR * 0.12)) / SR
            mx.add((np.sin(2 * np.pi * fr * tt) * 0.6 + hp(rng.uniform(-1, 1, len(tt)), 1500) * 0.5) * np.exp(-tt * 45), t + off, 0.2)
    elif kind == "tick":  # 시계 째깍
        for k, s in enumerate(np.arange(0, dur, 0.5)):
            tt = np.arange(int(SR * 0.025)) / SR
            mx.add(hp(rng.uniform(-1, 1, len(tt)), 2000) * np.exp(-tt * 300), t + s, 0.16 if k % 2 else 0.22, 0.3)
    elif kind == "boing":  # 띠용 (멍때림/귀여운 포인트)
        tt = np.arange(int(SR * 0.45)) / SR
        f = 300 + 120 * np.sin(2 * np.pi * 9 * tt) * np.exp(-tt * 4) + 180 * tt
        mx.add(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 6) * (1 - np.exp(-tt * 300)), t, 0.18)
    elif kind == "chime":  # 띵동 (퇴근/지하철 안내음 느낌)
        for k, m in enumerate([76, 72]):
            tt = np.arange(int(SR * 1.0)) / SR
            s = (np.sin(2 * np.pi * midi(m) * tt) + 0.3 * np.sin(4 * np.pi * midi(m) * tt)) * np.exp(-tt * 3.2) * (1 - np.exp(-tt * 300))
            mx.add(s, t + k * 0.32, 0.09)
    else:
        print(f"  (알 수 없는 sfx '{kind}' 건너뜀)")


def build_audio(path, dur, P, timeline, seed, day_dir):
    m = P["music"]
    mx = Mixer(dur, seed)
    if m["mode"] == "lofi":
        lofi(mx, dur, m["bpm"])
        mx.buf *= m.get("gain", 1.0)
    elif m["mode"] == "file" and m.get("file"):
        tmp = path + ".music.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(day_dir, m["file"]), "-t", str(dur), "-ac", "2", "-ar", str(SR), tmp])
        with wave.open(tmp) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32768
        mx.buf[: len(a)] += a[: mx.N] * m.get("gain", 1.0)
    for start, clip in timeline:
        for s in clip.get("sfx", []):
            sfx(mx, s["type"], start + s.get("at", 0), s.get("dur", clip["_dur"] - s.get("at", 0)))
    fi, fo = int(m["fade_in"] * SR), int(m["fade_out"] * SR)
    mx.buf[:fi] *= np.linspace(0, 1, fi)[:, None]
    mx.buf[-fo:] *= np.linspace(1, 0, fo)[:, None]
    peak = np.max(np.abs(mx.buf))
    if peak > 0:  # 음악 없이 효과음만 있을 땐 -6dB 정도로 잔잔하게
        mx.buf *= (0.89 if m["mode"] != "none" else 0.5) / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mx.buf * 32767).astype("<i2").tobytes())


# ───────────────────────── video ─────────────────────────
TONEMAP = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"


def hdr_prefix(path):
    """아이폰 HDR(HLG/PQ) 영상이면 SDR로 톤매핑하는 필터를 앞에 붙인다 (안 하면 색이 바래 보임)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return TONEMAP if r.stdout.strip().strip(",").split(",")[0] in ("arib-std-b67", "smpte2084") else ""


def grade_filter(P):
    g = P["grade"]
    c = g["curves"]
    return (f"eq=contrast={g['contrast']}:saturation={g['saturation']}:brightness={g['brightness']},"
            f"curves=r='{c['r']}':g='{c['g']}':b='{c['b']}'")


def grab_frame(day, P, clip, at, W, H, out, image=None, focus_x=0.5, focus_y=0.5, zoom=1.0):
    """영상 클립의 한 프레임, 또는 따로 찍은 사진(image)을 9:16으로 잘라 같은 색감으로 보정한다.
    focus_x/focus_y: 잘릴 때 어디를 남길지 (0=왼쪽·위, 0.5=가운데, 1=오른쪽·아래). zoom: 1.3이면 30% 확대."""
    zw, zh = int(W * zoom) // 2 * 2, int(H * zoom) // 2 * 2
    src = ["-i", os.path.join(day, image)] if image else ["-ss", str(clip["in"] + at), "-i", os.path.join(day, clip["src"])]
    run(["ffmpeg", "-y", "-v", "error", *src, "-frames:v", "1",
         "-vf", f"{'' if image else hdr_prefix(os.path.join(day, clip['src']))}scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H}:(iw-{W})*{focus_x}:(ih-{H})*{focus_y},{grade_filter(P)},noise=alls=4:allf=u", out])
    im = Image.open(out).convert("RGBA")
    os.remove(out)
    return im


def shade(im, top=0.0, mid=0.0, bottom=0.0):
    """세로 그라데이션으로 살짝 어둡게 (글자 가독성용)."""
    W, H = im.size
    y = np.linspace(0, 1, H)
    a = np.interp(y, [0, 0.5, 1], [top, mid, bottom])
    m = Image.fromarray(np.repeat(a[:, None], W, 1).astype(np.uint8), "L")
    im.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 0)] * 3 + [m]))


def fit(name, size, texts, maxw):
    f = font(name, size)
    widest = max(measure(t, f)[0] for t in texts)
    return f if widest <= maxw else font(name, int(size * maxw / widest))


def pill(im, cx, y, text, f, fg, bg, padx, pady, radius=0):
    w, h = measure(text, f)
    box = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((cx - w / 2 - padx, y, cx + w / 2 + padx, y + h + 2 * pady), radius=radius, fill=bg)
    im.alpha_composite(box)
    draw_rich(im, (cx - w / 2, y + pady), text, f, fg)
    return h + 2 * pady


def thumbnail(day, out, P, th, clips, W, H):
    """style: classic(필 박스 카피) | serif(A day in my life) | butter(Work Day 버터옐로) | chunky(출근로그 민트)"""
    k = W / 1080
    if th.get("grade_preset"):  # 이 썸네일만 다른 프리셋 색감으로 (비교용)
        P = dict(P, grade=json.load(open(os.path.join(ROOT, "presets", th["grade_preset"] + ".json"), encoding="utf-8"))["grade"])
    im = grab_frame(day, P, clips[th.get("clip", 0)], th.get("at", 0), W, H, out + ".frame.png",
                    image=th.get("image"), focus_x=th.get("focus_x", 0.5), focus_y=th.get("focus_y", 0.5), zoom=th.get("zoom", 1.0))
    style = th.get("style", "classic")
    cream = hex_rgba("#F3F0EA")

    if style == "serif":
        shade(im, top=110, mid=0)
        sizes = th.get("sizes", [96, 96, 64])
        y = H * th.get("y", 0.10)
        for i, line in enumerate(th["lines"]):
            f = font("GowunBatang-Regular.ttf", round(sizes[min(i, len(sizes) - 1)] * k))
            y += centered(im, y, line, f, cream, shadow=(0, 0, 0, 120), blur=5 * k) + 6 * k

    elif style == "butter":
        shade(im, top=40, mid=70, bottom=40)
        lines = th["title"].split("\n")
        f = fit("Pretendard-ExtraBold.otf", round(175 * k), lines, W * 0.9)
        fs = font("Pretendard-SemiBold.otf", round(54 * k))
        y = H * th.get("y", 0.36)
        for line in lines:
            y += centered(im, y, line, f, hex_rgba(th.get("color", "#F6E3A1")), shadow=(0, 0, 0, 90), blur=10 * k) - 18 * k
        y += 46 * k
        if th.get("sub"):
            centered(im, y, th["sub"], fs, hex_rgba("#FFFFFF"), shadow=(0, 0, 0, 120), blur=6 * k)

    elif style == "chunky":
        shade(im, mid=60, bottom=60)
        mint = hex_rgba(th.get("color", "#A6EFD6"))
        pen = font("NanumPenScript-Regular.ttf", round(88 * k))
        f = fit("Jua-Regular.ttf", round(160 * k), th["lines"], W * 0.92)
        y = H * th.get("y", 0.40)
        if th.get("label"):
            y += pill(im, W / 2, y, th["label"], pen, hex_rgba("#1F1F1F"), mint, 24 * k, 6 * k) + 14 * k
        for i, line in enumerate(th["lines"]):
            col = mint if i in th.get("accent", [1]) else hex_rgba("#FFFFFF")
            y += centered(im, y, line, f, col, shadow=(0, 0, 0, 110), blur=8 * k,
                          stroke=round(5 * k), stroke_fill=hex_rgba("#3A3A3A", 0.55)) - 4 * k
        if th.get("feat"):
            pill(im, W / 2 + 40 * k, y + 14 * k, th["feat"], pen, hex_rgba("#1F1F1F"), hex_rgba("#FFFFFF", 0.93), 26 * k, 8 * k)

    else:  # classic
        T = P["thumbnail"]
        shade(im, mid=0, bottom=T["bottom_shade"])
        ft, fm = font(T["font_tag"], round(T["size_tag"] * k)), font(T["font_text"], round(T["size_text"] * k))
        y = H * T["y"]
        if th.get("tag"):
            y += centered(im, y, th["tag"], ft, hex_rgba(P["caption"]["color_tag"]), shadow=(0, 0, 0, 140)) + 18 * k
        for l in wrap(th.get("copy", ""), fm, T["max_text_width"] * k):
            y += centered(im, y, l, fm, hex_rgba(P["caption"]["color_text"]), shadow=(0, 0, 0, 150)) + 10 * k
    im.convert("RGB").save(out, quality=95)


def compare_sheet(out_dir, thumbs, W, H):
    """썸네일 후보를 나란히: 위는 릴스 화면(9:16), 아래는 프로필 피드(가운데 3:4)."""
    w = 300
    h9, h34, pad, lab = int(w * H / W), int(w * 4 / 3), 24, 60
    n = len(thumbs)
    sheet = Image.new("RGB", (pad + (w + pad) * n, lab + h9 + pad + 36 + h34 + pad), (246, 243, 238))
    d = ImageDraw.Draw(sheet)
    f, fs = font("Pretendard-SemiBold.otf", 19), font("Pretendard-Medium.otf", 17)
    gy = (H - W * 4 // 3) // 2
    for i, th in enumerate(thumbs):
        x = pad + i * (w + pad)
        im = Image.open(os.path.join(out_dir, f"thumb_{i + 1}.jpg"))
        d.text((x, 18), th.get("name", f"thumb_{i + 1}"), font=f, fill=(40, 34, 30))
        sheet.paste(im.resize((w, h9), Image.LANCZOS), (x, lab))
        sheet.paste(im.crop((0, gy, W, H - gy)).resize((w, h34), Image.LANCZOS), (x, lab + h9 + pad + 36))
    d.text((pad, lab + h9 + pad + 6), "↓ 프로필 피드에서 보이는 모습 (가운데 3:4)", font=fs, fill=(110, 100, 90))
    sheet.save(os.path.join(out_dir, "thumb_compare.jpg"), quality=92)


def title_png(path, lines, P, W, H):
    """오프닝 타이틀 (A day in my life / 9am – 9pm / based in Seoul)."""
    T, k = P["title"], W / 720
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = H * T["y"]
    for i, line in enumerate(lines):
        f = font(T["font"], round(T["sizes"][min(i, len(T["sizes"]) - 1)] * k))
        y += centered(im, y, line, f, hex_rgba(T["color"]), shadow=hex_rgba("#000000", T.get("shadow", 0.5)), blur=3 * k) + T.get("line_gap", 0) * k
    im.save(path)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    day = os.path.abspath(sys.argv[1])
    sb = json.load(open(os.path.join(day, "storyboard.json"), encoding="utf-8"))
    P = json.load(open(os.path.join(ROOT, "presets", sb.get("preset", "default") + ".json"), encoding="utf-8"))
    for k, v in sb.get("preset_overrides", {}).items():  # 그날만 살짝 바꾸고 싶을 때
        P[k].update(v)
    O = P["output"]; W, H, FPS = O["width"], O["height"], O["fps"]
    out_dir = os.path.join(day, "out"); os.makedirs(out_dir, exist_ok=True)
    clips = sb["clips"]

    # 썸네일을 먼저 만든다 (오프닝에 썸네일을 그대로 띄울 수 있게)
    for i, th in enumerate(sb.get("thumbnails", []), 1):
        thumbnail(day, os.path.join(out_dir, f"thumb_{i}.jpg"), P, th, clips, W, H)
        print(f"  ✓ out/thumb_{i}.jpg")
    if len(sb.get("thumbnails", [])) > 1:
        compare_sheet(out_dir, sb["thumbnails"], W, H)
        print("  ✓ out/thumb_compare.jpg")

    # 타임라인: [썸네일 카드] + [오프닝 훅 샷들] + [본편 클립들]
    intro = sb.get("intro", {})
    segs = []
    if intro.get("thumbnail"):  # "thumbnail": 1 → out/thumb_1.jpg를 dur초 동안 살짝 줌인하며 보여준다
        segs.append({"_thumb": os.path.join(out_dir, f"thumb_{intro['thumbnail']}.jpg"), "_intro": True,
                     "in": 0, "out": intro.get("thumbnail_dur", 1.5), "sfx": intro.get("thumbnail_sfx", [])})
    for sh in intro.get("shots", []):  # 0.3~0.4초짜리 빠른 컷 몽타주, 자막 없음
        c = clips[sh["clip"]]
        a = c["in"] + sh.get("at", 0)
        segs.append({"src": c["src"], "in": a, "out": a + sh.get("dur", 0.4), "_intro": True})
    segs += clips
    timeline, t = [], 0.0
    for c in segs:
        speed = 1.0 if c.get("_thumb") else c.get("speed", P["pacing"]["speed"])
        c["_dur"] = (c["out"] - c["in"]) / speed
        c["_speed"] = speed
        timeline.append((t, c)); t += c["_dur"]
    total = t
    intro_dur = sum(c["_dur"] for c in segs if c.get("_intro"))
    main_tl = [(st, c) for st, c in timeline if not c.get("_intro")]
    print(f"{sb.get('date', '')}  오프닝 {intro_dur:.1f}s + 클립 {len(clips)}개, 총 {total:.2f}s")

    with tempfile.TemporaryDirectory() as tmp:
        vsegs = [c for c in segs if not c.get("_thumb")]
        thumb = next((c for c in segs if c.get("_thumb")), None)
        srcs = sorted({c["src"] for c in vsegs})
        args = ["ffmpeg", "-y", "-v", "error"]
        for s in srcs:
            args += ["-i", os.path.join(day, s)]
        nin = len(srcs)
        if thumb:
            args += ["-i", thumb["_thumb"]]; ti = nin; nin += 1
        audio = os.path.join(tmp, "audio.wav")
        seed = sb.get("seed", P["music"]["seed"]) or int(re.sub(r"\D", "", sb.get("date", "0")) or 0)
        build_audio(audio, total, P, timeline, seed, day)
        args += ["-i", audio]
        ai = nin; nin += 1
        f = []
        for n, c in enumerate(vsegs):
            si = srcs.index(c["src"])
            f.append(f"[{si}:v]{hdr_prefix(os.path.join(day, c['src']))}trim=start={c['in']:.3f}:end={c['out']:.3f},setpts=(PTS-STARTPTS)/{c['_speed']},"
                     f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},setsar=1[s{n}]")
        f.append("".join(f"[s{n}]" for n in range(len(vsegs))) + f"concat=n={len(vsegs)}:v=1:a=0,"
                 f"{grade_filter(P)},noise=alls={P['grade']['grain']}:allf=t+u,format=yuv420p" + ("[vm]" if thumb else "[v0]"))
        if thumb:  # 썸네일은 이미 보정돼 있으니 색보정을 다시 하지 않고, 2배로 키운 뒤 천천히 줌인 (흔들림 방지)
            nf = round(thumb["_dur"] * FPS)
            z = intro.get("thumbnail_zoom", 1.06)
            f.append(f"[{ti}:v]scale={2 * W}:{2 * H}:flags=lanczos,"
                     f"zoompan=z='1+{z - 1:.4f}*on/{nf}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{H}:fps={FPS},"
                     f"setsar=1,format=yuv420p[vt];[vt][vm]concat=n=2:v=1:a=0[v0]")
        overlays = []  # (png, start, end)
        if intro.get("title"):
            png = os.path.join(tmp, "title.png")
            title_png(png, intro["title"], P, W, H)
            overlays.append((png, intro.get("title_from", 0.0), intro.get("title_until", intro_dur)))
        for n, (start, c) in enumerate(main_tl):
            if c.get("tag") or c.get("text"):
                png = os.path.join(tmp, f"cap{n}.png")
                caption_png(png, c.get("tag", ""), c.get("text", ""), P, W, H, c.get("tone"))
                overlays.append((png, start, start + c["_dur"]))
        for n, (png, start, end) in enumerate(overlays):
            args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", png]
            fade = f",fade=t=in:st={start:.3f}:d={P['caption']['fade_in']}:alpha=1" if P["caption"]["fade_in"] else ""
            f.append(f"[{nin + n}:v]format=rgba{fade}[c{n}];"
                     f"[v{n}][c{n}]overlay=0:0:enable='between(t,{start:.3f},{end - 0.001:.3f})'[v{n + 1}]")
        args += ["-filter_complex", ";".join(f), "-map", f"[v{len(overlays)}]", "-map", f"{ai}:a", "-t", f"{total:.3f}",
                 "-c:v", "libx264", "-crf", str(O["crf"]), "-preset", "slow", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", O["audio_bitrate"], "-movflags", "+faststart", os.path.join(out_dir, "vlog.mp4")]
        run(args)
    print("  ✓ out/vlog.mp4")

    post = sb.get("post")
    if post:
        with open(os.path.join(out_dir, "post.txt"), "w", encoding="utf-8") as fh:
            fh.write(post.get("caption", "").strip() + "\n\n" + " ".join(post.get("hashtags", [])) + "\n")
        print("  ✓ out/post.txt")


if __name__ == "__main__":
    main()
