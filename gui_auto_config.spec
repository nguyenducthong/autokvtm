# -*- mode: python ; coding: utf-8 -*-

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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='autokvtm_pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon\\app.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='autokvtm_pro',
)

import os
import shutil

target_dir = os.path.join('dist', 'autokvtm_pro')
for item in ['assets', 'configs', 'tools']:
    src_path = item
    dst_path = os.path.join(target_dir, item)
    if os.path.exists(src_path):
        if not os.path.exists(dst_path):
            shutil.copytree(src_path, dst_path)

