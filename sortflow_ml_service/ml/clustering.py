"""Clustering K-Means et calcul de métriques"""
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from pathlib import Path
import pickle
import logging
from typing import Tuple, Optional, Union
import uuid

from core.config import settings

logger = logging.getLogger(__name__)

class ClusteringManager:
    """Gère les opérations de clustering"""
    
    def __init__(self):
        self.models = {}
    
    def fit_kmeans(
        self,
        embeddings: np.ndarray,
        n_clusters: int = 20,
        random_state: int = 42,
        n_init: int = 10,
        max_iter: int = 300
    ) -> dict:
        """
        Entraîne un modèle K-Means
        
        Returns:
            dict avec model_id, labels, centroids, metrics
        """
        logger.info(f"Fitting K-Means: n_clusters={n_clusters}, n_samples={len(embeddings)}")
        
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=n_init,
            max_iter=max_iter
        )
        
        labels = kmeans.fit_predict(embeddings)
        
        model_id = f"kmeans_{uuid.uuid4().hex[:8]}"
        self.models[model_id] = kmeans
        
        unique, counts = np.unique(labels, return_counts=True)
        cluster_sizes = dict(zip(unique.tolist(), counts.tolist()))
        
        result = {
            'model_id': model_id,
            'n_clusters': n_clusters,
            'labels': labels.tolist(),
            'centroids': kmeans.cluster_centers_.tolist(),
            'inertia': float(kmeans.inertia_),
            'n_iter': int(kmeans.n_iter_),
            'cluster_sizes': cluster_sizes
        }
        
        logger.info(f"K-Means fitted: model_id={model_id}, inertia={kmeans.inertia_:.2f}")
        
        return result
    
    def predict(
        self,
        embeddings: np.ndarray,
        model_id: str
    ) -> dict:
        """
        Prédit les clusters pour de nouveaux embeddings
        
        Returns:
            dict avec labels et distances
        """
        if model_id not in self.models:
            raise ValueError(f"Model not found: {model_id}")
        
        kmeans = self.models[model_id]
        
        labels = kmeans.predict(embeddings)
        
        distances = np.min(kmeans.transform(embeddings), axis=1)
        
        return {
            'labels': labels.tolist(),
            'distances': distances.tolist()
        }
    
    
    def calculate_confidence_scores(
        self,
        embeddings: np.ndarray,
        model_id: str,
        threshold: float = 0.3
    ) -> dict:
        """
        Calcule les scores de confiance basés sur la distance au centroïde
        
        Returns:
            dict avec confidence_scores et indices des images incertaines
        """
        if model_id not in self.models:
            raise ValueError(f"Model not found: {model_id}")
        
        kmeans = self.models[model_id]
        
        distances = np.min(kmeans.transform(embeddings), axis=1)
        
        max_distance = np.max(distances)
        confidence_scores = 1 - (distances / max_distance)
        
        uncertain_mask = confidence_scores < threshold
        uncertain_indices = np.where(uncertain_mask)[0]
        
        result = {
            'confidence_scores': confidence_scores.tolist(),
            'mean_confidence': float(np.mean(confidence_scores)),
            'median_confidence': float(np.median(confidence_scores)),
            'min_confidence': float(np.min(confidence_scores)),
            'max_confidence': float(np.max(confidence_scores)),
            'threshold': threshold,
            'uncertain_count': int(np.sum(uncertain_mask)),
            'uncertain_indices': uncertain_indices.tolist()
        }
        
        logger.info(f"Confidence: mean={result['mean_confidence']:.3f}, "
                   f"uncertain={result['uncertain_count']} ({result['uncertain_count']/len(embeddings)*100:.1f}%)")
        
        return result
    
    def save_model(self, model_id: str, path: Union[str, Path]) -> str:
        """Sauvegarde un modèle K-Means sur disque"""
        if model_id not in self.models:
            raise ValueError(f"Model not found: {model_id}")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        kmeans = self.models[model_id]
        
        with open(path, 'wb') as f:
            pickle.dump(kmeans, f)
        
        logger.info(f"Model {model_id} saved to {path}")
        
        return str(path)
    
    def load_model(self, path: Union[str, Path]) -> str:
        """Charge un modèle K-Means depuis le disque"""
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        
        with open(path, 'rb') as f:
            kmeans = pickle.load(f)
        
        model_id = f"kmeans_{uuid.uuid4().hex[:8]}"
        self.models[model_id] = kmeans
        
        logger.info(f"Model loaded from {path} as {model_id}")
        
        return model_id
    
    def get_model_info(self, model_id: str) -> dict:
        """Récupère les informations d'un modèle"""
        if model_id not in self.models:
            raise ValueError(f"Model not found: {model_id}")
        
        kmeans = self.models[model_id]
        
        return {
            'model_id': model_id,
            'n_clusters': int(kmeans.n_clusters),
            'n_features': int(kmeans.cluster_centers_.shape[1]),
            'inertia': float(kmeans.inertia_),
            'n_iter': int(kmeans.n_iter_)
        }

clustering_manager = ClusteringManager()