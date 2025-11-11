import streamlit as st
import pandas as pd
import json
import os
import base64
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import plotly.io as pio
from dotenv import load_dotenv
import shutil

# Configure Plotly for colored image exports
pio.templates.default = "plotly"

def ensure_figure_colors(fig):
    """Ensure figure has color configuration before export"""
    if fig is None:
        return fig
    
    # Ensure the figure has a color template
    if not fig.layout.template:
        fig.update_layout(template="plotly")
    
    return fig

# Import export manager
from export_sharing_manager import export_manager

# Load environment variables
load_dotenv()

# Constants
REPORTS_DIR = "reports"
DASHBOARDS_DIR = "saved_dashboards"
USERS_FILE = "users.json"

# Create directories if they don't exist
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(DASHBOARDS_DIR, exist_ok=True)

class DashboardManager:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')
    
    def send_email(self, to_email, subject, body, attachment_path=None):
        """Send email with optional attachment"""
        try:
            if not self.smtp_user or not self.smtp_pass:
                st.warning("SMTP credentials not configured. Email functionality disabled.")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}'
                )
                msg.attach(part)
            
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            text = msg.as_string()
            server.sendmail(self.smtp_user, to_email, text)
            server.quit()
            
            return True
        except Exception as e:
            st.error(f"Email sending failed: {str(e)}")
            return False
    
    def send_registration_email(self, user_email, username):
        """Send registration success email"""
        subject = "Welcome to Inferaboard AI Dashboard"
        body = f"""
Hello {username},

Welcome to Inferaboard AI Dashboard Generator!

You have successfully registered and can now start creating intelligent dashboards with AI-powered insights.

Key Features:
• AI-Powered Dashboard Generation
• Natural Language & Voice Queries
• Smart Forecasting & Anomaly Detection
• Automated Report Generation
• Role-Based Collaboration

Start exploring your data today!

Best regards,
Inferaboard Team
        """
        return self.send_email(user_email, subject, body)
    
    def send_login_email(self, user_email, username):
        """Send login success email"""
        subject = "Login Successful - Inferaboard AI Dashboard"
        body = f"""
Hello {username},

You have successfully logged into your Inferaboard account.

If this was you, no action is needed.
If you didn't initiate this login, please contact support immediately.

Happy analyzing!

Best regards,
Inferaboard Team
        """
        return self.send_email(user_email, subject, body)
    
    def send_report_share_email(self, user_email, sharer_name, report_name, access_level):
        """Send report share notification email"""
        subject = "Report Access Granted - Inferaboard"
        body = f"""
Hello,

You've been granted {access_level} access to the report "{report_name}" by {sharer_name}.

You can now access this report in your "Shared Reports" section.

Log in to review and analyze the shared dashboard.

Best regards,
Inferaboard Team
        """
        return self.send_email(user_email, subject, body)

