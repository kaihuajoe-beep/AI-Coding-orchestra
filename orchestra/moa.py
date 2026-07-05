"""Deterministic Mixture-of-Agents orchestration.

The runtime deliberately keeps proposal and review agents read-only.  It produces
an auditable decision packet; applying the selected change is a separate,
explicit delivery step guarded by project tests.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


Provider = Callable[[str, str], dict[str, Any]]


@dataclass(frozen=True)
class Agent:
    name: str
    family: str
    invoke: Provider


@dataclass(frozen=True)
class MoARequest:
    task: str
    workdir: str
    candidate_count: int = 3
    reviews_per_candidate: int = 2
    max_cost_rmb: float = 10.0
    synthesizer: str | None = None

    def validate(self) -> None:
        if not self.task.strip():
            raise ValueError("task 不能为空")
        if not Path(self.workdir).is_dir():
            raise ValueError(f"workdir 不存在或不是目录: {self.workdir}")
        if not 2 <= self.candidate_count <= 8:
            raise ValueError("candidate_count 必须在 2 到 8 之间")
        if not 1 <= self.reviews_per_candidate <= 4:
            raise ValueError("reviews_per_candidate 必须在 1 到 4 之间")
        if self.max_cost_rmb <= 0:
            raise ValueError("max_cost_rmb 必须大于 0")


@dataclass
class Candidate:
    id: str
    agent: str
    family: str
    proposal: str
    cost_rmb: float = 0.0
    reviews: list[dict[str, Any]] = field(default_factory=list)
    score: float = 0.0


class MoAOrchestrator:
    """Run proposal -> cross-family review -> rank -> optional synthesis."""

    def __init__(self, agents: Iterable[Agent]):
        self.agents = {agent.name: agent for agent in agents}

    def run(self, request: MoARequest) -> dict[str, Any]:
        request.validate()
        started = time.monotonic()
        trace: list[dict[str, Any]] = []
        selected = self._select_candidates(request.candidate_count)
        if len({agent.family for agent in selected}) < 2:
            raise ValueError("MoA 至少需要两个可用的不同模型家族")

        proposals = self._parallel_proposals(selected, request, trace)
        if len(proposals) < 2:
            raise RuntimeError("成功生成的候选方案不足两个，无法进入 MoA 评审")
        self._enforce_budget(proposals, request.max_cost_rmb)

        self._parallel_reviews(proposals, request, trace)
        for candidate in proposals:
            candidate.score = self._score(candidate)
        proposals.sort(key=lambda item: (-item.score, item.cost_rmb, item.id))

        total_cost = sum(c.cost_rmb for c in proposals) + sum(
            float(r.get("cost_rmb", 0)) for c in proposals for r in c.reviews
        )
        if total_cost > request.max_cost_rmb:
            raise RuntimeError(
                f"MoA 成本 ¥{total_cost:.4f} 超过任务预算 ¥{request.max_cost_rmb:.4f}"
            )

        synthesis = self._synthesize(proposals, request, trace)
        total_cost += float(synthesis.get("cost_rmb", 0))
        if total_cost > request.max_cost_rmb:
            raise RuntimeError(
                f"合成后成本 ¥{total_cost:.4f} 超过任务预算 ¥{request.max_cost_rmb:.4f}"
            )

        return {
            "success": True,
            "run_id": uuid.uuid4().hex[:12],
            "mode": "read_only_decision",
            "winner": proposals[0].id,
            "decision": synthesis["output"],
            "candidates": [self._candidate_dict(c) for c in proposals],
            "cost_rmb": round(total_cost, 4),
            "duration_seconds": round(time.monotonic() - started, 3),
            "trace": trace,
            "next_step": "由单一执行 Agent 应用决策，并运行项目测试后再交付。",
        }

    def _select_candidates(self, count: int) -> list[Agent]:
        # Stable order makes runs and tests reproducible; one agent per family first.
        ordered = sorted(self.agents.values(), key=lambda a: (a.family, a.name))
        selected: list[Agent] = []
        seen: set[str] = set()
        for agent in ordered:
            if agent.family not in seen:
                selected.append(agent)
                seen.add(agent.family)
            if len(selected) == count:
                return selected
        for agent in ordered:
            if agent not in selected:
                selected.append(agent)
            if len(selected) == count:
                break
        return selected

    def _parallel_proposals(
        self, agents: list[Agent], request: MoARequest, trace: list[dict[str, Any]]
    ) -> list[Candidate]:
        prompt = self._proposal_prompt(request.task, self._repository_context(request.workdir))
        candidates: list[Candidate] = []
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            futures = {pool.submit(a.invoke, prompt, request.workdir): a for a in agents}
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # provider isolation is intentional
                    result = {"success": False, "error": str(exc)}
                trace.append(self._trace("proposal", agent, result))
                if result.get("success") and result.get("output", "").strip():
                    candidates.append(
                        Candidate(
                            id=f"{agent.family}:{agent.name}",
                            agent=agent.name,
                            family=agent.family,
                            proposal=result["output"],
                            cost_rmb=float(result.get("cost_rmb", 0)),
                        )
                    )
        return candidates

    def _parallel_reviews(
        self,
        candidates: list[Candidate],
        request: MoARequest,
        trace: list[dict[str, Any]],
    ) -> None:
        jobs: list[tuple[Candidate, Agent]] = []
        ordered = sorted(self.agents.values(), key=lambda a: (a.family, a.name))
        for candidate in candidates:
            reviewers = [a for a in ordered if a.family != candidate.family]
            jobs.extend((candidate, reviewer) for reviewer in reviewers[: request.reviews_per_candidate])
        if not jobs:
            raise RuntimeError("没有可用的跨家族评审 Agent")

        with ThreadPoolExecutor(max_workers=min(len(jobs), 8)) as pool:
            futures = {
                pool.submit(
                    reviewer.invoke,
                    self._review_prompt(request.task, candidate.proposal),
                    request.workdir,
                ): (candidate, reviewer)
                for candidate, reviewer in jobs
            }
            for future in as_completed(futures):
                candidate, reviewer = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"success": False, "error": str(exc)}
                trace.append(self._trace("review", reviewer, result, candidate.id))
                if result.get("success"):
                    parsed = self._parse_review(result.get("output", ""))
                    parsed.update(
                        {
                            "reviewer": reviewer.name,
                            "family": reviewer.family,
                            "cost_rmb": float(result.get("cost_rmb", 0)),
                        }
                    )
                    candidate.reviews.append(parsed)

    def _synthesize(
        self,
        candidates: list[Candidate],
        request: MoARequest,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        winner = candidates[0]
        if not request.synthesizer:
            return {"output": winner.proposal, "cost_rmb": 0}
        agent = self.agents.get(request.synthesizer)
        if not agent:
            raise ValueError(f"未知 synthesizer: {request.synthesizer}")
        packet = "\n\n".join(
            f"## {c.id} score={c.score:.2f}\n{c.proposal}\nReviews: {json.dumps(c.reviews, ensure_ascii=False)}"
            for c in candidates
        )
        result = agent.invoke(self._synthesis_prompt(request.task, packet), request.workdir)
        trace.append(self._trace("synthesis", agent, result))
        if not result.get("success") or not result.get("output", "").strip():
            return {"output": winner.proposal, "cost_rmb": 0, "fallback": True}
        return result

    @staticmethod
    def _proposal_prompt(task: str, context: str) -> str:
        return f"""你是 MoA 候选方案 Agent。只读分析，不得修改文件、提交或推送。
