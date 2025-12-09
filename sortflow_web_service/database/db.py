# database/db.py
"""Configuration de la base de données SQLite"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Instance SQLAlchemy
db = SQLAlchemy()

def init_db(app):
    """Initialise la base de données avec l'app Flask"""
    db.init_app(app)
    
    with app.app_context():
        # Créer toutes les tables
        db.create_all()
        print("✅ Base de données initialisée")

def reset_db(app):
    """Supprime et recrée toutes les tables (DEV uniquement)"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("✅ Base de données réinitialisée")