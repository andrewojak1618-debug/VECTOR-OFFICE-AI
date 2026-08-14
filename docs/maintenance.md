# Export, Versionen und Wiederherstellung

Die Wartungsfunktionen kontrollieren die lokale Bibliothek, ohne Dokumenttexte
oder Embedding-Vektoren in Diagnose- oder Metadatenexporte aufzunehmen.

## Übersicht und Versionsstatus

`/documents` zeigt für jedes Dokument:

- ID, Titel und Importzeit,
- vollständige SHA-256-Prüfsumme,
- Anzahl der bekannten Dokumentversionen,
- aktives Embedding-Modell samt Digest und Dimension,
- Anzahl aktueller und veralteter Vektoren.

Jeder geänderte Import erzeugt einen Eintrag in
`knowledge_document_versions`. Gespeichert werden nur Prüfsumme,
Versionsnummer, Abschnittsanzahl und Importzeit. Unveränderte Importe erzeugen
keine zusätzliche Version. Bestehende Datenbanken erhalten bei der Migration
zerstörungsfrei einen ersten Versionsdatensatz für ihren aktuellen Stand.

```text
/versions 4
/stale-vectors
```

`/versions ID` zeigt die Metadatenhistorie eines Dokuments. `/stale-vectors`
zeigt ausschließlich IDs, Modellinformationen, Dimension und Zeitstempel;
Vektorwerte und Dokumentinhalte bleiben verborgen.

## Reindexierung

```text
/reindex 4
/reindex-all
```

`/reindex ID` baut ein einzelnes Dokument vollständig neu auf.
`/reindex-all` verarbeitet alle importierten Dokumente lokal mit dem aktuell
konfigurierten Ollama-Embedding-Modell. Fortschrittsausgaben enthalten nur
Zähler. Schlägt ein Provider-Batch fehl, werden für dieses Dokument keine
unvollständigen neuen Vektoren gespeichert.

## Getrennte Exporte

```text
/export-library data/exports/library-metadata.json
/export-memories data/exports/confirmed-memories.json
```

Beide Befehle schreiben UTF-8-JSON atomar über eine temporäre Datei. Die
Bibliotheksdatei enthält Dokument-, Versions- und Modellmetadaten, jedoch keine
Dokumenttexte, Vektorwerte oder absoluten Quellpfade. Der Erinnerungs-Export ist
absichtlich getrennt und enthält ausschließlich ausdrücklich bestätigte
Erinnerungen. Gängige Schlüssel-, Token-, Passwort- und Secret-Muster werden
vor dem Schreiben durch `[REDACTED]` ersetzt.

!!! warning
    Erinnerungen können trotz automatischer Secret-Redaktion persönliche Daten
    enthalten. Exportdateien bleiben lokal, gehören nicht ins Repository und
    sollten nur verschlüsselt weitergegeben oder gesichert werden.

## Löschung

`/forget-document ID` löscht den Dokumentdatensatz. SQLite entfernt über
`ON DELETE CASCADE` seine Abschnitte, Embeddings und Versionsmetadaten. Der
Anwendungsdienst prüft danach zusätzlich, dass kein Dokument-, Versions- oder
Vektordatensatz für diese ID erreichbar ist. Ein Fehlschlag wird ausdrücklich
gemeldet.

## Wiederherstellungsstrategie

Der Metadatenexport ist ein Audit-Nachweis, kein vollständiges Backup der
Dokumentinhalte. Für eine vollständig wiederherstellbare lokale Sicherung:

1. Vector Office AI beenden, damit keine Schreibtransaktion aktiv ist.
2. `data/vector_memory.db` in einen verschlüsselten Sicherungsort kopieren.
3. Die bewusst importierten Originaldokumente separat sichern.
4. `.env` nur in einem Secret-Manager oder verschlüsselten Tresor sichern und
   niemals zusammen mit normalen Exporten oder im Repository ablegen.
5. Zur Wiederherstellung die SQLite-Datei bei beendetem Programm an
   `MEMORY_DB_PATH` zurückkopieren und anschließend `/documents` prüfen.
6. Fehlen Embeddings oder wurde das Modell gewechselt, `/reindex-all`
   ausführen. Embeddings sind vollständig aus den Originaldokumenten
   reproduzierbar.

Wenn nur Originaldokumente und Metadatenexport vorhanden sind, werden die
Dokumente erneut mit `/learn PFAD` importiert und danach lokal reindexiert. Für
eine exakte automatische Wiederherstellung bestätigter Erinnerungen bleibt die
SQLite-Sicherung maßgeblich; der getrennte JSON-Export dient bis zu einem
späteren kontrollierten Importbefehl als lesbare Sicherheitskopie.
