from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "using-apps-like-a-user" / "scripts"))

import _effects as fx  # noqa: E402
from _effects import Signals  # noqa: E402

PNG_DIR = ROOT / "tests" / "fixtures" / "using-apps-like-a-user" / "png"

RGB_PIXELS = [
    [(7, 104, 201), (60, 157, 254), (113, 210, 51), (166, 7, 104)],
    [(38, 135, 232), (91, 188, 29), (144, 241, 82), (197, 38, 135)],
    [(69, 166, 7), (122, 219, 60), (175, 16, 113), (228, 69, 166)],
    [(100, 197, 38), (153, 250, 91), (206, 47, 144), (3, 100, 197)],
    [(131, 228, 69), (184, 25, 122), (237, 78, 175), (34, 131, 228)],
]
GRAY_PIXELS = [
    [14, 67, 120, 173],
    [45, 98, 151, 204],
    [76, 129, 182, 235],
    [107, 160, 213, 10],
    [138, 191, 244, 41],
]
GRAYA_GRAY = [
    [21, 74, 127, 180],
    [52, 105, 158, 211],
    [83, 136, 189, 242],
    [114, 167, 220, 17],
    [145, 198, 251, 48],
]
RGBA_RGB = [
    [(28, 125, 222), (81, 178, 19), (134, 231, 72), (187, 28, 125)],
    [(59, 156, 253), (112, 209, 50), (165, 6, 103), (218, 59, 156)],
    [(90, 187, 28), (143, 240, 81), (196, 37, 134), (249, 90, 187)],
    [(121, 218, 59), (174, 15, 112), (227, 68, 165), (24, 121, 218)],
    [(152, 249, 90), (205, 46, 143), (2, 99, 196), (55, 152, 249)],
]
PALETTE = [(10, 20, 30), (200, 100, 50), (0, 255, 128), (255, 255, 255)]
PALETTE_PIXELS = [[PALETTE[(x + y) % 4] for x in range(4)] for y in range(5)]


def rows_to_pixels(rows):
    return [[tuple(r[i:i + 3]) for i in range(0, len(r), 3)] for r in rows]


def gray_rows(pixels):
    return [[p[0] for p in r] for r in rows_to_pixels(pixels)]


def filter_types(path: Path):
    data = path.read_bytes()
    pos, idat = 8, b""
    width = height = bpp = None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            width, height, _, ctype = struct.unpack(">IIBB", body[:10])
            bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
        if kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = 1 + width * bpp
    return [raw[y * stride] for y in range(height)]


def make_png(width, height, ctype, bit_depth, interlace, raw):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, ctype, 0, 0, interlace))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(
    "name,expected_filter",
    [("none", 0), ("sub", 1), ("up", 2), ("average", 3), ("paeth", 4)],
)
def test_rgb_decodes_for_every_filter_type(name, expected_filter):
    path = PNG_DIR / f"rgb_{name}.png"
    assert set(filter_types(path)) == {expected_filter}
    w, h, rows = fx.decode_png(path.read_bytes())
    assert (w, h) == (4, 5)
    assert rows_to_pixels(rows) == RGB_PIXELS


def test_mixed_filter_rows_decode():
    path = PNG_DIR / "rgb_mixed.png"
    assert filter_types(path) == [0, 1, 2, 3, 4]
    _, _, rows = fx.decode_png(path.read_bytes())
    assert rows_to_pixels(rows) == RGB_PIXELS


@pytest.mark.parametrize("name", ["gray_paeth", "gray_sub"])
def test_gray_expands_to_rgb(name):
    _, _, rows = fx.decode_png((PNG_DIR / f"{name}.png").read_bytes())
    expected = [[(v, v, v) for v in r] for r in GRAY_PIXELS]
    assert rows_to_pixels(rows) == expected


def test_gray_alpha_drops_alpha():
    path = PNG_DIR / "graya_average.png"
    assert set(filter_types(path)) == {3}
    _, _, rows = fx.decode_png(path.read_bytes())
    assert rows_to_pixels(rows) == [[(v, v, v) for v in r] for r in GRAYA_GRAY]


