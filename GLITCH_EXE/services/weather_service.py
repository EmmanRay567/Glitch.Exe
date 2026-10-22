import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models.weather_state import (
    DailyForecast,
    HourlyForecast,
    WeatherState,
)


class WeatherService:
    """
    Live weather provider using Open-Meteo.
    """

    GEOCODING_URL = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    FORECAST_URL = (
        "https://api.open-meteo.com/v1/forecast"
    )

    WEATHER_CODES = {
        0: "clear skies",
        1: "mostly clear skies",
        2: "partly cloudy skies",
        3: "overcast skies",
        45: "fog",
        48: "freezing fog",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        56: "light freezing drizzle",
        57: "freezing drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        66: "light freezing rain",
        67: "freezing rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        77: "snow grains",
        80: "light rain showers",
        81: "rain showers",
        82: "heavy rain showers",
        85: "light snow showers",
        86: "heavy snow showers",
        95: "thunderstorms",
        96: "thunderstorms with hail",
        99: "strong thunderstorms with hail",
    }

    def _get_json(self, base_url, params):
        url = (
            base_url
            + "?"
            + urlencode(
                params,
                doseq=True
            )
        )

        request = Request(
            url,
            headers={
                "User-Agent":
                    "GLITCH.EXE/Phase2-Weather"
            }
        )

        with urlopen(
            request,
            timeout=10
        ) as response:

            return json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    def condition_from_code(self, code):
        return (
            self.WEATHER_CODES
            .get(
                int(code or 0),
                "mixed weather conditions"
            )
        )

    def geocode(self, location_query):
        data = (
            self._get_json(
                self.GEOCODING_URL,
                {
                    "name": location_query,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                }
            )
        )

        results = (
            data.get("results")
            or []
        )

        if not results:
            raise ValueError(
                f"I could not locate {location_query}."
            )

        result = results[0]

        display_parts = [
            result.get("name")
        ]

        admin = result.get("admin1")
        country = result.get("country")

        if admin:
            display_parts.append(admin)

        if country:
            display_parts.append(country)

        return {
            "name":
                ", ".join(
                    part
                    for part in display_parts
                    if part
                ),

            "latitude":
                float(result["latitude"]),

            "longitude":
                float(result["longitude"]),
        }

    def get_weather_for_coordinates(
        self,
        latitude,
        longitude,
        location_name="Current location"
    ):

        return self._get_weather_from_point(
            latitude,
            longitude,
            location_name,
        )


    def get_weather(self, location_query):
        location = (
            self.geocode(
                location_query
            )
        )

        return self._get_weather_from_point(
            location["latitude"],
            location["longitude"],
            location["name"],
        )


    def _get_weather_from_point(
        self,
        latitude,
        longitude,
        location_name
    ):

        location = {
            "name": location_name,
            "latitude": float(latitude),
            "longitude": float(longitude),
        }

        params = {
            "latitude":
                location["latitude"],

            "longitude":
                location["longitude"],

            "timezone":
                "auto",

            "temperature_unit":
                "fahrenheit",

            "wind_speed_unit":
                "mph",

            "forecast_days":
                7,

            "current": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "weather_code",
                "wind_speed_10m",
            ],

            "hourly": [
                "temperature_2m",
                "precipitation_probability",
                "weather_code",
            ],

            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "sunrise",
                "sunset",
            ],
        }

        data = (
            self._get_json(
                self.FORECAST_URL,
                params
            )
        )

        current = (
            data.get("current")
            or {}
        )

        hourly = (
            data.get("hourly")
            or {}
        )

        daily = (
            data.get("daily")
            or {}
        )

        weather = WeatherState(
            location_name=
                location["name"],

            latitude=
                location["latitude"],

            longitude=
                location["longitude"],

            timezone=
                data.get(
                    "timezone",
                    ""
                ),

            temperature_f=
                float(
                    current.get(
                        "temperature_2m",
                        0.0
                    )
                    or 0.0
                ),

            apparent_temperature_f=
                float(
                    current.get(
                        "apparent_temperature",
                        0.0
                    )
                    or 0.0
                ),

            humidity_percent=
                float(
                    current.get(
                        "relative_humidity_2m",
                        0.0
                    )
                    or 0.0
                ),

            wind_speed_mph=
                float(
                    current.get(
                        "wind_speed_10m",
                        0.0
                    )
                    or 0.0
                ),

            weather_code=
                int(
                    current.get(
                        "weather_code",
                        0
                    )
                    or 0
                ),
        )

        weather.condition = (
            self.condition_from_code(
                weather.weather_code
            )
        )

        hourly_times = (
            hourly.get("time")
            or []
        )

        hourly_temps = (
            hourly.get("temperature_2m")
            or []
        )

        hourly_rain = (
            hourly.get(
                "precipitation_probability"
            )
            or []
        )

        hourly_codes = (
            hourly.get("weather_code")
            or []
        )

        for index, timestamp in enumerate(
            hourly_times
        ):

            probability = (
                float(
                    hourly_rain[index]
                    or 0.0
                )
                if index < len(hourly_rain)
                else 0.0
            )

            code = (
                int(
                    hourly_codes[index]
                    or 0
                )
                if index < len(hourly_codes)
                else 0
            )

            temperature = (
                float(
                    hourly_temps[index]
                    or 0.0
                )
                if index < len(hourly_temps)
                else 0.0
            )

            weather.hourly.append(
                HourlyForecast(
                    time=timestamp,
                    temperature_f=
                        temperature,
                    precipitation_probability=
                        probability,
                    weather_code=
                        code,
                    condition=
                        self.condition_from_code(
                            code
                        ),
                )
            )

        daily_times = (
            daily.get("time")
            or []
        )

        codes = (
            daily.get("weather_code")
            or []
        )

        highs = (
            daily.get("temperature_2m_max")
            or []
        )

        lows = (
            daily.get("temperature_2m_min")
            or []
        )

        rain_max = (
            daily.get(
                "precipitation_probability_max"
            )
            or []
        )

        wind_max = (
            daily.get("wind_speed_10m_max")
            or []
        )

        sunrises = (
            daily.get("sunrise")
            or []
        )

        sunsets = (
            daily.get("sunset")
            or []
        )

        for index, date in enumerate(
            daily_times
        ):

            code = (
                int(codes[index] or 0)
                if index < len(codes)
                else 0
            )

            weather.daily.append(
                DailyForecast(
                    date=date,
                    weather_code=
                        code,
                    condition=
                        self.condition_from_code(
                            code
                        ),
                    high_f=
                        float(highs[index] or 0.0)
                        if index < len(highs)
                        else 0.0,
                    low_f=
                        float(lows[index] or 0.0)
                        if index < len(lows)
                        else 0.0,
                    precipitation_probability_max=
                        float(rain_max[index] or 0.0)
                        if index < len(rain_max)
                        else 0.0,
                    wind_speed_max_mph=
                        float(wind_max[index] or 0.0)
                        if index < len(wind_max)
                        else 0.0,
                    sunrise=
                        sunrises[index]
                        if index < len(sunrises)
                        else "",
                    sunset=
                        sunsets[index]
                        if index < len(sunsets)
                        else "",
                )
            )

        if weather.daily:
            weather.precipitation_probability = (
                weather.daily[0]
                .precipitation_probability_max
            )

        return weather
