#!/usr/bin/env python3
"""
MCP Model Router — AI Coding 编排中台的多模型路由服务器

让 Claude Code 通过 MCP 协议调度 Codex CLI、DeepSeek API、MiniMax API。
协议: MCP stdio (JSON-RPC 2.0)

模型家族:
  - openai:    Codex / GPT-5-Codex (桌面端会员, ¥0 边际成本)
  - deepseek:  DeepSeek V4 Pro (API 直连, ~¥0.9/1M tokens)
  - minimax:   MiniMax M3 (Token Plan Max, ¥119/月已付)
  - anthropic: Claude (通过 CC Switch, ~¥20-50/月)

环境变量:
  DEEPSEEK_API_KEY  - DeepSeek API 密钥
  MINIMAX_API_KEY   - MiniMax API 密钥
  OPENROUTER_API_KEY - OpenRouter API 密钥 (兜底用)
"""

import json
import os
import shutil
import subprocess
import sys
import time
import hashlib
from pathlib import Path
from typing import Any

# 服务启动时间和版本
_start_time = time.time()
VERSION = "1.0.0"

# ============================================================
# 成本追踪
# ============================================================
_cost_log: list[dict] = []

def _track_cost(agent: str, model: str, tokens_in: int, tokens_out: int, cost: float):
    _cost_log.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agent": agent,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_rmb": round(cost, 4),
    })

# ============================================================
# 模型成本表 (RMB / 百万 token)
# ============================================================
COST_TABLE = {
    "deepseek-v4-pro":   {"input": 0.435 * 7.2, "output": 0.87 * 7.2},    # DeepSeek API
    "deepseek-v4-flash": {"input": 0.27 * 7.2,  "output": 1.10 * 7.2},
    "minimax-m3":        {"input": 2.1,          "output": 8.4},            # MiniMax 国内价
    "codex-gpt-5":       {"input": 0,            "output": 0},              # 会员已付
    "openrouter-claude": {"input": 21.0,         "output": 84.0},           # 贵! 仅兜底
}

# 模型家族映射
FAMILY_MAP = {
    "deepseek-v4-pro":   "deepseek",
    "deepseek-v4-flash": "deepseek",
    "minimax-m3":        "minimax",
    "codex-gpt-5":       "openai",
    "gpt-5-codex":       "openai",
    "openrouter-claude": "anthropic",
}

# ============================================================
# Agent 执行器
# ============================================================

