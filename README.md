# ExposureLens

**Version scanners say you're vulnerable. Your config says whether you're exposed.**

ExposureLens is a multi-agent app for network security teams. You upload device configs
(Cisco IOS-XE, ASA, Palo Alto PAN-OS). Agents find the security advisories that apply,
decide for each device whether the vulnerable feature is actually configured, cite the exact
config lines that prove it, and draft a mitigation with verify and rollback commands.

Built for the **Nebius x NVIDIA Global AI Hackathon** — *Best Apps and Agents* track.
Powered by **NVIDIA Nemotron 3 (Nano, Super, Ultra) on Nebius Token Factory**, with **Tavily**
for live advisory discovery. MIT licensed.

---

## The problem

Most critical network-device CVEs only matter if a specific feature is turned on: the IOS-XE
Web UI bug needs `ip http server`, the PAN-OS GlobalProtect bug needs a GlobalProtect portal or
gateway. Version-based scanners flag every device on an affected version, so engineers spend
the first hours of every emergency advisory opening configs one by one to find out which
devices are really exposed. ExposureLens does that triage in minutes, with evidence.

In the sample fleet, two routers run the same vulnerable IOS-XE version. A version scanner
flags both. ExposureLens marks `edge-rtr-01` **EXPOSED** (line 32: `ip http server`) and
`branch-rtr-02` **NOT EXPOSED** (line 22: `no ip http server`).

## How it works

```
configs ──► Fingerprint ──► Advisory hunt ──────────► Exposure judge ──► Evidence check ──► Fix + brief
            Nemotron Nano    Tavily + Nemotron Super    Nemotron Ultra     deterministic     Nemotron Super
```

| Stage | Model | Why this tier |
|---|---|---|
| Fingerprint every config: OS, version, enabled features, proof lines | **Nemotron 3 Nano** | High-volume structured extraction; runs once per device in parallel |
| Turn live Tavily results from vendor PSIRT / CISA into structured advisories (affected versions, vulnerable feature, exploit conditions, workaround) | **Nemotron 3 Super** | Long-context reading of many sources; output is source-checked (every advisory URL must come from Tavily results) |
| Decide EXPOSED / NOT_EXPOSED / NEEDS_REVIEW for each device × advisory | **Nemotron 3 Ultra** | The hard reasoning step: version range + feature presence + reachability + existing mitigations |
| Verify every cited config line exists in the file | Python | The model never gets the last word on evidence. An EXPOSED verdict with no verifiable lines is downgraded to NEEDS_REVIEW |
| Draft interim mitigation, verification, rollback, permanent fix; write the 24-hour brief | **Nemotron 3 Super** | Structured drafting at a fraction of Ultra's cost |

The UI shows a live **"Which Nemotron did what"** table: calls, tokens, latency and estimated
cost per tier, compared to running every call on Ultra.

**Safety by design:** ExposureLens is read-only. It never connects to or changes a device.
All commands are labelled as drafts for human review in your change process.

## Where Nebius Token Factory helped

- One OpenAI-compatible endpoint for all three Nemotron tiers, so tier routing is a one-line model swap (`app/llm.py`).
- Nano fingerprinting and Ultra judging run in parallel threads against the same endpoint, so scan time grows slowly with fleet size.
- Token Factory's per-token pricing made it practical to reserve Ultra only for verdicts.
- `jobs/nightly_scan.py` runs the same pipeline as a batch job (container-ready for Nebius Serverless Jobs) so new advisories are caught overnight.

## Run it locally

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/natrajexplore/exposurelens && cd exposurelens
uv sync
cp .env.example .env          # add NEBIUS_API_KEY (and optionally TAVILY_API_KEY)
uv run python scripts/list_models.py --test   # checks all three Nemotron tiers answer
uv run uvicorn app.main:app --reload
```

Tests: `uv run pytest -q`

With pip:

```bash
git clone https://github.com/natrajexplore/exposurelens && cd exposurelens
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # add NEBIUS_API_KEY (and optionally TAVILY_API_KEY)
python scripts/list_models.py --test   # checks all three Nemotron tiers answer
uvicorn app.main:app --reload
```

Open http://localhost:8000 and click **Scan the sample fleet**, or upload your own configs
(remove secrets first). Without a Tavily key, advisories come from a small bundled offline pack,
clearly labelled in the UI.

**Tests (no API keys needed):** `pytest -q`

**Batch mode:** `CONFIG_DIR=samples/configs OUTPUT_DIR=out python -m jobs.nightly_scan`

**Cost guard:** model calls stop once estimated spend reaches `BUDGET_USD` (default $0.50),
tracked in `out/spend.json` across runs. A sample-fleet scan costs about $0.01–0.03.

## Run with Docker

Pre-built image, no clone needed:

```bash
docker run --rm -p 127.0.0.1:8000:8000 \
  -e NEBIUS_API_KEY=your_key -e TAVILY_API_KEY=your_key \
  ghcr.io/natrajexplore/exposurelens:latest
```

Or build it from the repo and reuse your `.env`:

```bash
docker build -t exposurelens .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -v "$PWD/out:/app/out" exposurelens
```

Docker's `--env-file` passes values literally, so write `NEBIUS_API_KEY=abc` in `.env`, not
`NEBIUS_API_KEY="abc"`. The `-v` mount keeps the spend tracker across container restarts.
Binding to `127.0.0.1` keeps the app reachable only from your machine.

## Hosting

ExposureLens is demoed locally. The same image runs on Nebius Serverless Endpoints or any
container host; if you expose it publicly, set `APP_ACCESS_KEY` so visitors must enter a key
before a scan can spend your credits.

## Project layout

```
app/llm.py           Nemotron tier router + usage ledger (Token Factory)
app/advisories.py    Tavily advisory hunter + offline pack
app/pipeline.py      Agent orchestration
app/config_tools.py  Line numbering, quick facts, evidence validation, risk score
app/prompts.py       Agent prompts (JSON contracts)
app/main.py          FastAPI API + UI
app/static/          Single-page UI
jobs/nightly_scan.py Batch job for Serverless Jobs / cron
samples/configs/     Synthetic sample fleet (no real data)
tests/               Offline tests with a fake Nemotron router
```

## Limitations

- Supports Cisco IOS-XE, ASA and PAN-OS configs today; others are parsed best-effort.
- Verdicts depend on the config you upload; runtime state (e.g. a feature enabled via GUI and not saved) is out of scope.
- Advisory facts come from public pages at scan time. Always confirm on the vendor advisory before changing production.
