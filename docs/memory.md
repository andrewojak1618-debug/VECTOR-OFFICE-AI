# Gemeinsames Gedächtnis und Dokumentbibliothek

Das Langzeitgedächtnis liegt lokal in SQLite. OpenAI und Ollama erhalten über
den Agenten dieselben relevanten, bestätigten Erinnerungen.

Zusätzlich können ausgewählte Markdown- und Textdateien in eine lokale
Dokumentbibliothek aufgenommen werden. Ein Import geschieht ausschließlich auf
einen bewussten `/learn`-Befehl hin.

## Kontrollierte Speicherung

Nur der Benutzer entscheidet, was dauerhaft gespeichert wird:

- `/remember TEXT` speichert eine bestätigte Erinnerung.
- `/feedback TEXT` speichert bestätigtes Feedback ausschließlich für Stil und Ton.
- `/memories` zeigt gespeicherte Einträge und IDs.
- `/forget ID` löscht einen Eintrag dauerhaft.
- `/clear` entfernt nur den aktuellen Gesprächskontext.

Im Sprachdialog bereitet der bevorzugte Alias `Erinnerung speichern: …` genau
einen lokalen Fakt vor; `Merke dir, dass …` bleibt zusätzlich verfügbar. Der
Inhalt bleibt zunächst nur im Arbeitsspeicher und wird in der anschließenden
Frage nicht wiederholt. Erst ein getrenntes eindeutiges `Ja` übergibt ihn einmal
an `memory.remember_confirmed`; `Nein`, Abbruch und Zeitüberschreitung verwerfen
ihn. Die Spracheingabe ist auf 240 Zeichen und eine Zeile begrenzt. Freie
Kategorien, Quellen, Datenbankpfade oder Memory-IDs sind dabei ausgeschlossen.

Das Toolargument `content` ist als sensibel markiert. Das lokale Tool-Audit
speichert deshalb ausschließlich `[REDACTED]`, Status und Werkzeugname. Die
Registry-Ausgabe bestätigt nur den Speichervorgang und enthält weder Text noch
ID. OpenAI, Ollama und Diagnosen werden für Vorbereitung und Speicherung nicht
aufgerufen.

Jeder Eintrag enthält Inhalt, Kategorie, Herkunft und Zeitstempel. Doppelte
Inhalte werden nicht mehrfach angelegt. Feedback erhält die eigene Kategorie
`feedback`, wird von der Faktensuche ausgeschlossen und kann weiterhin über
`/memories` eingesehen sowie über `/forget ID` gelöscht werden.

## Abruf

Bestätigte Erinnerungen verwenden weiterhin eine transparente lexikalische
Suche. Dokumentabschnitte kombinieren ihre bestehende lexikalische Rangfolge mit
lokaler semantischer Kosinus-Ähnlichkeit. Der Agent führt beide Ergebnisgruppen
als klar getrennte lokale Kontextabschnitte zusammen.

Eine providerunabhängige Embedding-Schnittstelle und ein lokaler Ollama-Adapter
sind in `memory/embeddings.py` umgesetzt. Einzeltexte und mehrere Abschnitte
können real mit `embeddinggemma` vektorisiert und über
`memory/embedding_store.py` dauerhaft in SQLite gespeichert werden.
`memory/search.py` nutzt ausschließlich aktuelle Vektoren der aktiven
Modellversion. Ist Ollama nicht verfügbar, bleibt die lexikalische Suche
automatisch funktionsfähig.

## Persistente Dokumentvektoren

Die Tabelle `knowledge_embeddings` ordnet jeden Vektor eindeutig über
`chunk_id` einem Dokumentabschnitt zu. Gespeichert werden:

- Modellname und vollständiger Ollama-Modell-Digest,
- Vektordimension und SHA-256-Hash des Abschnittstextes,
- kompakter Little-Endian-Float32-BLOB,
- Erstellungs- und Aktualisierungszeitpunkt.

Die Kombination aus Abschnitt, Modell und Modellversion ist eindeutig. Ein
erneutes Indexieren aktualisiert den bestehenden Datensatz. Abweichende
Modell-Digests, Dimensionen oder Inhaltshashes kennzeichnen veraltete Vektoren.
Beim Löschen oder Ersetzen eines Dokuments entfernt SQLite über mehrstufiges
`ON DELETE CASCADE` automatisch auch die betroffenen Vektoren.

Erinnerungen gelten für das Modell ausdrücklich als Daten, niemals als
Anweisungen. Dadurch wird das Risiko gespeicherter Prompt-Manipulationen
reduziert.

## Kontrollierter Dokumentimport

