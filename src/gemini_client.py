"""
RetailIQ - Gemini API Client Integration
NexusTiQ24 Hackathon | Track: PS03 - Retail: Sales and Inventory Copilot

Provides safe, modular interaction with Google Gemini GenAI SDK.
- SDK: google-genai
- Model: gemini-3.5-flash-lite
- Reads GEMINI_API_KEY from environment / .env
- Fully isolated from analytics calculations
- Fails gracefully without crashing the server
"""

import os
from typing import Optional, Dict, Any

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

from src import config


class GeminiClient:
    """
    Encapsulates interaction with the Google GenAI SDK using gemini-3.5-flash-lite.
    Handles authentication, error recovery, timeouts, and missing key edge cases.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = (api_key or config.get_gemini_api_key()).strip()
        self.model = (model or config.GEMINI_MODEL).strip()
        self._client = None

    def is_configured(self) -> bool:
        """Returns True if a non-placeholder GEMINI_API_KEY is present."""
        if not self.api_key:
            # Refresh from environment in case it was set dynamically
            self.api_key = config.get_gemini_api_key()
        placeholder_values = {"", "your_gemini_api_key_here", "your_api_key_here", "none"}
        return bool(self.api_key and self.api_key.lower() not in placeholder_values)

    def _get_client(self):
        """Lazily instantiates and returns the GenAI client."""
        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai SDK is not installed in the current environment.")
        if not self.is_configured():
            raise ValueError("GEMINI_API_KEY is not configured.")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def check_availability(self) -> Dict[str, Any]:
        """
        Safely checks Gemini connectivity without exposing keys or credentials.
        Returns application-level status.
        """
        if not self.is_configured():
            return {
                "configured": False,
                "model": self.model,
                "available": False,
                "message": "Gemini API key is not configured."
            }

        if not GENAI_AVAILABLE:
            return {
                "configured": True,
                "model": self.model,
                "available": False,
                "message": "google-genai SDK is not installed."
            }

        try:
            client = self._get_client()
            # Send a micro-prompt to test live connectivity
            response = client.models.generate_content(
                model=self.model,
                contents="ping",
                config={"max_output_tokens": 5}
            )
            is_ok = bool(response and getattr(response, "text", None))
            return {
                "configured": True,
                "model": self.model,
                "available": is_ok,
                "message": "Gemini API connected successfully." if is_ok else "Gemini returned empty response."
            }
        except Exception as err:
            error_str = str(err)
            # Mask any potential credential exposure in error messages
            sanitized_err = "Authentication or quota error" if "40" in error_str else "Connection failed"
            return {
                "configured": True,
                "model": self.model,
                "available": False,
                "message": f"Gemini API is unavailable ({sanitized_err})."
            }

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_output_tokens: int = 512,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Sends a prompt to gemini-3.5-flash-lite and returns a clean, safe dictionary response.
        Does NOT perform business or math calculations.
        """
        if not self.is_configured():
            return {
                "success": False,
                "text": None,
                "model": self.model,
                "error": "Gemini API key is not configured. Set GEMINI_API_KEY in .env or environment."
            }

        if not prompt or not prompt.strip():
            return {
                "success": False,
                "text": None,
                "model": self.model,
                "error": "Prompt cannot be empty."
            }

        try:
            client = self._get_client()
            config_params: Dict[str, Any] = {
                "max_output_tokens": max_output_tokens,
                "temperature": temperature
            }
            if system_instruction:
                config_params["system_instruction"] = system_instruction

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config_params
            )

            generated_text = ""
            if response and hasattr(response, "text") and response.text:
                generated_text = response.text.strip()

            return {
                "success": True,
                "text": generated_text,
                "model": self.model,
                "error": None
            }

        except Exception as err:
            err_msg = str(err)
            # Sanitize error to prevent accidental secret leakage
            if "api_key" in err_msg.lower() or "400" in err_msg or "403" in err_msg:
                safe_err = "Gemini API authentication failed. Verify that GEMINI_API_KEY is valid."
            elif "429" in err_msg:
                safe_err = "Gemini API rate limit exceeded. Please retry shortly."
            else:
                safe_err = f"Gemini request failed: {err_msg[:120]}"

            return {
                "success": False,
                "text": None,
                "model": self.model,
                "error": safe_err
            }
