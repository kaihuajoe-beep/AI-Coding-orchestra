# AI Coding 编排中台 — 产品需求文档 (PRD)

> 版本: v1.0 | 日期: 2025-07-05 | 状态: 待评审

---

## 一、产品概述

### 1.1 产品定位

**AI Coding 编排中台** 是一套基于 Claude Code Skill 体系的轻量级编排层，通过 MCP 协议调度多个异构 AI 模型（Codex、DeepSeek、MiniMax M3），实现软件全生命周期的 **多模型协作开发 + 互相校验 + 自动化运维巡检**。

### 1.2 核心价值主张

```
单模型编码 → 盲区自检失败 → 线上 Bug
多模型协作 + 交叉审查 + 对抗验证 → 互相校验 → 高质量交付
```

一句话：**让 4 个不同家族的 AI 模型像一支开发团队一样协作，互相审查、互相纠错，最终输出比任意单个模型都可靠的代码。**

### 1.3 与现有产品的差异

| | Zenflow | Pantheon | aiforcecli | **本方案** |
|------|:--:|:--:|:--:|:--:|
| 全流程覆盖 | ✅ | ❌ | ❌ | ✅ |
| 跨家族交叉审查 | 部分 | ✅ | ✅ | ✅ (4 家族) |
| 国产模型支持 | ❌ | 部分 | ❌ | ✅ (DeepSeek+MiniMax) |
| CLI 原生 | ❌ (桌面 App) | ✅ | ✅ | ✅ |
| 定时巡检 | ❌ | ❌ | ❌ | ✅ (Routines+Actions) |
| GitHub 深度集成 | 部分 | ❌ | ✅ | ✅ |
| 中文原生 | ❌ | ❌ | ❌ | ✅ |
| 成本最优 | — | — | — | ✅ (Codex 已付+DeepSeek 低价) |

---

## 二、用户画像与场景

### 2.1 目标用户

- 个人/独立开发者，使用 VS Code + Claude Code 作为主力开发环境
- 已有 Codex 会员 + DeepSeek API + MiniMax Token Plan
- 通过 CC Switch 中转访问 Claude 模型
- 所有代码托管在 GitHub

### 2.2 核心场景

| 场景 | 频率 | 当前痛点 | 本方案解法 |
|------|------|------|------|
| **新功能开发** | 每天 | 一个模型写代码，自审自纠有盲区 | 3 模型并行实现 → 跨家族审查 → 对抗验证 → 投票合成 |
| **Bug 修复** | 每天 | AI 修 A 引入 B，频繁返工 | 多视角分析 → 修复 + 测试 + 交叉审查 |
| **Code Review** | 每 PR | 人工 Review 耗时且可能遗漏 | AI 多模型自动一审，人只审关键决策 |
| **代码巡检** | 每天/每周 | 靠人工记忆和 CI，容易遗漏 | 自动化巡检 + 安全扫描 + 依赖审计 |
| **Issue 处理** | 按需 | 分类靠人，简单 Bug 堆积 | AI 自动分类 + 简单 Bug 自动修复提 PR |

---

## 三、产品形态

### 3.1 呈现形态

**本产品不是一个独立的应用程序，而是一个 Claude Code Skill 包 + MCP Server + GitHub Actions 的组合方案。**

```
用户感知层:    VS Code 中 Claude Code 插件
               输入: /orchestra:full "开发 OAuth 登录"
               输入: /orchestra:patrol daily

编排逻辑层:    Claude Code Skills (8 个 Skill 文件)
               ~/.claude/skills/orchestra/*.md

模型路由层:    MCP Model Router (1 个 Python Server, ~300 行)
               mcp-model-router/server.py

CI/CD 层:     GitHub Actions (6 个 Workflow 文件)
               .github/workflows/*.yml
```

### 3.2 不做什么

- ❌ 不做独立 GUI 应用
- ❌ 不做自有模型训练
- ❌ 不做代码托管平台
- ❌ 不做项目管理/IM（Issue/Kanban 走 GitHub 原生）

---

## 四、功能需求

### 4.1 开发管线（8 个 Skill）

#### 4.1.1 规划 `/orchestra:plan`

