import os

from dotenv import load_dotenv
from flask import Flask
from flask_wtf import CSRFProtect

from blueprints.admin import admin_bp
from blueprints.auth import auth_bp
from blueprints.enseignant import enseignant_bp
from blueprints.etudiant import etudiant_bp

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET_KEY"]

csrf = CSRFProtect(app)

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "uploads",
    "justificatifs"
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(etudiant_bp)
app.register_blueprint(enseignant_bp)


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
