from django.utils.translation import gettext_lazy as _

from mayan.apps.common.apps import MayanAppConfig


class PlatformForgeApp(MayanAppConfig):
    app_namespace = 'platform_forge'
    app_url = 'platform_forge'
    name = 'mayan.apps.platform_forge'
    verbose_name = _(message='Platform Forge')

    def ready(self):
        super().ready()

        # TODO: Remove this direct activation in version 4.8.
        from .platform_templates import (  # NOQA
            PlatformTemplateForgeDockerComposefile, PlatformTemplateForgeDockerfile
        )
