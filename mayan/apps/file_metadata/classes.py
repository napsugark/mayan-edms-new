import logging

from django.apps import apps
from django.db.utils import OperationalError, ProgrammingError
from django.utils.functional import classproperty

from mayan.apps.common.class_mixins import AppsModuleLoaderMixin
from mayan.apps.common.utils import (
    convert_to_internal_name, deduplicate_dictionary_values,
    get_class_full_name
)

from .exceptions import FileMetadataError

logger = logging.getLogger(name=__name__)


class FileMetadataDriverCollection:
    _driver_enabled_list = []
    _driver_to_mime_type_dict = {}
    _mime_type_to_driver_dict = {}

    @classmethod
    def do_driver_disable(cls, driver):
        if driver in cls._driver_to_mime_type_dict:
            cls._driver_enabled_list.remove(driver)

    @classmethod
    def do_driver_disable_all(cls):
        cls._driver_enabled_list = []

    @classmethod
    def do_driver_enable(cls, driver):
        if driver in cls._driver_to_mime_type_dict:
            if driver not in cls._driver_enabled_list:
                cls._driver_enabled_list.append(driver)

    @classmethod
    def do_driver_register(cls, klass):
        if klass in cls._driver_to_mime_type_dict:
            raise FileMetadataError(
                'Driver "{}" is already registered.'.format(klass)
            )

        cls._driver_to_mime_type_dict[klass] = klass.mime_type_list

        for mime_type in klass.mime_type_list:
            cls._mime_type_to_driver_dict.setdefault(
                mime_type, []
            ).append(klass)

        klass.dotted_path = get_class_full_name(klass=klass)

        cls.do_driver_enable(driver=klass)

    @classmethod
    def get_all(cls, sorted=False):
        result = set()
        for mime_type, drivers in cls._mime_type_to_driver_dict.items():
            result.update(
                list(drivers)
            )

        result = list(result)

        if sorted:
            result.sort(key=lambda driver: driver.label)

        return result

    @classmethod
    def get_driver_for_mime_type(cls, mime_type):
        driver_class_list = cls._mime_type_to_driver_dict.get(
            mime_type, ()
        )
        # Add wildcard drivers, drivers meant to be executed for all MIME
        # types.
        driver_class_list += tuple(
            cls._mime_type_to_driver_dict.get(
                '*', ()
            )
        )

        result = [
            driver_class for driver_class in driver_class_list if driver_class in cls._driver_enabled_list
        ]

        return result


class FileMetadataDriverMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(
            mcs, name, bases, attrs
        )

        if not new_class.__module__ == __name__:
            FileMetadataDriverCollection.do_driver_register(klass=new_class)

        return new_class


class FileMetadataDriver(
    AppsModuleLoaderMixin, metaclass=FileMetadataDriverMetaclass
):
    _loader_module_name = 'drivers'
    description = ''
    internal_name = None
    label = None
    mime_type_list = ()

    @classproperty
    def collection(cls):
        if cls != FileMetadataDriver:
            raise AttributeError(
                'This method is only available to the parent class.'
            )
        return FileMetadataDriverCollection

    @classmethod
    def do_model_instance_populate(cls):
        StoredDriver = apps.get_model(
            app_label='file_metadata', model_name='StoredDriver'
        )
        model_instance, created = StoredDriver.objects.get_or_create(
            driver_path=cls.dotted_path, defaults={
                'internal_name': cls.internal_name
            }
        )
        cls.model_instance = model_instance

    @classmethod
    def get_mime_type_list_display(cls):
        return ', '.join(cls.mime_type_list)

    @classmethod
    def post_load_modules(cls):
        StoredDriver = apps.get_model(
            app_label='file_metadata', model_name='StoredDriver'
        )

        try:
            """
            Check is the table is ready.
            If not, this will log an error similar to this:
            2023-12-12 09:12:46.985 UTC [79] ERROR:  relation "file_metadata_storeddriver" does not exist at character 22
            2023-12-12 09:12:46.985 UTC [79] STATEMENT:  SELECT 1 AS "a" FROM "file_metadata_storeddriver" LIMIT 1
            This error is expected and should be ignored.
            """
            StoredDriver.objects.exists()
        except (OperationalError, ProgrammingError):
            """
            This error is expected when trying to initialize the
            stored permissions during the initial creation of the
            database. Can be safely ignored under that situation.
            """
        else:
            for driver in cls.collection.get_all():
                driver.do_model_instance_populate()

    def __init__(self, auto_initialize=True, **kwargs):
        self.auto_initialize = auto_initialize

    def initialize(self):
        """
        Driver specific initialization code.
        """

    def process(self, document_file):
        logger.debug('Starting processing document file: %s', document_file)

        FileMetadataEntry = apps.get_model(
            app_label='file_metadata', model_name='FileMetadataEntry'
        )

        file_metadata_dictionary = self._process(document_file=document_file) or {}

        internal_name_dictionary = {}
        for key in file_metadata_dictionary.keys():
            internal_name_dictionary[key] = convert_to_internal_name(
                value=key
            )

        internal_name_dictionary_deduplicated = deduplicate_dictionary_values(
            dictionary=internal_name_dictionary
        )

        queryset_document_file_metadata = self.model_instance.driver_entries.filter(
            document_file=document_file
        )
        queryset_document_file_metadata.delete()

        document_file_driver_entry = self.model_instance.driver_entries.create(
            document_file=document_file
        )

        coroutine = FileMetadataEntry.objects.create_bulk()
        next(coroutine)

        for key, value in file_metadata_dictionary.items():
            internal_name = internal_name_dictionary_deduplicated[key]
            coroutine.send(
                {
                    'document_file_driver_entry': document_file_driver_entry,
                    'internal_name': internal_name, 'key': key, 'value': value
                }
            )

        coroutine.close()

    def _process(self, document_file):
        raise NotImplementedError(
            'Your %s class has not defined the required _process() '
            'method.' % self.__class__.__name__
        )
