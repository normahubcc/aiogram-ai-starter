"""Tests for NormaHubClient async API wrapper."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.client.normahub import (
    NormaHubAuthError,
    NormaHubBalanceError,
    NormaHubClient,
    NormaHubRateLimitError,
)


def make_mock_session(mock_resp) -> MagicMock:
    """Helper to mock aiohttp ClientSession with proper async context manager."""
    session = MagicMock()
    context = AsyncMock()
    context.__aenter__.return_value = mock_resp
    context.__aexit__.return_value = None
    session.post.return_value = context
    session.get.return_value = context
    return session


@pytest.fixture
def client():
    """Create test client instance."""
    return NormaHubClient(
        api_key="nr_hub_test_key_12345",
        base_url="https://api.normahub.cc/v1/",
    )


def test_client_init(client):
    """Test client initialization and base_url normalization."""
    assert client.base_url == "https://api.normahub.cc/v1"
    assert client.api_key == "nr_hub_test_key_12345"
    headers = client._headers()
    assert headers["Authorization"] == "Bearer nr_hub_test_key_12345"
    assert "User-Agent" in headers


@pytest.mark.asyncio
async def test_stream_chat_completion_sse(client):
    """Test SSE streaming parser yielding tokens from chunks."""
    sse_chunks = [
        b'data: {"choices": [{"delta": {"content": "\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"}}]}\n\n',
        b'data: {"choices": [{"delta": {"content": ", \xd0\xbc\xd0\xb8\xd1\x80!"}}]}\n\n',
        b"data: [DONE]\n\n",
    ]

    async def mock_iter_any():
        for chunk in sse_chunks:
            yield chunk

    mock_content = MagicMock()
    mock_content.iter_any = mock_iter_any

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content = mock_content
    mock_resp.headers = {"x-request-id": "req-12345"}

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        tokens = []
        async for token in client.stream_chat_completion(
            messages=[{"role": "user", "content": "Тест"}],
            model="deepseek-v4.1-flash",
        ):
            tokens.append(token)

        assert "".join(tokens) == "Привет, мир!"


@pytest.mark.asyncio
async def test_create_chat_completion_non_streaming(client):
    """Test non-streaming chat completion request."""
    mock_payload = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {"role": "assistant", "content": "НормаХаб готов к работе!"},
            }
        ],
    }

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"x-request-id": "req-999"}
    mock_resp.text.return_value = json.dumps(mock_payload)

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        result = await client.create_chat_completion(
            messages=[{"role": "user", "content": "Статус"}],
        )
        assert result == "НормаХаб готов к работе!"


@pytest.mark.asyncio
async def test_client_error_handling_auth(client):
    """Test 401 raises NormaHubAuthError."""
    mock_resp = AsyncMock()
    mock_resp.status = 401
    mock_resp.headers = {"x-request-id": "req-auth-fail"}
    mock_resp.text.return_value = json.dumps({"error": {"message": "Invalid API key", "code": "invalid_api_key"}})

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        with pytest.raises(NormaHubAuthError) as exc_info:
            await client.create_chat_completion(messages=[])
        assert exc_info.value.status_code == 401
        assert "Неверный или отсутствующий API-ключ" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_error_handling_balance(client):
    """Test 402 raises NormaHubBalanceError."""
    mock_resp = AsyncMock()
    mock_resp.status = 402
    mock_resp.headers = {"x-request-id": "req-balance-fail"}
    mock_resp.text.return_value = json.dumps({"error": {"message": "Zero balance", "code": "insufficient_balance"}})

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        with pytest.raises(NormaHubBalanceError) as exc_info:
            await client.create_chat_completion(messages=[])
        assert exc_info.value.status_code == 402
        assert "Недостаточно средств на балансе" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_error_handling_rate_limit(client):
    """Test 429 raises NormaHubRateLimitError."""
    mock_resp = AsyncMock()
    mock_resp.status = 429
    mock_resp.headers = {"x-request-id": "req-limit"}
    mock_resp.text.return_value = json.dumps({"error": {"message": "Rate limit exceeded"}})

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        with pytest.raises(NormaHubRateLimitError):
            await client.create_chat_completion(messages=[])


@pytest.mark.asyncio
async def test_create_video_task(client):
    """Test submitting video generation task."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.text.return_value = json.dumps({"id": "task_seedance_123", "status": "pending"})

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        res = await client.create_video_task(prompt="Космос", model="seedance-2.5")
        assert res["id"] == "task_seedance_123"
        assert res["status"] == "pending"


@pytest.mark.asyncio
async def test_generate_image(client):
    """Test image generation endpoint."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.text.return_value = json.dumps({
        "created": 1234567890,
        "data": [{"url": "https://img.normahub.cc/test.png"}],
    })

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        res = await client.generate_image(prompt="Закат на Байкале")
        assert len(res["data"]) == 1
        assert res["data"][0]["url"] == "https://img.normahub.cc/test.png"


@pytest.mark.asyncio
async def test_transcribe_audio(client):
    """Test voice/audio transcription endpoint."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.text.return_value = json.dumps({"text": "Привет, как дела?"})

    mock_session = make_mock_session(mock_resp)

    with patch.object(client, "_get_session", return_value=mock_session):
        res = await client.transcribe_audio(audio_bytes=b"fake-ogg-bytes")
        assert res == "Привет, как дела?"


@pytest.mark.asyncio
async def test_check_balance(client):
    """Test balance check fallback to /models."""
    mock_404 = AsyncMock()
    mock_404.status = 404

    mock_models = AsyncMock()
    mock_models.status = 200
    mock_models.headers = {}
    mock_models.text.return_value = json.dumps({
        "data": [{"id": "deepseek-v4.1-flash"}, {"id": "claude-sonnet-5-5"}],
    })

    def get_side_effect(url, **kwargs):
        context = AsyncMock()
        if "models" in url:
            context.__aenter__.return_value = mock_models
        else:
            context.__aenter__.return_value = mock_404
        context.__aexit__.return_value = None
        return context

    mock_session = MagicMock()
    mock_session.get.side_effect = get_side_effect

    with patch.object(client, "_get_session", return_value=mock_session):
        res = await client.check_balance()
        assert res["status"] == "operational"
        assert res["active_models_count"] == 2
