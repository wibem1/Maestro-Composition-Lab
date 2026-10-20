Gemeinsame Engine, getrennte Mac- und Windows-Oberflächen. Interne Version 3.0.0.

Installationspakete: Mac Intel, Mac Apple Silicon und Windows x64. ZIP vollständig entpacken. Mac-App nach Programme kopieren; unter Windows die EXE im entpackten Ordner starten. Windows benötigt .NET Framework 4.8 und Microsoft WebView2 Runtime.

Die Veröffentlichung erfolgt nur nach erfolgreichen Linux-Kerntests und nativen Builds/Selbsttests für alle drei Ziele. Alle 113 Engine-Tests laufen einschließlich Lua-Simulation auf Linux. Auf nativen Runnern werden Tests ohne dort installierte Lua-Bibliothek als übersprungen ausgewiesen; das gemeinsame Lua-Verhalten ist im vorgeschalteten Linux-Job vollständig geprüft. Zusätzlich: Anbieter-/MCP-Tests, beide UI-Ablaufsimulationen, Mac-Hosttests und Windows-Hosttest.

Behoben: fehlende Windows-Hinweise zu KI-Strukturkorrekturen, falsche Versionsanzeigen, veraltete UI-Testziele, Mac-Testpfade und unvollständige Builddateien. Die ursprüngliche ZIP-Grundlage bleibt im Branch reference/v3.0-source-package erhalten.

Noch keine stabile Freigabe: Maestro-Praxistest, visuelle Kontrolle der nativen Fenster, reale KI-Anfragen und echter Schlüsselbund/DPAPI-Rundlauf stehen aus. Pakete sind nicht mit Entwicklerzertifikaten signiert/notarisiert. Keine neuen musikalischen Funktionen und keine Änderung der bewährten Schreibregeln.
