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
- Registry-Wertvalidierung aus dem grenznahen Registry-Modul ausgelagert
- Embedding-Typen, Persistenzrecords und Float32-Codec fachlich getrennt
- SQLite-Zeilenabbildung und lexikalisches Ranking aus der Bibliothek gelöst
- größte betroffene Module von 397–380 auf höchstens 351 Zeilen reduziert

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
- Version `0.2.0-rc.1` und Changelog vorbereitet
- annotierten Tag `v0.2.0-rc.1` historisch auf den geprüften Release-Commit gesetzt

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

## Lokale Tool-Audit-Persistenz

- bereits redigierte Registry-Ereignisse additiv in SQLite gespeichert
- Toolname, Berechtigungsstufe, Status, Fehlercode und sichere Argumente erfasst
- Nutzersätze, Modellantworten, Tool-Ausgaben und Dokumentwissen ausgeschlossen
- unbekannte Toolargumente und sensible Parameter auch persistent ferngehalten
- standardmäßige Aufbewahrung auf 30 Tage und 1.000 Ereignisse begrenzt
- automatische Alters- und Mengenbereinigung nach jedem Eintrag ergänzt
- Audit-Persistenz über lokale Settings vollständig deaktivierbar gemacht
- Initialisierungs- und Schreibfehler ohne Einfluss auf die Toolausführung gehalten
- Anzeige, manuelle Bereinigung und bestätigtes Löschen lokal diagnostizierbar gemacht
- bestehende Memory-Daten bei Migration und Audit-Löschung unverändert verifiziert

## Kontrollierte Ausdruckszuordnung

- `brain/expression_actions.py` als providerunabhängige Abbildungsschicht ergänzt
- neutrale Cues und Zustände mit Intensität 0 vollständig aktionslos gehalten
- attentive und supportive Cues auf die dezente `eyes_only`-Animation begrenzt
- reflective Cues auf ein festes, registrygeprüftes Ausdrucksprofil begrenzt
- Begrüßung, Kopf, Lift, Fahrbewegung und Notfallstopp nicht automatisch abgeleitet
- Vorschlag erneut gegen feste Option, Registry, Berechtigung und Parameter geprüft
- Nutzersätze und Zustandsgründe aus dem Vorschlagsobjekt ausgeschlossen
- Toolausführung, Autorisierung und Audit-Ereignis in dieser Schicht verhindert
- automatische Aktivierung und konkrete Roboterausführung strikt getrennt gehalten

## Sequenzielle Ausdrucks- und Sprachausgabe

- `application/expression_delivery.py` als eigene Orchestrierungsschicht ergänzt
- ausschließlich cuegebundene feste Ausdrucksprofile in diesem Pfad akzeptiert
- Mutationsfreigabe und Einzelbestätigung für jeden konkreten Ablauf verlangt
- bestätigte Animation vollständig vor Beginn der deutschen TTS abgeschlossen
- parallele Sprache und Robot-Aktion durch synchrone Reihenfolge ausgeschlossen
- Antwort bei fehlender Bestätigung oder Animationsfehler weiterhin gesprochen
- fremde, manipulierte oder nicht verfügbare Vorschläge ohne Bewegung verworfen
- gesprochenen Antworttext aus dem strukturierten Ergebnis ausgeschlossen
- automatische Aktivierung in der produktiven Gesprächsschleife ausgeschlossen

## Expliziter Ausdrucksdialog

- `application/expression_conversation.py` produktiv in Konsole und WirePod angebunden
- nur die eindeutige Einleitung `Mit Ausdruck ...` als Ausdruckswunsch akzeptiert
- Antwort vor der Aktion vorbereitet und höchstens einen Vorschlag offen gehalten
- Animation erst nach einem separaten exakten Ja einmalig autorisiert
- Nein als Sprachausgabe ohne Animation und Abbrechen als vollständiges Verwerfen behandelt
- Notfallstopp und behandelte Konsolenbefehle gegenüber offenen Vorschlägen priorisiert
- Sitzungskontext bei vollständig verworfenen vorbereiteten Antworten zurückgesetzt
- normale Gespräche und neutrale Zustände weiterhin ohne Ausdrucksbewegung ausgeliefert
- OpenAI und Ollama denselben lokalen, providerunabhängigen Kontrollpfad gegeben

## Reflektiertes Bewegungs- und Sprechprofil

- `reflective_expression` als feste 18-Grad-Kopf-, Augen- und Rückkehrsequenz ergänzt
- Räder und Lift aus diesem Ausdrucksprofil weiterhin vollständig ausgeschlossen
- reflektierte Antwortausgabe mit begrenztem OneCore-SSML-Profil erweitert
- Tempo leicht reduziert, Tonlage minimal gesenkt und natürliche Satzpausen ergänzt
- neutrale TTS-Ausgabe und bestehende Lautheitskompression unverändert gelassen
- Promptregeln gegen Manuskriptton, Nominalketten und abstrakte Aufzählungen verschärft
- abgelehnte Bewegung bei ausdrücklichem Reflexionswunsch weiterhin ruhig gesprochen
- `vektor beenden` als Erkennungsvariante und sauberes `Ctrl+C` ergänzt
- reale lokale SSML-WAV-Erzeugung sowie automatisierte Sicherheitsabläufe geprüft
- ersten Hardwarelauf wegen zu kurz aufgeteiltem Animationstimeout sicher gestoppt
- jeden Sequenzschritt anschließend auf den bestehenden Einzelaktionstimeout korrigiert
- korrigierte Kopf-Augen-Kopf-Sequenz am physischen Vector vollständig abgeschlossen
- reflektierte TTS anschließend konfliktfrei und verständlich wiedergegeben
- Bewegungs- und Sprachwirkung vom Benutzer als besser als die Vorstufe bewertet
- Profil als verbesserte Zwischenstufe statt als endgültige Ausdrucksqualität eingeordnet

