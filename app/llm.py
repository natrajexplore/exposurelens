"""Nemotron tier router for Nebius Token Factory (OpenAI-compatible API).

Every model call goes through `NemotronRouter.call(tier, ...)` so the app can
show judges exactly which Nemotron tier did which job, with tokens, latency and
an estimated cost compared to running everything on Ultra.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict

BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")

# Exact IDs differ per account/region: run `python scripts/list_models.py`
# and set these in .env to the IDs your Token Factory catalog shows.
TIER_MODELS = {
    "nano": os.getenv("NEMOTRON_NANO_MODEL", "nvidia/Nemotron-3-Nano-30B-A3B"),
    "super": os.getenv("NEMOTRON_SUPER_MODEL", "nvidia/Nemotron-3-Super-120B-A12B"),
    "ultra": os.getenv("NEMOTRON_ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550B-A55B"),
}

# Estimated USD per 1M tokens (input, output). Override with env if prices change.
def _price(tier: str, default_in: float, default_out: float) -> tuple[float, float]:
    raw = os.getenv(f"PRICE_{tier.upper()}")  # e.g. "0.05,0.20"
    if raw:
        a, b = raw.split(",")
        return float(a), float(b)
    return default_in, default_out

TIER_PRICES = {
    "nano": _price("nano", 0.05, 0.20),
    "super": _price("super", 0.09, 0.45),
    "ultra": _price("ultra", 0.60, 2.40),
}

# What each tier is used for (shown in the UI and README).
TIER_ROLES = {
    "nano": "Config fingerprinting (fast, high-volume extraction)",
    "super": "Advisory structuring, remediation drafting, fleet brief",
    "ultra": "Exposure verdicts: does THIS config meet THIS advisory's exploit conditions?",
}


@dataclass
class CallRecord:
    tier: str
    model: str
    purpose: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    ok: bool
    error: str | None = None

    @property
    def cost(self) -> float:
        pin, pout = TIER_PRICES[self.tier]
        return (self.prompt_tokens * pin + self.completion_tokens * pout) / 1e6

    @property
    def cost_if_ultra(self) -> float:
        pin, pout = TIER_PRICES["ultra"]
        return (self.prompt_tokens * pin + self.completion_tokens * pout) / 1e6


@dataclass
class Ledger:
    calls: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, rec: CallRecord) -> None:
        with self._lock:
            self.calls.append(rec)

    def summary(self) -> dict:
        tiers = {}
        for t in TIER_MODELS:
            cs = [c for c in self.calls if c.tier == t]
            tiers[t] = {
                "model": TIER_MODELS[t],
                "role": TIER_ROLES[t],
                "calls": len(cs),
                "prompt_tokens": sum(c.prompt_tokens for c in cs),
                "completion_tokens": sum(c.completion_tokens for c in cs),
                "avg_latency_ms": int(sum(c.latency_ms for c in cs) / len(cs)) if cs else 0,
                "est_cost_usd": round(sum(c.cost for c in cs), 6),
            }
        actual = sum(c.cost for c in self.calls)
        all_ultra = sum(c.cost_if_ultra for c in self.calls)
        return {
            "tiers": tiers,
            "total_calls": len(self.calls),
            "est_cost_usd": round(actual, 6),
            "est_cost_if_all_ultra_usd": round(all_ultra, 6),
            "savings_pct": round(100 * (1 - actual / all_ultra), 1) if all_ultra else 0.0,
            "errors": [asdict(c) for c in self.calls if not c.ok],
        }


_THINK = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str) -> dict:
    """Parse JSON from a model reply, tolerating <think> blocks and ``` fences."""
    text = _THINK.sub("", text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class NemotronRouter:
    """Routes calls to Nano / Super / Ultra on Nebius Token Factory."""

    def __init__(self, api_key: str | None = None, ledger: Ledger | None = None):
        from openai import OpenAI  # imported lazily so tests run without the SDK

        key = api_key or os.getenv("NEBIUS_API_KEY")
        if not key:
            raise RuntimeError("NEBIUS_API_KEY is not set (see .env.example)")
        self.client = OpenAI(base_url=BASE_URL, api_key=key, timeout=180, max_retries=2)
        self.ledger = ledger or Ledger()
        self._json_mode_ok: dict[str, bool] = {}

    def call(self, tier: str, system: str, user: str, purpose: str,
             max_tokens: int = 2048, temperature: float = 0.1) -> dict:
        model = TIER_MODELS[tier]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kwargs = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        t0 = time.time()
        last_err = None
        for attempt in range(2):
            try:
                use_json = self._json_mode_ok.get(model, True)
                if use_json:
                    try:
                        resp = self.client.chat.completions.create(
                            response_format={"type": "json_object"}, **kwargs)
                    except Exception as e:  # model may not support JSON mode
                        if "response_format" in str(e) or "json" in str(e).lower():
                            self._json_mode_ok[model] = False
                            resp = self.client.chat.completions.create(**kwargs)
                        else:
                            raise
                else:
                    resp = self.client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                data = extract_json(content)
                u = resp.usage
                self.ledger.add(CallRecord(tier, model, purpose,
                                           getattr(u, "prompt_tokens", 0) or 0,
                                           getattr(u, "completion_tokens", 0) or 0,
                                           int((time.time() - t0) * 1000), True))
                return data
            except Exception as e:  # retry once with a stricter reminder
                last_err = e
                messages = messages[:2] + [{"role": "user", "content":
                    "Reply again with ONLY one valid JSON object, no prose."}]
                kwargs["messages"] = messages
        self.ledger.add(CallRecord(tier, model, purpose, 0, 0,
                                   int((time.time() - t0) * 1000), False, str(last_err)[:300]))
        raise RuntimeError(f"{tier} call failed for {purpose}: {last_err}")