def run_codex(task: str, workdir: str, model: str = "gpt-5-codex") -> dict:
    """通过 Codex CLI 执行编码任务"""
    prompt = f"""你是一个高效的编码 Agent。请完成以下任务。

任务：
{task}

工作目录：{workdir}

要求：
1. 先理解代码库结构和现有代码
2. 实现功能变更
3. 运行测试验证（如果项目有测试命令）
4. 如果测试失败，分析原因并修复
5. 返回：变更摘要 + 文件列表 + 测试状态 + 信心度(1-10)

请用中文回复。
"""
    try:
        result = subprocess.run(
            ["codex", "exec", "--model", model, "--json", prompt],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = result.stdout or result.stderr
        _track_cost("codex", model, 0, 0, 0)  # 会员已付, 成本为 0
        return {
            "success": result.returncode == 0,
            "agent": "codex",
            "family": "openai",
            "model": model,
            "output": output[:8000],
            "cost_rmb": 0,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "agent": "codex",
            "family": "openai",
            "error": "Codex CLI 未安装。请运行: npm install -g @openai/codex",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "agent": "codex",
            "family": "openai",
            "error": "Codex 执行超时 (10分钟)",
        }


def run_deepseek(task: str, workdir: str, model: str = "deepseek-v4-pro") -> dict:
    """通过 DeepSeek API 执行编码任务 (OpenAI 兼容接口)"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"success": False, "agent": "deepseek", "error": "未设置 DEEPSEEK_API_KEY"}

    import requests

    system_prompt = """你是一个高效的 AI 编码 Agent。请完成用户的任务。

执行步骤：
1. 理解任务需求和现有代码结构
2. 实现代码变更
3. 自检：是否有逻辑错误？是否有安全漏洞？是否有边界条件遗漏？
4. 返回：变更摘要 + 具体代码 + 测试状态 + 信心度(1-10)

请用中文回复。工作目录: """ + workdir

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task},
                ],
                "max_tokens": 16384,
                "temperature": 0.3,
            },
            timeout=180,
        )
        data = resp.json()

        if "error" in data:
            return {"success": False, "agent": "deepseek", "error": data["error"]}

        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        cost_in = COST_TABLE.get(model, {}).get("input", 0) * tokens_in / 1_000_000
        cost_out = COST_TABLE.get(model, {}).get("output", 0) * tokens_out / 1_000_000
        cost = cost_in + cost_out

        _track_cost("deepseek", model, tokens_in, tokens_out, cost)

        content = data["choices"][0]["message"]["content"]
        return {
            "success": True,
            "agent": "deepseek",
            "family": "deepseek",
            "model": model,
            "output": content[:8000],
            "tokens": {"in": tokens_in, "out": tokens_out},
            "cost_rmb": round(cost, 4),
        }
    except Exception as e:
        return {"success": False, "agent": "deepseek", "error": str(e)}


def run_minimax(task: str, workdir: str, mode: str = "code", model: str = "MiniMax-M3") -> dict:
    """通过 MiniMax API 执行任务 (Anthropic 兼容接口)

    mode:
      - "code":        编码实现
      - "review":      代码审查
      - "adversarial": 对抗验证 (安全攻击视角)
    """
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return {"success": False, "agent": "minimax", "error": "未设置 MINIMAX_API_KEY"}

    import requests

    system_prompts = {
        "code": "你是一个高效的 AI 编码 Agent。请完成用户的编码任务。返回变更摘要、代码、测试状态和信心度。用中文回复。",
        "review": """你是资深代码审查专家。请严格审查以下代码。

审查维度 (每个维度必须给出具体发现):
1. 🔴 安全漏洞 (OWASP Top 10: 注入/认证/敏感数据/XXE/SSRF)
2. 🟡 逻辑错误 (边界条件/错误处理/状态机/并发)
3. 🟠 性能问题 (N+1查询/不必要拷贝/内存泄漏/阻塞操作)
4. 🔵 架构一致性 (命名规范/依赖方向/接口设计)
5. 🟢 测试质量 (覆盖率/边界测试/Mock使用)

对每个发现给出: 严重程度 | 文件位置 | 问题描述 | 修复建议 | 置信度

如果确实未发现问题，明确说明"审查通过"。绝不说模棱两可的结论。""",
        "adversarial": """你是恶意渗透测试专家。请找出以下代码的所有安全漏洞和可利用的攻击面。

你必须找到至少 5 个潜在问题。绝不说'代码看起来安全'。

攻击视角:
1. 注入攻击 (SQL/命令/模板/XSS)
2. 认证绕过 (Token伪造/会话劫持/权限提升)
3. 数据泄露 (敏感信息暴露/日志泄露/错误消息)
4. 拒绝服务 (资源耗尽/无限循环/大输入崩溃)
5. 业务逻辑漏洞 (越权操作/金额篡改/竞态条件)

对每个发现给出: 攻击向量 | 危害等级 | 利用难度 | 修复方案""",
    }

    system = system_prompts.get(mode, system_prompts["code"])

    try:
        resp = requests.post(
            "https://api.minimaxi.com/anthropic/v1/messages",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "system": system,
                "messages": [{"role": "user", "content": f"工作目录: {workdir}\n\n任务:\n{task}"}],
                "max_tokens": 16384,
            },
            timeout=180,
        )
        data = resp.json()

        if "error" in data:
            return {"success": False, "agent": "minimax", "error": data["error"]}

        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
        cost_in = COST_TABLE.get("minimax-m3", {}).get("input", 0) * tokens_in / 1_000_000
        cost_out = COST_TABLE.get("minimax-m3", {}).get("output", 0) * tokens_out / 1_000_000
        cost = cost_in + cost_out

        _track_cost("minimax", model, tokens_in, tokens_out, cost)

        content = data.get("content", [{}])[0].get("text", "")
        return {
            "success": True,
            "agent": "minimax",
            "family": "minimax",
            "model": model,
            "mode": mode,
            "output": content[:8000],
            "tokens": {"in": tokens_in, "out": tokens_out},
            "cost_rmb": round(cost, 4),
        }
    except Exception as e:
        return {"success": False, "agent": "minimax", "error": str(e)}


def run_cross_review(args: dict) -> dict:
    """跨模型交叉审查：自动选择不同家族的审查者"""
    code_path = args.get("code_path", "")
    author_family = args.get("author_family", "")
    workdir = args.get("workdir", os.getcwd())

    # 读取代码
    code = ""
    path = Path(code_path) if code_path else Path(workdir)
    if path.is_file():
        code = path.read_text()
    elif path.is_dir():
        for f in list(path.rglob("*.py")) + list(path.rglob("*.ts")) + list(path.rglob("*.js")) + list(path.rglob("*.go")) + list(path.rglob("*.java")):
            rel = f.relative_to(path)
            content = f.read_text()
            code += f"\n// {rel}\n{content}\n"
            if len(code) > 50000:
                code += "\n// ... (截断, 总代码量超出 50000 字符)"
                break

    if not code:
        return {"success": False, "error": "未找到可审查的代码文件"}

    # 自动选择不同家族的审查者
    reviewer_map = {
        "openai":    {"agent": "minimax",  "fn": run_minimax, "mode": "review"},
        "deepseek":  {"agent": "minimax",  "fn": run_minimax, "mode": "review"},
        "minimax":   {"agent": "deepseek", "fn": run_deepseek, "mode": "review"},
        "anthropic": {"agent": "minimax",  "fn": run_minimax, "mode": "review"},
    }

    reviewer = reviewer_map.get(author_family)
    if not reviewer:
        return {"success": False, "error": f"未知的作者家族: {author_family}"}

    review_task = f"""请审查以下由 {author_family} 家族模型生成的代码。

{code[:40000]}

审查要求: 对每个发现给出 严重程度 | 文件位置 | 问题描述 | 修复建议"""

    if reviewer["agent"] == "minimax":
        result = reviewer["fn"](review_task, str(path.parent), mode="review")
    else:
        result = reviewer["fn"](review_task, str(path.parent))

    result["reviewer_family"] = FAMILY_MAP.get(reviewer["agent"], reviewer["agent"])
    result["author_family"] = author_family
    return result


def run_openrouter_fallback(task: str, workdir: str) -> dict:
    """OpenRouter 兜底 — 仅在 CC Switch 不可用时使用"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"success": False, "error": "未设置 OPENROUTER_API_KEY (兜底不可用)"}

    import requests

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-5",
                "messages": [{"role": "user", "content": task}],
                "max_tokens": 8192,
            },
            timeout=120,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        cost = data.get("usage", {}).get("total_tokens", 0) * 21.0 / 1_000_000
        _track_cost("openrouter", "claude-sonnet-5", 0, 0, cost)

        return {
            "success": True,
            "agent": "openrouter",
            "family": "anthropic",
            "model": "claude-sonnet-5",
            "output": content[:8000],
            "cost_rmb": round(cost, 4),
        }
    except Exception as e:
        return {"success": False, "agent": "openrouter", "error": str(e)}


