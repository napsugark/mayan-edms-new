from django.utils.translation import gettext_lazy as _

from mayan.apps.dependencies.classes import (
    GoogleFontDependency, JavaScriptDependency, PythonDependency
)

GoogleFontDependency(
    label=_(message='Lato font'), module=__name__, name='lato',
    url='https://fonts.googleapis.com/css?family=Lato:400,700,400italic'
)
JavaScriptDependency(
    label=_(message='Bootstrap'), module=__name__, name='bootstrap',
    version_string='=3.4.1'
)
JavaScriptDependency(
    label=_(message='Bootswatch'), module=__name__, name='bootswatch',
    replace_list=[
        {
            'filename_pattern': 'bootstrap.*.css',
            'content_patterns': [
                {
                    'search': '"https://fonts.googleapis.com/css?family=Lato:400,700,400italic"',
                    'replace': '../../../google_fonts/lato/import.css',
                }
            ]
        }
    ], version_string='=3.4.1'
)
JavaScriptDependency(
    label=_(message='Fancybox'), module=__name__, name='@fancyapps/fancybox',
    version_string='=3.2.5'
)
JavaScriptDependency(
    label=_(message='FontAwesome'), module=__name__,
    name='@fortawesome/fontawesome-free', version_string='=6.5.2'
)
JavaScriptDependency(
    label=_(message='jQuery'), module=__name__, name='jquery',
    version_string='=3.7.1'
)
JavaScriptDependency(
    label=_(message='JQuery Form'), module=__name__, name='jquery-form',
    version_string='=4.3.0'
)
JavaScriptDependency(
    label=_(message='JQuery Match Height'), module=__name__,
    name='jquery-match-height', version_string='=0.7.2'
)
JavaScriptDependency(
    label=_(message='Select 2'), module=__name__, name='select2',
    version_string='=4.0.13'
)
JavaScriptDependency(
    label=_(message='Toastr'), module=__name__, name='toastr',
    version_string='=2.1.4'
)

PythonDependency(
    module=__name__, name='bleach', version_string='==6.2.0'
)
