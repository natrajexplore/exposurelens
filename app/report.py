"""Markdown export of a scan result (for tickets / CAB records)."""
from __future__ import annotations


def to_markdown(result: dict) -> str:
    b = result.get("brief", {})
    c = result.get("counts", {})
    u = result.get("usage", {})
    out = [
        "# ExposureLens scan report", "",
        f"**{b.get('headline', '')}**", "",
        f"Exposed: {c.get('EXPOSED', 0)} · Needs review: {c.get('NEEDS_REVIEW', 0)} · "
        f"Not exposed: {c.get('NOT_EXPOSED', 0)} · Advisory source: {', '.join(result.get('advisory_source', []))}", "",
        "## Next 24 hours", *[f"- {x}" for x in b.get("next_24h", [])], "",
        "## This week", *[f"- {x}" for x in b.get("this_week", [])], "",
        f"_Noise avoided:_ {b.get('noise_avoided', '')}", "",
        "## Findings",
    ]
    for f in result.get("findings", []):
        a, v, r = f["advisory"], f["verdict"], f.get("remediation") or {}
        out += [
            "", f"### [{v['verdict']}] {f['device']} — {a.get('title')} (score {f['score']})",
            f"- OS: {f['os']} · Severity: {a.get('severity')} · KEV: {a.get('kev')} · "
            f"CVE: {', '.join(a.get('cve', []))}",
            f"- Advisory: {a.get('url')}",
            f"- Reasoning: {v.get('reasoning', '')}",
        ]
        if v.get("evidence"):
            out.append("- Config evidence:")
            out += [f"  - line {e['line']}: `{e['text']}`" for e in v["evidence"]]
        if v.get("grounding_note"):
            out.append(f"- Grounding: {v['grounding_note']}")
        if r:
            out += ["- Proposed interim mitigation (review before applying):", "```",
                    *r.get("interim_mitigation", []), "```",
                    "- Verify:", "```", *r.get("verification", []), "```",
                    "- Rollback:", "```", *r.get("rollback", []), "```",
                    f"- Permanent fix: {r.get('permanent_fix', '')}",
                    f"- Business impact: {r.get('business_impact', '')}"]
    out += ["", "## Model usage (NVIDIA Nemotron on Nebius Token Factory)"]
    for t, s in u.get("tiers", {}).items():
        out.append(f"- {t}: {s['model']} — {s['calls']} calls, "
                   f"{s['prompt_tokens'] + s['completion_tokens']} tokens, ~${s['est_cost_usd']}")
    out.append(f"- Estimated cost ${u.get('est_cost_usd')} vs ${u.get('est_cost_if_all_ultra_usd')} "
               f"if every call used Ultra ({u.get('savings_pct')}% saved)")
    return "\n".join(out) + "\n"
