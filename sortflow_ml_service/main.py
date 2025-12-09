# main.py
"""SortFlow ML Service - FastAPI Application"""
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
import time
import logging
import numpy as np
from pathlib import Path

from core.config import settings
from core.models import model_manager
from ml.embeddings import EmbeddingGenerator
from ml.clustering import clustering_manager
from schemas.ml import *

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tracking du uptime
START_TIME = time.time()

# ============================================================================
# LIFESPAN EVENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Startup
    logger.info("="*60)
    logger.info(f"{settings.SERVICE_NAME} v{settings.VERSION}")
    logger.info("="*60)
    logger.info(f"Device: {settings.DEVICE}")
    logger.info(f"Default model: {settings.DEFAULT_MODEL}")
    logger.info("="*60)
    
    # Pré-charger le modèle par défaut
    logger.info("Pre-loading default model...")
    model_manager.get_model(settings.DEFAULT_MODEL)
    logger.info("Model loaded successfully")
    
    logger.info("ML Service ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ML Service...")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="Service ML pour génération d'embeddings et clustering",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH & INFO
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de la santé du service"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "device": str(settings.DEVICE),
        "models_loaded": model_manager.list_models(),
        "uptime_seconds": time.time() - START_TIME
    }

@app.get("/models", response_model=ModelsListResponse)
async def list_models():
    """Liste les modèles disponibles"""
    return {
        "available_models": model_manager.list_models(),
        "current_model": settings.DEFAULT_MODEL
    }

# ============================================================================
# EMBEDDINGS
# ============================================================================

@app.post("/embeddings/generate")
async def generate_embeddings(
    files: List[UploadFile] = File(...),
    model: str = "resnet50",
    batch_size: int = 32
):
    """Génère les embeddings pour un batch d'images"""
    logger.info(f"Generating embeddings for {len(files)} images")
    
    if len(files) > settings.MAX_IMAGES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many images. Max: {settings.MAX_IMAGES_PER_REQUEST}"
        )
    
    start_time = time.time()
    
    try:
        # Initialiser le générateur
        generator = EmbeddingGenerator(model_name=model)
        
        # Lire les fichiers en mémoire
        image_bytes = []
        for file in files:
            content = await file.read()
            image_bytes.append(content)
        
        # Générer embeddings
        embeddings, valid_indices = generator.generate_batch(
            image_bytes,
            batch_size=batch_size
        )
        
        processing_time = time.time() - start_time
        
        return {
            "embeddings": embeddings.tolist(),
            "metadata": {
                "n_images": len(files),
                "n_valid": len(valid_indices),
                "embedding_dim": generator.embedding_dim,
                "model": model,
                "processing_time": processing_time,
                "device": str(settings.DEVICE),
                "valid_indices": valid_indices
            }
        }
    
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/save", response_model=EmbeddingSaveResponse)
async def save_embeddings(request: EmbeddingSaveRequest):
    """Sauvegarde les embeddings sur disque"""
    try:
        embeddings = np.array(request.embeddings)
        
        generator = EmbeddingGenerator()
        file_path = generator.save_embeddings(embeddings, request.path)
        
        size_mb = Path(file_path).stat().st_size / 1024**2
        
        return {
            "success": True,
            "file_path": file_path,
            "size_mb": size_mb
        }
    
    except Exception as e:
        logger.error(f"Error saving embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embeddings/load", response_model=EmbeddingLoadResponse)
async def load_embeddings(path: str):
    """Charge les embeddings depuis le disque"""
    try:
        generator = EmbeddingGenerator()
        embeddings, metadata = generator.load_embeddings(path)
        
        return {
            "embeddings": embeddings.tolist(),
            "shape": list(embeddings.shape),
            "metadata": metadata
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except Exception as e:
        logger.error(f"Error loading embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CLUSTERING
# ============================================================================

@app.post("/clustering/kmeans/fit", response_model=KMeansFitResponse)
async def fit_kmeans(request: KMeansFitRequest):
    """Entraîne un modèle K-Means"""
    logger.info(f"Fitting K-Means: n_clusters={request.n_clusters}")
    
    try:
        # Charger les embeddings
        if request.embeddings is not None:
            embeddings = np.array(request.embeddings)
            logger.info(f"Using embeddings from request: shape={embeddings.shape}")
        elif request.embeddings_path is not None:
            generator = EmbeddingGenerator()
            embeddings, _ = generator.load_embeddings(request.embeddings_path)
            logger.info(f"Loaded embeddings from {request.embeddings_path}: shape={embeddings.shape}")
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'embeddings' or 'embeddings_path' must be provided"
            )
        
        # Entraîner K-Means
        result = clustering_manager.fit_kmeans(
            embeddings=embeddings,
            n_clusters=request.n_clusters,
            random_state=request.random_state,
            n_init=request.n_init,
            max_iter=request.max_iter
        )
        
        logger.info(f"K-Means fit successful: model_id={result['model_id']}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fitting K-Means: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clustering/kmeans/predict", response_model=KMeansPredictResponse)
async def predict_kmeans(request: KMeansPredictRequest):
    """Prédit les clusters pour de nouveaux embeddings"""
    try:
        # Charger les embeddings
        if request.embeddings is not None:
            embeddings = np.array(request.embeddings)
        elif request.embeddings_path is not None:
            generator = EmbeddingGenerator()
            embeddings, _ = generator.load_embeddings(request.embeddings_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'embeddings' or 'embeddings_path' must be provided"
            )
        
        # Prédire
        result = clustering_manager.predict(embeddings, request.model_id)
        
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error predicting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clustering/metrics", response_model=ClusteringMetricsResponse)
async def calculate_metrics(request: ClusteringMetricsRequest):
    """Calcule les métriques de clustering"""
    try:
        # Charger les embeddings
        if request.embeddings is not None:
            embeddings = np.array(request.embeddings)
        elif request.embeddings_path is not None:
            generator = EmbeddingGenerator()
            embeddings, _ = generator.load_embeddings(request.embeddings_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'embeddings' or 'embeddings_path' must be provided"
            )
        
        labels = np.array(request.labels)
        
        # Calculer métriques
        metrics = clustering_manager.calculate_metrics(embeddings, labels)
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clustering/confidence", response_model=ConfidenceResponse)
async def calculate_confidence(request: ConfidenceRequest):
    """Calcule les scores de confiance"""
    try:
        # Charger les embeddings
        if request.embeddings is not None:
            embeddings = np.array(request.embeddings)
        elif request.embeddings_path is not None:
            generator = EmbeddingGenerator()
            embeddings, _ = generator.load_embeddings(request.embeddings_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'embeddings' or 'embeddings_path' must be provided"
            )
        
        # Calculer confiance
        result = clustering_manager.calculate_confidence_scores(
            embeddings,
            request.model_id,
            request.threshold
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating confidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clustering/kmeans/save", response_model=ModelSaveResponse)
async def save_model(request: ModelSaveRequest):
    """Sauvegarde un modèle K-Means"""
    try:
        file_path = clustering_manager.save_model(request.model_id, request.path)
        
        return {
            "success": True,
            "file_path": file_path
        }
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clustering/kmeans/load", response_model=ModelLoadResponse)
async def load_model(request: ModelLoadRequest):
    """Charge un modèle K-Means"""
    try:
        model_id = clustering_manager.load_model(request.path)
        model_info = clustering_manager.get_model_info(model_id)
        
        return {
            "model_id": model_id,
            "n_clusters": model_info['n_clusters'],
            "n_features": model_info['n_features']
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Model file not found: {request.path}")
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )