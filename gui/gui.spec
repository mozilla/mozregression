# -*- mode: python -*-
import sys
from PyInstaller.utils.hooks import collect_all

IS_MAC = sys.platform == "darwin"

block_cipher = None

datas, binaries, hiddenimports = [], [], []
for pkgname in ['glean', 'glean_parser', 'mozregression', 'yamllint']:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkgname)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hiddenimports)

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
            name='mozregression-gui',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=False,
            console=False,
            icon='wininst/app_icon.ico')
    app = BUNDLE(exe,
                a.binaries,
                a.zipfiles,
                a.datas,
                strip=False,
                upx=True,
                name='mozregression-gui.app',
                icon='icons/app_icon.icns',
                bundle_identifier=None)
else:
    exe = EXE(pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            [],
            name='mozregression-gui',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=False,
            runtime_tmpdir=None,
            console=False,
            icon='wininst/app_icon.ico')
