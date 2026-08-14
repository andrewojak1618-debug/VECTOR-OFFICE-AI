# Gemeinsames Gedächtnis und Dokumentbibliothek

Das Langzeitgedächtnis liegt lokal in SQLite. OpenAI und Ollama erhalten über
den Agenten dieselben relevanten, bestätigten Erinnerungen.

Zusätzlich können ausgewählte Markdown- und Textdateien in eine lokale
Dokumentbibliothek aufgenommen werden. Ein Import geschieht ausschließlich auf
einen bewussten `/learn`-Befehl hin.

## Kontrollierte Speicherung

Nur der Benutzer entscheidet, was dauerhaft gespeichert wird:

- `/remember TEXT` speichert eine bestätigte Erinnerung.
- `/memories` zeigt gespeicherte Einträge und IDs.
- `/forget ID` löscht einen Eintrag dauerhaft.
- `/clear` entfernt nur den aktuellen Gesprächskontext.

Jeder Eintrag enthält Inhalt, Kategorie, Herkunft und Zeitstempel. Doppelte
Inhalte werden nicht mehrfach angelegt.

## Abruf

Die aktuelle Grundlage verwendet eine transparente lexikalische Suche. Nur
passende Einträge werden als lokale Wissensbasis in den Systemkontext der
aktuellen Anfrage aufgenommen.

Eine providerunabhängige Embedding-Schnittstelle und ein lokaler Ollama-Adapter
sind in `memory/embeddings.py` umgesetzt. Einzeltexte und mehrere Abschnitte
können real mit `embeddinggemma` vektorisiert und über
`memory/embedding_store.py` dauerhaft in SQLite gespeichert werden. Die
produktive Suche verwendet die Vektoren noch nicht.

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
- `/forget-document ID` entfernt ein Dokument und sämtliche Abschnitte.
- Dateien sind auf 2 MiB begrenzt und werden in Abschnitte zerlegt.
- Eine SHA-256-Prüfsumme verhindert unveränderte Doppelimporte.
- Bei einer geänderten Quelldatei bleiben identische Abschnitte samt Vektoren
  erhalten; nur geänderte Abschnitte werden ersetzt und neu indexiert.
- Nicht mehr vorhandene Abschnitte und ihre Vektoren werden automatisch
  entfernt.

Quellpfad, Titel, Prüfsumme und Importzeit bleiben nachvollziehbar. Die aktuelle
Suche ist bewusst transparent und lexikalisch.

## Datenschutzgrenze

Importierte Dokumentinhalte werden standardmäßig nur Ollama bereitgestellt.
Bei OpenAI bleiben sie gesperrt, solange `KNOWLEDGE_ALLOW_CLOUD=false` gesetzt
ist. Erst eine ausdrückliche Änderung auf `true` erlaubt die Übergabe passender
Dokumentauszüge an den Cloud-Anbieter.

Auch freigegebene Dokumentauszüge werden im Modellkontext ausdrücklich als
Daten und nicht als ausführbare Anweisungen markiert.

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
- hybride semantische und lexikalische Suche integrieren
- Vertrauensstatus und erweiterte Versionshistorie
- Export- und vollständige Löschfunktionen
- bestätigtes Feedback für beide Provider
