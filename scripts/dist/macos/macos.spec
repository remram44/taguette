# -*- mode: python -*-

block_cipher = None


a = Analysis(['pyinstaller_entrypoint.py'],
             pathex=['/Users/vagrant/taguette'],
             binaries=[],
             datas=[('taguette/static', 'taguette/static'),
                    ('taguette/templates', 'taguette/templates'),
                    ('taguette/migrations', 'taguette/migrations'),
                    ('taguette/l10n', 'taguette/l10n')],
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
          [],
          exclude_binaries=True,
          name='taguette_exe',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='taguette')
app = BUNDLE(coll,
             name='Taguette.app',
             icon='scripts/dist/macos/taguette.icns',
             bundle_identifier='fr.taguette')
