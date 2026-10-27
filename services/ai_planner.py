"""
AI Planner & Narrative Service for Namma Payana.
Uses Google Gemini AI when a key is configured.
Crucial Rule: AI output is NEVER trusted directly for IDs, timings, or budget.
All proposed content is strictly re-verified by the Python Trip Reality Engine.
"""
from abc import ABC, abstractmethod
import os
import json
import logging
import re
from typing import Dict, Any, Optional
from services.destination_service import destination_service
from services.itinerary import ItineraryEngine
from services.budget import BudgetEngine
from services.feasibility import FeasibilityEngine

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generates JSON structured response from the LLM or raises an exception."""
        pass


class NullLLMProvider(LLMProvider):
    """Fallback when no AI keys are configured."""
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise RuntimeError("No AI provider configured.")


class GeminiLLMProvider(LLMProvider):
    """Google Gemini AI provider using the google-genai SDK."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from google.genai import types
        client = self._get_client()
        candidate_models = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
        last_error = None
        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.25,
                        max_output_tokens=1024,
                    )
                )
                raw = response.text.strip()
                raw = re.sub(r'^```(?:json)?\s*', '', raw)
                raw = re.sub(r'\s*```$', '', raw)
                return json.loads(raw)
            except Exception as e:
                last_error = e
                logger.warning(f"AI planner model {model_name} failed: {e}")
                continue
        raise last_error or RuntimeError("No Gemini models available")


class AIPlannerService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        if provider is None:
            provider = self._auto_detect_provider()
        self.provider = provider

    @staticmethod
    def _auto_detect_provider() -> LLMProvider:
        """Automatically detects and configures the best available AI provider."""
        try:
            import config
            api_key = getattr(config, "GEMINI_API_KEY", "").strip()
            if api_key and api_key != "your_gemini_api_key_here":
                logger.info("Gemini AI provider configured.")
                return GeminiLLMProvider(api_key=api_key)
        except Exception as e:
            logger.warning("Could not load AI config: %s", e)
        logger.info("No AI provider configured. Using deterministic engine.")
        return NullLLMProvider()

    def generate_plan(self, dna_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a trip plan. Always returns a verified, deterministic itinerary.
        If Gemini is available, enriches the itinerary with AI-generated narratives and tips.
        """
        # Deterministic engine (ground truth)
        plan_result = ItineraryEngine.generate(dna_dict)
        flat_stops = []
        for d in plan_result.get("days", []):
            flat_stops.extend(d.get("stops", []))

        budget_result = BudgetEngine.calculate_budget(
            dna_dict, flat_stops, plan_result.get("total_distance_km", 0.0)
        )
        feasibility_result = FeasibilityEngine.evaluate(dna_dict, budget_result, plan_result)

        is_ai_generated = False
        ai_narrative = None

        # Attempt Gemini AI enrichment (narrative only — never modifies verified structure)
        if not isinstance(self.provider, NullLLMProvider):
            try:
                dest_names = [s.get("name", "") for s in flat_stops[:5]]
                city = dna_dict.get("start_city", "Karnataka")
                days = dna_dict.get("days", 1)
                theme_list = ", ".join(dna_dict.get("interests", ["heritage"]))
                prompt = f"""You are a Karnataka tourism expert writing an enticing trip introduction.

Trip Details:
- Start: {city}
- Duration: {days} days  
- Themes: {theme_list}
- Key Destinations: {', '.join(dest_names)}

Write a warm, vivid 2-3 sentence introduction for this Karnataka journey. 
Focus on the emotion, culture, and unique experiences. 
Respond ONLY with a JSON object: {{"narrative": "<your text here>"}}"""

                result = self.provider.generate(prompt)
                if result and result.get("narrative"):
                    ai_narrative = result["narrative"]
                    is_ai_generated = True
            except Exception as e:
                logger.warning("AI narrative generation failed: %s", e)

        return {
            "itinerary": plan_result,
            "budget": budget_result,
            "feasibility": feasibility_result,
            "ai_meta": {
                "used_ai": is_ai_generated,
                "notice": "Gemini AI enriched" if is_ai_generated else "AI unavailable, using rule-based planner",
                "narrative": ai_narrative,
            }
        }


# Global singleton — auto-detects provider at startup
ai_planner_service = AIPlannerService()
