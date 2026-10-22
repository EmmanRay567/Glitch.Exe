import asyncio
from datetime import datetime

from models.location_state import LocationState


class LocationService:
    """
    Windows geolocation service for GLITCH.EXE.

    Flow:
        1. Request permission once from the foreground UI thread.
        2. Retrieve a fresh Windows position on demand.
        3. Fall back to coarse Windows positioning when supported.
        4. Preserve the last known good position.
    """

    def __init__(self):
        self.access_granted = False
        self.access_status = "NOT_REQUESTED"
        self.last_location = None
        self.last_error = None

    # ---------------------------------------------------------
    # WINRT IMPORT
    # ---------------------------------------------------------

    def _load_winrt(self):
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
            )

        except Exception as error:
            self.last_error = (
                "WinRT import failed: "
                f"{type(error).__name__}: {error}"
            )

            print(
                "LOCATION ERROR //",
                self.last_error
            )

            return None

    # ---------------------------------------------------------
    # PERMISSION
    # ---------------------------------------------------------

    async def _request_access_async(self):
        loaded = self._load_winrt()

        if loaded is None:
            return False

        (
            Geolocator,
            GeolocationAccessStatus,
            _
        ) = loaded

        try:
            status = await (
                Geolocator.request_access_async()
            )

            self.access_status = (
                getattr(
                    status,
                    "name",
                    str(status)
                )
            )

            self.access_granted = (
                status
                == GeolocationAccessStatus.ALLOWED
            )

            print(
                "LOCATION ACCESS STATUS //",
                self.access_status
            )

            if not self.access_granted:
                self.last_error = (
                    "Windows returned location access status: "
                    f"{self.access_status}"
                )

            return self.access_granted

        except Exception as error:
            self.access_granted = False

            self.last_error = (
                "Permission request failed: "
                f"{type(error).__name__}: {error}"
            )

            print(
                "LOCATION ERROR //",
                self.last_error
            )

            return False

    def request_access(self):
        """
        Must be called from GLITCH's foreground UI thread.
        """

        try:
            return asyncio.run(
                self._request_access_async()
            )

        except Exception as error:
            self.access_granted = False

            self.last_error = (
                "Location permission bootstrap failed: "
                f"{type(error).__name__}: {error}"
            )

            print(
                "LOCATION ERROR //",
                self.last_error
            )

            return False

    # ---------------------------------------------------------
    # CURRENT POSITION
    # ---------------------------------------------------------

    async def _get_current_location_async(self):
        loaded = self._load_winrt()

        if loaded is None:
            return None

        (
            Geolocator,
            _,
            PositionAccuracy,
        ) = loaded

        try:
            geolocator = Geolocator()

            geolocator.desired_accuracy = (
                PositionAccuracy.DEFAULT
            )

            # On laptops without GPS, allow Windows to use a
            # less precise source when the OS supports it.
            try:
                if hasattr(
                    geolocator,
                    "allow_fallback_to_consentless_positions"
                ):
                    geolocator.allow_fallback_to_consentless_positions()
            except Exception:
                pass

            print(
                "LOCATION // requesting current Windows position..."
            )

            position = await (
                geolocator.get_geoposition_async()
            )

            coordinate = (
                position.coordinate
            )

            point = (
                coordinate.point.position
            )

            latitude = float(
                point.latitude
            )

            longitude = float(
                point.longitude
            )

            accuracy = float(
                coordinate.accuracy
            )

            state = LocationState(
                latitude=latitude,
                longitude=longitude,
                accuracy_meters=accuracy,
                source="WINDOWS_GEOLOCATION",
                available=True,
                timestamp=datetime.now(),
            )

            self.last_location = state
            self.last_error = None

            print(
                "LOCATION FIX // "
                f"accuracy={accuracy:.0f}m"
            )

            return state

        except Exception as error:
            self.last_error = (
                "Position request failed: "
                f"{type(error).__name__}: {error}"
            )

            print(
                "LOCATION ERROR //",
                self.last_error
            )

            return None

    def get_current_location(self):
        """
        Called from the weather worker/background thread.
        """

        try:
            state = asyncio.run(
                self._get_current_location_async()
            )

            if state is not None:
                return state

        except Exception as error:
            self.last_error = (
                "Location lookup failed: "
                f"{type(error).__name__}: {error}"
            )

            print(
                "LOCATION ERROR //",
                self.last_error
            )

        return self.last_location

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def get_last_location(self):
        return self.last_location

    def is_available(self):
        return (
            self.last_location is not None
            and self.last_location.available
        )

    def diagnostic_status(self):
        return {
            "access_granted":
                self.access_granted,

            "access_status":
                self.access_status,

            "has_last_location":
                self.last_location
                is not None,

            "last_error":
                self.last_error,
        }
