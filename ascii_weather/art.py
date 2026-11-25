"""ASCII art: the animated weather scene, mini icons for the forecast and big digits for the temperature.

Everything is plain characters in text colors (no backgrounds), so the terminal's own background shows
through, transparent or not. Everything is a function of the time `t`, so a frozen scene is simply t = 0.
"""

import math
import random

DESCRIPTIONS = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}
LIGHT = {51, 56, 61, 71, 77, 80, 85}
HEAVY = {55, 57, 65, 67, 75, 82, 86, 96, 99}

# Colors as (r, g, b).
SUN, SUN_INSIDE, SUN_RAYS = (255, 214, 92), (238, 168, 64), ((255, 190, 70), (255, 234, 150))
SUNSET, SUNSET_INSIDE, SUNSET_RAYS = (255, 160, 92), (226, 100, 72), ((255, 128, 86), (255, 186, 120))
MOON = (246, 238, 196)
CLOUD_SHADES = {  # top to bottom
    "day": [(250, 251, 255), (236, 240, 248), (214, 220, 234), (190, 198, 216), (160, 168, 190)],
    "night": [(190, 194, 222), (176, 180, 210), (156, 160, 194), (136, 140, 176), (112, 116, 152)],
    "rain": [(196, 202, 218), (180, 186, 204), (160, 166, 186), (140, 146, 168), (118, 124, 148)],
    "thunder": [(150, 150, 172), (132, 132, 156), (114, 114, 140), (98, 98, 124), (84, 84, 110)],
    "flash": [(255, 255, 255)] * 5,
}
RAIN, DRIZZLE, SNOW, BOLT = (140, 186, 255), (170, 220, 245), (248, 250, 255), (255, 236, 110)
STAR_COLORS = ((255, 255, 255), (255, 240, 180), (186, 222, 255))

SUN_RAY_FRAMES = [
    ["       \\    |    /", "    '.             .'", "", "  ---               ---", "",
     "    .'             '.", "       /    |    \\"],
    ["     .   \\  |  /   .", "", "", " ----               ----", "", "", "     '   /  |  \\   '"],
]
SUN_BODY = [
    "         .-----.",
    "        /:::::::\\",
    "       |:::::::::|",
    "        \\:::::::/",
    "         '-----'",
]
SUN_CENTER = 12

MOON_ART = [
    "   .--.",
    "  /  .-'",
    " |  (",
    "  \\  '-.",
    "   '--'",
]
MOON_CENTER = 4

CLOUD = [
    "          _.---._",
    "     _.--(       )--._",
    "  .-(                 )-.",
    " (                       )",
    "  '-._________________.-'",
]
CLOUD_CENTER = 13

SMALL_CLOUD = [
    "    .--.",
    " .-(    ).",
    "(___.__)__)",
]

HOUSE = [
    "  ___||__",
    " /       \\",
    "/_________\\",
    " |[] ∩ []|",
]
TREE = [
    "  @@@@@",
    " @@@@@@@",
    "  @@@@@",
]

MINI_CLOUD = ["   .-.", "  (   ).", " (___(__)"]
MINI_SUN = [["  \\ | /", " -- O --", "  / | \\"], ["  \\   /", " -  O  -", "  /   \\"]]
MINI_MOON = ["   .-.", "  (  .'", "   '-'"]

DIGITS = {
    "0": ["  __  ", " /  \\ ", "| () |", " \\__/ "],
    "1": [" _ ", "/ |", "| |", "|_|"],
    "2": [" ___ ", "|_  )", " / / ", "/___|"],
    "3": [" ____", "|__ /", " |_ \\", "|___/"],
    "4": [" _ _  ", "| | | ", "|_  _|", "  |_| "],
    "5": [" ___ ", "| __|", "|__ \\", "|___/"],
    "6": ["  __ ", " / / ", "/ _ \\", "\\___/"],
    "7": [" ____ ", "|__  |", "  / / ", " /_/  "],
    "8": [" ___ ", "( _ )", "/ _ \\", "\\___/"],
    "9": [" ___ ", "/ _ \\", "\\_, /", " /_/ "],
    "-": ["    ", "    ", " ___", "    "],
    "°": ["o", " ", " ", " "],
    "C": ["  ___ ", " / __|", "| (__ ", " \\___|"],
    "F": [" ___ ", "| __|", "| _| ", "|_|  "],
}


