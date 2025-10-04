import toml
import sys
import re
from collections import OrderedDict

def parse_dependency_string(dep_string):
    # Gestisce prima le dipendenze URL
    match_url = re.match(r'([^ ]+) @ (.*)', dep_string)
    if match_url:
        package_name = match_url.group(1).strip()
        url = match_url.group(2).strip()
        return package_name, {'url': url}

    # Gestisce gli specificatori di versione tra parentesi
    match_version_spec = re.match(r'([^ ]+) \((.*)\)', dep_string)
    if match_version_spec:
        package_name = match_version_spec.group(1).strip()
        version_spec = match_version_spec.group(2).strip()
        return package_name, version_spec
    
    # Gestisce il nome del pacchetto semplice con versione opzionale (es. "package ^1.0.0" o "package")
    parts = dep_string.split(' ', 1) # Divide solo al primo spazio
    if len(parts) == 2:
        package_name = parts[0].strip()
        version_spec = parts[1].strip()
        return package_name, version_spec
    elif len(parts) == 1:
        package_name = parts[0].strip()
        return package_name, "*" # Predefinito a qualsiasi versione se non specificato
    
    print(f"Attenzione: Impossibile analizzare completamente la stringa di dipendenza '{dep_string}'. Saltando.")
    return None, None


def convert_pyproject_to_poetry_1x(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            data = toml.load(f)
    except FileNotFoundError:
        print(f"Errore: File di input '{input_file}' non trovato.")
        sys.exit(1)
    except toml.TomlDecodeError as e:
        print(f"Errore durante la decodifica TOML da '{input_file}': {e}")
        sys.exit(1)

    new_data = OrderedDict()
    new_data['tool'] = OrderedDict()
    new_data['tool']['poetry'] = OrderedDict()

    # Sposta i metadati da [project] a [tool.poetry]
    if 'project' in data:
        project = data['project']
        new_data['tool']['poetry']['name'] = project.get('name')
        new_data['tool']['poetry']['version'] = project.get('version')
        new_data['tool']['poetry']['description'] = project.get('description')
        
        # Conversione formato autori
        authors = project.get('authors', [])
        formatted_authors = []
        for author in authors:
            name = author.get('name')
            email = author.get('email')
            if name and email:
                formatted_authors.append(f"{name} <{email}>")
            elif name:
                formatted_authors.append(name)
        if formatted_authors:
            new_data['tool']['poetry']['authors'] = formatted_authors

        new_data['tool']['poetry']['readme'] = project.get('readme')

        # Gestisce i pacchetti dall'esistente [tool.poetry]
        if 'tool' in data and 'poetry' in data['tool'] and 'packages' in data['tool']['poetry']:
            new_data['tool']['poetry']['packages'] = data['tool']['poetry']['packages']

        # Sposta le dipendenze principali e la versione di python
        new_data['tool']['poetry']['dependencies'] = OrderedDict()
        if 'requires-python' in project:
            new_data['tool']['poetry']['dependencies']['python'] = project['requires-python']
        
        if 'dependencies' in project:
            for dep_string in project['dependencies']:
                package_name, dep_spec = parse_dependency_string(dep_string)
                if package_name and dep_spec:
                    new_data['tool']['poetry']['dependencies'][package_name] = dep_spec

    # Sposta gli script da [project.scripts] a [tool.poetry.scripts]
    if 'project' in data and 'scripts' in data['project']:
        new_data['tool']['poetry']['scripts'] = data['project']['scripts']

    # Converte [tool.poetry.group.*.dependencies] in [tool.poetry.dev-dependencies]
    new_data['tool']['poetry']['dev-dependencies'] = OrderedDict()
    if 'tool' in data and 'poetry' in data['tool'] and 'group' in data['tool']['poetry']:
        for group_name, group_data in data['tool']['poetry']['group'].items():
            if 'dependencies' in group_data:
                for dep_name, dep_spec in group_data['dependencies'].items():
                    new_data['tool']['poetry']['dev-dependencies'][dep_name] = dep_spec

    # Aggiunge nuovamente build-system
    if 'build-system' in data:
        new_data['build-system'] = data['build-system']

    try:
        with open(output_file, 'w') as f:
            toml.dump(new_data, f)
        print(f"Convertito con successo '{input_file}' al formato Poetry 1.x in '{output_file}'.")
    except IOError as e:
        print(f"Errore durante la scrittura del file di output '{output_file}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Utilizzo: python convert_poetry.py <input_pyproject.toml> <output_pyproject.toml>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    convert_pyproject_to_poetry_1x(input_path, output_path)
