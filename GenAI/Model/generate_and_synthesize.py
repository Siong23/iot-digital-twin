#!/usr/bin/env python3
"""
generate_and_synthesize.py

Interactive CLI:
  - Lists classes from flows_master.parquet
  - Prompts user to choose class and number of flows
  - Loads a saved CTGAN/SDV synthesizer (cloudpickle/pickle fallback)
  - Samples synthetic flows conditioned by class (via rejection sampling)
  - Writes synth CSV and builds a PCAP by realizing sequences from seqs_*.npz
  - Output PCAP saved to dataset/processed_dataset/synth_pcaps/

Usage:
  python3 dataset/scripts/generate_and_synthesize.py [--model MODEL_PATH] [--n_attempt_batch N]

Notes:
  - Assumes repo layout:
      dataset/processed_dataset/processed_for_model/flows_master.parquet
      dataset/processed_dataset/processed_for_model/seqs_index.json
      dataset/processed_dataset/processed_for_model/*.npz
      dataset/scripts/generate_and_synthesize.py (this file)
  - The model should be a pickled SDV/CTGAN synthesizer object that supports .sample(num_rows=...)
"""
import argparse, os, json, random, time, sys
from pathlib import Path
import pandas as pd
import numpy as np

# Try cloudpickle then pickle
try:
    import cloudpickle as cpickle
    PICKLE = cpickle
except Exception:
    import pickle as cpickle
    PICKLE = cpickle

# scapy
try:
    from scapy.all import Ether, IP, TCP, UDP, Raw, wrpcap
    from scapy.layers.dns import DNS, DNSQR, DNSRR
except Exception:
    print("ERROR: scapy not installed. Install with: pip install scapy")
    sys.exit(1)

# Paths (relative to repo root when script is run)
REPO_ROOT = Path.cwd()
PROCESSED = REPO_ROOT / "dataset" / "processed_dataset"
PROCESSED_MODEL = PROCESSED / "processed_for_model"
FLOWS_MASTER = PROCESSED_MODEL / "flows_master.parquet"
SEQS_INDEX = PROCESSED_MODEL / "seqs_index.json"
NPZ_DIR = PROCESSED_MODEL
OUT_SYNTH_CSV = PROCESSED_MODEL / "synth_flows_sdv1.csv"
OUT_PCAP_DIR = PROCESSED / "synth_pcaps"
OUT_PCAP_DIR.mkdir(parents=True, exist_ok=True)

