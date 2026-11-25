"""Location and weather data. Uses ipinfo.io and Open-Meteo, both free and without API keys."""

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HEADERS = {"User-Agent": "ascii-weather", "Accept": "application/json"}
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
POLLEN = ["alder", "birch", "grass", "mugwort", "olive", "ragweed"]


class WeatherError(Exception):
    """An error whose message can be shown to the user as it is."""


def get_json(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def locate_by_ip():
    try:
        data = get_json("https://ipinfo.io/json")
        lat, lon = (float(value) for value in data["loc"].split(","))
    except (OSError, ValueError, KeyError) as error:
        raise WeatherError(
            "Couldn't find your location. Try 'weather <city>' or set a home location in 'weather settings'."
        ) from error
    name = ", ".join(part for part in (data.get("city"), data.get("country")) if part)
    return {"name": name or "Your location", "lat": lat, "lon": lon}


def search_city(query):
    """Best match for a city name, or None. Text after a comma ("Paris, Texas") picks the country or region."""
    name, _, region = (part.strip() for part in query.partition(","))
    params = {"name": name, "count": 10, "language": "en", "format": "json"}
    results = get_json(GEOCODING_URL, params).get("results") or []
    if region:
        wanted = region.lower()
        matches = [
            place for place in results
            if any(str(place.get(key, "")).lower().startswith(wanted) for key in ("country", "country_code", "admin1"))
        ]
        results = matches or results
    if not results:
        return None
    best = results[0]
    label = ", ".join(part for part in (best.get("name"), best.get("country")) if part)
    return {"name": label, "lat": best["latitude"], "lon": best["longitude"]}


def get_weather(query, config):
    """Everything the weather screen needs, for a city name or (if empty) the home or IP location."""
    try:
        if query:
            place = search_city(query)
            if place is None:
                raise WeatherError(f"Couldn't find a place called '{query}'.")
        else:
            place = config.get("home") or locate_by_ip()

        imperial = config.get("units") == "imperial"
        forecast_params = {
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,"
                       "wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                     "sunrise,sunset,uv_index_max",
            "timezone": "auto",
            "forecast_days": 7,
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
        }
        air_params = {
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": "european_aqi," + ",".join(f"{kind}_pollen" for kind in POLLEN),
            "timezone": "auto",
        }
        with ThreadPoolExecutor(2) as pool:
            forecast_job = pool.submit(get_json, FORECAST_URL, forecast_params)
            air_job = pool.submit(get_json, AIR_URL, air_params)
            forecast = forecast_job.result()
            try:
                air = air_job.result().get("current")
            except (OSError, ValueError):
                air = None  # air quality is a nice extra, the weather still works without it
    except (OSError, ValueError) as error:
        raise WeatherError("Can't reach the weather service. Are you online?") from error

    return {
        "place": place["name"],
        "imperial": imperial,
        "utc_offset": forecast.get("utc_offset_seconds", 0),
        "current": forecast["current"],
        "hourly": forecast["hourly"],
        "daily": forecast["daily"],
        "air": air,
    }
