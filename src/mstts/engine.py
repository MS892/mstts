"""
Edge TTS Engine — Implementiert TTSEngine Contract via Microsoft Edge TTS.

Verwendet die edge-tts Bibliothek (kostenlos, kein API-Key).
Fallback: System-TTS via subprocess (powershell/say/espeak).
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

from mstts.contracts import OutputFormat, TTSRequest, TTSResponse, TTSEngine, Voice


class EdgeTTSEngine:
    """TTS-Engine basierend auf Microsoft Edge TTS (edge-tts).

    Contract-Erfüllung:
    - TTSEngine Protocol wird vollständig implementiert
    - Alle Fehler werden als TTSResponse(success=False) zurückgegeben
    - Thread-safe durch asyncio-basierte Ausführung
    """

    engine_name = "edge"

    # Bekannte deutsche Stimmen
    _KNOWN_VOICES: list[Voice] = [
        Voice(id="de-DE-ConradNeural", name="Conrad", language="de-DE", gender="Male", engine="edge"),
        Voice(id="de-DE-KatjaNeural", name="Katja", language="de-DE", gender="Female", engine="edge"),
        Voice(id="de-DE-KillianNeural", name="Killian", language="de-DE", gender="Male", engine="edge"),
        Voice(id="de-DE-AmalaNeural", name="Amala", language="de-DE", gender="Female", engine="edge"),
        Voice(id="de-DE-SeraphinaNeural", name="Seraphina", language="de-DE", gender="Female", engine="edge"),
        Voice(id="en-US-AriaNeural", name="Aria", language="en-US", gender="Female", engine="edge"),
        Voice(id="en-US-GuyNeural", name="Guy", language="en-US", gender="Male", engine="edge"),
        Voice(id="en-US-JennyNeural", name="Jenny", language="en-US", gender="Female", engine="edge"),
    ]

    async def list_voices(self) -> list[Voice]:
        """Liste verfügbare Stimmen (bekannte + von edge-tts geladene)."""
        try:
            import edge_tts

            voices = await edge_tts.list_voices()
            result = []
            seen = {v.id for v in self._KNOWN_VOICES}
            result.extend(self._KNOWN_VOICES)

            for v in voices:
                vid = v.get("ShortName", "")
                if vid not in seen:
                    result.append(
                        Voice(
                            id=vid,
                            name=v.get("FriendlyName", vid),
                            language=v.get("Locale", ""),
                            gender=v.get("Gender", "Neutral"),
                            engine="edge",
                        )
                    )
                    seen.add(vid)
            return result
        except ImportError:
            return list(self._KNOWN_VOICES)
        except Exception:
            return list(self._KNOWN_VOICES)

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Führe Sprachsynthese via edge-tts durch.

        Contract: Darf keine Exception werfen.
        """
        start_time = time.time()

        try:
            import edge_tts

            output_file = request.output_file
            if output_file is None:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=f".{request.format.value}", delete=False
                )
                output_file = tmp.name
                tmp.close()

            # Baue Communicate-Objekt
            communicate = edge_tts.Communicate(
                text=request.text,
                voice=request.voice,
                rate=_rate_to_string(request.rate),
                pitch=_pitch_to_string(request.pitch),
            )

            # Speichere Audio
            await communicate.save(output_file)

            duration_ms = int((time.time() - start_time) * 1000)

            return TTSResponse(
                success=True,
                output_file=output_file,
                duration_ms=duration_ms,
                text_length=len(request.text),
                voice_used=request.voice,
                engine_used=self.engine_name,
            )

        except ImportError:
            # edge-tts nicht installiert — versuche System-Fallback
            return await self._system_fallback(request, start_time)

        except Exception as e:
            return TTSResponse(
                success=False,
                error_message=str(e),
                voice_used=request.voice,
                engine_used=self.engine_name,
                text_length=len(request.text),
            )

    async def _system_fallback(
        self, request: TTSRequest, start_time: float
    ) -> TTSResponse:
        """System-TTS-Fallback ohne externe Abhängigkeiten."""
        try:
            system = platform.system()
            output_file = request.output_file or tempfile.mktemp(
                suffix=f".{request.format.value}"
            )

            if system == "Windows":
                await self._speak_windows(request.text, request.voice)
            elif system == "Darwin":
                await self._speak_macos(request.text, request.voice)
            else:
                await self._speak_linux(request.text, request.voice)

            duration_ms = int((time.time() - start_time) * 1000)

            return TTSResponse(
                success=True,
                output_file=output_file,
                duration_ms=duration_ms,
                text_length=len(request.text),
                voice_used=request.voice,
                engine_used=f"system-{system.lower()}",
            )

        except Exception as e:
            return TTSResponse(
                success=False,
                error_message=f"System-Fallback fehlgeschlagen: {e}",
                voice_used=request.voice,
                engine_used=f"system-{platform.system().lower()}",
                text_length=len(request.text),
            )

    async def _speak_windows(self, text: str, voice: str) -> None:
        """Windows SAPI TTS via PowerShell."""
        # Escape text for PowerShell
        escaped = text.replace('"', '""')
        ps_script = f'''
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $synth.Speak("{escaped}")
        '''
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-Command", ps_script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    async def _speak_macos(self, text: str, voice: str) -> None:
        """macOS say-Kommando."""
        proc = await asyncio.create_subprocess_exec(
            "say", text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    async def _speak_linux(self, text: str, voice: str) -> None:
        """Linux espeak-ng."""
        proc = await asyncio.create_subprocess_exec(
            "espeak-ng", text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()


def _rate_to_string(rate: float) -> str:
    """Konvertiere Rate-Faktor (0.5-3.0) zu edge-tts String."""
    if rate == 1.0:
        return "+0%"
    pct = int((rate - 1.0) * 100)
    return f"{'+' if pct >= 0 else ''}{pct}%"


def _pitch_to_string(pitch: float) -> str:
    """Konvertiere Pitch (-20..+20 Hz) zu edge-tts String."""
    if pitch == 0.0:
        return "+0Hz"
    return f"{'+' if pitch >= 0 else ''}{pitch:.0f}Hz"
