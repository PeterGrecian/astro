"""Summary of hours-ranked.csv: per regime, dark hours and clear (clarity >= 0.8, moonless, not blurred) hours."""
import csv, sys, collections
R = list(csv.DictReader(open(sys.argv[1])))
by = collections.defaultdict(list)
for r in R: by[r["regime"]].append(r)
print("regime              hours dark clear blurred  best nights (clear hours)")
for reg in sorted(by, key=lambda k: min(x["night"] for x in by[k])):
    rs = by[reg]; dark = [r for r in rs if "twilight" not in r["flags"]]
    good = [r for r in dark if float(r["clarity"]) >= 0.8 and "moon" not in r["flags"] and "blurred" not in r["flags"]]
    cnt = collections.Counter(r["night"] for r in good).most_common(4)
    print(f"{reg:19} {len(rs):5d} {len(dark):4d} {len(good):5d} {sum('blurred' in r['flags'] for r in rs):7d}  " + " ".join(f"{n[5:]}({c})" for n, c in cnt))
print("\ntop 12 hours overall:")
for r in R[:12]: print(r["hour"], r["regime"], r["clarity"], r["stars_min"], r["flags"])
