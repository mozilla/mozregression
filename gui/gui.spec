# -*- mode: python -*-

block_cipher = None


a = Analysis(['mozregression-gui.py'],
             pathex=['/Users/wlach/src/mozregression/gui'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
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
