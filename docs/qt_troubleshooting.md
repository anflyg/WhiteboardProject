# macOS Qt startproblem – snabbguide

Så här är projektet upplagt nu för att Qt ska hitta cocoa-plugin:

- `run.sh` kopierar Qt platform-plugins från `.venv/.../PySide6/Qt/plugins/platforms/` till `tmp_qt_plugins/platforms/` och pekar `QT_PLUGIN_PATH`/`QT_QPA_PLATFORM_PLUGIN_PATH` dit.
- VS Code-launchen `"Whiteboard (PySide6)"` kör en preLaunchTask som gör samma kopia och använder `tmp_qt_plugins` i env samt sätter `PYTHONPATH` och `cwd`.
- `src/main.py` gör en sista guard: den lägger till projektroten i `sys.path`, kopierar plugins till `tmp_qt_plugins/platforms/` och sätter Qt/DYLD-env innan appen startas (gäller även “Run Python File”-knappen).

Återställning om något strular:
1) Ta bort den lokala kopian och låt den skapas om:
```
rm -rf tmp_qt_plugins
./run.sh
```
2) Kontrollera venv-stigen i `run.sh` och `.vscode/launch.json` pekar på `.venv/bin/python`.
3) Om env krockar: rensa gamla variabler och kör skriptet:
```
unset QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH QT_QPA_PLATFORM DYLD_FRAMEWORK_PATH DYLD_LIBRARY_PATH
./run.sh
```
4) Starta via VS Code: välj “Whiteboard (PySide6)” i Run and Debug och tryck F5.

Kvarstår felet? Kör med debug-logg:
```
QT_DEBUG_PLUGINS=1 ./run.sh 2>&1 | tail -n 200
```