def kind_of(code):
    """Group a WMO weather code into the kinds of scenes we can draw."""
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    return "cloudy"


def mix(a, b, amount):
    return tuple(round(p + (q - p) * amount) for p, q in zip(a, b))


def at_night(color):
    """Darker and bluer, for the landscape at night."""
    return mix(tuple(round(c * 0.45) for c in color), (40, 48, 96), 0.3)


def temp_rgb(celsius):
    """A color for a temperature, from violet (freezing) over green to red (hot)."""
    stops = [(-15, (176, 146, 255)), (-5, (132, 172, 255)), (3, (120, 212, 255)), (10, (120, 232, 196)),
             (17, (172, 236, 122)), (23, (255, 226, 112)), (29, (255, 166, 92)), (35, (255, 102, 102))]
    if celsius is None:
        return (150, 150, 160)
    if celsius <= stops[0][0]:
        return stops[0][1]
    for (t1, c1), (t2, c2) in zip(stops, stops[1:]):
        if celsius <= t2:
            return mix(c1, c2, (celsius - t1) / (t2 - t1))
    return stops[-1][1]


def draw_art(canvas, x, y, rows, colors, marks=None):
    """Draw multi-line art. `colors` is one color or one per row, `marks` maps characters to their own color.
    Spaces around the shape are see-through; spaces inside it clear what's behind (like a hill line)."""
    for dy, row in enumerate(rows):
        color = colors[min(dy, len(colors) - 1)] if isinstance(colors, list) else colors
        start = len(row) - len(row.lstrip(" "))
        for dx in range(start, len(row.rstrip(" "))):
            char = row[dx]
            canvas.put(x + dx, y + dy, char, marks.get(char, color) if marks else color)


def drifting(t, speed, phase, width, margin=12):
    """Position of something that drifts across an area and comes back in on the other side."""
    return int((t * speed + phase * (width + 2 * margin)) % (width + 2 * margin)) - margin


def falling(count, seed, height, t, speed):
    """Falling particles as (random x, rows fallen, random value). The same seed gives the same particles."""
    rng = random.Random(seed)
    for _ in range(count):
        place, phase, extra = rng.random(), rng.random(), rng.random()
        yield place, int((phase * height + t * speed * (0.8 + 0.4 * extra)) % height), extra


def draw_cloud(canvas, center_x, top, style):
    draw_art(canvas, center_x - CLOUD_CENTER, top, CLOUD, CLOUD_SHADES[style])


def draw_sun(canvas, center_x, top, t, low):
    """The sun with shimmering rays. Low over the horizon it turns orange."""
    frame = int(t / 0.5) % 2
    body, inside, rays = (SUNSET, SUNSET_INSIDE, SUNSET_RAYS) if low else (SUN, SUN_INSIDE, SUN_RAYS)
    draw_art(canvas, center_x - SUN_CENTER, top, SUN_RAY_FRAMES[frame], rays[frame])
    draw_art(canvas, center_x - SUN_CENTER, top + 1, SUN_BODY, body, {":": inside})


def draw_moon(canvas, center_x, top):
    draw_art(canvas, center_x - MOON_CENTER, top, MOON_ART, MOON)


# ---------------------------------------------------------------------------------------------------------
# The scene


