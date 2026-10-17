"""Public skills.sh page parsing and the cached fetch."""

from __future__ import annotations

from agent_server.skills_service import page_meta

_HTML = """
<div>Summary</div>
<strong>Fold a protein</strong>
<ul><li>Uses Boltz</li><li>Writes a report</li></ul>
<span>SKILL.md</span>
<div>GitHub Stars</span></div><span>1.5K</span>
<div>First Seen</span></div><div class="date">Mar 2026</div>
"""


def test_parse_compact_count():
    assert page_meta.parse_compact_count("1.5K") == 1500
    assert page_meta.parse_compact_count("2M") == 2_000_000
    assert page_meta.parse_compact_count("3B") == 3_000_000_000
    assert page_meta.parse_compact_count("12") == 12
    assert page_meta.parse_compact_count("nope") is None
    assert page_meta.parse_compact_count("") is None


def test_parse_skills_page_pulls_summary_stars_and_date():
    parsed = page_meta.parse_skills_sh_page_meta(_HTML)
    assert parsed["summary"] == "**Fold a protein**\n\n- Uses Boltz\n- Writes a report"
    assert parsed["github_stars"] == 1500
    assert parsed["first_seen"] == "Mar 2026"
    assert page_meta.parse_skills_sh_page_meta("") == {
        "summary": None,
        "github_stars": None,
        "first_seen": None,
    }


def test_parse_summary_falls_back_to_plain_text():
    body = ">Summary</div>Just a sentence<span>SKILL.md</span>"
    parsed = page_meta.parse_skills_sh_page_meta(body)
    assert parsed["summary"] == "Just a sentence"


def test_fetch_uses_cache_and_survives_a_network_error(monkeypatch):
    page_meta._page_meta_cache.clear()
    calls = {"n": 0}

    class _Response:
        def read(self):
            return _HTML.encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=15):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Response()
        raise TimeoutError("down")

    monkeypatch.setattr(
        "agent_server.skills_service.urlopen",
        fake_urlopen,
    )
    first = page_meta.fetch_skills_sh_page_meta("Org", "fold")
    second = page_meta.fetch_skills_sh_page_meta("org", "fold")
    assert first["github_stars"] == 1500
    assert second == first
    assert calls["n"] == 1

    page_meta._page_meta_cache.clear()
    calls["n"] = 1
    missed = page_meta.fetch_skills_sh_page_meta("org", "fold")
    assert missed == {"summary": None, "github_stars": None, "first_seen": None}
    assert page_meta.fetch_skills_sh_page_meta("", "fold")["summary"] is None
