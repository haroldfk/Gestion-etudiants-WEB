import csv
import io

import mysql.connector
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for
)
from reportlab.pdfgen import canvas
from werkzeug.security import generate_password_hash

from config import db_cursor
from decorators import role_required
from utils import BLOCS_HORAIRES, JOURS_SEMAINE, calculer_mention, notifier_etudiant

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard", endpoint="dashboard")
@role_required("ADMIN")
def dashboard():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM etudiants
        """)

        nb_etudiants = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM utilisateurs
        """)

        nb_utilisateurs = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT
                e.nom,
                e.prenom,
                AVG(n.note) AS moyenne

            FROM etudiants e

            JOIN notes n
                ON e.id = n.etudiant_id

            GROUP BY e.id, e.nom, e.prenom

            ORDER BY moyenne DESC

            LIMIT 5
        """)

        top_etudiants = cursor.fetchall()

        cursor.execute("""
            SELECT
                filiere,
                COUNT(*) AS nombre
            FROM etudiants
            GROUP BY filiere
            ORDER BY nombre DESC
        """)

        stats_filieres = cursor.fetchall()

        cursor.execute("""
            SELECT
                c.id,
                c.nom,
                c.niveau,
                COUNT(DISTINCT e.id) AS nombre_etudiants,
                AVG(n.note) AS moyenne
            FROM classes c
            LEFT JOIN etudiants e
                ON e.classe_id = c.id
            LEFT JOIN notes n
                ON n.etudiant_id = e.id
            GROUP BY c.id, c.nom, c.niveau
            ORDER BY c.nom
        """)

        stats_classes = cursor.fetchall()

    return render_template(
        "dashboard.html",
        nom=session.get("nom", "Utilisateur"),
        nb_etudiants=nb_etudiants,
        nb_utilisateurs=nb_utilisateurs,
        top_etudiants=top_etudiants,
        stats_filieres=stats_filieres,
        stats_classes=stats_classes
    )


@admin_bp.route("/export_csv", endpoint="export_csv")
@role_required("ADMIN")
def export_csv():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
        SELECT *
        FROM etudiants
        """)

        etudiants = cursor.fetchall()

    output = io.StringIO()

    writer = csv.writer(
        output,
        delimiter=";")

    writer.writerow([
        "ID",
        "Nom",
        "Prenom",
        "Age",
        "Filiere"
    ])

    for etudiant in etudiants:

        writer.writerow([
            etudiant["id"],
            etudiant["nom"],
            etudiant["prenom"],
            etudiant["age"],
            etudiant["filiere"]
        ])

    csv_data = output.getvalue()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=etudiants.csv"
        }
    )


@admin_bp.route("/ajouter_etudiant", methods=["GET", "POST"], endpoint="ajouter_etudiant")
@role_required("ADMIN")
def ajouter_etudiant():

    with db_cursor(dictionary=True) as (connexion, cursor):

        if request.method == "POST":

            nom = request.form["nom"]
            prenom = request.form["prenom"]
            age = request.form["age"]
            filiere = request.form["filiere"]
            classe_id = request.form.get("classe_id") or None

            cursor.execute(
                """
                INSERT INTO etudiants (nom, prenom, age, filiere, classe_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (nom, prenom, age, filiere, classe_id)
            )

            flash(
                "Étudiant ajouté avec succès !",
                "success"
            )

            return redirect(
                url_for("admin.liste_etudiants")
            )

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

    return render_template(
        "ajouter_etudiant.html",
        classes=classes
    )


@admin_bp.route("/liste_etudiants", endpoint="liste_etudiants")
@role_required("ADMIN")
def liste_etudiants():

    recherche = request.args.get("recherche")

    with db_cursor(dictionary=True) as (connexion, cursor):

        if recherche:

            motif = "%" + recherche + "%"

            cursor.execute(
                """
                SELECT
                    e.*,
                    c.nom AS classe_nom
                FROM etudiants e
                LEFT JOIN classes c
                    ON c.id = e.classe_id
                WHERE e.nom LIKE %s
                OR e.prenom LIKE %s
                OR CONCAT(e.nom, ' ', e.prenom) LIKE %s
                OR CONCAT(e.prenom, ' ', e.nom) LIKE %s
                """,
                (motif, motif, motif, motif)
            )

        else:

            cursor.execute("""
                SELECT
                    e.*,
                    c.nom AS classe_nom
                FROM etudiants e
                LEFT JOIN classes c
                    ON c.id = e.classe_id
            """)

        etudiants = cursor.fetchall()

    return render_template(
        "liste_etudiants.html",
        etudiants=etudiants
    )


@admin_bp.route("/supprimer_etudiant/<int:id>", methods=["POST"], endpoint="supprimer_etudiant")
@role_required("ADMIN")
def supprimer_etudiant(id):

    with db_cursor() as (connexion, cursor):

        cursor.execute(
            """
            DELETE FROM etudiants
            WHERE id = %s
            """,
            (id,)
        )

    flash(
       "Étudiant supprimé avec succès !",
       "success"
    )

    return redirect(url_for("admin.liste_etudiants"))


@admin_bp.route("/modifier_etudiant/<int:id>", methods=["GET", "POST"], endpoint="modifier_etudiant")
@role_required("ADMIN")
def modifier_etudiant(id):

    if request.method == "POST":

        nom = request.form["nom"]
        prenom = request.form["prenom"]
        age = request.form["age"]
        filiere = request.form["filiere"]
        classe_id = request.form.get("classe_id") or None

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                UPDATE etudiants
                SET nom=%s,
                    prenom=%s,
                    age=%s,
                    filiere=%s,
                    classe_id=%s
                WHERE id=%s
                """,
                (nom, prenom, age, filiere, classe_id, id)
            )

        flash(
            "Étudiant modifié avec succès !",
            "success"
        )

        return redirect(url_for("admin.liste_etudiants"))

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            "SELECT * FROM etudiants WHERE id=%s",
            (id,)
        )

        etudiant = cursor.fetchone()

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

    return render_template(
        "modifier_etudiant.html",
        etudiant=etudiant,
        classes=classes
    )


