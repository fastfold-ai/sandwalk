from agent_server.title import (
    MIN_MESSAGES_FOR_LLM_TITLE,
    TitleResult,
    build_title_prompt,
    fallback_title_from_query,
    is_placeholder_title,
    sanitize_generated_title,
    should_attempt_llm_title,
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


def test_build_title_prompt_includes_recent_exchange():
    prompt = build_title_prompt(
        [
            {"role": "system", "content": "ignore"},
            {"role": "user", "content": "Fold 4KW4"},
            {"role": "assistant", "content": "Sure, folding now."},
            {"role": "user", "content": "Also design a binder"},
            {"role": "assistant", "content": "Designing binder next."},
        ]
    )
    assert "User: Fold 4KW4" in prompt
    assert "Assistant: Sure, folding now." in prompt
    assert "User: Also design a binder" in prompt
    assert "Assistant: Designing binder next." in prompt


def test_should_attempt_llm_title_waits_for_four_messages():
    short = [
        {"role": "user", "content": "Fold TP53"},
        {"role": "assistant", "content": "Folding."},
    ]
    assert not should_attempt_llm_title(short)
    assert should_attempt_llm_title(short, force=True)
    assert MIN_MESSAGES_FOR_LLM_TITLE == 4

    long = short + [
        {"role": "user", "content": "Show confidence"},
        {"role": "assistant", "content": "High confidence."},
    ]
    assert should_attempt_llm_title(long)


def test_title_result_marks_final():
    assert TitleResult(title="Fold TP53", final=True).final
    assert not TitleResult(title="Fold TP53", final=False).final
