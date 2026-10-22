from dataclasses import dataclass, field


@dataclass
class DailyForecast:
    date: str = ""
    weather_code: int = 0
    condition: str = "Unknown"
    high_f: float = 0.0
    low_f: float = 0.0
    precipitation_probability_max: float = 0.0
    wind_speed_max_mph: float = 0.0
    sunrise: str = ""
    sunset: str = ""


@dataclass
class HourlyForecast:
    time: str = ""
    temperature_f: float = 0.0
    precipitation_probability: float = 0.0
    weather_code: int = 0
    condition: str = "Unknown"


@dataclass
class WeatherState:
    location_name: str = "Unknown"
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = ""

    temperature_f: float = 0.0
    apparent_temperature_f: float = 0.0
    humidity_percent: float = 0.0
    precipitation_probability: float = 0.0
    wind_speed_mph: float = 0.0
    weather_code: int = 0
    condition: str = "Unknown"

    daily: list[DailyForecast] = field(default_factory=list)
    hourly: list[HourlyForecast] = field(default_factory=list)

    def day(self, index):
        if 0 <= index < len(self.daily):
            return self.daily[index]

        return None