@admin_bp.route("/notes/<int:id>", endpoint="notes")
@role_required("ADMIN")
def notes(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            "SELECT * FROM etudiants WHERE id=%s",
            (id,)
        )

        etudiant = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM notes
            WHERE etudiant_id=%s
            """,
            (id,)
        )

        notes = cursor.fetchall()

        cursor.execute(
            """
            SELECT AVG(note) AS moyenne
            FROM notes
            WHERE etudiant_id=%s
            """,
            (id,)
        )

        moyenne = cursor.fetchone()["moyenne"]

    mention = calculer_mention(moyenne)

    return render_template(
        "notes.html",
        etudiant=etudiant,
        notes=notes,
        moyenne=moyenne,
        mention=mention
    )


@admin_bp.route("/ajouter_note/<int:id>", methods=["GET", "POST"], endpoint="ajouter_note")
@role_required("ADMIN")
def ajouter_note(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT *
            FROM matieres
            ORDER BY nom
        """)

        matieres = cursor.fetchall()

        if request.method == "POST":

            matiere = request.form["matiere"]
            note = request.form.get("note")

            if not matiere or note is None:

                flash(
                    "Veuillez remplir tous les champs.",
                    "warning"
                )

                return redirect(url_for("admin.ajouter_note", id=id))

            try:
                note = float(note)

            except ValueError:

                flash(
                    "La note doit être un nombre.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_note", id=id))

            if note < 0 or note > 20:

                flash(
                    "La note doit être comprise entre 0 et 20.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_note", id=id))

            cursor.execute(
                """
                INSERT INTO notes
                (etudiant_id, matiere, note)
                VALUES (%s, %s, %s)
                """,
                (id, matiere, note)
            )

            flash(
                "Note ajoutée avec succès !",
                "success"
            )

            return redirect(
                url_for("admin.notes", id=id)
            )

        return render_template(
            "ajouter_note.html",
            matieres=matieres
        )


@admin_bp.route("/supprimer_note/<int:note_id>/<int:etudiant_id>", methods=["POST"], endpoint="supprimer_note")
@role_required("ADMIN")
def supprimer_note(note_id, etudiant_id):

    with db_cursor() as (connexion, cursor):

        cursor.execute(
            """
            DELETE FROM notes
            WHERE id=%s
            """,
            (note_id,)
        )

    flash(
        "Note supprimée avec succès !",
        "success"
    )

    return redirect(
        url_for("admin.notes", id=etudiant_id)
    )


@admin_bp.route("/modifier_note/<int:id>", methods=["GET", "POST"], endpoint="modifier_note")
@role_required("ADMIN")
def modifier_note(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        if request.method == "POST":

            matiere = request.form["matiere"]
            note = request.form.get("note")

            if not matiere or note is None:

                flash(
                    "Veuillez remplir tous les champs.",
                    "warning"
                )

                return redirect(url_for("admin.modifier_note", id=id))

            try:
                note = float(note)

            except ValueError:

                flash(
                    "La note doit être un nombre.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_note", id=id))

            if note < 0 or note > 20:

                flash(
                    "La note doit être comprise entre 0 et 20.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_note", id=id))

            cursor.execute(
                """
                UPDATE notes
                SET matiere=%s,
                    note=%s
                WHERE id=%s
                """,
                (matiere, note, id)
            )

            cursor.execute(
                """
                SELECT etudiant_id
                FROM notes
                WHERE id=%s
                """,
                (id,)
            )

            resultat = cursor.fetchone()

            flash(
                "Note modifiée avec succès !",
                "success"
            )

            return redirect(
                url_for("admin.notes", id=resultat["etudiant_id"])
            )

        cursor.execute(
            """
            SELECT *
            FROM notes
            WHERE id=%s
            """,
            (id,)
        )

        note = cursor.fetchone()

    return render_template(
        "modifier_note.html",
        note=note
    )


@admin_bp.route("/classement", endpoint="classement")
@role_required("ADMIN")
def classement():

    filiere = request.args.get("filiere")
    classe_id = request.args.get("classe_id")

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT DISTINCT filiere
            FROM etudiants
            ORDER BY filiere
        """)

        filieres = cursor.fetchall()

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

        conditions = []
        parametres = []

        if filiere:

            conditions.append("e.filiere = %s")
            parametres.append(filiere)

        if classe_id:

            conditions.append("e.classe_id = %s")
            parametres.append(classe_id)

        clause_where = ""

        if conditions:

            clause_where = "WHERE " + " AND ".join(conditions)

        cursor.execute(
            f"""
            SELECT
                e.id,
                e.nom,
                e.prenom,
                e.filiere,
                c.nom AS classe_nom,
                AVG(n.note) AS moyenne
            FROM etudiants e
            JOIN notes n
                ON e.id = n.etudiant_id
            LEFT JOIN classes c
                ON c.id = e.classe_id
            {clause_where}
            GROUP BY
                e.id,
                e.nom,
                e.prenom,
                e.filiere,
                c.nom
            ORDER BY moyenne DESC
            """,
            tuple(parametres)
        )

        classement = cursor.fetchall()

    return render_template(
        "classement.html",
        classement=classement,
        filieres=filieres,
        filiere_selectionnee=filiere,
        classes=classes,
        classe_selectionnee=classe_id
    )


@admin_bp.route("/matieres", endpoint="matieres")
@role_required("ADMIN")
def matieres():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT
                m.*,
                GROUP_CONCAT(c.nom ORDER BY c.nom SEPARATOR ', ') AS classes_noms
            FROM matieres m
            LEFT JOIN matiere_classes mc
                ON mc.matiere_id = m.id
            LEFT JOIN classes c
                ON c.id = mc.classe_id
            GROUP BY m.id
            ORDER BY m.nom
        """)

        matieres = cursor.fetchall()

    return render_template(
        "matieres.html",
        matieres=matieres
    )


