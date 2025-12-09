# routes/projects.py
"""Routes pour la gestion des projets"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database.db import db
from models.project import Project, Image
from datetime import datetime
import os
from pathlib import Path
import uuid
import shutil

# Blueprint
projects_bp = Blueprint('projects', __name__, url_prefix='/projects')

# Configuration upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB par fichier

def allowed_file(filename):
    """Vérifie si l'extension est autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder(project_id):
    """Retourne le dossier d'upload pour un projet"""
    base_folder = Path('uploads') / 'projects' / str(project_id)
    base_folder.mkdir(parents=True, exist_ok=True)
    return base_folder

# ============================================================================
# LISTE DES PROJETS
# ============================================================================

@projects_bp.route('/')
@login_required
def list_projects():
    """Liste tous les projets de l'utilisateur"""
    projects = Project.query.filter_by(user_id=current_user.id).order_by(
        Project.created_at.desc()
    ).all()
    
    return render_template('projects/list.html', projects=projects)

# ============================================================================
# NOUVEAU PROJET - GET (Formulaire)
# ============================================================================

@projects_bp.route('/new', methods=['GET'])
@login_required
def new_project():
    """Affiche le formulaire de création de projet"""
    return render_template('projects/new.html')

@projects_bp.route('/create-empty', methods=['POST'])
@login_required
def create_empty_project():
    """Crée un projet vide (sans images)"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        n_clusters = data.get('n_clusters', 20)
        
        if not name:
            return jsonify({'error': 'Le nom du projet est requis'}), 400
        
        if n_clusters < 2 or n_clusters > 50:
            return jsonify({'error': 'Le nombre de clusters doit être entre 2 et 50'}), 400
        
        # Créer le projet
        project = Project(
            user_id=current_user.id,
            name=name,
            description=description if description else None,
            n_clusters=n_clusters,
            status='uploading',
            created_at=datetime.utcnow()
        )
        
        db.session.add(project)
        db.session.commit()
        
        # Créer le dossier d'upload
        upload_folder = get_upload_folder(project.id)
        project.images_folder = str(upload_folder)
        db.session.commit()
        
        return jsonify({'project_id': project.id})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/upload-batch', methods=['POST'])
@login_required
def upload_batch(project_id):
    """Upload un batch d'images"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        files = request.files.getlist('images')
        upload_folder = Path(project.images_folder)
        
        uploaded_count = 0
        total_size = 0
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{extension}"
                file_path = upload_folder / unique_filename
                
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size <= MAX_FILE_SIZE:
                    file.save(str(file_path))
                    
                    image = Image(
                        project_id=project.id,
                        filename=unique_filename,
                        original_filename=original_filename,
                        file_path=str(file_path),
                        file_size=file_size,
                        uploaded_at=datetime.utcnow()
                    )
                    
                    db.session.add(image)
                    uploaded_count += 1
                    total_size += file_size
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'uploaded': uploaded_count
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/finalize-upload', methods=['POST'])
@login_required
def finalize_upload(project_id):
    """Finalise l'upload et met à jour les stats du projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        # Compter les images et la taille totale
        images = Image.query.filter_by(project_id=project_id).all()
        
        project.n_images = len(images)
        project.total_size_mb = sum(img.file_size for img in images) / (1024 * 1024)
        project.status = 'created'
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# NOUVEAU PROJET - POST (Création)
# ============================================================================

@projects_bp.route('/new', methods=['POST'])
@login_required
def create_project():
    """Crée un nouveau projet et upload les images"""
    try:
        # 1. Valider les données du formulaire
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        n_clusters = request.form.get('n_clusters', 20, type=int)
        
        if not name:
            flash('Le nom du projet est requis', 'error')
            return redirect(url_for('projects.new_project'))
        
        if n_clusters < 2 or n_clusters > 50:
            flash('Le nombre de clusters doit être entre 2 et 50', 'error')
            return redirect(url_for('projects.new_project'))
        
        # 2. Vérifier qu'il y a des fichiers
        if 'images' not in request.files:
            flash('Aucune image sélectionnée', 'error')
            return redirect(url_for('projects.new_project'))
        
        files = request.files.getlist('images')
        
        if len(files) == 0 or (len(files) == 1 and files[0].filename == ''):
            flash('Aucune image sélectionnée', 'error')
            return redirect(url_for('projects.new_project'))
        
        # 3. Créer le projet en DB
        project = Project(
            user_id=current_user.id,
            name=name,
            description=description if description else None,
            n_clusters=n_clusters,
            status='uploading',
            created_at=datetime.utcnow()
        )
        
        db.session.add(project)
        db.session.commit()
        
        # 4. Créer le dossier d'upload
        upload_folder = get_upload_folder(project.id)
        project.images_folder = str(upload_folder)
        
        # 5. Sauvegarder les images
        uploaded_count = 0
        total_size = 0
        errors = []
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                # Générer un nom unique
                original_filename = secure_filename(file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{extension}"
                
                # Chemin complet
                file_path = upload_folder / unique_filename
                
                # Vérifier la taille
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    errors.append(f"{original_filename}: fichier trop volumineux (max 10MB)")
                    continue
                
                # Sauvegarder le fichier
                file.save(str(file_path))
                
                # Créer l'entrée en DB
                image = Image(
                    project_id=project.id,
                    filename=unique_filename,
                    original_filename=original_filename,
                    file_path=str(file_path),
                    file_size=file_size,
                    uploaded_at=datetime.utcnow()
                )
                
                db.session.add(image)
                uploaded_count += 1
                total_size += file_size
            else:
                if file and file.filename:
                    errors.append(f"{file.filename}: format non supporté")
        
        # 6. Mettre à jour les statistiques du projet
        project.n_images = uploaded_count
        project.total_size_mb = total_size / (1024 * 1024)
        project.status = 'created'  # Prêt pour traitement
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # 7. Messages de feedback
        if uploaded_count > 0:
            flash(f'Projet créé avec succès ! {uploaded_count} images uploadées.', 'success')
            
            if errors:
                flash(f'{len(errors)} images ignorées (format ou taille)', 'warning')
            
            return redirect(url_for('projects.project_detail', project_id=project.id))
        else:
            flash('Aucune image valide uploadée', 'error')
            db.session.delete(project)
            db.session.commit()
            return redirect(url_for('projects.new_project'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la création du projet: {str(e)}', 'error')
        return redirect(url_for('projects.new_project'))

# ============================================================================
# DÉTAIL DU PROJET
# ============================================================================

@projects_bp.route('/<int:project_id>')
@login_required
def project_detail(project_id):
    """Affiche les détails d'un projet"""
    project = Project.query.get_or_404(project_id)
    
    # Vérifier que c'est bien son projet
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Récupérer les images
    images = Image.query.filter_by(project_id=project_id).all()
    
    return render_template('projects/detail.html', project=project, images=images)