def test_rgba_drops_alpha():
    path = PNG_DIR / "rgba_up.png"
    assert set(filter_types(path)) == {2}
    _, _, rows = fx.decode_png(path.read_bytes())
    assert rows_to_pixels(rows) == RGBA_RGB


def test_palette_resolves_through_plte():
    path = PNG_DIR / "palette_sub.png"
    assert set(filter_types(path)) == {1}
    _, _, rows = fx.decode_png(path.read_bytes())
    assert rows_to_pixels(rows) == PALETTE_PIXELS


def test_rows_are_bytes_of_width_times_three():
    _, _, rows = fx.decode_png((PNG_DIR / "rgb_none.png").read_bytes())
    assert len(rows) == 5
    assert all(isinstance(r, bytes) and len(r) == 12 for r in rows)


def test_interlaced_png_is_rejected():
    data = make_png(1, 1, 2, 8, 1, b"\x00\x01\x02\x03")
    with pytest.raises(ValueError, match="interlaced"):
        fx.decode_png(data)


def test_sixteen_bit_png_is_rejected():
    data = make_png(1, 1, 2, 16, 0, b"\x00" + bytes(6))
    with pytest.raises(ValueError, match="16-bit"):
        fx.decode_png(data)


def test_non_png_is_rejected():
    with pytest.raises(ValueError):
        fx.decode_png(b"not a png at all")


def test_hamming_counts_differing_bits():
    assert fx.hamming(0, 0) == 0
    assert fx.hamming(0b1010, 0b0110) == 2
    assert fx.hamming(0, (1 << 64) - 1) == 64


def test_identical_images_hash_to_distance_zero():
    a = fx.average_hash(PNG_DIR / "gradient.png")
    b = fx.average_hash(PNG_DIR / "gradient.png")
    assert fx.hamming(a, b) == 0
    assert 0 <= a < (1 << 64)


def test_inverted_image_is_far_away():
    a = fx.average_hash(PNG_DIR / "gradient.png")
    b = fx.average_hash(PNG_DIR / "gradient_inverted.png")
    assert fx.hamming(a, b) >= 56
    assert fx.hamming(a, b) > fx.SCREEN_HASH_THRESHOLD


def test_hash_sets_bit_only_for_cells_above_the_mean(tmp_path):
    left_dark = make_png(8, 8, 0, 8, 0, b"".join(b"\x00" + bytes([0] * 4 + [255] * 4) for _ in range(8)))
    p = tmp_path / "half.png"
    p.write_bytes(left_dark)
    h = fx.average_hash(p)
    assert bin(h).count("1") == 32
    for row in range(8):
        bits = (h >> (56 - 8 * row)) & 0xFF
        assert bits == 0b00001111


def test_hash_handles_images_smaller_than_eight_pixels():
    h = fx.average_hash(PNG_DIR / "rgb_none.png")
    assert 0 <= h < (1 << 64)


def test_flat_image_has_no_bits_above_the_mean(tmp_path):
    p = tmp_path / "flat.png"
    p.write_bytes(make_png(8, 8, 0, 8, 0, b"".join(b"\x00" + bytes([77] * 8) for _ in range(8))))
    assert fx.average_hash(p) == 0


def test_threshold_is_provisional_six():
    assert fx.SCREEN_HASH_THRESHOLD == 6
    assert fx.SETTLE_POLL_S == 0.25
    assert fx.SETTLE_CAP_S == 2.0
    assert fx.SIGNALS == ("url", "title", "tree", "focus", "value", "screen")


NORMALIZE_CASES = [
    ('- button "Save" [ref=e12]', '- button "Save"'),
    ('- textbox "Email" [active] [ref=e3]: me@example.com', '- textbox "Email": me@example.com'),
    ('- link "Home" [ref=e1] [cursor=pointer]', '- link "Home" [cursor=pointer]'),
    ('[12] button "Save"', 'button "Save"'),
    ('  [7] textbox "Name" value="Ada"', 'textbox "Name" value="Ada"'),
    ('#12 button "Save"', 'button "Save"'),
    ('    #305 AXTextField "Search" value=cats', 'AXTextField "Search" value=cats'),
    ('- heading   "Welcome"\t\t[level=1]', '- heading "Welcome" [level=1]'),
    ('- checkbox "Remember me" [checked] [ref=e9]', '- checkbox "Remember me" [checked]'),
    ('- button "Item [3]" [ref=e4]', '- button "Item [3]"'),
    ('- text "Order #42 shipped"', '- text "Order #42 shipped"'),
]


