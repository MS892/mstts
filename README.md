# 🎙️ mstts — Minimal Speech TTS CLI

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Text-to-Speech für die Kommandozeile — einfach, schnell, kostenlos.**

`mstts` nutzt Microsoft Edge TTS (kostenlos, kein API-Key) mit Fallback auf
Windows SAPI / macOS `say` / Linux `espeak-ng`.

---

## Quickstart

```bash
pip install -e .
mstts speak "Hallo Welt"
mstts speak "Guten Tag" --voice de-DE-KatjaNeural --rate 1.2
mstts speak-file dokument.txt -o ausgabe.mp3
mstts list-voices --language de-DE
```

## Contract-Driven Development

Alle Komponenten kommunizieren über Pydantic-Contracts:

- `TTSRequest` → Engine Input
- `TTSResponse` → Engine Output
- `TTSEngine` → Interface Protocol
- `Voice` → Stimm-Metadaten

Neue Engines: `TTSEngine` Protocol implementieren → automatisch CLI-kompatibel.

## TDD

44 Tests validieren Contracts und Engine-Verhalten:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Projekt-Struktur

```
mstts/
├── src/mstts/
│   ├── __init__.py
│   ├── contracts.py    # Pydantic Models + Protocols
│   ├── engine.py       # Edge TTS + System-Fallback
│   └── cli.py          # Typer CLI (4 Commands)
├── tests/
│   ├── test_contracts.py   # Contract-Validierung (15 Tests)
│   └── test_engine.py      # Engine Contract (9 Tests)
└── pyproject.toml
```

## Lizenz

MIT — [MS892/mstts](https://github.com/MS892/mstts)
