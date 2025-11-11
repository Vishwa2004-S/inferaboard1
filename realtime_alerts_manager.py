import streamlit as st
import pandas as pd
import json
import os
import threading
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from typing import Dict, List
import schedule
from dotenv import load_dotenv
import logging
import hashlib

# Configure logging with ASCII-only characters for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('realtime_alerts.log')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class RealTimeSyncManager:
    def __init__(self):
        self.sync_config_file = "realtime_sync_config.json"
        self.alerts_config_file = "alerts_config.json"
        
        # Initialize components
        self.sync_thread = None
        self.alert_thread = None
        self.is_running = False
        
        # SMTP Configuration
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_pass = os.getenv('SMTP_PASS', '')
        
        # Enhanced SMTP configuration logging (ASCII only)
        logger.info("=" * 60)
        logger.info("SMTP CONFIGURATION STATUS - DEBUG MODE")
        logger.info("=" * 60)
        logger.info(f"SMTP Host: {self.smtp_host}")
        logger.info(f"SMTP Port: {self.smtp_port}")
        logger.info(f"SMTP User: {self.smtp_user}")
        logger.info(f"SMTP Password Set: {'YES' if self.smtp_pass else 'NO'}")
        
        if not self.smtp_user or not self.smtp_pass:
            logger.error("CRITICAL: SMTP credentials are missing or incomplete!")
            logger.error("   Please check your .env file for SMTP_USER and SMTP_PASS")
        else:
            logger.info("SUCCESS: SMTP credentials found in environment variables")
            
        # Test SMTP connection on startup
        self.smtp_working = self._test_smtp_connection()
        
        # Load configurations
        self.sync_config = self._load_sync_config()
        self.alerts_config = self._load_alerts_config()
        
        # Create directories if they don't exist
        os.makedirs("realtime_data", exist_ok=True)
        os.makedirs("alert_logs", exist_ok=True)
        os.makedirs("user_notifications", exist_ok=True)
    
    def _test_smtp_connection(self):
        """Test SMTP connection on startup with comprehensive debugging"""
        logger.info("")
        logger.info("INITIATING SMTP CONNECTION TEST")
        logger.info("=" * 50)
        
        if not self.smtp_user or not self.smtp_pass:
            logger.error("Cannot test SMTP: Missing credentials")
            return False
            
        try:
            logger.info(f"Step 1: Creating SMTP connection to {self.smtp_host}:{self.smtp_port}")
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
            logger.info("SUCCESS: SMTP connection object created")
            
            logger.info("Step 2: Setting debug level to 1 for detailed output")
            server.set_debuglevel(1)
            
            logger.info("Step 3: Sending EHLO command")
            server.ehlo()
            logger.info("SUCCESS: EHLO command successful")
            
            logger.info("Step 4: Starting TLS encryption")
            server.starttls()
            logger.info("SUCCESS: TLS started successfully")
            
            logger.info("Step 5: Sending EHLO again after TLS")
            server.ehlo()
            logger.info("SUCCESS: EHLO after TLS successful")
            
            logger.info(f"Step 6: Attempting login with user: {self.smtp_user}")
            server.login(self.smtp_user, self.smtp_pass)
            logger.info("SUCCESS: SMTP login successful")
            
            logger.info("Step 7: Closing connection")
            server.quit()
            logger.info("SUCCESS: SMTP connection closed properly")
            
            logger.info("SMTP CONNECTION TEST: SUCCESS!")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            logger.error("   Possible causes:")
            logger.error("   - Incorrect username or password")
            logger.error("   - For Gmail: Need to use App Password instead of regular password")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP Connection failed: {e}")
            logger.error("   Possible causes:")
            logger.error("   - Wrong SMTP host or port")
            logger.error("   - Firewall blocking connection")
            return False
        except Exception as e:
            logger.error(f"SMTP test failed with unexpected error: {e}")
            return False
    
    def _load_sync_config(self):
        """Load synchronization configuration"""
        if os.path.exists(self.sync_config_file):
            with open(self.sync_config_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_alerts_config(self):
        """Load alerts configuration"""
        if os.path.exists(self.alerts_config_file):
            with open(self.alerts_config_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_sync_config(self):
        """Save synchronization configuration"""
        with open(self.sync_config_file, 'w') as f:
            json.dump(self.sync_config, f, indent=2)
    
    def save_alerts_config(self):
        """Save alerts configuration"""
        with open(self.alerts_config_file, 'w') as f:
            json.dump(self.alerts_config, f, indent=2)
    
    def setup_data_source_sync(self, username: str, source_type: str, config: Dict):
        """Set up real-time synchronization for a data source"""
        sync_id = f"{username}_{source_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.sync_config[sync_id] = {
            "username": username,
            "source_type": source_type,
            "config": config,
            "created_at": datetime.now().isoformat(),
            "is_active": True,
            "last_sync": None,
            "sync_interval": config.get('sync_interval', 60),
            "last_data_hash": None
        }
        
        self.save_sync_config()
        logger.info(f"Sync setup for {username} - {source_type}")
        return sync_id
    
    def setup_alert_rule(self, username: str, dashboard_id: str, rule: Dict):
        """Set up an alert rule for a dashboard"""
        alert_id = f"{username}_{dashboard_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.alerts_config[alert_id] = {
            "username": username,
            "dashboard_id": dashboard_id,
            "rule": rule,
            "created_at": datetime.now().isoformat(),
            "is_active": True,
            "last_triggered": None,
            "trigger_count": 0
        }
        
        self.save_alerts_config()
        
        # Enhanced logging for alert setup (ASCII only)
        alert_email = rule.get('email')
        logger.info(f"ALERT RULE CREATED")
        logger.info(f"   Username: {username}")
        logger.info(f"   Alert ID: {alert_id}")
        logger.info(f"   Alert Name: {rule.get('name', 'Unnamed Rule')}")
        logger.info(f"   Condition: {rule.get('condition_type')} on {rule.get('column')}")
        if alert_email and alert_email.strip():
            logger.info(f"   Email configured: {alert_email}")
            logger.info(f"   SMTP Status: {'WORKING' if self.smtp_working else 'NOT WORKING'}")
        else:
            logger.warning(f"   No email configured for this alert rule")
        
        return alert_id
    
    def toggle_alert_rule(self, alert_id: str, is_active: bool):
        """Enable or disable an alert rule"""
        if alert_id in self.alerts_config:
            self.alerts_config[alert_id]['is_active'] = is_active
            self.save_alerts_config()
            logger.info(f"Alert {alert_id} {'enabled' if is_active else 'disabled'}")
            return True
        return False
    
    def delete_alert_rule(self, alert_id: str):
        """Delete an alert rule"""
        if alert_id in self.alerts_config:
            del self.alerts_config[alert_id]
            self.save_alerts_config()
            logger.info(f"Alert {alert_id} deleted")
            return True
        return False
    
    def _calculate_data_hash(self, data: pd.DataFrame) -> str:
        """Calculate hash of data to detect changes"""
        try:
            data_string = data.to_string()
            return hashlib.md5(data_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating data hash: {e}")
            return str(datetime.now().timestamp())
    
    def sync_google_sheets(self, sync_config: Dict) -> Dict:
        """Sync data from Google Sheets with improved change detection"""
        try:
            sheet_url = sync_config['config'].get('sheet_url')
            if not sheet_url:
                return {"success": False, "error": "No sheet URL provided"}
            
            if "/d/" in sheet_url:
                sheet_id = sheet_url.split("/d/")[1].split("/")[0]
            else:
                sheet_id = sheet_url
            
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            
            logger.info(f"Fetching data from Google Sheets: {sheet_url}")
            
            response = requests.get(csv_url)
            if response.status_code == 200:
                new_data = pd.read_csv(csv_url)
                logger.info(f"Successfully fetched {len(new_data)} rows from Google Sheets")
                
                new_data_hash = self._calculate_data_hash(new_data)
                previous_data_hash = sync_config.get('last_data_hash')
                
                has_changes = new_data_hash != previous_data_hash
                
                if has_changes:
                    logger.info(f"DATA CHANGES DETECTED in Google Sheets for {sync_config['username']}")
                    
                    previous_data_path = f"realtime_data/{sync_config['username']}_sheets.csv"
                    new_data.to_csv(previous_data_path, index=False)
                    
                    user_data_path = f"user_data/{sync_config['username']}.csv"
                    new_data.to_csv(user_data_path, index=False)
                    logger.info(f"Updated user data file: {user_data_path}")
                    
                    sync_config['last_data_hash'] = new_data_hash
                    
                    return {
                        "success": True, 
                        "has_changes": True,
                        "data_shape": f"{len(new_data)} rows, {len(new_data.columns)} columns",
                        "timestamp": datetime.now().isoformat(),
                        "data_hash": new_data_hash
                    }
                else:
                    logger.info(f"No data changes detected for {sync_config['username']}")
                    return {
                        "success": True,
                        "has_changes": False,
                        "timestamp": datetime.now().isoformat(),
                        "data_hash": new_data_hash
                    }
            else:
                logger.error(f"Google Sheets HTTP error: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Google Sheets sync error: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_rest_api(self, sync_config: Dict) -> Dict:
        """Sync data from REST API with improved change detection"""
        try:
            api_url = sync_config['config'].get('api_url')
            if not api_url:
                return {"success": False, "error": "No API URL provided"}
            
            logger.info(f"Fetching data from REST API: {api_url}")
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    new_data = pd.DataFrame(data)
                elif isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, list):
                            new_data = pd.DataFrame(value)
                            break
                    else:
                        new_data = pd.DataFrame([data])
                else:
                    return {"success": False, "error": "Unsupported data format"}
                
                logger.info(f"Successfully fetched {len(new_data)} rows from REST API")
                
                new_data_hash = self._calculate_data_hash(new_data)
                previous_data_hash = sync_config.get('last_data_hash')
                
                has_changes = new_data_hash != previous_data_hash
                
                if has_changes:
                    logger.info(f"DATA CHANGES DETECTED in REST API for {sync_config['username']}")
                    
                    previous_data_path = f"realtime_data/{sync_config['username']}_api.csv"
                    new_data.to_csv(previous_data_path, index=False)
                    
                    user_data_path = f"user_data/{sync_config['username']}.csv"
                    new_data.to_csv(user_data_path, index=False)
                    
                    sync_config['last_data_hash'] = new_data_hash
                    
                    return {
                        "success": True, 
                        "has_changes": True,
                        "data_shape": f"{len(new_data)} rows, {len(new_data.columns)} columns",
                        "timestamp": datetime.now().isoformat(),
                        "data_hash": new_data_hash
                    }
                else:
                    logger.info(f"No data changes detected for {sync_config['username']}")
                    return {
                        "success": True,
                        "has_changes": False,
                        "timestamp": datetime.now().isoformat(),
                        "data_hash": new_data_hash
                    }
            else:
                logger.error(f"REST API HTTP error: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"REST API sync error: {e}")
            return {"success": False, "error": str(e)}
    
    def sync_sql_database(self, sync_config: Dict) -> Dict:
        """Sync data from SQL Database with improved change detection"""
        try:
            db_config = sync_config['config']
            db_type = db_config.get('db_type')
            query = db_config.get('query')
            
            if not all([db_type, query]):
                return {"success": False, "error": "Missing database configuration"}
            
            logger.info(f"Fetching data from {db_type} database")
            
            if db_type == "MySQL":
                import pymysql
                connection = pymysql.connect(
                    host=db_config.get('host'),
                    user=db_config.get('user'),
                    password=db_config.get('password'),
                    database=db_config.get('dbname')
                )
            elif db_type == "PostgreSQL":
                import psycopg2
                connection = psycopg2.connect(
                    host=db_config.get('host'),
                    database=db_config.get('dbname'),
                    user=db_config.get('user'),
                    password=db_config.get('password')
                )
            elif db_type == "SQLite":
                import sqlite3
                connection = sqlite3.connect(db_config.get('dbname'))
            else:
                return {"success": False, "error": f"Unsupported database type: {db_type}"}
            
            new_data = pd.read_sql(query, connection)
            connection.close()
            
            logger.info(f"Successfully fetched {len(new_data)} rows from {db_type} database")
            
            new_data_hash = self._calculate_data_hash(new_data)
            previous_data_hash = sync_config.get('last_data_hash')
            
            has_changes = new_data_hash != previous_data_hash
            
            if has_changes:
                logger.info(f"DATA CHANGES DETECTED in {db_type} database for {sync_config['username']}")
                
                previous_data_path = f"realtime_data/{sync_config['username']}_sql.csv"
                new_data.to_csv(previous_data_path, index=False)
                
                user_data_path = f"user_data/{sync_config['username']}.csv"
                new_data.to_csv(user_data_path, index=False)
                
                sync_config['last_data_hash'] = new_data_hash
                
                return {
                    "success": True, 
                    "has_changes": True,
                    "data_shape": f"{len(new_data)} rows, {len(new_data.columns)} columns",
                    "timestamp": datetime.now().isoformat(),
                    "data_hash": new_data_hash
                }
            else:
                logger.info(f"No data changes detected for {sync_config['username']}")
                return {
                    "success": True,
                    "has_changes": False,
                    "timestamp": datetime.now().isoformat(),
                    "data_hash": new_data_hash
                }
                
        except Exception as e:
            logger.error(f"{db_type} database sync error: {e}")
            return {"success": False, "error": str(e)}
    
    def _should_trigger_alert(self, alert_config: Dict) -> bool:
        """Check if alert should be triggered"""
        return True
    
    def check_alert_rules(self, username: str, data: pd.DataFrame) -> List[Dict]:
        """Check all alert rules for a user against current data"""
        triggered_alerts = []
        
        active_alerts_count = len([a for a in self.alerts_config.values() if a['username'] == username and a['is_active']])
        logger.info(f"Checking {active_alerts_count} active alert rules for {username}")
        
        for alert_id, alert_config in self.alerts_config.items():
            if (alert_config['username'] == username and 
                alert_config['is_active']):
                
                # Log alert details before evaluation
                alert_email = alert_config['rule'].get('email')
                alert_name = alert_config['rule'].get('name', 'Unnamed Rule')
                logger.info(f"Evaluating alert: {alert_name}")
                logger.info(f"   Alert ID: {alert_id}")
                logger.info(f"   Email configured: {alert_email if alert_email else 'NO EMAIL'}")
                logger.info(f"   SMTP Status: {'WORKING' if self.smtp_working else 'NOT WORKING'}")
                logger.info(f"   Active: {alert_config['is_active']}")
                
                is_condition_met = self._evaluate_alert_rule(alert_config['rule'], data)
                
                if is_condition_met:
                    logger.info(f"ALERT CONDITION MET: {alert_name}")
                    
                    alert_config['last_triggered'] = datetime.now().isoformat()
                    alert_config['trigger_count'] += 1
                    
                    triggered_alerts.append({
                        'alert_id': alert_id,
                        'rule': alert_config['rule'],
                        'dashboard_id': alert_config['dashboard_id'],
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # FIX: Wrap log_alert in try-except to prevent it from blocking email sending
                    try:
                        self._log_alert(alert_id, alert_config, data)
                    except Exception as e:
                        logger.warning(f"Could not log alert (non-critical): {e}")
                    
                    self._create_main_notification(alert_config, data)
                    
                    # ENHANCED: Email sending with error handling to ensure it runs
                    if alert_email and alert_email.strip():
                        logger.info("")
                        logger.info("=" * 60)
                        logger.info("ALERT EMAIL PROCESS - INITIATING")
                        logger.info("=" * 60)
                        logger.info(f"   Alert Name: {alert_name}")
                        logger.info(f"   Recipient: {alert_email}")
                        logger.info(f"   SMTP User: {self.smtp_user}")
                        logger.info(f"   SMTP Host: {self.smtp_host}:{self.smtp_port}")
                        logger.info(f"   SMTP Working: {self.smtp_working}")
                        
                        # FIX: Ensure email sending always runs even if other parts fail
                        try:
                            email_sent = self._send_email_notification_direct(alert_config, data, alert_email, username)
                            if email_sent:
                                logger.info("EMAIL SENT SUCCESSFULLY!")
                            else:
                                logger.error("EMAIL SENDING FAILED!")
                        except Exception as e:
                            logger.error(f"CRITICAL: Email sending failed with error: {e}")
                        logger.info("=" * 60)
                        logger.info("")
                    else:
                        logger.warning(f"No email configured for alert: {alert_name}")
                    
                else:
                    logger.debug(f"Alert condition not met for: {alert_name}")
        
        if triggered_alerts:
            self.save_alerts_config()
            logger.info(f"ALERTS TRIGGERED: {len(triggered_alerts)} alerts fired for {username}")
            for alert in triggered_alerts:
                logger.info(f"   {alert['rule'].get('name', 'Unnamed Rule')}")
        else:
            logger.info(f"No alerts triggered for {username}")
        
        return triggered_alerts
    
    def _create_main_notification(self, alert_config: Dict, data: pd.DataFrame):
        """Create detailed notification for main interface with threshold values"""
        try:
            rule = alert_config['rule']
            username = alert_config['username']
            
            condition_type = rule.get('condition_type')
            column = rule.get('column')
            value = rule.get('value')
            operator = rule.get('operator')
            
            if condition_type == 'threshold':
                if operator == 'greater_than':
                    triggered_values = data[data[column] > value][column].tolist()
                    notification_title = f"Threshold Alert: {rule.get('name', 'Unnamed Rule')}"
                    notification_message = f"""
THRESHOLD ALERT TRIGGERED

Condition: {column} > {value}
Triggered Values: {triggered_values[:5]}
Total Records: {len(data)}
Latest Value: {data[column].iloc[-1] if len(data) > 0 else 'N/A'}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                    """
                elif operator == 'less_than':
                    triggered_values = data[data[column] < value][column].tolist()
                    notification_title = f"Threshold Alert: {rule.get('name', 'Unnamed Rule')}"
                    notification_message = f"""
THRESHOLD ALERT TRIGGERED

Condition: {column} < {value}
Triggered Values: {triggered_values[:5]}
Total Records: {len(data)}
Latest Value: {data[column].iloc[-1] if len(data) > 0 else 'N/A'}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                    """
                elif operator == 'equals':
                    triggered_values = data[data[column] == value][column].tolist()
                    notification_title = f"Threshold Alert: {rule.get('name', 'Unnamed Rule')}"
                    notification_message = f"""
THRESHOLD ALERT TRIGGERED

Condition: {column} = {value}
Triggered Values: {triggered_values[:5]}
Total Records: {len(data)}
Latest Value: {data[column].iloc[-1] if len(data) > 0 else 'N/A'}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                    """
                else:
                    triggered_values = data[data[column] != value][column].tolist()
                    notification_title = f"Threshold Alert: {rule.get('name', 'Unnamed Rule')}"
                    notification_message = f"""
THRESHOLD ALERT TRIGGERED

Condition: {column} ≠ {value}
Triggered Values: {triggered_values[:5]}
Total Records: {len(data)}
Latest Value: {data[column].iloc[-1] if len(data) > 0 else 'N/A'}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                    """
            
            elif condition_type == 'anomaly':
                Q1 = data[column].quantile(0.25)
                Q3 = data[column].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                anomalies = data[(data[column] < lower_bound) | (data[column] > upper_bound)]
                anomaly_values = anomalies[column].tolist()
                
                notification_title = f"Anomaly Alert: {rule.get('name', 'Unnamed Rule')}"
                notification_message = f"""
ANOMALY ALERT TRIGGERED

Condition: Anomaly detected in {column}
Anomaly Values: {anomaly_values[:5]}
Total Anomalies: {len(anomalies)}
Normal Range: {lower_bound:.2f} to {upper_bound:.2f}
Total Records: {len(data)}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                """
            
            elif condition_type == 'trend':
                last_value = data[column].iloc[-1] if len(data) > 0 else 0
                avg_value = data[column].mean()
                change_percent = ((last_value - avg_value) / avg_value) * 100
                
                trend_direction = "increasing" if operator == 'increasing' else "decreasing"
                
                notification_title = f"Trend Alert: {rule.get('name', 'Unnamed Rule')}"
                notification_message = f"""
TREND ALERT TRIGGERED

Condition: {trend_direction} trend in {column} (> {value}% change)
Current Value: {last_value:.2f}
Average Value: {avg_value:.2f}
Change Percentage: {change_percent:.2f}%
Total Records: {len(data)}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                """
            else:
                notification_title = f"Alert: {rule.get('name', 'Unnamed Rule')}"
                notification_message = f"""
ALERT TRIGGERED

Condition Type: {condition_type}
Column: {column}
Value: {value}
Total Records: {len(data)}

Alert Rule: {rule.get('name', 'Unnamed Rule')}
Triggered At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review your dashboard for detailed insights.
                """
            
            self._create_user_notification(username, notification_title, notification_message)
            logger.info(f"Created main interface notification for {username}: {notification_title}")
            
        except Exception as e:
            logger.error(f"Error creating main notification: {e}")
    
    def _evaluate_alert_rule(self, rule: Dict, data: pd.DataFrame) -> bool:
        """Evaluate if an alert rule condition is met"""
        try:
            condition_type = rule.get('condition_type')
            column = rule.get('column')
            value = rule.get('value')
            operator = rule.get('operator', 'equals')
            
            if column not in data.columns:
                logger.warning(f"Column '{column}' not found in data")
                return False
            
            logger.info(f"Evaluating alert condition: {rule.get('name', 'Unnamed Rule')} on column '{column}'")
            
            if condition_type == 'threshold':
                if operator == 'greater_than':
                    result = bool((data[column] > value).any())
                    if result:
                        triggered_values = data[data[column] > value][column].tolist()
                        logger.info(f"THRESHOLD ALERT: {column} > {value} - Triggered values: {triggered_values}")
                    return result
                elif operator == 'less_than':
                    result = bool((data[column] < value).any())
                    if result:
                        triggered_values = data[data[column] < value][column].tolist()
                        logger.info(f"THRESHOLD ALERT: {column} < {value} - Triggered values: {triggered_values}")
                    return result
                elif operator == 'equals':
                    result = bool((data[column] == value).any())
                    if result:
                        logger.info(f"THRESHOLD ALERT: {column} = {value}")
                    return result
                elif operator == 'not_equals':
                    result = bool((data[column] != value).any())
                    if result:
                        logger.info(f"THRESHOLD ALERT: {column} ≠ {value}")
                    return result
            
            elif condition_type == 'anomaly':
                if len(data) < 2:
                    logger.warning(f"Need at least 2 data points for anomaly detection")
                    return False
                    
                Q1 = data[column].quantile(0.25)
                Q3 = data[column].quantile(0.75)
                IQR = Q3 - Q1
                
                if IQR == 0:
                    logger.warning(f"No variance in data for anomaly detection")
                    return False
                    
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                anomalies = data[(data[column] < lower_bound) | (data[column] > upper_bound)]
                result = len(anomalies) > 0
                if result:
                    anomaly_values = anomalies[column].tolist()
                    logger.info(f"ANOMALY ALERT: {len(anomalies)} anomalies in {column} - Anomaly values: {anomaly_values}")
                return result
            
            elif condition_type == 'trend':
                if len(data) >= 2:
                    last_value = data[column].iloc[-1]
                    avg_value = data[column].mean()
                    threshold = value
                    
                    if operator == 'increasing' and last_value > avg_value * (1 + threshold/100):
                        change_percent = ((last_value - avg_value) / avg_value) * 100
                        logger.info(f"TREND ALERT: {column} increasing - Last: {last_value:.2f}, Avg: {avg_value:.2f}, Change: {change_percent:.2f}%")
                        return True
                    elif operator == 'decreasing' and last_value < avg_value * (1 - threshold/100):
                        change_percent = ((avg_value - last_value) / avg_value) * 100
                        logger.info(f"TREND ALERT: {column} decreasing - Last: {last_value:.2f}, Avg: {avg_value:.2f}, Change: {change_percent:.2f}%")
                        return True
                    else:
                        logger.info(f"No trend detected for {column} - Last: {last_value:.2f}, Avg: {avg_value:.2f}")
            
            logger.info(f"Alert condition not met for {rule.get('name', 'Unnamed Rule')}")
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating alert rule: {e}")
            return False
    
    def _log_alert(self, alert_id: str, alert_config: Dict, data: pd.DataFrame):
        """Log triggered alert to file - FIXED with better error handling"""
        try:
            log_entry = {
                'alert_id': alert_id,
                'rule': alert_config['rule'],
                'timestamp': datetime.now().isoformat(),
                'data_snapshot': {
                    'rows': len(data),
                    'columns': list(data.columns),
                    'triggered_value': self._get_triggered_value(alert_config['rule'], data)
                }
            }
            
            log_file = f"alert_logs/{alert_id}_{datetime.now().strftime('%Y%m%d')}.json"
            log_data = []
            
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        log_data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    log_data = []
            
            log_data.append(log_entry)
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            # Don't raise the exception, just log it and continue
            logger.warning(f"Could not log alert to file (non-critical): {e}")
    
    def _send_email_notification_direct(self, alert_config: Dict, data: pd.DataFrame, user_email: str, username: str) -> bool:
        """Send email notification directly using SMTP - UPDATED with creative content"""
        logger.info("STARTING EMAIL SENDING PROCESS")
        
        try:
            rule = alert_config['rule']
            
            if not user_email or not user_email.strip():
                logger.error("No valid email provided for alert")
                return False
            
            if not self.smtp_user or not self.smtp_pass:
                logger.error("SMTP credentials not configured. Email functionality disabled.")
                return False
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, user_email):
                logger.error(f"Invalid email format: {user_email}")
                return False
            
            # UPDATED: Creative subject line
            subject = f"🚨 ALERT: {rule.get('name', 'Unnamed Rule')} - {username} - Inferaboard AI Analytics"
            message_body = self._format_email_alert_message(rule, data, username)
            
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = user_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message_body, 'plain'))
            
            # SMTP DEBUGGING
            logger.info("SMTP DEBUGGING - STEP BY STEP")
            logger.info("=" * 50)
            
            try:
                # Step 1: Connect to SMTP server
                logger.info("Step 1/7: Creating SMTP connection...")
                logger.info(f"   Host: {self.smtp_host}")
                logger.info(f"   Port: {self.smtp_port}")
                
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                logger.info("SUCCESS: SMTP connection object created")
                
                # Step 2: Enable debug output
                logger.info("Step 2/7: Enabling SMTP debug output...")
                server.set_debuglevel(1)
                logger.info("SUCCESS: SMTP debug level set to 1")
                
                # Step 3: EHLO command
                logger.info("Step 3/7: Sending EHLO command...")
                server.ehlo()
                logger.info("SUCCESS: EHLO command successful")
                
                # Step 4: Start TLS
                logger.info("Step 4/7: Starting TLS encryption...")
                server.starttls()
                logger.info("SUCCESS: TLS started successfully")
                
                # Step 5: EHLO after TLS
                logger.info("Step 5/7: Sending EHLO after TLS...")
                server.ehlo()
                logger.info("SUCCESS: EHLO after TLS successful")
                
                # Step 6: Login
                logger.info("Step 6/7: Attempting SMTP login...")
                logger.info(f"   Username: {self.smtp_user}")
                
                server.login(self.smtp_user, self.smtp_pass)
                logger.info("SUCCESS: SMTP login successful")
                
                # Step 7: Send email
                logger.info("Step 7/7: Sending email message...")
                logger.info(f"   From: {self.smtp_user}")
                logger.info(f"   To: {user_email}")
                logger.info(f"   Subject: {subject}")
                
                text = msg.as_string()
                server.sendmail(self.smtp_user, user_email, text)
                logger.info("SUCCESS: Email sent successfully")
                
                # Final step: Quit
                logger.info("Final step: Closing SMTP connection...")
                server.quit()
                logger.info("SUCCESS: SMTP connection closed properly")
                
                logger.info("EMAIL SENT SUCCESSFULLY!")
                logger.info("=" * 50)
                return True
                
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Authentication failed at Step 6: {e}")
                return False
            except smtplib.SMTPConnectError as e:
                logger.error(f"SMTP Connection failed at Step 1: {e}")
                return False
            except smtplib.SMTPSenderRefused as e:
                logger.error(f"SMTP Sender refused at Step 7: {e}")
                return False
            except smtplib.SMTPRecipientsRefused as e:
                logger.error(f"SMTP Recipient refused at Step 7: {e}")
                return False
            except smtplib.SMTPException as e:
                logger.error(f"SMTP error occurred: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected SMTP error: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _format_email_alert_message(self, rule: Dict, data: pd.DataFrame, username: str) -> str:
        """Format detailed email alert message with creative content - UPDATED"""
        condition_type = rule.get('condition_type')
        column = rule.get('column')
        value = rule.get('value')
        operator = rule.get('operator')
        
        # Creative email header
        message = "🚨 INFERABOARD ALERT NOTIFICATION 🚨\n\n"
        message += "="*60 + "\n\n"
        message += f"📊 ALERT SUMMARY\n\n"
        message += f"🔸 Alert Name: {rule.get('name', 'Unnamed Rule')}\n"
        message += f"🔸 User: {username}\n"
        message += f"🔸 Triggered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"🔸 Status: ACTIVE\n\n"
        message += "="*60 + "\n\n"
        
        # Alert details section
        message += "📈 ALERT DETAILS\n\n"
        
        if condition_type == 'threshold':
            if operator == 'greater_than':
                triggered_values = data[data[column] > value][column].tolist()
                message += f"🎯 TYPE: Threshold Alert (Greater Than)\n\n"
                message += f"📋 CONDITION:\n"
                message += f"   • Column: {column}\n"
                message += f"   • Threshold: > {value}\n"
                message += f"   • Triggered Values: {triggered_values[:8]}\n"
                message += f"   • Total Records Exceeding: {len(triggered_values)}\n\n"
                message += f"💡 INSIGHT: Values have crossed the upper threshold limit\n\n"
            elif operator == 'less_than':
                triggered_values = data[data[column] < value][column].tolist()
                message += f"🎯 TYPE: Threshold Alert (Less Than)\n\n"
                message += f"📋 CONDITION:\n"
                message += f"   • Column: {column}\n"
                message += f"   • Threshold: < {value}\n"
                message += f"   • Triggered Values: {triggered_values[:8]}\n"
                message += f"   • Total Records Below: {len(triggered_values)}\n\n"
                message += f"💡 INSIGHT: Values have dropped below the minimum threshold\n\n"
            elif operator == 'equals':
                triggered_values = data[data[column] == value][column].tolist()
                message += f"🎯 TYPE: Threshold Alert (Equals)\n\n"
                message += f"📋 CONDITION:\n"
                message += f"   • Column: {column}\n"
                message += f"   • Target Value: = {value}\n"
                message += f"   • Matching Values: {triggered_values[:8]}\n"
                message += f"   • Total Matches: {len(triggered_values)}\n\n"
                message += f"💡 INSIGHT: Values matching the exact target have been detected\n\n"
            else:
                triggered_values = data[data[column] != value][column].tolist()
                message += f"🎯 TYPE: Threshold Alert (Not Equals)\n\n"
                message += f"📋 CONDITION:\n"
                message += f"   • Column: {column}\n"
                message += f"   • Excluded Value: ≠ {value}\n"
                message += f"   • Different Values: {triggered_values[:8]}\n"
                message += f"   • Total Different: {len(triggered_values)}\n\n"
                message += f"💡 INSIGHT: Values different from the specified value detected\n\n"
        
        elif condition_type == 'anomaly':
            Q1 = data[column].quantile(0.25)
            Q3 = data[column].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            anomalies = data[(data[column] < lower_bound) | (data[column] > upper_bound)]
            anomaly_values = anomalies[column].tolist()
            
            message += f"🎯 TYPE: Anomaly Detection Alert\n\n"
            message += f"📋 CONDITION:\n"
            message += f"   • Column: {column}\n"
            message += f"   • Anomaly Values: {anomaly_values[:8]}\n"
            message += f"   • Total Anomalies: {len(anomalies)}\n"
            message += f"   • Normal Range: {lower_bound:.2f} to {upper_bound:.2f}\n\n"
            message += f"💡 INSIGHT: Unusual patterns detected outside normal behavior range\n\n"
        
        elif condition_type == 'trend':
            last_value = data[column].iloc[-1] if len(data) > 0 else 0
            avg_value = data[column].mean()
            change_percent = ((last_value - avg_value) / avg_value) * 100
            
            trend_direction = "increasing" if operator == 'increasing' else "decreasing"
            
            message += f"🎯 TYPE: Trend Detection Alert\n\n"
            message += f"📋 CONDITION:\n"
            message += f"   • Column: {column}\n"
            message += f"   • Trend Direction: {trend_direction}\n"
            message += f"   • Change Threshold: > {value}%\n"
            message += f"   • Current Value: {last_value:.2f}\n"
            message += f"   • Average Value: {avg_value:.2f}\n"
            message += f"   • Actual Change: {change_percent:.2f}%\n\n"
            message += f"💡 INSIGHT: Significant {trend_direction} trend detected in the data\n\n"
        
        # Data statistics section
        message += "📊 DATA STATISTICS\n\n"
        message += f"   • Total Records Analyzed: {len(data):,}\n"
        if column in data.columns:
            message += f"   • Current Range: {data[column].min():.2f} to {data[column].max():.2f}\n"
            message += f"   • Latest Value: {data[column].iloc[-1]:.2f}\n"
            message += f"   • Average Value: {data[column].mean():.2f}\n"
            message += f"   • Median Value: {data[column].median():.2f}\n\n"
        
        # Action required section
        message += "="*60 + "\n\n"
        message += "🚀 RECOMMENDED ACTIONS\n\n"
        message += "🔹 Review the dashboard for detailed analysis\n"
        message += "🔹 Investigate the root cause of this alert\n"
        message += "🔹 Consider adjusting thresholds if needed\n"
        message += "🔹 Monitor for similar patterns in the future\n"
        message += "🔹 Share insights with relevant team members\n\n"
        
        # Footer
        message += "="*60 + "\n\n"
        message += "💼 Need help? Visit your Inferaboard dashboard for complete analysis.\n\n"
        message += "Best regards,\n"
        message += "🤖 Inferaboard AI Analytics System\n"
        message += "📧 Automated Alert Service\n"
        message += "🌐 Making Data Intelligence Accessible\n\n"
        message += "---\n"
        message += "This is an automated alert. Please do not reply to this email.\n"
        message += "To manage your alert preferences, visit your dashboard settings.\n"
        
        return message
    
    def _create_user_notification(self, username: str, title: str, message: str):
        """Create in-app notification for user"""
        try:
            notifications_file = f"user_notifications/{username}.json"
            notifications = []
            
            if os.path.exists(notifications_file):
                with open(notifications_file, 'r') as f:
                    notifications = json.load(f)
            
            notification = {
                'id': f"notif_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                'title': title,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'read': False,
                'type': 'alert'
            }
            
            notifications.insert(0, notification)
            notifications = notifications[:100]
            
            with open(notifications_file, 'w') as f:
                json.dump(notifications, f, indent=2)
                
            logger.info(f"Created notification for {username}: {title}")
            
        except Exception as e:
            logger.error(f"Error creating user notification: {e}")
    
    def _get_operator_text(self, operator: str) -> str:
        """Convert operator to human-readable text"""
        operator_map = {
            'greater_than': '>',
            'less_than': '<',
            'equals': '=',
            'not_equals': '≠',
            'increasing': 'increasing',
            'decreasing': 'decreasing'
        }
        return operator_map.get(operator, operator)
    
    def _get_triggered_value(self, rule: Dict, data: pd.DataFrame):
        """Get the value that triggered the alert"""
        try:
            condition_type = rule.get('condition_type')
            column = rule.get('column')
            value = rule.get('value')
            operator = rule.get('operator')
            
            if condition_type == 'threshold':
                if operator == 'greater_than':
                    return data[data[column] > value][column].iloc[0] if len(data[data[column] > value]) > 0 else None
                elif operator == 'less_than':
                    return data[data[column] < value][column].iloc[0] if len(data[data[column] < value]) > 0 else None
                elif operator == 'equals':
                    return data[data[column] == value][column].iloc[0] if len(data[data[column] == value]) > 0 else None
                elif operator == 'not_equals':
                    return data[data[column] != value][column].iloc[0] if len(data[data[column] != value]) > 0 else None
            elif condition_type == 'anomaly':
                Q1 = data[column].quantile(0.25)
                Q3 = data[column].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                anomalies = data[(data[column] < lower_bound) | (data[column] > upper_bound)]
                return anomalies[column].iloc[0] if len(anomalies) > 0 else None
            elif condition_type == 'trend':
                return data[column].iloc[-1] if len(data) > 0 else None
                
            return None
        except Exception as e:
            logger.error(f"Error getting triggered value: {e}")
            return None
    
    def get_user_alerts(self, username: str):
        """Get all alert rules for a user"""
        return {alert_id: config for alert_id, config in self.alerts_config.items() 
                if config['username'] == username}
    
    def get_sync_status(self, username: str) -> Dict:
        """Get synchronization status for a user"""
        user_syncs = {
            sync_id: config for sync_id, config in self.sync_config.items()
            if config['username'] == username
        }
        
        status = {
            'active_syncs': len([c for c in user_syncs.values() if c['is_active']]),
            'last_sync': None,
            'next_sync': None
        }
        
        active_syncs = [c for c in user_syncs.values() if c['is_active']]
        if active_syncs:
            last_syncs = [c.get('last_sync') for c in active_syncs if c.get('last_sync')]
            if last_syncs:
                status['last_sync'] = max(last_syncs)
            
            next_syncs = []
            for sync_config in active_syncs:
                if sync_config.get('last_sync'):
                    last_sync = datetime.fromisoformat(sync_config['last_sync'])
                    next_sync = last_sync + timedelta(seconds=sync_config.get('sync_interval', 60))
                    next_syncs.append(next_sync)
            
            if next_syncs:
                status['next_sync'] = min(next_syncs).isoformat()
        
        return status
    
    def start_sync_service(self):
        """Start the real-time synchronization service"""
        if self.is_running:
            return
        
        self.is_running = True
        
        def sync_worker():
            while self.is_running:
                try:
                    for sync_id, sync_config in self.sync_config.items():
                        if sync_config['is_active']:
                            last_sync = sync_config.get('last_sync')
                            sync_interval = sync_config.get('sync_interval', 60)
                            
                            if not last_sync or (
                                datetime.now() - datetime.fromisoformat(last_sync) > 
                                timedelta(seconds=sync_interval)
                            ):
                                logger.info(f"Running scheduled sync for: {sync_id}")
                                
                                source_type = sync_config['source_type']
                                sync_result = None
                                
                                if source_type == 'google_sheets':
                                    sync_result = self.sync_google_sheets(sync_config)
                                elif source_type == 'rest_api':
                                    sync_result = self.sync_rest_api(sync_config)
                                elif source_type == 'sql_database':
                                    sync_result = self.sync_sql_database(sync_config)
                                
                                if sync_result and sync_result.get('success'):
                                    sync_config['last_sync'] = datetime.now().isoformat()
                                    
                                    if sync_result.get('has_changes'):
                                        logger.info(f"SYNC COMPLETED WITH CHANGES: {sync_id}")
                                        
                                        username = sync_config['username']
                                        user_data_path = f"user_data/{username}.csv"
                                        if os.path.exists(user_data_path):
                                            try:
                                                data = pd.read_csv(user_data_path)
                                                logger.info(f"CHECKING ALERT RULES after data change for {username}")
                                                triggered_alerts = self.check_alert_rules(username, data)
                                                if triggered_alerts:
                                                    logger.info(f"ALERTS FIRED: {len(triggered_alerts)} alerts triggered for {username}")
                                                    for alert in triggered_alerts:
                                                        logger.info(f"   {alert['rule'].get('name', 'Unnamed Rule')}")
                                                else:
                                                    logger.info(f"No alerts triggered for {username}")
                                            except Exception as e:
                                                logger.error(f"Error checking alert rules: {e}")
                                    else:
                                        logger.info(f"Sync completed without changes: {sync_id}")
                                
                                self.save_sync_config()
                    
                    time.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Sync worker error: {e}")
                    time.sleep(30)
        
        self.sync_thread = threading.Thread(target=sync_worker, daemon=True)
        self.sync_thread.start()
        
        logger.info("Real-time sync service started")
    
    def stop_sync_service(self):
        """Stop the real-time synchronization service"""
        self.is_running = False
        logger.info("Real-time sync service stopped")
    
    def get_user_notifications(self, username: str, unread_only: bool = True) -> List[Dict]:
        """Get notifications for a user"""
        notifications_file = f"user_notifications/{username}.json"
        
        if not os.path.exists(notifications_file):
            return []
        
        try:
            with open(notifications_file, 'r') as f:
                notifications = json.load(f)
            
            if unread_only:
                notifications = [n for n in notifications if not n.get('read', False)]
            
            return sorted(notifications, key=lambda x: x['timestamp'], reverse=True)
        except:
            return []
    
    def mark_notification_read(self, username: str, notification_id: str):
        """Mark a notification as read"""
        notifications_file = f"user_notifications/{username}.json"
        
        if not os.path.exists(notifications_file):
            return
        
        try:
            with open(notifications_file, 'r') as f:
                notifications = json.load(f)
            
            for notification in notifications:
                if notification.get('id') == notification_id:
                    notification['read'] = True
            
            with open(notifications_file, 'w') as f:
                json.dump(notifications, f, indent=2)
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")

# Create global instance
realtime_manager = RealTimeSyncManager()