@pytest.mark.parametrize("raw,expected", NORMALIZE_CASES)
def test_normalize_tree_cases(raw, expected):
    assert fx.normalize_tree(raw).strip() == expected.strip()


def test_normalize_tree_preserves_indentation_depth_and_line_structure():
    raw = '- list [ref=e1]:\n  - listitem [ref=e2]:\n    - link "A" [ref=e3]\n'
    out = fx.normalize_tree(raw)
    assert out.splitlines() == ['- list:', '  - listitem:', '    - link "A"']


def test_normalize_tree_is_stable_across_ref_renumbering():
    a = '- button "Save" [ref=e5]\n- textbox "Name" [active] [ref=e6]: Ada'
    b = '- button "Save" [ref=e50]\n- textbox "Name" [ref=e60]: Ada'
    assert fx.normalize_tree(a) == fx.normalize_tree(b)


def test_normalize_tree_is_idempotent():
    for raw, _ in NORMALIZE_CASES:
        once = fx.normalize_tree(raw)
        assert fx.normalize_tree(once) == once


def test_normalize_tree_keeps_changed_values_visible():
    a = fx.normalize_tree('- textbox "Name" [ref=e1]: Ada')
    b = fx.normalize_tree('- textbox "Name" [ref=e1]: Grace')
    assert a != b


def sig(**kw):
    return Signals(**kw)


def test_signals_default_to_none():
    s = Signals()
    assert (s.url, s.title, s.tree, s.focus, s.value, s.screen_hash) == (None,) * 6


def test_diff_names_changed_signals_in_signals_order():
    before = sig(url="a", title="t", tree="x", focus="f", value="v")
    after = sig(url="b", title="t2", tree="y", focus="g", value="w")
    assert fx.diff(before, after) == ["url", "title", "tree", "focus", "value"]


def test_diff_is_empty_when_nothing_changed():
    s = sig(url="a", title="t", tree="x", focus="f", value="v", screen_hash=5)
    assert fx.diff(s, s) == []


def test_diff_treats_none_to_value_as_a_change():
    assert fx.diff(sig(value=None), sig(value="x")) == ["value"]
    assert fx.diff(sig(value=None), sig(value=None)) == []


def test_screen_compares_only_when_both_hashes_exist():
    assert fx.diff(sig(screen_hash=None), sig(screen_hash=(1 << 64) - 1)) == []
    assert fx.diff(sig(screen_hash=0), sig(screen_hash=None)) == []
    assert fx.diff(sig(screen_hash=0), sig(screen_hash=(1 << 64) - 1)) == ["screen"]


def test_screen_distance_must_exceed_threshold():
    at = (1 << fx.SCREEN_HASH_THRESHOLD) - 1
    over = (1 << (fx.SCREEN_HASH_THRESHOLD + 1)) - 1
    assert fx.diff(sig(screen_hash=0), sig(screen_hash=at)) == []
    assert fx.diff(sig(screen_hash=0), sig(screen_hash=over)) == ["screen"]
    assert fx.diff(sig(screen_hash=0), sig(screen_hash=at), threshold=2) == ["screen"]


def test_classify_unsettled_wins_over_any_change():
    before, after = sig(url="a"), sig(url="b")
    status, signals, other = fx.classify(before, after, "any", settled=False)
    assert status == "UNSETTLED"
    assert signals == ["url"]


def test_classify_unsettled_with_nothing_changed():
    s = sig(url="a")
    assert fx.classify(s, s, "any", settled=False)[0] == "UNSETTLED"


def test_classify_any_observed_when_diff_non_empty():
    status, signals, other = fx.classify(sig(tree="a"), sig(tree="b"), "any", settled=True)
    assert (status, signals, other) == ("OBSERVED", ["tree"], [])


