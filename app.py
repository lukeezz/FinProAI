# app.py - NUTRISCANAI with all features (FIXED VERSION)
import streamlit as st
from datetime import datetime, timedelta
import json
import os
import pandas as pd
from typing import Dict, Any
import tempfile
from PIL import Image
import plotly.graph_objects as go

# Import our modules
try:
    from database import NutritionDatabase, extract_number
    from image_classifier import get_food_classifier
    from deepseek_api import get_nutrition_api, extract_number as extract_num
except ImportError:
    # Fallback if modules are in same directory
    import sys
    sys.path.append('.')
    from database import NutritionDatabase, extract_number
    from image_classifier import get_food_classifier
    from deepseek_api import get_nutrition_api, extract_number as extract_num

# -------------------------
# KONFIGURASI APLIKASI
# -------------------------
st.set_page_config(
    page_title="NutriScanAI",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
@st.cache_resource
def init_database():
    return NutritionDatabase()

db = init_database()

# Initialize classifier and API (cached) - WITH ERROR HANDLING
@st.cache_resource
def init_classifier():
    try:
        return get_food_classifier('best_food_effnet.keras')
    except Exception as e:
        st.error(f"Gagal memuat model AI: {str(e)}")
        return None  # RETURN None JIKA ERROR

@st.cache_resource
def init_nutrition_api():
    try:
        return get_nutrition_api()
    except Exception as e:
        st.error(f"Gagal memuat API nutrisi: {str(e)}")
        return None

# Initialize APIs
classifier = init_classifier()
nutrition_api = init_nutrition_api()

# -------------------------
# SESSION STATE MANAGEMENT
# -------------------------
def init_session_state():
    """Initialize session state variables"""
    default_states = {
        "page": "login",
        "user": None,
        "user_id": None,
        "current_data": {},
        "show_register": False,
        "food_input": "",
        "uploaded_image": None,
        "prediction_result": None,
        "nutrition_result": None,
        "selected_date": datetime.now().strftime("%Y-%m-%d"),
        "model_available": classifier is not None,
        "api_available": nutrition_api is not None if nutrition_api else False
    }
    
    for key, value in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# -------------------------
# HELPER FUNCTIONS (FIXED)
# -------------------------
def get_nutrition_from_prediction(food_name, portion_grams=100):
    """Get nutrition analysis for predicted food with error handling"""
    if not food_name or not food_name.strip():
        return {
            'calories': 0,
            'protein': '0 g',
            'fat': '0 g',
            'carbs': '0 g',
            'notes': 'Makanan tidak dikenali'
        }
    
    with st.spinner(f"Menganalisis nutrisi {food_name}..."):
        try:
            if nutrition_api:
                nutrition = nutrition_api.analyze_food_nutrition(food_name, portion_grams)
            else:
                # FALLBACK jika API tidak tersedia
                nutrition = {
                    'calories': portion_grams * 1.5,  # Estimasi
                    'protein': f"{portion_grams * 0.1:.1f} g",
                    'fat': f"{portion_grams * 0.05:.1f} g",
                    'carbs': f"{portion_grams * 0.2:.1f} g",
                    'notes': 'Analisis menggunakan data estimasi'
                }
            return nutrition
        except Exception as e:
            # RETURN DEFAULT JIKA ERROR
            return {
                'calories': portion_grams * 1.5,
                'protein': f"{portion_grams * 0.1:.1f} g",
                'fat': f"{portion_grams * 0.05:.1f} g",
                'carbs': f"{portion_grams * 0.2:.1f} g",
                'notes': f'Error: {str(e)}'
            }
        
def calculate_daily_needs(user_profile):
    """Calculate daily nutritional needs - ULTRA SAFE VERSION"""
    # DEFAULT VALUES
    defaults = {
        'target_calories': 2000,
        'target_protein': 100,
        'target_fat': 67,
        'target_carbs': 250,
        'target_water': 2000,
        'target_fiber': 25,
        'target_sugar': 25,
        'target_sodium': 2300
    }
    
    try:
        if not user_profile:
            return defaults
        
        # EXTRACT WITH EXTREME SAFETY
        def get_safe_float(key, default):
            val = user_profile.get(key)
            if val is None:
                return default
            try:
                return float(val)
            except:
                return default
        
        def get_safe_int(key, default):
            val = user_profile.get(key)
            if val is None:
                return default
            try:
                return int(float(val))
            except:
                return default
        
        def get_safe_str_lower(key, default):
            val = user_profile.get(key)
            if val is None:
                return default
            try:
                if isinstance(val, str):
                    return val.lower().strip()
                else:
                    return str(val).lower().strip()
            except:
                return default
        
        # Get values
        weight = get_safe_float('weight', 65)
        height = get_safe_float('height', 170)
        age = get_safe_int('age', 25)
        activity = get_safe_str_lower('activity_level', 'medium')
        goal = get_safe_str_lower('goal', 'maintain')
        
        # Calculate BMR
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        
        # Activity multipliers
        activity_multipliers = {
            'sedentary': 1.2,
            'light': 1.375,
            'medium': 1.55,
            'active': 1.725,
            'very_active': 1.9
        }
        
        # Get activity factor - activity sudah pasti string lowercase
        activity_factor = activity_multipliers.get(activity, 1.55)
        maintenance_calories = bmr * activity_factor
        
        # Goal adjustments
        if goal == 'lose':
            target_calories = maintenance_calories * 0.85
        elif goal == 'gain':
            target_calories = maintenance_calories * 1.15
        else:
            target_calories = maintenance_calories
        
        # Macronutrient distribution
        protein_g = weight * 1.6
        protein_cal = protein_g * 4
        
        fat_cal = target_calories * 0.25
        fat_g = fat_cal / 9
        
        carbs_cal = target_calories - protein_cal - fat_cal
        carbs_g = carbs_cal / 4
        
        return {
            'target_calories': round(target_calories),
            'target_protein': round(protein_g),
            'target_fat': round(fat_g),
            'target_carbs': round(carbs_g),
            'target_water': 2000,
            'target_fiber': 25,
            'target_sugar': 25,
            'target_sodium': 2300
        }
        
    except Exception as e:
        print(f"ERROR in calculate_daily_needs: {e}")
        return defaults
# -------------------------
# AUTHENTICATION PAGES (UNCHANGED)
# -------------------------
def login_page():
    """Login page"""
    st.title("🍎 NutriScanAI")
    st.markdown("### Masuk ke Akun Anda")
    
    # Demo credentials
    with st.expander("ℹ️ Akun Demo"):
        st.code("Email: demo@example.com\nPassword: demo123")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3077/3077321.png", width=150)
    
    with col2:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔐 Login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("Email dan password harus diisi")
                else:
                    try:
                        user = db.authenticate_user(email, password)
                        if user:
                            st.session_state.user = user
                            st.session_state.user_id = user['id']
                            st.session_state.page = "home"
                            st.success(f"Selamat datang, {user['name']}!")
                            st.rerun()
                        else:
                            st.error("Email atau password salah")
                    except Exception as e:
                        st.error(f"Error autentikasi: {str(e)}")
        
        with col_btn2:
            if st.button("📝 Daftar Baru", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
    
    # Registration form
    if st.session_state.show_register:
        st.markdown("---")
        st.subheader("📝 Pendaftaran Akun Baru")
        
        reg_col1, reg_col2 = st.columns(2)
        
        with reg_col1:
            reg_name = st.text_input("Nama Lengkap", key="reg_name")
            reg_email = st.text_input("Email", key="reg_email")
        
        with reg_col2:
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_confirm = st.text_input("Konfirmasi Password", type="password", key="reg_confirm")
        
        if st.button("✅ Daftar Sekarang", type="primary"):
            if not all([reg_name, reg_email, reg_password, reg_confirm]):
                st.error("Semua field harus diisi")
            elif reg_password != reg_confirm:
                st.error("Password tidak cocok")
            elif len(reg_password) < 6:
                st.error("Password minimal 6 karakter")
            else:
                try:
                    if db.user_exists(reg_email):
                        st.error("Email sudah terdaftar")
                    else:
                        user_id = db.create_user(reg_email, reg_password, reg_name)
                        if user_id:
                            st.success("🎉 Akun berhasil dibuat! Silakan login.")
                            st.session_state.show_register = False
                            st.rerun()
                        else:
                            st.error("Gagal membuat akun")
                except Exception as e:
                    st.error(f"Error pendaftaran: {str(e)}")
        
        if st.button("❌ Batal"):
            st.session_state.show_register = False
            st.rerun()

def logout():
    """Logout user"""
    st.session_state.user = None
    st.session_state.user_id = None
    st.session_state.page = "login"
    st.rerun()

# -------------------------
# IMAGE UPLOAD & PREDICTION FUNCTIONS (FIXED)
# -------------------------
def handle_image_upload():
    """Handle image upload and food prediction with error handling"""
    
    st.subheader("📸 Upload Foto Makanan")
    
    if not st.session_state.model_available:
        st.warning("⚠️ Model AI tidak tersedia. Fitur analisis gambar dinonaktifkan.")
        return
    
    # Image upload
    uploaded_file = st.file_uploader(
        "Pilih foto makanan Anda",
        type=['jpg', 'jpeg', 'png', 'webp'],
        help="Upload foto makanan untuk dianalisis secara otomatis"
    )
    
    if uploaded_file is not None:
        try:
            # Display image
            image = Image.open(uploaded_file)
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(image, caption="Foto Makanan", width=250)
            
            with col2:
                # Save to session state
                st.session_state.uploaded_image = image
                
                # Predict button
                if st.button("🔍 Analisis Gambar", type="primary"):
                    with st.spinner("Menganalisis gambar..."):
                        if classifier is None:
                            st.error("Model AI tidak tersedia")
                            return
                        
                        try:
                            # Make prediction
                            predictions = classifier.predict(image, top_k=3)
                            
                            if predictions:
                                st.session_state.prediction_result = predictions
                                
                                # Display predictions
                                st.success("✅ Gambar berhasil dianalisis!")
                                
                                st.write("**Hasil Prediksi:**")
                                for food_name, confidence in predictions:
                                    st.write(f"• {food_name} ({confidence:.1%} confidence)")
                                
                                # Auto-fill food input
                                best_food = predictions[0][0]
                                st.session_state.food_input = best_food
                                st.rerun()
                            
                            else:
                                st.error("❌ Tidak dapat mengenali makanan dalam gambar")
                        except Exception as e:
                            st.error(f"Error prediksi: {str(e)}")
        except Exception as e:
            st.error(f"Error memproses gambar: {str(e)}")
    
    # Or use camera
    with st.expander("📷 Atau gunakan kamera"):
        camera_photo = st.camera_input("Ambil foto dengan kamera")
        
        if camera_photo:
            try:
                image = Image.open(camera_photo)
                st.session_state.uploaded_image = image
                
                if st.button("Analisis Foto Kamera", type="primary"):
                    with st.spinner("Menganalisis gambar..."):
                        if classifier is None:
                            st.error("Model AI tidak tersedia")
                            return
                        
                        predictions = classifier.predict(image, top_k=3)
                        
                        if predictions:
                            st.session_state.prediction_result = predictions
                            st.success(f"✅ Terdeteksi: {predictions[0][0]}")
                            
                            # Auto-fill with best prediction
                            st.session_state.food_input = predictions[0][0]
                            st.rerun()
                        else:
                            st.error("Tidak dapat mengenali makanan")
            except Exception as e:
                st.error(f"Error kamera: {str(e)}")

# -------------------------
# HOME PAGE (FIXED)
# -------------------------
def home_page():
    """Main home page with image upload"""
    try:
        # Load user profile
        user_profile = db.get_user_profile(st.session_state.user_id)
        
        if not user_profile:
            st.error("Profil tidak ditemukan. Silakan login kembali.")
            logout()
            return
        
        # Header
        col_header1, col_header2, col_header3 = st.columns([3, 1, 1])
        with col_header1:
            st.title(f"🍎 NutriScanAI - Selamat Datang, {user_profile.get('name', 'User')}!")
            st.caption("Analisis nutrisi cerdas dengan AI")
        with col_header2:
            st.metric("📅 Hari Ini", datetime.now().strftime("%d %b %Y"))
        with col_header3:
            if st.button("🚪 Logout", type="secondary"):
                logout()
        
        st.markdown("---")
        
        # Today's summary
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            today_summary = db.get_daily_nutrition_summary(st.session_state.user_id, today)
        except:
            today_summary = {}  # DEFAULT JIKA ERROR
        
        # Ensure all keys exist with defaults
        today_summary = {
            'food_count': today_summary.get('food_count', 0),
            'total_calories': today_summary.get('total_calories', 0),
            'total_protein': today_summary.get('total_protein', 0),
            'total_water': today_summary.get('total_water', 0)
        }
        
        col_summary1, col_summary2, col_summary3, col_summary4 = st.columns(4)
        
        with col_summary1:
            st.metric("🍽️ Makanan", today_summary['food_count'])
        with col_summary2:
            st.metric("🔥 Kalori", f"{int(today_summary['total_calories'])}")
        with col_summary3:
            st.metric("🥩 Protein", f"{int(today_summary['total_protein'])}g")
        with col_summary4:
            st.metric("💧 Air", f"{today_summary['total_water']}ml")
        
        st.markdown("---")
        
        # Main content with tabs
        tab1, tab2, tab3 = st.tabs(["📸 Analisis Gambar", "📝 Input Manual", "🍱 Pilihan Cepat"])
        
        with tab1:
            # Image upload section
            handle_image_upload()
            
            # Show prediction result if available
            if st.session_state.prediction_result:
                st.markdown("---")
                st.subheader("🥗 Analisis Nutrisi dari Gambar")
                
                predictions = st.session_state.prediction_result
                best_food = predictions[0][0]
                
                # Food name (editable)
                food_name = st.text_input("Nama Makanan", value=best_food, key="img_food_name")
                
                # Portion in grams
                col_portion1, col_portion2, col_portion3 = st.columns(3)
                with col_portion1:
                    portion_grams = st.number_input("🍽️ Berat (gram)", min_value=1, max_value=2000, value=100, step=10, key="img_grams")
                with col_portion2:
                    water = st.number_input("💧 Air (ml)", min_value=0, max_value=5000, value=500, step=100, key="img_water")
                with col_portion3:
                    exercise = st.number_input("🏃 Olahraga (mnt)", min_value=0, max_value=300, value=0, step=5, key="img_exercise")
                
                # Button to analyze nutrition
                if st.button("🧪 Analisis Nutrisi", type="primary"):
                    if not food_name.strip():
                        st.error("Masukkan nama makanan terlebih dahulu")
                        return
                    
                    nutrition = get_nutrition_from_prediction(food_name, portion_grams)
                    
                    # Display results
                    st.success(f"✅ Nutrisi {food_name} berhasil dianalisis!")
                    
                    col_nut1, col_nut2 = st.columns(2)
                    with col_nut1:
                        # Extract numeric values from strings if needed
                        calories = nutrition.get('calories', '0')
                        if isinstance(calories, str):
                            # Try to extract number from string
                            try:
                                calories_num = float(''.join(filter(str.isdigit, calories)) or 0)
                            except:
                                calories_num = 0
                        else:
                            calories_num = float(calories)
                        
                        protein = nutrition.get('protein', '0 g')
                        st.metric("🔥 Kalori", f"{int(calories_num)}")
                        st.metric("🥩 Protein", protein)
                    
                    with col_nut2:
                        fat = nutrition.get('fat', '0 g')
                        carbs = nutrition.get('carbs', '0 g')
                        st.metric("🥑 Lemak", fat)
                        st.metric("🍞 Karbo", carbs)
                    
                    if 'fiber' in nutrition:
                        st.write(f"🌾 **Serat:** {nutrition['fiber']}")
                    if 'notes' in nutrition:
                        st.info(f"📝 **Catatan:** {nutrition['notes']}")
                    
                    # Save button
                    if st.button("💾 Simpan ke Database", type="secondary"):
                        entry_data = {
                            "food": food_name,
                            "portion_grams": portion_grams,
                            "nutrition": nutrition,
                            "water": water,
                            "exercise": exercise,
                            "date": today,
                            "source": "image_upload"
                        }
                        
                        try:
                            if db.add_daily_entry(st.session_state.user_id, entry_data):
                                st.success("✅ Data berhasil disimpan!")
                                st.session_state.current_data = entry_data
                                st.rerun()
                            else:
                                st.error("❌ Gagal menyimpan data")
                        except Exception as e:
                            st.error(f"Error menyimpan data: {str(e)}")
        
        with tab2:
            # Manual input section
            st.subheader("📝 Input Manual")
            
            food_name = st.text_input(
                "🍽️ Apa yang kamu makan/minum?",
                value=st.session_state.food_input,
                placeholder="Contoh: Nasi goreng, Salad buah, Ayam bakar...",
                key="food_input_manual"
            )
            
            col_input1, col_input2, col_input3 = st.columns(3)
            with col_input1:
                portion_grams = st.number_input("🍽️ Berat (gram)", min_value=1, max_value=2000, value=100, step=10, key="manual_grams")
            with col_input2:
                water = st.number_input("💧 Air (ml)", min_value=0, max_value=5000, value=500, step=100, key="manual_water")
            with col_input3:
                exercise = st.number_input("🏃 Olahraga (mnt)", min_value=0, max_value=300, value=0, step=5, key="manual_exercise")
            
            if st.button("🔍 Simpan", type="primary", use_container_width=True):
                if not food_name.strip():
                    st.error("❗ Masukkan nama makanan terlebih dahulu")
                else:
                    with st.spinner("Menganalisis nutrisi..."):
                        nutrition = get_nutrition_from_prediction(food_name, portion_grams)
                        
                        entry_data = {
                            "food": food_name,
                            "portion_grams": portion_grams,
                            "nutrition": nutrition,
                            "water": water,
                            "exercise": exercise,
                            "date": today
                        }
                        
                        try:
                            if db.add_daily_entry(st.session_state.user_id, entry_data):
                                st.success("✅ Data berhasil disimpan!")
                                st.session_state.current_data = entry_data
                                st.session_state.food_input = ""  # Clear input
                                st.rerun()
                            else:
                                st.error("❌ Gagal menyimpan data")
                        except Exception as e:
                            st.error(f"Error menyimpan: {str(e)}")
        
        with tab3:
            # Quick selection
            st.subheader("🍱 Pilihan Cepat")
            
            quick_foods = [
                ("Nasi Putih", 100),
                ("Nasi Goreng", 150),
                ("Ayam Goreng", 120),
                ("Tempe Goreng", 80),
                ("Buah Pisang", 100),
                ("Sayur Bayam", 150),
                ("Telur Rebus", 50),
                ("Sate Ayam", 100)
            ]
            
            cols = st.columns(4)
            for idx, (food, grams) in enumerate(quick_foods):
                col = cols[idx % 4]
                if col.button(f"{food}\n({grams}g)", use_container_width=True):
                    st.session_state.food_input = food
                    st.rerun()
            
            st.markdown("---")
            st.write("Klik makanan di atas untuk mengisi otomatis")
        
        # Right sidebar with daily targets
        st.sidebar.markdown("---")
        with st.sidebar:
            st.subheader("🎯 Target Harian")
            
            # Calculate daily needs
            try:
                daily_needs = calculate_daily_needs(user_profile)
            except:
                daily_needs = {
                    'target_calories': 2000,
                    'target_water': 2000,
                    'target_protein': 100
                }
            
            # Progress bars with error handling
            try:
                cal_percent = min(today_summary['total_calories'] / daily_needs['target_calories'] * 100, 100)
                st.progress(cal_percent / 100, 
                           text=f"🔥 Kalori: {int(today_summary['total_calories'])}/{daily_needs['target_calories']}")
            except:
                st.progress(0, text="🔥 Kalori: 0/2000")
            
            try:
                water_percent = min(today_summary['total_water'] / daily_needs['target_water'] * 100, 100)
                st.progress(water_percent / 100,
                           text=f"💧 Air: {today_summary['total_water']}/{daily_needs['target_water']}ml")
            except:
                st.progress(0, text="💧 Air: 0/2000ml")
            
            try:
                protein_percent = min(today_summary['total_protein'] / daily_needs['target_protein'] * 100, 100)
                st.progress(protein_percent / 100,
                           text=f"🥩 Protein: {int(today_summary['total_protein'])}/{daily_needs['target_protein']}g")
            except:
                st.progress(0, text="🥩 Protein: 0/100g")
        
        # Navigation at bottom
        st.markdown("---")
        col_nav1, col_nav2, col_nav3, col_nav4 = st.columns(4)
        with col_nav1:
            if st.button("📊 Analisis", use_container_width=True, type="primary"):
                st.session_state.page = "analysis"
                st.rerun()
        with col_nav2:
            if st.button("📋 Riwayat", use_container_width=True):
                st.session_state.page = "history"
                st.rerun()
        with col_nav3:
            if st.button("📈 Statistik", use_container_width=True):
                st.session_state.page = "stats"
                st.rerun()
        with col_nav4:
            if st.button("👤 Profil", use_container_width=True):
                st.session_state.page = "profile"
                st.rerun()
                
    except Exception as e:
        st.error(f"Error di home page: {str(e)}")
        if st.button("Kembali ke Login"):
            logout()

# -------------------------
# ANALYSIS PAGE (FIXED)
# -------------------------
def analysis_page():
    """Daily nutrition analysis page"""
    try:
        st.title("📊 Analisis Asupan Harian")
        
        # Date selector
        col_date1, col_date2 = st.columns([2, 1])
        with col_date1:
            selected_date = st.date_input(
                "Pilih Tanggal",
                value=datetime.now(),
                max_value=datetime.now()
            )
            st.session_state.selected_date = selected_date.strftime("%Y-%m-%d")
        
        with col_date2:
            if st.button("🏠 Kembali ke Home"):
                st.session_state.page = "home"
                st.rerun()
        
        st.markdown("---")
        
        # Get daily summary
        try:
            daily_summary = db.get_daily_nutrition_summary(
                st.session_state.user_id, 
                st.session_state.selected_date
            )
        except:
            daily_summary = {}
        
        # Get user profile for targets
        user_profile = db.get_user_profile(st.session_state.user_id)
        daily_needs = calculate_daily_needs(user_profile)
        
        # Ensure all keys exist
        default_summary = {
            'total_calories': 0, 'total_protein': 0, 'total_fat': 0, 'total_carbs': 0,
            'total_fiber': 0, 'total_sugar': 0, 'total_sodium': 0,
            'total_water': 0, 'total_exercise': 0, 'food_count': 0
        }
        
        for key in default_summary:
            if key not in daily_summary:
                daily_summary[key] = default_summary[key]
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            try:
                cal_percent = min(daily_summary['total_calories'] / daily_needs['target_calories'] * 100, 100)
            except:
                cal_percent = 0
            st.metric("🔥 Kalori", 
                     f"{int(daily_summary['total_calories'])}",
                     f"{cal_percent:.0f}% dari target")
        
        with col2:
            try:
                protein_percent = min(daily_summary['total_protein'] / daily_needs['target_protein'] * 100, 100)
            except:
                protein_percent = 0
            st.metric("🥩 Protein",
                     f"{int(daily_summary['total_protein'])}g",
                     f"{protein_percent:.0f}% dari target")
        
        with col3:
            try:
                fat_percent = min(daily_summary['total_fat'] / daily_needs['target_fat'] * 100, 100)
            except:
                fat_percent = 0
            st.metric("🥑 Lemak",
                     f"{int(daily_summary['total_fat'])}g",
                     f"{fat_percent:.0f}% dari target")
        
        with col4:
            try:
                carbs_percent = min(daily_summary['total_carbs'] / daily_needs['target_carbs'] * 100, 100)
            except:
                carbs_percent = 0
            st.metric("🍞 Karbohidrat",
                     f"{int(daily_summary['total_carbs'])}g",
                     f"{carbs_percent:.0f}% dari target")
        
        # Macronutrient pie chart
        if daily_summary.get('total_calories', 0) > 0:
            st.subheader("🍽️ Distribusi Makronutrien")
            
            protein_cal = daily_summary.get('total_protein', 0) * 4
            fat_cal = daily_summary.get('total_fat', 0) * 9
            carbs_cal = daily_summary.get('total_carbs', 0) * 4
            total_cal = protein_cal + fat_cal + carbs_cal
            
            if total_cal > 0:
                fig = go.Figure(data=[
                    go.Pie(
                        labels=['Protein', 'Lemak', 'Karbohidrat'],
                        values=[protein_cal, fat_cal, carbs_cal],
                        hole=0.3,
                        marker_colors=['#4ECDC4', '#FFD166', '#06D6A0']
                    )
                ])
                fig.update_layout(height=300, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
        
        # Detailed breakdown
        st.subheader("📋 Detail Nutrisi")
        
        col_details1, col_details2, col_details3 = st.columns(3)
        
        with col_details1:
            st.write("**Nutrisi Utama**")
            st.metric("Kalori", f"{int(daily_summary['total_calories'])} kcal")
            st.metric("Protein", f"{int(daily_summary['total_protein'])} g")
            st.metric("Lemak", f"{int(daily_summary['total_fat'])} g")
            st.metric("Karbohidrat", f"{int(daily_summary['total_carbs'])} g")
        
        with col_details2:
            st.write("**Nutrisi Tambahan**")
            st.metric("Serat", f"{int(daily_summary['total_fiber'])} g")
            st.metric("Gula", f"{int(daily_summary['total_sugar'])} g")
            st.metric("Natrium", f"{int(daily_summary['total_sodium'])} mg")
        
        with col_details3:
            st.write("**Aktivitas**")
            st.metric("Air", f"{daily_summary['total_water']} ml")
            st.metric("Olahraga", f"{daily_summary['total_exercise']} mnt")
            st.metric("Jumlah Makanan", daily_summary['food_count'])
        
        # Get individual entries
        try:
            daily_entries = db.get_daily_entries(st.session_state.user_id, st.session_state.selected_date)
        except:
            daily_entries = []
        
        if daily_entries:
            st.subheader("🍽️ Detail Makanan")
            for entry in daily_entries:
                with st.expander(f"{entry.get('food_name', 'Unknown')} - {entry.get('portion_grams', 0)}g"):
                    col_entry1, col_entry2 = st.columns(2)
                    with col_entry1:
                        st.write(f"**Kalori:** {entry.get('calories', 0)} kcal")
                        st.write(f"**Protein:** {entry.get('protein', 0)} g")
                        st.write(f"**Lemak:** {entry.get('fat', 0)} g")
                        st.write(f"**Karbo:** {entry.get('carbs', 0)} g")
                    with col_entry2:
                        created_at = entry.get('created_at', '')
                        if created_at and len(created_at) > 16:
                            st.write(f"**Waktu:** {created_at[11:16]}")
                        else:
                            st.write(f"**Waktu:** Tidak diketahui")
                        st.write(f"**Air:** {entry.get('water_ml', 0)} ml")
                        st.write(f"**Olahraga:** {entry.get('exercise_min', 0)} mnt")
                    
                    # Delete button
                    entry_id = entry.get('id', '')
                    if entry_id and st.button(f"Hapus {entry.get('food_name', 'item')}", key=f"delete_{entry_id}"):
                        try:
                            if db.delete_entry(st.session_state.user_id, entry_id):
                                st.success(f"{entry.get('food_name', 'Item')} dihapus!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error menghapus: {str(e)}")
        
        # Recommendations
        st.markdown("---")
        st.subheader("💡 Rekomendasi")
        
        recommendations = []
        
        try:
            if daily_summary['total_calories'] < daily_needs['target_calories'] * 0.8:
                recommendations.append("🔥 Tambah asupan kalori untuk memenuhi target harian")
        except:
            pass
        
        try:
            if daily_summary['total_protein'] < daily_needs['target_protein'] * 0.8:
                recommendations.append("🥩 Konsumsi lebih banyak protein dari daging, ikan, atau kacang-kacangan")
        except:
            pass
        
        try:
            if daily_summary['total_water'] < daily_needs['target_water'] * 0.8:
                recommendations.append("💧 Minum lebih banyak air sepanjang hari")
        except:
            pass
        
        try:
            if daily_summary['total_fiber'] < daily_needs['target_fiber'] * 0.8:
                recommendations.append("🌾 Tambah serat dari sayuran dan buah-buahan")
        except:
            pass
        
        try:
            if daily_summary['total_sugar'] > daily_needs['target_sugar'] * 1.2:
                recommendations.append("🍬 Kurangi konsumsi gula tambahan")
        except:
            pass
        
        try:
            if daily_summary['total_exercise'] < 30:
                recommendations.append("🏃 Lakukan aktivitas fisik minimal 30 menit per hari")
        except:
            pass
        
        if recommendations:
            for rec in recommendations:
                st.info(rec)
        else:
            st.success("🎉 Asupan nutrisi Anda sudah baik! Pertahankan!")
        
        st.markdown("---")
        if st.button("🏠 Kembali ke Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
            
    except Exception as e:
        st.error(f"Error di analisis page: {str(e)}")
        if st.button("Kembali ke Home"):
            st.session_state.page = "home"
            st.rerun()

# -------------------------
# HISTORY PAGE (FIXED)
# -------------------------
def history_page():
    """Food history page"""
    try:
        st.title("📋 Riwayat Makanan")
        
        # Date range selector
        col_date1, col_date2, col_date3 = st.columns([2, 2, 1])
        
        with col_date1:
            start_date = st.date_input(
                "Dari Tanggal",
                value=datetime.now() - timedelta(days=7)
            )
        
        with col_date2:
            end_date = st.date_input(
                "Sampai Tanggal",
                value=datetime.now()
            )
        
        with col_date3:
            st.write("")
            if st.button("🏠 Home"):
                st.session_state.page = "home"
                st.rerun()
        
        st.markdown("---")
        
        # Get entries
        try:
            entries = db.get_entries_by_date_range(
                st.session_state.user_id,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
        except:
            entries = []
        
        if not entries:
            st.info("📭 Tidak ada data makanan pada rentang tanggal ini")
            if st.button("🏠 Kembali ke Home"):
                st.session_state.page = "home"
                st.rerun()
            return
        
        # Group by date
        entries_by_date = {}
        for entry in entries:
            date = entry.get('date', 'Unknown')
            if date not in entries_by_date:
                entries_by_date[date] = []
            entries_by_date[date].append(entry)
        
        # Display entries grouped by date
        for date in sorted(entries_by_date.keys(), reverse=True):
            try:
                date_total = sum(e.get('calories', 0) for e in entries_by_date[date])
            except:
                date_total = 0
            
            with st.expander(f"📅 {date} - {len(entries_by_date[date])} makanan - {int(date_total)} kalori"):
                for entry in entries_by_date[date]:
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{entry.get('food_name', 'Unknown')}** ({entry.get('portion_grams', 0)}g)")
                    with col2:
                        calories = entry.get('calories', 0)
                        protein = entry.get('protein', 0)
                        st.write(f"{int(calories)} kcal | {int(protein)}g protein")
                    with col3:
                        entry_id = entry.get('id', '')
                        if entry_id and st.button("🗑️", key=f"del_{entry_id}"):
                            try:
                                if db.delete_entry(st.session_state.user_id, entry_id):
                                    st.success("Dihapus!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error menghapus: {str(e)}")
                    
                    created_at = entry.get('created_at', '')
                    time_str = created_at[11:16] if created_at and len(created_at) > 16 else 'Unknown'
                    st.caption(f"Waktu: {time_str} | Air: {entry.get('water_ml', 0)}ml | Olahraga: {entry.get('exercise_min', 0)}mnt")
                    st.divider()
        
        # Summary statistics
        st.markdown("---")
        st.subheader("📊 Ringkasan Periode")
        
        try:
            total_cal = sum(float(e.get('calories', 0)) for e in entries)
        except:
            total_cal = 0
        
        try:
            total_pro = sum(float(e.get('protein', 0)) for e in entries)
        except:
            total_pro = 0
        
        try:
            total_fat = sum(float(e.get('fat', 0)) for e in entries)
        except:
            total_fat = 0
        
        try:
            total_carbs = sum(float(e.get('carbs', 0)) for e in entries)
        except:
            total_carbs = 0
        
        try:
            total_water = sum(float(e.get('water_ml', 0)) for e in entries)
        except:
            total_water = 0
        
        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
        with col_sum1:
            st.metric("🔥 Total Kalori", f"{int(total_cal)}")
        with col_sum2:
            st.metric("🍽️ Jumlah Makanan", len(entries))
        with col_sum3:
            st.metric("📅 Hari", len(entries_by_date))
        with col_sum4:
            st.metric("💧 Total Air", f"{int(total_water)}ml")
        
        st.markdown("---")
        if st.button("🏠 Kembali ke Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
            
    except Exception as e:
        st.error(f"Error di history page: {str(e)}")
        if st.button("Kembali ke Home"):
            st.session_state.page = "home"
            st.rerun()

# -------------------------
# STATISTICS PAGE (CLEAN VERSION)
# -------------------------
def statistics_page():
    """Statistics page - Clean version without debug info"""
    try:
        st.title("📈 Statistik & Trend")
        
        # Time period selector
        period = st.selectbox(
            "Pilih Periode",
            ["7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir", "Semua Waktu"],
            index=0
        )
        
        # Calculate date range
        today = datetime.now()
        if period == "7 Hari Terakhir":
            days = 7
        elif period == "30 Hari Terakhir":
            days = 30
        elif period == "90 Hari Terakhir":
            days = 90
        else:
            days = 365 * 5  # 5 years
        
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        # Get summary from database
        summary = db.get_user_summary(st.session_state.user_id, start_date, end_date)
        
        # Jika tidak ada data
        if not summary or not summary.get('daily_summaries'):
            st.info("📊 Tidak ada data statistik untuk ditampilkan pada periode ini.")
            st.write("Mulai tambahkan makanan Anda untuk melihat statistik dan trend.")
            
            if st.button("➕ Tambah Makanan Sekarang"):
                st.session_state.page = "home"
                st.rerun()
            
            if st.button("🏠 Kembali ke Home"):
                st.session_state.page = "home"
                st.rerun()
            return
        
        # Key metrics
        st.subheader("📊 Ringkasan Periode")
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("📅 Hari", summary.get('total_days', 0))
        
        with col_stat2:
            st.metric("🍽️ Makanan", summary.get('total_entries', 0))
        
        with col_stat3:
            avg_cal = summary.get('avg_calories', 0)
            st.metric("🔥 Rata² Kalori", f"{int(avg_cal)}")
        
        with col_stat4:
            avg_water = summary.get('avg_water', 0)
            st.metric("💧 Rata² Air", f"{int(avg_water)}ml")
        
        st.markdown("---")
        
        # Create dataframe for charts
        daily_data = summary.get('daily_summaries', [])
        df = pd.DataFrame(daily_data)
        
        # Convert date column and sort
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
        
        
        
        # 1. TOP FOODS
        st.subheader("🏆 Makanan Paling Sering")
        
        try:
            # Get all entries for this period
            entries = db.get_entries_by_date_range(st.session_state.user_id, start_date, end_date)
            
            if entries:
                food_counts = {}
                for entry in entries:
                    food = entry.get('food_name', '').strip()
                    if food and food.lower() != 'unknown':
                        food_counts[food] = food_counts.get(food, 0) + 1
                
                if food_counts:
                    # Sort and get top 10
                    top_foods = sorted(food_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Ranking Makanan:**")
                        for i, (food, count) in enumerate(top_foods[:5], 1):
                            st.write(f"{i}. **{food}** - {count} kali")
                    
                    with col2:
                        if len(top_foods) > 5:
                            st.write("**Lanjutan:**")
                            for i, (food, count) in enumerate(top_foods[5:], 6):
                                st.write(f"{i}. **{food}** - {count} kali")
                    
                    # Create bar chart for top foods
                    if top_foods:
                        foods = [f[0][:15] + "..." if len(f[0]) > 15 else f[0] for f in top_foods[:8]]
                        counts = [f[1] for f in top_foods[:8]]
                        
                        fig_foods = go.Figure(data=[
                            go.Bar(
                                x=foods,
                                y=counts,
                                marker_color='#4ECDC4',
                                hovertemplate='<b>%{x}</b><br>%{y} kali<extra></extra>'
                            )
                        ])
                        
                        fig_foods.update_layout(
                            height=350,
                            title="Frekuensi Konsumsi Makanan",
                            xaxis_title="Makanan",
                            yaxis_title="Jumlah Konsumsi",
                            xaxis_tickangle=-45,
                            plot_bgcolor='white',
                            paper_bgcolor='white'
                        )
                        
                        st.plotly_chart(fig_foods, use_container_width=True)
                else:
                    st.info("Belum ada data makanan yang tercatat")
            else:
                st.info("Belum ada data makanan pada periode ini")
        except Exception as e:
            st.info("Data makanan tidak dapat ditampilkan")
        
        # 2. NUTRITION DISTRIBUTION PIE CHART
        st.subheader("📊 Distribusi Makronutrien Rata-rata")
        
        try:
            # Get average values from summary
            avg_protein = summary.get('avg_protein', 0)
            avg_fat = summary.get('avg_fat', 0)
            avg_carbs = summary.get('avg_carbs', 0)
            
            if avg_protein > 0 or avg_fat > 0 or avg_carbs > 0:
                # Calculate total for percentage
                total = avg_protein + avg_fat + avg_carbs
                
                if total > 0:
                    labels = ['Protein', 'Lemak', 'Karbohidrat']
                    values = [avg_protein, avg_fat, avg_carbs]
                    
                    fig_pie = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.4,
                        marker_colors=['#4ECDC4', '#FFD166', '#06D6A0'],
                        textinfo='label+percent',
                        hovertemplate='<b>%{label}</b><br>%{value:.1f}g (%{percent})<extra></extra>'
                    )])
                    
                    fig_pie.update_layout(
                        height=400,
                        showlegend=True,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        legend=dict(
                            yanchor="top",
                            y=0.99,
                            xanchor="left",
                            x=1.05
                        )
                    )
                    
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("Data makronutrien tidak mencukupi")
            else:
                st.info("Data rata-rata makronutrien tidak tersedia")
        except:
            st.info("Chart distribusi tidak dapat ditampilkan")
        
        # 3. RECOMMENDATIONS
        st.markdown("---")
        st.subheader("💡 Insight & Rekomendasi")
        
        try:
            recommendations = []
            
            # Check calorie intake
            avg_calories = summary.get('avg_calories', 0)
            if avg_calories < 1500:
                recommendations.append("🔥 **Tingkatkan asupan kalori**: Rata-rata kalori harian Anda di bawah 1500 kcal. Pertimbangkan untuk menambah porsi makan sehat.")
            elif avg_calories > 2500:
                recommendations.append("⚖️ **Perhatikan asupan kalori**: Rata-rata kalori harian Anda di atas 2500 kcal. Pertimbangkan untuk menyeimbangkan porsi makan.")
            
            # Check water intake
            avg_water = summary.get('avg_water', 0)
            if avg_water < 1500:
                recommendations.append("💧 **Tingkatkan konsumsi air**: Rata-rata asupan air Anda di bawah 1500 ml/hari. Usahakan minum minimal 8 gelas per hari.")
            
            # Check food variety
            if 'food_counts' in locals() and len(food_counts) < 10:
                recommendations.append("🍎 **Tingkatkan variasi makanan**: Coba konsumsi lebih banyak jenis makanan untuk mendapatkan nutrisi yang beragam.")
            
            if recommendations:
                for rec in recommendations:
                    st.info(rec)
            else:
                st.success("🎉 **Asupan nutrisi Anda sudah baik!** Pertahankan pola makan sehat dan seimbang.")
                
        except:
            st.info("Analisis rekomendasi tidak tersedia")
        
        # Footer navigation
        st.markdown("---")
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("📊 Lihat Analisis Harian", use_container_width=True):
                st.session_state.page = "analysis"
                st.rerun()
        with col_nav2:
            if st.button("🏠 Kembali ke Home", use_container_width=True, type="primary"):
                st.session_state.page = "home"
                st.rerun()
                
    except Exception as e:
        st.error("Terjadi kesalahan saat memuat halaman statistik.")
        
        if st.button("🔄 Coba Muat Ulang"):
            st.rerun()
        if st.button("🏠 Kembali ke Home"):
            st.session_state.page = "home"
            st.rerun()

# -------------------------
# PROFILE PAGE (FIXED)
# -------------------------
def profile_page():
    """User profile page"""
    try:
        st.title("👤 Profil Pengguna")
        
        # Get user profile
        user_profile = db.get_user_profile(st.session_state.user_id)
        
        if not user_profile:
            st.error("Profil tidak ditemukan")
            if st.button("🏠 Kembali ke Home"):
                st.session_state.page = "home"
                st.rerun()
            return
        
        col_prof1, col_prof2 = st.columns([2, 1])
        
        with col_prof1:
            st.subheader("📋 Informasi Profil")
            st.write(f"**Nama:** {user_profile.get('name', 'N/A')}")
            st.write(f"**Email:** {user_profile.get('email', 'N/A')}")
            st.write(f"**Berat:** {user_profile.get('weight', 'N/A')} kg")
            st.write(f"**Tinggi:** {user_profile.get('height', 'N/A')} cm")
            st.write(f"**Usia:** {user_profile.get('age', 'N/A')} tahun")
            st.write(f"**Aktivitas:** {user_profile.get('activity_level', 'N/A')}")
            st.write(f"**Target:** {user_profile.get('goal', 'N/A')}")
        
        with col_prof2:
            st.subheader("🎯 Target Harian")
            try:
                daily_needs = calculate_daily_needs(user_profile)
                st.write(f"**Kalori:** {daily_needs['target_calories']} kcal")
                st.write(f"**Protein:** {daily_needs['target_protein']} g")
                st.write(f"**Lemak:** {daily_needs['target_fat']} g")
                st.write(f"**Karbo:** {daily_needs['target_carbs']} g")
                st.write(f"**Air:** {daily_needs['target_water']} ml")
            except:
                st.write("Target tidak dapat dihitung")
        
        st.markdown("---")
        st.subheader("⚙️ Edit Profil")
        
        with st.form("edit_profile_form"):
            col_edit1, col_edit2 = st.columns(2)
            
            with col_edit1:
                new_name = st.text_input("Nama", value=user_profile.get('name', ''))
                new_weight = st.number_input("Berat (kg)", 
                                           value=float(user_profile.get('weight', 65)), 
                                           min_value=30.0, max_value=200.0, step=0.1)
                new_age = st.number_input("Usia", 
                                        value=user_profile.get('age', 25), 
                                        min_value=10, max_value=100, step=1)
            
            with col_edit2:
                new_height = st.number_input("Tinggi (cm)", 
                                           value=float(user_profile.get('height', 170)), 
                                           min_value=100.0, max_value=250.0, step=0.1)
                
                # Activity level
                activity_options = ['sedentary', 'light', 'medium', 'active', 'very_active']
                current_activity = user_profile.get('activity_level', 'medium')
                activity_index = activity_options.index(current_activity) if current_activity in activity_options else 2
                new_activity = st.selectbox("Level Aktivitas", activity_options, index=activity_index)
                
                # Goal
                goal_options = ['maintain', 'lose', 'gain']
                current_goal = user_profile.get('goal', 'maintain')
                goal_index = goal_options.index(current_goal) if current_goal in goal_options else 0
                new_goal = st.selectbox("Target", goal_options, index=goal_index)
            
            if st.form_submit_button("💾 Simpan Perubahan", type="primary"):
                updates = {
                    'name': new_name,
                    'weight': new_weight,
                    'height': new_height,
                    'age': new_age,
                    'activity_level': new_activity,
                    'goal': new_goal
                }
                
                try:
                    if db.update_user_profile(st.session_state.user_id, **updates):
                        st.success("✅ Profil berhasil diperbarui!")
                        st.rerun()
                    else:
                        st.error("❌ Gagal memperbarui profil")
                except Exception as e:
                    st.error(f"Error memperbarui profil: {str(e)}")
        
        st.markdown("---")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🏠 Kembali ke Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
        with col_btn2:
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                logout()
                
    except Exception as e:
        st.error(f"Error di profile page: {str(e)}")
        if st.button("Kembali ke Home"):
            st.session_state.page = "home"
            st.rerun()

# -------------------------
# SIDEBAR NAVIGATION
# -------------------------
st.sidebar.title("🍎 NutriScanAI")

if st.session_state.user:
    try:
        user_profile = db.get_user_profile(st.session_state.user_id)
        if user_profile:
            st.sidebar.subheader(f"👋 {user_profile.get('name', 'User')}")
    except:
        st.sidebar.subheader("👋 User")
    
    st.sidebar.markdown("📍 **Navigasi**")
    
    nav_options = [
        ("🏠 Home", "home"),
        ("📊 Analisis", "analysis"),
        ("📋 Riwayat", "history"),
        ("📈 Statistik", "stats"),
        ("👤 Profil", "profile"),
    ]
    
    for label, page in nav_options:
        if st.sidebar.button(label, use_container_width=True, key=f"nav_{page}"):
            st.session_state.page = page
            st.rerun()
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🚪 Logout", type="secondary", use_container_width=True):
        logout()

else:
    st.sidebar.info("🔐 Silakan login untuk menggunakan aplikasi")

# System info
st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Info Sistem"):
    try:
        stats = db.get_database_stats()
        st.caption(f"**Pengguna:** {stats.get('total_users', 0)}")
        st.caption(f"**Entri:** {stats.get('total_entries', 0)}")
    except:
        st.caption("**Database:** Tidak tersedia")
    
    # Check if model exists
    model_exists = os.path.exists("best_food_effnet.keras")
    st.caption(f"**Model AI:** {'✅ Loaded' if st.session_state.model_available else '❌ Not found'}")
    
    # Check API status
    api_status = "✅ Active" if st.session_state.api_available else "❌ Inactive"
    st.caption(f"**DeepSeek API:** {api_status}")

# About
st.sidebar.markdown("---")
st.sidebar.caption("""
**NutriScanAI v4.0 (Fixed)**

• 🧠 Klasifikasi Gambar: best_food_effnet.keras
• 📊 Analisis Nutrisi: DeepSeek AI
• 💾 Database: SQLite Local

📸 Fitur Unggulan:
- Upload foto makanan
- Analisis kamera real-time
- Tracking nutrisi harian
- Statistik & rekomendasi
""")

# -------------------------
# MAIN ROUTER
# -------------------------
if st.session_state.user is None:
    login_page()
else:
    # Define page handlers
    page_handlers = {
        "home": home_page,
        "analysis": analysis_page,
        "history": history_page,
        "stats": statistics_page,
        "profile": profile_page,
    }
    
    # Get handler or default to home
    handler = page_handlers.get(st.session_state.page, home_page)
    try:
        handler()
    except Exception as e:
        st.error(f"Error loading page: {str(e)}")
        if st.button("Kembali ke Home"):
            st.session_state.page = "home"
            st.rerun()
