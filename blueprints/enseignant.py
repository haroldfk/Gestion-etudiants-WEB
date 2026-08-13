import os

import mysql.connector
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
from utils import (
    JOURS_SEMAINE,
    fichier_cours_autorise,
    notifier_classe,
    notifier_etudiant,
    notifier_matiere
)

enseignant_bp = Blueprint("enseignant", __name__)


@enseignant_bp.context_processor
def injecter_notifications_non_lues():

    if session.get("role") != "ENSEIGNANT" or "user_id" not in session:
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

            cursor.execute(
                """
                SELECT DISTINCT
                    c.id,
                    c.nom,
                    c.niveau,
                    c.annee_universitaire
                FROM enseignant_matieres em
                INNER JOIN matiere_classes mc
                    ON mc.matiere_id = em.matiere_id
                INNER JOIN classes c
                    ON c.id = mc.classe_id
                WHERE em.enseignant_id = %s
                ORDER BY c.nom ASC
                """,
                (enseignant_id,)
            )

            classes = cursor.fetchall()

        return render_template(
            "espace_enseignant.html",
            enseignant=enseignant,
            matieres=matieres,
            nombre_matieres=len(matieres),
            classes=classes,
            nombre_classes=len(classes)
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

            cursor.execute(
                """
                SELECT classe_id
                FROM matiere_classes
                WHERE matiere_id = %s
                """,
                (matiere_id,)
            )

            classes_ids = [ligne["classe_id"] for ligne in cursor.fetchall()]

            if request.method == "POST":

                etudiant_id = request.form.get("etudiant_id")

                note = request.form.get("note")

                evaluation_id = request.form.get("evaluation_id") or None

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

                etudiant = None

                if classes_ids:

                    placeholders = ", ".join(["%s"] * len(classes_ids))

                    cursor.execute(
                        f"""
                        SELECT id, classe_id
                        FROM etudiants
                        WHERE id = %s
                        AND classe_id IN ({placeholders})
                        """,
                        tuple([etudiant_id] + classes_ids)
                    )

                    etudiant = cursor.fetchone()

                if etudiant is None:

                    flash(
                        "Étudiant introuvable dans cette classe.",
                        "danger"
                    )

                    return redirect(
                        url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                    )

                if evaluation_id is not None:

                    cursor.execute(
                        """
                        SELECT id, classe_id
                        FROM evaluations
                        WHERE id = %s
                        AND matiere_id = %s
                        """,
                        (evaluation_id, matiere_id)
                    )

                    evaluation = cursor.fetchone()

                    if evaluation is None:

                        flash(
                            "Évaluation invalide pour cette matière.",
                            "danger"
                        )

                        return redirect(
                            url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                        )

                    if (
                        evaluation["classe_id"] is not None
                        and evaluation["classe_id"] != etudiant["classe_id"]
                    ):

                        flash(
                            "Cette évaluation appartient à une autre classe.",
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
                        note,
                        evaluation_id
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (etudiant_id, matiere["nom"], note, evaluation_id)
                )

                notifier_etudiant(
                    cursor,
                    etudiant_id,
                    "Nouvelle note",
                    f"Une note de {note}/20 a été ajoutée en {matiere['nom']}."
                )

                flash(
                    "Note enregistrée avec succès !",
                    "success"
                )

                return redirect(
                    url_for("enseignant.saisir_notes_enseignant", matiere_id=matiere_id)
                )

            etudiants = []

            if classes_ids:

                placeholders = ", ".join(["%s"] * len(classes_ids))

                cursor.execute(
                    f"""
                    SELECT
                        e.id,
                        e.nom,
                        e.prenom,
                        e.filiere,
                        c.nom AS classe_nom
                    FROM etudiants e
                    LEFT JOIN classes c
                        ON c.id = e.classe_id
                    WHERE e.classe_id IN ({placeholders})
                    ORDER BY e.nom ASC, e.prenom ASC
                    """,
                    tuple(classes_ids)
                )

                etudiants = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    ev.id,
                    ev.nom,
                    ev.coefficient,
                    ev.classe_id,
                    c.nom AS classe_nom,
                    edt.jour_semaine,
                    edt.heure_debut,
                    edt.heure_fin
                FROM evaluations ev
                LEFT JOIN classes c
                    ON c.id = ev.classe_id
                LEFT JOIN emplois_du_temps edt
                    ON edt.id = ev.emploi_du_temps_id
                WHERE ev.matiere_id = %s
                ORDER BY ev.id DESC
                """,
                (matiere_id,)
            )

            evaluations = cursor.fetchall()

        return render_template(
            "saisir_notes_enseignant.html",
            matiere=matiere,
            etudiants=etudiants,
            evaluations=evaluations
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
                    e.id,
                    e.nom,
                    e.prenom,
                    e.filiere,
                    c.nom AS classe_nom
                FROM etudiants e
                INNER JOIN classes c
                    ON c.id = e.classe_id
                WHERE e.classe_id IN (
                    SELECT DISTINCT mc.classe_id
                    FROM enseignant_matieres em
                    INNER JOIN matiere_classes mc
                        ON mc.matiere_id = em.matiere_id
                    WHERE em.enseignant_id = %s
                )
                ORDER BY e.nom ASC, e.prenom ASC
                """,
                (enseignant_id,)
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


@enseignant_bp.route("/mon_emploi_du_temps_enseignant", endpoint="mon_emploi_du_temps")
@role_required("ENSEIGNANT")
def mon_emploi_du_temps():

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé.",
            "danger"
        )

        return redirect(url_for("auth.login"))

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                edt.*,
                m.nom AS matiere_nom,
                c.nom AS classe_nom,
                GROUP_CONCAT(ev.nom SEPARATOR ', ') AS evaluations_noms
            FROM emplois_du_temps edt
            INNER JOIN matieres m
                ON m.id = edt.matiere_id
            INNER JOIN classes c
                ON c.id = edt.classe_id
            LEFT JOIN evaluations ev
                ON ev.emploi_du_temps_id = edt.id
            WHERE edt.enseignant_id = %s
            GROUP BY edt.id
            ORDER BY edt.jour_semaine, edt.heure_debut
            """,
            (enseignant_id,)
        )

        creneaux_par_jour = {jour: [] for jour in JOURS_SEMAINE}

        for creneau in cursor.fetchall():
            creneaux_par_jour[creneau["jour_semaine"]].append(creneau)

    return render_template(
        "mon_emploi_du_temps_enseignant.html",
        jours=JOURS_SEMAINE,
        creneaux_par_jour=creneaux_par_jour
    )


@enseignant_bp.route(
    "/enseignant/cours/<int:matiere_id>",
    methods=["GET", "POST"],
    endpoint="cours_matiere"
)
@role_required("ENSEIGNANT")
def cours_matiere(matiere_id):

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé.",
            "danger"
        )

        return redirect(url_for("auth.login"))

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

            titre = request.form.get("titre", "").strip()
            fichier = request.files.get("fichier")

            if not titre:

                flash(
                    "Veuillez indiquer un titre.",
                    "warning"
                )

                return redirect(
                    url_for("enseignant.cours_matiere", matiere_id=matiere_id)
                )

            if not fichier_cours_autorise(fichier):

                flash(
                    "Type de fichier non autorisé (PDF, Word, PowerPoint, "
                    "Excel, texte ou zip).",
                    "danger"
                )

                return redirect(
                    url_for("enseignant.cours_matiere", matiere_id=matiere_id)
                )

            cursor.execute(
                """
                INSERT INTO cours
                (matiere_id, enseignant_id, titre)
                VALUES (%s, %s, %s)
                """,
                (matiere_id, enseignant_id, titre)
            )

            cours_id = cursor.lastrowid

            nom_original = secure_filename(fichier.filename)

            nom_fichier = f"cours_{cours_id}_{nom_original}"

            chemin_fichier = os.path.join(
                current_app.config["COURS_FOLDER"],
                nom_fichier
            )

            fichier.save(chemin_fichier)

            cursor.execute(
                """
                UPDATE cours
                SET fichier = %s
                WHERE id = %s
                """,
                (nom_fichier, cours_id)
            )

            notifier_matiere(
                cursor,
                matiere_id,
                "Nouveau cours",
                f"Un nouveau cours a été déposé en {matiere['nom']} : {titre}."
            )

            flash(
                "Cours ajouté avec succès !",
                "success"
            )

            return redirect(
                url_for("enseignant.cours_matiere", matiere_id=matiere_id)
            )

        cursor.execute(
            """
            SELECT
                c.*,
                en.nom AS enseignant_nom,
                en.prenom AS enseignant_prenom
            FROM cours c
            INNER JOIN enseignants en
                ON en.id = c.enseignant_id
            WHERE c.matiere_id = %s
            ORDER BY c.date_upload DESC
            """,
            (matiere_id,)
        )

        cours_liste = cursor.fetchall()

    return render_template(
        "cours_matiere.html",
        matiere=matiere,
        cours_liste=cours_liste,
        enseignant_id=enseignant_id
    )


@enseignant_bp.route(
    "/enseignant/supprimer_cours/<int:id>",
    methods=["POST"],
    endpoint="supprimer_cours"
)
@role_required("ENSEIGNANT")
def supprimer_cours(id):

    enseignant_id = session.get("enseignant_id")

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT matiere_id, enseignant_id, fichier
            FROM cours
            WHERE id = %s
            """,
            (id,)
        )

        cours = cursor.fetchone()

        if cours is None or cours["enseignant_id"] != enseignant_id:

            flash(
                "Cours introuvable ou accès interdit.",
                "danger"
            )

            return redirect(url_for("enseignant.espace_enseignant"))

        cursor.execute(
            """
            DELETE FROM cours
            WHERE id = %s
            """,
            (id,)
        )

        matiere_id = cours["matiere_id"]
        nom_fichier = cours["fichier"]

    if nom_fichier:

        chemin_fichier = os.path.join(
            current_app.config["COURS_FOLDER"],
            nom_fichier
        )

        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)

    flash(
        "Cours supprimé avec succès !",
        "success"
    )

    return redirect(
        url_for("enseignant.cours_matiere", matiere_id=matiere_id)
    )


