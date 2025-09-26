import os
from pathlib import Path

from django.conf import settings
from django.template import loader
from django.template.base import Template
from django.template.context import Context
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from mayan.apps.backends.classes import BaseBackend
from mayan.apps.common.serialization import yaml_dump, yaml_load
from mayan.apps.task_manager.classes import Worker
from mayan.settings.literals import (
    DEFAULT_DATABASE_NAME, DEFAULT_DATABASE_PASSWORD, DEFAULT_DATABASE_USER,
    DEFAULT_DIRECTORY_INSTALLATION, DEFAULT_OS_USERNAME,
    DEFAULT_USER_SETTINGS_FOLDER, DOCKER_CLI_IMAGE_VERSION,
    DOCKER_DIND_IMAGE_VERSION, DOCKER_LINUX_IMAGE_VERSION,
    DOCKER_MYSQL_IMAGE_VERSION, DOCKER_POSTGRESQL_IMAGE_NAME,
    DOCKER_POSTGRESQL_IMAGE_TAG, GITLAB_CI_BRANCH_BUILDS_DOCKER,
    GITLAB_CI_BRANCH_BUILDS_DOCUMENTATION, GITLAB_CI_BRANCH_BUILDS_PYTHON,
    GITLAB_CI_BRANCH_DEPLOYMENTS_DEMO, GITLAB_CI_BRANCH_DEPLOYMENTS_STAGING,
    GITLAB_CI_BRANCH_RELEASES_ALL_MAJOR, GITLAB_CI_BRANCH_RELEASES_ALL_MINOR,
    GITLAB_CI_BRANCH_RELEASES_DOCKER_MAJOR,
    GITLAB_CI_BRANCH_RELEASES_DOCKER_MINOR,
    GITLAB_CI_BRANCH_RELEASES_DOCUMENTATION,
    GITLAB_CI_BRANCH_RELEASES_NIGHTLY, GITLAB_CI_BRANCH_RELEASES_PYTHON_MAJOR,
    GITLAB_CI_BRANCH_RELEASES_PYTHON_MINOR, GITLAB_CI_BRANCH_RELEASES_STAGING,
    GITLAB_CI_BRANCH_RELEASES_TESTING, GITLAB_CI_BRANCH_TESTS_ALL,
    GITLAB_CI_BRANCH_TESTS_DOCKER, GITLAB_CI_BRANCH_TESTS_PYTHON_ALL,
    GITLAB_CI_BRANCH_TESTS_PYTHON_BASE, GITLAB_CI_BRANCH_TESTS_PYTHON_UPGRADE,
    GITLAB_CI_BRANCH_TRY_STAGING, GUNICORN_LIMIT_REQUEST_LINE,
    GUNICORN_MAX_REQUESTS, GUNICORN_REQUESTS_JITTER, GUNICORN_TIMEOUT,
    GUNICORN_WORKER_CLASS, GUNICORN_WORKERS
)


class Variable:
    def __init__(self, name, default, environment_name):
        self.name = name
        self.default = default
        self.environment_name = environment_name

    def _get_value(self):
        return os.environ.get(self.environment_name, self.default)

    def get_value(self):
        return mark_safe(
            s=self._get_value()
        )


class YAMLVariable(Variable):
    def _get_value(self):
        value = os.environ.get(self.environment_name)
        if value:
            value = yaml_load(stream=value)
        else:
            value = self.default

        return yaml_dump(
            data=value, allow_unicode=True, default_flow_style=True,
            width=999
        ).replace('...\n', '').replace('\n', '')


class PlatformTemplate(BaseBackend):
    _backend_identifier = 'name'
    _loader_module_name = 'platform_templates'
    context = {}
    context_defaults = {}
    label = None
    name = None
    settings = None
    template_name = None
    template_string = None
    variables = None

    def __str__(self):
        label = self.get_label()
        return str(label)

    def get_context(self):
        return self.context

    def get_context_defaults(self):
        return self.context_defaults

    def get_label(self):
        return self.label or self.name

    def get_settings_context(self):
        result = {}
        for setting in self.settings or ():
            if setting.value:
                result[setting.global_name] = setting.value

        return result

    def get_template_name(self):
        return self.template_name or 'platform/{}.tmpl'.format(self.name)

    def get_variables_context(self):
        result = {}
        for variable in self.variables or ():
            result[variable.name] = variable.get_value()

        return result

    def render(self, context_string=None):
        """
        context_string allows the management command to pass context to this
        method as a JSON string
        """
        context = {}

        context.update(
            self.get_context_defaults()
        )
        context.update(
            self.get_settings_context()
        )
        context.update(
            self.get_variables_context()
        )
        # get_context goes last to server as the override.
        context.update(
            self.get_context()
        )

        if context_string:
            context.update(
                yaml_load(stream=context_string)
            )

        if self.template_string:
            template = Template(template_string=self.template_string)
            return template.render(
                context=Context(dict_=context)
            )
        else:
            return loader.render_to_string(
                context=context, template_name=self.get_template_name()
            )


