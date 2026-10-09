"""
Final functional authentication experiment for the frozen 2,048-challenge dataset.

Protocol implemented from the paper:
    1. Select a deterministic 1,920-bit response vector from the 2,048 common
       baseline challenges (first 1,920 challenges in ascending challenge order).
    2. Generate random 128-bit enrollment message M.
    3. Repeat each M bit 15 times -> 1,920-bit codeword C.
    4. Helper data H = W XOR C.
    5. At authentication, W' XOR H is majority-decoded to M'.
    6. HKDF-SHA256 derives a 32-byte Ed25519 seed from M'.
    7. Ed25519 signs Device_ID + fresh 256-bit nonce + protocol context.
    8. Server verifies with enrolled public key.

This is a functional simulation, not a formal fuzzy-extractor security proof.
"""
from pathlib import Path
import hashlib, secrets, base64
import numpy as np
import pandas as pd

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
except ImportError:
    raise SystemExit(
        "Missing dependency: cryptography. Install with: python -m pip install cryptography"
    )

ROOT = Path(__file__).resolve().parent
df = pd.read_csv(ROOT / "puf_sim_dataset_16bit_2048.csv")

CHALLENGES = sorted(df["Challenge_Dec"].unique())[:1920]
assert len(CHALLENGES) == 1920

def hkdf_seed(M):
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"PUF-ZTA-Ed25519-v1",
    ).derive(bytes(M))

def make_codeword(M, repetition=15):
    return np.repeat(np.asarray(M, dtype=np.uint8), repetition)

def majority_decode(bits, repetition=15):
    bits = np.asarray(bits, dtype=np.uint8)
    blocks = bits.reshape(-1, repetition)
    return (blocks.sum(axis=1) >= (repetition // 2 + 1)).astype(np.uint8)

def response_vector(device, temp):
    g = df[
        (df.Device_ID == device) &
        (df.Temperature == temp) &
        (df.Challenge_Dec.isin(CHALLENGES))
    ].sort_values("Challenge_Dec")
    assert len(g) == 1920
    return g.Response.to_numpy(dtype=np.uint8)

records=[]
rng = np.random.RandomState(4242)

for dev in sorted(df.Device_ID.unique()):
    W = response_vector(dev, 25.0)

    # Deterministic random enrollment message for reproducibility.
    M = rng.randint(0, 2, size=128, dtype=np.uint8)
    C = make_codeword(M, 15)
    H = np.bitwise_xor(W, C)

    seed = hkdf_seed(M)
    private = Ed25519PrivateKey.from_private_bytes(seed)
    public = private.public_key()

    Wp = response_vector(dev, 85.0)
    Mprime = majority_decode(np.bitwise_xor(Wp, H), 15)

    seed_prime = hkdf_seed(Mprime)
    private_prime = Ed25519PrivateKey.from_private_bytes(seed_prime)
    public_prime = private_prime.public_key()

    nonce = rng.bytes(32)
    message = (
        f"PUF-ZTA-v1|device={dev}|".encode()
        + nonce
    )
    signature = private_prime.sign(message)

    try:
        public.verify(signature, message)
        signature_ok = True
    except Exception:
        signature_ok = False

    enrolled_pub = public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    reconstructed_pub = public_prime.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    records.append({
        "Device_ID": dev,
        "M_reconstructed": bool(np.array_equal(M, Mprime)),
        "key_seed_match": bool(seed == seed_prime),
        "public_key_match": bool(enrolled_pub == reconstructed_pub),
        "signature_verified": bool(signature_ok),
        "hamming_M": int(np.sum(M != Mprime)),
        "nonce_bits": 256
    })

out = pd.DataFrame(records)
out.to_csv(ROOT / "authentication_results_2048_final.csv", index=False)

print("="*70)
print("FINAL AUTHENTICATION RESULTS")
print("="*70)
print(f"Trials                 : {len(out)}")
print(f"Message reconstruction : {out.M_reconstructed.sum()}/{len(out)}")
print(f"Key match              : {out.key_seed_match.sum()}/{len(out)}")
print(f"Public-key match       : {out.public_key_match.sum()}/{len(out)}")
print(f"Signature verification : {out.signature_verified.sum()}/{len(out)}")
print(f"Mean M Hamming errors  : {out.hamming_M.mean():.2f} / 128")
print("="*70)
