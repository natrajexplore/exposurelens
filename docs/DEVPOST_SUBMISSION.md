# Devpost submission kit

Deadline: **Fri 30 Oct 2026, 10:00 am PDT = 10:30 pm IST.** Submit by 29 Oct; don't rely on the last hour.

## Form fields

**Project name:** ExposureLens

**Tagline (≤ 200 chars):** Version scanners say you're vulnerable. ExposureLens reads your device configs with NVIDIA Nemotron and proves, line by line, whether you're actually exposed.

**Track:** Best Apps and Agents

**Built with:** nvidia-nemotron, nebius-token-factory, tavily, python, fastapi, openai-sdk, docker

## Description (paste into "About the project")

### Inspiration
When a critical network advisory drops (the IOS-XE Web UI bug, PAN-OS GlobalProtect), every network team does the same thing: export the list of devices on affected versions, then open configs one by one to see whether the vulnerable feature is even turned on. Version scanners can't answer that question, so a 200-device fleet becomes hours of manual triage during the most stressful window. I've done this triage for 10 years as a network security engineer. I wanted an agent that does it in minutes and shows its proof.

### What it does
Upload Cisco IOS-XE, ASA or PAN-OS configs. ExposureLens:
1. Fingerprints each device: OS, version, and every security-relevant feature, with the config lines that prove it.
2. Searches vendor PSIRT pages and CISA live with Tavily and structures the advisories that apply.
3. Judges each device against each advisory: is the version affected, is the vulnerable feature configured, are the exploit conditions met, is there already a mitigation?
4. Verifies every cited config line in code. An "exposed" claim without verifiable evidence is downgraded to "needs review".
5. Drafts the interim mitigation in the device's own CLI, with verification and rollback commands, plus a 24-hour action brief.

In the demo, two routers run the same vulnerable IOS-XE version. A version scanner flags both; ExposureLens marks one EXPOSED (line 32: `ip http server`) and rules the other out (line 22: `no ip http server`).

### How we built it
- **NVIDIA Nemotron 3 on Nebius Token Factory**, routed by job: **Nano** fingerprints configs in parallel, **Super** structures advisories and drafts remediation, **Ultra** makes the exposure verdicts — the one step where reasoning quality decides everything.
- **Tavily** advanced search, restricted to vendor PSIRT, CISA and NVD domains; advisories whose URL didn't come from Tavily are discarded.
- **Deterministic grounding layer** in Python: line-numbered configs, regex quick facts that override model guesses for version/OS, evidence validation, and a transparent risk score (severity, KEV, verdict, internet-facing).
- **FastAPI + single-page UI** with live agent progress and a "Which Nemotron did what" ledger showing calls, tokens, latency and cost per tier versus an all-Ultra baseline.
- **Batch job** (`jobs/nightly_scan.py`) packaged in the same Docker image for Nebius Serverless Jobs.

### Challenges
- Getting reliable JSON from reasoning models: JSON mode where supported, `<think>`-block stripping, and a single strict retry.
- Stopping confident hallucinations: the model must cite exact lines, and code checks them.
- Version strings differ between `show version` and running config; deterministic parsing wins over the model.

### Accomplishments
- A verdict you can paste into a change ticket: cited lines, advisory link, mitigation, rollback.
- Tier routing that cut estimated model cost by roughly half versus using Ultra everywhere (exact figure shown live in the app).

### What we learned
Most of the value is in the boundary between model and code: let Ultra reason, but let Python decide what counts as evidence.

### What's next
Live pulls from device inventories (NetBox, Cisco Catalyst Center, Panorama) over read-only APIs, more vendors (FortiOS, Junos), and ticket creation in ServiceNow/Jira.

## Testing instructions (for judges)
ExposureLens runs locally; there is no hosted demo. The video shows a full scan end to end.
To run it yourself you need a Nebius Token Factory API key (the Nebius Builder Program gives
free credits). A Tavily key is optional; without it, advisories come from a bundled, clearly
labelled offline pack.

