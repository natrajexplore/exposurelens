"""Batch scan for Nebius Serverless Jobs (or any cron/container runner).

Reads every config in CONFIG_DIR, runs the full agent pipeline, and writes
report.md + result.json to OUTPUT_DIR. New advisories published overnight are
picked up because Tavily searches live each run.

    CONFIG_DIR=samples/configs OUTPUT_DIR=out python -m jobs.nightly_scan
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.advisories import AdvisoryHunter  # noqa: E402
from app.llm import NemotronRouter  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.report import to_markdown  # noqa: E402


def main():
    src = Path(os.getenv("CONFIG_DIR", "samples/configs"))
    out = Path(os.getenv("OUTPUT_DIR", "out"))
    out.mkdir(parents=True, exist_ok=True)
    configs = {p.name: p.read_text() for p in sorted(src.glob("*")) if p.is_file()}
    result = Pipeline(NemotronRouter(), AdvisoryHunter(),
                      emit=lambda s, m: print(f"[{s}] {m}", flush=True)).run(configs)
    (out / "result.json").write_text(json.dumps(result, indent=2, default=str))
    (out / "report.md").write_text(to_markdown(result))
    print(json.dumps(result["counts"]), "->", out / "report.md")


if __name__ == "__main__":
    main()
