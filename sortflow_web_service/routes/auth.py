# routes/auth.py
"""Routes d'authentification : register, login, logout"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from database.db import db
from models.user import User
from utils.security import (
    hash_password, 
    verify_password, 
    validate_email, 
    validate_password,
    generate_jwt_token
)
from datetime import datetime
import os

# Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ============================================================================
# API ENDPOINTS (JSON)
# ============================================================================

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    API: Enregistrer un nouvel utilisateur
    
    Body JSON:
        {
            "email": "user@example.com",
            "password": "SecurePass123",
            "username": "John Doe" (optionnel)
        }
    
    Returns:
        {
            "success": true,
            "user": {...},
            "token": "jwt_token"
        }
    """
    try:
        data = request.get_json()
        
        # Validation des données
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée fournie'
            }), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        username = data.get('username', '').strip()
        
        # Validation email
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email requis'
            }), 400
        
        if not validate_email(email):
            return jsonify({
                'success': False,
                'error': 'Format email invalide'
            }), 400
        
        # Vérifier si email existe déjà
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Cet email est déjà utilisé'
            }), 400
        
        # Validation mot de passe
        if not password:
            return jsonify({
                'success': False,
                'error': 'Mot de passe requis'
            }), 400
        
        min_length = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
        is_valid, error_msg = validate_password(password, min_length)
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Créer l'utilisateur
        password_hash = hash_password(password)
        
        new_user = User(
            email=email,
            password_hash=password_hash,
            username=username if username else None,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        # Sauvegarder en DB
        db.session.add(new_user)
        db.session.commit()
        
        # Générer token JWT
        jwt_secret = os.getenv('JWT_SECRET_KEY', 'default_secret')
        jwt_hours = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
        token = generate_jwt_token(new_user.id, jwt_secret, jwt_hours)
        
        # Réponse
        return jsonify({
            'success': True,
            'message': 'Utilisateur créé avec succès',
            'user': new_user.to_dict(),
            'token': token
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Erreur serveur: {str(e)}'
        }), 500

# ============================================================================
# WEB ENDPOINTS (HTML)
# ============================================================================

@auth_bp.route('/register', methods=['GET', 'POST'])
def web_register():
    """
    Page web: Formulaire d'inscription
    
    GET: Affiche le formulaire
    POST: Traite l'inscription
    """
    if request.method == 'GET':
        # Afficher le formulaire
        return render_template('auth/register.html')
    
    # POST: Traiter l'inscription
    try:
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        username = request.form.get('username', '').strip()
        
        # Validation email
        if not email:
            flash('Email requis', 'error')
            return redirect(url_for('auth.web_register'))
        
        if not validate_email(email):
            flash('Format email invalide', 'error')
            return redirect(url_for('auth.web_register'))
        
        # Vérifier si email existe déjà
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Cet email est déjà utilisé', 'error')
            return redirect(url_for('auth.web_register'))
        
        # Validation mot de passe
        if not password:
            flash('Mot de passe requis', 'error')
            return redirect(url_for('auth.web_register'))
        
        if password != password_confirm:
            flash('Les mots de passe ne correspondent pas', 'error')
            return redirect(url_for('auth.web_register'))
        
        min_length = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
        is_valid, error_msg = validate_password(password, min_length)
        
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('auth.web_register'))
        
        # Créer l'utilisateur
        password_hash = hash_password(password)
        
        new_user = User(
            email=email,
            password_hash=password_hash,
            username=username if username else None,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        # Sauvegarder en DB
        db.session.add(new_user)
        db.session.commit()
        
        flash('Compte créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('auth.web_login'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la création du compte: {str(e)}', 'error')
        return redirect(url_for('auth.web_register'))

# ============================================================================
# LOGIN
# ============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def web_login():
    """
    Page web: Formulaire de connexion
    
    GET: Affiche le formulaire
    POST: Traite la connexion
    """
    if request.method == 'GET':
        # Afficher le formulaire
        return render_template('auth/login.html')
    
    # POST: Traiter la connexion
    try:
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Validation
        if not email or not password:
            flash('Email et mot de passe requis', 'error')
            return redirect(url_for('auth.web_login'))
        
        # Chercher l'utilisateur
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Email ou mot de passe incorrect', 'error')
            return redirect(url_for('auth.web_login'))
        
        # Vérifier le mot de passe
        if not verify_password(password, user.password_hash):
            flash('Email ou mot de passe incorrect', 'error')
            return redirect(url_for('auth.web_login'))
        
        # Vérifier que le compte est actif
        if not user.is_active:
            flash('Ce compte a été désactivé', 'error')
            return redirect(url_for('auth.web_login'))
        
        # Mettre à jour last_login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Connecter l'utilisateur avec Flask-Login
        login_user(user, remember=remember)
        
        flash(f'Bienvenue {user.username or user.email} !', 'success')
        return redirect(url_for('index'))
    
    except Exception as e:
        flash(f'Erreur lors de la connexion: {str(e)}', 'error')
        return redirect(url_for('auth.web_login'))

# ============================================================================
# LOGOUT
# ============================================================================

@auth_bp.route('/logout')
@login_required
def web_logout():
    """Déconnexion de l'utilisateur"""
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'success')
    return redirect(url_for('index'))

# ============================================================================
# ROUTE TEST (pour vérifier que tout fonctionne)
# ============================================================================

@auth_bp.route('/test')
def test():
    """Endpoint de test"""
    return jsonify({
        'message': 'Auth routes fonctionnent !',
        'endpoints': [
            'POST /auth/api/register - API registration',
            'GET  /auth/register - Web registration form',
            'POST /auth/register - Web registration submit'
        ]
    })