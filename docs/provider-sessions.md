# Providerwechsel in längeren Sitzungen

Der `FallbackProvider` entscheidet bei jeder Gesprächsrunde neu. Der
konfigurierte Primäranbieter wird zuerst angesprochen; nur bei einem Fehler oder
einer leeren Antwort übernimmt der lokale Ollama-Fallback diese Runde. In der
nächsten Runde wird der Primäranbieter erneut geprüft, sodass eine vorübergehende
Störung keinen dauerhaften Providerwechsel auslöst.

## Gemeinsamer Kontext

Der `Agent` verwaltet genau einen providerunabhängigen Gesprächsverlauf. Eine
vom Fallback erzeugte und validierte Antwort wird deshalb in der nächsten Runde
auch dem wieder verfügbaren Primäranbieter übergeben. Persönlichkeit,
bestätigtes Memory und freigegebener Dokumentkontext werden für beide Anbieter
nach denselben Regeln aufgebaut.

Wenn Primäranbieter und Fallback beide scheitern, wird die unbeantwortete
Benutzerrunde auf den letzten vollständigen Kontextstand zurückgesetzt. Damit
entstehen keine verwaisten Benutzertexte, die eine spätere Antwort verfälschen.

## Wiederholbarer Test

```powershell
.venv\Scripts\python.exe -m unittest tests.test_provider_sessions -v
```

Der Test simuliert ohne Netzwerk- oder API-Kosten die Folge
`OpenAI → Ollama → OpenAI`, prüft die Kontextübergabe und erzwingt zusätzlich
einen vollständigen Ausfall beider Anbieter. Die strukturierte Diagnose enthält
nur den Fallback-Ereigniscode und niemals Gesprächsinhalte.
