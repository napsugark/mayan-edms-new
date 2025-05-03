import yaml

from django.utils.html import mark_safe


class Dumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)


def yaml_dump(data, indent):
    result = yaml.dump(
        Dumper=Dumper, data=data, width=1000
    )

    result = result.replace('\'\'\'', '\'')

    output = []

    for line in result.split('\n'):
        if line:
            output.append(
                '{}{}'.format(
                    ' ' * indent, line
                )
            )

    return mark_safe(
        '\n'.join(output)
    )


def load_env_file(filename='config.env', skip_local_config=False):
    result = {}
    with open(file=filename) as file_object:
        for line in file_object:
            # Skip empty lines and comments.
            if len(line) > 1 and not line.startswith('#'):
                key, value = line.strip().split('=')

                result[key] = value

    if filename != 'config-local.env' and not skip_local_config:
        try:
            result.update(
                load_env_file(filename='config-local.env')
            )
        except FileNotFoundError:
            """
            Non fatal. Just means this deployment does not overrides the
            default `config.env` file values.
            """

    return result