## Natürlichere Satzmelodie

- neutrale Antworten auf acht Prozent und reflektierte Antworten auf fünf
  Prozent Beschleunigung eingestellt
- globale Absenkung der Tonhöhe entfernt und native Intonation erhalten
- die ersten beiden Wörter ohne Tempoänderung präsenter gestaltet
- die letzten drei Wörter mit leiserer und fallender Kontur ausklingen lassen
- Anfangspause auf 180 und Satzpause auf 190 Millisekunden verkürzt
- Lexikon- und Manuskripteinstiege in allen providerneutralen Regeln ausgeschlossen
- reflektierte Sätze möglichst auf weniger als 18 Wörter ausgerichtet
- reale lokale SSML-WAV-Erzeugung mit dem neuen Profil erfolgreich geprüft
- deterministische Ollama-Beispiele mit kürzeren gesprochenen Gedanken bestanden
- Lautheitskompression und Bewegungssicherheit unverändert gelassen
- feste deutsche Hörprobe am physischen Vector erfolgreich abgenommen

## Variable Reflexionseinleitung

- IPA-Summton, `Ich schätze` und `Lass mich überlegen` als feste Varianten hinterlegt
- bei jeder reflektierten Ausgabe unabhängig genau eine Variante zufällig gewählt
- alle drei Varianten gleich wahrscheinlich und direkte Wiederholungen zugelassen
- Auswahl vollständig aus Modellprompt, Antwortspeicher und Memory herausgehalten
- neutrale Antworten und Bestätigungsfragen weiterhin ohne Einleitung gesprochen
- alle aktiven Varianten durch deterministische SSML-Tests einzeln abgedeckt
- `Hmmm` und `Mmmm` nach unnatürlicher physischer Aussprache wieder entfernt
- echten gedehnten IPA-Summton als deutlich natürlichere Alternative physisch verglichen
- IPA-Summton nach Benutzerauswahl mit 1.500 Millisekunden Pause übernommen
- Summtonvarianten lokal vermessen und direkt am physischen Vector verglichen
- Summton mit minus 32 Prozent von rund 1,01 auf 1,54 Sekunden verlängert
- längere Variante nach positiver Hörabnahme produktiv übernommen
- Pause nach `Lass mich überlegen` nach Nutzerfeedback auf 2.000 Millisekunden gesetzt
- Pause nach `Ich schätze` unverändert bei 320 Millisekunden gelassen

## WirePod-Duplikatschutz

- identische Rohlogzeilen weiterhin nur einmal verarbeitet
- gleiche normalisierte Transkripte mit neuem Zeitstempel zusätzlich erkannt
- Duplikate desselben Geräts innerhalb von drei Sekunden unterdrückt
- bewusste Wiederholungen nach Ablauf des Fensters wieder zugelassen
- identische Texte verschiedener Geräte unabhängig behandelt
- Exit-, Notfall- und Bestätigungssignale beim ersten Auftreten sofort durchgereicht
- nur SHA-256-Fingerabdrücke in begrenzten sitzungslokalen Wiedererkennungslisten gehalten
- beschädigte WirePod-Zeitstempel ohne Abbruch der Voice-Schleife ignoriert

## Voice-Fehler und Abbruchsignale

- eindeutige Voice-Endsignale gegen Großschreibung, Leerraum und Satzzeichen normalisiert
- bewusste Varianten für Vector, Vektor, Gespräch und Dialog zugelassen
- ein einzelnes `Abbrechen` weiterhin nur für offene Bestätigungen verwendet
- Initialisierung und laufenden WirePod-Abruf auf fünf Fehlversuche begrenzt
- Wartezeiten dafür auf 1, 2, 5 und 10 Sekunden festgelegt
- kurze Pause zwischen lokalen Wiederholungsversuchen eingeführt
- interne Fehlerdetails aus der normalen Dialogausgabe ferngehalten
- `Ctrl+C` in der gesamten Voice-Verarbeitung ohne Traceback behandelt
- offene Ausdrucksantworten bei jedem Sitzungsende kontrolliert zurückgerollt

## Physischer Mehrturntest

- freie deutsche Frage lokal erkannt, mit Ollama beantwortet und vollständig gesprochen
- kontrollierte Kopfbewegung erst nach separatem `Ja bitte` einmalig ausgeführt
- Hörtimeout ohne Sitzungsabbruch erfolgreich durchlaufen
- offene Kopfaktion mit `Abbrechen` ohne Bewegung verworfen
- reale Vosk-Varianten `hebe deine Lift`, `Abbruch` und `bitte beenden` abgesichert
- parallele englisch klingende WirePod-OpenAI-Stimme als separate Ausgabequelle identifiziert
- irreführende globale Cloud-Ausgabe auf anwendungsspezifische Aussage korrigiert
- WirePod-Optionen `Enable intent-graph` und die Konversation über
  `I have a question` gezielt deaktiviert
- Transkriptpfad anschließend ohne englische Zweitstimme physisch bestätigt

## Einheitliche Provider-Resilienz

- gemeinsames konfigurierbares Anfragezeitlimit für OpenAI und Ollama ergänzt
- maximale Modellversuche auf einen Wert zwischen eins und fünf begrenzt
- OpenAI-SDK-Retries ausdrücklich statt über versteckte Standardwerte gesetzt
- Ollama-Wiederholung auf Transportfehler, 408, 409, 429 und Serverfehler begrenzt
- dauerhafte Clientfehler ohne unnötigen zweiten Aufruf beendet
- Fehlermeldungen weiterhin ohne Transportdetails oder sensible Inhalte gehalten
- bestehenden Wechsel von OpenAI zum lokalen Ollama-Fallback unverändert bewahrt

## Strukturierte Laufzeitdiagnose

