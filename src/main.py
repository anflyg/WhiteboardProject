"""
Entry point for whiteboard assist prototype.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

def _ensure_project_root_on_path() -> None:
    """
    Make src imports work regardless of how main.py is launched (Run Python File, debug, run.sh).
    """
    project_root = Path(__file__).resolve().parent.parent
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_ensure_project_root_on_path()


def _ensure_qt_plugin_paths() -> None:
    """
    Ensure Qt finds the cocoa platform plugin by setting plugin/library paths
    from the current PySide6 install (copied to tmp_qt_plugins/) and restart once
    so dyld sees the paths.
    """
    if os.environ.get("QT_ENV_FIXED") == "1":
        return
    try:
        import PySide6  # Import just to locate the installed package

        base = Path(PySide6.__file__).resolve().parent
        qt_dir = base / "Qt"
        plugins_path = qt_dir / "plugins"
        platforms_path = plugins_path / "platforms"
        libs_path = qt_dir / "lib"

        # Copy platform plugins to tmp_qt_plugins to avoid macOS hidden flag issues.
        tmp_plugins_root = Path(__file__).resolve().parent.parent / "tmp_qt_plugins"
        tmp_platforms_path = tmp_plugins_root / "platforms"
        if not tmp_platforms_path.exists() or not any(tmp_platforms_path.glob("libq*.dylib")):
            tmp_platforms_path.mkdir(parents=True, exist_ok=True)
            for dylib in platforms_path.glob("libq*.dylib"):
                try:
                    shutil.copy2(dylib, tmp_platforms_path / dylib.name)
                except OSError:
                    pass
        # Prefer copied plugins if present.
        plugins_path = tmp_plugins_root if tmp_plugins_root.exists() else plugins_path
        platforms_path = tmp_platforms_path if tmp_platforms_path.exists() else platforms_path

        env = os.environ.copy()
        env.setdefault("QT_PLUGIN_PATH", str(plugins_path))
        env.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms_path))
        env.setdefault("QT_QPA_PLATFORM", "cocoa")
        env.setdefault("QT_MAC_DISABLE_LIBRARY_VALIDATION", "1")
        env["DYLD_FRAMEWORK_PATH"] = str(libs_path) + (":" + env["DYLD_FRAMEWORK_PATH"] if "DYLD_FRAMEWORK_PATH" in env else "")
        env["DYLD_LIBRARY_PATH"] = str(libs_path) + (":" + env["DYLD_LIBRARY_PATH"] if "DYLD_LIBRARY_PATH" in env else "")
        env["QT_ENV_FIXED"] = "1"

        # Restart once so dyld picks up paths; guard with QT_ENV_FIXED to avoid loops.
        os.execve(sys.executable, [sys.executable, str(Path(__file__).resolve())] + sys.argv[1:], env)
    except Exception:
        return


_ensure_qt_plugin_paths()

from src.app import main
from src.capture import list_available_cameras


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Whiteboard Assist")
    parser.add_argument(
        "-c",
        "--camera-index",
        type=int,
        default=0,
        help="Camera index to open (0 for default webcam, 1 for second, etc.)",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="Print available camera indexes and exit",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.list_cameras:
        cameras = list_available_cameras()
        if cameras:
            print("Available cameras:", ", ".join(map(str, cameras)))
        else:
            print("No cameras found. Try adjusting permissions or plugging one in.")
        sys.exit(0)

    main(camera_index=args.camera_index)
