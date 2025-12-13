import cv2

HELP_LINES = [
    "Shortcuts (Qt):",
    "h: toggle help overlay",
    "q: quit application",
    "0: reset view (zoom/center/keystone)",
    "+/- or =/_: zoom in/out",
    "arrows or WASD: pan",
    "space or Ctrl+P: capture corrected photo",
    "t: toggle keystone on/off",
    "r: reset keystone to full frame",
    "1-4: select keystone corner (1=top-left, clockwise)",
    "i/j/k/l: nudge selected corner (up/left/down/right)",
    "m: mouse corner mode, click 4 corners",
    "Camera/View/Help menus finns i menyraden",
]


def draw_help_overlay(frame):
    overlay = frame.copy()
    pad = 16
    font_scale = 0.8
    thickness = 2
    line_h = 24
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
    return frame


def draw_corner_markers(frame, points, size: int = 80, color=(0, 0, 255), thickness: int = 2):
    """
    Draw red '+' markers at the given points.
    """
    if not points:
        return frame
    for x, y in points:
        cv2.line(frame, (x - size, y), (x + size, y), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x, y - size), (x, y + size), color, thickness, cv2.LINE_AA)
    return frame
