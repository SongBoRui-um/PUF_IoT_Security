"""
Final ML experiment on the frozen 2,048-common-challenge dataset.

Same experimental structure as the current paper:
A = same-device modeling / random row split
B = held-out-device generalization
C = baseline-to-stress transfer

Encodings:
binary challenge vector and standard Arbiter-PUF parity vector.

Models:
Transformer, MLP, Random Forest, Linear SVM.

For computational reproducibility on the 204,800-row dataset, neural
training uses batch_size=4096; 6 epochs; architecture dimensions remain fixed.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score

ROOT = Path(__file__).resolve().parent
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

df = pd.read_csv(ROOT / "puf_sim_dataset_16bit_2048.csv")
N_BITS = 16
N_DEV = int(df.Device_ID.nunique())

def chal_to_binary(c):
    return [int(x) for x in format(int(c), f"0{N_BITS}b")]

def chal_to_parity(c):
    bits = [1 - 2*int(x) for x in format(int(c), f"0{N_BITS}b")]
    phi = np.ones(N_BITS)
    running = 1.0
    for i in range(N_BITS-1, -1, -1):
        running *= bits[i]
        phi[i] = running
    return phi.tolist()

df["chal_bin"] = df["Challenge_Dec"].apply(chal_to_binary)
df["chal_par"] = df["Challenge_Dec"].apply(chal_to_parity)

scaler = StandardScaler()
env_scaled = scaler.fit_transform(df[["Temperature", "Voltage"]])
df["temp_s"] = env_scaled[:,0]
df["volt_s"] = env_scaled[:,1]

def build_features(sub, encoding):
    col = "chal_bin" if encoding == "binary" else "chal_par"
    chal = np.asarray(sub[col].tolist(), dtype=np.float32)
    env = sub[["temp_s","volt_s"]].to_numpy(dtype=np.float32)
    dev = (sub["Device_ID"].to_numpy(dtype=np.int64) - 1)
    X = np.hstack([chal, env]).astype(np.float32)
    y = sub["Response"].to_numpy(dtype=np.int64)
    return X, y, dev

class TransformerWithDeviceEmbed(nn.Module):
    def __init__(self, feat_dim, n_devices, d_model=32, nhead=4,
                 num_layers=2, dim_feedforward=64, emb_dim=8):
        super().__init__()
        self.dev_embed = nn.Embedding(n_devices, emb_dim)
        self.input_projection = nn.Linear(feat_dim + emb_dim, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead,
            dim_feedforward=dim_feedforward, batch_first=True
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, 2)

    def forward(self, x, dev):
        d = self.dev_embed(dev)
        h = torch.cat([x, d], dim=1).unsqueeze(1)
        h = self.input_projection(h)
        h = self.encoder(h).squeeze(1)
        return self.fc_out(h)

class MLPWithDeviceEmbed(nn.Module):
    def __init__(self, feat_dim, n_devices, hidden=64, emb_dim=8):
        super().__init__()
        self.dev_embed = nn.Embedding(n_devices, emb_dim)
        self.net = nn.Sequential(
            nn.Linear(feat_dim+emb_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, 2)
        )
    def forward(self, x, dev):
        return self.net(torch.cat([x, self.dev_embed(dev)], dim=1))

def train_torch(model, X, y, dev, epochs=6, lr=0.008):
    ds = TensorDataset(
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(y, dtype=torch.long),
        torch.tensor(dev, dtype=torch.long)
    )
    loader = DataLoader(ds, batch_size=4096, shuffle=True)
    opt = optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for xb, yb, db in loader:
            opt.zero_grad()
            loss = crit(model(xb, db), yb)
            loss.backward()
            opt.step()
    return model

def eval_torch(model, X, y, dev):
    model.eval()
    with torch.no_grad():
        pred = torch.argmax(
            model(torch.tensor(X, dtype=torch.float32),
                  torch.tensor(dev, dtype=torch.long)),
            dim=1
        ).numpy()
    return accuracy_score(y, pred) * 100

def classical(Xtr, ytr, dtr, Xte, yte, dte):
    oh_tr = np.eye(N_DEV, dtype=np.float32)[dtr]
    oh_te = np.eye(N_DEV, dtype=np.float32)[dte]
    Xtr2 = np.hstack([Xtr, oh_tr])
    Xte2 = np.hstack([Xte, oh_te])

    rf = RandomForestClassifier(
        n_estimators=50, random_state=42, n_jobs=-1
    )
    rf.fit(Xtr2, ytr)
    rf_acc = accuracy_score(yte, rf.predict(Xte2)) * 100

    rs = np.random.RandomState(0)
    idx = rs.choice(len(Xtr2), size=min(15000, len(Xtr2)), replace=False)
    svm = LinearSVC(max_iter=5000, dual="auto")
    svm.fit(Xtr2[idx], ytr[idx])
    svm_acc = accuracy_score(yte, svm.predict(Xte2)) * 100
    return rf_acc, svm_acc

def run_A(enc):
    X,y,d = build_features(df, enc)
    Xtr,Xte,ytr,yte,dtr,dte = train_test_split(
        X,y,d,test_size=.2,random_state=42,stratify=y
    )
    tf = train_torch(
        TransformerWithDeviceEmbed(X.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    mlp = train_torch(
        MLPWithDeviceEmbed(X.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    rf,svm = classical(Xtr,ytr,dtr,Xte,yte,dte)
    return eval_torch(tf,Xte,yte,dte), eval_torch(mlp,Xte,yte,dte), rf, svm

def run_B(enc):
    X,y,d = build_features(df, enc)
    gss = GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42)
    tr,te = next(gss.split(X,y,groups=d))
    Xtr,Xte,ytr,yte,dtr,dte = X[tr],X[te],y[tr],y[te],d[tr],d[te]
    assert not (set(dtr) & set(dte))
    # Unseen device IDs cannot use a learned target-device embedding.
    # Placeholder index 0 preserves the original experimental protocol.
    dte_model = np.zeros_like(dte)

    tf = train_torch(
        TransformerWithDeviceEmbed(X.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    mlp = train_torch(
        MLPWithDeviceEmbed(X.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    rf,svm = classical(Xtr,ytr,dtr,Xte,yte,dte_model)
    return eval_torch(tf,Xte,yte,dte_model), eval_torch(mlp,Xte,yte,dte_model), rf, svm

def run_C(enc):
    trdf = df[df.Temperature == 25.0]
    tedf = df[df.Temperature == 85.0]
    Xtr,ytr,dtr = build_features(trdf,enc)
    Xte,yte,dte = build_features(tedf,enc)

    tf = train_torch(
        TransformerWithDeviceEmbed(Xtr.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    mlp = train_torch(
        MLPWithDeviceEmbed(Xtr.shape[1], N_DEV),
        Xtr,ytr,dtr
    )
    rf,svm = classical(Xtr,ytr,dtr,Xte,yte,dte)
    return eval_torch(tf,Xte,yte,dte), eval_torch(mlp,Xte,yte,dte), rf, svm


import argparse, gc, json
parser=argparse.ArgumentParser()
parser.add_argument("--split", choices=["A","B","C"], required=True)
parser.add_argument("--encoding", choices=["binary","parity"], required=True)
args=parser.parse_args()

if args.split=="A":
    vals=run_A(args.encoding)
elif args.split=="B":
    vals=run_B(args.encoding)
else:
    vals=run_C(args.encoding)

row={
    "Split":args.split,
    "Encoding":args.encoding,
    "Transformer":vals[0],
    "MLP":vals[1],
    "RandomForest":vals[2],
    "LinearSVM":vals[3],
}
out_path=ROOT / f"ml_result_{args.split}_{args.encoding}_2048_final.csv"
pd.DataFrame([row]).to_csv(out_path,index=False)
print(json.dumps(row,indent=2))
