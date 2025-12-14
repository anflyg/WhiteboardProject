#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
QTBASE="$VENV/lib/python3.12/site-packages/PySide6/Qt"
TMP_PLUGINS="$ROOT/tmp_qt_plugins"

prepare_plugins() {
  local src="$QTBASE/plugins/platforms"
  local dst="$TMP_PLUGINS/platforms"
  if [ ! -d "$dst" ] || [ -z "$(ls -A "$dst" 2>/dev/null)" ]; then
    mkdir -p "$dst"
    cp "$src"/libq*.dylib "$dst"/ 2>/dev/null || true
  fi
}
prepare_plugins

export QT_MAC_DISABLE_LIBRARY_VALIDATION=1
export QT_PLUGIN_PATH="$TMP_PLUGINS"
export QT_QPA_PLATFORM_PLUGIN_PATH="$TMP_PLUGINS/platforms"
export QT_QPA_PLATFORM=cocoa
export DYLD_FRAMEWORK_PATH="$QTBASE/lib"
export DYLD_LIBRARY_PATH="$QTBASE/lib"
exec "$VENV/bin/python" "$ROOT/src/main.py" "$@"
