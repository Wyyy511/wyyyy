from __future__ import annotations
import json
import os
import re
from typing import Any
import requests

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"


def configured() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def _post(messages: list[dict[str, Any]], *, temperature: float = 0.15, max_tokens: int = 2200, json_mode: bool = False) -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    base = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload: dict[str, Any] = {
        "model": model_name(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    resp = requests.post(
        base + "/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def chat(system_prompt: str, user_prompt: str, fallback: str) -> tuple[str, dict[str, Any]]:
    """Generate language only. Numeric risk values must already exist in tool output."""
    if not configured():
        return fallback, {"provider": "local_fallback", "model": None, "used": False}
    try:
        text = _post([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        return text, {"provider": "DeepSeek", "model": model_name(), "used": True}
    except Exception as exc:
        return fallback, {"provider": "local_fallback", "model": model_name(), "used": False, "error": str(exc)[:300]}


def _json_from_text(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def classify_intent(message: str) -> dict[str, Any] | None:
    """Use DeepSeek only for intent/parameter understanding, never for risk calculation."""
    if not configured() or not (message or "").strip():
        return None
    sys = (
        "你是上游供应链水风险 AI Agent 的任务路由器。只做任务识别和情景参数抽取，不计算任何风险数字。"
        "只输出JSON对象，不要Markdown。"
        "intent只能是 analyze、scenario、explain、data_help、export、general。"
        "scenario_type只能是 PeakSeason、AqueductFuture、ExtremeDrought、NodeFailure 或 null。"
        "可选字段：material(甘蔗/甜菜/大豆或null)、year(整数或null)、path(BAU/OPT/PES或null)、"
        "failure_fraction(0-1或null)、inventory(0-1或null)。"
        "如果用户说分析上传材料或当前风险，intent=analyze；如果问缺什么数据或模板，intent=data_help；"
        "如果明确问情景变化，intent=scenario；如果要求下载报告，intent=export。"
    )
    try:
        raw = _post([
            {"role": "system", "content": sys},
            {"role": "user", "content": message},
        ], temperature=0.0, max_tokens=500, json_mode=True)
        obj = _json_from_text(raw)
        if not obj or obj.get("intent") not in {"analyze", "scenario", "explain", "data_help", "export", "general"}:
            return None
        if obj.get("scenario_type") not in {None, "PeakSeason", "AqueductFuture", "ExtremeDrought", "NodeFailure"}:
            obj["scenario_type"] = None
        return obj
    except Exception:
        return None


def extract_supply_chain(text: str) -> dict[str, Any] | None:
    """Extract candidate enterprise/material/node/procurement fields from report text.
    Output is candidate data only and must be confirmed before deterministic calculation.
    """
    if not configured() or not (text or "").strip():
        return None
    excerpt = text[:45000]
    sys = (
        "你是供应链资料结构化抽取工具。只从用户原文抽取，不猜测、不补齐。"
        "请只输出JSON，不要Markdown。结构：{enterprise:null或字符串, records:[...] }。"
        "每条records字段：material,node_id,node_name,purchase_weight,year,evidence,confidence。"
        "material只在原文明确时填甘蔗/甜菜/大豆或原材料原名；purchase_weight统一为0-1，原文没有就null；"
        "node_id只有原文明确包含项目节点编号时填写，否则null；node_name填写供应地/省州/国家/供应节点原文；"
        "evidence必须是支持该条记录的简短原文片段；confidence只可High/Medium/Low。"
        "不要把国家均值、推测值或常识当作企业采购事实。"
    )
    try:
        raw = _post([
            {"role": "system", "content": sys},
            {"role": "user", "content": "请抽取以下报告中的上游采购/供应链候选信息：\n" + excerpt},
        ], temperature=0.0, max_tokens=2200, json_mode=True)
        obj = _json_from_text(raw)
        if not obj or not isinstance(obj.get("records"), list):
            return None
        return obj
    except Exception:
        return None


def general_guidance(message: str, fallback: str) -> tuple[str, dict[str, Any]]:
    sys = (
        "你是科技型农食企业上游供应链水风险分析助手。回答用户关于如何准备数据、如何使用系统、"
        "Baseline/Scenario适用条件和结果含义的问题。"
        "不得凭空生成企业采购比例、地点WS/DR/SV、材料BWD/DYS/CTS/OA、PRWI或情景数值。"
        "如果用户想要正式风险分析，应引导其上传ESG/PDF/Word/Excel/CSV或下载标准模板。"
        "输出简洁中文。"
    )
    return chat(sys, message, fallback)


def analyze_tool_result(*, user_question: str, baseline: dict | None = None, scenario: dict | None = None,
                        validation: dict | None = None, fallback: str = "") -> tuple[str, dict[str, Any]]:
    """Explain deterministic tool output. DeepSeek may interpret and prioritize, but may not alter numbers."""
    if not configured():
        return fallback, {"provider": "local_fallback", "model": None, "used": False}
    payload = {
        "user_question": user_question,
        "validation": validation or {},
        "baseline": baseline or {},
        "scenario": scenario or {},
    }
    # Keep prompts bounded while preserving the official tool JSON fields used for explanation.
    raw_payload = json.dumps(payload, ensure_ascii=False, default=str)
    if len(raw_payload) > 42000:
        raw_payload = raw_payload[:42000]
    sys = (
        "你是 WaterPulse 上游供应链水风险决策助手。你只能解释给定的确定性工具结果，不能重新计算或修改任何数值。"
        "所有 PRWI、Coverage、节点风险、节点贡献、Scenario 变化、供应缺口和集中度数字必须逐字沿用输入JSON；"
        "如果某个数字不存在，就明确说当前工具结果没有提供，绝对不要猜。"
        "必须区分：①用户/原始资料事实；②确定性程序计算结论；③Scenario假设；④管理建议。"
        "优先解释总体风险、Top Risk Node、Top Contribution Node、WS/DR/SV主要驱动、Coverage/Unknown/Proxy、"
        "情景前后变化和数据缺口，并给采购、ESG或风险管理人员可执行但非自动执行的建议。"
        "如果数据状态为 insufficient/conflict/error，应说明原因并停止给正式风险结论。"
        "用自然、清晰、面向企业用户的中文回答；不要暴露后台12步workflow或代码细节。"
    )
    try:
        text = _post([
            {"role": "system", "content": sys},
            {"role": "user", "content": raw_payload},
        ], temperature=0.1, max_tokens=1800)
        return text, {"provider": "DeepSeek", "model": model_name(), "used": True}
    except Exception as exc:
        return fallback, {"provider": "local_fallback", "model": model_name(), "used": False, "error": str(exc)[:300]}