# ============================================================================
# TRAITER LE PROJET (ML)
# ============================================================================
@projects_bp.route('/<int:project_id>/process', methods=['POST'])
@login_required
def process_project(project_id):
    """Lance le traitement ML du projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    if project.n_images == 0:
        return jsonify({'error': 'Le projet ne contient aucune image'}), 400
    
    if project.status == 'processing':
        return jsonify({'error': 'Le projet est déjà en cours de traitement'}), 400
    
    try:
        from utils.ml_client import MLServiceClient
        import numpy as np
        import os
        
        ml_client = MLServiceClient()
        if not ml_client.health_check():
            return jsonify({
                'error': 'Le service ML n\'est pas accessible. Assurez-vous qu\'il est démarré.'
            }), 503
        
        project.status = 'processing'
        db.session.commit()
        
        images = Image.query.filter_by(project_id=project_id).all()
        image_paths = [img.file_path for img in images]
        
        # Définir les chemins des fichiers
        embeddings_file = os.path.join(project.images_folder, 'embeddings.npy')
        centroids_file = os.path.join(project.images_folder, 'centroids.npy')
        
        # Vérifier si les embeddings existent déjà
        if os.path.exists(embeddings_file):
            # RÉUTILISER les embeddings existants (RAPIDE - 10-20 secondes)
            current_app.logger.info(f"⚡ Réutilisation des embeddings depuis {embeddings_file}")
            embeddings = np.load(embeddings_file).tolist()
            
            # Recalculer uniquement le clustering
            clustering_result = ml_client.fit_kmeans(embeddings, project.n_clusters)
            labels = clustering_result['labels']
            model_id = clustering_result['model_id']
            
            # Sauvegarder les centroïdes pour la prédiction
            if 'centroids' in clustering_result:
                centroids_array = np.array(clustering_result['centroids'])
                np.save(centroids_file, centroids_array)
                current_app.logger.info(f"💾 Centroïdes sauvegardés dans {centroids_file}")
            
            # Calculer confiance
            confidence_result = ml_client.calculate_confidence(embeddings, model_id, threshold=0.3)
            
            result = {
                'embeddings': embeddings,
                'labels': labels,
                'confidence_scores': confidence_result['scores'],
                'model_id': model_id,
                'silhouette_score': clustering_result.get('silhouette_score'),
                'mean_confidence': confidence_result['mean_confidence'],
                'median_confidence': confidence_result['median_confidence'],
                'n_uncertain': confidence_result['n_uncertain'],
                'uncertain_indices': confidence_result['uncertain_indices'],
                'processing_time_seconds': 15  # Temps approximatif pour clustering seul
            }
            current_app.logger.info("✅ Clustering terminé avec embeddings réutilisés")
        else:
            # PREMIÈRE FOIS : calculer tout (LENT - 4-5 minutes)
            current_app.logger.info("🔄 Génération des nouveaux embeddings (première fois)")
            result = ml_client.process_project(
                image_paths=image_paths,
                n_clusters=project.n_clusters,
                model='resnet50'
            )
            
            # Sauvegarder les embeddings pour réutilisation future
            embeddings_array = np.array(result['embeddings'])
            np.save(embeddings_file, embeddings_array)
            project.embeddings_path = embeddings_file
            current_app.logger.info(f"💾 Embeddings sauvegardés dans {embeddings_file}")
            
            # Sauvegarder les centroïdes pour la prédiction
            if 'centroids' in result:
                centroids_array = np.array(result['centroids'])
                np.save(centroids_file, centroids_array)
                current_app.logger.info(f"💾 Centroïdes sauvegardés dans {centroids_file}")
        
        # Mettre à jour les images avec les résultats
        for i, image in enumerate(images):
            image.cluster_id = int(result['labels'][i])
            image.confidence_score = float(result['confidence_scores'][i])
            image.is_uncertain = (result['confidence_scores'][i] < 0.3)
            image.original_cluster_id = image.cluster_id
            image.initial_confidence = image.confidence_score
        
        # Mettre à jour le projet
        project.status = 'completed'
        project.ml_model_id = result['model_id']
        project.mean_confidence = result['mean_confidence']
        project.n_uncertain = result['n_uncertain']
        project.completed_at = datetime.utcnow()
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Traitement terminé: {len(images)} images classifiées en {project.n_clusters} clusters',
            'results': {
                'n_images': len(images),
                'n_clusters': project.n_clusters,
                'mean_confidence': result['mean_confidence'],
                'n_uncertain': result['n_uncertain'],
                'silhouette_score': result.get('silhouette_score'),
                'processing_time_seconds': result['processing_time_seconds']
            }
        })
    
    except Exception as e:
        project.status = 'created'
        db.session.commit()
        current_app.logger.error(f"Error processing project {project_id}: {e}")
        return jsonify({'error': f'Erreur lors du traitement: {str(e)}'}), 500

@projects_bp.route('/<int:project_id>/processing-status', methods=['GET'])
@login_required
def processing_status(project_id):
    """Retourne le statut du traitement en cours"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    # Récupérer le nombre total d'images
    total_images = project.n_images
    
    # Compter combien ont déjà un cluster_id (= traitées)
    processed_images = Image.query.filter(
        Image.project_id == project_id,
        Image.cluster_id.isnot(None)
    ).count()
    
    return jsonify({
        'status': project.status,
        'total': total_images,
        'processed': processed_images,
        'percent': round((processed_images / total_images * 100) if total_images > 0 else 0, 1)
    })

