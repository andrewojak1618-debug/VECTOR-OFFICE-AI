# Entwicklungsverlauf

Die Entwicklung erfolgt in kleinen, physisch getesteten Zwischenständen. Jeder
Meilenstein bleibt über Git reproduzierbar.

| Commit | Meilenstein | Ergebnis |
|---|---|---|
| `c88c224` | Repository-Basis | Erster versionierter Stand |
| `cdaf906` | Core-Grundlage | WirePod, SDK-Verbindung und WAV-Wiedergabe |
| `b85e5ed` | German TTS | Deutsche OneCore-Stimme und FFmpeg-Pipeline |
| `15ea79a` | Conversation Core | Providerunabhängiger Agent mit OpenAI und Ollama |
| `d4a3d5e` | Conversation Loop | Mehrere Gesprächsrunden und Projekt-Roadmap |
| `7843561` | Fallback & Memory | Ollama-Fallback und gemeinsames SQLite-Memory |
| `98037bd` | Voice Pipeline | Private WirePod-Spracheingabe bis zur Vector-TTS |
| `ea63def` | Personality Paths | Emotions- und Reflexionsarchitektur reserviert |

## Erfolgreich verifizierte End-to-End-Pfade

### Cloud-Pfad

`Benutzereingabe → Agent → OpenAI → deutsche TTS → Vector`

Dieser Pfad wurde mit Texteingabe physisch getestet. Sprachtranskripte dürfen
nur mit ausdrücklicher Cloud-Freigabe an diesen Pfad übergeben werden.

### Lokaler Sprachpfad

`Hey Vector → WirePod/Vosk → Agent → Ollama → deutsche TTS → Vector`

Dieser Pfad wurde vollständig mit einem physischen Vector 2.0 getestet. Leere
`intent_system_noaudio`-Ereignisse werden ignoriert.

## Qualitätsentwicklung

Die deutsche TTS wurde schrittweise verbessert:

1. OneCore-Stimme „Microsoft Stefan“ ausgewählt.
2. Ausgabe in 16 kHz, 16 Bit, Mono-PCM umgewandelt.
3. Vector-Lautstärke und Master-Volume getestet.
4. Sprachkompression und Loudness-Normalisierung abgestimmt.
5. Antworten für gesprochene Dialoge auf kurze, natürliche Sätze begrenzt.

## Aktueller Arbeitsstand: kontrollierte Dokumentbibliothek

- bewusster Import von UTF-8-kodierten `.md`- und `.txt`-Dateien
- lokale Speicherung in derselben SQLite-Datenbank wie das Memory
- nachvollziehbare Quellen, SHA-256-Prüfsummen und Abschnittsnummern
- lexikalischer Abruf passender Dokumentabschnitte
- gemeinsamer Agent-Kontext mit klarer Kennzeichnung als Daten
- Cloud-Sperre als Standard; Ollama darf die lokale Bibliothek verwenden
- Verwaltung über `/learn`, `/documents` und `/forget-document`

## Clean-Code-Audit

- monolithische Start-, Gesprächs-, Dokument- und TTS-Logik aufgeteilt
- explizite `application/`-Schicht für Orchestrierung eingeführt
- Provider-, Ollama-, WirePod- und Vector-SDK-Grenzen gekapselt
- öffentliche Python-APIs einheitlich dokumentiert
- wiederverwendete Grenzwerte in Settings oder Konstanten verschoben
- lokale SQLite-Neben- und Journaldaten vollständig über `data/` ignoriert
- Regressionstests für TTS, Providerwahl und Listenerfehler ergänzt
- automatische Strukturregeln in `tests/test_code_quality.py` hinterlegt

## Lokale Embedding-Grundlage

- `EmbeddingText` und `EmbeddingVector` als validierte Datentypen eingeführt
- `EmbeddingProvider` als providerunabhängigen Vertrag definiert
- aktuellen lokalen Ollama-Endpunkt `/api/embed` angebunden
- Modellname und tatsächliche beziehungsweise erwartete Dimension erfasst
- Timeout, Antwortvalidierung und sichere Fehlergrenze ergänzt
- Cloud-Embedding im Factory-Pfad ausdrücklich ausgeschlossen
- produktive Suche bewusst noch nicht verändert
