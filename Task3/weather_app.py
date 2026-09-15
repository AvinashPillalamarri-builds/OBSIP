"""
WeatherNow - Production-Quality Desktop Weather Application
Built with Python 3, Tkinter, Pillow, Requests, and python-dotenv.
Includes India State -> District Cascading Dropdowns & OpenWeatherMap Geocoding API integration.
"""

import os
import sys
import json
import threading
import datetime
from typing import Dict, List, Tuple, Optional, Any

import requests
from PIL import Image, ImageTk
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk

# Load environment variables from .env file
load_dotenv()

# --- CONSTANTS & CONFIGURATION ---
DEFAULT_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
BASE_URL_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
BASE_URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
BASE_URL_GEO = "https://api.openweathermap.org/geo/1.0/direct"
IPINFO_URL = "https://ipinfo.io/json"
ICON_URL_TEMPLATE = "https://openweathermap.org/img/wn/{}@2x.png"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(PROJECT_ROOT, "assets", "weather_icons")
INDIA_LOCATIONS_FILE = os.path.join(PROJECT_ROOT, "india_locations.json")

os.makedirs(CACHE_DIR, exist_ok=True)

# Theme Palette (Modern Dark Slate)
COLOR_BG = "#0F172A"          # Deep Slate background
COLOR_SURFACE = "#1E293B"     # Card background
COLOR_SURFACE_ALT = "#334155" # Secondary card / border
COLOR_ACCENT = "#38BDF8"      # Bright Sky Blue accent
COLOR_ACCENT_HOVER = "#0284C7"# Sky Blue Hover
COLOR_TEMP_WARM = "#F59E0B"   # Warm amber temperature
COLOR_TEXT_PRIMARY = "#F8FAFC" # White text
COLOR_TEXT_MUTED = "#94A3B8"  # Muted slate text
COLOR_ERROR_BG = "#7F1D1D"    # Dark red banner
COLOR_ERROR_TEXT = "#FEE2E2"  # Light red text
COLOR_SUCCESS_BG = "#064E3B"  # Dark green banner
COLOR_SUCCESS_TEXT = "#D1FAE5"

