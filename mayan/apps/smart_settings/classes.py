import errno
import logging
import os
import re
from shutil import copyfile
import sys

import yaml

from django.apps import apps
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from mayan.apps.common.class_mixins import AppsModuleLoaderMixin
from mayan.apps.common.serialization import yaml_dump, yaml_load

from .exceptions import SettingsException, SettingsExceptionRevert
from .literals import (
    COMMAND_NAME_SETTINGS_REVERT, NAMESPACE_VERSION_INITIAL,
    SMART_SETTINGS_NAMESPACES_NAME
)

logger = logging.getLogger(name=__name__)


def read_configuration_file(filepath):
    try:
        with open(file=filepath) as file_object:
            file_object.seek(0, os.SEEK_END)
            if file_object.tell():
                file_object.seek(0)
                try:
                    return yaml_load(stream=file_object)
                except yaml.YAMLError as exception:
                    exit(
                        'Error loading configuration file: {}; {}'.format(
                            filepath, exception
                        )
                    )
    except IOError as exception:
        if exception.errno == errno.ENOENT:
            # No config file, return empty dictionary.
            return {}
        else:
            raise


class SettingCluster(AppsModuleLoaderMixin):
    _loader_module_name = 'settings'

    def __init__(self, name):
        self.configuration_file_cache = None
        self.name = name
        self.namespace_dict = {}
        self.setting_dict = {}

    def do_cache_invalidate(self):
        for namespace in self.namespace_dict.values():
            namespace.do_cache_invalidate()

        self.configuration_file_cache = None

    def do_configuration_file_revert(self):
        if not settings.COMMON_DISABLE_LOCAL_STORAGE:
            try:
                copyfile(
                    src=settings.CONFIGURATION_LAST_GOOD_FILEPATH,
                    dst=settings.CONFIGURATION_FILEPATH
                )
            except IOError as exception:
                if exception.errno == errno.ENOENT:
                    raise SettingsException(
                        'There is no last valid version to restore.'
                    ) from exception
                else:
                    raise
        else:
            logger.info(
                'Local storage is disabled, cannot revert not existing '
                'configuration.'
            )

    def do_configuration_file_save(self, path=None):
        if not settings.COMMON_DISABLE_LOCAL_STORAGE:
            if not path:
                path = settings.CONFIGURATION_FILEPATH

            try:
                with open(file=path, mode='w') as file_object:
                    file_object.write(
                        self.get_data_dump()
                    )
            except IOError as exception:
                if exception.errno == errno.ENOENT:
                    logger.warning(
                        'The path to the configuration file `%s` doesn\'t '
                        'exist. It is not possible to save the backup file.',
                        path
                    )
        else:
            logger.info(
                'Local storage is disabled, skip saving configuration.'
            )

    def do_last_known_good_save(self):
        # Don't write over the last good configuration if we are trying
        # to restore the last good configuration.
        if COMMAND_NAME_SETTINGS_REVERT not in sys.argv and not settings.CONFIGURATION_FILE_IGNORE:
            self.do_configuration_file_save(
                path=settings.CONFIGURATION_LAST_GOOD_FILEPATH
            )

    def do_namespace_add(self, **kwargs):
        setting_namespace = SettingNamespace(cluster=self, **kwargs)

        if setting_namespace.name in self.namespace_dict:
            raise SettingsException(
                'Setting namespace "%s" already exists in '
                'cluster.' % setting_namespace.name
            )

        self.namespace_dict[setting_namespace.name] = setting_namespace
        return setting_namespace

    def do_namespace_remove(self, name):
        setting_namespace = self.get_namespace(name=name)

        self.namespace_dict.pop(setting_namespace.name)

    def do_post_edit_function_call(self):
        ContentType = apps.get_model(
            app_label='contenttypes', model_name='ContentType'
        )

        for namespace in self.namespace_dict.values():
            namespace.do_post_edit_function_call()

        # Clear the content type cache to avoid the event system from trying
        # to use the same ID that were cached when the setting post edit
        # functions executed. This is because the settings execute before
        # the apps objects are created.
        ContentType.objects.clear_cache()

    def do_settings_updated_clear(self):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        queryset = UpdatedSetting.objects.all()

        try:
            queryset.delete()
        except (OperationalError, ProgrammingError):
            """
            Non fatal. Non initialized installation. Ignore exception.
            """

    def get_configuration_file_content(self):
        if settings.CONFIGURATION_FILE_IGNORE:
            return {}
        else:
            # Cache content the of the configuration file to speed up
            # initial boot up.
            if not self.configuration_file_cache:
                self.configuration_file_cache = read_configuration_file(
                    filepath=settings.CONFIGURATION_FILEPATH
                ) or {}
            return self.configuration_file_cache

    def get_data_dump(self, filter_term=None, namespace_name=None):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        dictionary = {}

        if not namespace_name:
            namespace_dictionary = {}
            for namespace in self.get_namespace_list():
                namespace_dictionary[namespace.name] = {
                    'version': namespace.version
                }

            dictionary[SMART_SETTINGS_NAMESPACES_NAME] = namespace_dictionary

        if namespace_name:
            namespace_list = (
                self.get_namespace(name=namespace_name),
            )
        else:
            namespace_list = self.get_namespace_list()

        for namespace in namespace_list:
            for setting in namespace.get_setting_list():
                # If a namespace is specified, filter the list by that
                # namespace otherwise return always True to include all
                # (or not None == True).
                if (filter_term and filter_term.lower() in setting.global_name.lower()) or not filter_term:
                    try:
                        updated_setting = UpdatedSetting.objects.get(
                            global_name=setting.global_name
                        )
                    except (OperationalError, ProgrammingError, UpdatedSetting.DoesNotExist):
                        expressed_value = Setting.express_promises(
                            value=setting.value
                        )
                        dictionary[setting.global_name] = expressed_value
                    else:
                        dictionary[setting.global_name] = updated_setting.value_new

        return yaml_dump(data=dictionary, default_flow_style=False)

    def get_is_changed(self):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        try:
            return UpdatedSetting.objects.exists()
        except (OperationalError, ProgrammingError):
            return False

    def get_namespace(self, name):
        return self.namespace_dict[name]

    def get_namespace_configuration(self, name):
        namespace_configuration_map = self.get_namespace_configuration_map()

        return namespace_configuration_map.get(
            name, {}
        )

    def get_namespace_configuration_map(self):
        configuration_file_content = self.get_configuration_file_content()

        return configuration_file_content.get(
            SMART_SETTINGS_NAMESPACES_NAME, {}
        )

    def get_namespace_list(self):
        return sorted(
            self.namespace_dict.values(), key=lambda x: x.label
        )

    def get_setting(self, global_name):
        return self.setting_dict[global_name]

    def get_setting_list(self):
        return self.setting_dict.values()


