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
| `brain/` | Agent, Gesprächskontext, Provider, Zustandsmodell und Reflexion |
| `config/` | Validierte Konfiguration aus `.env` |
| `memory/` | SQLite-Memory, Dokumente, Versionen, Exporte und lokale Embeddings |
| `vector/` | WirePod-Healthcheck, SDK-Verbindung, deutsche TTS und kontrollierte Aktionen |
| `voice/` | WirePod-Transcript-Listener und Voice-Eingabe |
| `tools/` | Registry, Parameterschemata und explizite Aktionsberechtigungen |
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

## Persönlichkeitsgrenze

`brain/personality.py` definiert die gemeinsamen C1-, Ehrlichkeits- und
Tonregeln. `brain/emotions.py` berechnet ausschließlich einen kleinen,
sitzungsbezogenen Gesprächszustand; `brain/reflection.py` ergänzt bei passenden
Themen die Trennung von Fakt, Interpretation, Perspektive und Unsicherheit.
OpenAI und Ollama erhalten dieselbe zusammengesetzte Systemnachricht.

Die Antwortprüfung läuft vor Kontextspeicherung und TTS. Eindeutige
Gefühlsbehauptungen, falsche Gewissheit, belehrender Ton und überlange Antworten
erhalten genau einen Korrekturversuch. Persistentes Benutzerfeedback wird nur
nach `/feedback` als getrennte, löschbare Stilinformation berücksichtigt.

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

Die Dateiprüfung und Textsegmentierung sind in `memory/document_text.py`
gekapselt. `memory/knowledge_schema.py` und `memory/embedding_schema.py`
enthalten die additiven SQLite-Schemata. Dadurch bleiben Bibliothekslogik,
Textverarbeitung und Datenbankmigration getrennt, ohne die öffentlichen APIs
von `KnowledgeLibrary` oder `EmbeddingStore` zu verändern.

## Robot-Aktionsgrenze

`vector/actions.py` bildet eine feste Aktions-Allowlist auf begrenzte
SDK-Operationen ab. `vector/behavior_control.py` serialisiert Sprache und
Bewegungen, verwaltet aktive abbrechbare Futures und verriegelt den
Notfallstopp. Die SDK-Grenze nutzt normale `DEFAULT_PRIORITY`, feste Timeouts
und für Animationen immer eine deaktivierte Körper-/Radspur.

`tools/vector_actions.py` registriert Aktion und Notfallstopp als mutierende
Tools. Freie SDK-Methoden und Fahrbefehle sind nicht erreichbar. Die Runtime
stellt diese Werkzeuge bereit, erlaubt dem Sprachmodell aber noch keine
automatische Auswahl oder Autorisierung.