@enseignant_bp.route(
    "/enseignant/telecharger_cours/<int:id>",
    endpoint="telecharger_cours"
)
@role_required("ENSEIGNANT")
def telecharger_cours(id):

    enseignant_id = session.get("enseignant_id")

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT c.fichier
            FROM cours c
            INNER JOIN enseignant_matieres em
                ON em.matiere_id = c.matiere_id
            WHERE c.id = %s
            AND em.enseignant_id = %s
            """,
            (id, enseignant_id)
        )

        cours = cursor.fetchone()

    if cours is None or not cours["fichier"]:

        flash(
            "Cours introuvable.",
            "danger"
        )

        return redirect(url_for("enseignant.espace_enseignant"))

    return send_from_directory(
        current_app.config["COURS_FOLDER"],
        cours["fichier"]
    )


@enseignant_bp.route(
    "/enseignant/evaluations/<int:matiere_id>",
    methods=["GET", "POST"],
    endpoint="evaluations_matiere"
)
@role_required("ENSEIGNANT")
def evaluations_matiere(matiere_id):

    enseignant_id = session.get("enseignant_id")

    if enseignant_id is None:

        session.clear()

        flash(
            "Aucun profil enseignant associé.",
            "danger"
        )

        return redirect(url_for("auth.login"))

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

        cursor.execute(
            """
            SELECT
                edt.id,
                edt.classe_id,
                c.nom AS classe_nom,
                edt.jour_semaine,
                edt.heure_debut,
                edt.heure_fin
            FROM emplois_du_temps edt
            INNER JOIN classes c
                ON c.id = edt.classe_id
            WHERE edt.matiere_id = %s
            AND edt.enseignant_id = %s
            ORDER BY edt.jour_semaine, edt.heure_debut
            """,
            (matiere_id, enseignant_id)
        )

        creneaux = cursor.fetchall()

        if request.method == "POST":

            nom = request.form.get("nom", "").strip()
            coefficient = request.form.get("coefficient", "1").strip()
            emploi_du_temps_id = request.form.get("emploi_du_temps_id")

            if not nom or not emploi_du_temps_id:

                flash(
                    "Veuillez indiquer un nom et choisir un créneau.",
                    "warning"
                )

                return redirect(
                    url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
                )

            try:
                coefficient = int(coefficient)

            except ValueError:

                flash(
                    "Le coefficient doit être un nombre entier.",
                    "danger"
                )

                return redirect(
                    url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
                )

            if coefficient < 1:

                flash(
                    "Le coefficient doit être au moins égal à 1.",
                    "danger"
                )

                return redirect(
                    url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
                )

            cursor.execute(
                """
                SELECT classe_id
                FROM emplois_du_temps
                WHERE id = %s
                AND matiere_id = %s
                AND enseignant_id = %s
                """,
                (emploi_du_temps_id, matiere_id, enseignant_id)
            )

            creneau = cursor.fetchone()

            if creneau is None:

                flash(
                    "Créneau invalide pour cette matière.",
                    "danger"
                )

                return redirect(
                    url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
                )

            cursor.execute(
                """
                INSERT INTO evaluations
                (matiere_id, enseignant_id, classe_id, emploi_du_temps_id, nom, coefficient)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    matiere_id,
                    enseignant_id,
                    creneau["classe_id"],
                    emploi_du_temps_id,
                    nom,
                    coefficient
                )
            )

            notifier_classe(
                cursor,
                creneau["classe_id"],
                "Nouvelle évaluation",
                f"Une évaluation \"{nom}\" a été programmée en {matiere['nom']}."
            )

            flash(
                "Évaluation ajoutée avec succès !",
                "success"
            )

            return redirect(
                url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
            )

        cursor.execute(
            """
            SELECT
                ev.*,
                en.nom AS enseignant_nom,
                en.prenom AS enseignant_prenom,
                c.nom AS classe_nom,
                edt.jour_semaine,
                edt.heure_debut,
                edt.heure_fin
            FROM evaluations ev
            INNER JOIN enseignants en
                ON en.id = ev.enseignant_id
            LEFT JOIN classes c
                ON c.id = ev.classe_id
            LEFT JOIN emplois_du_temps edt
                ON edt.id = ev.emploi_du_temps_id
            WHERE ev.matiere_id = %s
            ORDER BY ev.id DESC
            """,
            (matiere_id,)
        )

        evaluations = cursor.fetchall()

    return render_template(
        "evaluations_matiere.html",
        matiere=matiere,
        evaluations=evaluations,
        creneaux=creneaux,
        enseignant_id=enseignant_id
    )


