#!/usr/bin/env python3
"""
npp_publisher.py

CSV->MQTT publisher for NuclearPowerPlantAccidentData:
 - Uses the provided canonical short names (TIME, TAVG, THA, ... WFLB)
 - Supports speed multiplier, loop, optional small random noise, and publish-by-csv-time
"""

import argparse
import json
import logging
import time
import random
from datetime import datetime, timedelta
import pandas as pd
import paho.mqtt.client as mqtt
from dateutil import parser as dateparser

# ---------------------------------------------------------------------
# COLUMN NAMES (short-codes in the order you provided)
COLS = [
 "TIME","TAVG","THA","THB","TCA","TCB","WRCA","WRCB","PSGA","PSGB",
 "WFWA","WFWB","WSTA","WSTB","VOL","LVPZ","VOID","WLR","WUP","HUP",
 "HLW","WHPI","WECS","QMWT","LSGA","LSGB","QMGA","QMGB","NSGA","NSGB",
 "TBLD","WTRA","WTRB","TSAT","QRHR","LVCR","SCMA","SCMB","FRCL","PRB",
 "PRBA","TRB","LWRB","DNBR","QFCL","WBK","WSPY","WCSP","HTR","MH2",
 "CNH2","RHBR","RHMT","RHFL","RHRD","RH","PWNT","PWR","TFSB","TFPK",
 "TF","TPCT","WCFT","WLPI","WCHG","RM1","RM2","RM3","RM4","RC87",
 "RC131","STRB","STSG","STTB","RBLK","SGLK","DTHY","DWB","P","WRLA",
 "WRLB","WLD","MBK","EBK","TKLV","FRZR","MDBR","MCRT","MGAS","TDBR",
 "TSLP","TCRT","PPM","RRCA","RRCB","RRCO","WFLB"
]
# ---------------------------------------------------------------------

def make_args():
    p = argparse.ArgumentParser(description="Publish NPP CSV rows to MQTT")
    p.add_argument("--csv", default="/mnt/data/1.csv", help="CSV file path")
    p.add_argument("--broker", default="192.168.20.2", help="MQTT broker IP")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--user", default="admin")
    p.add_argument("--password", default="admin123")
    p.add_argument("--topic", default="npp/simulation/data")
    p.add_argument("--speed", type=float, default=1.0, help="Speed multiplier (1.0 = realtime using TIME column)")
    p.add_argument("--loop", action="store_true", help="Loop CSV when finished")
    p.add_argument("--use-csv-time", action="store_true", help="Use TIME column to pace messages (seconds)")
    p.add_argument("--stamp-now", action="store_true", help="Replace TIME values with current time (ISO) on publish")
    p.add_argument("--jitter", type=float, default=0.0, help="max fractional jitter of value (e.g. 0.01 = ±1%)")
    p.add_argument("--log", default="npp_sim.log")
    return p.parse_args()