- lokales JSONL-Ereignisschema mit Version, UTC-Zeit, Stufe und Ereigniscode ergänzt
- zulässige Detailfelder auf harmlose technische Metadaten begrenzt
- Transkript-, Prompt-, Antwort-, Dokument-, Secret- und Vektorfelder blockiert
- Anwendungsstart, lokale Dienste, SDK-Zugriff und Betriebsmodus angebunden
- Ollama-Wiederholungen und Provider-Fallback ohne Anfrageinhalte sichtbar gemacht
- Dateigröße begrenzt und genau eine lokale Vorgängerversion vorgesehen
- Diagnosefehler vom eigentlichen Roboterbetrieb entkoppelt

## Mehrturnige Providerwechsel

- deterministische Sitzung mit der Folge OpenAI, Ollama-Fallback und OpenAI geprüft
- Primäranbieter in jeder neuen Runde erneut bevorzugt statt dauerhaft umgeschaltet
- validierte Fallback-Antwort in den gemeinsamen Gesprächskontext übernommen
- vollständigen Verlauf beim wieder verfügbaren Primäranbieter nachgewiesen
- Totalausfall beider Anbieter ohne verwaiste Benutzerfrage zurückgerollt
- Fallback-Ereignis ohne Gesprächsinhalte in der lokalen Diagnose bestätigt

## ConnectionSupervisor

- zentrale Zustände für lokale und externe Dienste vorbereitet
- Wiederholungsstaffel auf 1, 2, 5, 10 und höchstens 30 Sekunden begrenzt
- WirePod- und Vector-SDK-Startprüfung mit drei Versuchen angebunden
- Ollama-Endzustand in dieselbe Verbindungsaufsicht aufgenommen
- Fehlerzähler nach erfolgreicher Wiederverbindung zurückgesetzt
- nur Zustandswechsel ohne Adressen oder Gesprächsinhalte protokolliert
- Firmware-Autonomie als separaten OSKR-Forschungspfad dokumentiert

## Lokale Offline-Ansage

- ersten Cloud-Ausfall als einmaligen konsumierbaren Providerzustand modelliert
- lokale Meldung vor der erfolgreichen Ollama-Fallback-Antwort gesprochen
- Wiederholung während desselben Ausfalls unterdrückt
- neuen Hinweis nach zwischenzeitlicher Cloud-Erholung wieder zugelassen
- bei Totalausfall keine unzutreffende Behauptung lokalen Weiterbetriebs verwendet
- Ansage vollständig über den bestehenden lokalen deutschen TTS-Pfad ausgegeben
- beide Offline-Varianten am physischen Vector erfolgreich hörgeprüft und bestätigt

## Lokale Wiederherstellungsansage

- laufende WirePod-Sprachabfragen an den gemeinsamen ConnectionSupervisor angebunden
- vorübergehende Fehler mit der gemeinsamen 1-, 2-, 5- und 10-Sekunden-Staffel wiederholt
- erfolgreiche Wiederverbindung als einmalig konsumierbaren Übergang modelliert
- lokale deutsche Ansage erst nach wiederhergestelltem Audioweg ausgegeben
- Wiederholungen innerhalb desselben Ausfalls zuverlässig unterdrückt
- initial verfügbare Verbindung ausdrücklich nicht als Wiederherstellung behandelt
- Runtime-Weitergabe desselben Supervisors durch einen Regressionstest abgesichert
- produktiven Recovery-Übergang bis zur physischen Vector-TTS erfolgreich ausgeführt
- vollständige Verständlichkeit der deutschen Ansage vom Benutzer bestätigt

## Windows-Autostart und Host-Watchdog

- testbaren Host-Watchdog als getrennte Anwendungsschicht ergänzt
- lokale Einzelinstanz über geplante Aufgabe und Dateisperre abgesichert
- fehlenden WirePod-Prozess ohne Doppelstart kontrolliert wiederanlaufen lassen
- bestehende Ollama-Startlogik statt einer zweiten Implementierung weiterverwendet
- Anwendung nur nach Fehlercodes mit 2-, 5- und 10-Sekunden-Staffel neu gestartet
- bewusstes Sitzungsende ohne unerwünschten Wiederanlauf erhalten
- Voice-Wiederanlauffenster auf fünf begrenzte Versuche erweitert
- Installation und Rückbau als secretfreie PowerShell-Skripte bereitgestellt
- Aufgabenaufbau mit `-WhatIf` ohne Systemänderung erfolgreich geprüft
- Besitzer-PID und gezielte Prozessbaumbereinigung für Aufgabenstopps ergänzt
- betriebssystemspezifische Prozesskontrolle aus dem Watchdog-Fachmodul getrennt
- geplante Aufgabe lokal mit 20 Sekunden Anmeldeverzögerung installiert
- realen Start bis WirePod, Ollama, Vector-SDK und Voice-Modus bestätigt
- manuellen Aufgabenstopp ohne verwaiste Projektprozesse erfolgreich abgenommen
- Voice-Recovery beim Cleanup aus der allgemeinen Gesprächsschleife ausgelagert

## VECTOR-PY-CLEANUP nach Karte 18

- allgemeine Gesprächsschleife von 369 auf 323 Zeilen reduziert
- Voice-Recovery als eigenes dokumentiertes Fachmodul erhalten
- native Windows-Prozessgrenze mit expliziten 64-Bit-Signaturen gehärtet
- unbenutzten Testimport und veraltete Drei-Versuche-Angaben entfernt
- sämtliche produktiven Python-Module weiterhin unter 400 Zeilen gehalten
- sämtliche Funktionen weiterhin auf höchstens 35 physische Zeilen begrenzt
- 366 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- `.env`, Laufzeitdaten und Secrets weiterhin aus dem Git-Stand ausgeschlossen

## Karte 19 – Windows-Kaltstart und Bereitschaftsstatus

