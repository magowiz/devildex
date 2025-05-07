import pdoc

config_file = "../../../devildex_config.ini"


def run_pdoc():
    modules = ['a', 'b']  # Public submodules are auto-imported
    context = pdoc.Context()

    modules = [pdoc.Module(mod, context=context)
            for mod in modules]
    pdoc.link_inheritance(context)

    def recursive_htmls(mod):
        yield mod.name, mod.html()
        for submod in mod.submodules():
            yield from recursive_htmls(submod)

    for mod in modules:
        for module_name, html in recursive_htmls(mod):
            pdoc.html()

def git_clone(repo_url):
    subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    default_branch,
                    repo_url,
                    clone_dir_path,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
    run_pdoc()

def run():
    final_output_dir = os.path.join("../../../docset", project_slug, version_identifier)


if __name__ == "__main__":
    url = "https://github.com/psf/black"
    run(url)