# models/project.py
"""Modèle Project pour les projets de clustering"""
from database.db import db
from datetime import datetime

class Project(db.Model):
    """Modèle projet de clustering"""
    
    __tablename__ = 'projects'
    
    # Clé primaire
    id = db.Column(db.Integer, primary_key=True)
    
    # Propriétaire
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Informations de base
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    n_clusters = db.Column(db.Integer, default=20, nullable=False)
    
    # Statut du traitement
    status = db.Column(db.String(50), default='created', nullable=False)
    # Valeurs possibles: created, uploading, processing, completed, failed
    
    # Métadonnées images
    n_images = db.Column(db.Integer, default=0)
    total_size_mb = db.Column(db.Float, default=0.0)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Résultats ML
    ml_model_id = db.Column(db.String(100), nullable=True)
    mean_confidence = db.Column(db.Float, nullable=True)
    n_uncertain = db.Column(db.Integer, default=0)
    
    # Chemins de stockage
    embeddings_path = db.Column(db.String(500), nullable=True)
    images_folder = db.Column(db.String(500), nullable=True)
    
    # Itération (pour réentraînement)
    training_iteration = db.Column(db.Integer, default=1)
    
    # Relations
    images = db.relationship('Image', backref='project', lazy=True, cascade='all, delete-orphan')
    clusters = db.relationship('Cluster', backref='project', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    def to_dict(self):
        """Convertit le projet en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'n_clusters': self.n_clusters,
            'status': self.status,
            'n_images': self.n_images,
            'total_size_mb': self.total_size_mb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'mean_confidence': self.mean_confidence,
            'n_uncertain': self.n_uncertain,
            'training_iteration': self.training_iteration
        }

class Image(db.Model):
    """Modèle image dans un projet"""
    
    __tablename__ = 'images'
    
    # Clé primaire
    id = db.Column(db.Integer, primary_key=True)
    
    # Projet parent
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    # Fichier
    filename = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # en bytes
    
    # Résultats clustering
    cluster_id = db.Column(db.Integer, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    is_uncertain = db.Column(db.Boolean, default=False)
    
    # Validation
    validation_status = db.Column(db.String(50), default='pending')
    # Valeurs: pending, approved, rejected, moved
    validated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    validated_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(200), nullable=True)
    
    # Historique
    original_cluster_id = db.Column(db.Integer, nullable=True)
    moved_from_cluster = db.Column(db.Integer, nullable=True)
    initial_confidence = db.Column(db.Float, nullable=True)
    
    # Dates
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Image {self.filename}>'
    
    def to_dict(self):
        """Convertit l'image en dictionnaire"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'cluster_id': self.cluster_id,
            'confidence_score': self.confidence_score,
            'is_uncertain': self.is_uncertain,
            'validation_status': self.validation_status,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class Cluster(db.Model):
    """Modèle pour nommer les clusters"""
    
    __tablename__ = 'clusters'
    
    # Clé primaire
    id = db.Column(db.Integer, primary_key=True)
    
    # Projet parent
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    # ID du cluster (0, 1, 2, ...)
    cluster_id = db.Column(db.Integer, nullable=False)
    
    # Nom et description
    cluster_name = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Contrainte d'unicité
    __table_args__ = (
        db.UniqueConstraint('project_id', 'cluster_id', name='uix_project_cluster'),
    )
    
    def __repr__(self):
        return f'<Cluster {self.cluster_name or self.cluster_id}>'
    
    def to_dict(self):
        """Convertit le cluster en dictionnaire"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'cluster_id': self.cluster_id,
            'cluster_name': self.cluster_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