@admin_bp.route("/ajouter_matiere", methods=["GET", "POST"], endpoint="ajouter_matiere")
@role_required("ADMIN")
def ajouter_matiere():

    with db_cursor(dictionary=True) as (connexion, cursor):

        if request.method == "POST":

            nom = request.form["nom"]
            classes_ids = request.form.getlist("classes")

            cursor.execute("""
                INSERT INTO matieres(nom)
                VALUES(%s)
            """, (nom,))

            matiere_id = cursor.lastrowid

            for classe_id in classes_ids:

                cursor.execute(
                    """
                    INSERT INTO matiere_classes (matiere_id, classe_id)
                    VALUES (%s, %s)
                    """,
                    (matiere_id, classe_id)
                )

            flash(
                "Matière ajoutée avec succès",
                "success"
            )

            return redirect(url_for("admin.matieres"))

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

    return render_template(
        "ajouter_matiere.html",
        classes=classes
    )


@admin_bp.route("/supprimer_matiere/<int:id>", methods=["POST"], endpoint="supprimer_matiere")
@role_required("ADMIN")
def supprimer_matiere(id):

    with db_cursor() as (connexion, cursor):

        cursor.execute(
            """
            DELETE FROM matieres
            WHERE id = %s
            """,
            (id,)
        )

    flash(
        "Matière supprimée avec succès !",
        "success"
    )

    return redirect(url_for("admin.matieres"))


@admin_bp.route("/modifier_matiere/<int:id>", methods=["GET", "POST"], endpoint="modifier_matiere")
@role_required("ADMIN")
def modifier_matiere(id):

    if request.method == "POST":

        nom = request.form["nom"]
        classes_ids = request.form.getlist("classes")

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                UPDATE matieres
                SET nom=%s
                WHERE id=%s
                """,
                (nom, id)
            )

            cursor.execute(
                """
                DELETE FROM matiere_classes
                WHERE matiere_id=%s
                """,
                (id,)
            )

            for classe_id in classes_ids:

                cursor.execute(
                    """
                    INSERT INTO matiere_classes (matiere_id, classe_id)
                    VALUES (%s, %s)
                    """,
                    (id, classe_id)
                )

        flash(
            "Matière modifiée avec succès !",
            "success"
        )

        return redirect(url_for("admin.matieres"))

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM matieres
            WHERE id=%s
            """,
            (id,)
        )

        matiere = cursor.fetchone()

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

        cursor.execute(
            """
            SELECT classe_id
            FROM matiere_classes
            WHERE matiere_id=%s
            """,
            (id,)
        )

        classes_selectionnees = [
            ligne["classe_id"] for ligne in cursor.fetchall()
        ]

    return render_template(
        "modifier_matiere.html",
        matiere=matiere,
        classes=classes,
        classes_selectionnees=classes_selectionnees
    )


@admin_bp.route("/classes", endpoint="classes")
@role_required("ADMIN")
def classes():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT *
            FROM classes
            ORDER BY nom
        """)

        classes = cursor.fetchall()

    return render_template(
        "classes.html",
        classes=classes
    )


@admin_bp.route("/ajouter_classe", methods=["GET", "POST"], endpoint="ajouter_classe")
@role_required("ADMIN")
def ajouter_classe():

    if request.method == "POST":

        nom = request.form["nom"]
        niveau = request.form.get("niveau", "").strip()
        annee_universitaire = request.form.get("annee_universitaire", "").strip()

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                INSERT INTO classes (nom, niveau, annee_universitaire)
                VALUES (%s, %s, %s)
                """,
                (nom, niveau or None, annee_universitaire or None)
            )

        flash(
            "Classe ajoutée avec succès !",
            "success"
        )

        return redirect(url_for("admin.classes"))

    return render_template(
        "ajouter_classe.html"
    )


@admin_bp.route("/modifier_classe/<int:id>", methods=["GET", "POST"], endpoint="modifier_classe")
@role_required("ADMIN")
def modifier_classe(id):

    if request.method == "POST":

        nom = request.form["nom"]
        niveau = request.form.get("niveau", "").strip()
        annee_universitaire = request.form.get("annee_universitaire", "").strip()

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                UPDATE classes
                SET nom=%s,
                    niveau=%s,
                    annee_universitaire=%s
                WHERE id=%s
                """,
                (nom, niveau or None, annee_universitaire or None, id)
            )

        flash(
            "Classe modifiée avec succès !",
            "success"
        )

        return redirect(url_for("admin.classes"))

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM classes
            WHERE id=%s
            """,
            (id,)
        )

        classe = cursor.fetchone()

    return render_template(
        "modifier_classe.html",
        classe=classe
    )


@admin_bp.route("/supprimer_classe/<int:id>", methods=["POST"], endpoint="supprimer_classe")
@role_required("ADMIN")
def supprimer_classe(id):

    try:

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                DELETE FROM classes
                WHERE id = %s
                """,
                (id,)
            )

        flash(
            "Classe supprimée avec succès !",
            "success"
        )

    except mysql.connector.errors.IntegrityError:

        flash(
            "Impossible de supprimer cette classe : des étudiants ou "
            "des matières y sont encore rattachés.",
            "danger"
        )

    return redirect(url_for("admin.classes"))


@admin_bp.route("/bulletin/<int:id>", endpoint="bulletin")
@role_required("ADMIN")
def bulletin(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM etudiants
            WHERE id=%s
            """,
            (id,)
        )

        etudiant = cursor.fetchone()

        cursor.execute(
            """
            SELECT *
            FROM notes
            WHERE etudiant_id=%s
            """,
            (id,)
        )

        notes = cursor.fetchall()

        cursor.execute(
            """
            SELECT AVG(note) AS moyenne
            FROM notes
            WHERE etudiant_id=%s
            """,
            (id,)
        )

        moyenne = cursor.fetchone()["moyenne"]

    mention = calculer_mention(moyenne)

    response = make_response()

    response.headers["Content-Type"] = "application/pdf"

    response.headers["Content-Disposition"] = (
        f"attachment; filename=bulletin_{id}.pdf"
    )

    pdf = canvas.Canvas(response.stream)

    pdf.setTitle("Bulletin")

    pdf.setFont("Helvetica-Bold", 18)

    pdf.drawString(180, 800, "BULLETIN DE NOTES")

    pdf.line(50, 790, 550, 790)

    pdf.setFont("Helvetica", 12)

    pdf.drawString(50, 750, f"Nom : {etudiant['nom']}")

    pdf.drawString(50, 730, f"Prénom : {etudiant['prenom']}")

    pdf.drawString(50, 710, f"Filière : {etudiant['filiere']}")

    pdf.line(50, 690, 550, 690)

    y = 650

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(60, y, "Matières")

    pdf.drawString(350, y, "Note")

    y -= 20

    pdf.line(50, y, 550, y)

    y -= 20

    pdf.setFont("Helvetica", 12)

    for note in notes:

        pdf.drawString(60, y, str(note["matiere"]))

        pdf.drawString(350, y, str(note["note"]))

        y -= 25

    pdf.line(50, y, 550, y)

    y -= 40

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(60, y, f"Moyenne Générale : {round(moyenne, 2)}")

    y -= 25

    pdf.drawString(60, y, f"Mention : {mention}")

    pdf.save()

    return response


