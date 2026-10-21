import subprocess

from services.base_service import BaseService


class SystemPowerService(BaseService):
    """
    Low-level Windows power operations.

    IMPORTANT:
    This service performs commands only.
    It does NOT decide whether an action is safe or confirmed.
    Confirmation belongs to PowerController.
    """

    def __init__(self, event_bus=None):
        super().__init__(event_bus)


    def shutdown(self):
        """
        Shut Windows down immediately.
        """

        subprocess.Popen(
            [
                "shutdown",
                "/s",
                "/t",
                "0",
            ],
            shell=False,
        )

        return True


    def restart(self):
        """
        Restart Windows immediately.
        """

        subprocess.Popen(
            [
                "shutdown",
                "/r",
                "/t",
                "0",
            ],
            shell=False,
        )

        return True


    def cancel_pending_shutdown(self):
        """
        Cancel a Windows shutdown/restart countdown if one
        exists.
        """

        result = subprocess.run(
            [
                "shutdown",
                "/a",
            ],
            shell=False,
            capture_output=True,
            text=True,
        )

        return (
            result.returncode == 0
        )