def setup_logging(fn):
    logging.basicConfig(filename=fn, level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    logging.getLogger().addHandler(logging.StreamHandler())

# MQTT helper
class MqttPublisher:
    def __init__(self, host, port, user, password):
        self.client = mqtt.Client(client_id=f"npp-sim-{int(time.time())}")
        self.client.username_pw_set(user, password)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.host = host; self.port = port
        self._connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected to MQTT broker")
            self._connected = True
        else:
            logging.warning("MQTT connect returned rc=%s", rc)

    def on_disconnect(self, client, userdata, rc):
        logging.warning("MQTT disconnected rc=%s", rc)
        self._connected = False

    def connect(self):
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            # wait briefly for connect
            t0 = time.time()
            while not self._connected and time.time() - t0 < 5:
                time.sleep(0.1)
        except Exception as e:
            logging.exception("MQTT connect failed: %s", e)

    def publish(self, topic, payload, qos=0, retain=False):
        if not self._connected:
            logging.debug("Not connected to broker; attempting reconnect")
            try:
                self.client.reconnect()
            except Exception:
                time.sleep(1)
                return False
        try:
            r = self.client.publish(topic, payload, qos=qos, retain=retain)
            r.wait_for_publish()  # block until pub complete
            return True
        except Exception as e:
            logging.exception("Publish error: %s", e)
            return False

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

def load_csv(path):
    # try reading with header; if headers don't match, fallback to no-header and assign COLS
    df = None
    try:
        df = pd.read_csv(path)
        cols = df.columns.tolist()
        # if header doesn't look like the COLS, but has same length, try rename
        if len(cols) == len(COLS) and set(cols) != set(COLS):
            df.columns = COLS
    except Exception as e:
        logging.warning("CSV read failed with header: %s -- trying without header", e)
        df = pd.read_csv(path, header=None)
        if df.shape[1] == len(COLS):
            df.columns = COLS
        else:
            raise RuntimeError("CSV columns don't match expected count. Got %d columns" % df.shape[1])
    # ensure our TIME column exists
    if "TIME" not in df.columns:
        # try first column as TIME
        df = df.rename(columns={df.columns[0]: "TIME"})
    return df

def row_to_message(row, jitter=0.0, stamp_now=False):
    # build dict using COLS order (if columns present)
    msg = {}
    for c in COLS:
        if c in row:
            val = row[c]
            # optionally add small jitter to numeric values (not TIME)
            if c != "TIME" and pd.notna(val) and jitter > 0:
                try:
                    v = float(val)
                    # ±jitter fraction
                    frac = random.uniform(-jitter, jitter)
                    v = v * (1.0 + frac)
                    # keep same numeric type
                    msg[c] = float(v)
                except Exception:
                    msg[c] = val
            else:
                # convert numpy types
                if pd.isna(val):
                    msg[c] = None
                else:
                    # keep numeric typed as float
                    try:
                        msg[c] = float(val)
                    except Exception:
                        msg[c] = str(val)
        else:
            msg[c] = None
    # Timestamp handling
    if stamp_now:
        msg["TIMESTAMP"] = datetime.utcnow().isoformat() + "Z"
    else:
        # use TIME field raw; if TIME looks like numeric secs, turn into ISO basing on now
        t = row.get("TIME", None)
        if t is None or (isinstance(t, float) and pd.isna(t)):
            msg["TIMESTAMP"] = datetime.utcnow().isoformat() + "Z"
        else:
            try:
                # If TIME is numeric seconds since start, convert to ISO by adding offset
                # We'll encode the raw TIME separately too
                msg["raw_TIME"] = float(t)
                # convert to window relative to now (you may want to keep original semantics).
                msg["TIMESTAMP"] = datetime.utcnow().isoformat() + "Z"
            except Exception:
                # try parsing if it's an ISO timestamp string
                try:
                    dt = dateparser.parse(str(t))
                    msg["TIMESTAMP"] = dt.isoformat()
                except Exception:
                    msg["TIMESTAMP"] = str(t)
    return msg

def main():
    args = make_args()
    setup_logging(args.log)
    logging.info("Starting NPP CSV -> MQTT publisher")
    df = load_csv(args.csv)
    logging.info("Loaded CSV with %d rows", len(df))

    pub = MqttPublisher(args.broker, args.port, args.user, args.password)
    pub.connect()

    # prepare pacing
    times = None
    if args.use_csv_time:
        # ensure TIME numeric
        try:
            times = df["TIME"].astype(float).tolist()
        except Exception:
            logging.warning("TIME column could not be converted to float; will publish rows at fixed interval")
            times = None

    idx = 0
    nrows = len(df)
    while True:
        row = df.iloc[idx]
        msg = row_to_message(row, jitter=args.jitter, stamp_now=args.stamp_now)
        payload = json.dumps(msg)
        ok = pub.publish(args.topic, payload, qos=0, retain=False)
        if ok:
            logging.info("Published row %d to %s", idx, args.topic)
        else:
            logging.warning("Publish failed for row %d", idx)
        # pacing
        if args.use_csv_time and times is not None:
            # compute delta to next row
            if idx < nrows - 1:
                delta = float(times[idx+1]) - float(times[idx])
            else:
                # on wrap: if loop -> delta from last to last+1 ~ use same as previous delta
                if nrows >= 2:
                    delta = float(times[-1]) - float(times[-2])
                    if delta < 0:
                        delta = 1.0
                else:
                    delta = 1.0
            sleep_for = max(0.0, delta / max(1.0, args.speed))
        else:
            # default fixed 1s scaled by speed
            sleep_for = max(0.0, 1.0 / max(0.0001, args.speed))
        time.sleep(sleep_for)
        idx += 1
        if idx >= nrows:
            if args.loop:
                idx = 0
            else:
                break

    pub.stop()
    logging.info("Finished publishing CSV")

if __name__ == "__main__":
    main()
