# -*- mode: python ; coding: utf-8 -*-
#
# Build with: pyinstaller manual-scrobble.spec
#
# A committed spec file (rather than a long CLI command) so the exclude list
# below is never accidentally dropped by a shell/copy-paste mistake. It's what
# keeps PySide6/Qt (installed for the Linux dev fallback, see Pipfile) out of
# the Windows build, which otherwise bloats the exe by 150MB+.

import os

import nicegui

nicegui_dir = os.path.dirname(nicegui.__file__)

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[(nicegui_dir, 'nicegui')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'PySide2', 'PyQt5', 'PyQt6', 'qtpy', 'shiboken6', 'shiboken2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='manual-scrobble',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
