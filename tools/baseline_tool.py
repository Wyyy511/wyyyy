from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Any
import pandas as pd
from core.paths import ENGINE_DIR
from tools.query_adapter import lookup_water_risk, lookup_material_parameters

# Load D's frozen deterministic API. Its internal import expects the engine directory on sys.path.
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
spec = importlib.util.spec_from_file_location("d_baseline_api", ENGINE_DIR / "baseline_api.py")
dapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dapi)


def _meta(source_ref=None, data_status=None, confidence=None, approved_proxy=False, proxy_value=None):
    return {
        "source_ref": source_ref,
        "data_status": data_status,
        "confidence": confidence,
        "approved_proxy": bool(approved_proxy),
        "proxy_value": proxy_value,
    }


def build_baseline_request(df: pd.DataFrame, *, run_id: str = "agent_run", data_version: str = "integrated-mvp-2026-09-06") -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if df is None or df.empty:
        return {"run_id": run_id, "enterprise_id": "USER_ENTERPRISE", "data_version": data_version, "materials": []}, ["没有已确认采购数据"]

    enterprise = str(df.iloc[0].get("enterprise") or "USER_ENTERPRISE")
    materials = []
    for mat, g in df.groupby("material", dropna=False):
        mat = str(mat or "").strip()
        if not mat:
            continue
        weights = pd.to_numeric(g["purchase_weight"], errors="coerce")
        sum_w = float(weights.fillna(0).sum())
        U = max(0.0, 1.0 - sum_w)
        mp = lookup_material_parameters(mat)
        mpd = mp.get("data") or {}
        warnings.extend(mp.get("warnings", []))
        m_field_meta = {}
        for f in ["BWD", "DYS", "CTS", "OA"]:
            m_field_meta[f] = _meta(
                source_ref=mpd.get("source_ref"),
                data_status=(mpd.get("data_type") or {}).get(f),
                confidence=(mpd.get("confidence") or {}).get(f),
            )
        nodes = []
        for _, r in g.iterrows():
            nid = str(r.get("node_id") or "").strip()
            wr = lookup_water_risk(nid)
            wrd = wr.get("data") or {}
            warnings.extend(wr.get("warnings", []))
            vals = wrd.get("values") or {}
            def value(name):
                return (vals.get(name) or {}).get("value")
            nd = {
                "node_id": nid or None,
                "node_name": str(r.get("node_name") or wrd.get("node_name") or ""),
                "reference_period": wrd.get("reference_period") or str(r.get("year") or ""),
                "W": None if pd.isna(r.get("purchase_weight")) else float(r.get("purchase_weight")),
                "WS": value("WS"), "WS_unit": "aqueduct_score_0_5",
                "SV": value("SV"), "SV_unit": "aqueduct_score_0_5",
                "DR": value("DR"),
                "field_meta": {
                    "W": _meta(source_ref="user_confirmed_input", data_status="V", confidence=str(r.get("confidence") or "High")),
                    "WS": _meta(source_ref=wrd.get("source_ref"), data_status=wrd.get("data_type"), confidence=wrd.get("confidence")),
                    "SV": _meta(source_ref=wrd.get("source_ref"), data_status=wrd.get("data_type"), confidence=wrd.get("confidence")),
                    "DR": _meta(source_ref=wrd.get("source_ref"), data_status=wrd.get("data_type"), confidence=wrd.get("confidence")),
                },
            }
            nodes.append(nd)
        materials.append({
            "material": mat,
            "U": U,
            "material_params": {
                "BWD": mpd.get("BWD"), "DYS": mpd.get("DYS"), "CTS": mpd.get("CTS"), "OA": mpd.get("OA"),
            },
            "field_meta": m_field_meta,
            "nodes": nodes,
        })
    request = {
        "run_id": run_id,
        "enterprise_id": enterprise,
        "data_version": data_version,
        "theta": {"WS": 1/3, "DR": 1/3, "SV": 1/3},
        "materials": materials,
    }
    return request, list(dict.fromkeys(warnings))


