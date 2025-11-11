import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import bcrypt
import whisper
from sklearn.preprocessing import LabelEncoder
import pytesseract
import google.generativeai as genai
from dotenv import load_dotenv
from streamlit_mic_recorder import mic_recorder
import numpy as np
from datetime import datetime, timedelta
import warnings
import re # Import the regex module for email validation
from PIL import Image

# Load the custom CSS
# Fix: Check if CSS file exists and handle missing file
def load_css():
    with open("styles.css") as f:
        
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Import dashboard manager and export manager
from dashboard_manager import dash_manager, saving_ui, report_generator
from export_sharing_manager import export_manager

# Import real-time alerts manager
from realtime_alerts_manager import realtime_manager

warnings.filterwarnings('ignore')

# Load environment variables from the .env file
load_dotenv()

# Add this line to explicitly set the path to your FFmpeg directory.
os.environ["PATH"] += os.pathsep + r"C:\Users\Vishwa\Desktop\v\dashboard-copy\dashboard-copy\dashboard\ffmpeg-master-latest-win64-gpl-shared\ffmpeg-master-latest-win64-gpl-shared\bin"

# Configure the Gemini API key from environment variables
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
else:
    st.error("Gemini API key not found. Please set it in your environment variables.")

# Set tesseract command path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- Constants ----------
USER_FILE = "users.json"
USER_DATA_DIR = "user_data"

# Create the user data directory if it doesn't exist
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

# Email regex pattern for validation
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


# ---------- Module 1: Authentication ----------
def load_users():
    """Loads user data from a JSON file."""
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    """Saves user data to a JSON file."""
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def register():
    """Handles new user registration with comprehensive email validation."""
    st.subheader("🔐 Register")
    new_user = st.text_input("Username", placeholder="Enter your username")
    new_pass = st.text_input("Password", type="password", placeholder="Enter your password")
    confirm_pass = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
    new_email = st.text_input("Email", placeholder="Enter your email address")
    role = st.selectbox("Select Role", ["Analyst", "Viewer"])
    
    # Validation logic
    if st.button("Register", type="primary"):
        valid = True
        errors = []
        
        # 1. Check for empty fields
        if not new_user.strip():
            errors.append("❌ Username cannot be empty.")
            valid = False
        if not new_pass:
            errors.append("❌ Password cannot be empty.")
            valid = False
        if not confirm_pass:
            errors.append("❌ Please confirm your password.")
            valid = False
        if not new_email.strip():
            errors.append("❌ Email cannot be empty.")
            valid = False
        
        # 2. Username validation
        if new_user.strip():
            if len(new_user.strip()) < 3:
                errors.append("❌ Username must be at least 3 characters long.")
                valid = False
            if len(new_user.strip()) > 20:
                errors.append("❌ Username cannot exceed 20 characters.")
                valid = False
            if not re.match(r'^[a-zA-Z0-9_]+$', new_user.strip()):
                errors.append("❌ Username can only contain letters, numbers, and underscores.")
                valid = False
        
        # 3. Password validation (simplified - only 6 characters required)
        if new_pass:
            if len(new_pass) < 6:
                errors.append("❌ Password must be at least 6 characters long.")
                valid = False
            
            # Check password confirmation
            if new_pass != confirm_pass:
                errors.append("❌ Passwords do not match.")
                valid = False
        
        # 4. Enhanced email validation
        if new_email.strip():
            email = new_email.strip().lower()
            
            # Basic regex validation
            if not re.match(EMAIL_REGEX, email):
                errors.append("❌ Please enter a valid email address (e.g., user@example.com).")
                valid = False
            else:
                # Additional email validation checks
                local_part, domain = email.split('@')
                
                # Check local part (before @)
                if len(local_part) < 1:
                    errors.append("❌ Email local part cannot be empty.")
                    valid = False
                if len(local_part) > 64:
                    errors.append("❌ Email local part is too long (max 64 characters).")
                    valid = False
                if local_part.startswith('.') or local_part.endswith('.'):
                    errors.append("❌ Email local part cannot start or end with a dot.")
                    valid = False
                if '..' in local_part:
                    errors.append("❌ Email local part cannot contain consecutive dots.")
                    valid = False
                
                # Check domain part
                if len(domain) < 4:
                    errors.append("❌ Email domain is invalid.")
                    valid = False
                if '.' not in domain:
                    errors.append("❌ Email domain must contain a dot.")
                    valid = False
                
                # Check for valid domain format
                domain_parts = domain.split('.')
                if len(domain_parts) < 2:
                    errors.append("❌ Email domain format is invalid.")
                    valid = False
                else:
                    tld = domain_parts[-1]
                    if len(tld) < 2:
                        errors.append("❌ Email domain TLD is too short.")
                        valid = False
                
                # Check for common disposable email domains
                disposable_domains = [
                    'tempmail.com', 'throwaway.com', 'fake.com', 'guerrillamail.com', 
                    'mailinator.com', '10minutemail.com', 'yopmail.com', 'trashmail.com',
                    'disposable.com', 'temp-mail.org', 'getairmail.com', 'maildrop.cc'
                ]
                if any(domain.endswith(disposable_domain) for disposable_domain in disposable_domains):
                    errors.append("❌ Disposable email addresses are not allowed.")
                    valid = False
                
                # Check for common email providers (you can expand this list)
                common_providers = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 
                                  'icloud.com', 'protonmail.com', 'aol.com', 'zoho.com']
                if not any(domain.endswith(provider) for provider in common_providers):
                    st.warning("⚠️ Please use a common email provider for better deliverability")
        
        # 5. Check if username/email already exists
        if valid:
            users = load_users()
            
            # Check if trying to register as default admin
            default_admins = ["Vishwa", "Veera", "Roja", "Pavithra"]
            if new_user.strip() in default_admins:
                errors.append("❌ This username is reserved. Please choose a different username.")
                valid = False
            elif new_user.strip() in users:
                errors.append("❌ Username already exists! Please choose a different one.")
                valid = False
            else:
                # Check if email is already registered
                existing_emails = [user_data.get('email', '').lower() for user_data in users.values()]
                if new_email.strip().lower() in existing_emails:
                    errors.append("❌ Email address is already registered. Please use a different email or login.")
                    valid = False
        
        # Display all errors at once
        if errors:
            for error in errors:
                st.error(error)
        else:
            # Proceed with registration only if all fields are valid
            try:
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                users[new_user.strip()] = {
                    "password": hashed, 
                    "email": new_email.strip().lower(), 
                    "role": role,
                    "created_at": datetime.now().isoformat(),
                    "last_login": None
                }
                save_users(users)
                
                # Send registration email
                dash_manager.send_registration_email(new_email.strip().lower(), new_user.strip())
                
                st.success("🎉 Registered successfully! Please login with your new credentials.")
                st.balloons()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Registration failed: {str(e)}")

def login():
    """Handles user login with input validation."""
    st.subheader("🔑 Login")
    username = st.text_input("Username", placeholder="Enter your username")
    password = st.text_input("Password", type="password", placeholder="Enter your password")
    
  
    
    # Validation logic
    if st.button("Login", type="primary"):
        valid = True
        errors = []
        
        # 1. Check for empty fields
        if not username.strip():
            errors.append("❌ Username field is required.")
            valid = False
        if not password:
            errors.append("❌ Password field is required.")
            valid = False
        
        # 2. Username format validation
        if username.strip() and not re.match(r'^[a-zA-Z0-9_]+$', username.strip()):
            errors.append("❌ Invalid username format.")
            valid = False
        
        # 3. Proceed with login only if fields are valid
        if valid:
            users = load_users()
            
            # Check if user exists in the database
            if username.strip() in users:
                user_data = users[username.strip()]
                
                # Verify password
                if bcrypt.checkpw(password.encode(), user_data["password"].encode()):
                    # Successful login
                    st.session_state.authenticated = True
                    st.session_state.username = username.strip()
                    st.session_state.role = user_data["role"]
                    
                    # Update last login time
                    user_data["last_login"] = datetime.now().isoformat()
                    save_users(users)
                    
                    # Send login email
                    user_email = user_data["email"]
                    dash_manager.send_login_email(user_email, username.strip())
                    
                    st.success("✅ Login successful! Redirecting...")
                    st.rerun()
                else:
                    errors.append("❌ Invalid password. Please try again.")
            else:
                errors.append("❌ Username not found. Please check your username or register.")
        
        # Display all errors
        for error in errors:
            st.error(error)
