import asyncio
import base64
import logging
from abc import ABC, abstractmethod
from typing import Any

from curl_cffi import requests as curl_requests
from google import genai

from settings import settings

logger = logging.getLogger(__name__)

DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEEPSEEK_BASE_URL = "https://api.siliconflow.cn/v1"
REQUEST_TIMEOUT = 60


class APIError(Exception):
    pass


class LLMClient(ABC):
    supports_multimodal: bool = False

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        max_tokens: int = 1000,
    ) -> str: ...


class DoubaoClient(LLMClient):
    supports_multimodal = True

    def __init__(self):
        self.api_key = settings.doubao_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        max_tokens: int = 1000,
    ) -> str:
        content_parts: list[dict] = []

        if images:
            for img in images:
                content_parts.append({"type": "image_url", "image_url": {"url": img}})

        content_parts.append({"type": "text", "text": prompt})

        payload: dict[str, Any] = {
            "model": settings.doubao_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content_parts if images else prompt}],
        }

        logger.info(
            "[Doubao] 发送请求: images=%d prompt_len=%d",
            len(images) if images else 0, len(prompt),
        )

        async with curl_requests.AsyncSession() as client:
            response = await client.post(
                f"{DOUBAO_BASE_URL}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise APIError(f"Unexpected response format: {data}") from exc


class DeepSeekClient(LLMClient):
    supports_multimodal = False

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        max_tokens: int = 1000,
    ) -> str:
        payload = {
            "model": settings.deepseek_model,
            "max_tokens": max_tokens,
            "stream": False,
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        logger.info("[DeepSeek] 发送请求: prompt_len=%d", len(prompt))

        async with curl_requests.AsyncSession() as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise APIError(f"Unexpected response format: {data}") from exc


class GeminiClient(LLMClient):
    supports_multimodal = True

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self._client = genai.Client(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        max_tokens: int = 1000,
    ) -> str:
        loop = asyncio.get_event_loop()

        contents: list[Any] = []

        if images:
            for img_uri in images:
                if img_uri.startswith("data:image/"):
                    header, b64data = img_uri.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                    img_bytes = base64.b64decode(b64data)
                    contents.append({"mime_type": mime, "data": img_bytes})
                else:
                    contents.append(img_uri)

        contents.append(prompt)

        def _generate():
            return self._client.models.generate_content(
                model="gemini-1.5-flash",
                contents=contents,
            )

        logger.info("[Gemini] 发送请求: images=%d prompt_len=%d", len(images) if images else 0, len(prompt))
        response = await loop.run_in_executor(None, _generate)
        return response.text
