import asyncio
import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import (
    Request,
    urlopen,
)

from models.location_state import (
    LocationState
)


class LocationService:
    """
    Location service for GLITCH.EXE.

    Resolution order:
        1. Windows.Devices.Geolocation
        2. Last known good location for this runtime
        3. Approximate public-IP location

    The IP fallback is intentionally coarse. It is used so commands
    such as "weather in my area" still work on laptops where Windows
    Location Services or WinRT geolocation are unavailable.
    """

    IP_PROVIDERS = [
        "https://ipwho.is/",
        "https://ipapi.co/json/",
    ]

    REVERSE_GEOCODE_URL = (
        "https://nominatim.openstreetmap.org/reverse"
    )

    APP_USER_AGENT = (
        "GLITCH.EXE/1.0 "
        "(personal desktop assistant; "
        "reverse geocoding only on user request)"
    )


    def __init__(
        self,
        allow_ip_fallback=True
    ):

        self.access_granted = False

        self.access_status = (
            "NOT_REQUESTED"
        )

        self.last_location = None

        self.last_error = None

        self.allow_ip_fallback = bool(
            allow_ip_fallback
        )

        self.last_source = None

        self._reverse_cache_key = None
        self._reverse_cache_value = None


    # ---------------------------------------------------------
    # WINDOWS GEOLOCATION IMPORT
    # ---------------------------------------------------------

    def _load_windows_geolocation(
        self
    ):

        errors = []

        # Modern PyWinRT package layout.
        try:

            from winrt.windows.devices.geolocation import (
                Geolocator,
                GeolocationAccessStatus,
                PositionAccuracy,
            )

            return (
                Geolocator,
                GeolocationAccessStatus,
                PositionAccuracy,
                "WINRT",
            )

        except Exception as error:

            errors.append(
                "winrt: "
                f"{type(error).__name__}: "
                f"{error}"
            )


        # Some Python Windows setups use winsdk instead.
        try:

            from winsdk.windows.devices.geolocation import (
                Geolocator,
                GeolocationAccessStatus,
                PositionAccuracy,
            )

            return (
                Geolocator,
                GeolocationAccessStatus,
                PositionAccuracy,
                "WINSDK",
            )

        except Exception as error:

            errors.append(
                "winsdk: "
                f"{type(error).__name__}: "
                f"{error}"
            )


        self.last_error = (
            "Windows geolocation imports unavailable. "
            + " | ".join(
                errors
            )
        )

        return None


    # ---------------------------------------------------------
    # WINDOWS PERMISSION
    # ---------------------------------------------------------

    async def _request_access_async(
        self
    ):

        loaded = (
            self._load_windows_geolocation()
        )

        if loaded is None:
            return False


        (
            Geolocator,
            GeolocationAccessStatus,
            _,
            backend,
        ) = loaded


        try:

            status = await (
                Geolocator
                .request_access_async()
            )

            self.access_status = str(
                getattr(
                    status,
                    "name",
                    status
                )
            )

            self.access_granted = (
                status
                ==
                GeolocationAccessStatus.ALLOWED
            )

            if self.access_granted:

                self.last_error = None

                print(
                    "LOCATION ACCESS // "
                    f"{backend} // ALLOWED"
                )

            else:

                self.last_error = (
                    "Windows returned location "
                    f"access status: "
                    f"{self.access_status}"
                )

            return (
                self.access_granted
            )

        except Exception as error:

            self.access_granted = False

            self.last_error = (
                "Windows location permission "
                "request failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return False


    def request_access(
        self
    ):
        """
        Called from the foreground Qt/UI thread.

        A False result only means precise Windows geolocation was not
        granted. Weather can still use the coarse IP fallback later.
        """

        try:

            return asyncio.run(
                self._request_access_async()
            )

        except Exception as error:

            self.access_granted = False

            self.last_error = (
                "Location permission bootstrap "
                "failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return False


    # ---------------------------------------------------------
    # WINDOWS CURRENT POSITION
    # ---------------------------------------------------------

    async def _get_windows_location_async(
        self
    ):

        loaded = (
            self._load_windows_geolocation()
        )

        if loaded is None:
            return None


        (
            Geolocator,
            _,
            PositionAccuracy,
            backend,
        ) = loaded


        try:

            geolocator = (
                Geolocator()
            )

            geolocator.desired_accuracy = (
                PositionAccuracy.DEFAULT
            )

            # Some Windows builds can return a less precise
            # consentless position when GPS is unavailable.
            try:

                fallback_method = getattr(
                    geolocator,
                    "allow_fallback_to_consentless_positions",
                    None
                )

                if callable(
                    fallback_method
                ):
                    fallback_method()

            except Exception:
                pass


            position = await (
                geolocator
                .get_geoposition_async()
            )

            coordinate = (
                position.coordinate
            )

            point = (
                coordinate
                .point
                .position
            )

            state = LocationState(
                latitude=float(
                    point.latitude
                ),
                longitude=float(
                    point.longitude
                ),
                accuracy_meters=float(
                    coordinate.accuracy
                ),
                source=(
                    "WINDOWS_GEOLOCATION"
                ),
                available=True,
                timestamp=datetime.now(),
            )

            self.last_location = state

            self.last_source = (
                "WINDOWS_GEOLOCATION"
            )

            self.last_error = None

            print(
                "LOCATION FIX // "
                f"{backend} // "
                f"accuracy="
                f"{state.accuracy_meters:.0f}m"
            )

            return state

        except Exception as error:

            self.last_error = (
                "Windows position request failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return None


    def _get_windows_location(
        self
    ):

        try:

            return asyncio.run(
                self._get_windows_location_async()
            )

        except Exception as error:

            self.last_error = (
                "Windows location lookup failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return None


    # ---------------------------------------------------------
    # COARSE NETWORK / PUBLIC-IP FALLBACK
    # ---------------------------------------------------------

    def _get_ip_json(
        self,
        url
    ):

        request = Request(
            url,
            headers={
                "User-Agent":
                    "GLITCH.EXE/Location"
            }
        )

        with urlopen(
            request,
            timeout=6
        ) as response:

            return json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )


    def _ip_location_from_ipwho(
        self
    ):

        data = self._get_ip_json(
            "https://ipwho.is/"
        )

        if not data.get(
            "success",
            True
        ):
            return None


        latitude = data.get(
            "latitude"
        )

        longitude = data.get(
            "longitude"
        )

        if (
            latitude is None
            or longitude is None
        ):
            return None


        return LocationState(
            latitude=float(
                latitude
            ),
            longitude=float(
                longitude
            ),
            accuracy_meters=None,
            source="IP_GEOLOCATION",
            available=True,
            timestamp=datetime.now(),
        )


    def _ip_location_from_ipapi(
        self
    ):

        data = self._get_ip_json(
            "https://ipapi.co/json/"
        )

        latitude = data.get(
            "latitude"
        )

        longitude = data.get(
            "longitude"
        )

        if (
            latitude is None
            or longitude is None
        ):
            return None


        return LocationState(
            latitude=float(
                latitude
            ),
            longitude=float(
                longitude
            ),
            accuracy_meters=None,
            source="IP_GEOLOCATION",
            available=True,
            timestamp=datetime.now(),
        )


    def _get_ip_location(
        self
    ):

        if not self.allow_ip_fallback:
            return None


        errors = []

        providers = [
            (
                "ipwho.is",
                self._ip_location_from_ipwho,
            ),
            (
                "ipapi.co",
                self._ip_location_from_ipapi,
            ),
        ]


        for (
            name,
            provider
        ) in providers:

            try:

                state = (
                    provider()
                )

                if (
                    state is not None
                    and state.available
                ):

                    self.last_location = (
                        state
                    )

                    self.last_source = (
                        state.source
                    )

                    self.last_error = None

                    print(
                        "LOCATION FIX // "
                        f"COARSE NETWORK // "
                        f"{name}"
                    )

                    return state

            except Exception as error:

                errors.append(
                    f"{name}: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )


        if errors:

            self.last_error = (
                "Approximate network location "
                "failed. "
                + " | ".join(
                    errors
                )
            )

        return None


    # ---------------------------------------------------------
    # REVERSE GEOCODING
    # ---------------------------------------------------------

    def _reverse_geocode(
        self,
        latitude,
        longitude,
        coarse=False
    ):
        """
        Convert coordinates into a human-readable place.

        Nominatim is called only from an explicit user location
        request. Results are cached in memory so repeated questions
        about the same position do not create unnecessary requests.
        """

        latitude = float(
            latitude
        )

        longitude = float(
            longitude
        )

        cache_key = (
            round(
                latitude,
                4
                if not coarse
                else 2
            ),
            round(
                longitude,
                4
                if not coarse
                else 2
            ),
            bool(
                coarse
            ),
        )

        if (
            cache_key
            ==
            self._reverse_cache_key
            and
            self._reverse_cache_value
            is not None
        ):
            return dict(
                self._reverse_cache_value
            )


        params = {
            "format":
                "jsonv2",

            "lat":
                latitude,

            "lon":
                longitude,

            "addressdetails":
                1,

            "layer":
                "address",

            # IP geolocation is only city-level-ish, so do not
            # reverse it into a misleading building address.
            "zoom":
                10
                if coarse
                else 18,
        }

        url = (
            self.REVERSE_GEOCODE_URL
            + "?"
            + urlencode(
                params
            )
        )

        request = Request(
            url,
            headers={
                "User-Agent":
                    self.APP_USER_AGENT,

                "Accept-Language":
                    "en",
            },
        )

        try:

            with urlopen(
                request,
                timeout=8
            ) as response:

                data = json.loads(
                    response
                    .read()
                    .decode(
                        "utf-8"
                    )
                )

        except Exception as error:

            self.last_error = (
                "Reverse geocoding failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return None


        address = (
            data.get(
                "address"
            )
            or {}
        )

        city = (
            address.get(
                "city"
            )
            or address.get(
                "town"
            )
            or address.get(
                "village"
            )
            or address.get(
                "municipality"
            )
            or address.get(
                "hamlet"
            )
        )

        state = (
            address.get(
                "state"
            )
            or address.get(
                "region"
            )
        )

        postcode = (
            address.get(
                "postcode"
            )
        )

        road = (
            address.get(
                "road"
            )
            or address.get(
                "pedestrian"
            )
            or address.get(
                "residential"
            )
            or address.get(
                "highway"
            )
        )

        house_number = (
            address.get(
                "house_number"
            )
        )

        neighbourhood = (
            address.get(
                "neighbourhood"
            )
            or address.get(
                "suburb"
            )
            or address.get(
                "quarter"
            )
        )

        country = (
            address.get(
                "country"
            )
        )

        if (
            not coarse
            and road
        ):

            street = (
                f"{house_number} {road}"
                if house_number
                else road
            )

        else:

            street = None


        parts = []

        if street:
            parts.append(
                street
            )

        if (
            neighbourhood
            and
            neighbourhood
            not in parts
        ):
            parts.append(
                neighbourhood
            )

        if (
            city
            and
            city
            not in parts
        ):
            parts.append(
                city
            )

        if (
            state
            and
            state
            not in parts
        ):
            parts.append(
                state
            )

        if postcode:
            parts.append(
                postcode
            )

        if (
            country
            and
            country
            not in parts
        ):
            parts.append(
                country
            )


        result = {
            "display_name":
                (
                    ", ".join(
                        parts
                    )
                    if parts
                    else data.get(
                        "display_name"
                    )
                ),

            "street":
                street,

            "road":
                road,

            "neighbourhood":
                neighbourhood,

            "city":
                city,

            "state":
                state,

            "postcode":
                postcode,

            "country":
                country,
        }

        self._reverse_cache_key = (
            cache_key
        )

        self._reverse_cache_value = (
            dict(
                result
            )
        )

        return result


    def describe_current_location(
        self
    ):
        """
        Return a user-facing description of the current location.

        When Windows geolocation is available, GLITCH provides the
        nearest reverse-geocoded address plus coordinates and reported
        accuracy.

        When only public-IP geolocation is available, GLITCH clearly
        labels the answer as approximate and limits reverse geocoding
        to city-level detail.
        """

        state = (
            self.get_current_location()
        )

        if (
            state is None
            or not state.available
        ):
            return {
                "available":
                    False,

                "message":
                    (
                        "I couldn't determine your current location. "
                        "Windows location and the approximate network "
                        "fallback are both unavailable."
                    ),
            }


        source = str(
            getattr(
                state,
                "source",
                ""
            )
            or ""
        ).upper()

        coarse = (
            source.startswith(
                "IP_"
            )
        )

        place = (
            self._reverse_geocode(
                state.latitude,
                state.longitude,
                coarse=coarse
            )
        )

        latitude = float(
            state.latitude
        )

        longitude = float(
            state.longitude
        )

        coordinate_text = (
            f"{latitude:.5f}, "
            f"{longitude:.5f}"
        )


        if coarse:

            place_name = (
                place.get(
                    "display_name"
                )
                if place
                else None
            )

            if place_name:

                message = (
                    "I can only determine your location "
                    "approximately from the network. "
                    f"You appear to be near {place_name}. "
                    f"Approximate coordinates are "
                    f"{coordinate_text}."
                )

            else:

                message = (
                    "I can only determine your location "
                    "approximately from the network. "
                    f"Your approximate coordinates are "
                    f"{coordinate_text}."
                )

            return {
                "available":
                    True,

                "precise":
                    False,

                "source":
                    source,

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "accuracy_meters":
                    None,

                "place":
                    place,

                "message":
                    message,
            }


        accuracy = getattr(
            state,
            "accuracy_meters",
            None
        )

        place_name = (
            place.get(
                "display_name"
            )
            if place
            else None
        )


        if place_name:

            message = (
                f"You appear to be near {place_name}. "
            )

        else:

            message = (
                "I have your current coordinates, "
                "but I couldn't translate them into "
                "a street address. "
            )


        if (
            accuracy is not None
            and
            float(
                accuracy
            ) > 0
        ):

            message += (
                "Windows reports the location "
                f"accuracy at about "
                f"{float(accuracy):.0f} meters. "
            )


        message += (
            f"Your coordinates are "
            f"{coordinate_text}."
        )


        return {
            "available":
                True,

            "precise":
                True,

            "source":
                source,

            "latitude":
                latitude,

            "longitude":
                longitude,

            "accuracy_meters":
                accuracy,

            "place":
                place,

            "message":
                message,
        }


    # ---------------------------------------------------------
    # PUBLIC LOCATION RESOLUTION
    # ---------------------------------------------------------

    def get_current_location(
        self
    ):
        """
        Get the best available location.

        Windows is attempted first. If Windows cannot provide a
        position, use a coarse public-IP location so weather remains
        functional.
        """

        windows_state = (
            self._get_windows_location()
        )

        if (
            windows_state is not None
            and windows_state.available
        ):
            return windows_state


        # Preserve a known good Windows location within this runtime.
        if (
            self.last_location is not None
            and self.last_location.available
            and str(
                self.last_location.source
            ).upper().startswith(
                "WINDOWS"
            )
        ):

            return (
                self.last_location
            )


        ip_state = (
            self._get_ip_location()
        )

        if (
            ip_state is not None
            and ip_state.available
        ):

            return ip_state


        return (
            self.last_location
        )


    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def get_last_location(
        self
    ):

        return (
            self.last_location
        )


    def is_available(
        self
    ):

        return (
            self.last_location
            is not None
            and
            self.last_location.available
        )


    def diagnostic_status(
        self
    ):

        return {
            "access_granted":
                self.access_granted,

            "access_status":
                self.access_status,

            "has_last_location":
                self.last_location
                is not None,

            "last_source":
                self.last_source,

            "ip_fallback_enabled":
                self.allow_ip_fallback,

            "last_error":
                self.last_error,
        }
