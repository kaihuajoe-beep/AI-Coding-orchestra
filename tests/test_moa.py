import json
from pathlib import Path

import pytest

from orchestra.moa import Agent, MoAOrchestrator, MoARequest


def fake_agent(name, family, proposal, score, cost=0.01):
    def invoke(prompt, _workdir):
        if "独立跨家族评审" in prompt:
            payload = {
                "score": score,
                "verdict": "approve" if score >= 70 else "revise",
                "evidence": [f"{name} evidence"],
            }
            return {"success": True, "output": f"review\nVERDICT_JSON={json.dumps(payload)}", "cost_rmb": cost}
        return {"success": True, "output": proposal, "cost_rmb": cost}

    return Agent(name, family, invoke)


def request(tmp_path, **overrides):
    values = {
        "task": "add health endpoint",
        "workdir": str(tmp_path),
        "candidate_count": 2,
        "reviews_per_candidate": 1,
        "max_cost_rmb": 1,
    }
    values.update(overrides)
    return MoARequest(**values)


def test_runs_cross_family_moa_and_returns_auditable_packet(tmp_path):
    agents = [
        fake_agent("alpha", "family-a", "proposal alpha", 92),
        fake_agent("beta", "family-b", "proposal beta", 74),
    ]

    result = MoAOrchestrator(agents).run(request(tmp_path))

    assert result["success"] is True
    assert result["mode"] == "read_only_decision"
    assert len(result["candidates"]) == 2
    for candidate in result["candidates"]:
        assert candidate["reviews"]
        assert candidate["reviews"][0]["family"] != candidate["family"]
        assert candidate["reviews"][0]["evidence"]
    assert {item["stage"] for item in result["trace"]} == {"proposal", "review"}


def test_isolates_failed_provider_when_two_candidates_survive(tmp_path):
    def broken(_prompt, _workdir):
        raise RuntimeError("provider down")

    agents = [
        fake_agent("alpha", "family-a", "A", 80),
        fake_agent("beta", "family-b", "B", 80),
        Agent("broken", "family-c", broken),
    ]

    result = MoAOrchestrator(agents).run(request(tmp_path, candidate_count=3))

    assert len(result["candidates"]) == 2
    assert any(item["agent"] == "broken" and not item["success"] for item in result["trace"])


def test_requires_two_model_families(tmp_path):
    agents = [
        fake_agent("alpha", "same", "A", 80),
        fake_agent("beta", "same", "B", 80),
    ]

    with pytest.raises(ValueError, match="两个可用的不同模型家族"):
        MoAOrchestrator(agents).run(request(tmp_path))


def test_enforces_reported_cost_budget(tmp_path):
    agents = [
        fake_agent("alpha", "family-a", "A", 80, cost=1),
        fake_agent("beta", "family-b", "B", 80, cost=1),
    ]

    with pytest.raises(RuntimeError, match="超过任务预算"):
        MoAOrchestrator(agents).run(request(tmp_path, max_cost_rmb=0.5))


def test_repository_context_excludes_common_secret_files(tmp_path):
    (tmp_path / "app.py").write_text("print('safe')", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (tmp_path / "credentials.json").write_text('{"password":"secret"}', encoding="utf-8")

    context = MoAOrchestrator._repository_context(str(tmp_path))

    assert "print('safe')" in context
    assert "TOKEN=secret" not in context
    assert "password" not in context


def test_invalid_workdir_is_rejected():
    with pytest.raises(ValueError, match="workdir"):
        MoARequest(task="x", workdir="/definitely/missing").validate()
