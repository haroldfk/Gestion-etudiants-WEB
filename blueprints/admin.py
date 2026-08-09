import csv
import io

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
from utils import calculer_mention

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

    return render_template(
        "dashboard.html",
        nom=session.get("nom", "Utilisateur"),
        nb_etudiants=nb_etudiants,
        nb_utilisateurs=nb_utilisateurs,
        top_etudiants=top_etudiants,
        stats_filieres=stats_filieres
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

    if request.method == "POST":

        nom = request.form["nom"]
        prenom = request.form["prenom"]
        age = request.form["age"]
        filiere = request.form["filiere"]

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                INSERT INTO etudiants (nom, prenom, age, filiere)
                VALUES (%s, %s, %s, %s)
                """,
                (nom, prenom, age, filiere)
            )

        flash(
            "Étudiant ajouté avec succès !",
            "success"
        )

        return redirect(
            url_for("admin.liste_etudiants")
        )

    return render_template(
        "ajouter_etudiant.html"
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
                SELECT * FROM etudiants
                WHERE nom LIKE %s
                OR prenom LIKE %s
                OR CONCAT(nom, ' ', prenom) LIKE %s
                OR CONCAT(prenom, ' ', nom) LIKE %s
                """,
                (motif, motif, motif, motif)
            )

        else:

            cursor.execute("""
            SELECT * FROM etudiants
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

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                UPDATE etudiants
                SET nom=%s,
                    prenom=%s,
                    age=%s,
                    filiere=%s
                WHERE id=%s
                """,
                (nom, prenom, age, filiere, id)
            )

        return redirect(url_for("admin.liste_etudiants"))

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute(
            "SELECT * FROM etudiants WHERE id=%s",
            (id,)
        )

        etudiant = cursor.fetchone()

    return render_template(
        "modifier_etudiant.html",
        etudiant=etudiant
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

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT DISTINCT filiere
            FROM etudiants
            ORDER BY filiere
        """)

        filieres = cursor.fetchall()

        if filiere:

            cursor.execute(
                """
                SELECT
                    e.id,
                    e.nom,
                    e.prenom,
                    e.filiere,
                    AVG(n.note) AS moyenne
                FROM etudiants e
                JOIN notes n
                    ON e.id = n.etudiant_id
                WHERE e.filiere = %s
                GROUP BY
                    e.id,
                    e.nom,
                    e.prenom,
                    e.filiere
                ORDER BY moyenne DESC
                """,
                (filiere,)
            )

        else:

            cursor.execute("""
                SELECT
                    e.id,
                    e.nom,
                    e.prenom,
                    e.filiere,
                    AVG(n.note) AS moyenne
                FROM etudiants e
                JOIN notes n
                    ON e.id = n.etudiant_id
                GROUP BY
                    e.id,
                    e.nom,
                    e.prenom,
                    e.filiere
                ORDER BY moyenne DESC
            """)

        classement = cursor.fetchall()

    return render_template(
        "classement.html",
        classement=classement,
        filieres=filieres,
        filiere_selectionnee=filiere
    )


@admin_bp.route("/matieres", endpoint="matieres")
@role_required("ADMIN")
def matieres():

    with db_cursor(dictionary=True) as (connexion, cursor):

        cursor.execute("""
            SELECT *
            FROM matieres
            ORDER BY nom
        """)

        matieres = cursor.fetchall()

    return render_template(
        "matieres.html",
        matieres=matieres
    )


@admin_bp.route("/ajouter_matiere", methods=["GET", "POST"], endpoint="ajouter_matiere")
@role_required("ADMIN")
def ajouter_matiere():

    if request.method == "POST":

        nom = request.form["nom"]

        with db_cursor() as (connexion, cursor):

            cursor.execute("""
                INSERT INTO matieres(nom)
                VALUES(%s)
            """, (nom,))

        flash(
            "Matière ajoutée avec succès",
            "success"
        )

        return redirect(url_for("admin.matieres"))

    return render_template(
        "ajouter_matiere.html"
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

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                UPDATE matieres
                SET nom=%s
                WHERE id=%s
                """,
                (nom, id)
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

    return render_template(
        "modifier_matiere.html",
        matiere=matiere
    )


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
            SELECT *
            FROM absences
            WHERE etudiant_id=%s
            ORDER BY date_absence DESC
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

    if request.method == "POST":

        date_absence = request.form["date_absence"]
        motif = request.form["motif"]

        with db_cursor() as (connexion, cursor):

            cursor.execute(
                """
                INSERT INTO absences
                (
                    etudiant_id,
                    date_absence,
                    motif
                )

                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (id, date_absence, motif)
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
        etudiant_id=id
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
