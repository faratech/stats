# app.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=[('templates', 'templates')],
             hiddenimports=[
                 'asyncio',
                 'uvicorn',
                 'fastapi',
                 'psutil',
                 'win32service',
                 'win32serviceutil',
                 'websockets',
                 'h11',
                 'httptools',
                 'wsproto',
                 'anyio',
                 'typing_extensions',
                 'starlette',
                 'starlette.websockets',
                 'idna',  # For WebSockets
                 'sniffio',  # For anyio
                 'json',  # For JSON serialization
                 'http',
                 'email',
                 'certifi',  # SSL certificates
                 'jinja2',  # Templating
                 'jinja2.ext',  # Jinja2 extensions
             ],
             hookspath=[],
             hooksconfig={},
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
          name='stats_app',
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
               upx_exclude=[],
               name='stats_app')