@admin_bp.route("/absences/<int:id>", endpoint="absences")
@role_required("ADMIN")
def absences(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM etudiants
            WHERE id=%s
            """,
            (id,)
        )

        etudiant = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                a.*,
                m.nom AS matiere_nom,
                en.nom AS enseignant_nom,
                en.prenom AS enseignant_prenom
            FROM absences a
            LEFT JOIN matieres m
                ON m.id = a.matiere_id
            LEFT JOIN enseignants en
                ON en.id = a.enseignant_id
            WHERE a.etudiant_id=%s
            ORDER BY a.date_absence DESC
            """,
            (id,)
        )

        absences = cursor.fetchall()

    return render_template(
        "absences.html",
        etudiant=etudiant,
        absences=absences
    )


@admin_bp.route("/ajouter_absence/<int:id>", methods=["GET", "POST"], endpoint="ajouter_absence")
@role_required("ADMIN", "ENSEIGNANT")
def ajouter_absence(id):

    est_enseignant = session.get("role") == "ENSEIGNANT"

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT id, classe_id
            FROM etudiants
            WHERE id = %s
            """,
            (id,)
        )

        etudiant = cursor.fetchone()

        if etudiant is None:

            flash(
                "Étudiant introuvable.",
                "danger"
            )

            return redirect(url_for("admin.dashboard"))

        classe_id = etudiant["classe_id"]

        if est_enseignant:

            cursor.execute(
                """
                SELECT
                    edt.id,
                    edt.jour_semaine,
                    edt.heure_debut,
                    edt.heure_fin,
                    m.nom AS matiere_nom,
                    en.nom AS enseignant_nom,
                    en.prenom AS enseignant_prenom
                FROM emplois_du_temps edt
                INNER JOIN matieres m
                    ON m.id = edt.matiere_id
                INNER JOIN enseignants en
                    ON en.id = edt.enseignant_id
                WHERE edt.classe_id = %s
                AND edt.enseignant_id = %s
                ORDER BY edt.jour_semaine, edt.heure_debut
                """,
                (classe_id, session.get("enseignant_id"))
            )

            creneaux = cursor.fetchall()

        elif classe_id is not None:

            cursor.execute(
                """
                SELECT
                    edt.id,
                    edt.jour_semaine,
                    edt.heure_debut,
                    edt.heure_fin,
                    m.nom AS matiere_nom,
                    en.nom AS enseignant_nom,
                    en.prenom AS enseignant_prenom
                FROM emplois_du_temps edt
                INNER JOIN matieres m
                    ON m.id = edt.matiere_id
                INNER JOIN enseignants en
                    ON en.id = edt.enseignant_id
                WHERE edt.classe_id = %s
                ORDER BY edt.jour_semaine, edt.heure_debut
                """,
                (classe_id,)
            )

            creneaux = cursor.fetchall()

        else:

            creneaux = []

        if est_enseignant and not creneaux:

            flash(
                "Vous ne pouvez déclarer une absence que pour un étudiant "
                "de vos classes.",
                "danger"
            )

            return redirect(url_for("enseignant.mes_etudiants"))

        if request.method == "POST":

            date_absence = request.form["date_absence"]
            motif = request.form["motif"]
            emploi_du_temps_id = request.form.get("emploi_du_temps_id")

            if not date_absence or not motif or not emploi_du_temps_id:

                flash(
                    "Veuillez remplir tous les champs, y compris le créneau.",
                    "warning"
                )

                return redirect(url_for("admin.ajouter_absence", id=id))

            if est_enseignant:

                cursor.execute(
                    """
                    SELECT matiere_id, enseignant_id
                    FROM emplois_du_temps
                    WHERE id = %s
                    AND classe_id = %s
                    AND enseignant_id = %s
                    """,
                    (emploi_du_temps_id, classe_id, session.get("enseignant_id"))
                )

            else:

                cursor.execute(
                    """
                    SELECT matiere_id, enseignant_id
                    FROM emplois_du_temps
                    WHERE id = %s
                    AND classe_id = %s
                    """,
                    (emploi_du_temps_id, classe_id)
                )

            creneau = cursor.fetchone()

            if creneau is None:

                flash(
                    "Créneau invalide.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_absence", id=id))

            cursor.execute(
                """
                INSERT INTO absences
                (
                    etudiant_id,
                    date_absence,
                    motif,
                    matiere_id,
                    enseignant_id,
                    emploi_du_temps_id
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    id,
                    date_absence,
                    motif,
                    creneau["matiere_id"],
                    creneau["enseignant_id"],
                    emploi_du_temps_id
                )
            )

            notifier_etudiant(
                cursor,
                id,
                "Absence déclarée",
                f"Une absence a été enregistrée pour le {date_absence}. "
                "Vous pouvez envoyer un justificatif depuis votre espace."
            )

            flash(
                "Absence enregistrée avec succès. Le statut est désormais 'En attente' jusqu'à l'envoi et la validation d'un justificatif.",
                "success"
            )

            if session.get("role") == "ADMIN":
                return redirect(
                    url_for("admin.absences", id=id)
                )

            return redirect(
                url_for("enseignant.mes_etudiants")
            )

    return render_template(
        "ajouter_absence.html",
        etudiant_id=id,
        creneaux=creneaux
    )


