# Architektur

## Leitprinzipien

- Providerunabhängige Kernlogik
- lokale Verarbeitung als sichere Voreinstellung
- explizite Zustimmung für dauerhafte Erinnerungen
- nachvollziehbare Fehler statt Secret-Leaks
- kleine, testbare Komponenten
- physische Tests zusätzlich zu automatisierten Tests

## Hauptkomponenten

| Bereich | Verantwortung |
|---|---|
| `brain/` | Agent, Gesprächskontext, Provider und zukünftige Persönlichkeit |
| `config/` | Validierte Konfiguration aus `.env` |
| `memory/` | Lokales SQLite-Langzeitgedächtnis |
| `vector/` | WirePod-Healthcheck, SDK-Verbindung und deutsche TTS |
| `voice/` | WirePod-Transcript-Listener und Voice-Eingabe |
| `tools/` | Reservierter Bereich für kontrollierte Aktionen |
| `tests/` | Automatisierte Regressionstests |

## Providerfluss

OpenAI ist der bevorzugte Cloud-Provider für freigegebene Anfragen. Wenn ein
OpenAI-Aufruf fehlschlägt, kann Ollama denselben Gesprächskontext übernehmen.
Im WirePod-Voice-Modus erzwingt `VOICE_ALLOW_CLOUD=false` eine ausschließlich
lokale Verarbeitung mit Ollama.

## Datenschutzgrenzen

Folgende Inhalte bleiben lokal und werden von Git ignoriert:

- `.env` und API-Schlüssel
- Vector-Zertifikate unter `.anki_vector`
- SQLite-Datenbanken unter `data/`
- temporäre TTS-Audiodateien

Ungeprüfte Modellantworten werden nicht automatisch als Fakten oder Training
gespeichert.
