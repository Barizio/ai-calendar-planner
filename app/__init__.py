from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    app.secret_key = os.getenv('SECRET_KEY', 'dev')

    from .routes import main
    app.register_blueprint(main)

    return app
