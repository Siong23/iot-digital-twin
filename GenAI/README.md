# GenAI — README

> **Goal:** a reproducible pipeline that turns IoT attack PCAPs (Kaggle dataset) into model-ready features and per-flow packet sequences, trains a generative model over flows, and *realizes* selected synthetic flows back into PCAPs that Zeek can parse.
>
> This repo focuses on producing three final artifacts you (and the synth engine) need:
>
> * `dataset/processed_dataset/processed_for_model/flows_master.parquet`
> * `dataset/processed_dataset/processed_for_model/seqs_index.json`
> * `dataset/processed_dataset/processed_for_model/seqs_<PCAP_ID>.npz` (many per-pcap NPZs)

> Read this file end-to-end. It explains prerequisites, each script’s role, step-by-step commands, how to train and use the gen‑AI, and safety/ethics guidance.

---

# Contents (repo layout)

```
GenAI/
├── Model/
│   ├── ctgan_model.py
│   ├── generate_and_synthesize.py
├── data preparation/
│   ├── 01_build_master_flow_table_minimal.py
│   ├── 02_tokenize_packet_sequences.py
│   ├── build_flow_packet_sequences_opt_all.py
│   ├── export_packets_all.py
│   ├── run_pipeline.sh
│   ├── run_zeek_on_pcaps.sh
│   ├── zeek_to_csv_minimal.py
├── README.md  (this file)
```

---

# 0 — IMPORTANT SAFETY & ETHICS (READ FIRST)

* The generated PCAPs **contain malicious-looking traffic patterns**. Only run, store, or share them in isolated lab environments (air-gapped or controlled virtual networks).
* Do **not** deploy generated PCAPs or run live network traffic that could cause harm or violate laws / terms of use.
* Use the pipeline for research, red-team testing in controlled settings, dataset augmentation for defenders, or education — never to attack production networks or third parties.

---

# 1 — Quick overview of what the pipeline does

1. **Run Zeek** on raw PCAPs to get protocol logs (`conn.log`, `dns.log`, `http.log`, etc.).
2. **Parse Zeek logs** into per-pcap CSVs and produce a minimal per-pcap `flows/<PCAP_ID>.csv` with the flow fields we use.
3. **Export per-packet CSVs** from every PCAP via `tshark` (frame-level timestamps, sizes, flags).
4. **Match packets → flows** to produce per-flow packet sequence JSONL files (`seqs/<PCAP_ID>_seqs.jsonl`).
5. **Tokenize & compress sequences** into per-pcap `.npz` files and write a `seqs_index.json` mapping UIDs → NPZ.
6. **Merge per-pcap flows** into one `flows_master.parquet`.
7. Use `ctgan_model.py` to train a CTGAN model on `flows_master.parquet` rows and save a pickled synthesizer.
8. Use `generate_and_synthesize.py` to pick a class (Normal / DDoS / …) and number of flows, sample those flows from the model (or fallback to sampling real flows), and synthesize a `.pcap` by realizing sequences (uses seqs_index + per-pcap npz to create realistic packet timings/sizes where available).
9. Run Zeek on the generated PCAP to produce logs you can use to train downstream classifiers.

---

# 2 — Prerequisites

**System tools**

* `zeek` (formerly Bro) in PATH
* `tshark` (Wireshark's CLI) in PATH
* `python3` (>=3.8 recommended)
* (optional, for synthesis) `scapy` installed for PCAP writing

**Python packages**

```bash
pip3 install pandas numpy pyarrow tqdm scikit-learn cloudpickle sdv scapy
```

* If you will train CTGAN using SDV/CTGAN, install `sdv` (and its requirements). On low-memory laptops you may sample and train on subsets.

**Hardware**

* CPU with enough RAM to process chunks — pipeline is chunked/resume-friendly, but building very large datasets still needs time and disk.
* If you want to train faster: GPU + PyTorch (CTGAN may use GPU if available).

---

# 3 — Dataset source note

This project expects you to supply a dataset of PCAPs (Kaggle IoT dataset). Place PCAPs under:

```
GenAI/dataset/PCAPs/<Attack>/<Count>/<Path>/*.pcap
```

Example:

```
dataset/PCAPs/Brute-force/1/DigitalBrokerServer/*.pcap
```

---

# 4 — Step-by-step: prepare the dataset (start to finish)

From the repo root (where `GenAI/` sits):

1. Place the Kaggle PCAP dataset into `GenAI/dataset/PCAPs/` with the structure above.

2. Make sure tools and python packages are installed (see prerequisites).

3. Run the full minimal pipeline:

```bash
cd "GenAI/data preparation"
chmod +x run_pipeline.sh
./run_pipeline.sh
```

`run_pipeline.sh` executes the following stage-by-stage:

* **1) run_zeek_on_pcaps.sh**
  Runs Zeek over `dataset/PCAPs/` and writes logs to:

  ```
  dataset/ZEEK_LOGS/<Attack>/<Count>/<Path>/zeek_logs/*.log
  ```

  *What it does:* if `conn.log` already exists under a pcap’s zeek_logs directory it will skip (unless you pass `--force`).

