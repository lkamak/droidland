from pathlib import Path

from app.experts import expert_to_markdown, parse_expert_markdown
from app.models import Expert


def test_markdown_round_trip():
    expert = Expert(
        slug="my-expert",
        name="My Expert",
        description="does things",
        model="claude-sonnet-4-5-20250929",
        autonomy="medium",
        interaction_mode="auto",
        skills=["Read", "Grep"],
        integrations=["github"],
        run_in_worktree=True,
        prompt="You are My Expert. Do the work.",
    )
    text = expert_to_markdown(expert)
    parsed = parse_expert_markdown(text, "my-expert")
    assert parsed.name == expert.name
    assert parsed.autonomy == "medium"
    assert parsed.skills == ["Read", "Grep"]
    assert parsed.integrations == ["github"]
    assert parsed.run_in_worktree is True
    assert parsed.prompt == "You are My Expert. Do the work."


def test_create_writes_file_and_db(app_client, settings):
    resp = app_client.post("/api/experts", json={
        "slug": "doc-writer",
        "name": "Doc Writer",
        "description": "writes docs",
        "autonomy": "low",
        "interaction_mode": "auto",
        "skills": ["Read"],
        "integrations": [],
        "prompt": "You write docs.",
    })
    assert resp.status_code == 200
    assert resp.json()["slug"] == "doc-writer"

    # File written into the (temp) experts dir
    assert (Path(settings.experts_dir) / "doc-writer.md").exists()
    # And visible via the API
    slugs = {e["slug"] for e in app_client.get("/api/experts").json()}
    assert "doc-writer" in slugs


def test_create_duplicate_conflict(app_client):
    assert app_client.post("/api/experts", json={
        "slug": "code-reviewer", "name": "dup", "prompt": "x",
    }).status_code == 409


def test_create_invalid_slug(app_client):
    assert app_client.post("/api/experts", json={
        "slug": "Bad Slug", "name": "x", "prompt": "y",
    }).status_code == 400


def test_create_invalid_autonomy(app_client):
    assert app_client.post("/api/experts", json={
        "slug": "x", "name": "x", "autonomy": "ultra", "prompt": "y",
    }).status_code == 400


def test_update_changes_fields(app_client, settings):
    app_client.post("/api/experts", json={"slug": "tmp", "name": "Tmp", "prompt": "a"})
    resp = app_client.put("/api/experts/tmp", json={
        "name": "Tmp Renamed", "autonomy": "high", "prompt": "b", "interaction_mode": "auto",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Tmp Renamed"
    assert resp.json()["autonomy"] == "high"
    text = (Path(settings.experts_dir) / "tmp.md").read_text()
    assert "Tmp Renamed" in text


def test_update_missing_404(app_client):
    resp = app_client.put("/api/experts/ghost", json={"name": "x", "prompt": "y"})
    assert resp.status_code == 404


def test_delete_removes_file_and_db(app_client, settings):
    app_client.post("/api/experts", json={"slug": "throwaway", "name": "T", "prompt": "p"})
    assert (Path(settings.experts_dir) / "throwaway.md").exists()
    assert app_client.delete("/api/experts/throwaway").status_code == 200
    assert not (Path(settings.experts_dir) / "throwaway.md").exists()
    assert app_client.delete("/api/experts/throwaway").status_code == 404


def test_validate_reports_warnings(app_client):
    resp = app_client.post("/api/experts/validate", json={
        "slug": "ok-slug", "integrations": ["github"], "skills": [],
    })
    body = resp.json()
    assert body["ok"] is True
    assert any("integrations" in w for w in body["warnings"])
