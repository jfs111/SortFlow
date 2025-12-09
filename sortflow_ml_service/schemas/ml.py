"""Schémas Pydantic pour validation des requêtes/réponses"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# === EMBEDDINGS ===

class EmbeddingRequest(BaseModel):
    model: str = Field(default="resnet50", description="Nom du modèle")
    batch_size: int = Field(default=32, ge=1, le=128, description="Taille du batch")

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    metadata: Dict[str, Any]

class EmbeddingSaveRequest(BaseModel):
    embeddings: List[List[float]]
    path: str
    format: str = Field(default="npy", pattern="^(npy|npz)$")

class EmbeddingSaveResponse(BaseModel):
    success: bool
    file_path: str
    size_mb: float

class EmbeddingLoadResponse(BaseModel):
    embeddings: List[List[float]]
    shape: List[int]
    metadata: Dict[str, Any]

# === KMEANS ===

class KMeansFitRequest(BaseModel):
    embeddings: Optional[List[List[float]]] = None
    embeddings_path: Optional[str] = None
    n_clusters: int = Field(default=20, ge=2, le=100)
    random_state: int = Field(default=42)
    n_init: int = Field(default=10, ge=1)
    max_iter: int = Field(default=300, ge=100)

class KMeansFitResponse(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    model_id: str
    n_clusters: int
    labels: List[int]
    centroids: List[List[float]]
    inertia: float
    n_iter: int
    cluster_sizes: Dict[int, int]

class KMeansPredictRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    embeddings: Optional[List[List[float]]] = None
    embeddings_path: Optional[str] = None
    model_id: str

class KMeansPredictResponse(BaseModel):
    labels: List[int]
    distances: List[float]

class ClusteringMetricsRequest(BaseModel):
    embeddings: Optional[List[List[float]]] = None
    embeddings_path: Optional[str] = None
    labels: List[int]

class ClusteringMetricsResponse(BaseModel):
    n_samples: int
    n_clusters: int
    silhouette_score: Optional[float]
    davies_bouldin_score: Optional[float]
    calinski_harabasz_score: Optional[float]
    cluster_distribution: Dict[int, int]

class ConfidenceRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    embeddings: Optional[List[List[float]]] = None
    embeddings_path: Optional[str] = None
    model_id: str
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)

class ConfidenceResponse(BaseModel):
    confidence_scores: List[float]
    mean_confidence: float
    median_confidence: float
    min_confidence: float
    max_confidence: float
    threshold: float
    uncertain_count: int
    uncertain_indices: List[int]

class ModelSaveRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    model_id: str
    path: str

class ModelSaveResponse(BaseModel):
    success: bool
    file_path: str

class ModelLoadRequest(BaseModel):
    path: str

class ModelLoadResponse(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    model_id: str
    n_clusters: int
    n_features: int

# === SANTEE ===

class HealthResponse(BaseModel):
    status: str
    version: str
    device: str
    models_loaded: Dict[str, Any]
    uptime_seconds: float

class ModelsListResponse(BaseModel):
    available_models: Dict[str, Any]
    current_model: str