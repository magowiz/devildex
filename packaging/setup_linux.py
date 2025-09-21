from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["wx", "sqlalchemy", "requests", "fastmcp", "devildex", "sqlalchemy.dialects", "sqlalchemy.dialects.sqlite", "pkg_resources", "sqlalchemy.orm"],
    "path": ["src"],
    "includes": ["sqlalchemy.orm", "sqlalchemy.ext.declarative", "devildex.database.db_manager"],
    "zip_include_packages": ["sqlalchemy", "sqlalchemy.orm"],
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
            base=None, # For Linux, often no specific base is needed for GUI apps
            target_name="devildex", # No extension
        )
    ],
)
