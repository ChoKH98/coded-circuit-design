import klayout.db as db

r = db.DeviceClassResistor()
print("Resistor class:", type(r))
print("Resistor attrs:", [a for a in dir(r) if 'term' in a.lower() or 'port' in a.lower()])

# Try getting terminals via the netlist
nl = db.Netlist()
nl.add(r)
r2 = nl.device_class_by_name(r.name) if r.name else None

# Check terminal definition methods
for attr in dir(r):
    if 'terminal' in attr.lower():
        print(f"  {attr}")
