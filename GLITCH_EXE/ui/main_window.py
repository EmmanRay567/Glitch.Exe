import os
import re
import json
import math
import time
from pathlib import Path


from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QStackedWidget,
    QTextEdit,
    QPlainTextEdit,
    QLineEdit,
    QSlider,
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QApplication,
    QAbstractButton,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QGraphicsColorizeEffect,
)

from PySide6.QtCore import (
    QThread,
    Signal,
    QObject,
    QTimer,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QEvent,
    Qt,
    QUrl,
    QPropertyAnimation,
    QEasingCurve,
)

from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QKeySequence,
    QShortcut,
)

from PySide6.QtMultimedia import (
    QSoundEffect,
)


from core.assistant import GlitchAssistant
from core.event_bus import EventBus
from core.command_router import CommandRouter
from core.service_container import ServiceContainer
from core.perf_monitor import PerfMonitor
from models.intent import InteractionIntent
from commands.navigation_commands import NavigationCommand
from controllers.navigation_controller import NavigationController
from controllers.gesture_controller import GestureController
from controllers.interaction_controller import InteractionController
from controllers.voice_controller import VoiceController
from controllers.power_controller import PowerController
from controllers.system_query_controller import SystemQueryController
from controllers.conversation_controller import ConversationController
from controllers.context_controller import ContextController
from controllers.weather_query_controller import WeatherQueryController
from controllers.security_query_controller import SecurityQueryController
from controllers.security_control_controller import SecurityControlController
from services.application_service import ApplicationService
from services.system_monitoring_service import SystemMonitoringService
from services.system_power_service import SystemPowerService
from services.weather_service import WeatherService
from services.location_service import LocationService
from services.adaptive_context_service import AdaptiveContextService
from services.security_engine import SecurityEngine
from services.auto_security_scan_service import AutoSecurityScanService
from services.windows_security_telemetry_service import WindowsSecurityTelemetryService
from services.auth_session import AuthSession
from services.security_alert_service import SecurityAlertService
from services.security_action_service import SecurityActionService

from voice.voice_engine import VoiceEngine
from voice.voice_listener import VoiceListener

from gestures.hand_tracker import (
    HandTracker,
    HandTrackingThread,
)

from ui.reactor_widget import ReactorWidget
from ui.status_panel import StatusPanel
from ui.command_bar import CommandBar
from ui.response_panel import ResponsePanel
from ui.auth_overlay import AuthOverlay
from services.auth_voice import AuthVoice
from services.career_service import CareerService
from ui.career_matrix_page import CareerMatrixPage
from ui.security_alert_overlay import SecurityAlertOverlay
from ui.security_findings_overlay import SecurityFindingsOverlay

# NEW
from ui.system_matrix_widget import SystemMatrixWidget
from ui.security_matrix_widget import SecurityMatrixWidget
from ui.hud_effects import (
    HudTransitionOverlay,
    HandHologramOverlay,
    HoloNavRail,
    HoloProjector,
    WarpTransitionOverlay,
    make_whoosh_wav,
    PAGE_TITLES,
)
from services.sports_service import SportsService
from ui.sports_holo_page import SportsHoloPage, SportsBackdrop
from ui.ambient_player import AmbientPlayer


# =========================================================
# AI WORKER
# =========================================================

class AIWorker(QObject):

    finished = Signal(str)
    error = Signal(str)

    # Pieces of the reply while it is being written (streaming mode).
    partial = Signal(str)

    def __init__(
        self,
        assistant,
        message,
        mode="CHAT",
        stream=False
    ):

        super().__init__()

        self.assistant = assistant
        self.message = message
        self.mode = mode
        self.stream = stream


    def run(self):

        try:

            if self.mode == "SEARCH":

                response = (
                    self.assistant
                    .search_web(
                        self.message
                    )
                )

            elif (
                self.stream
                and hasattr(self.assistant, "ask_stream")
            ):

                # Speak while the reply is still being written.
                for delta in self.assistant.ask_stream(
                    self.message
                ):

                    self.partial.emit(
                        delta
                    )

                response = (
                    self.assistant.last_reply
                )

            else:

                response = (
                    self.assistant
                    .ask(
                        self.message
                    )
                )


            self.finished.emit(
                response
            )


        except Exception as error:

            self.error.emit(
                str(error)
            )


# =========================================================
# WEATHER WORKER
# =========================================================

class WeatherWorker(QObject):

    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        weather_query_controller,
        command
    ):

        super().__init__()

        self.weather_query_controller = (
            weather_query_controller
        )

        self.command = (
            command
        )


    def run(self):

        try:

            result = (
                self.weather_query_controller
                .handle_query(
                    self.command
                )
            )

            self.finished.emit(
                result
            )

        except Exception as error:

            self.error.emit(
                str(
                    error
                )
            )


# =========================================================
# SECURITY SCAN WORKER
# =========================================================

class SecurityScanWorker(QObject):

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        security_engine,
        target,
        recursive=True,
        max_files=5000
    ):

        super().__init__()

        self.security_engine = (
            security_engine
        )

        self.target = (
            target
        )

        self.recursive = (
            recursive
        )

        self.max_files = (
            max_files
        )


    def run(
        self
    ):

        try:

            results = (
                self.security_engine
                .scan_directory(
                    self.target,
                    recursive=self.recursive,
                    max_files=self.max_files
                )
            )

            self.finished.emit(
                results
            )

        except Exception as error:

            self.error.emit(
                str(error)
            )


# =========================================================
# WINDOWS SECURITY TELEMETRY WORKER
# =========================================================

class WindowsSecurityTelemetryWorker(QObject):

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        telemetry_service
    ):

        super().__init__()

        self.telemetry_service = (
            telemetry_service
        )


    def run(
        self
    ):

        try:

            snapshot = (
                self.telemetry_service
                .collect_snapshot()
            )

            self.finished.emit(
                snapshot
            )

        except Exception as error:

            self.error.emit(
                str(error)
            )


# =========================================================
# FINGER CURSOR
# =========================================================

class FingerCursor(QWidget):

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )


        self.setFixedSize(
            42,
            42
        )


        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )


        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )


        self.hide()


    def paintEvent(
        self,
        event
    ):

        painter = QPainter(
            self
        )


        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )


        center = QPointF(
            self.width() / 2,
            self.height() / 2
        )


        # =============================================
        # OUTER RING
        # =============================================

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    150
                ),
                2
            )
        )


        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )


        painter.drawEllipse(
            center,
            17,
            17
        )


        # =============================================
        # INNER RING
        # =============================================

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    220
                ),
                1
            )
        )


        painter.drawEllipse(
            center,
            9,
            9
        )


        # =============================================
        # CENTER DOT
        # =============================================

        painter.setBrush(
            QBrush(
                QColor(
                    57,
                    255,
                    120,
                    220
                )
            )
        )


        painter.setPen(
            Qt.PenStyle.NoPen
        )


        painter.drawEllipse(
            center,
            3,
            3
        )


# =========================================================
# MAIN WINDOW
# =========================================================

