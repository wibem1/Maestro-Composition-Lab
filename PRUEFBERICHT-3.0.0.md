# Prüfbericht 3.0.0 — 20. Oktober 2026

Geprüfter Programmstand: `a191b79f5e46d368ab5ada2437a6b5336bb82f33`.
[GitHub-Actions-Lauf](https://github.com/wibem1/Maestro-Composition-Lab/actions/runs/39371891046).

## Ergebnis

| Prüfung | Ergebnis |
|---|---|
| Linux: Engine inklusive echter Lua-5.4-Schreibsimulation | 113 Tests bestanden, keine übersprungen |
| Anbieter-/MCP-/HTTP-Selbsttests | 14 Tests bestanden |
| Mac-Hosttests | 11 Tests bestanden, auch auf beiden nativen Mac-Runnern |
| Windows- und Mac-Oberflächen | Beide JS-Ablaufsimulationen bestanden |
| Windows x64 | Native .NET-Kompilierung, C#-Backendtest und Selbsttest der paketierten EXE erfolgreich |
| Mac Intel und Apple Silicon | Pakete erstellt; jeweils 163 native Binärdateien auf passende Architektur geprüft; Laufzeit-/Framework-/Backend-Selbsttests erfolgreich |
| Referenzdateien | Unverändert; ursprüngliches ZIP im Referenzbranch rekonstruiert |

Auf Windows und Mac wurden im Engine-Testlauf jeweils 77 Lua-abhängige Tests wegen fehlender Lua-Systembibliothek übersprungen. Sie wurden im vorgeschalteten Linux-Job vollständig ausgeführt. Das ist keine native Maestro-Integration.

## Nachgewiesene Fehler und Korrekturen

1. Windows zeigte Warnungen der gemeinsam genutzten Antwortkorrektur nicht an. Anzeige an Mac angeglichen, ohne Windows-Layout zu ersetzen.
2. Alte Versionsnummern in HTML-Oberflächen, Windows-Assembly und Host-/Pakettests auf 3.0.0 vereinheitlicht.
3. UI-Test prüfte eine nicht mehr ausgelieferte Einstiegseite. Er prüft jetzt getrennt ui/windows.html und ui/mac.html.
4. Mac-Hosttests verwiesen nach Zusammenführung auf den falschen Engine-Ordner. Pfade korrigiert.
5. Mac-Build benötigte fehlendes Icon und fehlende Begleitdateien. Vorhandenes Icon verwendet, Dokumentation ergänzt und fertiges Bundle für native Tests aufbewahrt.
6. Windows-Paketierungsroutine fehlte. Native Kompilierung, mitgelieferte Python-Laufzeit, Hashliste und Paket-Selbsttest ergänzt.
7. Vorhandene DPAPI-Unit-Tests waren nicht vom macOS-Schlüsselbundzweig isoliert. Adaptertests getrennt; eigene Mac-Keychain-Tests erhalten.
8. Neuer UI-Vergleichstest las UTF-8 unter Windows zunächst mit der Systemkodierung. Explizite UTF-8-Dekodierung ergänzt.

## Architektur und Datenflüsse

Siehe [ARCHITEKTUR.md](ARCHITEKTUR.md). Die musikalischen Validatoren, Partitur-Snapshots, kontrollierten Lua-Schreiber und Schutzregeln wurden nicht durch neue Implementierungen ersetzt. Die Hosts bleiben getrennt; dieselben Engine-Dateien werden in alle Pakete übernommen.

## Freigabegrenzen

Die Pakete sind installierbare **Prüffassungen** mit interner Version 3.0.0, kein abschließend freigegebenes stabiles Release.

Noch offen: echter Maestro-Lese-/Schreibtest auf beiden Plattformen, visuelle Kontrolle und Bedienung der nativen Fenster, reale Anbieteranfragen und realer Schlüsselbund-/DPAPI-Speicherzyklus. Die automatisierten Schlüsseltests verwenden Adapter-Simulationen. Ein erfolgreicher Backend-Selbsttest beweist nicht den vollständigen GUI-Ablauf.

Keine Entwicklerzertifikat-Signierung oder Apple-Notarisierung. Windows benötigt .NET Framework 4.8 und WebView2. Vor Praxistests wichtige Partituren in Maestro sichern. Bestehende Referenzversionen und die ursprüngliche Quellbasis wurden nicht überschrieben.