任务：{task}
仓库上下文（可能截断）：
{context}
请基于仓库证据输出：方案摘要、拟修改文件、关键 diff/伪代码、测试计划、风险与假设。
不确定时明确标注；不要声称执行过未执行的测试。"""

    @staticmethod
    def _review_prompt(task: str, proposal: str) -> str:
        return f"""你是独立跨家族评审 Agent。只读评估候选方案，不得修改文件。
原始任务：{task}
候选方案：\n{proposal}
检查正确性、安全性、可维护性、测试充分性和任务贴合度。
问题必须给出仓库位置、推理链或可复现测试；不要为了凑数量编造问题。
最后严格输出一行：VERDICT_JSON={{"score":0到100,"verdict":"approve或revise或reject","evidence":["证据"]}}"""

    @staticmethod
    def _synthesis_prompt(task: str, packet: str) -> str:
        return f"""你是 MoA 合成 Agent。只读输出最终实施决策，不修改仓库。
任务：{task}
按证据权重而非多数票合成；保留关键异议，禁止声称执行过测试。
候选与评审：\n{packet}"""

    @staticmethod
    def _parse_review(output: str) -> dict[str, Any]:
        match = re.search(r"VERDICT_JSON\s*=\s*(\{.*\})", output, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                score = max(0.0, min(100.0, float(data["score"])))
                verdict = data.get("verdict", "revise")
                if verdict not in {"approve", "revise", "reject"}:
                    verdict = "revise"
                evidence = data.get("evidence", [])
                return {
                    "score": score,
                    "verdict": verdict,
                    "evidence": evidence if isinstance(evidence, list) else [str(evidence)],
                    "raw": output,
                }
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return {"score": 50.0, "verdict": "revise", "evidence": [], "raw": output}

    @staticmethod
    def _score(candidate: Candidate) -> float:
        if not candidate.reviews:
            return 0.0
        scores = sorted(float(review["score"]) for review in candidate.reviews)
        # Median resists one unusually generous or hostile reviewer.
        middle = len(scores) // 2
        median = scores[middle] if len(scores) % 2 else (scores[middle - 1] + scores[middle]) / 2
        evidence_bonus = min(5.0, sum(bool(r.get("evidence")) for r in candidate.reviews))
        reject_penalty = 10.0 * sum(r.get("verdict") == "reject" for r in candidate.reviews)
        return round(max(0.0, median + evidence_bonus - reject_penalty), 2)

    @staticmethod
    def _enforce_budget(candidates: list[Candidate], budget: float) -> None:
        cost = sum(candidate.cost_rmb for candidate in candidates)
        if cost > budget:
            raise RuntimeError(f"候选生成成本 ¥{cost:.4f} 超过任务预算 ¥{budget:.4f}")

    @staticmethod
    def _trace(
        stage: str, agent: Agent, result: dict[str, Any], candidate: str | None = None
    ) -> dict[str, Any]:
        return {
            "stage": stage,
            "agent": agent.name,
            "family": agent.family,
            "candidate": candidate,
            "success": bool(result.get("success")),
            "cost_rmb": float(result.get("cost_rmb", 0)),
            "error": result.get("error"),
        }

    @staticmethod
    def _candidate_dict(candidate: Candidate) -> dict[str, Any]:
        return {
            "id": candidate.id,
            "agent": candidate.agent,
            "family": candidate.family,
            "score": candidate.score,
            "cost_rmb": candidate.cost_rmb,
            "proposal": candidate.proposal,
            "reviews": candidate.reviews,
        }

    @staticmethod
    def _repository_context(workdir: str, limit: int = 40_000) -> str:
        """Build a bounded, secret-conscious repository snapshot for API agents."""
        root = Path(workdir).resolve()
        allowed = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
            ".md", ".toml", ".yaml", ".yml", ".json",
        }
        blocked_parts = {".git", "node_modules", ".venv", "venv", "dist", "build"}
        blocked_names = {".env", ".env.local", "credentials.json", "secrets.json"}
        chunks: list[str] = []
        size = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
            if any(part in blocked_parts for part in rel.parts):
                continue
            if path.name in blocked_names or path.suffix.lower() not in allowed:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            chunk = f"\n--- {rel}\n{content}"
            remaining = limit - size
            if remaining <= 0:
                break
            chunks.append(chunk[:remaining])
            size += min(len(chunk), remaining)
        return "".join(chunks) or "（未找到可安全读取的文本源码）"
