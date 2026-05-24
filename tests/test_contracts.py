"""Tests für mstts Contracts — Contract-Driven TDD.

Testet die Pydantic-Contracts auf Typ-Validierung,
Constraint-Enforcement und Interface-Compliance.
"""

import pytest
from pydantic import ValidationError

from mstts.contracts import OutputFormat, TTSRequest, TTSResponse, Voice


class TestOutputFormat:
    """OutputFormat Enum Contract."""

    def test_mp3_exists(self):
        assert OutputFormat.MP3 == "mp3"

    def test_wav_exists(self):
        assert OutputFormat.WAV == "wav"

    def test_pcm_exists(self):
        assert OutputFormat.RAW_PCM == "pcm"


class TestVoiceContract:
    """Voice Pydantic Model Contract."""

    def test_valid_voice(self):
        v = Voice(
            id="de-DE-ConradNeural",
            name="Conrad",
            language="de-DE",
            gender="Male",
            engine="edge",
        )
        assert v.id == "de-DE-ConradNeural"
        assert v.engine == "edge"

    def test_voice_requires_all_fields(self):
        with pytest.raises(ValidationError):
            Voice(id="test")  # type: ignore


class TestTTSRequestContract:
    """TTSRequest Contract — was muss ein Request validieren?"""

    def test_minimal_request(self):
        """Minimaler Request: nur Text, Rest Defaults."""
        req = TTSRequest(text="Hallo Welt")
        assert req.text == "Hallo Welt"
        assert req.voice == "de-DE-ConradNeural"  # default
        assert req.format == OutputFormat.MP3  # default
        assert req.rate == 1.0
        assert req.pitch == 0.0

    def test_empty_text_rejected(self):
        """Leerer Text muss abgelehnt werden (Contract: min_length=1)."""
        with pytest.raises(ValidationError):
            TTSRequest(text="")

    def test_text_too_long_rejected(self):
        """Text > 100.000 Zeichen wird abgelehnt."""
        with pytest.raises(ValidationError):
            TTSRequest(text="x" * 100_001)

    def test_rate_bounds(self):
        """Rate muss 0.5-3.0 sein."""
        # Gültig
        TTSRequest(text="test", rate=0.5)
        TTSRequest(text="test", rate=3.0)
        # Ungültig
        with pytest.raises(ValidationError):
            TTSRequest(text="test", rate=0.4)
        with pytest.raises(ValidationError):
            TTSRequest(text="test", rate=3.1)

    def test_pitch_bounds(self):
        """Pitch muss -20.0 bis +20.0 sein."""
        TTSRequest(text="test", pitch=-20.0)
        TTSRequest(text="test", pitch=20.0)
        with pytest.raises(ValidationError):
            TTSRequest(text="test", pitch=-20.1)

    def test_full_request(self):
        """Vollständiger Request mit allen Feldern."""
        req = TTSRequest(
            text="Guten Tag, dies ist ein Test.",
            voice="de-DE-KatjaNeural",
            output_file="/tmp/test.mp3",
            format=OutputFormat.WAV,
            rate=1.2,
            pitch=2.0,
        )
        assert req.voice == "de-DE-KatjaNeural"
        assert req.format == OutputFormat.WAV
        assert req.output_file == "/tmp/test.mp3"


class TestTTSResponseContract:
    """TTSResponse Contract."""

    def test_success_response(self):
        resp = TTSResponse(
            success=True,
            output_file="/tmp/audio.mp3",
            duration_ms=3500,
            text_length=100,
            voice_used="de-DE-ConradNeural",
            engine_used="edge",
        )
        assert resp.success is True
        assert resp.duration_ms == 3500

    def test_error_response(self):
        resp = TTSResponse(
            success=False,
            error_message="Engine nicht verfügbar",
            voice_used="unknown",
            engine_used="none",
            text_length=0,
        )
        assert resp.success is False
        assert resp.error_message is not None
