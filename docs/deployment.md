# Homeserver- und Docker-Grenzen

Diese Seite beschreibt eine mögliche spätere Verteilung des Vector Office AI
Core. Sie ist eine Planungsgrundlage und führt weder Docker noch eine Server-API
produktiv ein. Das bestätigte Windows-, WirePod- und Vector-System bleibt bis zu
einer eigenen Migrationskarte unverändert.

## Aktueller gebundener Betrieb

Heute läuft die Anwendung als zusammenhängendes System auf dem Windows-Rechner.
Der Rechner erreicht WirePod, Ollama und Vector über lokale beziehungsweise
private Netzverbindungen und besitzt die benutzergebundene SDK-Konfiguration.

| Komponente | Aktuelle Bindung | Begründung |
|---|---|---|
| Windows OneCore TTS | Windows-Host | Microsoft Stefan und die SSML-Erzeugung verwenden Windows-Sprachkomponenten. |
| FFmpeg-Audioaufbereitung | Windows-Host | Der aktuelle TTS-Pfad erzeugt dort die an Vector übertragene WAV-Datei. |
| Vector SDK | Windows-Host | Der SDK-Prozess benötigt den Roboter im lokalen Netz, die Seriennummer und die lokale Zertifikatskonfiguration. |
| Vector-Aktionen und Audioübertragung | Windows-Host | Diese Grenze steuert unmittelbar physische Hardware und bleibt unter `BehaviorControl`. |
| WirePod | Windows-Host | Der Watchdog kennt derzeit den festen Windows-Prozess `chipper.exe` und dessen lokalen HTTP-Endpunkt. |
| Windows-Autostart und Watchdog | Windows-Host | Aufgabenplanung, PowerShell, WScript und Prozessprüfung sind absichtlich Windows-spezifisch. |
| Ollama | Windows-Host | Der aktuelle Endpunkt ist `http://127.0.0.1:11434`; Start und Modellvorwärmung erwarten einen lokalen Dienst. |
| SQLite und lokale Exporte | Projekt-Host | Alle schreibenden Prozesse greifen derzeit auf die lokale Projektablage zu. |

Diese Komponenten werden nicht allein deshalb containerisiert, weil ihre
Programmlogik teilweise plattformneutral ist. Die bestätigten Audio-,
Verbindungs- und Sicherheitsgrenzen haben Vorrang vor einem frühen Umbau.

## Vector SDK und Zertifikate

`vector/sdk_client.py` bildet die kontrollierte Grenze zu Vector. Der installierte
SDK-Client löst die benutzerbezogene Roboterkonfiguration auf dem Host auf. Dazu
gehören insbesondere:

- `VECTOR_SERIAL` aus der lokalen `.env`,
- Zertifikate und Tokens unter `%USERPROFILE%\.anki_vector\`,
- die lokale SDK-Konfiguration einschließlich `sdk_config.ini`,
- die Erreichbarkeit des physischen Roboters im privaten Netz.

Diese Dateien sind Secrets. Sie werden weder in Git noch in ein zukünftiges
Container-Image kopiert. Sollte die SDK-Grenze später überhaupt in einen
Container wechseln, dürfen Zertifikate erst nach einer gesonderten
Sicherheitsprüfung als schreibgeschütztes Laufzeit-Secret eingebunden werden.
Bis dahin bleiben SDK, TTS und Robot-Aktionen gemeinsam auf Windows.

## WirePod-Grenze

WirePod stellt heute Wakeword-, Transkriptions- und lokale Robot-Dienste bereit.
`WIREPOD_HOST` zeigt standardmäßig auf `http://127.0.0.1:8080`. Der bestehende
Host-Watchdog kann zusätzlich genau den konfigurierten Windows-Pfad
`C:\Program Files\wire-pod\chipper\chipper.exe` starten.

Ein Homeserver darf später einen erreichbaren WirePod-Dienst nutzen, aber die
aktuelle Prozesssteuerung ist nicht auf einen entfernten Dienst übertragbar.
Dafür wären getrennte Healthchecks, Authentisierung, Netzfreigaben und eine
eindeutige Verantwortung für Start und Wiederherstellung notwendig. Bis diese
Grenze implementiert und physisch geprüft ist, bleibt WirePod lokal auf dem
Windows-Host.

## Lokale Daten und Speicherorte

Die Standardablage liegt unterhalb des ignorierten Projektordners `data/`:

| Pfad | Inhalt | Spätere Persistenz |
|---|---|---|
| `data/vector_memory.db` | bestätigte Erinnerungen, Dokumentabschnitte, Versionen, Embeddings und Tool-Audits | eigenes persistentes Volume, genau ein schreibender Core |
| `data/diagnostics/events.jsonl` | rotierende, inhaltsfreie Diagnoseereignisse | optionales separates Diagnose-Volume |
| `data/exports/` | bewusst erzeugte Memory- und Bibliotheksmetadatenexporte | verschlüsselte Sicherungsablage, nicht ins Image |
| `data/acceptance/` | lokale Abnahmeberichte ohne Prozessinhalte | kurzlebige oder getrennt archivierte Ablage |
| `data/startup/` | Windows-Dateisperren und Startstatus | bleibt Host-Laufzeitdaten, nicht migrieren |

`MEMORY_DB_PATH` ist standardmäßig `data/vector_memory.db` und kann später auf
einen eingehängten Datenpfad zeigen. Eine SQLite-Datei darf nicht gleichzeitig
von Windows und einem Container oder über eine ungesicherte Netzfreigabe
beschrieben werden. Für die erste Migration gilt deshalb: Anwendung stoppen,
konsistente Sicherung erstellen, Datei auf den neuen Datenträger kopieren und
erst dort wieder mit genau einem schreibenden Core öffnen.

