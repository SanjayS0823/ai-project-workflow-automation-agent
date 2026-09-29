"""AI planning service: turns a natural-language brief into a structured plan.

The real implementation calls Google's official Gemini API (the google-genai
SDK) with structured JSON output and validates the result against the
ProjectPlan schema. When AI_USE_FALLBACK=1 the Gemini planner is skipped
entirely; when AI_USE_FALLBACK=0 (or unset) plan_project() tries Gemini first
and, if it fails for any AI-provider reason (configuration, authentication,
quota/rate limit, timeout, network, malformed JSON, or schema-invalid output),
logs the failure and automatically uses the deterministic development
fallback planner. Invalid AI output is never persisted.
"""

import json
import logging
import os
from typing import Any, Optional

from pydantic import ValidationError

from ..schemas import ProjectPlan
from .fallback_planner import generate_fallback_plan
from .prompts import PLANNER_SYSTEM_PROMPT, build_planning_prompt

logger = logging.getLogger(__name__)


class AIPlannerError(Exception):
    """Base error for the AI planning service."""


class AIPlannerConfigurationError(AIPlannerError):
    """Raised when required configuration (e.g. an API key) is missing."""


class InvalidAIOutputError(AIPlannerError):
    """Raised when the model response cannot form a valid ProjectPlan."""


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _default_base_url() -> Optional[str]:
    """Optional override for the Gemini API endpoint (e.g. a proxy).

    When unset, the google-genai SDK uses its default Google endpoint
    (https://generativelanguage.googleapis.com/v1beta).
    """
    return os.getenv("AI_LLM_BASE_URL") or None


def _default_model() -> str:
    # A currently supported Gemini model (see ai.google.dev/gemini-api/docs/models).
    # The 2.5 family was retired; gemini-3.5-flash is a current stable model.
    # Override with AI_LLM_MODEL.
    return os.getenv("AI_LLM_MODEL", "gemini-3.5-flash")


def _default_timeout() -> int:
    try:
        return max(1, int(float(os.getenv("AI_LLM_TIMEOUT_SECONDS", "60"))))
    except ValueError:
        return 60


def use_fallback() -> bool:
    """Whether the deterministic development fallback should be used."""
    return _env_flag("AI_USE_FALLBACK")


MIN_BRIEF_LENGTH = 10


def _validate_brief(brief: str) -> str:
    """Validate and normalize a project brief."""
    brief = (brief or "").strip()
    if not brief:
        raise ValueError("Project brief must not be empty.")
    if len(brief) < MIN_BRIEF_LENGTH:
        raise ValueError(
            "Project brief is too short. Please provide more detail."
        )
    return brief


class GeminiPlanner:
    """Planner backed by Google's official Gemini API (google-genai SDK)."""

    def __init__(self, client: Any = None, model: Optional[str] = None) -> None:
        api_key = os.getenv("AI_LLM_API_KEY")
        if not api_key or not api_key.strip():
            raise AIPlannerConfigurationError(
                "AI_LLM_API_KEY is not set. Configure it in the environment, or "
                "set AI_USE_FALLBACK=1 to use the development fallback planner."
            )
        if client is None:
            import httpx

            from google import genai
            from google.genai import types

            timeout = _default_timeout()
            # Inject a standard httpx client with the timeout applied on the
            # client itself. IMPORTANT: do not also set HttpOptions.timeout —
            # the SDK mis-scales that value (seconds are applied as
            # milliseconds on the connect timeout), which makes every request
            # fail with a TLS handshake timeout even though the endpoint is
            # reachable. The injected client is used as-is and carries its own
            # timeout.
            http_options: dict = {
                "httpx_client": httpx.Client(timeout=timeout),
            }
            base_url = _default_base_url()
            if base_url:
                http_options["base_url"] = base_url
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(**http_options),
            )
        self.client = client
        self.model = model or _default_model()

    def generate_plan(self, brief: str) -> ProjectPlan:
        """Generate and validate a structured plan for the brief."""
        brief = _validate_brief(brief)

        try:
            from google.genai import types

            response = self.client.models.generate_content(
                model=self.model,
                contents=build_planning_prompt(brief),
                config=types.GenerateContentConfig(
                    system_instruction=PLANNER_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
        except AIPlannerError:
            raise
        except Exception as exc:  # auth, quota, timeout, network, provider errors
            raise AIPlannerError(f"AI planning request failed: {exc}") from exc

        try:
            content = response.text
        except (AttributeError, IndexError, KeyError) as exc:
            raise InvalidAIOutputError(
                "AI returned an unexpected response structure."
            ) from exc

        if not content or not content.strip():
            raise InvalidAIOutputError("AI returned an empty response.")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidAIOutputError("AI returned invalid JSON.") from exc

        try:
            return ProjectPlan.model_validate(data)
        except ValidationError as exc:
            raise InvalidAIOutputError(
                f"AI output failed plan validation: {exc}"
            ) from exc


def plan_project(brief: str) -> ProjectPlan:
    """Generate a structured plan for the given brief.

    - AI_USE_FALLBACK=1: use the deterministic fallback planner only (Gemini
      is never called).
    - AI_USE_FALLBACK=0 (or unset): try the real Gemini planner first. If it
      fails for any AI-provider reason (missing/invalid key, authentication,
      quota/rate limit, timeout, network, malformed JSON, or schema-invalid
      output), log the failure and automatically use the deterministic
      fallback planner.

    Only AI-provider errors trigger the fallback. Database/persistence
    errors, invalid request data, and unrelated application exceptions are
    handled elsewhere and are never swallowed here.
    """
    brief = _validate_brief(brief)

    if use_fallback():
        return generate_fallback_plan(brief)

    try:
        return GeminiPlanner().generate_plan(brief)
    except AIPlannerError as exc:
        logger.warning(
            "Gemini planning failed (%s); automatically using the fallback planner.",
            exc,
        )
        return generate_fallback_plan(brief)
