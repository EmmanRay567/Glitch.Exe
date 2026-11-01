from models.security_state import SecurityState

from services.file_scanner_service import (
    FileScannerService
)

from services.quarantine_service import (
    QuarantineService
)


class SecurityEngine:
    """
    Facade for GLITCH Security Engine.

    Background scanning may scan files without updating shared
    state one-by-one, then commit the whole batch at once.
    """

    def __init__(
        self,
        file_scanner=None,
        quarantine_service=None
    ):

        self.file_scanner = (
            file_scanner
            or FileScannerService()
        )

        self.quarantine_service = (
            quarantine_service
            or QuarantineService()
        )

        self.state = (
            SecurityState()
        )

        self.state.quarantined_files = len(
            self.quarantine_service
            .list_items()
        )


    def scan_file(
        self,
        file_path,
        update_state=True
    ):

        result = (
            self.file_scanner
            .scan_file(
                file_path
            )
        )


        if update_state:

            self.state.update_from_results(
                file_path,
                [result]
            )


        return result


    def scan_directory(
        self,
        directory_path,
        recursive=True,
        max_files=5000
    ):

        results = (
            self.file_scanner
            .scan_directory(
                directory_path,
                recursive=recursive,
                max_files=max_files,
                exclude_paths=[
                    self.quarantine_service
                    .quarantine_directory
                ]
            )
        )


        self.state.update_from_results(
            directory_path,
            results
        )


        return results


    def record_background_results(
        self,
        target,
        results
    ):

        results = list(
            results
        )

        if not results:
            return


        self.state.update_from_results(
            target,
            results
        )


    def quarantine(
        self,
        scan_result
    ):

        metadata = (
            self.quarantine_service
            .quarantine_file(
                scan_result.path,
                scan_result
            )
        )


        self.state.quarantined_files = len(
            self.quarantine_service
            .list_items()
        )


        return metadata


    def list_quarantine(
        self
    ):

        return (
            self.quarantine_service
            .list_items()
        )


    def restore_quarantine_item(
        self,
        item_id
    ):

        path = (
            self.quarantine_service
            .restore(
                item_id
            )
        )


        self.state.quarantined_files = len(
            self.quarantine_service
            .list_items()
        )


        return path


    def permanently_delete_quarantine_item(
        self,
        item_id
    ):

        result = (
            self.quarantine_service
            .permanently_delete(
                item_id
            )
        )


        self.state.quarantined_files = len(
            self.quarantine_service
            .list_items()
        )


        return result