@admin_bp.route("/supprimer_absence/<int:id>", methods=["POST"], endpoint="supprimer_absence")
@role_required("ADMIN")
def supprimer_absence(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            "SELECT etudiant_id FROM absences WHERE id = %s",
            (id,)
        )

        absence = cursor.fetchone()

        if absence is None:

            flash(
                "Absence introuvable.",
                "danger"
            )

            return redirect(url_for("admin.dashboard"))

        cursor.execute(
            "DELETE FROM absences WHERE id = %s",
            (id,)
        )

        etudiant_id = absence["etudiant_id"]

    flash(
        "Absence supprimée avec succès !",
        "success"
    )

    return redirect(
        url_for("admin.absences", id=etudiant_id)
    )


@admin_bp.route(
    "/creer_compte_etudiant",
    methods=["GET", "POST"],
    endpoint="creer_compte_etudiant"
)
@role_required("ADMIN")
def creer_compte_etudiant():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        if request.method == "POST":

            etudiant_id = request.form["etudiant_id"]

            email = request.form["email"].strip().lower()

            mot_de_passe = request.form["mot_de_passe"]

            cursor.execute(
                """
                SELECT *
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

                return redirect(url_for("admin.creer_compte_etudiant"))

            cursor.execute(
                """
                SELECT id
                FROM utilisateurs
                WHERE email = %s
                """,
                (email,)
            )

            if cursor.fetchone():

                flash(
                    "Cet email est déjà utilisé.",
                    "danger"
                )

                return redirect(url_for("admin.creer_compte_etudiant"))

            cursor.execute(
                """
                SELECT id
                FROM utilisateurs
                WHERE etudiant_id = %s
                """,
                (etudiant_id,)
            )

            if cursor.fetchone():

                flash(
                    "Cet étudiant possède déjà un compte.",
                    "warning"
                )

                return redirect(url_for("admin.creer_compte_etudiant"))

            mot_de_passe_hash = generate_password_hash(
                mot_de_passe
            )

            cursor.execute(
                """
                INSERT INTO utilisateurs
                (
                    nom,
                    email,
                    mot_de_passe,
                    role,
                    etudiant_id,
                    enseignant_id
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    etudiant["nom"],
                    email,
                    mot_de_passe_hash,
                    "ETUDIANT",
                    etudiant_id,
                    None
                )
            )

            flash(
                "Compte étudiant créé avec succès !",
                "success"
            )

            return redirect(url_for("admin.creer_compte_etudiant"))

        cursor.execute(
            """
            SELECT
                e.id,
                e.nom,
                e.prenom,
                e.filiere

            FROM etudiants e

            LEFT JOIN utilisateurs u
                ON u.etudiant_id = e.id

            WHERE u.id IS NULL

            ORDER BY e.nom, e.prenom
            """
        )

        etudiants = cursor.fetchall()

    return render_template(
        "creer_compte_etudiant.html",
        etudiants=etudiants
    )


@admin_bp.route("/voir_justificatif/<int:absence_id>", endpoint="voir_justificatif")
@role_required("ADMIN")
def voir_justificatif(absence_id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT justificatif
            FROM absences
            WHERE id = %s
            """,
            (absence_id,)
        )

        absence = cursor.fetchone()

    if absence is None:

        flash(
            "Absence introuvable.",
            "danger"
        )

        return redirect(url_for("admin.dashboard"))

    if not absence["justificatif"]:

        flash(
            "Aucun justificatif disponible.",
            "warning"
        )

        return redirect(url_for("admin.dashboard"))

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        absence["justificatif"]
    )


@admin_bp.route(
    "/accepter_justificatif/<int:absence_id>",
    methods=["POST"],
    endpoint="accepter_justificatif"
)
@role_required("ADMIN")
def accepter_justificatif(absence_id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                id,
                etudiant_id,
                justificatif

            FROM absences

            WHERE id = %s
            """,
            (absence_id,)
        )

        absence = cursor.fetchone()

        if absence is None:

            flash(
                "Absence introuvable.",
                "danger"
            )

            return redirect(url_for("admin.dashboard"))

        if not absence["justificatif"]:

            flash(
                "Impossible d'accepter : aucun justificatif envoyé.",
                "warning"
            )

            return redirect(
                url_for("admin.absences", id=absence["etudiant_id"])
            )

        cursor.execute(
            """
            UPDATE absences

            SET statut = %s

            WHERE id = %s
            """,
            ("Justifiée", absence_id)
        )

        etudiant_id = absence["etudiant_id"]

        notifier_etudiant(
            cursor,
            etudiant_id,
            "Justificatif accepté",
            "Votre justificatif d'absence a été accepté."
        )

    flash(
        "Justificatif accepté avec succès.",
        "success"
    )

    return redirect(
        url_for("admin.absences", id=etudiant_id)
    )


