"""Offline tests: deterministic helpers + full pipeline with a fake Nemotron router."""
from pathlib import Path

from app.advisories import offline_advisories
from app.config_tools import quick_facts, validate_evidence, risk_score
from app.llm import Ledger, CallRecord, extract_json
from app.pipeline import Pipeline
from app.report import to_markdown

CFG = Path(__file__).resolve().parent.parent / "samples" / "configs"


def test_quick_facts():
    assert quick_facts((CFG / "edge-rtr-01.txt").read_text())["version"] == "17.06.05"
    pa = quick_facts((CFG / "fw-edge-01.txt").read_text())
    assert (pa["os_family"], pa["version"]) == ("PAN-OS", "11.1.2")
    asa = quick_facts((CFG / "asa-vpn-01.txt").read_text())
    assert (asa["os_family"], asa["version"], asa["hostname"]) == ("ASA", "9.16.4", "asa-vpn-01")


def test_evidence_grounding():
    text = (CFG / "edge-rtr-01.txt").read_text()
    good, bad = validate_evidence(text, [
        {"line": 1, "text": "ip http server"},          # wrong line -> corrected
        {"line": 99, "text": "ip http fake-feature"},   # hallucinated -> rejected
    ])
    assert len(good) == 1 and good[0]["line_corrected"] and len(bad) == 1


def test_extract_json_handles_think_and_fences():
    assert extract_json('<think>hmm</think>```json\n{"a": 1}\n```') == {"a": 1}


def test_risk_score_orders():
    assert risk_score("critical", "EXPOSED", True, True) > risk_score("critical", "NOT_EXPOSED", True, True)


class FakeRouter:
    """Mimics Nemotron replies so the orchestration can be tested without API keys."""
    def __init__(self):
        self.ledger = Ledger()

    def call(self, tier, system, user, purpose, **kw):
        self.ledger.add(CallRecord(tier, "fake", purpose, 100, 50, 5, True))
        if purpose.startswith("fingerprint"):
            return {"vendor": "cisco", "features": [], "internet_facing_services": ["https"]}
        if purpose.startswith("judge"):
            if "edge-rtr-01" in purpose:
                return {"verdict": "EXPOSED", "confidence": .9, "reasoning": "web ui on",
                        "evidence": [{"line": 33, "text": "ip http server"}]}
            if "fw-edge-01" in purpose:  # claims exposure with a hallucinated line
                return {"verdict": "EXPOSED", "confidence": .8, "reasoning": "x",
                        "evidence": [{"line": 2, "text": "set imaginary thing"}]}
            return {"verdict": "NOT_EXPOSED", "confidence": .9, "reasoning": "http disabled",
                    "evidence": [{"line": 21, "text": "no ip http server"}]}
        if purpose.startswith("remediate"):
            return {"summary": "s", "interim_mitigation": ["no ip http server"], "verification": [],
                    "rollback": [], "permanent_fix": "upgrade", "business_impact": "", "change_risk": "low"}
        return {"headline": "h", "next_24h": [], "this_week": [], "noise_avoided": ""}


class NoTavily:
    live = False


def test_pipeline_end_to_end():
    configs = {p.name: p.read_text() for p in CFG.glob("*.txt")}
    res = Pipeline(FakeRouter(), NoTavily()).run(configs)
    by = {f["device"]: f["verdict"]["verdict"] for f in res["findings"]}
    assert by["edge-rtr-01"] == "EXPOSED"
    assert by["branch-rtr-02"] == "NOT_EXPOSED"
    assert by["fw-edge-01"] == "NEEDS_REVIEW"  # downgraded: no verifiable evidence
    assert res["findings"][0]["device"] == "edge-rtr-01"
    assert res["usage"]["savings_pct"] > 0
    assert "ExposureLens scan report" in to_markdown(res)
    assert len(offline_advisories("IOS-XE")) == 1
