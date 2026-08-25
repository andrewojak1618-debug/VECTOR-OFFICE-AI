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

OpenAI und Ollama verwenden dieselben konfigurierten Grenzen für Anfragezeit
und maximale Versuche. OpenAI erhält diese Werte direkt beim SDK-Aufbau;
Ollama wiederholt nur vorübergehende Transport-, Drosselungs- und Serverfehler.
Dauerhafte Clientfehler werden nicht erneut gesendet. Erst nach ausgeschöpften
Primärversuchen greift der bestehende lokale Provider-Fallback.

`main.py` ist ausschließlich der schlanke Einstiegspunkt. Der optionale lokale
Windows-Start wird in `application/host_watchdog.py` überwacht und bleibt von
der eigentlichen Laufzeitkomposition getrennt. Der passive WirePod-SDK-Test
liegt in `application/wirepod_preflight.py`; die zugehörige begrenzte
Prozesssteuerung liegt in `application/wirepod_host_service.py`. Der bisherige
Import von `WirePodHostService` über den Host-Watchdog bleibt kompatibel. Die Zusammensetzung
der Abhängigkeiten liegt in `application/runtime.py`; Konsolen- und
WirePod-Dialoge liegen in `application/conversation.py` und die expliziten
Verwaltungsbefehle in `application/commands.py`. Die Vorbereitung und Ausgabe
von Modellantworten liegt getrennt in `application/response_delivery.py`.
`application/runtime_resources.py` kapselt die lokale Storage-, Bibliotheks-
und Tool-Komposition, damit der Einstiegspunkt klein und überprüfbar bleibt.
`application/runtime_startup.py` bündelt ausschließlich die unveränderten
Startprüfungen für Ollama, WirePod und Vector; `application/runtime.py` behält
die bisherigen privaten Importpfade als kompatible Aliase bei.

`config/environment.py` validiert ausschließlich skalare Umgebungswerte;
`config/settings.py` setzt daraus die Anwendungskonfiguration zusammen und
behält die bisherigen öffentlichen Importpfade bei. `brain/providers.py`
enthält die OpenAI-/Ollama-Adapter und ihre Fabrik. Der Zustandsübergang zum
lokalen Ersatzmodell ist in `brain/fallback_provider.py` gekapselt, während
`brain/provider_diagnostics.py` nur inhaltsfreie Provider-Metadaten ausgibt.
Die neutralen Agent-Verträge für Sprachmodell, Memory und Wissensbibliothek
liegen in `brain/contracts.py`. `brain/agent.py` importiert und re-exportiert
diese Namen weiterhin, damit bestehende Provider- und Testimporte stabil
bleiben.

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

Die providerneutralen Embedding-Verträge liegen in `memory/embedding_types.py`;
`memory/embedding_records.py` kapselt gespeicherte Records und den Float32-Codec.
`memory/knowledge_records.py` übernimmt ausschließlich SQLite-Zeilenabbildung
und lexikalisches Ranking. Die bisherigen öffentlichen Importpfade über
`memory/embeddings.py` und `memory/embedding_store.py` bleiben kompatibel.

## Robot-Aktionsgrenze

`vector/actions.py` bildet eine feste Aktions-Allowlist auf begrenzte
SDK-Operationen ab. `vector/behavior_control.py` serialisiert Sprache und
Bewegungen, verwaltet aktive abbrechbare Futures und verriegelt den
Notfallstopp. Die SDK-Grenze nutzt normale `DEFAULT_PRIORITY`, feste Timeouts
und für Animationen immer eine deaktivierte Körper-/Radspur.

`tools/vector_actions.py` registriert Aktion und Notfallstopp als mutierende
Tools. Freie SDK-Methoden und Fahrbefehle sind nicht erreichbar. Die Runtime
stellt diese Werkzeuge zusammen mit dem rein lokalen Read-only-Datums- und
Uhrzeittool aus `tools/office.py` bereit. `tools/project_status.py` liest nur
begrenzte Metadaten des festen Projektordners und den letzten lokalen
Kernabnahmestatus. `tools/project_checks.py` darf nach expliziter Bestätigung
ausschließlich die fest eingebaute lokale Python-Test-Suite starten und gibt
nur eine begrenzte Zusammenfassung zurück. `tools/service_status.py` prüft
argumentlos und rein lesend ausschließlich die fest konfigurierten lokalen
WirePod- und Ollama-Endpunkte. `tools/library_status.py` fasst die bereits
vorhandenen lokalen Dokument- und Vektorstatus ausschließlich zu Zählern
zusammen. `tools/memory_status.py` erhält von der gemeinsam verwendeten
Memory-Instanz ausschließlich bestätigte Erinnerungs- und Feedbackzähler.
`tools/roadmap_status.py` liest argumentlos nur den ersten offenen Eintrag aus
dem festen Abschnitt `Tools und Sicherheit` der lokalen Projekt-Roadmap und
verwirft unzulässige oder übergroße Ausgaben.
`tools/documentation_status.py` prüft sechs fest vorgegebene öffentliche
Kerndokumente und gibt ausschließlich bereinigte Vollständigkeitszähler zurück.
`tools/code_quality_status.py` parst nur die festen Python-Produktivpfade und
gibt ausschließlich begrenzte Zähler für die dokumentierten Qualitätsregeln
zurück; Pfade, Namen und Quelltext bleiben innerhalb der lokalen Prüfgrenze.
`tools/changelog_status.py` liest nur den ersten validierten Eintrag im festen
`[Unreleased]`-Abschnitt der lokalen `CHANGELOG.md` und verwirft weitere Inhalte.
`tools/research_source.py` darf nach separater Einmalbestätigung nur die feste
offizielle Python.org-Quelle ohne Weiterleitung und ohne Inhaltsabruf prüfen.
`tools/python_release.py` liest von derselben festen Quelle höchstens eine
begrenzte HTML-Menge und gibt nur eine streng validierte stabile Versionsnummer
weiter. `tools/selection_matching.py` hält die parameterlose kanonische
Spracherkennung getrennt von der Registry-Auswahl in `tools/selection.py`.
`tools/proposals.py` kann eine abstrakte Modellvorschlags-ID
lokal auf einen festen Registry-Aufruf abbilden, führt ihn aber nicht aus und
erzeugt keine Autorisierung. Nur der ausdrücklich aktivierte Kontextdialog darf
einen begrenzten Ausdrucksvorschlag nach einem separaten `Ja` autorisieren.

`tools/audit_store.py` ist der optionale lokale Sink für bereits redigierte
Registry-Ereignisse. Er erweitert dieselbe ignorierte SQLite-Datei additiv,
wendet Alters- und Mengenlimits an und speichert keine Tool-Ausgaben oder
Gesprächsinhalte. Auditfehler können die Registry-Ausführung nicht abbrechen.

`tools/tool_values.py` kapselt die flachen Datentypen sowie Namens-, Parameter-
und Ergebnisvalidierung der Registry. `tools/registry.py` bleibt dadurch auf
Registrierung, Berechtigung, Ausführung und bereinigtes Audit fokussiert.
