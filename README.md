# Maestro Composition Lab 3.0.0

Gemeinsame Engine, getrennte Mac- und Windows-Oberflächen. Native Hosts: AppKit/WKWebView und WinForms/WebView2.

**Prüfkandidat, noch kein vollständig freigegebenes stabiles Release.** Installierbare ZIP-Pakete werden nach erfolgreichen nativen Tests in [GitHub Actions](https://github.com/wibem1/Maestro-Composition-Lab/actions) bereitgestellt. Echte Maestro-Praxistests stehen aus.

- [Architektur und Funktionsgleichheit](ARCHITEKTUR.md)
- [Teststand und Einschränkungen](TESTSTAND.txt)
- [Installation](LIESMICH.txt)
- [Änderungen](VERSIONS.md)

Die unveränderte ZIP-Grundlage ist im Branch `reference/v3.0-source-package` erhalten. Archivierte Integrationsdateien werden nicht ausgeliefert.

Lokal prüfen:
```sh
python -m unittest discover -s engine -p 'test_*.py'
python engine/selftest.py
python -m unittest discover -s macos/mac_tests
node engine/ui_selftest.js windows
node engine/ui_selftest.js mac
```
Lua-5.4-Systembibliothek für Schreibsimulationen erforderlich. Native Pakete werden ausschließlich auf dem jeweiligen Betriebssystem getestet.
