# models/api_key.py
"""Modèle APIKey pour l'authentification API"""
import secrets
from database.db import db
from datetime import datetime

class APIKey(db.Model):
    """Modèle pour les clés API"""
    
    __tablename__ = 'api_keys'
    
    # Clé primaire
    id = db.Column(db.Integer, primary_key=True)
    
    # Utilisateur propriétaire
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Clé API
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
    # Nom de la clé (pour identification)
    name = db.Column(db.String(200), nullable=False)
    
    # Statut
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Statistiques d'usage
    total_requests = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<APIKey {self.name}>'
    
    @staticmethod
    def generate_key():
        """Génère une clé API unique"""
        return f"sk_{secrets.token_urlsafe(48)}"
    
    def to_dict(self):
        """Convertit la clé API en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'key': self.key,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'total_requests': self.total_requests
        }