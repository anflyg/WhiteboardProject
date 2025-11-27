"""
Entry point for whiteboard assist prototype.
"""
import argparse
import sys
from pathlib import Path

# Make src imports work when running as a script (python src/main.py) or as module.
if __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))

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
