from mayan.apps.dependencies.classes import PythonDependency
from mayan.apps.dependencies.environments import environment_testing

PythonDependency(
    module=__name__, name='boto3', version_string='==1.35.85'
)
PythonDependency(
    module=__name__, name='django-storages', version_string='==1.14.6'
)
PythonDependency(
    module=__name__, name='extract-msg', version_string='==0.52.0'
)
PythonDependency(
    module=__name__, name='google-cloud-storage', version_string='==2.19.0'
)
PythonDependency(
    environment=environment_testing, module=__name__, name='psutil',
    version_string='==6.0.0'
)
PythonDependency(
    module=__name__, name='pycryptodome', version_string='==3.21.0'
)