class GlitchWindow(QMainWindow):

    def __init__(self):

        super().__init__()


        # =================================================
        # PATHS
        # =================================================

        self.base_dir = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )


        self.data_dir = (
            self.base_dir
            / "data"
        )


        self.data_dir.mkdir(
            exist_ok=True
        )


        self.settings_file = (
            self.data_dir
            / "glitch_settings.json"
        )


        # =================================================
        # SETTINGS
        # =================================================

        self.settings_data = {

            "voice_enabled":
                True,

            "ui_sound_volume":
                55,

            "gesture_dwell_ms":
                450,

            "weather_location":
                "",

            # Hand control: camera tracking for swipes / pinch / pointer.
            "gesture_control_enabled":
                True,

            # The holographic hand drawn over the HUD (visual only).
            "hand_hologram_enabled":
                True,

            # Freezes the animated reactor background into a still
            # image: the biggest single saving on slower machines.
            "performance_mode":
                False,
        }


        self.load_settings()


        self.voice_enabled = (
            self.settings_data[
                "voice_enabled"
            ]
        )

        self.gesture_control_enabled = bool(
            self.settings_data.get(
                "gesture_control_enabled",
                True
            )
        )

        self.hand_hologram_enabled = bool(
            self.settings_data.get(
                "hand_hologram_enabled",
                True
            )
        )


        self.ui_sound_volume = (
            self.settings_data[
                "ui_sound_volume"
            ]
            / 100.0
        )


        self.button_dwell_ms = (
            self.settings_data[
                "gesture_dwell_ms"
            ]
        )


        # =================================================
        # AI
        # =================================================

        self.assistant = (
            GlitchAssistant()
        )


        # =================================================
        # EVENT BUS
        # =================================================

        # One shared EventBus is created first so every
        # service and controller can publish to the same
        # internal GLITCH event network.
        self.event_bus = (
            EventBus()
        )


        # =================================================
        # SERVICE CONTAINER
        # =================================================

        # ServiceContainer is GLITCH's central registry for
        # reusable application/business services.
        self.services = (
            ServiceContainer()
        )


        # =================================================
        # APPLICATION SERVICE
        # =================================================

        self.services.register(
            "application",
            ApplicationService(
                self.event_bus
            )
        )


        self.application_service = (
            self.services.get(
                "application"
            )
        )


        # =================================================
        # SYSTEM MONITORING SERVICE
        # =================================================

        # SystemMonitoringService owns CPU, RAM, battery,
        # network, and hostname collection. The UI only
        # displays the snapshot it receives.
        self.services.register(
            "system_monitoring",
            SystemMonitoringService(
                self.event_bus
            )
        )


        self.system_monitoring_service = (
            self.services.get(
                "system_monitoring"
            )
        )


        # =================================================
        # SYSTEM POWER SERVICE
        # =================================================

        # Low-level Windows power operations live in a
        # dedicated service. They are never called directly
        # from voice or keyboard input.
        self.services.register(
            "system_power",
            SystemPowerService(
                self.event_bus
            )
        )


        self.system_power_service = (
            self.services.get(
                "system_power"
            )
        )


        # PowerController owns the safety/confirmation state.
        self.power_controller = (
            PowerController(
                self.system_power_service
            )
        )


        # =================================================
        # SYSTEM QUERY CONTROLLER
        # =================================================

        # Answers deterministic questions about the local
        # computer from the HardwareState Digital Twin.
        self.system_query_controller = (
            SystemQueryController(
                self.system_monitoring_service
            )
        )


        # =================================================
        # CONVERSATION CONTROLLER
        # =================================================

        # Wake once, then allow natural follow-up speech for a
        # short active session without repeating "Glitch".
        self.conversation_controller = (
            ConversationController(
                timeout_seconds=40.0
            )
        )


        # =================================================
        # CONTEXT CONTROLLER
        # =================================================

        # Adaptive context owns rolling conversation memory
        # plus a lightweight long-term user profile.
        self.adaptive_context_service = (
            AdaptiveContextService()
        )


        # Resolves short conversational follow-ups such as
        # "what about CPU?", "why is it doing that?",
        # and "close it".
        self.context_controller = (
            ContextController(
                self.adaptive_context_service
            )
        )


        # Lets GLITCH's quick spoken lines know your preferred form of
        # address and log what it just did for the AI to refer back to.
        self.conversation_controller.attach_context(
            self.adaptive_context_service
        )


        # =================================================
        # PHASE 3 SECURITY ENGINE
        # =================================================

        self.security_engine = (
            SecurityEngine()
        )


        self.windows_security_telemetry_service = (
            WindowsSecurityTelemetryService()
        )


        self.security_query_controller = (
            SecurityQueryController(
                self.security_engine
            )
        )


        self.security_control_controller = (
            SecurityControlController()
        )

        self.security_action_service = (
            SecurityActionService(
                self.security_engine
            )
        )

        self.pending_security_action = None


        self.auto_security_scan_service = (
            AutoSecurityScanService(
                self.security_engine,
                scan_targets=[
                    Path.home()
                    / "Downloads"
                ],
                idle_seconds=120,
                poll_seconds=15,
                max_files_per_pass=150,
            )
        )


        self.auto_security_scan_service.start()


        self.security_thread = None
        self.security_worker = None
        self.security_should_speak = False


        self.windows_security_thread = None
        self.windows_security_worker = None


        self.windows_security_timer = QTimer(
            self
        )

        self.windows_security_timer.timeout.connect(
            self.start_windows_security_refresh
        )

        self.windows_security_timer.start(
            30000
        )


        # =================================================
        # WEATHER INTELLIGENCE
        # =================================================

        self.location_service = (
            LocationService()
        )


        self.weather_service = (
            WeatherService()
        )


        self.weather_query_controller = (
            WeatherQueryController(
                self.weather_service,
                default_location=(
                    self.settings_data
                    .get(
                        "weather_location"
                    )
                    or None
                ),
                location_service=
                    self.location_service
            )
        )


        self.weather_thread = None
        self.weather_worker = None
        self.weather_should_speak = False

        # Tracks what the shared weather/location worker
        # is currently doing so the HUD can show the
        # correct live status.
        self.weather_request_mode = "WEATHER"


        # =================================================
        # NAVIGATION ARCHITECTURE
        # =================================================


        # NavigationController owns the navigation decision.
        # It asks this window to render the requested page.
        self.navigation_controller = (
            NavigationController(
                self,
                self.event_bus
            )
        )


        # CommandRouter lets buttons, voice, gestures, and
        # future agents use the same navigation command path.
        self.command_router = (
            CommandRouter()
        )


        self.command_router.register(
            "NAVIGATE",
            lambda destination:
                NavigationCommand(
                    self.navigation_controller,
                    destination
                )
        )


        # =================================================
        # INTERACTION CONTROLLER
        # =================================================

        # Phase 1 unified interaction layer.
        # Voice, gestures, mouse, keyboard, and future agents
        # can all express actions as InteractionIntent objects.
        self.interaction_controller = (
            InteractionController(
                self.command_router,
                self.event_bus
            )
        )


        # =================================================
        # GESTURE CONTROLLER
        # =================================================

        # HandTracker detects the physical gesture.
        # GestureController converts that gesture into an
        # InteractionIntent and sends it through the unified
        # InteractionController.
        self.gesture_controller = (
            GestureController(
                self.interaction_controller,
                self.event_bus
            )
        )


        # =================================================
        # VOICE CONTROLLER
        # =================================================

        # Voice navigation now enters the same Phase 1
        # InteractionIntent pipeline used by gestures.
        # Media and application control still route through
        # ApplicationService during this migration step.
        self.voice_controller = (
            VoiceController(
                self.interaction_controller,
                self.application_service,
                self.event_bus
            )
        )


        # =================================================
        # INTERACTION HISTORY EVENT SUBSCRIPTION
        # =================================================

        self.event_bus.subscribe(
            "INTERACTION_PROCESSED",
            self.handle_interaction_processed
        )


        self.ai_thread = None
        self.ai_worker = None


        self.pending_ai_mode = (
            "CHAT"
        )


        # =================================================
        # VOICE OUTPUT
        # =================================================

        self.voice_engine = (
            VoiceEngine()
        )


        self.voice_output_active = (
            False
        )


        # =================================================
        # VOICE INPUT
        # =================================================

        self.voice_listener = (
            VoiceListener()
        )


        self.voice_listener_active = (
            False
        )


        # =================================================
        # HAND TRACKING
        # =================================================

        self.hand_tracker = (
            HandTracker()
        )


        self.hand_thread = (
            HandTrackingThread(
                self.hand_tracker
            )
        )


        self.hovered_button = None
        self.hover_start_time = None


        self.finger_x = 0
        self.finger_y = 0


        # =================================================
        # CURRENT MODE
        # =================================================

        self.current_mode = (
            "HOME"
        )


        # =================================================
        # WINDOW
        # =================================================

        self.setWindowTitle(
            "GLITCH.EXE"
        )


        self.resize(
            1200,
            760
        )


        self.setMinimumSize(
            1000,
            650
        )


        self.setStyleSheet(
            """
            QMainWindow {

                background:
                    #020504;
            }


            QLabel {

                color:
                    #caffd7;

                font-family:
                    Consolas;
            }


            QPushButton {

                background:
                    rgba(
                        0,
                        22,
                        12,
                        150
                    );

                color:
                    #39ff78;

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        100
                    );

                border-radius:
                    7px;

                padding:
                    8px;

                font-family:
                    Consolas;
            }


            QPushButton:hover {

                background:
                    rgba(
                        57,
                        255,
                        120,
                        40
                    );

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        220
                    );
            }


            QLineEdit,
            QTextEdit,
            QPlainTextEdit {

                background:
                    rgba(
                        0,
                        10,
                        7,
                        180
                    );

                color:
                    #baffca;

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        90
                    );

                border-radius:
                    7px;

                padding:
                    8px;

                font-family:
                    Consolas;
            }


            QCheckBox {

                color:
                    #39ff78;

                font-family:
                    Consolas;
            }
            """
        )


        # =================================================
        # CENTRAL
        # =================================================

        self.central_widget = (
            QWidget()
        )


        self.central_widget.setStyleSheet(
            "background: transparent;"
        )


        self.setCentralWidget(
            self.central_widget
        )


        # =================================================
        # REACTOR
        # =================================================

        self.reactor = (
            ReactorWidget(
                self.central_widget
            )
        )


        self.reactor.lower()


        # Team-coloured background that replaces the green reactor
        # backdrop while the Sports Nexus is open.
        self.sports_backdrop = (
            SportsBackdrop(
                self.central_widget
            )
        )


        # =================================================
        # HOLOGRAPHIC NAVIGATION (replaces the old sidebar)
        # =================================================

        self.holo_nav = (
            HoloNavRail(
                self.central_widget
            )
        )

        # Compatibility alias: older code still refers to
        # self.sidebar.home_button, self.sidebar.chat_button, ...
        self.sidebar = self.holo_nav


        self.holo_projector = (
            HoloProjector(
                self.central_widget
            )
        )

        self.holo_nav.hovered.connect(
            self.holo_projector.preview
        )


        # =================================================
        # UI SOUNDS
        # =================================================

        self.ui_sounds = {}


        audio_dir = (
            self.base_dir
            / "audio"
        )


        sound_files = {

            "HOME":
                "ui_home.wav",

            "CHAT":
                "ui_chat.wav",

            "CREATE":
                "ui_create.wav",

            "SEARCH":
                "ui_search.wav",

            "CODE":
                "ui_code.wav",

            "APPS":
                "ui_apps.wav",

            "SETTINGS":
                "ui_settings.wav",
        }


        for (
            name,
            filename
        ) in sound_files.items():

            effect = (
                QSoundEffect(
                    self
                )
            )


            effect.setSource(
                QUrl.fromLocalFile(
                    str(
                        audio_dir
                        / filename
                    )
                )
            )


            effect.setVolume(
                self.ui_sound_volume
            )


            self.ui_sounds[
                name
            ] = effect


        # =================================================
        # STATUS PANEL
        # =================================================

        self.status_panel = (
            StatusPanel(
                self.central_widget
            )
        )


        # =================================================
        # VOICE INPUT BADGE
        # =================================================

        self.voice_input_badge = QLabel(
            self.central_widget
        )


        self.voice_input_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        self.voice_input_badge.setWordWrap(
            True
        )


        self.set_voice_input_status(
            "STARTING"
        )


        # =================================================
        # PAGE STACK
        # =================================================

        self.page_stack = (
            QStackedWidget(
                self.central_widget
            )
        )


        self.page_stack.setStyleSheet(
            "background: transparent;"
        )


        # =================================================
        # BUILD PAGES
        # =================================================

        self.home_page = (
            self.build_home_page()
        )


        # NEW SYSTEM MATRIX PAGE
        # Phase 2: inject the shared SystemMonitoringService
        # so the System Matrix reads from the HardwareState
        # Digital Twin instead of collecting telemetry itself.
        self.system_matrix_page = (
            SystemMatrixWidget(
                self.system_monitoring_service
            )
        )


        # PHASE 3 SECURITY MATRIX
        # Visual shell first; live security telemetry is
        # connected in the next Phase 3 step.
        self.security_matrix_page = (
            SecurityMatrixWidget(
                self.security_engine
            )
        )


        # =================================================
        # PHASE 3 SECURITY ALERT INTELLIGENCE
        # =================================================

        self.security_alert_service = (
            SecurityAlertService()
        )

        self.security_alert_queue = []
        self.security_alert_active = False

        # Existing unresolved findings are restored by the
        # Security Matrix, but they are silently primed here
        # so GLITCH does not repeat old voice/HUD alerts
        # every time the assistant starts.
        try:

            self.security_alert_service.prime(
                self.security_matrix_page
                .get_active_security_findings()
            )

        except Exception:

            pass


        QTimer.singleShot(
            1200,
            self.start_windows_security_refresh
        )


        self.chat_page = (
            self.build_chat_page()
        )


        self.create_page_widget = (
            self.build_create_page()
        )


        self.search_page = (
            self.build_search_page()
        )


        self.code_page = (
            self.build_code_page()
        )


        self.apps_page = (
            self.build_apps_page()
        )


        self.settings_page = (
            self.build_settings_page()
        )


        # =================================================
        # SPORTS NEXUS (double-tap / "Glitch, show me sports")
        # =================================================

        self.sports_service = (
            SportsService()
        )

        self.sports_page = (
            SportsHoloPage(
                self.sports_service
            )
        )

        # Recolour the HUD when you switch teams inside the Nexus.
        self.sports_page.team_changed.connect(
            lambda key: self.update_sports_theme(self.current_mode)
        )

        self.sports_service.team_updated.connect(
            lambda key, data: self.update_sports_theme(self.current_mode)
        )

        # Team questions to the AI get the live sports data.
        self.context_controller.sports_service = (
            self.sports_service
        )

        # Warm the cache in the background so the page opens instantly.
        QTimer.singleShot(
            4000,
            self.sports_service.refresh
        )

        # =================================================
        # CAREER MATRIX (campus, jobs, world news, style)
        # =================================================

        self.career_service = (
            CareerService()
        )

        self.career_page = (
            CareerMatrixPage(
                self.career_service
            )
        )

        # Career questions to the AI get the live Career Matrix data.
        self.context_controller.career_service = (
            self.career_service
        )

        # Outfit picks / product search results are spoken.
        self.career_page.announce.connect(
            self.say_confirmation
        )

        QTimer.singleShot(
            6000,
            self.career_service.refresh
        )

        self._pre_sports_mode = "HOME"

        self._warp_in_progress = False

        self._last_empty_tap = 0.0


        for page in [

            self.home_page,

            self.system_matrix_page,

            self.security_matrix_page,

            self.chat_page,

            self.create_page_widget,

            self.search_page,

            self.code_page,

            self.apps_page,

            self.settings_page,

            self.sports_page,

            self.career_page,

        ]:

            self.page_stack.addWidget(
                page
            )


        # =================================================
        # RESPONSE PANEL
        # =================================================

        self.response_panel = (
            ResponsePanel(
                self.central_widget
            )
        )


        # =================================================
        # COMMAND BAR
        # =================================================

        self.command_bar = (
            CommandBar(
                self.central_widget
            )
        )


        # =================================================
        # FINGER CURSOR
        # =================================================

        self.finger_cursor = (
            FingerCursor(
                self.central_widget
            )
        )


        self.finger_cursor.raise_()


        # =================================================
        # JARVIS HUD EFFECTS
        # =================================================

        self.hand_overlay = (
            HandHologramOverlay(
                self.central_widget
            )
        )

        self.transition_overlay = (
            HudTransitionOverlay(
                self.central_widget
            )
        )


        # Cinematic jump into / out of the Sports Nexus.
        self.warp_overlay = (
            WarpTransitionOverlay(
                self.central_widget
            )
        )

        self.warp_sounds = {}

        for name, reverse in (("in", False), ("out", True)):

            try:

                path = (
                    self.base_dir
                    / "audio"
                    / f"ui_sports_whoosh_{name}.wav"
                )

                path.parent.mkdir(parents=True, exist_ok=True)

                if not path.exists():

                    make_whoosh_wav(path, reverse=reverse)

                effect = QSoundEffect(self)

                effect.setSource(QUrl.fromLocalFile(str(path)))

                effect.setVolume(0.9)

                self.warp_sounds[name] = effect

            except Exception as error:

                print("WHOOSH SOUND ERROR:", error)


        # Double-click anywhere empty on the HUD opens the Sports Nexus.
        QApplication.instance().installEventFilter(
            self
        )

        self.security_alert_overlay = (
            SecurityAlertOverlay(
                self.central_widget
            )
        )

        self.security_alert_overlay.alert_finished.connect(
            self.handle_security_alert_finished
        )


        self.security_findings_overlay = (
            SecurityFindingsOverlay(
                self.central_widget
            )
        )

        self.security_findings_overlay.closed.connect(
            self.handle_security_findings_closed
        )

        # Direction of the swipe that triggered the current
        # navigation:
        #  1 = sweep left -> right
        # -1 = sweep right -> left
        #  0 = non-swipe navigation
        self.pending_sweep_direction = 0

        self.pending_sweep_vertical = False


        # =================================================
        # FACE-ONLY SECURITY GATE
        # =================================================

        # Camera / face verification is the only biometric factor.
        # Voice biometrics are intentionally not used.
        self.authenticated = False
        self._authenticated_systems_started = False
        self._face_unlock_in_progress = False


        self.auth_session = (
            AuthSession(
                self.data_dir,
                self
            )
        )


        self.auth_overlay = (
            AuthOverlay(
                self.central_widget
            )
        )


        # Face-only UI wiring.
        self.auth_session.stage_changed.connect(
            self.auth_overlay.set_stage
        )

        self.auth_session.preview_frame.connect(
            self.auth_overlay.set_preview
        )

        self.auth_session.face_status.connect(
            self.auth_overlay.set_face_status
        )

        # Watch the face status directly so GLITCH unlocks as soon
        # as the camera verification succeeds, before any legacy
        # voice-biometric stage can begin.
        self.auth_session.face_status.connect(
            self.handle_face_auth_status
        )

        # Some AuthSession builds expose a generic factor result.
        # We listen only to identify a successful FACE result.
        self.auth_session.factor_result.connect(
            self.handle_face_factor_result
        )

        # The AuthSession is the authority for successful authentication.
        # When the face scan passes, it emits granted(AuthResult).
        self.auth_session.granted.connect(
            self.handle_auth_granted
        )

        self.auth_session.denied.connect(
            self.handle_auth_denied
        )

        self.auth_session.lockdown.connect(
            self.auth_overlay.show_lockdown
        )

        self.auth_overlay.retry_requested.connect(
            self.start_authentication
        )

        self.auth_overlay.unlock_finished.connect(
            self.finish_unlock
        )


        # GLITCH speaks at the gate: "Scanning user", "Please show
        # yourself...", "Sorry. You are not 404...", and a personal
        # welcome that learns your routine (data/auth/owner_memory.json).
        self.auth_voice = AuthVoice(
            self.voice_engine,
            self.data_dir,
            enabled=lambda: getattr(self, "voice_enabled", True),
            parent=self,
            sounds_dir=self.base_dir / "audio",
        )

        self.auth_voice.attach(
            self.auth_session
        )

        self._auth_greeting = None


        # =================================================
        # HOLO NAV CONNECTIONS
        # =================================================

        for nav_key, nav_button in (
            self.holo_nav.buttons.items()
        ):

            if nav_key == "CAREER_MATRIX":

                # Same pipeline, with a direct fallback in case the
                # navigation controller doesn't know this page yet.
                nav_button.clicked.connect(
                    lambda checked=False:
                        self._open_career("MOUSE")
                )

                continue

            nav_button.clicked.connect(
                lambda checked=False, key=nav_key:
                    self.navigate_with_intent(
                        key,
                        "MOUSE"
                    )
            )


        # =================================================
        # COMMAND BAR
        # =================================================

        self.command_bar.commandSubmitted.connect(
            self.handle_command
        )


        # =================================================
        # VOICE OUTPUT CONNECTIONS
        # =================================================

        self.voice_engine.speech_started.connect(
            self.handle_voice_started
        )


        self.voice_engine.speech_finished.connect(
            self.handle_voice_finished
        )


        # Full-duplex voice: the mic stays open while GLITCH talks and
        # you can interrupt it just by speaking.
        self.voice_listener.set_echo_reference(
            self.voice_engine.output_level
        )

        self.voice_listener.barge_in.connect(
            self.handle_barge_in
        )


        self.voice_engine.voice_error.connect(
            self.handle_voice_error
        )


        # =================================================
        # GRID AMBIENCE (loops the whole time GLITCH is open)
        # =================================================

        self.ambience = AmbientPlayer(
            self.base_dir / "audio" / "grid_ambience.wav",
            volume=0.85,          # louder background (max 1.0)
            duck_volume=0.60,     # level while you or GLITCH are talking
            parent=self
        )

        self.ambience.start()

        # The microphone hears the ambience too. Tell the listener what
        # GLITCH is playing (voice + ambience) so neither one is ever
        # mistaken for you talking or interrupts GLITCH mid-sentence.
        self.voice_listener.set_echo_reference(
            lambda: (
                self.voice_engine.output_level()
                + self.ambience.output_level()
            )
        )

        # Drop to a whisper while GLITCH talks or while you talk,
        # so it never covers the voice or confuses the microphone.
        self.voice_engine.speech_started.connect(
            lambda: self.ambience.duck("glitch", True)
        )

        self.voice_engine.speech_finished.connect(
            lambda: self.ambience.duck("glitch", False)
        )

        if hasattr(self.voice_listener, "user_speaking"):

            self.voice_listener.user_speaking.connect(
                lambda speaking: self.ambience.duck("you", speaking)
            )


        # =================================================
        # VOICE INPUT CONNECTIONS
        # =================================================

        self.voice_listener.transcript_ready.connect(
            self.handle_voice_command
        )


        self.voice_listener.listening_started.connect(
            self.handle_voice_listening_started
        )


        self.voice_listener.listening_stopped.connect(
            self.handle_voice_listening_stopped
        )


        self.voice_listener.voice_error.connect(
            self.handle_voice_listener_error
        )


        # =================================================
        # HAND CONNECTIONS
        # =================================================

        # The old laggy finger_cursor widget stays disconnected.
        # Instead, the hand overlay draws a lightweight holographic
        # pointer on the index fingertip, highlights the HUD button
        # it is aiming at, and a pinch clicks that button.

        self.hand_tracker.finger_moved.connect(
            self.handle_finger_hover
        )

        self.hand_tracker.hand_lost.connect(
            self.clear_finger_hover
        )

        self.hand_tracker.pinch_detected.connect(
            self.handle_hud_pinch
        )


        self.hand_tracker.landmarks_updated.connect(
            self.hand_overlay.set_landmarks
        )

        self.hand_tracker.hand_lost.connect(
            self.hand_overlay.clear_hand
        )

        self.hand_tracker.swipe_charge.connect(
            self.hand_overlay.set_swipe_charge
        )

        self.hand_tracker.pinch_detected.connect(
            self.hand_overlay.flash_pinch
        )


        # SWIPE CONNECTIONS
        self.hand_tracker.swipe_left.connect(
            self.handle_swipe_left
        )


        self.hand_tracker.swipe_right.connect(
            self.handle_swipe_right
        )


        # Vertical swipes move between sections
        # (HOME, CHAT, CREATE, SEARCH, CODE, APPS, SETTINGS).
        self.hand_tracker.swipe_up.connect(
            self.handle_swipe_up
        )

        self.hand_tracker.swipe_down.connect(
            self.handle_swipe_down
        )

        self.hand_tracker.swipe_charge_vertical.connect(
            self.hand_overlay.set_swipe_charge_vertical
        )


        self.hand_tracker.tracking_started.connect(
            self.handle_tracking_started
        )


        self.hand_tracker.tracking_stopped.connect(
            self.handle_tracking_stopped
        )


        self.hand_tracker.tracking_error.connect(
            self.handle_gesture_error
        )


        # =================================================
        # INITIAL STATUS
        # =================================================

        self.status_panel.set_core_status(
            "ONLINE"
        )


        self.status_panel.set_voice_status(
            "ONLINE"
            if self.voice_enabled
            else "MUTED"
        )


        memory_count = (
            self.assistant
            .memory
            .count_memories()
        )


        self.status_panel.set_memory_status(
            f"ACTIVE [{memory_count}]"
        )


        self.status_panel.set_gesture_status(
            "STANDBY"
        )


        self.status_panel.set_health_status(
            "OPTIMAL"
        )


        # =================================================
        # SYSTEM TIMER
        # =================================================

        self.system_timer = (
            QTimer(
                self
            )
        )


        self.system_timer.timeout.connect(
            self.update_system_stats
        )


        self.system_timer.start(
            1000
        )


        # =================================================
        # DEFAULT PAGE
        # =================================================

        self.page_stack.setCurrentWidget(
            self.home_page
        )


        self.set_active_sidebar_button(
            self.sidebar.home_button
        )


        self.holo_projector.set_active(
            "HOME"
        )


        # Gesture / hologram toggles (saved between sessions).
        self.hand_overlay.set_hologram_visible(
            self.hand_hologram_enabled
        )

        QShortcut(
            QKeySequence("Ctrl+G"),
            self,
            activated=lambda: self.set_gesture_control(
                not self.gesture_control_enabled,
                announce=True
            )
        )

        QShortcut(
            QKeySequence("Ctrl+P"),
            self,
            activated=lambda: self.set_performance_mode(
                not self.performance_mode,
                announce=True
            )
        )

        self.performance_mode = False

        if self.settings_data.get("performance_mode"):

            QTimer.singleShot(
                1500,
                lambda: self.set_performance_mode(True)
            )

        # Prints where the UI freezes (see core/perf_monitor.py).
        self.perf_monitor = PerfMonitor(self)

        QShortcut(
            QKeySequence("Ctrl+H"),
            self,
            activated=lambda: self.set_hand_hologram(
                not self.hand_hologram_enabled,
                announce=True
            )
        )


        self.response_panel.set_response(
            "GLITCH.EXE ONLINE // SYSTEMS NOMINAL"
        )


        self.update_layout()
        self.update_system_stats()


        self.handle_interaction_processed(
            None
        )


        # =================================================
        # STARTUP // FACE-ONLY SECURE BOOT
        # =================================================

        QTimer.singleShot(
            250,
            self.start_authentication
        )


    # =====================================================
    # LOCATION ACCESS
    # =====================================================

    def initialize_location_access(
        self
    ):

        granted = (
            self.location_service
            .request_access()
        )


        if granted:

            print(
                "LOCATION ACCESS // GRANTED"
            )

        else:

            print(
                "LOCATION ACCESS // UNAVAILABLE"
            )

            if (
                self.location_service
                .last_error
            ):

                print(
                    "LOCATION ERROR //",
                    self.location_service
                    .last_error
                )


    # =====================================================
    # VOICE INPUT BADGE
    # =====================================================

    def set_voice_input_status(
        self,
        status,
        detail=None
    ):

        if detail:

            text = (
                f"VOICE INPUT\n"
                f"{status}\n"
                f"{detail}"
            )

        else:

            text = (
                f"VOICE INPUT\n"
                f"{status}"
            )


        self.voice_input_badge.setText(
            text
        )


        if status == "ERROR":

            self.voice_input_badge.setStyleSheet(
                """
                QLabel {

                    background:
                        rgba(
                            45,
                            0,
                            0,
                            180
                        );

                    color:
                        #ff7070;

                    border:
                        1px solid
                        rgba(
                            255,
                            80,
                            80,
                            170
                        );

                    border-radius:
                        8px;

                    padding:
                        7px;

                    font-family:
                        Consolas;

                    font-size:
                        10px;

                    font-weight:
                        bold;
                }
                """
            )


        elif status == "HEARD":

            self.voice_input_badge.setStyleSheet(
                """
                QLabel {

                    background:
                        rgba(
                            15,
                            55,
                            25,
                            190
                        );

                    color:
                        #7dff9e;

                    border:
                        1px solid
                        rgba(
                            90,
                            255,
                            145,
                            220
                        );

                    border-radius:
                        8px;

                    padding:
                        7px;

                    font-family:
                        Consolas;

                    font-size:
                        10px;

                    font-weight:
                        bold;
                }
                """
            )


        elif status == "PROCESSING":

            self.voice_input_badge.setStyleSheet(
                """
                QLabel {

                    background:
                        rgba(
                            20,
                            35,
                            10,
                            180
                        );

                    color:
                        #c7ff6b;

                    border:
                        1px solid
                        rgba(
                            190,
                            255,
                            90,
                            170
                        );

                    border-radius:
                        8px;

                    padding:
                        7px;

                    font-family:
                        Consolas;

                    font-size:
                        10px;

                    font-weight:
                        bold;
                }
                """
            )


        else:

            self.voice_input_badge.setStyleSheet(
                """
                QLabel {

                    background:
                        rgba(
                            0,
                            16,
                            9,
                            165
                        );

                    color:
                        #39ff78;

                    border:
                        1px solid
                        rgba(
                            57,
                            255,
                            120,
                            100
                        );

                    border-radius:
                        8px;

                    padding:
                        7px;

                    font-family:
                        Consolas;

                    font-size:
                        10px;

                    font-weight:
                        bold;
                }
                """
            )


    # =====================================================
    # SETTINGS STORAGE
    # =====================================================

    def load_settings(self):

        try:

            if self.settings_file.exists():

                with open(
                    self.settings_file,
                    "r",
                    encoding="utf-8"
                ) as file:

                    saved = (
                        json.load(
                            file
                        )
                    )


                self.settings_data.update(
                    saved
                )


        except Exception as error:

            print(
                "SETTINGS LOAD ERROR:",
                error
            )


    def save_settings(self):

        try:

            with open(
                self.settings_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    self.settings_data,
                    file,
                    indent=4
                )


        except Exception as error:

            print(
                "SETTINGS SAVE ERROR:",
                error
            )


    # =====================================================
    # HEADER
    # =====================================================

    def create_header(
        self,
        mode,
        title,
        subtitle
    ):

        container = (
            QWidget()
        )


        layout = QVBoxLayout(
            container
        )


        layout.setContentsMargins(
            0,
            0,
            0,
            12
        )


        mode_label = QLabel(
            f"// {mode}"
        )


        mode_label.setStyleSheet(
            """
            color:
                rgba(
                    57,
                    255,
                    120,
                    150
                );

            font-size:
                11px;
            """
        )


        title_label = QLabel(
            title
        )


        title_label.setStyleSheet(
            """
            color:
                #39ff78;

            font-size:
                22px;

            font-weight:
                bold;
            """
        )


        subtitle_label = QLabel(
            subtitle
        )


        subtitle_label.setWordWrap(
            True
        )


        subtitle_label.setStyleSheet(
            """
            color:
                rgba(
                    205,
                    255,
                    220,
                    170
                );

            font-size:
                11px;
            """
        )


        layout.addWidget(
            mode_label
        )


        layout.addWidget(
            title_label
        )


        layout.addWidget(
            subtitle_label
        )


        return container


    # =====================================================
    # STAT CARD
    # =====================================================

    def make_stat_card(
        self,
        name
    ):

        frame = (
            QFrame()
        )


        frame.setStyleSheet(
            """
            QFrame {

                background:
                    rgba(
                        0,
                        20,
                        12,
                        90
                    );

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        70
                    );

                border-radius:
                    8px;
            }
            """
        )


        layout = QVBoxLayout(
            frame
        )


        title = QLabel(
            name
        )


        title.setStyleSheet(
            """
            color:
                rgba(
                    185,
                    255,
                    210,
                    150
                );

            font-size:
                10px;
            """
        )


        value = QLabel(
            "---"
        )


        value.setStyleSheet(
            """
            color:
                #39ff78;

            font-size:
                17px;

            font-weight:
                bold;
            """
        )


        layout.addWidget(
            title
        )


        layout.addWidget(
            value
        )


        return (
            frame,
            value
        )


    # =====================================================
    # HOME PAGE
    # =====================================================

    def build_home_page(self):

        page = (
            QWidget()
        )


        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "HOME",

                "GLITCH.EXE SYSTEM CORE",

                "Live workstation telemetry and assistant status."
            )
        )


        grid = (
            QGridLayout()
        )


        card, self.time_value = (
            self.make_stat_card(
                "LOCAL TIME"
            )
        )

        grid.addWidget(
            card,
            0,
            0
        )


        card, self.cpu_value = (
            self.make_stat_card(
                "CPU LOAD"
            )
        )

        grid.addWidget(
            card,
            0,
            1
        )


        card, self.ram_value = (
            self.make_stat_card(
                "MEMORY LOAD"
            )
        )

        grid.addWidget(
            card,
            1,
            0
        )


        card, self.battery_value = (
            self.make_stat_card(
                "BATTERY"
            )
        )

        grid.addWidget(
            card,
            1,
            1
        )


        card, self.network_value = (
            self.make_stat_card(
                "NETWORK"
            )
        )

        grid.addWidget(
            card,
            2,
            0
        )


        card, self.host_value = (
            self.make_stat_card(
                "SYSTEM NODE"
            )
        )

        grid.addWidget(
            card,
            2,
            1
        )


        layout.addLayout(
            grid
        )


        swipe_hint = QLabel(
            "☝ SWIPE LEFT // OPEN SYSTEM MATRIX"
        )


        swipe_hint.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        swipe_hint.setStyleSheet(
            """
            color:
                rgba(
                    57,
                    255,
                    120,
                    115
                );

            font-size:
                9px;

            font-family:
                Consolas;
            """
        )


        layout.addWidget(
            swipe_hint
        )


        # =================================================
        # LIVE INTERACTION HISTORY
        # =================================================

        self.interaction_history_view = (
            QPlainTextEdit()
        )


        self.interaction_history_view.setReadOnly(
            True
        )


        self.interaction_history_view.setMaximumHeight(
            150
        )


        self.interaction_history_view.setPlaceholderText(
            "INTERACTION HISTORY // waiting for input..."
        )


        self.interaction_history_view.setStyleSheet(
            """
            QPlainTextEdit {

                background:
                    rgba(
                        0,
                        12,
                        7,
                        150
                    );

                color:
                    #7dff9e;

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        85
                    );

                border-radius:
                    8px;

                padding:
                    8px;

                font-family:
                    Consolas;

                font-size:
                    10px;
            }
            """
        )


        layout.addWidget(
            self.interaction_history_view
        )


        layout.addStretch()


        return page


    # =====================================================
    # CHAT
    # =====================================================

    def build_chat_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "CHAT",

                "AI COMMUNICATION CHANNEL",

                "Direct conversation with GLITCH.EXE."
            )
        )


        self.chat_history = (
            QTextEdit()
        )


        self.chat_history.setReadOnly(
            True
        )


        self.chat_input = (
            QLineEdit()
        )


        self.chat_input.setPlaceholderText(
            "Message GLITCH..."
        )


        send_button = QPushButton(
            "SEND //"
        )


        send_button.clicked.connect(
            self.send_chat_message
        )


        self.chat_input.returnPressed.connect(
            self.send_chat_message
        )


        row = (
            QHBoxLayout()
        )


        row.addWidget(
            self.chat_input
        )


        row.addWidget(
            send_button
        )


        layout.addWidget(
            self.chat_history,
            1
        )


        layout.addLayout(
            row
        )


        return page


    # =====================================================
    # CREATE
    # =====================================================

    def build_create_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "CREATE",

                "CREATIVE SYSTEMS",

                "Develop music concepts, visuals, project ideas "
                "and creative directions."
            )
        )


        self.create_prompt = (
            QTextEdit()
        )


        self.create_prompt.setPlaceholderText(
            "Describe what you want GLITCH to develop..."
        )


        button = QPushButton(
            "GENERATE CONCEPT //"
        )


        button.clicked.connect(
            self.run_create_prompt
        )


        layout.addWidget(
            self.create_prompt,
            1
        )


        layout.addWidget(
            button
        )


        return page


    # =====================================================
    # SEARCH
    # =====================================================

    def build_search_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "SEARCH",

                "LIVE INFORMATION NETWORK",

                "GLITCH can search current information from the web."
            )
        )


        self.search_input = (
            QLineEdit()
        )


        self.search_input.setPlaceholderText(
            "Search live information..."
        )


        search_button = QPushButton(
            "SEARCH NETWORK //"
        )


        self.search_results = (
            QTextEdit()
        )


        self.search_results.setReadOnly(
            True
        )


        search_button.clicked.connect(
            self.run_search
        )


        self.search_input.returnPressed.connect(
            self.run_search
        )


        layout.addWidget(
            self.search_input
        )


        layout.addWidget(
            search_button
        )


        layout.addWidget(
            self.search_results,
            1
        )


        return page


    # =====================================================
    # CODE
    # =====================================================

    def build_code_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "CODE",

                "DEVELOPMENT ENVIRONMENT",

                "Paste code and ask GLITCH to debug, explain or improve it."
            )
        )


        self.code_editor = (
            QPlainTextEdit()
        )


        self.code_editor.setPlaceholderText(
            "# Paste code here..."
        )


        self.code_question = (
            QLineEdit()
        )


        self.code_question.setPlaceholderText(
            "What should GLITCH do with this code?"
        )


        button = QPushButton(
            "ANALYZE CODE //"
        )


        button.clicked.connect(
            self.analyze_code
        )


        layout.addWidget(
            self.code_editor,
            1
        )


        layout.addWidget(
            self.code_question
        )


        layout.addWidget(
            button
        )


        return page


    # =====================================================
    # APPS
    # =====================================================

    def build_apps_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "APPS",

                "APPLICATION CONTROL",

                "Launch Windows applications directly through GLITCH."
            )
        )


        grid = (
            QGridLayout()
        )


        apps = [

            (
                "VISUAL STUDIO",
                "visualstudio"
            ),

            (
                "CHROME",
                "chrome"
            ),

            (
                "SPOTIFY",
                "spotify"
            ),

            (
                "ANDROID STUDIO",
                "androidstudio"
            ),

            (
                "SERATO STUDIO",
                "seratostudio"
            ),

            (
                "SERATO DJ",
                "seratodj"
            ),

            (
                "FILE EXPLORER",
                "explorer"
            ),

            (
                "NOTEPAD",
                "notepad"
            ),

            (
                "CALCULATOR",
                "calculator"
            ),
        ]


        self.app_buttons = []


        for index, (
            name,
            key
        ) in enumerate(
            apps
        ):

            button = (
                QPushButton(
                    name
                )
            )


            button.setMinimumHeight(
                58
            )


            button.clicked.connect(

                lambda checked=False,
                app_key=key:

                    self.launch_app(
                        app_key
                    )
            )


            self.app_buttons.append(
                button
            )


            grid.addWidget(
                button,
                index // 2,
                index % 2
            )


        layout.addLayout(
            grid
        )


        layout.addStretch()


        return page


    # =====================================================
    # SETTINGS
    # =====================================================

    def build_settings_page(self):

        page = QWidget()

        layout = QVBoxLayout(
            page
        )


        layout.addWidget(
            self.create_header(

                "SETTINGS",

                "SYSTEM CONFIGURATION",

                "Changes are automatically stored between sessions."
            )
        )


        self.voice_checkbox = (
            QCheckBox(
                "VOICE RESPONSES"
            )
        )


        self.voice_checkbox.setChecked(
            self.voice_enabled
        )


        self.voice_checkbox.toggled.connect(
            self.set_voice_enabled
        )


        self.gesture_checkbox = (
            QCheckBox(
                "GESTURE CONTROL  (SWIPE / PINCH / POINTER)   [CTRL+G]"
            )
        )

        self.gesture_checkbox.setChecked(
            self.gesture_control_enabled
        )

        self.gesture_checkbox.toggled.connect(
            lambda checked: self.set_gesture_control(
                checked,
                announce=False
            )
        )


        self.hologram_checkbox = (
            QCheckBox(
                "HOLOGRAPHIC HAND   [CTRL+H]"
            )
        )

        self.hologram_checkbox.setChecked(
            self.hand_hologram_enabled
        )

        self.hologram_checkbox.toggled.connect(
            lambda checked: self.set_hand_hologram(
                checked,
                announce=False
            )
        )


        sound_label = QLabel(
            "GRID SOUND VOLUME"
        )


        self.sound_slider = (
            QSlider(
                Qt.Orientation.Horizontal
            )
        )


        self.sound_slider.setRange(
            0,
            100
        )


        self.sound_slider.setValue(
            self.settings_data[
                "ui_sound_volume"
            ]
        )


        self.sound_slider.valueChanged.connect(
            self.set_ui_sound_volume
        )


        self.dwell_label = QLabel(
            f"GESTURE ACTIVATION: "
            f"{self.button_dwell_ms} ms"
        )


        self.dwell_slider = (
            QSlider(
                Qt.Orientation.Horizontal
            )
        )


        self.dwell_slider.setRange(
            200,
            1200
        )


        self.dwell_slider.setValue(
            self.button_dwell_ms
        )


        self.dwell_slider.valueChanged.connect(
            self.set_gesture_dwell
        )


        layout.addWidget(
            self.voice_checkbox
        )


        layout.addSpacing(
            10
        )

        layout.addWidget(
            self.gesture_checkbox
        )

        layout.addWidget(
            self.hologram_checkbox
        )


        self.performance_checkbox = (
            QCheckBox(
                "PERFORMANCE MODE  (STILL BACKGROUND, SMOOTHER HUD)   [CTRL+P]"
            )
        )

        self.performance_checkbox.setChecked(
            bool(self.settings_data.get("performance_mode"))
        )

        self.performance_checkbox.toggled.connect(
            lambda checked: self.set_performance_mode(
                checked,
                announce=False
            )
        )

        layout.addWidget(
            self.performance_checkbox
        )


        layout.addSpacing(
            18
        )


        layout.addWidget(
            sound_label
        )


        layout.addWidget(
            self.sound_slider
        )


        layout.addSpacing(
            18
        )


        layout.addWidget(
            self.dwell_label
        )


        layout.addWidget(
            self.dwell_slider
        )


        layout.addStretch()


        return page


    # =====================================================
    # SYSTEM TELEMETRY
    # =====================================================

    def update_system_stats(self):

        # The UI still owns presentation-specific time formatting.
        self.time_value.setText(
            time.strftime(
                "%I:%M:%S %p"
            )
        )


        try:

            # Ask the service for one complete telemetry snapshot.
            # main_window no longer talks directly to psutil/socket.
            stats = (
                self.system_monitoring_service
                .get_snapshot()
            )


            cpu = (
                stats[
                    "cpu_percent"
                ]
            )


            self.cpu_value.setText(
                f"{cpu:.0f}%"
            )


            ram = (
                stats[
                    "memory_percent"
                ]
            )


            self.ram_value.setText(
                f"{ram:.0f}%"
            )


            battery = (
                stats[
                    "battery"
                ]
            )


            self.battery_value.setText(
                battery[
                    "display"
                ]
            )


            self.network_value.setText(
                stats[
                    "network"
                ]
            )


            self.host_value.setText(
                stats[
                    "hostname"
                ]
            )


        except Exception as error:

            self.response_panel.set_response(
                f"SYSTEM MONITOR ERROR // {error}"
            )


    # =====================================================
    # VOICE LISTENER
    # =====================================================

    def start_voice_listener(self):

        if not self.authenticated:

            self.set_voice_input_status(
                "LOCKED"
            )

            return


        if self.voice_output_active:

            self.set_voice_input_status(
                "PAUSED"
            )

            return


        if self.voice_listener_active:

            return


        self.set_voice_input_status(
            "STARTING"
        )


        self.voice_listener.start()


    def handle_voice_listening_started(self):

        self.voice_listener_active = (
            True
        )


        self.set_voice_input_status(
            "LISTENING"
        )


    def handle_voice_listening_stopped(self):

        self.voice_listener_active = (
            False
        )


        if self.voice_output_active:

            self.set_voice_input_status(
                "PAUSED"
            )

        else:

            self.set_voice_input_status(
                "OFFLINE"
            )


    def handle_voice_listener_error(
        self,
        error
    ):

        self.voice_listener_active = (
            False
        )


        self.set_voice_input_status(
            "ERROR"
        )


        self.response_panel.set_response(
            f"VOICE INPUT ERROR // {error}"
        )


    # =====================================================
    # SPEECH INTERRUPTION / RESPONSE DEPTH
    # =====================================================

    def is_speech_interrupt_command(
        self,
        transcript
    ):

        command = (
            transcript
            .strip()
            .lower()
            .strip(
                " ,.!?:;-"
            )
        )


        if command.startswith(
            "glitch "
        ):

            command = (
                command[
                    len("glitch "):
                ]
                .strip()
            )


        return command in {
            "stop",
            "stop talking",
            "stop speaking",
            "quiet",
            "be quiet",
            "that's enough",
            "that is enough",
            "enough",
            "cancel response",
            "cancel that",
        }


    def handle_response_style_command(
        self,
        transcript
    ):

        command = (
            transcript
            .strip()
            .lower()
            .strip(
                " ,.!?:;-"
            )
        )


        if command.startswith(
            "glitch "
        ):

            command = (
                command[
                    len("glitch "):
                ]
                .strip()
            )


        brief_commands = {
            "keep it brief",
            "keep it short",
            "short answers",
            "shorter answers",
            "be concise",
            "give me the short version",
            "brief answers",
        }


        detailed_commands = {
            "go deeper",
            "explain more",
            "tell me more",
            "more detail",
            "be more detailed",
            "give me more detail",
        }


        normal_commands = {
            "normal answers",
            "normal detail",
            "regular detail",
        }


        if command in brief_commands:

            self.assistant.set_response_style(
                "BRIEF"
            )

            self.say_confirmation(
                "Got it. I'll keep it brief."
            )

            return True


        if command in detailed_commands:

            self.assistant.set_response_style(
                "DETAILED"
            )

            self.say_confirmation(
                "Got it. I'll go deeper."
            )

            return True


        if command in normal_commands:

            self.assistant.set_response_style(
                "NORMAL"
            )

            self.say_confirmation(
                "Got it. Normal detail."
            )

            return True


        return False


    # =====================================================
    # VOICE COMMAND PROCESSOR
    # =====================================================

    def handle_voice_command(
        self,
        transcript
    ):

        if hasattr(
            self,
            "auto_security_scan_service"
        ):

            self.auto_security_scan_service.notify_glitch_activity()


        # Interrupt commands must be processed even while
        # GLITCH is actively speaking.
        if self.is_speech_interrupt_command(
            transcript
        ):

            self.voice_engine.stop()

            self.response_panel.set_response(
                "GLITCH // SPEECH STOPPED"
            )

            self.set_voice_input_status(
                "LISTENING"
            )

            if (
                hasattr(
                    self,
                    "conversation_controller"
                )
                and self.conversation_controller.is_active()
            ):

                self.conversation_controller.touch()

            return


        if self.voice_output_active:
            return


        if self.handle_response_style_command(
            transcript
        ):

            return


        original = (
            transcript
            .strip()
        )


        command = (
            original
            .lower()
            .strip()
        )


        short_display = (
            original[:36]
        )


        if len(original) > 36:
            short_display += "..."


        self.set_voice_input_status(
            "HEARD",
            short_display
        )


        self.response_panel.set_response(
            f'VOICE INPUT // HEARD: "{original}"'
        )


        self.reactor.trigger_glitch(
            0.35,
            6
        )


        # =================================================
        # CONVERSATIONAL WAKE / SESSION GATE
        # =================================================

        # "Glitch" can be anywhere in the sentence ("Hey Glitch...",
        # "What's the weather, Glitch?"). Set GLITCH_REQUIRE_WAKE_WORD=0
        # in .env to let GLITCH answer everything it hears.
        extract_wake_word = getattr(
            self.conversation_controller,
            "extract_wake_word",
            None
        )

        if extract_wake_word is not None:

            wake_word_used, command = extract_wake_word(
                command
            )

        else:

            # Older conversation_controller.py without the flexible
            # wake word: fall back to "starts with glitch".
            wake_word_used = command.startswith("glitch")

            if wake_word_used:

                command = command[len("glitch"):].strip(" ,.!?:;-")

        if os.getenv("GLITCH_REQUIRE_WAKE_WORD", "1") == "0":

            wake_word_used = True


        if wake_word_used:

            if not self.conversation_controller.is_active():

                self.conversation_controller.start_session()

            else:

                self.conversation_controller.touch()


        elif (
            self.conversation_controller
            .is_active()
        ):

            # Natural follow-up speech is allowed while the
            # conversation window is active.
            self.conversation_controller.touch()


        else:

            # Heard, but not addressed to GLITCH. Say so on screen
            # instead of silently ignoring it.
            self.response_panel.set_response(
                f'VOICE INPUT // HEARD: "{original}"  '
                "// STANDING BY - SAY \"GLITCH\" TO WAKE ME"
            )

            QTimer.singleShot(
                1200,
                lambda:
                    self.set_voice_input_status(
                        "LISTENING"
                    )
            )

            return


        if not command:

            # Just the wake word: greet in character. Spoken directly
            # so it isn't wrapped in a command acknowledgement.
            wake_line = (
                self.conversation_controller
                .wake_response()
            )

            self.response_panel.set_response(
                wake_line
            )

            if self.voice_enabled:

                self.voice_engine.speak(
                    wake_line
                )

            else:

                self.set_voice_input_status(
                    "LISTENING"
                )

            return


        if (
            self.conversation_controller
            .is_end_phrase(
                command
            )
        ):

            ending_message = (
                self.conversation_controller
                .ending_response()
            )


            self.conversation_controller.end_session()


            self.response_panel.set_response(
                f"CONVERSATION // {ending_message}"
            )


            if self.voice_enabled:

                self.voice_engine.speak(
                    ending_message
                )

            else:

                self.set_voice_input_status(
                    "LISTENING"
                )


            return


        self.conversation_controller.touch()


        # Resolve short follow-ups into explicit commands before
        # deterministic routing.
        command = (
            self.context_controller
            .resolve(
                command
            )
        )


        # Spoken turns feed the same adaptive context as typed ones
        # (mood, preferences, how to address you).
        self.adaptive_context_service.observe_user(
            command
        )


        if self.handle_sports_command(
            command,
            "VOICE"
        ):

            return


        if self.handle_career_command(
            command,
            "VOICE"
        ):

            return


        if self.handle_gesture_toggle_command(
            command
        ):

            return


        self.set_voice_input_status(
            "PROCESSING"
        )


        # =================================================
        # SAFE SYSTEM POWER CONTROL
        # =================================================

        power_result = (
            self.power_controller
            .handle_command(
                command,
                "VOICE"
            )
        )


        if power_result[
            "handled"
        ]:

            message = (
                power_result[
                    "message"
                ]
                or "Power command processed."
            )


            self.response_panel.set_response(
                f"POWER // {message}"
            )


            self.say_confirmation(
                message
            )


            return


        # =================================================
        # DIGITAL TWIN SYSTEM QUERIES
        # =================================================

        system_query_result = (
            self.system_query_controller
            .handle_query(
                command
            )
        )


        if system_query_result[
            "handled"
        ]:

            self.context_controller.remember_system_result(
                system_query_result
            )


            message = (
                system_query_result[
                    "message"
                ]
            )


            self.response_panel.set_response(
                f"SYSTEM // {message}"
            )


            self.say_confirmation(
                message
            )


            return


        # =================================================
        # PHASE 3 SECURITY CONTROL
        # =================================================

        if self.handle_security_control_command(
            command,
            speak=True
        ):
            return

        # =================================================
        # GLITCH SECURITY ENGINE
        # =================================================

        security_result = (
            self.security_query_controller
            .parse(
                command
            )
        )


        if security_result[
            "handled"
        ]:

            action = (
                security_result[
                    "action"
                ]
            )


            if action == "SCAN_DIRECTORY":

                self.start_security_scan(
                    security_result[
                        "target"
                    ],
                    speak_response=True
                )

            else:

                message = (
                    security_result[
                        "message"
                    ]
                    or "Security command processed."
                )


                self.response_panel.set_response(
                    f"SECURITY // {message}"
                )


                self.security_matrix_page.refresh_security_state()


                self.say_confirmation(
                    message
                )


            return


        # =================================================
        # LIVE WEATHER INTELLIGENCE
        # =================================================

        if (
            self.weather_query_controller
            .can_handle(
                command
            )
        ):

            self.start_weather_request(
                command,
                speak_response=True
            )

            return


        # =================================================
        # LIVE SEARCH
        # =================================================

        # Search remains here because it coordinates
        # UI fields + AIWorker behavior.
        if command.startswith(
            "search for "
        ):

            query = (
                command[
                    len("search for "):
                ]
                .strip()
            )


            if query:

                self.open_search()


                self.search_input.setText(
                    query
                )


                self.search_results.setPlainText(
                    f"SEARCHING // {query}"
                )


                self.start_ai_request(
                    query,
                    "SEARCH"
                )


            return


        # =================================================
        # OPEN PROJECT
        # =================================================

        # Project launching remains here for now.
        if (
            command.startswith(
                "open my "
            )
            and "project" in command
        ):

            project = (
                command
                .replace(
                    "open my ",
                    "",
                    1
                )
                .replace(
                    "project",
                    ""
                )
                .strip()
            )


            if self.open_project(
                project
            ):

                self.say_confirmation(
                    f"Opening your {project} project."
                )

            else:

                self.say_confirmation(
                    "I could not locate that project."
                )


            return


        # =================================================
        # ADVANCED CONTEXT HISTORY
        # =================================================

        if command in [
            "what did i do before that",
            "what happened before that",
            "what was the action before that",
        ]:

            intent = (
                self.get_interaction_by_offset(
                    1
                )
            )


            description = (
                self.describe_interaction(
                    intent
                )
            )


            if description is None:

                self.say_confirmation(
                    "I do not have an earlier interaction in my history."
                )

            else:

                self.say_confirmation(
                    description
                )


            return


        if command in [
            "show me my last 3 actions",
            "show my last 3 actions",
            "what were my last 3 actions",
            "tell me my last 3 actions",
        ]:

            descriptions = (
                self.get_recent_interaction_descriptions(
                    3
                )
            )


            if not descriptions:

                self.say_confirmation(
                    "I do not have recent interactions to report."
                )

                return


            spoken = (
                "Your last actions were: "
                + " ".join(
                    f"{index + 1}. {description}"
                    for index, description
                    in enumerate(
                        descriptions
                    )
                )
            )


            self.say_confirmation(
                spoken
            )

            return


        if command in [
            "go back to the last screen i opened with gesture",
            "return to the last screen i opened with gesture",
            "go to the last page i opened with gesture",
            "last page i opened with gesture",
        ]:

            target = (
                self.get_last_navigation_target_by_source(
                    "GESTURE"
                )
            )


            if target is None:

                self.say_confirmation(
                    "I do not have a previous gesture navigation target."
                )

                return


            self.navigate_with_intent(
                target,
                "VOICE"
            )


            readable_target = (
                target
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            self.say_confirmation(
                f"Returning to the last page you opened with gesture: {readable_target}."
            )

            return


        if command in [
            "repeat my last navigation",
            "repeat the last navigation",
            "repeat my last page change",
        ]:

            target = (
                self.get_last_navigation_target()
            )


            if target is None:

                self.say_confirmation(
                    "I do not have a previous navigation target to repeat."
                )

                return


            self.navigate_with_intent(
                target,
                "VOICE"
            )


            readable_target = (
                target
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            self.say_confirmation(
                f"Repeating your last navigation to {readable_target}."
            )

            return


        # =================================================
        # DEEPER CONTEXT AWARENESS
        # =================================================

        if command in [
            "what did i just do",
            "what was my last action",
            "what did i do last",
        ]:

            description = (
                self.describe_last_interaction()
            )


            if description is None:

                self.say_confirmation(
                    "I do not have a recent interaction to report."
                )

            else:

                self.say_confirmation(
                    description
                )


            return


        if command in [
            "what screen was i on before this",
            "what was the previous screen",
            "what page was i on before this",
        ]:

            target = (
                self.get_previous_navigation_target()
            )


            if target is None:

                self.say_confirmation(
                    "I do not have a previous screen in my interaction history."
                )

            else:

                readable_target = (
                    target
                    .replace(
                        "_",
                        " "
                    )
                    .lower()
                )


                self.say_confirmation(
                    f"You were on {readable_target} before this."
                )


            return


        if command in [
            "go back two screens",
            "back two screens",
            "go back 2 screens",
            "back 2 screens",
        ]:

            target = (
                self.get_navigation_target_by_steps(
                    2
                )
            )


            if target is None:

                self.say_confirmation(
                    "I do not have enough navigation history to go back two screens."
                )

                return


            self.navigate_with_intent(
                target,
                "VOICE"
            )


            readable_target = (
                target
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            self.say_confirmation(
                f"Going back two screens to {readable_target}."
            )

            return


        if command in [
            "return to the last page i opened with voice",
            "go to the last page i opened with voice",
            "last page i opened with voice",
        ]:

            target = (
                self.get_last_navigation_target_by_source(
                    "VOICE"
                )
            )


            if target is None:

                self.say_confirmation(
                    "I do not have a previous voice navigation target."
                )

                return


            self.navigate_with_intent(
                target,
                "VOICE"
            )


            readable_target = (
                target
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            self.say_confirmation(
                f"Returning to the last page you opened with voice: {readable_target}."
            )

            return


        # =================================================
        # CONTEXT-AWARE NAVIGATION
        # =================================================

        if command in [
            "back",
            "go back",
            "return",
            "return to last screen",
            "go to the last screen",
            "previous screen",
        ]:

            target = (
                self.get_previous_navigation_target()
            )


            if target is None:

                self.say_confirmation(
                    "There is no previous screen in my interaction history."
                )

                return


            self.navigate_with_intent(
                target,
                "VOICE"
            )


            spoken_target = (
                target
                .replace(
                    "_",
                    " "
                )
                .lower()
            )


            self.say_confirmation(
                f"Returning to {spoken_target}."
            )

            return


        # =================================================
        # PHASE 1 VOICE INTENT ROUTING
        # =================================================

        result = (
            self.voice_controller
            .handle_command(
                command
            )
        )


        if result[
            "handled"
        ]:

            action_type = (
                result[
                    "type"
                ]
            )


            if action_type in [
                "open_app",
                "close_app",
            ]:

                self.context_controller.remember_app_from_command(
                    command
                )


            message = (
                result[
                    "message"
                ]
            )


            if action_type == "open_app":

                self.play_ui_sound(
                    "APPS"
                )


                self.reactor.trigger_glitch(
                    0.5,
                    8
                )


            # Preserve the confirmations the original
            # working implementation already used.
            if (
                action_type == "navigation"
                and message is None
            ):

                if command in [
                    "open system matrix",
                    "system matrix",
                    "open diagnostics",
                    "show diagnostics",
                    "show system stats",
                ]:

                    message = (
                        "Opening system matrix."
                    )

                elif command in [
                    "home",
                    "go home",
                    "open home",
                ]:

                    message = (
                        "Home interface."
                    )


            if message:

                self.say_confirmation(
                    message
                )

            else:

                QTimer.singleShot(
                    500,
                    lambda:
                        self.set_voice_input_status(
                            "LISTENING"
                        )
                )


            return


        # =================================================
        # AI FALLBACK
        # =================================================

        # During an active voice conversation, do NOT force the
        # interface into CHAT mode. Keep the user on the current
        # screen and let the AI answer conversationally in place.
        if (
            hasattr(
                self,
                "conversation_controller"
            )
            and self.conversation_controller.is_active()
        ):

            self.chat_history.append(
                f"404 VOICE > {command}"
            )


            contextual_command = (
                self.context_controller
                .build_ai_context(
                    command
                )
            )


            self.start_ai_request(
                contextual_command,
                "CONVERSATION"
            )


            self.conversation_controller.touch()


            return


        # Outside an active conversation, preserve the original
        # behavior and route normal voice AI requests to CHAT.
        self.open_chat()


        self.chat_history.append(
            f"404 VOICE > {command}"
        )


        self.start_ai_request(
            command,
            "CHAT"
        )


    # =====================================================
    # VOICE CONFIRMATION
    # =====================================================

    def say_confirmation(
        self,
        text
    ):

        spoken_text = (
            text
        )


        if (
            hasattr(
                self,
                "conversation_controller"
            )
            and self.conversation_controller.is_active()
        ):

            spoken_text = (
                self.conversation_controller
                .decorate_confirmation(
                    text
                )
            )

            self.conversation_controller.touch()


        self.response_panel.set_response(
            spoken_text
        )


        if self.voice_enabled:

            self.voice_engine.speak(
                spoken_text
            )

        else:

            self.set_voice_input_status(
                "LISTENING"
            )


    # =====================================================
    # MEDIA
    # =====================================================

    def media_play_pause(self):

        self.application_service.media_play_pause()


    def media_next(self):

        self.application_service.media_next()


    def media_previous(self):

        self.application_service.media_previous()


    def media_stop(self):

        self.application_service.media_stop()


    # =====================================================
    # CLOSE APP
    # =====================================================

    def close_app(
        self,
        app
    ):

        success, message = (
            self.application_service
            .close_app(app)
        )


        if not success:

            self.response_panel.set_response(
                message
            )


        return success


    def close_app_and_confirm(
        self,
        app,
        display_name
    ):

        if self.close_app(
            app
        ):

            self.say_confirmation(
                f"Closing {display_name}."
            )

        else:

            self.say_confirmation(
                f"{display_name} does not appear to be running."
            )


    # =====================================================
    # OPEN PROJECT
    # =====================================================

    def open_project(
        self,
        project_name
    ):

        home = (
            Path.home()
        )


        repo_roots = [

            home
            / "source"
            / "repos",

            home
            / "Documents"
            / "Visual Studio 2022"
            / "Projects",
        ]


        search_name = (
            project_name
            .lower()
            .replace(
                "project",
                ""
            )
            .strip()
        )


        if not search_name:

            return False


        for root in repo_roots:

            if not root.exists():

                continue


            for folder in root.iterdir():

                if not folder.is_dir():

                    continue


                if (
                    search_name
                    not in folder.name.lower()
                ):

                    continue


                try:

                    solutions = list(
                        folder.rglob(
                            "*.sln"
                        )
                    )


                    if solutions:

                        os.startfile(
                            str(
                                solutions[0]
                            )
                        )


                        return True


                    os.startfile(
                        str(folder)
                    )


                    return True


                except Exception:

                    continue


        return False


    # =====================================================
    # CHAT
    # =====================================================

    def send_chat_message(self):

        message = (
            self.chat_input
            .text()
            .strip()
        )


        if not message:

            return


        self.chat_history.append(
            f"404 > {message}"
        )


        self.chat_input.clear()


        self.start_ai_request(
            message,
            "CHAT"
        )


    # =====================================================
    # CREATE
    # =====================================================

    def run_create_prompt(self):

        prompt = (
            self.create_prompt
            .toPlainText()
            .strip()
        )


        if not prompt:

            return


        self.start_ai_request(

            "You are currently in GLITCH.EXE CREATE mode. "
            "Help develop this idea creatively and practically:\n\n"
            + prompt,

            "CREATE"
        )


    # =====================================================
    # SEARCH
    # =====================================================

    def run_search(self):

        query = (
            self.search_input
            .text()
            .strip()
        )


        if not query:

            return


        self.search_results.setPlainText(
            "SEARCHING LIVE NETWORK..."
        )


        self.start_ai_request(
            query,
            "SEARCH"
        )


    # =====================================================
    # CODE
    # =====================================================

    def analyze_code(self):

        code = (
            self.code_editor
            .toPlainText()
            .strip()
        )


        question = (
            self.code_question
            .text()
            .strip()
        )


        if not code:

            return


        if not question:

            question = (
                "Analyze this code, explain it, "
                "identify issues, and suggest improvements."
            )


        request = (
            "You are in GLITCH.EXE CODE mode.\n\n"
            f"TASK:\n{question}\n\n"
            f"CODE:\n{code}"
        )


        self.start_ai_request(
            request,
            "CODE"
        )


    # =====================================================
    # LAUNCH APP
    # =====================================================

    def launch_app(
        self,
        app
    ):

        success, message = (
            self.application_service
            .launch_app(app)
        )


        if success:

            self.app_launched(
                app
            )


            return True


        self.response_panel.set_response(
            f"APP NOT LOCATED // {app.upper()} // {message}"
        )


        return False


    def app_launched(
        self,
        app
    ):

        self.play_ui_sound(
            "APPS"
        )


        self.response_panel.set_response(
            f"APPLICATION LAUNCHED // {app.upper()}"
        )


        self.reactor.trigger_glitch(
            0.5,
            8
        )


    def app_error(
        self,
        app,
        error
    ):

        self.response_panel.set_response(
            f"APP ERROR // {app.upper()} // {error}"
        )


    # =====================================================
    # SETTINGS
    # =====================================================

    def set_voice_enabled(
        self,
        enabled
    ):

        self.voice_enabled = (
            enabled
        )


        self.settings_data[
            "voice_enabled"
        ] = enabled


        self.save_settings()


        if enabled:

            self.status_panel.set_voice_status(
                "ONLINE"
            )

        else:

            self.status_panel.set_voice_status(
                "MUTED"
            )


            try:

                self.voice_engine.stop()

            except Exception:

                pass


    def set_ui_sound_volume(
        self,
        value
    ):

        self.ui_sound_volume = (
            value
            / 100
        )


        self.settings_data[
            "ui_sound_volume"
        ] = value


        self.save_settings()


        for sound in (
            self.ui_sounds.values()
        ):

            sound.setVolume(
                self.ui_sound_volume
            )


    def set_gesture_dwell(
        self,
        value
    ):

        self.button_dwell_ms = (
            value
        )


        self.settings_data[
            "gesture_dwell_ms"
        ] = value


        self.save_settings()


        self.dwell_label.setText(
            f"GESTURE ACTIVATION: {value} ms"
        )


    # =====================================================
    # WEATHER
    # =====================================================

    def start_weather_request(
        self,
        command,
        speak_response=False
    ):

        if (
            self.weather_thread is not None
            and self.weather_thread.isRunning()
        ):

            if (
                self.weather_request_mode
                == "LOCATION"
            ):

                self.response_panel.set_response(
                    "LOCATION // REQUEST ALREADY IN PROGRESS..."
                )

            else:

                self.response_panel.set_response(
                    "WEATHER // REQUEST ALREADY IN PROGRESS..."
                )

            return


        self.weather_should_speak = (
            speak_response
        )


        # =================================================
        # DETERMINE REQUEST TYPE
        # =================================================

        is_location_request = False

        try:

            location_query_checker = getattr(
                self.weather_query_controller,
                "_is_location_query",
                None
            )

            if callable(
                location_query_checker
            ):

                is_location_request = bool(
                    location_query_checker(
                        command
                    )
                )

        except Exception:

            is_location_request = False


        # Defensive fallback in case the controller is ever
        # swapped for an older build that does not expose
        # _is_location_query().
        if not is_location_request:

            lowered_command = (
                str(
                    command
                    or ""
                )
                .strip()
                .lower()
            )

            location_phrases = (
                "where am i",
                "where am i at",
                "where am i currently",
                "where am i currently at",
                "what is my current location",
                "what's my current location",
                "whats my current location",
                "tell me my current location",
                "what city am i in",
                "what area am i in",
                "where are we",
                "i'm lost where am i",
                "im lost where am i",
                "i am lost where am i",
            )

            is_location_request = (
                any(
                    phrase in lowered_command
                    for phrase in location_phrases
                )
                or
                (
                    "lost"
                    in lowered_command
                    and
                    "where"
                    in lowered_command
                )
            )


        # =================================================
        # LIVE HUD STATUS
        # =================================================

        if is_location_request:

            self.weather_request_mode = (
                "LOCATION"
            )

            self.response_panel.set_response(
                "LOCATION // CHECKING LOCATION..."
            )

        else:

            self.weather_request_mode = (
                "WEATHER"
            )

            self.response_panel.set_response(
                "WEATHER // CHECKING LIVE FORECAST..."
            )


        # Small reactor response while live information
        # is being retrieved.
        try:

            self.reactor.trigger_glitch(
                0.30,
                5
            )

        except Exception:

            pass


        # =================================================
        # BACKGROUND WORKER
        # =================================================

        self.weather_thread = (
            QThread()
        )


        self.weather_worker = (
            WeatherWorker(
                self.weather_query_controller,
                command
            )
        )


        self.weather_worker.moveToThread(
            self.weather_thread
        )


        self.weather_thread.started.connect(
            self.weather_worker.run
        )


        self.weather_worker.finished.connect(
            self.handle_weather_response
        )


        self.weather_worker.error.connect(
            self.handle_weather_error
        )


        self.weather_worker.finished.connect(
            self.weather_thread.quit
        )


        self.weather_worker.error.connect(
            self.weather_thread.quit
        )


        self.weather_worker.finished.connect(
            self.weather_worker.deleteLater
        )


        self.weather_worker.error.connect(
            self.weather_worker.deleteLater
        )


        self.weather_thread.finished.connect(
            self.weather_thread.deleteLater
        )


        self.weather_thread.finished.connect(
            self.cleanup_weather_thread
        )


        self.weather_thread.start()


    def handle_weather_response(
        self,
        result
    ):

        is_location_result = (
            self.weather_request_mode
            == "LOCATION"
            or
            (
                isinstance(
                    result,
                    dict
                )
                and
                "location_result"
                in result
            )
        )


        message = (
            result.get(
                "message"
            )
            if isinstance(
                result,
                dict
            )
            else None
        )


        if not message:

            message = (
                "Location data unavailable."
                if is_location_result
                else "Weather data unavailable."
            )


        # =================================================
        # LOCATION RESULT
        # =================================================

        if is_location_result:

            self.response_panel.set_response(
                f"LOCATION // {message}"
            )


        # =================================================
        # WEATHER RESULT
        # =================================================

        else:

            self.response_panel.set_response(
                f"WEATHER // {message}"
            )


            # Only actual weather responses should affect
            # weather conversation context.
            try:

                self.context_controller.remember_weather_result(
                    result
                )

            except Exception:

                pass


        # =================================================
        # VOICE RESPONSE
        # =================================================

        if (
            self.weather_should_speak
            and self.voice_enabled
        ):

            self.voice_engine.speak(
                message
            )


        # Keep the wake-once conversational session alive.
        if (
            hasattr(
                self,
                "conversation_controller"
            )
            and
            self.conversation_controller.is_active()
        ):

            self.conversation_controller.touch()


    def handle_weather_error(
        self,
        error
    ):

        if (
            self.weather_request_mode
            == "LOCATION"
        ):

            self.response_panel.set_response(
                f"LOCATION ERROR // {error}"
            )

        else:

            self.response_panel.set_response(
                f"WEATHER ERROR // {error}"
            )


    def cleanup_weather_thread(
        self
    ):

        self.weather_thread = None
        self.weather_worker = None

        self.weather_request_mode = (
            "WEATHER"
        )


    # =====================================================
    # PHASE 3 SECURITY CONTROL / FINDINGS
    # =====================================================

    def _security_findings(
        self
    ):

        return (
            self.security_matrix_page
            .get_active_security_findings()
        )


    def _resolve_finding_index(
        self,
        requested_index
    ):

        findings = self._security_findings()

        if requested_index is None:

            if len(findings) == 1:
                return 1, findings[0], None

            if not findings:
                return None, None, "There are no active security findings."

            return (
                None,
                None,
                "There is more than one active finding. Say the finding number, for example finding 1."
            )

        try:
            index = int(
                requested_index
            )
        except (TypeError, ValueError):
            return None, None, "That finding number is invalid."

        if index < 1 or index > len(findings):
            return (
                None,
                None,
                f"Finding {index} does not exist. There are {len(findings)} active findings."
            )

        return index, findings[index - 1], None


    def show_security_findings(
        self,
        selected_index=None
    ):

        findings = self._security_findings()
        history = (
            self.security_matrix_page
            .recent_security_events(
                limit=12
            )
        )

        self.security_findings_overlay.setGeometry(
            self.central_widget.rect()
        )

        self.security_findings_overlay.show_findings(
            findings,
            history,
            selected_index=selected_index
        )

        return len(findings)


    def handle_security_findings_closed(
        self
    ):

        self.response_panel.set_response(
            "SECURITY FINDINGS // CLOSED"
        )


    def _security_control_response(
        self,
        message,
        speak=False
    ):

        self.response_panel.set_response(
            f"SECURITY // {message}"
        )

        if speak:
            self.say_confirmation(
                message
            )


    def _prepare_security_action(
        self,
        action,
        index,
        finding,
        speak=False
    ):

        process_name = str(
            finding.get(
                "process_name",
                "UNKNOWN"
            )
            or "UNKNOWN"
        )

        risk_score = int(
            finding.get(
                "risk_score",
                0
            )
            or 0
        )

        action_words = {
            "QUARANTINE": "quarantine the executable file",
            "TERMINATE": "terminate the running process",
            "BLOCK": "block outbound network access",
        }

        description = action_words.get(
            action,
            action.lower()
        )

        self.pending_security_action = {
            "action": action,
            "index": index,
            "finding": dict(
                finding
            ),
            "created_at": time.time(),
        }

        message = (
            f"Confirmation required. Finding {index} is {process_name}, "
            f"risk score {risk_score}. I am ready to {description}. "
            "Say confirm to proceed or cancel to abort."
        )

        self._security_control_response(
            message,
            speak=speak
        )


    def _cancel_security_action(
        self,
        speak=False
    ):

        if self.pending_security_action is None:
            message = "There is no pending security action."
        else:
            self.pending_security_action = None
            message = "Pending security action cancelled."

        self._security_control_response(
            message,
            speak=speak
        )


    def _confirm_security_action(
        self,
        speak=False
    ):

        pending = self.pending_security_action

        if pending is None:
            self._security_control_response(
                "There is no pending security action to confirm.",
                speak=speak
            )
            return

        if (
            time.time()
            - float(
                pending.get(
                    "created_at",
                    0
                )
            )
            > 90
        ):
            self.pending_security_action = None
            self._security_control_response(
                "That security confirmation expired. Request the action again.",
                speak=speak
            )
            return

        action = pending[
            "action"
        ]
        finding = pending[
            "finding"
        ]
        index = pending[
            "index"
        ]

        self.pending_security_action = None

        if action == "QUARANTINE":
            result = (
                self.security_action_service
                .quarantine_finding(
                    finding
                )
            )

        elif action == "TERMINATE":
            result = (
                self.security_action_service
                .terminate_finding(
                    finding
                )
            )

        elif action == "BLOCK":
            result = (
                self.security_action_service
                .block_finding(
                    finding
                )
            )

        else:
            result = {
                "success": False,
                "message": "Unknown security action.",
            }

        success = bool(
            result.get(
                "success"
            )
        )
        message = str(
            result.get(
                "message"
            )
            or "Security action completed."
        )

        self.security_matrix_page.record_security_control_event(
            action,
            finding,
            success,
            message
        )

        if success:
            finding_key = finding.get(
                "finding_key"
            )

            if finding_key:
                self.security_matrix_page.resolve_security_finding(
                    finding_key,
                    note=(
                        f"{action} confirmed by 404. {message}"
                    )
                )

                try:
                    self.security_alert_service.forget(
                        finding_key
                    )
                except Exception:
                    pass

            message = (
                f"Confirmed action completed for finding {index}. "
                + message
            )

        self._security_control_response(
            message,
            speak=speak
        )

        self.show_security_findings()


    def handle_security_control_command(
        self,
        command,
        speak=False
    ):

        result = (
            self.security_control_controller
            .parse(
                command
            )
        )

        if not result.get(
            "handled"
        ):
            return False

        action = result.get(
            "action"
        )
        requested_index = result.get(
            "index"
        )

        if action == "SHOW_FINDINGS":
            count = self.show_security_findings()
            self._security_control_response(
                f"Showing {count} active security findings.",
                speak=speak
            )
            return True

        if action == "SHOW_HISTORY":
            self.show_security_findings()
            events = (
                self.security_matrix_page
                .recent_security_events(
                    limit=25
                )
            )
            self._security_control_response(
                f"Showing security history. I have {len(events)} recent events stored.",
                speak=speak
            )
            return True

        if action == "CLOSE_FINDINGS":
            self.security_findings_overlay.hide()
            self._security_control_response(
                "Security findings closed.",
                speak=speak
            )
            return True

        if action == "MOST_SUSPICIOUS":
            findings = self._security_findings()

            if not findings:
                message = "There are no active suspicious process findings."
            else:
                finding = findings[0]
                name = finding.get(
                    "process_name",
                    "UNKNOWN"
                )
                severity = finding.get(
                    "severity",
                    "REVIEW"
                )
                score = finding.get(
                    "risk_score",
                    0
                )
                reasons = finding.get(
                    "reasons",
                    []
                ) or []
                reason = (
                    reasons[0]
                    if reasons
                    else "No reason data available."
                )
                message = (
                    f"The highest-risk active finding is {name}, "
                    f"rated {severity} with score {score}. {reason}"
                )
                self.show_security_findings(
                    selected_index=1
                )

            self._security_control_response(
                message,
                speak=speak
            )
            return True

        if action == "CONFIRM":
            self._confirm_security_action(
                speak=speak
            )
            return True

        if action == "CANCEL":
            self._cancel_security_action(
                speak=speak
            )
            return True

        index, finding, error = (
            self._resolve_finding_index(
                requested_index
            )
        )

        if error:
            self._security_control_response(
                error,
                speak=speak
            )
            return True

        if action == "SHOW_FINDING":
            self.show_security_findings(
                selected_index=index
            )

            reasons = finding.get(
                "reasons",
                []
            ) or []
            reason = (
                reasons[0]
                if reasons
                else "No reason data available."
            )

            message = (
                f"Finding {index}: {finding.get('process_name', 'UNKNOWN')}, "
                f"{finding.get('severity', 'REVIEW')}, "
                f"risk score {finding.get('risk_score', 0)}. {reason}"
            )

            self._security_control_response(
                message,
                speak=speak
            )
            return True

        if action == "RESOLVE_FINDING":
            finding_key = finding.get(
                "finding_key"
            )

            if not finding_key:
                message = "That finding does not have a persistent key."
            else:
                changed = (
                    self.security_matrix_page
                    .resolve_security_finding(
                        finding_key,
                        note="Manually resolved by 404."
                    )
                )

                if changed:
                    try:
                        self.security_alert_service.forget(
                            finding_key
                        )
                    except Exception:
                        pass

                    self.security_matrix_page.record_security_control_event(
                        "RESOLVE",
                        finding,
                        True,
                        "Manually resolved by 404."
                    )

                    message = f"Finding {index} has been marked resolved."
                else:
                    message = f"Finding {index} could not be resolved."

            self._security_control_response(
                message,
                speak=speak
            )
            self.show_security_findings()
            return True

        if action == "REQUEST_QUARANTINE":
            self._prepare_security_action(
                "QUARANTINE",
                index,
                finding,
                speak=speak
            )
            return True

        if action == "REQUEST_TERMINATE":
            self._prepare_security_action(
                "TERMINATE",
                index,
                finding,
                speak=speak
            )
            return True

        if action == "REQUEST_BLOCK":
            self._prepare_security_action(
                "BLOCK",
                index,
                finding,
                speak=speak
            )
            return True

        return True


    # =====================================================
    # WINDOWS SECURITY TELEMETRY
    # =====================================================

    def start_windows_security_refresh(
        self
    ):

        if (
            self.windows_security_thread is not None
            and self.windows_security_thread.isRunning()
        ):

            return


        self.windows_security_thread = (
            QThread()
        )


        self.windows_security_worker = (
            WindowsSecurityTelemetryWorker(
                self.windows_security_telemetry_service
            )
        )


        self.windows_security_worker.moveToThread(
            self.windows_security_thread
        )


        self.windows_security_thread.started.connect(
            self.windows_security_worker.run
        )


        self.windows_security_worker.finished.connect(
            self.handle_windows_security_snapshot
        )


        self.windows_security_worker.error.connect(
            self.handle_windows_security_error
        )


        self.windows_security_worker.finished.connect(
            self.windows_security_thread.quit
        )


        self.windows_security_worker.error.connect(
            self.windows_security_thread.quit
        )


        self.windows_security_worker.finished.connect(
            self.windows_security_worker.deleteLater
        )


        self.windows_security_worker.error.connect(
            self.windows_security_worker.deleteLater
        )


        self.windows_security_thread.finished.connect(
            self.windows_security_thread.deleteLater
        )


        self.windows_security_thread.finished.connect(
            self.cleanup_windows_security_thread
        )


        self.windows_security_thread.start()


    def handle_windows_security_snapshot(
        self,
        snapshot
    ):

        self.security_matrix_page.set_windows_security_telemetry(
            snapshot
        )

        self.check_security_alerts()


    # =====================================================
    # PHASE 3 SECURITY ALERTS
    # =====================================================

    def check_security_alerts(
        self
    ):

        try:

            findings = (
                self.security_matrix_page
                .get_active_security_findings()
            )

            new_alerts = (
                self.security_alert_service
                .collect_new_alerts(
                    findings
                )
            )

        except Exception as error:

            print(
                "SECURITY ALERT CHECK ERROR:",
                error
            )

            return


        if not new_alerts:

            return


        self.security_alert_queue.extend(
            new_alerts
        )

        self.show_next_security_alert()


    def show_next_security_alert(
        self
    ):

        if self.security_alert_active:

            return


        if not self.authenticated:

            return


        if not self.security_alert_queue:

            return


        finding = (
            self.security_alert_queue
            .pop(
                0
            )
        )

        severity = str(
            finding.get(
                "severity",
                "REVIEW"
            )
            or "REVIEW"
        ).upper()

        process_name = str(
            finding.get(
                "process_name",
                "UNKNOWN"
            )
            or "UNKNOWN"
        )

        risk_score = int(
            finding.get(
                "risk_score",
                0
            )
            or 0
        )

        reasons = (
            finding.get(
                "reasons",
                []
            )
            or []
        )

        reason = (
            str(
                reasons[0]
            )
            if reasons
            else (
                "Unusual process behavior requires review."
            )
        )


        self.security_alert_active = True


        self.security_alert_overlay.setGeometry(
            self.central_widget.rect()
        )

        self.security_alert_overlay.show_alert(
            severity,
            process_name,
            risk_score,
            reason
        )


        if severity in {
            "HIGH",
            "CRITICAL",
        }:

            response = (
                "SECURITY ALERT // HIGH RISK\n"
                f"PROCESS // {process_name}\n"
                f"RISK // {risk_score}\n"
                f"ANALYSIS // {reason}"
            )

            glitch_intensity = 0.95
            glitch_frames = 14

            spoken = (
                f"404, high-risk security activity was detected "
                f"from {process_name}. "
                "Review the Security Matrix."
            )

        elif severity in {
            "SUSPICIOUS",
            "WARNING",
        }:

            response = (
                "SECURITY ALERT // SUSPICIOUS\n"
                f"PROCESS // {process_name}\n"
                f"RISK // {risk_score}\n"
                f"ANALYSIS // {reason}"
            )

            glitch_intensity = 0.72
            glitch_frames = 11

            spoken = (
                f"404, I detected unusual network activity "
                f"from {process_name}. "
                "Review the Security Matrix."
            )

        else:

            response = (
                "SECURITY NOTICE // REVIEW\n"
                f"PROCESS // {process_name}\n"
                f"RISK // {risk_score}\n"
                f"ANALYSIS // {reason}"
            )

            glitch_intensity = 0.45
            glitch_frames = 7

            spoken = None


        self.response_panel.set_response(
            response
        )


        self.reactor.trigger_glitch(
            glitch_intensity,
            glitch_frames
        )


        # Voice only for SUSPICIOUS/HIGH alerts.
        # REVIEW remains visual to avoid unnecessary interruptions.
        if (
            spoken
            and self.voice_enabled
            and not self.voice_output_active
        ):

            self.voice_engine.speak(
                spoken
            )


    def handle_security_alert_finished(
        self
    ):

        self.security_alert_active = False

        if self.security_alert_queue:

            QTimer.singleShot(
                350,
                self.show_next_security_alert
            )


    def handle_windows_security_error(
        self,
        error
    ):

        print(
            "WINDOWS SECURITY TELEMETRY ERROR:",
            error
        )


    def cleanup_windows_security_thread(
        self
    ):

        self.windows_security_thread = None
        self.windows_security_worker = None


    # =====================================================
    # SECURITY ENGINE
    # =====================================================

    def start_security_scan(
        self,
        target,
        speak_response=False
    ):

        if (
            self.security_thread is not None
            and self.security_thread.isRunning()
        ):

            message = (
                "A security scan is already running."
            )

            self.response_panel.set_response(
                f"SECURITY // {message}"
            )

            if speak_response:
                self.say_confirmation(
                    message
                )

            return


        self.security_should_speak = (
            speak_response
        )


        self.response_panel.set_response(
            (
                "SECURITY // SCANNING\n"
                f"TARGET // {target}"
            )
        )


        self.security_matrix_page.core_status.setText(
            "ANTIVIRUS SCAN // ACTIVE"
        )


        self.security_thread = (
            QThread()
        )


        self.security_worker = (
            SecurityScanWorker(
                self.security_engine,
                target
            )
        )


        self.security_worker.moveToThread(
            self.security_thread
        )


        self.security_thread.started.connect(
            self.security_worker.run
        )


        self.security_worker.finished.connect(
            self.handle_security_scan_finished
        )


        self.security_worker.error.connect(
            self.handle_security_scan_error
        )


        self.security_worker.finished.connect(
            self.security_thread.quit
        )


        self.security_worker.error.connect(
            self.security_thread.quit
        )


        self.security_worker.finished.connect(
            self.security_worker.deleteLater
        )


        self.security_worker.error.connect(
            self.security_worker.deleteLater
        )


        self.security_thread.finished.connect(
            self.security_thread.deleteLater
        )


        self.security_thread.finished.connect(
            self.cleanup_security_thread
        )


        self.security_thread.start()


    def handle_security_scan_finished(
        self,
        results
    ):

        total = len(
            results
        )


        suspicious = [
            result
            for result in results
            if result.suspicious
        ]


        errors = [
            result
            for result in results
            if result.error
        ]


        state = (
            self.security_engine
            .state
        )


        self.security_matrix_page.refresh_security_state()


        if suspicious:

            preview = ", ".join(
                result.file_name
                for result
                in suspicious[:3]
            )

            message = (
                f"Scan complete. I scanned {total} files and "
                f"flagged {len(suspicious)} for review. "
                f"Highest security state is {state.security_status}. "
                f"Recent flags include {preview}."
            )

        else:

            message = (
                f"Scan complete. I scanned {total} files and "
                "did not flag any suspicious files."
            )


        if errors:

            message += (
                f" {len(errors)} files could not be scanned."
            )


        self.response_panel.set_response(
            f"SECURITY // {message}"
        )


        self.security_matrix_page.core_status.setText(
            "DEFENSIVE GRID // ONLINE"
        )


        if self.security_should_speak:

            self.say_confirmation(
                message
            )


    def handle_security_scan_error(
        self,
        error
    ):

        message = (
            f"Security scan failed: {error}"
        )


        self.response_panel.set_response(
            f"SECURITY ERROR // {error}"
        )


        self.security_matrix_page.core_status.setText(
            "ANTIVIRUS SCAN // ERROR"
        )


        if self.security_should_speak:

            self.say_confirmation(
                message
            )


    def cleanup_security_thread(
        self
    ):

        self.security_thread = None
        self.security_worker = None
        self.security_should_speak = False


    # =====================================================
    # AI
    # =====================================================

    def start_ai_request(
        self,
        message,
        mode
    ):

        if (
            self.ai_thread is not None
            and self.ai_thread.isRunning()
        ):

            self.response_panel.set_response(
                "GLITCH.EXE // CURRENT REQUEST STILL PROCESSING..."
            )

            return


        self.pending_ai_mode = (
            mode
        )


        self.status_panel.set_core_status(
            "THINKING"
        )


        if mode == "SEARCH":

            self.response_panel.set_response(
                "SEARCH // ACCESSING LIVE NETWORK..."
            )

        elif mode == "CONVERSATION":

            self.response_panel.set_response(
                "GLITCH // THINKING..."
            )

        else:

            self.response_panel.set_response(
                f"{mode} // PROCESSING..."
            )


        self.reactor.trigger_glitch(
            1.1,
            18
        )


        self.ai_thread = (
            QThread()
        )


        # Stream spoken replies so GLITCH starts talking after the
        # first sentence instead of after the whole answer.
        self._ai_streaming = (
            self.voice_enabled
            and mode != "SEARCH"
        )

        self._ai_stream_begun = False

        self._ai_partial_text = ""


        self.ai_worker = (
            AIWorker(
                self.assistant,
                message,
                mode,
                self._ai_streaming
            )
        )


        self.ai_worker.partial.connect(
            self.handle_ai_partial
        )


        self.ai_worker.moveToThread(
            self.ai_thread
        )


        self.ai_thread.started.connect(
            self.ai_worker.run
        )


        self.ai_worker.finished.connect(
            self.handle_ai_response
        )


        self.ai_worker.error.connect(
            self.handle_ai_error
        )


        self.ai_worker.finished.connect(
            self.ai_thread.quit
        )


        self.ai_worker.error.connect(
            self.ai_thread.quit
        )


        self.ai_worker.finished.connect(
            self.ai_worker.deleteLater
        )


        self.ai_worker.error.connect(
            self.ai_worker.deleteLater
        )


        self.ai_thread.finished.connect(
            self.ai_thread.deleteLater
        )


        self.ai_thread.finished.connect(
            self.cleanup_ai_thread
        )


        self.ai_thread.start()


    def handle_command(
        self,
        message
    ):

        if hasattr(
            self,
            "auto_security_scan_service"
        ):

            self.auto_security_scan_service.notify_glitch_activity()


        if not message:
            return


        command = (
            message
            .strip()
            .lower()
        )


        # Give keyboard commands the same short-reference
        # resolution used by voice.
        command = (
            self.context_controller
            .resolve(
                command
            )
        )


        self.adaptive_context_service.observe_user(
            command
        )


        if self.handle_sports_command(
            command,
            "KEYBOARD"
        ):

            return


        if self.handle_career_command(
            command,
            "KEYBOARD"
        ):

            return


        if self.handle_gesture_toggle_command(
            command
        ):

            return


        # =================================================
        # SAFE SYSTEM POWER CONTROL
        # =================================================

        power_result = (
            self.power_controller
            .handle_command(
                command,
                "KEYBOARD"
            )
        )


        if power_result[
            "handled"
        ]:

            message = (
                power_result[
                    "message"
                ]
                or "Power command processed."
            )


            self.response_panel.set_response(
                f"POWER // {message}"
            )


            return


        # =================================================
        # DIGITAL TWIN SYSTEM QUERIES
        # =================================================

        system_query_result = (
            self.system_query_controller
            .handle_query(
                command
            )
        )


        if system_query_result[
            "handled"
        ]:

            self.context_controller.remember_system_result(
                system_query_result
            )


            self.response_panel.set_response(
                (
                    "SYSTEM // "
                    + system_query_result[
                        "message"
                    ]
                )
            )


            return


        # =================================================
        # PHASE 3 SECURITY CONTROL
        # =================================================

        if self.handle_security_control_command(
            command,
            speak=False
        ):
            return

        # =================================================
        # GLITCH SECURITY ENGINE
        # =================================================

        security_result = (
            self.security_query_controller
            .parse(
                command
            )
        )


        if security_result[
            "handled"
        ]:

            action = (
                security_result[
                    "action"
                ]
            )


            if action == "SCAN_DIRECTORY":

                self.start_security_scan(
                    security_result[
                        "target"
                    ],
                    speak_response=False
                )

            else:

                message = (
                    security_result[
                        "message"
                    ]
                    or "Security command processed."
                )


                self.response_panel.set_response(
                    f"SECURITY // {message}"
                )


                self.security_matrix_page.refresh_security_state()


            return


        # =================================================
        # LIVE WEATHER INTELLIGENCE
        # =================================================

        if (
            self.weather_query_controller
            .can_handle(
                command
            )
        ):

            self.start_weather_request(
                command,
                speak_response=False
            )

            return


        # =================================================
        # ADVANCED KEYBOARD CONTEXT HISTORY
        # =================================================

        if command in [
            "what did i do before that",
            "what happened before that",
            "what was the action before that",
        ]:

            description = (
                self.describe_interaction(
                    self.get_interaction_by_offset(
                        1
                    )
                )
            )


            self.response_panel.set_response(
                description
                if description is not None
                else "CONTEXT // NO EARLIER INTERACTION"
            )

            return


        if command in [
            "show me my last 3 actions",
            "show my last 3 actions",
            "what were my last 3 actions",
            "tell me my last 3 actions",
        ]:

            descriptions = (
                self.get_recent_interaction_descriptions(
                    3
                )
            )


            if not descriptions:

                self.response_panel.set_response(
                    "CONTEXT // NO RECENT INTERACTIONS"
                )

            else:

                self.response_panel.set_response(
                    "\n".join(
                        f"{index + 1}. {description}"
                        for index, description
                        in enumerate(
                            descriptions
                        )
                    )
                )


            return


        if command in [
            "go back to the last screen i opened with gesture",
            "return to the last screen i opened with gesture",
            "go to the last page i opened with gesture",
            "last page i opened with gesture",
        ]:

            target = (
                self.get_last_navigation_target_by_source(
                    "GESTURE"
                )
            )


            if target is None:

                self.response_panel.set_response(
                    "CONTEXT // NO PREVIOUS GESTURE NAVIGATION TARGET"
                )

            else:

                self.navigate_with_intent(
                    target,
                    "KEYBOARD"
                )


            return


        if command in [
            "repeat my last navigation",
            "repeat the last navigation",
            "repeat my last page change",
        ]:

            target = (
                self.get_last_navigation_target()
            )


            if target is None:

                self.response_panel.set_response(
                    "CONTEXT // NO PREVIOUS NAVIGATION TARGET"
                )

            else:

                self.navigate_with_intent(
                    target,
                    "KEYBOARD"
                )


            return


        # =================================================
        # DEEPER KEYBOARD CONTEXT AWARENESS
        # =================================================

        if command in [
            "what did i just do",
            "what was my last action",
            "what did i do last",
        ]:

            description = (
                self.describe_last_interaction()
            )


            self.response_panel.set_response(
                description
                if description is not None
                else "CONTEXT // NO RECENT INTERACTION"
            )

            return


        if command in [
            "what screen was i on before this",
            "what was the previous screen",
            "what page was i on before this",
        ]:

            target = (
                self.get_previous_navigation_target()
            )


            if target is None:

                self.response_panel.set_response(
                    "CONTEXT // NO PREVIOUS SCREEN"
                )

            else:

                self.response_panel.set_response(
                    f"CONTEXT // PREVIOUS SCREEN: {target}"
                )


            return


        if command in [
            "go back two screens",
            "back two screens",
            "go back 2 screens",
            "back 2 screens",
        ]:

            target = (
                self.get_navigation_target_by_steps(
                    2
                )
            )


            if target is None:

                self.response_panel.set_response(
                    "CONTEXT // NOT ENOUGH NAVIGATION HISTORY"
                )

            else:

                self.navigate_with_intent(
                    target,
                    "KEYBOARD"
                )


            return


        if command in [
            "return to the last page i opened with voice",
            "go to the last page i opened with voice",
            "last page i opened with voice",
        ]:

            target = (
                self.get_last_navigation_target_by_source(
                    "VOICE"
                )
            )


            if target is None:

                self.response_panel.set_response(
                    "CONTEXT // NO PREVIOUS VOICE NAVIGATION TARGET"
                )

            else:

                self.navigate_with_intent(
                    target,
                    "KEYBOARD"
                )


            return


        # =================================================
        # CONTEXT-AWARE KEYBOARD NAVIGATION
        # =================================================

        if command in [
            "back",
            "go back",
            "return",
            "return to last screen",
            "go to the last screen",
            "previous screen",
        ]:

            self.navigate_back(
                "KEYBOARD"
            )

            return


        # =================================================
        # PHASE 1 KEYBOARD NAVIGATION INTENTS
        # =================================================

        # The command bar can now express navigation through
        # the same InteractionIntent pipeline as voice,
        # gesture, and mouse input.
        navigation_commands = {

            "home": "HOME",
            "go home": "HOME",
            "open home": "HOME",

            "chat": "CHAT",
            "open chat": "CHAT",
            "go to chat": "CHAT",

            "create": "CREATE",
            "open create": "CREATE",
            "go to create": "CREATE",

            "search": "SEARCH",
            "open search": "SEARCH",

            "code": "CODE",
            "open code": "CODE",

            "apps": "APPS",
            "open apps": "APPS",

            "settings": "SETTINGS",
            "open settings": "SETTINGS",

            "system matrix": "SYSTEM_MATRIX",
            "open system matrix": "SYSTEM_MATRIX",
            "open diagnostics": "SYSTEM_MATRIX",
            "show diagnostics": "SYSTEM_MATRIX",
            "show system stats": "SYSTEM_MATRIX",

            "security matrix": "SECURITY_MATRIX",
            "open security matrix": "SECURITY_MATRIX",
            "show security matrix": "SECURITY_MATRIX",
            "open security": "SECURITY_MATRIX",
            "show security": "SECURITY_MATRIX",
            "security hub": "SECURITY_MATRIX",
            "open security hub": "SECURITY_MATRIX",

            "career matrix": "CAREER_MATRIX",
            "open career matrix": "CAREER_MATRIX",
            "show career matrix": "CAREER_MATRIX",
            "career": "CAREER_MATRIX",
            "careers": "CAREER_MATRIX",
        }


        destination = (
            navigation_commands
            .get(
                command
            )
        )


        if destination is not None:

            self.navigate_with_intent(
                destination,
                "KEYBOARD"
            )

            return


        # =================================================
        # NORMAL AI COMMAND BAR REQUEST
        # =================================================

        # Anything that is not a deterministic navigation
        # command keeps the existing AI behavior unchanged.
        contextual_command = (
            self.context_controller
            .build_ai_context(
                command
            )
        )


        self.start_ai_request(
            contextual_command,
            self.current_mode
        )


    def handle_ai_response(
        self,
        response
    ):

        mode = (
            self.pending_ai_mode
        )


        self.response_panel.set_response(
            response
        )


        self.adaptive_context_service.observe_assistant(
            response
        )


        if mode == "CHAT":

            self.chat_history.append(
                f"\nGLITCH > {response}\n"
            )


        elif mode == "CONVERSATION":

            # Spoken conversational responses stay in the current
            # interface instead of being treated as CHAT history.
            pass


        elif mode == "SEARCH":

            self.search_results.setPlainText(
                response
            )


        self.status_panel.set_core_status(
            "ONLINE"
        )


        memory_count = (
            self.assistant
            .memory
            .count_memories()
        )


        self.status_panel.set_memory_status(
            f"ACTIVE [{memory_count}]"
        )


        self.reactor.trigger_glitch(
            0.75,
            12
        )


        if (
            hasattr(
                self,
                "conversation_controller"
            )
            and self.conversation_controller.is_active()
        ):

            self.conversation_controller.touch()


        if getattr(self, "_ai_stream_begun", False):

            # Already speaking: just let it finish the last sentence.
            self._ai_stream_begun = False

            self.voice_engine.end_stream()

        elif self.voice_enabled:

            self.voice_engine.speak(
                response
            )


    def handle_ai_partial(
        self,
        delta
    ):

        self._ai_partial_text += delta

        self.response_panel.set_response(
            self._ai_partial_text
        )

        if not self.voice_enabled:

            return

        if not self._ai_stream_begun:

            self._ai_stream_begun = True

            self.voice_engine.begin_stream()

        self.voice_engine.feed(
            delta
        )


    def handle_ai_error(
        self,
        error
    ):

        if getattr(self, "_ai_stream_begun", False):

            self._ai_stream_begun = False

            self.voice_engine.stop()

        self.status_panel.set_core_status(
            "ERROR"
        )


        self.response_panel.set_response(
            f"GLITCH.EXE ERROR // {error}"
        )


        if (
            self.pending_ai_mode
            == "SEARCH"
        ):

            self.search_results.setPlainText(
                f"SEARCH ERROR:\n{error}"
            )


    def cleanup_ai_thread(self):

        self.ai_thread = None
        self.ai_worker = None


    # =====================================================
    # PAGE ANIMATION
    # =====================================================

    def play_hud_transition(self):

        destination = (
            self.current_mode
            .strip()
            .upper()
        )

        # The warp overlay is already doing the cinematic part.
        if getattr(self, "_warp_in_progress", False):

            self.pending_sweep_direction = 0

            self.pending_sweep_vertical = False

            return


        title, subtitle = PAGE_TITLES.get(
            destination,
            (
                destination.replace(
                    "_",
                    " "
                ),
                "HUD ONLINE"
            )
        )


        direction = (
            self.pending_sweep_direction
        )

        vertical = (
            self.pending_sweep_vertical
        )


        self.pending_sweep_direction = 0

        self.pending_sweep_vertical = False


        self.transition_overlay.play(
            title,
            subtitle,
            direction,
            vertical
        )


    def animate_page(
        self,
        page
    ):

        self.play_hud_transition()


        effect = (
            QGraphicsOpacityEffect(
                page
            )
        )


        page.setGraphicsEffect(
            effect
        )


        animation = (
            QPropertyAnimation(
                effect,
                b"opacity",
                self
            )
        )


        animation.setDuration(
            260
        )


        animation.setStartValue(
            0.10
        )


        animation.setEndValue(
            1.0
        )


        animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )


        animation.finished.connect(
            lambda:
                page.setGraphicsEffect(
                    None
                )
        )


        self.page_animation = (
            animation
        )


        animation.start()


    # =====================================================
    # SOUND
    # =====================================================

    def play_ui_sound(
        self,
        mode
    ):

        effect = (
            self.ui_sounds.get(
                mode
            )
        )


        if effect:

            effect.stop()

            effect.play()


    # =====================================================
    # PAGE NAVIGATION RENDERER
    # =====================================================

    def show_page(
        self,
        destination
    ):
        """
        Render a requested GLITCH page.

        NavigationController calls this method after a
        NavigationCommand has been routed through CommandRouter.

        This method owns only the visual page-switch behavior.
        """

        destination = (
            destination
            .strip()
            .upper()
        )


        page_map = {

            "HOME": (
                self.home_page,
                "HOME // LIVE SYSTEM TELEMETRY",
                self.sidebar.home_button,
                "HOME",
                0.55,
                9
            ),

            "CHAT": (
                self.chat_page,
                "CHAT // COMMUNICATION CHANNEL READY",
                self.sidebar.chat_button,
                "CHAT",
                0.55,
                9
            ),

            "CREATE": (
                self.create_page_widget,
                "CREATE // CREATIVE SYSTEMS READY",
                self.sidebar.create_button,
                "CREATE",
                0.55,
                9
            ),

            "SEARCH": (
                self.search_page,
                "SEARCH // LIVE INFORMATION NETWORK READY",
                self.sidebar.search_button,
                "SEARCH",
                0.55,
                9
            ),

            "CODE": (
                self.code_page,
                "CODE // DEVELOPMENT ENVIRONMENT READY",
                self.sidebar.code_button,
                "CODE",
                0.55,
                9
            ),

            "APPS": (
                self.apps_page,
                "APPS // APPLICATION CONTROL READY",
                self.sidebar.apps_button,
                "APPS",
                0.55,
                9
            ),

            "SETTINGS": (
                self.settings_page,
                "SETTINGS // CONFIGURATION READY",
                self.sidebar.settings_button,
                "SETTINGS",
                0.55,
                9
            ),

            # SYSTEM MATRIX is an extension of HOME, so the
            # HOME sidebar button and HOME sound stay active.
            "SYSTEM_MATRIX": (
                self.system_matrix_page,
                "SYSTEM MATRIX // HARDWARE DIAGNOSTICS ONLINE",
                self.holo_nav.matrix_button,
                "HOME",
                0.90,
                16
            ),

            # CAREER MATRIX: the next matrix after SECURITY (swipe left).
            "CAREER_MATRIX": (
                self.career_page,
                "CAREER MATRIX // CAMPUS + JOBS + STYLE ONLINE",
                getattr(self.holo_nav, "career_button", None),
                "HOME",
                0.90,
                16
            ),

            # Hidden section: double-tap empty space or ask by voice.
            "SPORTS": (
                self.sports_page,
                "SPORTS // HOLO-NEXUS ONLINE",
                None,
                "SPORTS",
                0.90,
                16
            ),

            # SECURITY MATRIX is another HOME-adjacent system layer.
            # Until a dedicated sidebar control is added, HOME remains
            # highlighted while navigating internal GLITCH matrices.
            "SECURITY_MATRIX": (
                self.security_matrix_page,
                "SECURITY MATRIX // CYBER DEFENSE GRID ONLINE",
                self.holo_nav.security_button,
                "HOME",
                1.00,
                18
            ),
        }


        page_info = (
            page_map.get(
                destination
            )
        )


        if page_info is None:

            self.response_panel.set_response(
                f"NAVIGATION ERROR // UNKNOWN DESTINATION: {destination}"
            )

            return False


        (
            page,
            response,
            active_button,
            sound_mode,
            glitch_duration,
            glitch_intensity
        ) = page_info


        self.current_mode = (
            destination
        )


        if sound_mode in self.ui_sounds:

            self.play_ui_sound(
                sound_mode
            )


        self.page_stack.setCurrentWidget(
            page
        )


        self.animate_page(
            page
        )


        if getattr(self, "authenticated", False) and hasattr(self, "auth_voice"):

            self.auth_voice.note_page(
                destination
            )


        self.response_panel.set_response(
            response
        )


        self.set_active_sidebar_button(
            active_button
        )


        self.holo_projector.set_active(
            destination
        )


        self.update_sports_theme(
            destination
        )


        self.reactor.trigger_glitch(
            glitch_duration,
            glitch_intensity
        )


        return True


    # =====================================================
    # COMMAND-BASED NAVIGATION
    # =====================================================

    def handle_interaction_processed(
        self,
        event
    ):
        """
        Refresh the visible interaction history whenever the
        InteractionController publishes INTERACTION_PROCESSED.
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    8
                )
            )


            lines = []


            for intent in recent:

                action = (
                    intent.normalized_action()
                )


                target = (
                    intent.normalized_target()
                )


                source = (
                    intent.source
                    .strip()
                    .upper()
                )


                target_text = (
                    target
                    if target is not None
                    else "-"
                )


                lines.append(
                    f"[{source:<8}] "
                    f"{action:<10} -> "
                    f"{target_text}"
                )


            if not lines:

                lines = [
                    "INTERACTION HISTORY // waiting for input..."
                ]


            self.interaction_history_view.setPlainText(
                "\n".join(
                    lines
                )
            )


            scrollbar = (
                self.interaction_history_view
                .verticalScrollBar()
            )


            scrollbar.setValue(
                scrollbar.maximum()
            )


        except Exception as error:

            print(
                f"INTERACTION HISTORY ERROR // {error}"
            )


    def get_interaction_by_offset(
        self,
        offset=0
    ):
        """
        Return a recent InteractionIntent by reverse offset.

        offset=0 -> most recent interaction
        offset=1 -> interaction before that
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    100
                )
            )


            index = (
                len(recent)
                - 1
                - offset
            )


            if (
                index >= 0
                and index < len(recent)
            ):

                return recent[
                    index
                ]


        except Exception as error:

            self.response_panel.set_response(
                f"CONTEXT ERROR // {error}"
            )


        return None


    def describe_interaction(
        self,
        intent
    ):
        """
        Convert an InteractionIntent into a short,
        human-readable sentence.
        """

        if intent is None:
            return None


        action = (
            intent.normalized_action()
        )


        target = (
            intent.normalized_target()
        )


        source = (
            intent.source
            .strip()
            .upper()
        )


        if action == "NAVIGATE":

            readable_target = (
                target
                .replace(
                    "_",
                    " "
                )
                if target is not None
                else "an unknown screen"
            )


            return (
                f"You navigated to {readable_target} "
                f"using {source.lower()}."
            )


        return (
            f"Your action was {action.lower()} "
            f"from {source.lower()}."
        )


    def get_recent_interaction_descriptions(
        self,
        limit=3
    ):
        """
        Return up to 'limit' recent interactions as readable
        numbered descriptions, newest first.
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    limit
                )
            )


            descriptions = []


            for intent in reversed(
                recent
            ):

                description = (
                    self.describe_interaction(
                        intent
                    )
                )


                if description is not None:

                    descriptions.append(
                        description
                    )


            return descriptions


        except Exception as error:

            self.response_panel.set_response(
                f"CONTEXT ERROR // {error}"
            )


        return []


    def get_last_navigation_target(
        self
    ):
        """
        Return the most recent navigation target that differs
        from the screen currently being displayed.
        """

        return (
            self.get_navigation_target_by_steps(
                1
            )
        )


    def get_last_interaction(
        self
    ):
        """
        Return the most recent InteractionIntent, if one exists.
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    1
                )
            )


            if recent:
                return recent[-1]


        except Exception as error:

            self.response_panel.set_response(
                f"CONTEXT ERROR // {error}"
            )


        return None


    def describe_last_interaction(
        self
    ):
        """
        Describe the most recent interaction.
        """

        return (
            self.describe_interaction(
                self.get_last_interaction()
            )
        )


    def get_navigation_target_by_steps(
        self,
        steps_back=1
    ):
        """
        Walk backward through unique navigation states.

        steps_back=1 returns the previous screen.
        steps_back=2 returns the screen before that.
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    100
                )
            )


            current = (
                self.current_mode
                .strip()
                .upper()
            )


            unique_targets = []


            for intent in reversed(
                recent
            ):

                if (
                    intent.normalized_action()
                    != "NAVIGATE"
                ):

                    continue


                target = (
                    intent.normalized_target()
                )


                if (
                    target is None
                    or target == current
                ):

                    continue


                if (
                    target
                    not in unique_targets
                ):

                    unique_targets.append(
                        target
                    )


            index = (
                steps_back - 1
            )


            if (
                index >= 0
                and index < len(
                    unique_targets
                )
            ):

                return (
                    unique_targets[
                        index
                    ]
                )


        except Exception as error:

            self.response_panel.set_response(
                f"CONTEXT ERROR // {error}"
            )


        return None


    def get_last_navigation_target_by_source(
        self,
        source
    ):
        """
        Return the most recent navigation target produced by
        a specific input source, such as VOICE or MOUSE.
        """

        try:

            recent = (
                self.interaction_controller
                .get_recent_interactions(
                    100
                )
            )


            source = (
                source
                .strip()
                .upper()
            )


            current = (
                self.current_mode
                .strip()
                .upper()
            )


            for intent in reversed(
                recent
            ):

                if (
                    intent.normalized_action()
                    != "NAVIGATE"
                ):

                    continue


                intent_source = (
                    intent.source
                    .strip()
                    .upper()
                )


                target = (
                    intent.normalized_target()
                )


                if (
                    intent_source == source
                    and target is not None
                    and target != current
                ):

                    return target


        except Exception as error:

            self.response_panel.set_response(
                f"CONTEXT ERROR // {error}"
            )


        return None


    def get_previous_navigation_target(
        self
    ):
        """
        Return the immediately previous unique navigation target.
        """

        return (
            self.get_navigation_target_by_steps(
                1
            )
        )


    def navigate_back(
        self,
        source="UNKNOWN"
    ):
        """
        Context-aware navigation command.

        GLITCH uses recent interaction history to determine
        which screen should be considered the previous screen.
        """

        target = (
            self.get_previous_navigation_target()
        )


        if target is None:

            self.response_panel.set_response(
                "CONTEXT // NO PREVIOUS SCREEN AVAILABLE"
            )

            return False


        return (
            self.navigate_with_intent(
                target,
                source
            )
        )


    def navigate_with_intent(
        self,
        destination,
        source="MOUSE"
    ):
        """
        Route an input-driven navigation request through the
        Phase 1 InteractionIntent pipeline.

        Sidebar mouse clicks use source='MOUSE'. Other input
        systems can reuse this helper later with their own
        source labels.
        """

        try:

            intent = InteractionIntent(

                action="NAVIGATE",

                target=destination,

                source=source,

                confidence=1.0,

                data={
                    "current_mode":
                        self.current_mode,
                }
            )


            return (
                self.interaction_controller
                .handle_intent(
                    intent
                )
            )


        except Exception as error:

            self.response_panel.set_response(
                f"INTERACTION ERROR // {error}"
            )

            return False


    def navigate_to(
        self,
        destination
    ):

        if not self.authenticated:
            return False
        """
        Send every navigation request through CommandRouter.
        """

        try:

            return self.command_router.execute(
                "NAVIGATE",
                destination
            )

        except Exception as error:

            self.response_panel.set_response(
                f"NAVIGATION ERROR // {error}"
            )

            return False


    # =====================================================
    # PUBLIC NAVIGATION HELPERS
    # =====================================================

    # These small wrappers are intentionally kept so existing
    # sidebar, voice, gesture, and AI code does not have to
    # change. Every wrapper now uses the same command pipeline.

    def open_home(self):

        return self.navigate_to(
            "HOME"
        )


    def open_chat(self):

        return self.navigate_to(
            "CHAT"
        )


    def open_create(self):

        return self.navigate_to(
            "CREATE"
        )


    def open_search(self):

        return self.navigate_to(
            "SEARCH"
        )


    def open_code(self):

        return self.navigate_to(
            "CODE"
        )


    def open_apps(self):

        return self.navigate_to(
            "APPS"
        )


    def open_settings(self):

        return self.navigate_to(
            "SETTINGS"
        )


    def open_system_matrix(self):

        return self.navigate_to(
            "SYSTEM_MATRIX"
        )


    def open_security_matrix(self):

        return self.navigate_to(
            "SECURITY_MATRIX"
        )


    def open_career_matrix(self):

        return self.navigate_to(
            "CAREER_MATRIX"
        )


    # =====================================================
    # PERFORMANCE MODE
    # =====================================================

    def _sync_reactor_visibility(self):

        """Show the live reactor only when it can actually be seen."""

        covered = (
            hasattr(self, "sports_backdrop")
            and self.current_mode == "SPORTS"
            and self.sports_backdrop.is_fully_covering()
        )

        frozen = getattr(self, "performance_mode", False)

        self.reactor.setVisible(not covered and not frozen)

        snapshot = getattr(self, "_reactor_snapshot", None)

        if snapshot is not None:

            snapshot.setVisible(frozen and not covered)


    def set_performance_mode(
        self,
        enabled,
        announce=False
    ):

        """Freeze the animated reactor into a still image (it repaints
        the whole window many times a second), and calm the hand
        hologram to 30 fps."""

        enabled = bool(enabled)

        if enabled and not getattr(self, "performance_mode", False):

            # Take the still before hiding the live reactor (grab()
            # renders it even if it's currently hidden).
            if True:

                pixmap = self.reactor.grab()

                if getattr(self, "_reactor_snapshot", None) is None:

                    self._reactor_snapshot = QLabel(
                        self.central_widget
                    )

                    self._reactor_snapshot.setScaledContents(True)

                    self._reactor_snapshot.setAttribute(
                        Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                        True
                    )

                self._reactor_snapshot.setPixmap(pixmap)

                self._reactor_snapshot.setGeometry(
                    self.reactor.geometry()
                )

                self.update_layout()

        self.performance_mode = enabled

        self.settings_data["performance_mode"] = enabled

        self.save_settings()

        self.hand_overlay._timer.setInterval(
            33 if enabled else 16
        )

        if hasattr(self, "performance_checkbox"):

            self.performance_checkbox.blockSignals(True)

            self.performance_checkbox.setChecked(enabled)

            self.performance_checkbox.blockSignals(False)

        self._sync_reactor_visibility()

        if announce:

            self.say_confirmation(
                "Enabling performance mode. The background is now still."
                if enabled
                else "Disabling performance mode. Full animation is back."
            )


    # =====================================================
    # GESTURE / HOLOGRAM TOGGLES
    # =====================================================

    def set_gesture_control(
        self,
        enabled,
        announce=False
    ):

        """Turn hand control (camera tracking, swipes, pinch, pointer)
        on or off. Off releases the camera completely."""

        enabled = bool(enabled)

        self.gesture_control_enabled = enabled

        self.settings_data["gesture_control_enabled"] = enabled

        self.save_settings()

        if hasattr(self, "gesture_checkbox"):

            self.gesture_checkbox.blockSignals(True)

            self.gesture_checkbox.setChecked(enabled)

            self.gesture_checkbox.blockSignals(False)

        if enabled:

            self._resume_hand_tracking()

        else:

            try:

                self.hand_tracker.stop()

            except Exception:

                pass

            self.hand_overlay.clear_hand()

            self.clear_finger_hover()

            self.status_panel.set_gesture_status(
                "DISABLED"
            )

        if announce:

            self.say_confirmation(
                "Enabling gesture control."
                if enabled
                else "Disabling gesture control. The camera is off."
            )


    def _resume_hand_tracking(
        self,
        attempts=12
    ):

        """Restart tracking; if the previous run is still shutting
        down, try again shortly."""

        if not self.gesture_control_enabled or not self.authenticated:

            return

        if self.hand_thread.isRunning():

            if self.hand_tracker.running:

                return

            if attempts > 0:

                QTimer.singleShot(
                    250,
                    lambda: self._resume_hand_tracking(attempts - 1)
                )

            return

        self.start_hand_tracking()


    def set_hand_hologram(
        self,
        visible,
        announce=False
    ):

        """Show or hide the holographic hand. Gestures keep working;
        the fingertip pointer and button brackets stay visible."""

        visible = bool(visible)

        self.hand_hologram_enabled = visible

        self.settings_data["hand_hologram_enabled"] = visible

        self.save_settings()

        self.hand_overlay.set_hologram_visible(visible)

        if hasattr(self, "hologram_checkbox"):

            self.hologram_checkbox.blockSignals(True)

            self.hologram_checkbox.setChecked(visible)

            self.hologram_checkbox.blockSignals(False)

        if self.gesture_control_enabled and self.hand_thread.isRunning():

            self.status_panel.set_gesture_status(
                "TRACKING" if visible else "TRACKING // HOLO OFF"
            )

        if announce:

            self.say_confirmation(
                "Showing the holographic hand."
                if visible
                else "Hiding the holographic hand. Gestures still work."
            )


    GESTURE_WORDS = (
        "gesture", "gestures", "hand tracking", "hand control",
        "finger swipe", "finger swipes", "swipe", "swipes", "swiping",
        "hand gestures", "finger tracking", "tracking my hand",
    )

    HOLOGRAM_WORDS = (
        "hologram", "holographic", "hand hologram", "finger hologram",
        "holo hand", "skeleton hand",
    )


    def handle_gesture_toggle_command(
        self,
        command
    ):

        """'turn off gestures', 'enable finger swipe', 'hide the
        hologram', 'holographic hand on', 'toggle gestures' ..."""

        lowered = (
            " "
            + command
            .strip()
            .lower()
            .strip(" ,.!?")
            + " "
        )

        off_words = (
            " off ", " disable", " deactivate", " hide", " stop",
            " turn off", " switch off", " kill",
        )

        on_words = (
            " on ", " enable", " activate", " show", " start",
            " turn on", " switch on", " bring back",
        )

        toggle = " toggle" in lowered

        wants_off = any(word in lowered for word in off_words)

        wants_on = any(word in lowered for word in on_words)

        # "turn on ..." contains " on " as well as " turn on".
        if wants_off and wants_on:

            first_off = min(
                (lowered.find(word) for word in off_words if word in lowered),
                default=10**6
            )

            first_on = min(
                (lowered.find(word) for word in on_words if word in lowered),
                default=10**6
            )

            wants_off = first_off < first_on

            wants_on = not wants_off

        if not (toggle or wants_off or wants_on):

            return False

        if "performance mode" in lowered or "smooth mode" in lowered:

            target = (
                not self.performance_mode
                if toggle
                else wants_on
            )

            self.set_performance_mode(
                target,
                announce=True
            )

            return True

        about_hologram = any(word in lowered for word in self.HOLOGRAM_WORDS)

        about_gestures = any(word in lowered for word in self.GESTURE_WORDS)

        # "holographic finger swipe" -> it's about the swipe control.
        if about_hologram and about_gestures and "swipe" not in lowered and "tracking" not in lowered:

            about_gestures = False

        if about_gestures:

            target = (
                not self.gesture_control_enabled
                if toggle
                else wants_on
            )

            self.set_gesture_control(
                target,
                announce=True
            )

            return True

        if about_hologram:

            target = (
                not self.hand_hologram_enabled
                if toggle
                else wants_on
            )

            self.set_hand_hologram(
                target,
                announce=True
            )

            return True

        return False


    # =====================================================
    # CAREER MATRIX
    # =====================================================

    CAREER_GARMENTS = (
        ("quarter zip", "top", "QUARTER-ZIP"),
        ("quarter-zip", "top", "QUARTER-ZIP"),
        ("button up", "top", "BUTTON-UP"),
        ("button-up", "top", "BUTTON-UP"),
        ("dress shirt", "top", "BUTTON-UP"),
        ("hoodie", "top", "HOODIE"),
        ("polo", "top", "POLO"),
        ("t-shirt", "top", "TEE"),
        ("tshirt", "top", "TEE"),
        ("tee", "top", "TEE"),
        ("shirt", "top", "BUTTON-UP"),
        ("blazer", "top", "SUIT JACKET"),
        ("sweatpants", "bottom", "SWEATPANTS"),
        ("joggers", "bottom", "JOGGERS"),
        ("shorts", "bottom", "SHORTS"),
        ("jeans", "bottom", "JEANS"),
        ("chinos", "bottom", "CHINOS"),
        ("slacks", "bottom", "SUIT PANTS"),
        ("dress shoes", "shoes", "DRESS SHOES"),
        ("loafers", "shoes", "DRESS SHOES"),
        ("high tops", "shoes", "HIGH-TOPS"),
        ("high-tops", "shoes", "HIGH-TOPS"),
        ("sneakers", "shoes", "SNEAKERS"),
        ("shoes", "shoes", "SNEAKERS"),
        ("boots", "shoes", "BOOTS"),
        ("slides", "shoes", "SLIDES"),
    )

    CAREER_WORDS = {
        "shade": {
            "emerald": "EMERALD", "forest": "FOREST", "hunter": "HUNTER",
            "olive": "OLIVE", "sage": "SAGE", "mint": "MINT",
            "neon": "NEON", "lime": "NEON",
        },
        "fit": {"slim": "SLIM", "oversized": "OVERSIZED", "baggy": "OVERSIZED", "regular": "REGULAR"},
        "style": {
            "streetwear": "STREETWEAR", "business": "BUSINESS", "athletic": "ATHLETIC",
            "gym": "ATHLETIC", "techwear": "TECHWEAR", "smart casual": "SMART CASUAL",
        },
    }


    def _open_career(
        self,
        source,
        tab=None
    ):

        if not self.authenticated:

            return

        if tab:

            self.career_page.set_tab(tab)

        if self.current_mode != "CAREER_MATRIX":

            self.navigate_with_intent(
                "CAREER_MATRIX",
                source
            )

            if self.current_mode != "CAREER_MATRIX":

                self.show_page(
                    "CAREER_MATRIX"
                )


    def handle_career_command(
        self,
        command,
        source="VOICE"
    ):

        """Career Matrix navigation and the outfit Customizer by
        voice. Questions ('what's happening on campus?', 'any
        internships?') fall through to the AI, which gets the live
        Career Matrix data as context."""

        lowered = (
            command
            .strip()
            .lower()
            .strip(" ,.!?")
        )

        opening = lowered.startswith(
            (
                "open", "show", "pull up", "bring up", "go to",
                "launch", "take me to", "switch to",
            )
        )

        # ---- outfit: recommendation
        if any(
            phrase in lowered
            for phrase in (
                "what should i wear", "recommend an outfit", "recommend me an outfit",
                "pick my outfit", "pick an outfit", "pick my fit", "outfit for today",
                "what do i wear", "style me",
            )
        ):

            self._open_career(source, "STYLE")

            self.career_page.recommend(command)

            self.say_confirmation(
                "Picking your fit."
            )

            return True

        # ---- outfit: find specific pieces
        if lowered.startswith(("find me", "find a", "find some", "search for", "look for", "get me")):

            changes = {}

            for word, category, value in self.CAREER_GARMENTS:

                if word in lowered and category not in changes:

                    changes[category] = value

            if "suit" in lowered and "top" not in changes:

                changes.update(
                    {"top": "SUIT JACKET", "bottom": "SUIT PANTS", "shoes": "DRESS SHOES", "style": "BUSINESS"}
                )

            if not changes:

                return False

            for category, words in self.CAREER_WORDS.items():

                for word, value in words.items():

                    if word in lowered:

                        changes[category] = value

            budget = re.search(r"under \$?(\d+)", lowered)

            if budget:

                amount = int(budget.group(1))

                changes["budget"] = next(
                    (option for option in ("$50", "$100", "$200", "$400") if amount <= int(option[1:])),
                    "ANY"
                )

            self._open_career(source, "STYLE")

            for category, value in changes.items():

                self.career_page.choose(category, value)

            self.career_page.find(command)

            self.say_confirmation(
                "Searching stores for that look."
            )

            return True

        if not opening and lowered not in ("career", "careers", "career matrix", "the career matrix"):

            return False

        # ---- navigation
        if "career" in lowered:

            self._open_career(source)

            self.say_confirmation("Opening the Career Matrix.")

            return True

        tab = None

        if any(word in lowered for word in ("job", "internship", "handshake")):

            tab = "JOBS"

        elif "campus" in lowered or "istrike" in lowered or "famu" in lowered:

            tab = "CAMPUS"

        elif "news" in lowered or "headlines" in lowered:

            tab = "WORLD"

        elif any(word in lowered for word in ("outfit", "customizer", "my style", "my fit", "wardrobe")):

            tab = "STYLE"

        if tab is None:

            return False

        self._open_career(source, tab)

        self.say_confirmation(
            {
                "JOBS": "Pulling up your job leads.",
                "CAMPUS": "Pulling up campus intel.",
                "WORLD": "Pulling up the news.",
                "STYLE": "Opening the Customizer.",
            }[tab]
        )

        return True


    # =====================================================
    # SPORTS NEXUS
    # =====================================================

    def toggle_sports_nexus(
        self,
        source="GESTURE",
        team_key=None
    ):

        """Warp into the Sports Nexus, or back to where you were."""

        if not self.authenticated:

            return

        if self.warp_overlay.is_playing():

            return

        entering = (
            self.current_mode != "SPORTS"
        )

        if team_key:

            self.sports_page.select_team(team_key)

        if entering:

            self._pre_sports_mode = (
                self.current_mode
            )

            target = "SPORTS"

            title, subtitle = PAGE_TITLES.get(
                "SPORTS",
                ("SPORTS NEXUS", "")
            )

            tint = self.sports_page._colors()[0]

        else:

            target = (
                self._pre_sports_mode
                or "HOME"
            )

            title, subtitle = PAGE_TITLES.get(
                target,
                (target.replace("_", " "), "HUD ONLINE")
            )

            tint = None

        sound = self.warp_sounds.get(
            "in" if entering else "out"
        )

        if sound is not None:

            sound.stop()

            sound.play()

        self.reactor.trigger_glitch(
            1.2,
            20
        )

        self.warp_overlay.play(
            title,
            subtitle,
            reverse=not entering,
            tint=tint,
            on_peak=lambda: self._warp_navigate(
                target,
                source
            )
        )


    def _sports_themed_widgets(self):

        """HUD panels recoloured to the team while in the Nexus."""

        names = (
            "status_panel",
            "response_panel",
            "command_bar",
            "voice_input_badge",
            "holo_nav",
            "holo_projector",
        )

        return [
            getattr(self, name)
            for name in names
            if hasattr(self, name)
        ]


    def update_sports_theme(
        self,
        destination
    ):

        """Team colours on, or back to GLITCH green."""

        if not hasattr(self, "sports_backdrop") or not hasattr(self, "sports_page"):

            return

        active = (
            str(destination).upper() == "SPORTS"
        )

        theme = self.sports_page.theme()

        self.sports_backdrop.set_theme(theme)

        self.sports_backdrop.activate(active)

        # The hand hologram / pointer takes the team colour too
        # (Jaguars teal, Celtics green, Patriots blue), GLITCH green
        # everywhere else.
        if hasattr(self.hand_overlay, "set_tint"):

            self.hand_overlay.set_tint(
                theme["accent"] if active else None
            )

        # GLITCH remembers which team you follow (for the welcome).
        if active and getattr(self, "authenticated", False) and hasattr(self, "auth_voice"):

            self.auth_voice.note_team(
                self.sports_page.current_team_name()
            )

        # The reactor is invisible behind the opaque team backdrop, but
        # its animation would still force full-window repaints. Pause it.
        if active:

            QTimer.singleShot(
                int(self.sports_backdrop.FADE_S * 1000) + 120,
                self._sync_reactor_visibility
            )

        else:

            self._sync_reactor_visibility()

        # Screen-blend tint: dark areas take a mid-tone of the team
        # colour, light text stays light, so panels stay readable.
        accent = QColor(theme["accent"])

        hue, saturation, _, _ = accent.getHsvF()

        tint = QColor.fromHsvF(
            max(0.0, hue),
            min(1.0, saturation),
            0.55
        )

        for widget in self._sports_themed_widgets():

            effect = widget.graphicsEffect()

            if active:

                if effect is None:

                    effect = QGraphicsColorizeEffect(widget)

                    widget.setGraphicsEffect(effect)

                if isinstance(effect, QGraphicsColorizeEffect):

                    effect.setColor(tint)

                    effect.setStrength(1.0)

            elif isinstance(effect, QGraphicsColorizeEffect):

                widget.setGraphicsEffect(None)


    def _warp_navigate(
        self,
        target,
        source
    ):

        self._warp_in_progress = True

        try:

            self.navigate_with_intent(
                target,
                source
            )

            # Fallback if the command router doesn't know SPORTS.
            if self.current_mode != target:

                self.show_page(
                    target
                )

        finally:

            self._warp_in_progress = False


    SPORTS_OPEN_WORDS = (
        "open", "show", "pull up", "bring up", "go to",
        "launch", "take me to", "switch to",
    )

    SPORTS_CLOSE_PHRASES = {
        "close sports", "exit sports", "leave sports",
        "close the sports nexus", "exit the sports nexus",
        "go back", "back out",
    }


    def handle_sports_command(
        self,
        command,
        source="VOICE"
    ):

        """Deterministic sports navigation. Questions ('how are the
        Celtics doing?') fall through to the AI, which gets the live
        sports data as context."""

        lowered = (
            command
            .strip()
            .lower()
            .strip(" ,.!?")
        )

        if (
            lowered in self.SPORTS_CLOSE_PHRASES
            and self.current_mode == "SPORTS"
        ):

            self.toggle_sports_nexus(source)

            self.say_confirmation(
                "Closing the Sports Nexus."
            )

            return True

        wants_open = any(
            lowered.startswith(word)
            for word in self.SPORTS_OPEN_WORDS
        )

        if not wants_open:

            return False

        team_key = (
            self.sports_service
            .match_team(
                lowered
            )
        )

        mentions_sports = any(
            word in lowered
            for word in (
                "sports", "my teams", "scores",
            )
        )

        if team_key is None and not mentions_sports:

            return False

        if self.current_mode == "SPORTS":

            if team_key:

                self.sports_page.select_team(
                    team_key
                )

        else:

            self.toggle_sports_nexus(
                source,
                team_key
            )

        if team_key:

            self.say_confirmation(
                f"Pulling up the {self.sports_page.current_team_name()}."
            )

        else:

            self.say_confirmation(
                "Opening the Sports Nexus."
            )

        return True


    def eventFilter(
        self,
        watched,
        event
    ):

        """Double-click on empty HUD space toggles the Sports Nexus."""

        try:

            if (
                event.type() == QEvent.Type.MouseButtonDblClick
                and isinstance(watched, QWidget)
                and watched.window() is self
                and self.authenticated
            ):

                widget = watched

                while widget is not None and widget is not self:

                    if isinstance(
                        widget,
                        (
                            QAbstractButton,
                            QLineEdit,
                            QTextEdit,
                            QPlainTextEdit,
                            QAbstractSlider,
                            QAbstractSpinBox,
                            QComboBox,
                        )
                    ):

                        return False

                    widget = widget.parentWidget()

                self.toggle_sports_nexus(
                    "MOUSE"
                )

                return True

        except Exception as error:

            print("DOUBLE-TAP FILTER ERROR:", error)

        return super().eventFilter(
            watched,
            event
        )


    # =====================================================
    # SWIPE CONTROL
    # =====================================================

    def handle_swipe_left(self):

        if not self.authenticated:
            return

        if not self.gesture_control_enabled:
            return


        if self.current_mode == "SPORTS":

            self.sports_page.next_team(1)

            self.hand_overlay.flash_swipe(1)

            self.response_panel.set_response(
                f"SPORTS // {self.sports_page.current_team_name().upper()}"
            )

            return


        self.pending_sweep_direction = 1


        success = (
            self.gesture_controller
            .swipe_left(
                self.current_mode
            )
        )


        self.pending_sweep_direction = 0


        if success:

            self.hand_overlay.flash_swipe(
                1
            )


            self.response_panel.set_response(
                "GESTURE // SWIPE LEFT DETECTED"
            )


    def handle_swipe_right(self):

        if not self.authenticated:
            return

        if not self.gesture_control_enabled:
            return


        if self.current_mode == "SPORTS":

            self.sports_page.next_team(-1)

            self.hand_overlay.flash_swipe(-1)

            self.response_panel.set_response(
                f"SPORTS // {self.sports_page.current_team_name().upper()}"
            )

            return


        self.pending_sweep_direction = -1


        success = (
            self.gesture_controller
            .swipe_right(
                self.current_mode
            )
        )


        self.pending_sweep_direction = 0


        if success:

            self.hand_overlay.flash_swipe(
                -1
            )


            self.response_panel.set_response(
                "GESTURE // SWIPE RIGHT DETECTED"
            )


    def handle_swipe_up(self):

        if not self.authenticated:
            return

        if not self.gesture_control_enabled:
            return


        # Hand moved up: the new section sweeps in bottom -> top.
        self.pending_sweep_direction = -1

        self.pending_sweep_vertical = True


        success = (
            self.gesture_controller
            .swipe_up(
                self.current_mode
            )
        )


        self.pending_sweep_direction = 0

        self.pending_sweep_vertical = False


        if success:

            self.hand_overlay.flash_swipe(
                -1,
                vertical=True
            )


            self.response_panel.set_response(
                "GESTURE // SWIPE UP // NEXT SECTION"
            )


    def handle_swipe_down(self):

        if not self.authenticated:
            return

        if not self.gesture_control_enabled:
            return


        self.pending_sweep_direction = 1

        self.pending_sweep_vertical = True


        success = (
            self.gesture_controller
            .swipe_down(
                self.current_mode
            )
        )


        self.pending_sweep_direction = 0

        self.pending_sweep_vertical = False


        if success:

            self.hand_overlay.flash_swipe(
                1,
                vertical=True
            )


            self.response_panel.set_response(
                "GESTURE // SWIPE DOWN // PREVIOUS SECTION"
            )


    # =====================================================
    # FACE-ONLY AUTHENTICATION
    # =====================================================

    def start_authentication(self):

        if self.authenticated:
            return

        if self._face_unlock_in_progress:
            return


        self.hand_overlay.set_enabled(False)
        self.hand_overlay.clear_hand()


        try:

            self.voice_listener.stop()

        except Exception:

            pass


        try:

            self.hand_tracker.stop()

        except Exception:

            pass


        self.finger_cursor.hide()


        self.set_voice_input_status(
            "LOCKED"
        )


        self.auth_overlay.begin_session()


        self.auth_overlay.setGeometry(
            self.central_widget.rect()
        )


        self.auth_overlay.raise_()


        self.auth_voice.session_started()


        self.auth_session.begin()


    def _text_contains_face_success(
        self,
        *values
    ):

        text = " ".join(
            str(value)
            for value in values
            if value is not None
        ).lower()


        success_words = (
            "verified",
            "matched",
            "match",
            "passed",
            "pass",
            "success",
            "confirmed",
            "accepted",
            "granted",
        )


        failure_words = (
            "failed",
            "fail",
            "denied",
            "rejected",
            "mismatch",
            "not verified",
            "not matched",
        )


        if any(
            word in text
            for word in failure_words
        ):

            return False


        return any(
            word in text
            for word in success_words
        )


    def handle_face_auth_status(
        self,
        score,
        present,
        box
    ):

        # Live face_status is presentation feedback only.
        # AuthSession.granted / factor_result decides access.
        return


    def handle_face_factor_result(
        self,
        name,
        ok,
        score
    ):

        if self.authenticated:
            return

        if (
            str(name).strip().upper() == "FACE"
            and bool(ok)
        ):

            self.complete_face_unlock()


    def complete_face_unlock(self):

        if self.authenticated:
            return


        self._face_unlock_in_progress = True

        self.authenticated = True


        # Stop the legacy session immediately after successful
        # camera verification so it cannot advance to voice auth.
        try:

            self.auth_session.shutdown()

        except Exception:

            pass


        self.auth_overlay.show_granted(
            "404"
        )


        # Personal welcome while the unlock animation plays.
        self._auth_greeting = self.auth_voice.granted()


    def handle_auth_granted(
        self,
        result
    ):

        if self.authenticated:
            return

        self._face_unlock_in_progress = True
        self.authenticated = True

        self.auth_overlay.show_granted(
            "404"
        )


        # Personal welcome while the unlock animation plays.
        self._auth_greeting = self.auth_voice.granted()


    def handle_auth_denied(
        self,
        result
    ):

        if self.authenticated:
            return


        self.auth_overlay.show_denied(
            result
        )


    def finish_unlock(self):

        if not self.authenticated:
            return


        self.hand_overlay.set_enabled(
            True
        )


        self._face_unlock_in_progress = False


        self.start_authenticated_systems()


    def start_authenticated_systems(self):

        if self._authenticated_systems_started:
            return


        self._authenticated_systems_started = True


        # If a brand-new security finding appeared while the
        # biometric gate was active, present it now.
        QTimer.singleShot(
            1200,
            self.show_next_security_alert
        )


        self.status_panel.set_core_status(
            "ONLINE"
        )


        self.set_voice_input_status(
            "STARTING"
        )


        self.transition_overlay.play(
            "GLITCH.EXE",
            "FACE VERIFIED // SYSTEMS ONLINE",
            1
        )


        QTimer.singleShot(
            250,
            self.startup_greeting
        )


        QTimer.singleShot(
            1100,
            self.start_hand_tracking
        )


        QTimer.singleShot(
            2200,
            self.start_voice_listener
        )


        QTimer.singleShot(
            3500,
            self.initialize_location_access
        )


    # =====================================================
    # STARTUP
    # =====================================================

    def startup_greeting(self):

        # The biometric gate already welcomed you out loud; show the
        # same words on screen instead of saying hello twice.
        if getattr(self, "_auth_greeting", None):

            self.response_panel.set_response(
                self._auth_greeting
            )

            self.reactor.trigger_glitch(
                0.45,
                8
            )

            return


        greeting = (
            "Hello 404. What's on the agenda?"
        )


        self.response_panel.set_response(
            greeting
        )


        self.reactor.trigger_glitch(
            0.45,
            8
        )


        if self.voice_enabled:

            self.voice_engine.speak(
                greeting
            )


    # =====================================================
    # VOICE OUTPUT
    # =====================================================

    def handle_voice_started(self):

        self.voice_output_active = (
            True
        )


        self.status_panel.set_voice_status(
            "SPEAKING"
        )


        # Keep the microphone open (barge-in) instead of stopping it.
        self.voice_listener.set_assistant_speaking(
            True
        )

        self.set_voice_input_status(
            "LISTENING"
            if self.voice_listener_active
            else "PAUSED"
        )


    def handle_barge_in(self):

        if not self.voice_output_active:

            return

        # Only let you cut GLITCH off mid-conversation. Greetings and
        # announcements (like "Hello 404") always finish.
        if not (
            hasattr(self, "conversation_controller")
            and self.conversation_controller.is_active()
        ):

            return

        self.voice_engine.stop()

        self.response_panel.set_response(
            "GLITCH // GO AHEAD..."
        )

        if (
            hasattr(
                self,
                "conversation_controller"
            )
            and self.conversation_controller.is_active()
        ):

            self.conversation_controller.touch()


    def handle_voice_finished(self):

        self.voice_output_active = (
            False
        )

        self.voice_listener.set_assistant_speaking(
            False
        )

        if self.voice_listener_active:

            self.status_panel.set_voice_status(
                "ONLINE"
                if self.voice_enabled
                else "MUTED"
            )

            self.set_voice_input_status(
                "LISTENING"
            )

            return


        self.status_panel.set_voice_status(
            "ONLINE"
            if self.voice_enabled
            else "MUTED"
        )


        self.set_voice_input_status(
            "STARTING"
        )


        QTimer.singleShot(
            500,
            self.start_voice_listener
        )


    def handle_voice_error(
        self,
        error
    ):

        self.voice_output_active = (
            False
        )

        self.voice_listener.set_assistant_speaking(
            False
        )


        self.status_panel.set_voice_status(
            "ERROR"
        )


        self.set_voice_input_status(
            "STARTING"
        )


        QTimer.singleShot(
            500,
            self.start_voice_listener
        )


    # =====================================================
    # HAND TRACKING
    # =====================================================

    def start_hand_tracking(self):

        if not self.authenticated:
            return


        if not self.gesture_control_enabled:

            self.status_panel.set_gesture_status(
                "DISABLED"
            )

            return


        if not self.hand_thread.isRunning():

            self.status_panel.set_gesture_status(
                "STARTING"
            )


            self.hand_thread.start()


    def handle_tracking_started(self):

        self.status_panel.set_gesture_status(
            "TRACKING"
            if self.hand_hologram_enabled
            else "TRACKING // HOLO OFF"
        )


        # Direct-swipe mode has no visible finger cursor.
        self.finger_cursor.hide()


    def handle_tracking_stopped(self):

        self.status_panel.set_gesture_status(
            "OFFLINE"
            if self.gesture_control_enabled
            else "DISABLED"
        )


        self.finger_cursor.hide()


    def handle_gesture_error(
        self,
        error
    ):

        self.status_panel.set_gesture_status(
            "ERROR"
        )


        self.finger_cursor.hide()


        self.response_panel.set_response(
            f"GESTURE ERROR // {error}"
        )


    # =====================================================
    # TIME
    # =====================================================

    def current_milliseconds(self):

        return int(
            time.perf_counter()
            * 1000
        )


    # =====================================================
    # FINGER CURSOR
    # =====================================================

    def handle_finger_move(
        self,
        normalized_x,
        normalized_y
    ):

        # Legacy compatibility only.
        # Direct-swipe mode does not render a finger cursor or
        # perform dwell-click navigation.
        self.finger_cursor.hide()

        return


    # =====================================================
    # PROXIMITY RIPPLE
    # =====================================================

    HUD_TOUCH_PADDING = 18

    HUD_TOUCH_STICKY = 12

    def _hud_button_list(self):

        # findChildren walks the whole widget tree, so refresh it
        # a few times a second rather than on every camera frame.
        now = time.perf_counter()

        cache = getattr(self, "_hud_button_cache", None)

        if cache is not None and now - cache[0] < 0.15:

            return cache[1]

        buttons = self.central_widget.findChildren(QPushButton)

        self._hud_button_cache = (now, buttons)

        return buttons


    def _hud_button_at(
        self,
        normalized_x,
        normalized_y,
        sticky=None
    ):

        """Best HUD button under a normalized point, as
        (button, QRect in central_widget coordinates), or None.

        A point inside a button beats a point only inside its touch
        padding; ties go to the nearest button centre. The button
        currently hovered (sticky) gets extra reach so the highlight
        does not flicker on its edge."""

        px = normalized_x * self.central_widget.width()

        py = normalized_y * self.central_widget.height()

        best = None

        best_key = None

        for button in self._hud_button_list():

            try:

                if (
                    not button.isVisible()
                    or not button.isEnabled()
                    or button.width() <= 0
                    or button.height() <= 0
                ):

                    continue

                top_left = button.mapTo(
                    self.central_widget,
                    QPoint(0, 0)
                )

            except RuntimeError:

                # Widget was deleted since the cache was built.
                self._hud_button_cache = None

                continue

            rect = QRect(top_left, button.size())

            reach = self.HUD_TOUCH_PADDING

            if button is sticky:

                reach += self.HUD_TOUCH_STICKY

            if not rect.adjusted(
                -reach, -reach, reach, reach
            ).contains(int(px), int(py)):

                continue

            centre = rect.center()

            key = (
                0 if rect.contains(int(px), int(py)) else 1,
                math.hypot(
                    px - centre.x(),
                    py - centre.y()
                )
            )

            if best_key is None or key < best_key:

                best_key = key

                best = (button, rect)

        return best


    def _hud_button_name(self, button):

        return (
            button.text().strip()
            or button.objectName()
            or "HUD CONTROL"
        )


    def handle_finger_hover(
        self,
        normalized_x,
        normalized_y
    ):

        if not self.authenticated:

            return

        if not self.gesture_control_enabled:

            return

        self.hand_overlay.set_pointer(
            normalized_x,
            normalized_y
        )

        hit = self._hud_button_at(
            normalized_x,
            normalized_y,
            sticky=getattr(self, "_finger_target", None)
        )

        if hit is None:

            self.clear_finger_target()

            return

        button, rect = hit

        self.holo_projector.preview(
            getattr(button, "nav_key", "")
        )

        if button is not getattr(self, "_finger_target", None):

            self._finger_target = button

            self._finger_label = self._hud_button_name(button)

        self.hand_overlay.set_hover(
            QRectF(rect),
            self._finger_label
        )


    def clear_finger_target(self):

        if getattr(self, "_finger_target", None) is not None:

            self._finger_target = None

        self.hand_overlay.set_hover(None)

        self.holo_projector.preview("")


    def clear_finger_hover(self):

        self.clear_finger_target()


    def handle_hud_pinch(
        self,
        normalized_x,
        normalized_y
    ):

        if not self.authenticated:

            return

        if not self.gesture_control_enabled:

            return

        hit = self._hud_button_at(
            normalized_x,
            normalized_y
        )

        if hit is None:

            # Two quick taps on empty space = jump to the Sports Nexus.
            now = time.perf_counter()

            if now - self._last_empty_tap < 0.65:

                self._last_empty_tap = 0.0

                self.toggle_sports_nexus("GESTURE")

                return

            self._last_empty_tap = now

            self.response_panel.set_response(
                "GESTURE // PINCH DETECTED // NO HUD TARGET"
            )

            return

        selected_button, rect = hit

        screen_x = int(
            normalized_x
            * self.central_widget.width()
        )

        screen_y = int(
            normalized_y
            * self.central_widget.height()
        )

        try:

            reactor_point = (
                self.reactor.mapFrom(
                    self.central_widget,
                    QPoint(
                        screen_x,
                        screen_y
                    )
                )
            )

            self.reactor.create_ripple(
                QPointF(
                    reactor_point.x(),
                    reactor_point.y()
                )
            )

        except Exception:

            pass

        self.hand_overlay.flash_click(
            QRectF(rect)
        )

        button_name = self._hud_button_name(
            selected_button
        )

        self.response_panel.set_response(
            f"GESTURE // HUD SELECT // {button_name.upper()}"
        )

        try:

            self.gesture_controller.pinch_click(
                button_name,
                self.current_mode
            )

        except Exception:

            pass

        selected_button.click()

        # The click may change the page; rebuild the target list.
        self._hud_button_cache = None


    # =====================================================
    # SIDEBAR
    # =====================================================

    def sidebar_buttons(self):

        # The sidebar is now the holographic nav rail.
        return self.holo_nav.button_list()


    def set_active_sidebar_button(
        self,
        active_button
    ):

        if active_button is None:

            # Pages without a nav node (Sports Nexus): clear highlight.
            self.holo_nav.set_active("")

            return

        self.holo_nav.set_active_button(
            active_button
        )


    def apply_default_button_style(
        self,
        button
    ):

        button.setStyleSheet(
            """
            QPushButton {

                background:
                    rgba(
                        0,
                        18,
                        10,
                        70
                    );

                color:
                    rgba(
                        185,
                        255,
                        210,
                        190
                    );

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        55
                    );

                border-radius:
                    8px;

                padding:
                    10px;

                text-align:
                    left;
            }
            """
        )


    def apply_hover_style(
        self,
        button
    ):

        button.setStyleSheet(
            """
            QPushButton {

                background:
                    rgba(
                        57,
                        255,
                        120,
                        75
                    );

                color:
                    #39ff78;

                border:
                    1px solid
                    rgba(
                        57,
                        255,
                        120,
                        240
                    );

                border-radius:
                    8px;

                padding:
                    10px;

                text-align:
                    left;
            }
            """
        )


    def reset_button_hover(self):

        # Legacy dwell-hover hook. Nav nodes animate their own hover.
        self.hovered_button = None
        self.hover_start_time = None


    # =====================================================
    # RESIZE
    # =====================================================

    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )


        self.update_layout()


    # =====================================================
    # LAYOUT
    # =====================================================

    def update_layout(self):

        width = (
            self.width()
        )


        height = (
            self.height()
        )


        self.reactor.setGeometry(
            0,
            0,
            width,
            height
        )


        status_width = (
            215
        )

        margin = 20

        rail_top = 12

        rail_height = 76

        content_top = (
            rail_top
            + rail_height
            + 12
        )

        # The projection bay takes the old sidebar column. On
        # narrow windows it folds away to give pages the room.
        bay_width = (
            240
            if width >= 1150
            else 0
        )


        self.status_panel.setGeometry(
            width
            - status_width
            - margin,
            65,
            status_width,
            height - 120
        )


        self.voice_input_badge.setGeometry(
            width
            - status_width
            - margin,
            height - 150,
            status_width,
            72
        )


        center_left = (
            margin
            + (bay_width + 22 if bay_width else 5)
        )


        center_right = (
            width
            - status_width
            - 45
        )


        center_width = (
            center_right
            - center_left
        )


        self.holo_nav.setGeometry(
            margin,
            rail_top,
            center_right - margin,
            rail_height
        )


        if bay_width:

            self.holo_projector.setGeometry(
                margin,
                content_top,
                bay_width,
                height - content_top - 30
            )

            self.holo_projector.show()

        else:

            self.holo_projector.hide()


        self.page_stack.setGeometry(
            center_left,
            content_top,
            center_width,
            height - 215 - content_top
        )


        self.response_panel.setGeometry(
            center_left,
            height - 205,
            center_width,
            105
        )


        self.command_bar.setGeometry(
            center_left,
            height - 95,
            center_width,
            65
        )


        self.sports_backdrop.setGeometry(
            0,
            0,
            width,
            height
        )

        if getattr(self, "_reactor_snapshot", None) is not None:

            self._reactor_snapshot.setGeometry(
                0,
                0,
                width,
                height
            )

        # Order: reactor (bottom) -> still snapshot -> sports backdrop
        # -> everything else.
        self.sports_backdrop.lower()

        if getattr(self, "_reactor_snapshot", None) is not None:

            self._reactor_snapshot.lower()

        self.reactor.lower()

        self.holo_projector.raise_()

        self.holo_nav.raise_()

        self.status_panel.raise_()

        self.voice_input_badge.raise_()

        self.page_stack.raise_()

        self.response_panel.raise_()

        self.command_bar.raise_()

        self.finger_cursor.raise_()


        self.hand_overlay.setGeometry(
            self.central_widget.rect()
        )

        self.transition_overlay.setGeometry(
            self.central_widget.rect()
        )

        self.hand_overlay.raise_()

        self.transition_overlay.raise_()

        self.warp_overlay.setGeometry(
            self.central_widget.rect()
        )

        self.warp_overlay.raise_()


        if hasattr(
            self,
            "security_alert_overlay"
        ):

            self.security_alert_overlay.setGeometry(
                self.central_widget.rect()
            )

            if self.security_alert_overlay.isVisible():

                self.security_alert_overlay.raise_()


        if hasattr(
            self,
            "security_findings_overlay"
        ):

            self.security_findings_overlay.setGeometry(
                self.central_widget.rect()
            )

            if self.security_findings_overlay.isVisible():
                self.security_findings_overlay.raise_()


        if hasattr(
            self,
            "auth_overlay"
        ):

            self.auth_overlay.setGeometry(
                self.central_widget.rect()
            )


            if self.auth_overlay.isVisible():

                self.auth_overlay.raise_()


    # =====================================================
    # CLOSE
    # =====================================================

    def closeEvent(
        self,
        event
    ):

        self.save_settings()


        try:

            self.ambience.stop(0.2)

        except Exception:

            pass


        try:

            self.auth_session.shutdown()

        except Exception:

            pass


        try:

            self.voice_listener.stop()

        except Exception:

            pass


        try:

            self.voice_engine.stop()

        except Exception:

            pass


        try:

            self.hand_tracker.stop()


            if (
                self.hand_thread
                .isRunning()
            ):

                self.hand_thread.wait(
                    2000
                )


        except Exception:

            pass


        if (
            self.ai_thread is not None
            and self.ai_thread.isRunning()
        ):

            self.ai_thread.quit()


            self.ai_thread.wait(
                1500
            )


        event.accept()