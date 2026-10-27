import json
import os
import urllib.parse

with open('data/destinations.json', encoding='utf-8') as f:
    dests = json.load(f)

img_files = set(os.listdir('static/images'))

matched_dests = {}
unmatched_dests = []

for d in dests:
    d_name = d['name_en']
    d_id = d['id']
    curr_f = d.get('image', {}).get('file', '')
    
    found = None
    if curr_f in img_files:
        found = curr_f
    else:
        for f in img_files:
            f_clean = f.lower().replace('.jpg', '')
            if (f_clean in d_name.lower() or d_name.lower() in f_clean or 
                f_clean in d_id.lower() or d_id.lower() in f_clean or
                d_name.lower().startswith(f_clean[:15])):
                found = f
                break
    if found:
        matched_dests[d_id] = (d_name, found)
    else:
        unmatched_dests.append(d)

print(f"Matched destinations: {len(matched_dests)}")
print(f"Unmatched destinations: {len(unmatched_dests)}")
print("\n--- UNMATCHED DESTINATIONS LIST ---")
for d in unmatched_dests:
    print(f"ID: {d['id']:<30} Name: {d['name_en']:<50} District: {d['district']}")
