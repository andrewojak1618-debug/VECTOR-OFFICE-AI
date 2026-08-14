# Spracheingabe und Sprachausgabe

## Eingabe über WirePod

Der `WirePodTranscriptListener` liest neue Einträge aus WirePods lokaler
`/api/get_logs`-Schnittstelle. Er extrahiert Zeitstempel, Intent, Text und
Geräte-ID und verarbeitet jeden Eintrag nur einmal.

Leere `intent_system_noaudio`-Ereignisse zählen nicht als Spracheingabe. Damit
wartet die Anwendung nach einem fehlgeschlagenen Aufnahmeversuch auf den
nächsten tatsächlichen Text.

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

## Deutsche TTS

Die Sprachpipeline besteht aus:

1. Windows OneCore Speech Synthesis mit „Microsoft Stefan“
2. FFmpeg-Kompression und Loudness-Normalisierung
3. Umwandlung in 16-kHz-, 16-Bit-, Mono-PCM-WAV
4. Wiedergabe über `robot.audio.stream_wav_file`

Der physische Vector wurde mit `TTS_VOLUME=90` und hohem Master-Volume getestet.

## Diagnose

```powershell
.venv\Scripts\python.exe -m voice.wirepod_input --timeout 60
```

Der Diagnosemodus gibt nur das nächste erkannte Transkript aus und startet
keine KI-Antwort.
