"""
Entry point for whiteboard assist prototype.
Opens a camera stream and provides a simple window loop you can extend.
"""

import cv2
import sys
from pathlib import Path
import numpy as np

# Hjälpfunktion för att passa en rektangel med given aspect i w x h utan att ändra aspect.
def fit_rect_with_aspect(w: int, h: int, aspect: float) -> np.ndarray:
    frame_aspect = w / h
    if frame_aspect >= aspect:
        dst_h = h
        dst_w = int(h * aspect)
    else:
        dst_w = w
        dst_h = int(w / aspect)
    ox = (w - dst_w) // 2
    oy = (h - dst_h) // 2
    return np.array(
        [
            [ox, oy],
            [ox + dst_w - 1, oy],
            [ox + dst_w - 1, oy + dst_h - 1],
            [ox, oy + dst_h - 1],
        ],
        dtype="float32",
    )

def quad_aspect(src_pts: np.ndarray) -> float:
    """
    Approximate aspect ratio of a quad by averaging top/bottom width and left/right height.
    """
    top = np.linalg.norm(src_pts[1] - src_pts[0])
    bottom = np.linalg.norm(src_pts[2] - src_pts[3])
    left = np.linalg.norm(src_pts[3] - src_pts[0])
    right = np.linalg.norm(src_pts[2] - src_pts[1])
    mean_w = max(1e-6, (top + bottom) / 2.0)
    mean_h = max(1e-6, (left + right) / 2.0)
    return mean_w / mean_h


def reorder_quad(pts: list[tuple[int, int]]) -> np.ndarray:
    """
    Ta fyra punkter i valfri ordning och returnera dem som TL, TR, BR, BL.
    Använder summor/differenser för att hitta hörnen robust.
    """
    if len(pts) != 4:
        raise ValueError("Need 4 points to reorder")
    pts_np = np.array(pts, dtype="float32")
    s = pts_np.sum(axis=1)
    diff = np.diff(pts_np, axis=1).flatten()
    tl = pts_np[np.argmin(s)]
    br = pts_np[np.argmax(s)]
    tr = pts_np[np.argmin(diff)]
    bl = pts_np[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype="float32")

# Centralt kommando-register för att visa hjälptext.
HELP_LINES = [
    "h: toggle help",
    "q: quit",
    "0: reset view (zoom/center/keystone)",
    "+/- or =/_: zoom in/out",
    "arrows or WASD: pan",
    "t: toggle keystone on/off",
    "r: reset keystone to full frame",
    "1-4: select keystone corner (1=top-left, clockwise)",
    "i/j/k/l: nudge selected corner (up/left/down/right)",
    "m: mouse mode, click 4 corners (valfri ordning)",
]

# Make src imports work when running as a script (python src/main.py) or as module.
if __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.append(str(project_root))

from src.keystone import warp_perspective
from src.zoom import crop_zoom