def _wrapper_from_d(raw: dict, request: dict, extra_warnings: list[str]) -> dict:
    rows = []
    summaries = []
    req_node_meta = {}
    for mat in request.get("materials", []):
        for nd in mat.get("nodes", []):
            req_node_meta[(mat.get("material"), nd.get("node_id"))] = nd
    for m in raw.get("materials", []):
        path = m.get("path_contribution") or {}
        summaries.append({
            "material": m.get("material"), "enterprise": raw.get("enterprise_id"),
            "PRWI": m.get("PRWI"), "KnownRisk": m.get("PRWI"),
            "R_max": 1.0, "PRWI_lower": m.get("PRWI_lower"), "PRWI_upper": m.get("PRWI_upper"),
            "Coverage": m.get("procurement_coverage"), "scored_coverage": m.get("scored_coverage"),
            "unknown_share_U": m.get("unknown_share"),
            "path_contrib_WS": path.get("WS", 0), "path_contrib_DR": path.get("DR", 0), "path_contrib_SV": path.get("SV", 0),
            "n_nodes": len(m.get("nodes", [])), "overall_confidence": m.get("overall_confidence"),
            "calculation_mode": m.get("calculation_mode"),
        })
        for nd in m.get("nodes", []):
            source = req_node_meta.get((m.get("material"), nd.get("node_id")), {})
            paths = {"WS": nd.get("Path_WS"), "DR": nd.get("Path_DR"), "SV": nd.get("Path_SV")}
            dom = max(paths, key=lambda k: paths[k] if paths[k] is not None else -1)
            rows.append({
                "material": m.get("material"), "enterprise": raw.get("enterprise_id"),
                "node_id": nd.get("node_id"), "node_name": nd.get("node_name"), "pfaf_id": None,
                "data_type": (source.get("field_meta") or {}).get("WS", {}).get("data_status"),
                "ws_norm": nd.get("WS_norm"), "sv_norm": nd.get("SV_norm"), "dr": nd.get("DR"),
                "bwd": nd.get("BWD"), "dys": nd.get("DYS"), "cts": nd.get("CTS"), "oa": nd.get("OA"),
                "weight": nd.get("W"), "path_ws": nd.get("Path_WS"), "path_dr": nd.get("Path_DR"), "path_sv": nd.get("Path_SV"),
                "R": nd.get("R"), "C": nd.get("C"), "dominant_path": dom,
                "overall_confidence": (nd.get("confidence") or {}).get("overall"),
                "contribution_share": nd.get("contribution_share"), "rank_contribution": nd.get("rank"), "rank_risk": None,
                "status": nd.get("node_status"),
            })
    nodes = pd.DataFrame(rows)
    if not nodes.empty:
        nodes["rank_risk"] = nodes.groupby("material")["R"].rank(ascending=False, method="min")
    summary = pd.DataFrame(summaries)
    return {
        "status": raw.get("status"),
        "calculation_mode": raw.get("calculation_mode"),
        "data": None if raw.get("status") in {"error", "conflict", "insufficient"} and not summaries else {"summary": summary, "nodes": nodes, "raw": raw},
        "warnings": list(dict.fromkeys((raw.get("warnings") or []) + extra_warnings)),
        "data_gaps": raw.get("missing_fields") or raw.get("errors") or raw.get("conflicts") or [],
        "source_refs": raw.get("source_refs") or [],
        "data_version": raw.get("data_version"),
        "model_version": raw.get("engine_version"),
        "engine_version": raw.get("engine_version"),
        "formula_version": raw.get("formula_version"),
        "parameter_version": raw.get("parameter_version"),
        "input_hash": raw.get("input_hash"),
        "run_id": raw.get("run_id"),
        "raw": raw,
    }


def calculate_baseline(df: pd.DataFrame, *, run_id: str = "agent_run") -> dict:
    request, warnings = build_baseline_request(df, run_id=run_id)
    raw = dapi.calculate_baseline(request)
    out = _wrapper_from_d(raw, request, warnings)
    out["request"] = request
    return out
