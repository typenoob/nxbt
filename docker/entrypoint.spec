# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['entrypoint.py'],
    pathex=['/nxbt/docker'],
    binaries=[],
    datas=[],
    hiddenimports=[
            'eventlet.hubs.epolls',
            'eventlet.hubs.kqueue',
            'eventlet.hubs.selects',
            'dns',
            'dns.dnssec',
            'dns.e164',
            'dns.hash',
            'dns.namedict',
            'dns.tsigkeyring',
            'dns.update',
            'dns.version',
            'dns.asyncresolver',
            'dns.asyncquery',
            'dns.versioned'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,

    [],
    name='entrypoint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)