@admin_bp.route(
    "/refuser_justificatif/<int:absence_id>",
    methods=["POST"],
    endpoint="refuser_justificatif"
)
@role_required("ADMIN")
def refuser_justificatif(absence_id):

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT
                id,
                etudiant_id,
                justificatif

            FROM absences

            WHERE id = %s
            """,
            (absence_id,)
        )

        absence = cursor.fetchone()

        if absence is None:

            flash(
                "Absence introuvable.",
                "danger"
            )

            return redirect(url_for("admin.dashboard"))

        if not absence["justificatif"]:

            flash(
                "Impossible de refuser : aucun justificatif envoyé.",
                "warning"
            )

            return redirect(
                url_for("admin.absences", id=absence["etudiant_id"])
            )

        cursor.execute(
            """
            UPDATE absences

            SET statut = %s

            WHERE id = %s
            """,
            ("Refusée", absence_id)
        )

        etudiant_id = absence["etudiant_id"]

        notifier_etudiant(
            cursor,
            etudiant_id,
            "Justificatif refusé",
            "Votre justificatif d'absence a été refusé."
        )

    flash(
        "Justificatif refusé.",
        "warning"
    )

    return redirect(
        url_for("admin.absences", id=etudiant_id)
    )


@admin_bp.route(
    "/creer_compte_enseignant",
    methods=["GET", "POST"],
    endpoint="creer_compte_enseignant"
)
@role_required("ADMIN")
def creer_compte_enseignant():

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        if request.method == "POST":

            nom = request.form["nom"].strip()

            prenom = request.form["prenom"].strip()

            email = request.form["email"].strip().lower()

            telephone = request.form.get("telephone", "").strip()

            specialite = request.form.get("specialite", "").strip()

            mot_de_passe = request.form["mot_de_passe"]

            matieres_ids = request.form.getlist("matieres")

            if not matieres_ids:

                flash(
                    "Veuillez sélectionner au moins une matière.",
                    "warning"
                )

                cursor.execute(
                    """
                    SELECT id, nom
                    FROM matieres
                    ORDER BY nom
                    """
                )

                matieres = cursor.fetchall()

                return render_template(
                    "creer_compte_enseignant.html",
                    matieres=matieres
                )

            cursor.execute(
                """
                SELECT id
                FROM utilisateurs
                WHERE email = %s
                """,
                (email,)
            )

            if cursor.fetchone():

                flash(
                    "Cet email possède déjà un compte utilisateur.",
                    "danger"
                )

                return redirect(url_for("admin.creer_compte_enseignant"))

            cursor.execute(
                """
                SELECT id
                FROM enseignants
                WHERE email = %s
                """,
                (email,)
            )

            if cursor.fetchone():

                flash(
                    "Un enseignant utilise déjà cet email.",
                    "danger"
                )

                return redirect(url_for("admin.creer_compte_enseignant"))

            try:

                cursor.execute(
                    """
                    INSERT INTO enseignants
                    (
                        nom,
                        prenom,
                        email,
                        telephone,
                        specialite
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        nom,
                        prenom,
                        email,
                        telephone or None,
                        specialite or None
                    )
                )

                enseignant_id = cursor.lastrowid

                mot_de_passe_hash = generate_password_hash(
                    mot_de_passe
                )

                cursor.execute(
                    """
                    INSERT INTO utilisateurs
                    (
                        nom,
                        email,
                        mot_de_passe,
                        role,
                        etudiant_id,
                        enseignant_id
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        nom,
                        email,
                        mot_de_passe_hash,
                        "ENSEIGNANT",
                        None,
                        enseignant_id
                    )
                )

                for matiere_id in matieres_ids:

                    cursor.execute(
                        """
                        INSERT INTO enseignant_matieres
                        (
                            enseignant_id,
                            matiere_id
                        )

                        VALUES
                        (
                            %s,
                            %s
                        )
                        """,
                        (enseignant_id, matiere_id)
                    )

                connexion.commit()

                flash(
                    "Enseignant et compte de connexion créés avec succès !",
                    "success"
                )

            except Exception as erreur:

                connexion.rollback()

                current_app.logger.error(
                    "Erreur création enseignant : %r",
                    erreur
                )

                flash(
                    "Erreur lors de la création de l'enseignant.",
                    "danger"
                )

            return redirect(url_for("admin.creer_compte_enseignant"))

        cursor.execute(
            """
            SELECT
                id,
                nom

            FROM matieres

            ORDER BY nom
            """
        )

        matieres = cursor.fetchall()

    return render_template(
        "creer_compte_enseignant.html",
        matieres=matieres
    )


@admin_bp.route("/enseignants", endpoint="enseignants")
@role_required("ADMIN")
def enseignants():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT
                e.*,
                COUNT(em.matiere_id) AS nombre_matieres
            FROM enseignants e
            LEFT JOIN enseignant_matieres em
                ON em.enseignant_id = e.id
            GROUP BY e.id
            ORDER BY e.nom ASC, e.prenom ASC
        """)

        enseignants = cursor.fetchall()

    return render_template(
        "enseignants.html",
        enseignants=enseignants
    )


@admin_bp.route(
    "/modifier_matieres_enseignant/<int:id>",
    methods=["GET", "POST"],
    endpoint="modifier_matieres_enseignant"
)
@role_required("ADMIN")
def modifier_matieres_enseignant(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM enseignants
            WHERE id = %s
            """,
            (id,)
        )

        enseignant = cursor.fetchone()

        if enseignant is None:

            flash(
                "Enseignant introuvable.",
                "danger"
            )

            return redirect(url_for("admin.enseignants"))

        if request.method == "POST":

            matieres_ids = request.form.getlist("matieres")

            if not matieres_ids:

                flash(
                    "Veuillez sélectionner au moins une matière.",
                    "warning"
                )

                return redirect(
                    url_for("admin.modifier_matieres_enseignant", id=id)
                )

            cursor.execute(
                """
                DELETE FROM enseignant_matieres
                WHERE enseignant_id = %s
                """,
                (id,)
            )

            for matiere_id in matieres_ids:

                cursor.execute(
                    """
                    INSERT INTO enseignant_matieres
                    (enseignant_id, matiere_id)
                    VALUES (%s, %s)
                    """,
                    (id, matiere_id)
                )

            flash(
                "Matières de l'enseignant mises à jour avec succès !",
                "success"
            )

            return redirect(url_for("admin.enseignants"))

        cursor.execute("""
            SELECT id, nom
            FROM matieres
            ORDER BY nom
        """)

        matieres = cursor.fetchall()

        cursor.execute(
            """
            SELECT matiere_id
            FROM enseignant_matieres
            WHERE enseignant_id = %s
            """,
            (id,)
        )

        matieres_selectionnees = [
            ligne["matiere_id"] for ligne in cursor.fetchall()
        ]

    return render_template(
        "modifier_matieres_enseignant.html",
        enseignant=enseignant,
        matieres=matieres,
        matieres_selectionnees=matieres_selectionnees
    )


@admin_bp.route(
    "/modifier_enseignant/<int:id>",
    methods=["GET", "POST"],
    endpoint="modifier_enseignant"
)
@role_required("ADMIN")
def modifier_enseignant(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM enseignants
            WHERE id = %s
            """,
            (id,)
        )

        enseignant = cursor.fetchone()

        if enseignant is None:

            flash(
                "Enseignant introuvable.",
                "danger"
            )

            return redirect(url_for("admin.enseignants"))

        if request.method == "POST":

            nom = request.form["nom"].strip()
            prenom = request.form["prenom"].strip()
            email = request.form["email"].strip().lower()
            telephone = request.form.get("telephone", "").strip()
            specialite = request.form.get("specialite", "").strip()

            cursor.execute(
                """
                SELECT id
                FROM enseignants
                WHERE email = %s
                AND id != %s
                """,
                (email, id)
            )

            if cursor.fetchone():

                flash(
                    "Un autre enseignant utilise déjà cet email.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_enseignant", id=id))

            cursor.execute(
                """
                UPDATE enseignants
                SET nom=%s,
                    prenom=%s,
                    email=%s,
                    telephone=%s,
                    specialite=%s
                WHERE id=%s
                """,
                (nom, prenom, email, telephone or None, specialite or None, id)
            )

            flash(
                "Enseignant modifié avec succès !",
                "success"
            )

            return redirect(url_for("admin.enseignants"))

    return render_template(
        "modifier_enseignant.html",
        enseignant=enseignant
    )


