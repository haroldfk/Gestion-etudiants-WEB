JOURS_SEMAINE = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche"
]

BLOCS_HORAIRES = [
    (f"{heure:02d}:00", f"{heure + 1:02d}:00") for heure in range(8, 19)
]


def formater_heure(valeur):
    """Formate une colonne TIME MySQL (renvoyée comme datetime.timedelta
    par mysql-connector-python) en chaîne "HH:MM"."""

    if valeur is None:
        return ""

    total_secondes = int(valeur.total_seconds())

    heures, reste = divmod(total_secondes, 3600)
    minutes = reste // 60

    return f"{heures:02d}:{minutes:02d}"


def calculer_mention(moyenne):

    if moyenne is None:
        return ""

    if moyenne < 10:
        return "Échec"

    elif moyenne < 12:
        return "Passable"

    elif moyenne < 14:
        return "Assez Bien"

    elif moyenne < 16:
        return "Bien"

    else:
        return "Très Bien"


def fichier_pdf_autorise(fichier):

    if not fichier:
        return False

    nom_fichier = fichier.filename

    if not nom_fichier:
        return False

    return (
        "." in nom_fichier
        and nom_fichier.rsplit(".", 1)[1].lower() == "pdf"
    )


EXTENSIONS_COURS_AUTORISEES = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip"
}


def fichier_cours_autorise(fichier):

    if not fichier:
        return False

    nom_fichier = fichier.filename

    if not nom_fichier or "." not in nom_fichier:
        return False

    extension = nom_fichier.rsplit(".", 1)[1].lower()

    return extension in EXTENSIONS_COURS_AUTORISEES


def notifier_etudiant(cursor, etudiant_id, titre, message):
    """Crée une notification pour le compte de connexion lié à cet
    étudiant, s'il en a un. Le cursor doit être en mode dictionary=True
    et faire partie de la même transaction que l'action déclenchante."""

    cursor.execute(
        "SELECT id FROM utilisateurs WHERE etudiant_id = %s",
        (etudiant_id,)
    )

    utilisateur = cursor.fetchone()

    if utilisateur is not None:

        cursor.execute(
            """
            INSERT INTO notifications (utilisateur_id, titre, message)
            VALUES (%s, %s, %s)
            """,
            (utilisateur["id"], titre, message)
        )


def notifier_classe(cursor, classe_id, titre, message):
    """Notifie tous les étudiants d'une classe qui ont un compte de
    connexion. Même contrat de cursor que notifier_etudiant."""

    cursor.execute(
        """
        SELECT u.id
        FROM utilisateurs u
        INNER JOIN etudiants e
            ON e.id = u.etudiant_id
        WHERE e.classe_id = %s
        """,
        (classe_id,)
    )

    for utilisateur in cursor.fetchall():

        cursor.execute(
            """
            INSERT INTO notifications (utilisateur_id, titre, message)
            VALUES (%s, %s, %s)
            """,
            (utilisateur["id"], titre, message)
        )


def notifier_enseignants_classe(cursor, classe_id, titre, message):
    """Notifie tous les enseignants qui donnent au moins une matière
    dans cette classe (via matiere_classes + enseignant_matieres) et
    qui ont un compte de connexion. Même contrat de cursor que
    notifier_etudiant."""

    cursor.execute(
        """
        SELECT DISTINCT u.id
        FROM utilisateurs u
        INNER JOIN enseignants en
            ON en.id = u.enseignant_id
        INNER JOIN enseignant_matieres em
            ON em.enseignant_id = en.id
        INNER JOIN matiere_classes mc
            ON mc.matiere_id = em.matiere_id
        WHERE mc.classe_id = %s
        """,
        (classe_id,)
    )

    for utilisateur in cursor.fetchall():

        cursor.execute(
            """
            INSERT INTO notifications (utilisateur_id, titre, message)
            VALUES (%s, %s, %s)
            """,
            (utilisateur["id"], titre, message)
        )


def notifier_matiere(cursor, matiere_id, titre, message):
    """Notifie tous les étudiants des classes qui suivent cette matière
    (via matiere_classes) et qui ont un compte de connexion. Même
    contrat de cursor que notifier_etudiant."""

    cursor.execute(
        """
        SELECT DISTINCT u.id
        FROM utilisateurs u
        INNER JOIN etudiants e
            ON e.id = u.etudiant_id
        INNER JOIN matiere_classes mc
            ON mc.classe_id = e.classe_id
        WHERE mc.matiere_id = %s
        """,
        (matiere_id,)
    )

    for utilisateur in cursor.fetchall():

        cursor.execute(
            """
            INSERT INTO notifications (utilisateur_id, titre, message)
            VALUES (%s, %s, %s)
            """,
            (utilisateur["id"], titre, message)
        )
