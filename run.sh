#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
QTBASE="$VENV/lib/python3.12/site-packages/PySide6/Qt"
export QT_MAC_DISABLE_LIBRARY_VALIDATION=1
export QT_PLUGIN_PATH="$QTBASE/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$QTBASE/plugins/platforms"
export QT_QPA_PLATFORM=cocoa
export DYLD_FRAMEWORK_PATH="$QTBASE/lib"
export DYLD_LIBRARY_PATH="$QTBASE/lib"
exec "$VENV/bin/python" "$ROOT/src/main.py" "$@"
