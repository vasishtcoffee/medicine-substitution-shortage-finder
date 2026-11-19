"""Compute sRGB contrast for actual CSS token pairs. Source check, not WCAG certification."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")
tokens = dict(re.findall(r"--([\w-]+):\s*(#[\da-fA-F]{6})", css.split("}", 1)[0]))


def luminance(hex_color):
    rgb = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    rgb = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
    return sum(value * weight for value, weight in zip(rgb, [.2126, .7152, .0722]))


pairs = []
for fg in ("text", "muted", "ok", "warn", "err"):
    for bg in ("bg", "surface", "surface-hover"):
        pairs.append((fg, bg, 4.5, "text"))
pairs += [("text", "bg", 4.5, "input text"), ("accent-text", "accent", 4.5, "primary action"),
          ("accent-text", "accent-hover", 4.5, "primary hover"),
          ("ok", "ok-bg", 4.5, "success feedback"), ("warn", "warn-bg", 4.5, "verification status"),
          ("err", "err-bg", 4.5, "error/destructive action")]
for fg in ("control", "focus"):
    for bg in ("bg", "surface", "surface-hover", "err-bg", "warn-bg", "ok-bg"):
        pairs.append((fg, bg, 3, "control boundary" if fg == "control" else "offset focus outline"))
pairs += [("text", "surface-hover", 3, "active navigation indicator"), ("accent", "surface", 3, "primary button boundary")]
report = []
for fg, bg, target, use in pairs:
    a, b = sorted([luminance(tokens[fg]), luminance(tokens[bg])])
    ratio = (b + .05) / (a + .05)
    report.append({"use": use, "foreground": fg, "background": bg, "colors": [tokens[fg], tokens[bg]],
                   "ratio": round(ratio, 3), "target": target, "passed": ratio >= target})
print(json.dumps({"tokens": tokens, "pairs": report,
                  "note": "Focus has 4px offset; evaluated against surrounding surface, not the button fill. Decorative card separators are not control boundaries. Disabled controls are not included."}, indent=2))
raise SystemExit(int(any(not row["passed"] for row in report)))
