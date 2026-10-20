"""Advisory hunting with Tavily (live web), plus a labeled offline pack for demos."""
from __future__ import annotations

import json
import os
from pathlib import Path

VENDOR_DOMAINS = {
    "cisco": ["sec.cloudapps.cisco.com", "tools.cisco.com", "cisco.com"],
    "paloalto": ["security.paloaltonetworks.com", "paloaltonetworks.com"],
    "fortinet": ["fortiguard.com", "fortinet.com"],
    "juniper": ["supportportal.juniper.net", "juniper.net"],
}
COMMON_DOMAINS = ["cisa.gov", "nvd.nist.gov"]

OFFLINE_PACK = Path(__file__).resolve().parent.parent / "samples" / "advisories_offline.json"


class AdvisoryHunter:
    """Finds candidate advisories for a (vendor, os_family, version)."""

    def __init__(self, tavily_key: str | None = None):
        key = tavily_key or os.getenv("TAVILY_API_KEY")
        self.client = None
        if key:
            from tavily import TavilyClient
            self.client = TavilyClient(api_key=key)

    @property
    def live(self) -> bool:
        return self.client is not None

    def queries_for(self, vendor: str, os_family: str, version: str | None, focus: str | None) -> list[str]:
        v = version or ""
        qs = [
            f"{vendor} {os_family} {v} critical security advisory vulnerability",
            f"{os_family} {v} actively exploited CVE CISA known exploited",
        ]
        if focus:
            qs.insert(0, f"{focus} {os_family} advisory affected versions workaround")
        return qs

    def search(self, vendor: str, os_family: str, version: str | None, focus: str | None = None) -> list[dict]:
        """Return a de-duplicated list of {url,title,content} sources."""
        if not self.live:
            return []
        domains = VENDOR_DOMAINS.get(vendor, []) + COMMON_DOMAINS
        seen, sources = set(), []
        for q in self.queries_for(vendor, os_family, version, focus):
            res = self.client.search(query=q, search_depth="advanced", max_results=6,
                                     include_domains=domains)
            for r in res.get("results", []):
                url = r.get("url")
                if url and url not in seen:
                    seen.add(url)
                    sources.append({"url": url, "title": r.get("title", ""),
                                    "content": (r.get("content") or "")[:1800]})
        return sources[:10]


def offline_advisories(os_family: str) -> list[dict]:
    """Bundled reference advisories for the offline demo (clearly labeled in UI)."""
    data = json.loads(OFFLINE_PACK.read_text())
    out = []
    for a in data["advisories"]:
        if a["os_family"].lower() == (os_family or "").lower():
            out.append({**a, "source": "offline-pack"})
    return out
