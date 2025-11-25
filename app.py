from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_file
import yt_dlp
import requests
import os
import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configuración
DOWNLOAD_FOLDER = 'downloads'
DATABASE = 'mediadownloader.db'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ==================== BASE DE DATOS ====================
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Tabla de usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        arobase TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Tabla de playlists
    c.execute('''CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        visibility TEXT DEFAULT 'private',
        access_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Tabla de medios en playlists
    c.execute('''CREATE TABLE IF NOT EXISTS playlist_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        media_type TEXT NOT NULL,
        thumbnail TEXT,
        duration TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (playlist_id) REFERENCES playlists(id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== DECORADORES ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Debes iniciar sesión', 'redirect': True}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MediaDownloaderPRO v2.0</title>
    <script src="https://www.google.com/recaptcha/api.js" async defer></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            padding: 40px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            margin-bottom: 40px;
            box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);
        }
        
        .header h1 {
            font-size: 3em;
            font-weight: 900;
            background: linear-gradient(45deg, #fff, #00f2ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px rgba(0, 242, 255, 0.5);
        }
        
        .user-info {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 15px 25px;
            border-radius: 15px;
            display: none;
        }
        
        .user-info.active {
            display: block;
        }
        
        .logout-btn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            color: #fff;
            cursor: pointer;
            margin-left: 15px;
            font-weight: 600;
        }
        
        /* AUTH STYLES */
        .auth-container {
            max-width: 450px;
            margin: 50px auto;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .auth-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        
        .auth-tab {
            flex: 1;
            padding: 15px;
            background: rgba(102, 126, 234, 0.2);
            border: none;
            border-radius: 10px;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .auth-tab.active {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }
        
        .auth-form {
            display: none;
        }
        
        .auth-form.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #00f2ff;
            font-weight: 600;
        }
        
        .form-input {
            width: 100%;
            padding: 15px 20px;
            border: 2px solid rgba(102, 126, 234, 0.5);
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            border-radius: 12px;
            font-size: 16px;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 20px rgba(102, 126, 234, 0.5);
        }
        
        .submit-btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .submit-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        }
        
        /* MAIN APP STYLES */
        .main-content {
            display: none;
        }
        
        .main-content.active {
            display: block;
        }
        
        .nav-menu {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
        }
        
        .nav-btn {
            padding: 15px 30px;
            background: rgba(102, 126, 234, 0.2);
            border: 2px solid #667eea;
            border-radius: 12px;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .nav-btn:hover, .nav-btn.active {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }
        
        .section {
            display: none;
        }
        
        .section.active {
            display: block;
        }
        
        .platform-selector {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .platform-btn {
            padding: 15px 25px;
            border: 2px solid #667eea;
            background: rgba(102, 126, 234, 0.1);
            color: #fff;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 16px;
            font-weight: 600;
        }
        
        .platform-btn:hover {
            background: linear-gradient(135deg, #667eea, #764ba2);
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .platform-btn.active {
            background: linear-gradient(135deg, #667eea, #764ba2);
            box-shadow: 0 0 30px rgba(102, 126, 234, 0.6);
        }
        
        .input-section {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .input-group {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            position: relative;
        }
        
        .url-input {
            flex: 1;
            padding: 15px 100px 15px 20px;
            border: 2px solid rgba(102, 126, 234, 0.5);
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            border-radius: 12px;
            font-size: 16px;
        }
        
        .url-input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 20px rgba(102, 126, 234, 0.5);
        }
        
        .input-actions {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            gap: 10px;
        }
        
        .icon-btn {
            padding: 10px 15px;
            background: rgba(0, 242, 255, 0.2);
            border: 2px solid #00f2ff;
            border-radius: 8px;
            color: #00f2ff;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .icon-btn:hover {
            background: #00f2ff;
            color: #0f0c29;
        }
        
        .format-selector {
            display: flex;
            gap: 10px;
            justify-content: center;
        }
        
        .format-btn {
            padding: 12px 30px;
            border: 2px solid #00f2ff;
            background: rgba(0, 242, 255, 0.1);
            color: #00f2ff;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        
        .format-btn.active {
            background: #00f2ff;
            color: #0f0c29;
        }
        
        .download-btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 20px;
            transition: all 0.3s;
        }
        
        .download-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(245, 87, 108, 0.4);
        }
        
        .add-to-playlist-btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #00f2ff 0%, #667eea 100%);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.3s;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .preview-section {
            display: none;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 20px;
            margin-top: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .preview-card {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 15px;
            border: 2px solid rgba(102, 126, 234, 0.3);
        }
        
        .preview-card h3 {
            color: #00f2ff;
            margin-bottom: 15px;
        }
        
        .preview-card img {
            width: 100%;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .preview-card video {
            width: 100%;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .download-link {
            display: inline-block;
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            margin-top: 10px;
            transition: all 0.3s;
        }
        
        .download-link:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .info-text {
            color: #aaa;
            font-size: 14px;
            margin: 5px 0;
        }
        
        /* PLAYLIST STYLES */
        .playlist-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        
        .create-playlist-btn {
            padding: 15px 30px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-weight: 700;
            cursor: pointer;
        }
        
        .playlists-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .playlist-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            padding: 25px;
            border-radius: 15px;
            border: 2px solid rgba(102, 126, 234, 0.3);
            transition: all 0.3s;
        }
        
        .playlist-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.4);
        }
        
        .playlist-title {
            font-size: 1.5em;
            color: #00f2ff;
            margin-bottom: 10px;
        }
        
        .playlist-meta {
            color: #aaa;
            font-size: 14px;
            margin-bottom: 15px;
        }
        
        .visibility-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 10px;
        }
        
        .visibility-public {
            background: rgba(0, 255, 0, 0.2);
            color: #0f0;
        }
        
        .visibility-private {
            background: rgba(255, 0, 0, 0.2);
            color: #f55;
        }
        
        .visibility-code {
            background: rgba(255, 165, 0, 0.2);
            color: #fa0;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: linear-gradient(135deg, #0f0c29, #302b63);
            padding: 40px;
            border-radius: 20px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .close-modal {
            background: rgba(255, 0, 0, 0.3);
            border: none;
            color: #fff;
            font-size: 24px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
        }
        
        .error-msg {
            background: rgba(255, 0, 0, 0.2);
            border: 1px solid #f55;
            color: #f55;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        
        .success-msg {
            background: rgba(0, 255, 0, 0.2);
            border: 1px solid #0f0;
            color: #0f0;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="user-info" id="userInfo">
            <span id="userDisplay"></span>
            <button class="logout-btn" onclick="logout()">Cerrar Sesión</button>
        </div>
        
        <!-- AUTH SECTION -->
        <div id="authSection">
            <div class="header">
                <h1>MediaDownloaderPRO v2.0</h1>
                <p>Sistema avanzado de gestión multimedia</p>
            </div>
            
            <div class="auth-container">
                <div class="auth-tabs">
                    <button class="auth-tab active" onclick="switchAuthTab('login')">Iniciar Sesión</button>
                    <button class="auth-tab" onclick="switchAuthTab('register')">Registrarse</button>
                </div>
                
                <div id="errorMsg" class="error-msg"></div>
                <div id="successMsg" class="success-msg"></div>
                
                <!-- LOGIN FORM -->
                <form class="auth-form active" id="loginForm" onsubmit="return handleLogin(event)">
                    <div class="form-group">
                        <label>Usuario (@usuario)</label>
                        <input type="text" class="form-input" name="username" required placeholder="@tu_usuario">
                    </div>
                    <div class="form-group">
                        <label>Contraseña</label>
                        <input type="password" class="form-input" name="password" required>
                    </div>
                    <button type="submit" class="submit-btn">Iniciar Sesión</button>
                </form>
                
                <!-- REGISTER FORM -->
                <form class="auth-form" id="registerForm" onsubmit="return handleRegister(event)">
                    <div class="form-group">
                        <label>Nombre de Usuario</label>
                        <input type="text" class="form-input" name="username" required placeholder="tu_nombre">
                    </div>
                    <div class="form-group">
                        <label>Nombre de Arroba (@usuario)</label>
                        <input type="text" class="form-input" name="arobase" required placeholder="@nombre_unico">
                    </div>
                    <div class="form-group">
                        <label>Contraseña</label>
                        <input type="password" class="form-input" name="password" required minlength="8">
                    </div>
                    <div class="form-group">
                        <label>Verificar Contraseña</label>
                        <input type="password" class="form-input" name="confirm_password" required minlength="8">
                    </div>
                    <button type="submit" class="submit-btn">Crear Cuenta</button>
                </form>
            </div>
        </div>
        
        <!-- MAIN APP SECTION -->
        <div class="main-content" id="mainContent">
            <div class="header">
                <h1>MediaDownloaderPRO v2.0</h1>
                <p>Descarga y gestiona tu contenido multimedia</p>
            </div>
            
            <div class="nav-menu">
                <button class="nav-btn active" onclick="switchSection('downloader')">📥 Descargar</button>
                <button class="nav-btn" onclick="switchSection('playlists')">🎵 Indiana Playlist</button>
                <button class="nav-btn" onclick="showAccessByCode()">🔑 Acceder con Código</button>
            </div>
            
            <!-- DOWNLOADER SECTION -->
            <div class="section active" id="downloaderSection">
                <div class="platform-selector">
                    <button class="platform-btn active" data-platform="youtube">YouTube</button>
                    <button class="platform-btn" data-platform="instagram">Instagram</button>
                    <button class="platform-btn" data-platform="facebook">Facebook</button>
                    <button class="platform-btn" data-platform="tiktok">TikTok</button>
                </div>
                
                <div class="input-section">
                    <div class="input-group">
                        <input type="text" class="url-input" id="urlInput" placeholder="Pega la URL aquí...">
                        <div class="input-actions">
                            <button class="icon-btn" onclick="pasteUrl()" title="Pegar">📋</button>
                            <button class="icon-btn" onclick="clearUrl()" title="Borrar">🗑️</button>
                        </div>
                    </div>
                    
                    <div class="format-selector">
                        <button class="format-btn active" data-format="mp4">MP4</button>
                        <button class="format-btn" data-format="mp3">MP3</button>
                        <button class="format-btn" data-format="photo" id="photoBtn" style="display:none;">Fotos</button>
                    </div>
                    
                    <button class="download-btn" onclick="processMedia()">Procesar Media</button>
                    <button class="add-to-playlist-btn" onclick="showAddToPlaylist()">Añadir a Playlist</button>
                </div>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p style="margin-top: 15px;">Procesando...</p>
                </div>
                
                <div class="preview-section" id="previewSection">
                    <h2>Vista Previa</h2>
                    <div class="preview-grid" id="previewGrid"></div>
                </div>
            </div>
            
            <!-- PLAYLISTS SECTION -->
            <div class="section" id="playlistsSection">
                <div class="playlist-header">
                    <h2>🎵 Indiana Playlist - Almacenamiento Ilimitado</h2>
                    <button class="create-playlist-btn" onclick="showCreatePlaylist()">+ Nueva Playlist</button>
                </div>
                
                <div class="playlists-grid" id="playlistsGrid">
                    <!-- Playlists will be loaded here -->
                </div>
            </div>
        </div>
        
        <!-- CREATE PLAYLIST MODAL -->
        <div class="modal" id="createPlaylistModal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Crear Nueva Playlist</h2>
                    <button class="close-modal" onclick="closeModal('createPlaylistModal')">×</button>
                </div>
                <div id="playlistErrorMsg" class="error-msg"></div>
                <form onsubmit="return createPlaylist(event)">
                    <div class="form-group">
                        <label>Nombre de la Playlist *</label>
                        <input type="text" class="form-input" name="name" required placeholder="Mi Playlist">
                    </div>
                    <div class="form-group">
                        <label>Descripción (opcional)</label>
                        <input type="text" class="form-input" name="description" placeholder="Describe tu playlist...">
                    </div>
                    <div class="form-group">
                        <label>Visibilidad</label>
                        <select class="form-input" name="visibility" onchange="toggleCodeField(this)">
                            <option value="private">🔒 Privada - Solo yo</option>
                            <option value="public">🌍 Pública - Todos</option>
                            <option value="code">🔑 Con Código - Acceso restringido</option>
                        </select>
                    </div>
                    <div class="form-group" id="codeField" style="display:none;">
                        <label>Código de Acceso</label>
                        <input type="text" class="form-input" id="generatedCode" readonly style="background: rgba(0,242,255,0.1); border-color: #00f2ff; font-weight: 700; letter-spacing: 2px;">
                        <p style="font-size: 12px; color: #aaa; margin-top: 5px;">Este código se generará automáticamente</p>
                    </div>
                    <button type="submit" class="submit-btn">✨ Crear Playlist</button>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        let selectedPlatform = 'youtube';
        let selectedFormat = 'mp4';
        let currentMedia = null;
        
        // Auth functions
        function switchAuthTab(tab) {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tab + 'Form').classList.add('active');
        }
        
        async function handleLogin(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(Object.fromEntries(formData))
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('¡Inicio de sesión exitoso!');
                    setTimeout(() => {
                        document.getElementById('authSection').style.display = 'none';
                        document.getElementById('mainContent').classList.add('active');
                        document.getElementById('userInfo').classList.add('active');
                        document.getElementById('userDisplay').textContent = data.arobase;
                        loadPlaylists();
                    }, 1000);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error de conexión');
            }
        }
        
        async function handleRegister(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            
            if (data.password !== data.confirm_password) {
                showError('Las contraseñas no coinciden');
                return false;
            }
            
            if (!data.arobase.startsWith('@')) {
                showError('El nombre de arroba debe comenzar con @');
                return false;
            }
            
            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showSuccess('¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.');
                    setTimeout(() => {
                        switchAuthTab('login');
                    }, 2000);
                } else {
                    showError(result.error);
                }
            } catch (error) {
                showError('Error de conexión');
            }
            
            return false;
        }
        
        async function logout() {
            try {
                await fetch('/logout', { method: 'POST' });
                location.reload();
            } catch (error) {
                console.error('Error al cerrar sesión');
            }
        }
        
        function showError(msg) {
            const errorDiv = document.getElementById('errorMsg');
            if (errorDiv) {
                errorDiv.textContent = msg;
                errorDiv.style.display = 'block';
                setTimeout(() => errorDiv.style.display = 'none', 5000);
            }
            console.error('Error:', msg);
        }
        
        function showSuccess(msg) {
            const successDiv = document.getElementById('successMsg');
            if (successDiv) {
                successDiv.textContent = msg;
                successDiv.style.display = 'block';
                setTimeout(() => successDiv.style.display = 'none', 3000);
            }
            console.log('Success:', msg);
        }
        
        // Section switching
        function switchSection(section) {
            document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(section + 'Section').classList.add('active');
            
            if (section === 'playlists') {
                loadPlaylists();
            }
        }
        
        // Platform selection
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.platform-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                selectedPlatform = this.dataset.platform;
                
                document.getElementById('photoBtn').style.display = 
                    selectedPlatform === 'tiktok' ? 'inline-block' : 'none';
            });
        });
        
        // Format selection
        document.querySelectorAll('.format-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                selectedFormat = this.dataset.format;
            });
        });
        
        // URL functions
        async function pasteUrl() {
            try {
                const text = await navigator.clipboard.readText();
                document.getElementById('urlInput').value = text;
            } catch (error) {
                showError('No se pudo pegar desde el portapapeles');
            }
        }
        
        function clearUrl() {
            document.getElementById('urlInput').value = '';
            document.getElementById('previewSection').style.display = 'none';
            currentMedia = null;
        }
        
        async function processMedia() {
            const url = document.getElementById('urlInput').value;
            if (!url) {
                showError('Por favor ingresa una URL');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('previewSection').style.display = 'none';
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: url,
                        platform: selectedPlatform,
                        format: selectedFormat
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    currentMedia = data;
                    displayPreview(data);
                } else {
                    showError('Error: ' + data.error);
                }
            } catch (error) {
                showError('Error de conexión: ' + error);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function displayPreview(data) {
            const previewSection = document.getElementById('previewSection');
            const previewGrid = document.getElementById('previewGrid');
            previewGrid.innerHTML = '';
            
            if (data.platform === 'tiktok') {
                // Info card para TikTok
                previewGrid.innerHTML += `
                    <div class="preview-card">
                        <h3>📊 Información</h3>
                        <p class="info-text">👤 ${data.uploader || 'Desconocido'}</p>
                        <p class="info-text">👁️ ${formatNumber(data.view_count || 0)} vistas</p>
                        <p class="info-text">❤️ ${formatNumber(data.like_count || 0)} likes</p>
                        <p class="info-text">💬 ${formatNumber(data.comment_count || 0)} comentarios</p>
                        <p class="info-text">↗️ ${formatNumber(data.share_count || 0)} compartidos</p>
                    </div>
                `;
                
                if (data.video) {
                    previewGrid.innerHTML += `
                        <div class="preview-card">
                            <h3>🎥 Video</h3>
                            ${data.thumbnail ? `<img src="${data.thumbnail}" alt="Thumbnail">` : ''}
                            <p class="info-text"><strong>${data.title || 'Sin título'}</strong></p>
                            <p class="info-text">⏱️ Duración: ${data.duration || 'N/A'}</p>
                            <p class="info-text">📺 Calidad: ${data.quality || 'N/A'}</p>
                            <a href="${data.video}" class="download-link" download="${sanitizeFilename(data.title)}.mp4">Descargar Video</a>
                        </div>
                    `;
                }
                
                if (data.audio) {
                    previewGrid.innerHTML += `
                        <div class="preview-card">
                            <h3>🎵 Audio</h3>
                            <audio controls src="${data.audio}" style="width:100%;"></audio>
                            <a href="${data.audio}" class="download-link" download="${sanitizeFilename(data.title)}.mp3">Descargar Audio</a>
                        </div>
                    `;
                }
                
                if (data.images && data.images.length > 0) {
                    data.images.forEach((img, idx) => {
                        previewGrid.innerHTML += `
                            <div class="preview-card">
                                <h3>📷 Foto ${idx + 1}</h3>
                                <img src="${img}" alt="Image ${idx + 1}">
                                <a href="${img}" class="download-link" download="${sanitizeFilename(data.title)}_${idx + 1}.jpg">Descargar</a>
                            </div>
                        `;
                    });
                }
            } else {
                // Info card para YouTube y otras plataformas
                previewGrid.innerHTML += `
                    <div class="preview-card">
                        <h3>📊 Información del Video</h3>
                        ${data.thumbnail ? `<img src="${data.thumbnail}" alt="Thumbnail">` : ''}
                        <p class="info-text"><strong>${data.title || 'Sin título'}</strong></p>
                        <p class="info-text">👤 ${data.uploader || 'Desconocido'}</p>
                        <p class="info-text">👁️ ${formatNumber(data.view_count || 0)} vistas</p>
                        <p class="info-text">❤️ ${formatNumber(data.like_count || 0)} likes</p>
                        <p class="info-text">⏱️ Duración: ${data.duration || 'N/A'}</p>
                        <p class="info-text">📅 Subido: ${formatDate(data.upload_date)}</p>
                    </div>
                `;
                
                previewGrid.innerHTML += `
                    <div class="preview-card">
                        <h3>📥 Descargar</h3>
                        <p class="info-text">Formato: ${data.format || 'N/A'}</p>
                        <p class="info-text">Calidad: ${data.quality || 'N/A'}</p>
                        <a href="${data.download_url}" class="download-link" download="${sanitizeFilename(data.title)}.${data.format.toLowerCase()}">
                            Descargar ${data.format}
                        </a>
                    </div>
                `;
                
                if (data.description) {
                    previewGrid.innerHTML += `
                        <div class="preview-card" style="grid-column: 1 / -1;">
                            <h3>📝 Descripción</h3>
                            <p class="info-text">${data.description}</p>
                        </div>
                    `;
                }
            }
            
            previewSection.style.display = 'block';
        }
        
        function formatNumber(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(1) + 'K';
            }
            return num.toString();
        }
        
        function formatDate(dateStr) {
            if (!dateStr || dateStr === 'N/A') return 'N/A';
            try {
                const year = dateStr.substring(0, 4);
                const month = dateStr.substring(4, 6);
                const day = dateStr.substring(6, 8);
                return `${day}/${month}/${year}`;
            } catch {
                return dateStr;
            }
        }
        
        function sanitizeFilename(filename) {
            return filename.replace(/[^a-z0-9]/gi, '_').substring(0, 50);
        }
        
        // Playlist functions
        async function loadPlaylists() {
            try {
                const response = await fetch('/playlists');
                
                if (response.status === 401) {
                    showError('Sesión expirada. Por favor inicia sesión nuevamente.');
                    setTimeout(() => location.reload(), 2000);
                    return;
                }
                
                const data = await response.json();
                console.log('Playlists cargadas:', data);
                
                if (data.success) {
                    displayPlaylists(data.playlists);
                } else {
                    console.error('Error al cargar playlists:', data.error);
                    if (data.redirect) {
                        showError('Sesión expirada. Recargando...');
                        setTimeout(() => location.reload(), 2000);
                    } else {
                        showError(data.error || 'Error al cargar playlists');
                    }
                }
            } catch (error) {
                console.error('Error de conexión:', error);
                showError('Error al cargar playlists: ' + error.message);
            }
        }
        
        function displayPlaylists(playlists) {
            const grid = document.getElementById('playlistsGrid');
            
            console.log('Mostrando', playlists.length, 'playlists');
            
            if (!playlists || playlists.length === 0) {
                grid.innerHTML = `
                    <div style="grid-column: 1/-1; text-align: center; padding: 40px;">
                        <p style="color:#aaa; font-size: 18px; margin-bottom: 20px;">
                            📂 No tienes playlists aún
                        </p>
                        <p style="color:#666; margin-bottom: 30px;">
                            ¡Crea tu primera playlist y comienza a organizar tu música y videos!
                        </p>
                        <button class="create-playlist-btn" onclick="showCreatePlaylist()">
                            ✨ Crear Mi Primera Playlist
                        </button>
                    </div>
                `;
                return;
            }
            
            grid.innerHTML = playlists.map(playlist => `
                <div class="playlist-card">
                    <h3 class="playlist-title">${playlist.name}</h3>
                    <p class="info-text">${playlist.description || 'Sin descripción'}</p>
                    <p class="playlist-meta">📁 ${playlist.item_count || 0} elementos</p>
                    <p class="playlist-meta">📅 Creada: ${new Date(playlist.created_at).toLocaleDateString()}</p>
                    <span class="visibility-badge visibility-${playlist.visibility}">
                        ${playlist.visibility === 'public' ? '🌍 Pública' : 
                          playlist.visibility === 'private' ? '🔒 Privada' : 
                          '🔑 Código: ' + (playlist.access_code || 'N/A')}
                    </span>
                    <div style="margin-top: 15px;">
                        <button class="download-link" onclick="viewPlaylist(${playlist.id})">👁️ Ver Contenido</button>
                    </div>
                </div>
            `).join('');
        }
        
        function showCreatePlaylist() {
            document.getElementById('createPlaylistModal').classList.add('active');
        }
        
        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }
        
        function toggleCodeField(select) {
            const codeField = document.getElementById('codeField');
            const codeInput = document.getElementById('generatedCode');
            
            if (select.value === 'code') {
                codeField.style.display = 'block';
                codeInput.value = generateAccessCode();
            } else {
                codeField.style.display = 'none';
            }
        }
        
        function generateAccessCode() {
            return Math.random().toString(36).substring(2, 10).toUpperCase();
        }
        
        async function createPlaylist(e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            
            console.log('Datos del formulario:', data);
            
            if (data.visibility === 'code') {
                data.access_code = document.getElementById('generatedCode').value;
            } else {
                data.access_code = null;
            }
            
            console.log('Enviando datos:', data);
            
            try {
                const response = await fetch('/create_playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                console.log('Respuesta del servidor:', result);
                
                if (result.success) {
                    showSuccess('¡Playlist creada exitosamente!');
                    closeModal('createPlaylistModal');
                    setTimeout(() => {
                        loadPlaylists();
                    }, 500);
                    e.target.reset();
                    document.getElementById('codeField').style.display = 'none';
                } else {
                    showError(result.error || 'Error al crear playlist');
                }
            } catch (error) {
                console.error('Error:', error);
                showError('Error de conexión: ' + error.message);
            }
            
            return false;
        }
        
        async function showAddToPlaylist() {
            if (!currentMedia) {
                showError('Primero procesa un medio');
                return;
            }
            
            try {
                const response = await fetch('/playlists');
                const data = await response.json();
                
                if (data.success && data.playlists.length > 0) {
                    const playlistSelect = data.playlists.map(p => 
                        `<option value="${p.id}">${p.name}</option>`
                    ).join('');
                    
                    const modalHTML = `
                        <div class="modal active" id="addToPlaylistModal">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h2>Añadir a Playlist</h2>
                                    <button class="close-modal" onclick="closeAddToPlaylist()">×</button>
                                </div>
                                <div class="form-group">
                                    <label>Selecciona una Playlist</label>
                                    <select class="form-input" id="selectPlaylist">
                                        ${playlistSelect}
                                    </select>
                                </div>
                                <button class="submit-btn" onclick="addMediaToPlaylist()">Añadir</button>
                            </div>
                        </div>
                    `;
                    
                    document.body.insertAdjacentHTML('beforeend', modalHTML);
                } else {
                    showError('Primero crea una playlist');
                }
            } catch (error) {
                showError('Error al cargar playlists');
            }
        }
        
        function closeAddToPlaylist() {
            const modal = document.getElementById('addToPlaylistModal');
            if (modal) modal.remove();
        }
        
        async function addMediaToPlaylist() {
            const playlistId = document.getElementById('selectPlaylist').value;
            
            try {
                const response = await fetch('/add_to_playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        playlist_id: playlistId,
                        media: currentMedia
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('¡Media añadido a la playlist!');
                    closeAddToPlaylist();
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al añadir a playlist');
            }
        }
        
        function viewPlaylist(playlistId) {
            loadPlaylistContent(playlistId);
        }
        
        async function loadPlaylistContent(playlistId) {
            try {
                const response = await fetch(`/playlist/${playlistId}`);
                const data = await response.json();
                
                if (data.success) {
                    showPlaylistModal(data.playlist, data.items);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al cargar contenido');
            }
        }
        
        function showPlaylistModal(playlist, items) {
            const itemsHTML = items.length > 0 ? items.map((item, idx) => {
                const isAudio = item.media_type === 'mp3' || item.media_type === 'audio';
                const isVideo = item.media_type === 'mp4' || item.media_type === 'video';
                const isImage = item.media_type === 'jpg' || item.media_type === 'png' || item.media_type === 'image';
                
                let mediaPreview = '';
                if (isImage || item.thumbnail) {
                    mediaPreview = `<img src="${item.thumbnail || item.url}" alt="${item.title}">`;
                } else if (isAudio) {
                    mediaPreview = `
                        <div style="background: rgba(0,242,255,0.1); padding: 30px; border-radius: 10px; text-align: center;">
                            <p style="font-size: 48px; margin: 0;">🎵</p>
                            <audio controls src="${item.url}" style="width:100%; margin-top: 10px;"></audio>
                        </div>
                    `;
                } else if (isVideo) {
                    mediaPreview = `<video controls src="${item.url}" style="width:100%; border-radius: 10px;"></video>`;
                }
                
                return `
                    <div class="preview-card" id="item-${item.id}">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <h3 contenteditable="true" 
                                id="title-${item.id}" 
                                onblur="renameItem(${item.id}, this.textContent)"
                                style="flex: 1; cursor: text; border: 2px dashed transparent; padding: 5px; border-radius: 5px;"
                                onfocus="this.style.borderColor='#00f2ff'"
                                onblur="this.style.borderColor='transparent'">
                                ${idx + 1}. ${item.title}
                            </h3>
                            <span style="font-size: 12px; color: #aaa; margin-left: 10px;">✏️</span>
                        </div>
                        ${mediaPreview}
                        <p class="info-text">📁 Tipo: ${item.media_type.toUpperCase()}</p>
                        <p class="info-text">⏱️ Duración: ${item.duration || 'N/A'}</p>
                        <p class="info-text">📅 Añadido: ${new Date(item.added_at).toLocaleDateString()}</p>
                        <div style="display: flex; gap: 10px; margin-top: 10px;">
                            <a href="${item.url}" class="download-link" download="${item.title}.${item.media_type}" target="_blank" style="flex: 1; text-align: center;">
                                📥 Descargar
                            </a>
                            <button class="icon-btn" onclick="removeFromPlaylist(${playlist.id}, ${item.id})" style="background: rgba(255,0,0,0.2); border-color: #f55; color: #f55;">
                                🗑️
                            </button>
                        </div>
                    </div>
                `;
            }).join('') : '<p style="text-align:center;color:#aaa;">Esta playlist está vacía</p>';
            
            const shareHTML = playlist.visibility === 'code' ? `
                <div style="background: rgba(255,165,0,0.2); padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <p style="color: #fa0; font-weight: 600;">🔑 Código de Acceso:</p>
                    <p style="font-size: 24px; font-weight: 700; letter-spacing: 3px;">${playlist.access_code}</p>
                    <button class="icon-btn" onclick="copyCode('${playlist.access_code}')">📋 Copiar</button>
                </div>
            ` : playlist.visibility === 'public' ? `
                <div style="background: rgba(0,255,0,0.2); padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <p style="color: #0f0; font-weight: 600;">🌍 Esta playlist es pública</p>
                    <p style="font-size: 14px; color: #aaa;">Cualquiera puede verla</p>
                </div>
            ` : `
                <div style="background: rgba(255,0,0,0.2); padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <p style="color: #f55; font-weight: 600;">🔒 Esta playlist es privada</p>
                    <p style="font-size: 14px; color: #aaa;">Solo tú puedes verla</p>
                </div>
            `;
            
            const modalHTML = `
                <div class="modal active" id="playlistContentModal">
                    <div class="modal-content" style="max-width: 900px;">
                        <div class="modal-header">
                            <div>
                                <h2>${playlist.name}</h2>
                                <p style="color: #aaa;">${playlist.description || 'Sin descripción'}</p>
                            </div>
                            <button class="close-modal" onclick="closePlaylistModal()">×</button>
                        </div>
                        ${shareHTML}
                        
                        <!-- Botón para subir archivos -->
                        <div style="margin-bottom: 20px;">
                            <input type="file" id="fileUpload-${playlist.id}" accept="audio/*,video/*,image/*" style="display:none;" onchange="uploadFile(${playlist.id})">
                            <button class="submit-btn" onclick="document.getElementById('fileUpload-${playlist.id}').click()">
                                📤 Subir Archivo desde Mi Dispositivo
                            </button>
                        </div>
                        
                        <div class="preview-grid" style="max-height: 400px; overflow-y: auto;">
                            ${itemsHTML}
                        </div>
                        <div style="margin-top: 20px;">
                            <button class="submit-btn" onclick="downloadAllPlaylist(${playlist.id})">📥 Descargar Todas</button>
                            <button class="logout-btn" style="width:100%; margin-top:10px;" onclick="deletePlaylist(${playlist.id})">🗑️ Eliminar Playlist</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }
        
        async function renameItem(itemId, newTitle) {
            if (!newTitle || newTitle.trim() === '') {
                showError('El título no puede estar vacío');
                return;
            }
            
            try {
                const response = await fetch('/rename_item', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        item_id: itemId, 
                        new_title: newTitle.trim() 
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('✏️ Título actualizado');
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al renombrar');
            }
        }
        
        async function uploadFile(playlistId) {
            const fileInput = document.getElementById(`fileUpload-${playlistId}`);
            const file = fileInput.files[0];
            
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('playlist_id', playlistId);
            
            try {
                showSuccess('📤 Subiendo archivo...');
                
                const response = await fetch('/upload_to_playlist', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('✅ Archivo subido exitosamente');
                    closePlaylistModal();
                    setTimeout(() => loadPlaylistContent(playlistId), 500);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al subir archivo');
            }
        }
        
        function closePlaylistModal() {
            const modal = document.getElementById('playlistContentModal');
            if (modal) modal.remove();
        }
        
        function copyCode(code) {
            navigator.clipboard.writeText(code);
            showSuccess('¡Código copiado al portapapeles!');
        }
        
        async function removeFromPlaylist(playlistId, itemId) {
            if (!confirm('¿Eliminar este elemento?')) return;
            
            try {
                const response = await fetch('/remove_from_playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ item_id: itemId })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('Elemento eliminado');
                    closePlaylistModal();
                    loadPlaylistContent(playlistId);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al eliminar');
            }
        }
        
        async function deletePlaylist(playlistId) {
            if (!confirm('¿Eliminar esta playlist completa?')) return;
            
            try {
                const response = await fetch('/delete_playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ playlist_id: playlistId })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess('Playlist eliminada');
                    closePlaylistModal();
                    loadPlaylists();
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al eliminar playlist');
            }
        }
        
        function downloadAllPlaylist(playlistId) {
            showSuccess('Iniciando descarga de todos los archivos...');
            fetch(`/playlist/${playlistId}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        data.items.forEach((item, idx) => {
                            setTimeout(() => {
                                const a = document.createElement('a');
                                a.href = item.url;
                                a.download = `${item.title}.${item.media_type}`;
                                a.click();
                            }, idx * 1000);
                        });
                    }
                });
        }
        
        function showAccessByCode() {
            const modalHTML = `
                <div class="modal active" id="accessCodeModal">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h2>🔑 Acceder con Código</h2>
                            <button class="close-modal" onclick="closeAccessCodeModal()">×</button>
                        </div>
                        <div class="form-group">
                            <label>Introduce el Código de Acceso</label>
                            <input type="text" class="form-input" id="accessCodeInput" placeholder="XXXXXXXX" style="text-transform: uppercase;">
                        </div>
                        <button class="submit-btn" onclick="accessPlaylistByCode()">Acceder</button>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }
        
        function closeAccessCodeModal() {
            const modal = document.getElementById('accessCodeModal');
            if (modal) modal.remove();
        }
        
        async function accessPlaylistByCode() {
            const code = document.getElementById('accessCodeInput').value.toUpperCase();
            
            if (!code) {
                showError('Introduce un código');
                return;
            }
            
            try {
                const response = await fetch('/access_playlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ access_code: code })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    closeAccessCodeModal();
                    showPlaylistModal(data.playlist, data.items);
                } else {
                    showError(data.error);
                }
            } catch (error) {
                showError('Error al acceder');
            }
        }
        
        async function checkSession() {
            try {
                const response = await fetch('/check_session');
                const data = await response.json();
                
                console.log('Estado de sesión:', data);
                
                if (data.logged_in) {
                    document.getElementById('authSection').style.display = 'none';
                    document.getElementById('mainContent').classList.add('active');
                    document.getElementById('userInfo').classList.add('active');
                    document.getElementById('userDisplay').textContent = data.arobase;
                    return true;
                } else {
                    document.getElementById('authSection').style.display = 'block';
                    document.getElementById('mainContent').classList.remove('active');
                    return false;
                }
            } catch (error) {
                console.error('Error al verificar sesión:', error);
                return false;
            }
        }
        
        window.addEventListener('DOMContentLoaded', async () => {
            console.log('Página cargada, verificando sesión...');
            const isLoggedIn = await checkSession();
            if (isLoggedIn) {
                console.log('Usuario con sesión activa');
            } else {
                console.log('No hay sesión activa');
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    arobase = data.get('arobase')
    password = data.get('password')
    
    if not arobase.startswith('@'):
        return jsonify({'success': False, 'error': 'El nombre de arroba debe comenzar con @'})
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT id FROM users WHERE username = ? OR arobase = ?', (username, arobase))
        if c.fetchone():
            return jsonify({'success': False, 'error': 'Usuario o arroba ya existe'})
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        c.execute('INSERT INTO users (username, arobase, password) VALUES (?, ?, ?)',
                  (username, arobase, hashed_password))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username.startswith('@'):
        username = '@' + username
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT id, arobase, password FROM users WHERE arobase = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['arobase'] = user[1]
            return jsonify({'success': True, 'arobase': user[1]})
        else:
            return jsonify({'success': False, 'error': 'Credenciales incorrectas'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/check_session', methods=['GET'])
def check_session():
    if 'user_id' in session:
        return jsonify({
            'success': True, 
            'logged_in': True,
            'user_id': session['user_id'],
            'arobase': session.get('arobase', 'Unknown')
        })
    else:
        return jsonify({'success': True, 'logged_in': False})

@app.route('/process', methods=['POST'])
@login_required
def process_media():
    data = request.json
    url = data.get('url')
    platform = data.get('platform')
    format_type = data.get('format')
    
    try:
        if platform == 'tiktok':
            return process_tiktok(url, format_type)
        else:
            return process_ytdlp(url, platform, format_type)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def process_tiktok(url, format_type):
    try:
        api_url = 'https://www.tikwm.com/api/'
        response = requests.post(api_url, data={'url': url, 'hd': 1})
        result = response.json()
        
        if result.get('code') != 0:
            return jsonify({'success': False, 'error': 'Error al obtener datos de TikTok'})
        
        data = result.get('data', {})
        
        response_data = {
            'success': True,
            'platform': 'tiktok',
            'title': data.get('title', 'TikTok Video'),
            'duration': f"{data.get('duration', 0)}s",
            'duration_seconds': data.get('duration', 0),
            'quality': 'HD' if data.get('hdplay') else 'SD',
            'video': data.get('hdplay') or data.get('play'),
            'audio': data.get('music'),
            'images': data.get('images', []),
            'view_count': data.get('play_count', 0),
            'like_count': data.get('digg_count', 0),
            'comment_count': data.get('comment_count', 0),
            'share_count': data.get('share_count', 0),
            'uploader': data.get('author', {}).get('nickname', 'Desconocido'),
            'thumbnail': data.get('cover', '')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def process_ytdlp(url, platform, format_type):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        if format_type == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
            })
        else:
            ydl_opts.update({
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Información adicional
            duration_seconds = info.get('duration', 0)
            duration_formatted = f"{duration_seconds // 60}:{duration_seconds % 60:02d}"
            
            response_data = {
                'success': True,
                'platform': platform,
                'title': info.get('title', 'Sin título'),
                'thumbnail': info.get('thumbnail'),
                'duration': duration_formatted,
                'duration_seconds': duration_seconds,
                'quality': info.get('resolution', 'N/A'),
                'format': format_type.upper(),
                'download_url': info.get('url'),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'uploader': info.get('uploader', 'Desconocido'),
                'upload_date': info.get('upload_date', 'N/A'),
                'description': info.get('description', '')[:200] if info.get('description') else 'Sin descripción'
            }
            
            return jsonify(response_data)
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create_playlist', methods=['POST'])
@login_required
def create_playlist():
    data = request.json
    user_id = session['user_id']
    
    name = data.get('name')
    description = data.get('description', '')
    visibility = data.get('visibility', 'private')
    access_code = data.get('access_code')
    
    if not name:
        return jsonify({'success': False, 'error': 'El nombre es requerido'})
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('''INSERT INTO playlists (user_id, name, description, visibility, access_code)
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, name, description, visibility, access_code))
        
        conn.commit()
        playlist_id = c.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'playlist_id': playlist_id, 'message': 'Playlist creada exitosamente'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Error al crear la playlist'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error: {str(e)}'})

@app.route('/playlists', methods=['GET'])
@login_required
def get_playlists():
    user_id = session['user_id']
    
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''SELECT p.*, COUNT(pi.id) as item_count 
                     FROM playlists p 
                     LEFT JOIN playlist_items pi ON p.id = pi.playlist_id 
                     WHERE p.user_id = ? 
                     GROUP BY p.id 
                     ORDER BY p.created_at DESC''', (user_id,))
        
        playlists = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({'success': True, 'playlists': playlists})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_to_playlist', methods=['POST'])
@login_required
def add_to_playlist():
    data = request.json
    playlist_id = data.get('playlist_id')
    media = data.get('media')
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM playlists WHERE id = ?', (playlist_id,))
        playlist = c.fetchone()
        
        if not playlist or playlist[0] != session['user_id']:
            return jsonify({'success': False, 'error': 'Playlist no encontrada'})
        
        # Determinar la URL y tipo de medio correcto
        media_url = media.get('download_url') or media.get('video') or media.get('audio', '')
        media_type = media.get('format', 'mp4').lower()
        
        c.execute('''INSERT INTO playlist_items (playlist_id, title, url, media_type, thumbnail, duration)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (playlist_id, media.get('title', 'Sin título'), 
                   media_url,
                   media_type,
                   media.get('thumbnail'),
                   media.get('duration')))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload_to_playlist', methods=['POST'])
@login_required
def upload_to_playlist():
    """Subir archivo desde almacenamiento local"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se encontró archivo'})
        
        file = request.files['file']
        playlist_id = request.form.get('playlist_id')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó archivo'})
        
        # Verificar que la playlist pertenece al usuario
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM playlists WHERE id = ?', (playlist_id,))
        playlist = c.fetchone()
        
        if not playlist or playlist[0] != session['user_id']:
            return jsonify({'success': False, 'error': 'Playlist no encontrada'})
        
        # Guardar archivo
        filename = file.filename
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Determinar tipo de medio
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
        media_type = 'mp3' if ext in ['mp3', 'wav', 'ogg'] else 'mp4' if ext in ['mp4', 'avi', 'mov'] else ext
        
        # Añadir a playlist
        c.execute('''INSERT INTO playlist_items (playlist_id, title, url, media_type, thumbnail, duration)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (playlist_id, filename.rsplit('.', 1)[0], 
                   f'/downloads/{filename}',
                   media_type,
                   None,
                   'N/A'))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Archivo subido exitosamente'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/rename_item', methods=['POST'])
@login_required
def rename_item():
    """Renombrar item en playlist"""
    data = request.json
    item_id = data.get('item_id')
    new_title = data.get('new_title')
    user_id = session['user_id']
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Verificar que el item pertenece a una playlist del usuario
        c.execute('''SELECT pi.id FROM playlist_items pi 
                     JOIN playlists p ON pi.playlist_id = p.id 
                     WHERE pi.id = ? AND p.user_id = ?''', (item_id, user_id))
        
        if not c.fetchone():
            return jsonify({'success': False, 'error': 'Item no encontrado'})
        
        c.execute('UPDATE playlist_items SET title = ? WHERE id = ?', (new_title, item_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/playlist/<int:playlist_id>', methods=['GET'])
@login_required
def get_playlist_content(playlist_id):
    user_id = session['user_id']
    
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('SELECT * FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
        playlist = c.fetchone()
        
        if not playlist:
            return jsonify({'success': False, 'error': 'Playlist no encontrada'})
        
        c.execute('SELECT * FROM playlist_items WHERE playlist_id = ? ORDER BY added_at DESC', (playlist_id,))
        items = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'playlist': dict(playlist),
            'items': items
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/remove_from_playlist', methods=['POST'])
@login_required
def remove_from_playlist():
    data = request.json
    item_id = data.get('item_id')
    user_id = session['user_id']
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('''SELECT pi.id FROM playlist_items pi 
                     JOIN playlists p ON pi.playlist_id = p.id 
                     WHERE pi.id = ? AND p.user_id = ?''', (item_id, user_id))
        
        if not c.fetchone():
            return jsonify({'success': False, 'error': 'Item no encontrado'})
        
        c.execute('DELETE FROM playlist_items WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_playlist', methods=['POST'])
@login_required
def delete_playlist():
    data = request.json
    playlist_id = data.get('playlist_id')
    user_id = session['user_id']
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        c.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
        
        if not c.fetchone():
            return jsonify({'success': False, 'error': 'Playlist no encontrada'})
        
        c.execute('DELETE FROM playlist_items WHERE playlist_id = ?', (playlist_id,))
        c.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/access_playlist', methods=['POST'])
@login_required
def access_playlist():
    data = request.json
    access_code = data.get('access_code')
    
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('SELECT * FROM playlists WHERE access_code = ? AND visibility = ?', 
                  (access_code, 'code'))
        playlist = c.fetchone()
        
        if not playlist:
            return jsonify({'success': False, 'error': 'Código inválido'})
        
        c.execute('SELECT * FROM playlist_items WHERE playlist_id = ? ORDER BY added_at DESC', 
                  (playlist['id'],))
        items = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'playlist': dict(playlist),
            'items': items
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """Servir archivos subidos"""
    try:
        return send_file(os.path.join(DOWNLOAD_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