- rein lesenden, wiederholbaren Autostart-Prüfbefehl ergänzt
- Aufgabenregistrierung, Startaktion, Zustand und letztes Ergebnis einbezogen
- lokale WirePod- und Ollama-Endpunkte ohne Cloudzugriff geprüft
- doppelte Watchdog-, Anwendungs- und WirePod-Prozesse erkennbar gemacht
- Vorabmodus für eine bewusst beendete Aufgabe von der Kaltstart-Abnahme getrennt
- Ausgabe auf technische Zustände ohne Secrets oder Gesprächsinhalte begrenzt
- ersten echten Kaltstart als fehlgeschlagenen 18-Sekunden-Grenzfall erkannt
- begrenztes WirePod-Startfenster mit sechstem Versuch auf rund 48 Sekunden erweitert
- langsamen erfolgreichen sechsten WirePod-Start automatisiert abgesichert
- wiederholten Kaltstartabbruch auf eine CP-1252/OEM-Decodierung von `tasklist` zurückgeführt
- Prozessnamensprüfung auf codierungsunabhängige ASCII-Bytes umgestellt
- unerwartete Watchdog-Grenzfehler inhaltsfrei diagnostiziert und kontrolliert beendet
- beide wiederholten Lernfragen als korrekt erkannte WirePod-Ereignisse nachgewiesen
- verzögerte erste Antwort auf den kalten lokalen Ollama-Modellstart eingegrenzt
- lokales Chatmodell vor Voice-Bereitschaft mit leerer inhaltsfreier Anfrage vorgewärmt
- dauerhafte PowerShell-Aufgabenhülle mit verborgenem Fenstermodus konfiguriert
- geplante Aufgabe zusätzlich als verborgen markiert
- sichtbares Fenster dem von Windows 11 vorgeschalteten Windows Terminal zugeordnet
- feste argumentlose WScript-Hülle für einen tatsächlich windowlosen Start ergänzt
- WScript-Aufgabenprozess als tatsächlichen Watchdog-Besitzer angebunden
- windowlosen Aufgabenstart mit null sichtbaren Terminalfenstern praktisch abgenommen
- vollständige Startdiagnose für Aufgabe, Dienste und Einzelinstanzen bestanden
- echte lokale Agentenantwort vor der Optimierung mit 18,02 Sekunden gemessen
- Embedding-Aufruf bei einer leeren Dokumentbibliothek vollständig vermieden
- lokale Ausgabe auf 96 Tokens, 4096 Kontexttokens und Temperatur 0,25 begrenzt
- Ollama-Sprachmodell für Gesprächspausen 30 Minuten im Speicher gehalten
- vier vollständige lokale Antworten nach der Optimierung in 1,91 bis 3,03 Sekunden erzeugt
- drei vorhandene lokale Überlegungseinleitungen vor jede Modellantwort verschoben
- Antwortberechnung und Einleitung kontrolliert parallelisiert
- Antwortwiedergabe weiterhin strikt nach dem vollständigen Einleitungsende gestartet
- direkte Tools, Bestätigungen und Sicherheitsaktionen von der Denkphase ausgenommen
- alle drei zufälligen Überlegungsausgaben am physischen Vector erfolgreich gehört

## Dynamische Gesprächsprosodie

- bestätigtes Gesprächsprofil als unveränderten neutralen Rückfall erhalten
- unterstützende Aussagen auf ein sanfteres Profil bei gleichem Grundtempo abgebildet
- Risiko- und Unsicherheitsfragen mit kurzen zusätzlichen Strukturpausen versehen
- reflektierende Aussagen weiterhin über das separat abgestimmte Profil ausgegeben
- Prosodieauswahl auch im normalen Voice-Dialog an den lokalen Zustand angebunden
- Antworttext, Modellwahl und Bewegungsberechtigungen von der Prosodie getrennt
- feste SSML-Werte in `vector/speech_prosody.py` gekapselt und getestet
- physische Feinabnahme der neuen unterstützenden und vorsichtigen Profile vorgemerkt
- Wortgruppenblöcke zugunsten eines durchgehenden Sprachbogens entfernt
- Antwort-WAV bereits parallel zur hörbaren Überlegungsphase vorbereitet
- konkurrierende OneCore-Synthesen durch eine lokale Sperre serialisiert
- lokalen Voice-Output auf 64 Tokens begrenzt und Promptwiederholungen reduziert
- reine Satzlängenverstöße ohne zweite Modellanfrage sicher gekürzt
- Zielzeit von fünf bis sechs Sekunden für warmes Qwen festgehalten

## Optionale ElevenLabs-TTS

- ElevenLabs als ausdrücklich freizugebenden TTS-Provider ergänzt
- Voice-ID für „Felix Serenitas – Calm and Trustworthy“ lokal konfiguriert
- Microsoft Stefan als automatischen Offline-Fallback beibehalten
- hörbare Überlegung vollständig lokal und ohne Cloudanfrage belassen
- Modellformatierung vor beiden Sprachpfaden in flüssigen Sprechtext überführt
- Cloud-Audio mit dynamikerhaltender Loudness-Normalisierung vorbereitet
- API-, Audio- und Konvertierungsfehler ohne Antwort- oder Secret-Logs abgesichert
- API-Zugriff nach Credit-Freigabe mit rund 1,03 Sekunden Erzeugungszeit bestätigt
- Felix vollständig über FFmpeg, Vector-SDK und physischen Lautsprecher abgespielt
- gewünschte Stimme, Natürlichkeit und Grundabstimmung vom Benutzer bestätigt
- verborgene Autostart-Aufgabe mit dem neuen TTS-Provider erfolgreich neu gestartet

## Natürliche Ollama-Formulierungen

- vollständige deutsche Sätze mit erkennbarem Subjekt und finitem Verb gefordert
- Telegrammstil und typische alleinstehende Prädikatsfragmente lokal abgesichert
- Korrekturversuch weiterhin inhaltsfrei über einen neutralen Fehlercode ausgelöst
- persönliche Statusfrage mit `qwen3:4b-instruct` erfolgreich real getestet
- 405 Tests, Kompilierung, strikten Dokumentationsbau und Diff-Prüfung bestanden

