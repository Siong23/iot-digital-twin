import re
from collections import defaultdict

def parse_cisco_config(config_text):
    blocks = defaultdict(list)
    current_block = None

    for line in config_text.splitlines():
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Match top-level config blocks
        match = re.match(r'^(interface|ip dhcp pool|ip route|snmp-server|ip flow-export|ip flow-cache|flow exporter|flow monitor)(.*?)$', stripped)

        if match:
            block_type = match.group(1).strip()
            identifier = match.group(2).strip()
            current_block = f"{block_type} {identifier}".strip()
            blocks[current_block].append(stripped)
        elif current_block:
            blocks[current_block].append(stripped)

    return blocks

# Example usage
if __name__ == "__main__":
    with open("physical_router_config.txt", "r") as f:
        config = f.read()

    parsed_blocks = parse_cisco_config(config)

    for block_name, lines in parsed_blocks.items():
        print(f"\n--- {block_name} ---")
        for line in lines:
            print(line)
