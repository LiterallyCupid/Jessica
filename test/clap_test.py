from __future__ import annotations
import csv,time
from pathlib import Path
import numpy as np
import sounddevice as sd
SAMPLE_RATE=44100;BLOCK_MS=10;CHANNELS=1;MIN_RMS=0.008;COOLDOWN=0.4
DATASET=Path("dataset");CSV_FILE=DATASET/"dataset.csv";MODES=["clap","snap","keyboard","door","voice","noise"]
DATASET.mkdir(exist_ok=True)
for m in MODES:(DATASET/m).mkdir(exist_ok=True)
if not CSV_FILE.exists():
    with open(CSV_FILE,"w",newline="") as f: csv.writer(f).writerow(["file","label","rms","peak","crest","width","duration_ms","zero_crossings"])
def block_samples(): return int(SAMPLE_RATE*BLOCK_MS/1000)
def mono(x): return np.mean(x,axis=1) if x.ndim>1 else x
def rms(x): x=mono(x).astype(np.float64); return float(np.sqrt(np.mean(x**2)))
def zero_crossings(x): x=mono(x); return int(np.sum(np.diff(np.sign(x))!=0))
def width(x,p): x=mono(x); return int(np.sum(np.abs(x)>p*0.5))
def duration_ms(w): return w*1000/SAMPLE_RATE
mode=0; last=0.0
count={m:len(list((DATASET/m).glob("*.npy"))) for m in MODES}
print("Jessica Dataset Recorder")
print("Current mode:",MODES[mode])
try:
    with sd.InputStream(samplerate=SAMPLE_RATE,channels=CHANNELS,dtype="float32",blocksize=block_samples()) as stream:
        while True:
            data,overflow=stream.read(block_samples())
            if overflow: continue
            level=rms(data)
            if level<MIN_RMS: continue
            now=time.monotonic()
            if now-last<COOLDOWN: continue
            last=now
            peak=float(np.max(np.abs(data))); crest=peak/max(level,1e-9); w=width(data,peak); dur=duration_ms(w); zc=zero_crossings(data)
            label=MODES[mode]; count[label]+=1
            fn=f"{label}_{count[label]:04d}.npy"; fp=DATASET/label/fn
            np.save(fp,data)
            with open(CSV_FILE,"a",newline="") as f: csv.writer(f).writerow([str(fp),label,level,peak,crest,w,dur,zc])
            print(f"[{label}] saved {fn}")
            cmd=input("Enter=continue, m=change mode: ").strip().lower()
            if cmd=="m":
                for i,m in enumerate(MODES,1): print(i,m)
                try:
                    s=int(input("Choice: "))
                    if 1<=s<=len(MODES): mode=s-1; print("Mode:",MODES[mode])
                except: pass
except KeyboardInterrupt:
    print("Stopped")
