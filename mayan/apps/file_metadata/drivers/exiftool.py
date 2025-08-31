import json
import logging
from pathlib import Path

import sh

from django.utils.translation import gettext_lazy as _

from mayan.apps.storage.utils import TemporaryDirectory

from ..classes import FileMetadataDriver
from ..settings import setting_drivers_arguments

from .literals import DEFAULT_EXIF_PATH

logger = logging.getLogger(name=__name__)


class EXIFToolDriver(FileMetadataDriver):
    description = _(message='Read meta information stored in files.')
    internal_name = 'exiftool'
    label = _(message='EXIF Tool')
    mime_type_list = ('*',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.read_settings()

        if self.auto_initialize:
            try:
                self.command_exiftool = sh.Command(path=self.exiftool_path)
            except sh.CommandNotFound:
                self.command_exiftool = None
            else:
                self.command_exiftool = self.command_exiftool.bake('-j')

    def _process(self, document_file):
        if self.command_exiftool:
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
                        output = self.command_exiftool(
                            temporary_fileobject.name
                        )
                    except sh.ErrorReturnCode_1 as exception:
                        result = json.loads(s=exception.stdout)[0]
                        if result.get('Error', '') == 'Unknown file type':
                            # Not a fatal error.
                            return result
                    else:
                        return json.loads(s=output)[0]
        else:
            logger.error(
                'EXIFTool binary not found, not processing document '
                'file: %s', document_file
            )

    def read_settings(self):
        self.exiftool_path = setting_drivers_arguments.value.get(
            'exif_driver', {}
        ).get('exiftool_path', DEFAULT_EXIF_PATH)
