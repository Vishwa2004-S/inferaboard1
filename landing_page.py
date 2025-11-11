import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(__file__))

# --------------------------------------------
# ✅ FUNCTION: Load Dashboard
# --------------------------------------------
def show_dashboard():
    """Load and display main_dashboard.py content (without running it separately)."""
    import main_dashboard
    main_dashboard.main()

# --------------------------------------------
# ✅ FUNCTION: Login / Navigation Handler
# --------------------------------------------
def login_action():
    """Handles login functionality and navigates to the main dashboard."""
    st.session_state.show_dashboard = True
    

# --------------------------------------------
# ✅ MAIN LANDING PAGE FUNCTION
# --------------------------------------------
def main():
    st.set_page_config(
        page_title="Inferaboard - AI Dashboard Generator",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Session state setup
    if 'show_dashboard' not in st.session_state:
        st.session_state.show_dashboard = False

    # If dashboard should be displayed
    if st.session_state.show_dashboard:
        show_dashboard()
        return

    # --------------------------------------------
    # CUSTOM CSS (From first code)
    # --------------------------------------------
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Montserrat:wght@300;400;600;800&display=swap');

        .stApp {
            background: linear-gradient(135deg, #0f004f, #2b005e 50%, #400040);
            color: white;
            font-family: 'Montserrat', sans-serif;
        }

        :root {
            --neon-green: #00ff99;
            --gold: #FFD700;
            --purple: #7B00FF;
            --dark-bg: rgba(30, 0, 50, 0.7);
        }

        /* ===== HEADER ===== */
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 3rem;
            border-radius: 0 0 25px 25px;
            background: linear-gradient(90deg, rgba(120,0,255,0.4), rgba(0,0,0,0.3), rgba(255,215,0,0.3));
            box-shadow: 0 0 30px rgba(255,255,255,0.1);
            border-bottom: 2px solid rgba(255,255,255,0.1);
            position: relative;
            overflow: hidden;
            width: 90vw;
            box-sizing: border-box;
        }

        .header-bar::before {
            content: "";
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: linear-gradient(90deg, var(--neon-green), var(--gold), var(--purple));
            background-size: 400%;
            opacity: 0.2;
            filter: blur(12px);
            z-index: 0;
            animation: glowMove 6s linear infinite;
        }

        @keyframes glowMove {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .header-text {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.5rem;
            color: var(--gold);
            text-shadow: 0 0 15px rgba(255,255,150,0.6);
            z-index: 1;
            position: relative;
        }

        .header-sub {
            color: #CCEEFF;
            font-size: 1rem;
            font-weight: 400;
            z-index: 1;
            position: relative;
        }

        .login-btn-container {
            z-index: 1;
            position: relative;
        }

        .login-btn {
            background: linear-gradient(90deg, var(--purple), var(--neon-green));
            color: black;
            border-radius: 8px;
            font-weight: 800;
            font-size: 1rem;
            padding: 0.5rem 1rem;
            border: none;
            cursor: pointer;
            transition: all 0.3s;
        }

        .login-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 0 25px var(--neon-green);
        }

        /* ===== TITLE BOX ===== */
        .title-box {
            text-align: center;
            padding: 3.5rem 2rem;
            border-radius: 25px;
            margin-top: 1.5rem;
            margin-bottom: 2rem;
            background: radial-gradient(circle at top left, rgba(120,0,255,0.4), rgba(0,0,0,0.2));
            box-shadow: 0 0 35px rgba(255, 215, 0, 0.25), inset 0 0 25px rgba(0,255,255,0.1);
            border: 2px solid rgba(255,255,255,0.1);
            position: relative;
            overflow: hidden;
        }

        .title-box::before {
            content: "";
            position: absolute;
            top: -3px; left: -3px;
            width: calc(100% + 6px);
            height: calc(100% + 6px);
            background: linear-gradient(90deg, var(--neon-green), var(--gold), var(--purple), var(--neon-green));
            background-size: 400%;
            z-index: -1;
            filter: blur(12px);
            opacity: 0.8;
            border-radius: 25px;
            animation: borderGlow 6s linear infinite;
        }

        @keyframes borderGlow {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .main-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 4.5rem;
            font-weight: 800;
            color: var(--gold);
            text-shadow: 0 0 20px rgba(255,255,100,0.8), 0 0 35px rgba(0,255,255,0.3);
            letter-spacing: 4px;
        }

        .title-subtext {
            font-size: 1.5rem;
            color: #CCEEFF;
            margin-top: 1rem;
            font-weight: 400;
            text-shadow: 0 0 10px rgba(0,255,200,0.4);
        }

        .title-separator {
            width: 200px;
            height: 5px;
            margin: 1.5rem auto;
            background: linear-gradient(90deg, var(--neon-green), var(--gold), var(--purple));
            border-radius: 10px;
            animation: lineFlow 4s infinite linear;
        }

        @keyframes lineFlow {
            0% { background-position: 0%; }
            100% { background-position: 200%; }
        }

        /* ===== INTRO & FEATURES ===== */
        .intro-box {
            text-align: center;
            padding: 2rem 3rem;
            border-radius: 20px;
            background-color: rgba(255,255,255,0.05);
            margin-top: 2rem;
            box-shadow: 0 0 20px rgba(0,255,100,0.2);
        }

        .feature-box {
            background: linear-gradient(145deg, rgba(20, 0, 40, 0.7), rgba(60, 0, 80, 0.7));
            border: 2px solid rgba(255, 215, 0, 0.2);
            border-radius: 20px;
            padding: 2rem 1.5rem;
            text-align: center;
            transition: all 0.4s ease-in-out;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 25px rgba(0, 255, 0, 0.15);
        }
        .feature-box * {
             position: relative;
            z-index: 1; /* ensures content stays above glow */
        }
        .feature-box:hover::before {
            opacity: 1;
            animation: glowing 3s linear infinite;
        }
    

        .feature-box::before {
            content: "";
            position: absolute;
            top: -2px; left: -2px;
            width: calc(100% + 4px);
            height: calc(100% + 4px);
            background: linear-gradient(45deg, #00ff99, #00ffff, #ff00ff, #ffcc00);
            background-size: 300%;
            border-radius: 20px;
            z-index: 0;
            filter: blur(6px);
            opacity: 0;
            transition: opacity 0.5s;
        }

        @keyframes glowing {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .stButton>button {
            background: linear-gradient(90deg, var(--purple), var(--neon-green));
            color: black;
            font-weight: 800;
            border-radius: 10px;
            font-size: 1.3rem;
            border: none;
            transition: all 0.3s;
        }

        .stButton>button:hover {
            transform: scale(1.05);
            box-shadow: 0 0 25px var(--neon-green);
        }
        </style>
    """, unsafe_allow_html=True)

    # --------------------------------------------
    # HEADER SECTION (FULL WIDTH + LOGIN RIGHT)
    # --------------------------------------------
    header_cols = st.columns([0.85, 0.15])
    with header_cols[0]:
        st.markdown("""
            <div class="header-bar">
                <div>
                    <div class="header-text">INFERABOARD.AI</div>
                    <div class="header-sub">Empowering Data • Simplifying Decisions • Driven by Intelligence</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with header_cols[1]:
        st.button("🔑 Login", key="header_login_btn", on_click=login_action, type="secondary")

    # --------------------------------------------
    # TITLE SECTION
    # --------------------------------------------
    st.markdown("""
        <div class="title-box">
            <h1 class="main-title">🌐 INFERABOARD</h1>
            <div class="title-separator"></div>
            <p class="title-subtext">AI-Powered Dashboard Generator for Smarter Insights</p>
        </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------
    # INTRO SECTION
    # --------------------------------------------
    st.markdown("""
        <div class="intro-box">
            <p><b>Inferaboard</b> transforms raw data into dynamic dashboards with the power of AI.  
            Analyze, visualize, and predict — all through natural language.  
            The future of analytics starts here.</p>
        </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------
    # FEATURES SECTION
    # --------------------------------------------
    st.markdown("## ✨ Key Highlights")

    row1 = st.columns(3)
    row2 = st.columns(3)

    features = [
        ("🧠", "Intelligent Analysis", "AI automatically cleans, processes, and visualizes your data."),
        ("🗣️", "Natural Language & Voice Queries", "Ask in plain English or use your voice — get instant visual insights."),
        ("⚡", "Real-Time Data Connections", "Connect to Google Sheets, APIs, SQL and stream live data."),
        ("🔮", "Smart Predictions", "Forecast trends and detect anomalies with ML-driven predictions."),
        ("👤", "Role-Based Access", "Admin, Analyst, and Viewer modes for controlled data access."),
        ("📈", "Multi-Format Data Support", "Seamlessly upload CSV, Excel, or image data for visualization.")
    ]

    for i, col in enumerate(row1):
        icon, title, desc = features[i]
        with col:
            st.markdown(f"""
                <div class="feature-box">
                    <span class="icon">{icon}</span>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
            """, unsafe_allow_html=True)

    for i, col in enumerate(row2):
        icon, title, desc = features[i+3]
        with col:
            st.markdown(f"""
                <div class="feature-box">
                    <span class="icon">{icon}</span>
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
            """, unsafe_allow_html=True)

    # --------------------------------------------
    # BUTTONS SECTION
    # --------------------------------------------
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.button("🔑 Login to Dashboard", use_container_width=True, on_click=login_action)
    with col_btn2:
        st.button("🚀 Get Started Now", use_container_width=True, on_click=login_action)

    st.markdown("<br><hr><p style='text-align:center; color:#bbb;'>© 2025 Inferaboard | Data. AI. Insights.</p>", unsafe_allow_html=True)

# --------------------------------------------
# ENTRY POINT
# --------------------------------------------
if __name__ == "__main__":
    main() 