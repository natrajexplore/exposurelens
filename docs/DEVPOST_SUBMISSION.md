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
1. Open the demo URL.
2. Enter access key: `<APP_ACCESS_KEY>` (only if the page asks).
3. Click **Scan the sample fleet** (4 synthetic devices). A scan takes about a minute.
4. Open the top finding to see the cited config lines, mitigation, verify and rollback commands. Download the report.
5. Optional: upload your own config (remove secrets) or type a CVE in the focus box, e.g. `CVE-2024-3400`.

## Feedback section (eligible for "Most Valuable Feedback")
Write this from your real experience during the build — specific beats polite. Starter points to verify and expand:
- Token Factory: OpenAI compatibility made tier routing trivial. Note any model-ID naming inconsistencies you hit (case, version suffixes, `-fast` variants) and whether JSON mode worked per model.
- Record real latency for Nano vs Super vs Ultra from the app's ledger and say where Ultra's latency hurt the UX.
- Was there a way to see per-model usage/cost in the console that matched your app's numbers?
- Nemotron reasoning traces: how `<think>` output interacted with structured output; what would make it easier (e.g. a documented flag to disable reasoning per request).
- Tavily: domain-restricted advanced search quality on PSIRT pages; anything missing (e.g. publish dates).

## 3-minute video script (target 2:45)

| Time | Screen | Voice-over |
|---|---|---|
| 0:00–0:20 | Vendor advisory page, then a spreadsheet of "affected devices" | "When a critical network CVE drops, scanners tell you which devices run the affected version. They can't tell you which ones are actually exposed. That gap costs network teams hours during the worst possible window." |
| 0:20–0:35 | ExposureLens home | "I'm Nataraj, a network security engineer. ExposureLens reads your configs with NVIDIA Nemotron on Nebius Token Factory and proves exposure line by line." |
| 0:35–1:05 | Click "Scan the sample fleet"; pipeline lights up; log scrolls | "Nemotron Nano fingerprints every device in parallel. Tavily searches vendor PSIRT and CISA live, and Nemotron Super structures what it finds. Nemotron Ultra then judges every device against every advisory." |
| 1:05–1:45 | Results: KPI cards; expand edge-rtr-01 then branch-rtr-02 | "Same IOS-XE version on both routers. A version scanner flags both. ExposureLens marks this one exposed — line 32, ip http server — and rules this one out — line 22, no ip http server. Every cited line is checked in code; if the model can't prove it, the verdict is downgraded." |
| 1:45–2:10 | Mitigation, verify, rollback blocks; download report | "For exposed devices it drafts the interim fix in the device's own CLI, with verification and rollback, ready for a change ticket. It never touches your devices." |
| 2:10–2:35 | "Which Nemotron did what" table | "Ultra only does the verdicts; Nano and Super handle the volume. That routing makes this scan about half the cost of running everything on Ultra." |
| 2:35–2:50 | Architecture diagram from README, GitHub URL | "Open source, MIT licensed, runs as an endpoint or a nightly job on Nebius. Stop triaging versions. Triage exposure." |

Recording tips: 1080p, browser zoom 110%, record the live scan once and trim waiting time; no copyrighted music; upload as Public on YouTube.