class SettingNamespace:
    def __init__(
        self, cluster, name, label, migration_class=None,
        version=NAMESPACE_VERSION_INITIAL
    ):
        self.cluster = cluster
        self.migration_class = migration_class
        self.name = name
        self.label = label
        self.setting_dict = {}
        self.version = version

    def __str__(self):
        return force_str(s=self.label)

    def do_cache_invalidate(self):
        for setting in self.setting_dict.values():
            setting.do_cache_invalidate()

    def do_post_edit_function_call(self):
        for setting in self.setting_dict.values():
            setting.do_post_edit_function_call()

    def do_migrate(self, setting):
        if self.migration_class:
            self.migration_class(namespace=self).do_migrate(setting=setting)

    def do_setting_add(self, **kwargs):
        setting = Setting(namespace=self, **kwargs)

        if setting.global_name in self.setting_dict:
            raise SettingsException(
                'Setting "%s" already exists in '
                'namespace.' % setting.global_name
            )

        self.setting_dict[setting.global_name] = setting
        self.cluster.setting_dict[setting.global_name] = setting

        return setting

    def do_setting_remove(self, global_name):
        setting = self.setting_dict.get(global_name)

        self.setting_dict.pop(setting.global_name)
        self.cluster.setting_dict.pop(setting.global_name)

        return setting

    def get_configuration_file_version(self):
        return self.cluster.get_namespace_configuration(name=self.name).get(
            'version', NAMESPACE_VERSION_INITIAL
        )

    def get_setting(self, global_name):
        return self.setting_dict[global_name]

    def get_setting_list(self):
        return sorted(
            self.setting_dict.values(), key=lambda x: x.global_name
        )


