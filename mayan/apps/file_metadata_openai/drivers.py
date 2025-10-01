from openai import OpenAI

from django.apps import apps
from django.utils.translation import gettext_lazy as _

from mayan.apps.common.serialization import yaml_load
from mayan.apps.common.utils import flatten_object
from mayan.apps.credentials.models import StoredCredential
from mayan.apps.credentials.permissions import permission_credential_use
from mayan.apps.file_metadata.classes import FileMetadataDriver
from mayan.apps.file_metadata.exceptions import FileMetadataDriverError
from mayan.apps.file_metadata.literals import RESULT_SEPARATOR
from mayan.apps.forms import form_fields, forms
from mayan.apps.templating.fields import TemplateField
from mayan.apps.templating.template_backends import Template

from .literals import DEFAULT_TIMEOUT


class FileMetadataDriverOpenAIResponseAPI(FileMetadataDriver):
    argument_name_list = (
        'base_url', 'input', 'model', 'organization', 'project',
        'stored_credential_id', 'timeout'
    )
    description = _(message='Analyze content using OpenAI\'s Response API.')
    enabled = False
    internal_name = 'openai_response'
    label = _(message='OpenAI Response API driver')
    mime_type_list = ('*',)

    class Form(forms.Form):
        class FormMeta:
            fieldsets = (
                (
                    _(message='Basic'), {
                        'fields': ('enabled', 'arguments')
                    }
                ),
                (
                    _(message='Authentication'), {
                        'fields': ('stored_credential_id',)
                    }
                ),
                (
                    _(message='Control'), {
                        'fields': ('organization', 'project', 'model')
                    }
                ),
                (
                    _(message='Prompt'), {
                        'fields': ('input',)
                    }
                ),
                (
                    _(message='Communication'), {
                        'fields': ('base_url', 'timeout',)
                    }
                ),
            )

        base_url = TemplateField(
            initial_help_text=_(
                message='API endpoint base URL. Change this only when using '
                'a compatible non-default endpoint or proxy.'
            ), label=_(message='Base URL'), required=False
        )
        stored_credential_id = form_fields.FormFieldFilteredModelChoice(
            help_text=_(
                message='The credential entry to use for authentication. '
                'Only use credential backend that provide a `token` value.'
            ),
            source_model=StoredCredential,
            permission=permission_credential_use,
            label=_(message='Credential'), required=True
        )
        input = TemplateField(
            initial_help_text=_(
                message='Text or file content to send to the OpenAI API '
                'for analysis. The document file object is available as '
                '{{ document_file }}.'
            ), label=_(message='Input'), required=False
        )
        model = TemplateField(
            initial_help_text=_(
                message='Identifier of the OpenAI model to use '
                '(for example: gpt-5, gpt-5-nano). The document file object '
                'is available as {{ document_file }}.'
            ), label=_(message='Model'), required=True
        )
        organization = TemplateField(
            initial_help_text=_(
                message='Optional OpenAI organization ID. Used when the API key is linked to multiple organizations. The document file object is available as {{ document_file }}.'
            ), label=_(message='Organization'), required=False
        )
        project = TemplateField(
            initial_help_text=_(
                message='Optional OpenAI project ID. Allows scoping requests to a specific project.  The document file object is available as {{ document_file }}.'
            ), label=_(message='Project'), required=False
        )
        timeout = TemplateField(
            initial_help_text=_(
                message='Maximum time (in seconds) to wait for a response from the API before failing.  The document file object is available as {{ document_file }}.'
            ), label=_(message='Timeout'), required=False
        )

    @classmethod
    def get_argument_values_for_document_file(cls, document_file):
        document_type = document_file.document.document_type

        configuration_instance = document_type.file_metadata_driver_configurations.get(
            stored_driver__internal_name=cls.internal_name
        )

        document_type_arguments = configuration_instance.get_arguments()

        context = {'document_file': document_file}

        argument_values_rendered = {}

        for key, value in document_type_arguments.items():
            template = Template(template_string=value)
            template_result = template.render(context=context)
            argument_values_rendered[key] = template_result

        return argument_values_rendered

    @classmethod
    def get_argument_values_from_settings(cls):
        result = {'timeout': DEFAULT_TIMEOUT}
        setting_arguments = super().get_argument_values_from_settings()

        if setting_arguments:
            result.update(setting_arguments)

        return result

    def __init__(
        self, input, model, stored_credential_id, base_url=None,
        organization=None, project=None, timeout=None, **kwargs
    ):
        super().__init__(**kwargs)

        self.base_url = base_url
        self.input = yaml_load(stream=input)
        self.model = model
        self.organization = organization
        self.project = project
        self.stored_credential_id = stored_credential_id
        self.timeout = int(timeout)

        self.api_key = self.get_api_key()

    def get_api_key(self):
        StoredCredential = apps.get_model(
            app_label='credentials', model_name='StoredCredential'
        )

        stored_credential = StoredCredential.objects.get(
            pk=self.stored_credential_id
        )

        backend_instance = stored_credential.get_backend_instance()

        credential = backend_instance.get_credential(
            action_object=self.model_instance
        )

        try:
            return credential['token']
        except KeyError:
            raise FileMetadataDriverError(
                _(message='The credential provided does not provide a token.')
            )

    def _process(self, document_file):
        result = {}

        client = OpenAI(
            api_key=self.api_key, base_url=self.base_url,
            organization=self.organization, project=self.project
        )

        response = client.responses.create(
            input=self.input, model=self.model
        )

        dictionary = response.to_dict()
        generator = flatten_object(obj=dictionary, separator=RESULT_SEPARATOR)
        result = dict(generator)

        return result
