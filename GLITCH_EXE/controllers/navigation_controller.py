from models.events import NavigationEvent


class NavigationController:
    """
    Coordinates GLITCH page navigation.

    The controller decides where navigation goes, while the
    main window remains responsible for drawing the requested
    page on screen.
    """

    def __init__(
        self,
        main_window,
        event_bus=None
    ):

        self.main_window = main_window
        self.event_bus = event_bus


    def navigate(
        self,
        destination: str
    ):
        """
        Navigate GLITCH to a destination.

        Returns True when the page was successfully rendered.
        """

        destination = (
            destination
            .strip()
            .upper()
        )


        success = (
            self.main_window
            .show_page(
                destination
            )
        )


        if (
            success
            and self.event_bus is not None
        ):

            event = NavigationEvent(
                name="NAVIGATION_CHANGED",
                target=destination,
                source="NavigationController"
            )

            self.event_bus.publish(
                event
            )


        return success
