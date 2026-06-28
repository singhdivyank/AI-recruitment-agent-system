"""
Centralized LLM client with:
  - Gemini 2.5 Pro (complex reasoning) / Gemini Flash (simple tasks)
  - Cost guardrails: per-JD cap, daily budget cap
  - Retry with exponential backoff (max 3 retries, NO full-context resend on failure)
  - Token + cost tracking on every call
  - LangSmith tracing via LANGCHAIN_TRACING_V2 env var
"""
from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import BaseMessage, HumanMessage, SystemMessage

import redis.asyncio as aioredis

from core.config import get_settings
from observability.telemetry import record_llm_usage

settings = get_settings()
logger = structlog.get_logger()


class CostGuardrailError(Exception):
    """Raised when cost/token limits are exceeded."""


class LLMClient:
    """
    Thread-safe LLM client with per-JD and daily cost guardrails.

    Cost guardrail strategy:
      1. Before each call, check if jd_id has exceeded max_cost_per_jd_usd
      2. Check if daily total has exceeded daily_budget_usd
      3. Use smaller model for simple tasks to reduce cost
      4. Cap retries at max_llm_retries; on retry send ONLY the retry prompt,
         not the full conversation history (prevents the $4K→$40K bill spike)
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client
        self._pro = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
        self._flash = ChatGoogleGenerativeAI(
            model=settings.gemini_flash_model,
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
        self.pricing = {
            settings.gemini_model: {
                "input": 3.50 / 1_000_000,
                "output": 10.50 / 1_000_000,
            },
            settings.gemini_flash_model: {
                "input": 0.10 / 1_000_000,
                "output": 0.40 / 1_000_000,
            },
        }

    def _get_model(self, use_flash: bool = False):
        return self._flash if use_flash else self._pro

    def _model_name(self, use_flash: bool = False) -> str:
        return settings.gemini_flash_model if use_flash else settings.gemini_model

    def _compute_cost(self, model_name: str, input_tokens: int, output_tokens: int):
        p = self.pricing.get(model_name, self.pricing[settings.gemini_model])
        self.estimated_cost = p["input"] * input_tokens + p["output"] * output_tokens
    
    def _check_jd_cost(self, jd_cost: float, jd_id: str):
        if jd_cost + self.estimated_cost > settings.max_cost_per_jd_usd:
            raise CostGuardrailError(
                f"JD {jd_id} would exceed per-JD cost cap of ${settings.max_cost_per_jd_usd:.2f} "
                f"(current: ${jd_cost:.4f})"
            )
    
    def _check_token_cost(self, jd_id: str, jd_tokens: int, estimated_input_tokens: int):
        if jd_tokens + estimated_input_tokens > settings.max_tokens_per_jd:
            raise CostGuardrailError(
                f"JD {jd_id} would exceed token cap of {settings.max_tokens_per_jd:,}"
            )
    
    def _check_daily_budget(self, daily_cost: float):
        if daily_cost + self.estimated_cost > settings.daily_budget_usd:
            raise CostGuardrailError(
                f"Daily budget cap of ${settings.daily_budget_usd:.2f} would be exceeded "
                f"(current: ${daily_cost:.4f})"
            )

    async def _check_guardrails(self, jd_id: Optional[str], estimated_input_tokens: int, use_flash: bool) -> None:
        """Raise CostGuardrailError if limits would be exceeded."""
        if not self._redis or not jd_id:
            return

        model_name = self._model_name(use_flash)
        self._compute_cost(model_name, estimated_input_tokens, 500)

        # Per-JD cost check
        jd_cost_key = f"cost:jd:{jd_id}"
        jd_cost_bytes = await self._redis.get(jd_cost_key)
        jd_cost = float(jd_cost_bytes or 0)
        self._check_jd_cost(jd_cost=jd_cost, jd_id=jd_id)

        # Per-JD token check
        jd_token_key = f"tokens:jd:{jd_id}"
        jd_tokens_bytes = await self._redis.get(jd_token_key)
        jd_tokens = int(jd_tokens_bytes or 0)
        self._check_token_cost(jd_id=jd_id, jd_tokens=jd_tokens, estimated_input_tokens=estimated_input_tokens)

        # Daily budget check
        daily_cost_key = "cost:daily"
        daily_cost_bytes = await self._redis.get(daily_cost_key)
        daily_cost = float(daily_cost_bytes or 0)
        self._check_daily_budget(daily_cost=daily_cost)

    async def _record_usage(
        self,
        jd_id: Optional[str],
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        if not self._redis:
            return
        pipe = self._redis.pipeline()
        if jd_id:
            pipe.incrbyfloat(f"cost:jd:{jd_id}", cost_usd)
            pipe.expire(f"cost:jd:{jd_id}", 86400 * 30)
            pipe.incrby(f"tokens:jd:{jd_id}", input_tokens + output_tokens)
            pipe.expire(f"tokens:jd:{jd_id}", 86400 * 30)
        pipe.incrbyfloat("cost:daily", cost_usd)
        pipe.expire("cost:daily", 86400)
        await pipe.execute()

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "unknown",
        jd_id: Optional[str] = None,
        use_flash: bool = False,
    ) -> BaseMessage:
        """
        Make a single LLM call. On retry (attempt > 0), sends only the retry
        prompt — NOT the full prior context — to prevent runaway token spend.
        """
        model = self._get_model(use_flash)
        model_name = self._model_name(use_flash)
        estimated_tokens = len(system_prompt.split()) + len(user_prompt.split())

        await self._check_guardrails(jd_id, estimated_tokens, use_flash)

        start = time.monotonic()
        try:
            response = await model.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            elapsed = time.monotonic() - start

            # Extract token usage (Gemini returns usage_metadata)
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "input_tokens", estimated_tokens) if usage else estimated_tokens
            output_tokens = getattr(usage, "output_tokens", 100) if usage else 100
            self._compute_cost(model_name, input_tokens, output_tokens)

            await self._record_usage(jd_id, input_tokens, output_tokens, self.estimated_cost)
            record_llm_usage(agent_name, model_name, input_tokens, output_tokens, elapsed, self.estimated_cost)
            return response

        except CostGuardrailError:
            raise
        except Exception as _:
            elapsed = time.monotonic() - start
            record_llm_usage(agent_name, model_name, 0, 0, elapsed, 0.0, success=False)
            raise

    async def call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "unknown",
        jd_id: Optional[str] = None,
        use_flash: bool = False,
    ) -> BaseMessage:
        """
        Retry wrapper with exponential backoff. Critically, each retry sends
        the SAME prompt (not appended history) to avoid token explosion.
        """
        last_exc = None
        for attempt in range(settings.max_llm_retries + 1):
            try:
                return await self.call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    agent_name=agent_name,
                    jd_id=jd_id,
                    use_flash=use_flash,
                )
            except CostGuardrailError:
                raise  # never retry cost errors
            except Exception as exc:
                last_exc = exc
                if attempt < settings.max_llm_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "llm_retry",
                        agent=agent_name,
                        attempt=attempt + 1,
                        wait_s=wait,
                        error=str(exc),
                    )
                    await asyncio.sleep(wait)

        raise RuntimeError(f"LLM call failed after {settings.max_llm_retries} retries: {last_exc}")

    async def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str = "unknown",
        jd_id: Optional[str] = None,
        use_flash: bool = False,
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response. Strips markdown fences."""
        raw = await self.call_with_retry(
            system_prompt=system_prompt + "\n\nRespond ONLY with valid JSON, no markdown fences.",
            user_prompt=user_prompt,
            agent_name=agent_name,
            jd_id=jd_id,
            use_flash=use_flash,
        )
        # Strip ```json ... ``` if model adds it despite instructions
        content = raw.content
        if isinstance(content, str):
            clean: str = content.strip()
        if isinstance(content, List):
            if isinstance(content[0], str):
                clean: str = clean[0].strip()
        
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:]).strip()
        if clean.endswith("```"):
            clean = "\n".join(clean.split("\n")[:-1]).strip()
        return json.loads(clean)
