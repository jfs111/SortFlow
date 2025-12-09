# utils/security.py
"""Fonctions de sécurité : hash password, JWT, validation"""
import bcrypt
import jwt
import re
from datetime import datetime, timedelta
from typing import Optional

def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec bcrypt
    
    Args:
        password: Mot de passe en clair
        
    Returns:
        Hash bcrypt du mot de passe
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """
    Vérifie un mot de passe contre son hash
    
    Args:
        password: Mot de passe en clair
        password_hash: Hash bcrypt stocké
        
    Returns:
        True si le mot de passe correspond
    """
    password_bytes = password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)

def validate_email(email: str) -> bool:
    """
    Valide le format d'un email
    
    Args:
        email: Adresse email à valider
        
    Returns:
        True si l'email est valide
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str, min_length: int = 8) -> tuple[bool, Optional[str]]:
    """
    Valide la force d'un mot de passe
    
    Args:
        password: Mot de passe à valider
        min_length: Longueur minimale
        
    Returns:
        (is_valid, error_message)
    """
    if len(password) < min_length:
        return False, f"Le mot de passe doit contenir au moins {min_length} caractères"
    
    if not re.search(r'[A-Z]', password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    
    if not re.search(r'[a-z]', password):
        return False, "Le mot de passe doit contenir au moins une minuscule"
    
    if not re.search(r'[0-9]', password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    
    # Optionnel : caractère spécial
    # if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
    #     return False, "Le mot de passe doit contenir au moins un caractère spécial"
    
    return True, None

def generate_jwt_token(user_id: int, secret_key: str, expiration_hours: int = 24) -> str:
    """
    Génère un token JWT pour un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        secret_key: Clé secrète JWT
        expiration_hours: Durée de validité en heures
        
    Returns:
        Token JWT encodé
    """
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expiration_hours),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token