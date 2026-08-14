# Lokale Embedding-Architektur

Die erste semantische Grundlage ist providerunabhängig aufgebaut und verwendet
aktuell ausschließlich einen lokalen Ollama-Adapter. Erinnerungen und
Dokumentabschnitte werden in dieser Phase noch nicht automatisch vektorisiert;
die bestehende lexikalische Suche bleibt deshalb unverändert aktiv.

## Bausteine

| Baustein | Verantwortung |
|---|---|
| `EmbeddingText` | normalisierte, nicht leere Texteingabe |
| `EmbeddingVector` | unveränderlicher, endlicher Zahlenvektor |
| `EmbeddingResult` | Text, Vektor, tatsächliches Modell und Dimension |
| `EmbeddingProvider` | providerunabhängiger Vertrag für eine Vektorerzeugung |
| `OllamaEmbeddingProvider` | lokaler Adapter für `POST /api/embed` |

Ollama erhält genau einen Text pro Aufruf. `truncate=false` verhindert eine
unbemerkte Kürzung langer Inhalte. Modellname und tatsächliche Vektordimension
werden aus der Antwort übernommen. Eine konfigurierte Dimension wird zusätzlich
gegen das Ergebnis geprüft.

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

## Fehlergrenzen

Transport- und HTTP-Fehler werden als verständlicher `EmbeddingError`
weitergegeben, ohne interne Verbindungsdetails offenzulegen. Ungültige,
mehrdeutige oder dimensionsfalsche Antworten werden abgelehnt.

## Nächster Integrationsschritt

Als nächste Karte können Vektoren gemeinsam mit Erinnerungen und
Dokumentabschnitten in SQLite gespeichert werden. Erst danach sollte die
lexikalische Suche durch eine kontrollierte hybride Suche aus Texttreffern und
semantischer Ähnlichkeit ergänzt werden.
