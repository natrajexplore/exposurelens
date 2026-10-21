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


def test_budget_blocks_calls(tmp_path, monkeypatch):
    import pytest
    from app import llm
    monkeypatch.setattr(llm, "SPEND_FILE", tmp_path / "spend.json")
    llm._add_spend(0.60)
    with pytest.raises(RuntimeError, match="Budget reached"):
        llm.NemotronRouter(api_key="unused").call("nano", "s", "u", purpose="t")


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


def test_live_advisories_keep_curated():
    class LiveHunter:
        live = True
        def search(self, *a):
            return [{"url": "https://security.paloaltonetworks.com/CVE-2024-3400", "title": "", "content": ""},
                    {"url": "https://example.com/new", "title": "", "content": ""}]

    class Router(FakeRouter):
        def call(self, tier, system, user, purpose, **kw):
            if purpose.startswith("advisories"):
                return {"advisories": [
                    {"id": "live-3400", "cve": ["cve-2024-3400"], "url": "https://security.paloaltonetworks.com/CVE-2024-3400"},
                    {"id": "live-new", "cve": ["CVE-2099-0001"], "url": "https://example.com/new"},
                    {"id": "made-up", "cve": ["CVE-2099-0002"], "url": "https://not-from-tavily.example"}]}
            return super().call(tier, system, user, purpose, **kw)

    advs, src = Pipeline(Router(), LiveHunter()).advisories_for(
        {"vendor": "paloalto", "os_family": "PAN-OS", "version": "11.1.2"}, None)
    assert src == "tavily-live"
    assert [a["id"] for a in advs] == ["live-3400", "live-new"]  # curated 3400 deduped by CVE, ungrounded URL dropped

    advs, _ = Pipeline(Router(), LiveHunter()).advisories_for(
        {"vendor": "cisco", "os_family": "IOS-XE", "version": "17.06.05"}, None)
    assert "cisco-sa-iosxe-webui-privesc-j22SaA4z" in [a["id"] for a in advs]  # curated kept when live misses it


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
