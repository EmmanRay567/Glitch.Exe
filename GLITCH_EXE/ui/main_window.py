import os
import json
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
)

from PySide6.QtCore import (
    QThread,
    Signal,
    QObject,
    QTimer,
    QPointF,
    QRect,
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
)

from PySide6.QtMultimedia import (
    QSoundEffect,
)


from core.assistant import GlitchAssistant
from core.event_bus import EventBus
from core.command_router import CommandRouter
from core.service_container import ServiceContainer
from models.intent import InteractionIntent
from commands.navigation_commands import NavigationCommand
from controllers.navigation_controller import NavigationController
from controllers.gesture_controller import GestureController
from controllers.interaction_controller import InteractionController
from controllers.voice_controller import VoiceController
from controllers.power_controller import PowerController
from services.application_service import ApplicationService
from services.system_monitoring_service import SystemMonitoringService
from services.system_power_service import SystemPowerService

from voice.voice_engine import VoiceEngine
from voice.voice_listener import VoiceListener

from gestures.hand_tracker import (
    HandTracker,
    HandTrackingThread,
)

from ui.reactor_widget import ReactorWidget
from ui.sidebar import Sidebar
from ui.status_panel import StatusPanel
from ui.command_bar import CommandBar
from ui.response_panel import ResponsePanel

# NEW
from ui.system_matrix_widget import SystemMatrixWidget


# =========================================================
# AI WORKER
# =========================================================

