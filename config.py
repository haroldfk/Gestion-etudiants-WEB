import os
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():

    connexion = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "gestion_etudiants")
    )

    return connexion


@contextmanager
def db_cursor(dictionary=False, buffered=False):
    """
    Ouvre une connexion + curseur, commit automatiquement en sortie
    normale, rollback automatiquement si une exception survient,
    et ferme systématiquement curseur/connexion.
    """

    connexion = get_db_connection()
    cursor = connexion.cursor(
        dictionary=dictionary,
        buffered=buffered
    )

    try:
        yield connexion, cursor
        connexion.commit()

    except Exception:
        connexion.rollback()
        raise

    finally:
        cursor.close()
        connexion.close()
