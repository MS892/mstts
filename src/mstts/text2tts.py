"""
TTS-Text-Converter: Bereinigt Texte für Sprachausgabe.
Entfernt/ersetzt: Trennlinien, Tabellen, Markdown-Formatierung, Sonderzeichen.
"""

import re
from pathlib import Path
from typing import Optional


# ── Regelwerk ─────────────────────────────────────────────────────────────

_REPLACEMENTS: list[tuple[str, str, str]] = [
    # (regex, replacement, description)
    
    # ASCII-Trennlinien
    (r'={3,}', '', 'Trennlinie (====) entfernt'),
    (r'-{3,}', '', 'Trennlinie (----) entfernt'),
    (r'#{3,}', '', 'Trennlinie (####) entfernt'),
    (r'\*{3,}', '', 'Trennlinie (****) entfernt'),
    (r'_{3,}', '', 'Trennlinie (____) entfernt'),
    (r'~{3,}', '', 'Trennlinie (~~~~) entfernt'),
    
    # Tabellen (Markdown-style)
    (r'\|[-| :]+\|', '', 'Tabellen-Trennzeile entfernt'),
    (r'^\|(.+)\|$', r'Tabelle: \1', 'Tabellenzeile umformatiert'),
    
    # Box-Drawing / Rahmen
    (r'[\u2500-\u257F]+', '', 'Box-Drawing-Zeichen entfernt'),
    
    # Code-Blöcke
    (r'```[\s\S]*?```', ' Programmcode wurde ausgelassen. ', 'Codeblock ersetzt'),
    (r'`([^`]+)`', r'\1', 'Inline-Code-Backticks entfernt'),
    
    # HTML-Tags
    (r'<[^>]+>', '', 'HTML-Tag entfernt'),
    
    # URLs behalten aber klammern
    (r'(https?://[^\s<>"]+)', r'(Link: \1)', 'URL markiert'),
    
    # Mehrfache Leerzeilen auf max. 1 reduzieren
    (r'\n{3,}', '\n\n', 'Mehrfache Leerzeilen reduziert'),
    
    # Leading/Trailing Whitespace pro Zeile
    (r'^[ \t]+', '', 'Führende Leerzeichen entfernt'),
    (r'[ \t]+$', '', 'Nachfolgende Leerzeichen entfernt'),
    
    # Bullet-List-Symbole normalisieren
    (r'^[•·▪▸►▻○●◉◦✓✔☑☒✗✘⦿⦾][ \t]*', 'Punkt: ', 'Bullet ersetzt'),
    (r'^[-*+][ \t]+', 'Punkt: ', 'Listenstrich ersetzt'),
    
    # Emojis → Text (häufigste)
    ('✅', 'Erledigt: ', '✅ → Text'),
    ('❌', 'Fehler: ', '❌ → Text'),
    ('⚠️', 'Warnung: ', '⚠️ → Text'),
    ('🔥', 'Hervorragend: ', '🔥 → Text'),
    ('⭐', 'Pluspunkt: ', '⭐ → Text'),
    ('🔴', 'Hohe Priorität: ', '🔴 → Text'),
    ('🟡', 'Mittlere Priorität: ', '🟡 → Text'),
    ('🟢', 'Niedrige Priorität: ', '🟢 → Text'),
    ('🎙️', '', 'Mikrofon-Emoji entfernt'),
    ('📄', 'Dokument: ', '📄 → Text'),
    ('📁', 'Verzeichnis: ', '📁 → Text'),
    ('💰', '', 'Geld-Emoji entfernt'),
    ('🏛️', '', 'Gebäude-Emoji entfernt'),
    ('🇩🇪', 'Deutschland', 'DE-Flagge → Text'),
    ('🇦🇹', 'Österreich', 'AT-Flagge → Text'),
    ('🇬🇧', 'Englisch', 'GB-Flagge → Text'),
    ('★', '', 'Stern entfernt'),
    ('☆', '', 'Stern entfernt'),
    
    # Pfeile
    ('→', 'zu', '→ → Text'),
    ('←', 'von', '← → Text'),
    ('↑', 'steigend', '↑ → Text'),
    ('↓', 'fallend', '↓ → Text'),
    ('⇒', 'daher', '⇒ → Text'),
    ('⇐', 'weil', '⇐ → Text'),
    
    # Anführungszeichen normalisieren
    ('„', '"', '„ → "'),
    ('"', '"', '" → "'),
    ('"', '"', '" → "'),
    (''', "'", 'Anführungszeichen normalisiert'),
    (''', "'", 'Anführungszeichen normalisiert'),
    ('»', '"', '» → "'),
    ('«', '"', '« → "'),
    ('›', '"', '› → "'),
    ('‹', '"', '‹ → "'),
    
    # Gedankenstrich
    ('—', ', ', 'Gedankenstrich → Komma'),
    ('–', '-', 'Halbgeviertstrich → Bindestrich'),
    
    # Auslassungspunkte
    ('…', '...', '… → ...'),
    
    # Nicht-druckbare Zeichen
    (r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', 'Steuerzeichen entfernt'),
]


def convert_text(text: str) -> str:
    """Wandelt Text in TTS-freundliche Version um."""
    result = text
    
    for pattern, replacement, _desc in _REPLACEMENTS:
        try:
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE)
        except re.error:
            # Fallback: literal string replacement
            result = result.replace(pattern, replacement)
    
    # Aufräumen: leere Zeilen die nur aus Satzzeichen bestehen
    result = re.sub(r'^\s*[.,;:!?\s]+\s*$', '', result, flags=re.MULTILINE)
    
    # Doppelte Spaces
    result = re.sub(r'  +', ' ', result)
    
    # Leere Zeilen am Anfang/Ende
    result = result.strip()
    
    return result


def convert_file(input_path: str | Path, output_path: Optional[str | Path] = None) -> Path:
    """Liest Datei, konvertiert, speichert als .tts.txt."""
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.with_suffix('.tts.txt')
    else:
        output_path = Path(output_path)
    
    text = input_path.read_text(encoding='utf-8')
    converted = convert_text(text)
    output_path.write_text(converted, encoding='utf-8')
    
    original_chars = len(text)
    converted_chars = len(converted)
    reduction = 100 * (1 - converted_chars / original_chars) if original_chars else 0
    
    print(f"[OK] {input_path.name}")
    print(f"  {original_chars} -> {converted_chars} Zeichen ({reduction:.0f}% reduziert)")
    print(f"  -> {output_path}")
    
    return output_path
