import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for
)
from werkzeug.utils import secure_filename

from config import db_cursor
from decorators import role_required
from utils import fichier_pdf_autorise

etudiant_bp = Blueprint("etudiant", __name__)


@etudiant_bp.route("/espace_etudiant", endpoint="espace_etudiant")
@role_required("ETUDIANT")
def espace_etudiant():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.*
            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            WHERE u.id = %s
            """,
            (session["user_id"],)
        )

        etudiant = cursor.fetchone()

        if etudiant is None:

            session.clear()

            flash(
                "Aucun profil étudiant associé à ce compte.",
                "danger"
            )

            return redirect(url_for("auth.login"))

        cursor.execute(
            """
            SELECT *
            FROM notes
            WHERE etudiant_id = %s
            ORDER BY id DESC
            """,
            (etudiant["id"],)
        )

        notes = cursor.fetchall()

        cursor.execute(
            """
            SELECT AVG(note) AS moyenne
            FROM notes
            WHERE etudiant_id = %s
            """,
            (etudiant["id"],)
        )

        moyenne = cursor.fetchone()["moyenne"]

        cursor.execute(
            """
            SELECT *
            FROM absences
            WHERE etudiant_id = %s
            ORDER BY date_absence DESC
            """,
            (etudiant["id"],)
        )

        absences = cursor.fetchall()

    return render_template(
        "espace_etudiant.html",
        etudiant=etudiant,
        notes=notes,
        moyenne=moyenne,
        absences=absences
    )


@etudiant_bp.route(
    "/envoyer_justificatif/<int:absence_id>",
    methods=["GET", "POST"],
    endpoint="envoyer_justificatif"
)
@role_required("ETUDIANT")
def envoyer_justificatif(absence_id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.id,
                e.nom,
                e.prenom

            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            WHERE u.id = %s
            """,
            (session["user_id"],)
        )

        etudiant = cursor.fetchone()

        if etudiant is None:

            flash(
                "Aucun profil étudiant associé à ce compte.",
                "danger"
            )

            return redirect(url_for("auth.login"))

        cursor.execute(
            """
            SELECT *
            FROM absences

            WHERE id = %s
            AND etudiant_id = %s
            """,
            (absence_id, etudiant["id"])
        )

        absence = cursor.fetchone()

        if absence is None:

            flash(
                "Absence introuvable ou accès interdit.",
                "danger"
            )

            return redirect(url_for("etudiant.espace_etudiant"))

        if request.method == "POST":

            fichier = request.files.get("justificatif")

            if fichier is None or fichier.filename == "":

                flash(
                    "Veuillez sélectionner un fichier PDF.",
                    "warning"
                )

                return redirect(
                    url_for("etudiant.envoyer_justificatif", absence_id=absence_id)
                )

            if not fichier_pdf_autorise(fichier):

                flash(
                    "Seuls les fichiers PDF sont autorisés.",
                    "danger"
                )

                return redirect(
                    url_for("etudiant.envoyer_justificatif", absence_id=absence_id)
                )

            nom_original = secure_filename(fichier.filename)

            nom_fichier = (
                f"justificatif_"
                f"{etudiant['id']}_"
                f"{absence_id}_"
                f"{nom_original}"
            )

            chemin_fichier = os.path.join(
                current_app.config["UPLOAD_FOLDER"],
                nom_fichier
            )

            fichier.save(chemin_fichier)

            cursor.execute(
                """
                UPDATE absences

                SET
                    justificatif = %s,
                    statut = %s

                WHERE id = %s
                AND etudiant_id = %s
                """,
                (
                    nom_fichier,
                    "En attente",
                    absence_id,
                    etudiant["id"]
                )
            )

            flash(
                "Justificatif PDF envoyé avec succès. "
                "Il est maintenant en attente de validation.",
                "success"
            )

            return redirect(url_for("etudiant.espace_etudiant"))

        return render_template(
            "envoyer_justificatif.html",
            absence=absence,
            etudiant=etudiant
        )


@etudiant_bp.route("/mes_documents", endpoint="mes_documents")
@role_required("ETUDIANT")
def mes_documents():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.*
            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            WHERE u.id = %s
            """,
            (session["user_id"],)
        )

        etudiant = cursor.fetchone()

        if etudiant is None:

            session.clear()

            flash(
                "Aucun profil étudiant associé à ce compte.",
                "danger"
            )

            return redirect(url_for("auth.login"))

        cursor.execute(
            """
            SELECT *
            FROM absences
            WHERE etudiant_id = %s
            AND justificatif IS NOT NULL
            ORDER BY date_absence DESC
            """,
            (etudiant["id"],)
        )

        documents = cursor.fetchall()

    return render_template(
        "mes_documents.html",
        etudiant=etudiant,
        documents=documents
    )


@etudiant_bp.route("/mon_justificatif/<int:absence_id>", endpoint="mon_justificatif")
@role_required("ETUDIANT")
def mon_justificatif(absence_id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT a.justificatif
            FROM absences a

            JOIN utilisateurs u
                ON u.etudiant_id = a.etudiant_id

            WHERE a.id = %s
            AND u.id = %s
            """,
            (absence_id, session["user_id"])
        )

        absence = cursor.fetchone()

    if absence is None or not absence["justificatif"]:

        flash(
            "Justificatif introuvable.",
            "danger"
        )

        return redirect(url_for("etudiant.mes_documents"))

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        absence["justificatif"]
    )
