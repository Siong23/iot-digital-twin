#!/usr/bin/env python3
# 02_tokenize_packet_sequences.py
import json, os
from pathlib import Path
import numpy as np
from tqdm import tqdm
import argparse

ROOT = Path("dataset/processed_dataset")
SEQS_DIR = ROOT / "seqs"
OUT_DIR = ROOT / "processed_for_model"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# discretize packet sizes into bins (you can adjust bins)
SIZE_BINS = [0, 64, 128, 256, 512, 1024, 1500, 3000, 10000]
def size_to_bin(x):
    for i,b in enumerate(SIZE_BINS):
        if x <= b: return i
    return len(SIZE_BINS)

def flag_to_token(flags):
    # simple mapping: common flags combinations
    if flags is None: return 0
    f = str(flags)
    # reduce to a small token set
    if 'S' in f and 'A' not in f: return 1
    if 'S' in f and 'A' in f: return 2
    if 'F' in f: return 3
    if 'R' in f: return 4
    if 'P' in f: return 5
    return 6  # other

def process_one(path, max_len=200, pad=True):
    rows = []
    with open(path,'r') as fi:
        for line in fi:
            obj = json.loads(line)
            uid = obj['uid']
            pkts = obj['packets']
            # build arrays
            sizes = np.array([p.get('size',0) for p in pkts], dtype=np.int32)
            iats = np.array([p.get('iat',0) for p in pkts], dtype=np.float32)
            dirs = np.array([p.get('direction',0) for p in pkts], dtype=np.int8)
            flags = np.array([flag_to_token(p.get('flags','')) for p in pkts], dtype=np.int8)
            # discretize sizes
            size_bins = np.array([size_to_bin(int(s)) for s in sizes], dtype=np.int8)
            length = len(sizes)
            # trim/pad
            if length > max_len:
                sizes = sizes[:max_len]; iats = iats[:max_len]; dirs = dirs[:max_len]; flags = flags[:max_len]; size_bins = size_bins[:max_len]
                length = max_len
            if pad:
                pad_len = max_len - length
                sizes = np.pad(sizes, (0,pad_len))
                iats  = np.pad(iats, (0,pad_len))
                dirs  = np.pad(dirs, (0,pad_len), constant_values=-1)
                flags = np.pad(flags, (0,pad_len), constant_values=-1)
                size_bins = np.pad(size_bins, (0,pad_len), constant_values=-1)
            rows.append({
                "uid": uid, "len": length, "sizes": sizes, "iats": iats, "dirs": dirs, "flags": flags, "size_bins": size_bins
            })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-len", type=int, default=200)
    parser.add_argument("--pad", action="store_true")
    args = parser.parse_args()
    all_files = sorted(SEQS_DIR.glob("*_seqs.jsonl"))
    print("Found seqs files:", len(all_files))
    master_index = []
    # We'll save all sequences into a compressed .npz per-file (append-style)
    for sf in tqdm(all_files):
        pcap_id = sf.stem.replace("_seqs","")
        rows = process_one(sf, max_len=args.max_len, pad=args.pad)
        if not rows: continue
        # stack arrays
        sizes = np.stack([r['sizes'] for r in rows])
        iats  = np.stack([r['iats'] for r in rows])
        dirs  = np.stack([r['dirs'] for r in rows])
        flags = np.stack([r['flags'] for r in rows])
        lens  = np.array([r['len'] for r in rows], dtype=np.int32)
        uids  = [r['uid'] for r in rows]
        outp = OUT_DIR / f"seqs_{pcap_id}.npz"
        np.savez_compressed(outp, sizes=sizes, iats=iats, dirs=dirs, flags=flags, lens=lens, uids=np.array(uids))
        master_index.extend([{"pcap_id":pcap_id,"uid":u,"npz":str(outp.name),"len":int(l)} for u,l in zip(uids,lens)])
    # write index
    import json
    with open(OUT_DIR / "seqs_index.json","w") as fo:
        json.dump(master_index, fo)
    print("Wrote seqs_index.json and npz files in", OUT_DIR)

if __name__ == "__main__":
    main()