# ============================================================
# MCP Server 主循环
# ============================================================

def handle_request(req: dict) -> dict:
    """处理 MCP JSON-RPC 请求"""
    req_id = req.get("id")
    method = req.get("method")

    # ---- tools/list ----
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "codex_execute",
                        "description": "调用 Codex CLI (GPT-5-Codex) 执行编码任务。"
                                       "OpenAI 家族。成本: ¥0 (桌面端会员已付)。"
                                       "适用: 主力开发、快速实现、批量操作、CI 修复。"
                                       "返回: 变更摘要 + 测试状态 + 信心度。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "编码任务描述 (中文)"},
                                "workdir": {"type": "string", "description": "项目工作目录绝对路径"},
                                "model": {"type": "string", "default": "gpt-5-codex"},
                            },
                            "required": ["task", "workdir"],
                        },
                    },
                    {
                        "name": "deepseek_execute",
                        "description": "调用 DeepSeek V4 API 执行编码任务。"
                                       "DeepSeek 家族。成本: 极低 (~¥0.9/1M tokens)。"
                                       "适用: 中文文档、长上下文分析、大批量操作、补充实现。"
                                       "返回: 变更摘要 + 测试状态 + 信心度 + Token 用量。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "编码任务描述 (中文)"},
                                "workdir": {"type": "string", "description": "项目工作目录绝对路径"},
                                "model": {"type": "string", "default": "deepseek-v4-pro"},
                            },
                            "required": ["task", "workdir"],
                        },
                    },
                    {
                        "name": "minimax_execute",
                        "description": "调用 MiniMax M3 API 执行任务。"
                                       "MiniMax 家族。成本: Token Plan Max 已付 (¥119/月, 18亿 token)。"
                                       "模式: code(编码) / review(代码审查) / adversarial(对抗验证-安全攻击视角)。"
                                       "适用: 交叉审查、安全对抗、边界测试、补充编码。"
                                       "返回: 结果文本 + Token 用量。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "任务描述 (中文)"},
                                "workdir": {"type": "string", "description": "项目工作目录绝对路径"},
                                "mode": {
                                    "type": "string",
                                    "enum": ["code", "review", "adversarial"],
                                    "default": "code",
                                    "description": "执行模式: code=编码实现, review=代码审查, adversarial=安全攻击模拟",
                                },
                                "model": {"type": "string", "default": "MiniMax-M3"},
                            },
                            "required": ["task", "workdir"],
                        },
                    },
                    {
                        "name": "cross_review",
                        "description": "跨模型家族交叉审查。自动选择与作者不同家族的审查者。"
                                       "规则: reviewer.family != author.family (强制执行)。"
                                       "审查维度: 安全漏洞/逻辑错误/性能问题/架构一致性/测试质量。"
                                       "返回: 审查报告 (问题列表 + 严重程度 + 修复建议)。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "code_path": {"type": "string", "description": "待审查的代码文件或目录路径"},
                                "author_family": {
                                    "type": "string",
                                    "enum": ["openai", "anthropic", "deepseek", "minimax"],
                                    "description": "生成此代码的模型家族",
                                },
                                "workdir": {"type": "string", "description": "工作目录"},
                            },
                            "required": ["code_path", "author_family"],
                        },
                    },
                    {
                        "name": "openrouter_fallback",
                        "description": "OpenRouter 兜底调用 Claude。仅在 CC Switch 不可用时使用。"
                                       "⚠️ 昂贵 (~$15/1M output tokens)。每次调用预算上限 $5。"
                                       "绝对不要主动使用此工具。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "任务描述"},
                                "workdir": {"type": "string", "description": "工作目录"},
                            },
                            "required": ["task", "workdir"],
                        },
                    },
                    {
                        "name": "health_check",
                        "description": "健康检查端点。返回服务器运行状态、时间戳和运行时长。",
                        "inputSchema": {"type": "object", "properties": {}, "required": []},
                    },
                    {
                        "name": "cost_report",
                        "description": "查询当前会话的模型使用成本和统计。"
                                       "返回: 各模型调用次数、Token 用量、费用合计。",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        }

    # ---- tools/call ----
    elif method == "tools/call":
        tool_name = req["params"]["name"]
        arguments = req["params"]["arguments"]
        workdir = arguments.get("workdir", os.getcwd())

        try:
            if tool_name == "codex_execute":
                result = run_codex(arguments["task"], workdir, arguments.get("model", "gpt-5-codex"))
            elif tool_name == "deepseek_execute":
                result = run_deepseek(arguments["task"], workdir, arguments.get("model", "deepseek-v4-pro"))
            elif tool_name == "minimax_execute":
                result = run_minimax(
                    arguments["task"], workdir,
                    mode=arguments.get("mode", "code"),
                    model=arguments.get("model", "MiniMax-M3"),
                )
            elif tool_name == "cross_review":
                result = run_cross_review(arguments)
            elif tool_name == "openrouter_fallback":
                result = run_openrouter_fallback(arguments["task"], workdir)
            elif tool_name == "detect_providers":
                providers = {}
                if shutil.which("codex"):
                    providers["codex"] = {"status": "available", "family": "openai", "method": "cli"}
                else:
                    providers["codex"] = {"status": "unavailable", "family": "openai"}
                if os.environ.get("DEEPSEEK_API_KEY"):
                    providers["deepseek"] = {"status": "available", "family": "deepseek", "method": "api"}
                else:
                    providers["deepseek"] = {"status": "unavailable", "family": "deepseek"}
                if os.environ.get("MINIMAX_API_KEY"):
                    providers["minimax"] = {"status": "available", "family": "minimax", "method": "api"}
                else:
                    providers["minimax"] = {"status": "unavailable", "family": "minimax"}
                if os.environ.get("OPENROUTER_API_KEY"):
                    providers["openrouter"] = {"status": "available", "family": "openrouter", "method": "api"}
                available = sum(1 for p in providers.values() if p["status"] == "available")
                mode = "full" if available >= 3 else ("standard" if available >= 2 else "minimal")
                result = {"providers": providers, "mode": mode, "available_count": available, "success": True}
            elif tool_name == "health_check":
                result = {
                    "status": "ok",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "uptime_seconds": round(time.time() - _start_time, 2),
                    "version": VERSION,
                    "success": True,
                }
            elif tool_name == "cost_report":
                result = get_cost_report()
            else:
                result = {"success": False, "error": f"未知工具: {tool_name}"}

        except Exception as e:
            result = {"success": False, "error": str(e)}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            },
        }

    # ---- 未知方法 ----
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}


def get_cost_report() -> dict:
    """生成成本报告"""
    total = sum(item.get("cost_rmb", 0) for item in _cost_log)
    by_agent = {}
    for item in _cost_log:
        agent = item["agent"]
        if agent not in by_agent:
            by_agent[agent] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_rmb": 0}
        by_agent[agent]["calls"] += 1
        by_agent[agent]["tokens_in"] += item.get("tokens_in", 0)
        by_agent[agent]["tokens_out"] += item.get("tokens_out", 0)
        by_agent[agent]["cost_rmb"] += item.get("cost_rmb", 0)

    return {
        "success": True,
        "summary": {
            "total_cost_rmb": round(total, 4),
            "total_calls": len(_cost_log),
            "by_agent": by_agent,
        },
        "detail": _cost_log[-20:],  # 最近 20 条
    }


def main():
    """MCP stdio 主循环"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line.strip())
            response = handle_request(request)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except BrokenPipeError:
            break
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": None,
            }
            try:
                sys.stdout.write(json.dumps(error_resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except BrokenPipeError:
                break


if __name__ == "__main__":
    main()