# ---------- helper: load model ----------
def load_model(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Model file not found: {p}")
    try:
        with open(p, "rb") as f:
            obj = PICKLE.load(f)
        print(f"[model] Loaded synthesizer object from {p} using {PICKLE.__name__}")
        return obj
    except Exception as e:
        raise RuntimeError(f"Failed to load model {p}: {e}")

# ---------- helper: sample conditioned on class ----------
def sample_for_class(synth, target_class, n_needed, discrete_class_col="class", batch_size=None, max_iters=200):
    """
    Rejection sampling: sample batches from synthesizer and filter rows where class==target_class.
    synth must support synth.sample(num_rows=int) -> pandas.DataFrame
    """
    if batch_size is None:
        batch_size = max(1000, n_needed * 4)
    out_rows = []
    iters = 0
    while len(out_rows) < n_needed and iters < max_iters:
        iters += 1
        try:
            batch = synth.sample(num_rows=batch_size)
        except TypeError:
            # some synthesizers use sample(num_rows=...) or sample(n_rows)
            batch = synth.sample(n_rows=batch_size) if hasattr(synth, "sample") else None
        if batch is None or not hasattr(batch, "columns"):
            raise RuntimeError("Synthesizer.sample did not return a DataFrame-like result.")
        # ensure column exists
        if discrete_class_col not in batch.columns:
            # Maybe the synthesizer emits class under different name; fallback: cannot condition
            raise RuntimeError(f"Model output missing '{discrete_class_col}' column required for conditioning.")
        # select
        sel = batch[batch[discrete_class_col].astype(str) == str(target_class)]
        if not sel.empty:
            out_rows.append(sel)
        # safety jitter: if model frequently misses, try smaller batches or raise later
        if iters % 10 == 0:
            batch_size = min(batch_size * 2, 20000)
    if not out_rows:
        return pd.DataFrame(columns=[discrete_class_col])
    res = pd.concat(out_rows, ignore_index=True, sort=False)
    return res.head(n_needed)

# ---------- seqs utilities ----------
def load_seqs_index():
    if not SEQS_INDEX.exists():
        print("Warning: seqs_index.json not found:", SEQS_INDEX)
        return []
    with open(SEQS_INDEX, "r") as f:
        return json.load(f)

def load_npz_cache(npz_cache, npz_filename):
    p = NPZ_DIR / npz_filename
    if str(npz_filename) not in npz_cache:
        if not p.exists():
            return None
        npz_cache[str(npz_filename)] = np.load(str(p), allow_pickle=True)
    return npz_cache.get(str(npz_filename))

def get_sequence_by_uid(uid, seqs_index, npz_cache):
    ent = next((e for e in seqs_index if str(e.get('uid')) == str(uid)), None)
    if not ent: return None
    arr = load_npz_cache(npz_cache, ent['npz'])
    if arr is None: return None
    uids = arr['uids'].astype(str)
    idxs = np.where(uids == str(uid))[0]
    if len(idxs) == 0: return None
    idx = idxs[0]
    sizes = arr['sizes'][idx].tolist() if 'sizes' in arr else []
    iats  = arr['iats'][idx].tolist() if 'iats' in arr else []
    dirs  = arr['dirs'][idx].tolist() if 'dirs' in arr else []
    flags = arr['flags'][idx].tolist() if 'flags' in arr else []
    # trim using lens if available
    if 'lens' in arr:
        L = int(arr['lens'][idx])
        sizes = sizes[:L]; iats=iats[:L]; dirs=dirs[:L]; flags=flags[:L]
    else:
        if any(sizes):
            nz = [i for i,s in enumerate(sizes) if s and s>0]
            if nz:
                last = nz[-1] + 1
                sizes = sizes[:last]; iats=iats[:last]; dirs=dirs[:last]; flags=flags[:last]
    return {"sizes": sizes, "iats": iats, "dirs": dirs, "flags": flags}

# ---------- lightweight packet builders (similar to earlier script) ----------
def craft_tcp_handshake(src_ip, dst_ip, sport, dport, t0):
    p1 = Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="S",seq=1000); p1.time=t0
    p2 = Ether()/IP(src=dst_ip,dst=src_ip)/TCP(sport=dport,dport=sport,flags="SA",seq=2000,ack=1001); p2.time=t0+0.001
    p3 = Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="A",seq=1001,ack=2001); p3.time=t0+0.002
    return [p1,p2,p3]

def craft_http_flow(src_ip, dst_ip, sport, dport, sizes, iats, start_time):
    HTTP_REQ_TEMPLATE = b"GET /index.html HTTP/1.1\r\nHost: example.com\r\nUser-Agent: synth/1.0\r\n\r\n"
    HTTP_RESP_BODY = b"<html>ok</html>"
    HTTP_RESP_TEMPLATE = b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nContent-Type: text/html\r\n\r\n%s"
    pkts=[]
    t=start_time
    req_payload = HTTP_REQ_TEMPLATE
    req_size = sizes[0] if sizes else max(len(req_payload),60)
    req_load = req_payload + b"A"*(max(0,int(req_size)-len(req_payload)))
    p = Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="PA")/Raw(load=req_load); p.time=t; pkts.append(p)
    resp_body = HTTP_RESP_BODY; resp_payload = HTTP_RESP_TEMPLATE % (len(resp_body), resp_body)
    resp_size = sizes[1] if len(sizes)>1 else len(resp_payload)
    resp_load = resp_payload + b"B"*(max(0,int(resp_size)-len(resp_payload)))
    t += (iats[0] if iats and iats[0] else 0.001)
    p2 = Ether()/IP(src=dst_ip,dst=src_ip)/TCP(sport=dport,dport=sport,flags="PA")/Raw(load=resp_load); p2.time=t; pkts.append(p2)
    pfin = Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="FA"); pfin.time=t+0.001; pkts.append(pfin)
    return pkts

