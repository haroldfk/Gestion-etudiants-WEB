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
from werkzeug.security import check_password_hash

from config import db_cursor

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", endpoint="accueil")
def accueil():
    return render_template("index.html")


@auth_bp.route("/logout", endpoint="logout")
def logout():

    session.clear()

    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        mot_de_passe = request.form.get(
            "mot_de_passe",
            ""
        )

        if not email or not mot_de_passe:

            flash(
                "Veuillez remplir tous les champs.",
                "warning"
            )

            return render_template(
                "login.html",
                email=email
            )

        try:

            with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

                cursor.execute(
                    """
                    SELECT
                        id,
                        nom,
                        email,
                        mot_de_passe,
                        role,
                        etudiant_id,
                        enseignant_id
                    FROM utilisateurs
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,)
                )

                utilisateur = cursor.fetchone()

                if utilisateur is None:

                    flash(
                        "Email ou mot de passe incorrect.",
                        "danger"
                    )

                    return render_template(
                        "login.html",
                        email=email
                    )

                mot_de_passe_valide = check_password_hash(
                    utilisateur["mot_de_passe"],
                    mot_de_passe
                )

                if not mot_de_passe_valide:

                    flash(
                        "Email ou mot de passe incorrect.",
                        "danger"
                    )

                    return render_template(
                        "login.html",
                        email=email
                    )

                role = utilisateur["role"]

                session.clear()

                session["user_id"] = utilisateur["id"]
                session["nom"] = utilisateur["nom"]
                session["role"] = role

                if role == "ADMIN":

                    session["etudiant_id"] = None
                    session["enseignant_id"] = None

                    flash(
                        "Bienvenue dans l'espace administrateur !",
                        "success"
                    )

                    return redirect(
                        url_for("admin.dashboard")
                    )

                elif role == "ETUDIANT":

                    etudiant_id = utilisateur[
                        "etudiant_id"
                    ]

                    if etudiant_id is None:

                        session.clear()

                        flash(
                            "Aucun profil étudiant associé à ce compte.",
                            "danger"
                        )

                        return redirect(
                            url_for("auth.login")
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

                        session.clear()

                        flash(
                            "Profil étudiant introuvable.",
                            "danger"
                        )

                        return redirect(
                            url_for("auth.login")
                        )

                    session["etudiant_id"] = etudiant_id
                    session["enseignant_id"] = None

                    flash(
                        "Bienvenue dans votre espace étudiant !",
                        "success"
                    )

                    return redirect(
                        url_for("etudiant.espace_etudiant")
                    )

                elif role == "ENSEIGNANT":

                    enseignant_id = utilisateur[
                        "enseignant_id"
                    ]

                    if enseignant_id is None:

                        session.clear()

                        flash(
                            "Aucun profil enseignant associé à ce compte.",
                            "danger"
                        )

                        return redirect(
                            url_for("auth.login")
                        )

                    cursor.execute(
                        """
                        SELECT
                            id,
                            nom,
                            prenom
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

                        return redirect(
                            url_for("auth.login")
                        )

                    session["enseignant_id"] = enseignant_id
                    session["etudiant_id"] = None

                    flash(
                        "Bienvenue dans votre espace enseignant !",
                        "success"
                    )

                    return redirect(
                        url_for("enseignant.espace_enseignant")
                    )

                else:

                    session.clear()

                    flash(
                        "Rôle utilisateur non reconnu.",
                        "danger"
                    )

                    return redirect(
                        url_for("auth.login")
                    )

        except Exception as erreur:

            current_app.logger.error(
                "Erreur login : %r",
                erreur
            )

            session.clear()

            flash(
                "Erreur technique pendant la connexion.",
                "danger"
            )

            return render_template(
                "login.html",
                email=email
            )

    return render_template(
        "login.html"
    )
