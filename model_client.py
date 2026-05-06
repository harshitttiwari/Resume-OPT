"""Small LLM client wrapper for Gemini/Groq JSON calls."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv

from log import get_logger

load_dotenv()
log = get_logger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower().strip()

GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")
GROQ_MODEL_STRONG = os.getenv("GROQ_MODEL_STRONG", "llama-3.3-70b-versatile")

# Recommended for this project:
# - Fast model: repo analysis, JD/resume parsing, short validation.
# - Strong model: resume rewriting and final structured resume generation.
GEMINI_FAST_MODELS = os.getenv(
    "GEMINI_FAST_MODELS",
    "gemini-2.5-flash-lite,gemini-2.5-flash",
)
GEMINI_STRONG_MODELS = os.getenv(
    "GEMINI_STRONG_MODELS",
    "gemini-2.5-flash,gemini-2.5-flash-lite",
)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))


# LLM client

@lru_cache(maxsize=4)
def get_groq_llm(model: str, temperature: float = 0.0) -> Any:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing.")

    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


def _split_models(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _selected_provider() -> str:
    if LLM_PROVIDER in {"gemini", "groq"}:
        return LLM_PROVIDER
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "groq"


def _invoke_groq(prompt: str, fast: bool) -> str:
    model = GROQ_MODEL_FAST if fast else GROQ_MODEL_STRONG
    log.info(f"LLM call | provider=groq | model={model} | fast={fast}")
    return get_groq_llm(model, 0.0).invoke(prompt).content


def _invoke_gemini(prompt: str, fast: bool) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    models = _split_models(GEMINI_FAST_MODELS if fast else GEMINI_STRONG_MODELS)
    errors = []

    for model in models:
        url = GEMINI_API_URL.format(model=model)
        log.info(f"LLM call | provider=gemini | model={model} | fast={fast}")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "response_mime_type": "application/json",
                "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            },
        }

        try:
            response = requests.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=60,
            )
            if response.status_code >= 400:
                log.info(f"LLM call failed | provider=gemini | model={model} | status={response.status_code}")
                errors.append(f"{model}: {response.status_code} {response.text[:300]}")
                continue

            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
            if text.strip():
                log.info(f"LLM call succeeded | provider=gemini | model={model}")
                return text
            log.info(f"LLM call returned empty text | provider=gemini | model={model}")
            errors.append(f"{model}: empty response")
        except Exception as exc:
            log.info(f"LLM call failed | provider=gemini | model={model} | error={exc}")
            errors.append(f"{model}: {exc}")

    raise ValueError("Gemini request failed for all configured models: " + " | ".join(errors))


def invoke_llm(prompt: str, fast: bool = False) -> str:
    provider = _selected_provider()
    if provider == "gemini":
        try:
            return _invoke_gemini(prompt, fast)
        except Exception as exc:
            if LLM_PROVIDER == "auto" and os.getenv("GROQ_API_KEY"):
                log.info(f"Gemini failed; falling back to Groq | reason={exc}")
                return _invoke_groq(prompt, fast)
            raise
    return _invoke_groq(prompt, fast)


def parse_json(text: str) -> dict[str, Any]:
    """
    Extract and parse the first JSON object from an LLM response.
    Handles code fences and minor control-character issues.
    """
    text = re.sub(r"```(?:json)?|```", "", str(text or ""), flags=re.IGNORECASE).strip()
    start = text.find("{")

    if start < 0:
        raise ValueError("LLM did not return a JSON object.")

    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        cleaned = re.sub(
            r'(?<!\\)[\x00-\x1f\x7f]',
            lambda m: repr(m.group())[1:-1],
            text[start:],
        )
        try:
            obj, _ = json.JSONDecoder().raw_decode(cleaned)
            return obj
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned malformed JSON: {exc}") from exc


def ask_json(prompt: str, fast: bool = False) -> dict[str, Any]:
    """
    Ask the LLM for JSON.
    If first response is malformed, run one JSON repair pass.
    """
    response = invoke_llm(prompt, fast=fast)

    try:
        return parse_json(response)
    except Exception:
        log.info("LLM JSON parse failed; running one JSON repair call")
        repair_prompt = f"""
Fix the following response into valid JSON only.
Do not add explanation.
Do not add markdown.
Return only one corrected JSON object.

Broken response:
{response[:6000]}
"""
        repaired = invoke_llm(repair_prompt, fast=fast)
        return parse_json(repaired)
