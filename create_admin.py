"""
Script interactif pour créer le tout premier compte ADMIN.

À lancer une seule fois, après avoir importé schema.sql, pour pouvoir
se connecter à /login et accéder au dashboard admin (qui permet ensuite
de créer les comptes enseignants et étudiants depuis l'interface).

Usage :
    python create_admin.py
"""

import getpass

from werkzeug.security import generate_password_hash

from config import db_cursor


def main():

    print("=== Création d'un compte administrateur ===")

    nom = input("Nom : ").strip()

    email = input("Email : ").strip().lower()

    if not nom or not email:

        print("Le nom et l'email sont obligatoires.")

        return

    mot_de_passe = getpass.getpass("Mot de passe : ")

    confirmation = getpass.getpass("Confirmer le mot de passe : ")

    if not mot_de_passe:

        print("Le mot de passe ne peut pas être vide.")

        return

    if mot_de_passe != confirmation:

        print("Les deux mots de passe ne correspondent pas.")

        return

    mot_de_passe_hash = generate_password_hash(mot_de_passe)

    with db_cursor(dictionary=True, buffered=True) as (connexion, cursor):

        cursor.execute(
            """
            SELECT id
            FROM utilisateurs
            WHERE email = %s
            """,
            (email,)
        )

        if cursor.fetchone():

            print(f"Un compte existe déjà avec l'email {email}.")

            return

        cursor.execute(
            """
            INSERT INTO utilisateurs
            (nom, email, mot_de_passe, role, etudiant_id, enseignant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (nom, email, mot_de_passe_hash, "ADMIN", None, None)
        )

    print(f"Compte admin '{email}' créé avec succès.")


if __name__ == "__main__":
    main()
