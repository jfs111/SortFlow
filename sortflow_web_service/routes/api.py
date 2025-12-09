# routes/api.py
"""Routes API publiques"""
from flask import Blueprint, request, jsonify, current_app
from database.db import db
from models.project import Project, Image, Cluster
from models.api_key import APIKey
from datetime import datetime
import os
import base64
import tempfile
import uuid

# Blueprint API sans préfixe
api_bp = Blueprint('api', __name__)

@api_bp.route('/api/v1/projects/<int:project_id>/predict', methods=['POST'])
def predict_image(project_id):
    """API : Prédit le cluster d'une image (avec API key)"""
    from utils.ml_client import MLServiceClient
    
    # Vérifier l'API key
    api_key = request.headers.get('X-API-Key')
    
    if not api_key:
        return jsonify({'error': 'API key manquante (header X-API-Key)'}), 401
    
    key_obj = APIKey.query.filter_by(key=api_key, is_active=True).first()
    
    if not key_obj:
        return jsonify({'error': 'API key invalide ou inactive'}), 401
    
    # Vérifier l'expiration
    if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
        return jsonify({'error': 'API key expirée'}), 401
    
    # Mettre à jour les stats
    key_obj.last_used_at = datetime.utcnow()
    key_obj.total_requests += 1
    db.session.commit()
    
    # Récupérer le projet
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != key_obj.user_id:
        return jsonify({'error': 'Accès non autorisé à ce projet'}), 403
    
    if project.status not in ['completed', 'finalized']:
        return jsonify({'error': 'Le projet doit être traité avant la prédiction'}), 400
    
    try:
        # Récupérer l'image (base64 ou file)
        data = request.get_json() if request.is_json else {}
        
        temp_dir = tempfile.gettempdir()
        temp_filename = f"{uuid.uuid4().hex}.jpg"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        if 'image_base64' in data:
            # Image en base64
            image_data = base64.b64decode(data['image_base64'])
            with open(temp_path, 'wb') as f:
                f.write(image_data)
        elif 'file' in request.files:
            # Image uploadée
            file = request.files['file']
            file.save(temp_path)
        else:
            return jsonify({'error': 'Aucune image fournie (image_base64 dans JSON ou file en multipart)'}), 400
        
        # Vérifier que les fichiers du modèle existent
        embeddings_file = os.path.join(project.images_folder, 'embeddings.npy')
        centroids_file = os.path.join(project.images_folder, 'centroids.npy')
        
        if not os.path.exists(centroids_file):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'error': 'Modèle non disponible pour ce projet (centroïdes manquants)'}), 400
        
        # Prédire
        ml_client = MLServiceClient()
        prediction = ml_client.predict(temp_path, embeddings_file, centroids_file)
        
        # Récupérer le nom du cluster
        cluster = Cluster.query.filter_by(
            project_id=project_id,
            cluster_id=prediction['cluster_id']
        ).first()
        
        cluster_name = cluster.cluster_name if cluster else f"Cluster {prediction['cluster_id']}"
        
        # Nettoyer
        os.remove(temp_path)
        
        current_app.logger.info(f"API Prediction for project {project_id}: cluster {prediction['cluster_id']}, confidence {prediction['confidence_score']:.2f}")
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'project_name': project.name,
            'cluster_id': prediction['cluster_id'],
            'cluster_name': cluster_name,
            'confidence_score': prediction['confidence_score'],
            'distance': prediction['distance'],
            'is_uncertain': prediction['confidence_score'] < 0.3
        })
    
    except Exception as e:
        # Nettoyer en cas d'erreur
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        current_app.logger.error(f"Error in API prediction: {e}")
        return jsonify({'error': str(e)}), 500