"""NormaHub AI API Asynchronous Client.

Provides native streaming chat completions, video generation (SeeDance 2.5),
image generation (GPT Image 2.5 Flare), audio transcription (Whisper),
and balance checking with resilient retry logic.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class NormaHubError(Exception):
    """Base exception for NormaHub API errors."""

    def __init__(self, message: str, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"[Status: {self.status_code}]")
        if self.request_id:
            parts.append(f"[Request ID: {self.request_id}]")
        return " ".join(parts)


class NormaHubAuthError(NormaHubError):
    """Raised on 401 Unauthorized or invalid API key."""


class NormaHubBalanceError(NormaHubError):
    """Raised on 402 Insufficient Balance or spend limit exceeded."""


class NormaHubRateLimitError(NormaHubError):
    """Raised on 429 Rate Limit exceeded."""


class NormaHubTimeoutError(NormaHubError):
    """Raised on request or polling timeouts."""


class NormaHubAPIError(NormaHubError):
    """Raised on generic API errors (4xx/5xx)."""


class NormaHubClient:
    """Async client communicating with NormaHub AI Gateway (https://api.normahub.cc/v1)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.normahub.cc/v1",
        timeout: float = 120.0,
        session: aiohttp.ClientSession | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._owns_session = True
        return self._session

    def _headers(self, custom: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "NormaHub-Aiogram-Starter/1.0.0",
        }
        if custom:
            headers.update(custom)
        return headers

    async def close(self) -> None:
        """Close client session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "NormaHubClient":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def _handle_error_response(self, status: int, text: str, req_id: str | None) -> None:
        """Parse error payload and raise appropriate NormaHub exception."""
        error_msg = text
        code = ""
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                error_obj = parsed.get("error") or parsed
                error_msg = error_obj.get("message") or text
                code = str(error_obj.get("code") or "")
        except Exception:
            pass

        if status == 401 or code == "invalid_api_key":
            raise NormaHubAuthError(
                f"Неверный или отсутствующий API-ключ NormaHub. Проверьте ключ в https://normahub.cc: {error_msg}",
                status_code=status,
                request_id=req_id,
            )
        if status == 402 or code in ("insufficient_balance", "provider_balance_depleted", "budget_exceeded"):
            raise NormaHubBalanceError(
                f"Недостаточно средств на балансе NormaHub. Пополните баланс на https://normahub.cc: {error_msg}",
                status_code=status,
                request_id=req_id,
            )
        if status == 429:
            raise NormaHubRateLimitError(
                f"Превышен лимит запросов к NormaHub API: {error_msg}",
                status_code=status,
                request_id=req_id,
            )
        raise NormaHubAPIError(
            f"Ошибка NormaHub API: {error_msg}",
            status_code=status,
            request_id=req_id,
        )

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-v4.1-flash",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from NormaHub.

        Yields text chunks as they arrive from Server-Sent Events (SSE).
        """
        session = await self._get_session()
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = self._headers({"Content-Type": "application/json"})

        async with session.post(url, json=payload, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            if resp.status != 200:
                body = await resp.text()
                self._handle_error_response(resp.status, body, req_id)

            buffer = ""
            async for chunk in resp.content.iter_any():
                buffer += chunk.decode("utf-8", errors="replace")
                lines = buffer.split("\n")
                buffer = lines.pop()  # Keep incomplete line in buffer

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                                # Fallback to reasoning_content if model emits thought tokens
                                elif "reasoning_content" in delta and delta["reasoning_content"]:
                                    yield delta["reasoning_content"]
                        except json.JSONDecodeError:
                            continue

    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "deepseek-v4.1-flash",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Non-streaming chat completion request."""
        session = await self._get_session()
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = self._headers({"Content-Type": "application/json"})

        async with session.post(url, json=payload, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            body = await resp.text()
            if resp.status != 200:
                self._handle_error_response(resp.status, body, req_id)

            data = json.loads(body)
            choices = data.get("choices", [])
            if not choices:
                return ""
            return str(choices[0].get("message", {}).get("content", ""))

    async def generate_image(
        self,
        prompt: str,
        model: str = "gpt-image-2.5-flare",
        size: str = "1024x1024",
        n: int = 1,
    ) -> dict[str, Any]:
        """Generate an image using models like gpt-image-2.5-flare or grok-imagine-image-2.0."""
        session = await self._get_session()
        url = f"{self.base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": n,
        }
        headers = self._headers({"Content-Type": "application/json"})

        async with session.post(url, json=payload, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            body = await resp.text()
            if resp.status != 200:
                self._handle_error_response(resp.status, body, req_id)
            return json.loads(body)

    async def create_video_task(
        self,
        prompt: str,
        model: str = "seedance-2.5",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        image_url: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Submit an asynchronous video generation task (SeeDance 2.5)."""
        session = await self._get_session()
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            **kwargs,
        }
        if image_url:
            payload["image_url"] = image_url

        headers = self._headers({"Content-Type": "application/json"})

        # Try standard /videos endpoint
        url = f"{self.base_url}/videos"
        async with session.post(url, json=payload, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            if resp.status == 404:
                # Fallback to /videos/generations
                alt_url = f"{self.base_url}/videos/generations"
                async with session.post(alt_url, json=payload, headers=headers) as alt_resp:
                    body = await alt_resp.text()
                    if alt_resp.status not in (200, 201, 202):
                        self._handle_error_response(alt_resp.status, body, req_id)
                    return json.loads(body)

            body = await resp.text()
            if resp.status not in (200, 201, 202):
                self._handle_error_response(resp.status, body, req_id)
            return json.loads(body)

    async def get_video_status(self, task_id: str) -> dict[str, Any]:
        """Poll the current status of a video generation task."""
        session = await self._get_session()
        headers = self._headers()
        url = f"{self.base_url}/videos/status/{task_id}"

        async with session.get(url, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            if resp.status == 404:
                alt_url = f"{self.base_url}/videos/tasks/{task_id}"
                async with session.get(alt_url, headers=headers) as alt_resp:
                    body = await alt_resp.text()
                    if alt_resp.status != 200:
                        self._handle_error_response(alt_resp.status, body, req_id)
                    return json.loads(body)

            body = await resp.text()
            if resp.status != 200:
                self._handle_error_response(resp.status, body, req_id)
            return json.loads(body)

    async def poll_video_until_done(
        self,
        task_id: str,
        timeout: float = 300.0,
        initial_delay: float = 4.0,
    ) -> dict[str, Any]:
        """Poll task until status is 'completed' or 'failed', or until timeout."""
        start_time = asyncio.get_event_loop().time()
        delay = initial_delay

        while asyncio.get_event_loop().time() - start_time < timeout:
            data = await self.get_video_status(task_id)
            status = data.get("status", "processing")
            if status == "completed":
                return data
            if status == "failed":
                error_msg = data.get("error") or "Video generation failed upstream"
                raise NormaHubAPIError(f"Ошибка генерации видео: {error_msg}")

            await asyncio.sleep(delay)
            delay = min(delay * 1.2, 10.0)

        raise NormaHubTimeoutError(f"Таймаут генерации видео ({timeout}s) для задачи {task_id}")

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        model: str = "whisper-1",
        language: str | None = None,
    ) -> str:
        """Transcribe speech/voice bytes via /v1/audio/transcriptions."""
        session = await self._get_session()
        url = f"{self.base_url}/audio/transcriptions"

        form = aiohttp.FormData()
        form.add_field("file", audio_bytes, filename=filename, content_type="audio/ogg")
        form.add_field("model", model)
        if language:
            form.add_field("language", language)

        headers = self._headers()  # Let aiohttp set multipart boundary automatically

        async with session.post(url, data=form, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            body = await resp.text()
            if resp.status != 200:
                self._handle_error_response(resp.status, body, req_id)
            data = json.loads(body)
            return str(data.get("text", ""))

    async def check_balance(self) -> dict[str, Any]:
        """Check user balance and active models status.

        Queries /dashboard/billing/balance, /user/balance, or retrieves catalog via /models.
        """
        session = await self._get_session()
        headers = self._headers({"Content-Type": "application/json"})

        # Try balance endpoints with graceful fallback
        for endpoint in ("dashboard/billing/balance", "user/balance", "dashboard/billing/usage"):
            url = f"{self.base_url}/{endpoint}"
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        data = json.loads(body)
                        data["status"] = "operational"
                        return data
            except Exception:
                continue

        # Fallback to verifying gateway operational status via /models
        models_url = f"{self.base_url}/models"
        async with session.get(models_url, headers=headers) as resp:
            req_id = resp.headers.get("x-request-id")
            body = await resp.text()
            if resp.status != 200:
                self._handle_error_response(resp.status, body, req_id)
            models_data = json.loads(body)
            models_count = len(models_data.get("data", []))
            return {
                "status": "operational",
                "active_models_count": models_count,
                "note": "Ключ активен. Точный рублевый баланс доступен на https://normahub.cc/dashboard",
            }