## VECTOR-PY-CLEANUP nach Sprachintegration

- Python-Regeln aus `docs/quality.md` und die relevante 400-Zeilen-Vorgabe abgeglichen
- validierte Umgebungswerte aus `config/settings.py` nach `config/environment.py` ausgelagert
- Provider-Fallback und inhaltsfreie Diagnostik aus der Provider-Fassade getrennt
- Antwortvorbereitung und Sprachausgabe aus der Gesprächsschleife ausgelagert
- bestehende öffentliche Importpfade als kompatible Fassaden beibehalten und getestet
- `config/settings.py` von 393 auf 335 Zeilen reduziert
- `brain/providers.py` von 388 auf 307 Zeilen reduziert
- `application/conversation.py` von 376 auf 276 Zeilen reduziert
- Wakeword-A/B-Test mit deutschem Locale, stummen Systemtönen und ruhiger Ladestation dokumentiert
- fünf von fünf Wakeword-Aktivierungen bis ungefähr 90 Zentimeter sofort erkannt
- sämtliche produktiven Python-Module unter 400 und Funktionen unter 36 Zeilen gehalten
- 407 Tests, Kompilierung, strikten Dokumentationsbau und Diff-Prüfung bestanden
- `.env`, lokale Audiodaten, Diagnosen und Secrets weiterhin vom Git-Stand ausgeschlossen

## ElevenLabs-Prosodieprofile physisch abgenommen

- bisher verworfenen Sprachstil bis in den ElevenLabs-Request weitergegeben
- bestätigtes neutrales und gewöhnliches Gesprächsprofil unverändert erhalten
- unterstützende Ausgabe geringfügig variabler und sanfter abgestimmt
- vorsichtige Ausgabe stabiler gehalten, ohne sie merklich zu verlangsamen
- Style-Übertreibung wegen möglicher Latenz und Instabilität nicht erhöht
- beide Profile nacheinander über ElevenLabs und Vector-SDK wiedergegeben
- Vector-Verbindung und beide Audiowiedergaben ohne Fehler abgeschlossen
- beide Varianten vom Benutzer als natürlich genug bestätigt
- 410 automatisierte Tests und strikten Dokumentationsbau bestanden

## Karte 20 – Kontextabhängige Vorschläge kontrolliert freigegeben

- produktive Aktivierung auf zwei eindeutige deutsche Einleitungen begrenzt
- normale Gespräche ohne zusätzlichen Klassifikationsaufruf erhalten
- Modellkatalog auf das deutlich sichtbare feste Reflexionsprofil reduziert
- Toolnamen, Parameter und Autorisierung weiterhin ausschließlich lokal bestimmt
- nur abstrakte Vorschlags-ID und lokale Bezeichnung vorübergehend gehalten
- offene Vorschläge nach 30 Sekunden automatisch verworfen
- `Nein`, `Abbrechen` und Sitzungsende ohne Ausführung behandelt
- unmittelbar vor einem bestätigten Aufruf erneut gegen die Registry geprüft
- separate einmalige Mutationsfreigabe erst nach einem exakten `Ja` erzeugt
- unbekannte IDs, Schemaerweiterungen und Modellfehler inhaltsfrei blockiert
- lokales Qwen bei eindeutigen Anfragen stabil auf eine abstrakte, lokal
  geprüfte Vorschlags-ID begrenzt
- reale Vorschlagsfrage über ElevenLabs am physischen Vector verständlich ausgegeben
- Vorschlagsausgabe vom Benutzer als erfolgreich bestätigt
- wartenden Diagnoselauf ohne exaktes separates `Ja` ohne Bewegung beendet
- reales `Ja` erkannt und `eyes_only` laut Audit erfolgreich ausgeführt; die
  Animation erwies sich am physischen Vector jedoch als nicht sichtbar genug
- kontextabhängigen Katalog deshalb auf die erprobte 18-Grad-Kopf-, Augen- und
  Rückkehrsequenz `reflective_expression` umgestellt
- durch WirePods Satzende nach `Welche Aktion passt dazu?` ausgelösten Abbruch
  mit einem kontrollierten 30-Sekunden-Kontextfenster für die nächste Eingabe
  abgefangen
- getrennten Drei-Schritt-Sprachpfad mit Kontext, Bestätigung und deutlich
  sichtbarer Reflexionsaktion am physischen Vector erfolgreich abgenommen
- 427 Tests, Kompilierung, strikten Dokumentationsbau und Diff-Prüfung bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Karte 21 – Erstes lokales Bürotool implementiert

- `office.local_datetime` als produktives Read-only-Tool registriert
- Datum und Uhrzeit ausschließlich aus der lokalen Systemzeit erzeugt
- deutsche Wochentage und Monatsnamen unabhängig vom System-Locale festgelegt
- feste Sprachabsichten für Uhrzeit und Datum ohne Modellklassifikation ergänzt
- Toolparameter auf die lokalen Werte `date` und `time` begrenzt
- natürliche deutsche Antwort ohne OpenAI, Ollama oder Netzwerk aufgebaut
- Aufruf ohne Bestätigung, Mutation, Datei- oder Dokumentzugriff gehalten
- ungültige Modi und Clockfehler an der Registry-Grenze neutral abgefangen
- gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- Uhrzeitfrage am physischen Vector korrekt über das lokale Tool beantwortet
- Datumsfrage von WirePod real als `welchen tag haben wir heute` erkannt und
  wegen fehlender Variante zunächst fälschlich an Qwen weitergereicht
- beobachtete Vosk-Variante in die feste Datumsauswahl aufgenommen
- nicht eindeutig freigegebene Datums- und Uhrzeitfragen gegen Modell-Fallback
  gesperrt, damit kein Sprachmodell aktuelle Zeitangaben erfinden kann
