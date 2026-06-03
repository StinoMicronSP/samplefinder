# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-spec voor een one-file SampleFinder-executable (console-modus).
#
# Bouwen:   pyinstaller --noconfirm SampleFinder.spec   ->   dist/SampleFinder(.exe)
#
# Bundelt optioneel een ffmpeg-binary als ./ffmpeg/ffmpeg(.exe) bestaat. De
# release-workflow zet die er via `imageio-ffmpeg` neer, zodat de .exe ook werkt
# zonder dat de gebruiker ffmpeg apart installeert. Op runtime vindt het script
# die binary via _ffmpeg() (kijkt in de PyInstaller-bundel).
import os

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# tkinter wordt lazy (in een functie) geïmporteerd voor de GUI -> expliciet meenemen.
hiddenimports += ["tkinter", "tkinter.ttk", "tkinter.filedialog",
                  "tkinter.scrolledtext", "tkinter.messagebox"]

# Pakketten met data-bestanden / lazy-imports die PyInstaller niet altijd
# automatisch meeneemt. Per pakket defensief: ontbreekt het, sla het over.
for pkg in ("librosa", "soundfile", "soxr", "audioread", "pooch",
            "lazy_loader", "numba", "llvmlite", "decorator", "msgpack",
            "mutagen", "joblib", "threadpoolctl"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # pragma: no cover - build-tijd
        print(f"[spec] collect_all({pkg}) overgeslagen: {exc}")

# Optioneel: bundel een ffmpeg-binary die naast deze spec in ./ffmpeg/ staat.
for cand in ("ffmpeg/ffmpeg.exe", "ffmpeg/ffmpeg"):
    if os.path.exists(cand):
        binaries += [(cand, ".")]
        print(f"[spec] ffmpeg gebundeld: {cand}")
        break
else:
    print("[spec] geen ffmpeg gevonden om te bundelen (PATH-ffmpeg blijft nodig)")


a = Analysis(
    ["sample_finder.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "demucs", "matplotlib", "pytest", "tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SampleFinder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,        # console-modus: toont de kandidaten-tabel + prompts
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