SettingNamespace.verbose_name = _(message='Settings namespace')


class SettingNamespaceMigration:
    @staticmethod
    def get_method_name(setting):
        return setting.global_name.lower()

    def __init__(self, namespace):
        self.namespace = namespace

    def do_migrate(self, setting):
        if self.namespace.get_configuration_file_version() != self.namespace.version:
            setting_method_name = SettingNamespaceMigration.get_method_name(
                setting=setting
            )

            # Get methods for this setting.
            pattern = r'{}_\d{{4}}'.format(setting_method_name)
            setting_methods = re.findall(
                pattern=pattern, string='\n'.join(
                    dir(self)
                )
            )

            # Get order of execution of setting methods.
            version_list = [
                method.replace(
                    '{}_'.format(setting_method_name), ''
                ) for method in setting_methods
            ]
            try:
                start = version_list.index(
                    self.namespace.get_configuration_file_version()
                )
            except ValueError:
                start = 0

            try:
                end = version_list.index(self.namespace.version)
            except ValueError:
                end = None

            value = setting.value_raw
            for version in version_list[start:end]:
                method = getattr(
                    self, self.get_method_name_full(
                        setting=setting, version=version
                    ), None
                )
                if method:
                    value = method(value=value)

            setting.value_raw = value

    def get_method_name_full(self, setting, version):
        return '{}_{}'.format(
            self.get_method_name(setting=setting), version
        )