@enseignant_bp.route(
    "/enseignant/supprimer_evaluation/<int:id>",
    methods=["POST"],
    endpoint="supprimer_evaluation"
)
@role_required("ENSEIGNANT")
def supprimer_evaluation(id):

    enseignant_id = session.get("enseignant_id")

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT matiere_id, enseignant_id
            FROM evaluations
            WHERE id = %s
            """,
            (id,)
        )

        evaluation = cursor.fetchone()

    if evaluation is None or evaluation["enseignant_id"] != enseignant_id:

        flash(
            "Évaluation introuvable ou accès interdit.",
            "danger"
        )

        return redirect(url_for("enseignant.espace_enseignant"))

    matiere_id = evaluation["matiere_id"]

    try:

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                DELETE FROM evaluations
                WHERE id = %s
                """,
                (id,)
            )

        flash(
            "Évaluation supprimée avec succès !",
            "success"
        )

    except mysql.connector.errors.IntegrityError:

        flash(
            "Impossible de supprimer cette évaluation : des notes y "
            "sont déjà rattachées.",
            "danger"
        )

    return redirect(
        url_for("enseignant.evaluations_matiere", matiere_id=matiere_id)
    )


@enseignant_bp.route("/enseignant/mes_notifications", endpoint="mes_notifications")
@role_required("ENSEIGNANT")
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
        "mes_notifications_enseignant.html",
        notifications=notifications
    )
