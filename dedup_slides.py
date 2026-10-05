#!/usr/bin/env python3
r"""Collapse incremental-reveal pages of a slide PDF into a print-friendly PDF.

Slide decks exported to PDF (Beamer \pause / \uncover, PowerPoint / Keynote
builds, ...) have one page per reveal step. This keeps, for every run of
consecutive pages that build up the same slide, only the last (fullest) page.
The kept pages are copied as they are -- content streams, fonts and images
are not re-encoded or rasterised -- and bookmarks that pointed at a dropped
page are re-pointed to the kept page of its group.

Grouping is lossless: page A is dropped only if what is *visible* on it
(content outside the page box, where Beamer parks hidden overlay material,
does not count) reappears on the next page B:
  * text: at least 95% of the words of A are words of B, and the title band
    (top of the page) is unchanged;
  * graphics: A's vector paths all reappear on B, compared by kind, colours
    and size but not position (frames re-centre vertically as content is
    added); only plain filled boxes may change size (a box growing around new
    content). A's raster images reappear on B (by content digest); if not, a
    low-resolution render decides whether A's ink is still on B, allowing for
    a vertical shift.
Pages where content is replaced rather than added (Beamer \only) are kept.

  python dedup_slides.py talk.pdf                 -> talk_print.pdf + report
  python dedup_slides.py talk.pdf -o out.pdf --report groups.json
  python dedup_slides.py talk.pdf --dry-run       report only
  python dedup_slides.py talk.pdf --visual check
        also render every merged pair and list those whose ink moved or changed
        (for eyeballing; does not change the grouping)

Requires PyMuPDF (pip install pymupdf).

Copyright (C) 2026 Jince Chen
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse, json, os, sys
from collections import Counter

import pymupdf

TITLE_BAND = 0.15       # top fraction of the page that holds the slide title
IMAGES_MIN = 0.9        # share of A's raster images (by digest) that must reappear on B
BOX_SLACK = 0.1         # filled boxes of A allowed to be missing from B (resized): 1 + this share of A's paths
RENDER_DPI = 40
MAX_SHIFT = 0.35        # vertical shift (share of page height) tried by the render check
INK_MATCH = 0.97        # share of A's ink pixels that must be unchanged on B
PIXEL_TOL = 40          # grey-level difference still counted as unchanged


def visible(r, page_rect):
    """r overlaps the page box (degenerate rects -- straight lines -- included)."""
    return r.x0 <= page_rect.x1 and r.x1 >= page_rect.x0 and r.y0 <= page_rect.y1 and r.y1 >= page_rect.y0


def page_features(page):
    pr = page.rect
    words = [w for w in page.get_text('words') if visible(pymupdf.Rect(w[:4]), pr)]
    title = ' '.join(w[4] for w in words if w[3] <= pr.y0 + TITLE_BAND * pr.height)
    images = Counter(i['digest'] for i in page.get_image_info(hashes=True)
                     if visible(pymupdf.Rect(i['bbox']), pr))
    xobjs = Counter(x[0] for x in page.get_xobjects())      # reused form XObjects (reported only)
    shapes = Counter()
    for d in page.get_drawings():
        r = d['rect']
        if not visible(r, pr) or (d['type'] == 'f' and r.contains(pr)):   # skip page background
            continue
        shapes[_shape(d, r)] += 1
    return {'words': Counter(w[4] for w in words), 'title': title, 'images': images, 'xobjs': xobjs,
            'shapes': shapes}


def _shape(d, r):
    """A path's kind, colours and size, but not where it sits on the page (frames
    re-centre vertically as content is added)."""
    box = d['type'] == 'f' and all(item[0] == 're' for item in d['items'])  # plain background box
    return (d['type'], _col(d.get('fill')), _col(d.get('color')), round(r.width), round(r.height), box)


def _col(c):
    return tuple(round(v, 2) for v in c) if c else None


def containment(a, b):
    """Share of multiset a that is also in b (1.0 for empty a)."""
    n = sum(a.values())
    return sum((a & b).values()) / n if n else 1.0


def ink_containment(pa, pb):
    """Share of page A's ink pixels (those differing from A's background) found unchanged
    on page B, at the best vertical shift of B. -> (share, shift in pixels)"""
    def grey(p):
        pix = p.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY, alpha=False)
        return pix.samples, pix.width, pix.height
    a, w, h = grey(pa)
    b, wb, hb = grey(pb)
    if (w, h) != (wb, hb):
        return 0.0, 0
    bg = Counter(a).most_common(1)[0][0]
    ink = [k for k, x in enumerate(a) if abs(x - bg) > PIXEL_TOL]
    if not ink:
        return 1.0, 0
    best = (0.0, 0)
    for dy in sorted(range(-int(h * MAX_SHIFT), int(h * MAX_SHIFT) + 1), key=abs):
        off = dy * w
        same = sum(1 for k in ink if 0 <= k + off < len(b) and abs(a[k] - b[k + off]) <= PIXEL_TOL)
        best = max(best, (same / len(ink), dy))
        if best[0] >= 0.999:
            break
    return best


def same_slide(doc, i, fa, fb, threshold, visual):
    """Is page i (features fa) an earlier reveal state of page i+1 (fb)? -> (bool, why, scores)"""
    n_shapes = sum(fa['shapes'].values())
    gone = fa['shapes'] - fb['shapes']
    boxes_gone = sum(n for k, n in gone.items() if k[-1])
    text = containment(fa['words'], fb['words'])
    s = {'text': round(text, 3),
         'words_missing': sum(fa['words'].values()) - sum((fa['words'] & fb['words']).values()),
         'shapes_missing': sum(gone.values()), 'shapes': n_shapes,
         'images': round(containment(fa['images'], fb['images']), 3),
         'xobj_reuse': round(containment(fa['xobjs'], fb['xobjs']), 3)}
    if text < threshold:
        return False, f"text replaced (text⊆ {text:.2f}, {s['words_missing']} words gone)", s
    if fa['title'] and fb['title'] and fa['title'] != fb['title']:
        return False, 'title changed', s
    if s['shapes_missing'] > boxes_gone or boxes_gone > 1 + BOX_SLACK * n_shapes:
        return False, f"graphics replaced ({s['shapes_missing']}/{n_shapes} paths gone)", s
    if visual == 'check' or (s['images'] < IMAGES_MIN and visual != 'off'):
        s['ink'], s['ink_shift'] = ink_containment(doc[i], doc[i + 1])
        s['ink'] = round(s['ink'], 3)
    if s['images'] < IMAGES_MIN:
        if s.get('ink', 0) < INK_MATCH:
            return False, f"image replaced (images⊆ {s['images']:.2f}, ink⊆ {s.get('ink', '-')})", s
        return True, 'reveal (text + render)', s
    return True, 'reveal (text + objects)', s


def group_pages(doc, threshold=0.95, visual='fallback'):
    """Runs of consecutive pages that build up one slide. Returns a list of dicts
    {'pages': [0-based...], 'keep': index, 'links': [scores per merge], 'next': why the run ended}."""
    if len(doc) == 0:
        return []
    feats = [page_features(p) for p in doc]
    groups = [{'pages': [0], 'links': []}]
    for i in range(len(doc) - 1):
        ok, why, s = same_slide(doc, i, feats[i], feats[i + 1], threshold, visual)
        if ok:
            groups[-1]['pages'].append(i + 1)
            groups[-1]['links'].append(s)
        else:
            groups[-1]['next'] = (why, s)
            groups.append({'pages': [i + 1], 'links': []})
    for g in groups:
        g['keep'] = g['pages'][-1]
    return groups


def write_output(doc, groups, out):
    kept = [g['keep'] for g in groups]
    new_no = {}                                              # old page -> new page (both 1-based)
    for n, g in enumerate(groups, 1):
        for p in g['pages']:
            new_no[p + 1] = n
    toc = [[lvl, title, new_no.get(page, -1)] for lvl, title, page in doc.get_toc()]
    doc.select(kept)
    doc.set_toc(toc)
    doc.save(out, garbage=3, deflate=True)


def report(groups, n_pages):
    lines = []
    for g in groups:
        a, b = g['pages'][0] + 1, g['pages'][-1] + 1
        rng = f'{a}-{b}' if a != b else f'{a}'
        if len(g['pages']) > 1:
            t = min(s['text'] for s in g['links'])
            note = f'{len(g["pages"])} states, text⊆ {t:.2f}'
        else:
            note = ''
        lines.append(f'pages {rng:>7} -> keep {b:>3}  {note}'.rstrip())
    moved = [(g['pages'][k] + 1, s['ink']) for g in groups for k, s in enumerate(g['links'])
             if s.get('ink', 1) < INK_MATCH]
    if moved:
        lines.append(f'render check: in {len(moved)} merges the earlier page does not overlay the later one '
                     '(layout moved or figure redrawn; worth a look): '
                     + ', '.join(f'{p}->{p + 1} (ink⊆ {v:.3f})' for p, v in moved))
    kept = len(groups)
    lines.append(f'{n_pages} pages -> {kept} pages ({n_pages - kept} removed)')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('-o', '--output', help='output PDF (default: <input>_print.pdf)')
    ap.add_argument('--report', help='also write the grouping as JSON here')
    ap.add_argument('--threshold', type=float, default=0.95,
                    help="share of a page's words that must reappear on the next page (default 0.95)")
    ap.add_argument('--visual', choices=['fallback', 'check', 'off'], default='fallback',
                    help='rendered check: only when raster images differ (default); also report it for '
                         'every merge (check); never (off)')
    ap.add_argument('--dry-run', action='store_true', help='print the grouping, write no PDF')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    doc = pymupdf.open(args.pdf)
    n_pages = len(doc)
    groups = group_pages(doc, args.threshold, args.visual)
    if not groups:
        sys.exit(f'{args.pdf}: no pages')
    print(report(groups, n_pages))
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump([{'pages': [p + 1 for p in g['pages']], 'keep': g['keep'] + 1,
                        'merge_scores': g['links'], 'split_from_next': g.get('next', (None,))[0]} for g in groups],
                      f, indent=1, ensure_ascii=False)
    if not args.dry_run:
        out = args.output or os.path.splitext(args.pdf)[0] + '_print.pdf'
        write_output(doc, groups, out)
        print(f'wrote {out}')


if __name__ == '__main__':
    main()
