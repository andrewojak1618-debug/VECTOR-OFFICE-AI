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
| `application/` | Startlogik, Betriebsmodus, Befehle und Gesprächsschleifen |
| `brain/` | Agent, Gesprächskontext, Provider und zukünftige Persönlichkeit |
| `config/` | Validierte Konfiguration aus `.env` |
| `memory/` | SQLite-Langzeitgedächtnis, Dokumente und lokale Embeddings |
| `vector/` | WirePod-Healthcheck, SDK-Verbindung und deutsche TTS |
| `voice/` | WirePod-Transcript-Listener und Voice-Eingabe |
| `tools/` | Reservierter Bereich für kontrollierte Aktionen |
| `tests/` | Automatisierte Regressionstests |

`main.py` ist ausschließlich der schlanke Einstiegspunkt. Die Zusammensetzung
der Abhängigkeiten liegt in `application/runtime.py`; Konsolen- und
WirePod-Dialoge liegen in `application/conversation.py` und die expliziten
Verwaltungsbefehle in `application/commands.py`.

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

Dokumentauszüge erscheinen im Systemkontext als JSON-kodierte
`UNVERTRAUENSWÜRDIGE_DOKUMENTDATEN`. Der Systemtext verbietet die Ausführung
eingebetteter Aufforderungen. Treffer aus mehreren Dateien erhalten einen
sichtbaren Hinweis auf mögliche Quellenkonflikte. Die vollständigen Regeln und
die genaue Bedeutung einer Cloud-Freigabe stehen unter [Datenschutz](privacy.md).

## Embedding-Grenze

`memory/embeddings.py` definiert den neutralen `EmbeddingProvider`-Vertrag und
klare Datentypen für Texte und Zahlenvektoren. Der einzige konkrete Adapter
verwendet Ollama lokal; ein Cloud-Embedding-Fallback existiert bewusst nicht.
Die produktive Dokumentensuche kombiniert die bestehende lexikalische Rangfolge
mit lokal berechneter Kosinus-Ähnlichkeit. Bestätigte Erinnerungen behalten ihre
transparente lexikalische Suche; der Agent führt beide Quellen im Kontext
zusammen.

Die SQLite-Integration liegt in `memory/embedding_store.py`. Jeder Vektor
verweist auf genau einen Dokumentabschnitt. Dokument, Abschnitte und Vektoren
bilden eine durchgehende Fremdschlüsselkette mit Löschweitergabe. Der Indexer in
`memory/indexing.py` koordiniert Batch-Erzeugung und atomare Speicherung.
`memory/search.py` lädt nur aktuelle Vektoren der aktiven Modellversion, führt
lexikalische und semantische Treffer nach Chunk-ID zusammen und fällt bei einer
nicht verfügbaren lokalen Embedding-Grenze automatisch auf Lexik zurück.
