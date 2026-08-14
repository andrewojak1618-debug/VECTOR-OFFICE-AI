# Evaluation semantischer Paraphrasen

Die Evaluation prüft, ob `embeddinggemma` denselben eindeutigen Fakt trotz
abweichender Formulierung zuverlässig als besten Dokumentabschnitt findet. Alle
realen Läufe verwenden temporäre Dokumente und eine temporäre SQLite-Datenbank.
Weder Fragen noch Dokumenttexte oder Vektorwerte werden protokolliert.

## Testwissen

Das Testdokument enthält drei bewusst unterscheidbare Abschnitte:

1. Lage einer Notabschaltung im Serverraum,
2. Lage eines ähnlichen Hauptschalters in einer Werkstatt,
3. Zeitpunkt einer regelmäßigen Datensicherung.

Damit lassen sich ein eindeutiger Fakt, ein thematisch ähnlicher Abschnitt und
ein fachlicher Ablenker getrennt bewerten. Quelle und Abschnittsnummer bleiben
in jedem Suchergebnis erhalten.

## Reales Ergebnis mit Ollama

Getestet wurde lokal mit `embeddinggemma` und dem produktiven
Mindestähnlichkeitswert `0,35`.

| Fall | Erwartung | Ergebnis |
|---|---|---|
| Direkte Frage mit gleichen Begriffen | Serverraum-Abschnitt auf Rang 1 | bestanden |
| Sinngleiche Frage ohne lexikalischen Treffer | Serverraum-Abschnitt auf Rang 1 | bestanden |
| Paraphrase mit Wetter- und Kaffee-Zusatz | Serverraum-Abschnitt auf Rang 1 | bestanden |
| Ähnlicher Werkstatt-Abschnitt | hinter dem fachlich genaueren Treffer | bestanden |
| Fachfremde Kuchenfrage | kein Treffer | 0 Falschtreffer |

Der reale Lauf ist reproduzierbar über:

```powershell
.venv\Scripts\python.exe -m diagnostics.paraphrase_search_ollama
```

## Beobachtung zum Mindestwert

Ein probeweise strenger Wert von `0,50` entfernte die Paraphrase mit
irrelevanten Zusätzen vollständig. Das war ein dokumentierter False Negative:
Der richtige Abschnitt wurde nicht durch einen falschen verdrängt, sondern lag
unterhalb des zu hohen Grenzwerts.

Mit `0,35` bestanden alle drei relevanten Fragen, während die fachfremde Frage
weiterhin keinen Treffer erzeugte. Dieser kleine Testsatz begründet den aktuellen
Default, ersetzt aber keinen späteren größeren Qualitätsdatensatz. Neue
Dokumentarten und Sprachstile müssen gegen denselben Falschtreffer- und
False-Negative-Maßstab geprüft werden.

## Automatisierte Abdeckung

Die deterministische Suite verwendet kontrollierte Testvektoren und prüft:

- direkte und vollständig umformulierte Fragen,
- irrelevante Zusätze,
- Ranking ähnlicher Abschnitte,
- semantische Korrektur eines lexikalischen Rangs,
- Mindestähnlichkeit und dokumentierte Falschtrefferzahl,
- leere Bibliothek,
- nicht erreichbares Ollama mit lexikalischem Fallback.
