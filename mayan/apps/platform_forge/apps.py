from django.utils.translation import gettext_lazy as _

from mayan.apps.app_manager.apps import MayanAppConfig


class PlatformForgeApp(MayanAppConfig):
    app_namespace = 'platform_forge'
    app_url = 'platform_forge'
    name = 'mayan.apps.platform_forge'
    verbose_name = _(message='Platform Forge')
