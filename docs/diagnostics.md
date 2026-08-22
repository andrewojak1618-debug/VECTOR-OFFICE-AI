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

## Provider-Status sicher prüfen

Der argumentlose Diagnosebefehl prüft Vector SDK, WirePod und Ollama über
begrenzte, ausschließlich lesende Verfügbarkeitszugriffe:

```powershell
.venv\Scripts\python.exe -m diagnostics.provider_status
```

Die passive Vector-Prüfung fordert keine Verhaltenskontrolle an und startet
weder Bewegung, Animation noch Sprache. Jede lokale Prüfung besitzt zusätzlich
eine äußere Frist von sechs Sekunden. Interne Transportfehler werden verworfen
und nicht in die Terminalausgabe übernommen.

OpenAI und ElevenLabs werden bewusst nur anhand ihrer lokalen Freigabe und der
Vollständigkeit erforderlicher Konfigurationsfelder bewertet. Der Befehl sendet
keine kostenpflichtige OpenAI-Anfrage, erzeugt keine ElevenLabs-Sprache und gibt
keinen Schlüssel, keine Stimmenkennung, keine Seriennummer und keinen Endpunkt
aus. Vollständig konfigurierte, aber nicht live geprüfte Cloud-Provider werden
deshalb transparent als `degraded` gemeldet. Nicht gewählte optionale Provider
erscheinen als `disabled`.

Der Prozess liefert Statuscode `0`, wenn alle benötigten Dienste mindestens
kontrolliert verfügbar oder konfiguriert sind. Ein benötigter Zustand
`unavailable` führt zu Statuscode `1`.