def craft_dns_flow(src_ip, dst_ip, sport, dport, start_time, qname="example.com"):
    q = Ether()/IP(src=src_ip,dst=dst_ip)/UDP(sport=sport,dport=dport)/DNS(rd=1,qd=DNSQR(qname=qname)); q.time=start_time
    a = Ether()/IP(src=dst_ip,dst=src_ip)/UDP(sport=dport,dport=sport)/DNS(id=q[DNS].id,qr=1,aa=1,qd=DNSQR(qname=qname),an=DNSRR(rrname=qname, rdata="1.2.3.4")); a.time=start_time+0.001
    return [q,a]

# realize flows -> pcap
def realize_flows_to_pcap(synth_df, out_pcap_path, nflows_limit=None):
    seqs_index = load_seqs_index()
    npz_cache = {}
    all_pkts=[]
    timeline = 0.0
    used=0
    for _, r in synth_df.iterrows():
        proto = str(r.get('proto','')).lower() if pd.notnull(r.get('proto')) else ""
        # pick a uid candidate (prefer using flow_size_bucket + proto) to reuse sequence if available
        # We try to find a real uid in flows_master that corresponds to the row's bucket/proto
        # Fallback: generate a synthetic small sequence
        uid = r.get('uid', None)
        seq=None
        if uid and seqs_index:
            seq = get_sequence_by_uid(uid, seqs_index, npz_cache)
        if seq is None:
            # fallback: random small seq
            L=random.randint(1,4)
            seq={"sizes":[random.randint(60,1200) for _ in range(L)],
                 "iats":[max(1e-5, random.expovariate(50)) for _ in range(L)],
                 "dirs":[0 if i%2==0 else 1 for i in range(L)],
                 "flags":["P"]*L}
        # ips/ports
        src_ip = f"10.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
        dst_ip = f"10.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
        sport = random.randint(1024,65535)
        service = str(r.get('service','')).lower() if pd.notnull(r.get('service')) else ""
        if proto.startswith("udp"):
            dport = 53 if ('dns' in service or (r.get('dns_q_count',0) and int(r.get('dns_q_count',0))>0)) else random.randint(1,65535)
        else:
            dport = 80 if ('http' in service or (r.get('http_count',0) and int(r.get('http_count',0))>0)) else random.randint(1,65535)
        start_t = timeline + random.uniform(1e-4,0.01)
        pkts_block=[]
        if proto.startswith("tcp"):
            pkts_block += craft_tcp_handshake(src_ip,dst_ip,sport,dport,start_t)
            if ('http' in service) or (int(r.get('http_count',0)) if pd.notnull(r.get('http_count')) else 0)>0:
                pkts_block += craft_http_flow(src_ip,dst_ip,sport,dport,seq['sizes'],seq['iats'],start_t+0.003)
            else:
                t = start_t+0.003
                for i,sz in enumerate(seq['sizes']):
                    load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-54))])
                    if seq['dirs'][i]==0:
                        p=Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="PA")/Raw(load=load)
                    else:
                        p=Ether()/IP(src=dst_ip,dst=src_ip)/TCP(sport=dport,dport=sport,flags="PA")/Raw(load=load)
                    p.time=t; pkts_block.append(p)
                    if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
                pfin=Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="FA"); pfin.time=t+0.001; pkts_block.append(pfin)
        elif proto.startswith("udp"):
            if (int(r.get('dns_q_count',0)) if pd.notnull(r.get('dns_q_count')) else 0)>0 or ('dns' in service):
                pkts_block += craft_dns_flow(src_ip,dst_ip,sport,dport,start_t)
            else:
                t = start_t
                for i,sz in enumerate(seq['sizes']):
                    load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-28))])
                    if seq['dirs'][i]==0:
                        p=Ether()/IP(src=src_ip,dst=dst_ip)/UDP(sport=sport,dport=dport)/Raw(load=load)
                    else:
                        p=Ether()/IP(src=dst_ip,dst=src_ip)/UDP(sport=dport,dport=sport)/Raw(load=load)
                    p.time=t; pkts_block.append(p)
                    if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
        else:
            # fallback TCP-like
            t = start_t
            for i,sz in enumerate(seq['sizes']):
                load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-40))])
                p = Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="PA")/Raw(load=load)
                p.time=t; pkts_block.append(p)
                if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
        if pkts_block:
            all_pkts.extend(pkts_block)
            timeline = max(getattr(p,"time",0) for p in pkts_block) + 0.01
            used += 1
        if nflows_limit and used >= nflows_limit:
            break
    if not all_pkts:
        raise RuntimeError("No packets produced.")
    all_pkts = sorted(all_pkts, key=lambda x: getattr(x,"time",0.0))
    wrpcap(str(out_pcap_path), all_pkts)

