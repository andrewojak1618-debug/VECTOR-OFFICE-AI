# Strukturierte Laufzeitdiagnose

Vector Office AI schreibt zusätzlich zu den lesbaren Konsolentexten lokale
JSONL-Ereignisse. Jede Zeile ist ein unabhängiges JSON-Objekt mit stabiler
Schema-Version, UTC-Zeit, Schweregrad, Komponente, Ereigniscode und geprüften
technischen Metadaten.

## Datenschutzgrenze

Die Schnittstelle akzeptiert ausschließlich eine feste Liste harmloser
Metadaten wie Provider, Betriebsmodus, Versuchszahl und Statuscode. Felder für
Transkripte, Prompts, Antworten, Dokumente, API-Schlüssel oder Vektoren werden
bereits vor dem Schreiben abgelehnt. Transportfehler erscheinen nur als feste
Ursachencodes; interne Fehlermeldungen werden nicht übernommen.

## Konfiguration

```env
DIAGNOSTICS_ENABLED=true
DIAGNOSTICS_PATH=data/diagnostics/events.jsonl
DIAGNOSTICS_MAX_BYTES=1000000
```

Der Standardpfad liegt unter dem von Git ignorierten Verzeichnis `data/`.
Erreicht die aktive Datei die konfigurierte Obergrenze, wird genau eine
Vorgängerversion als `events.jsonl.1` behalten. Ein Schreibfehler darf den
Roboterbetrieb nicht blockieren.

## Ereignisse ansehen

```powershell
Get-Content data\diagnostics\events.jsonl -Tail 20
```

Die erste Integration erfasst Anwendungsstart und -ende, Ollama- und
WirePod-Verfügbarkeit, Vector-SDK-Zugriff, Betriebsmodus, begrenzte
Ollama-Wiederholungen sowie einen aktivierten Provider-Fallback.
