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

## Bibliothekswartung und Versionsverwaltung

- Dokumentübersicht um Importzeit, SHA-256, Version und Modellstatus erweitert
- additive SQLite-Historie für geänderte Dokumentstände eingeführt
- bestehende Datenbanken zerstörungsfrei mit einer ersten Version ergänzt
- aktives Embedding-Modell, Dimension sowie aktuelle und alte Vektoren sichtbar
- Einzel-Reindexierung beibehalten und `/reindex-all` ergänzt
- Bibliotheksmetadaten ohne Texte, Vektoren und absolute Pfade exportierbar
- bestätigte Erinnerungen in einen getrennten JSON-Export ausgelagert
- bekannte Credential-Muster vor dem Schreiben automatisch redigiert
- Cascade-Löschung um Versionsdaten erweitert und nachträglich verifiziert
- lokale Backup- und Wiederherstellungsstrategie dokumentiert

## Tool Registry und Berechtigungssystem

- `tools/registry.py` als einzige spätere Tool-Ausführungsgrenze implementiert
- einheitliche Definitionen für Namen, Beschreibungen und Parameter ergänzt
- flache String-, Integer-, Number- und Boolean-Parameter streng validiert
- `READ_ONLY`, `MUTATING` und `DANGEROUS` als Berechtigungsstufen eingeführt
- Änderungen an eine explizite Freigabe und Gefahren an Einzelbestätigung gebunden
- unbekannte Tools und ungültige Parameter vor der Ausführung blockiert
- Erfolge und Fehler als strukturierte Agent-Ergebnisse modelliert
- interne Tool-Exceptions durch neutrale Fehlercodes ersetzt
- sensible Parameter aus optionalen Audit-Ereignissen entfernt
- Argumente unbekannter Tools vollständig aus Audit-Ereignissen ausgeschlossen
- nebenwirkungsfreies `test.echo`-Tool für Integrationstests ergänzt
- Runtime mit leerer, standardmäßig blockierender Registry verbunden
- automatische Toolauswahl durch Sprachmodelle bewusst noch nicht aktiviert

## Python-Strukturbereinigung

- Modulgrenze von strikt weniger als 400 Zeilen automatisiert abgesichert
- Dateiprüfung und Textsegmentierung aus `memory/library.py` ausgelagert
- Wissens- und Embedding-Schemata in getrennte Fachmodule verschoben
- öffentliche Bibliotheks- und Speicher-APIs unverändert beibehalten
- reservierte Architekturpfade und Sicherheitsgrenzen bewahrt

## Kontrollierte Robot-Aktionen

- `vector/actions.py` mit sechs festen sicheren Aktionsnamen implementiert
- Kopf- und Liftwerte auf geprüfte feste Positionen begrenzt
- zwei kurze Animations-Trigger mit deaktivierter Radspur freigegeben
- Fahrbewegungen vollständig außerhalb der Aktionsschnittstelle gehalten
- gemeinsame BehaviorControl für Sprache und Aktionen eingeführt
- normale SDK-Priorität unter Beibehaltung physischer Schutzreaktionen verwendet
- SDK-Aktionen durch konfigurierbare Timeouts und Future-Abbruch abgesichert
- verriegelten Notfallstopp mit `stop_all_motors` ergänzt
- Aktion und Notfallstopp als explizit mutierende Registry-Tools registriert
- alle sechs Aktionen und den Leerlauf-Notfallstopp physisch erfolgreich geprüft

## Emotionen und philosophische Reflexion

- vier transparente simulierte Gesprächshaltungen festgelegt
- Intensität, Übergangshistorie und Gründe deterministisch begrenzt
- Nutzersätze aus Zustandsmetadaten ausgeschlossen
- optionale Reflexion für klar philosophische Themen implementiert
- Fakt, Interpretation, Perspektive und Unsicherheit im Prompt getrennt
- deutsche C1-, Kürze- und Anti-Belehrungsregeln zentralisiert
- Modellantworten vor Speicherung und TTS auf harte Stilregeln geprüft
- genau einen sicheren Korrekturversuch bei Regelverstößen ergänzt
- bestätigtes Stilfeedback als eigene Memory-Kategorie eingeführt
- OpenAI- und Ollama-Nachrichten auf identische Persönlichkeitsregeln getestet
- nicht ausführbare Ausdruckshinweise für spätere Animationen vorbereitet
- drei automatisierte und drei reale lokale Beispieldialoge geprüft