# ---------- main CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(PROCESSED / "processed_for_model" / "model.pkl"), help="Path to saved synthesizer (pickle/cloudpickle)")
    ap.add_argument("--n_attempt_batch", type=int, default=2000, help="Batch size used during rejection sampling")
    args = ap.parse_args()

    # 1) discover classes
    if not FLOWS_MASTER.exists():
        print("ERROR: flows_master.parquet not found at", FLOWS_MASTER)
        return
    master = pd.read_parquet(str(FLOWS_MASTER))
    if 'class' not in master.columns:
        print("ERROR: flows_master.parquet missing 'class' column.")
        return
    classes = sorted(master['class'].fillna("UNK").astype(str).unique().tolist())
    print("Select the traffic class you want to generate:")
    for i,c in enumerate(classes, start=1):
        print(f"  {i}. {c}")
    sel = input(f"Enter number (1-{len(classes)}): ").strip()
    try:
        idx = int(sel)-1
        if idx < 0 or idx >= len(classes):
            raise ValueError()
    except Exception:
        print("Invalid selection.")
        return
    chosen = classes[idx]
    howmany = input("How many flows do you want to generate? (e.g. 200): ").strip()
    try:
        n = int(howmany)
        if n <= 0: raise ValueError()
    except Exception:
        print("Invalid number.")
        return
    print(f"Generating {n} flows of class '{chosen}' ...")

    # 2) load model (if present). If loading fails, fallback to sampling real flows
    synth = None
    model_path = Path(args.model)
    if model_path.exists():
        try:
            synth = load_model(model_path)
        except Exception as e:
            print("Warning: failed to load model:", e)
            synth = None
    else:
        print("Model path not found, will sample real flows from flows_master.parquet.")

    # 3) produce synth_df
    if synth is None:
        # fallback: sample from master rows with chosen class
        candidates = master[master['class'].astype(str) == str(chosen)]
        if candidates.empty:
            print("No rows of that class found in flows_master.parquet.")
            return
        synth_df = candidates.sample(n=n, replace=True, random_state=42).reset_index(drop=True)
    else:
        print("Sampling from model via rejection sampling (may take a short while)...")
        # use rejection sampling
        # adapt batch size
        batch = max(1000, n * 4)
        sampled = sample_for_class(synth, chosen, n, discrete_class_col="class", batch_size=batch)
        if sampled is None or sampled.empty or len(sampled) < n:
            # try fallback to sample more aggressively
            print("Model sampling returned fewer rows than requested; falling back to sampling from master for remainder.")
            sampled = sampled if sampled is not None else pd.DataFrame()
            needed = n - len(sampled)
            if needed > 0:
                extra = master[master['class'].astype(str) == str(chosen)].sample(n=needed, replace=True, random_state=43)
                sampled = pd.concat([sampled, extra], ignore_index=True, sort=False)
        synth_df = sampled.reset_index(drop=True)

    # 4) Save synth CSV
    synth_df.to_csv(OUT_SYNTH_CSV, index=False)
    print("Saved synthetic flows CSV to:", OUT_SYNTH_CSV)

    # 5) realize to pcap
    out_pcap_path = OUT_PCAP_DIR / f"synth_{chosen}_{int(time.time())}.pcap"
    print("Realizing flows to pcap:", out_pcap_path)
    # call internal realize function
    try:
        # small wrapper to create pcap in place
        seqs_index = load_seqs_index()
        npz_cache = {}
        all_pkts = []
        timeline = 0.0
        used = 0
        for _, row in synth_df.iterrows():
            # reuse logic from realize_flows_to_pcap but write inlined to allow out_pcap_path variable
            proto = str(row.get('proto','')).lower() if pd.notnull(row.get('proto')) else ""
            uid = row.get('uid', None)
            seq = get_sequence_by_uid(uid, seqs_index, npz_cache) if uid else None
            if seq is None:
                L = random.randint(1,4)
                seq={"sizes":[random.randint(60,1200) for _ in range(L)],
                     "iats":[max(1e-5, random.expovariate(50)) for _ in range(L)],
                     "dirs":[0 if i%2==0 else 1 for i in range(L)],
                     "flags":["P"]*L}
            src_ip = f"10.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            dst_ip = f"10.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            sport = random.randint(1024,65535)
            service = str(row.get('service','')).lower() if pd.notnull(row.get('service')) else ""
            if proto.startswith("udp"):
                dport = 53 if ('dns' in service or (row.get('dns_q_count',0) and int(row.get('dns_q_count',0))>0)) else random.randint(1,65535)
            else:
                dport = 80 if ('http' in service or (row.get('http_count',0) and int(row.get('http_count',0))>0)) else random.randint(1,65535)
            start_t = timeline + random.uniform(1e-4,0.01)
            pkts_block=[]
            if proto.startswith("tcp"):
                pkts_block += craft_tcp_handshake(src_ip,dst_ip,sport,dport,start_t)
                if ('http' in service) or (int(row.get('http_count',0)) if pd.notnull(row.get('http_count')) else 0)>0:
                    pkts_block += craft_http_flow(src_ip,dst_ip,sport,dport,seq['sizes'],seq['iats'],start_t+0.003)
                else:
                    t = start_t+0.003
                    for i,sz in enumerate(seq['sizes']):
                        load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-54))])
                        if seq['dirs'][i]==0:
                            p=Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="PA")/Raw(load=load)
                        else:
                            p=Ether()/IP(src=dst_ip,dst=src_ip)/TCP(sport=dport,dport=sport,flags="PA")/Raw(load=load)
                        p.time=t; pkts_block.append(p)
                        if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
                    pfin=Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="FA"); pfin.time=t+0.001; pkts_block.append(pfin)
            elif proto.startswith("udp"):
                if (int(row.get('dns_q_count',0)) if pd.notnull(row.get('dns_q_count')) else 0)>0 or ('dns' in service):
                    pkts_block += craft_dns_flow(src_ip,dst_ip,sport,dport,start_t)
                else:
                    t = start_t
                    for i,sz in enumerate(seq['sizes']):
                        load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-28))])
                        if seq['dirs'][i]==0:
                            p=Ether()/IP(src=src_ip,dst=dst_ip)/UDP(sport=sport,dport=dport)/Raw(load=load)
                        else:
                            p=Ether()/IP(src=dst_ip,dst=src_ip)/UDP(sport=dport,dport=sport)/Raw(load=load)
                        p.time=t; pkts_block.append(p)
                        if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
            else:
                t = start_t
                for i,sz in enumerate(seq['sizes']):
                    load = bytes([random.randint(0,255) for _ in range(max(0,int(sz)-40))])
                    p=Ether()/IP(src=src_ip,dst=dst_ip)/TCP(sport=sport,dport=dport,flags="PA")/Raw(load=load); p.time=t; pkts_block.append(p)
                    if i < len(seq['iats']): t+=max(1e-6,float(seq['iats'][i]) if seq['iats'][i] else 0.001)
            if pkts_block:
                # append to global list
                if 'all_pkts' not in locals():
                    all_pkts = []
                all_pkts.extend(pkts_block)
                timeline = max(getattr(p,"time",0) for p in pkts_block) + 0.01
                used += 1
        # write PCAP
        if not all_pkts:
            print("No packets to write.")
            return
        all_pkts = sorted(all_pkts, key=lambda x: getattr(x,"time",0.0))
        from scapy.all import wrpcap
        wrpcap(str(out_pcap_path), all_pkts)
        print("Wrote synthetic PCAP:", out_pcap_path, "flows:", used, "packets:", len(all_pkts))
    except Exception as e:
        print("Failed to realize PCAP:", e)
        return

    print("\nNext step: run Zeek on the generated pcap:")
    print(f"  zeek -r {out_pcap_path} local")
    print("Then process the logs through your usual preprocessing pipeline.")

if __name__ == "__main__":
    main()
