from mayan.apps.dependencies.classes import PythonDependency
from mayan.apps.dependencies.environments import environment_testing

from mayan.settings.literals import PYTHON_PSUTIL_VERSION

PythonDependency(
    module=__name__, name='boto3', version_string='==1.37.22'
)
PythonDependency(
    module=__name__, name='django-storages', version_string='==1.14.5'
)
PythonDependency(
    module=__name__, name='extract-msg', version_string='==0.54.0'
)
PythonDependency(
    module=__name__, name='google-cloud-storage', version_string='==3.1.0'
)
PythonDependency(
    environment=environment_testing, module=__name__, name='psutil',
    version_string='=={}'.format(
        PYTHON_PSUTIL_VERSION
    )
)
PythonDependency(
    module=__name__, name='pycryptodome', version_string='==3.22.0'
)
