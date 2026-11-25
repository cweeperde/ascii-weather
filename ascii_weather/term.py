"""Terminal helpers: fullscreen mode, key input and a small canvas that is drawn in one go."""

import functools
import os
import shutil
import sys
import time

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty

COLORS = {
    "black": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36, "white": 37,
    "gray": 90, "bright_red": 91, "bright_green": 92, "bright_yellow": 93, "bright_blue": 94,
    "bright_magenta": 95, "bright_cyan": 96, "bright_white": 97,
}

KEYS = {"\r": "enter", "\n": "enter", "\x1b": "esc", "\x08": "backspace", "\x7f": "backspace"}
WINDOWS_ARROWS = {"H": "up", "P": "down", "K": "left", "M": "right"}
POSIX_ARROWS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left", "OA": "up", "OB": "down", "OC": "right", "OD": "left"}


def size():
    return shutil.get_terminal_size((80, 24))


def write(text):
    sys.stdout.write(text)
    sys.stdout.flush()


class Canvas:
    """A grid of characters with one text color each: an ANSI name like "bright_cyan" or an (r, g, b) tuple.
    There are no background colors, so the terminal's own background (even a transparent one) shows
    everywhere. Drawing outside the grid (or the clip area) is ignored."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.chars = [[" "] * width for _ in range(height)]
        self.colors = [[None] * width for _ in range(height)]
        self.clip = (0, 0, width, height)

    def put(self, x, y, text, color=None):
        left, top, right, bottom = self.clip
        if not top <= y < bottom:
            return
        for i, char in enumerate(text):
            if left <= x + i < right:
                self.chars[y][x + i] = char
                self.colors[y][x + i] = color

    def center(self, x, y, width, text, color=None):
        self.put(x + (width - len(text)) // 2, y, text, color)

    def box(self, x, y, width, height, color=None):
        self.put(x, y, "╭" + "─" * (width - 2) + "╮", color)
        for row in range(y + 1, y + height - 1):
            self.put(x, row, "│", color)
            self.put(x + width - 1, row, "│", color)
        self.put(x, y + height - 1, "╰" + "─" * (width - 2) + "╯", color)

    def divider(self, y, title, color=None, title_color="white"):
        """A horizontal line across a full-width box, with a title in it."""
        self.put(0, y, "├" + "─" * (self.width - 2) + "┤", color)
        self.put(2, y, f" • {title} • ", title_color)

    def lines(self):
        out = []
        for chars, colors in zip(self.chars, self.colors):
            parts = []
            current = "unset"
            for char, color in zip(chars, colors):
                if color != current:
                    parts.append(style(color))
                    current = color
                parts.append(char)
            out.append("".join(parts))
        return out


@functools.lru_cache(maxsize=None)
def style(color):
    """Escape code for a text color (ANSI name or (r, g, b), None for the default)."""
    if isinstance(color, tuple):
        return f"\x1b[0;38;2;{color[0]};{color[1]};{color[2]}m"
    if color:
        return f"\x1b[0;{COLORS[color]}m"
    return "\x1b[0m"


class Screen:
    """Fullscreen mode on the terminal's alternate screen. Leaving it brings back the console as it was."""

    def __enter__(self):
        self.restore_mode = None
        if os.name == "nt":
            self.restore_mode = enable_ansi_on_windows()
            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            self.saved_tty = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        # Alternate screen, hidden cursor, no line wrap (so writing the last column never scrolls the screen).
        write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J")
        self.last_lines = []
        self.last_size = None
        return self

    def __exit__(self, *exc):
        write("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
        if os.name == "nt":
            if self.restore_mode:
                self.restore_mode()
        else:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.saved_tty)
        return False

    def draw(self, canvas):
        out = ["\x1b[?2026h"]  # synchronized output: terminals that know it show the frame at once
        if (canvas.width, canvas.height) != self.last_size:
            out.append("\x1b[2J")
            self.last_lines = []
            self.last_size = (canvas.width, canvas.height)
        lines = canvas.lines()
        for y, line in enumerate(lines):
            if y >= len(self.last_lines) or self.last_lines[y] != line:
                out.append(f"\x1b[{y + 1};1H{line}")
        out.append("\x1b[0m\x1b[?2026l")
        write("".join(out))
        self.last_lines = lines


def enable_ansi_on_windows():
    """Turn on escape-code support in the classic Windows console. Returns a function that undoes it."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    handle = kernel32.GetStdHandle(-11)
    mode = wintypes.DWORD()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return None
    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    return lambda: kernel32.SetConsoleMode(handle, mode.value)


def get_key(timeout):
    """Wait up to `timeout` seconds for a key. Returns a name like "up" or "enter", the typed character, or None."""
    if os.name == "nt":
        deadline = time.monotonic() + timeout
        while not msvcrt.kbhit():
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)
        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            return WINDOWS_ARROWS.get(msvcrt.getwch(), "other")
        return KEYS.get(char, char)

    fd = sys.stdin.fileno()
    if not select.select([fd], [], [], timeout)[0]:
        return None
    char = os.read(fd, 1).decode(errors="ignore")
    if char != "\x1b":
        return KEYS.get(char, char)
    sequence = ""
    while len(sequence) < 4 and select.select([fd], [], [], 0.02)[0]:
        sequence += os.read(fd, 1).decode(errors="ignore")
    return POSIX_ARROWS.get(sequence, "esc" if not sequence else "other")
