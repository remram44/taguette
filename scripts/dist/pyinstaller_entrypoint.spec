# -*- mode: python -*-

block_cipher = None


a = Analysis(['pyinstaller_entrypoint.py'],
             pathex=['C:\\Users\\user\\Desktop\\taguette'],
             binaries=[],
             datas=[('taguette/static', 'taguette/static'),
                    ('taguette/templates', 'taguette/templates')],
             hiddenimports=['bcrypt', 'cffi', 'sqlalchemy.*', 'sqlalchemy.ext.baked'],
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
          name='pyinstaller_entrypoint',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
