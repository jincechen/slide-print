"""Smoke test on a generated deck (python test_dedup_slides.py, or pytest)."""
import os, tempfile

import pymupdf
import dedup_slides as ds


def _image(rgb):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40), False)
    pix.set_rect(pix.irect, rgb)
    return pix.tobytes('png')


def make_deck():
    red, blue = _image((200, 30, 30)), _image((30, 30, 200))
    doc = pymupdf.open()

    def page(lines, image=None, title='Results', dy=0):
        p = doc.new_page(width=480, height=270)
        p.insert_text((20, 30), title, fontsize=18)
        for k, line in enumerate(lines):
            p.insert_text((20, 70 + dy + 18 * k), line, fontsize=12)
        p.draw_rect(pymupdf.Rect(20, 200 + dy, 120, 230 + dy), color=(0, 0, 0))
        if image:
            p.insert_image(pymupdf.Rect(300, 80, 420, 160), stream=image)

    page(['First point'])                                   # 1  build of 2
    page(['First point'], red)                              # 2  image appears
    page(['First point'], blue)                             # 3  image swapped: keep 2 and 3
    page(['First point', 'Second point'], blue, dy=-10)     # 4  build of 3, layout moved up
    page(['Other text'], blue, title='Other')               # 5  new slide, image reused
    page(['Gone', 'Kept'], title='Swap')                    # 6  text replaced: keep 6 and 7
    page(['Kept', 'New'], title='Swap')                     # 7
    doc.set_toc([[1, 'Results', 1], [1, 'Swap', 6]])
    return pymupdf.open('pdf', doc.tobytes())               # as if opened from a file


def test_grouping_and_output():
    doc = make_deck()
    groups, labels = ds.group_pages(doc)
    assert labels is None
    assert [[p + 1 for p in g['pages']] for g in groups] == [[1, 2], [3, 4], [5], [6], [7]]
    src = make_deck()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'out.pdf')
        ds.write_output(doc, groups, out)
        res = pymupdf.open(out)
        assert len(res) == 5
        for n, g in enumerate(groups):                       # kept pages copied unchanged
            assert res[n].read_contents() == src[g['keep']].read_contents()
        assert res.get_toc() == [[1, 'Results', 1], [1, 'Swap', 4]]
        res.close()


def test_restarting_page_labels_are_not_frames():
    doc = pymupdf.open()
    for _ in range(6):
        doc.new_page()
    doc.set_page_labels([{'startpage': 0, 'style': 'D', 'firstpagenum': 1},
                         {'startpage': 3, 'style': 'D', 'firstpagenum': 1}])      # 1 2 3 1 2 3
    assert ds.frame_labels(doc) is None


def _labelled_deck(raw_labels):
    """Pages 2-3 are one slide built up in two steps; raw_labels are PDF strings, e.g. '(2)'."""
    doc = pymupdf.open()
    for lines in (['Intro'], ['Point one'], ['Point one', 'Point two'], ['End']):
        p = doc.new_page(width=480, height=270)
        for k, line in enumerate(lines):
            p.insert_text((20, 70 + 18 * k), line, fontsize=12)
    nums = ' '.join(f'{n} <</P {raw}>>' for n, raw in enumerate(raw_labels))
    doc.xref_set_key(doc.pdf_catalog(), 'PageLabels', f'<</Nums [{nums}]>>')
    return pymupdf.open('pdf', doc.tobytes())


def _write(doc):
    groups, _ = ds.group_pages(doc)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'out.pdf')
        ds.write_output(doc, groups, out)
        res = pymupdf.open(out)
        labels = ds.page_labels(res)
        res.close()
    return labels


def test_frame_labels_group_pages():
    doc = _labelled_deck(['(1)', '(2)', '(2)', '(3)'])
    assert ds.frame_labels(doc) == ['1', '2', '2', '3']
    assert _write(doc) == ['1', '2', '3']


def test_other_labels_follow_their_pages():
    # not frame numbers (roman front matter): each kept page keeps its own label
    doc = _labelled_deck(['(i)', '(ii)', '(1)', '(2)'])
    assert _write(doc) == ['i', '1', '2']


if __name__ == '__main__':
    for name, f in list(globals().items()):
        if name.startswith('test_'):
            f()
    print('ok')