FONT_HEADER = ("Segoe UI", 18, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_BIG_TEMP = ("Segoe UI", 36, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
FONT_BODY = ("Segoe UI", 10)
FONT_BODY_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)

# Fallback Emoji mapping for weather conditions if icon fails to load
WEATHER_EMOJI_MAP = {
    "01d": "☀️", "01n": "🌙",
    "02d": "🌤️", "02n": "☁️",
    "03d": "☁️", "03n": "☁️",
    "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️",
    "10d": "🌦️", "10n": "🌧️",
    "11d": "⛈️", "11n": "⛈️",
    "13d": "❄️", "13n": "❄️",
    "50d": "🌫️", "50n": "🌫️",
}


class WeatherAPIError(Exception):
    """Custom exception for user-friendly API error messages."""
    pass


class LocationDataLoader:
    """Loads and manages Indian state and district location data."""

    @staticmethod
    def load_india_locations() -> Dict[str, List[str]]:
        """Loads india_locations.json dataset."""
        if not os.path.exists(INDIA_LOCATIONS_FILE):
            return {}
        try:
            with open(INDIA_LOCATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            return {}


class WeatherAPIClient:
    """Handles network requests to OpenWeatherMap (Geocoding, Weather, Forecast) and ipinfo.io."""

    @staticmethod
    def geocode_location(query: str, api_key: str) -> Optional[Tuple[float, float, str, str]]:
        """
        Geocodes a location query using OpenWeatherMap Direct Geocoding API.
        Returns tuple: (lat, lon, display_name, state_country_str) or None.
        """
        try:
            resp = requests.get(
                BASE_URL_GEO,
                params={"q": query, "limit": 1, "appid": api_key},
                timeout=8
            )
            if resp.status_code == 200:
                results = resp.json()
                if results and isinstance(results, list):
                    item = results[0]
                    lat = item.get("lat")
                    lon = item.get("lon")
                    name = item.get("name", "")
                    state = item.get("state", "")
                    country = item.get("country", "")

                    region_parts = [p for p in [state, country] if p]
                    region_str = ", ".join(region_parts)
                    return lat, lon, name, region_str
        except Exception:
            pass
        return None

    @classmethod
    def fetch_weather_by_coords(cls, lat: float, lon: float, api_key: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Fetches current weather and 5-day forecast by coordinates."""
        try:
            curr_resp = requests.get(
                BASE_URL_CURRENT,
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                timeout=10
            )
        except requests.exceptions.Timeout:
            raise WeatherAPIError("Request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            raise WeatherAPIError("Unable to connect to the weather service. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            raise WeatherAPIError(f"Network error: {str(e)}")

        if curr_resp.status_code == 401:
            raise WeatherAPIError("Invalid API key. Please check your OpenWeatherMap API key.")
        elif curr_resp.status_code != 200:
            raise WeatherAPIError(f"API Error ({curr_resp.status_code}): Could not retrieve current weather.")

        try:
            fore_resp = requests.get(
                BASE_URL_FORECAST,
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                timeout=10
            )
        except requests.exceptions.Timeout:
            raise WeatherAPIError("Request timed out fetching forecast data.")
        except requests.exceptions.ConnectionError:
            raise WeatherAPIError("Network connection lost while fetching forecast data.")
        except requests.exceptions.RequestException as e:
            raise WeatherAPIError(f"Network error fetching forecast: {str(e)}")

        if fore_resp.status_code != 200:
            raise WeatherAPIError(f"API Error ({fore_resp.status_code}): Could not retrieve forecast data.")

        return curr_resp.json(), fore_resp.json()

    @classmethod
    def fetch_weather_by_city_query(cls, city: str, api_key: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Fallback method to fetch weather directly by city query."""
        if not city or not city.strip():
            raise WeatherAPIError("Please enter a city name.")

        if not api_key or api_key == "YOUR_OPENWEATHERMAP_API_KEY":
            raise WeatherAPIError("Invalid API key. Please check your OpenWeatherMap API key.")

        try:
            curr_resp = requests.get(
                BASE_URL_CURRENT,
                params={"q": city.strip(), "appid": api_key, "units": "metric"},
                timeout=10
            )
        except requests.exceptions.Timeout:
            raise WeatherAPIError("Request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            raise WeatherAPIError("Unable to connect to the weather service. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            raise WeatherAPIError(f"Network error: {str(e)}")

        if curr_resp.status_code == 404:
            raise WeatherAPIError("City not found. Please check the city name.")
        elif curr_resp.status_code == 401:
            raise WeatherAPIError("Invalid API key. Please check your OpenWeatherMap API key.")
        elif curr_resp.status_code != 200:
            raise WeatherAPIError(f"API Error ({curr_resp.status_code}): Could not retrieve current weather.")

        try:
            fore_resp = requests.get(
                BASE_URL_FORECAST,
                params={"q": city.strip(), "appid": api_key, "units": "metric"},
                timeout=10
            )
        except requests.exceptions.Timeout:
            raise WeatherAPIError("Request timed out fetching forecast data.")
        except requests.exceptions.ConnectionError:
            raise WeatherAPIError("Network connection lost while fetching forecast data.")
        except requests.exceptions.RequestException as e:
            raise WeatherAPIError(f"Network error fetching forecast: {str(e)}")

        if fore_resp.status_code != 200:
            raise WeatherAPIError(f"API Error ({fore_resp.status_code}): Could not retrieve forecast data.")

        return curr_resp.json(), fore_resp.json()

    @staticmethod
    def detect_user_location() -> Optional[str]:
        """Attempts to auto-detect user's city via ipinfo.io."""
        try:
            resp = requests.get(IPINFO_URL, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                city = data.get("city")
                if city:
                    return city
        except Exception:
            pass
        return None


class WeatherDataProcessor:
    """Transforms raw API responses into structured data for the GUI."""

    @staticmethod
    def c_to_f(celsius: float) -> float:
        """Converts Celsius to Fahrenheit."""
        return (celsius * 9 / 5) + 32

    @staticmethod
    def ms_to_mph(ms: float) -> float:
        """Converts m/s to mph."""
        return ms * 2.23694

    @classmethod
    def process_current(cls, raw: Dict[str, Any], custom_title: Optional[str] = None, custom_subtitle: Optional[str] = None) -> Dict[str, Any]:
        """Parses current weather data, allowing optional display overrides for state/district."""
        main = raw.get("main", {})
        weather_list = raw.get("weather", [{}])
        weather = weather_list[0] if weather_list else {}
        wind = raw.get("wind", {})
        sys_data = raw.get("sys", {})

        temp_c = main.get("temp", 0.0)
        feels_c = main.get("feels_like", temp_c)
        wind_ms = wind.get("speed", 0.0)

        city_name = custom_title or raw.get("name", "Unknown City")
        country_code = sys_data.get("country", "")
        region_subtitle = custom_subtitle or country_code

        return {
            "city": city_name,
            "subtitle": region_subtitle,
            "temp_c": temp_c,
            "temp_f": cls.c_to_f(temp_c),
            "feels_c": feels_c,
            "feels_f": cls.c_to_f(feels_c),
            "condition": weather.get("main", "Clear"),
            "description": weather.get("description", "").title(),
            "humidity": main.get("humidity", 0),
            "wind_ms": wind_ms,
            "wind_mph": cls.ms_to_mph(wind_ms),
            "icon_code": weather.get("icon", "01d"),
        }

    @classmethod
    def process_hourly(cls, raw_forecast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts the next 6 forecast slots (3-hour steps)."""
        hourly = []
        entries = raw_forecast.get("list", [])[:6]

        for item in entries:
            dt_txt = item.get("dt_txt", "")
            dt_obj = None
            if dt_txt:
                try:
                    dt_obj = datetime.datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            if not dt_obj:
                dt_obj = datetime.datetime.fromtimestamp(item.get("dt", 0))

            time_str = dt_obj.strftime("%I %p").lstrip("0")  # e.g. "3 PM"

            main = item.get("main", {})
            weather_list = item.get("weather", [{}])
            weather = weather_list[0] if weather_list else {}
            temp_c = main.get("temp", 0.0)

            hourly.append({
                "time": time_str,
                "temp_c": temp_c,
                "temp_f": cls.c_to_f(temp_c),
                "condition": weather.get("main", "Clear"),
                "description": weather.get("description", "").title(),
                "icon_code": weather.get("icon", "01d")
            })

        return hourly

    @classmethod
    def process_daily(cls, raw_forecast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Groups 3-hour forecasts by date to generate a 5-day daily forecast."""
        daily_map: Dict[str, List[Dict[str, Any]]] = {}

        for item in raw_forecast.get("list", []):
            dt_txt = item.get("dt_txt", "")
            if dt_txt:
                date_key = dt_txt.split(" ")[0]
            else:
                date_key = datetime.datetime.fromtimestamp(item.get("dt", 0)).strftime("%Y-%m-%d")

            if date_key not in daily_map:
                daily_map[date_key] = []
            daily_map[date_key].append(item)

        daily_results = []
        sorted_dates = sorted(daily_map.keys())

        for date_str in sorted_dates:
            if len(daily_results) >= 5:
                break

            slots = daily_map[date_str]
            temps = [s.get("main", {}).get("temp", 0.0) for s in slots]
            max_c = max(temps) if temps else 0.0
            min_c = min(temps) if temps else 0.0

            # Select representative midday weather slot
            midday_slot = slots[len(slots) // 2]
            for slot in slots:
                if "12:00:00" in slot.get("dt_txt", "") or "15:00:00" in slot.get("dt_txt", ""):
                    midday_slot = slot
                    break

            weather_list = midday_slot.get("weather", [{}])
            weather = weather_list[0] if weather_list else {}

            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            day_name = date_obj.strftime("%a").upper()

            daily_results.append({
                "date": date_str,
                "day_name": day_name,
                "max_c": max_c,
                "max_f": cls.c_to_f(max_c),
                "min_c": min_c,
                "min_f": cls.c_to_f(min_c),
                "condition": weather.get("main", "Clear"),
                "icon_code": weather.get("icon", "01d")
            })

        return daily_results


class IconManager:
    """Manages icon downloading, disk caching, and resizing with Pillow."""

    def __init__(self):
        self._memory_cache: Dict[Tuple[str, int, int], ImageTk.PhotoImage] = {}

    def get_icon(self, icon_code: str, size: Tuple[int, int] = (50, 50)) -> Tuple[Optional[ImageTk.PhotoImage], str]:
        """
        Retrieves PhotoImage for icon_code resized to `size`.
        Returns tuple: (ImageTk.PhotoImage or None, fallback_emoji_str).
        """
        fallback_emoji = WEATHER_EMOJI_MAP.get(icon_code, "🌤️")
        cache_key = (icon_code, size[0], size[1])

        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key], fallback_emoji

        filepath = os.path.join(CACHE_DIR, f"{icon_code}.png")

        # Download if not cached on disk
        if not os.path.exists(filepath):
            url = ICON_URL_TEMPLATE.format(icon_code)
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
            except Exception:
                pass

        if os.path.exists(filepath):
            try:
                img = Image.open(filepath).convert("RGBA")
                img = img.resize(size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._memory_cache[cache_key] = photo
                return photo, fallback_emoji
            except Exception:
                pass

        return None, fallback_emoji


class WeatherNowApp(tk.Tk):
    """Main Application GUI Window."""

    def __init__(self):
        super().__init__()
        self.title("WeatherNow - Real-Time Weather")
        self.geometry("740x920")
        self.minsize(700, 840)
        self.configure(bg=COLOR_BG)

        # State Variables
        self.api_key = DEFAULT_API_KEY
        self.unit = "C"  # "C" or "F"
        self.current_data: Optional[Dict[str, Any]] = None
        self.hourly_data: List[Dict[str, Any]] = []
        self.daily_data: List[Dict[str, Any]] = []

        self.india_locations = LocationDataLoader.load_india_locations()
        self.icon_manager = IconManager()

        # Build UI Components
        self._create_styles()
        self._build_header()
        self._build_location_selector()
        self._build_banner()
        self._build_main_content()

        # Start auto-location detection in background
        self.after(500, self._async_detect_location)

    def _create_styles(self):
        """Sets up ttk styles for widgets and comboboxes."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Card.TFrame", background=COLOR_SURFACE, relief="flat")

        # Style Comboboxes for Dark Slate Theme
        style.configure(
            "TCombobox",
            fieldbackground=COLOR_SURFACE,
            background=COLOR_SURFACE_ALT,
            foreground=COLOR_TEXT_PRIMARY,
            darkcolor=COLOR_SURFACE_ALT,
            lightcolor=COLOR_SURFACE_ALT,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_TEXT_PRIMARY,
            bordercolor=COLOR_SURFACE_ALT,
            arrowcolor=COLOR_TEXT_PRIMARY
        )
        style.map("TCombobox", fieldbackground=[("readonly", COLOR_SURFACE)])

    def _build_header(self):
        """Top Header section with logo, title, and unit toggle."""
        header_frame = tk.Frame(self, bg=COLOR_BG)
        header_frame.pack(fill="x", padx=20, pady=(15, 8))

        title_box = tk.Frame(header_frame, bg=COLOR_BG)
        title_box.pack(side="left")

        app_title = tk.Label(
            title_box,
            text="🌦️ WeatherNow",
            font=FONT_HEADER,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG
        )
        app_title.pack(anchor="w")

        subtitle = tk.Label(
            title_box,
            text="Real-Time Weather Information & Forecasts",
            font=FONT_SUBTITLE,
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG
        )
        subtitle.pack(anchor="w")

        # Unit Toggle Button (°C / °F)
        self.btn_unit_toggle = tk.Button(
            header_frame,
            text="°C / °F",
            font=FONT_BODY_BOLD,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SURFACE_ALT,
            activebackground=COLOR_ACCENT,
            activeforeground=COLOR_TEXT_PRIMARY,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=6,
            command=self._toggle_unit
        )
        self.btn_unit_toggle.pack(side="right")

    def _build_location_selector(self):
        """Builds India State -> District Cascading Dropdowns & Manual City Search."""
        loc_container = tk.Frame(self, bg=COLOR_BG)
        loc_container.pack(fill="x", padx=20, pady=5)

        card = tk.Frame(loc_container, bg=COLOR_SURFACE, bd=1, relief="solid", pady=10, padx=15)
        card.pack(fill="x")

        # Title
        tk.Label(
            card,
            text="📍 Select Location",
            font=FONT_BODY_BOLD,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SURFACE
        ).pack(anchor="w", pady=(0, 6))

        # Dropdowns Frame (Grid layout)
        dd_frame = tk.Frame(card, bg=COLOR_SURFACE)
        dd_frame.pack(fill="x")
        dd_frame.columnconfigure(0, weight=1)
        dd_frame.columnconfigure(1, weight=1)

        # State Label & Combobox
        tk.Label(dd_frame, text="State / UT", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE).grid(row=0, column=0, sticky="w", padx=4)
        state_list = sorted(list(self.india_locations.keys()))
        self.cb_state = ttk.Combobox(dd_frame, values=state_list, state="readonly", font=FONT_BODY)
        self.cb_state.set("Select State")
        self.cb_state.grid(row=1, column=0, sticky="ew", padx=4, pady=(2, 6))
        self.cb_state.bind("<<ComboboxSelected>>", self._on_state_selected)

        # District Label & Combobox
        tk.Label(dd_frame, text="District", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE).grid(row=0, column=1, sticky="w", padx=4)
        self.cb_district = ttk.Combobox(dd_frame, values=[], state="disabled", font=FONT_BODY)
        self.cb_district.set("Select State First")
        self.cb_district.grid(row=1, column=1, sticky="ew", padx=4, pady=(2, 6))

        # Get Weather Button for Dropdown Selection
        self.btn_get_location_weather = tk.Button(
            card,
            text="🌤️ Get Weather",
            font=FONT_BODY_BOLD,
            fg="#FFFFFF",
            bg=COLOR_ACCENT,
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=5,
            command=self._on_get_location_weather_click
        )
        self.btn_get_location_weather.pack(fill="x", pady=(4, 8), padx=4)

        # Divider ("─────── OR ───────")
        div_frame = tk.Frame(card, bg=COLOR_SURFACE)
        div_frame.pack(fill="x", pady=4)
        tk.Frame(div_frame, bg=COLOR_SURFACE_ALT, height=1).pack(side="left", fill="x", expand=True)
        tk.Label(div_frame, text="  OR  ", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE).pack(side="left")
        tk.Frame(div_frame, bg=COLOR_SURFACE_ALT, height=1).pack(side="right", fill="x", expand=True)

        # Manual Search Section
        search_box = tk.Frame(card, bg=COLOR_SURFACE)
        search_box.pack(fill="x", pady=(4, 0))

        tk.Label(search_box, text="Search City", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE).pack(anchor="w", padx=4)

        input_row = tk.Frame(search_box, bg=COLOR_SURFACE)
        input_row.pack(fill="x", padx=4, pady=2)

        self.city_entry = tk.Entry(
            input_row,
            font=FONT_BODY,
            bg=COLOR_SURFACE_ALT,
            fg=COLOR_TEXT_PRIMARY,
            insertbackground=COLOR_TEXT_PRIMARY,
            relief="flat",
            bd=5
        )
        self.city_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.city_entry.bind("<Return>", lambda e: self._on_manual_search_click())

        self.btn_manual_search = tk.Button(
            input_row,
            text="🔍 Search",
            font=FONT_BODY_BOLD,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SURFACE_ALT,
            activebackground=COLOR_ACCENT,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=4,
            command=self._on_manual_search_click
        )
        self.btn_manual_search.pack(side="right")

        # Auto-Detect Location Button
        self.btn_location = tk.Button(
            card,
            text="📍 Auto-Detect My Location",
            font=FONT_SMALL,
            fg=COLOR_ACCENT,
            bg=COLOR_SURFACE,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_ACCENT_HOVER,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._async_detect_location
        )
        self.btn_location.pack(anchor="e", padx=4, pady=(4, 0))

    def _on_state_selected(self, event):
        """Cascading logic: Populates districts when state is selected."""
        state = self.cb_state.get()
        districts = self.india_locations.get(state, [])

        if districts:
            self.cb_district.configure(state="readonly", values=sorted(districts))
            self.cb_district.set("Select District")
        else:
            self.cb_district.configure(state="disabled", values=[])
            self.cb_district.set("Select State First")

    def _build_banner(self):
        """Error / Notification banner area."""
        self.banner_frame = tk.Frame(self, bg=COLOR_ERROR_BG)
        self.banner_label = tk.Label(
            self.banner_frame,
            text="",
            font=FONT_BODY_BOLD,
            fg=COLOR_ERROR_TEXT,
            bg=COLOR_ERROR_BG,
            wraplength=620,
            justify="center",
            pady=8
        )
        self.banner_label.pack(fill="x", expand=True)

    def _show_error(self, message: str):
        """Displays error banner inside GUI."""
        self.banner_frame.configure(bg=COLOR_ERROR_BG)
        self.banner_label.configure(text=f"⚠️  {message}", bg=COLOR_ERROR_BG, fg=COLOR_ERROR_TEXT)
        self.banner_frame.pack(fill="x", padx=20, pady=(5, 10), before=self.main_scroll_container)

    def _clear_banner(self):
        """Hides error banner."""
        self.banner_frame.pack_forget()

    def _build_main_content(self):
        """Builds main content container for Current, Hourly, and Daily weather."""
        self.main_scroll_container = tk.Frame(self, bg=COLOR_BG)
        self.main_scroll_container.pack(fill="both", expand=True, padx=20, pady=5)

        # Loading Indicator Frame
        self.loading_frame = tk.Frame(self.main_scroll_container, bg=COLOR_BG)
        self.loading_label = tk.Label(
            self.loading_frame,
            text="⏳ Loading weather...",
            font=FONT_TITLE,
            fg=COLOR_ACCENT,
            bg=COLOR_BG
        )
        self.loading_label.pack(pady=40)

        # Content Frame
        self.content_frame = tk.Frame(self.main_scroll_container, bg=COLOR_BG)
        self.content_frame.pack(fill="both", expand=True)

        # 1. CURRENT WEATHER HERO CARD
        self._build_current_weather_card()

        # 2. HOURLY FORECAST SECTION
        self._build_hourly_section()

        # 3. 5-DAY FORECAST SECTION
        self._build_daily_section()

        # Initial state
        self._show_welcome_state()

    def _build_current_weather_card(self):
        """Creates hero card displaying location weather."""
        self.hero_card = tk.Frame(self.content_frame, bg=COLOR_SURFACE, bd=1, relief="solid")
        self.hero_card.pack(fill="x", pady=8)

        # Location Pin & Header
        self.lbl_location = tk.Label(
            self.hero_card,
            text="📍 Select a location above",
            font=FONT_TITLE,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_SURFACE
        )
        self.lbl_location.pack(pady=(14, 0))

        self.lbl_sub_location = tk.Label(
            self.hero_card,
            text="",
            font=FONT_SUBTITLE,
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_SURFACE
        )
        self.lbl_sub_location.pack(pady=(0, 4))

        # Main Icon & Temp Container
        temp_box = tk.Frame(self.hero_card, bg=COLOR_SURFACE)
        temp_box.pack(pady=2)

        self.lbl_current_icon = tk.Label(temp_box, text="☀️", font=("Segoe UI Symbol", 42), bg=COLOR_SURFACE, fg=COLOR_TEMP_WARM)
        self.lbl_current_icon.pack(side="left", padx=10)

        self.lbl_current_temp = tk.Label(temp_box, text="--°", font=FONT_BIG_TEMP, fg=COLOR_TEXT_PRIMARY, bg=COLOR_SURFACE)
        self.lbl_current_temp.pack(side="left", padx=10)

        # Condition Description
        self.lbl_condition = tk.Label(
            self.hero_card,
            text="Ready for search",
            font=FONT_BODY_BOLD,
            fg=COLOR_ACCENT,
            bg=COLOR_SURFACE
        )
        self.lbl_condition.pack(pady=(0, 8))

        # Metrics (Humidity & Wind)
        metrics_frame = tk.Frame(self.hero_card, bg=COLOR_SURFACE_ALT, pady=10)
        metrics_frame.pack(fill="x", side="bottom")

        # Humidity Metric
        hum_box = tk.Frame(metrics_frame, bg=COLOR_SURFACE_ALT)
        hum_box.pack(side="left", expand=True)

        tk.Label(hum_box, text="💧 Humidity", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE_ALT).pack()
        self.lbl_humidity = tk.Label(hum_box, text="--%", font=FONT_BODY_BOLD, fg=COLOR_TEXT_PRIMARY, bg=COLOR_SURFACE_ALT)
        self.lbl_humidity.pack()

        # Divider
        tk.Frame(metrics_frame, bg=COLOR_SURFACE, width=1, height=30).pack(side="left", fill="y")

        # Wind Metric
        wind_box = tk.Frame(metrics_frame, bg=COLOR_SURFACE_ALT)
        wind_box.pack(side="right", expand=True)

        tk.Label(wind_box, text="🌬️ Wind Speed", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE_ALT).pack()
        self.lbl_wind = tk.Label(wind_box, text="-- m/s", font=FONT_BODY_BOLD, fg=COLOR_TEXT_PRIMARY, bg=COLOR_SURFACE_ALT)
        self.lbl_wind.pack()

        # Temperature alternate metric (Fahrenheit display)
        self.lbl_alt_temp = tk.Label(
            self.hero_card,
            text="",
            font=FONT_SMALL,
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_SURFACE
        )
        self.lbl_alt_temp.pack(pady=(0, 4))

    def _build_hourly_section(self):
        """Creates section for 6-hour forecast cards."""
        self.hourly_section = tk.Frame(self.content_frame, bg=COLOR_BG)
        self.hourly_section.pack(fill="x", pady=8)

        hdr = tk.Label(
            self.hourly_section,
            text="⏱️ Hourly Forecast (Next 6 Hours)",
            font=FONT_BODY_BOLD,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG
        )
        hdr.pack(anchor="w", pady=(0, 4))

        self.hourly_cards_frame = tk.Frame(self.hourly_section, bg=COLOR_BG)
        self.hourly_cards_frame.pack(fill="x")

        self.hourly_card_widgets = []
        for i in range(6):
            card = tk.Frame(self.hourly_cards_frame, bg=COLOR_SURFACE, bd=1, relief="solid", width=95, height=115)
            card.pack_propagate(False)
            card.pack(side="left", expand=True, fill="both", padx=3)

            lbl_time = tk.Label(card, text="--", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE)
            lbl_time.pack(pady=(6, 2))

            lbl_icon = tk.Label(card, text="☀️", font=("Segoe UI Symbol", 18), bg=COLOR_SURFACE, fg=COLOR_TEMP_WARM)
            lbl_icon.pack()

            lbl_temp = tk.Label(card, text="--°", font=FONT_BODY_BOLD, fg=COLOR_TEXT_PRIMARY, bg=COLOR_SURFACE)
            lbl_temp.pack(pady=2)

            lbl_cond = tk.Label(card, text="--", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE)
            lbl_cond.pack(pady=(0, 4))

            self.hourly_card_widgets.append({
                "card": card,
                "time": lbl_time,
                "icon": lbl_icon,
                "temp": lbl_temp,
                "cond": lbl_cond
            })

    def _build_daily_section(self):
        """Creates section for 5-day daily forecast cards."""
        self.daily_section = tk.Frame(self.content_frame, bg=COLOR_BG)
        self.daily_section.pack(fill="x", pady=8)

        hdr = tk.Label(
            self.daily_section,
            text="📅 5-Day Forecast",
            font=FONT_BODY_BOLD,
            fg=COLOR_TEXT_PRIMARY,
            bg=COLOR_BG
        )
        hdr.pack(anchor="w", pady=(0, 4))

        self.daily_cards_frame = tk.Frame(self.daily_section, bg=COLOR_BG)
        self.daily_cards_frame.pack(fill="x")

        self.daily_card_widgets = []
        for i in range(5):
            card = tk.Frame(self.daily_cards_frame, bg=COLOR_SURFACE, bd=1, relief="solid", width=115, height=140)
            card.pack_propagate(False)
            card.pack(side="left", expand=True, fill="both", padx=3)

            lbl_day = tk.Label(card, text="DAY", font=FONT_BODY_BOLD, fg=COLOR_ACCENT, bg=COLOR_SURFACE)
            lbl_day.pack(pady=(8, 2))

            lbl_icon = tk.Label(card, text="☀️", font=("Segoe UI Symbol", 20), bg=COLOR_SURFACE, fg=COLOR_TEMP_WARM)
            lbl_icon.pack()

            lbl_max = tk.Label(card, text="--°", font=FONT_BODY_BOLD, fg=COLOR_TEXT_PRIMARY, bg=COLOR_SURFACE)
            lbl_max.pack(pady=1)

            lbl_min = tk.Label(card, text="--°", font=FONT_SMALL, fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE)
            lbl_min.pack(pady=1)

            lbl_cond = tk.Label(card, text="--", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_SURFACE)
            lbl_cond.pack(pady=(0, 6))

            self.daily_card_widgets.append({
                "card": card,
                "day": lbl_day,
                "icon": lbl_icon,
                "max": lbl_max,
                "min": lbl_min,
                "cond": lbl_cond
            })

    def _show_welcome_state(self):
        """Displays initial welcome prompt."""
        self.lbl_location.configure(text="📍 Welcome to WeatherNow")
        self.lbl_sub_location.configure(text="Select a state & district above or search a city")
        self.lbl_current_temp.configure(text="--°")
        self.lbl_condition.configure(text="Ready for search")
        self.lbl_humidity.configure(text="--%")
        self.lbl_wind.configure(text="-- m/s")
        self.lbl_alt_temp.configure(text="")

    def _toggle_unit(self):
        """Toggles temperature unit between °C and °F dynamically."""
        self.unit = "F" if self.unit == "C" else "C"
        self.btn_unit_toggle.configure(text=f"°{self.unit}")
        if self.current_data:
            self._render_weather_data()

    def _on_get_location_weather_click(self):
        """Handles State -> District weather fetch button click."""
        state = self.cb_state.get()
        district = self.cb_district.get()

        if not state or state == "Select State":
            self._show_error("Please select a state.")
            return

        if not district or district in ["Select District", "Select State First"]:
            self._show_error("Please select a district.")
            return

        self._start_fetch_thread_location(district, state)

    def _on_manual_search_click(self):
        """Handles manual city search button click."""
        city = self.city_entry.get().strip()
        if not city:
            self._show_error("Please enter a city name.")
            return

        self._start_fetch_thread_manual(city)

    def _async_detect_location(self):
        """Triggers location auto-detection in background thread."""
        def worker():
            detected_city = WeatherAPIClient.detect_user_location()
            if detected_city:
                self.after(0, lambda: self._on_location_detected(detected_city))

        threading.Thread(target=worker, daemon=True).start()

    def _on_location_detected(self, city: str):
        """Populates city entry and starts weather fetch when location detected."""
        if not self.city_entry.get().strip():
            self.city_entry.insert(0, city)
            self._start_fetch_thread_manual(city)

    def _set_loading_state(self, is_loading: bool):
        """Disables/enables UI buttons during background network requests."""
        if is_loading:
            self._clear_banner()
            self.btn_get_location_weather.configure(state="disabled", text="⏳ Loading weather...")
            self.btn_manual_search.configure(state="disabled")
            self.loading_frame.pack(fill="x", pady=20)
            self.content_frame.pack_forget()
        else:
            self.btn_get_location_weather.configure(state="normal", text="🌤️ Get Weather")
            self.btn_manual_search.configure(state="normal")
            self.loading_frame.pack_forget()
            self.content_frame.pack(fill="both", expand=True)

    def _start_fetch_thread_location(self, district: str, state: str):
        """Fetches weather for selected State & District using Geocoding API."""
        self._set_loading_state(True)

        def worker():
            try:
                # Resolve via Geocoding API: District, State, IN
                geo_query = f"{district}, {state}, IN"
                geo_res = WeatherAPIClient.geocode_location(geo_query, self.api_key)

                if geo_res:
                    lat, lon, geo_name, geo_region = geo_res
                    curr_raw, fore_raw = WeatherAPIClient.fetch_weather_by_coords(lat, lon, self.api_key)
                    parsed_curr = WeatherDataProcessor.process_current(curr_raw, custom_title=district, custom_subtitle=f"{state}, India")
                else:
                    # Fallback to direct city query if geocoding returns no result
                    curr_raw, fore_raw = WeatherAPIClient.fetch_weather_by_city_query(f"{district}, IN", self.api_key)
                    parsed_curr = WeatherDataProcessor.process_current(curr_raw, custom_title=district, custom_subtitle=f"{state}, India")

                parsed_hourly = WeatherDataProcessor.process_hourly(fore_raw)
                parsed_daily = WeatherDataProcessor.process_daily(fore_raw)

                self.after(0, lambda: self._on_fetch_success(parsed_curr, parsed_hourly, parsed_daily))
            except WeatherAPIError as err:
                self.after(0, lambda: self._on_fetch_error(str(err)))
            except Exception as ex:
                self.after(0, lambda: self._on_fetch_error("Weather data is not available for this location. Please try another district or use city search."))

        threading.Thread(target=worker, daemon=True).start()

    def _start_fetch_thread_manual(self, city: str):
        """Fetches weather for manual city search."""
        self._set_loading_state(True)

        def worker():
            try:
                # Resolve via Geocoding or fallback to city name
                geo_res = WeatherAPIClient.geocode_location(city, self.api_key)
                if geo_res:
                    lat, lon, geo_name, geo_region = geo_res
                    curr_raw, fore_raw = WeatherAPIClient.fetch_weather_by_coords(lat, lon, self.api_key)
                    parsed_curr = WeatherDataProcessor.process_current(curr_raw, custom_title=geo_name or city, custom_subtitle=geo_region)
                else:
                    curr_raw, fore_raw = WeatherAPIClient.fetch_weather_by_city_query(city, self.api_key)
                    parsed_curr = WeatherDataProcessor.process_current(curr_raw)

                parsed_hourly = WeatherDataProcessor.process_hourly(fore_raw)
                parsed_daily = WeatherDataProcessor.process_daily(fore_raw)

                self.after(0, lambda: self._on_fetch_success(parsed_curr, parsed_hourly, parsed_daily))
            except WeatherAPIError as err:
                self.after(0, lambda: self._on_fetch_error(str(err)))
            except Exception as ex:
                self.after(0, lambda: self._on_fetch_error(f"Unexpected error: {str(ex)}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_success(self, current: Dict[str, Any], hourly: List[Dict[str, Any]], daily: List[Dict[str, Any]]):
        """Callback when API request succeeds."""
        self._set_loading_state(False)

        self.current_data = current
        self.hourly_data = hourly
        self.daily_data = daily

        self._render_weather_data()

    def _on_fetch_error(self, error_message: str):
        """Callback when API request fails."""
        self._set_loading_state(False)
        self._show_error(error_message)

    def _render_weather_data(self):
        """Renders weather data according to selected unit (°C or °F)."""
        if not self.current_data:
            return

        c = self.current_data
        unit_label = f"°{self.unit}"

        # Render Location & Subtitle
        self.lbl_location.configure(text=f"📍 {c['city']}")
        self.lbl_sub_location.configure(text=c['subtitle'])

        temp_val = c['temp_c'] if self.unit == "C" else c['temp_f']
        self.lbl_current_temp.configure(text=f"{round(temp_val)}{unit_label}")

        alt_temp_val = c['temp_f'] if self.unit == "C" else c['temp_c']
        alt_unit = "°F" if self.unit == "C" else "°C"
        self.lbl_alt_temp.configure(text=f"Temperature: {alt_temp_val:.1f}{alt_unit}")

        self.lbl_condition.configure(text=f"{c['condition']} — {c['description']}")
        self.lbl_humidity.configure(text=f"{c['humidity']}%")

        if self.unit == "C":
            self.lbl_wind.configure(text=f"{c['wind_ms']:.1f} m/s")
        else:
            self.lbl_wind.configure(text=f"{c['wind_mph']:.1f} mph")

        # Load Current Icon
        icon_photo, emoji = self.icon_manager.get_icon(c['icon_code'], size=(70, 70))
        if icon_photo:
            self.lbl_current_icon.configure(image=icon_photo, text="")
            self.lbl_current_icon.image = icon_photo
        else:
            self.lbl_current_icon.configure(image="", text=emoji)

        # Render Hourly Forecast
        for idx, widget_group in enumerate(self.hourly_card_widgets):
            if idx < len(self.hourly_data):
                h = self.hourly_data[idx]
                widget_group["time"].configure(text=h["time"])

                h_temp = h["temp_c"] if self.unit == "C" else h["temp_f"]
                widget_group["temp"].configure(text=f"{round(h_temp)}°")
                widget_group["cond"].configure(text=h["condition"][:9])

                h_icon, h_emoji = self.icon_manager.get_icon(h["icon_code"], size=(36, 36))
                if h_icon:
                    widget_group["icon"].configure(image=h_icon, text="")
                    widget_group["icon"].image = h_icon
                else:
                    widget_group["icon"].configure(image="", text=h_emoji)

        # Render Daily Forecast
        for idx, widget_group in enumerate(self.daily_card_widgets):
            if idx < len(self.daily_data):
                d = self.daily_data[idx]
                widget_group["day"].configure(text=d["day_name"])

                max_t = d["max_c"] if self.unit == "C" else d["max_f"]
                min_t = d["min_c"] if self.unit == "C" else d["min_f"]

                widget_group["max"].configure(text=f"{round(max_t)}°")
                widget_group["min"].configure(text=f"{round(min_t)}°")
                widget_group["cond"].configure(text=d["condition"][:10])

                d_icon, d_emoji = self.icon_manager.get_icon(d["icon_code"], size=(40, 40))
                if d_icon:
                    widget_group["icon"].configure(image=d_icon, text="")
                    widget_group["icon"].image = d_icon
                else:
                    widget_group["icon"].configure(image="", text=d_emoji)


def main():
    """Application entry point."""
    app = WeatherNowApp()
    app.mainloop()


if __name__ == "__main__":
    main()