| 属性 | 描述 |
|------|------|
| 输入 | 自然语言需求描述 |
| 执行模型 | Claude (CC Switch) |
| 输出 | `spec.md` + `tasks.json` + `review-matrix.json` |
| 门禁 | Spec 评分 ≥ 8/10，任务可独立验证 |

#### 4.1.2 并行构建 `/orchestra:build`

| 属性 | 描述 |
|------|------|
| 输入 | 规划阶段的 tasks.json |
| 执行模型 | Codex + DeepSeek + MiniMax（并行，独立 worktree） |
| 路由规则 | P0 核心逻辑 → Codex，P1 通用代码 → DeepSeek，P2 中文/前端 → MiniMax |
| 门禁 | 每个 Agent 自运行测试通过 |

#### 4.1.3 交叉审查 `/orchestra:review`

| 属性 | 描述 |
|------|------|
| 核心规则 | **强制 reviewer.family ≠ author.family** |
| 审查矩阵 | Codex 代码 → DeepSeek+MiniMax 审查；DeepSeek → MiniMax+Codex；MiniMax → Codex+DeepSeek |
| 审查维度 | 安全漏洞/逻辑错误/性能/架构一致性/测试质量 |
| 门禁 | ≥2/3 审查方通过；所有 🔴 高危问题必须修复 |

#### 4.1.4 对抗验证 `/orchestra:adversarial`

| 属性 | 描述 |
|------|------|
| 执行模型 | MiniMax M3 (主) + DeepSeek (副) |
| 攻击视角 | 注入/认证绕过/数据泄露/DoS/业务逻辑漏洞 |
| 边界测试 | 空值/极大值/负数/Unicode/超长字符串/并发 |
| 门禁 | 无 CVSS ≥ 7 的漏洞残留 |

#### 4.1.5 合成 `/orchestra:synthesize`

| 属性 | 描述 |
|------|------|
| 执行模型 | Claude (CC Switch) 主导 |
| 投票机制 | 冲突方案由 4 模型投票（Codex 权重 3, 其他各 2, Claude 打破平局） |
| 输出 | 统一 diff + 变更说明 + 采纳来源标注 |
| 门禁 | ≥2 模型同意每个关键改动 |

#### 4.1.6 交付 `/orchestra:deliver`

| 属性 | 描述 |
|------|------|
| 操作 | 创建分支 → 应用变更 → 运行全量测试 → Push → 创建 PR |
| PR 内容 | 变更摘要 + 参与模型清单 + 审查通过率 + 风险评分 + 成本报告 |
| 风险评分 | 基于变更规模/安全敏感路径/新依赖/测试覆盖变化 综合计算 |

#### 4.1.7 巡检 `/orchestra:patrol`

| 模式 | 频率 | 检查项 | 执行模型 |
|------|------|------|------|
| `daily` | 每天 | 新增代码审查/测试覆盖变化/高危依赖/敏感文件提交 | DeepSeek (省钱) |
| `weekly` | 每周 | 全部 daily + 技术债积累/架构一致性/文档同步/性能趋势 | Claude (深度) |
| `security` | 按需/每天 | OWASP/CVE/密钥泄露/SAST | MiniMax (安全专长) |
| `full` | 按需 | 所有检查项 | Claude 主导 |

#### 4.1.8 维护 `/orchestra:maintain`

| 模式 | 触发条件 | 操作 |
|------|------|------|
| `triage` | 新 Issue 创建 | 自动分类 + 标签 + 优先级 + 推荐 assignee |
| `bug-fix` | Issue 标记 `ai-fix` | 分析 → 复现 → 修复 → 测试 → 自动 PR |
| `doc-sync` | 每天/Release | 检测文档与代码不一致 → 自动修正 PR |
| `perf-check` | PR 到 main | 跑基准测试 → 对比基线 → 退化 >10% 阻塞 |

### 4.2 模型路由系统

#### 4.2.1 路由原则

1. **成本优先**: Codex (¥0 边际) > DeepSeek (极低) > MiniMax (已付) > Claude CC (低) > OpenRouter (仅兜底)
2. **能力匹配**: 规划/合成用最强推理 → Claude；编码主力用最快 → Codex；审查用不同家族
3. **强制跨家族**: 审查方必须与实现方属于不同模型家族

