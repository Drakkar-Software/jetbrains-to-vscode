#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Convert the configurations from your Jetbrains IDE to VSCode.

    Requirements:
        - workspace.xml:
            Copy your workspace.xml from your Jetbrains IDE into this folder.
        - launch.json: (Optional)
            Copy launch.json from your Jetbrains IDE into this folder.
"""

import json
import xml.dom.minidom


__author__ = "github.com/Drakkar-Software/OctoBot based on github.com/topscoder"
__license__ = "UNLICENSE"

TEST_GROUP = "2.Test" # example value
RUN_GROUP = "1.Run"  # example value
HIDDEN_FOLDERS = [
    # your run config that should not be displayed in the vscode UI selector
]
PRIORITY_BY_GROUP = {
    **{
        RUN_GROUP: 1,
        TEST_GROUP: 2,
    },
    **{
        name: i + 3
        for i, name in enumerate(HIDDEN_FOLDERS)
    }
}


class Convert():
    def __init__(self):
        self.now()

    def now(self):
        workspace_parsed = self.parse_workspace_xml()
        contents = {}

        with open('launch.json', 'w+') as target:
            # Warning! It's overwriting all existing configurations.
            try:
                contents = json.load(target)
            except Exception:
                pass
            contents['configurations'] = workspace_parsed
            target.write(json.dumps(contents, indent=2))

            target.close()

        print('> OK written to launch.json.')
        print('> Copy launch.json to your VSCode project / workspace '
              'and have fun!')

    def parse_workspace_xml(self) -> list:
        doc = xml.dom.minidom.parse("workspace.xml")
        configuration_nodes = doc.getElementsByTagName('configuration')
        nodes = []
        node_by_name = {}
        folder_order = {}
        for node in configuration_nodes:
            is_pytest = False
            if node.getAttribute('type') == 'PythonConfigurationType':
                pass
            elif node.getAttribute('type') == 'tests':
                if node.getAttribute('factoryName') == "py.test":
                    is_pytest = True
                else:
                    raise ValueError("Unexpected type '%s'" % node.getAttribute('factoryName'))
            else:
                continue

            folder_name = node.getAttribute('folderName')

            if node.getAttribute('name') == '' or node.getAttribute('name') in node_by_name:
                # prevent duplicate
                continue

            if node.getAttribute('type') == '':
                continue

            vscode_node = VSCodeConfigurationElement(
                node.getAttribute('name'),
                node.getAttribute('type'),
                'launch',
                '',
                'integratedTerminal'
            )
            node_by_name[vscode_node.name] = vscode_node
            if is_pytest:
                vscode_node.is_pytest()

            if node.getElementsByTagName('module'):
                module_name = node.getElementsByTagName('module')[0] \
                                    .getAttribute('name')
                vscode_node.presentation['group'] = TEST_GROUP if is_pytest else (folder_name or RUN_GROUP)
                orders = folder_order.get(vscode_node.presentation['group'], 1)
                vscode_node.presentation['order'] = orders
                folder_order[vscode_node.presentation['group']] = orders + 5    # +5 to easily add new ones in between later on
                vscode_node.presentation['hidden'] = vscode_node.presentation['group'] in HIDDEN_FOLDERS

            for option in node.getElementsByTagName('option'):
                if option.getAttribute('name') == 'SCRIPT_NAME':
                    vscode_node.program = option.getAttribute('value')
                    continue

                if option.getAttribute('name') == 'PARAMETERS':
                    vscode_node.args = option.getAttribute('value').split(' ')

                if option.getAttribute('name') == 'WORKING_DIRECTORY':
                    vscode_node.cwd = option.getAttribute('value')

                if option.getAttribute('name') == '_new_additionalArguments' and len(
                    option.getAttribute('value')
                ):
                    # pytest args
                    vscode_node.args.extend(option.getAttribute('value')[1:-1].replace("\\", "").replace("\"", '').split(' '))

            for envs in node.getElementsByTagName('envs'):
                for env in envs.getElementsByTagName('env'):
                    name = env.getAttribute('name')
                    if name and name != 'PYTHONUNBUFFERED':
                        vscode_node.envs[name] = env.getAttribute('value')

            nodes.append(vscode_node)

        return [
            node.as_dict()
            for node in sorted(nodes, key=lambda n: n.get_sorting_key())
        ]


class VSCodeConfigurationElement():
    """This object contains one configuration element.

        Example:
        {
            "name": "Python: Current file",
            "type": "python",
            "request": "launch",
            "runtimeExecutable": "python3",
            "program": "${file}",
            "console": "integratedTerminal",
            "args": ["--foobar"]
        }
    """

    name: str
    conf_type: str
    __request: str
    program: str
    console: str
    cwd: str
    runtimeExecutable: str
    module: str
    args: dict
    presentation: dict
    envs: dict[str, str]

    def __init__(self, el_name, conf_type, request, program, console):
        self.name = el_name
        self.conf_type = conf_type
        self.__request = request
        self.program = program
        self.console = console
        self.cwd = ""  # WORKING_DIRECTORY

        self.module = ""
        self.args = []
        self.envs: dict[str, str] = {}  # envs
        self.presentation = {
            'hidden': False,
            'group': 'Default'
        }

    def as_dict(self):
        dict_v = {
            'type': self.conf_type,
            'name': self.name,
            'request': self.__request,
            'console': self.console,
            'program': self.program,
            'cwd': self.cwd,
            'presentation': self.presentation,
            'justMyCode': False,
        }
        if self.args:
            if "-k" in self.args:
                k_index = self.args.index("-k")
                if len(self.args) > k_index and self.args[k_index + 1] == "":
                    # "" as -k arg is not supported
                    self.args[k_index + 1] = " "

            dict_v["args"] = self.args
        if self.envs:
            dict_v["env"] = self.envs
        if self.module:
            dict_v.pop("program")
            dict_v["module"] = self.module
        return dict_v

    def as_json(self):
        return json.dumps(self.as_dict())

    def is_pytest(self):
        self.module = "pytest"

    def get_sorting_key(self):
        priority = PRIORITY_BY_GROUP[self.presentation['group']]
        return priority * 100 + self.presentation['order']

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name == 'conf_type':
            self.__dict__[name] = value.replace(
                'PythonConfigurationType',
                'debugpy'
            ).replace(
                'tests',
                'debugpy'
            )

        if '$PROJECT_DIR$/..' in value:
            self.__dict__[name] = value.replace(
                '$PROJECT_DIR$/..',
                '${workspaceFolder}')
        elif '$PROJECT_DIR$' in value:
            self.__dict__[name] = value.replace(
                '$PROJECT_DIR$',
                '${workspaceFolder}')


if __name__ == '__main__':
    Convert()