class PlatformTemplateGitLabCI(PlatformTemplate):
    label = _(message='Template that generates a GitLab CI config file.')
    name = 'gitlab-ci'

    def __init__(self):
        self.variables = (
            Variable(
                name='DEFAULT_DATABASE_NAME',
                default=DEFAULT_DATABASE_NAME,
                environment_name='MAYAN_DEFAULT_DATABASE_NAME'
            ),
            Variable(
                name='DEFAULT_DATABASE_PASSWORD',
                default=DEFAULT_DATABASE_PASSWORD,
                environment_name='MAYAN_DEFAULT_DATABASE_PASSWORD'
            ),
            Variable(
                name='DEFAULT_DATABASE_USER',
                default=DEFAULT_DATABASE_USER,
                environment_name='MAYAN_DEFAULT_DATABASE_USER'
            ),
            Variable(
                name='DOCKER_CLI_IMAGE_VERSION',
                default=DOCKER_CLI_IMAGE_VERSION,
                environment_name='MAYAN_DOCKER_CLI_IMAGE_VERSION'
            ),
            Variable(
                name='DOCKER_DIND_IMAGE_VERSION',
                default=DOCKER_DIND_IMAGE_VERSION,
                environment_name='MAYAN_DOCKER_DIND_IMAGE_VERSION'
            ),
            Variable(
                name='DOCKER_LINUX_IMAGE_VERSION',
                default=DOCKER_LINUX_IMAGE_VERSION,
                environment_name='MAYAN_DOCKER_LINUX_IMAGE_VERSION'
            ),
            Variable(
                name='DOCKER_MYSQL_IMAGE_VERSION',
                default=DOCKER_MYSQL_IMAGE_VERSION,
                environment_name='MAYAN_DOCKER_MYSQL_IMAGE_VERSION'
            ),
            Variable(
                name='DOCKER_POSTGRESQL_IMAGE_NAME',
                default=DOCKER_POSTGRESQL_IMAGE_NAME,
                environment_name='MAYAN_DOCKER_POSTGRESQL_IMAGE_NAME'
            ),
            Variable(
                name='DOCKER_POSTGRESQL_IMAGE_TAG',
                default=DOCKER_POSTGRESQL_IMAGE_TAG,
                environment_name='MAYAN_DOCKER_POSTGRESQL_IMAGE_TAG'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_BUILDS_DOCKER',
                default=GITLAB_CI_BRANCH_BUILDS_DOCKER,
                environment_name='MAYAN_GITLAB_CI_BRANCH_BUILDS_DOCKER'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_BUILDS_DOCUMENTATION',
                default=GITLAB_CI_BRANCH_BUILDS_DOCUMENTATION,
                environment_name='MAYAN_GITLAB_CI_BRANCH_BUILDS_DOCUMENTATION'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_BUILDS_PYTHON',
                default=GITLAB_CI_BRANCH_BUILDS_PYTHON,
                environment_name='MAYAN_GITLAB_CI_BRANCH_BUILDS_PYTHON'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_DEPLOYMENTS_DEMO',
                default=GITLAB_CI_BRANCH_DEPLOYMENTS_DEMO,
                environment_name='MAYAN_GITLAB_CI_BRANCH_DEPLOYMENTS_DEMO'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_DEPLOYMENTS_STAGING',
                default=GITLAB_CI_BRANCH_DEPLOYMENTS_STAGING,
                environment_name='MAYAN_GITLAB_CI_BRANCH_DEPLOYMENTS_STAGING'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_ALL_MAJOR',
                default=GITLAB_CI_BRANCH_RELEASES_ALL_MAJOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_ALL_MAJOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_ALL_MINOR',
                default=GITLAB_CI_BRANCH_RELEASES_ALL_MINOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_ALL_MINOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_DOCKER_MAJOR',
                default=GITLAB_CI_BRANCH_RELEASES_DOCKER_MAJOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_DOCKER_MAJOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_DOCKER_MINOR',
                default=GITLAB_CI_BRANCH_RELEASES_DOCKER_MINOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_DOCKER_MINOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_DOCUMENTATION',
                default=GITLAB_CI_BRANCH_RELEASES_DOCUMENTATION,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_DOCUMENTATION'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_NIGHTLY',
                default=GITLAB_CI_BRANCH_RELEASES_NIGHTLY,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_NIGHTLY'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_PYTHON_MAJOR',
                default=GITLAB_CI_BRANCH_RELEASES_PYTHON_MAJOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_PYTHON_MAJOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_PYTHON_MINOR',
                default=GITLAB_CI_BRANCH_RELEASES_PYTHON_MINOR,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_PYTHON_MINOR'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_STAGING',
                default=GITLAB_CI_BRANCH_RELEASES_STAGING,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_STAGING'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_RELEASES_TESTING',
                default=GITLAB_CI_BRANCH_RELEASES_TESTING,
                environment_name='MAYAN_GITLAB_CI_BRANCH_RELEASES_TESTING'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TESTS_ALL',
                default=GITLAB_CI_BRANCH_TESTS_ALL,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TESTS_ALL'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TESTS_DOCKER',
                default=GITLAB_CI_BRANCH_TESTS_DOCKER,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TESTS_DOCKER'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TESTS_PYTHON_ALL',
                default=GITLAB_CI_BRANCH_TESTS_PYTHON_ALL,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TESTS_PYTHON_ALL'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TESTS_PYTHON_BASE',
                default=GITLAB_CI_BRANCH_TESTS_PYTHON_BASE,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TESTS_PYTHON_BASE'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TESTS_PYTHON_UPGRADE',
                default=GITLAB_CI_BRANCH_TESTS_PYTHON_UPGRADE,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TESTS_PYTHON_UPGRADE'
            ),
            Variable(
                name='GITLAB_CI_BRANCH_TRY_STAGING',
                default=GITLAB_CI_BRANCH_TRY_STAGING,
                environment_name='MAYAN_GITLAB_CI_BRANCH_TRY_STAGING'
            )
        )


