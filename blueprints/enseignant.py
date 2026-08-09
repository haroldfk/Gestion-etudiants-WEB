from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from config import db_cursor
from decorators import role_required

enseignant_bp = Blueprint("enseignant", __name__)


@enseignant_bp.route("/espace_enseignant", endpoint="espace_enseignant")
@role_required("ENSEIGNANT")
def espace_enseignant():

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé à ce compte.",
            "danger"
        )

        return redirect(url_for("auth.login"))

    try:

        with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

            cursor.execute(
                """
                SELECT
                    id,
                    nom,
                    prenom,
                    email,
                    telephone,
                    specialite
                FROM enseignants
                WHERE id = %s
                """,
                (enseignant_id,)
            )

            enseignant = cursor.fetchone()

            if enseignant is None:

                session.clear()

                flash(
                    "Profil enseignant introuvable.",
                    "danger"
                )

                return redirect(url_for("auth.login"))

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.nom
                FROM enseignant_matieres em
                INNER JOIN matieres m
                    ON m.id = em.matiere_id
                WHERE em.enseignant_id = %s
                ORDER BY m.nom ASC
                """,
                (enseignant_id,)
            )

            matieres = cursor.fetchall()

        return render_template(
            "espace_enseignant.html",
            enseignant=enseignant,
            matieres=matieres,
            nombre_matieres=len(matieres)
        )

    except Exception as erreur:

        current_app.logger.error(
            "Erreur espace enseignant : %r",
            erreur
        )

        flash(
            "Une erreur est survenue dans votre espace enseignant.",
            "danger"
        )

        return redirect(url_for("auth.logout"))


@enseignant_bp.route(
    "/enseignant/saisir_notes/<int:matiere_id>",
    methods=["GET", "POST"],
    endpoint="saisir_notes_enseignant"
)
@role_required("ENSEIGNANT")
def saisir_notes_enseignant(matiere_id):

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé.",
            "danger"
        )

        return redirect(url_for("auth.login"))

    try:

        with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.nom
                FROM matieres m
                INNER JOIN enseignant_matieres em
                    ON em.matiere_id = m.id
                WHERE em.enseignant_id = %s
                AND m.id = %s
                """,
                (enseignant_id, matiere_id)
            )

            matiere = cursor.fetchone()

            if matiere is None:

                flash(
                    "Vous n'êtes pas autorisé à gérer cette matière.",
                    "danger"
                )

                return redirect(url_for("enseignant.espace_enseignant"))

            if request.method == "POST":

                etudiant_id = request.form.get("etudiant_id")

                note = request.form.get("note")

                if not etudiant_id or note is None:

                    flash(
                        "Veuillez remplir tous les champs.",
                        "warning"
                    )

                    return redirect(
                        url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                    )

                try:
                    note = float(note)

                except ValueError:

                    flash(
                        "La note doit être un nombre.",
                        "danger"
                    )

                    return redirect(
                        url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                    )

                if note < 0 or note > 20:

                    flash(
                        "La note doit être comprise entre 0 et 20.",
                        "danger"
                    )

                    return redirect(
                        url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                    )

                cursor.execute(
                    """
                    SELECT id
                    FROM etudiants
                    WHERE id = %s
                    """,
                    (etudiant_id,)
                )

                etudiant = cursor.fetchone()

                if etudiant is None:

                    flash(
                        "Étudiant introuvable.",
                        "danger"
                    )

                    return redirect(
                        url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                    )

                cursor.execute(
                    """
                    INSERT INTO notes
                    (
                        etudiant_id,
                        matiere,
                        note
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (etudiant_id, matiere["nom"], note)
                )

                flash(
                    "Note enregistrée avec succès !",
                    "success"
                )

                return redirect(
                    url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                )

            cursor.execute(
                """
                SELECT
                    id,
                    nom,
                    prenom,
                    filiere
                FROM etudiants
                ORDER BY nom ASC, prenom ASC
                """
            )

            etudiants = cursor.fetchall()

        return render_template(
            "saisir_notes_enseignant.html",
            matiere=matiere,
            etudiants=etudiants
        )

    except Exception as erreur:

        current_app.logger.error(
            "Erreur saisie des notes : %r",
            erreur
        )

        flash(
            "Une erreur est survenue lors de la saisie des notes.",
            "danger"
        )

        return redirect(url_for("enseignant.espace_enseignant"))


@enseignant_bp.route("/mes_etudiants", endpoint="mes_etudiants")
@role_required("ENSEIGNANT")
def mes_etudiants():

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé.",
            "danger"
        )

        return redirect(url_for("auth.login"))

    try:

        with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.nom
                FROM enseignant_matieres em
                INNER JOIN matieres m
                    ON m.id = em.matiere_id
                WHERE em.enseignant_id = %s
                ORDER BY m.nom ASC
                """,
                (enseignant_id,)
            )

            matieres = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    id,
                    nom,
                    prenom,
                    filiere
                FROM etudiants
                ORDER BY nom ASC, prenom ASC
                """
            )

            etudiants = cursor.fetchall()

            notes_par_etudiant = {}

            if matieres:

                noms_matieres = [matiere["nom"] for matiere in matieres]

                placeholders = ", ".join(["%s"] * len(noms_matieres))

                cursor.execute(
                    f"""
                    SELECT etudiant_id, matiere, note
                    FROM notes
                    WHERE matiere IN ({placeholders})
                    """,
                    tuple(noms_matieres)
                )

                for ligne in cursor.fetchall():

                    notes_par_etudiant.setdefault(
                        ligne["etudiant_id"], {}
                    )[ligne["matiere"]] = ligne["note"]

        return render_template(
            "mes_etudiants.html",
            matieres=matieres,
            etudiants=etudiants,
            notes_par_etudiant=notes_par_etudiant
        )

    except Exception as erreur:

        current_app.logger.error(
            "Erreur mes étudiants : %r",
            erreur
        )

        flash(
            "Une erreur est survenue.",
            "danger"
        )

        return redirect(url_for("enseignant.espace_enseignant"))