- `Welcher Tag ist heute?` als zuverlässige WirePod-Formulierung bestätigt
- korrekte lokale Antwort für Donnerstag, den 20. August 2026 physisch gehört
- erfolgreiche Read-only-Ausführungen für Uhrzeit und Datum im Audit bestätigt
- 437 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 22 – Kontrollierte lokale Projektstatus-Abfrage

- `development.project_status` als argumentloses Read-only-Tool implementiert
- Projektwurzel innerhalb der Runtime festgelegt und freie Pfade ausgeschlossen
- Git-Aufrufe auf Branch, kurzen Commit-Hash und Statuszähler begrenzt
- Shellausführung, freie Unterbefehle und Modellparameter ausgeschlossen
- offene Änderungen nur gezählt, ohne Dateinamen oder Diffs auszugeben
- letzten festen lokalen Kernabnahmebericht als bestanden, fehlgeschlagen oder
  unbekannt ausgewertet
- Branchnamen und Commit-Hash vor der strukturierten Ausgabe streng validiert
- Zeitlimit und bereinigte Registry-Fehlergrenze für lokale Git-Aufrufe verwendet
- festen Sprachbefehl `Wie ist der Projektstatus?` ohne Modellaufruf ergänzt
- 51 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Metadatenaufruf auf Branch `main` erfolgreich geprüft
- ersten Sprachversuch von WirePod als `wie ist der projekt status` erkannt
- getrenntes Vosk-Kompositum deshalb als feste erlaubte Variante ergänzt
- weitere erkennbare Projektstatusfragen gegen Modell-Fallback gesperrt
- zweiten Versuch als `wie ist das projekt`, `wie ist ihr projekt status` und
  `ist der projekt status` beobachtet
- Projekt-plus-Status-Transkriptionen auf das feste argumentlose Read-only-Tool
  kanonisiert und die vollständige Verkürzung separat freigegeben
- Kurzbefehl `Projekt Status` am physischen Vector erfolgreich erkannt
- lokale Statusausgabe verständlich wiedergegeben und vom Benutzer bestätigt
- erfolgreiche argumentlose Read-only-Ausführung im lokalen Audit nachgewiesen
- 449 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 23 – Kontrollierter lokaler Projekt-Testlauf

- `development.run_core_tests` als argumentloses mutierendes Tool implementiert
- ausschließlich die feste lokale Python-Test-Suite ohne Shellzugriff zugelassen
- Interpreter, Projektwurzel, Testziel und Zeitlimit intern festgelegt
- freie Pfade, Befehle, Prozessargumente und Modellparameter ausgeschlossen
- separates `Ja` vor jedem Testlauf über die bestehende Registry-Grenze erzwungen
- Rohdaten aus Standard- und Fehlerausgabe vollständig aus Tool- und Sprachausgabe entfernt
- Rückgabe auf Ergebnis, Testanzahl, Laufzeit und lokalen Sprechtext begrenzt
- fehlgeschlagene Tests transparent und ohne interne Fehlermeldungen dargestellt
- feste Sprachvarianten für `Projekt Test` und `Projekt Tests` ergänzt
- 55 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Registry-Lauf mit 460 erfolgreichen Tests geprüft
- ersten Sprachversuch von WirePod als `projekte ist` erkannt
- ausschließlich diese beobachtete Lautvariante auf das bestätigungspflichtige,
  argumentlose Test-Tool abgebildet
- festen Testlauf nach separatem `Ja` am physischen Vector erfolgreich ausgeführt
- gesprochenen Hunderter und Rest nach akustisch missverständlicher Testanzahl getrennt
- erfolgreicher mutierender Registry-Aufruf ohne Argumente im lokalen Audit bestätigt
- 460 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 24 – Lokaler Read-only-Systemstatus

- `system.local_service_status` als argumentloses Read-only-Tool implementiert
- WirePod und Ollama ausschließlich über fest konfigurierte lokale Healthchecks geprüft
- freie Hosts, URLs, Ports, Pfade und Modellparameter ausgeschlossen
- Transportfehler ohne technische Details als nicht erreichbar dargestellt
- Ausgabe auf boolesche Zustände und einen lokalen deutschen Sprechtext begrenzt
- Internet-, OpenAI-, ElevenLabs-, Akku- und Hardwarestatus bewusst ausgeschlossen
- stille WirePod-Statusprüfung vom sichtbaren Startup-Fehlerpfad getrennt
- festen Sprachbefehl `System Status` ohne Modellaufruf oder Bestätigung ergänzt
- 60 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Aufruf mit verfügbarem WirePod und Ollama erfolgreich geprüft
- Sprachbefehl `System Status` am physischen Vector erfolgreich beantwortet
- erfolgreichen argumentlosen Read-only-Aufruf im lokalen Audit bestätigt

- 471 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 25 – Lokaler Read-only-Bibliotheksstatus

- `knowledge.library_status` als argumentloses Read-only-Tool implementiert
- dieselbe `IndexedKnowledgeLibrary` gemeinsam für Agent und Tool verdrahtet
- Dokumentstatus vor jeder Toolausgabe auf vier begrenzte Zähler reduziert
- Titel, Pfade, Prüfsummen, Importzeiten, Modelle und Inhalte ausgeschlossen
- Dokumente, Abschnitte sowie aktuelle und veraltete Vektoren zusammengefasst
- leere Bibliothek mit einem eigenen transparenten deutschen Sprechtext behandelt
- Singular, Plural und Dativ der festen deutschen Ausgabe automatisiert geprüft
- freie Datenbank-, Datei-, Dokument- und Modellparameter ausgeschlossen
- festen Sprachbefehl `Bibliothek Status` ohne Modellaufruf oder Bestätigung ergänzt
- 72 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Aufruf mit einer leeren Bibliothek erfolgreich geprüft
- Sprachbefehl `Bibliothek Status` am physischen Vector korrekt beantwortet
- erfolgreichen argumentlosen Read-only-Aufruf im lokalen Audit bestätigt
- 479 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 26 – Lokaler Read-only-Gedächtnisstatus

