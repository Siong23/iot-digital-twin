#!/usr/bin/env python3
# ctgan_model.py
import torch
import pandas as pd
import argparse
import os
import sys
import traceback
from sdv.metadata import SingleTableMetadata
from sdv.single_table import CTGANSynthesizer

# Try to import cloudpickle for safer serialization; fallback to pickle if missing
try:
    import cloudpickle as cpickle
    _PICKLE_MODULE = 'cloudpickle'
except Exception:
    import pickle as cpickle
    _PICKLE_MODULE = 'pickle'

def save_model(synth, pkl_path: str, also_native_save: str = None):
    """
    Save the synthesizer:
      - If also_native_save is provided, attempt synth.save(also_native_save)
      - Then attempt to serialize with cloudpickle (preferred) to pkl_path
      - Falls back to builtin pickle if cloudpickle unavailable.
    """
    # 1) attempt native synthesizer.save(dir) if requested and available
    if also_native_save:
        try:
            # synth.save may expect a directory path
            print(f"[save_model] Attempting native synthesizer.save('{also_native_save}') ...")
            synth.save(also_native_save)
            print(f"[save_model] Native synthesizer.save succeeded: {also_native_save}")
        except Exception as e:
            print(f"[save_model] Native synthesizer.save failed: {e}")
            # do not abort — we will try pickling below

    # 2) attempt pickling via cloudpickle/pickle
    try:
        print(f"[save_model] Serializing synthesizer with {_PICKLE_MODULE} -> {pkl_path} ...")
        with open(pkl_path, "wb") as fo:
            cpickle.dump(synth, fo)
        print(f"[save_model] Model serialized to: {pkl_path}")
    except Exception as e:
        print("[save_model] ERROR: failed to pickle synthesizer:", e)
        traceback.print_exc()
        raise

def main(args):
    # GPU check
    use_cuda = torch.cuda.is_available()
    print("CUDA available:", use_cuda)
    if use_cuda:
        try:
            print("GPU:", torch.cuda.get_device_name(0))
        except Exception:
            pass

    # Paths
    master_parquet = args.parquet
    out_csv = args.out
    save_model_path = args.save_model  # may be None

    # Columns & discrete (adapt if your parquet differs)
    cols = [
        'proto','service','duration',
        'orig_bytes','resp_bytes',
        'orig_pkts','resp_pkts',
        'dns_q_count','http_count','tls_count',
        'class','flow_size_bucket'
    ]
    discrete = ['proto', 'service', 'class', 'flow_size_bucket']

    # Load
    print("Loading", master_parquet, "...")
    df = pd.read_parquet(master_parquet)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing expected columns in parquet: {missing}")

    df2 = df[cols].copy()

    # Robust handling: categorical -> str fill "NA"; numeric -> numeric fill 0
    numeric_cols = [c for c in cols if c not in discrete]

    for c in discrete:
        if pd.api.types.is_categorical_dtype(df2[c]):
            df2[c] = df2[c].astype(object)
        df2[c] = df2[c].fillna("NA").astype(str)

    for c in numeric_cols:
        df2[c] = pd.to_numeric(df2[c], errors='coerce').fillna(0)

    print("Prepared dataframe shape:", df2.shape)
    print("Dtypes:")
    print(df2.dtypes)

    # Sample for training to avoid OOM on laptop
    sample_n = min(args.sample_n, len(df2))
    if sample_n < len(df2):
        print(f"Sampling {sample_n:,} rows for training (of {len(df2):,}) — faster iteration.")
        df_sample = df2.sample(n=sample_n, random_state=42).reset_index(drop=True)
    else:
        print("Using full dataset for training (may be slow).")
        df_sample = df2

    # Build metadata (SDV 1.x API expects dataframe positional arg)
    print("Detecting metadata from sample...")
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df_sample)

    # Create CTGAN synth (SDV 1.x). Use cuda if available.
    print(f"Initializing CTGANSynthesizer (epochs={args.epochs}, cuda={use_cuda}) ...")
    synth = CTGANSynthesizer(
        metadata=metadata,
        epochs=args.epochs,
        verbose=True,
        cuda=use_cuda
    )

    # Fit
    print("Fitting synthesizer (this will show progress)...")
    synth.fit(df_sample)

    # Sample synthetic rows
    print(f"Sampling {args.num_samples} synthetic rows...")
    samples = synth.sample(num_rows=args.num_samples)
    samples.to_csv(out_csv, index=False)
    print("Wrote synthetic flows to:", out_csv)

    # Save model if requested
    if save_model_path:
        # decide native-save directory (if user provided a path ending in .pkl we'll still try to save native to dirname)
        native_dir = None
        if save_model_path.endswith(".pkl"):
            native_dir = os.path.splitext(save_model_path)[0] + "_sdv_native"
        else:
            native_dir = save_model_path + "_sdv_native"
        try:
            save_model(synth, save_model_path, also_native_save=native_dir)
        except Exception as e:
            print("Failed to save model:", e)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", default="dataset/processed_dataset/processed_for_model/flows_master.parquet",
                   help="Path to flows_master.parquet")
    p.add_argument("--out", default="dataset/processed_dataset/processed_for_model/synth_flows_sdv1.csv",
                   help="Output CSV path for synthetic rows")
    p.add_argument("--sample-n", type=int, default=100000,
                   help="Number of rows to sample for metadata detection & training (default 100k)")
    p.add_argument("--epochs", type=int, default=50, help="Epochs for CTGAN training (default 50)")
    p.add_argument("--num-samples", type=int, default=1000, help="Number of synthetic rows to generate")
    p.add_argument("--save-model", type=str, default=None,
                   help="Optional: path to save the trained model as .pkl (e.g. model.pkl). Also attempts synthesizer.save(native_dir).")
    args = p.parse_args()
    main(args)
