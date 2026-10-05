#!/usr/bin/env python3
"""Draw SlidePrint's icon sets: icons/<set>/icon.ico (exe and window), logo.png (header
in the window) and splash.png (the "Starting..." card shown while the exe unpacks).

  python icons/make_assets.py            # all sets
  python icons/make_assets.py cards      # one set

Sets: 'layers' (Font Awesome "layer-group" on a blue tile; the one shipped) and 'cards'
(ghost slides behind a tilted front slide). Which set ships is chosen in build.bat / the workflow
(ICONSET). Needs Pillow and PyMuPDF, and the Segoe UI fonts of Windows for the splash.

SPDX-License-Identifier: AGPL-3.0-or-later
"""
import io, os, sys

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
N = 1024                                   # master size, scaled down for every use
ICO_SIZES = [(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)]


# --- 'cards' ---------------------------------------------------------------

def _rounded_mask(size, box, radius):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, fill=255)
    return m


def _gradient(size, top, bottom):
    w, h = size
    g = Image.new('RGB', (1, h))
    for y in range(h):
        t = y / (h - 1)
        g.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize((w, h))


def _card(w, h, radius, fill, alpha, content=False):
    """One slide, upright, on a transparent layer filled with its own colour (no dark
    fringe when blurred or rotated)."""
    pad = 60
    layer = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), fill + (0,))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill + (alpha,))
    if content:                            # title bar, two bullets
        blue, line = (66, 122, 240), (170, 186, 216)
        d.rounded_rectangle([pad + 0.10 * w, pad + 0.15 * h, pad + 0.90 * w, pad + 0.42 * h], radius=0.05 * h, fill=blue)
        for yy in (0.60, 0.80):
            cy, r = pad + yy * h, 0.055 * h
            d.ellipse([pad + 0.15 * w - r, cy - r, pad + 0.15 * w + r, cy + r], fill=blue)
            d.rounded_rectangle([pad + 0.27 * w, cy - 0.035 * h, pad + 0.88 * w, cy + 0.035 * h],
                                radius=0.035 * h, fill=line)
    return layer


def _rotate(layer, angle, fill):
    return layer.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=fill + (0,))