def test_classify_any_no_effect_when_diff_empty():
    s = sig(url="a", tree="a")
    assert fx.classify(s, s, "any", settled=True) == ("NO_EFFECT", [], [])


def test_classify_named_expect_observed_when_that_signal_changed():
    before = sig(url="a", title="t", tree="x")
    after = sig(url="b", title="t", tree="y")
    status, signals, other = fx.classify(before, after, "url", settled=True)
    assert status == "OBSERVED"
    assert signals == ["url", "tree"]
    assert other == ["tree"]


def test_classify_named_expect_unchanged_is_no_effect_with_other_changes():
    before = sig(url="a", title="t", tree="x", focus="f")
    after = sig(url="a", title="t", tree="y", focus="g")
    status, signals, other = fx.classify(before, after, "title", settled=True)
    assert status == "NO_EFFECT"
    assert signals == ["tree", "focus"]
    assert other == ["tree", "focus"]


def test_classify_named_expect_nothing_changed_is_plain_no_effect():
    s = sig(url="a")
    assert fx.classify(s, s, "value", settled=True) == ("NO_EFFECT", [], [])


def test_classify_screen_expect_needs_both_hashes():
    before, after = sig(screen_hash=0), sig(screen_hash=None)
    assert fx.classify(before, after, "screen", settled=True)[0] == "NO_EFFECT"
    after = sig(screen_hash=(1 << 64) - 1)
    assert fx.classify(before, after, "screen", settled=True) == ("OBSERVED", ["screen"], [])


def test_classify_rejects_an_unknown_expect():
    with pytest.raises(ValueError):
        fx.classify(sig(), sig(), "bogus", settled=True)


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def scripted(reads):
    it = iter(reads)
    calls = []

    def read():
        calls.append(1)
        return next(it)

    return read, calls


def test_settle_returns_true_on_two_equal_consecutive_reads():
    t = FakeTime()
    a, b = sig(url="u", tree="t1", focus="f"), sig(url="u", tree="t2", focus="f")
    read, calls = scripted([a, b, b])
    settled, last = fx.settle(read, sleep=t.sleep, clock=t.clock)
    assert settled is True
    assert last == b
    assert len(calls) == 3
    assert t.sleeps == [0.25, 0.25]


def test_settle_with_already_stable_page_reads_twice():
    t = FakeTime()
    s = sig(url="u", tree="t", focus="f")
    read, calls = scripted([s, s])
    assert fx.settle(read, sleep=t.sleep, clock=t.clock) == (True, s)
    assert len(calls) == 2


def test_settle_ignores_value_and_screen_when_comparing():
    t = FakeTime()
    a = sig(url="u", tree="t", focus="f", value="1", screen_hash=0)
    b = sig(url="u", tree="t", focus="f", value="2", screen_hash=(1 << 64) - 1)
    read, _ = scripted([a, b])
    settled, last = fx.settle(read, sleep=t.sleep, clock=t.clock)
    assert settled is True
    assert last == b


def test_settle_times_out_on_a_read_that_changes_every_call():
    t = FakeTime()
    counter = {"n": 0}

    def read():
        counter["n"] += 1
        return sig(url="u", tree="tick %d" % counter["n"], focus="f")

    settled, last = fx.settle(read, poll_s=0.25, cap_s=2.0, sleep=t.sleep, clock=t.clock)
    assert settled is False
    assert last.tree == "tick %d" % counter["n"]
    assert t.now >= 2.0
    assert t.now <= 2.25
    assert counter["n"] <= 10


def test_settle_with_zero_cap_returns_after_the_first_read():
    t = FakeTime()
    read, calls = scripted([sig(tree="a"), sig(tree="a")])
    settled, last = fx.settle(read, cap_s=0.0, sleep=t.sleep, clock=t.clock)
    assert settled is False
    assert len(calls) == 1


def test_settle_tree_change_between_reads_blocks_settling():
    t = FakeTime()
    reads = [sig(tree="a"), sig(tree="b"), sig(tree="c"), sig(tree="c")]
    read, _ = scripted(reads)
    settled, last = fx.settle(read, sleep=t.sleep, clock=t.clock)
    assert (settled, last.tree) == (True, "c")
