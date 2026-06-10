def test_health(app_client):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["factory_configured"] is True


def test_experts_listed_from_library(app_client):
    resp = app_client.get("/api/experts")
    assert resp.status_code == 200
    slugs = {e["slug"] for e in resp.json()}
    assert "code-reviewer" in slugs


def test_expert_detail_404(app_client):
    assert app_client.get("/api/experts/nope").status_code == 404


def test_create_trigger_rejects_unknown_expert(app_client):
    resp = app_client.post("/api/triggers", json={
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "ghost",
    })
    assert resp.status_code == 400


def test_trigger_create_and_test_fire(app_client):
    create = app_client.post("/api/triggers", json={
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
        "prompt_template": "Review {{external_ref}}",
    })
    assert create.status_code == 200
    tid = create.json()["id"]

    fire = app_client.post(f"/api/triggers/{tid}/test", json={
        "external_ref": "acme/widgets#10",
        "payload": {"action": "opened", "number": 10},
    })
    assert fire.status_code == 200
    activation = fire.json()
    assert activation["factory_session_id"] == "sess-1"

    # duplicate ref -> 409
    dup = app_client.post(f"/api/triggers/{tid}/test", json={"external_ref": "acme/widgets#10"})
    assert dup.status_code == 409

    activations = app_client.get("/api/activations").json()
    assert any(a["external_ref"] == "acme/widgets#10" for a in activations)


def test_manual_poll_endpoint(app_client):
    # No connectors configured in tests -> zero activations, but endpoint works.
    resp = app_client.post("/api/connectors/poll")
    assert resp.status_code == 200
    assert resp.json() == {"activations_fired": 0}


def test_default_triggers_seeded(app_client):
    triggers = app_client.get("/api/triggers").json()
    by_expert = {t["expert_slug"]: t for t in triggers}
    assert "code-reviewer" in by_expert
    assert "implementor" in by_expert
    assert by_expert["code-reviewer"]["source"] == "github"
    assert by_expert["implementor"]["source"] == "linear"


def test_delete_trigger(app_client):
    tid = app_client.post("/api/triggers", json={
        "source": "github", "event_type": "pull_request",
        "condition": {"action": "opened"}, "expert_slug": "code-reviewer",
    }).json()["id"]
    assert app_client.delete(f"/api/triggers/{tid}").status_code == 200
    assert app_client.delete(f"/api/triggers/{tid}").status_code == 404


def test_usage_endpoint(app_client, context):
    # Seed some session data
    context.db.execute(
        """
        INSERT INTO session_cache
            (factory_session_id, expert_slug, status, tokens_json, app_url, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "sess-1",
            "code-reviewer",
            "running",
            '{"inputTokens":100,"outputTokens":50,"totalCreditsUsed":0.15}',
            "http://example.com",
            "2026-06-10T12:00:00Z",
        ),
    )
    context.db.execute(
        """
        INSERT INTO session_cache
            (factory_session_id, expert_slug, status, tokens_json, app_url, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "sess-2",
            "implementor",
            "error",
            '{"inputTokens":200,"outputTokens":100,"totalCreditsUsed":0.25}',
            "http://example.com",
            "2026-06-10T12:00:00Z",
        ),
    )

    resp = app_client.get("/api/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_input_tokens"] == 300
    assert body["total_output_tokens"] == 150
    assert body["total_credits"] == 0.4
    assert body["total_sessions"] == 2
    assert body["active_sessions"] == 1
    assert body["errored_sessions"] == 1


def test_activations_filtering(app_client, context):
    # Create a trigger and some test activations
    tid = app_client.post("/api/triggers", json={
        "source": "github", "event_type": "pull_request",
        "condition": {}, "expert_slug": "code-reviewer",
    }).json()["id"]

    # Fire multiple activations
    app_client.post(f"/api/triggers/{tid}/test", json={"external_ref": "repo#1"})
    app_client.post(f"/api/triggers/{tid}/test", json={"external_ref": "repo#2"})

    # Create another trigger with a different expert
    tid2 = app_client.post("/api/triggers", json={
        "source": "linear", "event_type": "issue",
        "condition": {}, "expert_slug": "implementor",
    }).json()["id"]
    app_client.post(f"/api/triggers/{tid2}/test", json={"external_ref": "LIN-1"})

    # Test filtering by expert
    resp = app_client.get("/api/activations?expert=code-reviewer")
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) == 2
    assert all(a["expert_slug"] == "code-reviewer" for a in filtered)

    # Test filtering by source
    resp = app_client.get("/api/activations?source=linear")
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) == 1
    assert filtered[0]["source"] == "linear"

    # Test filtering by status
    resp = app_client.get("/api/activations?status=running")
    assert resp.status_code == 200
    filtered = resp.json()
    assert all(a["status"] == "running" for a in filtered)


def test_activation_rerun(app_client):
    # Create a trigger and fire it
    tid = app_client.post("/api/triggers", json={
        "source": "github", "event_type": "pull_request",
        "condition": {}, "expert_slug": "code-reviewer",
        "prompt_template": "Review {{external_ref}}",
    }).json()["id"]

    activation = app_client.post(f"/api/triggers/{tid}/test", json={
        "external_ref": "acme/widgets#5",
    }).json()
    activation_id = activation["id"]

    # Re-run the activation
    resp = app_client.post(f"/api/activations/{activation_id}/rerun")
    assert resp.status_code == 200
    rerun = resp.json()
    assert rerun["expert_slug"] == "code-reviewer"
    assert "rerun" in rerun["external_ref"]
    assert rerun["id"] != activation_id

    # Verify both activations exist
    activations = app_client.get("/api/activations").json()
    assert len(activations) == 2


def test_activation_rerun_404(app_client):
    resp = app_client.post("/api/activations/999/rerun")
    assert resp.status_code == 404
