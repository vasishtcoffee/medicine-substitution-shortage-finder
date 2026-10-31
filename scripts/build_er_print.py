"""Build the printable ER diagram + relational schema sheet from the LIVE MySQL schema.

  python scripts/build_er_print.py   ->  docs/ER_AND_SCHEMA_PRINT.html  (open in a browser, Ctrl+P, landscape)
                                         docs/ER_diagram.svg           (standalone image of the diagram)
"""
import html
from collections import defaultdict

from check_schema_docs import SKIP, load
from envload import ROOT, env, load_env

load_env()
DB = env("MYSQL_DATABASE", "medsub")

# conceptual classification (see docs/VIVA_PRESENTATION.md for the reasoning)
STRONG = ["users", "pharmacies", "medicine_categories", "active_ingredients", "medicines", "orders", "shortage_entries", "sync_outbox"]
WEAK = {"order_items": "orders", "substitution_reviews": "order_items", "inventory_movements": "inventory", "low_stock_alerts": "inventory"}
ASSOC = {"inventory": "pharmacies M:N medicines", "medicine_ingredients": "medicines M:N active_ingredients",
         "pharmacist_assignments": "users 1:1 pharmacies (pharmacist works at one pharmacy)"}

# grid position (column, row) of every entity box in the diagram
POS = {"users": (0, 0), "orders": (1, 0), "order_items": (2, 0), "substitution_reviews": (3, 0),
       "pharmacist_assignments": (0, 1), "pharmacies": (1, 1), "medicines": (2, 1), "medicine_categories": (3, 1),
       "inventory_movements": (0, 2), "inventory": (1, 2), "shortage_entries": (2, 2), "medicine_ingredients": (3, 2),
       "low_stock_alerts": (1, 3), "sync_outbox": (2, 3), "active_ingredients": (3, 3)}
# (parent, child, parent label, child label, relationship name, optional waypoints)
LINKS = [("users", "orders", "1", "N", "places"), ("users", "pharmacist_assignments", "1", "1", "is assigned"),
         ("pharmacies", "pharmacist_assignments", "1", "N", "employs"), ("pharmacies", "orders", "1", "N", "fulfils"),
         ("orders", "order_items", "1", "N", "contains"), ("medicines", "order_items", "1", "N", "requested / dispensed as"),
         ("order_items", "substitution_reviews", "1", "N", "reviewed in"), ("pharmacies", "inventory", "1", "N", "stocks"),
         ("medicines", "inventory", "1", "N", "stocked as"), ("inventory", "inventory_movements", "1", "N", "ledger"),
         ("inventory", "low_stock_alerts", "1", "N", "raises"), ("medicine_categories", "medicines", "1", "N", "classifies"),
         ("medicines", "shortage_entries", "1", "N", "reported for"), ("medicines", "medicine_ingredients", "1", "N", "composed of"),
         ("active_ingredients", "medicine_ingredients", "1", "N", "used in")]
W, ROWH, LINE = 215, 300, 15
GAP = 120
BOXX, BOXY = 40, 75


def build():
    cols, fks, uniq, checks = load(DB)
    tables = defaultdict(list)
    for r in cols:
        if r["t"] not in SKIP:
            tables[r["t"]].append(r)
    fkcols = defaultdict(dict)
    for f in fks:
        fkcols[f["child"]][f["ccol"]] = f
    return tables, fks, fkcols, uniq, checks


def box_geometry(t, rows):
    c, r = POS[t]
    x, y = BOXX + c * (W + GAP), BOXY + r * ROWH
    h = 30 + LINE * len(rows) + 6
    return x, y, h


def attr_label(t, r, fkcols):
    name = r["c"]
    pk = r["k"] == "PRI"
    fk = name in fkcols[t]
    gen = bool(r["g"])
    txt = ("/" if gen else "") + name + (" (FK)" if fk else "") + (" ?" if r["n"] == "YES" and not pk else "")
    style = ""
    if pk:
        style += "text-decoration:underline;font-weight:bold;"
    if fk:
        style += "font-style:italic;"
    return txt, style


