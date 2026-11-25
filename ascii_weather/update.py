"""Update notice: checks GitHub for a new version at most once a day, and after the weather screen closes
prints a note with the command to update (like pip does)."""

import importlib.metadata
import json
import re
import threading
import time
import urllib.request

from . import api, settings

UPDATE_COMMAND = "pip install --upgrade git+https://github.com/cweeperde/ascii-weather"
VERSION_URL = "https://raw.githubusercontent.com/cweeperde/ascii-weather/main/pyproject.toml"
DAY = 24 * 60 * 60


def installed_version():
    try:
        return importlib.metadata.version("ascii-weather")
    except importlib.metadata.PackageNotFoundError:
        return None


def is_editable_install():
    """True after 'pip install -e .': the working copy is the newest version, so there is nothing to suggest."""
    try:
        info = importlib.metadata.distribution("ascii-weather").read_text("direct_url.json")
        return bool(info and json.loads(info).get("dir_info", {}).get("editable"))
    except (importlib.metadata.PackageNotFoundError, ValueError):
        return False


def parse_version(text):
    return tuple(int(part) for part in re.findall(r"\d+", text))


class UpdateCheck:
    """Looks up the newest version in a background thread while the weather is on screen. The result is kept in
    the config, so the notice shows on every exit until the update is installed, but GitHub is asked only daily."""

    def __init__(self, config):
        self.config = config
        self.current = installed_version()
        self.thread = None
        due = time.time() - config.get("last_update_check", 0) > DAY
        if due and self.current and not is_editable_install():
            self.thread = threading.Thread(target=self.check, daemon=True)
            self.thread.start()

    def check(self):
        try:
            request = urllib.request.Request(VERSION_URL, headers=api.HEADERS)
            with urllib.request.urlopen(request, timeout=10) as response:
                text = response.read().decode("utf-8", errors="ignore")
        except OSError:
            return  # offline, or the repo isn't public: try again next time
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            self.config["latest_version"] = match.group(1)
        self.config["last_update_check"] = time.time()

    def finish(self):
        """Call after leaving fullscreen: saves what the check found and prints the notice if there is an update."""
        if self.thread is not None and not self.thread.is_alive():
            settings.save_config(self.config)
        latest = self.config.get("latest_version")
        if self.current and latest and not is_editable_install() and parse_version(latest) > parse_version(self.current):
            print(f"[notice] A new release of ascii-weather is available: {self.current} -> {latest}")
            print(f"[notice] To update, run: {UPDATE_COMMAND}")
