# models/user.py
"""Modèle User pour l'authentification"""
from database.db import db
from datetime import datetime
from flask_login import UserMixin

class User(db.Model, UserMixin):
    """Modèle utilisateur"""
    
    __tablename__ = 'users'
    
    # Colonnes
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(80), nullable=True)
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relations (à ajouter plus tard)
    # projects = db.relationship('Project', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        """Convertit l'utilisateur en dictionnaire (sans password)"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'is_admin': self.is_admin
        }

#import secrets
#from database.db import db
#from datetime import datetime

#class APIKey(db.Model):
#    """Modèle pour les clés API"""
    
#    __tablename__ = 'api_keys'
    
#    # Clé primaire
#    id = db.Column(db.Integer, primary_key=True)
    
#    # Utilisateur propriétaire
#    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
#    # Clé API
#    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
#    # Nom de la clé (pour identification)
#    name = db.Column(db.String(200), nullable=False)
    
#    # Statut
#    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
#    # Dates
#    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
#    last_used_at = db.Column(db.DateTime, nullable=True)
#    expires_at = db.Column(db.DateTime, nullable=True)
    
#    # Statistiques d'usage
#    total_requests = db.Column(db.Integer, default=0)
    
#    def __repr__(self):
#        return f'<APIKey {self.name}>'
    
#    @staticmethod
#    def generate_key():
#        """Génère une clé API unique"""
#        return f"sk_{secrets.token_urlsafe(48)}"
    
#    def to_dict(self):
#        """Convertit la clé API en dictionnaire"""
#        return {
#            'id': self.id,
#            'name': self.name,
#            'key': self.key,
#            'is_active': self.is_active,
#            'created_at': self.created_at.isoformat() if self.created_at else None,
#            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
#            'total_requests': self.total_requests
#        }