import os, re

lvs_dir = '/home/whqkrel/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/klayout/tech/lvs'
for root, dirs, files in os.walk(lvs_dir):
    for f in sorted(files):
        if not f.endswith(('.py', '.rb', '.lvs')):
            continue
        path = os.path.join(root, f)
        try:
            lines = open(path).readlines()
        except:
            continue
        hits = []
        for i, line in enumerate(lines):
            if re.search(r'terminal|\.element|device_class|res_dev|cap_dev|NetlistSpice', line, re.I):
                hits.append(f"  {i+1}: {line.rstrip()[:120]}")
        if hits:
            print(f"\n=== {path} ===")
            for h in hits[:20]:
                print(h)