## Qualitätsabnahme nach Karten 9 bis 12

- alle produktiven Python-Module erneut gegen die Unter-400-Zeilen-Regel geprüft
- zentrale Memory-, Tool-, Robot- und Persönlichkeitsmodule als dokumentierte
  Architekturpfade in der automatischen Qualitätskontrolle verankert
- reservierte Pfade und öffentliche Schnittstellen unverändert beibehalten
- vollständige Unit-Test-, Syntax-, Dokumentations- und Git-Prüfung ausgeführt
- private `.env`- und `data/`-Laufzeitdaten weiterhin aus Git ausgeschlossen

## Systemabnahme und Release-Kandidat

- zentralen Runner für Kern-, Live-Provider- und physische Prüfungen ergänzt
- Standardlauf ohne API-Kosten, Sprachausgabe oder Robot-Aktion abgesichert
- OpenAI-Erreichbarkeit als minimale, ausgabefreie Live-Diagnose vorbereitet
- physische Prüfungen an eine zweite ausdrückliche Bestätigung gebunden
- secretfreien lokalen JSON-Abnahmebericht unter `data/` ermöglicht
- SQLite-Sicherung und Wiederherstellung automatisiert praktisch geprüft
- Freigabekriterien für Versionsnummer, Changelog und Git-Tag dokumentiert
- Kernabnahme mit 227 Tests und 4/4 Prüfschritten bestanden
- lokale Ollama-Abnahme mit 7/7 Prüfschritten bestanden
- minimale OpenAI-Live-Abnahme mit 5/5 Prüfschritten bestanden
- physische Vector-Abnahme mit TTS und Begrüßung mit 6/6 bestanden
- Aussprache, Lautstärke, Wissensantwort und Bewegung subjektiv bestätigt
- Version `0.2.0-rc.1` und Changelog vorbereitet; Git-Tag noch ausstehend

## Kontrollierte Tool-Auswahl im Gespräch

- feste deutsche Intent-Regeln ohne Sprachmodellzugriff eingeführt
- Auswahl an die tatsächlich registrierten Tooldefinitionen gebunden
- rein lesende Anzeige sicherer Aktionen automatisch freigegeben
- Kopf-, Lift- und Animationsaktionen an ein separates Ja/Nein gebunden
- offene Bestätigung über Konsolen- und WirePod-Turns hinweg begrenzt gehalten
- zusätzliche oder unklare Anweisungen nicht als Toolaufruf interpretiert
- gefährliche Tools im Gesprächspfad vollständig blockiert
- Notfallstopp als sofortige Sicherheitsunterbrechung priorisiert
- Modellaufrufe für ausgewählte, bestätigte und abgebrochene Tools ausgeschlossen
- Leseabfrage, Rückfrage, separates Ja, Animation und Abschluss-TTS produktiv
  mit dem physischen Vector erfolgreich geprüft

## Strukturierte Modellvorschläge ohne Ausführungsrecht

- providerneutralen Klassifikationspfad für OpenAI und Ollama ergänzt
- Modellausgabe auf ein exaktes JSON-Schema mit abstrakter Vorschlags-ID begrenzt
- Toolnamen und Parameter ausschließlich aus einer festen lokalen Tabelle ergänzt
- Notfallstopp, gefährliche Tools und sensible Parameter aus dem Katalog entfernt
- Vorschläge erneut nebenwirkungsfrei gegen die aktuelle Registry geprüft
- zusätzliche Felder, Berechtigungen, freie Parameter, Markdown und Text verworfen
- rohe oder fehlerhafte Modellantworten nicht im Prüfergebnis aufbewahrt
- keinerlei Toolausführung, Audit-Ereignisse oder Autorisierungen erzeugt
- produktive Gesprächsaktivierung bis zu einer gesonderten Freigabe deaktiviert
- OpenAI-/Ollama-neutralen Vertrag und Prompt-Injection-Fälle automatisiert geprüft
