import streamlit as st
import pandas as pd
import json
import os
import base64
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path
import plotly.io as pio
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import uuid
import requests
from dotenv import load_dotenv

# Configure Plotly for colored image exports
pio.templates.default = "plotly"
try:
    pio.kaleido.scope.default_format = "png"
    pio.kaleido.scope.default_width = 1200
    pio.kaleido.scope.default_height = 800
    pio.kaleido.scope.default_scale = 2
except Exception as e:
    print(f"Kaleido configuration warning: {e}")

# Try to import PDF libraries, fallback if not available
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    st.warning("PDF export disabled. Install: pip install fpdf2")

load_dotenv()

def ensure_figure_colors(fig):
    """Ensure figure has color configuration before export"""
    if fig is None:
        return fig
    
    # Ensure the figure has a color template
    if not fig.layout.template:
        fig.update_layout(template="plotly")
    
    return fig

class ExportSharingManager:
    def __init__(self):
        self.exports_dir = "exports"
        self.shared_links_dir = "shared_links"
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')
        
        # Create directories if they don't exist
        os.makedirs(self.exports_dir, exist_ok=True)
        os.makedirs(self.shared_links_dir, exist_ok=True)
        
        # Create shared_dashboards directory for web access
        self.shared_dashboards_dir = "shared_dashboards"
        os.makedirs(self.shared_dashboards_dir, exist_ok=True)
    
    def export_dashboard_pdf(self, dashboard_data, chart_figures, username):
        """Export dashboard as PDF report using fpdf2"""
        if not PDF_AVAILABLE:
            st.error("PDF export not available. Please install fpdf2: pip install fpdf2")
            return None
            
        try:
            user_export_dir = os.path.join(self.exports_dir, username)
            os.makedirs(user_export_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # FIX: Handle missing dashboard_name gracefully
            dashboard_name = dashboard_data.get('dashboard_name', 'unknown_dashboard')
            filename = f"dashboard_{dashboard_name}_{timestamp}.pdf"
            filepath = os.path.join(user_export_dir, filename)
            
            # Create PDF using fpdf2
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            # Set title
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, dashboard_data.get('dashboard_name', 'Dashboard Report'), 0, 1, 'C')
            pdf.ln(5)
            
            # Add generation date
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C')
            pdf.ln(10)
            
            # Add dashboard summary
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Dashboard Summary', 0, 1)
            pdf.set_font('Arial', '', 10)
            
            summary_lines = [
                f"Type: {dashboard_data.get('dashboard_type', 'Unknown')}",
                f"Data: {dashboard_data.get('data_shape', 'Unknown')}",
                f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ]
            
            for line in summary_lines:
                pdf.cell(0, 8, line, 0, 1)
            
            pdf.ln(5)
            
            # Add AI summary if available
            if dashboard_data.get('ai_summary'):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, 'AI Insights', 0, 1)
                pdf.set_font('Arial', '', 10)
                
                # Split AI summary into manageable chunks
                ai_summary = dashboard_data['ai_summary']
                # Limit summary length for PDF
                if len(ai_summary) > 500:
                    ai_summary = ai_summary[:500] + "..."
                
                pdf.multi_cell(0, 8, ai_summary)
                pdf.ln(5)
            
            # Add KPIs if available
            if dashboard_data.get('kpis'):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, 'Key Performance Indicators', 0, 1)
                pdf.set_font('Arial', '', 10)
                
                for kpi_name, kpi_value in dashboard_data['kpis'].items():
                    pdf.cell(0, 8, f"{kpi_name}: {kpi_value}", 0, 1)
                
                pdf.ln(5)
            
            # Add chart images
            if chart_figures:
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, 'Visualizations', 0, 1)
                pdf.set_font('Arial', '', 10)
                
                for i, fig in enumerate(chart_figures):
                    # Save chart as temporary image
                    temp_img_path = os.path.join(tempfile.gettempdir(), f"chart_{i}_{timestamp}.png")
                    try:
                        # FIXED: Ensure colors and use proper export
                        fig = ensure_figure_colors(fig)
                        pio.write_image(fig, temp_img_path, width=800, height=600, format="png", engine="kaleido")
                        
                        # Add chart title
                        chart_title = f"Chart {i+1}"
                        if dashboard_data.get('charts', []):
                            chart_info = dashboard_data['charts'][i] if i < len(dashboard_data['charts']) else {}
                            chart_title = chart_info.get('title', f"Chart {i+1}")
                        
                        pdf.cell(0, 8, chart_title, 0, 1)
                        
                        # Add image to PDF (resize to fit)
                        try:
                            pdf.image(temp_img_path, x=10, w=190)
                            pdf.ln(5)
                        except Exception as e:
                            pdf.cell(0, 8, f"Could not add chart image: {str(e)}", 0, 1)
                        
                        # Clean up temp file
                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)
                        
                        # Add page break if not last chart
                        if i < len(chart_figures) - 1:
                            pdf.add_page()
                    except Exception as e:
                        pdf.cell(0, 8, f"Error generating chart {i+1}: {str(e)}", 0, 1)
            
            # Add footer
            pdf.set_y(-15)
            pdf.set_font('Arial', 'I', 8)
            pdf.cell(0, 10, f'Generated by Inferaboard AI Dashboard | Report ID: {dashboard_data.get("dashboard_id", "N/A")}', 0, 0, 'C')
            
            # Save PDF
            pdf.output(filepath)
            return filepath
            
        except Exception as e:
            st.error(f"PDF export failed: {str(e)}")
            return None
    
    def export_dashboard_html(self, dashboard_data, chart_figures, username):
        """Export dashboard as standalone HTML file with actual dashboard images"""
        try:
            user_export_dir = os.path.join(self.exports_dir, username)
            os.makedirs(user_export_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dashboard_name = dashboard_data.get('dashboard_name', 'unknown_dashboard')
            filename = f"dashboard_{dashboard_name}_{timestamp}.html"
            filepath = os.path.join(user_export_dir, filename)
            
            # Create HTML content with actual dashboard images
            html_content = self._create_dashboard_html_with_images(dashboard_data, chart_figures)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return filepath
        except Exception as e:
            st.error(f"HTML export failed: {str(e)}")
            return None
    
    def _create_dashboard_html_with_images(self, dashboard_data, chart_figures):
        """Create HTML with actual dashboard chart images"""
        dashboard_name = dashboard_data.get('dashboard_name', 'Dashboard Report')
        dashboard_type = dashboard_data.get('dashboard_type', 'Unknown')
        data_shape = dashboard_data.get('data_shape', 'Unknown')
        ai_summary = dashboard_data.get('ai_summary', '')
        kpis = dashboard_data.get('kpis', {})
        
        # Generate actual chart images as base64
        chart_sections = ""
        for i, fig in enumerate(chart_figures):
            try:
                # FIXED: Convert plotly figure to base64 image with colors
                fig = ensure_figure_colors(fig)
                img_bytes = pio.to_image(fig, format='png', width=1000, height=600, engine="kaleido")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                
                chart_title = f"Visualization {i+1}"
                if dashboard_data.get('charts', []) and i < len(dashboard_data['charts']):
                    chart_info = dashboard_data['charts'][i]
                    chart_title = chart_info.get('title', f"Chart {i+1}")
                
                chart_sections += f"""
                <div class="chart-section">
                    <div class="chart-header">
                        <h3>{chart_title}</h3>
                    </div>
                    <div class="chart-image">
                        <img src="data:image/png;base64,{img_base64}" alt="{chart_title}" class="dashboard-chart">
                    </div>
                </div>
                """
            except Exception as e:
                chart_sections += f"""
                <div class="chart-section">
                    <div class="chart-header">
                        <h3>Chart {i+1}</h3>
                    </div>
                    <div class="chart-image">
                        <p class="error-message">Error displaying chart: {str(e)}</p>
                    </div>
                </div>
                """
        
        # Generate KPIs section
        kpis_section = ""
        if kpis:
            kpis_section = """
            <div class="kpis-section">
                <h2>📊 Key Performance Indicators</h2>
                <div class="kpis-grid">
            """
            for kpi_name, kpi_value in kpis.items():
                kpis_section += f"""
                    <div class="kpi-card">
                        <div class="kpi-name">{kpi_name}</div>
                        <div class="kpi-value">{kpi_value}</div>
                    </div>
                """
            kpis_section += """
                </div>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{dashboard_name} - Inferaboard Dashboard</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                    color: #333;
                }}
                
                .dashboard-container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.15);
                    overflow: hidden;
                }}
                
                .dashboard-header {{
                    background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
                    color: white;
                    padding: 40px;
                    text-align: center;
                }}
                
                .dashboard-header h1 {{
                    font-size: 2.8em;
                    font-weight: 300;
                    margin-bottom: 10px;
                }}
                
                .dashboard-header .subtitle {{
                    font-size: 1.2em;
                    opacity: 0.9;
                    margin-bottom: 5px;
                }}
                
                .dashboard-header .timestamp {{
                    font-size: 0.9em;
                    opacity: 0.7;
                }}
                
                .dashboard-content {{
                    padding: 40px;
                }}
                
                .info-section {{
                    background: #f8f9fa;
                    padding: 25px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    border-left: 5px solid #3498db;
                }}
                
                .info-section h2 {{
                    color: #2c3e50;
                    margin-bottom: 15px;
                    font-size: 1.6em;
                }}
                
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 15px;
                    margin-top: 15px;
                }}
                
                .info-item {{
                    padding: 10px;
                    background: white;
                    border-radius: 5px;
                    border-left: 3px solid #3498db;
                }}
                
                .info-item strong {{
                    color: #2c3e50;
                }}
                
                .ai-summary {{
                    background: #e3f2fd;
                    padding: 25px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    border-left: 5px solid #2196f3;
                }}
                
                .ai-summary h3 {{
                    color: #1976d2;
                    margin-bottom: 15px;
                    font-size: 1.4em;
                }}
                
                .kpis-section {{
                    margin-bottom: 40px;
                }}
                
                .kpis-section h2 {{
                    color: #2c3e50;
                    margin-bottom: 25px;
                    text-align: center;
                    font-size: 1.8em;
                }}
                
                .kpis-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                    gap: 20px;
                }}
                
                .kpi-card {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 25px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}
                
                .kpi-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 12px 35px rgba(0,0,0,0.2);
                }}
                
                .kpi-name {{
                    font-size: 0.95em;
                    opacity: 0.9;
                    margin-bottom: 10px;
                    font-weight: 500;
                }}
                
                .kpi-value {{
                    font-size: 2.2em;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                
                .charts-section {{
                    margin-top: 40px;
                }}
                
                .charts-section h2 {{
                    color: #2c3e50;
                    text-align: center;
                    margin-bottom: 40px;
                    font-size: 2em;
                }}
                
                .chart-section {{
                    background: white;
                    margin-bottom: 40px;
                    border-radius: 10px;
                    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                    border: 1px solid #e9ecef;
                    overflow: hidden;
                }}
                
                .chart-header {{
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    padding: 20px;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .chart-header h3 {{
                    color: #2c3e50;
                    margin: 0;
                    font-size: 1.3em;
                    font-weight: 600;
                }}
                
                .chart-image {{
                    padding: 30px;
                    text-align: center;
                }}
                
                .dashboard-chart {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    border: 1px solid #dee2e6;
                }}
                
                .error-message {{
                    color: #e74c3c;
                    font-style: italic;
                    padding: 20px;
                    background: #ffeaa7;
                    border-radius: 5px;
                }}
                
                .dashboard-footer {{
                    background: #2c3e50;
                    color: white;
                    padding: 30px;
                    text-align: center;
                    margin-top: 40px;
                }}
                
                .dashboard-footer p {{
                    margin: 5px 0;
                    opacity: 0.9;
                }}
                
                .dashboard-footer a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                
                .dashboard-footer a:hover {{
                    text-decoration: underline;
                }}
                
                @media (max-width: 768px) {{
                    .dashboard-container {{
                        margin: 10px;
                        border-radius: 10px;
                    }}
                    
                    .dashboard-header {{
                        padding: 25px;
                    }}
                    
                    .dashboard-header h1 {{
                        font-size: 2em;
                    }}
                    
                    .dashboard-content {{
                        padding: 20px;
                    }}
                    
                    .kpis-grid {{
                        grid-template-columns: 1fr;
                    }}
                    
                    .chart-image {{
                        padding: 15px;
                    }}
                    
                    .info-grid {{
                        grid-template-columns: 1fr;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="dashboard-container">
                <div class="dashboard-header">
                    <h1>📊 {dashboard_name}</h1>
                    <p class="subtitle">AI-Powered Dashboard Report</p>
                    <p class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M')}</p>
                </div>
                
                <div class="dashboard-content">
                    <div class="info-section">
                        <h2>Dashboard Overview</h2>
                        <div class="info-grid">
                            <div class="info-item">
                                <strong>Dashboard Type:</strong> {dashboard_type}
                            </div>
                            <div class="info-item">
                                <strong>Data Shape:</strong> {data_shape}
                            </div>
                            <div class="info-item">
                                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}
                            </div>
                            <div class="info-item">
                                <strong>Total Charts:</strong> {len(chart_figures)}
                            </div>
                        </div>
                    </div>
                    
                    {f'<div class="ai-summary"><h3>🤖 AI Insights</h3><p>{ai_summary}</p></div>' if ai_summary else ''}
                    
                    {kpis_section}
                    
                    <div class="charts-section">
                        <h2>📈 Dashboard Visualizations</h2>
                        {chart_sections}
                    </div>
                </div>
                
                <div class="dashboard-footer">
                    <p><strong>Generated by Inferaboard AI Dashboard Generator</strong></p>
                    <p>Report ID: {dashboard_data.get('dashboard_id', 'N/A')}</p>
                    <p><a href="https://inferaboard.com">Create your own interactive dashboards</a></p>
                    <p><small>This is an exported dashboard report with actual chart images.</small></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def export_chart_image(self, chart_figure, chart_title, username, format='png'):
        """Export individual chart as image"""
        try:
            user_export_dir = os.path.join(self.exports_dir, username, "charts")
            os.makedirs(user_export_dir, exist_ok=True)
            
            # Clean chart title for filename
            clean_title = "".join(c for c in chart_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chart_{clean_title}_{timestamp}.{format}"
            filepath = os.path.join(user_export_dir, filename)
            
            # FIXED: Export chart with colors
            fig = ensure_figure_colors(chart_figure)
            if format == 'png':
                pio.write_image(fig, filepath, width=1200, height=800, format="png", engine="kaleido")
            elif format == 'jpeg':
                pio.write_image(fig, filepath, format='jpeg', width=1200, height=800, engine="kaleido")
            elif format == 'svg':
                pio.write_image(fig, filepath, format='svg', engine="kaleido")
            
            return filepath
        except Exception as e:
            st.error(f"Chart export failed: {str(e)}")
            return None
    
    def create_shareable_link(self, dashboard_data, chart_figures, username, access_type="public", expiration_days=7):
        """Create shareable link for dashboard with proper web URL"""
        try:
            # Generate unique link ID
            link_id = str(uuid.uuid4())[:8]
            
            # Create comprehensive dashboard data for sharing
            dashboard_name = dashboard_data.get('dashboard_name', 'Unknown Dashboard')
            
            share_dashboard_data = {
                "link_id": link_id,
                "dashboard_name": dashboard_name,
                "dashboard_type": dashboard_data.get('dashboard_type', 'Unknown'),
                "username": username,
                "created_date": datetime.now().isoformat(),
                "data_shape": dashboard_data.get('data_shape', 'Unknown'),
                "ai_summary": dashboard_data.get('ai_summary', ''),
                "kpis": dashboard_data.get('kpis', {}),
                "chart_info": dashboard_data.get('chart_info', {}),
                "total_charts": len(chart_figures) if chart_figures else 0
            }
            
            share_data = {
                "link_id": link_id,
                "dashboard_data": share_dashboard_data,
                "created_by": username,
                "created_date": datetime.now().isoformat(),
                "expiration_date": (datetime.now() + timedelta(days=expiration_days)).isoformat(),
                "access_type": access_type,
                "view_count": 0,
                "is_active": True
            }
            
            # Create the complete shared dashboard HTML
            shared_html_path = self._create_shared_dashboard_html(link_id, share_dashboard_data, chart_figures)
            
            if shared_html_path:
                share_data["shared_html_path"] = shared_html_path
            
            # Save share data
            share_file = os.path.join(self.shared_links_dir, f"{link_id}.json")
            with open(share_file, 'w') as f:
                json.dump(share_data, f, indent=2)
            
            # Create proper web URL for the shared dashboard
            # For local development, use file:// protocol
            # For production, this would be your actual domain
            if os.path.exists(shared_html_path):
                # Get absolute path and convert to file URL
                absolute_path = os.path.abspath(shared_html_path)
                share_url = f"file:///{absolute_path}".replace("\\", "/")
                
                # Also create a simple HTTP server suggestion for local access
                local_url = f"http://localhost:8000/{self.shared_dashboards_dir}/{link_id}.html"
                
                st.success(f"✅ Shareable link created successfully!")
                st.info(f"**Dashboard:** {dashboard_name}")
                st.info(f"**Link ID:** {link_id}")
                st.info(f"**Access Type:** {access_type}")
                st.info(f"**Expires:** {(datetime.now() + timedelta(days=expiration_days)).strftime('%Y-%m-%d')}")
                
                st.subheader("🌐 How to Access the Shared Dashboard:")
                
                # Option 1: Direct file access
                st.write("**Option 1: Direct File Access**")
                st.code(share_url, language="text")
                st.write("Copy and paste this URL into your web browser")
                
                # Option 2: Local HTTP server
                st.write("**Option 2: Local HTTP Server**")
                st.code(f"python -m http.server 8000", language="bash")
                st.write("Then visit:")
                st.code(local_url, language="text")
                
                # Option 3: Manual file access
                st.write("**Option 3: Manual File Access**")
                st.code(f"Open file: {shared_html_path}", language="text")
                st.write("Right-click the file and open with your web browser")
                
                return share_url, link_id
            else:
                st.error("Failed to create shared dashboard HTML file")
                return None, None
                
        except Exception as e:
            st.error(f"Shareable link creation failed: {str(e)}")
            return None, None
    
    def _create_shared_dashboard_html(self, link_id, dashboard_data, chart_figures):
        """Create a complete shared dashboard HTML file with actual images"""
        try:
            html_file_path = os.path.join(self.shared_dashboards_dir, f"{link_id}.html")
            
            # Generate actual chart images as base64
            chart_sections = ""
            for i, fig in enumerate(chart_figures):
                try:
                    # FIXED: Convert plotly figure to base64 image with colors
                    fig = ensure_figure_colors(fig)
                    img_bytes = pio.to_image(fig, format='png', width=1000, height=600, engine="kaleido")
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    
                    chart_title = f"Visualization {i+1}"
                    if dashboard_data.get('chart_info', {}).get('charts', []) and i < len(dashboard_data['chart_info']['charts']):
                        chart_info = dashboard_data['chart_info']['charts'][i]
                        chart_title = chart_info.get('title', f"Chart {i+1}")
                    
                    chart_sections += f"""
                    <div class="chart-section">
                        <div class="chart-header">
                            <h3>{chart_title}</h3>
                        </div>
                        <div class="chart-image">
                            <img src="data:image/png;base64,{img_base64}" alt="{chart_title}" class="dashboard-chart">
                        </div>
                    </div>
                    """
                except Exception as e:
                    chart_sections += f"""
                    <div class="chart-section">
                        <div class="chart-header">
                            <h3>Chart {i+1}</h3>
                        </div>
                        <div class="chart-image">
                            <p class="error-message">Unable to display chart: {str(e)}</p>
                        </div>
                    </div>
                    """
            
            # Generate KPIs section
            kpis_section = ""
            kpis = dashboard_data.get('kpis', {})
            if kpis:
                kpis_section = """
                <div class="kpis-section">
                    <h2>📊 Key Performance Indicators</h2>
                    <div class="kpis-grid">
                """
                for kpi_name, kpi_value in kpis.items():
                    kpis_section += f"""
                        <div class="kpi-card">
                            <div class="kpi-name">{kpi_name}</div>
                            <div class="kpi-value">{kpi_value}</div>
                        </div>
                    """
                kpis_section += """
                    </div>
                </div>
                """
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{dashboard_data['dashboard_name']} - Shared Dashboard</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        padding: 20px;
                        color: #333;
                    }}
                    
                    .shared-container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 15px;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.15);
                        overflow: hidden;
                    }}
                    
                    .shared-header {{
                        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
                        color: white;
                        padding: 40px;
                        text-align: center;
                    }}
                    
                    .shared-header h1 {{
                        font-size: 2.8em;
                        font-weight: 300;
                        margin-bottom: 10px;
                    }}
                    
                    .shared-header .subtitle {{
                        font-size: 1.2em;
                        opacity: 0.9;
                        margin-bottom: 5px;
                    }}
                    
                    .shared-header .link-info {{
                        font-size: 0.9em;
                        opacity: 0.7;
                        margin-top: 10px;
                    }}
                    
                    .shared-content {{
                        padding: 40px;
                    }}
                    
                    .shared-info {{
                        background: #f8f9fa;
                        padding: 25px;
                        border-radius: 10px;
                        margin-bottom: 30px;
                        border-left: 5px solid #3498db;
                    }}
                    
                    .shared-info h2 {{
                        color: #2c3e50;
                        margin-bottom: 15px;
                        font-size: 1.6em;
                    }}
                    
                    .info-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 15px;
                        margin-top: 15px;
                    }}
                    
                    .info-item {{
                        padding: 10px;
                        background: white;
                        border-radius: 5px;
                        border-left: 3px solid #3498db;
                    }}
                    
                    .ai-summary {{
                        background: #e3f2fd;
                        padding: 25px;
                        border-radius: 10px;
                        margin-bottom: 30px;
                        border-left: 5px solid #2196f3;
                    }}
                    
                    .ai-summary h3 {{
                        color: #1976d2;
                        margin-bottom: 15px;
                        font-size: 1.4em;
                    }}
                    
                    .kpis-section {{
                        margin-bottom: 40px;
                    }}
                    
                    .kpis-section h2 {{
                        color: #2c3e50;
                        margin-bottom: 25px;
                        text-align: center;
                        font-size: 1.8em;
                    }}
                    
                    .kpis-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                        gap: 20px;
                    }}
                    
                    .kpi-card {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 25px;
                        border-radius: 10px;
                        text-align: center;
                        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                    }}
                    
                    .kpi-name {{
                        font-size: 0.95em;
                        opacity: 0.9;
                        margin-bottom: 10px;
                    }}
                    
                    .kpi-value {{
                        font-size: 2.2em;
                        font-weight: bold;
                        margin: 10px 0;
                    }}
                    
                    .charts-section {{
                        margin-top: 40px;
                    }}
                    
                    .charts-section h2 {{
                        color: #2c3e50;
                        text-align: center;
                        margin-bottom: 40px;
                        font-size: 2em;
                    }}
                    
                    .chart-section {{
                        background: white;
                        margin-bottom: 40px;
                        border-radius: 10px;
                        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                        border: 1px solid #e9ecef;
                        overflow: hidden;
                    }}
                    
                    .chart-header {{
                        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                        padding: 20px;
                        border-bottom: 1px solid #e9ecef;
                    }}
                    
                    .chart-header h3 {{
                        color: #2c3e50;
                        margin: 0;
                        font-size: 1.3em;
                    }}
                    
                    .chart-image {{
                        padding: 30px;
                        text-align: center;
                    }}
                    
                    .dashboard-chart {{
                        max-width: 100%;
                        height: auto;
                        border-radius: 8px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    }}
                    
                    .shared-footer {{
                        background: #2c3e50;
                        color: white;
                        padding: 30px;
                        text-align: center;
                    }}
                    
                    .shared-footer a {{
                        color: #3498db;
                        text-decoration: none;
                    }}
                    
                    @media (max-width: 768px) {{
                        .shared-container {{
                            margin: 10px;
                        }}
                        
                        .shared-header {{
                            padding: 25px;
                        }}
                        
                        .shared-header h1 {{
                            font-size: 2em;
                        }}
                        
                        .shared-content {{
                            padding: 20px;
                        }}
                        
                        .kpis-grid {{
                            grid-template-columns: 1fr;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="shared-container">
                    <div class="shared-header">
                        <h1>📊 {dashboard_data['dashboard_name']}</h1>
                        <p class="subtitle">Shared Dashboard • Inferaboard AI</p>
                        <p class="link-info">Link ID: {link_id} • Shared on {datetime.now().strftime('%Y-%m-%d at %H:%M')}</p>
                    </div>
                    
                    <div class="shared-content">
                        <div class="shared-info">
                            <h2>Dashboard Information</h2>
                            <div class="info-grid">
                                <div class="info-item">
                                    <strong>Type:</strong> {dashboard_data['dashboard_type']}
                                </div>
                                <div class="info-item">
                                    <strong>Data:</strong> {dashboard_data['data_shape']}
                                </div>
                                <div class="info-item">
                                    <strong>Created by:</strong> {dashboard_data['username']}
                                </div>
                                <div class="info-item">
                                    <strong>Charts:</strong> {dashboard_data['total_charts']} visualizations
                                </div>
                            </div>
                        </div>
                        
                        {f'<div class="ai-summary"><h3>🤖 AI Insights</h3><p>{dashboard_data["ai_summary"]}</p></div>' if dashboard_data.get('ai_summary') else ''}
                        
                        {kpis_section}
                        
                        <div class="charts-section">
                            <h2>📈 Dashboard Visualizations</h2>
                            {chart_sections}
                        </div>
                    </div>
                    
                    <div class="shared-footer">
                        <p><strong>Shared via Inferaboard AI Dashboard Generator</strong></p>
                        <p><a href="https://inferaboard.com">Create your own interactive dashboards</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(html_file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return html_file_path
        except Exception as e:
            st.error(f"Error creating shared dashboard HTML: {e}")
            return None
    
    def revoke_shareable_link(self, link_id, username):
        """Revoke a shareable link"""
        try:
            share_file = os.path.join(self.shared_links_dir, f"{link_id}.json")
            
            if os.path.exists(share_file):
                with open(share_file, 'r') as f:
                    share_data = json.load(f)
                
                # Check if user owns this link
                if share_data["created_by"] == username:
                    # Delete shared HTML file
                    shared_html_path = share_data.get("shared_html_path")
                    if shared_html_path and os.path.exists(shared_html_path):
                        os.remove(shared_html_path)
                    
                    # Delete share file
                    os.remove(share_file)
                    return True
            
            return False
        except Exception as e:
            st.error(f"Link revocation failed: {str(e)}")
            return False
    
    def get_shared_links(self, username):
        """Get all shared links created by user"""
        try:
            shared_links = []
            
            for file in os.listdir(self.shared_links_dir):
                if file.endswith('.json'):
                    filepath = os.path.join(self.shared_links_dir, file)
                    with open(filepath, 'r') as f:
                        share_data = json.load(f)
                    
                    if share_data["created_by"] == username:
                        shared_links.append(share_data)
            
            return sorted(shared_links, key=lambda x: x['created_date'], reverse=True)
        except Exception as e:
            st.error(f"Error loading shared links: {str(e)}")
            return []
    
    def send_dashboard_email(self, to_email, dashboard_data, chart_figures, username, message=""):
        """Send dashboard via email with attachments"""
        try:
            if not self.smtp_user or not self.smtp_pass:
                st.warning("SMTP credentials not configured. Email functionality disabled.")
                return False
            
            # Create temporary directory for attachments
            with tempfile.TemporaryDirectory() as temp_dir:
                attachments = []
                
                # Export dashboard as PDF (if available)
                if PDF_AVAILABLE:
                    pdf_path = self.export_dashboard_pdf(dashboard_data, chart_figures, username)
                    if pdf_path:
                        attachments.append(pdf_path)
                
                # Export main chart as image
                if chart_figures:
                    img_path = self.export_chart_image(chart_figures[0], dashboard_data.get('dashboard_name', 'Dashboard'), username)
                    if img_path:
                        attachments.append(img_path)
                
                # Create email
                msg = MIMEMultipart()
                msg['From'] = self.smtp_user
                msg['To'] = to_email
                msg['Subject'] = f"Inferaboard Dashboard: {dashboard_data.get('dashboard_name', 'Unknown Dashboard')}"
                
                # Email body
                body = f"""
Hello,

{message}

You're receiving this dashboard from {username} via Inferaboard.

Dashboard: {dashboard_data.get('dashboard_name', 'Unknown Dashboard')}
Type: {dashboard_data.get('dashboard_type', 'Unknown')}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Data: {dashboard_data.get('data_shape', 'Unknown')}

Best regards,
Inferaboard Team
                """
                
                msg.attach(MIMEText(body, 'plain'))
                
                # Add attachments
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        with open(attachment_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                        
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(attachment_path)}'
                        )
                        msg.attach(part)
                
                # Send email
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

# Global instance
export_manager = ExportSharingManager()