def cards_icon():
    img = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    m, R = 72, 230                         # tile margin and corner radius
    tile = (m, m, N - m, N - m)

    shadow = Image.new('RGBA', (N, N), (70, 90, 130, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((m, m + 18, N - m, N - m + 18), radius=R, fill=(70, 90, 130, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))

    bg = _gradient((N, N), (214, 224, 240), (166, 184, 214)).convert('RGBA')
    glow = Image.new('L', (N, N), 0)
    ImageDraw.Draw(glow).ellipse((-200, -260, 700, 620), fill=110)
    bg = Image.composite(Image.new('RGBA', (N, N), (236, 241, 250, 255)), bg, glow.filter(ImageFilter.GaussianBlur(160)))
    img.paste(bg, (0, 0), _rounded_mask((N, N), tile, R))

    angle, W, H = 7, 520, 340
    ghost = (246, 249, 255)
    for dx, dy, scale, alpha, blur in ((-250, -95, 0.62, 140, 5), (-170, -55, 0.70, 190, 3)):
        g = _rotate(_card(int(W * scale), int(H * scale * 1.35), 34, ghost, alpha), angle, ghost)
        g.putalpha(g.getchannel('A').filter(ImageFilter.GaussianBlur(blur)))
        img.alpha_composite(g, (N // 2 + dx - g.width // 2 + 40, N // 2 + dy - g.height // 2 + 40))

    front = _rotate(_card(W, H, 40, (255, 255, 255), 255, content=True), angle, (255, 255, 255))
    drop = Image.new('RGBA', front.size, (40, 60, 110, 0))
    drop.putalpha(front.getchannel('A').point(lambda a: a * 0.38))
    drop = drop.filter(ImageFilter.GaussianBlur(26))
    fx, fy = N // 2 + 60 - front.width // 2, N // 2 + 95 - front.height // 2
    img.alpha_composite(drop, (fx + 10, fy + 26))
    img.alpha_composite(front, (fx, fy))
    return img


# --- 'layers' --------------------------------------------------------------

# Font Awesome Free 6.7.2 "layer-group" (CC BY 4.0, https://fontawesome.com)
LAYER_GROUP = ('M264.5 5.2c14.9-6.9 32.1-6.9 47 0l218.6 101c8.5 3.9 13.9 12.4 13.9 21.8s-5.4 17.9-13.9 21.8l-218.6 101'
               'c-14.9 6.9-32.1 6.9-47 0L45.9 149.8C37.4 145.8 32 137.3 32 128s5.4-17.9 13.9-21.8L264.5 5.2zM476.9 209.6'
               'l53.2 24.6c8.5 3.9 13.9 12.4 13.9 21.8s-5.4 17.9-13.9 21.8l-218.6 101c-14.9 6.9-32.1 6.9-47 0L45.9 277.8'
               'C37.4 273.8 32 265.3 32 256s5.4-17.9 13.9-21.8l53.2-24.6 152 70.2c23.4 10.8 50.4 10.8 73.8 0l152-70.2z'
               'm-152 198.2l152-70.2 53.2 24.6c8.5 3.9 13.9 12.4 13.9 21.8s-5.4 17.9-13.9 21.8l-218.6 101c-14.9 6.9-32.1 6.9'
               '-47 0L45.9 405.8C37.4 401.8 32 393.3 32 384s5.4-17.9 13.9-21.8l53.2-24.6 152 70.2c23.4 10.8 50.4 10.8 73.8 0z')


def layers_icon():
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">'
           f'<rect x="32" y="32" width="960" height="960" rx="210" fill="#2f6fde"/>'
           f'<g transform="translate(512 528) scale(1.05) translate(-288 -256)"><path fill="#ffffff" d="{LAYER_GROUP}"/></g></svg>')
    page = pymupdf.open(stream=svg.encode(), filetype='svg')[0]
    pix = page.get_pixmap(alpha=True, matrix=pymupdf.Matrix(N / page.rect.width, N / page.rect.width))
    return Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGBA')


# --- shared ----------------------------------------------------------------

def splash(icon, icon_pt):
    """The start-up card, drawn at 2x (sharp on 200% screens). Windows splash transparency is
    a colour key, so the rounded corners are cut with all-or-nothing alpha."""
    S, SS = 2, 4
    W, H, R = 300 * S, 110 * S, 12 * S
    bg, border = (246, 247, 249), (222, 225, 230)
    big = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, W * SS - 1, H * SS - 1], radius=R * SS, fill=border + (255,))
    b = S * SS
    d.rounded_rectangle([b, b, W * SS - 1 - b, H * SS - 1 - b], radius=R * SS - b, fill=bg + (255,))
    card = big.resize((W, H), Image.LANCZOS)
    rgb = Image.new('RGB', (W, H), border)
    rgb.paste(card.convert('RGB'), mask=card.getchannel('A'))
    side = icon_pt * S
    ic = icon.resize((side, side), Image.LANCZOS)
    rgb.paste(ic, (26 * S + (48 - icon_pt) * S // 2, (H - side) // 2), ic)
    d = ImageDraw.Draw(rgb)
    fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    d.text((90 * S, H // 2 - 3 * S), 'SlidePrint', font=ImageFont.truetype(os.path.join(fonts, 'seguisb.ttf'), 21 * S),
           fill='#1b1d21', anchor='ls')
    d.text((90 * S, H // 2 + 7 * S), 'Starting\u2026', font=ImageFont.truetype(os.path.join(fonts, 'segoeui.ttf'), 13 * S),
           fill='#6b7280', anchor='lt')
    out = rgb.convert('RGBA')
    out.putalpha(card.getchannel('A').point(lambda a: 255 if a >= 128 else 0))
    return out


SETS = {                                   # name: (drawing, icon size on the splash in pt)
    'cards': (cards_icon, 56),
    'layers': (layers_icon, 48),
}


def build(name):
    draw, splash_pt = SETS[name]
    icon = draw()
    folder = os.path.join(HERE, name)
    os.makedirs(folder, exist_ok=True)
    icon.resize((256, 256), Image.LANCZOS).save(os.path.join(folder, 'icon.ico'), sizes=ICO_SIZES)
    icon.resize((132, 132), Image.LANCZOS).save(os.path.join(folder, 'logo.png'), optimize=True)   # 44 pt at 3x
    splash(icon, splash_pt).save(os.path.join(folder, 'splash.png'), optimize=True)
    print('wrote', folder)


if __name__ == '__main__':
    for name in sys.argv[1:] or SETS:
        build(name)
