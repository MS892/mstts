"""Tests für die EdgeTTSEngine.

Contract-Tests: Validieren dass die Engine den TTSEngine-Contract erfüllt.
"""

import pytest
from mstts.contracts import (
    OutputFormat,
    TTSRequest,
    TTSResponse,
    TTSEngine,
    Voice,
)
from mstts.engine import EdgeTTSEngine, _rate_to_string, _pitch_to_string


class TestRateConversion:
    """Rate-Konvertierung (helper)."""

    def test_normal_rate(self):
        assert _rate_to_string(1.0) == "+0%"

    def test_faster(self):
        assert "+20%" in _rate_to_string(1.2)

    def test_slower(self):
        assert "-30%" in _rate_to_string(0.7)


class TestPitchConversion:
    """Pitch-Konvertierung (helper)."""

    def test_default(self):
        assert _pitch_to_string(0.0) == "+0Hz"

    def test_positive(self):
        assert "+5Hz" in _pitch_to_string(5.0)

    def test_negative(self):
        assert "-10Hz" in _pitch_to_string(-10.0)


class TestEdgeTTSEngineContract:
    """Validiert dass EdgeTTSEngine den TTSEngine Contract erfüllt."""

    @pytest.fixture
    def engine(self):
        return EdgeTTSEngine()

    def test_implements_protocol(self, engine):
        """Engine implementiert TTSEngine Protocol."""
        assert isinstance(engine, TTSEngine)

    def test_engine_name(self, engine):
        assert engine.engine_name == "edge"

    @pytest.mark.asyncio
    async def test_list_voices_returns_list(self, engine):
        """list_voices() gibt list[Voice] zurück."""
        voices = await engine.list_voices()
        assert isinstance(voices, list)
        assert len(voices) >= 6  # mindestens die bekannten DE-Stimmen
        for voice in voices:
            assert isinstance(voice, Voice)
            assert voice.id
            assert voice.engine == "edge"

    @pytest.mark.asyncio
    async def test_list_voices_contains_german(self, engine):
        """Deutsche Stimmen sind verfügbar."""
        voices = await engine.list_voices()
        german = [v for v in voices if v.language == "de-DE"]
        assert len(german) >= 2

    @pytest.mark.asyncio
    async def test_synthesize_returns_response(self, engine):
        """synthesize() gibt TTSResponse zurück (Contract)."""
        request = TTSRequest(text="Test")
        response = await engine.synthesize(request)
        assert isinstance(response, TTSResponse)
        # Ohne edge-tts installiert: erwarte Fallback
        assert response.text_length == 4

    @pytest.mark.asyncio
    async def test_synthesize_never_raises(self, engine):
        """synthesize() darf NIE eine Exception werfen (Contract)."""
        # Ungültige Stimme
        request = TTSRequest(text="Test", voice="invalid-voice-xyz")
        try:
            response = await engine.synthesize(request)
            assert isinstance(response, TTSResponse)
        except Exception as e:
            pytest.fail(f"Engine hat Exception geworfen: {e}")

    @pytest.mark.asyncio
    async def test_empty_text_handled(self, engine):
        """Auch bei Problem-Requests keine Exception."""
        # Test mit minimalem Text
        request = TTSRequest(text=".")
        response = await engine.synthesize(request)
        assert isinstance(response, TTSResponse)
