# Sample Finder — projectcontext voor Claude Code

Een lokaal Python-CLI dat **sparse secties** in een muziekbestand detecteert en
ze **non-destructief** exporteert als bruikbare samples. Drie types: een
**drum-break** (drums solo), een **solo-instrument**, en een **decay/uitklank-tail**.

> Dit document is de single source of truth voor het project. Het volledige script
> staat onderaan en is identiek aan `sample_finder.py`. Pas bij wijzigingen
> altijd beide aan, of genereer `sample_finder.py` opnieuw uit dit document.

---

## 1. Scope

**Wel:** dunne (sparse) secties vinden via goedkope analyse op de mix, daar
gericht stems van scheiden, audio-aware snijden, en exporteren met instelbaar
formaat + resolutie en een metadata-rijke bestandsnaam. Werkt op een enkel
bestand of een hele map (batch).

**Niet:** dichte, volle mixsecties doorzoeken (bewuste keuze: precisie boven
recall). Geen automatische "beste sample"-beoordeling — de tool levert
kandidaten, het oor beslist.

---

## 2. Vastgelegde ontwerpkeuzes

| Beslissing | Keuze | Reden |
|---|---|---|
| Structuur/beats | allin1, met **librosa-fallback** | allin1 is op Windows lastig (zie §5); fallback houdt je niet vast |
| Separatie-strategie | allin1 voor labels, **eigen Demucs-pass enkel op sparse vensters** | zware kwaliteit (`htdemucs_ft`) alleen waar het loont |
| Recall vs precisie | **Precisie**: enkel sparse stukken | schone kandidaten, geen ruis |
| Snijden | **Audio-aware per type**: breaks bar-aligned, tails op decay-einde | een naklank eindigt niet op een downbeat |
| Bron | **Non-destructief** | origineel wordt nooit aangeraakt |

---

## 3. Architectuur (pijplijn)

1. **Ingest + metadata** — `librosa.load` (decodeert via ffmpeg), `mutagen` voor
   artist/title/bpm. Alleen lezen.
2. **Structuur** — allin1 of librosa: beats, downbeats, bpm, segmenten.
3. **Density-analyse op de MIX** (geen separatie): HPSS percussief-ratio,
   chroma-entropie, spectrale entropie, RMS-envelope, onset-strength →
   één **sparseness-score** per maat.
4. **Kandidaat-detectie** (rule-based, per type):
   - *break*: sparse + percussief-dominant + lage chroma-entropie
   - *solo*: sparse + harmonisch + lage chroma-entropie, ≥N maten
   - *tail*: dalende RMS na laatste onset → decay-einde onder stilte-drempel
5. **Gerichte Demucs-pass** — `htdemucs_ft` **alleen** op kandidaat-vensters.
6. **Audio-aware snijden + export** — stem-keuze per type, fades tegen klikken,
   resampling naar doel-SR, getemplate bestandsnaam.

Fase 3–4 zijn de detectie; bewijs die eerst (subcommando `analyze`) voordat je in
separatie/export investeert (`export`).

---

## 4. Algoritmes & referenties (de lineage)

- **all-in-one (mir-aidj)** — functionele structuuranalyse; labels o.a.
  `intro/outro/break/inst/solo/...`, plus beats/downbeats, intern op 4 Demucs-stems.
- **López-Serrano, Dittmar & Müller (2018), *Finding Drum Breaks in Digital Music
  Recordings*** (AudioLabs Erlangen) — formaliseert drum-break-detectie via
  **CHRP** (cascaded harmonic-residual-percussive). Onze break-heuristiek (HPSS
  percussief-ratio + weggevallen harmonie) is hiervan een vereenvoudiging.
- **Tamagnan & Yang (2021), *Drum Fills Detection and Generation*** — een *fill*
  (overgangsroffel) ≠ een *break* (drums solo). v1 mikt op breaks; fills zijn een
  apart, onrijper probleem (weinig datasets).
- **Demucs / HTDemucs** — bronscheiding; `htdemucs_ft` is de fijn-afgestemde,
  trage maar schoonste variant — vandaar: enkel op korte vensters.

---

## 5. Installatie (Windows)

