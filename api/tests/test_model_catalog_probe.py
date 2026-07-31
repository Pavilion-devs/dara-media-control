from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from dara.tools.probe_model_catalog import OPENAI_MODELS, fetch_catalog


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"data": [{"id": model} for model in OPENAI_MODELS[:-1]]}
        ).encode()


class ModelCatalogProbeTests(unittest.TestCase):
    def test_probe_reports_missing_models_without_exposing_the_key(self) -> None:
        seen: dict[str, object] = {}

        def request(value: object, timeout: float) -> Response:
            seen["request"] = value
            seen["timeout"] = timeout
            return Response()

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-sensitive"}):
            result = fetch_catalog(request)  # type: ignore[arg-type]

        self.assertFalse(result["all_available"])
        self.assertEqual(result["missing"], [OPENAI_MODELS[-1]])
        self.assertNotIn("sk-sensitive", json.dumps(result))
        self.assertEqual(seen["timeout"], 30.0)


if __name__ == "__main__":
    unittest.main()
