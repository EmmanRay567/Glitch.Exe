from datetime import datetime


class WeatherQueryController:
    """
    Handles natural weather questions and conversational
    follow-ups such as "what about tomorrow?".
    """

    def __init__(
        self,
        weather_service,
        default_location=None,
        location_service=None
    ):

        self.weather_service = (
            weather_service
        )

        self.default_location = (
            default_location
        )

        self.location_service = (
            location_service
        )

        self.last_location = None
        self.last_weather_state = None


    def set_default_location(
        self,
        location
    ):

        self.default_location = (
            location
        )


    def _extract_location(
        self,
        command
    ):

        markers = [
            "what's the weather like in ",
            "what is the weather like in ",
            "weather like in ",
            "what's the weather in ",
            "what is the weather in ",
            "weather in ",
            "weather for ",
            "forecast for ",
            "forecast in ",
            "temperature in ",
            "rain in ",
            "humidity in ",
            "wind in ",
        ]


        lowered = (
            command.lower()
        )


        for marker in markers:

            if marker in lowered:

                location = (
                    lowered
                    .split(
                        marker,
                        1
                    )[1]
                    .strip(
                        " ,.!?"
                    )
                )


                if location:

                    return location


        return None


    def _location_for_command(
        self,
        command
    ):

        explicit = (
            self._extract_location(
                command
            )
        )


        if explicit:

            return {
                "type": "NAMED",
                "value": explicit,
            }


        if self.location_service is not None:

            current = (
                self.location_service
                .get_current_location()
            )


            if (
                current is not None
                and current.available
            ):

                return {
                    "type": "COORDINATES",
                    "latitude":
                        current.latitude,

                    "longitude":
                        current.longitude,

                    "label":
                        "your current area",
                }


        if self.last_location:

            return {
                "type": "NAMED",
                "value": self.last_location,
            }


        if self.default_location:

            return {
                "type": "NAMED",
                "value": self.default_location,
            }


        return None


    def _day_index(
        self,
        command
    ):

        lowered = (
            command.lower()
        )


        if (
            "day after tomorrow"
            in lowered
        ):

            return 2


        if "tomorrow" in lowered:

            return 1


        return 0


    def _format_hour(
        self,
        timestamp
    ):

        hour = (
            datetime
            .fromisoformat(
                timestamp
            )
            .hour
        )


        suffix = (
            "AM"
            if hour < 12
            else "PM"
        )


        display_hour = (
            hour % 12
        )


        if display_hour == 0:

            display_hour = 12


        return (
            f"{display_hour} {suffix}"
        )


    def _rain_window(
        self,
        state,
        day_index
    ):

        day = state.day(
            day_index
        )


        if day is None:

            return None


        samples = [
            item
            for item in state.hourly
            if item.time.startswith(
                day.date
            )
        ]


        if not samples:

            return None


        peak = max(
            samples,
            key=lambda item:
                item.precipitation_probability
        )


        return (
            peak.precipitation_probability,
            self._format_hour(
                peak.time
            )
        )


    def _current_summary(
        self,
        state
    ):

        today = state.day(0)

        extra = ""


        if today:

            extra = (
                f" Today's high is about "
                f"{today.high_f:.0f} degrees "
                f"with a low near "
                f"{today.low_f:.0f}. "
                f"The maximum rain chance is "
                f"{today.precipitation_probability_max:.0f} percent."
            )


        return (
            f"In {state.location_name}, it's currently "
            f"{state.temperature_f:.0f} degrees with "
            f"{state.condition}. It feels like "
            f"{state.apparent_temperature_f:.0f}. "
            f"Humidity is {state.humidity_percent:.0f} percent "
            f"and winds are around "
            f"{state.wind_speed_mph:.0f} miles per hour."
            f"{extra}"
        )


    def _day_summary(
        self,
        state,
        day_index
    ):

        day = state.day(
            day_index
        )


        if day is None:

            return (
                "That forecast day is not available yet."
            )


        if day_index == 0:

            day_name = "Today"

        elif day_index == 1:

            day_name = "Tomorrow"

        else:

            day_name = (
                datetime
                .fromisoformat(
                    day.date
                )
                .strftime(
                    "%A"
                )
            )


        return (
            f"{day_name} in {state.location_name} should have "
            f"{day.condition}, with a high around "
            f"{day.high_f:.0f} and a low around "
            f"{day.low_f:.0f} degrees. "
            f"The maximum precipitation chance is "
            f"{day.precipitation_probability_max:.0f} percent, "
            f"with winds up to about "
            f"{day.wind_speed_max_mph:.0f} miles per hour."
        )


    def _rain_summary(
        self,
        state,
        day_index
    ):

        day = state.day(
            day_index
        )


        if day is None:

            return (
                "I don't have that forecast day available."
            )


        window = (
            self._rain_window(
                state,
                day_index
            )
        )


        day_name = (
            "today"
            if day_index == 0
            else "tomorrow"
        )


        if window:

            probability, hour = (
                window
            )


            if probability >= 70:

                confidence = (
                    "Rain looks fairly likely"
                )

            elif probability >= 40:

                confidence = (
                    "Rain is possible"
                )

            elif probability >= 20:

                confidence = (
                    "There's a smaller chance of rain"
                )

            else:

                confidence = (
                    "Rain looks unlikely"
                )


            return (
                f"{confidence} {day_name} in "
                f"{state.location_name}. "
                f"The forecast peaks near "
                f"{probability:.0f} percent around {hour}."
            )


        return (
            f"The maximum precipitation chance {day_name} is "
            f"{day.precipitation_probability_max:.0f} percent."
        )


    def can_handle(
        self,
        command
    ):

        lowered = (
            command
            .strip()
            .lower()
        )


        followup_phrases = [
            "what about tomorrow",
            "how about tomorrow",
            "and tomorrow",
            "what about today",
            "how about today",
        ]


        weather_words = [
            "weather",
            "forecast",
            "temperature",
            "rain",
            "humidity",
            "wind",
            "hot",
            "cold",
            "storm",
            "thunderstorm",
            "umbrella",
            "outside",
        ]


        return (
            any(
                word in lowered
                for word in weather_words
            )
            or (
                lowered in followup_phrases
                and self.last_weather_state
                is not None
            )
        )


    def _weather_topic(
        self,
        command
    ):

        lowered = (
            command
            .strip()
            .lower()
        )


        if any(
            word in lowered
            for word in [
                "rain",
                "umbrella",
                "storm",
                "thunderstorm",
            ]
        ):

            return "PRECIPITATION"


        if any(
            word in lowered
            for word in [
                "temperature",
                "hot",
                "cold",
            ]
        ):

            return "TEMPERATURE"


        if "humidity" in lowered:

            return "HUMIDITY"


        if "wind" in lowered:

            return "WIND"


        return "FORECAST"


    def handle_query(
        self,
        command
    ):

        original = (
            command.strip()
        )


        lowered = (
            original.lower()
        )


        followup_phrases = [
            "what about tomorrow",
            "how about tomorrow",
            "and tomorrow",
            "what about today",
            "how about today",
        ]


        is_followup = (
            lowered in followup_phrases
            and self.last_weather_state
            is not None
        )


        if not self.can_handle(
            original
        ):

            return {
                "handled": False,
                "message": None,
            }


        location = (
            self._location_for_command(
                original
            )
        )


        if not location:

            return {
                "handled": True,
                "message": (
                    "I couldn't determine your current location yet. "
                    "Make sure Windows Location Services are enabled, "
                    "or ask me about a specific city."
                ),
            }


        try:

            if location["type"] == "COORDINATES":

                state = (
                    self.weather_service
                    .get_weather_for_coordinates(
                        location["latitude"],
                        location["longitude"],
                        location["label"],
                    )
                )

            else:

                state = (
                    self.weather_service
                    .get_weather(
                        location["value"]
                    )
                )


        except Exception as error:

            return {
                "handled": True,
                "message": (
                    "I couldn't retrieve the live weather right now. "
                    f"{error}"
                ),
            }


        if location["type"] == "NAMED":

            self.last_location = (
                location["value"]
            )


        self.last_weather_state = (
            state
        )


        day_index = (
            self._day_index(
                lowered
            )
        )


        if any(
            word in lowered
            for word in [
                "rain",
                "umbrella",
                "storm",
                "thunderstorm",
            ]
        ):

            message = (
                self._rain_summary(
                    state,
                    day_index
                )
            )


        elif (
            "tomorrow" in lowered
            or is_followup
        ):

            message = (
                self._day_summary(
                    state,
                    day_index
                )
            )


        elif "humidity" in lowered:

            message = (
                f"Humidity in {state.location_name} is currently "
                f"{state.humidity_percent:.0f} percent."
            )


        elif "wind" in lowered:

            message = (
                f"Winds in {state.location_name} are currently around "
                f"{state.wind_speed_mph:.0f} miles per hour."
            )


        elif any(
            word in lowered
            for word in [
                "temperature",
                "hot",
                "cold",
            ]
        ):

            day = (
                state.day(
                    day_index
                )
            )


            if (
                day is not None
                and day_index > 0
            ):

                message = (
                    f"{'Tomorrow' if day_index == 1 else 'That day'} "
                    f"in {state.location_name} should reach about "
                    f"{day.high_f:.0f} degrees, with a low near "
                    f"{day.low_f:.0f}."
                )

            else:

                message = (
                    f"It's currently {state.temperature_f:.0f} degrees "
                    f"in {state.location_name}, and it feels like "
                    f"{state.apparent_temperature_f:.0f}."
                )


        elif "forecast" in lowered:

            message = (
                self._day_summary(
                    state,
                    day_index
                )
            )


        else:

            message = (
                self._current_summary(
                    state
                )
            )


        return {
            "handled": True,
            "message": message,
            "weather_topic":
                self._weather_topic(
                    original
                ),
            "day_index":
                day_index,
        }