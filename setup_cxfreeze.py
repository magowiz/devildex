"""setup for cx_freeze."""

from cx_Freeze import Executable, setup

build_options = {"packages": ["encodings"], "excludes": []}

BASE = "gui"

executables = [Executable("src/devildex/main.py", base=BASE)]

setup(
    name="devildex",
    version="1.0",
    description="",
    options={"build_exe": build_options},
    executables=executables,
)
