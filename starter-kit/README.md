# AI Coding 编排中台 — 快速开始

## 1. 复制到你的项目

```bash
cp -r starter-kit/.github 你的项目/
cp -r starter-kit/.aicoding 你的项目/
cp ~/.claude/CLAUDE.md.template 你的项目/CLAUDE.md
# 编辑 CLAUDE.md，填入你的项目信息
```

## 2. 配置 GitHub Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加:

| Secret | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `MINIMAX_API_KEY` | MiniMax API 密钥 |
| `CC_SWITCH_URL` | CC Switch 中转地址 |
| `CC_SWITCH_TOKEN` | CC Switch 令牌 |

## 3. 日常使用

在 VS Code 中打开 Claude Code:

```
# 日常开发
"修一下这个空指针"                        → 直接修

# 编排模式
/o full "开发 OAuth 登录模块"              → 全流程自动
/o build "按 plan 实现"                   → 只构建
/o review                                  → 只审查
/o patrol daily                            → 每日巡检

# 智能触发
"完整实现用户认证功能，包括邮箱验证"       → 自动询问是否启动编排
"重构支付系统，保证安全"                   → 自动建议编排
```

## 4. 文件结构

```
你的项目/
├── .claude/settings.json      # Claude Code 配置
├── CLAUDE.md                   # 项目规范
├── .github/workflows/          # 自动化
│   ├── orchestra-ci.yml        # PR CI + AI审查
│   ├── patrol-daily.yml        # 每日巡检
│   ├── patrol-weekly.yml       # 每周深度巡检
│   ├── issue-bot.yml           # Issue自动分类修复
│   ├── security-scan.yml       # 安全扫描
│   └── perf-regression.yml     # 性能回归
└── specs/                      # AI生成的Spec存档
```

## 5. 成本

| 场景 | 月费 |
|------|------|
| Codex 会员 | 已付 |
| MiniMax M3 Token Plan Max | ¥119 |
| DeepSeek API | ~¥20-70 |
| CC Switch | ~¥20-80 |
| **合计** | **~¥200-270/月** |
