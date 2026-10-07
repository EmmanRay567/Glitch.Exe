import ctypes
import os
import subprocess

import psutil

from services.base_service import BaseService


class ApplicationService(BaseService):
    """
    Handles Windows application control and media-key actions.

    Keeping this code here prevents the UI layer from needing to know
    executable paths, process names, or Windows virtual-key details.
    """

    def __init__(self, event_bus=None):
        super().__init__(event_bus)

    # =========================================================
    # PATH HELPERS
    # =========================================================

    def find_existing_path(self, possible_paths):
        """Return the first application path that exists."""

        for path in possible_paths:
            expanded = os.path.expandvars(str(path))

            if os.path.exists(expanded):
                return expanded

        return None

    # =========================================================
    # APP LAUNCHING
    # =========================================================

    def launch_app(self, app_name):
        """
        Launch a supported Windows application.

        Returns:
            (True, message) on success
            (False, message) on failure
        """

        app_name = app_name.strip().lower()

        # Keep the compact names already used by GLITCH voice commands
        # and app buttons, while also accepting normal spoken names.
        aliases = {
            "visualstudio": "visual studio",
            "androidstudio": "android studio",
            "seratostudio": "serato studio",
            "seratodj": "serato dj",
        }

        normalized_name = aliases.get(app_name, app_name)

        try:
            if normalized_name in ("explorer", "file explorer"):
                subprocess.Popen(["explorer.exe"])

            elif normalized_name == "notepad":
                subprocess.Popen(["notepad.exe"])

            elif normalized_name in ("calculator", "calc"):
                subprocess.Popen(["calc.exe"])

            elif normalized_name in ("chrome", "google chrome"):
                chrome_path = self.find_existing_path(
                    [
                        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
                    ]
                )

                if chrome_path is None:
                    return False, "Chrome was not found."

                subprocess.Popen([chrome_path])

            elif normalized_name == "spotify":
                spotify_path = self.find_existing_path(
                    [
                        r"%APPDATA%\Spotify\Spotify.exe",
                        r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
                    ]
                )

                if spotify_path is None:
                    return False, "Spotify was not found."

                subprocess.Popen([spotify_path])

            elif normalized_name == "android studio":
                android_path = self.find_existing_path(
                    [
                        r"%ProgramFiles%\Android\Android Studio\bin\studio64.exe",
                        r"%ProgramFiles%\Android\Android Studio\bin\studio.exe",
                        r"%LOCALAPPDATA%\Programs\Android Studio\bin\studio64.exe",
                    ]
                )

                if android_path is None:
                    return False, "Android Studio was not found."

                subprocess.Popen([android_path])

            elif normalized_name in (
                "visual studio",
                "visual studio 2022",
                "vs",
            ):
                visual_studio_path = self.find_existing_path(
                    [
                        r"%ProgramFiles%\Microsoft Visual Studio\2022\Community\Common7\IDE\devenv.exe",
                        r"%ProgramFiles%\Microsoft Visual Studio\2022\Professional\Common7\IDE\devenv.exe",
                        r"%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\Common7\IDE\devenv.exe",
                    ]
                )

                if visual_studio_path is None:
                    return False, "Visual Studio was not found."

                subprocess.Popen([visual_studio_path])

            elif normalized_name in ("serato studio", "serato"):
                serato_studio_path = self.find_existing_path(
                    [
                        r"%ProgramFiles%\Serato\Serato Studio\Serato Studio.exe",
                        r"%LOCALAPPDATA%\Serato\Serato Studio\Serato Studio.exe",
                        r"%ProgramFiles(x86)%\Serato\Serato Studio\Serato Studio.exe",
                    ]
                )

                if serato_studio_path is None:
                    return False, "Serato Studio was not found."

                subprocess.Popen([serato_studio_path])

            elif normalized_name in ("serato dj", "serato dj pro"):
                serato_dj_path = self.find_existing_path(
                    [
                        r"%ProgramFiles%\Serato\Serato DJ Pro\Serato DJ Pro.exe",
                        r"%ProgramFiles(x86)%\Serato\Serato DJ Pro\Serato DJ Pro.exe",
                        r"%LOCALAPPDATA%\Serato\Serato DJ Pro\Serato DJ Pro.exe",
                    ]
                )

                if serato_dj_path is None:
                    return False, "Serato DJ Pro was not found."

                subprocess.Popen([serato_dj_path])

            else:
                return False, f"Application not supported: {app_name}"

            return True, f"{self._display_name(normalized_name)} launched."

        except Exception as error:
            return False, f"Unable to launch {self._display_name(normalized_name)}: {error}"

    # =========================================================
    # APP CLOSING
    # =========================================================

    def close_app(self, app_name):
        """
        Ask a supported running application to terminate gracefully.

        Unlike the old taskkill /F implementation, this does not force-kill
        the process immediately. That is safer for apps with unsaved work.
        """

        app_name = app_name.strip().lower()

        aliases = {
            "visualstudio": "visual studio",
            "androidstudio": "android studio",
            "seratostudio": "serato studio",
            "seratodj": "serato dj",
        }

        normalized_name = aliases.get(app_name, app_name)

        process_names = {
            "chrome": ["chrome.exe"],
            "google chrome": ["chrome.exe"],
            "spotify": ["Spotify.exe"],
            "notepad": ["notepad.exe"],
            "calculator": ["CalculatorApp.exe", "Calculator.exe"],
            "android studio": ["studio64.exe", "studio.exe"],
            "visual studio": ["devenv.exe"],
            "visual studio 2022": ["devenv.exe"],
            "vs": ["devenv.exe"],
            "serato studio": ["Serato Studio.exe"],
            "serato": ["Serato Studio.exe"],
            "serato dj": ["Serato DJ Pro.exe"],
            "serato dj pro": ["Serato DJ Pro.exe"],
        }

        targets = process_names.get(normalized_name)

        if targets is None:
            return False, f"Application not supported: {app_name}"

        found = False

        try:
            for process in psutil.process_iter(["pid", "name"]):
                process_name = process.info.get("name")

                if process_name in targets:
                    found = True

                    try:
                        process.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            if found:
                return True, f"{self._display_name(normalized_name)} close requested."

            return False, f"{self._display_name(normalized_name)} is not running."

        except Exception as error:
            return False, f"Unable to close {self._display_name(normalized_name)}: {error}"

    # =========================================================
    # MEDIA CONTROLS
    # =========================================================

    def press_media_key(self, virtual_key):
        """Send one Windows media-key press and release."""

        KEYEVENTF_KEYUP = 0x0002

        ctypes.windll.user32.keybd_event(
            virtual_key,
            0,
            0,
            0,
        )

        ctypes.windll.user32.keybd_event(
            virtual_key,
            0,
            KEYEVENTF_KEYUP,
            0,
        )

    def media_play_pause(self):
        self.press_media_key(0xB3)
        return True, "Media play/pause toggled."

    def media_next(self):
        self.press_media_key(0xB0)
        return True, "Next track."

    def media_previous(self):
        self.press_media_key(0xB1)
        return True, "Previous track."

    def media_stop(self):
        self.press_media_key(0xB2)
        return True, "Media stopped."

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    def _display_name(self, app_name):
        names = {
            "explorer": "File Explorer",
            "file explorer": "File Explorer",
            "chrome": "Chrome",
            "google chrome": "Chrome",
            "spotify": "Spotify",
            "android studio": "Android Studio",
            "visual studio": "Visual Studio",
            "visual studio 2022": "Visual Studio",
            "vs": "Visual Studio",
            "serato studio": "Serato Studio",
            "serato": "Serato Studio",
            "serato dj": "Serato DJ",
            "serato dj pro": "Serato DJ",
            "notepad": "Notepad",
            "calculator": "Calculator",
            "calc": "Calculator",
        }

        return names.get(app_name, app_name.title())
