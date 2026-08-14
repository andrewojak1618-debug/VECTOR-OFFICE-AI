# Lokale Embedding-Architektur

Die semantische Grundlage ist providerunabhängig aufgebaut und verwendet
aktuell ausschließlich einen lokalen Ollama-Adapter. Einzeltexte und mehrere
Dokumentabschnitte können real vektorisiert und dauerhaft in SQLite gespeichert
werden. Die produktive Suche bleibt bis zur Ähnlichkeitsbewertung zunächst
lexikalisch.

## Modellauswahl

`embeddinggemma` wurde als lokales Standardmodell ausgewählt. Es ist ein
mehrsprachiges On-Device-Modell mit 300 Millionen Parametern, ungefähr 622 MB,
einem Kontextfenster von 2K und einer nativen Dimension von 768. Die
[Ollama-Modellseite](https://ollama.com/library/embeddinggemma) nennt es zusammen
mit der [Embedding-Dokumentation](https://docs.ollama.com/capabilities/embeddings)
als empfohlenes Modell für semantische Suche und Retrieval.

## Bausteine

| Baustein | Verantwortung |
|---|---|
| `EmbeddingText` | normalisierte, nicht leere Texteingabe |
| `EmbeddingVector` | unveränderlicher, endlicher Zahlenvektor |
| `EmbeddingResult` | Text, Vektor, tatsächliches Modell und Dimension |
| `EmbeddingProvider` | Vertrag für Verfügbarkeit, Einzel- und Batch-Erzeugung |
| `OllamaEmbeddingProvider` | lokaler Adapter für `POST /api/embed` |

Ollama erhält einen Text oder eine Liste von Abschnitten pro Aufruf.
`truncate=false` verhindert eine unbemerkte Kürzung langer Inhalte. Modellname
und tatsächliche Vektordimension werden aus der Antwort übernommen. Alle
Batch-Vektoren müssen dieselbe Dimension besitzen. Spätere Aufrufe werden gegen
die zuerst beobachtete Dimension geprüft.

Die Implementierung folgt dem aktuellen offiziellen Ollama-Endpunkt:
[Generate embeddings](https://docs.ollama.com/api/embed).

## Lokale Konfiguration

```env
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=embeddinggemma
OLLAMA_EMBEDDING_DIMENSION=0
OLLAMA_EMBEDDING_TIMEOUT=60
```

`OLLAMA_EMBEDDING_DIMENSION=0` akzeptiert die native Dimension des Modells und
zeichnet sie im Ergebnis auf. Ein positiver Wert aktiviert eine strikte
Dimensionsprüfung. Der Timeout gilt für den lokalen HTTP-Aufruf einschließlich
eines möglicherweise notwendigen Modellstarts.

Der Factory-Pfad akzeptiert bewusst nur `ollama`. Ein Cloud-Embedding-Anbieter
ist weder implementiert noch als Fallback vorgesehen.

## Modellverfügbarkeit

Vor einer Verarbeitung kann `ensure_model_available()` das Modell über
`POST /api/show` prüfen, ohne Dokumenttext zu übertragen. Ein fehlendes Modell
führt zu einem konkreten Hinweis:

```powershell
ollama pull embeddinggemma
```

Ein nicht erreichbarer Ollama-Dienst und ein nicht installiertes Modell bleiben
getrennte, verständliche Fehlerfälle.

## Fehlergrenzen

Transport- und HTTP-Fehler werden als verständlicher `EmbeddingError`
weitergegeben, ohne interne Verbindungsdetails offenzulegen. Ungültige,
mehrdeutige oder dimensionsfalsche Antworten werden abgelehnt.

Der produktive Code enthält keine Text- oder Vektorprotokollierung. Auch der
Diagnosepfad gibt nur Modellname, Dimension und Anzahl erzeugter Vektoren aus.

## Reale lokale Diagnose

```powershell
.venv\Scripts\python.exe -m diagnostics.embeddings_ollama
```

Der geprüfte Lauf mit Ollama `0.32.11` und `embeddinggemma` erzeugte drei
Vektoren in einem Batch. Modellmetadaten und Ergebnis bestätigten konsistent die
Dimension 768.

## SQLite-Speicherung

`memory/embedding_store.py` erweitert bestehende Wissensdatenbanken automatisch
um `knowledge_embeddings`. Die Vektoren werden als Float32-BLOB mit vier Byte
pro Dimension gespeichert. Modellname, vollständiger Modell-Digest, Dimension
und Chunk-Inhaltshash bilden die nachvollziehbaren Metadaten.

`memory/indexing.py` vergleicht jeden aktuellen Abschnitt mit Modellname,
Modelldigest, Dimension und Inhaltshash. Nur fehlende oder veraltete Abschnitte
werden in begrenzten Batches berechnet. Erst wenn alle Batches erfolgreich sind,
speichert eine einzige Transaktion die Ergebnisse. Unveränderte Vektoren bleiben
erhalten; entfernte Abschnitte verschwinden samt Vektoren per Cascade-Löschung.

`/learn PFAD` startet diesen Ablauf automatisch. Ein SHA-256-identisches
Dokument verursacht keine neue Embedding-Berechnung. Ein Modellwechsel wird
erkannt und erzeugt einen vollständigen Index für die neue Modellidentität.
`/reindex ID` bietet zusätzlich einen bewussten vollständigen Neuaufbau an.
Bei größeren Dokumenten zeigt die Konsole den Fortschritt pro Batch, ohne
Dokumenttext oder Vektorwerte auszugeben.

Der reale Speicherdiagnosepfad verwendet nur ein temporäres Testdokument und
eine temporäre Datenbank:

```powershell
.venv\Scripts\python.exe -m diagnostics.embedding_store_ollama
```

## Hybride Suche

`memory/search.py` erzeugt für jede Anfrage lokal einen Vektor und vergleicht
ihn per Kosinus-Ähnlichkeit mit allen aktuellen Dokumentabschnitten der aktiven
Modellversion. Semantische Treffer unterhalb des konfigurierten Mindestwerts
werden verworfen. Die bestehende lexikalische Rangfolge bleibt erhalten und
wird gewichtet mit den semantischen Treffern zusammengeführt.

Doppelte Treffer werden über die Chunk-ID vereinigt. Die kombinierte Bewertung,
danach semantische und lexikalische Teilbewertung sowie Quelle und
Abschnittsnummer ergeben eine stabile Sortierung. Schlägt der lokale
Embedding-Dienst fehl, liefert dieselbe Schnittstelle automatisch ausschließlich
die lexikalischen Ergebnisse.

Der reale Diagnosepfad arbeitet mit temporären Dokumenten und SQLite-Daten:

```powershell
.venv\Scripts\python.exe -m diagnostics.hybrid_search_ollama
```

Direkte Fragen, echte Paraphrasen, irrelevante Zusätze und Falschtreffer werden
separat unter [Evaluation semantischer Paraphrasen](paraphrase-evaluation.md)
dokumentiert.