#### 4.2.2 四家族能力矩阵

| | Anthropic (Claude) | OpenAI (Codex) | DeepSeek | MiniMax M3 |
|------|:--:|:--:|:--:|:--:|
| **推理/规划** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **编码实现** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **代码审查** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **安全分析** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **中文能力** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **上下文窗口** | 200K | 256K | 1M | 1M |
| **边际成本** | 低(中转) | ¥0(已付) | 极低 | ¥0(已付) |

### 4.3 GitHub 集成

#### 4.3.1 6 个自动化工作流

| 工作流 | 触发 | 功能 |
|------|------|------|
| `orchestra-ci.yml` | PR 创建/更新 | AI 自动一审 + 风险评分 + CI 验证 |
| `patrol-daily.yml` | 每天 UTC 0:00 | 轻量巡检 + 🔴 问题自动建 Issue |
| `patrol-weekly.yml` | 每周一 | 深度巡检 + 技术债报告 |
| `issue-bot.yml` | Issue 创建/标记 | 自动分类 + `ai-fix` 标记自动修复 |
| `security-scan.yml` | 每天 + PR 触发 | 依赖 CVE + SAST + 密钥泄露扫描 |
| `perf-regression.yml` | PR → main | 基准测试 + 退化阻塞 |

#### 4.3.2 项目配置（CLAUDE.md）

每个项目通过 `CLAUDE.md` 声明自己的规范，Skills 自动适配：

- 项目类型（web-fullstack / backend-service / cli-tool / library）
- 技术栈（语言/框架/测试命令/构建命令）
- 架构约束（目录结构/依赖规则）
- Git 规范（分支命名/Commit 格式/PR 基础分支）
- 模型路由覆盖（可覆盖默认路由规则）

---

## 五、关键决策：是否需要单独的运维智能体？

### 5.1 运维需求拆解

| 运维子场景 | 频率要求 | 持续时长 | 需要常驻进程？ | Claude Code 能否覆盖？ |
|------|:--:|------|:--:|------|
| 每日代码巡检 | 1 次/天 | 2-5 分钟 | ❌ | ✅ Routines / GitHub Actions |
| 每周深度检查 | 1 次/周 | 10-20 分钟 | ❌ | ✅ Routines / GitHub Actions |
| PR 自动审查 | 事件驱动 | 每次 1-3 分钟 | ❌ | ✅ GitHub Actions |
| Issue 自动分类修复 | 事件驱动 | 每次 1-5 分钟 | ❌ | ✅ GitHub Actions |
| 安全漏洞扫描 | 1 次/天 | 3-5 分钟 | ❌ | ✅ GitHub Actions |
| **生产日志实时监控** | **持续** | **7×24** | ✅ | ❌ |
| **告警秒级响应** | **事件驱动** | **<30 秒** | ✅ | ⚠️ 延迟高 |
| **跨项目统一监控面板** | **持续** | **实时** | ✅ | ❌ |
| **巡检结果推送微信/Slack** | **事件驱动** | **即时** | 部分 | ⚠️ 需额外配置 |

### 5.2 结论：当前阶段不需要单独的运维智能体

**理由**：

1. **你的运维场景是"定时巡检 + 事件驱动"，不是"7×24 实时值守"**
   - 每天巡检 1 次 → Claude Code Routines 原生支持
   - PR/Issue 触发 → GitHub Actions 完美覆盖
   - 成本：Routines Pro 计划 5 次/天，绰绰有余

2. **Claude Code + GitHub Actions 已经覆盖了 90% 的运维需求**
   - Routines：云上定时执行，不需要你的电脑开机
   - Actions：GitHub 原生事件驱动，零额外成本
   - Headless CLI：`claude -p --bare` 可在任何 CI 环境运行

3. **单独运维智能体的额外收益在当前阶段不显著**
   - 你不需要 7×24 秒级响应
   - 你不需要多通道推送（微信/Telegram/Slack）
   - 你不需要跨日状态追踪（Hermes 的强项）
   - 这些都是"有了更好，但没到必须"的场景

