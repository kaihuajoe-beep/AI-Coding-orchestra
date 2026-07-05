# Task: MoA multi-model orchestration

- Owner: `codex`
- Branch: `codex/moa-orchestration`
- Project: `/Users/kalenovo/Desktop/CODEX/AI-Coding-orchestra`
- Status: `done`

## Goal

把模型路由器升级为可验证、可审计、默认只读的 Mixture-of-Agents（MoA）协作运行时。

## Scope

- In: 并行提案、跨家族评审、证据评分、确定性排序、可选模型合成、预算门禁、MCP 工具、测试与文档。
- Out: 自动应用模型生成代码、自动合并主分支、生产级 GUI 与常驻调度服务。

## Acceptance criteria

- [x] 至少两个不同模型家族能够并行生成候选方案。
- [x] 候选方案由不同家族审查，结论包含证据而非强制问题数量。
- [x] 无模型可用、部分失败、预算不足和无效参数均有确定行为。
- [x] MoA 结果包含排名、决策依据、成本和完整阶段轨迹。
- [x] 项目测试和 `./scripts/repo-check.sh` 通过。

## Handoff

- Changed: 新增 `orchestra/moa.py`，接入 `moa_orchestrate` MCP 工具，补充 MCP 初始化协议、测试、配置和架构文档。
- Verified: `python3 -m pytest -q`（8 passed）、`compileall`、`git diff --check`、MCP stdio 握手与工具发现 smoke test。
- Risks / follow-up: 精确成本只能在 Provider 返回 usage 后计算；上下文过滤不替代组织级出站数据策略；自动应用与 PR 交付刻意留在 MoA 只读边界之外。
