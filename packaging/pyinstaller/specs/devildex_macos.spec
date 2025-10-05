# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../../../src/devildex/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../../../src/devildex/local_data_parse/_external_scanner_script.py', 'devildex/local_data_parse'),
        ('../../../devildex_config.ini', '.'),
        ('../../../pyproject.toml', '.'),
        ('../../../requirements.txt', '.'),
        ('../../../src/devildex/database/__init__.py', 'devildex/database'),
        ('../../../src/devildex/database/db_manager.py', 'devildex/database'),
        ('../../../src/devildex/alembic.ini', 'devildex'),
        ('../../../src/devildex/alembic/versions', 'devildex/alembic/versions'),
        ('../../../src/devildex/alembic/env.py', 'devildex/alembic')
    ],
    hiddenimports=['sqlalchemy.dialects.sqlite', 'pkg_resources', 'devildex.database.db_manager', 'alembic.command', 'alembic.config', 'alembic.script', 'logging.config'],
    hookspath=['packaging/pyinstaller/hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='devildex_macos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