- `/learn PFAD` importiert und indexiert eine UTF-8-kodierte `.md`- oder
  `.txt`-Datei lokal.
- `/documents` zeigt alle importierten Dokumente mit Quelle und ID.
- `/reindex ID` erzeugt den lokalen semantischen Index vollständig neu.
- `/reindex-all` baut alle lokalen Dokumentvektoren vollständig neu auf.
- `/versions ID` zeigt die zeitlich geordnete Prüfsummen-Historie.
- `/stale-vectors` zeigt veraltete Vektormetadaten ohne Vektorwerte.
- `/export-library PFAD.json` exportiert nur sichere Bibliotheksmetadaten.
- `/export-memories PFAD.json` exportiert bestätigte Erinnerungen getrennt.
- `/forget-document ID` entfernt ein Dokument und sämtliche Abschnitte.
- Dateien sind auf 2 MiB begrenzt und werden in Abschnitte zerlegt.
- Eine SHA-256-Prüfsumme verhindert unveränderte Doppelimporte.
- Bei einer geänderten Quelldatei bleiben identische Abschnitte samt Vektoren
  erhalten; nur geänderte Abschnitte werden ersetzt und neu indexiert.
- Nicht mehr vorhandene Abschnitte und ihre Vektoren werden automatisch
  entfernt.

Quellpfad, Titel, Prüfsumme und Importzeit bleiben nachvollziehbar. Auch hybride
Treffer behalten Quelle und Abschnittsnummer.

Geänderte Dokumente erhalten zusätzlich eine fortlaufende Metadatenversion mit
Prüfsumme, Importzeit und Abschnittsanzahl. Dokumentinhalte werden dafür nicht
dupliziert. Details zu Export, Löschverifikation und Wiederherstellung stehen
unter [Export, Versionen und Wiederherstellung](maintenance.md).

## Datenschutzgrenze

Importierte Dokumentinhalte werden standardmäßig nur Ollama bereitgestellt.
Bei OpenAI bleiben sie gesperrt, solange `KNOWLEDGE_ALLOW_CLOUD=false` gesetzt
ist. Erst eine ausdrückliche Änderung auf `true` erlaubt die Übergabe passender
Dokumentauszüge an den Cloud-Anbieter.

Diese Freigabe überträgt nur die für eine konkrete Anfrage ausgewählten
Auszüge. Bibliotheksdatenbank und Embeddings bleiben lokal; auch die semantische
Auswahl läuft weiterhin über Ollama. Details stehen unter
[Datenschutz und Kontextschutz](privacy.md).

Auch freigegebene Dokumentauszüge werden im Modellkontext ausdrücklich als
Daten und nicht als ausführbare Anweisungen markiert. Sie werden JSON-kodiert
und als `UNVERTRAUENSWÜRDIGE_DOKUMENTDATEN` gekennzeichnet. Mehrere Quellen
erzeugen zusätzlich einen transparenten Hinweis auf mögliche Konflikte.

## Lokaler Integrationstest

Der wiederverwendbare Diagnoseablauf importiert ein temporäres Dokument,
prüft den lexikalischen Abruf und lässt eine echte Ollama-Instanz die darin
enthaltene Testinformation beantworten:

```powershell
.venv\Scripts\python.exe -m diagnostics.library_ollama
```

Dabei werden weder OpenAI noch die produktive Memory-Datenbank verwendet.

Für den vollständigen physischen Pfad kann zusätzlich die Projekt-README als
temporäres Wissen bis zur deutschen Sprachausgabe auf Vector getestet werden:

```powershell
.venv\Scripts\python.exe -m diagnostics.library_vector
```

## Geplante Erweiterung

- ✅ providerunabhängige Typen und lokale Ollama-Embeddings
- ✅ Modellverfügbarkeit, Batch-Verarbeitung und Dimension validieren
- ✅ realen lokalen Aufruf mit `embeddinggemma` ausführen
- ✅ Embedding-Vektoren versioniert und kompakt in SQLite speichern
- ✅ Duplikate, Aktualität und Cascade-Löschung absichern
- ✅ automatische differentielle Indexierung und manuelle Reindexierung
- ✅ hybride semantische und lexikalische Suche integrieren
- ✅ Metadaten-Versionierung und Modellstatus
- ✅ getrennte, Secret-bereinigte JSON-Exporte
- ✅ vollständige Reindexierung und verifizierte Löschung
- ✅ bestätigtes, getrennt behandeltes Stilfeedback für beide Provider
- ✅ kontrollierter Sprachpfad für lokale Erinnerungen einschließlich
  Speicherung und späterem Abruf am physischen Vector abgenommen