- `MemoryStatistics` als inhaltsfreien Zähler-Datentyp ergänzt
- Erinnerungen und Stil-Feedback in einer lokalen SQLite-Abfrage getrennt gezählt
- `memory.local_status` als argumentloses Read-only-Tool implementiert
- Agent und Tool mit derselben `SQLiteMemoryStore`-Instanz verdrahtet
- Inhalte, Kategorien, Quellen, Zeitpunkte und IDs aus der Ausgabe ausgeschlossen
- leeren Gedächtniszustand transparent und ohne erfundene Angaben behandelt
- freie Suchtexte, Memory-IDs, Kategorien und Datenbankpfade ausgeschlossen
- festen Sprachbefehl `Gedächtnis Status` ohne Modellaufruf oder Bestätigung ergänzt
- Storage- und Tool-Komposition aus der wachsenden Runtime fachlich ausgelagert
- bisherige Runtime-Importpfade für bestehende Aufrufer beibehalten
- 91 gezielte Datenbank-, Registry-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Aufruf mit leerem bestätigtem Gedächtnis erfolgreich geprüft
- Sprachbefehl `Gedächtnis Status` am physischen Vector korrekt wiedergegeben
- erfolgreichen argumentlosen Read-only-Aufruf im lokalen Audit bestätigt
- 487 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen

## Punkt 27 – Kontrollierter lokaler Roadmapstatus

- `development.next_roadmap_item` als argumentloses Read-only-Tool implementiert
- Projektwurzel, `docs/roadmap.md` und Abschnitt `Tools und Sicherheit` festgelegt
- freie Pfade, Abschnitte, Suchtexte und Modellparameter ausgeschlossen
- Ausgabe auf den ersten offenen Eintrag und lokalen Sprechtext begrenzt
- Dateigröße, Ausgabelänge und erlaubte Zeichen streng validiert
- URLs, Pfadtrenner, Steuerzeichen und ungeprüfte Lesefehler abgefangen
- festen Sprachbefehl `Was ist der nächste Projektpunkt?` ohne Modellaufruf ergänzt
- nächsten konkreten Sicherheitsausbau in der Roadmap sichtbar hinterlegt
- 66 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Roadmapaufruf mit dem erwarteten nächsten Eintrag geprüft
- 497 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen
- Voice-Runtime nach einem vorübergehenden WirePod-Abbruch kontrolliert neu gestartet
- Sprachbefehl am physischen Vector korrekt erkannt und beantwortet
- erfolgreichen argumentlosen Read-only-Aufruf im lokalen Audit bestätigt

## Punkt 28 – Kontrollierter lokaler Dokumentationsstatus

- `development.documentation_status` als argumentloses Read-only-Tool implementiert
- sechs öffentlich versionierte Kerndokumente als feste Allowlist definiert
- Projektzugehörigkeit, Dateityp, Größe, UTF-8 und Hauptüberschrift lokal geprüft
- freie Pfade, Verzeichnisse, Dateinamen, Kriterien und Modellparameter ausgeschlossen
- Ausgabe auf Vollständigkeitszustand und vier begrenzte Zähler reduziert
- Dateinamen, Pfade, Inhalte und interne Lesefehler aus Sprache und Audit entfernt
- fehlende und ungültige Dokumente mit korrektem Singular und Plural behandelt
- festen Sprachbefehl `Dokumentation Status` ohne Modellaufruf ergänzt
- 69 gezielte Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- realen lokalen Aufruf mit sechs von sechs gültigen Dokumenten geprüft
- 507 automatisierte Tests, Kompilierung und strikten Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen
- Sprachbefehl am physischen Vector aktiv erkannt und korrekt beantwortet
- erfolgreichen argumentlosen Read-only-Aufruf im lokalen Audit bestätigt

## Punkt 29 – Kontrollierte Recherchequelle mit Netzwerkrecht

- `NETWORK` als eigene Berechtigungsstufe neben lokalem Lesen und Mutationen ergänzt
- `ToolAuthorization` um eine separate, boolesch validierte Netzwerkfreigabe erweitert
- Netzwerkzugriffe ohne `allow_network=True` vollständig vor Ausführung blockiert
- zusätzliche Einmalbestätigung für jeden externen Aufruf erzwungen
- Mutationsrechte ausdrücklich von Netzwerkrechten getrennt
- Netzwerk-Tools aus strukturierten Modellvorschlägen ausgeschlossen
- `research.python_source_status` als argumentloses Netzwerk-Tool implementiert
- ausschließlich `https://www.python.org/downloads/` als feste Quelle erlaubt
- freie URLs, Suchbegriffe, Header, Weiterleitungen und Zeitlimits ausgeschlossen
- Abruf auf eine begrenzte `HEAD`-Anfrage ohne Seiteninhalt reduziert
- Transportfehler ohne technische oder private Details als nicht erreichbar behandelt
- festen Sprachbefehl `Recherchequelle prüfen` mit separatem `Ja` ergänzt
- WirePod-Variante `recherche quelle überprüfen` gezielt freigegeben
- mehrdeutige Fehltranskription `schärfe quellen überprüfen` bewusst blockiert
- weitere reale Transkriptionen als zu verstümmelt für Netzwerkfreigabe bewertet
- bevorzugten kurzen Befehl `Python Status` mit eindeutiger Quellenbindung ergänzt
- unklare Recherchefragen vor dem Modell-Fallback mit Wiederholungsbitte blockiert
- 106 gezielte Berechtigungs-, Registry-, Dialog-, Runtime- und Qualitätstests bestanden
- Netzwerkberechtigung ohne Remote-Inhalte im lokalen Auditformat abgesichert
- 526 automatisierte Tests, Kompilierung und strikter Dokumentationsbau bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen
- physischen Bestätigungsdialog mit `Python Status` erfolgreich abgeschlossen
- kontrollierten Netzwerkaufruf als Audit-Ereignis 18 mit Status `success` bestätigt

