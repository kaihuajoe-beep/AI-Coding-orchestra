# AI Coding 编排中台 — 使用指南

## 触发词速查表

你只需要说中文。系统自动检测是否启动编排:

| 你说 | 系统行为 |
|------|------|
| **"完整实现**XXX功能" | 全流程 (规划→编码→审查→交付) |
| **"帮我开发**XXX" | 同上 |
| **"重构**XXX模块" | 同上 |
| **"做一个**XXX" | 同上 |
| **"巡检/扫描项目**" | 每日或深度巡检 |
| **"修这个Bug**" | 自动修复 |
| "改一下变量名" | 不触发 (小改动走Claude Code直接模式) |

## 中间环节启动

| 场景 | 说法 |
|------|------|
| 已有需求文档, 直接编码 | "按 spec.md 实现这些功能" |
| 代码写好了, 要审查 | "审查 src/ 下所有代码" |
| 要安全检查 | "对 auth模块做安全渗透测试" |
| 只要提PR | "帮我创建 PR" |
| Issue太多 | "帮我分类这些 Issue" |

## 快捷命令 (可选)

```
/o full <需求>    — 全流程
/o plan <需求>    — 仅规划
/o build          — 仅编码
/o review         — 仅审查
/o advex          — 仅对抗验证
/o synth          — 仅合成
/o deliver        — 仅交付
/o patrol daily   — 每日巡检
/o maint bug-fix <issue#> — Bug自动修复
```

## 模型调度规则

| 阶段 | 模型 | 原因 |
|------|------|------|
| 规划 | Claude (CC Switch) | 最强推理 |
| 编码 | Codex优先 → DeepSeek溢出 | 会员已付优先 + 便宜补位 |
| 审查 | 强制跨家族 (reviewer≠author) | 避免自审盲区 |
| 对抗 | MiniMax主 → DeepSeek辅 | 安全思维强 |
| 合成 | Claude | 投票+决策 |
| 巡检 | DeepSeek (轻量) / Claude (深度) | 成本控制 |

## 新项目接入

```bash
git clone https://github.com/kaihuajoe-beep/ai-coding-orchestra.git
cp ai-coding-orchestra/starter-kit/.github 你的项目/
cp ai-coding-orchestra/starter-kit/CLAUDE.md.template 你的项目/CLAUDE.md
# 编辑 CLAUDE.md, 填入项目信息
# 在 GitHub Settings 中添加 Secrets: DEEPSEEK_API_KEY, MINIMAX_API_KEY
```

## 成本估算

| 场景 | 月费 |
|------|------|
| Codex 会员 | 已付 |
| MiniMax M3 | ¥119 |
| DeepSeek API | ~¥20-70 |
| CC Switch | ~¥20-80 |
| **合计** | **~¥200-270/月** |
