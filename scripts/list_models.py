"""List the NVIDIA models your Nebius Token Factory key can call, then smoke-test one.

Usage:  python scripts/list_models.py            # list NVIDIA models
        python scripts/list_models.py --test     # also send a 1-line test to each tier in .env
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url=os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
                api_key=os.environ["NEBIUS_API_KEY"])

ids = sorted(m.id for m in client.models.list().data)
nv = [i for i in ids if "nvidia" in i.lower() or "nemotron" in i.lower()]
print("NVIDIA / Nemotron models available to this key:")
for i in nv:
    print("  ", i)
print(f"({len(ids)} models total)")

if "--test" in sys.argv:
    for tier in ("NANO", "SUPER", "ULTRA"):
        model = os.getenv(f"NEMOTRON_{tier}_MODEL")
        try:
            r = client.chat.completions.create(model=model, max_tokens=20,
                                               messages=[{"role": "user", "content": "Reply with: ok"}])
            print(f"{tier:5} {model}: OK -> {r.choices[0].message.content!r}")
        except Exception as e:
            print(f"{tier:5} {model}: FAILED -> {e}")
