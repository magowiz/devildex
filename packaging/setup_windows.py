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
    "include_msvcr": True, # Important for Windows
}

setup(
    name="DevilDex",
    version="0.2.0",
    description="A desktop application for managing Python package documentation.",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "src/devildex/main.py",
            base="Win32GUI", # Specifically for Windows GUI
            target_name="devildex.exe",
            icon="devildex.ico" # You'll need to provide a .ico file
        )
    ],
)