```powershell
# kies je interpreter (zie runner-workflow); dan:
py -3.12 -m pip install librosa soundfile numpy scipy mutagen demucs torch
# optioneel, betere structuur (kan tegenstribbelen op Windows):
py -3.12 -m pip install allin1
```

- **ffmpeg** moet op PATH staan (mp3/m4a decode + lossy export). `tkinter` zit in
  de stdlib.
- **allin1-waarschuwing:** de dependency `natten` heeft beperkte Windows-wheels en
  faalt vaak. Lukt het niet, gebruik dan `--beat-backend librosa`. De
  interactieve/dubbelklik-modus gebruikt librosa al als veilige default.
- **torch:** voor GPU-versnelling installeer je de CUDA-build van PyTorch; anders
  draait Demucs op CPU (trager, maar werkt — en het zijn maar korte vensters).

---

## 6. Gebruik

### A. Als executable (dubbelklik) — bestand of map
Dubbelklik `sample_finder.py` (of een gebouwde `.exe`). Er verschijnt een
keuzevenster: **Ja = map** (batch), **Nee = enkel bestand**. Daarna analyseert het
en vraagt of je wilt exporteren (formaat + bit-depth). Output gaat naar
`sample_finder_out/` naast je invoer.

### B. CLI
```powershell
# enkel bestand
py -3.12 sample_finder.py analyze "track.mp3" --out-dir .\out
py -3.12 sample_finder.py export  "track.mp3" --out-dir .\out --format wav --bit-depth 24

# hele map (batch), inclusief submappen, alles ineen:
py -3.12 sample_finder.py run "C:\muziek" --recursive --types break solo --beat-backend librosa
```
`input` mag altijd een bestand of een map zijn. `--types` kiest welke je zoekt.
`export`/`run` kennen `--format {wav,flac,mp3,m4a}`, `--bit-depth {16,24,32}`,
`--samplerate`, `--bitrate`, en `--index` om specifieke kandidaten te kiezen.

### C. Bouwen naar een echte `.exe` (optioneel)
```powershell
py -3.12 -m pip install pyinstaller
py -3.12 -m PyInstaller --onefile --name SampleFinder sample_finder.py
```
> Eerlijk: een `.exe` met torch/demucs/librosa wordt **groot en traag te bouwen**,
> en model-downloads gebeuren alsnog runtime. Voor testen is dubbelklik op het
> `.py` (met Python geïnstalleerd) lichter en betrouwbaarder.

---

## 7. Bestandsnaam-template

```
{artist}_{title}__{type}__{pos}__{starttijd}-{eindtijd}__{resolutie}.{ext}
```
- `pos` = `bars032-036` (bar-aligned) of `free` (tails).
- `type` = `break` / `solo` / `tail-{stem}`.
- voorbeeld: `ChemBros_SettingSun__break__bars032-036__01m12s00-01m21s00__24b-44k.wav`

Exports per track landen in `out/<tracknaam>/` om batch netjes te houden.

---

## 8. Bekende beperkingen (lees dit eerlijk)

- **Niet getest op echte audio.** v1; eerste run = kalibratie.
- **Tail-detectie is de zwakste schakel** — én detectie (heuristisch) én Demucs
  kan op kale naklanken smeren (out-of-distribution). Begin eventueel met
  `--types break solo`.
- **librosa-downbeats raden 4/4** (elke 4e beat). Klopt redelijk voor
  4-to-the-floor, fout bij rubato/oneven maat.
- **Precisie boven recall:** samples die in dichte secties begraven zitten worden
  per definitie gemist.
- **Lossy → hoge resolutie is een illusie**; de tool waarschuwt maar verbiedt niet.
- **Drempels in `CFG` zijn startwaarden** en moeten op jouw materiaal worden
  afgesteld.

---

## 9. Roadmap / open `[SPECIFY]`

- `[SPECIFY]` Doel-DAW-conventie voor naamgeving (Reaper-vriendelijk?).
- v2: allin1 vervangen door madmom voor beats → vermijdt volledige-track-Demucs
  en realiseert de échte rekenwinst van sparse-first.
- v2: drum-*fill*-detectie (Tamagnan-regel: maat met afwijkende noten t.o.v. buren).
- v2: timbre-clustering van secties via stem-embeddings ("schoonste 2 maten bas").
- v2: kandidaten-review-GUI i.p.v. console-tabel.

