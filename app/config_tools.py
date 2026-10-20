"""Deterministic config helpers: line numbering, quick facts, evidence grounding.

These run without any model so the LLM's claims can be checked against the
actual config text. A verdict that cites config lines which don't exist is
downgraded — the model never gets the last word on evidence.
"""
from __future__ import annotations

import re


def number_lines(text: str) -> str:
    return "\n".join(f"{i:>4}| {line}" for i, line in enumerate(text.splitlines(), 1))


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def quick_facts(text: str) -> dict:
    """Vendor / OS / version / hostname from obvious markers (no AI)."""
    facts = {"vendor": "unknown", "os_family": "unknown", "version": None, "hostname": None}
    if re.search(r"^set deviceconfig|^sw-version:", text, re.M) or "<config version" in text:
        facts.update(vendor="paloalto", os_family="PAN-OS")
        m = re.search(r"^sw-version:\s*(\S+)", text, re.M)
        if m:
            facts["version"] = m.group(1)
        m = re.search(r"hostname\s+(\S+)", text)
        if m:
            facts["hostname"] = m.group(1)
    elif re.search(r"^:?\s*ASA Version\s+(\S+)", text, re.M):
        facts.update(vendor="cisco", os_family="ASA")
        facts["version"] = re.search(r"ASA Version\s+(\S+)", text).group(1)
    elif re.search(r"Cisco IOS XE|^version 1[6-9]\.", text, re.M):
        facts.update(vendor="cisco", os_family="IOS-XE")
        m = re.search(r"Version\s+(\d+\.\d+\.\d+\w*)", text)
        facts["version"] = m.group(1) if m else None
    elif re.search(r"^version \d+\.\d+", text, re.M):
        facts.update(vendor="cisco", os_family="IOS")
    if not facts["hostname"]:
        m = re.search(r"^hostname\s+(\S+)", text, re.M)
        if m:
            facts["hostname"] = m.group(1)
    return facts


def validate_evidence(config_text: str, evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split model-cited evidence into (verified, rejected).

    An item is verified if its text matches the config line it cites, or if the
    exact text exists elsewhere in the config (line number is corrected).
    """
    lines = config_text.splitlines()
    norm = [normalize(l) for l in lines]
    good, bad = [], []
    for item in evidence or []:
        text = normalize(str(item.get("text", "")))
        if not text:
            bad.append(item)
            continue
        try:
            n = int(item.get("line", 0))
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= len(lines) and (norm[n - 1] == text or text in norm[n - 1]):
            good.append({"line": n, "text": lines[n - 1].strip()})
            continue
        hit = next((i for i, l in enumerate(norm) if text and (l == text or text in l)), None)
        if hit is not None:
            good.append({"line": hit + 1, "text": lines[hit].strip(), "line_corrected": True})
        else:
            bad.append(item)
    return good, bad


SEVERITY_WEIGHT = {"critical": 10, "high": 7, "medium": 4, "low": 2}
VERDICT_WEIGHT = {"EXPOSED": 1.0, "NEEDS_REVIEW": 0.5, "NOT_EXPOSED": 0.0}


def risk_score(severity: str, verdict: str, kev: bool, internet_facing: bool) -> float:
    """0–100 deterministic priority score used to sort findings."""
    base = SEVERITY_WEIGHT.get((severity or "").lower(), 4) * 7
    score = base * VERDICT_WEIGHT.get(verdict, 0.5)
    if kev:
        score += 20 * VERDICT_WEIGHT.get(verdict, 0.5)
    if internet_facing:
        score += 10 * VERDICT_WEIGHT.get(verdict, 0.5)
    return round(min(score, 100), 1)
