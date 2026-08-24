# Spracheingabe und Sprachausgabe

## Eingabe über WirePod

Der `WirePodTranscriptListener` liest neue Einträge aus WirePods lokaler
`/api/get_logs`-Schnittstelle. Er extrahiert Zeitstempel, Intent, Text und
Geräte-ID und verarbeitet jeden Eintrag nur einmal.

Zusätzlich unterdrückt der Listener denselben normalisierten Text desselben
Geräts innerhalb eines festen Fensters von drei Sekunden, selbst wenn WirePod
ihn mit einem neuen Zeitstempel protokolliert. Nach Ablauf des Fensters ist eine
bewusste Wiederholung wieder zulässig; identischer Text eines anderen Geräts
bleibt ebenfalls gültig. Die erste Äußerung wird ohne Verzögerung ausgegeben,
sodass Exit-, Notfall- und Bestätigungssignale sofort verarbeitet werden.

Für beide lokalen Wiedererkennungslisten werden nur SHA-256-Fingerabdrücke
aufbewahrt. Transkripttexte werden durch diesen Schutz weder protokolliert noch
dauerhaft gespeichert. Die Liste ist zusätzlich auf 50 jüngste Textmuster
begrenzt und endet mit dem Prozess.

Leere `intent_system_noaudio`-Ereignisse zählen nicht als Spracheingabe. Damit
wartet die Anwendung nach einem fehlgeschlagenen Aufnahmeversuch auf den
nächsten tatsächlichen Text.

Temporäre Fehler des lokalen WirePod-Endpunkts beenden den Dialog nicht mehr
sofort. Initialisierung und laufende Erkennung werden bis zu fünfmal mit der
begrenzten Staffel 1, 2, 5 und 10 Sekunden erneut versucht. Erst fünf
aufeinanderfolgende Fehler beenden die Sitzung kontrolliert. Die Fehlermeldung übernimmt dabei weder interne
HTTP-Fehlerdetails noch zusätzliche Transkriptinhalte.

## Wakeword-Annahme

„Hey Vector“ wird bereits in Vectors Firmware erkannt. Erst nach erfolgreicher
Aktivierung sendet der Roboter Audio an WirePod; Python-Polling,
`VOICE_LISTEN_TIMEOUT` und eine nachträgliche Verstärkung können daher keine
vollständig überhörten Wakewords retten. Die lokale WirePod-Version bietet
keinen freigegebenen Regler für Mikrofonverstärkung oder Wakeword-Schwelle.

Vector und Vosk sind für den deutschen Betrieb beide auf `de-DE` eingestellt.
Vectors interne Lautstärke steht testweise auf `Mute`; der unabhängige externe
ElevenLabs-Audiostream bleibt trotzdem hörbar. Die Rückentaste ist weiterhin
als alternative Wakeword-Aktivierung konfiguriert.

Der physische Vergleich am 19. August 2026 zeigte bei einem bewegten Vector nur
eine von fünf Aktivierungen beim ersten Ruf. Ruhig auf der Ladestation wurden
fünf von fünf Versuchen sofort erkannt, einschließlich eines vollständigen
Dialogs aus ungefähr 90 Zentimetern Entfernung. Lautsprechertöne sind damit
nicht die einzige Störquelle: mechanische Kopf-, Lift- und Radgeräusche können
weiterhin direkt in das Mikrofonarray einkoppeln.

## Abbruchsignale

Groß- und Kleinschreibung, mehrfache Leerzeichen sowie abschließende
Satzzeichen werden bei eindeutigen Sitzungsbefehlen vereinheitlicht. Unter
anderem beenden `Vector beenden`, `Vektor bitte beenden`, `Gespräch beenden`
und `Gespräch abbrechen` die Voice-Sitzung. Ein einzelnes `Abbrechen` bleibt
bewusst der Ablehnung einer offenen Werkzeug- oder Ausdrucksbestätigung
vorbehalten und beendet nicht versehentlich das gesamte Gespräch.

`Ctrl+C` wird während der gesamten Voice-Verarbeitung einschließlich
Initialisierung, Zuhören und Antwortausgabe sauber behandelt. Bei jedem
Sitzungsende wird eine noch nicht bestätigte
Ausdrucksantwort verworfen und der vorherige Gesprächskontext wiederhergestellt.

## Eingabemodi

```env
INPUT_MODE=console
```

oder:

```env
INPUT_MODE=wirepod
VOICE_LISTEN_TIMEOUT=120
VOICE_ALLOW_CLOUD=false
```

`VOICE_ALLOW_CLOUD=false` hält Transkript, Erinnerungen und Antwortgenerierung
im Voice-Modus lokal bei Ollama.

Die Variable kontrolliert nur die Anwendung und kann einen unabhängig
aktivierten WirePod Knowledge Graph nicht abschalten. Der physische
Mehrturntest am 17. August 2026 zeigte, dass WirePod denselben unbekannten Turn
parallel an seinen eigenen OpenAI-Provider weitergab und mit einer zweiten
Stimme beantwortete. Für den lokalen Einzelstimmenbetrieb wurden deshalb in
WirePod `Enable intent-graph` und
`Enable conversations via "I have a question"` deaktiviert. Der anschließende
physische Test lieferte das Transkript weiterhin an die Anwendung, ohne die
englisch klingende Zweitstimme auszugeben.