## Punkt 30 – Inhaltlich begrenzte Python-Versionsabfrage

- `research.python_latest_version` als separates argumentloses Netzwerk-Tool implementiert
- dieselbe feste offizielle Python.org-Downloadseite ohne freie Ziele verwendet
- Streaming-Abruf auf höchstens 750.000 Bytes begrenzt
- Weiterleitungen, andere Medientypen, Fehlerstatus und ungültiges UTF-8 abgewiesen
- ausschließlich stabile Versionsnummern im festen Format `3.x.y` akzeptiert
- Alpha-, Beta- und Release-Candidate-Versionen aus der Auswahl ausgeschlossen
- Ergebnis auf Quelle, Prüfstatus, Versionsnummer und lokalen Sprechtext reduziert
- Webseiteninhalt und mögliche eingebettete Anweisungen vor Modell und TTS verworfen
- bei uneindeutiger Antwort bewusst keine Version geraten
- festen Sprachbefehl `Python Version` mit separater Netzwerkbestätigung ergänzt
- `Python Status` unverändert als reine Erreichbarkeitsprüfung beibehalten
- Auswahlhilfen in `tools/selection_matching.py` strukturell ausgelagert
- 82 gezielte Tool-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- 538 automatisierte Tests bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen
- physischen Bestätigungsdialog und Versionsabruf erfolgreich abgeschlossen
- kontrollierten Aufruf als Audit-Ereignis 19 mit Netzwerkrecht und Status `success` bestätigt

## Punkt 31 – Letzte Projektänderung aus festem Changelog

- `development.latest_change` als argumentloses Read-only-Tool implementiert
- Projektwurzel, `CHANGELOG.md` und Abschnitt `[Unreleased]` fest vorgegeben
- ausschließlich den ersten dokumentierten Änderungseintrag ausgelesen
- freie Pfade, Dateinamen, Abschnitte, Suchtexte und Modellparameter ausgeschlossen
- Dateigröße und Ausgabelänge mit festen Obergrenzen abgesichert
- URLs, Pfadtrenner, Steuerzeichen und nicht unterstütztes Markup blockiert
- Markdown-Codezeichen vor der begrenzten Ausgabe lokal entfernt
- Ergebnis auf Fundstatus, eine sichere Zusammenfassung und Sprechtext reduziert
- Diffs, weitere Changelog-Einträge und interne Fehler vollständig verworfen
- festen Sprachbefehl `Projekt Änderung` ohne Modellaufruf ergänzt
- 81 gezielte Datei-, Registry-, Auswahl-, Dialog-, Runtime- und Qualitätstests bestanden
- 547 automatisierte Tests bestanden
- vollständige Kernabnahme mit vier von vier Prüfungen abgeschlossen
- physischen Sprachtest erfolgreich abgeschlossen
- argumentlosen Read-only-Aufruf als Audit-Ereignis 20 mit Status `success` bestätigt

## Punkt 32 – Deutsche Funktionsdokumentation

- verbindlichen Standard auf kurze deutsche Docstrings umgestellt
- öffentliche und private Produktionsfunktionen, Methoden, Konstruktoren,
  Properties und Protokollmethoden ausdrücklich einbezogen
- Tests mit selbsterklärenden `test_...`-Namen bewusst von Zusatztexten ausgenommen
- aktive deutsche Verben und konkrete Verantwortungsbeschreibungen vorgegeben
- Sicherheits-, Datenschutz- und Fehlergrenzen als dokumentationswürdig festgelegt
- 90 produktive Python-Dateien mit 763 Funktionen und Methoden inventarisiert
- 294 vorhandene und 469 fehlende Funktions-Docstrings festgestellt
- paketweise Migration vor Aktivierung der endgültigen Vollständigkeitssperre festgelegt
- Paket `tools/` mit 168 von 168 deutschen Funktions-Docstrings abgeschlossen
- 109 Tooltests und sieben strukturelle Qualitätstests nach dem ersten Paket bestanden
- größtes Toolmodul mit 363 Zeilen weiterhin unter der 400-Zeilen-Grenze gehalten
- Paket `application/` mit 174 von 174 deutschen Funktions-Docstrings abgeschlossen
- 97 gezielte Anwendungs-, Dialog-, Runtime- und Watchdog-Tests bestanden
- größtes Anwendungsmodul mit 348 Zeilen weiterhin unter der 400-Zeilen-Grenze gehalten
- Paket `brain/` mit 99 von 99 deutschen Funktions-Docstrings abgeschlossen
- Paket `memory/` mit 156 von 156 deutschen Funktions-Docstrings abgeschlossen
- 189 gezielte Agenten-, Anbieter-, Persönlichkeits-, Speicher- und Suchtests bestanden
- größtes Kernmodul mit 360 Zeilen weiterhin unter der 400-Zeilen-Grenze gehalten
- Pakete `vector/`, `voice/`, `diagnostics/`, `config/` und `main.py` mit 166 von 166 deutschen Funktions-Docstrings abgeschlossen
- 108 gezielte Hardware-, Sprach-, Eingabe-, Diagnose- und Konfigurationstests bestanden
- größtes Modul dieser Abnahmestufe mit 376 Zeilen unter der 400-Zeilen-Grenze gehalten
- alle 763 produktiven Funktionen und Methoden paketübergreifend dokumentiert
- Vollständigkeitssperre für öffentliche und private Funktions-Docstrings aktiviert
- englische Standardformulierungen als automatischen Rückfalltest ergänzt
- neun strukturelle Qualitätsprüfungen einschließlich 35- und 400-Zeilen-Grenzen bestanden
- 549 automatisierte Tests, Python-Kompilierung und strikter Dokumentationsbau bestanden
- vollständige lokale Kernabnahme mit vier von vier Prüfungen abgeschlossen
