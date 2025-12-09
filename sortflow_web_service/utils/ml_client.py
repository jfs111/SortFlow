# utils/ml_client.py
"""Client pour communiquer avec le service ML FastAPI"""
import os
import requests
from typing import List, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MLServiceClient:
    """Client pour le service ML FastAPI"""
    
    def __init__(self, base_url: str = 'http://localhost:8000'):
        self.base_url = base_url.rstrip('/')
        self.timeout = 300  # 5 minutes
        
    def health_check(self) -> bool:
        """Vérifie que le service ML est accessible"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"ML service health check failed: {e}")
            return False
    
    def generate_embeddings(self, image_paths: List[str], model: str = 'resnet50') -> Dict[str, Any]:
        """Génère les embeddings pour une liste d'images"""
        try:
            logger.info(f"Generating embeddings for {len(image_paths)} images with {model}")
            
            # Traiter par batch de 100 images pour éviter "too many open files"
            BATCH_SIZE = 100
            all_embeddings = []
            total_processing_time = 0
            
            for batch_start in range(0, len(image_paths), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(image_paths))
                batch_paths = image_paths[batch_start:batch_end]
                
                logger.info(f"Processing batch {batch_start // BATCH_SIZE + 1}: {len(batch_paths)} images")
                
                # Préparer les fichiers à envoyer (avec context manager)
                files = []
                file_handles = []
                
                try:
                    for path in batch_paths:
                        file_path = Path(path)
                        if not file_path.exists():
                            logger.error(f"File not found: {path}")
                            continue
                        
                        # Ouvrir le fichier
                        fh = open(path, 'rb')
                        file_handles.append(fh)
                        files.append(('files', (file_path.name, fh, 'image/jpeg')))
                    
                    if not files:
                        logger.warning(f"No valid files in batch {batch_start // BATCH_SIZE + 1}")
                        continue
                    
                    logger.info(f"Sending {len(files)} files to ML service")
                    
                    # Envoyer avec multipart/form-data
                    response = requests.post(
                        f"{self.base_url}/embeddings/generate",
                        files=files,
                        data={'model': model, 'batch_size': 32},
                        timeout=self.timeout
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"ML service returned {response.status_code}: {response.text}")
                        raise Exception(f"ML service error: {response.status_code}")
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # Ajouter les embeddings de ce batch
                    all_embeddings.extend(result['embeddings'])
                    total_processing_time += result['metadata']['processing_time']
                    
                finally:
                    # IMPORTANT: Fermer tous les fichiers de ce batch
                    for fh in file_handles:
                        try:
                            fh.close()
                        except:
                            pass
            
            if not all_embeddings:
                raise Exception("No embeddings generated")
            
            logger.info(f"Successfully generated {len(all_embeddings)} embeddings in {len(range(0, len(image_paths), BATCH_SIZE))} batches")
            
            return {
                'embeddings': all_embeddings,
                'model': model,
                'dimension': result['metadata']['embedding_dim'],
                'processing_time_seconds': total_processing_time,
                'n_images': len(all_embeddings)
            }
            
        except requests.exceptions.Timeout:
            raise Exception(f"ML service timeout après {self.timeout} secondes")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating embeddings: {e}")
            raise Exception(f"Erreur lors de la génération des embeddings: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception(f"Erreur inattendue: {str(e)}")
    
    def fit_kmeans(self, embeddings: List[List[float]], n_clusters: int) -> Dict[str, Any]:
        """Entraîne un modèle K-Means sur les embeddings"""
        try:
            logger.info(f"Fitting K-Means with {n_clusters} clusters on {len(embeddings)} samples")
            
            payload = {
                'embeddings': embeddings,
                'n_clusters': n_clusters,
                'random_state': 42,
                'n_init': 50  # ✅ Meilleure qualité de clustering
            }
            
            response = requests.post(
                f"{self.base_url}/clustering/kmeans/fit",
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"K-Means completed: model_id={result['model_id']}")
            return result
            
        except requests.exceptions.Timeout:
            raise Exception(f"ML service timeout après {self.timeout} secondes")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fitting K-Means: {e}")
            raise Exception(f"Erreur lors du clustering K-Means: {str(e)}")
    
    def calculate_confidence(self, embeddings: List[List[float]], model_id: str, threshold: float = 0.3) -> Dict[str, Any]:
        """Calcule les scores de confiance pour chaque image"""
        try:
            logger.info(f"Calculating confidence scores for {len(embeddings)} samples")
            
            payload = {
                'embeddings': embeddings,
                'model_id': model_id,
                'threshold': threshold
            }
            
            response = requests.post(
                f"{self.base_url}/clustering/confidence",
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Confidence calculated: mean={result['mean_confidence']:.3f}")
            
            # Adapter la réponse au format attendu
            return {
                'scores': result['confidence_scores'],  # ✅ Correct: confidence_scores
                'mean_confidence': result['mean_confidence'],
                'median_confidence': result['median_confidence'],
                'n_uncertain': result['uncertain_count'],  # ✅ Correct: uncertain_count
                'uncertain_indices': result['uncertain_indices']
            }
            
        except requests.exceptions.Timeout:
            raise Exception(f"ML service timeout après {self.timeout} secondes")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calculating confidence: {e}")
            raise Exception(f"Erreur lors du calcul de confiance: {str(e)}")
    
    def process_project(self, image_paths: List[str], n_clusters: int, 
                       model: str = 'resnet50') -> Dict[str, Any]:
        """Traite un projet complet: embeddings + clustering + confidence"""
        logger.info(f"Processing project: {len(image_paths)} images, {n_clusters} clusters")
        
        # 1. Générer embeddings
        embedding_result = self.generate_embeddings(image_paths, model)
        embeddings = embedding_result['embeddings']
        
        # 2. K-Means clustering
        clustering_result = self.fit_kmeans(embeddings, n_clusters)
        labels = clustering_result['labels']
        model_id = clustering_result['model_id']
        
        # 3. Calculer confiance
        confidence_result = self.calculate_confidence(embeddings, model_id, threshold=0.3)
        confidence_scores = confidence_result['scores']
        
        # Combiner les résultats
        return {
            'embeddings': embeddings,
            'labels': labels,
            'confidence_scores': confidence_scores,
            'model_id': model_id,
            'silhouette_score': clustering_result.get('silhouette_score'),
            'mean_confidence': confidence_result['mean_confidence'],
            'median_confidence': confidence_result['median_confidence'],
            'n_uncertain': confidence_result['n_uncertain'],
            'uncertain_indices': confidence_result['uncertain_indices'],
            'processing_time_seconds': embedding_result['processing_time_seconds']
        }
    
    def predict(self, image_path, embeddings_file, centroids_file):
        """
        Prédit le cluster d'une nouvelle image
        
        Args:
            image_path: Chemin de l'image à classifier
            embeddings_file: Chemin du fichier embeddings.npy (pour le modèle)
            centroids_file: Chemin du fichier centroids.npy
        
        Returns:
            dict avec cluster_id, confidence_score, distances
        """
        import numpy as np
        
        try:
            # Générer l'embedding de la nouvelle image
            with open(image_path, 'rb') as f:
                files = [('files', (os.path.basename(image_path), f, 'image/jpeg'))]
                response = requests.post(
                    f"{self.base_url}/embeddings/generate",
                    files=files,
                    timeout=30
                )
            
            if response.status_code != 200:
                raise Exception(f"Erreur génération embedding: {response.status_code}")
            
            embedding_result = response.json()
            embedding = np.array(embedding_result['embeddings'][0])
            
            # Charger les centroïdes
            centroids = np.load(centroids_file)
            
            # Calculer les distances à tous les centroïdes
            distances = np.linalg.norm(centroids - embedding, axis=1)
            
            # Cluster le plus proche
            cluster_id = int(np.argmin(distances))
            min_distance = float(distances[cluster_id])
            
            # Calculer le score de confiance (1 - distance normalisée)
            max_distance = float(np.max(distances))
            confidence_score = 1 - (min_distance / max_distance) if max_distance > 0 else 1.0
            
            return {
                'cluster_id': cluster_id,
                'confidence_score': confidence_score,
                'distance': min_distance,
                'all_distances': distances.tolist()
            }
        
        except Exception as e:
            raise Exception(f"Erreur lors de la prédiction: {str(e)}")