import logging
from pathlib import Path

import sh

from django.utils.translation import gettext_lazy as _

from mayan.apps.file_metadata.classes import FileMetadataDriver
from mayan.apps.file_metadata.settings import setting_drivers_arguments
from mayan.apps.storage.utils import TemporaryDirectory

from .literals import DEFAULT_PATH_CLAMSCAN

__all__ = ('ClamScanDriver',)
logger = logging.getLogger(name=__name__)


class ClamScanDriver(FileMetadataDriver):
    description = _(message='Command line anti-virus scanner.')
    label = _(message='ClamScan')
    internal_name = 'clamscan'
    mime_type_list = ('*',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.read_settings()

        if self.auto_initialize:
            try:
                self.command_clamscan = sh.Command(path=self.path_clamscan)
            except sh.CommandNotFound:
                self.command_clamscan = None

    def _process(self, document_file):
        if self.command_clamscan:
            with TemporaryDirectory() as temporary_folder:
                path_temporary_file = Path(
                    temporary_folder, Path(document_file.filename).name
                )

                with path_temporary_file.open(mode='xb') as temporary_fileobject:
                    document_file.save_to_file(
                        file_object=temporary_fileobject
                    )
                    temporary_fileobject.seek(0)
                    try:
                        output = self.command_clamscan(
                            temporary_fileobject.name, _ok_code=(0, 1)
                        )
                    except sh.ErrorReturnCode_2:
                        # Some error(s) occurred.
                        raise
                    else:
                        # This code path is executed is there is no exception
                        # (error code 0) or error code 1 (virus found).
                        result = {}
                        start_of_data = False
                        for line in output.split('\n'):
                            if start_of_data:
                                parts = line.split(':', 1)
                                if len(parts) > 1:
                                    key = parts[0]
                                    value = parts[1]
                                    value = value.strip()

                                    result[key] = value
                            if 'SCAN SUMMARY' in line:
                                start_of_data = True

                        return result
        else:
            logger.error(
                'clamscan binary not found, not processing document '
                'file: %s', document_file
            )

    def read_settings(self):
        self.path_clamscan = setting_drivers_arguments.value.get(
            'clamscan_driver', {}
        ).get('path_clamscan', DEFAULT_PATH_CLAMSCAN)
