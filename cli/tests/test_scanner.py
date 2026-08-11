"""Unit tests for the busy toolbar scanner."""

from ui.status.scanner import scanner_cells, scanner_frame_count, scanner_html


def test_scanner_frame_count():
    assert scanner_frame_count(width=10, hold_end=4, hold_start=6) == 29


def test_scanner_has_bright_head_and_inactive():
    cells = scanner_cells(0, width=10)
    assert len(cells) == 10
    # Frame 0: head at index 0
    assert cells[0][1] == "■"
    assert cells[0][0] == "#c8ffd8"
    assert any(ch == "⬝" for _, ch in cells)


def test_scanner_moves_forward():
    cells = scanner_cells(3, width=10)
    assert cells[3][1] == "■"
    assert cells[3][0] == "#c8ffd8"


def test_scanner_html_contains_styles():
    html = scanner_html(2, width=8)
    assert 'fg="#c8ffd8"' in html
    assert "■" in html
    assert "⬝" in html


def test_scanner_gold_palette_matches_compose_accent():
    cells = scanner_cells(0, width=10, palette="gold")
    assert cells[0][0] == "#f0e0a0"
    html = scanner_html(0, width=8, palette="gold")
    assert "#c9a227" in html or "#f0e0a0" in html
