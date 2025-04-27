from cx_Freeze import Executable, setup

# Dependencies are automatically detected, but it might need

build_options = {"packages": [], "excludes": []}

base = "gui"

executables = [Executable("main.py", base=base)]

setup(
    name="devildex",
    version="1.0",
    description="",
    options={"build_exe": build_options},
    executables=executables,
)
