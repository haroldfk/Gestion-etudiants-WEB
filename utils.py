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