def svg(tables, fkcols):
    geo = {t: box_geometry(t, rows) for t, rows in tables.items()}
    width = BOXX * 2 + 4 * W + 3 * GAP + 60
    height = BOXY + 4 * ROWH + 60
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" font-family="Arial, Helvetica, sans-serif">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<text x="20" y="24" font-size="16" font-weight="bold">ER diagram: Medicine Substitution &amp; Shortage Finder (generated from the live MySQL schema)</text>']

    def anchor(t, other):
        x, y, h = geo[t]
        ox, oy, oh = geo[other]
        cx, cy, ocx, ocy = x + W / 2, y + h / 2, ox + W / 2, oy + oh / 2
        if abs(ocx - cx) > abs(ocy - cy) * 0.8 and abs(ocx - cx) > W / 2:
            return (x + W, cy) if ocx > cx else (x, cy)
        return (cx, y + h) if ocy > cy else (cx, y)

    for parent, child, pl, cl, name in LINKS:
        (x1, y1), (x2, y2) = anchor(parent, child), anchor(child, parent)
        out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#333" stroke-width="1.4"/>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        out.append(f'<rect x="{mx - 4 * len(name) - 4:.0f}" y="{my - 17:.0f}" width="{8 * len(name) + 8}" height="14" fill="white"/>')
        out.append(f'<text x="{mx:.0f}" y="{my - 6:.0f}" font-size="11" text-anchor="middle" fill="#00507a" font-style="italic">{html.escape(name)}</text>')
        for (px, py), lab, (qx, qy) in ((((x1, y1)), pl, (x2, y2)), ((x2, y2), cl, (x1, y1))):
            dx = 14 if qx > px else -14 if qx < px else 0
            dy = 14 if qy > py else -14 if qy < py else 0
            if abs(qx - px) < abs(qy - py):
                dx = 10
            else:
                dy = -6
            out.append(f'<text x="{px + dx:.0f}" y="{py + dy:.0f}" font-size="13" font-weight="bold" text-anchor="middle">{lab}</text>')
    # users -> inventory_movements (actor) and users -> substitution_reviews (reviewer): drawn as margin routes
    ux, uy, uh = geo["users"]
    mx_, my_, mh = geo["inventory_movements"]
    out.append(f'<polyline points="{ux:.0f},{uy + 40:.0f} 14,{uy + 40:.0f} 14,{my_ + 40:.0f} {mx_:.0f},{my_ + 40:.0f}" fill="none" stroke="#333" stroke-dasharray="5,3"/>')
    out.append(f'<text x="18" y="{(uy + my_) / 2:.0f}" font-size="11" fill="#00507a" font-style="italic" transform="rotate(-90 18 {(uy + my_) / 2:.0f})">actor (users 1 : N inventory_movements)</text>')
    rx, ry, rh = geo["substitution_reviews"]
    out.append(f'<polyline points="{ux + W / 2:.0f},{uy:.0f} {ux + W / 2:.0f},52 {rx + W / 2:.0f},52 {rx + W / 2:.0f},{ry:.0f}" fill="none" stroke="#333" stroke-dasharray="5,3"/>')
    out.append(f'<text x="{(ux + rx + W) / 2:.0f}" y="48" font-size="11" fill="#00507a" font-style="italic" text-anchor="middle">reviewer (users 1 : N substitution_reviews)</text>')
    # self reference on medicine_categories
    cx, cy, ch = geo["medicine_categories"]
    out.append(f'<path d="M {cx + W:.0f} {cy + 50:.0f} h 22 v 40 h -22" fill="none" stroke="#333" stroke-width="1.4"/>')
    out.append(f'<text x="{cx + W + 26:.0f}" y="{cy + 74:.0f}" font-size="11" fill="#00507a" font-style="italic">parent</text>')

    for t, rows in tables.items():
        x, y, h = geo[t]
        if t in STRONG:
            kind, dash, extra = "strong", "", ""
        elif t in WEAK:
            kind, dash = "weak", ""
            extra = f'<rect x="{x - 4}" y="{y - 4}" width="{W + 8}" height="{h + 8}" fill="none" stroke="#000" stroke-width="1.4"/>'
        else:
            kind, dash, extra = "associative", ' stroke-dasharray="6,3"', ""
        fill = {"strong": "#eef6ff", "weak": "#fff4e0", "associative": "#eefbea"}[kind]
        out.append(extra)
        out.append(f'<rect x="{x}" y="{y}" width="{W}" height="{h}" fill="{fill}" stroke="#000" stroke-width="1.6"{dash}/>')
        out.append(f'<text x="{x + W / 2}" y="{y + 18}" font-size="13" font-weight="bold" text-anchor="middle">{t}</text>')
        out.append(f'<line x1="{x}" y1="{y + 24}" x2="{x + W}" y2="{y + 24}" stroke="#000"/>')
        for i, r in enumerate(rows):
            txt, style = attr_label(t, r, fkcols)
            out.append(f'<text x="{x + 8}" y="{y + 40 + i * LINE}" font-size="11" style="{style}">{html.escape(txt)}</text>')
    ly = height - 38
    out.append(f'<text x="20" y="{ly}" font-size="11"><tspan font-weight="bold" text-decoration="underline">Underlined bold</tspan> = primary key · <tspan font-style="italic">italic (FK)</tspan> = foreign key · ? = optional (NULL allowed) · /name = derived (generated column) · dashed line between boxes = relationship through a margin route</text>')
    out.append(f'<text x="20" y="{ly + 16}" font-size="11">Single border = strong entity · double border = weak entity (existence-dependent) · dashed border = associative entity (resolves an M:N or 1:1 relationship) · labels: 1 = one, N = many</text>')
    out.append("</svg>")
    return "\n".join(out)


