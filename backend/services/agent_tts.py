"""
TTS for AI agents when Session.Interaction.communicationMedia includes 'audio'.

Supports:
- OpenAI: OPENAI_API_KEY + AGENT_TTS_MODEL (e.g. tts-1)
- Azure OpenAI: AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY + AZURE_TTS_DEPLOYMENT
  (speech deployment name in Azure; separate from chat deployment AZURE_OPENAI_DEPLOYMENT)

Provider selection: AGENT_TTS_PROVIDER=auto|azure|openai (default auto).
"""
import os
import tempfile
import uuid
from typing import Optional, Tuple


def _upload_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'audio')


def save_audio_bytes(audio_bytes: bytes, ext: str = '.mp3') -> str:
    """Persist bytes under uploads/audio and return URL path for message playback."""
    upload_dir = _upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(upload_dir, unique_name)
    with open(path, 'wb') as f:
        f.write(audio_bytes)
    return f'/api/audio/{unique_name}'


def estimate_speech_duration_seconds(text: str) -> int:
    """Rough duration from word count (~130 wpm)."""
    words = len((text or '').split())
    if words < 1:
        return 1
    return max(1, int(words / 2.2 + 0.999))


def _speech_create_to_bytes(response) -> Tuple[Optional[bytes], Optional[str]]:
    """Normalize OpenAI / Azure OpenAI speech.create() responses to MP3 bytes."""
    data = getattr(response, 'content', None)
    if isinstance(data, (bytes, bytearray)) and len(data) > 0:
        return bytes(data), None
    if hasattr(response, 'stream_to_file'):
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            response.stream_to_file(tmp_path)
            with open(tmp_path, 'rb') as f:
                data = f.read()
            if not data:
                return None, 'empty TTS response'
            return data, None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    return None, 'unexpected TTS response shape'


def _tts_input_trim(text: str) -> str:
    tts_input = (text or '').strip()
    if not tts_input:
        return ''
    max_len = 4096
    if len(tts_input) > max_len:
        return tts_input[:max_len]
    return tts_input


def _openai_native_tts(tts_input: str) -> Tuple[Optional[bytes], Optional[str]]:
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        return None, 'OPENAI_API_KEY not set'

    voice = (os.getenv('AGENT_TTS_VOICE') or 'alloy').strip() or 'alloy'
    model = (os.getenv('AGENT_TTS_MODEL') or 'tts-1').strip() or 'tts-1'

    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=tts_input,
            response_format='mp3',
        )
        return _speech_create_to_bytes(response)
    except Exception as e:
        return None, str(e)


def _azure_openai_tts(tts_input: str) -> Tuple[Optional[bytes], Optional[str]]:
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '').strip()
    api_key = os.getenv('AZURE_OPENAI_API_KEY', '').strip()
    deployment = (os.getenv('AZURE_TTS_DEPLOYMENT') or '').strip()
    api_version = (os.getenv('AZURE_OPENAI_API_VERSION') or '2024-12-01-preview').strip()

    if not endpoint or not api_key:
        return None, 'AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY not set'
    if not deployment:
        return None, 'AZURE_TTS_DEPLOYMENT not set (Azure speech deployment name)'

    voice = (os.getenv('AGENT_TTS_VOICE') or 'alloy').strip() or 'alloy'

    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint.rstrip('/'),
        )
        # On Azure, `model` is the deployment name for the TTS model in your resource.
        response = client.audio.speech.create(
            model=deployment,
            voice=voice,
            input=tts_input,
            response_format='mp3',
        )
        return _speech_create_to_bytes(response)
    except Exception as e:
        return None, str(e)


def synthesize_agent_tts(text: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Synthesize speech to MP3 bytes via OpenAI or Azure OpenAI (see env docs).
    Returns (bytes, None) on success, (None, error_message) on failure.
    """
    tts_input = _tts_input_trim(text)
    if not tts_input:
        return None, 'empty text'

    provider = (os.getenv('AGENT_TTS_PROVIDER') or 'auto').strip().lower()
    if provider not in ('auto', 'azure', 'openai'):
        provider = 'auto'

    azure_ready = bool(
        os.getenv('AZURE_OPENAI_ENDPOINT', '').strip()
        and os.getenv('AZURE_OPENAI_API_KEY', '').strip()
        and (os.getenv('AZURE_TTS_DEPLOYMENT') or '').strip()
    )
    openai_ready = bool(os.getenv('OPENAI_API_KEY', '').strip())

    def try_azure() -> Tuple[Optional[bytes], Optional[str]]:
        return _azure_openai_tts(tts_input)

    def try_openai() -> Tuple[Optional[bytes], Optional[str]]:
        return _openai_native_tts(tts_input)

    if provider == 'azure':
        return try_azure()

    if provider == 'openai':
        return try_openai()

    # --- auto ---
    if azure_ready and openai_ready:
        data, err = try_azure()
        if data:
            return data, None
        data2, err2 = try_openai()
        if data2:
            return data2, None
        return None, f'Azure TTS failed ({err}); OpenAI fallback failed ({err2})'

    if azure_ready:
        return try_azure()

    if openai_ready:
        return try_openai()

    return (
        None,
        'No TTS configured: set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY + AZURE_TTS_DEPLOYMENT, '
        'or OPENAI_API_KEY (see .env.example)',
    )


def synthesize_openai_tts(text: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Deprecated alias for synthesize_agent_tts."""
    return synthesize_agent_tts(text)
