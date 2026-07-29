from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Callable
from typing import Any

from genblaze_core import EvaluationResult, Evaluator
from genblaze_openai import chat
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..storage import DaraStorage


QA_RUBRIC = """
Review the generated image against the supplied creative brief. Judge only what is
visible. Return the structured score with concrete issues and a complete replacement
prompt that fixes them.

Scoring:
- prompt_adherence: requested subject, count, composition, exclusions, and text
- technical_quality: artifacts, malformed geometry, illegible detail, and finish
- brand_fit: whether the visual language matches the brief
- usable_as_is: whether a producer could publish it without retouching
- overall: weighted judgement, not a simple mean

Be strict but practical. A clean, faithful image should pass.
""".strip()


class QAScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_adherence: float = Field(ge=0, le=1)
    technical_quality: float = Field(ge=0, le=1)
    brand_fit: float = Field(ge=0, le=1)
    usable_as_is: float = Field(ge=0, le=1)
    overall: float = Field(ge=0, le=1)
    issues: list[str] = Field(max_length=8)
    revised_prompt: str = Field(min_length=8, max_length=4000)


def _strip_markdown_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    return match.group(1) if match else stripped


def _result_asset_bytes(storage: DaraStorage, result: Any) -> tuple[bytes, str]:
    run = result.run
    asset = run.steps[0].assets[0]
    day = run.created_at.astimezone().date().isoformat()
    prefix = f"dara/live/runs/{run.tenant_id}/{day}/{run.run_id}"
    key = next(
        item
        for item in storage.list_prefix(prefix)
        if "/assets/" in item and asset.asset_id in item
    )
    data = storage.get_bytes(key)
    if data is None:
        raise RuntimeError("The QA evaluator could not load the generated candidate.")
    return data, asset.media_type


class OpenAIVisionEvaluator(Evaluator):
    def __init__(
        self,
        *,
        storage: DaraStorage,
        brief: str,
        threshold: float = 0.72,
        model: str | None = None,
        chat_call: Callable[..., Any] = chat,
        before_evaluate: Callable[[], None] | None = None,
    ) -> None:
        self.storage = storage
        self.brief = brief
        self.threshold = threshold
        self.model = model or os.getenv("DARA_QA_MODEL", "gpt-4.1-mini")
        self.chat_call = chat_call
        self.before_evaluate = before_evaluate
        self.evaluations: list[QAScore] = []
        self.parse_failures = 0

    def _score(self, result: Any, *, strict_retry: bool = False) -> QAScore:
        image, mime_type = _result_asset_bytes(self.storage, result)
        encoded = base64.b64encode(image).decode("ascii")
        prompt = result.run.steps[0].prompt
        response = self.chat_call(
            self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Original brief:\n{self.brief}\n\n"
                                f"Generation prompt:\n{prompt}\n\n"
                                "Score this candidate."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            system=(
                QA_RUBRIC
                + (
                    "\nThe previous response could not be parsed. Return only the "
                    "requested JSON object."
                    if strict_retry
                    else ""
                )
            ),
            response_format=QAScore,
            temperature=0,
            max_tokens=700,
            timeout=90.0,
        )
        return QAScore.model_validate_json(_strip_markdown_fence(response.text))

    def evaluate(self, result: Any) -> EvaluationResult:
        if self.before_evaluate is not None:
            self.before_evaluate()
        try:
            score = self._score(result)
        except (json.JSONDecodeError, ValidationError, ValueError):
            self.parse_failures += 1
            try:
                score = self._score(result, strict_retry=True)
            except (json.JSONDecodeError, ValidationError, ValueError):
                score = QAScore(
                    prompt_adherence=0.5,
                    technical_quality=0.5,
                    brand_fit=0.5,
                    usable_as_is=0.5,
                    overall=0.5,
                    issues=["The vision evaluator returned an invalid structured score."],
                    revised_prompt=(
                        f"{self.brief}. Preserve the requested subject and composition; "
                        "remove visible artifacts and produce a clean, publishable result."
                    ),
                )
        self.evaluations.append(score)
        passed = score.overall >= self.threshold
        return EvaluationResult(
            passed=passed,
            score=score.overall,
            feedback=(
                "The candidate passed Dara's visual QA gate."
                if passed
                else score.revised_prompt
            ),
            metadata=score.model_dump(),
        )