1. Start it with the pre-built image (Docker), no clone needed:
   ```bash
   docker run --rm -p 127.0.0.1:8000:8000 -e NEBIUS_API_KEY=your_key -e TAVILY_API_KEY=your_key ghcr.io/natrajexplore/exposurelens:latest
   ```
   Or from source: `git clone https://github.com/natrajexplore/exposurelens && cd exposurelens && uv sync`, put the keys in `.env` (see `.env.example`), then `uv run uvicorn app.main:app`.
2. Open http://localhost:8000 and click **Scan the sample fleet** (4 synthetic devices). A scan takes about a minute and costs about $0.01–0.03 in Token Factory credits.
3. Check the key result: `edge-rtr-01` is **EXPOSED** (line 32 `ip http server`) and `branch-rtr-02` is **NOT EXPOSED** (line 22 `no ip http server`), although both run the same IOS-XE version.
4. Open the top finding to see the cited config lines, mitigation, verify and rollback commands. Download the report.
5. Optional: upload your own config (remove secrets) or type a CVE in the focus box, e.g. `CVE-2024-3400`.
6. No API keys at all? `uv run pytest -q` runs the full pipeline offline against a simulated Nemotron.

## Feedback section (eligible for "Most Valuable Feedback")
Draft from the actual build (21 Oct 2026). Before pasting, check the two items marked [verify]
in the Token Factory console.

**What worked well**
- OpenAI compatibility is the best part of Token Factory. Routing three Nemotron tiers is one `model=` string per call, and JSON mode (`response_format: json_object`) returned parseable JSON on Nano, Super and Ultra.
- Domain-restricted Tavily search (`include_domains` set to vendor PSIRT, CISA and NVD) found real, current advisories, including PAN-OS and ASA advisories newer than our curated pack.

**1. Nemotron 3 reasoning silently ate the whole token budget (biggest issue)**
My first live scan failed on the very first call. Nano returned `content: ""` with `finish_reason: "length"` and 2,500/2,500 completion tokens; the hidden trace was in a non-standard `reasoning` field. A 20-token smoke test returned `None` the same way, which looked like a broken model rather than a reasoning budget problem.
- `reasoning_effort: "low"` did not help on Nano (still 2,500 tokens, empty content) but did work on Super and Ultra.
- What worked on all three was `extra_body={"chat_template_kwargs": {"enable_thinking": false}}`, which I found by trial and error.

Suggestions: document per-model reasoning controls on each model card; make `reasoning_effort` behave the same across Nemotron tiers; and when reasoning exhausts `max_tokens`, return a clear warning or error instead of an empty successful response.

**2. Model ID naming is inconsistent within one family**
The catalog lists `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b` and `nvidia/Nemotron-3-Ultra-550b-a55b`: three different casing and prefix conventions for one model family. My guessed IDs (`Nemotron-3-Super-120B-A12B`, etc.) failed, and I had to list models through the API to find the exact strings. Consistent IDs, or case-insensitive matching, would save every builder this step.

**3. Latency surprised us: Ultra was the fastest tier**
Measured in the app's ledger over three scans (hidden reasoning off): Ultra averaged 1.8–2.3 s per call, Super 3.7–6.0 s, Nano 4.5–11.0 s. Ultra's per-token output speed was also higher. That inverts the usual assumption that the small model is the fast one. Published latency and throughput figures per model would help builders choose tiers; we picked Nano for speed and it turned out to be our slowest tier.

**4. Cost visibility and spending limits**
- I could not find an official per-token price for Nemotron 3 Ultra, so the app's cost table uses estimates (a scan came to roughly $0.01–0.02, 55–66% below running everything on Ultra). [verify: compare with the console's usage page]
- There's no hard spending cap per API key that I could find [verify in console], so I built one into the app. A per-key budget limit, and per-request cost in the `usage` object, would make Token Factory much safer for hackathon and demo keys.

**5. Small papercuts**
- An API key accidentally wrapped in quotes (Docker `--env-file` keeps them) returned `401 "Couldn't authenticate. Reason: Unable authenticate"`. A hint such as "key contains unexpected characters" would have saved debugging time.
- The `nebius` CLI documents only Ubuntu and macOS installs, so Windows developers need WSL or the web console.
- For Serverless Endpoints, the only built-in auth is a Bearer token, which a browser web UI can't send. An option suited to web demos (e.g. basic auth or an IP allowlist) would help app builders.
- Builder Program credit amounts differ between the terms page and the announcement blog post; one clear figure would help.

