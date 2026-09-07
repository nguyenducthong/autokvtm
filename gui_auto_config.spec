# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.splash import Splash

a = Analysis(
    ['gui_auto_config.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('tools/tesseract', 'tools/tesseract'),
        ('configs', 'configs')
    ],
    hiddenimports=['requests', 'cv2', 'numpy', 'PIL', 'ppadb', 'webbrowser', 'onnx'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

splash = Splash(
    'assets/splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(45, 235),
    text_size=11,
    text_color='#2ecc71',
    text_default='Đang khởi động ứng dụng...',
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    [],
    name='autokvtm_pro',
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
    icon=['assets\\icon\\app.ico'],
)

