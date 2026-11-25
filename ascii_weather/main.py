"""The 'weather' command: fetches the weather and shows it fullscreen until a key is pressed."""

import math
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from . import api, art, settings, term, update

HELP = """\
weather              weather for your location
weather <city>       weather for a city, e.g. "weather new york" or "weather paris, texas"
weather settings     home location, units, time format, animations

Press any key to close the weather screen."""

WIND_DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def main():
    args = sys.argv[1:]
    if args[:1] in (["-h"], ["--help"]):
        print(HELP)
        return
    if args[:1] in (["-V"], ["--version"]):
        print(f"ascii-weather {update.installed_version() or 'dev'}")
        return
    for arg in args:
        if arg.startswith("-") and len(arg) > 1:
            print(f"weather: unknown option '{arg}' (try 'weather --help')", file=sys.stderr)
            sys.exit(1)
    config = settings.load_config()
    try:
        if args == ["settings"]:
            settings.run(config)
        else:
            show_weather(config, " ".join(args).strip())
    except KeyboardInterrupt:
        pass


def show_weather(config, query):
    checker = update.UpdateCheck(config)
    result = {}

    def fetch():
        try:
            result["data"] = api.get_weather(query, config)
        except api.WeatherError as error:
            result["error"] = str(error)
        except Exception as error:  # without this, a crash here would leave the loading screen up forever
            result["error"] = f"Something went wrong: {error}"

    threading.Thread(target=fetch, daemon=True).start()
    start = time.monotonic()
    with term.Screen() as screen:
        while True:
            cols, rows = term.size()
            canvas = term.Canvas(cols, rows)
            t = time.monotonic() - start
            if "data" in result:
                draw_weather(canvas, result["data"], config, t if config["animations"] else 0)
            elif "error" in result:
                art.draw_error(canvas, result["error"], t)
            else:
                art.draw_loading(canvas, t)
            screen.draw(canvas)
            if term.get_key(0.1):
                break
    checker.finish()


THEMES = {  # (accent, frame) colors for each kind of weather
    "clear": ("bright_yellow", "yellow"), "partly": ("bright_yellow", "yellow"), "cloudy": ("bright_white", "white"),
    "fog": ("white", "gray"), "drizzle": ("bright_cyan", "cyan"), "rain": ("bright_blue", "blue"),
    "snow": ("bright_cyan", "cyan"), "thunder": ("bright_yellow", "magenta"),
}


def theme(current):
    kind = art.kind_of(current["weather_code"])
    if not current["is_day"] and kind in ("clear", "partly"):
        return "bright_magenta", "magenta"
    return THEMES[kind]


def scene_info(data):
    """What the scene needs to know, in metric units: weather, wind, temperature, sun position and season."""
    current, imperial = data["current"], data["imperial"]
    now = local_now(data)
    wind, temp = current.get("wind_speed_10m") or 0, current.get("temperature_2m")
    try:
        sunrise = datetime.fromisoformat(data["daily"]["sunrise"][0])
        sunset = datetime.fromisoformat(data["daily"]["sunset"][0])
        progress = (now - sunrise) / (sunset - sunrise)
    except (TypeError, ValueError, ZeroDivisionError):
        progress = None  # polar day or night
    return {
        "code": current["weather_code"],
        "is_day": current["is_day"],
        "wind": wind * 1.609 if imperial else wind,
        "temp": None if temp is None else (temp - 32) * 5 / 9 if imperial else temp,
        "sun_progress": progress,
        "month": now.month,
    }


