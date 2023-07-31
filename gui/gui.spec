# -*- mode: python -*-
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

from mozregression.pyinstaller import BUNDLE_WITH_TK

IS_MAC = sys.platform == "darwin"

block_cipher = None

datas, binaries, hiddenimports = [], [], []
for pkgname in ["glean", "glean_parser", "mozregression", "yamllint", "bs4"]:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkgname)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hiddenimports)

a = Analysis(
    ["mozregression-gui.py"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=["splash_hook.py"],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if IS_MAC:
    binaries = a.binaries - TOC(
        [
            ("QtNetwork", None, None),
            ("QtOpenGL", None, None),
            ("QtPdf", None, None),
            ("QtQml", None, None),
            ("QtQmlModels", None, None),
            ("QtQuick", None, None),
            ("QtSvg", None, None),
            ("QtVirtualKeyboard", None, None),
        ]
    )
    binaries = binaries - TOC(
        [binary for binary in binaries if "PySide6/Qt/plugins/imageformats" in binary[0]]
    )

    datas = a.datas - TOC([data for data in a.datas if "PySide6/Qt/translations" in data[0]])
    datas = datas - TOC([data for data in datas if "bs4/tests" in data[0]])

    exe = EXE(
        pyz,
        a.scripts,
        binaries,
        a.zipfiles,
        datas,
        [],
        name="mozregression GUI",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        target_arch="universal2",
    )
    app = BUNDLE_WITH_TK(
        exe,
        strip=False,
        upx=False,
        name="mozregression GUI.app",
        icon="icons/app_icon.icns",
        bundle_identifier=None,
        info_plist={"NSPrincipalClass": "NSApplication", "NSHighResolutionCapable": "True"},
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name="mozregression-gui",
        exclude_binaries=True,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon="wininst/app_icon.ico",
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="mozregression-gui"
    )
