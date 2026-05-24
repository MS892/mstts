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
        """Führe Sprachsynthese durch. OneCore (neural) > edge-tts > SAPI."""
        start_time = time.time()

        # 1) OneCore first — always works offline, neural quality
        locale = request.voice.split("-")[0] + "-" + request.voice.split("-")[1] if "-" in request.voice else ""
        onecore_voice = self._ONECORE_MAP.get(locale, "")
        if onecore_voice and self._ONECORE_EXE.exists():
            try:
                chunks = self._split_text(request.text, 400)
                if len(chunks) == 1:
                    wav = await self._synth_onecore(onecore_voice, chunks[0])
                    if wav:
                        self._play_wav_mci(wav)
                        os.unlink(wav)
                        return TTSResponse(success=True, output_file=request.output_file or wav,
                            duration_ms=int((time.time()-start_time)*1000), text_length=len(request.text),
                            voice_used=request.voice, engine_used="onecore")
                else:
                    merged = await self._synth_chunked(onecore_voice, chunks)
                    if merged:
                        self._play_wav_mci(merged)
                        os.unlink(merged)
                        return TTSResponse(success=True, output_file=request.output_file or merged,
                            duration_ms=int((time.time()-start_time)*1000), text_length=len(request.text),
                            voice_used=request.voice, engine_used="onecore")
            except Exception:
                pass

        # 2) edge-tts — cloud, may be blocked
        try:
            import edge_tts

            output_file = request.output_file
            if output_file is None:
                tmp = tempfile.NamedTemporaryFile(
                    suffix=f".{request.format.value}", delete=False
                )
                output_file = tmp.name
                tmp.close()

            communicate = edge_tts.Communicate(
                text=request.text,
                voice=request.voice,
                rate=_rate_to_string(request.rate),
                pitch=_pitch_to_string(request.pitch),
            )
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
            pass
        except Exception:
            pass

        # 3) SAPI fallback (legacy)
        return await self._system_fallback(request, start_time)

    async def _system_fallback(
        self, request: TTSRequest, start_time: float
    ) -> TTSResponse:
        """System-TTS-Fallback ohne externe Abhängigkeiten."""
        try:
            system = platform.system()
            output_file = request.output_file or tempfile.mktemp(
                suffix=f".{request.format.value}"
            )

            engine_used = f"system-{system.lower()}"
            if system == "Windows":
                engine_used = await self._speak_windows(request.text, request.voice)
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
                engine_used=engine_used,
            )

        except Exception as e:
            return TTSResponse(
                success=False,
                error_message=f"System-Fallback fehlgeschlagen: {e}",
                voice_used=request.voice,
                engine_used=f"system-{platform.system().lower()}",
                text_length=len(request.text),
            )

    # Mapping: edge-tts locale → OneCore voice display name (WinRT neural)
    _ONECORE_MAP = {
        "de-DE": "Microsoft Michael",
        "en-US": "Microsoft Mark",
    }

    # Fallback: SAPI voice names (legacy, used only if OneCoreTTS.exe unavailable)
    _SAPI_LOCALE_MAP = {
        "de-DE": "Microsoft Stefan",
        "en-US": "Microsoft Mark",
    }

    _ONECORE_EXE = Path(__file__).parent / "OneCoreTTS.exe"

    async def _speak_windows(self, text: str, voice: str) -> str:
        """Windows TTS: OneCore (neural) bevorzugt, SAPI als Fallback."""
        import tempfile

        locale = voice.split("-")[0] + "-" + voice.split("-")[1] if "-" in voice else ""

        # OneCore (neural)
        onecore_voice = self._ONECORE_MAP.get(locale, "")
        if onecore_voice and self._ONECORE_EXE.exists():
            try:
                chunks = self._split_text(text, 400)
                if len(chunks) == 1:
                    wav = self._synth_onecore(onecore_voice, chunks[0])
                    if wav:
                        self._play_wav_mci(wav)
                        os.unlink(wav)
                        return "onecore"
                else:
                    merged = self._synth_chunked(onecore_voice, chunks)
                    if merged:
                        self._play_wav_mci(merged)
                        os.unlink(merged)
                        return "onecore"
            except Exception:
                pass

        # SAPI (legacy)
        sapi_voice = self._SAPI_LOCALE_MAP.get(locale, "")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as tf:
            tf.write(text)
            tmp_path = tf.name
        try:
            ps = f'Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
            if sapi_voice:
                ps += f"$s.SelectVoice('{sapi_voice}');"
            ps += f"$s.Speak([System.IO.File]::ReadAllText('{tmp_path}',[System.Text.Encoding]::UTF8))"
            proc = await asyncio.create_subprocess_exec("powershell", "-Command", ps,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await proc.wait()
        finally:
            os.unlink(tmp_path)
        return "system-windows"

    async def _synth_onecore(self, voice: str, text: str) -> str | None:
        """Synthesize single chunk via OneCoreTTS.exe. Returns WAV path or None."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav = tf.name
        proc = await asyncio.create_subprocess_exec(
            str(self._ONECORE_EXE), voice, wav,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0 and os.path.getsize(wav) > 100:
            return wav
        os.unlink(wav)
        return None

    async def _synth_chunked(self, voice: str, chunks: list[str]) -> str | None:
        """Synthesize chunks, merge WAVs. Returns merged WAV path or None."""
        import tempfile
        cwavs = []
        try:
            for chunk in chunks:
                cw = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                cw.close()
                cwavs.append(cw.name)
                proc = await asyncio.create_subprocess_exec(
                    str(self._ONECORE_EXE), voice, cw.name,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await proc.communicate(chunk.encode("utf-8"))
                if proc.returncode != 0 or os.path.getsize(cw.name) < 100:
                    return None
            merged = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            merged.close()
            self._merge_wavs(cwavs, merged.name)
            return merged.name
        finally:
            for cw in cwavs:
                try: os.unlink(cw)
                except: pass

    @staticmethod
    def _split_text(text: str, max_chars: int = 400) -> list[str]:
        """Split text into sentence-aware chunks."""
        import re
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) <= max_chars:
                current = (current + " " + s).strip()
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _merge_wavs(wav_paths: list[str], output_path: str) -> None:
        """Merge multiple PCM WAV files into one."""
        import struct
        # Read headers and data from all chunks
        all_data = bytearray()
        sample_rate = bits = channels = 0
        for wp in wav_paths:
            with open(wp, "rb") as f:
                f.seek(22)
                c = struct.unpack("<H", f.read(2))[0]
                f.seek(24)
                sr = struct.unpack("<I", f.read(4))[0]
                f.seek(34)
                bps = struct.unpack("<H", f.read(2))[0]
                # Find data chunk
                f.seek(36)
                while True:
                    chunk_id = f.read(4)
                    chunk_size = struct.unpack("<I", f.read(4))[0]
                    if chunk_id == b"data":
                        all_data.extend(f.read(chunk_size))
                        break
                    f.seek(chunk_size, 1)
                if not sample_rate:
                    sample_rate, bits, channels = sr, bps, c
        # Write merged WAV
        byte_rate = sample_rate * channels * bits // 8
        block_align = channels * bits // 8
        with open(output_path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + len(all_data)))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))
            f.write(struct.pack("<H", 1))  # PCM
            f.write(struct.pack("<H", channels))
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", byte_rate))
            f.write(struct.pack("<H", block_align))
            f.write(struct.pack("<H", bits))
            f.write(b"data")
            f.write(struct.pack("<I", len(all_data)))
            f.write(all_data)

    @staticmethod
    def _play_wav_mci(wav_path: str) -> None:
        """Play WAV via Win32 MCI (synchronous, any size)."""
        import ctypes
        wav_abs = os.path.abspath(wav_path)
        ctypes.windll.winmm.mciSendStringW(
            f'open "{wav_abs}" type waveaudio alias tts', None, 0, None
        )
        ctypes.windll.winmm.mciSendStringW(
            "play tts wait", None, 0, None
        )
        ctypes.windll.winmm.mciSendStringW(
            "close tts", None, 0, None
        )

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
    pct = round((rate - 1.0) * 100)
    return f"{'+' if pct >= 0 else ''}{pct}%"


def _pitch_to_string(pitch: float) -> str:
    """Konvertiere Pitch (-20..+20 Hz) zu edge-tts String."""
    if pitch == 0.0:
        return "+0Hz"
    return f"{'+' if pitch >= 0 else ''}{pitch:.0f}Hz"
