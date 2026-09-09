"""Test Nvidia NIM API with DeepSeek V4 Flash model.

Verifies the reported hang for deepseek-v4-flash on Nvidia NIM.
The bug report (https://github.com/anomalyco/opencode/issues/24264) claims
chat_template_kwargs is needed, but testing shows the model hangs regardless —
it appears to be a server-side issue with Nvidia.

Usage:
    python3 -m pytest server/tests/test_nvidia_deepseek.py -v -s
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error

import pytest


def _get_nvidia_api_key() -> str:
    """Get the Nvidia API key from the DB or env."""
    key = os.environ.get("NVIDIA_API_KEY")
    if key:
        return key

    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        from server.models.providers.api_provider import ApiProvider
        from server.models.providers.api_key import ApiKey
        nvidia = ApiProvider.objects.get(name="Nvidia")
        apikey = ApiKey.objects.filter(api_provider=nvidia, enabled=True).first()
        if apikey:
            return apikey.key
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    pytest.skip("No NVIDIA_API_KEY in env and DB lookup failed")


def _call_nvidia_nim(
    api_key: str,
    model: str,
    messages: list[dict] | None = None,
    stream: bool = False,
    chat_template_kwargs: dict | None = None,
    timeout: int = 15,
) -> dict:
    """Raw HTTP call to Nvidia NIM. Returns success/error/elapsed."""
    if messages is None:
        messages = [{"role": "user", "content": "Say ok"}]

    payload: dict = {"model": model, "messages": messages, "stream": stream}
    if chat_template_kwargs is not None:
        payload["chat_template_kwargs"] = chat_template_kwargs

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            elapsed = time.time() - start
            if stream:
                return {"success": len(body) > 0, "elapsed": elapsed, "bytes": len(body)}
            parsed = json.loads(body)
            content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": bool(content), "response": content, "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"success": False, "error": str(e), "elapsed": elapsed}


class TestNvidiaNimHealth:
    """Verify the Nvidia API key works with a known-good model."""

    def test_nemotron_super_responds(self):
        api_key = _get_nvidia_api_key()
        result = _call_nvidia_nim(api_key, model="nvidia/nemotron-3-super-120b-a12b")
        assert result["success"], f"Nemotron should work: {result.get('error')}"
        assert result["elapsed"] < 10, f"Took too long: {result['elapsed']:.1f}s"


class TestDeepSeekV4Hangs:
    """Confirm deepseek-v4-flash hangs on Nvidia NIM regardless of parameters."""

    @pytest.mark.parametrize(
        "stream,chat_kwargs",
        [
            (False, None),
            (True, None),
            (True, {"enable_thinking": True, "thinking": True}),
            (False, {"enable_thinking": True, "thinking": True}),
        ],
        ids=[
            "no-stream no-kwargs",
            "stream no-kwargs",
            "stream + kwargs",
            "no-stream + kwargs",
        ],
    )
    def test_deepseek_v4_flash_hangs(self, stream, chat_kwargs):
        api_key = _get_nvidia_api_key()
        result = _call_nvidia_nim(
            api_key,
            model="deepseek-ai/deepseek-v4-flash-0731",
            stream=stream,
            chat_template_kwargs=chat_kwargs,
            timeout=12,
        )
        print(f"  stream={stream} kwargs={chat_kwargs}: {result}")
        if result["success"]:
            pytest.fail(
                "deepseek-v4-flash responded — Nvidia may have fixed the hang. "
                "Update this test and nvidia-nim.md if stable."
            )
        else:
            print(f"  CONFIRMED HANG: {result.get('error', 'timeout')} ({result['elapsed']:.1f}s)")