**6. Tavily**
Results vary between runs for the same query. One run returned the Cisco IOS-XE Web UI advisory (CVE-2023-20198) and the next didn't, and the number of PAN-OS advisories went from 5 to 3. For security workflows where completeness matters, a "stable" or cached mode, and advisory publish dates in results, would help. We now merge live results with a curated pack so well-known cases never drop out.

## 3-minute video script (target 2:45)

Run one scan while recording and keep its result page. Each scan costs about $0.02, so do
narration retakes over the same page rather than rescanning. Live advisories vary per run,
so expect about 12 findings, not 4. The edge-rtr-01 / branch-rtr-02 pair always appears
because curated advisories are always included.

| Time | Screen (what to do) | Voice-over |
|---|---|---|
| 0:00–0:20 | Tab with the [CVE-2023-20198 Cisco advisory](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-iosxe-webui-privesc-j22SaA4z); scroll slowly | "When a critical network CVE drops, scanners tell you which devices run the affected version. They can't tell you which ones are actually exposed. That gap costs network teams hours during the worst possible window." |
| 0:20–0:35 | Switch to http://localhost:8000; hover the tagline "Your config says whether you're exposed." | "I'm Nataraj, a network security engineer. ExposureLens reads your configs with NVIDIA Nemotron on Nebius Token Factory and proves exposure line by line." |
| 0:35–1:05 | Click **Scan the sample fleet**; the "Agent pipeline" stages light up (NANO → TAVILY + SUPER → ULTRA → CODE → SUPER) and the log scrolls. The scan takes 30–65 s: cut it to ~15 s in the edit | "Nemotron Nano fingerprints every device in parallel. Tavily searches vendor PSIRT and CISA live, and Nemotron Super structures what it finds. Nemotron Ultra then judges every device against every advisory." |
| 1:05–1:20 | Results appear; point at the four KPI cards (Exposed, Needs review, Ruled out by config evidence, cost) | "Out of every advisory that matched a version, it ruled out [N] by config evidence alone. That's the noise a version scanner would have handed you." |
| 1:20–1:45 | Click **edge-rtr-01** (top finding, score 100) to expand it: show `L32 ip http server` under "Config evidence (verified)". Scroll down to **branch-rtr-02 · IOS XE Web UI** among NOT EXPOSED and expand it: `L22 no ip http server`, "No action needed" | "Same IOS-XE version on both routers. A version scanner flags both. ExposureLens marks this one exposed — line 32, ip http server — and rules this one out — line 22, no ip http server. Every cited line is checked in code; if the model can't prove it, the verdict is downgraded." |
| 1:45–2:10 | Back on edge-rtr-01's right column: mitigation, Verify and Rollback blocks; click **Download report (.md)** | "For exposed devices it drafts the interim fix in the device's own CLI, with verification and rollback, ready for a change ticket. It never touches your devices." |
| 2:10–2:35 | Scroll to the **"Which Nemotron did what"** table | "Ultra only does the verdicts; Nano and Super handle the volume. That routing makes this scan cost less than half of running everything on Ultra. And interestingly, Ultra was our fastest tier, about two seconds per verdict." |
| 2:35–2:50 | GitHub repo page: README pipeline diagram, then the URL | "Open source, MIT licensed, runs locally in Docker or as a nightly batch job. Stop triaging versions. Triage exposure." |

Replace [N] with the "Ruled out by config evidence" number from your run.

**Recording setup (Windows 11)**
- Record with Snipping Tool (Win + Shift + R, select the browser window, turn the mic on). It's lighter on RAM than OBS while Docker runs.
- Edit in Clipchamp: trim the scan wait, keep it under 3:00, export at 1080p.
- Browser at 1080p, zoom 110%, bookmarks bar hidden (Ctrl+Shift+B). Turn on Do Not Disturb.
- Never show `.env`, a terminal with keys, or the Token Factory console's key page.
- No copyrighted music. Upload to YouTube as **Public**, not Unlisted.
