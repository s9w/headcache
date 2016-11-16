# -*- mode: python -*-

block_cipher = None

added_files = [("style.qss", ".")]

a = Analysis(['parrot.py'],
             pathex=['C:\\Dropbox\\parrot'],
             binaries=None,
             datas=added_files,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='parrot',
          debug=False,
          strip=False,
          upx=True,
          console=False )
