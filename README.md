# AI Coding Orchestra 2.0

> 四模型家族协作，覆盖软件全生命周期。规划→编码→审查→验证→交付→运维，全流程 AI 化。

## 一句话

**让 Codex + DeepSeek + MiniMax + Claude 通过可审计的 Mixture-of-Agents（MoA）流程协作，以仓库证据、测试和明确门禁决定最终方案。**

## 核心能力

```
你说: "完整实现用户登录功能"
系统: 🎯 启动多模型协作
      ① Claude 生成 Spec 和任务拆解
      ② 多家族并行生成只读候选方案
      ③ 跨家族证据评审 (reviewer.family ≠ author.family)
      ④ 中位数稳健评分 + 异议保留
      ⑤ 可选模型合成，失败自动回退最高分候选
      ⑥ 单一执行者落盘 → 测试门禁 → 人工批准交付
```

> MoA 不会让多个模型同时修改同一工作树。提案、评审和合成默认只读，输出决策包；应用代码是后续显式步骤。

## MoA 运行时

MCP 工具 `moa_orchestrate` 提供：

- 2–8 个候选并行生成，优先覆盖不同模型家族；
- 每个候选接受 1–4 个不同家族的独立评审；
- 评审必须附仓库位置、推理依据或可复现测试，不要求“凑够问题数”；
- 使用评审分数中位数、证据奖励和否决惩罚排名；
- Provider 部分失败时隔离故障，候选不足两个才终止；
- 返回候选、评审、排名、成本、阶段轨迹与最终决策。

完整协议和安全边界见 [MoA 架构文档](docs/MOA-ARCHITECTURE.md)。

## 快速开始

```bash
# 1. 复制 MCP Server
cp -r mcp-model-router ~/

# 2. 安装 Skills
cp -r starter-kit/.claude ~/.claude/

# 3. 配置 API Keys (~/.mcp.json)
# 填入 DEEPSEEK_API_KEY 和 MINIMAX_API_KEY

# 4. 复制到项目
cp starter-kit/.github your-project/
cp starter-kit/CLAUDE.md.template your-project/CLAUDE.md

# 5. 在 MCP 客户端调用 moa_orchestrate，至少配置两个模型家族
```

## 模型阵容

| 模型 | 家族 | 成本 | 职责 |
|------|------|------|------|
| Codex (GPT-5) | OpenAI | ¥0 (会员) | 超主力编码 |
| DeepSeek V4 | DeepSeek | ~¥1/1M tok | 溢出编码+中文 |
| MiniMax M3 | MiniMax | ¥119/月 | 交叉审查+对抗验证 |
| Claude (CC Switch) | Anthropic | ~¥20-50/月 | 规划+合成+终审 |

## 架构

```
MCP Client → MoA Runtime → 并行只读提案 → 跨家族证据评审 → 排名/合成
                                ↓
                  单一执行 Agent → 测试/CI → 人工批准 → PR
```

## 目录

```
mcp-model-router/
├── server.py          # MCP 路由服务器 (7 tools, 4 adapters)
├── config.yaml        # 模型家族 + 路由规则
├── PRD.md             # 产品需求文档
├── starter-kit/
│   ├── .github/workflows/  # 6个自动化工作流
│   └── README.md
└── requirements.txt

~/.claude/
├── skills/orchestra/   # 8个 Skill
├── agents/             # 5个 Agent 定义
├── settings.json       # 权限
└── .mcp.json          # MCP 注册
```

## 许可证

MIT License
