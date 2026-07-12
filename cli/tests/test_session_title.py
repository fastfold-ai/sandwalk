from agent_server.title import (
    build_title_prompt,
    fallback_title_from_query,
    is_placeholder_title,
    sanitize_generated_title,
)


def test_sanitize_strips_quotes_and_whitespace():
    assert sanitize_generated_title('  "TP53 Analysis"  ') == "TP53 Analysis"
    assert sanitize_generated_title("‘Fold Boltz’") == "Fold Boltz"


def test_placeholder_titles():
    assert is_placeholder_title("Untitled session")
    assert is_placeholder_title("New research session")
    assert is_placeholder_title("")
    assert not is_placeholder_title("Analyze TP53")


def test_fallback_title_truncates():
    long_query = "word " * 30
    title = fallback_title_from_query(long_query)
    assert len(title) <= 64
    assert title.endswith("...")


def test_build_title_prompt_uses_first_exchange():
    prompt = build_title_prompt(
        [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "Fold 4KW4"},
            {"role": "assistant", "content": "Sure, folding now."},
            {"role": "user", "content": "Also design a binder"},
        ]
    )
    assert prompt == "User: Fold 4KW4\nAssistant: Sure, folding now."