def relational_schema(tables, fkcols):
    rows = []
    for t, cols in tables.items():
        parts = []
        for r in cols:
            name = html.escape(r["c"])
            if r["k"] == "PRI":
                name = f"<u><b>{name}</b></u>"
            if r["c"] in fkcols[t]:
                name = f"<i>{name}</i>"
            if r["g"]:
                name = f"/{name}"
            parts.append(name)
        cons = (WEAK.get(t) and "weak") or ("associative" if t in ASSOC else "strong")
        rows.append(f"<tr><td><b>{t}</b><br><small>{cons}</small></td><td>( {', '.join(parts)} )</td></tr>")
    return "\n".join(rows)


def fk_table(fks, tables, uniq):
    seen, out = set(), []
    uk = {(u["t"], u["cols"]) for u in uniq if u["ty"] in ("UNIQUE", "PRIMARY KEY")}
    for f in fks:
        if f["name"] in seen or f["child"] in SKIP:
            continue
        seen.add(f["name"])
        cols = [x["ccol"] for x in fks if x["name"] == f["name"]]
        childcols = {c["c"]: c for c in tables[f["child"]]}
        optional = any(childcols[c]["n"] == "YES" for c in cols)
        one = (f["child"], ",".join(cols)) in uk
        card = "1 : 1" if one else "1 : N"
        part = "partial (FK may be NULL)" if optional else "total (FK NOT NULL)"
        out.append(f"<tr><td>{f['parent']}</td><td>{f['child']}</td><td>{', '.join(cols)}</td><td>{card}</td><td>{part}</td><td>ON DELETE {f['del']}</td></tr>")
    return "\n".join(out)


