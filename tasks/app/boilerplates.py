# pylint: disable=line-too-long
"""
Boilerplates
"""
from __future__ import print_function

import logging
import os
import re

try:
    from invoke import ctask as task
except ImportError:  # Invoke 0.13 renamed ctask to task
    from invoke import task


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@task
def crud_module(context, module_name='', module_name_singular=''):
    # pylint: disable=unused-argument
    """
    Create CRUD (Create-Read-Update-Delete) empty module.

    Usage:
    $ invoke app.boilerplates.crud-module --module-name=articles --module-name-singular=article
    """
    try:
        import jinja2
    except ImportError:
        log.critical("jinja2 is required to create boilerplates. Please, do `pip install jinja2`")
        return

    if not module_name:
        log.critical("Module name is required")
        return

    if not re.match('^[a-zA-Z0-9_]+$', module_name):
        log.critical(
            "Module module_name is allowed to contain only letters, numbers and underscores "
            "([a-zA-Z0-9_]+)"
        )
        return

    if not module_name_singular:
        module_name_singular = module_name[:-1]

    module_path = 'app/modules/%s' % module_name

    module_title = " ".join(
        [word.capitalize()
            for word in module_name.split('_')
        ]
    )

    model_name = "".join(
        [word.capitalize()
            for word in module_name_singular.split('_')
        ]
    )

    if os.path.exists(module_path):
        log.critical('Module `%s` already exists.', module_name)
        return

    os.makedirs(module_path)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('tasks/app/boilerplates_templates/crud_module')
    )
    for template_file in (
        '__init__',
        'models',
        'parameters',
        'resources',
        'schemas',
    ):
        template = env.get_template('%s.py.template' % template_file)
        template.stream(
            module_name=module_name,
            module_name_singular=module_name_singular,
            module_title=module_title,
            module_namespace=module_name.replace('_', '-'),
            model_name=model_name,
        ).dump(
            '%s/%s.py' % (module_path, template_file)
        )

    log.info("Module `%s` has been created.", module_name)
    print(
        "Add `%(module_name)s` to `ENABLED_MODULES` in `config.py`\n"
        "ENABLED_MODULES = (\n"
        "\t'auth',\n"
        "\t'users',\n"
        "\t'teams',\n"
        "\t'%(module_name)s',\n\n"
        "\t'api',\n"
        ")\n\n"
        "You can find your module at `app/modules/` directory"
        % {'module_name': module_name}
    )
@task
def provider(context, provider_name=''):
    # pylint: disable=unused-argument
    """
    Create Provider empty File.

    Usage:
    $ invoke app.boilerplates.provider --provider-name=docker
    """
    try:
        import jinja2
    except ImportError:
        log.critical("jinja2 is required to create boilerplates. Please, do `pip install jinja2`")
        return

    if not provider_name:
        log.critical("Provider name is required")
        return

    if not re.match('^[a-zA-Z0-9_]+$', provider_name):
        log.critical(
            "Provider provider_name is allowed to contain only letters, numbers and underscores "
            "([a-zA-Z0-9_]+)"
        )
        return

    provider_path = 'app/extensions/providers'

    provider_class = "".join(
        [word.capitalize()
            for word in provider_name.split('_')
        ]
    )
    provider_class = provider_class+'Provider'
    
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('tasks/app/boilerplates_templates/provider')
    )
    template = env.get_template('provider.py.template')
    template.stream(
        provider_name=provider_name,
        provider_class=provider_class,
    ).dump(
        '%s/%s.py' % (provider_path, provider_name)
    )

    log.info("Provider `%s` has been created.", provider_name)
    print(
        "Add `%(provider_name)s` to `__init__.py` in `app/providers` directory\n"
        "from .%(provider_name)s import %(provider_class)s"
        % {'provider_name': provider_name,'provider_class': provider_class}
    )
