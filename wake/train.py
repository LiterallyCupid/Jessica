
from pathlib import Path
import json, joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET = BASE_DIR / "test" / "dataset"
print("Dataset path:", DATASET.resolve())
OUT = BASE_DIR / "wake"
OUT=Path("wake")
OUT.mkdir(exist_ok=True)
CLASSES=["clap","snap","keyboard","voice","noise"]

def feat(x):
    if x.ndim>1: x=np.mean(x,axis=1)
    x=x.astype(np.float32)
    rms=float(np.sqrt(np.mean(x*x)))
    peak=float(np.max(np.abs(x)))
    crest=peak/max(rms,1e-9)
    zc=int(np.sum(np.diff(np.sign(x))!=0))
    energy=float(np.sum(x*x))
    mean=float(np.mean(x))
    std=float(np.std(x))
    mag=np.abs(np.fft.rfft(x))
    freqs=np.fft.rfftfreq(len(x),1/44100)
    if mag.sum()==0:
        centroid=0.0; bandwidth=0.0
    else:
        centroid=float((freqs*mag).sum()/mag.sum())
        bandwidth=float(np.sqrt((((freqs-centroid)**2)*mag).sum()/mag.sum()))
    return [rms,peak,crest,zc,energy,mean,std,centroid,bandwidth]

X=[]; y=[]
print("Jessica Wake Model Trainer")
for c in CLASSES:
    fs=sorted((DATASET/c).glob("*.npy")) if (DATASET/c).exists() else []
    print(f"{c}: {len(fs)}")
    for f in fs:
        X.append(feat(np.load(f)))
        y.append(c)
X=np.asarray(X); y=np.asarray(y)
Xtr,Xte,Ytr,Yte=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)
m=RandomForestClassifier(n_estimators=300,random_state=42,class_weight="balanced")
m.fit(Xtr,Ytr)
pred=m.predict(Xte)
print("Accuracy:",accuracy_score(Yte,pred))
print(classification_report(Yte,pred))
print(confusion_matrix(Yte,pred,labels=CLASSES))
joblib.dump(m,OUT/"wake_model.pkl")
with open(OUT/"labels.json","w") as f: json.dump(m.classes_.tolist(),f,indent=2)
print("Saved",OUT/"wake_model.pkl")