class PlatformTemplateSupervisord(PlatformTemplate):
    label = _(message='Template for Supervisord.')
    name = 'supervisord'

    def __init__(self):
        self.variables = (
            Variable(
                name='GUNICORN_REQUESTS_JITTER',
                default=GUNICORN_REQUESTS_JITTER,
                environment_name='MAYAN_GUNICORN_REQUESTS_JITTER'
            ),
            Variable(
                name='GUNICORN_LIMIT_REQUEST_LINE',
                default=GUNICORN_LIMIT_REQUEST_LINE,
                environment_name='MAYAN_GUNICORN_GUNICORN_LIMIT_REQUEST_LINE'
            ),
            Variable(
                name='GUNICORN_MAX_REQUESTS',
                default=GUNICORN_MAX_REQUESTS,
                environment_name='MAYAN_GUNICORN_MAX_REQUESTS'
            ),
            Variable(
                name='GUNICORN_TIMEOUT',
                default=GUNICORN_TIMEOUT,
                environment_name='MAYAN_GUNICORN_TIMEOUT'
            ),
            Variable(
                name='GUNICORN_WORKER_CLASS',
                default=GUNICORN_WORKER_CLASS,
                environment_name='MAYAN_GUNICORN_WORKER_CLASS'
            ),
            Variable(
                name='GUNICORN_WORKERS',
                default=GUNICORN_WORKERS,
                environment_name='MAYAN_GUNICORN_WORKERS'
            ),
            Variable(
                name='GUNICORN_TIMEOUT',
                default=GUNICORN_TIMEOUT,
                environment_name='MAYAN_GUNICORN_TIMEOUT'
            ),
            Variable(
                name='INSTALLATION_PATH',
                default=DEFAULT_DIRECTORY_INSTALLATION,
                environment_name='MAYAN_INSTALLATION_PATH'
            ),
            Variable(
                name='OS_USERNAME', default=DEFAULT_OS_USERNAME,
                environment_name='MAYAN_OS_USERNAME'
            ),
            Variable(
                name='USER_SETTINGS_FOLDER',
                default=DEFAULT_USER_SETTINGS_FOLDER,
                environment_name='MAYAN_USER_SETTINGS_FOLDER'
            ),
            YAMLVariable(
                name='MEDIA_ROOT', default=settings.MEDIA_ROOT,
                environment_name='MAYAN_MEDIA_ROOT'
            )
        )

    def get_context(self):
        *_, user_settings_folder, media_root = self.variables

        return {
            'autorestart': 'true',
            'shell_path': '/bin/sh',
            'user_settings_folder': Path(
                media_root.get_value()
            ) / user_settings_folder.get_value(),
            'workers': Worker.all()
        }


class PlatformTemplateWorkerQueues(PlatformTemplate):
    label = _(message='Template showing the queues of a worker.')
    name = 'worker_queues'

    variables = (
        Variable(
            name='WORKER_NAME', default=None,
            environment_name='MAYAN_WORKER_NAME'
        ),
    )

    def get_context(self):
        worker_name = self.get_variables_context().get('WORKER_NAME')
        try:
            queues = Worker.get(name=worker_name).queues
        except KeyError:
            raise KeyError(
                'Worker name "{}" not found.'.format(worker_name)
            )

        return {
            'queues': queues, 'queue_names': sorted(
                map(lambda x: x.name, queues)
            )
        }