@admin_bp.route(
    "/supprimer_enseignant/<int:id>",
    methods=["POST"],
    endpoint="supprimer_enseignant"
)
@role_required("ADMIN")
def supprimer_enseignant(id):

    with db_cursor() as (connexion, cursor):

        cursor.execute(
            """
            DELETE FROM enseignants
            WHERE id = %s
            """,
            (id,)
        )

    flash(
        "Enseignant supprimé avec succès !",
        "success"
    )

    return redirect(url_for("admin.enseignants"))


@admin_bp.route(
    "/emploi_du_temps/<int:classe_id>",
    endpoint="emploi_du_temps"
)
@role_required("ADMIN")
def emploi_du_temps(classe_id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM classes
            WHERE id = %s
            """,
            (classe_id,)
        )

        classe = cursor.fetchone()

        if classe is None:

            flash(
                "Classe introuvable.",
                "danger"
            )

            return redirect(url_for("admin.classes"))

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
            (classe_id,)
        )

        creneaux_par_jour = {jour: [] for jour in JOURS_SEMAINE}

        for creneau in cursor.fetchall():
            creneaux_par_jour[creneau["jour_semaine"]].append(creneau)

    return render_template(
        "emploi_du_temps.html",
        classe=classe,
        jours=JOURS_SEMAINE,
        creneaux_par_jour=creneaux_par_jour
    )


def _combinaisons_matiere_enseignant(cursor, classe_id):
    """Couples (matière, enseignant) valides pour une classe donnée :
    la matière doit être associée à la classe, et l'enseignant doit
    être affecté à cette matière."""

    cursor.execute(
        """
        SELECT DISTINCT
            m.id AS matiere_id,
            m.nom AS matiere_nom,
            en.id AS enseignant_id,
            en.nom AS enseignant_nom,
            en.prenom AS enseignant_prenom
        FROM matiere_classes mc
        INNER JOIN matieres m
            ON m.id = mc.matiere_id
        INNER JOIN enseignant_matieres em
            ON em.matiere_id = m.id
        INNER JOIN enseignants en
            ON en.id = em.enseignant_id
        WHERE mc.classe_id = %s
        ORDER BY m.nom, en.nom
        """,
        (classe_id,)
    )

    return cursor.fetchall()


@admin_bp.route(
    "/ajouter_creneau/<int:classe_id>",
    methods=["GET", "POST"],
    endpoint="ajouter_creneau"
)
@role_required("ADMIN")
def ajouter_creneau(classe_id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM classes
            WHERE id = %s
            """,
            (classe_id,)
        )

        classe = cursor.fetchone()

        if classe is None:

            flash(
                "Classe introuvable.",
                "danger"
            )

            return redirect(url_for("admin.classes"))

        combinaisons = _combinaisons_matiere_enseignant(cursor, classe_id)

        if request.method == "POST":

            combinaison = request.form.get("combinaison", "")
            jour_semaine = request.form.get("jour_semaine")
            bloc_horaire = request.form.get("bloc_horaire", "")
            salle = request.form.get("salle", "").strip()

            if (
                "|" not in combinaison
                or not jour_semaine
                or "|" not in bloc_horaire
            ):

                flash(
                    "Veuillez remplir tous les champs obligatoires.",
                    "warning"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            matiere_id, enseignant_id = combinaison.split("|", 1)
            heure_debut, heure_fin = bloc_horaire.split("|", 1)

            if jour_semaine not in JOURS_SEMAINE:

                flash(
                    "Jour invalide.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            if (heure_debut, heure_fin) not in BLOCS_HORAIRES:

                flash(
                    "Créneau horaire invalide.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            cursor.execute(
                """
                SELECT 1
                FROM matiere_classes mc
                INNER JOIN enseignant_matieres em
                    ON em.matiere_id = mc.matiere_id
                WHERE mc.classe_id = %s
                AND mc.matiere_id = %s
                AND em.enseignant_id = %s
                """,
                (classe_id, matiere_id, enseignant_id)
            )

            if cursor.fetchone() is None:

                flash(
                    "Cette matière n'est pas enseignée par ce professeur "
                    "dans cette classe.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            cursor.execute(
                """
                SELECT 1
                FROM emplois_du_temps
                WHERE classe_id = %s
                AND jour_semaine = %s
                AND heure_debut < %s
                AND heure_fin > %s
                """,
                (classe_id, jour_semaine, heure_fin, heure_debut)
            )

            if cursor.fetchone():

                flash(
                    "Cette classe a déjà un cours sur ce créneau.",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            cursor.execute(
                """
                SELECT 1
                FROM emplois_du_temps
                WHERE enseignant_id = %s
                AND jour_semaine = %s
                AND heure_debut < %s
                AND heure_fin > %s
                """,
                (enseignant_id, jour_semaine, heure_fin, heure_debut)
            )

            if cursor.fetchone():

                flash(
                    "Ce professeur a déjà un cours sur ce créneau "
                    "(dans une autre classe).",
                    "danger"
                )

                return redirect(url_for("admin.ajouter_creneau", classe_id=classe_id))

            cursor.execute(
                """
                INSERT INTO emplois_du_temps
                (classe_id, matiere_id, enseignant_id, jour_semaine,
                 heure_debut, heure_fin, salle)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    classe_id,
                    matiere_id,
                    enseignant_id,
                    jour_semaine,
                    heure_debut,
                    heure_fin,
                    salle or None
                )
            )

            flash(
                "Créneau ajouté avec succès !",
                "success"
            )

            return redirect(url_for("admin.emploi_du_temps", classe_id=classe_id))

    return render_template(
        "ajouter_creneau.html",
        classe=classe,
        combinaisons=combinaisons,
        jours=JOURS_SEMAINE,
        blocs=BLOCS_HORAIRES
    )


@admin_bp.route(
    "/modifier_creneau/<int:id>",
    methods=["GET", "POST"],
    endpoint="modifier_creneau"
)
@role_required("ADMIN")
def modifier_creneau(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT *
            FROM emplois_du_temps
            WHERE id = %s
            """,
            (id,)
        )

        creneau = cursor.fetchone()

        if creneau is None:

            flash(
                "Créneau introuvable.",
                "danger"
            )

            return redirect(url_for("admin.classes"))

        classe_id = creneau["classe_id"]

        cursor.execute(
            """
            SELECT *
            FROM classes
            WHERE id = %s
            """,
            (classe_id,)
        )

        classe = cursor.fetchone()

        combinaisons = _combinaisons_matiere_enseignant(cursor, classe_id)

        if request.method == "POST":

            combinaison = request.form.get("combinaison", "")
            jour_semaine = request.form.get("jour_semaine")
            bloc_horaire = request.form.get("bloc_horaire", "")
            salle = request.form.get("salle", "").strip()

            if (
                "|" not in combinaison
                or not jour_semaine
                or "|" not in bloc_horaire
            ):

                flash(
                    "Veuillez remplir tous les champs obligatoires.",
                    "warning"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            matiere_id, enseignant_id = combinaison.split("|", 1)
            heure_debut, heure_fin = bloc_horaire.split("|", 1)

            if jour_semaine not in JOURS_SEMAINE:

                flash(
                    "Jour invalide.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            if (heure_debut, heure_fin) not in BLOCS_HORAIRES:

                flash(
                    "Créneau horaire invalide.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            cursor.execute(
                """
                SELECT 1
                FROM matiere_classes mc
                INNER JOIN enseignant_matieres em
                    ON em.matiere_id = mc.matiere_id
                WHERE mc.classe_id = %s
                AND mc.matiere_id = %s
                AND em.enseignant_id = %s
                """,
                (classe_id, matiere_id, enseignant_id)
            )

            if cursor.fetchone() is None:

                flash(
                    "Cette matière n'est pas enseignée par ce professeur "
                    "dans cette classe.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            cursor.execute(
                """
                SELECT 1
                FROM emplois_du_temps
                WHERE classe_id = %s
                AND jour_semaine = %s
                AND heure_debut < %s
                AND heure_fin > %s
                AND id != %s
                """,
                (classe_id, jour_semaine, heure_fin, heure_debut, id)
            )

            if cursor.fetchone():

                flash(
                    "Cette classe a déjà un cours sur ce créneau.",
                    "danger"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            cursor.execute(
                """
                SELECT 1
                FROM emplois_du_temps
                WHERE enseignant_id = %s
                AND jour_semaine = %s
                AND heure_debut < %s
                AND heure_fin > %s
                AND id != %s
                """,
                (enseignant_id, jour_semaine, heure_fin, heure_debut, id)
            )

            if cursor.fetchone():

                flash(
                    "Ce professeur a déjà un cours sur ce créneau "
                    "(dans une autre classe).",
                    "danger"
                )

                return redirect(url_for("admin.modifier_creneau", id=id))

            cursor.execute(
                """
                UPDATE emplois_du_temps
                SET matiere_id=%s,
                    enseignant_id=%s,
                    jour_semaine=%s,
                    heure_debut=%s,
                    heure_fin=%s,
                    salle=%s
                WHERE id=%s
                """,
                (
                    matiere_id,
                    enseignant_id,
                    jour_semaine,
                    heure_debut,
                    heure_fin,
                    salle or None,
                    id
                )
            )

            flash(
                "Créneau modifié avec succès !",
                "success"
            )

            return redirect(url_for("admin.emploi_du_temps", classe_id=classe_id))

    return render_template(
        "modifier_creneau.html",
        creneau=creneau,
        classe=classe,
        combinaisons=combinaisons,
        jours=JOURS_SEMAINE,
        blocs=BLOCS_HORAIRES
    )


@admin_bp.route(
    "/supprimer_creneau/<int:id>",
    methods=["POST"],
    endpoint="supprimer_creneau"
)
@role_required("ADMIN")
def supprimer_creneau(id):

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT classe_id
            FROM emplois_du_temps
            WHERE id = %s
            """,
            (id,)
        )

        creneau = cursor.fetchone()

        if creneau is None:

            flash(
                "Créneau introuvable.",
                "danger"
            )

            return redirect(url_for("admin.classes"))

        classe_id = creneau["classe_id"]

        cursor.execute(
            """
            DELETE FROM emplois_du_temps
            WHERE id = %s
            """,
            (id,)
        )

    flash(
        "Créneau supprimé avec succès !",
        "success"
    )

    return redirect(url_for("admin.emploi_du_temps", classe_id=classe_id))
