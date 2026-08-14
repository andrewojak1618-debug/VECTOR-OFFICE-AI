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
| `eb055d9` | Clean Core | Strukturbereinigung und Embedding-Grundlage |
| `1254524` | Local Embedding Model | Reales `embeddinggemma` und Batch-Verarbeitung |

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

## Lokales Embedding-Modell

- `embeddinggemma` als kleines, mehrsprachiges On-Device-Modell ausgewählt
- Modellverfügbarkeit über Ollamas `/api/show` geprüft
- fehlendes Modell mit konkretem `ollama pull`-Hinweis behandelt
- Einzeltexte und mehrere Abschnitte über `/api/embed` verarbeitet
- Batch-Antworten auf Anzahl, Zahlenwerte und konsistente Dimension geprüft
- native Dimension 768 automatisch aus Metadaten und Ergebnis validiert
- realen lokalen Batch-Aufruf mit drei Vektoren erfolgreich ausgeführt
- keine Texte oder Vektorwerte im Diagnosepfad protokolliert

## Persistente Dokument-Embeddings

- bestehendes SQLite-Schema zerstörungsfrei um `knowledge_embeddings` erweitert
- eindeutige Fremdschlüsselbeziehung zu `knowledge_chunks` angelegt
- Vektoren kompakt als Little-Endian-Float32-BLOB serialisiert
- Modellname, vollständigen Digest, Dimension und Inhaltshash gespeichert
- wiederholte identische Embeddings über einen Unique-Index verhindert
- veraltete Modellversionen und Inhaltsstände erkennbar gemacht
- Dokument- und Chunk-Löschung bis zu Embeddings durchgereicht
- echten temporären Dokument-zu-Ollama-zu-SQLite-Pfad erfolgreich geprüft

## Automatische Indexierung und Reindexierung

- `/learn` mit der lokalen Ollama-Embedding-Pipeline verbunden
- unveränderte Dokumente per SHA-256 ohne neue Berechnung übersprungen
- identische Chunk-IDs und vorhandene Vektoren bei Teiländerungen bewahrt
- nur neue oder geänderte Abschnitte erneut indexiert
- entfernte Abschnitte samt Embeddings per Cascade-Löschung bereinigt
- Modellname und Digest zur automatischen Modellwechsel-Erkennung verwendet
- manuellen Vollneuaufbau über `/reindex ID` ergänzt
- Batch-Fortschritt ohne Ausgabe sensibler Inhalte sichtbar gemacht
- Persistenz bis zum Erfolg aller Provider-Batches zurückgestellt
- Import-, Delta-, Modellwechsel-, Rollback- und Fortschrittsfälle getestet

## Hybride Dokument- und Memory-Suche

- bestehende lexikalische Suche für Dokumente und Erinnerungen bewahrt
- Suchanfragen ausschließlich lokal mit `embeddinggemma` vektorisiert
- Kosinus-Ähnlichkeit für alle aktuellen Dokumentabschnitte berechnet
- lexikalische Rangfolge und semantische Ähnlichkeit gewichtet kombiniert
- konfigurierbaren Mindestwert für semantische Treffer eingeführt
- doppelte Chunk-Treffer über stabile IDs zusammengeführt
- Ergebnislimit des Agent-Kontexts durchgehend beachtet
- Quellen und Abschnittsnummern unverändert erhalten
- kombinierte Bewertung mit stabilen Tie-Breakern sortiert
- alte Modellversionen von der aktuellen Suche ausgeschlossen
- automatischen lexikalischen Fallback bei Ollama-Fehlern abgesichert
- reale lokale Hybridsuche mit temporären Daten vorbereitet

## Datenschutz und Kontextschutz

- Ollama als einzigen zulässigen Embedding-Anbieter und sicheren Default fixiert
- `KNOWLEDGE_ALLOW_CLOUD=false` als expliziten sicheren Default hinterlegt
- OpenAI-Dokumentkontext ohne bewusste Cloud-Freigabe getestet gesperrt
- lokale Dokumentnutzung für Ollama und privaten Voice-Modus getestet
- Dokumentabschnitte als JSON-kodierte unvertrauenswürdige Daten gekapselt
- eingebettete Befehle und Rollenwechsel im Systemtext ausdrücklich untersagt
- Mehrquellenkontext als möglichen Quellenkonflikt sichtbar markiert
- Suchpfad auf Freiheit von Dokument-, Anfrage- und Vektorlogs getestet
- `.env` und `data/` über automatisierte Gitignore-Leitplanke geschützt

## Semantische Suche mit Paraphrasen

- eindeutiges Testwissen mit Ziel-, ähnlichem und fachfremdem Abschnitt erstellt
- direkte Frage mit identischen Fachbegriffen erfolgreich gefunden
- lexikalisch überschneidungsfreie Paraphrase semantisch erfolgreich gefunden
- Paraphrase trotz irrelevanter Wetter- und Kaffeeangaben stabil gerankt
- ähnliche Dokumentabschnitte nach semantischer Nähe verglichen
- lexikalische und semantische Gewichtung gegeneinander getestet
- Mindestwert `0,50` als zu streng für den verrauschten Fall erkannt
- produktiven Mindestwert `0,35` mit drei relevanten Fällen bestätigt
- fachfremde Kontrollfrage mit 0 Falschtreffern abgeschlossen
- leere Bibliothek und nicht erreichbares Ollama automatisiert abgesichert

## Vollständiger Wissenspfad mit Ollama und Vector

- ungefährliches Projektdokument in eine temporäre Bibliothek importiert
- drei Abschnitte lokal mit `embeddinggemma` indexiert
- frei formulierte Frage semantisch auf Abschnitt 2 gerankt
- Quelle, kombinierten Wert `0,683` und Ähnlichkeit `0,423` ausgegeben
- Antwort ausschließlich mit lokalem `llama3.2:3b` erzeugt
- erwarteten Wissenswert `0,35` automatisch bestätigt
- Antwort erfolgreich auf zwei kurze Sätze begrenzt
- deutsche TTS mit Microsoft Stefan und Lautstärke 90 erzeugt
- Vector-SDK bei `4,04 V` verbunden und Audiostream vollständig abgespielt
- wiederholbaren Befehl und verbleibende subjektive Hörprüfung dokumentiert
