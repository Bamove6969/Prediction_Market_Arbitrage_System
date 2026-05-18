import json
import re

with open('Cloud_GPU_Matcher.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find the target cell containing match_on_gpu logic
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'def match_on_gpu(' in ''.join(cell['source']):
        source = cell['source']
        
        # Avoid double insertion
        if 'def get_key_numbers' in ''.join(source):
            print("Filter already added.")
            break
            
        print("Adding numerical conflict filter...")
        
        new_source = []
        
        # 1. Insert the helper function at the top of the cell
        new_source.append("def get_key_numbers(text):\n")
        new_source.append("    import re\n")
        new_source.append("    parsed = set()\n")
        new_source.append("    for n in re.findall(r'\\d+(?:\\.\\d+)?', text):\n")
        new_source.append("        val = float(n)\n")
        new_source.append("        if val not in (2024, 2025, 2026, 2027):\n")
        new_source.append("            parsed.add(val)\n")
        new_source.append("    return parsed\n\n")
        
        # 2. Add the actual loop logic and inject the filter right before compute_pair_arb
        for line in source:
            if 'arb_data = compute_pair_arb(ma, mb)' in line:
                indent = line[:line.find('arb')]
                new_source.append(f"{indent}# --- NUMERICAL CONFLICT FILTER ---\n")
                new_source.append(f"{indent}nums_a = get_key_numbers(ma['title'])\n")
                new_source.append(f"{indent}nums_b = get_key_numbers(mb['title'])\n")
                new_source.append(f"{indent}if nums_a and nums_b and nums_a.isdisjoint(nums_b):\n")
                new_source.append(f"{indent}    continue\n\n")
                
            new_source.append(line)
            
        cell['source'] = new_source
        break

with open('Cloud_GPU_Matcher.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Updated Cloud_GPU_Matcher.ipynb successfully.")
