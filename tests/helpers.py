"""Test helpers for calling stored procedures on raw connections."""


def call(cnx, sql, params=()):
    """Run a CALL (or any statement) and return the FIRST result set as a list of dicts ([] if none)."""
    cur = cnx.cursor(dictionary=True)
    cur.execute(sql, params)
    first = None
    while True:
        if cur.with_rows:
            rows = cur.fetchall()
            if first is None:
                first = rows
        if not cur.nextset():
            break
    cur.close()
    return first or []


def scalar(cnx, sql, params=()):
    cur = cnx.cursor()
    cur.execute(sql, params)
    v = cur.fetchone()[0]
    cur.close()
    return v
