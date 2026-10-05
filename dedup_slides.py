#!/usr/bin/env python3
r"""Collapse incremental-reveal pages of a slide PDF into a print-friendly PDF.

Slide decks exported to PDF (Beamer \pause / \uncover, PowerPoint / Keynote
builds, ...) have one page per reveal step. This keeps, for every run of
consecutive pages that build up the same slide, only the last (fullest) page.
The kept pages are copied as they are -- content streams, fonts and images
are not re-encoded or rasterised -- and bookmarks that pointed at a dropped
page are re-pointed to the kept page of its group.

Page A is dropped only if what is *visible* on it (content outside the page
box, where Beamer parks hidden overlay material, does not count) reappears on
the next page B: at least 95% of the words of A are words of B, and the title
band (top of the page) is unchanged.
Pages where content is replaced rather than added (Beamer \only) are kept.

  python dedup_slides.py talk.pdf                 -> talk_print.pdf + report
  python dedup_slides.py talk.pdf -o out.pdf --report groups.json
  python dedup_slides.py talk.pdf --dry-run       report only

Requires PyMuPDF (pip install pymupdf).

Copyright (C) 2026 Jince Chen
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import argparse, json, os, sys
from collections import Counter

import pymupdf

TITLE_BAND = 0.15       # top fraction of the page that holds the slide title


def visible(r, page_rect):
    """r overlaps the page box (degenerate rects -- straight lines -- included)."""
    return r.x0 <= page_rect.x1 and r.x1 >= page_rect.x0 and r.y0 <= page_rect.y1 and r.y1 >= page_rect.y0


def page_features(page):
    pr = page.rect
    words = [w for w in page.get_text('words') if visible(pymupdf.Rect(w[:4]), pr)]
    title = ' '.join(w[4] for w in words if w[3] <= pr.y0 + TITLE_BAND * pr.height)
    return {'words': Counter(w[4] for w in words), 'title': title}


def containment(a, b):
    """Share of multiset a that is also in b (1.0 for empty a)."""
    n = sum(a.values())
    return sum((a & b).values()) / n if n else 1.0


def same_slide(fa, fb, threshold):
    """Is a page (features fa) an earlier reveal state of the next page (fb)? -> (bool, why, scores)"""
    text = containment(fa['words'], fb['words'])
    s = {'text': round(text, 3),
         'words_missing': sum(fa['words'].values()) - sum((fa['words'] & fb['words']).values())}
    if text < threshold:
        return False, f"text replaced (text⊆ {text:.2f}, {s['words_missing']} words gone)", s
    if fa['title'] and fb['title'] and fa['title'] != fb['title']:
        return False, 'title changed', s
    return True, 'reveal (text)', s


def group_pages(doc, threshold=0.95):
    """Runs of consecutive pages that build up one slide. Returns a list of dicts
    {'pages': [0-based...], 'keep': index, 'links': [scores per merge], 'next': why the run ended}."""
    if len(doc) == 0:
        return []
    feats = [page_features(p) for p in doc]
    groups = [{'pages': [0], 'links': []}]
    for i in range(len(doc) - 1):
        ok, why, s = same_slide(feats[i], feats[i + 1], threshold)
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
    ap.add_argument('--dry-run', action='store_true', help='print the grouping, write no PDF')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    doc = pymupdf.open(args.pdf)
    n_pages = len(doc)
    groups = group_pages(doc, args.threshold)
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
