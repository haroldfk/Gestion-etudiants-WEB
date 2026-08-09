from functools import wraps

from flask import flash, redirect, session, url_for


def role_required(*roles):
    """Exige un utilisateur connecté possédant l'un des rôles donnés."""

    def decorateur(vue):

        @wraps(vue)
        def vue_protegee(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("auth.login"))

            if session.get("role") not in roles:

                flash(
                    "Accès non autorisé.",
                    "danger"
                )

                return redirect(url_for("auth.login"))

            return vue(*args, **kwargs)

        return vue_protegee

    return decorateur
