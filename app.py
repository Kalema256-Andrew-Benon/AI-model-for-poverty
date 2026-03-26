 # ============================================================================
# UGANDA POVERTY CLASSIFICATION SYSTEM - PROFESSIONAL EDITION
# ============================================================================
# Version: 2.1 Optimized - Fast Loading & Google Drive Integration
# Users: Individuals, NGOs, Government Agencies
# Features: Authentication, Admin Dashboard, CSV Bulk Upload, History, Reports
# Models: Cached loading from Google Drive with local fallback
# Performance: <0.5s response time after initial load
# ============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os
import json
import joblib
import hashlib
import sqlite3
import requests
import io
from datetime import datetime, timedelta
from PIL import Image
import warnings
from functools import wraps
warnings.filterwarnings('ignore')

# ============================================================================
# STREAMLIT PAGE CONFIG (Must be first)
# ============================================================================
st.set_page_config(
    page_title="🇺🇬 Uganda Poverty Classification",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# 1. DATABASE SETUP
# ============================================================================

def init_database():
    """Initialize SQLite database for user management and prediction history"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL,
            profile_pic BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_verified INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model_used TEXT NOT NULL,
            predicted_class TEXT NOT NULL,
            confidence REAL NOT NULL,
            input_data TEXT NOT NULL,
            recommendations TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_default_users():
    """Create default admin and user accounts for testing"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE username IN ('admin1', 'user1')")
    count = cursor.fetchone()[0]
    
    if count == 0:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, user_type, is_verified, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('admin1', 'admin@povertyapp.ug', hash_password('1234'), 'admin', 1, 1))
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, user_type, is_verified, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('user1', 'user@povertyapp.ug', hash_password('1234'), 'user', 1, 1))
        
        conn.commit()
    
    conn.close()

def authenticate_user(username, password):
    """Authenticate user and return user data"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    
    password_hash = hash_password(password)
    cursor.execute("""
        SELECT id, username, email, user_type, profile_pic, is_verified, is_active
        FROM users WHERE username = ? AND password_hash = ?
    """, (username, password_hash))
    
    user = cursor.fetchone()
    conn.close()
    
    if user and user[5] == 1 and user[6] == 1:
        return {
            'id': user[0], 'username': user[1], 'email': user[2],
            'user_type': user[3], 'profile_pic': user[4],
            'is_verified': user[5], 'is_active': user[6]
        }
    return None

def register_user(username, email, password, user_type='user', profile_pic=None):
    """Register new user"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, user_type, profile_pic, is_verified, is_active)
            VALUES (?, ?, ?, ?, ?, 0, 1)
        """, (username, email, password_hash, user_type, profile_pic))
        conn.commit()
        return True, "Registration successful! Please wait for admin verification."
    except sqlite3.IntegrityError:
        return False, "Username or email already exists."
    finally:
        conn.close()

def save_prediction(user_id, model_used, predicted_class, confidence, input_data, recommendations):
    """Save prediction to history"""
    try:
        conn = sqlite3.connect('poverty_app.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions (user_id, model_used, predicted_class, confidence, input_data, recommendations)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, model_used, predicted_class, confidence, json.dumps(input_data), json.dumps(recommendations)))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def get_user_predictions(user_id, limit=50):
    """Get user's prediction history"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, model_used, predicted_class, confidence, input_data, recommendations, created_at
        FROM predictions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    predictions = cursor.fetchall()
    conn.close()
    return [{
        'id': p[0], 'model_used': p[1], 'predicted_class': p[2], 'confidence': p[3],
        'input_data': json.loads(p[4]), 'recommendations': json.loads(p[5]), 'created_at': p[6]
    } for p in predictions]

def get_all_users():
    """Get all users (Admin only)"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, user_type, created_at, last_login, is_verified, is_active
        FROM users ORDER BY created_at DESC
    """)
    users = cursor.fetchall()
    conn.close()
    return [{
        'id': u[0], 'username': u[1], 'email': u[2], 'user_type': u[3],
        'created_at': u[4], 'last_login': u[5], 'is_verified': u[6], 'is_active': u[7]
    } for u in users]

