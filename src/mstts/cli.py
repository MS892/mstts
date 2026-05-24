"""
mstts CLI — Text-to-Speech via Kommandozeile.

Commands:
    speak       Text direkt vorlesen
    speak-file  Datei vorlesen
    list-voices Verfügbare Stimmen auflisten
    version     Version anzeigen
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from mstts.contracts import CLIContext, OutputFormat, TTSRequest
from mstts.engine import EdgeTTSEngine

app = typer.Typer(
    name="mstts",
    help="[mstts] Minimal Speech TTS — Text-to-Speech fuer die Kommandozeile",
    add_completion=False,
)

console = Console(force_terminal=True)
engine = EdgeTTSEngine()
ctx = CLIContext(engine=engine)


def _run_async(coro):
    """Hilfsfunktion: asyncio in sync-Kontext ausführen."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@app.command()
def speak(
    text: str = typer.Argument(..., help="Der vorzulesende Text"),
    voice: str = typer.Option(
        "de-DE-ConradNeural", "--voice", "-v",
        help="Stimmen-ID (z.B. de-DE-ConradNeural)",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Audio-Datei speichern (sonst: live Wiedergabe)",
    ),
    rate: float = typer.Option(
        1.0, "--rate", "-r",
        min=0.5, max=3.0,
        help="Sprechgeschwindigkeit (0.5-3.0)",
    ),
    pitch: float = typer.Option(
        0.0, "--pitch", "-p",
        min=-20.0, max=20.0,
        help="Tonhöhe ändern (-20..+20 Hz)",
    ),
    format: str = typer.Option(
        "mp3", "--format", "-f",
        help="Audio-Format (mp3, wav)",
    ),
) -> None:
    """Lies Text direkt vor."""
    fmt = OutputFormat.MP3
    if format == "wav":
        fmt = OutputFormat.WAV
    elif format == "pcm":
        fmt = OutputFormat.RAW_PCM

    request = TTSRequest(
        text=text,
        voice=voice,
        output_file=str(output) if output else None,
        format=fmt,
        rate=rate,
        pitch=pitch,
    )

    console.print(f"[*] [bold]Spreche[/] ({len(text)} Zeichen, Stimme: {voice})")

    response = _run_async(engine.synthesize(request))

    if response.success:
        engine_tag = f"\\[{response.engine_used}]"
        if response.output_file:
            console.print(
                f"[green][OK] {engine_tag} Audio gespeichert: {response.output_file}[/] "
                f"({response.duration_ms}ms)"
            )
        else:
            console.print(
                f"[green][OK] {engine_tag} Vorgelesen[/] ({response.duration_ms}ms)"
            )
    else:
        console.print(f"[red][!!] Fehler: {response.error_message}[/]")
        raise typer.Exit(1)


@app.command("speak-file")
def speak_file(
    file: Path = typer.Argument(..., help="Pfad zur Textdatei"),
    voice: str = typer.Option(
        "de-DE-ConradNeural", "--voice", "-v",
        help="Stimmen-ID",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Audio-Datei speichern",
    ),
    rate: float = typer.Option(1.0, "--rate", "-r", min=0.5, max=3.0),
) -> None:
    """Lies eine Textdatei vor."""
    if not file.exists():
        console.print(f"[red][!!] Datei nicht gefunden: {file}[/]")
        raise typer.Exit(1)

    text = file.read_text(encoding="utf-8")
    console.print(f"[>] [bold]{file.name}[/] ({len(text)} Zeichen)")

    request = TTSRequest(
        text=text,
        voice=voice,
        output_file=str(output) if output else None,
        rate=rate,
    )

    response = _run_async(engine.synthesize(request))

    if response.success:
        engine_tag = f"\\[{response.engine_used}]"
        if response.output_file:
            console.print(
                f"[green][OK] {engine_tag} Audio gespeichert: {response.output_file}[/] "
                f"({response.duration_ms}ms)"
            )
        else:
            console.print(
                f"[green][OK] {engine_tag} Vorgelesen[/] ({response.duration_ms}ms)"
            )
    else:
        console.print(f"[red][!!] Fehler: {response.error_message}[/]")
        raise typer.Exit(1)


@app.command("list-voices")
def list_voices(
    language: Optional[str] = typer.Option(
        None, "--language", "-l",
        help="Nach Sprache filtern (z.B. de-DE, en-US)",
    ),
) -> None:
    """Liste alle verfügbaren Stimmen auf."""
    voices = _run_async(engine.list_voices())

    if language:
        voices = [v for v in voices if v.language == language]

    table = Table(title=f"[*] Verfügbare Stimmen ({len(voices)})")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Sprache")
    table.add_column("Gender")

    for v in voices:
        table.add_row(v.id, v.name, v.language, v.gender)

    console.print(table)


@app.command()
def version() -> None:
    """Zeige Programmversion."""
    from mstts import __version__
    console.print(f"[*] [bold]mstts[/] v{__version__}")
    console.print("Engine: Microsoft Edge TTS (edge-tts)")
    console.print("Fallback: System-TTS (SAPI/say/espeak)")


@app.command("text2tts")
def text2tts_cmd(
    file: Path = typer.Argument(..., help="Pfad zur Textdatei"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Ausgabedatei (.tts.txt), sonst automatisch",
    ),
    play: bool = typer.Option(
        False, "--play", "-p",
        help="Nach Konvertierung direkt vorlesen",
    ),
) -> None:
    """Konvertiert Text in TTS-freundliche Version und spielt optional ab."""
    from mstts.text2tts import convert_file
    out = convert_file(file, output)
    console.print(f"[green][OK] {out}[/]")
    if play:
        console.print("[*] Starte Sprachausgabe...")
        text = out.read_text(encoding="utf-8")
        request = TTSRequest(text=text, voice="de-DE-ConradNeural")
        response = _run_async(engine.synthesize(request))
        if not response.success:
            console.print(f"[red][!!] {response.error_message}[/]")


def main() -> None:
    """Entry point."""
    app()
