# Lokale Embedding-Architektur

Die semantische Grundlage ist providerunabhängig aufgebaut und verwendet
aktuell ausschließlich einen lokalen Ollama-Adapter. Einzeltexte und mehrere
Dokumentabschnitte können bereits real vektorisiert werden. Die Vektoren werden
noch nicht in SQLite gespeichert; die produktive Suche bleibt daher zunächst
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

## Nächster Integrationsschritt

Als nächste Karte können Vektoren gemeinsam mit Erinnerungen und
Dokumentabschnitten in SQLite gespeichert werden. Erst danach sollte die
lexikalische Suche durch eine kontrollierte hybride Suche aus Texttreffern und
semantischer Ähnlichkeit ergänzt werden.
