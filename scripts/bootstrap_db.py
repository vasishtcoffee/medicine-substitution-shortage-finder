"""One-time (idempotent) server bootstrap, run as MySQL root.

Creates the database, the migrator account, the locked definer account, four MySQL roles and
four backend-only login accounts. The application itself never connects as root.

Usage:  python scripts/bootstrap_db.py [database_name]
"""
import sys

import mysql.connector

from envload import env, load_env

load_env()
HOST = env("APP_ACCOUNT_HOST", "%")

ROLES = ["app_patient_role", "app_pharmacist_role", "app_admin_role", "app_auth_role"]
SVC = [  # (user env prefix, role)
    ("PATIENT_SVC", "app_patient_role"),
    ("PHARMACIST_SVC", "app_pharmacist_role"),
    ("ADMIN_SVC", "app_admin_role"),
    ("AUTH_SVC", "app_auth_role"),
]


def q(s):  # quote a string literal
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def main(DB=None):
    DB = DB or env("MYSQL_DATABASE", "medsub")
    cnx = mysql.connector.connect(
        host=env("MYSQL_HOST", "127.0.0.1"), port=int(env("MYSQL_PORT", "3306")),
        user=env("MYSQL_ROOT_USER", "root"), password=env("MYSQL_ROOT_PASSWORD"), autocommit=True)
    cur = cnx.cursor()
    run = cur.execute

    # Binary logging is ON by default; without this non-SUPER accounts cannot create functions/triggers.
    try:
        run("SET GLOBAL log_bin_trust_function_creators = 1")
        print("set log_bin_trust_function_creators=1 (not persistent; docker-compose sets it permanently)")
    except mysql.connector.Error as e:
        print("WARNING could not set log_bin_trust_function_creators:", e)

    run(f"CREATE DATABASE IF NOT EXISTS `{DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")

    mig, migp = env("MIGRATOR_USER"), env("MIGRATOR_PASSWORD")
    run(f"CREATE USER IF NOT EXISTS {q(mig)}@{q(HOST)} IDENTIFIED BY {q(migp)}")
    run(f"ALTER USER {q(mig)}@{q(HOST)} IDENTIFIED BY {q(migp)}")
    run(f"GRANT ALL PRIVILEGES ON `{DB}`.* TO {q(mig)}@{q(HOST)} WITH GRANT OPTION")
    # needed to create routines/views whose DEFINER is the dedicated definer account
    run(f"GRANT SET_USER_ID ON *.* TO {q(mig)}@{q(HOST)}")

    dfn = env("DEFINER_USER", "medsub_definer")
    run(f"CREATE USER IF NOT EXISTS {q(dfn)}@{q(HOST)} IDENTIFIED BY {q('!locked-' + migp)} ACCOUNT LOCK")
    # definer: DML only (no DDL, no GRANT) on the application schema
    run(f"GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE, TRIGGER ON `{DB}`.* TO {q(dfn)}@{q(HOST)}")

    for r in ROLES:
        run(f"CREATE ROLE IF NOT EXISTS {q(r)}@{q(HOST)}")
    for prefix, role in SVC:
        u, p = env(prefix + "_USER"), env(prefix + "_PASSWORD")
        run(f"CREATE USER IF NOT EXISTS {q(u)}@{q(HOST)} IDENTIFIED BY {q(p)}")
        run(f"ALTER USER {q(u)}@{q(HOST)} IDENTIFIED BY {q(p)}")
        run(f"GRANT {q(role)}@{q(HOST)} TO {q(u)}@{q(HOST)}")
        run(f"SET DEFAULT ROLE {q(role)}@{q(HOST)} TO {q(u)}@{q(HOST)}")
    print(f"bootstrap OK: database `{DB}`, accounts and roles ready")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
