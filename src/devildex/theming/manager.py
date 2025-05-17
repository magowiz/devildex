import ast
from pathlib import Path
from typing import Union

from devildex.info import PROJECT_ROOT


class ThemeManager:

    def __init__(self, project_path: Path, doc_type: str, sphinx_conf_file:Union[Path|None]=None):
        self.project_path = project_path
        self.doc_type = doc_type
        self.sphinx_conf_file = sphinx_conf_file
        theme_container_dir = PROJECT_ROOT / 'src' / 'devildex' / 'theming' / 'sphinx'
        self.settings = {'html_theme': 'devildex_sphinx_theme',
                         'html_theme_path': [str(theme_container_dir.resolve())],
                         'html_css_files': ['devildex.css'],
                        'html_js_files': ['devildex.js']}
        self.new_theme_name = 'devildex'
        self.potential_sphinx_conf_paths = [
            self.project_path / 'conf.py',
            self.project_path / 'source' / 'conf.py',
            self.project_path / 'docs' / 'conf.py',
            self.project_path / 'doc' / 'conf.py',
        ]
    def sphinx_change_conf(self):
        if self.doc_type != 'sphinx':
            return
        conf_file = self.sphinx_conf_file
        if not conf_file or not conf_file.is_file():
            conf_file = next((p for p in self.potential_sphinx_conf_paths if p.is_file()), None)
        with open(conf_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
        tree = ast.parse(source_code, filename=str(conf_file))
        for var, value in self.settings.items():
            var_found = False
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                       isinstance(node.targets[0], ast.Name) and \
                       node.targets[0].id == var:
                    if isinstance(value, str):
                        node.value = ast.Constant(value=value)
                        var_found = True
                        break
                    else:
                        node.value = ast.List(elts=[ast.Constant(value=s) for s in value], ctx=ast.Load())
                        var_found = True
                        break
            if not var_found:
                if isinstance(value, str):
                    new_assignment = ast.Assign(
                        targets=[ast.Name(id=var, ctx=ast.Store())],
                        value=ast.Constant(value=value)
                    )
                    tree.body.append(new_assignment)
                else:
                    new_assignment = ast.Assign(
                        targets=[ast.Name(id=var, ctx=ast.Store())],
                        value=ast.List(elts=[ast.Constant(value=s) for s in value], ctx=ast.Load())
                    )
                    tree.body.append(new_assignment)
        ast.fix_missing_locations(tree)
        Path(conf_file).write_text(ast.unparse(tree), encoding='utf-8')