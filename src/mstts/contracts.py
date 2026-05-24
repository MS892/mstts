"""
Contracts für mstts — die kanonischen Datenmodelle und Schnittstellen.

Contract-Driven Development:
Alle Komponenten kommunizieren ausschließlich über diese Contracts.
Tests validieren die Contracts, nicht die Implementierung.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


# =============================================================================
# Output Format Contract
# =============================================================================

class OutputFormat(StrEnum):
    """Unterstützte Audio-Ausgabeformate."""

    MP3 = "mp3"
    WAV = "wav"
    RAW_PCM = "pcm"


# =============================================================================
# Voice Contract
# =============================================================================

class Voice(BaseModel):
    """Eine verfügbare TTS-Stimme."""

    id: str = Field(description="Eindeutige Stimmen-ID (z.B. de-DE-ConradNeural)")
    name: str = Field(description="Anzeigename (z.B. Conrad)")
    language: str = Field(description="Sprachcode (z.B. de-DE)")
    gender: str = Field(description="Gender (Male, Female, Neutral)")
    engine: str = Field(description="Engine-Name (edge, system, espeak)")


# =============================================================================
# TTS Request Contract
# =============================================================================

class TTSRequest(BaseModel):
    """Ein TTS-Request — was soll vorgelesen werden?"""

    text: str = Field(
        min_length=1, max_length=100_000,
        description="Der vorzulesende Text",
    )
    voice: str = Field(
        default="de-DE-ConradNeural",
        description="Stimmen-ID",
    )
    output_file: str | None = Field(
        default=None,
        description="Ausgabedatei (None = stdout/live playback)",
    )
    format: OutputFormat = Field(
        default=OutputFormat.MP3,
        description="Audioformat",
    )
    rate: float = Field(
        default=1.0, ge=0.5, le=3.0,
        description="Sprechgeschwindigkeit (0.5-3.0)",
    )
    pitch: float = Field(
        default=0.0, ge=-20.0, le=20.0,
        description="Tonhöhenänderung in Hz",
    )


# =============================================================================
# TTS Response Contract
# =============================================================================

class TTSResponse(BaseModel):
    """Ergebnis eines TTS-Requests."""

    success: bool = Field(description="War die Sprachsynthese erfolgreich?")
    output_file: str | None = Field(default=None, description="Pfad zur Audio-Datei")
    duration_ms: int = Field(default=0, description="Audiodauer in Millisekunden")
    text_length: int = Field(default=0, description="Länge des Quelltextes")
    voice_used: str = Field(default="", description="Verwendete Stimme")
    engine_used: str = Field(default="", description="Verwendete Engine")
    error_message: str | None = Field(default=None, description="Fehlermeldung")


# =============================================================================
# TTS Engine Contract (Interface)
# =============================================================================

@runtime_checkable
class TTSEngine(Protocol):
    """Contract für TTS-Engines.

    Jede TTS-Engine muss dieses Protokoll implementieren.
    Neue Engines (System-SAPI, Google Cloud TTS, etc.) werden
    durch Implementierung dieses Contracts integriert.
    """

    @property
    def engine_name(self) -> str:
        """Eindeutiger Engine-Name."""
        ...

    async def list_voices(self) -> list[Voice]:
        """Liste aller verfügbaren Stimmen dieser Engine."""
        ...

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Führe Sprachsynthese durch.

        Args:
            request: Der TTS-Request mit Text und Parametern.

        Returns:
            TTSResponse mit Ergebnis oder Fehler.

        Contract:
            - Darf keine Exception werfen (fange intern, gib TTSResponse mit success=False)
            - Muss thread-safe sein
            - output_file=None bedeutet: temporäre Datei erstellen und Pfad zurückgeben
        """
        ...


# =============================================================================
# CLI Context Contract
# =============================================================================

@dataclass
class CLIContext:
    """Kontext für CLI-Ausführung — hält Engine-Referenz."""

    engine: TTSEngine
    default_voice: str = "de-DE-ConradNeural"
    default_format: OutputFormat = OutputFormat.MP3