def draw_scene(canvas, x, y, width, height, info, t):
    """The big animated picture: sky, weather and a little landscape, filling the given area.

    `info` has the weather code, is_day, wind (km/h), temp (°C), sun_progress (0 at sunrise, 1 at sunset)
    and the month at the location."""
    code, day = info["code"], bool(info["is_day"])
    kind = kind_of(code)
    wind, temp, month = info.get("wind") or 0, info.get("temp"), info.get("month", 6)
    saved_clip = canvas.clip
    canvas.clip = (x, y, x + width, y + height)
    landscape = height >= 9 and width >= 30
    sky_rows = height - 4 if landscape else height
    cx = x + width // 2
    ground = y + height - 1
    drift = round(math.sin(t * 0.5) * 2)
    flash = kind == "thunder" and (t % 3.2 < 0.12 or 0.22 < t % 3.2 < 0.32)
    progress = info.get("sun_progress")
    progress = 0.5 if progress is None else min(1.0, max(0.0, progress))
    rise = math.sin(math.pi * progress)

    # Sky: stars, the sun or moon on its arc, clouds drifting far away.
    if kind in ("clear", "partly"):
        if not day:
            draw_stars(canvas, x, y, width, sky_rows, t)
        elif wind < 40:
            draw_birds(canvas, x, y, width, t)  # before the sun, so they fly behind it
        margin = 24 if landscape else 12
        if kind == "partly":
            body_x = cx - 9
        elif width >= 2 * margin + 10:
            body_x = x + margin + round(progress * (width - 2 * margin))
        else:
            body_x = cx
        if day:
            body_top = y + round((1 - rise) * max(0, sky_rows - 7))
            draw_sun(canvas, body_x, body_top, t, rise < 0.35)
        else:
            body_top = y + (1 if sky_rows > 6 else 0)
            draw_moon(canvas, body_x, body_top)
        if code != 0:
            draw_art(canvas, x + drifting(t, 1.0, 0.7, width), y, SMALL_CLOUD, (170, 178, 200) if day else (96, 100, 130))
        if kind == "partly":
            draw_cloud(canvas, body_x + 17 + drift, body_top + 2, "day" if day else "night")
    elif kind == "cloudy":
        for k in range(3):
            shade = mix((150, 158, 180), (90, 94, 120), k / 2) if day else mix((100, 104, 134), (70, 74, 100), k / 2)
            draw_art(canvas, x + drifting(t, 0.7 + k * 0.4, k * 0.37, width), y + k * 2 % 5, SMALL_CLOUD, shade)

    if landscape:
        draw_landscape(canvas, x, width, ground, kind, day, month, wind, temp, t)

    # Weather in front of the landscape. Clouds come after the drops, so drops never show inside a cloud.
    if kind not in ("clear", "partly"):
        top = y + max(0, (height - 12) // 3)
        bottom = ground if landscape else ground + 1
        draw_particles(canvas, kind, code, x, top + 2, width, bottom, wind, t, landscape)
        if kind != "cloudy":
            draw_art(canvas, x + drifting(t, 0.8, 0.2, width), top, SMALL_CLOUD, (120, 126, 150))
        if flash:
            draw_bolt(canvas, cx + random.Random(int(t / 3.2)).randint(-8, 8), top + 5, bottom, int(t / 3.2))
        if kind == "cloudy":
            draw_cloud(canvas, cx + drift, y + max(1, (height - 9) // 3), "day" if day else "night")
        elif flash:
            draw_cloud(canvas, cx + drift, top, "flash")
        elif kind == "thunder":
            draw_cloud(canvas, cx + drift, top, "thunder")
        elif kind in ("rain", "drizzle"):
            draw_cloud(canvas, cx + drift, top, "rain")
        else:
            draw_cloud(canvas, cx + drift, top, "day" if day else "night")
        if kind == "fog":
            draw_fog(canvas, x, width, top + 4, bottom, day, t)

    if wind >= 20:
        draw_wind(canvas, x, y, width, sky_rows, wind, t)
    canvas.clip = saved_clip


def draw_stars(canvas, x, y, width, rows, t):
    rng = random.Random(3)
    for _ in range(max(1, width * rows // 20)):
        sx, sy, phase = x + rng.randrange(width), y + rng.randrange(max(1, rows)), rng.random()
        color = rng.choice(STAR_COLORS)
        step = int(t * 1.5 + phase * 8) % 8
        char = "*" if step == 0 else "+" if step in (1, 7) else "."
        canvas.put(sx, sy, char, color if char != "." else (140, 150, 196))
    phase = t % 11  # a shooting star every 11 seconds
    if 0 < phase < 1.0:
        head_x, head_y = x + width - 6 - int(phase * 24), y + int(phase * 4)
        canvas.put(head_x, head_y, "*", (255, 255, 255))
        canvas.put(head_x + 1, head_y, "~-", (150, 160, 210))


def draw_birds(canvas, x, y, width, t):
    for k in range(3):
        bx = x + drifting(t, 3 + k * 0.8, k * 0.31, width) + k * 3
        by = y + 1 + k % 2 + round(math.sin(t * 2 + k) * 0.5)
        canvas.put(bx, by, "v" if int(t * 4 + k) % 2 else "-", (200, 206, 224))


def draw_landscape(canvas, x, width, ground, kind, day, month, wind, temp, t):
    """A meadow with grass and flowers, a house, a tree and a fence."""
    snowy = kind == "snow"
    wet = kind in ("rain", "drizzle", "thunder")
    if snowy:
        grass, darker = (240, 244, 252), (196, 206, 228)
    elif 3 <= month <= 5:
        grass, darker = (140, 214, 110), (96, 170, 80)
    elif 6 <= month <= 8:
        grass, darker = (112, 196, 92), (76, 150, 66)
    elif 9 <= month <= 11:
        grass, darker = (196, 180, 92), (156, 134, 62)
    else:
        grass, darker = (130, 160, 110), (96, 124, 84)
    if not day:
        grass, darker = at_night(grass), at_night(darker)

    # The meadow: a row of grass, blades swaying in the wind, flowers in the warm months.
    rng = random.Random(13)
    speed = 1.5 + wind / 10
    flowers = ((255, 150, 190), (255, 230, 110), (255, 255, 255), (190, 160, 255))
    for i in range(width):
        r, r2 = rng.random(), rng.random()
        if wet and math.sin(i * 0.35 + 1.0) > 0.6:  # puddles with ripples
            canvas.put(x + i, ground, "~" if (i + int(t * 3)) % 3 else "-", (150, 186, 240) if day else (80, 98, 150))
        else:
            canvas.put(x + i, ground, "~" if snowy else ",'.,`\""[int(r * 6)], grass if r2 < 0.5 else darker)
        if not snowy and 3 <= month <= 10 and r < 0.07:
            color = flowers[int(r2 * 4)]
            canvas.put(x + i, ground - 1, "*o@"[int(r2 * 3)], color if day else at_night(color))
        elif not snowy and r < 0.35:
            canvas.put(x + i, ground - 1, "/|\\|"[int(t * speed + i * 0.4) % 4], grass if r2 < 0.6 else darker)
        elif snowy and r < 0.15:
            canvas.put(x + i, ground - 1, ".", (200, 210, 235))

    house_x = x + 2
    draw_house(canvas, house_x, ground, day, snowy, temp is not None and temp < 12, wind, t)
    tree_x = x + width - 11
    draw_tree(canvas, tree_x, ground - 3, month, snowy, day)
    if width >= 50:
        fence = (236, 226, 204) if day else (110, 106, 112)
        canvas.put(house_x + 13, ground - 1, "^ ^ ^ ^ ^", fence)
        canvas.put(house_x + 13, ground, "|-|-|-|-|", fence)

    if 9 <= month <= 11 and not snowy:  # autumn leaves falling from the tree
        for k in range(2):
            p = (t * 0.25 + k * 0.5) % 1
            leaf_x = tree_x + 2 + k * 4 + round(math.sin(t * 2 + k) * 1.5) + int(p * wind / 5)
            color = ((240, 170, 60), (232, 104, 64))[k]
            canvas.put(leaf_x, ground - 1 + int(p * 2), "," if int(t * 3 + k) % 2 else "'", color)
    if not day and not wet and not snowy and temp is not None and temp > 10:  # fireflies on warm nights
        rng = random.Random(17)
        for k in range(5):
            base, phase = x + rng.randrange(width), rng.random() * 6.3
            if math.sin(t * 2.5 + phase * 3) > 0.2:
                fx = base + round(math.sin(t * 0.6 + phase) * 3)
                fy = ground - 2 - round(math.sin(t * 0.9 + phase * 2) + 1)
                canvas.put(fx, fy, ".", (255, 240, 120) if k % 2 else (190, 255, 140))


def draw_house(canvas, x, ground, day, snowy, cold, wind, t):
    top = ground - 3
    roof = [(240, 244, 252), (240, 244, 252), (196, 206, 228)] if snowy else [(150, 150, 160), (232, 108, 100), (196, 80, 80)]
    walls = (236, 214, 170)
    window = (176, 216, 246) if day else (255, 214, 110)  # the lights are on at night
    if not day:
        roof, walls = [at_night(color) for color in roof], at_night(walls)
    draw_art(canvas, x, top, HOUSE[:3], roof)
    draw_art(canvas, x, top + 3, HOUSE[3:], walls, {"[": window, "]": window, "∩": (196, 140, 96)})
    if cold:  # smoke from the chimney, blown sideways by the wind
        for k in range(4):
            p = (t * 0.45 + k / 4) % 1
            canvas.put(x + 5 + int(p * (2 + wind / 8)), top - 1 - int(p * 4), ".~~'"[min(3, int(p * 4))],
                       mix((235, 235, 240), (130, 136, 156), p))


def draw_tree(canvas, x, top, month, snowy, day):
    if 3 <= month <= 5:
        leaves = ((132, 212, 112), (255, 176, 206), (104, 190, 92))  # blossoms
    elif 6 <= month <= 8:
        leaves = ((92, 182, 82), (124, 204, 104), (70, 150, 66))
    elif 9 <= month <= 11:
        leaves = ((242, 172, 62), (232, 112, 62), (252, 212, 92))
    else:
        leaves = ((82, 132, 96), (112, 152, 122))
    rng = random.Random(21)
    for dy, row in enumerate(TREE):
        start = len(row) - len(row.lstrip())
        for dx in range(start, len(row)):
            color = (248, 250, 255) if snowy and dy == 0 else rng.choice(leaves)
            canvas.put(x + dx, top + dy, rng.choice("@@&"), color if day else at_night(color))
    canvas.put(x + 3, top + 3, "/|\\", (170, 120, 78) if day else (80, 62, 48))


def draw_particles(canvas, kind, code, x, y, width, bottom, wind, t, landscape):
    """Rain, drizzle or snow over the whole width, with splashes where the rain lands."""
    rows = bottom - y
    if rows <= 0:
        return
    density = 2.0 if code in HEAVY else 0.5 if code in LIGHT else 1.0
    if kind == "snow":
        for place, fallen, extra in falling(int(width * rows / 10 * density), 5, rows, t, 1.6):
            sway = round(math.sin(t * 1.3 + extra * 6.3) * 1.2) + int(fallen * wind / 40)
            char = "*" if extra < 0.4 else "+" if extra < 0.6 else "."
            canvas.put(x + (int(place * width) + sway) % width, y + fallen, char, SNOW if extra < 0.6 else (190, 220, 255))
    elif kind in ("rain", "thunder", "drizzle"):
        drizzle = kind == "drizzle" or code in LIGHT
        slant = 1 if wind > 25 else 2
        count = int(width * rows / (16 if drizzle else 6) * density)
        for place, fallen, extra in falling(count, 7, rows, t, 5 if drizzle else 11):
            color = mix(DRIZZLE if drizzle else RAIN, (255, 255, 255), extra * 0.35)
            canvas.put(x + (int(place * width) - fallen // slant) % width, y + fallen, "'" if drizzle else "/", color)
        if landscape:
            rng = random.Random(8)
            for _ in range(width // 6):  # splashes
                sx, phase = x + rng.randrange(width), rng.random()
                p = (t * 1.8 + phase) % 1
                if p < 0.75:
                    canvas.put(sx - (p >= 0.5), bottom - 1, (".", "o", "' '")[int(p * 4)], (190, 220, 255))


def draw_bolt(canvas, bolt_x, top, bottom, seed):
    """A zigzag lightning bolt, different every strike."""
    rng = random.Random(seed)
    for row in range(top, bottom):
        step = rng.choice((-1, 0, 1, 1))
        canvas.put(bolt_x, row, "/" if step < 0 else "\\" if step > 0 else "|", BOLT)
        if row == top + 2:
            canvas.put(bolt_x - 2, row + 1, "/", (255, 210, 90))
            canvas.put(bolt_x - 3, row + 2, "/", (255, 210, 90))
        bolt_x += step


def draw_fog(canvas, x, width, top, bottom, day, t):
    """Bands of fog drifting both ways, with gaps so the landscape shows through."""
    for row in range(top, bottom + 1):
        shift = t * (0.8 + (row % 3) * 0.4) * (1 if row % 2 else -1)
        for i in range(width):
            v = math.sin((i + shift) * 0.25 + row * 1.7) + math.sin((i - shift) * 0.11 + row)
            if v > 0.6:
                color = (232, 234, 240) if v > 1.3 else (176, 180, 192)
                canvas.put(x + i, row, "~" if v > 1.1 else "-", color if day else at_night(color))


def draw_wind(canvas, x, y, width, sky_rows, wind, t):
    for k in range(3 if wind > 35 else 2):
        sx = x + drifting(t, 14 + wind / 3, k * 0.41, width)
        canvas.put(sx, y + 1 + (k * 3) % max(1, sky_rows), "~~ ~~~" if k % 2 else "- ~~~", (200, 208, 226))


# ---------------------------------------------------------------------------------------------------------
# Loading and error screens


def draw_loading(canvas, t):
    top = max(0, (canvas.height - 12) // 2)
    center_x = canvas.width // 2
    draw_cloud(canvas, center_x, top + 1 + round(math.sin(t * 4)), "day")
    canvas.center(0, top + 8, canvas.width, "fetching the weather", "white")
    colors = ((255, 218, 100), (120, 212, 255), (255, 150, 190), (150, 230, 140), (190, 160, 255))
    for i, color in enumerate(colors):  # a wave of bouncing dots
        lift = 1 if math.sin(t * 6 - i * 0.9) > 0.4 else 0
        canvas.put(center_x - 4 + i * 2, top + 10 - lift, "•", color)


def draw_error(canvas, message, t):
    top = max(0, (canvas.height - 12) // 2)
    center_x = canvas.width // 2
    draw_cloud(canvas, center_x, top + 1, "rain")
    for k, dx in enumerate((-6, -1, 4)):  # a few drops
        canvas.put(center_x + dx, top + 6 + int(t * 3 + k) % 2, "'", DRIZZLE)
    canvas.center(0, top + 9, canvas.width, message, "bright_white")
    canvas.center(0, top + 11, canvas.width, "press any key to go back", "gray")


# ---------------------------------------------------------------------------------------------------------
# Mini icons and the big temperature


def mini_icon(canvas, x, y, code, is_day, t=0):
    """A small 4-row ASCII icon, at most 10 columns wide. Rain, snow and the sun's rays move a little."""
    kind = kind_of(code)
    frame = int(t * 2) % 2
    cloud = [(244, 246, 252), (214, 220, 234), (170, 178, 200)] if is_day else [(176, 180, 210), (150, 154, 188), (120, 124, 160)]
    if kind in ("clear", "partly"):
        shift = -3 if kind == "partly" else 0
        if is_day:
            draw_art(canvas, x + shift, y, MINI_SUN[frame], SUN_RAYS[frame], {"O": SUN})
        else:
            canvas.put(x + 8, y, "*+"[frame], (255, 255, 255))
            canvas.put(x, y + 2, "+*"[frame], (186, 222, 255))
            draw_art(canvas, x + shift, y, MINI_MOON, MOON)
        if kind == "partly":
            draw_art(canvas, x + 3, y + 1, MINI_CLOUD, cloud)
    elif kind == "cloudy":
        draw_art(canvas, x + 3, y, MINI_CLOUD[:2], (150, 156, 178) if is_day else (100, 104, 134))
        draw_art(canvas, x, y + 1, MINI_CLOUD, cloud)
    elif kind == "fog":
        for row in range(4):
            line = (" _ - _ -", "  - _ - _")[(row + frame) % 2]
            canvas.put(x, y + row, line, (220, 222, 230) if row % 2 else (170, 174, 188))
    else:
        if kind == "thunder":
            cloud = [(150, 150, 172), (126, 126, 150), (100, 100, 126)]
        elif kind in ("rain", "drizzle"):
            cloud = [(200, 206, 222), (176, 182, 202), (146, 152, 176)]
        draw_art(canvas, x, y, MINI_CLOUD, cloud)
        if kind == "drizzle":
            canvas.put(x + 2, y + 3, ("'   '", "  '   '")[frame], DRIZZLE)
        elif kind == "rain":
            canvas.put(x + 1, y + 3, (" / / / /", "/ / / / ")[frame], RAIN)
        elif kind == "snow":
            canvas.put(x + 2, y + 3, ("* . *", ". * . *")[frame], SNOW)
        elif kind == "thunder":
            canvas.put(x + 1, y + 3, "'     '", RAIN)
            draw_art(canvas, x + 3, y + 2, [" /", "/"], BOLT if frame else (255, 200, 80))


def big_text(canvas, x, y, text, color):
    """Draw text in 4-row ASCII digits (digits, minus, ° and C/F). Returns the width used."""
    start = x
    for char in text:
        glyph = DIGITS.get(char, DIGITS["-"])
        for row, part in enumerate(glyph):
            canvas.put(x, y + row, part, color)
        x += len(glyph[0])
    return x - start
