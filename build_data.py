"""Builds data.json (gear recipes, focus costs, item values) from ao-bin-dumps.

Rerun after a game patch:
  curl -L -o items.json  https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/items.json
  curl -L -o names.json  https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/formatted/items.json
  python build_data.py items.json names.json data.json
"""
import json
import re
import sys

TIERS = range(4, 9)
ENCH = range(5)
PREFIXES = ("Adept's ", "Expert's ", "Master's ", "Grandmaster's ", "Elder's ")
GROUPS = ("weapons", "armors", "head", "shoes", "offhands", "capes", "bags", "gathering", "consumables")
CONSUMABLES = ("food", "potions")  # cooking + alchemy; other consumables aren't crafted for profit

items_path, names_path, out_path = sys.argv[1:4]
raw = json.load(open(items_path, encoding="utf-8"))["items"]
items = {x["@uniquename"]: x for v in raw.values() if isinstance(v, list) for x in v if isinstance(x, dict) and "@uniquename" in x}
names = {x["UniqueName"]: (x.get("LocalizedNames") or {}).get("EN-US") for x in json.load(open(names_path, encoding="utf-8"))}


def recipe(base, t, e):
    """First recipe for T{t}_{base} at enchant e: [(resource_id, count, returnable)], focus, amount crafted."""
    x = items.get(f"T{t}_{base}")
    if not x:
        return None
    if e:
        ench = (x.get("enchantments") or {}).get("enchantment") or []
        x = next((en for en in (ench if isinstance(ench, list) else [ench]) if en["@enchantmentlevel"] == str(e)), None)
        if not x:
            return None
    req = x.get("craftingrequirements")
    if isinstance(req, list):
        req = req[0]
    if not req or "craftresource" not in req:
        return None
    res = req["craftresource"]
    res = res if isinstance(res, list) else [res]
    out = []
    for r in res:
        rid, lvl = r["@uniquename"], int(r.get("@enchantmentlevel", 0))
        out.append((rid + (f"@{lvl}" if lvl else ""), int(r["@count"]), r.get("@maxreturnamount") != "0"))
    return out, int(req.get("@craftingfocus", 0)), int(req.get("@amountcrafted", 1))


def value(rid):
    x = items.get(rid.split("@")[0])
    return int(x.get("@itemvalue", 0)) if x else 0


def template(rid, t, e):
    """One recipe per tier for every enchant: T5_METALBAR_LEVEL2@2 -> T5_METALBAR{e}, T5_CAPE@2 -> T5_CAPE{ae},
    T1_FISHSAUCE_LEVEL2 -> T1_FISHSAUCE{l} (food/potion enchant ingredients)."""
    return rid.replace(f"_LEVEL{e}@{e}", "{e}").replace(f"@{e}", "{ae}").replace(f"_LEVEL{e}", "{l}") if e else rid


gear = []
def wanted(x):
    cat = x.get("@shopcategory")
    return cat in GROUPS and x.get("craftingrequirements") and (cat != "consumables" or x.get("@shopsubcategory1") in CONSUMABLES)


bases = sorted({k[3:] for k, x in items.items() if re.match(r"T[1-8]_", k) and wanted(x)})
for base in bases:
    first = next(items[f"T{t}_{base}"] for t in range(1, 9) if f"T{t}_{base}" in items)
    cons = first["@shopcategory"] == "consumables"
    tmpl, focus, val, tiers, amount = {}, {}, {}, [], 1
    ok = True
    for t in (range(1, 9) if cons else TIERS):
        if not recipe(base, t, 0):
            continue
        tiers.append(t)
        focus[t], val[t] = [], []
        for e in ENCH:
            r = recipe(base, t, e)
            if not r:
                focus[t].append(None); val[t].append(None)
                continue
            res, f, amount = r
            tm = [[template(rid, t, e), n, int(ret)] for rid, n, ret in res]
            if t not in tmpl or (e == 1 and not any("{" in r[0][3:] for r in tmpl[t])):
                tmpl[t] = tm  # the enchant-1 recipe shows which inputs scale with enchant
            elif e > 1 and tm != tmpl[t]:
                ok = False
            focus[t].append(f)
            val[t].append(sum(n * value(rid) for rid, n, _ in res))
    if not tiers:
        continue
    if not ok:
        print("skipped", base, file=sys.stderr)
        continue
    name = names.get(f"T{tiers[0]}_{base}") or base
    for p in PREFIXES:
        name = name.removeprefix(p)
    gear.append({
        "id": base, "n": name, "g": first["@shopcategory"], "c": first.get("@shopsubcategory1"),
        "cc": first.get("@craftingcategory") or first.get("@shopsubcategory1"),
        "r": tmpl, "t": tiers, "f": focus, "v": val, **({"a": amount} if amount > 1 else {}),
        # food/potion names change per tier (Bean / Turnip / Potato Salad)
        **({"nt": {t: names.get(f"T{t}_{base}") or name for t in tiers}} if cons else {}),
    })

ref = {}
for kind in ("LEATHER", "CLOTH"):
    ref[kind] = {t: [] for t in TIERS}
    for t in TIERS:
        for e in ENCH:
            rid = f"T{t}_{kind}" + (f"_LEVEL{e}" if e else "")
            x = items.get(rid, {})
            req = x.get("craftingrequirements")
            req = req[0] if isinstance(req, list) else req or {}
            ref[kind][t].append([int(req.get("@craftingfocus", 0)), int(x.get("@itemvalue", 0))])

json.dump({"gear": gear, "ref": ref}, open(out_path, "w", encoding="utf-8"), separators=(",", ":"))
print(len(gear), "gear items written")
