# -*- mode: python -*-
import sys
from PyInstaller.utils.hooks import (collect_all, collect_submodules)

IS_MAC = sys.platform == "darwin"

block_cipher = None

datas, binaries, hiddenimports = [], [], []
for pkgname in ['glean', 'glean_parser', 'mozregression', 'yamllint']:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkgname)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hiddenimports)

# workaround this bad interaction between setuptools and pyinstaller:
# https://github.com/pypa/setuptools/issues/1963
hiddenimports.extend(collect_submodules('pkg_resources'))

a = Analysis(['mozregression-gui.py'],
             pathex=['/Users/wlach/src/mozregression/gui'],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if IS_MAC:
    exe = EXE(pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name='mozregression GUI',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=False,
            console=False)
    app = BUNDLE(exe,
                a.binaries,
                a.zipfiles,
                a.datas,
                strip=False,
                upx=True,
                name='mozregression GUI.app',
                icon='icons/app_icon.icns',
                bundle_identifier=None,
                info_plist={
                    'NSPrincipalClass': 'NSApplication',
                    'NSHighResolutionCapable': 'True'
                })
else:
    exe = EXE(pyz,
            a.scripts,
            [],
            name='mozregression-gui',
            exclude_binaries=True,
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=False,
            console=False,
            icon='wininst/app_icon.ico')
    coll = COLLECT(exe,
            a.binaries,
            a.zipfiles,
            a.datas,
            strip=False,
            upx=False,
            name='mozregression-gui')
