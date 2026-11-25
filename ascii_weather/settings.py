"""The config file and the fullscreen settings menu."""

import json
import math
import os
import time
from pathlib import Path

from . import api, art, term

DEFAULTS = {
    "home": None,
    "units": "metric",
    "time_format": "24h",
    "animations": True,
    "last_update_check": 0,
    "latest_version": None,
}

ITEMS = [
    ("home", "Home location"),
    ("units", "Units"),
    ("time_format", "Time format"),
    ("animations", "Animations"),
]


def config_path():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "ascii-weather" / "config.json"


def load_config():
    config = dict(DEFAULTS)
    try:
        saved = json.loads(config_path().read_text(encoding="utf-8"))
        config.update({key: value for key, value in saved.items() if key in DEFAULTS})
    except (OSError, ValueError, AttributeError):
        pass  # no config yet, or a broken one: use the defaults
    return config


def save_config(config):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def value_text(config, key):
    if key == "home":
        return config["home"]["name"] if config["home"] else "auto-detect (IP)"
    if key == "units":
        return "imperial (°F, mph)" if config["units"] == "imperial" else "metric (°C, km/h)"
    if key == "time_format":
        return config["time_format"]
    return "on" if config[key] else "off"


def toggle(config, key):
    if key == "units":
        config["units"] = "metric" if config["units"] == "imperial" else "imperial"
    elif key == "time_format":
        config["time_format"] = "24h" if config["time_format"] == "12h" else "12h"
    else:
        config[key] = not config[key]
    save_config(config)


def set_home(config, text):
    """Look up the typed city and save it as the home location. Returns a status line and its color."""
    text = text.strip()
    if not text:
        config["home"] = None
        save_config(config)
        return "Using your IP location.", "bright_green"
    try:
        place = api.search_city(text)
    except (OSError, ValueError):
        return "Can't reach the weather service. Are you online?", "bright_red"
    if place is None:
        return f"Couldn't find '{text}'.", "bright_red"
    config["home"] = place
    save_config(config)
    return f"Home location set to {place['name']}.", "bright_green"


RAINBOW = ("bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta")
PANEL_WIDTH = 58


def draw(screen, config, selected, typing, status, t):
    cols, rows = term.size()
    canvas = term.Canvas(cols, rows)
    x = max(0, (cols - PANEL_WIDTH) // 2)
    y = max(0, (rows - 21) // 2)

    # Mascot and a title whose colors flow like a rainbow.
    art.draw_cloud(canvas, x + 15, y + 1 + round(math.sin(t * 2)), "day")
    for i, char in enumerate("ascii-weather"):
        canvas.put(x + 33 + i, y + 2, char, RAINBOW[(i + int(t * 6)) % len(RAINBOW)])
    canvas.put(x + 33, y + 3, "settings", "gray")
    canvas.put(x + 47, y + 1, "*+"[int(t * 2) % 2], "bright_yellow")

    canvas.box(x, y + 7, PANEL_WIDTH, 8, "bright_cyan")
    for i, (key, label) in enumerate(ITEMS):
        row = y + 9 + i
        active = i == selected
        canvas.put(x + 3, row, ">" if active else " ", "bright_cyan")
        canvas.put(x + 5, row, label, "bright_cyan" if active else "white")
        value_x = x + 22
        if key == "home" and typing is not None:
            caret = "_" if int(t * 2) % 2 == 0 else " "
            canvas.put(value_x, row, f"[ {typing}{caret}".ljust(30) + "]", "bright_white")
        elif key == "animations":
            canvas.put(value_x, row, "[x] on" if config[key] else "[ ] off", "bright_green" if config[key] else "gray")
        else:
            text = value_text(config, key)
            canvas.put(value_x, row, f"< {text} >" if active else f"  {text}", "bright_yellow")

    if typing is not None:
        hints = [("Enter", "search"), ("empty", "auto-detect"), ("Esc", "cancel")]
    else:
        hints = [("↑↓", "move"), ("Enter", "change"), ("Esc", "exit")]
    hint_x = x + 2
    for key_name, action in hints:
        canvas.put(hint_x, y + 16, f"[{key_name}]", "white")
        canvas.put(hint_x + len(key_name) + 3, y + 16, action, "gray")
        hint_x += len(key_name) + len(action) + 6
    text, color = status
    if text:
        canvas.put(x + 2, y + 18, {"bright_green": "√ ", "bright_red": "! "}.get(color, "") + text, color)
    screen.draw(canvas)


def run(config):
    selected = 0
    typing = None  # the city being typed for the home location, None while not typing
    status = ("", None)
    start = time.monotonic()
    with term.Screen() as screen:
        while True:
            draw(screen, config, selected, typing, status, time.monotonic() - start)
            key = term.get_key(0.1)
            if key is None:
                continue
            if typing is not None:
                if key == "esc":
                    typing = None
                elif key == "enter":
                    draw(screen, config, selected, typing, ("Searching...", "gray"), time.monotonic() - start)
                    status = set_home(config, typing)
                    typing = None
                elif key == "backspace":
                    typing = typing[:-1]
                elif len(key) == 1 and key.isprintable() and len(typing) < 28:
                    typing += key  # the input field in the panel is 28 columns wide
                continue
            if key in ("esc", "q"):
                break
            if key == "up":
                selected = (selected - 1) % len(ITEMS)
            elif key == "down":
                selected = (selected + 1) % len(ITEMS)
            elif key in ("enter", "left", "right", " "):
                name = ITEMS[selected][0]
                status = ("", None)
                if name == "home":
                    typing = ""
                else:
                    toggle(config, name)
