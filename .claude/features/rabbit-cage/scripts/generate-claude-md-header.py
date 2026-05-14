#!/usr/bin/env python3
# generate-claude-md-header.py — print the CLAUDE.md header line from policy-header.json
# Usage: python3 generate-claude-md-header.py <policy_header_json_path>
import json, sys

policy_header_json = sys.argv[1]
print(json.load(open(policy_header_json))["header"])