* **2) zeek_to_csv_minimal.py**
  Parses Zeek logs and writes:

  ```
  dataset/processed_dataset/per_pcap_csvs/<Attack>/<Count>/<Path>/conn.csv
  dataset/processed_dataset/flows/<PCAP_ID>.csv
  ```

  *What it does:* ensures a minimal per-pcap `conn.csv` and a simplified per-pcap flows CSV (columns the master builder expects).

* **3) export_packets_all.py**
  Runs `tshark` on PCAPs and writes per-pcap packet CSVs:

  ```
  dataset/processed_dataset/packets/packets_<PCAP_ID>.csv
  ```

  *What it does:* extracts frame number, epoch time, src/dst IP/ports, frame length, and some TCP analysis flags.

* **4) build_flow_packet_sequences_opt_all.py**
  Inputs: `packets_*.csv` and `per_pcap_csvs/*/conn.csv`
  Outputs:

  ```
  dataset/processed_dataset/seqs/<PCAP_ID>_seqs.jsonl
  ```

  *What it does:* maps per-packet rows to flows (via Zeek `uid`) and writes per-flow NDJSON with packet arrays (ts, size, direction, flags). This is the most I/O heavy step; it uses chunked reading and per-UID temporary files.

* **5) 02_tokenize_packet_sequences.py**
  Inputs: `seqs/*.jsonl`
  Outputs (per pcap):

  ```
  dataset/processed_dataset/processed_for_model/seqs_<PCAP_ID>.npz
  dataset/processed_dataset/processed_for_model/seqs_index.json
  ```

  *What it does:* tokenizes packet attributes (size bins, flag tokens), pads/trims sequences to `max_len`, and stores arrays into compressed NPZ files. It also creates a `seqs_index.json` that maps each uid → npz file and position.

* **6) 01_build_master_flow_table_minimal.py**
  Inputs: `dataset/processed_dataset/flows/*.csv`
  Outputs:

  ```
  dataset/processed_dataset/processed_for_model/flows_master.parquet
  ```

  *What it does:* concatenates per-pcap flow CSVs, computes simple derived features (bytes_total, pkts_total, bytes_per_pkt, time-of-day features, flow_size_bucket), and writes a single parquet master table used for modeling.

**When the pipeline completes, you should have:**

```
dataset/processed_dataset/processed_for_model/flows_master.parquet
dataset/processed_dataset/processed_for_model/seqs_index.json
dataset/processed_dataset/processed_for_model/seqs_<PCAP_ID>.npz   (many files)
```

---

# 5 — Short file-by-file explanation

### `run_zeek_on_pcaps.sh`

* Bash script that finds PCAPs under `dataset/PCAPs` and runs `zeek -r <pcap> local` inside per-pcap `dataset/ZEEK_LOGS/<Attack>/<Count>/<Path>/zeek_logs/`.
* Skips reprocessing if `conn.log` already exists (unless `--force`).

### `zeek_to_csv_minimal.py`

* Minimal parser that reads Zeek log files, writes `conn.csv` into `per_pcap_csvs` and writes a minimal per-pcap `flows/<PCAP_ID>.csv` used by the master builder. Keeps only columns needed downstream.

### `export_packets_all.py`

* Runs `tshark` fields extraction on each PCAP and writes `packets_<pcap_id>.csv`. Fields include `frame.time_epoch`, `ip.src`, `ip.dst`, ports, `frame.len`, and TCP analysis flags.

### `build_flow_packet_sequences_opt_all.py`

* Maps packet rows onto flows using the conn map (keys include IPs, ports, proto, timestamps). Writes per-pcap `_seqs.jsonl` where each line is a flow with its packet array.

### `02_tokenize_packet_sequences.py`

* Tokenizes packet sizes into bins, maps flags to tokens, pads/trims to `max_len`, and writes per-pcap `.npz` files plus `seqs_index.json`. These npz files contain arrays: `sizes`, `iats`, `dirs`, `flags`, `lens`, `uids`.

### `01_build_master_flow_table_minimal.py`

* Concatenates all per-pcap flows, derives simple aggregate features, buckets flows by size, and writes `flows_master.parquet`.

