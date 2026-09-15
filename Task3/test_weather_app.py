"""
Unit verification test suite for WeatherNow app components.
"""

import unittest
from weather_app import (
    WeatherDataProcessor,
    WeatherAPIClient,
    WeatherAPIError,
    IconManager,
    LocationDataLoader
)

class TestWeatherApp(unittest.TestCase):

    def setUp(self):
        self.sample_current_raw = {
            "name": "Hyderabad",
            "sys": {"country": "IN"},
            "main": {"temp": 29.0, "feels_like": 31.5, "humidity": 62},
            "wind": {"speed": 3.8},
            "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}]
        }

        self.sample_forecast_raw = {
            "list": [
                {
                    "dt": 1600000000,
                    "dt_txt": "2026-09-14 12:00:00",
                    "main": {"temp": 29.0},
                    "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}]
                },
                {
                    "dt": 1600010800,
                    "dt_txt": "2026-09-14 15:00:00",
                    "main": {"temp": 28.0},
                    "weather": [{"main": "Clouds", "description": "few clouds", "icon": "02d"}]
                },
                {
                    "dt": 1600021600,
                    "dt_txt": "2026-09-15 12:00:00",
                    "main": {"temp": 31.0},
                    "weather": [{"main": "Clear", "description": "clear sky", "icon": "01d"}]
                },
                {
                    "dt": 1600032400,
                    "dt_txt": "2026-09-15 18:00:00",
                    "main": {"temp": 22.0},
                    "weather": [{"main": "Clear", "description": "clear sky", "icon": "01n"}]
                }
            ]
        }

    def test_india_locations_loading(self):
        locations = LocationDataLoader.load_india_locations()
        self.assertIn("Telangana", locations)
        self.assertIn("Hyderabad", locations["Telangana"])
        self.assertIn("Maharashtra", locations)
        self.assertIn("Mumbai City", locations["Maharashtra"])
        self.assertEqual(len(locations), 36)

    def test_c_to_f(self):
        self.assertEqual(WeatherDataProcessor.c_to_f(0), 32.0)
        self.assertEqual(WeatherDataProcessor.c_to_f(100), 212.0)
        self.assertEqual(round(WeatherDataProcessor.c_to_f(29.0), 1), 84.2)

    def test_process_current(self):
        curr = WeatherDataProcessor.process_current(self.sample_current_raw, custom_title="Hyderabad", custom_subtitle="Telangana, India")
        self.assertEqual(curr["city"], "Hyderabad")
        self.assertEqual(curr["subtitle"], "Telangana, India")
        self.assertEqual(curr["temp_c"], 29.0)
        self.assertEqual(round(curr["temp_f"], 1), 84.2)
        self.assertEqual(curr["humidity"], 62)
        self.assertEqual(curr["condition"], "Clear")
        self.assertEqual(curr["icon_code"], "01d")

    def test_process_hourly(self):
        hourly = WeatherDataProcessor.process_hourly(self.sample_forecast_raw)
        self.assertEqual(len(hourly), 4)
        self.assertEqual(hourly[0]["temp_c"], 29.0)
        self.assertEqual(hourly[1]["temp_c"], 28.0)

    def test_process_daily(self):
        daily = WeatherDataProcessor.process_daily(self.sample_forecast_raw)
        self.assertEqual(len(daily), 2)
        day2 = daily[1]
        self.assertEqual(day2["max_c"], 31.0)
        self.assertEqual(day2["min_c"], 22.0)

    def test_empty_city_validation(self):
        with self.assertRaises(WeatherAPIError) as ctx:
            WeatherAPIClient.fetch_weather_by_city_query("", "fake_key")
        self.assertIn("Please enter a city name", str(ctx.exception))

    def test_invalid_key_validation(self):
        with self.assertRaises(WeatherAPIError) as ctx:
            WeatherAPIClient.fetch_weather_by_city_query("London", "")
        self.assertIn("Invalid API key", str(ctx.exception))

    def test_icon_manager_fallback(self):
        im = IconManager()
        img, emoji = im.get_icon("non_existent_code_99x")
        self.assertEqual(emoji, "🌤️")

if __name__ == "__main__":
    unittest.main()