---

## 10. Handoff Block

```
TAAL:            Python 3.10+
ENTRYPOINT:      sample_finder.py  (dubbelklik => interactive_main)
SUBCOMMANDO'S:   analyze | export | run
INVOER:          bestand of map (+ --recursive)
BEAT-BACKEND:    allin1 (default) | librosa (fallback/dubbelklik)
SEPARATIE:       demucs htdemucs_ft, enkel op kandidaat-vensters
EXPORT:          wav/flac (soundfile) | mp3/m4a (ffmpeg); 16/24/32-bit; SR instelbaar
NON-DESTRUCTIEF: ja, bron alleen-lezen; output in sample_finder_out/<track>/
TE TESTEN:       1) analyze op 1 track  2) drempels in CFG ijken  3) export
```

---

## 11. Volledig script (`sample_finder.py`)

```python
# -*- coding: utf-8 -*-
"""
sample_finder.py  -- v1
Vindt 'sample-bare' SPARSE secties in muziek en exporteert ze non-destructief.
Types: drum-break, solo-instrument, decay/uitklank-tail.

GEBRUIK (drie manieren):
  1) Dubbelklik / zonder argumenten  -> keuzevenster: enkel BESTAND of hele MAP
  2) python sample_finder.py analyze "track.mp3" --out-dir ./out
     python sample_finder.py export  "track.mp3" --out-dir ./out --format wav --bit-depth 24
  3) python sample_finder.py run     "C:\\muziek\\map" --recursive   (analyze + export ineen)

Invoer mag een ENKEL BESTAND of een MAP zijn (batch). Met --recursive ook submappen.

ONTWERPKEUZES (vastgelegd in overleg):
  * allin1 (of librosa-fallback) levert beats/downbeats/structuur.
  * Goedkope density-detector op de MIX vindt de sparse vensters.
  * Zware Demucs-pass (htdemucs_ft) draait ALLEEN op die vensters.
  * Precisie boven recall: enkel sparse stukken.
  * Snijden audio-aware per type: breaks bar-aligned, tails op het decay-einde.
  * Non-destructief: bron wordt nooit aangeraakt; output gaat naar aparte map.

EERLIJKE KANTTEKENINGEN:
  * v1, NIET getest op echte audio door de auteur -- eerste run = kalibratie.
  * Alle drempels onder CFG zijn startwaarden; zet strenger voor meer precisie.
  * Demucs kan op zeer kale naklanken smeren (out-of-distribution): hoor de tails na.
  * mp3/m4a -> hoge bit-resolutie voegt GEEN informatie toe.

Afhankelijkheden:
  pip install librosa soundfile numpy scipy mutagen demucs torch
  (optioneel) pip install allin1        # betere structuur, lastig op Windows
  + ffmpeg op PATH (mp3/m4a decode + export). tkinter zit in de stdlib.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# CONFIG  -- pas drempels aan op je eigen materiaal (precisie boven recall)
# ----------------------------------------------------------------------------
CFG = {
    "hop_length": 512,
    "analysis_sr": 22050,
    "sparseness_min": 0.55,
    "break_perc_ratio_min": 0.62,
    "break_chroma_entropy_max": 0.78,
    "break_min_bars": 1,
    "solo_perc_ratio_max": 0.40,
    "solo_chroma_entropy_max": 0.55,
    "solo_min_bars": 2,
    "tail_rms_drop_db": -18.0,
    "tail_silence_db": -55.0,
    "tail_min_dur_s": 0.4,
    "tail_lookback_bars": 2,
    "demucs_model": "htdemucs_ft",
    "demucs_sr": 44100,
    "pad_seconds": 0.05,
    "fade_ms": 5.0,
}

DEMUCS_SOURCES = ["drums", "bass", "other", "vocals"]
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aif", ".aiff",
              ".ogg", ".wma", ".opus", ".aac"}


@dataclass
class Candidate:
    type: str
    start: float
    end: float
    start_bar: int
    end_bar: int
    score: float
    dominant_stem: str
    note: str = ""


# ----------------------------------------------------------------------------
# Invoer: enkel bestand of map -> lijst bestanden
# ----------------------------------------------------------------------------
def collect_inputs(path: str, recursive: bool = False):
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        it = p.rglob("*") if recursive else p.glob("*")
        return sorted(f for f in it if f.suffix.lower() in AUDIO_EXTS)
    return []


def pick_input_dialog():
    """Keuzevenster voor dubbelklik-gebruik: map (batch) of enkel bestand."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print(f"tkinter niet beschikbaar ({e}); geef een pad als argument.")
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    is_folder = messagebox.askyesno(
        "Sample Finder",
        "Een hele MAP verwerken (batch)?\n\nJa = map kiezen\nNee = enkel bestand")
    if is_folder:
        path = filedialog.askdirectory(title="Kies een map met audio")
    else:
        path = filedialog.askopenfilename(
            title="Kies een audiobestand",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.aif *.aiff *.ogg"),
                       ("Alle bestanden", "*.*")])
    root.destroy()
    return path or None


def _pause():
    try:
        input("\nDruk Enter om te sluiten...")
    except EOFError:
        pass


# ----------------------------------------------------------------------------
# Stap 0 -- Ingest + metadata (non-destructief: alleen lezen)
# ----------------------------------------------------------------------------
def read_metadata(path: str) -> dict:
    meta = {"artist": "", "title": "", "bpm": None}
    try:
        from mutagen import File as MutagenFile
        m = MutagenFile(path, easy=True)
        if m is not None:
            meta["artist"] = (m.get("artist", [""]) or [""])[0]
            meta["title"] = (m.get("title", [""]) or [""])[0]
            bpm = m.get("bpm", [None])
            if bpm and bpm[0]:
                try:
                    meta["bpm"] = float(bpm[0])
                except ValueError:
                    pass
    except Exception as e:
        print(f"[meta] tags niet leesbaar ({e}); val terug op bestandsnaam")
    stem = Path(path).stem
    if not meta["title"]:
        meta["title"] = stem
    if not meta["artist"] and " - " in stem:
        meta["artist"] = stem.split(" - ", 1)[0]
    return meta


def load_mix_mono(path: str, sr: int):
    import librosa
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y


def load_source_stereo(path: str):
    import librosa
    y, sr = librosa.load(path, sr=None, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return y, sr


# ----------------------------------------------------------------------------
# Stap 1a -- Beats/downbeats/segmenten  (allin1, met librosa-fallback)
# ----------------------------------------------------------------------------
def get_structure(path: str, backend: str):
    if backend == "allin1":
        try:
            import allin1
            r = allin1.analyze(path)
            return {
                "bpm": float(r.bpm),
                "beats": list(map(float, r.beats)),
                "downbeats": list(map(float, r.downbeats)),
                "segments": [
                    {"start": float(s.start), "end": float(s.end), "label": s.label}
                    for s in r.segments
                ],
            }
        except Exception as e:
            print(f"[structure] allin1 mislukte ({e}); val terug op librosa")
    import librosa
    y = load_mix_mono(path, CFG["analysis_sr"])
    tempo, beat_frames = librosa.beat.beat_track(
        y=y, sr=CFG["analysis_sr"], hop_length=CFG["hop_length"])
    beats = librosa.frames_to_time(
        beat_frames, sr=CFG["analysis_sr"], hop_length=CFG["hop_length"]).tolist()
    downbeats = beats[::4]  # ruwe 4/4-aanname
    dur = len(y) / CFG["analysis_sr"]
    return {"bpm": float(np.atleast_1d(tempo)[0]), "beats": beats,
            "downbeats": downbeats,
            "segments": [{"start": 0.0, "end": dur, "label": "unknown"}]}


# ----------------------------------------------------------------------------
# Stap 1b -- Density/sparseness op de MIX (geen separatie)
# ----------------------------------------------------------------------------
def analyze_density(y_mono, sr):
    import librosa
    hop = CFG["hop_length"]

    harm, perc = librosa.effects.hpss(y_mono)
    h_rms = librosa.feature.rms(y=harm, hop_length=hop)[0]
    p_rms = librosa.feature.rms(y=perc, hop_length=hop)[0]
    perc_ratio = p_rms / (h_rms + p_rms + 1e-9)

    chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr, hop_length=hop)
    cn = chroma / (chroma.sum(axis=0, keepdims=True) + 1e-9)
    chroma_entropy = -(cn * np.log(cn + 1e-9)).sum(axis=0) / np.log(12)

    S = np.abs(librosa.stft(y_mono, hop_length=hop)) ** 2
    Sn = S / (S.sum(axis=0, keepdims=True) + 1e-9)
    spec_entropy = -(Sn * np.log(Sn + 1e-9)).sum(axis=0) / np.log(S.shape[0])

    rms = librosa.feature.rms(y=y_mono, hop_length=hop)[0]
    rms_db = 20 * np.log10(rms + 1e-9)
    onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr, hop_length=hop)

    n = min(len(perc_ratio), len(chroma_entropy), len(spec_entropy),
            len(rms_db), len(onset_env))
    sl = slice(0, n)
    sparseness = 1.0 - 0.5 * (spec_entropy[sl] + chroma_entropy[sl])
    times = librosa.frames_to_time(np.arange(n), sr=sr, hop_length=hop)
    return {"times": times, "perc_ratio": perc_ratio[sl],
            "chroma_entropy": chroma_entropy[sl], "spec_entropy": spec_entropy[sl],
            "rms_db": rms_db[sl], "onset_env": onset_env[sl], "sparseness": sparseness}


def _bar_windows(downbeats, total_dur):
    db = list(downbeats) + [total_dur]
    return [(db[i], db[i + 1], i) for i in range(len(db) - 1) if db[i + 1] > db[i]]


def _mean_in(feat, times, t0, t1):
    m = (times >= t0) & (times < t1)
    if not np.any(m):
        return None
    return {k: float(np.mean(v[m])) for k, v in feat.items()
            if k != "times" and len(v) == len(times)}


# ----------------------------------------------------------------------------
# Stap 2 -- Kandidaten detecteren (rule-based, per type)
# ----------------------------------------------------------------------------
def detect_candidates(feat, structure, total_dur, wanted_types):
    cands = []
    bars = _bar_windows(structure["downbeats"], total_dur)
    times = feat["times"]

    bar_class = []
    for (t0, t1, bi) in bars:
        agg = _mean_in(feat, times, t0, t1)
        if agg is None:
            bar_class.append((bi, t0, t1, None, 0.0))
            continue
        spars = agg["sparseness"]
        label = None
        if spars >= CFG["sparseness_min"]:
            if ("break" in wanted_types
                    and agg["perc_ratio"] >= CFG["break_perc_ratio_min"]
                    and agg["chroma_entropy"] <= CFG["break_chroma_entropy_max"]):
                label = "break"
            elif ("solo" in wanted_types
                    and agg["perc_ratio"] <= CFG["solo_perc_ratio_max"]
                    and agg["chroma_entropy"] <= CFG["solo_chroma_entropy_max"]):
                label = "solo"
        bar_class.append((bi, t0, t1, label, spars))

    cands += _merge_bars(bar_class, "break", CFG["break_min_bars"])
    cands += _merge_bars(bar_class, "solo", CFG["solo_min_bars"])
    if "tail" in wanted_types:
        cands += _detect_tails(feat, structure, total_dur)
    return cands


def _merge_bars(bar_class, label, min_bars):
    out, run = [], []
    for entry in bar_class + [(None, None, None, "__end__", 0.0)]:
        bi, t0, t1, lab, spars = entry
        if lab == label:
            run.append(entry)
        else:
            if len(run) >= min_bars:
                score = float(np.mean([r[4] for r in run]))
                stem = "drums" if label == "break" else "other"
                out.append(Candidate(label, run[0][1], run[-1][2], run[0][0],
                                      run[-1][0], round(score, 3), stem,
                                      note=f"{len(run)} maten"))
            run = []
    return out


def _detect_tails(feat, structure, total_dur):
    times = feat["times"]
    rms_db = feat["rms_db"]
    onset = feat["onset_env"]
    onset_thr = float(np.percentile(onset, 70))
    out = []
    for seg_end in [s["end"] for s in structure["segments"]]:
        look = CFG["tail_lookback_bars"] * 2.0
        t_start = max(0.0, seg_end - look)
        m = (times >= t_start) & (times <= min(seg_end + 1.0, total_dur))
        if not np.any(m):
            continue
        idx = np.where(m)[0]
        local_peak = float(np.max(rms_db[idx]))
        on_idx = idx[onset[idx] >= onset_thr]
        if len(on_idx) == 0:
            continue
        last_onset_t = float(times[on_idx[-1]])
        after = idx[times[idx] > last_onset_t]
        end_t = None
        for j in after:
            if rms_db[j] <= CFG["tail_silence_db"]:
                end_t = float(times[j])
                break
        if end_t is None:
            end_t = float(times[idx[-1]])
        dur = end_t - last_onset_t
        if dur < CFG["tail_min_dur_s"]:
            continue
        drop = float(rms_db[after].min() - local_peak) if len(after) else 0.0
        if drop > CFG["tail_rms_drop_db"]:
            continue
        spars = float(np.mean(feat["sparseness"][idx]))
        if spars < CFG["sparseness_min"]:
            continue
        out.append(Candidate("tail", round(last_onset_t, 3), round(end_t, 3),
                             -1, -1, round(spars, 3), "auto",
                             note=f"decay {dur:.2f}s, drop {drop:.0f}dB"))
    return out


# ----------------------------------------------------------------------------
# Stap 3 -- Gerichte Demucs-separatie ALLEEN op kandidaat-vensters
# ----------------------------------------------------------------------------
def separate_window(src_stereo, src_sr, t0, t1, device=None):
    import torch
    import librosa
    from demucs.pretrained import get_model
    from demucs.apply import apply_model

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    i0 = max(0, int((t0 - CFG["pad_seconds"]) * src_sr))
    i1 = min(src_stereo.shape[1], int((t1 + CFG["pad_seconds"]) * src_sr))
    chunk = src_stereo[:, i0:i1]
    if src_sr != CFG["demucs_sr"]:
        chunk = np.stack([
            librosa.resample(chunk[c], orig_sr=src_sr, target_sr=CFG["demucs_sr"])
            for c in range(chunk.shape[0])])
    model = get_model(CFG["demucs_model"])
    model.to(device).eval()
    wav = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        est = apply_model(model, wav, device=device, progress=False)[0]
    est = est.cpu().numpy()
    return {model.sources[i]: est[i] for i in range(len(model.sources))}, CFG["demucs_sr"]


def pick_dominant_stem(stems: dict):
    e = {k: float(np.sqrt(np.mean(v ** 2))) for k, v in stems.items()}
    return max(e, key=e.get)


# ----------------------------------------------------------------------------
# Stap 4 -- Audio-aware snijden per type + export
# ----------------------------------------------------------------------------
def _apply_fade(audio, sr):
    n = int(CFG["fade_ms"] / 1000.0 * sr)
    if n > 0 and audio.shape[1] > 2 * n:
        ramp = np.linspace(0, 1, n)
        audio[:, :n] *= ramp
        audio[:, -n:] *= ramp[::-1]
    return audio


def _sanitize(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "", s).strip()
    s = re.sub(r"\s+", "-", s)
    return s or "x"


def _timestamp(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}m{s:05.2f}s".replace(".", "")


def build_filename(meta, cand, stem, res_tag, ext):
    artist = _sanitize(meta.get("artist") or "unknown")
    title = _sanitize(meta.get("title") or "untitled")
    pos = (f"bars{cand.start_bar:03d}-{cand.end_bar:03d}"
           if cand.start_bar >= 0 else "free")
    times = f"{_timestamp(cand.start)}-{_timestamp(cand.end)}"
    label = cand.type if cand.type != "tail" else f"tail-{stem}"
    return f"{artist}_{title}__{label}__{pos}__{times}__{res_tag}.{ext}"


def export_candidate(meta, cand, src_stereo, src_sr, out_dir,
                     fmt, bit_depth, samplerate, bitrate, device):
    import soundfile as sf
    import librosa

    stems, dsr = separate_window(src_stereo, src_sr, cand.start, cand.end, device)
    if cand.type == "break":
        stem_name = "drums"
    elif cand.type == "solo":
        stem_name = pick_dominant_stem({k: v for k, v in stems.items() if k != "drums"})
    else:
        stem_name = pick_dominant_stem(stems)
    audio = stems[stem_name].copy()

    if cand.type == "tail":
        env = np.sqrt(np.mean(audio ** 2, axis=0))
        thr = 10 ** (CFG["tail_silence_db"] / 20.0) * (env.max() + 1e-9)
        below = np.where(env < thr)[0]
        if len(below):
            audio = audio[:, : below[0] + int(0.02 * dsr)]

    audio = _apply_fade(audio, dsr)
    if samplerate and samplerate != dsr:
        audio = np.stack([librosa.resample(audio[c], orig_sr=dsr, target_sr=samplerate)
                          for c in range(audio.shape[0])])
        out_sr = samplerate
    else:
        out_sr = dsr

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt in ("wav", "flac"):
        subtype = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}.get(bit_depth, "PCM_24")
        res_tag = f"{bit_depth}b-{out_sr // 1000}k"
        fname = build_filename(meta, cand, stem_name, res_tag, fmt)
        sf.write(str(out_dir / fname), audio.T, out_sr, subtype=subtype)
    else:
        res_tag = f"{bitrate}k"
        fname = build_filename(meta, cand, stem_name, res_tag, fmt)
        tmp = out_dir / (fname + ".tmp.wav")
        sf.write(str(tmp), audio.T, out_sr, subtype="PCM_24")
        subprocess.run(["ffmpeg", "-y", "-i", str(tmp), "-b:a", f"{bitrate}k",
                        str(out_dir / fname)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tmp.unlink(missing_ok=True)
    print(f"    -> {fname}")
    return fname


# ----------------------------------------------------------------------------
# Per-bestand orkestratie
# ----------------------------------------------------------------------------
def print_candidates(cands):
    print(f"  {len(cands)} kandidaten:")
    print(f"  {'#':>2} {'type':<6} {'start':>8} {'end':>8} {'score':>6} {'stem':<7} note")
    for i, c in enumerate(cands):
        print(f"  {i:>2} {c.type:<6} {c.start:>8.2f} {c.end:>8.2f} "
              f"{c.score:>6.2f} {c.dominant_stem:<7} {c.note}")


def analyze_one(input_path, out_dir, types, beat_backend):
    print(f"  [1/3] structuur ({beat_backend}) ...")
    meta = read_metadata(input_path)
    structure = get_structure(input_path, beat_backend)
    print(f"        bpm~{structure['bpm']:.1f}, {len(structure['downbeats'])} downbeats")
    print("  [2/3] density-analyse op de mix ...")
    y = load_mix_mono(input_path, CFG["analysis_sr"])
    total_dur = len(y) / CFG["analysis_sr"]
    feat = analyze_density(y, CFG["analysis_sr"])
    print("  [3/3] kandidaten ...")
    cands = detect_candidates(feat, structure, total_dur, types)
    cands.sort(key=lambda c: c.score, reverse=True)
    print_candidates(cands)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    js = out / (Path(input_path).stem + ".candidates.json")
    js.write_text(json.dumps(
        {"meta": meta, "structure": {"bpm": structure["bpm"]},
         "candidates": [asdict(c) for c in cands]}, indent=2), encoding="utf-8")
    return meta, cands, js


def export_one(input_path, out_dir, types, index, fmt, bit_depth,
               samplerate, bitrate):
    js = Path(out_dir) / (Path(input_path).stem + ".candidates.json")
    if not js.exists():
        print(f"  geen kandidaten-JSON voor {Path(input_path).name}; sla over.")
        return
    data = json.loads(js.read_text(encoding="utf-8"))
    meta = data["meta"]
    cands = [Candidate(**c) for c in data["candidates"] if c["type"] in types]
    if index:
        cands = [cands[i] for i in index if 0 <= i < len(cands)]
    if not cands:
        print("  niets te exporteren.")
        return
    if fmt in ("mp3", "m4a") and bit_depth > 16:
        print("  LET OP: lossy export -- bit-depth telt niet; hogere resolutie "
              "voegt geen informatie toe.")
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    src, src_sr = load_source_stereo(input_path)
    track_out = Path(out_dir) / Path(input_path).stem
    print(f"  Demucs op {device} ({CFG['demucs_model']}), {len(cands)} venster(s) ...")
    for c in cands:
        print(f"  - {c.type} {c.start:.2f}-{c.end:.2f}s")
        try:
            export_candidate(meta, c, src, src_sr, track_out, fmt, bit_depth,
                             samplerate, bitrate, device)
        except Exception as e:
            print(f"    overgeslagen ({e})")


# ----------------------------------------------------------------------------
# CLI + interactieve (dubbelklik) modus
# ----------------------------------------------------------------------------
def _run_batch(files, out_dir, types, backend, do_export,
               fmt, bit_depth, samplerate, bitrate, index=None):
    for f in files:
        print(f"\n=== {f.name} ===")
        try:
            analyze_one(str(f), out_dir, types, backend)
            if do_export:
                export_one(str(f), out_dir, types, index, fmt, bit_depth,
                           samplerate, bitrate)
        except Exception as e:
            print(f"  FOUT bij {f.name}: {e}")


def interactive_main():
    print("=" * 62)
    print(" Sample Finder v1  --  sparse-section sample extractor")
    print("=" * 62)
    path = pick_input_dialog()
    if not path:
        print("Geen invoer gekozen.")
        _pause()
        return
    files = collect_inputs(path, recursive=False)
    if not files:
        print("Geen audiobestanden gevonden.")
        _pause()
        return
    base = Path(path).parent if Path(path).is_file() else Path(path)
    out_dir = str(base / "sample_finder_out")
    print(f"\n{len(files)} bestand(en). Output -> {out_dir}\n")

    # analyse eerst
    _run_batch(files, out_dir, ["break", "solo", "tail"], "librosa",
               do_export=False, fmt="wav", bit_depth=24, samplerate=None, bitrate=320)

    ans = input("\nKandidaten exporteren? (y/n): ").strip().lower()
    if ans == "y":
        fmt = (input("Formaat [wav]: ").strip() or "wav")
        try:
            bd = int(input("Bit-depth [24]: ").strip() or "24")
        except ValueError:
            bd = 24
        print()
        for f in files:
            print(f"=== export {f.name} ===")
            export_one(str(f), out_dir, ["break", "solo", "tail"], None,
                       fmt, bd, None, 320)
    print("\nKlaar.")
    _pause()


def main():
    if len(sys.argv) == 1:          # dubbelklik / geen argumenten
        interactive_main()
        return

    p = argparse.ArgumentParser(description="Sparse-section sample finder (v1)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptxt in [("analyze", "detecteer kandidaten"),
                          ("export", "separeer + snijd + schrijf"),
                          ("run", "analyze + export ineen")]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("input", help="bestand OF map")
        sp.add_argument("--out-dir", default="./out")
        sp.add_argument("--types", nargs="+", default=["break", "solo", "tail"],
                        choices=["break", "solo", "tail"])
        sp.add_argument("--recursive", action="store_true")
        sp.add_argument("--beat-backend", default="allin1",
                        choices=["allin1", "librosa"])
        if name in ("export", "run"):
            sp.add_argument("--index", nargs="*", type=int, default=None)
            sp.add_argument("--format", default="wav",
                            choices=["wav", "flac", "mp3", "m4a"])
            sp.add_argument("--bit-depth", type=int, default=24, choices=[16, 24, 32])
            sp.add_argument("--samplerate", type=int, default=None)
            sp.add_argument("--bitrate", type=int, default=320)

    args = p.parse_args()
    files = collect_inputs(args.input, args.recursive)
    if not files:
        print(f"Geen audiobestanden gevonden op: {args.input}")
        sys.exit(1)

    if args.cmd == "analyze":
        _run_batch(files, args.out_dir, args.types, args.beat_backend,
                   do_export=False, fmt="wav", bit_depth=24,
                   samplerate=None, bitrate=320)
    elif args.cmd == "export":
        for f in files:
            print(f"\n=== {f.name} ===")
            export_one(str(f), args.out_dir, args.types, args.index, args.format,
                       args.bit_depth, args.samplerate, args.bitrate)
    elif args.cmd == "run":
        _run_batch(files, args.out_dir, args.types, args.beat_backend,
                   do_export=True, fmt=args.format, bit_depth=args.bit_depth,
                   samplerate=args.samplerate, bitrate=args.bitrate, index=args.index)


if __name__ == "__main__":
    main()
```
