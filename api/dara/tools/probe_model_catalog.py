from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv


OPENAI_MODELS = (
    "gpt-image-2",
    "gpt-image-2-2026-04-21",
    "gpt-4.1-mini",
    "sora-2",
    "sora-2-pro",
    "tts-1",
    "tts-1-hd",
)


def fetch_catalog(
    request: Callable[[urllib.request.Request, float], object] = urllib.request.urlopen,
) -> dict[str, object]:
    token = os.getenv("OPENAI_API_KEY")
    if not token:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    value = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    with request(value, timeout=30.0) as response:  # type: ignore[call-arg,attr-defined]
        payload = json.loads(response.read())
    available = {item["id"] for item in payload.get("data", [])}
    return {
        "required": list(OPENAI_MODELS),
        "available": [model for model in OPENAI_MODELS if model in available],
        "missing": [model for model in OPENAI_MODELS if model not in available],
        "all_available": all(model in available for model in OPENAI_MODELS),
    }


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(fetch_catalog(), indent=2))


if __name__ == "__main__":
    main()
