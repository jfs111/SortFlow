"""Génération des embeddings"""
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Union, Tuple
import logging
from io import BytesIO

from core.models import model_manager
from core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """Génère des embeddings à partir d'images"""
    
    def __init__(self, model_name: str = "resnet50"):
        self.model_name = model_name
        self.model = model_manager.get_model(model_name)
        self.transform = model_manager.get_transform(model_name)
        self.device = model_manager.device
        self.embedding_dim = model_manager.get_embedding_dim(model_name)
    
    def generate_single(self, image: Union[Path, bytes, Image.Image]) -> np.ndarray:
        """Génère l'embedding d'une seule image"""
        try:
            if isinstance(image, (str, Path)):
                img = Image.open(image).convert('RGB')
            elif isinstance(image, bytes):
                img = Image.open(BytesIO(image)).convert('RGB')
            elif isinstance(image, Image.Image):
                img = image.convert('RGB')
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")
            
            img_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                embedding = self.model(img_tensor)
            
            embedding_np = embedding.squeeze().cpu().numpy()
            
            return embedding_np
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_batch(
        self, 
        images: List[Union[Path, bytes, Image.Image]], 
        batch_size: int = None
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Génère embeddings pour un batch d'images
        
        Returns:
            embeddings: array (n_images, embedding_dim)
            valid_indices: indices des images traitées avec succès
        """
        if batch_size is None:
            batch_size = settings.BATCH_SIZE
        
        all_embeddings = []
        valid_indices = []
        
        logger.info(f"Processing {len(images)} images in batches of {batch_size}")
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i+batch_size]
            batch_tensors = []
            batch_valid_indices = []
            
            for j, image in enumerate(batch):
                try:
                    if isinstance(image, (str, Path)):
                        img = Image.open(image).convert('RGB')
                    elif isinstance(image, bytes):
                        img = Image.open(BytesIO(image)).convert('RGB')
                    elif isinstance(image, Image.Image):
                        img = image.convert('RGB')
                    else:
                        logger.warning(f"Skipping image {i+j}: unsupported type")
                        continue
                    
                    img_tensor = self.transform(img)
                    batch_tensors.append(img_tensor)
                    batch_valid_indices.append(i + j)
                    
                except Exception as e:
                    logger.warning(f"Error processing image {i+j}: {e}")
                    continue
            
            if len(batch_tensors) == 0:
                continue
            
            batch_tensor = torch.stack(batch_tensors).to(self.device)
            
            with torch.no_grad():
                batch_embeddings = self.model(batch_tensor)
            
            batch_embeddings_np = batch_embeddings.squeeze().cpu().numpy()
            
            if batch_embeddings_np.ndim == 1:
                batch_embeddings_np = batch_embeddings_np.reshape(1, -1)
            
            all_embeddings.append(batch_embeddings_np)
            valid_indices.extend(batch_valid_indices)
            
            if (i // batch_size + 1) % 10 == 0:
                logger.info(f"Processed {i + len(batch)} / {len(images)} images")
        
        if len(all_embeddings) == 0:
            return np.array([]), []
        
        embeddings = np.vstack(all_embeddings)
        
        logger.info(f"Generated {len(embeddings)} embeddings (dim={self.embedding_dim})")
        
        return embeddings, valid_indices