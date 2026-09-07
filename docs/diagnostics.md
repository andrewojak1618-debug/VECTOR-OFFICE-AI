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

Provideraufrufe verwenden eine zusätzliche enge Schnittstelle. Sie nimmt nur
Providername, Laufzeit in Millisekunden, einen festen Fehlercode und bei einem
Rückfall den Namen des Ersatzproviders an. Freie Fehlertexte und Nutzdaten sind
an dieser Grenze nicht vorgesehen.

| Ereignis | Bedeutung | Sichere Zusatzdaten |
| --- | --- | --- |
| `provider.started` | ein begrenzter Provideraufruf beginnt | Providername |
| `provider.finished` | der Aufruf wurde erfolgreich beendet | Providername, Dauer |
| `provider.timeout` | die konfigurierte Frist ist abgelaufen | Providername, Dauer, Fehlercode |
| `provider.error` | der Provideraufruf ist kontrolliert fehlgeschlagen | Providername, Dauer, Fehlercode |
| `provider.fallback` | ein freigegebener Ersatzprovider übernimmt | Providername, Ersatzprovider, Fehlercode |
| `provider.recovered` | der zuvor ausgefallene Provider ist wieder nutzbar | Providername, optionaler Ersatzprovider |

Die Dauer wird mit einer monotonen lokalen Uhr gemessen. Zulässige Fehlercodes
sind feste Klassen wie `request-timeout`, `provider-unavailable`,
`invalid-response`, `primary-unavailable` und `health-check-failed`. Fragen,
Antworten, Sprachtexte, Erinnerungen, Dokumentabschnitte, Embeddings und Secrets
werden weder in Erfolgs- noch in Fehlerereignisse übernommen.

## Antwortlatenz und TTS-Übergänge

`diagnostics/response_latency.py` und
`application/controlled_turn_delivery.py` erfassen die wahrnehmbare
Antwortkette unabhängig vom gewählten Dialogpfad. Die Messung verwendet nur
eine monotone Uhr, feste Ereigniscodes, Millisekunden und den Zustand `active`,
`success` oder `failed`.

| Ereignis | Gemessene Grenze |
| --- | --- |
| `response.started` | Beginn der lokalen Turnverarbeitung |
| `response.prepared` | Antworttext und gegebenenfalls Audio sind vorbereitet |
| `response.tts.started` | Übergang zur tatsächlichen Wiedergabe |
| `response.tts.finished` | Ende oder Fehler der Wiedergabe |
| `response.finished` | vollständige Dauer des Antwortturns |

Frage, Antwort, Transkript, Dokumentinhalt, Audiopfad, Providertext und Secrets
sind keine Parameter dieser Schnittstelle. Providerwechsel bleiben getrennte
Ereignisse; dadurch lassen sich Modellzeit, TTS-Vorbereitung und Wiedergabe
zeitlich vergleichen, ohne Gesprächsinhalte miteinander zu verknüpfen.

Der argumentlose Bericht `diagnostics/response_latency_report.py` liest nur die
letzten validierten Messwerte aus der begrenzten lokalen Diagnoseablage:

```powershell
.venv\Scripts\python.exe -m diagnostics.response_latency_report
```

Er zeigt Vorbereitung, Zeit bis zum Wiedergabestart, TTS-Wiedergabe und gesamte
Turnzeit in Millisekunden. Fremde Komponenten, unbekannte Codes, zusätzliche
Inhaltsfelder und ungültige Werte werden nicht in die Ausgabe übernommen.

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

Die Integration erfasst Anwendungsstart und -ende, Ollama- und
WirePod-Verfügbarkeit, Vector-SDK-Zugriff, Betriebsmodus sowie die begrenzten
Lebenszyklen von OpenAI, Ollama und ElevenLabs einschließlich Rückfall und
Wiederherstellung.

## Provider-Status sicher prüfen

Der argumentlose Diagnosebefehl prüft Vector SDK, WirePods tatsächlichen
SDK-Lesezugriff und Ollama über begrenzte, ausschließlich lesende Zugriffe:

```powershell
.venv\Scripts\python.exe -m diagnostics.provider_status
```

Die passive Vector-Prüfung fordert keine Verhaltenskontrolle an und startet
weder Bewegung, Animation noch Sprache. Der WirePod-Check liest nur den lokalen
Batterieendpunkt und verwirft dessen Inhalt nach der Strukturprüfung. Ein
Authentifizierungsfehler erscheint ausschließlich als nicht verfügbar; der
Diagnosebefehl startet keine automatische Reparatur. Jede lokale Prüfung besitzt
eine äußere Frist von 22 Sekunden, der direkte Vector-SDK-Test davon intern fünf
Sekunden. Interne Transportfehler werden verworfen und nicht in die
Terminalausgabe übernommen.

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

## Begrenzter lokaler Stabilitätslauf

Karte 49 ergänzt denselben passiven lokalen Prüfpfad um wiederholte Messungen:

```powershell
.venv\Scripts\python.exe -m diagnostics.stability_run `
  --samples 10 `
  --interval-seconds 30
```

Geprüft werden ausschließlich Vector SDK ohne BehaviorControl, WirePods lokaler
SDK-Lesezugriff und Ollama. OpenAI und ElevenLabs werden weder angesprochen noch
als Laufzeitmessung ausgegeben. Die Grenzen erlauben 1 bis 120 Messungen, 1 bis
60 Sekunden Abstand und höchstens eine Stunde theoretische Gesamtdauer. Nach der
letzten Messung wird nicht mehr gewartet.

Die Terminalausgabe und der feste lokale Bericht
`data/acceptance/stability.json` enthalten pro Provider ausschließlich:

- Anzahl verfügbarer Messungen,
- Anzahl nicht verfügbarer Messungen,
- Anzahl der Zustandswechsel,
- längste zusammenhängende Ausfallserie.

Zusätzlich werden Messanzahl, Intervall, technische Gesamtdauer und das feste
Ergebnis `bestanden` oder `auffällig` gespeichert. Zeitpunkte, Fragen,
Antworten, Audio, Dokumente, Speicherinhalte, Endpunkte, Prozess-IDs,
Seriennummern, Schlüssel und interne Fehlertexte sind ausgeschlossen. Ein
unerwarteter Prüffehler zählt sicher als nicht verfügbar. Der Bericht liegt
unter `data/` und bleibt dadurch außerhalb von Git.
