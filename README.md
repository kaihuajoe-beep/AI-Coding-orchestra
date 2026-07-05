# AI Coding 编排中台

> 四模型家族协作，覆盖软件全生命周期。规划→编码→审查→验证→交付→运维，全流程 AI 化。

## 一句话

**让 Codex + DeepSeek + MiniMax + Claude 像一支开发团队一样协作，互相审查、互相纠错，输出比任意单个模型都可靠的代码。**

## 核心能力

```
你说: "完整实现用户登录功能"
系统: 🎯 启动多模型协作
      ① Claude 生成 Spec 和任务拆解
      ② Codex+DeepSeek+MiniMax 三路并行编码 (独立 Git Worktree)
      ③ 跨家族交叉审查 (强制 reviewer.family ≠ author.family)
      ④ MiniMax 扮演攻击者对抗验证
      ⑤ Claude 投票合成最优版本
      ⑥ 自动创建 PR + 风险评分
      💰 成本: ~¥0.3
```

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

# 5. 在 VS Code 中打开 Claude Code，说:
"帮我开发一个XXX功能"
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
Claude Code (VS Code) → Skills 编排 → MCP Server → Codex/DeepSeek/MiniMax
                                    → GitHub Actions → CI/巡检/Issue Bot
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
