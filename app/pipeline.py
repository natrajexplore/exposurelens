"""ExposureLens multi-agent pipeline.

  Fingerprint (Nemotron Nano)  ->  Advisory Hunter (Tavily + Nemotron Super)
      ->  Applicability Judge (Nemotron Ultra)  ->  Evidence Validator (deterministic)
      ->  Remediator (Nemotron Super)  ->  Fleet Brief (Nemotron Super)

Read-only by design: the app never connects to or pushes config to devices.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import prompts
from .advisories import AdvisoryHunter, offline_advisories
from .config_tools import number_lines, quick_facts, validate_evidence, risk_score

Emit = Callable[[str, str], None]  # (stage, message)


class Pipeline:
    def __init__(self, router, hunter: AdvisoryHunter, emit: Emit | None = None, workers: int = 4):
        self.llm = router
        self.hunter = hunter
        self.emit = emit or (lambda stage, msg: None)
        self.workers = workers

    # ---------- Stage 1: fingerprint ----------
    def fingerprint(self, name: str, text: str) -> dict:
        facts = quick_facts(text)
        self.emit("fingerprint", f"{name}: Nano reading config ({len(text.splitlines())} lines)")
        fp = self.llm.call("nano", prompts.FINGERPRINT,
                           f"DEVICE FILE: {name}\nDETERMINISTIC HINTS: {json.dumps(facts)}\n\nCONFIG:\n{number_lines(text)}",
                           purpose=f"fingerprint:{name}", max_tokens=2500)
        # deterministic facts win when present (model can't overwrite a parsed version)
        for k in ("vendor", "os_family", "version", "hostname"):
            if facts.get(k) not in (None, "unknown"):
                fp[k] = facts[k]
        for f in fp.get("features", []):
            f["evidence"], _ = validate_evidence(text, f.get("evidence", []))
        fp["file"] = name
        return fp

    # ---------- Stage 2: advisories ----------
    def advisories_for(self, fp: dict, focus: str | None) -> tuple[list[dict], str]:
        vendor, osf, ver = fp.get("vendor"), fp.get("os_family"), fp.get("version")
        if self.hunter.live:
            self.emit("advisories", f"Tavily searching PSIRT / CISA for {osf} {ver or ''}")
            sources = self.hunter.search(vendor, osf, ver, focus)
            if sources:
                data = self.llm.call("super", prompts.ADVISORY_STRUCTURER,
                                     f"DEVICE: vendor={vendor} os_family={osf} version={ver}\n"
                                     f"SOURCES:\n{json.dumps(sources, indent=1)}",
                                     purpose=f"advisories:{osf}", max_tokens=3000)
                urls = {s["url"] for s in sources}
                advs = [a for a in data.get("advisories", []) if a.get("url") in urls]
                for a in advs:
                    a["source"] = "tavily-live"
                if advs:
                    # curated advisories are always judged and win on overlapping CVEs (their
                    # facts are verified); live results add CVEs the curated pack doesn't cover
                    curated = offline_advisories(osf)
                    known = {c.upper() for a in curated for c in a.get("cve", [])}
                    fresh = [a for a in advs if not known & {c.upper() for c in a.get("cve", [])}]
                    return curated + fresh, "tavily-live"
            self.emit("advisories", f"No grounded live advisories for {osf}; using offline pack")
        return offline_advisories(osf), "offline-pack"

    # ---------- Stage 3+4: judge + validate ----------
    def judge(self, fp: dict, text: str, adv: dict) -> dict:
        out = self.llm.call("ultra", prompts.APPLICABILITY_JUDGE,
                            f"DEVICE FINGERPRINT:\n{json.dumps({k: fp.get(k) for k in ('vendor','os_family','version','hostname','internet_facing_services')})}\n\n"
                            f"ADVISORY:\n{json.dumps(adv, indent=1)}\n\nCONFIG:\n{number_lines(text)}",
                            purpose=f"judge:{fp['file']}:{adv.get('id')}", max_tokens=1800)
        good, bad = validate_evidence(text, out.get("evidence", []))
        out["evidence"], out["rejected_evidence"] = good, bad
        verdict = out.get("verdict", "NEEDS_REVIEW")
        if verdict not in ("EXPOSED", "NOT_EXPOSED", "NEEDS_REVIEW"):
            verdict = "NEEDS_REVIEW"
        if verdict == "EXPOSED" and not good:
            verdict = "NEEDS_REVIEW"
            out["grounding_note"] = "Downgraded: model claimed exposure but cited no verifiable config lines."
        elif bad:
            out["grounding_note"] = f"{len(bad)} cited line(s) not found in config and were discarded."
        out["verdict"] = verdict
        return out

    # ---------- Stage 5: remediate ----------
    def remediate(self, fp: dict, adv: dict, verdict: dict) -> dict:
        return self.llm.call("super", prompts.REMEDIATOR,
                             f"DEVICE: {json.dumps({k: fp.get(k) for k in ('vendor','platform','os_family','version','hostname')})}\n"
                             f"ADVISORY: {json.dumps(adv)}\nVERDICT: {json.dumps(verdict)}",
                             purpose=f"remediate:{fp['file']}:{adv.get('id')}", max_tokens=1500)

    # ---------- Orchestration ----------
    def run(self, configs: dict[str, str], focus: str | None = None) -> dict:
        t0 = time.time()
        with ThreadPoolExecutor(self.workers) as ex:
            fps = list(ex.map(lambda kv: self.fingerprint(*kv), configs.items()))

        # one advisory hunt per unique OS family + version
        adv_cache: dict[tuple, tuple[list[dict], str]] = {}
        for fp in fps:
            key = (fp.get("vendor"), fp.get("os_family"), fp.get("version"))
            if key not in adv_cache:
                adv_cache[key] = self.advisories_for(fp, focus)

        jobs = []
        for fp in fps:
            advs, _ = adv_cache[(fp.get("vendor"), fp.get("os_family"), fp.get("version"))]
            for adv in advs:
                jobs.append((fp, adv))
        self.emit("judge", f"Ultra judging {len(jobs)} device x advisory pairs against config evidence")

        def do(job):
            fp, adv = job
            v = self.judge(fp, configs[fp["file"]], adv)
            self.emit("judge", f"{fp.get('hostname') or fp['file']} / {adv.get('id')}: {v['verdict']}")
            rem = None
            if v["verdict"] in ("EXPOSED", "NEEDS_REVIEW"):
                rem = self.remediate(fp, adv, v)
            internet = bool(fp.get("internet_facing_services"))
            return {
                "device": fp.get("hostname") or fp["file"], "file": fp["file"],
                "os": f"{fp.get('os_family')} {fp.get('version') or '?'}",
                "advisory": adv, "verdict": v, "remediation": rem,
                "score": risk_score(adv.get("severity"), v["verdict"], bool(adv.get("kev")), internet),
            }

        with ThreadPoolExecutor(self.workers) as ex:
            findings = sorted(ex.map(do, jobs), key=lambda f: f["score"], reverse=True)

        counts = {k: sum(1 for f in findings if f["verdict"]["verdict"] == k)
                  for k in ("EXPOSED", "NEEDS_REVIEW", "NOT_EXPOSED")}
        self.emit("brief", "Super writing the fleet brief")
        brief = self.llm.call("super", prompts.FLEET_BRIEF, json.dumps({
            "counts": counts,
            "findings": [{"device": f["device"], "os": f["os"], "advisory": f["advisory"].get("id"),
                          "severity": f["advisory"].get("severity"), "kev": f["advisory"].get("kev"),
                          "verdict": f["verdict"]["verdict"], "reasoning": f["verdict"].get("reasoning"),
                          "score": f["score"]} for f in findings]}),
            purpose="fleet-brief", max_tokens=1200)

        return {
            "devices": fps,
            "findings": findings,
            "counts": counts,
            "brief": brief,
            "advisory_source": sorted({src for _, src in adv_cache.values()}),
            "elapsed_s": round(time.time() - t0, 1),
            "usage": self.llm.ledger.summary(),
        }
