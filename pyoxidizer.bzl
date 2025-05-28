def make_exe():
    dist = default_python_distribution()

    policy = dist.make_python_packaging_policy()
    python_config = dist.make_python_interpreter_config()
    python_config.run_filename = "src/devildex/main.py"

    exe = dist.to_python_executable(
        name="devildex_app",
        packaging_policy=policy,
        config=python_config,
    )
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files

def make_msi(exe):
    return exe.to_wix_msi_builder(
        "myapp",
        "My Application",
        "1.0",
        "Alice Jones"
    )

def register_code_signers():
    if not VARS.get("ENABLE_CODE_SIGNING"):
        return

register_code_signers()

register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)
register_target("msi_installer", make_msi, depends=["exe"])

resolve_targets()