def main() -> None:
    # Öppnar datorns första kamera (index 0). Byt index om du har flera.
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    window_name = "Whiteboard Assist"
    # Skapa ett fönster som kan ändra storlek.
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # Läs en första frame för att kunna sätta start-värden för center/zoom.
    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Could not read initial frame from camera")

    h, w = frame.shape[:2]
    # Starta med zoom 1.0 (ingen zoom) och center i mitten av bilden.
    zoom_scale = 1.0
    center = (w // 2, h // 2)
    pan_step = 20  # antal pixlar att flytta vid pan
    show_help = True

    # Keystone-state: hörn (standard = hela bilden) och nudge-steg.
    keystone_src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
    keystone_enabled = False
    keystone_step = 10
    selected_corner = 0  # 0=övre-vänster, 1=övre-höger, 2=nedre-höger, 3=nedre-vänster
    collecting_points = False
    mouse_points: list[tuple[int, int]] = []

    def on_mouse(event, x, y, flags, userdata):
        nonlocal collecting_points, mouse_points, keystone_src, keystone_enabled
        if not collecting_points:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            mouse_points.append((x, y))
            print(f"Hörn {len(mouse_points)} satt till ({x}, {y})")
            if len(mouse_points) == 4:
                keystone_src = reorder_quad(mouse_points)
                keystone_enabled = True
                collecting_points = False
                mouse_points.clear()
                print("Fyra hörn satta (omordnade TL,TR,BR,BL). Keystone aktiv.")

    # Koppla muscallback för hörnval.
    cv2.setMouseCallback(window_name, on_mouse)

    try:
        while True:
            # Läs nästa bildruta från kameran.
            ret, frame = cap.read()
            if not ret:
                break

            # Keystone: om aktivt, räta upp bilden mot hela fönstret.
            if keystone_enabled and keystone_src is not None:
                aspect = quad_aspect(keystone_src)
                dst_pts = fit_rect_with_aspect(w, h, aspect)
                frame = warp_perspective(frame, keystone_src, (w, h), dst_pts)

            # Skala/zooma runt valt center.
            frame = crop_zoom(frame, center, zoom_scale)

            # Rita hjälptext om den är aktiv.
            if show_help:
                overlay = frame.copy()
                pad = 16
                font_scale = 0.8
                thickness = 2
                line_h = 24
                # Beräkna boxbredd utifrån längsta raden.
                max_w = 0
                for line in HELP_LINES:
                    (tw, _), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                    max_w = max(max_w, tw)
                box_w = max_w + pad * 2
                box_h = pad * 2 + line_h * len(HELP_LINES)
                cv2.rectangle(overlay, (10, 10), (10 + box_w, 10 + box_h), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
                for idx, line in enumerate(HELP_LINES):
                    y = 10 + pad + line_h * (idx + 1)
                    cv2.putText(frame, line, (16, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

            # Visa bilden i fönstret.
            cv2.imshow(window_name, frame)

            # Vänta 1 ms på tangenttryck. waitKeyEx fångar piltangenter bättre än waitKey.
            key = cv2.waitKeyEx(1)
            # Avkommentera nästa rad för att se keycodes i terminalen (hjälper felsökning av piltangenter).
            # if key != -1:
            #     print(f"key pressed: {key}")

            # Avsluta loopen om användaren trycker 'q'.
            if key == ord("q"):
                break
            # Slå av/på hjälprutan.
            elif key == ord("h"):
                show_help = not show_help

            # Snabbåterställning: zoom, center, keystone.
            elif key == ord("0"):
                zoom_scale = 1.0
                center = (w // 2, h // 2)
                keystone_src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
                keystone_enabled = False
                collecting_points = False
                mouse_points.clear()
                print("Återställd till originalvy.")
                
            # Justera zoom med + / - (eller = / _).
            elif key == ord("+") or key == ord("="):
                zoom_scale *= 1.1  # Zooma in
            elif key == ord("-") or key == ord("_"):
                zoom_scale = max(1.0, zoom_scale / 1.1)  # Zooma ut, aldrig mindre än 1.0

            # Pan: piltangenter (flera keycodes beroende på plattform) eller WASD.
            elif key in (81, 2424832, 65361, 63234, ord("a")):  # Vänsterpil eller 'a'
                center = (max(center[0] - pan_step, 0), center[1])
            elif key in (83, 2555904, 65363, 63235, ord("d")):  # Högerpil eller 'd'
                center = (min(center[0] + pan_step, w - 1), center[1])
            elif key in (82, 2490368, 65362, 63232, ord("w")):  # Uppil eller 'w'
                center = (center[0], max(center[1] - pan_step, 0))
            elif key in (84, 2621440, 65364, 63233, ord("s")):  # Nedpil eller 's'
                center = (center[0], min(center[1] + pan_step, h - 1))
            
            # Keystone toggla och manuell nudge med I/J/K/L för valt hörn.
            elif key == ord("t"):  # toggla keystone av/på
                keystone_enabled = not keystone_enabled
                print(f"Keystone {'på' if keystone_enabled else 'av'}")
            elif key == ord("r"):  # reset keystone till full bild
                keystone_src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
                keystone_enabled = False
                print("Keystone återställd.")
            elif key in (ord("1"), ord("2"), ord("3"), ord("4")):
                selected_corner = int(chr(key)) - 1
                print(f"Valt hörn: {selected_corner + 1}")
            elif key == ord("j"):  # flytta valt hörn vänster
                keystone_src[selected_corner, 0] = max(0, keystone_src[selected_corner, 0] - keystone_step)
                keystone_enabled = True
            elif key == ord("l"):  # flytta valt hörn höger
                keystone_src[selected_corner, 0] = min(w - 1, keystone_src[selected_corner, 0] + keystone_step)
                keystone_enabled = True
            elif key == ord("i"):  # flytta valt hörn upp
                keystone_src[selected_corner, 1] = max(0, keystone_src[selected_corner, 1] - keystone_step)
                keystone_enabled = True
            elif key == ord("k"):  # flytta valt hörn ned
                keystone_src[selected_corner, 1] = min(h - 1, keystone_src[selected_corner, 1] + keystone_step)
                keystone_enabled = True
            elif key == ord("m"):  # starta mus-läge: klicka 4 hörn
                collecting_points = True
                mouse_points.clear()
                keystone_enabled = False
                print("Klicka 4 hörn (start övre-vänster, sedan medurs).")

            # Se till att beskärningsfönstret ligger inom bilden givet aktuell zoom.
            crop_w = max(1, int(w / zoom_scale))
            crop_h = max(1, int(h / zoom_scale))
            half_w = max(1, crop_w // 2)
            half_h = max(1, crop_h // 2)
            cx = max(half_w, min(center[0], w - half_w))
            cy = max(half_h, min(center[1], h - half_h))
            center = (cx, cy)

    finally:
        # Se till att kameran släpps och fönstret stängs, även vid fel.
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
