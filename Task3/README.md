# WeatherNow 🌦️

**WeatherNow** is a modern, production-quality desktop weather application built with Python 3, Tkinter, Pillow, and the OpenWeatherMap API. It features an **India State → District cascading dropdown** selection system, OpenWeatherMap **Direct Geocoding API** integration, real-time weather information, 6-hour hourly forecasts, 5-day daily forecasts, client-side unit toggling (°C / °F), automatic location detection, and resilient error handling.

---

## Features

- 📍 **India State → District Cascading Dropdowns**: Choose from all 28 Indian States & 8 Union Territories and select a district. The District dropdown dynamically populates and enables based on the selected State.
- 🔍 **Dual Location Selection**:
  - **Option A**: State + District Selection (`State → District → 🌤️ Get Weather`)
  - **Option B**: Manual City Search (`City Name → 🔍 Search`)
- 🌐 **OpenWeatherMap Direct Geocoding API**: Resolves location queries (`District, State, IN` or `City`) into exact latitude & longitude (`lat`, `lon`) coordinates for accurate weather fetching.
- 🌡️ **Real-Time Weather Metrics**: Displays current temperature (in °C and °F), weather conditions, humidity percentage, wind speed (m/s and mph), and location info (`📍 District \n State, Country`).
- 🖼️ **Dynamic OpenWeatherMap Icons**: Automatically downloads, resizes, and caches official weather icons locally, with emoji fallbacks for offline scenarios.
- ⏱️ **6-Hour Hourly Forecast**: Displays upcoming weather conditions for the next 6 hours (3-hour steps) with icons and temperatures.
- 📅 **5-Day Daily Forecast**: Aggregates 3-hour forecast data into daily summaries, showing calculated daily high/low temperatures, day of the week, and primary weather condition.
- 🔘 **Instant °C / °F Unit Toggle**: Seamlessly switches temperatures and wind speeds between metric (°C, m/s) and imperial (°F, mph) units across all views without making extra API calls.
- 📍 **Automatic Location Detection**: Attempts background location auto-detection via `ipinfo.io` on startup.
- ⚡ **Non-Blocking Threaded Architecture**: All network requests run in background threads, keeping the desktop GUI completely smooth and responsive.
- ⚠️ **In-App Error Handling**: Clear, friendly error banners inside the GUI for missing state, missing district, city not found, invalid API key, timeouts, and network connection drops.

---

## Technologies Used

- **Python 3.14+**
- **Tkinter (ttk)** for desktop GUI and combobox widgets
- **Requests** for HTTP API communications (Weather, Forecast, Geocoding, ipinfo.io)
- **Pillow (PIL)** for weather icon loading and high-quality image manipulation
- **python-dotenv** for secure environment configuration
- **OpenWeatherMap API** (Direct Geocoding, Current Weather, & 5-Day Forecast endpoints)
- **ipinfo.io API** (Optional IP geolocation lookup)

---

## Project Structure

```text
WeatherNow/
├── weather_app.py         # Main desktop application & Tkinter GUI
├── india_locations.json   # Dataset covering 36 Indian States/UTs & districts
├── test_weather_app.py    # Unit tests for dataset loading, geocoding & data processing
├── requirements.txt       # Python package dependencies
├── .env.example           # Environment template for OpenWeatherMap API key
├── README.md              # Comprehensive project documentation
└── assets/
    └── weather_icons/     # Local disk cache for OpenWeatherMap icons (.png)
```

---

## Installation

1. **Clone the repository** (or download source code):
   ```bash
   git clone https://github.com/your-username/WeatherNow.git
   cd WeatherNow
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## API Key Setup

1. Sign up for a free account at [OpenWeatherMap](https://home.openweathermap.org/users/sign_up).
2. Generate an **API Key** in your account dashboard.
3. Create a `.env` file in the project root directory (you can copy `.env.example`):
   ```bash
   cp .env.example .env
   ```
4. Open `.env` and set your API key:
   ```env
   OPENWEATHER_API_KEY=your_actual_api_key_here
   ```

---

## Running the Application

Launch the desktop app using Python:

```bash
python weather_app.py
```

---

## Error Handling Overview

The application handles network, validation, and API errors gracefully without crashing:

| Error Case | In-App Message Displayed |
| :--- | :--- |
| **No State Selected** | `Please select a state.` |
| **No District Selected** | `Please select a district.` |
| **Empty City Search** | `Please enter a city name.` |
| **City/Location Not Found** | `Weather data is not available for this location. Please try another district or use city search.` |
| **Invalid API Key (401)** | `Invalid API key. Please check your OpenWeatherMap API key.` |
| **Network Connection Drop** | `Unable to connect to the weather service. Please check your internet connection.` |
| **Request Timeout** | `Request timed out. Please try again.` |

All errors are rendered inside an alert banner at the top of the GUI.

---

## License

MIT License. Free to use, modify, and distribute.