Im selben Test wurden die tatsächlichen Vosk-Varianten `hebe deine Lift`,
`Abbruch` und `bitte beenden` beobachtet. Sie sind eng begrenzt in den
bestehenden Werkzeug-, Bestätigungs- und Sitzungs-Allowlists ergänzt; eine
allgemeine unscharfe Aktionsauswahl bleibt weiterhin ausgeschlossen.

## Deutsche TTS

Die Sprachpipeline besteht aus:

1. Windows OneCore Speech Synthesis mit „Microsoft Stefan“
2. FFmpeg-Kompression und Loudness-Normalisierung
3. Umwandlung in 16-kHz-, 16-Bit-, Mono-PCM-WAV
4. Wiedergabe über `robot.audio.stream_wav_file`

Die unveränderliche OneCore-PowerShell-Vorlage liegt getrennt in
`vector/onecore_tts.py`. Synthese, SSML-Auswahl, FFmpeg-Aufbereitung und
WAV-Prüfung bleiben in `vector/speech.py`; der bisherige Import der Vorlage
über dieses Modul bleibt kompatibel.

Der physische Vector wurde mit `TTS_VOLUME=90` und hohem Master-Volume getestet.
Neutrale Antworten werden um acht Prozent beschleunigt. Jeder Satz beginnt bei
unverändertem Tempo mit leicht erhöhter Lautstärke und Tonhöhe und endet mit
abgesenkter Tonhöhe sowie reduzierter Lautstärke. Der reflektierende Stil nutzt
dieselbe Satzkontur bei fünf Prozent Beschleunigung; die bestätigten Denkpausen
und der IPA-Summton bleiben dabei unverändert. Diese Kontur wurde am physischen
Vector hörgeprüft und vom Benutzer abgenommen.

## Optionale ElevenLabs-Ausgabe

`vector/elevenlabs_speech.py` kann die eigentliche Antwort mit einer bewusst
freigegebenen ElevenLabs-Stimme erzeugen. `vector/speech_factory.py` aktiviert
diesen Pfad nur, wenn `TTS_PROVIDER=elevenlabs`, `TTS_ALLOW_CLOUD=true`, ein
lokaler API-Key und eine Voice-ID vorhanden sind. Die zufällige hörbare
Überlegung bleibt immer bei Microsoft Stefan und benötigt keinen Cloudzugriff.

Die Cloud-Ausgabe wird ohne zusätzliche Sprachkompression normalisiert, damit
die Dynamik der erzeugten Stimme erhalten bleibt. FFmpeg wandelt sie danach in
das unveränderte Vector-Format mit 16 kHz, 16 Bit und Mono um. Nicht erreichbare
API, ungültige Antworten und Konvertierungsfehler führen automatisch zur
lokalen OneCore-Ausgabe derselben Antwort.

```env
TTS_PROVIDER=elevenlabs
TTS_ALLOW_CLOUD=true
ELEVENLABS_API_KEY=dein_lokaler_api_key
ELEVENLABS_VOICE_ID=rDmv3mOhK6TnhYWckFaD
ELEVENLABS_MODEL=eleven_flash_v2_5
ELEVENLABS_TIMEOUT=15
ELEVENLABS_STABILITY=0.45
ELEVENLABS_SIMILARITY=0.75
ELEVENLABS_STYLE=0.0
ELEVENLABS_SPEED=1.02
```

`TTS_ALLOW_CLOUD=false` ist die sichere Voreinstellung. Bei aktiver Freigabe
wird der vollständige zu sprechende Antworttext an ElevenLabs übertragen. Das
betrifft möglicherweise auch Informationen, die aus lokalem Memory oder einer
lokalen Dokumentbibliothek in die Antwort eingeflossen sind. Schlüssel,
Antworttexte und Audiodaten werden von der Anwendung nicht protokolliert oder
versioniert. Die Aufbewahrung beim Cloudanbieter richtet sich unabhängig davon
nach dem dort verwendeten Konto und Tarif.

Der vollständige Pfad aus ElevenLabs Flash v2.5, FFmpeg-Konvertierung,
Vector-SDK und physischem Lautsprecher wurde mit „Felix Serenitas“ erfolgreich
abgespielt. Die API-Erzeugung des kurzen Prüfsatzes dauerte rund 1,03 Sekunden;
Stimme, Tempo und Wirkung wurden vom Benutzer als gewünschtes Sprachbild
bestätigt. Anschließend wurde die verborgene Windows-Autostart-Aufgabe neu
gestartet und mit genau je einer Watchdog-, Anwendungs- und WirePod-Instanz
abgenommen.

## Diagnose

```powershell
.venv\Scripts\python.exe -m voice.wirepod_input --timeout 60
```

Der Diagnosemodus gibt nur das nächste erkannte Transkript aus und startet
keine KI-Antwort.