def stats(tables, fkcols):
    total = sum(len(v) for v in tables.values())
    pk = sum(1 for v in tables.values() for r in v if r["k"] == "PRI")
    fk = sum(len(v) for v in fkcols.values())
    nullable = sum(1 for v in tables.values() for r in v if r["n"] == "YES")
    gen = sum(1 for v in tables.values() for r in v if r["g"])
    enum = sum(1 for v in tables.values() for r in v if r["d"] == "enum")
    return total, pk, fk, nullable, gen, enum


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ER diagram and relational schema</title>
<style>
 body{font-family:Arial,Helvetica,sans-serif;margin:24px;color:#111} h1{font-size:20px} h2{font-size:16px;margin-top:26px;border-bottom:2px solid #333}
 table{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0} th,td{border:1px solid #888;padding:4px 6px;text-align:left;vertical-align:top} th{background:#eee}
 small{color:#555} .pb{page-break-before:always}
 @media print{@page{size:A4 landscape;margin:10mm} body{margin:0} h2{break-after:avoid} tr{break-inside:avoid}}
</style></head><body>
<h1>Medicine Substitution &amp; Shortage Finder: ER diagram and relational schema</h1>
<p>Educational demonstration, synthetic data. Generated from the live MySQL schema (<code>scripts/build_er_print.py</code>). Print: Ctrl+P, landscape.</p>
<h2>1. ER diagram</h2>
{svg}
<h2 class="pb">2. Entity classification ({n} tables)</h2>
<table><tr><th>Kind</th><th>Count</th><th>Tables</th><th>Why</th></tr>
<tr><td>Strong entities</td><td>{ns}</td><td>{strong}</td><td>Have their own primary key and exist independently of any other row.</td></tr>
<tr><td>Weak (existence-dependent) entities</td><td>{nw}</td><td>{weak}</td><td>Cannot exist without their owner; each is identified through a foreign key to it (identifying relationship): {weakown}. Implemented with a surrogate id, but the FK is NOT NULL and deleting the owner cascades or is blocked.</td></tr>
<tr><td>Associative entities (relationship tables)</td><td>{na}</td><td>{assoc}</td><td>Resolve an M:N (or 1:1) relationship and carry its own attributes (e.g. <code>inventory.quantity</code>, <code>medicine_ingredients.strength_mg</code>): {assocown}.</td></tr></table>
<p><small><code>sync_outbox</code> is an infrastructure table (transactional outbox for MongoDB) and is classed as strong because it stands alone. <code>schema_migrations</code> (migration bookkeeping) is not part of the model.</small></p>

<h2>3. Relationships (every foreign key)</h2>
<table><tr><th>Parent (1)</th><th>Child (N)</th><th>FK column(s)</th><th>Cardinality</th><th>Participation of child</th><th>Delete rule</th></tr>{fks}</table>
<p><small>M:N relationships: pharmacies &harr; medicines (through <code>inventory</code>), medicines &harr; active_ingredients (through <code>medicine_ingredients</code>). Recursive 1:N: <code>medicine_categories.parent_id</code> &rarr; <code>medicine_categories.id</code>.</small></p>

<h2 class="pb">4. Relational schema</h2>
<p><u><b>Underlined bold</b></u> = primary key · <i>italic</i> = foreign key · /name = derived (stored generated) column.</p>
<table><tr><th style="width:170px">Relation</th><th>Attributes</th></tr>{schema}</table>

<h2>5. Types of attributes in this schema ({total} columns in {n} tables)</h2>
<table><tr><th>Attribute type</th><th>Count / where</th><th>Examples</th></tr>
<tr><td>Simple (atomic)</td><td>almost all columns</td><td><code>users.email</code>, <code>medicines.name</code>, <code>orders.created_at</code></td></tr>
<tr><td>Key (primary key)</td><td>{pk} columns; <b>composite keys</b> in <code>inventory(pharmacy_id, medicine_id)</code> and <code>medicine_ingredients(medicine_id, ingredient_id)</code></td><td><code>users.id</code>, <code>orders.id</code></td></tr>
<tr><td>Foreign key</td><td>{fk} columns</td><td><code>orders.patient_id</code>, <code>inventory.medicine_id</code></td></tr>
<tr><td>Unique (candidate key)</td><td>alternate keys</td><td><code>users.email</code>, <code>medicines.name</code>, <code>pharmacist_assignments.user_id</code></td></tr>
<tr><td>Composite attribute</td><td>decomposed into atomic columns during design</td><td>pharmacy address &rarr; <code>city</code> + <code>address</code>; strength = (<code>strength_mg</code> + <code>strength_basis</code>)</td></tr>
<tr><td>Multivalued attribute</td><td>moved to its own relation (1NF)</td><td>a medicine's ingredients &rarr; <code>medicine_ingredients</code></td></tr>
<tr><td>Derived attribute</td><td>{gen} stored generated column + computed ones</td><td>stored: <code>low_stock_alerts.open_alert_key</code>; computed: availability band (<code>fn_availability_band</code>), composition text, <code>is_eligible</code> (view), low-stock status</td></tr>
<tr><td>Optional / NULLable</td><td>{nullable} columns</td><td><code>medicine_categories.parent_id</code>, <code>order_items.dispensed_medicine_id</code>, <code>shortage_entries.resolved_at</code>, <code>inventory_movements.batch_no</code></td></tr>
<tr><td>Enumerated (ENUM)</td><td>{enum} columns</td><td><code>users.role</code>, <code>orders.status</code>, <code>medicines.dosage_form</code></td></tr>
<tr><td>Descriptive attribute of a relationship</td><td>on associative tables</td><td><code>inventory.quantity</code>, <code>inventory.reorder_level</code>, <code>medicine_ingredients.strength_mg</code></td></tr>
<tr><td>Semi-structured (MongoDB, outside the relational model)</td><td>document fields</td><td><code>feed_events.payload</code>, <code>inventory_feed.metadata</code>, <code>flags[]</code></td></tr>
</table>
</body></html>"""


def main():
    tables, fks, fkcols, uniq, checks = build()
    diagram = svg(tables, fkcols)
    (ROOT / "docs" / "ER_diagram.svg").write_text(diagram, encoding="utf-8")
    total, pk, fk, nullable, gen, enum = stats(tables, fkcols)
    values = dict(
        svg=diagram, n=len(tables), ns=len(STRONG), nw=len(WEAK), na=len(ASSOC),
        strong=", ".join(STRONG), weak=", ".join(WEAK), assoc=", ".join(ASSOC),
        weakown="; ".join(f"{k} &rarr; {v}" for k, v in WEAK.items()),
        assocown="; ".join(f"{k} = {v}" for k, v in ASSOC.items()),
        fks=fk_table(fks, tables, uniq), schema=relational_schema(tables, fkcols),
        total=total, pk=pk, fk=fk, nullable=nullable, gen=gen, enum=enum)
    page = PAGE
    for k, v in values.items():
        page = page.replace('{' + k + '}', str(v))
    (ROOT / "docs" / "ER_AND_SCHEMA_PRINT.html").write_text(page, encoding="utf-8")
    assert set(STRONG) | set(WEAK) | set(ASSOC) == set(tables), set(tables) ^ (set(STRONG) | set(WEAK) | set(ASSOC))
    print(f"wrote docs/ER_AND_SCHEMA_PRINT.html and docs/ER_diagram.svg: {len(tables)} tables "
          f"({len(STRONG)} strong, {len(WEAK)} weak, {len(ASSOC)} associative); {total} columns, {pk} PK, {fk} FK, {nullable} nullable, {gen} generated, {enum} enum")


if __name__ == "__main__":
    main()