class AIWorker(QObject):

    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        assistant,
        message,
        mode="CHAT"
    ):

        super().__init__()

        self.assistant = assistant
        self.message = message
        self.mode = mode


    def run(self):

        try:

            if self.mode == "SEARCH":

                response = (
                    self.assistant
                    .search_web(
                        self.message
                    )
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
        }


        self.load_settings()


        self.voice_enabled = (
            self.settings_data[
                "voice_enabled"
            ]
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


        # =================================================
        # SIDEBAR
        # =================================================

        self.sidebar = (
            Sidebar(
                self.central_widget
            )
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


        for page in [

            self.home_page,

            self.system_matrix_page,

            self.chat_page,

            self.create_page_widget,

            self.search_page,

            self.code_page,

            self.apps_page,

            self.settings_page,

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
        # SIDEBAR CONNECTIONS
        # =================================================

        self.sidebar.home_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "HOME",
                    "MOUSE"
                )
        )


        self.sidebar.chat_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "CHAT",
                    "MOUSE"
                )
        )


        self.sidebar.create_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "CREATE",
                    "MOUSE"
                )
        )


        self.sidebar.search_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "SEARCH",
                    "MOUSE"
                )
        )


        self.sidebar.code_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "CODE",
                    "MOUSE"
                )
        )


        self.sidebar.apps_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "APPS",
                    "MOUSE"
                )
        )


        self.sidebar.settings_button.clicked.connect(
            lambda checked=False:
                self.navigate_with_intent(
                    "SETTINGS",
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


        self.voice_engine.voice_error.connect(
            self.handle_voice_error
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

        self.hand_tracker.finger_moved.connect(
            self.handle_finger_move
        )


        self.hand_tracker.pinch_detected.connect(
            self.handle_proximity_touch
        )


        # NEW SWIPE CONNECTIONS
        self.hand_tracker.swipe_left.connect(
            self.handle_swipe_left
        )


        self.hand_tracker.swipe_right.connect(
            self.handle_swipe_right
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


        self.response_panel.set_response(
            "GLITCH.EXE ONLINE // SYSTEMS NOMINAL"
        )


        self.update_layout()
        self.update_system_stats()


        self.handle_interaction_processed(
            None
        )


        # =================================================
        # STARTUP
        # =================================================

        QTimer.singleShot(
            500,
            self.startup_greeting
        )


        QTimer.singleShot(
            1500,
            self.start_hand_tracking
        )


        QTimer.singleShot(
            3000,
            self.start_voice_listener
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
    # VOICE COMMAND PROCESSOR
    # =====================================================

    def handle_voice_command(
        self,
        transcript
    ):

        if self.voice_output_active:
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
        # WAKE WORD
        # =================================================

        if not command.startswith(
            "glitch"
        ):

            QTimer.singleShot(
                1200,
                lambda:
                    self.set_voice_input_status(
                        "LISTENING"
                    )
            )

            return


        command = (
            command[
                len("glitch"):
            ]
            .strip(
                " ,.!?:;-"
            )
        )


        if not command:
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

        self.response_panel.set_response(
            text
        )


        if self.voice_enabled:

            self.voice_engine.speak(
                text
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


        self.ai_worker = (
            AIWorker(
                self.assistant,
                message,
                mode
            )
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

        if not message:
            return


        command = (
            message
            .strip()
            .lower()
        )


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
        self.start_ai_request(
            message,
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


        if mode == "CHAT":

            self.chat_history.append(
                f"\nGLITCH > {response}\n"
            )


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


        if self.voice_enabled:

            self.voice_engine.speak(
                response
            )


    def handle_ai_error(
        self,
        error
    ):

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

    def animate_page(
        self,
        page
    ):

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
                self.sidebar.home_button,
                "HOME",
                0.90,
                16
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


        self.response_panel.set_response(
            response
        )


        self.set_active_sidebar_button(
            active_button
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


    # =====================================================
    # SWIPE CONTROL
    # =====================================================

    def handle_swipe_left(self):

        success = (
            self.gesture_controller
            .swipe_left(
                self.current_mode
            )
        )


        if success:

            self.response_panel.set_response(
                "GESTURE // SWIPE LEFT DETECTED"
            )


    def handle_swipe_right(self):

        success = (
            self.gesture_controller
            .swipe_right(
                self.current_mode
            )
        )


        if success:

            self.response_panel.set_response(
                "GESTURE // SWIPE RIGHT DETECTED"
            )


    # =====================================================
    # STARTUP
    # =====================================================

    def startup_greeting(self):

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


        self.set_voice_input_status(
            "PAUSED"
        )


        try:

            self.voice_listener.stop()

        except Exception:

            pass


    def handle_voice_finished(self):

        self.voice_output_active = (
            False
        )


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

        if not self.hand_thread.isRunning():

            self.status_panel.set_gesture_status(
                "STARTING"
            )


            self.hand_thread.start()


    def handle_tracking_started(self):

        self.status_panel.set_gesture_status(
            "TRACKING"
        )


        self.finger_cursor.show()


    def handle_tracking_stopped(self):

        self.status_panel.set_gesture_status(
            "OFFLINE"
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

        window_x = (
            normalized_x
            * self.central_widget.width()
        )


        window_y = (
            normalized_y
            * self.central_widget.height()
        )


        self.finger_x = (
            window_x
        )


        self.finger_y = (
            window_y
        )


        self.finger_cursor.move(
            int(
                window_x
                - self.finger_cursor.width()
                / 2
            ),
            int(
                window_y
                - self.finger_cursor.height()
                / 2
            )
        )


        self.finger_cursor.show()

        self.finger_cursor.raise_()


        # =============================================
        # SYSTEM MATRIX
        #
        # No dwell-click behavior here.
        # Finger movement is used primarily for swipe.
        # =============================================

        if self.current_mode == "SYSTEM_MATRIX":

            self.reset_button_hover()

            return


        detected_button = None


        for button in (
            self.sidebar_buttons()
        ):

            top_left = button.mapTo(
                self.central_widget,
                button.rect().topLeft()
            )


            button_rect = QRect(
                top_left,
                button.size()
            )


            if button_rect.contains(
                int(window_x),
                int(window_y)
            ):

                detected_button = (
                    button
                )

                break


        if detected_button:

            if (
                detected_button
                != self.hovered_button
            ):

                self.reset_button_hover()


                self.hovered_button = (
                    detected_button
                )


                self.hover_start_time = (
                    self.current_milliseconds()
                )


                self.apply_hover_style(
                    detected_button
                )


            else:

                if (
                    self.hover_start_time
                    is None
                ):

                    return


                elapsed = (
                    self.current_milliseconds()
                    - self.hover_start_time
                )


                if elapsed >= (
                    self.button_dwell_ms
                ):

                    detected_button.click()


                    self.hover_start_time = (
                        self.current_milliseconds()
                        + 999999
                    )


        else:

            self.reset_button_hover()


    # =====================================================
    # PROXIMITY RIPPLE
    # =====================================================

    def handle_proximity_touch(
        self,
        normalized_x,
        normalized_y
    ):

        x = (
            normalized_x
            * self.reactor.width()
        )


        y = (
            normalized_y
            * self.reactor.height()
        )


        self.reactor.create_ripple(
            QPointF(
                x,
                y
            )
        )


    # =====================================================
    # SIDEBAR
    # =====================================================

    def sidebar_buttons(self):

        return [

            self.sidebar.home_button,

            self.sidebar.chat_button,

            self.sidebar.create_button,

            self.sidebar.search_button,

            self.sidebar.code_button,

            self.sidebar.apps_button,

            self.sidebar.settings_button,
        ]


    def set_active_sidebar_button(
        self,
        active_button
    ):

        for button in (
            self.sidebar_buttons()
        ):

            if (
                button
                == active_button
            ):

                button.setStyleSheet(
                    """
                    QPushButton {

                        background:
                            rgba(
                                57,
                                255,
                                120,
                                45
                            );

                        color:
                            #39ff78;

                        border:
                            1px solid
                            rgba(
                                57,
                                255,
                                120,
                                210
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


            else:

                self.apply_default_button_style(
                    button
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

        if self.hovered_button:

            active_map = {

                "HOME":
                    self.sidebar.home_button,

                "SYSTEM_MATRIX":
                    self.sidebar.home_button,

                "CHAT":
                    self.sidebar.chat_button,

                "CREATE":
                    self.sidebar.create_button,

                "SEARCH":
                    self.sidebar.search_button,

                "CODE":
                    self.sidebar.code_button,

                "APPS":
                    self.sidebar.apps_button,

                "SETTINGS":
                    self.sidebar.settings_button,
            }


            active = (
                active_map.get(
                    self.current_mode
                )
            )


            if (
                self.hovered_button
                == active
            ):

                self.set_active_sidebar_button(
                    active
                )


            else:

                self.apply_default_button_style(
                    self.hovered_button
                )


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


        sidebar_width = (
            175
        )


        status_width = (
            215
        )


        self.sidebar.setGeometry(
            25,
            65,
            sidebar_width,
            height - 120
        )


        self.status_panel.setGeometry(
            width
            - status_width
            - 20,
            65,
            status_width,
            height - 120
        )


        self.voice_input_badge.setGeometry(
            width
            - status_width
            - 20,
            height - 150,
            status_width,
            72
        )


        center_left = (
            sidebar_width
            + 50
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


        self.page_stack.setGeometry(
            center_left,
            65,
            center_width,
            height - 280
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


        self.reactor.lower()

        self.sidebar.raise_()

        self.status_panel.raise_()

        self.voice_input_badge.raise_()

        self.page_stack.raise_()

        self.response_panel.raise_()

        self.command_bar.raise_()

        self.finger_cursor.raise_()


    # =====================================================
    # CLOSE
    # =====================================================

    def closeEvent(
        self,
        event
    ):

        self.save_settings()


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