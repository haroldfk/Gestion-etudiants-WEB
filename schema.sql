-- Schéma de la base de données "gestion_etudiants"
-- Reconstitué à partir des requêtes SQL présentes dans blueprints/*.py
-- (aucun schema.sql n'existait dans le dépôt jusqu'ici).

CREATE DATABASE IF NOT EXISTS gestion_etudiants
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_etudiants;

-- ---------------------------------------------------------------------
-- Classes
-- ---------------------------------------------------------------------
CREATE TABLE classes (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    nom                   VARCHAR(100) NOT NULL,
    niveau                VARCHAR(50),
    annee_universitaire   VARCHAR(20)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Étudiants
-- classe_id est en RESTRICT : une classe qui a encore des étudiants ne
-- peut pas être supprimée (voir admin.supprimer_classe qui intercepte
-- l'erreur et affiche un message clair).
-- ---------------------------------------------------------------------
CREATE TABLE etudiants (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nom        VARCHAR(100) NOT NULL,
    prenom     VARCHAR(100) NOT NULL,
    age        INT NOT NULL,
    filiere    VARCHAR(100) NOT NULL,
    classe_id  INT NULL,

    FOREIGN KEY (classe_id)
        REFERENCES classes(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Enseignants
-- ---------------------------------------------------------------------
CREATE TABLE enseignants (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nom         VARCHAR(100) NOT NULL,
    prenom      VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    telephone   VARCHAR(30),
    specialite  VARCHAR(150)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Matières
-- ---------------------------------------------------------------------
CREATE TABLE matieres (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nom        VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Affectation matière <-> classes (plusieurs-à-plusieurs : une matière
-- peut être enseignée dans plusieurs classes).
-- classe_id est en RESTRICT, comme etudiants.classe_id : une classe
-- encore référencée par une matière ne peut pas être supprimée (voir
-- admin.supprimer_classe).
-- ---------------------------------------------------------------------
CREATE TABLE matiere_classes (
    matiere_id  INT NOT NULL,
    classe_id   INT NOT NULL,

    PRIMARY KEY (matiere_id, classe_id),

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE CASCADE,

    FOREIGN KEY (classe_id)
        REFERENCES classes(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Affectation enseignant <-> matières (plusieurs-à-plusieurs)
-- ---------------------------------------------------------------------
CREATE TABLE enseignant_matieres (
    enseignant_id  INT NOT NULL,
    matiere_id     INT NOT NULL,

    PRIMARY KEY (enseignant_id, matiere_id),

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE CASCADE,

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Cours (supports déposés par les enseignants)
-- Rattachés à une matière (pas directement à une classe) : un cours
-- est donc visible par toutes les classes auxquelles la matière est
-- associée via matiere_classes. enseignant_id doit être affecté à la
-- matière via enseignant_matieres (vérifié côté application dans
-- enseignant.cours_matiere).
-- ---------------------------------------------------------------------
CREATE TABLE cours (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    matiere_id     INT NOT NULL,
    enseignant_id  INT NOT NULL,
    titre          VARCHAR(200),
    fichier        VARCHAR(255),
    date_upload    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Emplois du temps
-- Un créneau = une matière donnée, dans une classe donnée, par un
-- enseignant donné, à un jour/horaire donné. La combinaison
-- (matiere_id, enseignant_id) doit correspondre à une affectation
-- existante dans enseignant_matieres, et matiere_id doit être associée
-- à classe_id via matiere_classes (vérifié côté application dans
-- admin.ajouter_creneau / admin.modifier_creneau, avec en plus une
-- détection des chevauchements horaires pour la classe et pour
-- l'enseignant).
-- ---------------------------------------------------------------------
CREATE TABLE emplois_du_temps (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    classe_id      INT NOT NULL,
    matiere_id     INT NOT NULL,
    enseignant_id  INT NOT NULL,
    jour_semaine   ENUM('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche') NOT NULL,
    heure_debut    TIME NOT NULL,
    heure_fin      TIME NOT NULL,
    salle          VARCHAR(50),

    FOREIGN KEY (classe_id)
        REFERENCES classes(id)
        ON DELETE CASCADE,

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE CASCADE,

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_edt_classe ON emplois_du_temps(classe_id);
CREATE INDEX idx_edt_enseignant ON emplois_du_temps(enseignant_id);

-- ---------------------------------------------------------------------
-- Évaluations (devoirs, examens...) rattachées à une matière et
-- créées par un enseignant qui l'enseigne.
--
-- classe_id / emploi_du_temps_id : au lieu de saisir une date libre,
-- l'enseignant choisit un créneau existant de SON emploi du temps pour
-- cette matière (admin.emploi_du_temps affiche alors "(Évaluation)" sur
-- ce créneau). L'évaluation devient donc propre à une classe précise
-- (celle du créneau choisi), et non plus visible par toutes les classes
-- de la matière. emploi_du_temps_id est en SET NULL : si le créneau est
-- supprimé plus tard, l'évaluation (et les notes qui y sont liées)
-- reste, elle perd juste son affichage sur l'emploi du temps.
-- classe_id est dupliqué (plutôt que dérivé du créneau à chaque requête)
-- pour que l'évaluation reste rattachée à sa classe même si le créneau
-- est supprimé. date_evaluation est conservée pour les évaluations plus
-- anciennes créées avant ce changement (nullable, plus utilisée par les
-- nouveaux formulaires).
--
-- Une note peut optionnellement être liée à une évaluation via
-- notes.evaluation_id (RESTRICT : une évaluation qui a déjà des notes
-- ne peut pas être supprimée, voir enseignant.supprimer_evaluation qui
-- intercepte l'erreur).
-- ---------------------------------------------------------------------
CREATE TABLE evaluations (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    matiere_id          INT NOT NULL,
    enseignant_id       INT NOT NULL,
    classe_id           INT NULL,
    emploi_du_temps_id  INT NULL,
    nom                 VARCHAR(100),
    coefficient         INT DEFAULT 1,
    date_evaluation     DATE,

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (classe_id)
        REFERENCES classes(id)
        ON DELETE SET NULL,

    FOREIGN KEY (emploi_du_temps_id)
        REFERENCES emplois_du_temps(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Comptes de connexion (admin / enseignant / étudiant)
-- Tous les comptes sont créés par un admin (creer_compte_etudiant,
-- creer_compte_enseignant) : le rôle est donc toujours fourni
-- explicitement par le code applicatif, il n'y a pas d'auto-inscription
-- publique.
-- ---------------------------------------------------------------------
CREATE TABLE utilisateurs (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    nom            VARCHAR(150) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    mot_de_passe   VARCHAR(255) NOT NULL,
    role           ENUM('ADMIN', 'ENSEIGNANT', 'ETUDIANT') NOT NULL,
    etudiant_id    INT NULL,
    enseignant_id  INT NULL,

    FOREIGN KEY (etudiant_id)
        REFERENCES etudiants(id)
        ON DELETE SET NULL,

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Notifications (internes à l'application, pas d'envoi d'email).
-- Créées automatiquement par le code applicatif (utils.notifier_etudiant
-- / notifier_classe / notifier_matiere) lors d'événements : nouvelle
-- note, absence déclarée, justificatif traité, nouveau cours déposé,
-- nouvelle évaluation programmée.
-- ---------------------------------------------------------------------
CREATE TABLE notifications (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    utilisateur_id     INT NOT NULL,
    titre              VARCHAR(200),
    message            TEXT,
    lu                 TINYINT(1) NOT NULL DEFAULT 0,
    date_notification  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (utilisateur_id)
        REFERENCES utilisateurs(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Notes
-- NB : "matiere" est stocké ici comme texte (nom de la matière au
-- moment de la saisie), pas comme clé étrangère vers matieres.id.
-- C'est le comportement actuel du code (admin.ajouter_note,
-- enseignant.saisir_notes_enseignant).
-- evaluation_id est optionnel : une note "libre" (sans évaluation
-- précise) reste possible, comme avant. RESTRICT car une évaluation
-- ne doit pas pouvoir être supprimée si des notes y sont déjà liées.
-- ---------------------------------------------------------------------
CREATE TABLE notes (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    etudiant_id    INT NOT NULL,
    matiere        VARCHAR(150) NOT NULL,
    note           DECIMAL(4,2) NOT NULL,
    evaluation_id  INT NULL,

    FOREIGN KEY (etudiant_id)
        REFERENCES etudiants(id)
        ON DELETE CASCADE,

    FOREIGN KEY (evaluation_id)
        REFERENCES evaluations(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Absences
-- statut par défaut 'En attente' : ajouter_absence() insère la ligne
-- sans préciser de statut et le message flash annonce explicitement
-- "En attente" comme valeur initiale.
--
-- emploi_du_temps_id : l'absence est déclarée pour un créneau précis
-- de l'emploi du temps de la classe (l'admin peut choisir le créneau
-- de n'importe quel enseignant, un enseignant ne voit que les siens).
-- matiere_id / enseignant_id sont dupliqués depuis le créneau choisi
-- (SET NULL sur emploi_du_temps_id pour ne pas perdre l'historique si
-- le créneau est supprimé plus tard). date_absence reste le jour
-- calendaire réel de l'absence (le créneau ne donne qu'un jour de la
-- semaine récurrent, pas une date précise).
-- ---------------------------------------------------------------------
CREATE TABLE absences (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    etudiant_id         INT NOT NULL,
    date_absence        DATE NOT NULL,
    motif               TEXT NOT NULL,
    justificatif        VARCHAR(255) NULL,
    statut              ENUM('En attente', 'Justifiée', 'Refusée') NOT NULL DEFAULT 'En attente',
    matiere_id          INT NULL,
    enseignant_id       INT NULL,
    emploi_du_temps_id  INT NULL,

    FOREIGN KEY (etudiant_id)
        REFERENCES etudiants(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (matiere_id)
        REFERENCES matieres(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (enseignant_id)
        REFERENCES enseignants(id)
        ON DELETE RESTRICT,

    FOREIGN KEY (emploi_du_temps_id)
        REFERENCES emplois_du_temps(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_notes_etudiant ON notes(etudiant_id);
CREATE INDEX idx_absences_etudiant ON absences(etudiant_id);

-- ---------------------------------------------------------------------
-- Compte admin initial (à adapter puis exécuter séparément : le hash
-- ci-dessous n'est qu'un exemple, générez le vôtre avec
-- werkzeug.security.generate_password_hash).
-- ---------------------------------------------------------------------
-- INSERT INTO utilisateurs (nom, email, mot_de_passe, role)
-- VALUES ('Admin', 'admin@example.com', '<hash_pbkdf2_a_generer>', 'ADMIN');
