#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# -*- coding: utf-8 -*-

from functools import cmp_to_key
from docutils import nodes
from docutils.parsers import rst
from docutils.parsers.rst import directives

from sphinx.util import logging

from oslo_utils import importutils
from senlin.common import schema

LOG = logging.getLogger(__name__)


class PolicyDirective(rst.Directive):

    # defines the parameter the directive expects
    # directives.unchanged means you get the raw value from RST
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = { 'policy_package': directives.unchanged}
    has_content = False
    add_index = True

    def run(self):
        sett = self.state.document.settings
        language_code = sett.language_code
        env = self.state.document.settings.env

        # gives you access to the parameter stored
        # in the main configuration file (conf.py)
        config = env.config

        # gives you access to the options of the directive
        options = self.options

        # we create main section
        content = []
        section = self._create_section(content, 'blah', title=options['policy_package'])

        # read in health policy class
        obj = importutils.import_class(options['policy_package'])

        # create version section
        version_section = self._create_section(section, 'version', title='Latest Version')
        field = nodes.line('', obj.VERSION)
        version_section.append(field)

        # build versions table
        self.build_version_table(sorted(obj.VERSIONS.items()), section)

        # create applicable profile types
        profile_type_section = self._create_section(section, 'profile_types', title='Applicable Profile Types')
        field = nodes.line('', 'This policy is designed to handle the following profile types:')
        profile_type_section.append(field)
        profile_list = nodes.bullet_list()
        for profile_type in obj.PROFILE_TYPE:
            profile_type_section += self._create_list_item(profile_type)

        # create actions handled
        self.build_target_table(sorted(obj.TARGET, key=lambda tup: tup[1]), section)

        # build properties
        properties_section = self._create_section(section, 'properties', title='Properties')
        sorted_schema = sorted(obj.properties_schema.items(), key=cmp_to_key(self.sort_by_type))
        for k, v in sorted_schema:
            self.build_schema_doc(k, v, properties_section)

        # we return the result
        return content

    def _create_list_item(self, str):
        para = nodes.paragraph()
        para += nodes.strong('', str)

        item = nodes.list_item()
        item += para

        return item

    def _create_section(self, parent, sectionid, title=None, term=None):
        idb = nodes.make_id(sectionid)
        section = nodes.section(ids=[idb])
        parent.append(section)

        if title:
            section.append(nodes.title('', title))
            return section

        if term:
            if term != '**':
                section.append(nodes.term('', term))

            definition = nodes.definition()
            section.append(definition)

            return definition

    def _create_def_list(self, parent):
        definition_list = nodes.definition_list()
        parent.append(definition_list)

        return definition_list

    def sort_by_type(self, x, y):
        LOG.info('sort(%s,%s)', x, y)
        x_key, x_value = x
        y_key, y_value = y

        # if both values are map or list, sort by their keys
        if ((isinstance(x_value, schema.Map) or
             isinstance(x_value, schema.List)) and
                (isinstance(y_value, schema.Map) or
                 isinstance(y_value, schema.List))):
            return (x_key > y_key) - (x_key < y_key)

        # show simple types before maps or list
        if (isinstance(x_value, schema.Map) or isinstance(x_value, schema.List)):
            return 1

        if (isinstance(y_value, schema.Map) or isinstance(y_value, schema.List)):
            return -1

        return (x_key > y_key) - (x_key < y_key)

    def create_table_row(self, cells, parent):
        row = nodes.row()
        parent.append(row)

        for c in cells:
            LOG.info('c: %s', c)
            entry = nodes.entry()
            row += entry
            entry += nodes.literal(text=c)

        return row

    def build_target_table(self, targets, section):
        headers = ['Action', 'Phase']
        table_section = self._create_section(section, 'targets', title='Actions Handled')

        table = nodes.table()
        tgroup = nodes.tgroup(len(headers))
        table += tgroup

        table_section.append(table)

        for _ in headers:
            tgroup.append(nodes.colspec(colwidth=1))

        # create header
        thead = nodes.thead()
        tgroup += thead
        self.create_table_row(headers, thead)

        tbody = nodes.tbody()
        tgroup += tbody

        # create body consisting of targets
        tbody = nodes.tbody()
        tgroup += tbody
        for phase, action in targets:
            cells = [ action, phase ]
            self.create_table_row(cells, tbody)

    def build_version_table(self, versions, section):
        headers = ['Version', 'Status', 'Supported Since']
        table_section = self._create_section(section, 'versions', title='Available Versions')

        table = nodes.table()
        tgroup = nodes.tgroup(len(headers))
        table += tgroup

        table_section.append(table)

        for _ in headers:
            tgroup.append(nodes.colspec(colwidth=1))

        # create header
        thead = nodes.thead()
        tgroup += thead
        self.create_table_row(headers, thead)

        tbody = nodes.tbody()
        tgroup += tbody

        # create body consisting of versions
        tbody = nodes.tbody()
        tgroup += tbody
        for version, support_status in versions:
            for support in support_status:
                cells = [version]
                sorted_support = sorted(support.items(), reverse=True)
                LOG.info('support: %s', sorted_support)
                cells += [x[1] for x in sorted_support]
                self.create_table_row(cells, tbody)

    def build_schema_doc(self, k, v, definition):
        if isinstance(v, schema.Map):
            newdef = self._create_section(definition, k, term=k)

            if v.schema is None:
                # if it's a map for arbritary values, only include description
                field = nodes.line('', v.description)
                newdef.append(field)
                return

            newdeflist = self._create_def_list(newdef)

            LOG.info('schema: %s', v.schema.items())
            sorted_schema = sorted(v.schema.items(), key=cmp_to_key(self.sort_by_type))
            for key,value in sorted_schema:
                self.build_schema_doc(key, value, newdeflist)
        elif isinstance(v, schema.List):
            newdef = self._create_section(definition, k, term=k)

            # field = nodes.line('', v.description)
            # newdef.append(field)

            # identify next section as list properties
            field = nodes.line()
            emph = nodes.emphasis('', 'List properties:')
            field.append(emph)
            newdef.append(field)

            newdeflist = self._create_def_list(newdef)

            self.build_schema_doc('**', v.schema['*'], newdeflist)
        else:
            newdef = self._create_section(definition, k, term=k)
            if 'description' in v:
                field = nodes.line('', v['description'])
                newdef.append(field)
            else:
                field = nodes.line('', '++')
                newdef.append(field)

def setup(app):
    app.add_directive('policydoc', PolicyDirective)