### 5.3 何时需要引入 Hermes Agent？

引入 Hermes 作为运维智能体的触发条件：

```
引入条件（满足任意 2 个即建议引入）:
□ 需要 <1 分钟的告警响应时间
□ 需要 7×24 不间断值守
□ 需要微信/钉钉/Telegram 推送巡检结果
□ 需要跨项目统一监控（3+ 个项目）
□ 巡检发现问题后需要跨天追踪修复进度
□ 每晚自动跑全量测试 → 失败自动修 → 早上看结果
```

**当前状态**：以上条件均不满足。**建议保持 Claude Code 原生方案，等真正需要时再加 Hermes。**

---

## 六、实施计划

### 6.1 总览

| 阶段 | 内容 | 工时 | 产出 |
|------|------|------|------|
| P1 | MCP Server + 基础 Skill | 2-3 天 | model-router 可用 + plan Skill |
| P2 | 核心开发管线 | 3-5 天 | build → review → advex → synth → deliver 全流程 |
| P3 | 运维巡检 | 2-3 天 | patrol + maintain + daily/weekly Actions |
| P4 | CI/CD 深度集成 | 2-3 天 | 全部 6 个 Actions + CLAUDE.md 模板 |
| P5 | 调优 + 文档 | 1-2 天 | 使用文档 + 成本追踪完善 |

### 6.2 详细任务清单

**P1: MCP Server + 基础 Skill**

- [ ] `mcp-model-router/server.py` — 5 个 MCP 工具
- [ ] DeepSeek / MiniMax / Codex / OpenRouter Provider Adapter
- [ ] 成本追踪 `cost_report()`
- [ ] `~/.claude/settings.json` — MCP Server 注册
- [ ] `SKILL.md` — 入口调度器
- [ ] `plan.md` — 规划 Skill
- [ ] 验证：`/orchestra:plan "实现一个功能"` 产出 Spec + tasks.json

**P2: 核心开发管线**

- [ ] `build.md` — 并行构建 Skill (worktree 隔离 + fan-out)
- [ ] `review.md` — 交叉审查 Skill (跨家族矩阵)
- [ ] `adversarial.md` — 对抗验证 Skill
- [ ] `synthesize.md` — 合成 Skill (投票机制)
- [ ] `deliver.md` — 交付 Skill (PR + 风险评分)
- [ ] 验证：`/orchestra:full "实现小功能"` 全流程跑通

**P3: 运维巡检**

- [ ] `patrol.md` — 巡检 Skill (daily/weekly/full/security/dependency)
- [ ] `maintain.md` — 维护 Skill (triage/bug-fix/doc-sync/perf-check)
- [ ] `patrol-daily.yml` — GitHub Actions 每日巡检
- [ ] `patrol-weekly.yml` — GitHub Actions 每周检查
- [ ] 验证：手动触发巡检 → 报告生成 → Issue 创建

**P4: CI/CD 深度集成**

- [ ] `orchestra-ci.yml` — PR CI + 自动审查
- [ ] `issue-bot.yml` — Issue 自动分类修复
- [ ] `security-scan.yml` — 安全扫描
- [ ] `perf-regression.yml` — 性能回归
- [ ] `CLAUDE.md` 模板（多项目类型）
- [ ] 验证：创建测试 PR → 自动审查 → CI 通过

**P5: 调优 + 文档**

- [ ] Prompt 调优（基于实际使用反馈）
- [ ] 成本追踪仪表盘
- [ ] README + 快速开始指南
- [ ] FAQ + 常见问题排查

---

## 七、成本预估

### 7.1 每月固定成本

| 项目 | 月费 | 备注 |
|------|------|------|
| Codex 桌面端会员 | 已付 | 主力开发引擎 |
| MiniMax M3 Token Plan Max | ¥119 | 交叉审查 + 对抗验证 |
| DeepSeek API | ~¥10-30 | 可变，按用量 |
| CC Switch | ~¥20-50 | 中转费用 |
| GitHub | ¥0 | 免费计划 |
| Claude Code Routines | ¥0 | Pro 计划含 5 次/天 |
| **合计** | **~¥150-200/月** | |

### 7.2 单次全流程成本

