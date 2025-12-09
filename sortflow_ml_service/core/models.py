"""Gestion centralisée des modèles ML (Singleton)"""
import torch
import torchvision.models as models
from torchvision import transforms
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

class ModelManager:
    """Singleton pour gérer les modèles ML"""
    _instance: Optional['ModelManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.device = torch.device(settings.DEVICE)
        self.models = {}
        self.transforms = {}
        
        self.load_model(settings.DEFAULT_MODEL)
        
        self._initialized = True
        logger.info(f"ModelManager initialized on device: {self.device}")
    
    def load_model(self, model_name: str = "resnet50"):
        """Charge un modèle d'embeddings"""
        if model_name in self.models:
            logger.info(f"Model {model_name} already loaded")
            return
        
        logger.info(f"Loading model: {model_name}")
        
        if model_name == "resnet50":
            resnet = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
            resnet = resnet.to(self.device)
            resnet.eval()
            
            embedding_model = torch.nn.Sequential(*list(resnet.children())[:-1])
            
            self.models[model_name] = {
                'model': embedding_model,
                'embedding_dim': 2048,
                'description': 'ResNet50 ImageNet pretrained'
            }
            
            self.transforms[model_name] = transforms.Compose([
                transforms.Resize(256),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                ),
            ])
        else:
            raise ValueError(f"Unknown model: {model_name}")
        
        logger.info(f"Model {model_name} loaded successfully")
    
    def get_model(self, model_name: str = "resnet50"):
        """Récupère un modèle chargé"""
        if model_name not in self.models:
            self.load_model(model_name)
        return self.models[model_name]['model']
    
    def get_transform(self, model_name: str = "resnet50"):
        """Récupère le transform associé"""
        if model_name not in self.transforms:
            self.load_model(model_name)
        return self.transforms[model_name]
    
    def get_embedding_dim(self, model_name: str = "resnet50") -> int:
        """Retourne la dimension d'embedding"""
        if model_name not in self.models:
            self.load_model(model_name)
        return self.models[model_name]['embedding_dim']
    
    def list_models(self):
        """Liste les modèles disponibles"""
        return {
            name: {
                'embedding_dim': info['embedding_dim'],
                'description': info['description'],
                'loaded': True
            }
            for name, info in self.models.items()
        }
    
    def get_device_info(self):
        """Informations sur le device"""
        info = {
            'device': str(self.device),
            'device_type': self.device.type
        }
        
        if self.device.type == 'cuda':
            info.update({
                'gpu_name': torch.cuda.get_device_name(0),
                'gpu_memory_gb': torch.cuda.get_device_properties(0).total_memory / 1024**3,
                'cuda_version': torch.version.cuda
            })
        
        return info

model_manager = ModelManager()