def get_app_statistics():
    """Get app-wide statistics (Admin only)"""
    conn = sqlite3.connect('poverty_app.db')
    cursor = conn.cursor()
    stats = {}
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['total_users'] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM predictions")
    stats['total_predictions'] = cursor.fetchone()[0]
    cursor.execute("SELECT predicted_class, COUNT(*) FROM predictions GROUP BY predicted_class")
    stats['predictions_by_class'] = dict(cursor.fetchall())
    conn.close()
    return stats

# ============================================================================
# 2. LOAD CONFIGURATION & MODELS (OPTIMIZED WITH CACHING)
# ============================================================================

@st.cache_data(ttl=3600)
def load_app_configuration():
    """Load app configuration from local or fallback defaults"""
    config_paths = [
        'outputs/models/phase12_app_configuration.json',
        'models/phase12_app_configuration.json',
        'phase12_app_configuration.json'
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except:
                continue
    
    # Default configuration
    return {
        'app_configuration': {
            'default_model': 'Random Forest',
            'available_models': ['Random Forest', 'XGBoost', 'LightGBM', 'Logistic Regression', 'Soft Voting', 'Hard Voting', 'Stacking'],
            'model_directory': 'models/optimized',
            'scaler_file': 'scaler_phase8.pkl',
            'feature_file': 'feature_columns.json',
            'class_mapping_file': 'class_mapping.json'
        },
        'features': {
            'n_features': 8,
            'feature_names': ['region', 'regurb', 'subreg', 'district', 'urban', 'equiv', 'hsize', 'nrrexp30'],
            'feature_app_names': {
                'region': 'Region', 'regurb': 'Region-Urban Type', 'subreg': 'Sub-Region',
                'district': 'District', 'urban': 'Urban/Rural', 'equiv': 'Monthly Income/Expenditure (UGX)',
                'hsize': 'Household Size', 'nrrexp30': 'Non-Food Expenses (UGX)'
            }
        },
        'class_info': {
            'n_classes': 3,
            'class_labels': ['poor', 'middle class', 'rich'],
            'class_mapping': {0: 'poor', 1: 'middle class', 2: 'rich'}
        },
        'confidence_settings': {
            'display_confidence': True, 'confidence_threshold': 0.7,
            'show_uncertainty_warning': True, 'uncertainty_threshold': 0.3
        }
    }

# Google Drive direct download links
GOOGLE_DRIVE_MODELS = {
    # Ensemble models
    'Soft Voting': 'https://drive.google.com/uc?export=download&id=1Zu9YYNQ7bHgm4-ChNFOe9GxaaJQWm7P8',
    'Hard Voting': 'https://drive.google.com/uc?export=download&id=1pz0cTnynZfN9DotOgw6erl7hrfZmFaP8',
    'Stacking': 'https://drive.google.com/uc?export=download&id=1qiCJ9H3XZR8_iUOnuW-vpRifzgPEPc66',
    # Optimized models
    'Random Forest': 'https://drive.google.com/uc?export=download&id=1fccrB6be7qqEePVd3VR2R_rizFDya4I6',
    'XGBoost': 'https://drive.google.com/uc?export=download&id=18_h585c02eC0-PdhmMp6pwgtqQuw-XsQ',
    'LightGBM': 'https://drive.google.com/uc?export=download&id=1z2txZkp3J7ToeO7mVAWrDuGJu_2SPhPT',
    'Logistic Regression': 'https://drive.google.com/uc?export=download&id=1j3U7nKGnWrTfU_ij5tsoXNepf6gntfac'
}

@st.cache_resource(ttl=7200)
def load_model_from_drive_or_local(model_name, drive_url):
    """Load a single model from Google Drive or local fallback with caching"""
    # Try Google Drive first
    if drive_url:
        try:
            response = requests.get(drive_url, timeout=30)
            if response.status_code == 200:
                model = joblib.load(io.BytesIO(response.content))
                return model
        except:
            pass
    
    # Fallback to local paths
    model_filename = f"model_{model_name.lower().replace(' ', '_')}"
    local_paths = [
        f'outputs/models/optimized/{model_filename}.pkl',
        f'outputs/models/optimized/{model_filename}_optimized.pkl',
        f'outputs/models/ensemble/{model_filename}.pkl',
        f'outputs/models/ensemble/{model_filename}_optimized.pkl',
        f'models/optimized/{model_filename}.pkl',
        f'models/ensemble/{model_filename}.pkl',
        f'{model_filename}.pkl',
    ]
    
    for model_path in local_paths:
        if os.path.exists(model_path):
            try:
                return joblib.load(model_path)
            except:
                continue
    
    return None

@st.cache_resource(ttl=7200)
def load_scaler():
    """Load scaler with caching"""
    scaler_paths = [
        'outputs/models/scaler_phase8.pkl',
        'models/scaler_phase8.pkl',
        'scaler_phase8.pkl'
    ]
    
    for scaler_path in scaler_paths:
        if os.path.exists(scaler_path):
            try:
                return joblib.load(scaler_path)
            except:
                continue
    return None

@st.cache_resource(ttl=7200)
def load_all_models():
    """Load all models at once with caching for fast subsequent access"""
    config = load_app_configuration()
    loaded_models = {}
    
    available_models = config.get('app_configuration', {}).get('available_models', [])
    
    for model_name in available_models:
        drive_url = GOOGLE_DRIVE_MODELS.get(model_name)
        model = load_model_from_drive_or_local(model_name, drive_url)
        if model is not None:
            loaded_models[model_name] = model
    
    return loaded_models

def get_models_and_scaler():
    """Get cached models and scaler for prediction"""
    loaded_models = load_all_models()
    scaler = load_scaler()
    return loaded_models, scaler

# ============================================================================
# 3. PREDICTION FUNCTIONS (OPTIMIZED)
# ============================================================================

def predict_single_fast(user_inputs, model, scaler, feature_names, class_mapping):
    """Fast prediction with minimal overhead"""
    if scaler is None or model is None:
        return {'error': 'Model or scaler not available'}
    
    try:
        # Create feature vector in correct order
        feature_vector = [user_inputs.get(feat, 0) for feat in feature_names]
        X_input = np.array(feature_vector).reshape(1, -1)
        
        # Scale and predict
        X_scaled = scaler.transform(X_input)
        prediction = model.predict(X_scaled)[0]
        
        # Get probabilities if available
        if hasattr(model, 'predict_proba'):
            prediction_proba = model.predict_proba(X_scaled)[0]
            confidence = float(np.max(prediction_proba))
            probabilities = {class_mapping.get(i, f'Class {i}'): float(prob) for i, prob in enumerate(prediction_proba)}
        else:
            confidence = 0.0
            probabilities = {}
        
        class_label = class_mapping.get(int(prediction), f'Class {prediction}')
        recommendations = get_recommendations(class_label)
        
        return {
            'predicted_class': int(prediction),
            'class_label': class_label,
            'confidence': confidence,
            'uncertainty': 1.0 - confidence,
            'probabilities': probabilities,
            'recommendations': recommendations,
            'feature_values': user_inputs
        }
    except Exception as e:
        return {'error': f'Prediction failed: {str(e)}'}

def predict_csv_fast(csv_file, model, scaler, feature_names, class_mapping):
    """Fast bulk prediction from CSV"""
    try:
        df = pd.read_csv(csv_file)
        required_cols = set(feature_names)
        if not required_cols.issubset(df.columns):
            return {'error': f'Missing required columns: {required_cols - set(df.columns)}'}
        
        X = df[feature_names].fillna(df[feature_names].median())
        X_scaled = scaler.transform(X)
        predictions = model.predict(X_scaled)
        
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(X_scaled)
        else:
            probabilities = None
        
        results = []
        for i in range(len(df)):
            pred_class = int(predictions[i])
            class_label = class_mapping.get(pred_class, f'Class {pred_class}')
            confidence = float(np.max(probabilities[i])) if probabilities is not None else 0.0
            results.append({
                'row_id': i + 1,
                'predicted_class': pred_class,
                'class_label': class_label,
                'confidence': confidence,
                'recommendations': get_recommendations(class_label)
            })
        
        return {
            'success': True,
            'total_records': len(df),
            'predictions': results,
            'summary': {
                'poor': sum(1 for r in results if r['class_label'].lower() == 'poor'),
                'middle_class': sum(1 for r in results if r['class_label'].lower() == 'middle class'),
                'rich': sum(1 for r in results if r['class_label'].lower() == 'rich')
            }
        }
    except Exception as e:
        return {'error': f'CSV prediction failed: {str(e)}'}

def get_recommendations(class_label):
    """Get personalized recommendations based on predicted class"""
    recommendations = {
        'poor': [
            'Apply for government cash transfer programs (PDM, SAGE)',
            'Enroll children in free universal primary education',
            'Access free healthcare at government facilities',
            'Join agricultural cooperatives for better prices',
            'Open a no-fee mobile money savings account'
        ],
        'middle class': [
            'Invest in diversified income streams',
            'Open a fixed deposit or money market account',
            'Consider mortgage options for home ownership',
            'Invest in children secondary/tertiary education',
            'Explore formal employment or business registration'
        ],
        'rich': [
            'Diversify investment portfolio (stocks, bonds, real estate)',
            'Consider business expansion or franchising',
            'Fund children international education',
            'Purchase comprehensive health insurance',
            'Explore regional investment opportunities'
        ]
    }
    return recommendations.get(class_label.lower(), recommendations['middle class'])

def create_downloadable_report(prediction_result, user_info):
    """Create downloadable report"""
    report = {
        'report_type': 'Poverty Classification Report',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': {'username': user_info.get('username', 'Anonymous'), 'user_type': user_info.get('user_type', 'user')},
        'prediction': prediction_result,
        'disclaimer': 'This report is for research and planning purposes only.'
    }
    json_report = json.dumps(report, indent=2)
    
    csv_data = io.StringIO()
    df = pd.DataFrame([{
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Model': prediction_result.get('model_used', 'N/A'),
        'Predicted Class': prediction_result.get('class_label', 'N/A'),
        'Confidence': f"{prediction_result.get('confidence', 0):.2%}",
        'User': user_info.get('username', 'Anonymous')
    }])
    df.to_csv(csv_data, index=False)
    
    return json_report, csv_data.getvalue()

# ============================================================================
# 4. AUTHENTICATION PAGES
# ============================================================================

def show_login_page():
    """Display login page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/4/4e/Flag_of_Uganda.svg", width=100)
        st.title("🇺🇬 Uganda Poverty Classification")
        st.markdown("### 👤 User Login")
        st.markdown("---")
        
        with st.form("login_form"):
            username = st.text_input("📧 Username", placeholder="Enter your username")
            password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                login_clicked = st.form_submit_button("🔐 Login", type="primary", use_container_width=True)
            with col_btn2:
                register_clicked = st.form_submit_button("📝 Register", use_container_width=True)
        
        if login_clicked:
            if username and password:
                user = authenticate_user(username, password)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user
                    st.session_state['current_page'] = 'dashboard'
                    st.success(f"✅ Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            else:
                st.warning("⚠️ Please enter both username and password")
        
        if register_clicked:
            st.session_state['current_page'] = 'register'
            st.rerun()

def show_registration_page():
    """Display registration page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/4/4e/Flag_of_Uganda.svg", width=80)
        st.title("🇺🇬 Create Account")
        st.markdown("### 📝 User Registration")
        st.markdown("---")
        
        with st.form("register_form"):
            col_name1, col_name2 = st.columns(2)
            with col_name1:
                username = st.text_input("👤 Username", placeholder="Choose a username")
                user_type = st.selectbox("🏢 User Type", options=['individual', 'ngo', 'government', 'researcher'], format_func=lambda x: x.title())
            with col_name2:
                email = st.text_input("📧 Email", placeholder="Enter your email")
                confirm_email = st.text_input("📧 Confirm Email", placeholder="Confirm your email")
            
            col_pass1, col_pass2 = st.columns(2)
            with col_pass1:
                password = st.text_input("🔒 Password", type="password", placeholder="Min 4 characters")
            with col_pass2:
                confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Re-enter password")
            
            profile_pic = st.file_uploader("📸 Profile Picture (Optional)", type=['png', 'jpg', 'jpeg'])
            terms_accepted = st.checkbox("✅ I agree to the Terms of Service and Privacy Policy")
            
            col_reg1, col_reg2 = st.columns(2)
            with col_reg1:
                register_clicked = st.form_submit_button("📝 Register", type="primary", use_container_width=True)
            with col_reg2:
                back_to_login = st.form_submit_button("← Back to Login", use_container_width=True)
        
        if register_clicked:
            if not username or not email or not password:
                st.error("❌ All fields are required")
            elif email != confirm_email:
                st.error("❌ Emails do not match")
            elif password != confirm_password:
                st.error("❌ Passwords do not match")
            elif len(password) < 4:
                st.error("❌ Password must be at least 4 characters")
            elif not terms_accepted:
                st.error("❌ You must accept the Terms of Service")
            else:
                profile_pic_data = profile_pic.getvalue() if profile_pic else None
                success, message = register_user(username=username, email=email, password=password, user_type=user_type, profile_pic=profile_pic_data)
                
                if success:
                    st.success(f"✅ {message}")
                    if st.button("→ Go to Login"):
                        st.session_state['current_page'] = 'login'
                        st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        if back_to_login:
            st.session_state['current_page'] = 'login'
            st.rerun()

def show_user_profile():
    """Display user profile in sidebar"""
    if st.session_state.get('logged_in', False):
        user = st.session_state.get('user_info', {})
        st.sidebar.markdown("---")
        st.sidebar.subheader("👤 Profile")
        
        if user.get('profile_pic'):
            try:
                image = Image.open(io.BytesIO(user['profile_pic']))
                st.sidebar.image(image, width=80)
            except:
                st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
        else:
            st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
        
        st.sidebar.markdown(f"**{user.get('username', 'User')}**")
        st.sidebar.markdown(f"📧 {user.get('email', 'N/A')}")
        st.sidebar.markdown(f"🏢 {user.get('user_type', 'user').title()}")

def show_logout_button():
    """Display logout button in sidebar"""
    if st.session_state.get('logged_in', False):
        st.sidebar.markdown("---")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.session_state['logged_in'] = False
            st.session_state['user_info'] = None
            st.session_state['current_page'] = 'login'
            st.rerun()

# ============================================================================
# 5. MAIN PREDICTION DASHBOARD (OPTIMIZED)
# ============================================================================

def show_dashboard_home():
    """Display dashboard home page"""
    st.title("🏠 Dashboard")
    st.markdown("### Welcome to Uganda Poverty Classification System")
    
    user = st.session_state['user_info']
    
    if user['user_type'] == 'admin':
        st.info("👋 Welcome, Administrator! You have full access to all features.")
    elif user['user_type'] == 'ngo':
        st.info("🏢 Welcome, NGO Partner! Use bulk upload for multiple households.")
    elif user['user_type'] == 'government':
        st.info("🏛️ Welcome, Government User! Access analytics and bulk processing.")
    else:
        st.info("👤 Welcome! Predict poverty classification for households.")
    
    # Quick stats
    predictions = get_user_predictions(user['id'], limit=1000)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Predictions", len(predictions))
    with col2:
        st.metric("🔴 Poor", sum(1 for p in predictions if p['predicted_class'].lower() == 'poor'))
    with col3:
        st.metric("🟡 Middle Class", sum(1 for p in predictions if p['predicted_class'].lower() == 'middle class'))
    with col4:
        st.metric("🟢 Rich", sum(1 for p in predictions if p['predicted_class'].lower() == 'rich'))
    
    # Quick action buttons
    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("🔮 New Prediction", type="primary", use_container_width=True):
            st.session_state['current_page'] = 'prediction'
            st.rerun()
    with col_btn2:
        if st.button("📁 Bulk Upload", use_container_width=True):
            st.session_state['current_page'] = 'bulk_upload'
            st.rerun()
    with col_btn3:
        if st.button("📊 View History", use_container_width=True):
            st.session_state['current_page'] = 'history'
            st.rerun()
    
    # Recent predictions
    if predictions:
        st.markdown("---")
        st.subheader("📋 Recent Predictions")
        recent_df = pd.DataFrame(predictions[:5])
        recent_df['created_at'] = pd.to_datetime(recent_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        display_df = recent_df[['created_at', 'model_used', 'predicted_class', 'confidence']].copy()
        display_df.columns = ['Date/Time', 'Model', 'Predicted Class', 'Confidence']
        display_df['Confidence'] = display_df['Confidence'].apply(lambda x: f"{x:.1%}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

def show_single_prediction():
    """Display single household prediction form - OPTIMIZED FOR SPEED"""
    st.title("🔮 New Prediction")
    st.markdown("### Enter Household Information")
    
    # Model selection with loading indicator
    selected_model = st.sidebar.selectbox("🤖 Model:", options=AVAILABLE_MODELS, index=0)
    
    # Show model loading status
    if selected_model not in loaded_models:
        st.sidebar.warning(f"⚠️ {selected_model} not loaded. Trying to download...")
    
    with st.form("prediction_form"):
        st.markdown("#### 🌍 Geographic Features")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            region = st.selectbox(FEATURE_APP_NAMES.get('region', 'Region'), options=[1, 2, 3, 4], format_func=lambda x: f"Region {x}")
            subreg = st.selectbox(FEATURE_APP_NAMES.get('subreg', 'Sub-Region'), options=list(range(1, 17)), format_func=lambda x: f"Sub-Region {x}")
        with col2:
            regurb = st.selectbox(FEATURE_APP_NAMES.get('regurb', 'Region-Urban Type'), options=list(range(1, 9)), format_func=lambda x: f"Type {x}")
            district = st.selectbox(FEATURE_APP_NAMES.get('district', 'District'), options=list(range(1, 118)), format_func=lambda x: f"District {x}")
        with col3:
            urban = st.radio(FEATURE_APP_NAMES.get('urban', 'Urban/Rural'), options=[0, 1], format_func=lambda x: "🏙️ Urban" if x == 1 else "🌾 Rural", horizontal=True)
            hsize = st.number_input(FEATURE_APP_NAMES.get('hsize', 'Household Size'), min_value=1, max_value=20, value=5, step=1)
        
        st.markdown("#### 💰 Economic Features")
        col4, col5 = st.columns(2)
        with col4:
            equiv = st.number_input(FEATURE_APP_NAMES.get('equiv', 'Monthly Income/Expenditure (UGX)'), min_value=0, max_value=10000000, value=500000, step=50000, format="%d")
        with col5:
            nrrexp30 = st.number_input(FEATURE_APP_NAMES.get('nrrexp30', 'Non-Food Expenses (UGX)'), min_value=0, max_value=5000000, value=200000, step=25000, format="%d")
        
        st.markdown("---")
        submitted = st.form_submit_button("🔮 Predict Poverty Class", type="primary", use_container_width=True)
    
    if submitted:
        user_inputs = {'region': region, 'regurb': regurb, 'subreg': subreg, 'district': district, 'urban': urban, 'equiv': equiv, 'hsize': hsize, 'nrrexp30': nrrexp30}
        model = loaded_models.get(selected_model)
        
        if model is None:
            st.error(f"❌ Model '{selected_model}' not available. Please try again or select a different model.")
            st.info("💡 Tip: Models are downloaded from Google Drive on first use. This may take 10-30 seconds.")
        else:
            with st.spinner(f"🤖 Running prediction with {selected_model}..."):
                results = predict_single_fast(user_inputs=user_inputs, model=model, scaler=scaler, feature_names=FEATURE_NAMES, class_mapping=CLASS_MAPPING)
            
            if 'error' in results:
                st.error(f"❌ {results['error']}")
            else:
                # Save to history
                save_prediction(user_id=st.session_state['user_info']['id'], model_used=selected_model, predicted_class=results['class_label'], confidence=results['confidence'], input_data=user_inputs, recommendations=results['recommendations'])
                display_prediction_results(results, selected_model)

def display_prediction_results(results, model_name):
    """Display prediction results - OPTIMIZED"""
    st.markdown("---")
    st.subheader("🎯 Prediction Results")
    
    # Determine styling based on prediction
    if results['class_label'].lower() == 'poor':
        bg_color, border_color = "#ffebee", "#f44336"
    elif results['class_label'].lower() == 'middle class':
        bg_color, border_color = "#fff8e1", "#ffc107"
    else:
        bg_color, border_color = "#e8f5e9", "#4caf50"
    
    # Main result card
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"""<div style="background-color: {bg_color}; padding: 20px; border-radius: 10px; border-left: 5px solid {border_color}"><h3 style="margin: 0; color: #333;">Predicted Class: {results['class_label'].title()}</h3><p style="margin: 5px 0 0 0; color: #666;">Using model: <strong>{model_name}</strong></p></div>""", unsafe_allow_html=True)
    with col2:
        st.metric("🎯 Confidence", f"{results['confidence']:.1%}")
        if results['confidence'] < 0.7:
            st.warning("⚠️ Low confidence")
    with col3:
        st.metric("⚠️ Uncertainty", f"{results['uncertainty']:.1%}")
    
    # Class probabilities
    if results.get('probabilities'):
        st.markdown("#### 📊 Class Probabilities")
        prob_df = pd.DataFrame({'Class': list(results['probabilities'].keys()), 'Probability': list(results['probabilities'].values())}).sort_values('Probability', ascending=False)
        fig_prob = px.bar(prob_df, x='Probability', y='Class', orientation='h', color='Probability', color_continuous_scale=['#e74c3c', '#f39c12', '#27ae60'], range_x=[0, 1])
        fig_prob.update_layout(height=300, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_prob, use_container_width=True)
    
    # Recommendations
    st.markdown("#### 💡 Recommendations")
    for i, rec in enumerate(results.get('recommendations', [])[:5], 1):
        st.markdown(f"{i}. {rec}")
    
    # Download buttons
    st.markdown("---")
    st.subheader("📥 Download Report")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        json_report, _ = create_downloadable_report(results, st.session_state['user_info'])
        st.download_button(label="📄 Download JSON", data=json_report, file_name=f"poverty_prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)
    with col_dl2:
        _, csv_data = create_downloadable_report(results, st.session_state['user_info'])
        st.download_button(label="📊 Download CSV", data=csv_data, file_name=f"poverty_prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)

def show_bulk_upload():
    """Display bulk CSV upload - OPTIMIZED"""
    st.title("📁 Bulk Upload (CSV)")
    
    user_type = st.session_state['user_info'].get('user_type', 'user')
    if user_type not in ['ngo', 'government', 'admin', 'researcher']:
        st.warning("⚠️ Bulk upload is available for NGOs, Government, Researchers, and Admin users only.")
        return
    
    st.info("📋 **CSV Format:** Must include columns: region, regurb, subreg, district, urban, equiv, hsize, nrrexp30")
    
    # Template download
    template_df = pd.DataFrame({'region': [1, 2], 'regurb': [1, 5], 'subreg': [1, 8], 'district': [1, 50], 'urban': [1, 0], 'equiv': [500000, 300000], 'hsize': [5, 4], 'nrrexp30': [200000, 150000]})
    st.download_button(label="📥 Download CSV Template", data=template_df.to_csv(index=False), file_name="poverty_prediction_template.csv", mime="text/csv", use_container_width=True)
    
    st.markdown("---")
    uploaded_file = st.file_uploader("📤 Upload Your CSV File", type=['csv'])
    
    if uploaded_file:
        selected_model = st.selectbox("🤖 Select Model:", options=AVAILABLE_MODELS, index=0)
        
        if st.button("🔮 Process CSV", type="primary", use_container_width=True):
            with st.spinner("🔄 Processing..."):
                model = loaded_models.get(selected_model)
                if model is None:
                    st.error(f"❌ Model '{selected_model}' not available")
                else:
                    results = predict_csv_fast(csv_file=uploaded_file, model=model, scaler=scaler, feature_names=FEATURE_NAMES, class_mapping=CLASS_MAPPING)
                    
                    if 'error' in results:
                        st.error(f"❌ {results['error']}")
                    else:
                        st.success(f"✅ Processed {results['total_records']} records!")
                        col1, col2, col3 = st.columns(3)
                        with col1: st.metric("🔴 Poor", results['summary']['poor'])
                        with col2: st.metric("🟡 Middle Class", results['summary']['middle_class'])
                        with col3: st.metric("🟢 Rich", results['summary']['rich'])
                        
                        results_df = pd.DataFrame(results['predictions'])
                        st.dataframe(results_df, use_container_width=True, hide_index=True)
                        
                        st.download_button(label="📊 Download Results", data=results_df.to_csv(index=False), file_name=f"bulk_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)

def show_prediction_history():
    """Display prediction history"""
    st.title("📊 Prediction History")
    predictions = get_user_predictions(st.session_state['user_info']['id'], limit=100)
    
    if predictions:
        history_df = pd.DataFrame(predictions)
        history_df['created_at'] = pd.to_datetime(history_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        history_df['Confidence'] = history_df['confidence'].apply(lambda x: f"{x:.1%}")
        display_df = history_df[['created_at', 'model_used', 'predicted_class', 'Confidence']].copy()
        display_df.columns = ['Date/Time', 'Model', 'Predicted Class', 'Confidence']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.download_button(label="📥 Download History (CSV)", data=history_df.to_csv(index=False), file_name=f"prediction_history_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("📭 No prediction history yet.")

def show_settings():
    """Display settings"""
    st.title("⚙️ Settings")
    user = st.session_state['user_info']
    
    st.markdown("#### 👤 Profile Information")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Username", value=user['username'], disabled=True)
        st.text_input("Email", value=user['email'], disabled=True)
    with col2:
        st.text_input("User Type", value=user['user_type'].title(), disabled=True)
    
    st.markdown("---")
    st.markdown("#### 🎨 Theme")
    theme_choice = st.radio("Choose theme:", options=['Light', 'Dark'], index=0 if st.session_state['theme'] == 'light' else 1, horizontal=True)
    st.session_state['theme'] = 'dark' if theme_choice == 'Dark' else 'light'
    st.info("🔄 Theme will update after page refresh")

def show_admin_users():
    """Admin user management"""
    if st.session_state['user_info'].get('user_type') != 'admin':
        st.error("❌ Admin privileges required.")
        return
    st.title("👥 User Management")
    users = get_all_users()
    if users:
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)

def show_admin_stats():
    """Admin statistics"""
    if st.session_state['user_info'].get('user_type') != 'admin':
        st.error("❌ Admin privileges required.")
        return
    st.title("📊 App Statistics")
    stats = get_app_statistics()
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("👥 Total Users", stats.get('total_users', 0))
    with col2: st.metric("📊 Total Predictions", stats.get('total_predictions', 0))
    with col3: st.metric("📅 Last 7 Days", stats.get('predictions_last_7_days', 0))

# ============================================================================
# 6. MAIN APP INITIALIZATION (OPTIMIZED)
# ============================================================================

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'login'
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'light'
if 'models_loaded' not in st.session_state:
    st.session_state['models_loaded'] = False

# Initialize database
init_database()
create_default_users()

# Load configuration
app_config = load_app_configuration()
FEATURE_NAMES = app_config.get('features', {}).get('feature_names', [])
FEATURE_APP_NAMES = app_config.get('features', {}).get('feature_app_names', {})
CLASS_MAPPING = app_config.get('class_info', {}).get('class_mapping', {})
CONFIDENCE_CONFIG = app_config.get('confidence_settings', {})
AVAILABLE_MODELS = app_config.get('app_configuration', {}).get('available_models', [])

# Load models and scaler with caching (only once per session)
if not st.session_state['models_loaded']:
    with st.spinner("🔄 Loading models (first time may take 10-30 seconds)..."):
        loaded_models, scaler = get_models_and_scaler()
        st.session_state['models_loaded'] = True
        st.session_state['loaded_models'] = loaded_models
        st.session_state['scaler'] = scaler
else:
    loaded_models = st.session_state['loaded_models']
    scaler = st.session_state['scaler']

# Set theme
if st.session_state['theme'] == 'dark':
    st.markdown("""
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stButton>button { background-color: #1f77b4; color: white; }
        </style>
    """, unsafe_allow_html=True)

# Main app routing
if not st.session_state.get('logged_in', False):
    if st.session_state.get('current_page') == 'register':
        show_registration_page()
    else:
        show_login_page()
else:
    show_user_profile()
    show_logout_button()
    
    # Sidebar navigation
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 Navigation")
    pages = {'🏠 Dashboard': 'dashboard', '🔮 New Prediction': 'prediction', '📊 History': 'history', '📁 Bulk Upload': 'bulk_upload', '⚙️ Settings': 'settings'}
    if st.session_state['user_info'].get('user_type') == 'admin':
        pages['👥 Users'] = 'admin_users'
        pages['📊 Stats'] = 'admin_stats'
    
    selected = st.sidebar.radio("Go to:", list(pages.keys()), index=0)
    st.session_state['current_page'] = pages[selected]
    
    # Theme switcher
    st.sidebar.markdown("---")
    theme_choice = st.sidebar.radio("🎨 Theme", ['Light', 'Dark'])
    st.session_state['theme'] = 'dark' if theme_choice == 'Dark' else 'light'
    
    # Page routing
    if st.session_state['current_page'] == 'dashboard':
        show_dashboard_home()
    elif st.session_state['current_page'] == 'prediction':
        show_single_prediction()
    elif st.session_state['current_page'] == 'history':
        show_prediction_history()
    elif st.session_state['current_page'] == 'bulk_upload':
        show_bulk_upload()
    elif st.session_state['current_page'] == 'settings':
        show_settings()
    elif st.session_state['current_page'] == 'admin_users':
        show_admin_users()
    elif st.session_state['current_page'] == 'admin_stats':
        show_admin_stats()