# ============================================================================
# VALIDATION DES CLUSTERS
# ============================================================================

@projects_bp.route('/<int:project_id>/validate')
@login_required
def validate_clusters(project_id):
    """Affiche l'interface de validation des clusters"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if project.status != 'completed':
        flash('Le projet doit être traité avant validation', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    images = Image.query.filter_by(project_id=project_id).all()
    
    clusters = {}
    for image in images:
        cluster_id = image.cluster_id
        if cluster_id not in clusters:
            clusters[cluster_id] = {
                'id': cluster_id,
                'images': [],
                'n_images': 0,
                'mean_confidence': 0,
                'n_uncertain': 0
            }
        clusters[cluster_id]['images'].append(image)
    
    for cluster in clusters.values():
        # TRI DÉCROISSANT : du plus proche (score élevé) au plus loin (score faible)
        cluster['images'].sort(key=lambda x: x.confidence_score or 0, reverse=True)
        cluster['n_images'] = len(cluster['images'])
        confidences = [img.confidence_score for img in cluster['images'] if img.confidence_score]
        cluster['mean_confidence'] = sum(confidences) / len(confidences) if confidences else 0
        cluster['n_uncertain'] = sum(1 for img in cluster['images'] if img.is_uncertain)
    
    sorted_clusters = dict(sorted(clusters.items()))
    
    return render_template('projects/validate.html', 
                         project=project, 
                         clusters=sorted_clusters)

@projects_bp.route('/<int:project_id>/clusters/<int:cluster_id>/validate', methods=['POST'])
@login_required
def validate_cluster(project_id, cluster_id):
    """Valide ou rejette des images d'un cluster"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        data = request.get_json()
        rejected_ids = data.get('rejected_ids', [])
        validated_ids = data.get('validated_ids', [])
        
        if rejected_ids:
            Image.query.filter(
                Image.id.in_(rejected_ids),
                Image.project_id == project_id
            ).update({
                'validation_status': 'rejected',
                'validated_by': current_user.id,
                'validated_at': datetime.utcnow()
            }, synchronize_session=False)
        
        if validated_ids:
            Image.query.filter(
                Image.id.in_(validated_ids),
                Image.project_id == project_id
            ).update({
                'validation_status': 'approved',
                'validated_by': current_user.id,
                'validated_at': datetime.utcnow()
            }, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'n_rejected': len(rejected_ids),
            'n_validated': len(validated_ids)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SUPPRIMER UN PROJET
# ============================================================================

@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Supprime un projet et toutes ses images"""
    project = Project.query.get_or_404(project_id)
    
    # Vérifier que c'est bien son projet
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        # Supprimer les fichiers physiques
        if project.images_folder and Path(project.images_folder).exists():
            import shutil
            shutil.rmtree(project.images_folder)
        
        # Supprimer en DB (cascade supprime aussi les images)
        db.session.delete(project)
        db.session.commit()
        
        flash(f'Projet "{project.name}" supprimé', 'success')
        return redirect(url_for('projects.list_projects'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression: {str(e)}', 'error')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
@projects_bp.route('/<int:project_id>/cluster-overview')
@login_required
def cluster_overview(project_id):
    """Affiche un aperçu des clusters avec leur image centrale"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if project.status != 'completed':
        flash('Le projet doit être traité avant visualisation', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    # Récupérer toutes les images
    images = Image.query.filter_by(project_id=project_id).all()
    
    # Grouper par cluster
    clusters = {}
    for image in images:
        cluster_id = image.cluster_id
        if cluster_id not in clusters:
            clusters[cluster_id] = {
                'id': cluster_id,
                'images': [],
                'n_images': 0,
                'mean_confidence': 0,
                'n_uncertain': 0,
                'central_image': None
            }
        clusters[cluster_id]['images'].append(image)
    
    # Pour chaque cluster, trouver l'image la plus centrale
    # (celle avec la plus haute confiance = la plus proche du centroïde)
    for cluster in clusters.values():
        cluster['n_images'] = len(cluster['images'])
        
        # Trier par confiance décroissante
        sorted_images = sorted(cluster['images'], 
                              key=lambda x: x.confidence_score or 0, 
                              reverse=True)
        
        # L'image la plus confiante = la plus proche du centroïde
        cluster['central_image'] = sorted_images[0] if sorted_images else None
        
        # Statistiques
        confidences = [img.confidence_score for img in cluster['images'] if img.confidence_score]
        cluster['mean_confidence'] = sum(confidences) / len(confidences) if confidences else 0
        cluster['n_uncertain'] = sum(1 for img in cluster['images'] if img.is_uncertain)
        
        # Ne garder que l'image centrale (pas besoin de toutes)
        cluster['images'] = []
    
    # Trier par ID
    sorted_clusters = dict(sorted(clusters.items()))
    
    # Statistiques globales
    total_images = len(images)
    avg_cluster_size = total_images / len(clusters) if clusters else 0
    small_clusters = sum(1 for c in clusters.values() if c['n_images'] < 50)
    large_clusters = sum(1 for c in clusters.values() if c['n_images'] > 1000)
    low_confidence_clusters = sum(1 for c in clusters.values() if c['mean_confidence'] < 0.5)
    
    stats = {
        'avg_cluster_size': avg_cluster_size,
        'small_clusters': small_clusters,
        'large_clusters': large_clusters,
        'low_confidence_clusters': low_confidence_clusters
    }
    
    return render_template('projects/cluster_overview.html', 
                         project=project, 
                         clusters=sorted_clusters,
                         stats=stats)

@projects_bp.route('/<int:project_id>/reprocess', methods=['POST'])
@login_required
def reprocess_project(project_id):
    """Relance le clustering avec un nouveau nombre de clusters"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        data = request.get_json()
        new_n_clusters = data.get('n_clusters')
        
        if not new_n_clusters or new_n_clusters < 2 or new_n_clusters > 50:
            return jsonify({'error': 'Le nombre de clusters doit être entre 2 et 50'}), 400
        
        # Mettre à jour le nombre de clusters
        project.n_clusters = new_n_clusters
        project.status = 'processing'
        
        # Réinitialiser les résultats précédents
        Image.query.filter_by(project_id=project_id).update({
            'cluster_id': None,
            'confidence_score': None,
            'is_uncertain': False,
            'validation_status': 'pending'
        })
        
        db.session.commit()
        
        # Relancer le traitement avec réutilisation des embeddings
        from utils.ml_client import MLServiceClient
        import numpy as np
        import os
        
        ml_client = MLServiceClient()
        if not ml_client.health_check():
            return jsonify({'error': 'Le service ML n\'est pas accessible'}), 503
        
        images = Image.query.filter_by(project_id=project_id).all()
        
        # Définir les chemins des fichiers
        embeddings_file = project.embeddings_path or os.path.join(project.images_folder, 'embeddings.npy')
        centroids_file = os.path.join(
            os.path.dirname(embeddings_file), 
            'centroids.npy'
        )
        
        # Vérifier si les embeddings existent
        if os.path.exists(embeddings_file):
            # RÉUTILISER les embeddings existants (RAPIDE - 10-20 secondes)
            current_app.logger.info(f"⚡ Réutilisation des embeddings pour retraitement avec {new_n_clusters} clusters")
            embeddings = np.load(embeddings_file).tolist()
            
            # Recalculer uniquement le clustering avec le nouveau n_clusters
            clustering_result = ml_client.fit_kmeans(embeddings, new_n_clusters)
            labels = clustering_result['labels']
            model_id = clustering_result['model_id']
            
            # Sauvegarder les centroïdes pour la prédiction
            if 'centroids' in clustering_result:
                centroids_array = np.array(clustering_result['centroids'])
                np.save(centroids_file, centroids_array)
                current_app.logger.info(f"💾 Centroïdes sauvegardés dans {centroids_file}")
            
            # Calculer confiance
            confidence_result = ml_client.calculate_confidence(embeddings, model_id, threshold=0.3)
            
            result = {
                'labels': labels,
                'confidence_scores': confidence_result['scores'],
                'model_id': model_id,
                'mean_confidence': confidence_result['mean_confidence'],
                'n_uncertain': confidence_result['n_uncertain'],
                'silhouette_score': clustering_result.get('silhouette_score'),
                'processing_time_seconds': 15
            }
            current_app.logger.info("✅ Retraitement terminé avec embeddings réutilisés")
        else:
            # PREMIÈRE FOIS : tout recalculer (LENT - 4-5 minutes)
            current_app.logger.info("🔄 Génération des embeddings (pas de fichier existant)")
            image_paths = [img.file_path for img in images]
            result = ml_client.process_project(
                image_paths=image_paths,
                n_clusters=new_n_clusters,
                model='resnet50'
            )
            
            # Sauvegarder les embeddings
            embeddings_array = np.array(result['embeddings'])
            os.makedirs(os.path.dirname(embeddings_file), exist_ok=True)
            np.save(embeddings_file, embeddings_array)
            project.embeddings_path = embeddings_file
            current_app.logger.info(f"💾 Embeddings sauvegardés dans {embeddings_file}")
            
            # Sauvegarder les centroïdes pour la prédiction
            if 'centroids' in result:
                centroids_array = np.array(result['centroids'])
                np.save(centroids_file, centroids_array)
                current_app.logger.info(f"💾 Centroïdes sauvegardés dans {centroids_file}")
        
        # Mettre à jour les images avec les nouveaux résultats
        for i, image in enumerate(images):
            image.cluster_id = int(result['labels'][i])
            image.confidence_score = float(result['confidence_scores'][i])
            image.is_uncertain = (result['confidence_scores'][i] < 0.3)
        
        # Mettre à jour le projet
        project.status = 'completed'
        project.ml_model_id = result['model_id']
        project.mean_confidence = result['mean_confidence']
        project.n_uncertain = result['n_uncertain']
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Nouveau clustering effectué avec {new_n_clusters} clusters'
        })
    
    except Exception as e:
        project.status = 'completed'
        db.session.commit()
        current_app.logger.error(f"Error reprocessing project: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/clusters/<int:cluster_id>/reject-all', methods=['POST'])
@login_required
def reject_all_cluster(project_id, cluster_id):
    """Rejette toutes les images d'un cluster"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        # Récupérer toutes les images du cluster
        images = Image.query.filter_by(
            project_id=project_id,
            cluster_id=cluster_id
        ).all()
        
        if not images:
            return jsonify({'error': 'Aucune image trouvée dans ce cluster'}), 404
        
        n_images = len(images)
        
        # Marquer toutes les images comme rejetées
        Image.query.filter_by(
            project_id=project_id,
            cluster_id=cluster_id
        ).update({
            'validation_status': 'rejected',
            'validated_by': current_user.id,
            'validated_at': datetime.utcnow(),
            'rejection_reason': f'Cluster {cluster_id} entier rejeté'
        })
        
        db.session.commit()
        
        current_app.logger.info(f"User {current_user.id} rejected entire cluster {cluster_id} ({n_images} images) in project {project_id}")
        
        return jsonify({
            'success': True,
            'message': f'{n_images} images du Cluster {cluster_id} ont été rejetées',
            'n_rejected': n_images
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting cluster {cluster_id}: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/name-clusters', methods=['GET'])
@login_required
def name_clusters(project_id):
    """Affiche l'interface de nommage des clusters"""
    from models.project import Cluster
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if project.status != 'completed':
        flash('Le projet doit être traité avant le nommage', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    # Récupérer tous les clusters avec leurs images (seulement approved)
    images = Image.query.filter_by(
        project_id=project_id,
        validation_status='approved'
    ).all()
    
    # Grouper par cluster_id
    clusters_data = {}
    for image in images:
        cluster_id = image.cluster_id
        if cluster_id not in clusters_data:
            clusters_data[cluster_id] = {
                'cluster_id': cluster_id,
                'n_images': 0,
                'mean_confidence': 0,
                'images': []
            }
        clusters_data[cluster_id]['images'].append(image)
        clusters_data[cluster_id]['n_images'] += 1
    
    # Calculer mean_confidence et récupérer noms existants
    for cluster_id, data in clusters_data.items():
        confidences = [img.confidence_score for img in data['images'] if img.confidence_score]
        data['mean_confidence'] = sum(confidences) / len(confidences) if confidences else 0
        
        # Récupérer l'image centrale (plus haute confiance)
        data['images'].sort(key=lambda x: x.confidence_score or 0, reverse=True)
        data['central_image'] = data['images'][0] if data['images'] else None
        
        # Récupérer le nom existant si déjà nommé
        existing_cluster = Cluster.query.filter_by(
            project_id=project_id,
            cluster_id=cluster_id
        ).first()
        
        data['cluster_name'] = existing_cluster.cluster_name if existing_cluster else ''
        data['description'] = existing_cluster.description if existing_cluster else ''
    
    sorted_clusters = dict(sorted(clusters_data.items()))
    
    return render_template('projects/name_clusters.html',
                         project=project,
                         clusters=sorted_clusters)

@projects_bp.route('/<int:project_id>/clusters/save-names', methods=['POST'])
@login_required
def save_cluster_names(project_id):
    """Enregistre les noms des clusters"""
    from models.project import Cluster
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        data = request.get_json()
        clusters = data.get('clusters', [])
        
        for cluster_data in clusters:
            cluster_id = cluster_data.get('cluster_id')
            cluster_name = cluster_data.get('cluster_name', '').strip()
            description = cluster_data.get('description', '').strip()
            
            # Chercher si le cluster existe déjà
            cluster = Cluster.query.filter_by(
                project_id=project_id,
                cluster_id=cluster_id
            ).first()
            
            if cluster:
                # Mettre à jour
                cluster.cluster_name = cluster_name if cluster_name else None
                cluster.description = description if description else None
                cluster.updated_at = datetime.utcnow()
            else:
                # Créer nouveau
                cluster = Cluster(
                    project_id=project_id,
                    cluster_id=cluster_id,
                    cluster_name=cluster_name if cluster_name else None,
                    description=description if description else None
                )
                db.session.add(cluster)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{len(clusters)} clusters nommés avec succès'
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving cluster names: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/merge-clusters', methods=['GET'])
@login_required
def merge_clusters_view(project_id):
    """Affiche l'interface de fusion des clusters"""
    from models.project import Cluster
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if project.status != 'completed':
        flash('Le projet doit être traité avant la fusion', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    # Récupérer tous les clusters avec leurs images (seulement approved)
    images = Image.query.filter_by(
        project_id=project_id,
        validation_status='approved'
    ).all()
    
    # Grouper par cluster_id
    clusters_data = {}
    for image in images:
        cluster_id = image.cluster_id
        if cluster_id not in clusters_data:
            clusters_data[cluster_id] = {
                'cluster_id': cluster_id,
                'n_images': 0,
                'mean_confidence': 0,
                'images': []
            }
        clusters_data[cluster_id]['images'].append(image)
        clusters_data[cluster_id]['n_images'] += 1
    
    # Calculer mean_confidence et récupérer noms
    for cluster_id, data in clusters_data.items():
        confidences = [img.confidence_score for img in data['images'] if img.confidence_score]
        data['mean_confidence'] = sum(confidences) / len(confidences) if confidences else 0
        
        # Image centrale (plus haute confiance)
        data['images'].sort(key=lambda x: x.confidence_score or 0, reverse=True)
        data['central_image'] = data['images'][0] if data['images'] else None
        
        # Récupérer le nom du cluster
        existing_cluster = Cluster.query.filter_by(
            project_id=project_id,
            cluster_id=cluster_id
        ).first()
        
        data['cluster_name'] = existing_cluster.cluster_name if existing_cluster else f'Cluster {cluster_id}'
    
    sorted_clusters = dict(sorted(clusters_data.items()))
    
    return render_template('projects/merge_clusters.html',
                         project=project,
                         clusters=sorted_clusters)

@projects_bp.route('/<int:project_id>/clusters/merge', methods=['POST'])
@login_required
def merge_clusters(project_id):
    """Fusionne plusieurs clusters en un seul"""
    from models.project import Cluster
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        data = request.get_json()
        cluster_ids = data.get('cluster_ids', [])
        new_name = data.get('new_name', '').strip()
        
        if len(cluster_ids) < 2:
            return jsonify({'error': 'Sélectionnez au moins 2 clusters à fusionner'}), 400
        
        # Le cluster de destination est le plus petit ID
        target_cluster_id = min(cluster_ids)
        source_cluster_ids = [cid for cid in cluster_ids if cid != target_cluster_id]
        
        # Déplacer toutes les images des clusters sources vers le cluster cible
        n_moved = 0
        for source_id in source_cluster_ids:
            images = Image.query.filter_by(
                project_id=project_id,
                cluster_id=source_id,
                validation_status='approved'
            ).all()
            
            for image in images:
                image.cluster_id = target_cluster_id
                image.moved_from_cluster = source_id
                n_moved += 1
        
        # Mettre à jour ou créer le nom du cluster fusionné
        target_cluster = Cluster.query.filter_by(
            project_id=project_id,
            cluster_id=target_cluster_id
        ).first()
        
        if target_cluster:
            if new_name:
                target_cluster.cluster_name = new_name
                target_cluster.updated_at = datetime.utcnow()
        else:
            if new_name:
                target_cluster = Cluster(
                    project_id=project_id,
                    cluster_id=target_cluster_id,
                    cluster_name=new_name
                )
                db.session.add(target_cluster)
        
        # Supprimer les entrées Cluster des clusters sources
        Cluster.query.filter(
            Cluster.project_id == project_id,
            Cluster.cluster_id.in_(source_cluster_ids)
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        current_app.logger.info(f"User {current_user.id} merged clusters {cluster_ids} into {target_cluster_id} in project {project_id}")
        
        return jsonify({
            'success': True,
            'message': f'{len(cluster_ids)} clusters fusionnés ({n_moved} images déplacées)',
            'target_cluster_id': target_cluster_id
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error merging clusters: {e}")
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<int:project_id>/export/csv', methods=['GET'])
@login_required
def export_csv(project_id):
    """Exporte les résultats du projet en CSV"""
    from models.project import Cluster
    import csv
    from io import StringIO
    from flask import Response
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Récupérer toutes les images
    images = Image.query.filter_by(project_id=project_id).all()
    
    # Récupérer les noms des clusters
    clusters = Cluster.query.filter_by(project_id=project_id).all()
    cluster_names = {c.cluster_id: c.cluster_name for c in clusters}
    
    # Créer le CSV en mémoire
    si = StringIO()
    writer = csv.writer(si)
    
    # En-têtes
    writer.writerow([
        'image_id',
        'filename',
        'cluster_id',
        'cluster_name',
        'confidence_score',
        'validation_status',
        'is_uncertain',
        'validated_at',
        'rejection_reason'
    ])
    
    # Données
    for image in images:
        cluster_name = cluster_names.get(image.cluster_id, f'Cluster {image.cluster_id}')
        writer.writerow([
            image.id,
            image.original_filename,
            image.cluster_id if image.cluster_id is not None else '',
            cluster_name,
            f"{image.confidence_score:.4f}" if image.confidence_score else '',
            image.validation_status,
            'Yes' if image.is_uncertain else 'No',
            image.validated_at.isoformat() if image.validated_at else '',
            image.rejection_reason or ''
        ])
    
    # Préparer la réponse
    output = si.getvalue()
    si.close()
    
    response = Response(output, mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename={project.name}_export.csv'
    
    current_app.logger.info(f"User {current_user.id} exported project {project_id} to CSV")
    
    return response

@projects_bp.route('/<int:project_id>/export/json', methods=['GET'])
@login_required
def export_json(project_id):
    """Exporte les résultats du projet en JSON"""
    from models.project import Cluster
    from flask import Response
    import json
    
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Récupérer toutes les images
    images = Image.query.filter_by(project_id=project_id).all()
    
    # Récupérer les clusters
    clusters = Cluster.query.filter_by(project_id=project_id).all()
    cluster_names = {c.cluster_id: c.cluster_name for c in clusters}
    
    # Grouper images par cluster
    clusters_data = {}
    for image in images:
        cluster_id = image.cluster_id
        if cluster_id not in clusters_data:
            clusters_data[cluster_id] = {
                'cluster_id': cluster_id,
                'cluster_name': cluster_names.get(cluster_id, f'Cluster {cluster_id}'),
                'images': []
            }
        
        clusters_data[cluster_id]['images'].append({
            'image_id': image.id,
            'filename': image.original_filename,
            'confidence_score': image.confidence_score,
            'validation_status': image.validation_status,
            'is_uncertain': image.is_uncertain,
            'validated_at': image.validated_at.isoformat() if image.validated_at else None,
            'rejection_reason': image.rejection_reason
        })
    
    # Construire le JSON complet
    export_data = {
        'project': {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'n_clusters': project.n_clusters,
            'n_images': project.n_images,
            'mean_confidence': project.mean_confidence,
            'n_uncertain': project.n_uncertain,
            'created_at': project.created_at.isoformat(),
            'completed_at': project.completed_at.isoformat() if project.completed_at else None
        },
        'clusters': list(clusters_data.values()),
        'statistics': {
            'total_images': len(images),
            'approved': len([img for img in images if img.validation_status == 'approved']),
            'rejected': len([img for img in images if img.validation_status == 'rejected']),
            'pending': len([img for img in images if img.validation_status == 'pending'])
        }
    }
    
    response = Response(
        json.dumps(export_data, indent=2),
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename={project.name}_export.json'
    
    current_app.logger.info(f"User {current_user.id} exported project {project_id} to JSON")
    
    return response

@projects_bp.route('/<int:project_id>/finalize', methods=['GET', 'POST'])
@login_required
def finalize_project(project_id):
    """Finalise le projet et propose de gérer les images rejetées"""
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if request.method == 'GET':
        # Compter les images rejetées
        n_rejected = Image.query.filter_by(
            project_id=project_id,
            validation_status='rejected'
        ).count()
        
        n_approved = Image.query.filter_by(
            project_id=project_id,
            validation_status='approved'
        ).count()
        
        return render_template('projects/finalize.html',
                             project=project,
                             n_rejected=n_rejected,
                             n_approved=n_approved)
    
    # POST - Traiter la finalisation
    action = request.form.get('action')
    
    if action == 'create_rejected_project':
        # Créer un nouveau projet avec les images rejetées
        rejected_images = Image.query.filter_by(
            project_id=project_id,
            validation_status='rejected'
        ).all()
        
        if len(rejected_images) < 2:
            flash('Pas assez d\'images rejetées pour créer un nouveau projet (minimum 2)', 'warning')
            return redirect(url_for('projects.finalize_project', project_id=project_id))
        
        # Créer le nouveau projet
        new_project = Project(
            user_id=current_user.id,
            name=f"{project.name} - Rejetées",
            description=f"Images rejetées du projet '{project.name}'",
            n_clusters=max(2, min(10, len(rejected_images) // 10)),  # Min 2, max 10
            status='created',
            n_images=len(rejected_images)
        )
        db.session.add(new_project)
        db.session.flush()
        
        # Créer le dossier
        new_folder = os.path.join('uploads', 'projects', str(new_project.id))
        os.makedirs(new_folder, exist_ok=True)
        new_project.images_folder = new_folder
        
        # Copier les images
        import shutil
        for old_image in rejected_images:
            # Copier le fichier
            new_filename = f"{uuid.uuid4().hex}{os.path.splitext(old_image.filename)[1]}"
            new_path = os.path.join(new_folder, new_filename)
            shutil.copy2(old_image.file_path, new_path)
            
            # Créer nouvelle entrée
            new_image = Image(
                project_id=new_project.id,
                filename=new_filename,
                original_filename=old_image.original_filename,
                file_path=new_path,
                file_size=old_image.file_size
            )
            db.session.add(new_image)
        
        # Marquer le projet original comme finalisé
        project.status = 'finalized'
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'✅ Projet "{new_project.name}" créé avec {len(rejected_images)} images rejetées', 'success')
        return redirect(url_for('projects.project_detail', project_id=new_project.id))
    
    elif action == 'delete_rejected':
        # Supprimer les images rejetées
        rejected_images = Image.query.filter_by(
            project_id=project_id,
            validation_status='rejected'
        ).all()
        
        # Supprimer les fichiers
        for image in rejected_images:
            try:
                if os.path.exists(image.file_path):
                    os.remove(image.file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting file {image.file_path}: {e}")
        
        # Supprimer les entrées DB
        Image.query.filter_by(
            project_id=project_id,
            validation_status='rejected'
        ).delete()
        
        # Mettre à jour le projet
        project.status = 'finalized'
        project.n_images = Image.query.filter_by(project_id=project_id).count()
        project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'✅ {len(rejected_images)} images rejetées supprimées', 'success')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    elif action == 'keep_rejected':
        # Juste marquer comme finalisé
        project.status = 'finalized'
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('✅ Projet finalisé', 'success')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    
    else:
        flash('Action invalide', 'error')
        return redirect(url_for('projects.finalize_project', project_id=project_id))

# ============================================
# ROUTES API KEYS
# ============================================

@projects_bp.route('/api-keys', methods=['GET'])
@login_required
def list_api_keys():
    """Liste les clés API de l'utilisateur"""
    from models.api_key import APIKey
    
    keys = APIKey.query.filter_by(user_id=current_user.id).order_by(APIKey.created_at.desc()).all()
    
    return render_template('api_keys/list.html', keys=keys)

@projects_bp.route('/api-keys/create', methods=['POST'])
@login_required
def create_api_key():
    """Crée une nouvelle clé API"""
    from models.api_key import APIKey
    
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Le nom de la clé est requis', 'error')
        return redirect(url_for('projects.list_api_keys'))
    
    # Créer la clé
    api_key = APIKey(
        user_id=current_user.id,
        key=APIKey.generate_key(),
        name=name,
        is_active=True
    )
    
    db.session.add(api_key)
    db.session.commit()
    
    flash(f'✅ Clé API créée avec succès', 'success')
    return redirect(url_for('projects.list_api_keys'))

@projects_bp.route('/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
def delete_api_key(key_id):
    """Supprime une clé API"""
    from models.api_key import APIKey
    
    key = APIKey.query.get_or_404(key_id)
    
    if key.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_api_keys'))
    
    db.session.delete(key)
    db.session.commit()
    
    flash('✅ Clé API supprimée', 'success')
    return redirect(url_for('projects.list_api_keys'))

@projects_bp.route('/api-keys/<int:key_id>/toggle', methods=['POST'])
@login_required
def toggle_api_key(key_id):
    """Active/Désactive une clé API"""
    from models.api_key import APIKey
    
    key = APIKey.query.get_or_404(key_id)
    
    if key.user_id != current_user.id:
        flash('Accès non autorisé', 'error')
        return redirect(url_for('projects.list_api_keys'))
    
    key.is_active = not key.is_active
    db.session.commit()
    
    status = 'activée' if key.is_active else 'désactivée'
    flash(f'✅ Clé API {status}', 'success')
    return redirect(url_for('projects.list_api_keys'))

