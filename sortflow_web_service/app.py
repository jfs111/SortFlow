# app.py
"""Application Flask principale - SortFlow Web Service"""
from flask import Flask, jsonify
from flask_login import LoginManager
from dotenv import load_dotenv
import os

# Charger variables d'environnement
load_dotenv()

# Import database
from database.db import db, init_db

# Import routes
from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.api import api_bp   

def create_app():
    """Factory pour créer l'application Flask"""
    
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret_key_change_me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///sortflow.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 2024  # 400 MB
    
    # Initialiser la base de données
    db.init_app(app)
    
    # Initialiser Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.web_login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'error'
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))
    
    with app.app_context():
        # Importer tous les modèles pour que SQLAlchemy les connaisse
        from models.user import User
        from models.project import Project, Image, Cluster
        from models.api_key import APIKey
        
        # Créer les tables
        db.create_all()
        print("✅ Base de données initialisée")
    
    # Enregistrer les blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)
    
    # Route racine
    @app.route('/')
    def index():
        """Page d'accueil"""
        from flask import render_template
        return render_template('index.html')
    
    # Servir les fichiers uploadés
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Sert les fichiers uploadés"""
        from flask import send_from_directory
        return send_from_directory('uploads', filename)
    
    # Route health check
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        })
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Configuration serveur
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    print("="*60)
    print("🚀 SortFlow Web Service")
    print("="*60)
    print(f"Server: http://{host}:{port}")
    print(f"Debug: {debug}")
    print(f"Database: {os.getenv('DATABASE_URL', 'sqlite:///sortflow.db')}")
    print("="*60)
    
    app.run(host=host, port=port, debug=debug)