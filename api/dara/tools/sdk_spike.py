from __future__ import annotations

import json
from importlib.metadata import version

from genblaze_core import Modality, Pipeline
from genblaze_core.testing import MockVideoProvider


def run_spike() -> dict[str, object]:
    result = (
        Pipeline("dara-sdk-spike", tenant_id="demo")
        .step(
            MockVideoProvider(),
            model="mock-v1",
            prompt="A controlled provenance test for Dara",
            modality=Modality.VIDEO,
        )
        .run(raise_on_failure=True)
    )
    return {
        "versions": {
            "genblaze": version("genblaze"),
            "genblaze-core": version("genblaze-core"),
            "genblaze-s3": version("genblaze-s3"),
        },
        "run_id": result.run.run_id,
        "step_count": len(result.run.steps),
        "canonical_hash": result.manifest.canonical_hash,
        "verify_hash": result.manifest.verify_hash(),
        "verify": result.manifest.verify(),
    }


def main() -> None:
    print(json.dumps(run_spike(), indent=2))


if __name__ == "__main__":
    main()