以中等功能（5 个子任务）为例：

| 阶段 | 模型 | 预估 Token | 成本 |
|------|------|------|------|
| 规划 | Claude (CC Switch) | 20K | ~¥0.03 |
| 实现 (×3 并行) | Codex + DeepSeek + MiniMax | 150K | ~¥0.15 |
| 交叉审查 (×3) | DeepSeek + MiniMax + Codex | 60K | ~¥0.05 |
| 对抗验证 (×2) | MiniMax + DeepSeek | 40K | ~¥0.03 |
| 合成 | Claude (CC Switch) | 40K | ~¥0.06 |
| **合计** | | **~310K** | **~¥0.32** |

> 每天开发 10 个中等功能 → 月成本 ~¥96（API）+ ¥119（MiniMax 固定）= **~¥215/月**

### 7.3 成本优化开关

```yaml
# 省钱模式 (轻度项目)
cost_mode: economy
  build_parallelism: 1       # 只用 1 个模型实现
  cross_review: false        # 跳过交叉审查
  advex: false               # 跳过对抗验证
  patrol: weekly_only        # 仅每周巡检
  
# 标准模式 (日常开发)
cost_mode: standard
  build_parallelism: 2       # Codex + DeepSeek
  cross_review: true         # 交叉审查
  advex: security_only       # 仅安全对抗
  patrol: daily              # 每日轻量巡检

# 质量模式 (关键项目)
cost_mode: quality
  build_parallelism: 3       # Codex + DeepSeek + MiniMax
  cross_review: true         # 全矩阵审查
  advex: full                # 安全+边界+并发
  patrol: daily + weekly     # 完整巡检
```

---

## 八、成功指标

| 指标 | 目标值 | 测量方式 |
|------|------|------|
| 全流程可用性 | `/orchestra:full` 成功率 > 80% | 统计执行记录 |
| 交叉审查增量价值 | 审查发现的问题数 > 单模型自查 2x | 对比实验 |
| 端到端耗时 | 中等功能 < 15 分钟 | 统计执行记录 |
| 人工介入率 | < 20% 的任务需要人工修改 | 统计 PR 修改次数 |
| 成本可控 | 月成本 < ¥300 | 成本追踪 |

---

## 九、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:--:|:--:|------|
| CC Switch 不稳定 | 中 | 高 | OpenRouter 兜底 + 自动切换 |
| 多模型输出不一致 | 高 | 中 | 投票机制 + Claude 打破平局 |
| MiniMax API 限流 | 低 | 低 | DeepSeek 替补审查 |
| Git Worktree 冲突 | 中 | 中 | 独立 worktree 隔离 + 清理脚本 |
| Token 成本超预算 | 低 | 中 | 每日预算上限 + 省钱模式开关 |

---

## 十、附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| **模型家族** | 不同公司/架构的模型群体。本方案分四族：Anthropic, OpenAI, DeepSeek, MiniMax |
| **交叉审查** | 用不同家族的模型审查代码，避免自审盲区 |
| **对抗验证** | 让模型扮演攻击者，试图找出代码漏洞 |
| **投票合成** | 多个模型对冲突方案投票，选出最优解 |
| **Worktree 隔离** | 每个 Agent 在独立 Git Worktree 中工作，互不干扰 |
| **法定人数门禁** | ≥N 个审查方同意才能通过的安全阀值 |

### B. 参考资料

- [Pantheon Skills](https://github.com/lolu1032/pantheon-skills) — Plan → Parallel → Adversarial → Judge 模式
- [GodModeSkill](https://github.com/99xAgency/GodModeSkill) — 3 家族法定人数审查
- [Sous-Chef](https://github.com/tomascupr/sous-chef) — Claude 规划/Codex 实现双模型模式
- [aiforcecli-chat](https://www.npmjs.com/package/aiforcecli-chat) — 多 Agent 竞速模式
- [deepseek-as-subagent](https://github.com/PsChina/deepseek-as-subagent) — DeepSeek 作为 Claude 子 Agent
- [RepoAI](https://www.sciencedirect.com/science/article/abs/pii/S0167642326000432) — 跨家族 LLM 审查的统计学验证 (p=0.007)
