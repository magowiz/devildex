from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["wx", "sqlalchemy", "requests", "fastmcp", "devildex"],
    "includes": [],
    "include_files": [
        ("imgs", "imgs"),
        ("devildex_config.ini", "devildex_config.ini"),
    ],
    "excludes": ["tkinter", "unittest", "pydoc", "email", "html", "http", "xml",
                 "test", "distutils", "setuptools", "lib2to3", "concurrent",
                 "asyncio", "json", "urllib", "xmlrpc", "logging", "multiprocessing"],
}

setup(
    name="DevilDex",
    version="0.2.0",
    description="A desktop application for managing Python package documentation.",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "src/devildex/main.py",
            base=None, # For macOS, often no specific base is needed for .app bundles
            target_name="devildex", # No .exe extension
            icon="devildex.icns" # You'll need to provide a .icns file
        )
    ],
)