### `Model/ctgan_model.py`

* Training script for a CTGAN (SDV/CTGAN) on `flows_master.parquet`.
* Typical use: sample rows for metadata detection, fit CTGAN synthesizer, save model (cloudpickle), and export synthetic flows CSV.

### `Model/generate_and_synthesize.py`

* Interactive CLI: lists `class` values from `flows_master.parquet`, prompts for selection and number of flows, loads saved synthesizer model, samples flows conditioned on `class`, writes `synth_flows_sdv1.csv`, then *realizes* the sampled rows into a `.pcap` using `seqs_index.json` + the per-pcap `.npz` files (where sequences exist). Writes pcap under `dataset/processed_dataset/synth_pcaps/`.

---

# 6 — How to train and use the generative model

## Train

Example (simple):

```bash
python3 Model/ctgan_model.py \
  --parquet dataset/processed_dataset/processed_for_model/flows_master.parquet \
  --sample-n 100000 --epochs 50 --num-samples 1000 --save-model dataset/processed_dataset/processed_for_model/model.pkl
```

* The script trains CTGAN on a sample (or full dataset if sample size >= rows) and saves a pickled synthesizer to `model.pkl`. Adjust `--sample-n` on memory-limited machines.

## Generate & synthesize PCAP

Interactive:

```bash
python3 Model/generate_and_synthesize.py --model dataset/processed_dataset/processed_for_model/model.pkl
```

* The script lists classes (from the master parquet), you choose e.g. `2` for `DDoS`, then enter how many flows to generate (e.g., `200`).
* It samples that many flows conditioned on class (rejection sampling) and synthesizes `dataset/processed_dataset/synth_pcaps/synth_<class>_<ts>.pcap`.

**Then validate:**

```bash
zeek -r dataset/processed_dataset/synth_pcaps/synth_<class>_<ts>.pcap local
ls dataset/processed_dataset/synth_pcaps
ls -l *.log
```

* Check `conn.log`, `dns.log`, `http.log`, etc. If a protocol log you need is missing (e.g., `tls.log` or `mqtt` logs), you can extend the synthesizer with protocol templates or supply real protocol snippet templates.

---

# 7 — Troubleshooting / common problems

* **Zeek not found**: `command -v zeek` must succeed. On Debian/Ubuntu: `sudo apt install zeek` (or follow Zeek docs).
* **Tshark not found**: `tshark` must be in PATH. Install Wireshark/tshark.
* **Scapy warnings on Windows**: Scapy may warn about `winpcap`/`Npcap` if you run in Windows — those warnings are harmless for PCAP writing (it will still write files).
* **Long processing times**: `build_flow_packet_sequences_opt_all.py` is I/O heavy. Use larger `--chunksize` if you have memory; otherwise it reads in chunks to keep memory low.
* **JSONL stuck on one file**: if a particular `*_seqs.jsonl` stalls, inspect the corresponding `packets_*.csv` — malformed rows, IPv6 link-local addresses, or extremely large chunks may break filters. Run the script on that single PCAP with smaller chunksize and add logging.
* **Model sampling returns fewer rows than requested**: If a class is rare, rejection sampling may fail to find enough rows from the model. Fallback to sampling from `flows_master.parquet` (script does this). Consider training a conditional model or oversampling rare classes.
* **`TypeError` with pandas categorical fillna**: The master builder handles categorical dtypes by converting to object before fillna. If you see errors, update pandas or run the minimal `01_build_master_flow_table_minimal.py` (included).

---

# 8 — Best practices & tips

* Keep a copy of `seqs_index.json` and per-pcap `.npz`. They let you stream sequences for training and generation without loading everything into RAM.
* For reproducible synths: set seeds (`random.seed`, `numpy.random.seed`) in `generate_and_synthesize.py`.
* If you need real TLS or MQTT fidelity (client hello / server hello / MQTT connect/publish payloads), extract a small set of real templates from your PCAPs and add them to the synth script — Zeek will then populate `tls.log` / `mqtt_*.log` from synthesized PCAPs.
* Use an isolated VM or container for running Zeek/tshark and for storing generated PCAPs.

---

# 9 — Contributing / extending

* If you add new protocol templates (TLS/MQTT) or improve sequence realism (retransmission patterns, TCP seq/ack), please add tests or small sample PCAPs and update README with template usage.
* Pull requests with performance improvements (parallelizing per-pcap work, optional Dockerfile, or Windows support notes) are welcome.

---

# 10 — LICENSE & CITATION

* This educational framework is provided for learning purposes. Use responsibly and ethically in controlled environments only.

