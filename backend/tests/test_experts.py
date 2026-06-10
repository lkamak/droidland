from app.experts import (
    get_expert,
    list_experts,
    load_experts_from_dir,
    parse_expert_markdown,
    sync_experts,
)
from tests.conftest import EXPERTS_DIR

SAMPLE = """---
name: Sample Expert
description: does things
model: claude-sonnet-4-5-20250929
autonomy: medium
interaction_mode: auto
skills: [Read, Grep]
integrations: [github]
run_in_worktree: true
---

You are the Sample expert. Do the task.
"""


def test_parse_frontmatter():
    expert = parse_expert_markdown(SAMPLE, "sample", "sample.md")
    assert expert.slug == "sample"
    assert expert.name == "Sample Expert"
    assert expert.autonomy == "medium"
    assert expert.skills == ["Read", "Grep"]
    assert expert.run_in_worktree is True
    assert expert.prompt.startswith("You are the Sample expert")


def test_parse_invalid_autonomy_defaults_off():
    text = "---\nname: X\nautonomy: bogus\n---\nbody"
    expert = parse_expert_markdown(text, "x")
    assert expert.autonomy == "off"


def test_parse_no_frontmatter():
    expert = parse_expert_markdown("just a prompt", "p")
    assert expert.name == "p"
    assert expert.prompt == "just a prompt"


def test_prebuilt_library_loads():
    experts = load_experts_from_dir(EXPERTS_DIR)
    slugs = {e.slug for e in experts}
    assert {"code-reviewer", "implementor", "e2e-verifier"}.issubset(slugs)


def test_sync_and_get(db):
    count = sync_experts(db, EXPERTS_DIR)
    assert count >= 5
    assert len(list_experts(db)) == count
    reviewer = get_expert(db, "code-reviewer")
    assert reviewer is not None
    assert "github" in reviewer.integrations