class ReportGenerator:
    def __init__(self):
        self.dash_manager = DashboardManager()
    
    def image_to_base64(self, image_path):
        """Convert image to base64 string for CSV storage"""
        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as img_file:
                    base64_data = base64.b64encode(img_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{base64_data}"
            return ""
        except Exception as e:
            st.warning(f"Could not convert image to base64: {str(e)}")
            return ""
    
    def create_dashboard_thumbnail(self, chart_fig, username, dashboard_id, width=400, height=300):
        """Create a thumbnail image for the dashboard"""
        try:
            if chart_fig is None:
                return None
                
            user_dash_dir = os.path.join(DASHBOARDS_DIR, username)
            os.makedirs(user_dash_dir, exist_ok=True)
            
            thumbnail_path = os.path.join(user_dash_dir, f"{dashboard_id}_thumbnail.png")
            
            # Create thumbnail with specified dimensions
            fig_copy = ensure_figure_colors(chart_fig)
            fig_copy.update_layout(
                width=width,
                height=height,
                margin=dict(l=10, r=10, t=50, b=10)
            )
            
            pio.write_image(fig_copy, thumbnail_path, format="png", engine="kaleido", width=width, height=height)
            return thumbnail_path
        except Exception as e:
            st.warning(f"Could not create thumbnail: {str(e)}")
            return None
    
    def save_dashboard(self, username, dashboard_name, dashboard_type, df, chart_info, kpis=None, 
                      forecast_results=None, anomalies=None, ai_summary=None, chart_figures=None):
        """Save dashboard with all components including images"""
        
        # Create user directory
        user_dash_dir = os.path.join(DASHBOARDS_DIR, username)
        os.makedirs(user_dash_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_id = f"{username}_{dashboard_name.replace(' ', '_')}_{timestamp}"
        
        # Create thumbnail image from the first available chart
        thumbnail_path = None
        if chart_figures and len(chart_figures) > 0:
            thumbnail_path = self.create_dashboard_thumbnail(chart_figures[0], username, dashboard_id)
        
        # Save dashboard data
        dashboard_data = {
            "dashboard_id": dashboard_id,
            "username": username,
            "dashboard_name": dashboard_name,
            "dashboard_type": dashboard_type,
            "created_date": datetime.now().isoformat(),
            "dataset_name": "Uploaded Dataset",
            "kpis": kpis or {},
            "forecast_results": forecast_results or {},
            "anomalies": anomalies or {},
            "ai_summary": ai_summary or "",
            "chart_info": chart_info,
            "data_shape": f"{len(df)} rows, {len(df.columns)} columns",
            "thumbnail_path": thumbnail_path or ""
        }
        
        # Save dashboard metadata
        dashboard_file = os.path.join(user_dash_dir, f"{dashboard_id}.json")
        with open(dashboard_file, 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        # Generate and save CSV report with image
        self.generate_csv_report(dashboard_data, df, username, thumbnail_path)
        
        st.success(f"Dashboard '{dashboard_name}' saved successfully!")
        return dashboard_id
    
    def generate_csv_report(self, dashboard_data, df, username, thumbnail_path=None):
        """Generate CSV report for the dashboard with embedded image and AI summary"""
        
        user_report_dir = os.path.join(REPORTS_DIR, username)
        os.makedirs(user_report_dir, exist_ok=True)
        
        report_file = os.path.join(user_report_dir, f"report_{dashboard_data['dashboard_id']}.csv")
        
        # Convert image to base64 for CSV storage
        image_base64 = self.image_to_base64(thumbnail_path) if thumbnail_path else ""
        
        # Prepare comprehensive report data with AI summary
        report_data = {
            "Report ID": [dashboard_data['dashboard_id']],
            "User": [dashboard_data['username']],
            "Dashboard Name": [dashboard_data['dashboard_name']],
            "Dataset Name": [dashboard_data['dataset_name']],
            "Dashboard Type": [dashboard_data['dashboard_type']],
            "Created Date": [dashboard_data['created_date']],
            "Data Shape": [dashboard_data['data_shape']],
            "AI Summary": [dashboard_data.get('ai_summary', 'No AI summary available')],
            "Thumbnail Base64": [image_base64],
            "Image Available": ["Yes" if image_base64 else "No"],
            "KPIs": [json.dumps(dashboard_data.get('kpis', {}), indent=2)],
            "Forecast Results": [json.dumps(dashboard_data.get('forecast_results', {}), indent=2)],
            "Anomaly Points": [json.dumps(dashboard_data.get('anomalies', {}), indent=2)],
            "Chart Info": [json.dumps(dashboard_data.get('chart_info', {}), indent=2)],
            "Total Records": [len(df)],
            "Total Columns": [len(df.columns)],
            "Numerical Columns": [str(df.select_dtypes(include=['int64', 'float64']).columns.tolist())],
            "Categorical Columns": [str(df.select_dtypes(include=['object', 'category']).columns.tolist())],
            "Date Columns": [str(df.select_dtypes(include=['datetime64']).columns.tolist())]
        }
        
        # Add basic statistics for numerical columns
        numerical_cols = df.select_dtypes(include=['int64', 'float64']).columns
        for col in numerical_cols[:3]:  # Limit to first 3 numerical columns
            report_data[f"{col}_mean"] = [f"{df[col].mean():.2f}"]
            report_data[f"{col}_median"] = [f"{df[col].median():.2f}"]
            report_data[f"{col}_std"] = [f"{df[col].std():.2f}"]
            report_data[f"{col}_min"] = [f"{df[col].min():.2f}"]
            report_data[f"{col}_max"] = [f"{df[col].max():.2f}"]
        
        # Create CSV report
        report_df = pd.DataFrame(report_data)
        report_df.to_csv(report_file, index=False, encoding='utf-8')
        
        # Also save the image separately
        if thumbnail_path and os.path.exists(thumbnail_path):
            image_filename = f"dashboard_image_{dashboard_data['dashboard_id']}.png"
            image_report_path = os.path.join(user_report_dir, image_filename)
            shutil.copy2(thumbnail_path, image_report_path)
        
        return report_file
    
    def load_user_dashboards(self, username):
        """Load all dashboards for a user"""
        user_dash_dir = os.path.join(DASHBOARDS_DIR, username)
        
        if not os.path.exists(user_dash_dir):
            return []
        
        dashboards = []
        for file in os.listdir(user_dash_dir):
            if file.endswith('.json'):
                try:
                    with open(os.path.join(user_dash_dir, file), 'r') as f:
                        dashboard_data = json.load(f)
                        dashboards.append(dashboard_data)
                except Exception as e:
                    st.warning(f"Error loading dashboard {file}: {str(e)}")
        
        # Sort by creation date, newest first
        dashboards.sort(key=lambda x: x['created_date'], reverse=True)
        return dashboards
    
    def get_dashboard_image(self, username, dashboard_id):
        """Get dashboard image path"""
        # Try different possible image paths
        possible_paths = [
            os.path.join(DASHBOARDS_DIR, username, f"{dashboard_id}_thumbnail.png"),
            os.path.join(DASHBOARDS_DIR, username, f"{dashboard_id}.png")
        ]
        
        for image_path in possible_paths:
            if os.path.exists(image_path):
                return image_path
        return None
    
    def share_dashboard(self, dashboard_id, owner_username, target_username, access_level):
        """Share dashboard with another user"""
        try:
            # Load sharing database
            share_db_file = os.path.join(DASHBOARDS_DIR, "sharing_db.json")
            if os.path.exists(share_db_file):
                with open(share_db_file, 'r') as f:
                    sharing_db = json.load(f)
            else:
                sharing_db = {}
            
            # Add sharing record
            if dashboard_id not in sharing_db:
                sharing_db[dashboard_id] = []
            
            # Check if already shared
            existing_share = next((s for s in sharing_db[dashboard_id] if s['user'] == target_username), None)
            if existing_share:
                existing_share['access'] = access_level
            else:
                sharing_db[dashboard_id].append({
                    "user": target_username,
                    "access": access_level,
                    "shared_date": datetime.now().isoformat(),
                    "shared_by": owner_username
                })
            
            # Save sharing database
            with open(share_db_file, 'w') as f:
                json.dump(sharing_db, f, indent=2)
            
            # Send notification email
            users = self.load_users()
            target_user_email = users.get(target_username, {}).get('email', '')
            if target_user_email:
                self.dash_manager.send_report_share_email(
                    target_user_email, 
                    owner_username, 
                    dashboard_id.split('_')[1],  # Extract dashboard name
                    access_level
                )
            
            return True
        except Exception as e:
            st.error(f"Error sharing dashboard: {str(e)}")
            return False
    
    def get_shared_dashboards(self, username):
        """Get dashboards shared with user"""
        share_db_file = os.path.join(DASHBOARDS_DIR, "sharing_db.json")
        if not os.path.exists(share_db_file):
            return []
        
        with open(share_db_file, 'r') as f:
            sharing_db = json.load(f)
        
        shared_dashboards = []
        for dashboard_id, shares in sharing_db.items():
            user_share = next((s for s in shares if s['user'] == username), None)
            if user_share:
                # Load dashboard data
                owner = dashboard_id.split('_')[0]
                dashboard_file = os.path.join(DASHBOARDS_DIR, owner, f"{dashboard_id}.json")
                if os.path.exists(dashboard_file):
                    with open(dashboard_file, 'r') as f:
                        dashboard_data = json.load(f)
                        dashboard_data['access_level'] = user_share['access']
                        dashboard_data['shared_by'] = user_share['shared_by']
                        dashboard_data['shared_date'] = user_share['shared_date']
                        shared_dashboards.append(dashboard_data)
        
        return shared_dashboards
    
    def load_users(self):
        """Load users from JSON file"""
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        return {}

class DashboardSavingUI:
    def __init__(self):
        self.report_gen = ReportGenerator()
        self.export_manager = export_manager
    
    def show_save_dashboard_interface(self, username, df, chart_info, chart_figures=None, anomalies=None, forecast_results=None, dashboard_type="Auto-Generated"):
        """Show interface for saving current dashboard"""
        st.sidebar.write("---")
        st.sidebar.subheader("💾 Save Dashboard")
        
        dashboard_name = st.sidebar.text_input("Dashboard Name", value=f"Dashboard_{datetime.now().strftime('%Y%m%d_%H%M')}")
        
        # Auto-detect dashboard type from chart_info if not provided
        if not dashboard_type and chart_info:
            dashboard_type = chart_info.get('dashboard_type', 'Auto-Generated')
        
        # Display dashboard type (read-only)
        st.sidebar.write(f"**Dashboard Type:** {dashboard_type}")
        
        # Extract KPIs from chart info
        kpis = {}
        if chart_info and 'charts' in chart_info:
            for chart in chart_info['charts']:
                chart_type = chart.get('type', 'unknown')
                kpis[f"{chart_type}_chart"] = chart.get('title', 'No title')
        
        if st.sidebar.button("💾 Save Dashboard", use_container_width=True):
            if dashboard_name:
                # Ensure AI summary is included
                ai_summary = chart_info.get('ai_summary', '')
                if not ai_summary and 'ai_summary' in st.session_state:
                    ai_summary = st.session_state.get('ai_summary', '')
                
                dashboard_id = self.report_gen.save_dashboard(
                    username=username,
                    dashboard_name=dashboard_name,
                    dashboard_type=dashboard_type,
                    df=df,
                    chart_info=chart_info,
                    kpis=kpis,
                    forecast_results=forecast_results,
                    anomalies=anomalies,
                    ai_summary=ai_summary,
                    chart_figures=chart_figures
                )
                
                # Show preview
                if dashboard_id:
                    thumbnail_path = self.report_gen.get_dashboard_image(username, dashboard_id)
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        st.sidebar.image(thumbnail_path, caption="Saved Thumbnail", use_column_width=True)
                    
                    st.sidebar.success(f"Dashboard '{dashboard_name}' saved successfully!")
                    st.sidebar.info(f"Dashboard ID: {dashboard_id}")
                    
                    # Show download options immediately after saving
                    if chart_figures:
                        st.sidebar.write("---")
                        st.sidebar.subheader("📥 Download Reports")
                        
                        # CSV Download
                        report_path = os.path.join(REPORTS_DIR, username, f"report_{dashboard_id}.csv")
                        if os.path.exists(report_path):
                            with open(report_path, "rb") as file:
                                st.sidebar.download_button(
                                    label="📊 Download CSV Report",
                                    data=file,
                                    file_name=f"report_{dashboard_id}.csv",
                                    mime="text/csv",
                                    key=f"csv_{dashboard_id}"
                                )
                        
                        # PDF Download
                        if st.sidebar.button("📄 Generate PDF Report", key=f"pdf_gen_{dashboard_id}"):
                            with st.spinner("Generating PDF report..."):
                                # Create proper dashboard data for PDF
                                pdf_dashboard_data = {
                                    "dashboard_id": dashboard_id,
                                    "dashboard_name": dashboard_name,
                                    "dashboard_type": dashboard_type,
                                    "data_shape": f"{len(df)} rows, {len(df.columns)} columns",
                                    "ai_summary": ai_summary,
                                    "kpis": kpis,
                                    "charts": chart_info.get('charts', []) if chart_info else []
                                }
                                
                                pdf_path = self.export_manager.export_dashboard_pdf(
                                    pdf_dashboard_data, 
                                    chart_figures, 
                                    username
                                )
                                if pdf_path and os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as file:
                                        st.download_button(
                                            label="📥 Download PDF Report",
                                            data=file,
                                            file_name=f"dashboard_{dashboard_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                            mime="application/pdf",
                                            key=f"pdf_download_{dashboard_id}"
                                        )
                                    st.sidebar.success("PDF generated successfully!")
                                else:
                                    st.sidebar.error("Failed to generate PDF")
                    
                    # Clear anomalies and forecast data after saving
                    if 'anomalies_data' in st.session_state:
                        del st.session_state['anomalies_data']
                    if 'forecast_data' in st.session_state:
                        del st.session_state['forecast_data']
            else:
                st.sidebar.error("Please enter a dashboard name")
    
    def show_export_interface(self, username, dashboard_data, chart_figures):
        """Show export and sharing interface for a dashboard"""
        st.sidebar.write("---")
        st.sidebar.subheader("📤 Export & Share")
        
        # Export options
        export_format = st.sidebar.selectbox(
            "Export Format",
            ["PDF Report", "HTML Dashboard", "Chart Images", "Shareable Link", "Email Dashboard"]
        )
        
        if export_format == "PDF Report":
            if st.sidebar.button("📄 Generate PDF Report"):
                with st.spinner("Generating PDF report..."):
                    pdf_path = self.export_manager.export_dashboard_pdf(dashboard_data, chart_figures, username)
                    if pdf_path:
                        with open(pdf_path, "rb") as file:
                            st.sidebar.download_button(
                                label="📥 Download PDF",
                                data=file,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf"
                            )
                        st.sidebar.success("PDF report generated!")
        
        elif export_format == "HTML Dashboard":
            if st.sidebar.button("🌐 Generate HTML Dashboard"):
                with st.spinner("Generating HTML dashboard..."):
                    html_path = self.export_manager.export_dashboard_html(dashboard_data, chart_figures, username)
                    if html_path:
                        with open(html_path, "rb") as file:
                            st.sidebar.download_button(
                                label="📥 Download HTML",
                                data=file,
                                file_name=os.path.basename(html_path),
                                mime="text/html"
                            )
                        st.sidebar.success("HTML dashboard generated!")
        
        elif export_format == "Chart Images":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                img_format = st.selectbox("Format", ["png", "jpeg", "svg"])
            with col2:
                if st.button("🖼️ Export Charts"):
                    with st.spinner(f"Exporting charts as {img_format}..."):
                        for i, fig in enumerate(chart_figures):
                            chart_title = f"Chart_{i+1}"
                            if dashboard_data.get('charts', []):
                                chart_info = dashboard_data['charts'][i] if i < len(dashboard_data['charts']) else {}
                                chart_title = chart_info.get('title', f"Chart_{i+1}")
                            
                            img_path = self.export_manager.export_chart_image(fig, chart_title, username, img_format)
                            if img_path:
                                with open(img_path, "rb") as file:
                                    st.sidebar.download_button(
                                        label=f"📥 {chart_title}.{img_format}",
                                        data=file,
                                        file_name=os.path.basename(img_path),
                                        mime=f"image/{img_format}",
                                        key=f"download_chart_{i}"
                                    )
        
        elif export_format == "Shareable Link":
            st.sidebar.write("Create a shareable link for this dashboard:")
            access_type = st.sidebar.selectbox("Access Type", ["public", "private"])
            expiration = st.sidebar.slider("Expiration (days)", 1, 30, 7)
            
            if st.sidebar.button("🔗 Create Shareable Link"):
                with st.spinner("Creating shareable link..."):
                    share_url, link_id = self.export_manager.create_shareable_link(
                        dashboard_data, chart_figures, username, access_type, expiration
                    )
                    if share_url:
                        st.sidebar.success("Shareable link created!")
                        st.sidebar.code(share_url)
                        
                        # Copy to clipboard functionality
                        st.sidebar.write("Share this URL:")
                        st.sidebar.info(share_url)
        
        elif export_format == "Email Dashboard":
            st.sidebar.write("Send dashboard via email:")
            recipient_email = st.sidebar.text_input("Recipient Email")
            message = st.sidebar.text_area("Message", "Check out this dashboard I created with Inferaboard!")
            
            if st.sidebar.button("📧 Send Dashboard"):
                if recipient_email:
                    with st.spinner("Sending dashboard via email..."):
                        success = self.export_manager.send_dashboard_email(
                            recipient_email, dashboard_data, chart_figures, username, message
                        )
                        if success:
                            st.sidebar.success("Dashboard sent successfully!")
                        else:
                            st.sidebar.error("Failed to send dashboard")
                else:
                    st.sidebar.error("Please enter recipient email")
    
    def show_shared_links_management(self, username):
        """Show interface for managing shared links"""
        st.subheader("🔗 Manage Shared Links")
        
        shared_links = self.export_manager.get_shared_links(username)
        
        if not shared_links:
            st.info("No shared links created yet.")
            return
        
        for link in shared_links:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    st.write(f"**Link ID:** {link['link_id']}")
                    dashboard_name = link.get('dashboard_data', {}).get('dashboard_name', 'Unknown Dashboard')
                    st.write(f"**Dashboard:** {dashboard_name}")
                    st.write(f"**Created:** {datetime.fromisoformat(link['created_date']).strftime('%Y-%m-%d %H:%M')}")
                
                with col2:
                    st.write(f"**Access:** {link['access_type']}")
                    st.write(f"**Expires:** {datetime.fromisoformat(link['expiration_date']).strftime('%Y-%m-%d')}")
                    st.write(f"**Views:** {link['view_count']}")
                
                with col3:
                    # Generate share URL for display
                    base_url = "https://yourapp.com/view"  # Replace with your actual domain
                    share_url = f"{base_url}?id={link['link_id']}"
                    st.code(share_url)
                
                with col4:
                    if st.button("Revoke", key=f"revoke_{link['link_id']}"):
                        if self.export_manager.revoke_shareable_link(link['link_id'], username):
                            st.success("Link revoked!")
                            st.rerun()
                        else:
                            st.error("Failed to revoke link")
                
                st.write("---")
    
    def show_my_reports_interface(self, username):
        """Show user's saved reports and dashboards"""
        st.header("📊 My Reports & Dashboards")
        
        # User's own dashboards
        user_dashboards = self.report_gen.load_user_dashboards(username)
        
        # Shared dashboards
        shared_dashboards = self.report_gen.get_shared_dashboards(username)
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["My Dashboards", "Shared With Me", "Share Dashboard", "Manage Shared Links"])
        
        with tab1:
            self._display_dashboards_list(user_dashboards, username, is_owner=True)
        
        with tab2:
            if shared_dashboards:
                self._display_dashboards_list(shared_dashboards, username, is_owner=False)
            else:
                st.info("No dashboards have been shared with you yet.")
        
        with tab3:
            self._show_sharing_interface(username, user_dashboards)
        
        with tab4:
            self.show_shared_links_management(username)
    
    def _display_dashboards_list(self, dashboards, username, is_owner=True):
        """Display list of dashboards"""
        if not dashboards:
            st.info("No dashboards found. Create and save your first dashboard!")
            return
        
        for i, dashboard in enumerate(dashboards):
            with st.container():
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    # Display dashboard thumbnail if available
                    owner_username = dashboard['username'] if not is_owner else username
                    image_path = self.report_gen.get_dashboard_image(owner_username, dashboard['dashboard_id'])
                    if image_path and os.path.exists(image_path):
                        st.image(image_path, use_column_width=True)
                    else:
                        st.info("📊 No preview available")
                
                with col2:
                    st.subheader(dashboard['dashboard_name'])
                    st.write(f"**Type:** {dashboard['dashboard_type']}")
                    st.write(f"**Created:** {datetime.fromisoformat(dashboard['created_date']).strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Data:** {dashboard['data_shape']}")
                    
                    # Show AI summary snippet
                    if dashboard.get('ai_summary'):
                        st.write(f"**AI Summary:** {dashboard['ai_summary'][:100]}...")
                    else:
                        st.write("**AI Summary:** No summary available")
                    
                    # Show access level for shared dashboards
                    if not is_owner:
                        st.write(f"**Shared by:** {dashboard.get('shared_by', 'Unknown')}")
                        st.write(f"**Access:** {dashboard.get('access_level', 'view').title()}")
                        st.write(f"**Shared on:** {datetime.fromisoformat(dashboard.get('shared_date', dashboard['created_date'])).strftime('%Y-%m-%d %H:%M')}")
                
                with col3:
                    # Action buttons
                    if is_owner:
                        if st.button("📤 Share", key=f"share_{dashboard['dashboard_id']}"):
                            st.session_state[f'sharing_dashboard_{dashboard["dashboard_id"]}'] = True
                        
                        if st.button("🗑️ Delete", key=f"delete_{dashboard['dashboard_id']}"):
                            self._delete_dashboard(username, dashboard['dashboard_id'])
                            st.rerun()
                    else:
                        # For shared dashboards, show edit option if access is edit
                        if dashboard.get('access_level') == 'edit':
                            if st.button("✏️ Edit Dashboard", key=f"edit_{dashboard['dashboard_id']}"):
                                st.session_state[f'editing_dashboard_{dashboard["dashboard_id"]}'] = True
                    
                    # Download options for both CSV and PDF
                    st.write("**Download:**")
                    report_owner = dashboard['username'] if not is_owner else username
                    report_path = os.path.join(REPORTS_DIR, report_owner, f"report_{dashboard['dashboard_id']}.csv")
                    
                    if os.path.exists(report_path):
                        # CSV Download
                        with open(report_path, "rb") as file:
                            st.download_button(
                                label="📊 CSV",
                                data=file,
                                file_name=f"report_{dashboard['dashboard_id']}.csv",
                                mime="text/csv",
                                key=f"download_csv_{dashboard['dashboard_id']}",
                                use_container_width=True
                            )
                    
                    # PDF Download Button
                    if st.button("📄 PDF", key=f"pdf_{dashboard['dashboard_id']}", use_container_width=True):
                        # Use current session chart figures if available
                        current_chart_figures = st.session_state.get('chart_figures', [])
                        if current_chart_figures:
                            with st.spinner("Generating PDF..."):
                                pdf_dashboard_data = {
                                    "dashboard_id": dashboard['dashboard_id'],
                                    "dashboard_name": dashboard['dashboard_name'],
                                    "dashboard_type": dashboard['dashboard_type'],
                                    "data_shape": dashboard['data_shape'],
                                    "ai_summary": dashboard.get('ai_summary', ''),
                                    "kpis": dashboard.get('kpis', {}),
                                    "charts": dashboard.get('chart_info', {}).get('charts', []) if dashboard.get('chart_info') else []
                                }
                                
                                pdf_path = self.export_manager.export_dashboard_pdf(
                                    pdf_dashboard_data, 
                                    current_chart_figures, 
                                    username
                                )
                                if pdf_path and os.path.exists(pdf_path):
                                    with open(pdf_path, "rb") as file:
                                        st.download_button(
                                            label="📥 Download PDF Report",
                                            data=file,
                                            file_name=f"dashboard_{dashboard['dashboard_name']}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                            mime="application/pdf",
                                            key=f"pdf_download_{dashboard['dashboard_id']}"
                                        )
                                else:
                                    st.error("Failed to generate PDF - no charts available")
                        else:
                            st.error("No charts available for PDF generation")
                
                # Sharing interface for this dashboard
                if is_owner and st.session_state.get(f'sharing_dashboard_{dashboard["dashboard_id"]}', False):
                    self._show_single_sharing_interface(username, dashboard, dashboard['dashboard_id'])
                
                # Edit interface for shared dashboards
                if not is_owner and st.session_state.get(f'editing_dashboard_{dashboard["dashboard_id"]}', False):
                    self._show_edit_interface(username, dashboard, dashboard['dashboard_id'])
                
                st.write("---")
    
    def _show_single_sharing_interface(self, username, dashboard, dashboard_id):
        """Show sharing interface for a specific dashboard"""
        st.write(f"**Sharing: {dashboard['dashboard_name']}**")
        
        # Load users for sharing
        users = self.report_gen.load_users()
        other_users = [u for u in users.keys() if u != username]
        
        if other_users:
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                target_user = st.selectbox("User", other_users, key=f"target_user_{dashboard_id}")
            
            with col2:
                access_level = st.selectbox("Access", ["view", "edit"], key=f"access_{dashboard_id}")
            
            with col3:
                if st.button("Share", key=f"confirm_share_{dashboard_id}"):
                    success = self.report_gen.share_dashboard(
                        dashboard['dashboard_id'],
                        username,
                        target_user,
                        access_level
                    )
                    if success:
                        st.success(f"Shared with {target_user}!")
                        st.session_state[f'sharing_dashboard_{dashboard_id}'] = False
                    else:
                        st.error("Sharing failed")
        else:
            st.info("No other users available to share with.")
        
        if st.button("Cancel", key=f"cancel_share_{dashboard_id}"):
            st.session_state[f'sharing_dashboard_{dashboard_id}'] = False

    def _show_edit_interface(self, username, dashboard, dashboard_id):
        """Show edit interface for shared dashboards with edit access"""
        st.subheader(f"✏️ Editing: {dashboard['dashboard_name']}")
        
        # Load the original data
        owner_username = dashboard['username']
        original_data_path = os.path.join("user_data", f"{owner_username}.csv")
        
        if os.path.exists(original_data_path):
            original_df = pd.read_csv(original_data_path)
            
            st.write("### Modify Filters")
            st.info("You have edit access to this dashboard. You can modify the filters and save a new version.")
            
            # Create filters similar to auto_generate_dashboard
            numerical_cols = original_df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            categorical_cols = original_df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            filtered_df = original_df.copy()
            
            # Create filters for categorical columns
            filter_options = {}
            if categorical_cols:
                for j, col in enumerate(categorical_cols[:3]):
                    unique_values = original_df[col].unique().tolist()
                    selected_values = st.multiselect(
                        f"Filter by {col}", 
                        options=unique_values,
                        default=unique_values,
                        key=f"edit_cat_filter_{dashboard_id}_{j}"
                    )
                    filter_options[col] = selected_values
            
            # Create filters for numerical columns
            if numerical_cols:
                for j, col in enumerate(numerical_cols[:2]):
                    min_val, max_val = float(original_df[col].min()), float(original_df[col].max())
                    selected_range = st.slider(
                        f"Range for {col}", 
                        min_val, max_val, (min_val, max_val),
                        key=f"edit_num_filter_{dashboard_id}_{j}"
                    )
                    filter_options[col] = selected_range
            
            # Apply filters to the dataframe
            for col, value in filter_options.items():
                if col in categorical_cols:
                    if value:
                        filtered_df = filtered_df[filtered_df[col].isin(value)]
                elif col in numerical_cols:
                    filtered_df = filtered_df[
                        (filtered_df[col] >= value[0]) & 
                        (filtered_df[col] <= value[1])
                    ]
            
            st.write(f"**Filtered Data:** {len(filtered_df)} of {len(original_df)} records")
            
            # Show filtered data preview
            st.dataframe(filtered_df.head())
            
            # Regenerate dashboard with filtered data
            if st.button("🔄 Update Dashboard Preview", key=f"update_preview_{dashboard_id}"):
                st.session_state[f'filtered_df_{dashboard_id}'] = filtered_df
                st.session_state[f'show_updated_dashboard_{dashboard_id}'] = True
            
            # Show updated dashboard if available
            if st.session_state.get(f'show_updated_dashboard_{dashboard_id}', False):
                filtered_df = st.session_state.get(f'filtered_df_{dashboard_id}', filtered_df)
                
                # Import and regenerate dashboard with filtered data
                from main_dashboard import auto_generate_dashboard
                
                # Store the original session state to restore later
                original_chart_info = st.session_state.get('chart_info', {})
                original_chart_figures = st.session_state.get('chart_figures', [])
                
                # Generate new dashboard with filtered data
                st.subheader("Updated Dashboard Preview")
                auto_generate_dashboard(filtered_df)
                
                # Store updated chart info for saving
                st.session_state[f'updated_chart_info_{dashboard_id}'] = st.session_state.get('chart_info', {})
                st.session_state[f'updated_chart_figures_{dashboard_id}'] = st.session_state.get('chart_figures', [])
                
                # Restore original session state
                st.session_state['chart_info'] = original_chart_info
                st.session_state['chart_figures'] = original_chart_figures
            
            # Save as new version
            new_dashboard_name = st.text_input("New Dashboard Name", 
                                             value=f"{dashboard['dashboard_name']}_edited_{datetime.now().strftime('%H%M')}",
                                             key=f"new_name_{dashboard_id}")
            
            if st.button("💾 Save as New Version", key=f"save_edit_{dashboard_id}"):
                if new_dashboard_name:
                    # Get updated chart info and figures if available
                    updated_chart_info = st.session_state.get(f'updated_chart_info_{dashboard_id}', dashboard.get('chart_info', {}))
                    updated_chart_figures = st.session_state.get(f'updated_chart_figures_{dashboard_id}', [])
                    
                    # Create new dashboard with filtered data
                    new_dashboard_id = self.report_gen.save_dashboard(
                        username=username,
                        dashboard_name=new_dashboard_name,
                        dashboard_type=f"Edited - {dashboard['dashboard_type']}",
                        df=filtered_df,
                        chart_info=updated_chart_info,
                        kpis=dashboard.get('kpis', {}),
                        forecast_results=dashboard.get('forecast_results', {}),
                        anomalies=dashboard.get('anomalies', {}),
                        ai_summary=dashboard.get('ai_summary', ''),
                        chart_figures=updated_chart_figures
                    )
                    
                    if new_dashboard_id:
                        st.success(f"New version '{new_dashboard_name}' saved successfully!")
                        st.session_state[f'editing_dashboard_{dashboard_id}'] = False
                        # Clear temporary session state
                        for key in [f'filtered_df_{dashboard_id}', f'show_updated_dashboard_{dashboard_id}', 
                                  f'updated_chart_info_{dashboard_id}', f'updated_chart_figures_{dashboard_id}']:
                            if key in st.session_state:
                                del st.session_state[key]
                else:
                    st.error("Please enter a name for the new version")
            
            if st.button("Cancel", key=f"cancel_edit_{dashboard_id}"):
                st.session_state[f'editing_dashboard_{dashboard_id}'] = False
        else:
            st.error("Original data file not found for editing")
            if st.button("Cancel", key=f"cancel_edit_{dashboard_id}"):
                st.session_state[f'editing_dashboard_{dashboard_id}'] = False
    
    def _show_sharing_interface(self, username, user_dashboards):
        """Show interface for sharing dashboards"""
        st.subheader("Share Your Dashboards")
        
        if not user_dashboards:
            st.info("No dashboards available to share. Save a dashboard first!")
            return
        
        # Select dashboard to share
        dashboard_options = {d['dashboard_name']: d for d in user_dashboards}
        selected_dashboard_name = st.selectbox("Select Dashboard", list(dashboard_options.keys()))
        
        if selected_dashboard_name:
            dashboard = dashboard_options[selected_dashboard_name]
            
            # Load users for sharing
            users = self.report_gen.load_users()
            other_users = [u for u in users.keys() if u != username]
            
            if other_users:
                col1, col2 = st.columns(2)
                
                with col1:
                    target_user = st.selectbox("Share With", other_users)
                
                with col2:
                    access_level = st.selectbox("Access Level", ["view", "edit"])
                
                if st.button("🔗 Share Dashboard"):
                    success = self.report_gen.share_dashboard(
                        dashboard['dashboard_id'],
                        username,
                        target_user,
                        access_level
                    )
                    if success:
                        st.success(f"Dashboard shared with {target_user} ({access_level} access)")
                    else:
                        st.error("Failed to share dashboard")
            else:
                st.info("No other users available to share with.")
    
    def _delete_dashboard(self, username, dashboard_id):
        """Delete a dashboard"""
        try:
            # Delete dashboard files
            dashboard_file = os.path.join(DASHBOARDS_DIR, username, f"{dashboard_id}.json")
            
            # Delete all associated image files
            image_patterns = [
                f"{dashboard_id}.png",
                f"{dashboard_id}_thumbnail.png"
            ]
            
            # Delete report files
            report_patterns = [
                f"report_{dashboard_id}.csv"
            ]
            
            files_to_delete = [dashboard_file]
            
            # Add image files
            for pattern in image_patterns:
                file_path = os.path.join(DASHBOARDS_DIR, username, pattern)
                if os.path.exists(file_path):
                    files_to_delete.append(file_path)
            
            # Add report files
            for pattern in report_patterns:
                file_path = os.path.join(REPORTS_DIR, username, pattern)
                if os.path.exists(file_path):
                    files_to_delete.append(file_path)
            
            # Delete all files
            for file_path in files_to_delete:
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            st.success("Dashboard and all associated files deleted successfully!")
            return True
        except Exception as e:
            st.error(f"Error deleting dashboard: {str(e)}")
            return False

# Global instances
dash_manager = DashboardManager()
report_generator = ReportGenerator()
saving_ui = DashboardSavingUI()