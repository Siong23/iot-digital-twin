import os
import pandas as pd
import subprocess

# Step 1: Automatically detect all .log files in current directory
all_logs = [f for f in os.listdir() if f.endswith(".log")]

if not all_logs:
    print("❌ No Zeek .log files found in the current directory.")
    exit(1)

print("🔍 Found Zeek logs:")
for log in all_logs:
    print(f" - {log}")

# Step 2: Convert each .log to .csv using zeek-cut
csv_files = []
for log in all_logs:
    csv_file = log.replace(".log", ".csv")
    with open(csv_file, "w") as out_f:
        subprocess.run(["zeek-cut"], stdin=open(log), stdout=out_f)
    csv_files.append(csv_file)

# Step 3: Merge all CSVs into one dataframe
merged_df = pd.DataFrame()
for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file, sep="\t", engine="python")
        df['source_log'] = csv_file.replace(".csv", "")
        merged_df = pd.concat([merged_df, df], axis=0, ignore_index=True)
    except Exception as e:
        print(f"⚠️ Skipped {csv_file} due to error: {e}")

# Step 4: Ask user to enter labeling info
print("\n📝 Enter labeling information for this dataset:")
label_value = input("Enter label (e.g., 0 for normal, 1 for attack): ").strip()
attack_type = input("Enter attack type (e.g., normal, ddos, mqtt, bruteforce): ").strip().lower()

merged_df['label'] = label_value
merged_df['attack_type'] = attack_type

# Step 5: Save the final labeled dataset
output_file = f"merged_labeled_{attack_type}.csv"
merged_df.to_csv(output_file, index=False)

print(f"\n✅ Labeled dataset saved as: {output_file}")
