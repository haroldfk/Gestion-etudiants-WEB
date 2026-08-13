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
from utils import JOURS_SEMAINE, fichier_pdf_autorise, notifier_enseignants_classe

etudiant_bp = Blueprint("etudiant", __name__)


@etudiant_bp.context_processor
def injecter_notifications_non_lues():

    if session.get("role") != "ETUDIANT" or "user_id" not in session:
        return {}

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM notifications
            WHERE utilisateur_id = %s
            AND lu = 0
            """,
            (session["user_id"],)
        )

        total = cursor.fetchone()["total"]

    return {"notifications_non_lues": total}


@etudiant_bp.route("/espace_etudiant", endpoint="espace_etudiant")
@role_required("ETUDIANT")
def espace_etudiant():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.*,
                c.nom AS classe_nom
            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            LEFT JOIN classes c
                ON c.id = e.classe_id

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
            SELECT
                n.*,
                ev.nom AS evaluation_nom,
                ev.date_evaluation
            FROM notes n
            LEFT JOIN evaluations ev
                ON ev.id = n.evaluation_id
            WHERE n.etudiant_id = %s
            ORDER BY n.id DESC
            """,
            (etudiant["id"],)
        )

        notes = cursor.fetchall()

        evaluations = []

        if etudiant["classe_id"] is not None:

            cursor.execute(
                """
                SELECT
                    ev.id,
                    ev.nom,
                    ev.coefficient,
                    ev.date_evaluation,
                    m.nom AS matiere_nom,
                    edt.jour_semaine,
                    edt.heure_debut,
                    edt.heure_fin
                FROM evaluations ev
                INNER JOIN matieres m
                    ON m.id = ev.matiere_id
                LEFT JOIN emplois_du_temps edt
                    ON edt.id = ev.emploi_du_temps_id
                WHERE ev.classe_id = %s
                ORDER BY edt.jour_semaine, edt.heure_debut
                """,
                (etudiant["classe_id"],)
            )

            evaluations = cursor.fetchall()

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
            SELECT
                a.*,
                m.nom AS matiere_nom
            FROM absences a
            LEFT JOIN matieres m
                ON m.id = a.matiere_id
            WHERE a.etudiant_id = %s
            ORDER BY a.date_absence DESC
            """,
            (etudiant["id"],)
        )

        absences = cursor.fetchall()

    return render_template(
        "espace_etudiant.html",
        etudiant=etudiant,
        notes=notes,
        moyenne=moyenne,
        absences=absences,
        evaluations=evaluations
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
                e.prenom,
                e.classe_id

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

            if etudiant["classe_id"] is not None:

                notifier_enseignants_classe(
                    cursor,
                    etudiant["classe_id"],
                    "Justificatif envoyé",
                    f"{etudiant['prenom']} {etudiant['nom']} a envoyé un "
                    "justificatif pour une absence."
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


@etudiant_bp.route("/mon_emploi_du_temps", endpoint="mon_emploi_du_temps")
@role_required("ETUDIANT")
def mon_emploi_du_temps():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.id,
                e.classe_id,
                c.nom AS classe_nom
            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            LEFT JOIN classes c
                ON c.id = e.classe_id

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

        creneaux_par_jour = {jour: [] for jour in JOURS_SEMAINE}

        if etudiant["classe_id"] is not None:

            cursor.execute(
                """
                SELECT
                    edt.*,
                    m.nom AS matiere_nom,
                    en.nom AS enseignant_nom,
                    en.prenom AS enseignant_prenom,
                    GROUP_CONCAT(ev.nom SEPARATOR ', ') AS evaluations_noms
                FROM emplois_du_temps edt
                INNER JOIN matieres m
                    ON m.id = edt.matiere_id
                INNER JOIN enseignants en
                    ON en.id = edt.enseignant_id
                LEFT JOIN evaluations ev
                    ON ev.emploi_du_temps_id = edt.id
                WHERE edt.classe_id = %s
                GROUP BY edt.id
                ORDER BY edt.jour_semaine, edt.heure_debut
                """,
                (etudiant["classe_id"],)
            )

            for creneau in cursor.fetchall():
                creneaux_par_jour[creneau["jour_semaine"]].append(creneau)

    return render_template(
        "mon_emploi_du_temps_etudiant.html",
        etudiant=etudiant,
        jours=JOURS_SEMAINE,
        creneaux_par_jour=creneaux_par_jour
    )


@etudiant_bp.route("/mes_cours", endpoint="mes_cours")
@role_required("ETUDIANT")
def mes_cours():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                e.id,
                e.classe_id,
                c.nom AS classe_nom
            FROM utilisateurs u

            JOIN etudiants e
                ON u.etudiant_id = e.id

            LEFT JOIN classes c
                ON c.id = e.classe_id

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

        cours_par_matiere = {}

        if etudiant["classe_id"] is not None:

            cursor.execute(
                """
                SELECT
                    c.id,
                    c.titre,
                    c.fichier,
                    c.date_upload,
                    m.nom AS matiere_nom,
                    en.nom AS enseignant_nom,
                    en.prenom AS enseignant_prenom
                FROM cours c
                INNER JOIN matieres m
                    ON m.id = c.matiere_id
                INNER JOIN matiere_classes mc
                    ON mc.matiere_id = m.id
                INNER JOIN enseignants en
                    ON en.id = c.enseignant_id
                WHERE mc.classe_id = %s
                ORDER BY m.nom ASC, c.date_upload DESC
                """,
                (etudiant["classe_id"],)
            )

            for cours in cursor.fetchall():

                cours_par_matiere.setdefault(
                    cours["matiere_nom"], []
                ).append(cours)

    return render_template(
        "mes_cours.html",
        etudiant=etudiant,
        cours_par_matiere=cours_par_matiere
    )


@etudiant_bp.route("/telecharger_cours/<int:id>", endpoint="telecharger_cours")
@role_required("ETUDIANT")
def telecharger_cours(id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT c.fichier
            FROM cours c

            INNER JOIN matiere_classes mc
                ON mc.matiere_id = c.matiere_id

            INNER JOIN etudiants e
                ON e.classe_id = mc.classe_id

            INNER JOIN utilisateurs u
                ON u.etudiant_id = e.id

            WHERE c.id = %s
            AND u.id = %s
            """,
            (id, session["user_id"])
        )

        cours = cursor.fetchone()

    if cours is None or not cours["fichier"]:

        flash(
            "Cours introuvable.",
            "danger"
        )

        return redirect(url_for("etudiant.mes_cours"))

    return send_from_directory(
        current_app.config["COURS_FOLDER"],
        cours["fichier"]
    )


@etudiant_bp.route("/mes_notifications", endpoint="mes_notifications")
@role_required("ETUDIANT")
def mes_notifications():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM notifications
            WHERE utilisateur_id = %s
            ORDER BY date_notification DESC
            """,
            (session["user_id"],)
        )

        notifications = cursor.fetchall()

        cursor.execute(
            """
            UPDATE notifications
            SET lu = 1
            WHERE utilisateur_id = %s
            AND lu = 0
            """,
            (session["user_id"],)
        )

    return render_template(
        "mes_notifications.html",
        notifications=notifications
    )