def create_default_admins():
    """Creates default admin users if they don't exist."""
    users = load_users()
    
    default_admins = {
        "Vishwa": {
            "password": bcrypt.hashpw("200425".encode(), bcrypt.gensalt()).decode(), 
            "email": "vishwa@gmail.com", 
            "role": "Admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None
        },
        "Veera": {
            "password": bcrypt.hashpw("200425".encode(), bcrypt.gensalt()).decode(), 
            "email": "aakashveera12305@gmail.com", 
            "role": "Admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None
        },
        "Roja": {
            "password": bcrypt.hashpw("200425".encode(), bcrypt.gensalt()).decode(), 
            "email": "rojajanardhanan3023@gmail.com", 
            "role": "Admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None
        },
        "Pavithra": {
            "password": bcrypt.hashpw("200425".encode(), bcrypt.gensalt()).decode(), 
            "email": "pavithracharu20@gmail.com", 
            "role": "Admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
    }
    
    # Add default admins if they don't exist
    admins_created = 0
    for username, user_data in default_admins.items():
        if username not in users:
            users[username] = user_data
            admins_created += 1
    
    if admins_created > 0:
        save_users(users)
    
    return admins_created
def auth_panel():
    """Displays the login/register panel with image layout if not authenticated."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "role" not in st.session_state:
        st.session_state.role = None

    # Inject CSS at the TOP for full screen layout
    st.markdown("""
    <style>
    /* Remove all spacing and padding from main container */
    .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
    }
    
    /* Remove padding from the main app container */
    .appview-container .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
    }

    /* Remove column gaps and make columns full width */
    [data-testid="column"] {
        padding: 0rem !important;
        gap: 0rem !important;
    }
    
    /* Center image in second column */
    [data-testid="column"]:nth-child(2) .stImage {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        height: 80% !important;
        padding: 2rem !important;
    }

    [data-testid="column"]:nth-child(2) .stImage img {
        border-radius: 20px !important;
        animation: centeredFloat 4s ease-in-out infinite !important;
        border: 3px solid transparent !important;
        background: linear-gradient(45deg, #00ff99, #7B00FF, #FFD700) !important;
        background-size: 300% 300% !important;
        padding: 10px !important;
        max-width: 85% !important;
        height: auto !important;
        display: block !important;
        margin: 0 auto !important;
        box-shadow: 
            0 0 50px rgba(0, 255, 153, 0.4),
            0 0 80px rgba(123, 0, 255, 0.3),
            0 0 120px rgba(255, 215, 0, 0.2) !important;
    }

    @keyframes centeredFloat {
        0%, 100% {
            transform: translateY(0px) rotate(0deg) scale(1);
            box-shadow: 
                0 0 50px rgba(0, 255, 153, 0.4),
                0 0 80px rgba(123, 0, 255, 0.3);
            background-position: 0% 50%;
        }
        25% {
            transform: translateY(-15px) rotate(2deg) scale(1.03);
            box-shadow: 
                0 0 60px rgba(255, 215, 0, 0.5),
                0 0 100px rgba(123, 0, 255, 0.4);
        }
        50% {
            transform: translateY(-8px) rotate(-2deg) scale(1.02);
            box-shadow: 
                0 0 70px rgba(123, 0, 255, 0.6),
                0 0 120px rgba(0, 255, 153, 0.4);
            background-position: 100% 50%;
        }
        75% {
            transform: translateY(-12px) rotate(1deg) scale(1.025);
            box-shadow: 
                0 0 55px rgba(0, 255, 153, 0.5),
                0 0 90px rgba(255, 215, 0, 0.4);
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # Use full width columns with minimal gap
    col1, col2 = st.columns([5, 4], gap="small")
    
    with col1:
        # Create a styled container for the form
        form_container = st.container()
        with form_container:
            # Authentication form content
            menu = ["Login", "Register"]
            choice = st.selectbox("Choose option", menu)
            
            if choice == "Login":
                login()
            else:
                register()
    
    with col2:
        # Display the dancing animated image
        try:
            # Check if image exists in current directory or images subfolder
            image_path = None
            if os.path.exists("frontend.png"):
                image_path = "frontend.png"
            elif os.path.exists("images/frontend.png"):
                image_path = "images/frontend.png"
            
            if image_path and os.path.exists(image_path):
                image = Image.open(image_path)
                st.image(image, use_container_width=True)
                
            else:
                # Show animated placeholder with enhanced glow
                st.markdown("""
                <div style='
                    width: 80%; 
                    height: 300px; 
                    background: linear-gradient(45deg, #00ff99, #7B00FF, #FFD700);
                    border-radius: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    animation: centeredFloat 4s ease-in-out infinite;
                    border: 3px solid transparent;
                    background-size: 300% 300%;
                    box-shadow: 
                        0 0 50px rgba(0, 255, 153, 0.4),
                        0 0 80px rgba(123, 0, 255, 0.3),
                        0 0 120px rgba(255, 215, 0, 0.2);
                    margin: 0 auto;
                '>
                    <span style='
                        color: white; 
                        font-size: 1.8rem; 
                        font-weight: bold; 
                        font-family: "Orbitron", sans-serif;
                        text-shadow: 0 0 20px rgba(255,255,255,0.8);
                    '>🚀 Inferaboard</span>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            # Show animated placeholder as fallback with enhanced glow
            st.markdown("""
            <div style='
                width: 100%; 
                height: 400px; 
                background: linear-gradient(45deg, #00ff99, #7B00FF, #FFD700);
                border-radius: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                animation: centeredFloat 4s ease-in-out infinite;
                border: 3px solid transparent;
                background-size: 300% 300%;
                box-shadow: 
                    0 0 50px rgba(0, 255, 153, 0.4),
                    0 0 80px rgba(123, 0, 255, 0.3),
                    0 0 120px rgba(255, 215, 0, 0.2);
                margin: 0 auto;
            '>
                <span style='
                    color: white; 
                    font-size: 1.8rem; 
                    font-weight: bold; 
                    font-family: "Orbitron", sans-serif;
                    text-shadow: 0 0 20px rgba(255,255,255,0.8);
                '>📊 Dashboard Preview</span>
            </div>
            """, unsafe_allow_html=True)
# ---------- Module 2: Data Upload and Loading ----------
def save_user_data(username, df):
    """Saves a dataframe for a specific user."""
    file_path = os.path.join(USER_DATA_DIR, f"{username}.csv")
    df.to_csv(file_path, index=False)

def load_user_data(username):
    """Loads a dataframe for a specific user."""
    file_path = os.path.join(USER_DATA_DIR, f"{username}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return None

def upload_data(username):
    """Handles data upload for a specific user, supporting multiple file types including images."""
    st.subheader(f"📤 Upload Dataset for {username}")
    uploaded_file = st.file_uploader(
        f"Choose a data file for {username}",
        type=["csv", "xlsx", "xls", "html", "jpg", "jpeg", "png"],
        key=f"uploader_{username}"
    )
    
    if uploaded_file is not None:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = None
        
        try:
            if file_extension == 'csv':
                df = pd.read_csv(uploaded_file)
            elif file_extension in ['xlsx', 'xls']:
                try:
                    df = pd.read_excel(uploaded_file)
                except ImportError:
                    st.error("The 'openpyxl' library is required to read Excel files. Please install it using 'pip install openpyxl'.")
                    return
            elif file_extension == 'html':
                # read_html returns a list of DataFrames, we'll take the first one
                html_data = pd.read_html(uploaded_file)
                if html_data:
                    df = html_data[0]
                else:
                    st.error("No tables found in the HTML file.")
                    return
            elif file_extension in ['jpg', 'jpeg', 'png']:
                try:
                    from PIL import Image
                    import pytesseract
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Image", use_column_width=True)
                    text_data = pytesseract.image_to_string(image)
                    
                    st.write("---")
                    st.subheader("Extracted Text from Image:")
                    st.text(text_data)
                    
                    st.warning("Automatic conversion of OCR text to a structured table is a complex task. The extracted text is displayed above. You can manually copy and paste it into a spreadsheet or use more advanced parsing techniques.")
                    return
                except ImportError as e:
                    st.error(f"Required Python libraries for image OCR are missing. Please install them: pip install Pillow pytesseract.")
                    return
                except pytesseract.TesseractNotFoundError:
                    st.error("Tesseract is not installed or it's not in your PATH. Please install Tesseract-OCR from the official Tesseract-OCR GitHub page.")
                    return
            else:
                st.error("Unsupported file type. Please upload a CSV, Excel, HTML, or an image file.")
                return

            st.session_state[f"dataframe_{username}"] = df
            save_user_data(username, df)
            st.success(f"File uploaded successfully for {username}!")
            st.write("Raw Data Preview:", df.head())
            return df
        
        except Exception as e:
            st.error(f"Error reading the file: {e}")
    
    return None

# ---------- Live Data Connection Module ----------
def connect_live_data(username):
    """Handles live data connections for various sources."""
    st.subheader(f"🔗 Connect to Live Data Source")
    connection_type = st.selectbox("Choose a data connection", ["None", "Google Sheets", "REST API", "SQL Database"])
    df = None

    if connection_type == "Google Sheets":
        sheet_url = st.text_input("Paste your Google Sheets URL (must be publicly accessible)")
        if st.button("Load Google Sheet"):
            try:
                # Extract the sheet ID from the URL
                if "/d/" in sheet_url:
                    sheet_id = sheet_url.split("/d/")[1].split("/")[0]
                else:
                    sheet_id = sheet_url
                
                # Construct the CSV export URL
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                
                # Read the CSV data
                df = pd.read_csv(csv_url)
                st.success("Data loaded from Google Sheets!")
                st.write("Data Preview:", df.head())
                save_user_data(username, df)
                st.session_state[f"dataframe_{username}"] = df
                return df
            except Exception as e:
                st.error(f"Google Sheets connection failed: {e}")

    elif connection_type == "REST API":
        api_url = st.text_input("Enter your REST API endpoint")
        if st.button("Fetch from API"):
            try:
                import requests
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different JSON response formats
                    if isinstance(data, list):
                        df = pd.DataFrame(data)
                    elif isinstance(data, dict):
                        # Try to find a key that contains a list of items
                        for key, value in data.items():
                            if isinstance(value, list):
                                df = pd.DataFrame(value)
                                break
                        if df is None:
                            # If no list found, create a DataFrame from the dict
                            df = pd.DataFrame([data])
                    
                    st.success("Data loaded from REST API!")
                    st.write("Data Preview:", df.head())
                    save_user_data(username, df)
                    st.session_state[f"dataframe_{username}"] = df
                    return df
                else:
                    st.error(f"API request failed with status code: {response.status_code}")
            except Exception as e:
                st.error(f"REST API connection failed: {e}")

    elif connection_type == "SQL Database":
        st.markdown("Fill in your database connection details below:")
        db_type = st.selectbox("Database Type", ["MySQL", "PostgreSQL", "SQLite"])
        host = st.text_input("Host")
        dbname = st.text_input("Database Name")
        user = st.text_input("Username")
        password = st.text_input("Password", type="password")
        query = st.text_area("SQL Query", "SELECT * FROM table_name LIMIT 1000")
        
        if st.button("Connect to SQL"):
            try:
                if db_type == "MySQL":
                    import pymysql
                    connection = pymysql.connect(
                        host=host,
                        user=user,
                        password=password,
                        database=dbname
                    )
                elif db_type == "PostgreSQL":
                    import psycopg2
                    connection = psycopg2.connect(
                        host=host,
                        database=dbname,
                        user=user,
                        password=password
                    )
                elif db_type == "SQLite":
                    import sqlite3
                    connection = sqlite3.connect(dbname)
                
                df = pd.read_sql(query, connection)
                connection.close()
                
                st.success("Data loaded from SQL Database!")
                st.write("Data Preview:", df.head())
                save_user_data(username, df)
                st.session_state[f"dataframe_{username}"] = df
                return df
            except Exception as e:
                st.error(f"SQL connection failed: {e}")

    return df

# ---------- Module 3: Data Preprocessing ----------
def preprocess_data(df):
    """Performs data cleaning and encoding."""
    st.subheader("🧹 Data Preprocessing")
    
    if df is None:
        st.warning("No data to preprocess. Please upload a file first.")
        return None

    processed_df = df.copy()
    
    # 🔹 NEW STEP: Try to convert any column with "date" in its name into datetime
    for col in processed_df.columns:
        if "date" in col.lower():
            try:
                processed_df[col] = pd.to_datetime(processed_df[col], errors="coerce")
            except Exception:
                pass  # ignore if conversion fails

    # Show missing values info
    missing_values = processed_df.isnull().sum()
    if missing_values.sum() > 0:
        st.warning(f"Dataset contains {missing_values.sum()} missing values. They will be removed.")
        st.write("Missing values per column:", missing_values[missing_values > 0])
    
    processed_df.dropna(inplace=True)

    # Encode categorical columns - but skip high-cardinality columns that are likely identifiers
    categorical_cols = processed_df.select_dtypes(include=["object"]).columns
    if len(categorical_cols) > 0:
        st.info(f"Found {len(categorical_cols)} categorical columns: {', '.join(categorical_cols)}")
        
        identifier_cols = []
        regular_categorical_cols = []
        
        for col in categorical_cols:
            unique_count = processed_df[col].nunique()
            total_count = len(processed_df[col])
            if unique_count > total_count * 0.5:
                identifier_cols.append((col, unique_count))
                st.warning(f"Column '{col}' has {unique_count} unique values and appears to be an identifier. It won't be encoded.")
            else:
                regular_categorical_cols.append(col)
        
        for col in regular_categorical_cols:
            le = LabelEncoder()
            processed_df[col] = le.fit_transform(processed_df[col].astype(str))
            st.write(f"Encoded column '{col}' with {processed_df[col].nunique()} categories")

    st.success("Data cleaned and preprocessed!")
    st.write("Processed Data Preview:", processed_df.head())
    
    return processed_df

# ---------- Module 4: Query Understanding (Improved for live recording) ----------
def query_understanding(df):
    """
    Handles text or live voice queries using the Gemini API to understand natural language
    and generate a structured query for dashboard creation.
    """
    st.subheader("💬 Query Understanding (NLP / Voice)")
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        st.error(f"Failed to load Gemini model. Make sure you have the 'google-generativeai' library installed and your API key is configured correctly. Error: {e}")
        return

    prompt_template = """
    You are a data analysis assistant. A user will provide a natural language query about their data.
    Your task is to translate this query into a structured JSON object that can be used to generate a dashboard.
    The JSON object should have the following keys:
    - "chart_type": The type of chart to create (e.g., "bar", "line", "scatter", "pie", "histogram", "box", "area", "heatmap", "violin", "treemap", "sunburst", "funnel").
    - "columns": A list of columns to use for the chart. The first column is for the X-axis or names, the second is for the Y-axis or values.
    - "operation": The aggregation operation to perform on the data (e.g., "sum", "average", "count", "none").

    The available columns in the user's data are: {columns}.
    
    Here are some examples:
    - User Query: "Show me the total sales by region"
    - Response: {{"chart_type": "bar", "columns": ["region", "sales"], "operation": "sum"}}
    
    - User Query: "What is the average price of each product?"
    - Response: {{"chart_type": "bar", "columns": ["product", "price"], "operation": "average"}}
    
    - User Query: "Display the distribution of age"
    - Response: {{"chart_type": "histogram", "columns": ["age"], "operation": "none"}}
    
    - User Query: "Create a pie chart for the number of users by country"
    - Response: {{"chart_type": "pie", "columns": ["country"], "operation": "count"}}
    
    - User Query: "Show correlation between price and sales"
    - Response: {{"chart_type": "scatter", "columns": ["price", "sales"], "operation": "none"}}
    
    - User Query: "Display sales distribution by category"
    - Response: {{"chart_type": "box", "columns": ["category", "sales"], "operation": "none"}}
    
    - User Query: "Show sales trend over time"
    - Response: {{"chart_type": "area", "columns": ["date", "sales"], "operation": "sum"}}
    
    - User Query: "Create a heatmap of sales by region and product"
    - Response: {{"chart_type": "heatmap", "columns": ["region", "product", "sales"], "operation": "sum"}}
    
    User Query: "{query}"
    Response:
    """

    if df is not None and not df.empty:
        available_columns = df.columns.tolist()
        st.info(f"Available columns: {', '.join(available_columns)}")
    else:
        st.warning("No data loaded. Cannot provide a list of columns for the query.")
        available_columns = []

    option = st.radio("Input type", ["Text", "Voice"], key="input_type")
    
    query = ""
    if option == "Text":
        query = st.text_input("Enter your data query (e.g., Show average sales)", key="text_query")
    else:
        st.info("Click 'Start recording' to speak your query. The transcription will appear below.")
        audio_bytes = mic_recorder(start_prompt="Start recording", stop_prompt="Stop recording", key="recorder")
        
        if audio_bytes:
            try:
                # Save the audio to a temporary file
                with open("temp_audio.wav", "wb") as f:
                    f.write(audio_bytes['bytes'])
                
                # Load Whisper model and transcribe
                whisper_model = whisper.load_model("base")
                result = whisper_model.transcribe("temp_audio.wav", language="en")
                query = result["text"]
                st.write(f"Transcribed query: {query}")
                
                # Clean up the temporary file
                os.remove("temp_audio.wav")
            except Exception as e:
                st.error(f"Error transcribing audio: {e}")
            
    if query and query != st.session_state.get('last_query', ''):
        st.session_state['last_query'] = query
        try:
            full_prompt = prompt_template.format(columns=available_columns, query=query)
            response = model.generate_content(full_prompt)
            
            # Extract JSON from the response
            gemini_output = response.text.strip()
            
            # Clean the response to extract only JSON
            if "{" in gemini_output and "}" in gemini_output:
                json_start = gemini_output.find("{")
                json_end = gemini_output.rfind("}") + 1
                gemini_output = gemini_output[json_start:json_end]
            
            # Parse the JSON response
            query_data = json.loads(gemini_output)
            
            # Validate the response structure
            required_keys = ["chart_type", "columns", "operation"]
            if all(key in query_data for key in required_keys):
                st.session_state['gemini_query'] = query_data
                st.session_state['generate_from_query'] = True
                st.success("Query understood by Gemini API!")
                st.json(query_data)
            else:
                st.error("Gemini response doesn't contain all required fields.")
                st.session_state['gemini_query'] = None
                st.session_state['generate_from_query'] = False

        except json.JSONDecodeError as e:
            st.error(f"Failed to parse Gemini response as JSON: {e}")
            st.write("Raw Gemini response:", response.text)
            st.session_state['gemini_query'] = None
            st.session_state['generate_from_query'] = False
        except Exception as e:
            st.error(f"Error processing query with Gemini: {e}")
            st.session_state['gemini_query'] = None
            st.session_state['generate_from_query'] = False

# ---------- Module 5: Auto Dashboard Generation (Improved Version) ----------
def auto_generate_dashboard(df, username=None):
    """Generates a dashboard, either from a query or manual selection, with AI enhancements."""
    st.subheader("📊 Auto-Generated Dashboard")

    if df is None or df.empty:
        st.warning("No data available to generate a dashboard.")
        return

    # Get username from parameter or session state
    if username is None:
        username = st.session_state.get('username', 'default_user')

    # Automatically identify column types
    numerical_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()

    # --- AI-Driven Dashboard Generation ---
    st.subheader("AI-Driven Insights")

    # 1. Dynamic Filters - Moved to the top to apply to all visualizations
    st.sidebar.subheader("📊 Dashboard Filters")
    
    # Initialize filtered_df with original data
    filtered_df = df.copy()
    
    # Create filters for categorical columns
    filter_options = {}
    if categorical_cols:
        for i, col in enumerate(categorical_cols[:3]):  # Limit to 3 categorical filters
            unique_values = df[col].unique().tolist()
            selected_values = st.sidebar.multiselect(
                f"Filter by {col}", 
                options=unique_values,
                default=unique_values,
                key=f"cat_filter_{username}_{i}"
            )
            filter_options[col] = selected_values
    
    # Create filters for numerical columns
    if numerical_cols:
        for i, col in enumerate(numerical_cols[:2]):  # Limit to 2 numerical filters
            min_val, max_val = float(df[col].min()), float(df[col].max())
            selected_range = st.sidebar.slider(
                f"Range for {col}", 
                min_val, max_val, (min_val, max_val),
                key=f"num_filter_{username}_{i}_{col}"
            )
            filter_options[col] = selected_range
    
    # Apply filters to the dataframe
    for col, value in filter_options.items():
        if col in categorical_cols:
            if value:  # Only apply if values are selected
                filtered_df = filtered_df[filtered_df[col].isin(value)]
        elif col in numerical_cols:
            filtered_df = filtered_df[
                (filtered_df[col] >= value[0]) & 
                (filtered_df[col] <= value[1])
            ]
    
    # Display filter status
    st.sidebar.info(f"Showing {len(filtered_df)} of {len(df)} records")
    
    # 2. Automatic KPI Generation - Improved with better metrics
    st.write("---")
    st.write("### Key Performance Indicators (KPIs)")
    
    # Calculate metrics for each numerical column
    metrics_data = []
    if numerical_cols:
        for col in numerical_cols[:4]:  # Limit to 4 columns to avoid clutter
            metrics_data.append({
                "Metric": f"Total {col}",
                "Value": f"{filtered_df[col].sum():,.0f}"
            })
            metrics_data.append({
                "Metric": f"Average {col}",
                "Value": f"{filtered_df[col].mean():,.2f}"
            })
        
        # Display metrics in a grid
        cols = st.columns(4)
        for i, metric in enumerate(metrics_data):
            with cols[i % 4]:
                st.metric(label=metric["Metric"], value=metric["Value"])
    else:
        st.info("No numerical columns found for KPI generation.")

    # 3. Automatic Chart Generation - Improved with better logic and proper titles
    st.write("---")
    st.write("### Smart Visualizations")
    
    # Create tabs for different chart types
    tab1, tab2, tab3, tab4 = st.tabs(["Trend Analysis", "Comparisons", "Distributions", "Relationships"])
    
    # Store chart information for later analysis
    chart_info = {
        "charts": [],
        "data_summary": f"Dataset with {len(filtered_df)} rows and {len(filtered_df.columns)} columns",
        "columns": {
            "numerical": numerical_cols,
            "categorical": categorical_cols,
            "date": date_cols
        },
        "dashboard_type": "Auto-Generated"
    }
    
    # Store chart figures for saving
    chart_figures = []
    
    with tab1:
        st.subheader("Trend Analysis")
        # Look for date columns for trend analysis
        if date_cols and numerical_cols:
            date_col = date_cols[0]
            value_col = numerical_cols[0]
            
            # Aggregate data by date
            df_date = filtered_df.groupby(date_col)[value_col].sum().reset_index()
            
            # Create line chart with proper title
            fig = px.line(df_date, x=date_col, y=value_col, 
                         title=f"Line Chart: Trend of {value_col} over time")
            st.plotly_chart(fig, use_container_width=True, key=f"trend_line_{username}")
            
            # Store chart info for analysis
            chart_info["charts"].append({
                "type": "line",
                "title": f"Trend of {value_col} over time",
                "x_axis": date_col,
                "y_axis": value_col,
                "data_points": len(df_date)
            })
        else:
            st.info("No date columns found for trend analysis.")
    
    with tab2:
        st.subheader("Comparisons")
        if categorical_cols and numerical_cols:
            cat_col = categorical_cols[0]
            num_col = numerical_cols[0]
            
            # Limit to top 10 categories to avoid clutter
            top_categories = filtered_df[cat_col].value_counts().nlargest(10).index
            df_filtered = filtered_df[filtered_df[cat_col].isin(top_categories)]
            
            # Create bar chart with proper title
            df_agg = df_filtered.groupby(cat_col)[num_col].sum().reset_index()
            fig = px.bar(df_agg, x=cat_col, y=num_col, 
                        title=f"Bar Chart: Total {num_col} by {cat_col}")
            st.plotly_chart(fig, use_container_width=True, key=f"comparison_bar_{username}")
            chart_figures.append(fig)
            
            # Store chart info for analysis
            chart_info["charts"].append({
                "type": "bar",
                "title": f"Total {num_col} by {cat_col}",
                "x_axis": cat_col,
                "y_axis": num_col,
                "categories": len(df_agg),
                "operation": "sum"
            })
            
            # Also show a pie chart for distribution with proper title
            if len(top_categories) <= 8:  # Only show pie chart for reasonable number of categories
                fig_pie = px.pie(df_agg, values=num_col, names=cat_col, 
                                title=f"Pie Chart: Distribution of {num_col} by {cat_col}")
                st.plotly_chart(fig_pie, use_container_width=True, key=f"comparison_pie_{username}")
                chart_figures.append(fig_pie)
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "pie",
                    "title": f"Distribution of {num_col} by {cat_col}",
                    "category": cat_col,
                    "value": num_col,
                    "categories": len(df_agg)
                })
        else:
            st.info("Need both categorical and numerical columns for comparisons.")
    
    with tab3:
        st.subheader("Distributions")
        if numerical_cols:
            num_col = numerical_cols[0]
            
            # Create histogram with proper title
            fig = px.histogram(filtered_df, x=num_col, title=f"Histogram: Distribution of {num_col}")
            st.plotly_chart(fig, use_container_width=True, key=f"dist_histogram_{username}")
            chart_figures.append(fig)
            
            # Store chart info for analysis
            chart_info["charts"].append({
                "type": "histogram",
                "title": f"Distribution of {num_col}",
                "variable": num_col,
                "bins": 30,
                "data_points": len(filtered_df)
            })
            
            # Also show box plot if we have categorical data with proper title
            if categorical_cols:
                cat_col = categorical_cols[0]
                top_categories = filtered_df[cat_col].value_counts().nlargest(5).index
                df_filtered = filtered_df[filtered_df[cat_col].isin(top_categories)]
                
                fig_box = px.box(df_filtered, x=cat_col, y=num_col, 
                                title=f"Box Plot: Distribution of {num_col} by {cat_col}")
                st.plotly_chart(fig_box, use_container_width=True, key=f"dist_box_{username}")
                chart_figures.append(fig_box)
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "box",
                    "title": f"Distribution of {num_col} by {cat_col}",
                    "category": cat_col,
                    "value": num_col,
                    "categories": len(top_categories)
                })
        else:
            st.info("No numerical columns found for distribution analysis.")
    
    with tab4:
        st.subheader("Relationships")
        if len(numerical_cols) >= 2:
            x_col, y_col = numerical_cols[0], numerical_cols[1]
            
            # Create scatter plot with proper title
            if categorical_cols:
                color_col = categorical_cols[0]
                top_categories = filtered_df[color_col].value_counts().nlargest(5).index
                df_filtered = filtered_df[filtered_df[color_col].isin(top_categories)]
                
                fig = px.scatter(df_filtered, x=x_col, y=y_col, color=color_col,
                               title=f"Scatter Plot: Relationship between {x_col} and {y_col} by {color_col}")
            else:
                fig = px.scatter(filtered_df, x=x_col, y=y_col, 
                               title=f"Scatter Plot: Relationship between {x_col} and {y_col}")
            
            st.plotly_chart(fig, use_container_width=True, key=f"rel_scatter_{username}")
            chart_figures.append(fig)
            
            # Store chart info for analysis
            chart_info["charts"].append({
                "type": "scatter",
                "title": f"Relationship between {x_col} and {y_col}",
                "x_axis": x_col,
                "y_axis": y_col,
                "data_points": len(filtered_df)
            })
            
            # Add correlation heatmap if we have multiple numerical columns with proper title
            if len(numerical_cols) >= 3:
                st.subheader("Correlation Heatmap")
                corr_matrix = filtered_df[numerical_cols[:5]].corr()
                fig_heatmap = px.imshow(corr_matrix, text_auto=True, aspect="auto",
                                      title="Heatmap: Correlation between numerical variables")
                st.plotly_chart(fig_heatmap, use_container_width=True, key=f"rel_heatmap_{username}")
                chart_figures.append(fig_heatmap)
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "heatmap",
                    "title": "Correlation between numerical variables",
                    "variables": numerical_cols[:5],
                    "correlation_matrix": True
                })
        else:
            st.info("Need at least two numerical columns for relationship analysis.")

    # Display the filtered data
    st.write("---")
    st.subheader("Filtered Data Preview")
    st.dataframe(filtered_df.head(10))
    
    # Generate AI summary for the dashboard
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        summary_prompt = f"""
        Write a comprehensive summary of this dashboard in simple business language.
        
        Dashboard Overview:
        - Data: {len(filtered_df)} rows, {len(filtered_df.columns)} columns
        - Key visualizations: {len(chart_info['charts'])} charts showing trends, comparisons, distributions, and relationships
        - Numerical columns: {len(numerical_cols)}
        - Categorical columns: {len(categorical_cols)}
        - Date columns: {len(date_cols)}
        
        Provide insights about what the data reveals and key takeaways for business decision making.
        Keep it concise but informative (3-4 paragraphs).
        """
        
        with st.spinner("Generating AI dashboard summary..."):
            response = model.generate_content(summary_prompt)
            ai_summary = response.text
            chart_info['ai_summary'] = ai_summary
            
            st.write("---")
            st.subheader("🤖 AI Dashboard Summary")
            st.write(ai_summary)
            
    except Exception as e:
        st.error(f"Error generating AI summary: {e}")
        chart_info['ai_summary'] = "AI summary not available."
    
    # Store the chart info and figures in session state for use in saving
    st.session_state['chart_info'] = chart_info
    st.session_state['chart_figures'] = chart_figures
    
    # Store dashboard type in session state
    st.session_state['current_dashboard_type'] = "Auto-Generated"
    
    # NEW: Auto-save the dashboard when generated
    if st.session_state.get('username') and chart_figures:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_name = f"Auto_Dashboard_{timestamp}"
            
            # Extract KPIs from chart info
            kpis = {}
            if chart_info and 'charts' in chart_info:
                for chart in chart_info['charts']:
                    chart_type = chart.get('type', 'unknown')
                    kpis[f"{chart_type}_chart"] = chart.get('title', 'No title')
            
            # Get anomalies and forecast data if available
            anomalies = st.session_state.get('anomalies_data', {})
            forecast_results = st.session_state.get('forecast_data', {})
            
            # Auto-save the dashboard
            dashboard_id = report_generator.save_dashboard(
                username=st.session_state.get('username'),
                dashboard_name=dashboard_name,
                dashboard_type="Auto-Generated",
                df=df,
                chart_info=chart_info,
                kpis=kpis,
                forecast_results=forecast_results,
                anomalies=anomalies,
                ai_summary=chart_info.get('ai_summary', ''),
                chart_figures=chart_figures
            )
            
            # Store the auto-saved dashboard ID
            st.session_state['last_auto_saved_dashboard'] = dashboard_id
            
        except Exception as e:
            # Silently fail for auto-save to not disrupt user experience
            pass
    
    # Return the filtered dataframe for use in Module 6
    return filtered_df

# ---------- Query-Based Dashboard Generator (All Chart Types) ----------
def query_based_dashboard_generator(df):
    """Generates a dashboard based on a user's query and Gemini's output."""
    st.subheader("📊 Query-Based Dashboard")
    gemini_query = st.session_state.get('gemini_query', None)
    
    if gemini_query is None:
        st.warning("No valid query found to generate a dashboard.")
        return

    st.write(f"Gemini-derived dashboard request: {gemini_query}")
    
    chart_type = gemini_query.get('chart_type')
    columns = gemini_query.get('columns', [])
    operation = gemini_query.get('operation', 'none')

    # Validate columns exist in the dataframe
    valid_columns = []
    for col in columns:
        if col in df.columns:
            valid_columns.append(col)
        else:
            st.warning(f"Column '{col}' not found in the dataset. Available columns: {list(df.columns)}")
    
    if not valid_columns:
        st.error("None of the specified columns exist in the dataset.")
        return
    
    fig = None
    chart_figures = []
    
    # Store chart information for later analysis
    chart_info = {
        "charts": [],
        "data_summary": f"Dataset with {len(df)} rows and {len(df.columns)} columns",
        "query_based": True,
        "query_type": chart_type,
        "query_columns": valid_columns,
        "query_operation": operation,
        "dashboard_type": "Query-Based",
        "columns": {
            "numerical": df.select_dtypes(include=['int64', 'float64']).columns.tolist(),
            "categorical": df.select_dtypes(include=['object', 'category']).columns.tolist(),
            "date": df.select_dtypes(include=['datetime64']).columns.tolist()
        }
    }
    
    try:
        if chart_type == 'bar':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(x_col)[y_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(x_col)[y_col].count().reset_index()
                    y_col = 'count'
                else:
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                fig = px.bar(df_agg, x=x_col, y=y_col, title=f"Bar Chart: {operation.title()} of {y_col} by {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "bar",
                    "title": f"{operation.title()} of {y_col} by {x_col}",
                    "x_axis": x_col,
                    "y_axis": y_col,
                    "operation": operation,
                    "categories": len(df_agg)
                })
        
        elif chart_type == 'line':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(x_col)[y_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(x_col)[y_col].count().reset_index()
                    y_col = 'count'
                else:
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                fig = px.line(df_agg, x=x_col, y=y_col, title=f"Line Chart: {operation.title()} of {y_col} by {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "line",
                    "title": f"{operation.title()} of {y_col} by {x_col}",
                    "x_axis": x_col,
                    "y_axis": y_col,
                    "operation": operation,
                    "data_points": len(df_agg)
                })
                
        elif chart_type == 'pie':
            if len(valid_columns) >= 1:
                names_col = valid_columns[0]
                if operation == 'count':
                    # For pie charts with count operation, count occurrences of each category
                    df_counts = df[names_col].value_counts().reset_index()
                    df_counts.columns = ['category', 'count']
                    fig = px.pie(df_counts, values='count', names='category', title=f"Pie Chart: Distribution of {names_col}")
                    
                    # Store chart info for analysis
                    chart_info["charts"].append({
                        "type": "pie",
                        "title": f"Distribution of {names_col}",
                        "category": names_col,
                        "operation": "count",
                        "categories": len(df_counts)
                    })
                else:
                    # For other operations, we need a second column
                    if len(valid_columns) >= 2:
                        values_col = valid_columns[1]
                        if operation == 'sum':
                            df_agg = df.groupby(names_col)[values_col].sum().reset_index()
                        elif operation == 'average':
                            df_agg = df.groupby(names_col)[values_col].mean().reset_index()
                        else:
                            df_agg = df.groupby(names_col)[values_col].sum().reset_index()
                        fig = px.pie(df_agg, values=values_col, names=names_col, title=f"Pie Chart: {operation.title()} of {values_col} by {names_col}")
                        
                        # Store chart info for analysis
                        chart_info["charts"].append({
                            "type": "pie",
                            "title": f"{operation.title()} of {values_col} by {names_col}",
                            "category": names_col,
                            "value": values_col,
                            "operation": operation,
                            "categories": len(df_agg)
                        })
                    else:
                        st.warning("Pie chart requires at least two columns for operations other than 'count'.")

        elif chart_type == 'histogram':
            if len(valid_columns) >= 1:
                x_col = valid_columns[0]
                fig = px.histogram(df, x=x_col, title=f"Histogram: Distribution of {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "histogram",
                    "title": f"Distribution of {x_col}",
                    "variable": x_col,
                    "bins": 30,
                    "data_points": len(df)
                })

        elif chart_type == 'scatter':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                if len(valid_columns) >= 3:
                    color_col = valid_columns[2]
                    fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=f"Scatter Plot: {y_col} vs {x_col} by {color_col}")
                    
                    # Store chart info for analysis
                    chart_info["charts"].append({
                        "type": "scatter",
                        "title": f"{y_col} vs {x_col} by {color_col}",
                        "x_axis": x_col,
                        "y_axis": y_col,
                        "color": color_col,
                        "data_points": len(df)
                    })
                else:
                    fig = px.scatter(df, x=x_col, y=y_col, title=f"Scatter Plot: {y_col} vs {x_col}")
                    
                    # Store chart info for analysis
                    chart_info["charts"].append({
                        "type": "scatter",
                        "title": f"{y_col} vs {x_col}",
                        "x_axis": x_col,
                        "y_axis": y_col,
                        "data_points": len(df)
                    })

        elif chart_type == 'box':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                fig = px.box(df, x=x_col, y=y_col, title=f"Box Plot: Distribution of {y_col} by {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "box",
                    "title": f"Distribution of {y_col} by {x_col}",
                    "category": x_col,
                    "value": y_col,
                    "categories": df[x_col].nunique()
                })
            elif len(valid_columns) >= 1:
                y_col = valid_columns[0]
                fig = px.box(df, y=y_col, title=f"Box Plot: Distribution of {y_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "box",
                    "title": f"Distribution of {y_col}",
                    "value": y_col
                })

        elif chart_type == 'area':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(x_col)[y_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(x_col)[y_col].count().reset_index()
                    y_col = 'count'
                else:
                    df_agg = df.groupby(x_col)[y_col].sum().reset_index()
                fig = px.area(df_agg, x=x_col, y=y_col, title=f"Area Chart: {operation.title()} of {y_col} by {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "area",
                    "title": f"{operation.title()} of {y_col} by {x_col}",
                    "x_axis": x_col,
                    "y_axis": y_col,
                    "operation": operation,
                    "data_points": len(df_agg)
                })

        elif chart_type == 'heatmap':
            if len(valid_columns) >= 3:
                x_col, y_col, z_col = valid_columns[0], valid_columns[1], valid_columns[2]
                if operation == 'sum':
                    df_agg = df.groupby([x_col, y_col])[z_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby([x_col, y_col])[z_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby([x_col, y_col])[z_col].count().reset_index()
                    z_col = 'count'
                else:
                    df_agg = df.groupby([x_col, y_col])[z_col].sum().reset_index()
                
                # Pivot the data for heatmap
                df_pivot = df_agg.pivot(index=y_col, columns=x_col, values=z_col).fillna(0)
                fig = px.imshow(df_pivot, title=f"Heatmap: {operation.title()} of {z_col} by {x_col} and {y_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "heatmap",
                    "title": f"{operation.title()} of {z_col} by {x_col} and {y_col}",
                    "x_axis": x_col,
                    "y_axis": y_col,
                    "value": z_col,
                    "operation": operation
                })
            else:
                st.warning("Heatmap requires at least three columns: x, y, and z.")

        elif chart_type == 'violin':
            if len(valid_columns) >= 2:
                x_col, y_col = valid_columns[0], valid_columns[1]
                fig = px.violin(df, x=x_col, y=y_col, title=f"Violin Plot: Distribution of {y_col} by {x_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "violin",
                    "title": f"Distribution of {y_col} by {x_col}",
                    "category": x_col,
                    "value": y_col,
                    "categories": df[x_col].nunique()
                })
            elif len(valid_columns) >= 1:
                y_col = valid_columns[0]
                fig = px.violin(df, y=y_col, title=f"Violin Plot: Distribution of {y_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "violin",
                    "title": f"Distribution of {y_col}",
                    "value": y_col
                })

        elif chart_type == 'treemap':
            if len(valid_columns) >= 2:
                path_col, value_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(path_col)[value_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(path_col)[value_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(path_col)[value_col].count().reset_index()
                    value_col = 'count'
                else:
                    df_agg = df.groupby(path_col)[value_col].sum().reset_index()
                fig = px.treemap(df_agg, path=[path_col], values=value_col, title=f"Treemap: {operation.title()} of {value_col} by {path_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "treemap",
                    "title": f"{operation.title()} of {value_col} by {path_col}",
                    "path": path_col,
                    "value": value_col,
                    "operation": operation,
                    "categories": len(df_agg)
                })

        elif chart_type == 'sunburst':
            if len(valid_columns) >= 2:
                path_col, value_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(path_col)[value_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(path_col)[value_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(path_col)[value_col].count().reset_index()
                    value_col = 'count'
                else:
                    df_agg = df.groupby(path_col)[value_col].sum().reset_index()
                fig = px.sunburst(df_agg, path=[path_col], values=value_col, title=f"Sunburst: {operation.title()} of {value_col} by {path_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "sunburst",
                    "title": f"{operation.title()} of {value_col} by {path_col}",
                    "path": path_col,
                    "value": value_col,
                    "operation": operation,
                    "categories": len(df_agg)
                })

        elif chart_type == 'funnel':
            if len(valid_columns) >= 2:
                stage_col, value_col = valid_columns[0], valid_columns[1]
                if operation == 'sum':
                    df_agg = df.groupby(stage_col)[value_col].sum().reset_index()
                elif operation == 'average':
                    df_agg = df.groupby(stage_col)[value_col].mean().reset_index()
                elif operation == 'count':
                    df_agg = df.groupby(stage_col)[value_col].count().reset_index()
                    value_col = 'count'
                else:
                    df_agg = df.groupby(stage_col)[value_col].sum().reset_index()
                fig = px.funnel(df_agg, x=value_col, y=stage_col, title=f"Funnel Chart: {operation.title()} of {value_col} by {stage_col}")
                
                # Store chart info for analysis
                chart_info["charts"].append({
                    "type": "funnel",
                    "title": f"{operation.title()} of {value_col} by {stage_col}",
                    "stage": stage_col,
                    "value": value_col,
                    "operation": operation,
                    "stages": len(df_agg)
                })
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"query_chart_{st.session_state.get('username', 'default')}")
            chart_figures.append(fig)

            # NEW: Simple plain-language summary using Gemini
            try:
                model = genai.GenerativeModel('gemini-2.0-flash')
                summary_prompt = f"""
                Write a very simple summary for a business manager about this chart.
                Avoid technical terms like 'axis', 'correlation', or 'distribution'.
                Just explain in plain words what the chart shows.

                - Chart type: {chart_type}
                - Columns used: {valid_columns}
                - Operation applied: {operation}
                - Dataset size: {len(df)} rows

                Explain the following clearly:
                1. If it is a trend chart → describe how the value is moving over time.
                2. If it is a comparison chart → explain which groups are higher or lower.
                3. If it is a distribution chart → explain if values are mostly close together or spread apart.
                4. If it is a relationship chart → explain if two numbers rise and fall together.

                Keep it short (4–5 sentences max) and business-friendly.
                """
                with st.spinner("Generating plain summary..."):
                    response = model.generate_content(summary_prompt)
                    ai_summary = response.text
                    chart_info['ai_summary'] = ai_summary
                    
                    st.info("📋 Chart Summary:")
                    st.write(ai_summary)
            except Exception as e:
                st.error(f"Error generating summary: {e}")
                chart_info['ai_summary'] = "Summary not available."
        else:
            st.warning("Could not generate a chart from the structured query.")

    except Exception as e:
        st.error(f"An error occurred while generating the chart: {e}")
        st.error(f"Error details: {str(e)}")
    
    # Store the chart info and figures in session state for use in saving
    st.session_state['chart_info'] = chart_info
    st.session_state['chart_figures'] = chart_figures
    
    # Store dashboard type in session state
    st.session_state['current_dashboard_type'] = "Query-Based"
    
    # NEW: Auto-save query-based dashboard
    if st.session_state.get('username') and chart_figures:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_name = f"Query_Dashboard_{timestamp}"
            
            # Extract KPIs from chart info
            kpis = {}
            if chart_info and 'charts' in chart_info:
                for chart in chart_info['charts']:
                    chart_type = chart.get('type', 'unknown')
                    kpis[f"{chart_type}_chart"] = chart.get('title', 'No title')
            
            # Get anomalies and forecast data if available
            anomalies = st.session_state.get('anomalies_data', {})
            forecast_results = st.session_state.get('forecast_data', {})
            
            # Auto-save the dashboard
            dashboard_id = report_generator.save_dashboard(
                username=st.session_state.get('username'),
                dashboard_name=dashboard_name,
                dashboard_type="Query-Based",
                df=df,
                chart_info=chart_info,
                kpis=kpis,
                forecast_results=forecast_results,
                anomalies=anomalies,
                ai_summary=chart_info.get('ai_summary', ''),
                chart_figures=chart_figures
            )
            
            # Store the auto-saved dashboard ID
            st.session_state['last_query_saved_dashboard'] = dashboard_id
            
        except Exception as e:
            # Silently fail for auto-save to not disrupt user experience
            pass
    
    # FIX: Allow saving for query-based dashboards
    st.session_state['generate_from_query'] = False
    
    # Reset the query state
    st.session_state['gemini_query'] = None

def generate_forecast(df, date_col, value_col, periods, method="Linear Trend"):
    """
    Generate a simple forecast using basic methods.
    Returns future_dates, forecast_values, upper_ci, lower_ci.
    """

    # Ensure date column is sorted
    df = df.sort_values(by=date_col)
    df = df[[date_col, value_col]].dropna()

    # Get last date
    last_date = df[date_col].iloc[-1]

    # Assume frequency is the difference between last two dates
    if len(df[date_col]) > 1:
        freq = df[date_col].diff().mode()[0]
    else:
        freq = pd.Timedelta(days=1)

    future_dates = [last_date + (i+1) * freq for i in range(periods)]

    # Forecasting methods
    values = df[value_col].values
    if method == "Weighted Average":
        forecast_values = [np.average(values, weights=range(1, len(values)+1))] * periods
    elif method == "Linear Trend":
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        forecast_values = list(np.polyval(coeffs, np.arange(len(values), len(values)+periods)))
    elif method == "Seasonal Pattern":
        season_length = min(12, len(values))  # assume monthly seasonality if enough data
        pattern = values[-season_length:]
        forecast_values = list((pattern.tolist() * ((periods // season_length) + 1))[:periods])
    else:
        forecast_values = [values.mean()] * periods

    # Confidence intervals (basic ±10%)
    upper_ci = [val * 1.1 for val in forecast_values]
    lower_ci = [val * 0.9 for val in forecast_values]

    return future_dates, forecast_values, upper_ci, lower_ci


# ---------- Module 6: Smart Insights & AutoML ----------
def generate_smart_insights(df, chart_info):
    """Generates AI-driven insights, anomaly detection, forecasting, and text summaries."""
    st.subheader("🤖 Smart Insights & AutoML")
    
    if df is None or df.empty:
        st.warning("No data available for generating insights.")
        return
    
    # Get numerical columns for analysis
    numerical_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    if not numerical_cols:
        st.warning("No numerical columns found for analysis.")
        return
    
    # Create tabs for different smart insights
    tab1, tab2, tab3, tab4 = st.tabs(["Anomaly Detection", "Forecasting", "Text Summary", "Key Metrics"])
    
    with tab1:
        st.subheader("📊 Anomaly Detection")
        if len(numerical_cols) >= 1:
            selected_col = st.selectbox("Select column for anomaly detection", numerical_cols, key="anomaly_col")
            
            # Use a button to trigger the analysis
            if st.button("Run Anomaly Detection", key="run_anomaly_detection_btn"):
                # Improved anomaly detection using IQR method
                Q1 = df[selected_col].quantile(0.25)
                Q3 = df[selected_col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                anomalies = df[(df[selected_col] < lower_bound) | (df[selected_col] > upper_bound)]
                
                if not anomalies.empty:
                    st.warning(f"⚠️ Found {len(anomalies)} anomalies in {selected_col}")
                    
                    # Create a visualization showing anomalies
                    fig = go.Figure()
                    
                    # Add normal data
                    normal_data = df[(df[selected_col] >= lower_bound) & (df[selected_col] <= upper_bound)]
                    if date_cols:
                        fig.add_trace(go.Scatter(
                            x=normal_data[date_cols[0]],
                            y=normal_data[selected_col],
                            mode='markers',
                            name='Normal',
                            marker=dict(color='blue', size=6)
                        ))
                    else:
                        fig.add_trace(go.Scatter(
                            x=normal_data.index,
                            y=normal_data[selected_col],
                            mode='markers',
                            name='Normal',
                            marker=dict(color='blue', size=6)
                        ))
                    
                    # Add anomalies
                    if date_cols:
                        fig.add_trace(go.Scatter(
                            x=anomalies[date_cols[0]],
                            y=anomalies[selected_col],
                            mode='markers',
                            marker=dict(color='red', size=8, symbol='x'),
                            name='Anomaly'
                        ))
                    else:
                        fig.add_trace(go.Scatter(
                            x=anomalies.index,
                            y=anomalies[selected_col],
                            mode='markers',
                            marker=dict(color='red', size=8, symbol='x'),
                            name='Anomaly'
                        ))
                    
                    # Add upper and lower bounds
                    if date_cols:
                        x_range = [df[date_cols[0]].min(), df[date_cols[0]].max()]
                    else:
                        x_range = [df.index.min(), df.index.max()]
                    
                    fig.add_trace(go.Scatter(
                        x=x_range,
                        y=[upper_bound, upper_bound],
                        mode='lines',
                        line=dict(color='orange', dash='dash'),
                        name='Upper Bound'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=x_range,
                        y=[lower_bound, lower_bound],
                        mode='lines',
                        line=dict(color='orange', dash='dash'),
                        name='Lower Bound'
                    ))
                    
                    fig.update_layout(
                        title=f"Anomaly Detection in {selected_col} (IQR Method)",
                        xaxis_title="Time" if date_cols else "Index",
                        yaxis_title=selected_col
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"anomaly_chart_{st.session_state.get('username', 'default')}")
                    
                    st.subheader("Anomalies Found:")
                    st.dataframe(anomalies)

                    # Store anomalies data for saving
                    st.session_state['anomalies_data'] = {
                        'column': selected_col,
                        'anomalies_count': len(anomalies),
                        'anomalies_data': anomalies.to_dict('records'),
                        'bounds': {'lower_bound': lower_bound, 'upper_bound': upper_bound}
                    }

                    # Generate Gemini-powered summary
                    try:
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        
                        summary_prompt = f"""
                        Based on the following anomaly detection results, provide a simple, easy-to-understand summary.
                        Avoid technical jargon like "IQR" or "outliers". Explain what the unusual values are and why they are flagged.

                        - Column analyzed: {selected_col}
                        - Number of unusual values found: {len(anomalies)}
                        - The normal range for this data is between {lower_bound:.2f} and {upper_bound:.2f}.
                        - The unusual values found are:
                        {anomalies[[selected_col]].to_markdown()}

                        Write the summary in a simple paragraph for a non-technical audience.
                        """
                        
                        with st.spinner("Generating AI-powered summary..."):
                            response = model.generate_content(summary_prompt)
                            st.info("📋 AI Anomaly Summary:")
                            st.write(response.text)
                            
                    except Exception as e:
                        st.error(f"Error generating text summary: {e}")
                else:
                    st.success(f"No unusual data points detected in {selected_col}.")
                    # Clear any previous anomalies data
                    if 'anomalies_data' in st.session_state:
                        del st.session_state['anomalies_data']

        else:
            st.info("Need at least one numerical column for anomaly detection.")
    with tab2:
        st.subheader("📈 Forecasting")
        
        # Check if we have both numerical and date columns
        if len(numerical_cols) >= 1 and len(date_cols) >= 1:
            col1, col2 = st.columns(2)
            
            with col1:
                # Allow user to select which numerical column to forecast
                selected_num_col = st.selectbox(
                    "Select value column to forecast", 
                    numerical_cols, 
                    key="forecast_num_col"
                )
                
            with col2:
                selected_date_col = st.selectbox("Select date column", date_cols, key="forecast_date_col")
            
            # Forecasting options
            col1, col2 = st.columns(2)
            with col1:
                forecast_periods = st.slider("Forecast periods", 1, 24, 6, key="forecast_periods")
            with col2:
                model_type = st.selectbox("Forecasting method", 
                                        ["Weighted Average", "Linear Trend", "Seasonal Pattern"], 
                                        key="forecast_model")
            
            # Use a button to trigger the forecast
            if st.button("Run Forecast", key="run_forecast_btn"):
                if len(df) < 4:
                    st.warning("Not enough data to run a forecast. Need at least 4 data points.")
                else:
                    st.subheader(f"Forecast for {selected_num_col}")
                    
                    # Generate forecast
                    future_dates, forecast_values, upper_ci, lower_ci = generate_forecast(
                        df, selected_date_col, selected_num_col, forecast_periods, model_type
                    )
                    
                    if future_dates is not None:
                        # Create a forecast visualization
                        fig = go.Figure()
                        
                        # Add historical data
                        fig.add_trace(go.Scatter(
                            x=df[selected_date_col],
                            y=df[selected_num_col],
                            mode='lines+markers',
                            name='Historical Data'
                        ))
                        
                        # Add forecast
                        fig.add_trace(go.Scatter(
                            x=future_dates,
                            y=forecast_values,
                            mode='lines+markers',
                            line=dict(dash='dot', color='red'),
                            name='Forecast'
                        ))
                        
                        # Add confidence intervals
                        fig.add_trace(go.Scatter(
                            x=future_dates + future_dates[::-1],  # x then reversed x
                            y=upper_ci + lower_ci[::-1],          # upper then lower reversed
                            fill='toself',
                            fillcolor='rgba(255, 0, 0, 0.2)',
                            line=dict(color='rgba(255,255,255,0)'),
                            name='Confidence Range'
                        ))
                        
                        fig.update_layout(
                            title=f"Forecast for {selected_num_col}",
                            xaxis_title=selected_date_col,
                            yaxis_title=selected_num_col
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"forecast_chart_{st.session_state.get('username', 'default')}")

                        # Display forecast values in a table
                        forecast_df = pd.DataFrame({
                            'Date': future_dates,
                            'Forecast': forecast_values,
                            'Upper Range': upper_ci,
                            'Lower Range': lower_ci
                        })
                        st.write("Forecast Values:")
                        st.dataframe(forecast_df)

                        # Store forecast data for saving
                        st.session_state['forecast_data'] = {
                            'column': selected_num_col,
                            'date_column': selected_date_col,
                            'periods': forecast_periods,
                            'method': model_type,
                            'forecast_values': forecast_values,
                            'confidence_intervals': {'upper': upper_ci, 'lower': lower_ci},
                            'future_dates': [str(date) for date in future_dates]
                        }

                        # Generate plain language summary
                        try:
                            model = genai.GenerativeModel('gemini-2.0-flash')
                            
                            summary_prompt = f"""
                            Write a short and clear summary of this forecast in simple words.
                            Do not use technical or statistical terms.
                            
                            - Value being forecast: {selected_num_col}
                            - Forecast period: {forecast_periods} steps ahead
                            - Current value: {df[selected_num_col].iloc[-1]:.2f}
                            - Expected future value: {forecast_values[-1]:.2f}
                            - Range of possible outcomes: from {lower_ci[-1]:.2f} to {upper_ci[-1]:.2f}
                            
                            Explain the trend as if you are speaking to a business manager.
                            """
                            
                            with st.spinner("Generating forecast summary..."):
                                response = model.generate_content(summary_prompt)
                                st.info("📋 Forecast Summary:")
                                st.write(response.text)
                                
                        except Exception as e:
                            st.error(f"Error generating forecast summary: {e}")
                    else:
                        # Clear any previous forecast data
                        if 'forecast_data' in st.session_state:
                            del st.session_state['forecast_data']
        else:
            st.info("Need at least one numerical column and one date column for forecasting.")
            if not date_cols:
                st.write("**Tip:** Make sure your date column is properly formatted as a datetime field.")
    
    
    with tab3:
        st.subheader("🧠 Smart Text Summary")
        
        try:
            # Use Gemini to generate a text summary of the dashboard
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Create a summary of the dashboard visualizations
            summary_prompt = f"""
            Analyze this data dashboard and provide a comprehensive, human-readable summary in plain English.
            Focus on explaining the key insights, patterns, and trends visible in the visualizations in a way that a non-technical business user can understand.
            
            {chart_info['data_summary']}
            
            The dashboard contains the following visualizations:
            {json.dumps(chart_info['charts'], indent=2)}
            
            Provide a detailed summary that includes:
            1. A clear explanation of what each visualization shows
            2. Key trends and patterns across the visualizations
            3. Notable highs, lows, or outliers and what they might mean
            4. Relationships or correlations between variables
            5. Business implications or recommendations based on the insights
            6. Step-by-step explanation of what the data is telling us
            
            Write the summary as if you're explaining it to a business manager who needs to make decisions but doesn't have a technical background.
            Keep it comprehensive but easy to understand (around 250-300 words).
            
            Dashboard Summary:
            """
            
            with st.spinner("Generating AI-powered dashboard summary..."):
                response = model.generate_content(summary_prompt)
                st.success("📋 AI Dashboard Summary Generated!")
                st.write(response.text)
                
        except Exception as e:
            st.error(f"Error generating text summary: {e}")
    
    with tab4:
        st.subheader("📌 Key Metrics Highlighting")
        
        # Allow user to select which metrics to display
        st.write("**Select metrics to display:**")
        selected_metrics = st.multiselect(
            "Choose metrics to highlight", 
            numerical_cols, 
            default=numerical_cols[:3] if len(numerical_cols) > 3 else numerical_cols,
            key="metric_selection"
        )
        
        if selected_metrics:
            # Calculate basic statistics for each selected numerical column
            metrics = []
            for col in selected_metrics:
                metrics.append({
                    "Metric": col,
                    "Total": f"{df[col].sum():,.2f}",
                    "Average": f"{df[col].mean():,.2f}",
                    "Median": f"{df[col].median():,.2f}",
                    "Max": f"{df[col].max():,.2f}",
                    "Min": f"{df[col].min():,.2f}",
                    "Std Dev": f"{df[col].std():,.2f}",
                    "Growth Rate": f"{((df[col].iloc[-1] if len(df) > 0 else 0) - (df[col].iloc[0] if len(df) > 0 else 0)) / (df[col].iloc[0] if df[col].iloc[0] != 0 else 1) * 100:.2f}%"
                })
            
            # Display metrics in a table
            metrics_df = pd.DataFrame(metrics)
            st.dataframe(metrics_df)
            
            # Generate plain language summary of key metrics
            try:
                model = genai.GenerativeModel('gemini-2.0-flash')
                
                summary_prompt = f"""
                Create a simple, non-technical summary of these key metrics for a business user.
                Explain what the numbers mean in plain language without using technical terms.
                
                Metrics Summary:
                {metrics_df.to_markdown()}
                
                Write a concise summary that explains:
                1. What each metric represents in simple terms
                2. Which metrics are performing well
                3. Which metrics might need attention
                4. Any interesting patterns or relationships between metrics
                
                Keep it focused on business implications rather than statistical details.
                """
                
                with st.spinner("Generating metrics summary..."):
                    response = model.generate_content(summary_prompt)
                    st.info("📋 Key Metrics Summary:")
                    st.write(response.text)
                    
            except Exception as e:
                st.error(f"Error generating metrics summary: {e}")
            
            # Highlight the most important metrics
            col1, col2, col3 = st.columns(3)
            
            # Highlight the metric with the highest sum
            if len(selected_metrics) > 0:
                max_sum_col = max(selected_metrics, key=lambda x: df[x].sum())
                with col1:
                    st.metric(
                        label="📈 Highest Total Value",
                        value=max_sum_col,
                        delta=f"{df[max_sum_col].sum():,.2f}"
                    )
                
            # Highlight the metric with the highest average
            if len(selected_metrics) > 0:
                max_avg_col = max(selected_metrics, key=lambda x: df[x].mean())
                with col2:
                    st.metric(
                        label="⭐ Highest Average",
                        value=max_avg_col,
                        delta=f"{df[max_avg_col].mean():,.2f}"
                    )
                
            # Highlight the metric with the most variability
            if len(selected_metrics) > 0:
                max_std_col = max(selected_metrics, key=lambda x: df[x].std())
                with col3:
                    st.metric(
                        label="📊 Most Variable",
                        value=max_std_col,
                        delta=f"{df[max_std_col].std():,.2f}"
                    )
            
            # Highlight the metric with the highest growth rate
            if len(selected_metrics) > 0 and len(df) > 1:
                growth_rates = []
                for col in selected_metrics:
                    if df[col].iloc[0] != 0:
                        growth_rate = ((df[col].iloc[-1] - df[col].iloc[0]) / df[col].iloc[0]) * 100
                    else:
                        growth_rate = 0
                    growth_rates.append((col, growth_rate))
                
                if growth_rates:
                    max_growth_col, max_growth = max(growth_rates, key=lambda x: abs(x[1]))
                    st.info(f"🚀 **Highest Growth Rate**: {max_growth_col} with {max_growth:.2f}% change from first to last value")
        
        if categorical_cols:
            st.write("📋 Category Insights:")
            for col in categorical_cols[:3]:  # Limit to 3 categorical columns
                value_counts = df[col].value_counts()
                top_category = value_counts.idxmax()
                top_count = value_counts.max()
                top_percentage = (top_count / len(df)) * 100
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label=f"Most Common {col}",
                        value=top_category,
                        delta=f"{top_count} occurrences"
                    )
                with col2:
                    st.metric(
                        label="Percentage of Total",
                        value=f"{top_percentage:.1f}%",
                        delta=f"of {len(df)} total records"
                    )
                
                # Show top 5 categories
                st.write(f"**Top 5 {col} categories:**")
                for i, (category, count) in enumerate(value_counts.head().items()):
                    percentage = (count / len(df)) * 100
                    st.write(f"{i+1}. {category}: {count} ({percentage:.1f}%)")

# ---------- Real-Time Alerts Interface ----------
def setup_realtime_alerts_interface(username, df):
    """Show real-time sync and alerts setup interface in sidebar"""
    st.sidebar.write("---")
    st.sidebar.subheader("🔄 Real-Time Sync & Alerts")
    
    # Real-time sync setup
    with st.sidebar.expander("📡 Data Source Sync", expanded=False):
        st.write("Set up real-time data synchronization")
        
        sync_source_type = st.selectbox(
            "Data Source Type",
            ["Google Sheets", "REST API", "SQL Database"],
            key=f"sync_source_type_{username}"
        )
        
        if sync_source_type == "Google Sheets":
            sheet_url = st.text_input("Google Sheets URL", key=f"sync_sheet_url_{username}")
            sync_interval = st.slider("Sync Interval (seconds)", 30, 3600, 60, key=f"sheets_sync_interval_{username}")
            
            if st.button("Enable Sync", key=f"enable_sheets_sync_{username}"):
                if sheet_url:
                    sync_config = {
                        'sheet_url': sheet_url,
                        'sync_interval': sync_interval
                    }
                    sync_id = realtime_manager.setup_data_source_sync(
                        username, 'google_sheets', sync_config
                    )
                    st.success(f"Google Sheets sync enabled! (ID: {sync_id})")
                else:
                    st.error("Please provide a Google Sheets URL")
        
        elif sync_source_type == "REST API":
            api_url = st.text_input("API Endpoint URL", key=f"sync_api_url_{username}")
            sync_interval = st.slider("Sync Interval (seconds)", 30, 3600, 60, key=f"api_sync_interval_{username}")
            
            if st.button("Enable Sync", key=f"enable_api_sync_{username}"):
                if api_url:
                    sync_config = {
                        'api_url': api_url,
                        'sync_interval': sync_interval
                    }
                    sync_id = realtime_manager.setup_data_source_sync(
                        username, 'rest_api', sync_config
                    )
                    st.success(f"REST API sync enabled! (ID: {sync_id})")
                else:
                    st.error("Please provide an API URL")
        
        elif sync_source_type == "SQL Database":
            db_type = st.selectbox("Database Type", ["MySQL", "PostgreSQL", "SQLite"], key=f"sync_db_type_{username}")
            host = st.text_input("Host", key=f"sync_db_host_{username}")
            dbname = st.text_input("Database Name", key=f"sync_db_name_{username}")
            user = st.text_input("Username", key=f"sync_db_user_{username}")
            password = st.text_input("Password", type="password", key=f"sync_db_password_{username}")
            query = st.text_area("SQL Query", "SELECT * FROM table_name", key=f"sync_db_query_{username}")
            sync_interval = st.slider("Sync Interval (seconds)", 30, 3600, 60, key=f"db_sync_interval_{username}")
            
            if st.button("Enable Sync", key=f"enable_db_sync_{username}"):
                if all([host, dbname, user, query]):
                    sync_config = {
                        'db_type': db_type.lower(),
                        'host': host,
                        'dbname': dbname,
                        'user': user,
                        'password': password,
                        'query': query,
                        'sync_interval': sync_interval
                    }
                    sync_id = realtime_manager.setup_data_source_sync(
                        username, 'sql_database', sync_config
                    )
                    st.success(f"Database sync enabled! (ID: {sync_id})")
                else:
                    st.error("Please fill all required database fields")
    
    # Alert rules setup
    with st.sidebar.expander("🚨 Alert Rules", expanded=False):
        st.write("Set up automatic alerts for your data")
        
        if df is not None and not df.empty:
            numerical_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            
            if numerical_cols:
                alert_name = st.text_input("Alert Name", "Sales Threshold Alert", key=f"alert_name_{username}")
                alert_column = st.selectbox("Monitor Column", numerical_cols, key=f"alert_column_{username}")
                condition_type = st.selectbox(
                    "Condition Type", 
                    ["threshold", "anomaly", "trend"], 
                    format_func=lambda x: {
                        "threshold": "Value Threshold",
                        "anomaly": "Statistical Anomaly", 
                        "trend": "Trend Detection"
                    }[x],
                    key=f"alert_condition_{username}"
                )
                
                if condition_type == "threshold":
                    operator = st.selectbox(
                        "Operator",
                        ["greater_than", "less_than", "equals", "not_equals"],
                        format_func=lambda x: {
                            "greater_than": "Greater Than",
                            "less_than": "Less Than", 
                            "equals": "Equals",
                            "not_equals": "Not Equals"
                        }[x],
                        key=f"alert_operator_{username}"
                    )
                    threshold_value = st.number_input("Threshold Value", key=f"alert_threshold_{username}")
                
                elif condition_type == "trend":
                    operator = st.selectbox(
                        "Trend Direction",
                        ["increasing", "decreasing"],
                        format_func=lambda x: "Increasing" if x == "increasing" else "Decreasing",
                        key=f"alert_trend_{username}"
                    )
                    threshold_value = st.number_input("Percentage Change Threshold", value=10.0, key=f"alert_trend_threshold_{username}")
                
                else:  # anomaly
                    threshold_value = None
                
                # NEW: Email input field for alerts
                st.write("---")
                st.subheader("📧 Alert Notifications")
                alert_email = st.text_input(
                    "Email for alerts", 
                    value="",  # Start empty
                    placeholder="Enter email to receive alerts",
                    key=f"alert_email_{username}"
                )
                
                # Validate email if provided
                if alert_email and not re.match(EMAIL_REGEX, alert_email):
                    st.error("Please enter a valid email address")
                    alert_email = None
                
                # REMOVED COOLDOWN TIMER - Alerts trigger immediately
                st.info("⏰ Alerts will trigger immediately when conditions are met")
                
                if alert_email:
                    st.success(f"📧 Alerts will be sent to: {alert_email}")
                else:
                    st.warning("⚠️ No email provided - alerts will only show in terminal")
                
                if st.button("Create Alert Rule", key=f"create_alert_{username}"):
                    alert_rule = {
                        'name': alert_name,
                        'condition_type': condition_type,
                        'column': alert_column,
                        'value': threshold_value,
                        'operator': operator if condition_type in ['threshold', 'trend'] else None,
                        'email': alert_email,  # NEW: Include email in alert rule
                        'priority': 'medium'
                    }
                    
                    # Use current dashboard if available
                    dashboard_id = st.session_state.get('last_auto_saved_dashboard') or st.session_state.get('last_query_saved_dashboard')
                    if not dashboard_id:
                        dashboard_id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    alert_id = realtime_manager.setup_alert_rule(username, dashboard_id, alert_rule)
                    if alert_email:
                        st.success(f"Alert rule created! (ID: {alert_id})")
                        st.info(f"📧 Email alerts will be sent to: {alert_email}")
                    else:
                        st.success(f"Alert rule created! (ID: {alert_id})")
                        st.warning("⚠️ No email provided - alerts will only show in terminal")
            
            else:
                st.info("No numerical columns available for alert rules.")
        else:
            st.info("Load data first to set up alert rules.")

    # Alert Management Section
    with st.sidebar.expander("⚙️ Manage Alert Rules", expanded=False):
        st.write("Manage your existing alert rules")
        
        # Get user's alerts
        user_alerts = realtime_manager.get_user_alerts(username)
        
        if user_alerts:
            for i, (alert_id, alert_config) in enumerate(user_alerts.items()):
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        rule = alert_config['rule']
                        status = "🟢 ACTIVE" if alert_config['is_active'] else "🔴 INACTIVE"
                        st.write(f"**{rule.get('name', 'Unnamed Rule')}** - {status}")
                        st.caption(f"Condition: {rule.get('column')} {realtime_manager._get_operator_text(rule.get('operator'))} {rule.get('value')}")
                        st.caption(f"Triggers: {alert_config.get('trigger_count', 0)} | Last: {alert_config.get('last_triggered', 'Never')}")
                        # Show email if configured
                        if rule.get('email'):
                            st.caption(f"📧 Email: {rule.get('email')}")
                        else:
                            st.caption("📧 Email: Not configured")
                    
                    with col2:
                        # Toggle button - FIXED with unique key
                        current_status = alert_config['is_active']
                        new_status = not current_status
                        button_text = "🔴 Stop" if current_status else "🟢 Start"
                        toggle_key = f"toggle_{username}_{alert_id}_{i}"
                        if st.button(button_text, key=toggle_key):
                            if realtime_manager.toggle_alert_rule(alert_id, new_status):
                                st.success(f"Alert {'enabled' if new_status else 'disabled'}!")
                                st.rerun()
                    
                    with col3:
                        # Delete button - FIXED with unique key
                        delete_key = f"delete_{username}_{alert_id}_{i}"
                        if st.button("🗑️", key=delete_key):
                            if realtime_manager.delete_alert_rule(alert_id):
                                st.success("Alert deleted!")
                                st.rerun()
                    
                    st.write("---")
        else:
            st.info("No alert rules created yet.")
    
    # Sync status and notifications
    with st.sidebar.expander("📊 Sync Status & Notifications", expanded=False):
        # Show sync status
        sync_status = realtime_manager.get_sync_status(username)
        st.write(f"**Active Syncs:** {sync_status['active_syncs']}")
        
        if sync_status['last_sync']:
            last_sync = datetime.fromisoformat(sync_status['last_sync'])
            st.write(f"**Last Sync:** {last_sync.strftime('%Y-%m-%d %H:%M')}")
        
        if sync_status['next_sync']:
            next_sync = datetime.fromisoformat(sync_status['next_sync'])
            st.write(f"**Next Sync:** {next_sync.strftime('%H:%M')}")
        
        # Show recent notifications - FIXED with unique keys
        notifications = realtime_manager.get_user_notifications(username, unread_only=True)
        if notifications:
            st.write("---")
            st.write("**Recent Alerts:**")
            for i, notification in enumerate(notifications[:3]):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"⚠️ {notification['title']}")
                    with col2:
                        # FIX: Use a more unique key by including index and timestamp
                        unique_key = f"mark_read_{username}_{i}_{notification['id']}_{datetime.now().timestamp()}"
                        if st.button("📌", key=unique_key):
                            realtime_manager.mark_notification_read(username, notification['id'])
                            st.rerun()
                    
                    st.caption(notification['message'][:100] + "...")
                    st.caption(f"🕒 {datetime.fromisoformat(notification['timestamp']).strftime('%H:%M')}")
        else:
            st.info("No unread notifications")
    
    # Start sync service if not already running
    if not realtime_manager.is_running:
        realtime_manager.start_sync_service()

# ---------- Module 1: Role-Based UI ----------
def show_role_info():
    """Displays role-specific information in the sidebar."""
    role = st.session_state.get("role", "Viewer")
    st.sidebar.success(f"Role: {role}")
    if role == "Admin":
        st.sidebar.info("🛠 You can manage and view dashboards for all users.")
    elif role == "Analyst":
        st.sidebar.info("📈 You can upload, analyze, and visualize your data.")
    else:
        st.sidebar.info("👀 You can only view your uploaded dashboard.")
def add_logout_button():
    """Add logout button to the sidebar"""
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()



# ---------- Main App (Modified with Smart Insights) ----------
def main():
    st.set_page_config(
        page_title="Inferaboard - AI Dashboard Generator",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    create_default_admins()
    load_css()

    # Inject CSS directly for the title with improved emoji styling
    st.markdown("""
    <style>
    .inferaboard-title {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 3.2rem !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, 
            #FF6B6B 0%, 
            #4ECDC4 25%, 
            #45B7D1 50%, 
            #96CEB4 75%, 
            #FFEAA7 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        background-size: 300% 300% !important;
        text-shadow: 
            0 0 25px rgba(255, 107, 107, 0.6),
            0 0 45px rgba(78, 205, 196, 0.5),
            0 0 65px rgba(69, 183, 209, 0.4) !important;
        letter-spacing: 2px !important;
        text-align: center !important;
        margin: 1.5rem 0 !important;
        padding: 1.2rem 0 !important;
        animation: titleGlow 3.5s ease-in-out infinite !important;
        position: relative !important;
        line-height: 1.3 !important;
    }

    /* FIXED EMOJI STYLING - Clear and Visible */
    .inferaboard-title .emoji {
        display: inline-block !important;
        font-size: 1.3em !important;
        margin-right: 15px !important;
        background: none !important;
        border-radius: none!important;
        padding: 2px 4px !important;
        -webkit-text-fill-color: initial !important;
        background-clip: initial !important;
    }


    @keyframes titleGlow {
        0%, 100% {
            background-position: 0% 50%;
            text-shadow: 
                0 0 25px rgba(255, 107, 107, 0.6),
                0 0 45px rgba(78, 205, 196, 0.5);
        }
        50% {
            background-position: 100% 50%;
            text-shadow: 
                0 0 35px rgba(255, 107, 107, 0.9),
                0 0 60px rgba(78, 205, 196, 0.7),
                0 0 85px rgba(69, 183, 209, 0.5);
        }
    }

    .inferaboard-title::before {
        content: "";
        position: absolute;
        top: 0;
        left: 5%;
        right: 5%;
        height: 3px;
        background: linear-gradient(90deg, 
            transparent, 
            #FF6B6B, 
            #4ECDC4, 
            #45B7D1, 
            #96CEB4, 
            #FFEAA7, 
            transparent);
        border-radius: 3px;
        animation: borderFlow 4s linear infinite;
    }

    .inferaboard-title::after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 10%;
        right: 10%;
        height: 2px;
        background: linear-gradient(90deg, 
            transparent, 
            #45B7D1, 
            #96CEB4, 
            #FFEAA7, 
            #FF6B6B, 
            transparent);
        border-radius: 2px;
        animation: borderFlow 4s linear infinite reverse;
    }

    @keyframes borderFlow {
        0% { background-position: -300px 0; }
        100% { background-position: 300px 0; }
    }

    /* Responsive design */
    @media (max-width: 1200px) {
        .inferaboard-title {
            font-size: 2.8rem !important;
        }
        .inferaboard-title .emoji {
            font-size: 1.25em !important;
        }
    }

    @media (max-width: 992px) {
        .inferaboard-title {
            font-size: 2.4rem !important;
        }
        .inferaboard-title .emoji {
            font-size: 1.2em !important;
            margin-right: 12px !important;
        }
    }

    @media (max-width: 768px) {
        .inferaboard-title {
            font-size: 2rem !important;
        }
        .inferaboard-title .emoji {
            font-size: 1.15em !important;
            margin-right: 10px !important;
        }
    }

    @media (max-width: 480px) {
        .inferaboard-title {
            font-size: 1.6rem !important;
        }
        .inferaboard-title .emoji {
            font-size: 1.1em !important;
            margin-right: 8px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # Use custom HTML for the title with separate emoji span
    st.markdown(
        '<h1 class="inferaboard-title"><span class="emoji">🚀</span>Inferaboard : AI Generated Automatic Dashboard and Insights Generator</h1>', 
        unsafe_allow_html=True
    )
    if st.session_state.get("authenticated", False):
        st.sidebar.success(f"Welcome, {st.session_state.get('username', '')}!")
        show_role_info()
        role = st.session_state.get("role", "Viewer")
        current_user = st.session_state.get("username")

        # Add a tab interface for data sources
        data_source_tab = st.sidebar.radio("Data Source", ["File Upload", "Live Connection"])
        df = None

        if data_source_tab == "File Upload":
            # Allow all roles to upload data
            df = upload_data(current_user)
        else:
            # Live data connection
            df = connect_live_data(current_user)

        # If no data loaded from current source, try to load from saved file
        if df is None:
            df = load_user_data(current_user)
        if st.session_state.get("authenticated", False):
        # Add logout button
            add_logout_button()

        # Initialize show_insights in session state
        if 'show_insights' not in st.session_state:
            st.session_state.show_insights = False
            
        # Initialize show_my_reports in session state
        if 'show_my_reports' not in st.session_state:
            st.session_state.show_my_reports = False

        # Process and display data if available
        if df is not None:
            processed_df = preprocess_data(df)

            if processed_df is not None:
                if role in ["Admin", "Analyst"]:
                    query_understanding(processed_df)

                    if st.session_state.get('generate_from_query'):
                        query_based_dashboard_generator(processed_df)
                        # FIX: Capture data for query-based dashboards
                        filtered_df = processed_df
                    else:
                        filtered_df = auto_generate_dashboard(processed_df)
                else:  # Viewer role
                    filtered_df = auto_generate_dashboard(processed_df)

                # --- Smart Insights button for ALL roles ---
                st.sidebar.write("---")
                if st.sidebar.button("🤖 Generate Smart Insights"):
                    st.session_state.show_insights = True

                if st.session_state.show_insights:
                    if st.sidebar.button("⬅️ Hide Insights"):
                        st.session_state.show_insights = False
                    generate_smart_insights(
                        filtered_df if filtered_df is not None else processed_df,
                        st.session_state.get('chart_info', {})
                    )
                    
                # --- Real-Time Alerts Interface ---
                if role in ["Admin", "Analyst"]:  # Only show alerts for Admin and Analyst
                    setup_realtime_alerts_interface(current_user, processed_df)

                # --- Dashboard Saving Interface ---
                if df is not None and processed_df is not None:
                    # Get the current chart figures for saving
                    current_chart_figures = st.session_state.get('chart_figures', [])
                    
                    # Get current dashboard type
                    current_dashboard_type = st.session_state.get('current_dashboard_type', 'Auto-Generated')
                    
                    # Show save dashboard interface
                    saving_ui.show_save_dashboard_interface(
                        username=current_user,
                        df=processed_df,
                        chart_info=st.session_state.get('chart_info', {}),
                        chart_figures=current_chart_figures,
                        anomalies=st.session_state.get('anomalies_data', {}),
                        forecast_results=st.session_state.get('forecast_data', {}),
                        dashboard_type=current_dashboard_type
                    )
                    
                    # Add export interface if we have charts
                    if current_chart_figures and st.session_state.get('chart_info'):
                        saving_ui.show_export_interface(
                            username=current_user,
                            dashboard_data=st.session_state.get('chart_info', {}),
                            chart_figures=current_chart_figures
                        )
                    
                    # Add navigation to My Reports
                    st.sidebar.write("---")
                    if st.sidebar.button("📊 My Reports & Dashboards"):
                        st.session_state.show_my_reports = True
                    
                    if st.session_state.get('show_my_reports', False):
                        saving_ui.show_my_reports_interface(current_user)
                        if st.sidebar.button("⬅️ Back to Dashboard"):
                            st.session_state.show_my_reports = False
        else:
            st.info("No data available. Please upload a file or connect to a live data source.")

        # Admin functionality to view other users' data
        if role == "Admin":
            st.sidebar.write("---")
            st.sidebar.subheader("Admin: View Other Users")
            users = load_users()
            user_list = [u for u in users.keys() if u != current_user]

            if user_list:
                selected_user = st.sidebar.selectbox("Select a User to View", [""] + user_list)
                if selected_user:
                    user_df = load_user_data(selected_user)
                    if user_df is not None:
                        st.sidebar.success(f"Viewing data for: {selected_user}")
                        user_processed_df = preprocess_data(user_df)
                        if user_processed_df is not None:
                            auto_generate_dashboard(user_processed_df,selected_user)
                    else:
                        st.sidebar.info(f"No data uploaded for user: {selected_user}.")
    else:
        auth_panel()

    # Add enhanced footer to main dashboard
    st.markdown("""
    <div class="footer-container">
        <div class="footer-content">
            <div class="footer-separator"></div>
            <p class="footer-text">
                <span class="footer-highlight">© 2025 Inferaboard</span> | Data. AI. Insights.
            </p>
            <p class="footer-subtext">
                Transform Your Data Into Actionable Intelligence
            </p>
            <div class="footer-separator"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
if __name__ == "__main__":
    main()