def draw_weather(canvas, data, config, t):
    if canvas.width >= 78 and canvas.height >= 30:
        draw_full(canvas, data, config, t)
    elif canvas.width >= 40 and canvas.height >= 14:
        draw_compact(canvas, data, config, t)
    else:
        canvas.center(0, canvas.height // 2 - 1, canvas.width, "(>_<)", "bright_yellow")
        canvas.center(0, canvas.height // 2, canvas.width, "make the window bigger", "gray")


def draw_frame(canvas, data, config, accent, frame):
    """Border, location, date and time, and the key hint at the bottom."""
    width, height = canvas.width, canvas.height
    canvas.box(0, 0, width, height, frame)
    canvas.put(2, 0, f" ⌂ {data['place']} ", accent)
    now = local_now(data)
    clock = f" {now.strftime('%a %d %b')} · {clock_time(now, config)} "
    if width > len(data["place"]) + len(clock) + 10:
        canvas.put(width - len(clock) - 2, 0, clock, accent)
    canvas.center(0, height - 1, width, " press any key to go back ", frame)


def draw_full(canvas, data, config, t):
    """Scene and details on top, then the next 24 hours, then the next 7 days."""
    width, height = canvas.width, canvas.height
    current = data["current"]
    accent, frame = theme(current)
    top_height = height - 18
    details_width = 36
    split_x = width - 2 - details_width
    hourly_y = top_height + 1
    daily_y = hourly_y + 8

    draw_frame(canvas, data, config, accent, frame)
    canvas.divider(hourly_y, "next 24 hours", frame, accent)
    canvas.divider(daily_y, "next 7 days", frame, accent)
    canvas.put(split_x, 0, "┬", frame)
    for row in range(1, hourly_y):
        canvas.put(split_x, row, "│", frame)
    canvas.put(split_x, hourly_y, "┴", frame)

    art.draw_scene(canvas, 1, 1, split_x - 1, top_height, scene_info(data), t)
    draw_details(canvas, split_x + 3, 1 + max(0, (top_height - 12) // 2), details_width - 4, data, config)
    draw_hourly(canvas, 1, hourly_y + 1, width - 2, data, config, accent, t)
    draw_daily(canvas, 1, daily_y + 1, width - 2, data, accent, t)


def draw_compact(canvas, data, config, t):
    """For small windows: only the scene and the current temperature."""
    width, height = canvas.width, canvas.height
    current = data["current"]
    accent, frame = theme(current)
    temp = current["temperature_2m"]
    unit = "°F" if data["imperial"] else "°C"
    draw_frame(canvas, data, config, accent, frame)
    art.draw_scene(canvas, 1, 1, width - 2, height - 4, scene_info(data), t)
    description = art.DESCRIPTIONS.get(current["weather_code"], "")
    line = f" {fmt(temp)}{unit} · {description} · feels like {fmt(current['apparent_temperature'])}{unit} "
    canvas.center(0, height - 2, width, line, temp_color(temp, data["imperial"]))


def draw_details(canvas, x, y, width, data, config):
    current, daily, air, imperial = data["current"], data["daily"], data["air"], data["imperial"]
    saved_clip = canvas.clip
    canvas.clip = (x, y, x + width, y + 12)
    unit = "°F" if imperial else "°C"
    temp = current["temperature_2m"]
    art.big_text(canvas, x, y, f"{fmt(temp)}°{unit[-1]}", temp_color(temp, imperial))
    canvas.put(x, y + 4, art.DESCRIPTIONS.get(current["weather_code"], ""), "bright_white")

    feels, humidity = current["apparent_temperature"], current["relative_humidity_2m"]
    uv = daily["uv_index_max"][0]
    uv_label, uv_color = uv_text(uv)
    aqi = air.get("european_aqi") if air else None
    aqi_label, aqi_color = aqi_text(aqi)
    direction = current["wind_direction_10m"]
    rows = [
        ("°", "bright_yellow", "Feels like", [(f"{fmt(feels)}{unit}", temp_color(feels, imperial))]),
        ("≈", "bright_cyan", "Wind", [
            (f"{fmt(current['wind_speed_10m'])} {'mph' if imperial else 'km/h'} ", "white"),
            (f"{arrow(direction)} {compass(direction)}", "bright_cyan"),
        ]),
        ("♦", "bright_blue", "Humidity", [(f"{fmt(humidity)}% ", "white"), *bar(humidity, 100, "bright_blue")]),
        ("¤", "bright_yellow", "UV max", [(f"{uv_label} ", uv_color), *bar(uv, 11, uv_color)]),
        ("↕", "yellow", "Sun", [
            ("↑", "bright_yellow"), (sun_time(daily["sunrise"][0], config) + "  ", "white"),
            ("↓", "yellow"), (sun_time(daily["sunset"][0], config), "white"),
        ]),
        ("≡", "bright_green", "Air", [(f"{aqi_label} ", aqi_color), *bar(aqi, 100, aqi_color)]),
        ("*", "bright_magenta", "Pollen", [pollen_text(air)]),
    ]
    for i, (icon, icon_color, label, parts) in enumerate(rows):
        row = y + 5 + i
        canvas.put(x, row, icon, icon_color)
        canvas.put(x + 2, row, label, "gray")
        part_x = x + 13
        for text, color in parts:
            canvas.put(part_x, row, text, color)
            part_x += len(text)
    canvas.clip = saved_clip


def bar(value, maximum, color, width=8):
    """A little bar like ======--, as two (text, color) parts."""
    if value is None:
        return []
    filled = max(0, min(width, round(value / maximum * width)))
    return [("=" * filled, color), ("-" * (width - filled), "gray")]


def draw_hourly(canvas, x, y, width, data, config, accent, t):
    hourly, imperial = data["hourly"], data["imperial"]
    start = current_hour_index(data)
    step = math.ceil(24 / max(1, width // 11))
    indexes = list(range(start, min(start + 24, len(hourly["time"])), step))
    column = width // len(indexes)
    for n, i in enumerate(indexes):
        left = x + n * column
        if n == 0:
            canvas.center(left, y, column, "> Now <", accent)
        else:
            canvas.center(left, y, column, hour_label(datetime.fromisoformat(hourly["time"][i]), config), "white")
        icon_t = t + n * 0.25  # so the icons don't all move in step
        art.mini_icon(canvas, left + (column - 10) // 2, y + 1, hourly["weather_code"][i], hourly["is_day"][i], icon_t)
        temp, rain = hourly["temperature_2m"][i], hourly["precipitation_probability"][i]
        canvas.center(left, y + 5, column, f"{fmt(temp)}°", temp_color(temp, imperial))
        if rain:
            canvas.center(left, y + 6, column, f"♦ {fmt(rain)}%", "bright_blue")


def draw_daily(canvas, x, y, width, data, accent, t):
    daily, imperial = data["daily"], data["imperial"]
    days = min(7, len(daily["time"]))
    column = width // days
    for n in range(days):
        left = x + n * column
        day = datetime.fromisoformat(daily["time"][n])
        if n == 0:
            canvas.center(left, y, column, "> Today <", accent)
        else:
            canvas.center(left, y, column, day.strftime("%a %d"), accent if day.weekday() >= 5 else "white")
        art.mini_icon(canvas, left + (column - 10) // 2, y + 1, daily["weather_code"][n], True, t + n * 0.25)
        high, low = daily["temperature_2m_max"][n], daily["temperature_2m_min"][n]
        high_text, low_text = f"{fmt(high)}°", f"{fmt(low)}°"
        text_x = left + (column - len(high_text) - 3 - len(low_text)) // 2
        canvas.put(text_x, y + 5, high_text, temp_color(high, imperial))
        canvas.put(text_x + len(high_text), y + 5, " / ", "gray")
        canvas.put(text_x + len(high_text) + 3, y + 5, low_text, temp_color(low, imperial))
        rain = daily["precipitation_probability_max"][n]
        if rain:
            canvas.center(left, y + 6, column, f"♦ {fmt(rain)}%", "bright_blue")


def local_now(data):
    """The current time at the weather location (not on this computer)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=data["utc_offset"])


def current_hour_index(data):
    """The current hour, or the first one to come after it, so no past hours are ever shown."""
    key = local_now(data).strftime("%Y-%m-%dT%H:00")
    times = data["hourly"]["time"]
    for i, text in enumerate(times):
        if text >= key:
            return i
    return max(0, len(times) - 1)


def clock_time(moment, config):
    if config["time_format"] == "12h":
        return f"{moment.hour % 12 or 12}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"
    return moment.strftime("%H:%M")


def sun_time(text, config):
    """Sunrise or sunset time. Near the poles there may be none."""
    return clock_time(datetime.fromisoformat(text), config) if text else "--"


def hour_label(moment, config):
    if config["time_format"] == "12h":
        return f"{moment.hour % 12 or 12} {'AM' if moment.hour < 12 else 'PM'}"
    return moment.strftime("%H:%M")


def fmt(value):
    return "--" if value is None else str(round(value))


def compass(degrees):
    return "" if degrees is None else WIND_DIRECTIONS[round(degrees / 45) % 8]


def arrow(degrees):
    """Where the wind blows to (the API gives where it comes from)."""
    return "" if degrees is None else "↓←↑→"[round(degrees / 90) % 4]


def temp_color(value, imperial):
    return art.temp_rgb(None if value is None else (value - 32) * 5 / 9 if imperial else value)


def uv_text(uv):
    if uv is None:
        return "--", "gray"
    for limit, name, color in ((3, "low", "bright_green"), (6, "moderate", "yellow"), (8, "high", "bright_red"),
                               (11, "very high", "red")):
        if uv < limit:
            return f"{round(uv)} ({name})", color
    return f"{round(uv)} (extreme)", "magenta"


def aqi_text(aqi):
    if aqi is None:
        return "--", "gray"
    for limit, name, color in ((20, "good", "bright_green"), (40, "fair", "green"), (60, "moderate", "yellow"),
                               (80, "poor", "bright_red"), (100, "very poor", "red")):
        if aqi <= limit:
            return f"{round(aqi)} ({name})", color
    return f"{round(aqi)} (extremely poor)", "magenta"


def pollen_text(air):
    """The strongest pollen right now. Open-Meteo only has pollen data for Europe."""
    values = {kind: air.get(f"{kind}_pollen") for kind in api.POLLEN} if air else {}
    values = {kind: amount for kind, amount in values.items() if amount is not None}
    if not values:
        return "no data", "gray"
    kind, amount = max(values.items(), key=lambda item: item[1])
    if amount < 1:
        return "none", "bright_green"
    if amount < 10:
        return f"{kind} (low)", "bright_green"
    if amount < 50:
        return f"{kind} (moderate)", "yellow"
    return f"{kind} (high)", "bright_red"
