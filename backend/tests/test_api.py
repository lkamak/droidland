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