Die bewusst importierten Originaldokumente bleiben eine eigene Sicherungsquelle.
Sie gehören ebenso wenig in das Container-Image wie Datenbank, Exporte oder
Embeddings.

## Ollama auf Laufwerk F

Der aktuelle Rechner verwendet für Ollama den vorgesehenen Modellspeicher:

```text
OLLAMA_MODELS=F:\Ollama\models
```

`OLLAMA_MODELS` ist eine Umgebungsvariable des Ollama-Hostprozesses und keine
Einstellung des Python-Projekts. Sie muss deshalb für genau das Benutzer- oder
Dienstkonto gelten, das Ollama startet. Nach einem Neustart wird der aktive
Speicherort mit `ollama list` und einem lokalen Modelltest geprüft.

Bei einer späteren Homeservermigration wird dieses Verzeichnis nicht als
Windows-Laufwerk in ein Image eingebaut. Modelle liegen dann in einem eigenen
persistenten Ollama-Volume oder werden anhand einer dokumentierten Modellliste
neu geladen. Das Volume ersetzt weder das Backup der SQLite-Datenbank noch die
Sicherung der Originaldokumente.

## Mögliche spätere Verteilung

| Ziel | Später geeignete Bestandteile | Bleibt zunächst ausgeschlossen |
|---|---|---|
| Windows-Edge-Host | OneCore-TTS, FFmpeg-Ausgabe, Vector SDK, Zertifikate, WirePod, Wakeword, Robot-Aktionen und Windows-Watchdog | kein ungeprüfter Fernzugriff auf Motoren oder Audio |
| Privater Homeserver | providerunabhängiger Brain-Core, Response-Qualität, Memory, Dokumentbibliothek, Embeddings, Tool Registry, Diagnosen und Ollama | keine automatische Übernahme von Windows-Prozesssteuerung oder Zertifikaten |
| Externe Cloud | OpenAI und ElevenLabs über ihre bestehenden, ausdrücklich freigegebenen Provideradapter | keine Datenbank, Embeddings, Zertifikate oder unselektierte Dokumentbibliothek |

Der hardwareunabhängige Core ist damit eine spätere Option, keine bereits
vollzogene Trennung. Vor einer Verteilung benötigt er eine kleine, typisierte
Schnittstelle zwischen Core und Windows-Edge. Tool-Berechtigungen,
`BehaviorControl`, Timeouts und Antwortvalidierung bleiben auch über diese
Grenze verbindlich. Verändernde oder physische Aktionen dürfen bei
Verbindungsfehlern niemals automatisch wiederholt werden.

## Sichere zukünftige API-Grenze

Eine mögliche Core-API bindet standardmäßig ausschließlich an `127.0.0.1`.
Sie wird weder im aktuellen Projekt eingeführt noch automatisch im LAN oder
Internet veröffentlicht. Ein Zugriff von einem zweiten Rechner erfordert
später eine ausdrückliche Konfiguration mit Authentisierung, TLS oder einem
privaten VPN, Firewall-Regeln, begrenzten Anfragegrößen und protokollfreien
Inhaltsgrenzen.

OpenAI- und ElevenLabs-Schlüssel werden einer Serveranwendung ausschließlich
zur Laufzeit über einen Secret-Store oder eine nicht versionierte Umgebung
bereitgestellt. Sie erscheinen nicht in Image-Layern, Build-Argumenten,
Compose-Dateien, Diagnoseberichten oder Backups normaler Projektdaten.

## Docker ist noch keine Produktivkomponente

Für diese Phase werden bewusst kein `Dockerfile`, keine Compose-Datei und kein
Container-Autostart angelegt. Eine spätere Docker-Karte muss mindestens:

1. den hardwareunabhängigen Prozess eindeutig vom Windows-Edge trennen,
2. lokale Tests ohne Netzwerk- oder Hardwarezugriff im Image ausführen,
3. einen nicht privilegierten Laufzeitbenutzer verwenden,
4. Secrets nur zur Laufzeit einbinden,
5. SQLite, Diagnosen und Ollama-Modelle als getrennte persistente Volumes planen,
6. Healthchecks ohne Benutzerinhalte oder kostenpflichtige Provideranfragen nutzen,
7. die API standardmäßig auf `127.0.0.1` begrenzen,
8. Rückbau und Wiederherstellung vor dem ersten Produktivbetrieb testen.

Erst nach einem reproduzierbaren Testaufbau und einer getrennten physischen
Vector-Abnahme kann entschieden werden, ob Docker gegenüber einem normalen
Homeserver-Dienst tatsächlich einen Vorteil bietet.

## Backup und Wiederherstellung

Vor jeder Server- oder Containerumstellung werden getrennt gesichert:

- die bei beendeter Anwendung kopierte SQLite-Datei aus `MEMORY_DB_PATH`,
- die bewusst importierten Originaldokumente,
- die verschlüsselte `.env` beziehungsweise ihre Secret-Store-Einträge,
- die Vector-SDK-Konfiguration und Zertifikate in einem separaten
  verschlüsselten Backup,
- eine Liste der Ollama-Modelle und ihrer Versionen,
- die für den Betrieb verwendete Projektversion beziehungsweise der Git-Tag.

Die Wiederherstellung wird zuerst ohne Vector-Aktion geprüft: Datenbank öffnen,
Dokumentübersicht kontrollieren, fehlende Embeddings lokal reindexieren und
Providerstatus ausführen. Live-Provider und der physische Vector folgen erst
nach der vollständigen lokalen Abnahme und der ausdrücklichen Bestätigung des
Nutzers. Die detaillierte SQLite-Strategie bleibt unter
[`docs/maintenance.md`](maintenance.md) verbindlich.