class Setting:
    @staticmethod
    def deserialize_value(value):
        return yaml_load(stream=value)

    @staticmethod
    def express_promises(value):
        """
        Walk all the elements of a value and force promises to text.
        """
        if isinstance(value, (list, tuple)):
            return [
                Setting.express_promises(item) for item in value
            ]
        elif isinstance(value, Promise):
            return force_str(s=value)
        else:
            return value

    @staticmethod
    def serialize_value(value):
        result = yaml_dump(
            allow_unicode=True, data=Setting.express_promises(value=value),
            default_flow_style=False
        )
        # safe_dump returns bytestrings.
        # Disregard the last 3 dots that mark the end of the YAML document.
        if force_str(s=result).endswith('...\n'):
            result = result[:-4]

        return result

    def __init__(
        self, namespace, global_name, default, choices=None, help_text=None,
        is_path=False, post_edit_function=None, validation_function=None
    ):
        self.choices = choices
        self.default = default
        self.help_text = help_text
        self.environment_variable = False
        self.global_name = global_name
        self.loaded = False
        self.namespace = namespace
        self.post_edit_function = post_edit_function
        self.validation_function = validation_function
        self.value_raw_new = None

    def __str__(self):
        return str(self.global_name)

    def do_cache_invalidate(self):
        self.loaded = False

    def do_migrate(self):
        self.namespace.do_migrate(setting=self)

    def do_post_edit_function_call(self):
        if self.post_edit_function:
            try:
                self.post_edit_function(setting=self)
            except Exception as exception:
                raise SettingsException(
                    'Unable to execute setting post update function '
                    'for setting "{}". Verify the value of the setting or '
                    'rollback to the previous known working configuration '
                    'file.'.format(self.global_name)
                ) from exception

    def do_value_cache(self, global_name=None, default_override=None):
        global_name = global_name or self.global_name

        environment_value = os.environ.get(
            'MAYAN_{}'.format(global_name)
        )
        if environment_value:
            self.environment_variable = True
            try:
                self.value_raw = yaml_load(stream=environment_value)
            except yaml.YAMLError as exception:
                raise type(exception)(
                    'Error interpreting environment variable: {} with '
                    'value: {}; {}'.format(
                        global_name, environment_value, exception
                    )
                )
        else:
            try:
                # Try the config file.
                configuration_file_content = self.namespace.cluster.get_configuration_file_content()
                self.value_raw = configuration_file_content[global_name]
            except KeyError:
                try:
                    # Try the Django settings variable.
                    self.value_raw = getattr(
                        settings, global_name
                    )
                except AttributeError:
                    # Finally set to the default value.
                    if default_override:
                        self.value_raw = default_override
                    else:
                        self.value_raw = self.default
            else:
                # Found in the config file, try to migrate the value.
                self.do_migrate()

        if self.validation_function:
            self.value_raw = self.validation_function(
                raw_value=self.value_raw, setting=self
            )

        self.value_yaml = Setting.serialize_value(value=self.value_raw)
        self.loaded = True

    def get_value_choices(self):
        return self.choices

    get_value_choices.short_description = _(message='Choices')
    get_value_choices.help_text = _(
        'Possible values allowed for this setting.'
    )

    def do_value_raw_set(self, raw_value):
        self.value = Setting.serialize_value(value=raw_value)
        self.loaded = True

    def do_value_raw_validate(self, raw_value):
        if self.validation_function:
            return self.validation_function(
                raw_value=raw_value, setting=self
            )

    def do_value_revert(self):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        if not self.get_has_value_new():
            raise SettingsExceptionRevert(
                _(
                    'Cannot revert setting. Setting value has not been '
                    'updated.'
                )
            )

        updated_setting = UpdatedSetting.objects.get(
            global_name=self.global_name
        )

        self.do_value_set(value=updated_setting.value_old)
        updated_setting.delete()

    def do_value_set(self, value):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        raw_value = Setting.deserialize_value(value=value)

        self.value_raw_new = raw_value

        if self.value_raw_new != self.value:
            updated_setting, created = UpdatedSetting.objects.update_or_create(
                global_name=self.global_name, defaults={
                    'value_new': self.value_raw_new,
                    'value_old': self.value
                }
            )
        else:
            queryset = UpdatedSetting.objects.filter(
                global_name=self.global_name
            )
            queryset.delete()

    def get_default(self):
        return Setting.serialize_value(value=self.default)

    get_default.short_description = _(message='Default')

    def get_has_value_new(self):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        queryset = UpdatedSetting.objects.filter(
            global_name=self.global_name
        )

        return queryset.exists()

    get_has_value_new.short_description = _(message='Modified')
    get_has_value_new.help_text = _(
        'The value of this setting being modified since the last restart.'
    )

    def get_is_overridden(self):
        return self.environment_variable

    get_is_overridden.short_description = _(message='Overridden')
    get_is_overridden.help_text = _(
        'The value of the setting is being overridden by an environment '
        'variable.'
    )

    def get_value_current(self):
        UpdatedSetting = apps.get_model(
            app_label='smart_settings', model_name='UpdatedSetting'
        )

        has_value_new = self.get_has_value_new()

        if has_value_new:
            updated_setting = UpdatedSetting.objects.get(
                global_name=self.global_name
            )

            return Setting.serialize_value(value=updated_setting.value_new)
        else:
            return self.serialized_value

    @property
    def pk(self):
        """
        Compatibility property for views that expect model instances.
        """
        return self.global_name

    @property
    def serialized_value(self):
        """
        YAML serialize value of the setting.
        Used for UI display.
        """
        if not self.loaded:
            self.do_value_cache()

        return self.value_yaml

    @property
    def value(self):
        if not self.loaded:
            self.do_value_cache()

        return self.value_raw

    @value.setter
    def value(self, value):
        # value is in YAML format.
        self.value_yaml = value
        self.value_raw = Setting.deserialize_value(value=self.value_yaml)
