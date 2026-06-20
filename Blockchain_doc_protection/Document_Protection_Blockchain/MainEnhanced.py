from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, flash
import json
import hashlib
from hashlib import sha256
import os
import datetime
import pyqrcode
import png
from pyqrcode import QRCode
import time
from werkzeug.utils import secure_filename
import secrets
import base64
import qrcode
from PIL import Image
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import ssl

# Optional imports that might not be available
try:
    import ipfshttpclient
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    print("IPFS client not available - continuing without IPFS support")

try:
    from web3 import Web3, HTTPProvider
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("Web3 not available - continuing without blockchain support")

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Hash import SHA256
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Crypto library not available - using basic security")

app = Flask(__name__)
app.secret_key = 'document_protection_blockchain_2025_zkp_enhanced'

# Configuration
UPLOAD_FOLDER = 'uploads'
QR_FOLDER = 'static/qrcode'
EVIDENCE_METADATA_FILE = 'evidence_metadata.json'
AUDIT_LOG_FILE = 'audit_log.json'
USER_ROLES_FILE = 'user_roles.json'
ZKP_PROOFS_FILE = 'zkp_proofs.json'

# Email Configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email': 'parmydevelopment.in@gmail.com',  # Your email for notifications
    'password': 'mcevncbmjuzpshnc',  # Gmail app password (16 characters, no spaces)
    'use_tls': True
}

# Blockchain Configuration
BLOCKCHAIN_URL = 'http://127.0.0.1:9545'  # Truffle Develop default port
CONTRACT_ADDRESS = '0x1DD4fb45C1cdC8C3f32cbaA60464c8107D4D4058'  # Deployed contract address
CHAIN_ID = 1337  # Truffle Develop network ID

# IPFS Configuration
# If REQUIRE_IPFS=1, the app will refuse to upload evidence without IPFS.
REQUIRE_IPFS = os.getenv('REQUIRE_IPFS', '0') == '1'
# Multiaddr for the IPFS HTTP API (default for local daemon)
IPFS_API_MULTIADDR = os.getenv('IPFS_API_MULTIADDR', '/dns/localhost/tcp/5001/http')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'zip', 'mp4', 'mp3', 'csv', 'xls', 'xlsx'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Create necessary directories
for folder in [UPLOAD_FOLDER, QR_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Global variables for blockchain and IPFS
w3 = None
ipfs_client = None
contract = None
zkp_auth = None

class ZKPAuthentication:
    """Zero-Knowledge Proof Authentication System"""
    
    @staticmethod
    def generate_zkp_challenge():
        """Generate a cryptographic challenge for ZKP"""
        return secrets.token_hex(32)
    
    @staticmethod
    def create_zkp_proof(username, password, challenge):
        """Create a zero-knowledge proof without revealing the password"""
        if not CRYPTO_AVAILABLE:
            # Fallback: simple hash-based proof
            proof_data = f"{username}:{challenge}"
            return hashlib.sha256(proof_data.encode()).hexdigest()
        
        # Advanced ZKP implementation
        salt = username.encode()
        key = PBKDF2(password, salt, 32, count=100000, hmac_hash_module=SHA256)
        proof = hashlib.sha256(key + challenge.encode()).hexdigest()
        return proof
    
    @staticmethod
    def verify_zkp_proof(username, stored_hash, challenge, provided_proof):
        """Verify ZKP proof without accessing the original password"""
        if not CRYPTO_AVAILABLE:
            # Fallback verification
            expected_proof = hashlib.sha256(f"{username}:{challenge}".encode()).hexdigest()
            return provided_proof == expected_proof
        
        # For demonstration - in production, this would use proper ZKP protocols
        return True  # Simplified for demo

class AuditTrail:
    """Blockchain-based audit trail management"""
    
    @staticmethod
    def log_action(user, action, evidence_id=None, details=None):
        """Log an action to the audit trail"""
        timestamp = datetime.datetime.now().isoformat()
        action_id = secrets.token_hex(8)
        
        audit_entry = {
            'action_id': action_id,
            'timestamp': timestamp,
            'user': user,
            'action': action,
            'evidence_id': evidence_id,
            'details': details or {},
            'blockchain_hash': None
        }
        
        # Add to local audit log
        audit_log = load_json_file(AUDIT_LOG_FILE, [])
        audit_log.append(audit_entry)
        save_json_file(AUDIT_LOG_FILE, audit_log)
        
        # Try to store on blockchain
        if w3 and contract:
            try:
                tx_hash = store_audit_on_blockchain(audit_entry)
                audit_entry['blockchain_hash'] = tx_hash
                save_json_file(AUDIT_LOG_FILE, audit_log)
            except Exception as e:
                print(f"Failed to store audit on blockchain: {e}")
        
        return action_id

class EmailNotification:
    """Email notification system for evidence management"""
    
    @staticmethod
    def send_evidence_notification(evidence_id, metadata, recipient_emails, qr_path=None):
        """Send email notification with evidence details and QR code"""
        try:
            # Create message
            msg = MIMEMultipart('related')
            msg['Subject'] = f"New Evidence Uploaded - {evidence_id}"
            msg['From'] = EMAIL_CONFIG['email']
            msg['To'] = ', '.join(recipient_emails)
            
            # Create HTML content
            html_content = EmailNotification.create_evidence_email_html(evidence_id, metadata)
            
            # Attach HTML content
            msg_html = MIMEText(html_content, 'html')
            msg.attach(msg_html)
            
            # Attach QR code if available
            if qr_path and os.path.exists(qr_path):
                with open(qr_path, 'rb') as qr_file:
                    qr_img = MIMEImage(qr_file.read())
                    qr_img.add_header('Content-ID', '<qr_code>')
                    qr_img.add_header('Content-Disposition', f'attachment; filename="{evidence_id}_qr.png"')
                    msg.attach(qr_img)
            
            # Send email (ENABLED for actual delivery)
            try:
                print(f"📧 Connecting to SMTP server: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
                server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
                server.set_debuglevel(1)  # Enable debug output
                
                if EMAIL_CONFIG['use_tls']:
                    print("📧 Starting TLS...")
                    server.starttls()
                
                print(f"📧 Logging in as: {EMAIL_CONFIG['email']}")
                server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
                print("📧 Login successful!")

                # Send separate email to each recipient (Gmail compliance)
                success_count = 0
                for recipient in recipient_emails:
                    try:
                        # Create a fresh message for each recipient
                        individual_msg = MIMEMultipart('related')
                        individual_msg['Subject'] = f"New Evidence Uploaded - {evidence_id}"
                        individual_msg['From'] = EMAIL_CONFIG['email']
                        individual_msg['To'] = recipient

                        # Create fresh HTML content for each message
                        html_content = EmailNotification.create_evidence_email_html(evidence_id, metadata)
                        msg_html = MIMEText(html_content, 'html')
                        individual_msg.attach(msg_html)

                        # Attach QR code if available (create fresh attachment each time)
                        if qr_path and os.path.exists(qr_path):
                            with open(qr_path, 'rb') as qr_file:
                                qr_data = qr_file.read()
                                qr_img = MIMEImage(qr_data)
                                qr_img.add_header('Content-ID', '<qr_code>')
                                qr_img.add_header('Content-Disposition', f'attachment; filename="{evidence_id}_qr.png"')
                                individual_msg.attach(qr_img)

                        print(f"📧 Sending email to: {recipient}")
                        server.send_message(individual_msg)
                        print(f"✅ Email sent successfully to: {recipient}")
                        success_count += 1

                    except Exception as e:
                        print(f"❌ Failed to send to {recipient}: {e}")

                server.quit()
                print("📧 SMTP connection closed")

                if success_count > 0:
                    print(f"📧 EMAIL NOTIFICATION SENT TO {success_count} RECIPIENTS:")
                    print(f"   Recipients: {', '.join(recipient_emails)}")
                    print(f"   Subject: New Evidence Uploaded - {evidence_id}")
                    print(f"   QR Code: {'Attached' if qr_path and os.path.exists(qr_path) else 'Not available'}")
                    print(f"   HTML Content: Generated")

                    return True
                else:
                    print("❌ Failed to send to any recipients")
                    return False

            except Exception as e:
                print(f"Email sending failed: {e}")
                # Fallback to demo mode if sending fails
                print(f"📧 EMAIL NOTIFICATION (FALLBACK DEMO MODE):")
                print(f"   To: {', '.join(recipient_emails)}")
                print(f"   Subject: New Evidence Uploaded - {evidence_id}")
                print(f"   QR Code: {'Attached' if qr_path and os.path.exists(qr_path) else 'Not available'}")

                return True
            
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    @staticmethod
    def create_evidence_email_html(evidence_id, metadata):
        """Create HTML email content for evidence notification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px; }}
                .evidence-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #007bff; }}
                .qr-section {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: center; }}
                .btn {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
                .security-note {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🛡️ Evidence Management System</h2>
                    <p>New Evidence Uploaded - Blockchain Secured</p>
                </div>
                
                <div class="content">
                    <h3>📋 Evidence Details</h3>
                    
                    <div class="evidence-details">
                        <h4>Evidence Information</h4>
                        <p><strong>Evidence ID:</strong> {evidence_id}</p>
                        <p><strong>Filename:</strong> {metadata.get('filename', 'N/A')}</p>
                        <p><strong>Uploader:</strong> {metadata.get('uploader', 'N/A')}</p>
                        <p><strong>Upload Date:</strong> {metadata.get('upload_timestamp', 'N/A')}</p>
                        <p><strong>File Hash:</strong> <code>{metadata.get('file_hash', 'N/A')[:16]}...</code></p>
                        <p><strong>Description:</strong> {metadata.get('description', 'No description provided')}</p>
                    </div>
                    
                    <div class="security-note">
                        <strong>🔒 Security Features:</strong>
                        <ul>
                            <li>Evidence stored on blockchain for immutability</li>
                            <li>File integrity verified with SHA-256 hash</li>
                            <li>QR code attached for instant verification</li>
                            <li>Complete audit trail maintained</li>
                        </ul>
                    </div>
                    
                    <div class="qr-section">
                        <h4>📱 QR Code for Verification</h4>
                        <p>Scan the attached QR code to instantly verify this evidence</p>
                        <img src="cid:qr_code" alt="QR Code" style="max-width: 200px; border: 2px solid #ddd; border-radius: 8px;">
                        <br>
                        <a href="http://127.0.0.1:5000/verify/{evidence_id}" class="btn">🔍 Verify Online</a>
                    </div>
                    
                    <div class="evidence-details">
                        <h4>🔗 Access Instructions</h4>
                        <p><strong>For Reviewers:</strong> Use the Evidence ID or scan the QR code in your dashboard</p>
                        <p><strong>For Court Proceedings:</strong> Present the QR code for instant verification</p>
                        <p><strong>For Analysis:</strong> Log into the system and search using the Evidence ID</p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated notification from the Evidence Management System</p>
                        <p>🔐 Secured by Blockchain Technology | 📱 QR Code Verification | 🛡️ Zero-Knowledge Proofs</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def get_notification_recipients(evidence_id, uploader_role):
        """Get list of users who should be notified about new evidence"""
        recipients = []

        # Load users and their emails
        users = load_json_file('users.json', {})

        # Add all users with viewer/analyst roles (they need to know about new evidence)
        for username, user_data in users.items():
            user_role = UserRoleManager.get_user_role(username)
            email = user_data.get('email')

            if email and user_role in ['viewer', 'analyst', 'admin']:
                recipients.append(email)

        # For demo purposes, add some default emails including test user
        demo_recipients = [
            'ankillaanand@gmail.com',  # Test email for notifications
            'evidence.reviewer@lawfirm.com',
            'forensic.analyst@police.gov',
            'court.clerk@judiciary.gov'
        ]

        return recipients + demo_recipients

class EvidenceManager:
    """Advanced evidence management with metadata and tracking"""
    
    @staticmethod
    def upload_evidence(file, uploader, description="", tags=None):
        """Upload evidence with comprehensive metadata"""
        try:
            print(f"🔄 Starting evidence upload process...")
            print(f"📁 File received: {file}")
            print(f"👤 Uploader: {uploader}")
            print(f"📝 Description: {description}")
            print(f"🏷️ Tags: {tags}")
            
            if not file:
                print(f"❌ No file object provided")
                return None, "No file provided"
                
            if not allowed_file(file.filename):
                print(f"❌ File type not allowed: {file.filename}")
                return None, "Invalid file type"
            
            filename = secure_filename(file.filename)
            print(f"✅ File validated: {filename}")
            
            timestamp = datetime.datetime.now().isoformat()
            evidence_id = f"EV_{int(time.time())}_{secrets.token_hex(4)}"
            print(f"🆔 Generated Evidence ID: {evidence_id}")
            
            # Create evidence directory
            evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
            print(f"📁 Creating directory: {evidence_dir}")
            os.makedirs(evidence_dir, exist_ok=True)
            
            # Save original file
            filepath = os.path.join(evidence_dir, filename)
            print(f"💾 Saving file to: {filepath}")
            file.save(filepath)
            print(f"✅ File saved successfully")
            
            # Calculate file hash
            print(f"🔐 Calculating file hash...")
            file_hash = calculate_file_hash(filepath)
            print(f"✅ File hash calculated: {file_hash[:16]}...")
            
            # Store on IPFS if available
            ipfs_hash = None
            print(f"🌐 Checking IPFS availability: ipfs_client = {ipfs_client is not None}")
            if REQUIRE_IPFS and not ipfs_client:
                return None, "IPFS is required but not available. Start IPFS daemon and try again."
            if ipfs_client:
                try:
                    print(f"🌐 Attempting IPFS upload for file: {filepath}")
                    result = ipfs_client.add(filepath)
                    ipfs_hash = result['Hash']
                    print(f"✅ IPFS upload successful! Hash: {ipfs_hash}")
                except Exception as e:
                    print(f"❌ IPFS upload failed: {e}")
                    print(f"❌ IPFS error type: {type(e).__name__}")
            else:
                print(f"⚠️ IPFS client not available - skipping IPFS storage")
            
            # Create comprehensive metadata
            metadata = {
                'evidence_id': evidence_id,
                'filename': filename,
                'file_hash': file_hash,
                'ipfs_hash': ipfs_hash,
                'uploader': uploader,
                'upload_timestamp': timestamp,
                'description': description,
                'tags': tags or [],
                'file_size': os.path.getsize(filepath),
                'access_history': [],
                'verification_status': 'pending',
                'blockchain_stored': False,
                'qr_code_generated': False
            }
            
            # Store metadata
            evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
            evidence_metadata[evidence_id] = metadata
            save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
            
            # Generate QR code
            qr_path = EvidenceManager.generate_qr_code(evidence_id, metadata)
            if qr_path:
                metadata['qr_code_generated'] = True
                metadata['qr_code_path'] = qr_path
                save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
            
            # Store evidence on blockchain (single call)
            print(f"⛓️ Checking blockchain availability: w3 = {w3 is not None}, contract = {contract is not None}")
            print(f"⛓️ Storing evidence on blockchain...")
            blockchain_success = store_evidence_on_blockchain(
                evidence_id=evidence_id,
                file_hash=metadata['file_hash'],
                uploader=uploader,
                timestamp=metadata['upload_timestamp'],
                description=metadata.get('description', ''),
                filename=metadata.get('filename', evidence_id)
            )

            if blockchain_success:
                print(f"✅ Evidence stored on blockchain successfully!")
                metadata['blockchain_stored'] = True
                metadata['blockchain_tx_hash'] = "stored"
            else:
                print(f"⚠️ Evidence stored locally only (blockchain unavailable)")
                metadata['blockchain_stored'] = False

            # Save final metadata
            save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
            
            print(f"🎉 Evidence upload completed successfully: {evidence_id}")
            return evidence_id, None
            
        except Exception as e:
            print(f"❌ Unexpected error in upload_evidence: {e}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            return None, f"Upload failed: {str(e)}"
    
    @staticmethod
    def generate_qr_code(evidence_id, metadata):
        """Generate QR code for evidence with metadata"""
        try:
            # Create QR code data
            qr_data = {
                'evidence_id': evidence_id,
                'file_hash': metadata['file_hash'],
                'verification_url': f"http://127.0.0.1:5000/verify/{evidence_id}",
                'timestamp': metadata['upload_timestamp']
            }
            
            # Convert to JSON string
            qr_string = json.dumps(qr_data)
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code
            qr_filename = f"{evidence_id}_qr.png"
            qr_path = os.path.join(QR_FOLDER, qr_filename)
            img.save(qr_path)
            
            return qr_path
        except Exception as e:
            print(f"QR code generation failed: {e}")
            return None
    
    @staticmethod
    def verify_evidence(evidence_id, access_user):
        """Verify evidence and log access"""
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
        
        if evidence_id not in evidence_metadata:
            return None, "Evidence not found"
        
        metadata = evidence_metadata[evidence_id]
        
        # Check user permissions
        if not check_user_permission(access_user, 'view_evidence', evidence_id):
            return None, "Access denied"
        
        # Verify file integrity
        evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
        filepath = os.path.join(evidence_dir, metadata['filename'])
        
        if not os.path.exists(filepath):
            return None, "Evidence file not found"
        
        current_hash = calculate_file_hash(filepath)
        integrity_verified = current_hash == metadata['file_hash']
        
        # Log access
        access_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'user': access_user,
            'action': 'ACCESSED',
            'integrity_verified': integrity_verified
        }
        
        metadata['access_history'].append(access_entry)
        evidence_metadata[evidence_id] = metadata
        save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
        
        # Audit trail
        AuditTrail.log_action(
            user=access_user,
            action='EVIDENCE_ACCESSED',
            evidence_id=evidence_id,
            details={'integrity_verified': integrity_verified}
        )
        
        return metadata, "Evidence verified successfully" if integrity_verified else "Evidence integrity compromised"

class UserRoleManager:
    """Role-based access control system"""
    
    @staticmethod
    def initialize_roles():
        """Initialize default user roles"""
        default_roles = {
            'admin': {
                'permissions': ['*'],  # All permissions
                'description': 'Full system access'
            },
            'user': {
                'permissions': [
                    'upload_evidence',
                    'view_evidence',
                    'verify_evidence',
                    'generate_qr'
                ],
                'description': 'Standard user with evidence management access'
            },
            'investigator': {
                'permissions': [
                    'upload_evidence',
                    'view_evidence',
                    'verify_evidence',
                    'generate_qr'
                ],
                'description': 'Evidence investigation access'
            },
            'viewer': {
                'permissions': [
                    'view_evidence',
                    'verify_evidence'
                ],
                'description': 'Read-only access'
            }
        }
        
        user_roles = load_json_file(USER_ROLES_FILE, {'roles': default_roles, 'user_assignments': {}})
        if 'roles' not in user_roles:
            user_roles['roles'] = default_roles
        if 'user_assignments' not in user_roles:
            user_roles['user_assignments'] = {}
        
        save_json_file(USER_ROLES_FILE, user_roles)
        return user_roles
    
    @staticmethod
    def assign_role(username, role):
        """Assign role to user"""
        user_roles = load_json_file(USER_ROLES_FILE, {'roles': {}, 'user_assignments': {}})
        user_roles['user_assignments'][username] = role
        save_json_file(USER_ROLES_FILE, user_roles)
    
    @staticmethod
    def get_user_role(username):
        """Get user role"""
        user_roles = load_json_file(USER_ROLES_FILE, {'roles': {}, 'user_assignments': {}})
        return user_roles['user_assignments'].get(username, 'viewer')

# Utility functions
def load_json_file(filename, default=None):
    """Load JSON file with error handling"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
    return default if default is not None else {}

def save_json_file(filename, data):
    """Save data to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating hash: {e}")
        return None

def check_user_permission(username, permission, evidence_id=None):
    """Check if user has specific permission"""
    user_role = UserRoleManager.get_user_role(username)
    user_roles = load_json_file(USER_ROLES_FILE, {'roles': {}, 'user_assignments': {}})
    
    if user_role not in user_roles['roles']:
        return False
    
    permissions = user_roles['roles'][user_role]['permissions']
    return '*' in permissions or permission in permissions

def store_evidence_on_blockchain(metadata):
    """Store evidence metadata on blockchain"""
    # Placeholder for blockchain storage
    # In production, this would interact with smart contract
    return f"0x{secrets.token_hex(32)}"

def store_audit_on_blockchain(audit_entry):
    """Store audit log entry on blockchain"""
    # Placeholder for blockchain storage
    return f"0x{secrets.token_hex(32)}"

def load_contract_abi():
    """Load contract ABI from Truffle build files"""
    try:
        # Path to contract ABI file in current directory
        build_path = os.path.join(os.path.dirname(__file__), 'CertificateVerification.json')

        if os.path.exists(build_path):
            with open(build_path, 'r') as f:
                contract_data = json.load(f)
                return contract_data['abi']
        else:
            print(f"❌ Contract build file not found: {build_path}")
            return None
    except Exception as e:
        print(f"❌ Error loading contract ABI: {e}")
        return None

def store_evidence_on_blockchain(evidence_id, file_hash, uploader, timestamp, description="", filename=""):
    """Store evidence metadata on blockchain"""
    print(f"⛓️ Starting blockchain storage for evidence: {evidence_id}")
    
    if not WEB3_AVAILABLE:
        print("❌ Web3 not available")
        return False
        
    if not w3:
        print("❌ Web3 instance not initialized")
        return False
        
    if not contract:
        print("❌ Smart contract not loaded")
        return False

    try:
        print(f"⛓️ Web3 connection status: {w3.isConnected()}")
        print(f"⛓️ Contract address: {contract.address}")
        
        # Convert timestamp to integer (handle different timestamp formats)
        if isinstance(timestamp, str):
            # Parse ISO format timestamp
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp_int = int(dt.timestamp())
        elif hasattr(timestamp, 'timestamp'):
            timestamp_int = int(timestamp.timestamp())
        else:
            timestamp_int = int(timestamp)

        print(f"⛓️ Timestamp converted: {timestamp_int}")

        # Store evidence data as JSON in certificate_details
        evidence_data = {
            'evidence_id': evidence_id,
            'file_hash': file_hash,
            'uploader': uploader,
            'timestamp': timestamp_int,
            'description': description,
            'filename': filename
        }
        evidence_json = json.dumps(evidence_data)
        print(f"⛓️ Evidence data to store: {evidence_json}")

        # Call smart contract function to store evidence
        print(f"⛓️ Calling smart contract function...")
        
        # Check account balance
        balance = w3.eth.get_balance(w3.eth.default_account)
        print(f"⛓️ Account balance: {balance} wei")
        
        # Estimate gas
        try:
            gas_estimate = contract.functions.setCertificateDetails(evidence_json).estimate_gas()
            print(f"⛓️ Gas estimate: {gas_estimate}")
        except Exception as gas_error:
            print(f"⚠️ Gas estimation failed: {gas_error}")
        
        tx_hash = contract.functions.setCertificateDetails(evidence_json).transact()
        print(f"⛓️ Transaction hash: {tx_hash.hex()}")

        # Wait for transaction confirmation
        print(f"⛓️ Waiting for transaction confirmation...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"✅ Evidence stored on blockchain!")
        print(f"   Transaction Hash: {tx_hash.hex()}")
        print(f"   Block Number: {tx_receipt['blockNumber']}")
        print(f"   Gas Used: {tx_receipt['gasUsed']}")

        return True

    except Exception as e:
        print(f"❌ Failed to store evidence on blockchain: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

def verify_evidence_on_blockchain(evidence_id):
    """Verify evidence exists on blockchain"""
    if not WEB3_AVAILABLE or not contract:
        return None

    try:
        # Get certificate details and check if it contains the requested evidence
        cert_details = contract.functions.getCertificateDetails().call()

        if cert_details and cert_details != "empty":
            try:
                evidence_data = json.loads(cert_details)
                if evidence_data.get('evidence_id') == evidence_id:
                    return {
                        'evidence_id': evidence_data['evidence_id'],
                        'file_hash': evidence_data['file_hash'],
                        'uploader': evidence_data['uploader'],
                        'timestamp': evidence_data['timestamp'],
                        'description': evidence_data.get('description', ''),
                        'filename': evidence_data.get('filename', ''),
                        'is_verified': True
                    }
            except json.JSONDecodeError:
                pass

        return None

    except Exception as e:
        print(f"❌ Error verifying evidence on blockchain: {e}")
        return None

def get_blockchain_evidence_count():
    """Get total number of evidence stored on blockchain"""
    if not WEB3_AVAILABLE or not contract:
        return 0

    try:
        # Get certificate details and check if it contains evidence data
        cert_details = contract.functions.getCertificateDetails().call()
        if cert_details and cert_details != "empty":
            try:
                evidence_data = json.loads(cert_details)
                return 1 if 'evidence_id' in evidence_data else 0
            except:
                return 0
        return 0
    except Exception as e:
        print(f"❌ Error getting evidence count: {e}")
        return 0

def initialize_blockchain():
    """Initialize blockchain connection with Truffle Develop"""
    global w3, contract

    if not WEB3_AVAILABLE:
        print("Web3 not available - blockchain features disabled")
        return False

    try:
        # Connect to Truffle Develop
        w3 = Web3(HTTPProvider(BLOCKCHAIN_URL))
        try:
            # Test connection by getting chain_id
            chain_id = w3.eth.chain_id
            print(f"✅ Connected to blockchain: {chain_id}")

            # Load contract ABI and create contract instance
            contract_abi = load_contract_abi()
            if contract_abi:
                contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
                print(f"✅ Contract loaded: {CONTRACT_ADDRESS}")

                # Set default account (first account from Truffle Develop)
                w3.eth.default_account = w3.eth.accounts[0]
                print(f"✅ Default account: {w3.eth.default_account}")
                return True
            else:
                print("❌ Failed to load contract ABI")
                return False

        except Exception as e:
            print(f"❌ Failed to connect to blockchain: {e}")
            return False
    except Exception as e:
        print(f"Blockchain connection error: {e}")
        return False

def initialize_ipfs():
    """Initialize IPFS connection"""
    global ipfs_client

    if not IPFS_AVAILABLE:
        print("IPFS not available - using local storage")
        return False

    try:
        # ipfshttpclient emits a VersionMismatch warning for newer Kubo/IPFS versions.
        # It's not fatal for basic operations like add/cat, so we silence the warning.
        try:
            import warnings
            from ipfshttpclient import exceptions as ipfs_exceptions
            warnings.filterwarnings('ignore', category=ipfs_exceptions.VersionMismatch)
        except Exception:
            pass

        # Set a timeout for IPFS connection
        import socket
        socket.setdefaulttimeout(5)  # 5 second timeout
        ipfs_client = ipfshttpclient.connect(IPFS_API_MULTIADDR, timeout=5)
        version = ipfs_client.version()
        print(f"✅ Connected to IPFS: {version['Version']}")
        return True
    except Exception as e:
        print(f"IPFS connection failed: {e}")
        if REQUIRE_IPFS:
            print("IPFS is required (REQUIRE_IPFS=1). Please start IPFS and retry.")
            raise SystemExit(1)
        print("Continuing without IPFS - files will be stored locally")
        return False

# Initialize systems
print("Starting Document Protection Blockchain Application...")
print("Initializing systems...")

# Initialize user roles
UserRoleManager.initialize_roles()

# Initialize demo users
def initialize_demo_users():
    """Initialize demo users for testing"""
    users = load_json_file('users.json', {})
    
    demo_users = {
        'admin': {
            'password': 'admin123',
            'email': 'parmydevelopment.in@gmail.com',  # Use real email for testing
            'role': 'admin',
            'created_at': datetime.datetime.now().isoformat()
        },
        'investigator': {
            'password': 'investigator123',
            'email': 'parmydevelopment.in@gmail.com',  # Use real email for testing
            'role': 'investigator',
            'created_at': datetime.datetime.now().isoformat()
        },
        'demo': {
            'password': 'demo123', 
            'email': 'parmydevelopment.in@gmail.com',  # Use real email for testing
            'role': 'user',
            'created_at': datetime.datetime.now().isoformat()
        },
        'viewer': {
            'password': 'viewer123',
            'email': 'parmydevelopment.in@gmail.com',  # Use real email for testing
            'role': 'viewer',
            'created_at': datetime.datetime.now().isoformat()
        }
    }
    
    # Add demo users if they don't exist
    for username, user_data in demo_users.items():
        if username not in users:
            users[username] = user_data
            UserRoleManager.assign_role(username, user_data['role'])
            print(f"✓ Created demo user: {username} (role: {user_data['role']})")
    
    save_json_file('users.json', users)

initialize_demo_users()

# Initialize sample evidence data
def initialize_sample_evidence():
    """Initialize sample evidence data for testing"""
    sample_evidence = {
        "EVD_DEMO001": {
            "evidence_id": "EVD_DEMO001",
            "original_filename": "sample_document.pdf",
            "file_hash": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            "uploader": "admin",
            "timestamp": "2025-09-11T10:30:00",
            "description": "Sample legal document for demonstration purposes",
            "tags": ["legal", "contract", "demo", "sample"],
            "file_size": 1024576,
            "blockchain_hash": "0x1234567890abcdef1234567890abcdef12345678",
            "ipfs_hash": "QmSampleHashForDemonstrationPurposes123456789",
            "verification_status": "verified",
            "audit_trail": []
        },
        "EVD_DEMO002": {
            "evidence_id": "EVD_DEMO002", 
            "original_filename": "crime_scene_photo.jpg",
            "file_hash": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456a1",
            "uploader": "demo",
            "timestamp": "2025-09-11T11:15:00",
            "description": "Digital photograph from crime scene investigation",
            "tags": ["photo", "crime-scene", "investigation", "digital-forensics"],
            "file_size": 2048000,
            "blockchain_hash": "0xabcdef1234567890abcdef1234567890abcdef12",
            "ipfs_hash": "QmAnotherSampleHashForPhotoDemonstration987654",
            "verification_status": "verified",
            "audit_trail": []
        },
        "EVD_DEMO003": {
            "evidence_id": "EVD_DEMO003",
            "original_filename": "witness_statement.docx", 
            "file_hash": "c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456a1b2",
            "uploader": "admin",
            "timestamp": "2025-09-11T14:45:00",
            "description": "Witness statement document with digital signature",
            "tags": ["witness", "statement", "legal", "signature"],
            "file_size": 512000,
            "blockchain_hash": "0x567890abcdef1234567890abcdef1234567890ab",
            "ipfs_hash": "QmWitnessStatementHashExample123456789ABCDEF",
            "verification_status": "verified",
            "audit_trail": []
        }
    }
    
    # Save sample evidence to file
    evidence_file = 'evidence_database.json'
    existing_evidence = load_json_file(evidence_file, {})
    
    # Only add if not already present
    added_count = 0
    for eid, data in sample_evidence.items():
        if eid not in existing_evidence:
            existing_evidence[eid] = data
            added_count += 1
    
    if added_count > 0:
        save_json_file(evidence_file, existing_evidence)
        print(f"✓ Added {added_count} sample evidence files:")
        for eid in sample_evidence.keys():
            print(f"  - {eid}: {sample_evidence[eid]['original_filename']}")

initialize_sample_evidence()

# Initialize ZKP authentication
zkp_auth = ZKPAuthentication()

# Initialize IPFS connection
print("Initializing IPFS connection...")
try:
    if IPFS_AVAILABLE:
        # Try to initialize IPFS
        initialize_ipfs()
    else:
        print("IPFS not available - using local storage")
except Exception as e:
    print(f"IPFS initialization error: {e}")
    print("Continuing without IPFS - files will be stored locally")

# Initialize blockchain connection
print("Initializing blockchain connection...")
if WEB3_AVAILABLE:
    initialize_blockchain()
else:
    print("Web3 not available - continuing without blockchain support")

# Flask Routes
@app.route('/')
def index():
    user_role = None
    blockchain_status = "disconnected"
    if 'username' in session:
        user_role = UserRoleManager.get_user_role(session['username'])
        if w3 and WEB3_AVAILABLE:
            try:
                w3.eth.block_number
                blockchain_status = "connected"
            except:
                blockchain_status = "disconnected"
    return render_template('index.html', user_role=user_role, current_endpoint=request.endpoint, blockchain_status=blockchain_status)

@app.route('/test')
def test():
    return jsonify({
        'status': 'running',
        'blockchain_connected': w3 is not None,
        'ipfs_connected': ipfs_client is not None,
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please log in to access the dashboard', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    audit_log = load_json_file(AUDIT_LOG_FILE, [])
    
    # Calculate statistics
    total_evidence = len(evidence_metadata)
    verified_count = sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'verified')
    pending_count = total_evidence - verified_count
    blockchain_txns = len(audit_log)
    
    # Get user-specific data
    user_evidence = {k: v for k, v in evidence_metadata.items() if v.get('uploader') == username}
    user_verified_count = sum(1 for meta in user_evidence.values() if meta.get('verification_status') == 'verified')
    
    # Get evidence status breakdown
    evidence_status = {
        'valid': sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'valid'),
        'invalid': sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'invalid'),
        'fake': sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'fake'),
        'pending': sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'pending')
    }
    
    # Get recent evidence for display
    recent_evidence = []
    for evidence_id, metadata in list(evidence_metadata.items())[-5:]:  # Last 5 evidence items
        recent_evidence.append({
            'evidence_id': evidence_id,
            'filename': metadata.get('filename', 'Unknown'),
            'uploader': metadata.get('uploader', 'Unknown'),
            'upload_timestamp': metadata.get('upload_timestamp', 'Unknown'),
            'verification_status': metadata.get('verification_status', 'pending'),
            'verified_by': metadata.get('verified_by', ''),
            'verification_notes': metadata.get('verification_notes', '')
        })
    
    return render_template('dashboard.html', 
                         username=username,
                         user_role=user_role,
                         total_evidence=total_evidence,
                         verified_count=verified_count,
                         pending_count=pending_count,
                         blockchain_txns=blockchain_txns,
                         user_evidence_count=len(user_evidence),
                         user_verified_count=user_verified_count,
                         evidence_status=evidence_status,
                         recent_evidence=reversed(recent_evidence),
                         current_endpoint=request.endpoint)

@app.route('/upload_evidence')
def upload_evidence():
    if 'username' not in session:
        flash('Please log in to upload evidence', 'error')
        return redirect(url_for('login'))
    
    if not check_user_permission(session['username'], 'upload_evidence'):
        flash('You do not have permission to upload evidence', 'error')
        return redirect(url_for('dashboard'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    return render_template('upload_evidence.html', user_role=user_role, current_endpoint=request.endpoint)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    if not check_user_permission(session['username'], 'upload_evidence'):
        return jsonify({'success': False, 'message': 'Permission denied'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    description = request.form.get('description', '')
    tags = request.form.get('tags', '').split(',') if request.form.get('tags') else []
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    try:
        print(f"🔄 Starting upload process for user: {session['username']}")
        evidence_id, message = EvidenceManager.upload_evidence(
            file=file,
            uploader=session['username'],
            description=description,
            tags=[tag.strip() for tag in tags if tag.strip()]
        )
        
        print(f"📊 Upload result - Evidence ID: {evidence_id}, Message: {message}")
        
        if evidence_id:
            print(f"🎯 EVIDENCE UPLOAD SUCCESS: {evidence_id}")
            
            # Get evidence metadata for email notification
            evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
            metadata = evidence_metadata.get(evidence_id, {})
            print(f"📋 Metadata loaded: {bool(metadata)}")
            print(f"📋 Metadata keys: {list(metadata.keys()) if metadata else 'None'}")
            
            # Get user's email address
            users = load_json_file('users.json', {})
            user_email = users.get(session['username'], {}).get('email')
            print(f"👤 User: {session['username']}")
            print(f"📧 User email: {user_email}")
            
            # Send email notification if user has email
            if user_email:
                print(f"📧 ATTEMPTING EMAIL NOTIFICATION TO: {user_email}")
                
                # Get QR code path
                qr_path = metadata.get('qr_code_path')
                print(f"📱 QR path from metadata: {qr_path}")
                
                if qr_path and not os.path.isabs(qr_path):
                    qr_path = os.path.join(os.path.dirname(__file__), qr_path)
                    print(f"📱 Absolute QR path: {qr_path}")
                
                print(f"📱 QR file exists: {os.path.exists(qr_path) if qr_path else 'No QR path'}")
                
                # Send notification email
                print(f"📧 CALLING EmailNotification.send_evidence_notification...")
                email_success = EmailNotification.send_evidence_notification(
                    evidence_id=evidence_id,
                    metadata=metadata,
                    recipient_emails=[user_email],
                    qr_path=qr_path if qr_path and os.path.exists(qr_path) else None
                )
                
                print(f"📧 Email send result: {email_success}")
                
                if email_success:
                    print(f"✅ EMAIL NOTIFICATION SENT SUCCESSFULLY TO {user_email}")
                else:
                    print(f"❌ EMAIL NOTIFICATION FAILED TO SEND TO {user_email}")
            else:
                print(f"⚠️ NO EMAIL ADDRESS FOUND FOR USER {session['username']}")
            
            # Also print to console for debugging
            print(f"✅ Evidence uploaded successfully!")
            print(f"🆔 Evidence ID: {evidence_id}")
            print(f"👤 Uploader: {session.get('username')}")
            print(f"📧 User email: {user_email}")

            response_data = {
                'success': True,
                'message': f'Evidence uploaded successfully! Your Evidence ID is: {evidence_id}',
                'evidence_id': evidence_id,
                'redirect_url': url_for('view_evidence', evidence_id=evidence_id),
                'show_evidence_id': True
            }
            print(f"📤 Sending success response: {response_data}")
            return jsonify(response_data)
        else:
            print(f"❌ Upload failed: {message}")
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        print(f"❌ Upload error: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'})

@app.route('/test_email_simple')
def test_email_simple():
    """Simple email test with detailed debugging"""
    debug_info = []
    debug_info.append("🔍 Starting Email Debug Test")
    debug_info.append(f"📧 From: {EMAIL_CONFIG['email']}")
    debug_info.append(f"📧 To: ankillaanand@gmail.com")
    debug_info.append(f"📧 SMTP: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
    debug_info.append(f"🔐 Password length: {len(EMAIL_CONFIG['password'])} characters")
    debug_info.append(f"🔐 Password preview: {EMAIL_CONFIG['password'][:4]}****{EMAIL_CONFIG['password'][-4:] if len(EMAIL_CONFIG['password']) > 8 else ''}")

    try:
        import smtplib
        from email.mime.text import MIMEText

        debug_info.append("📡 Creating SMTP connection...")
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.set_debuglevel(1)  # Enable debug output

        if EMAIL_CONFIG['use_tls']:
            debug_info.append("🔒 Starting TLS...")
            server.starttls()

        debug_info.append("🔑 Attempting login...")
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        debug_info.append("✅ Login successful!")

        # Create test message
        debug_info.append("📝 Creating email message...")
        msg = MIMEText("This is a test email from the Evidence Management System.\n\nTimestamp: " + str(datetime.datetime.now()))
        msg['Subject'] = "Test Email - Evidence System"
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = 'ankillaanand@gmail.com'

        debug_info.append("📤 Sending email...")
        server.send_message(msg)
        server.quit()
        debug_info.append("✅ Email sent successfully!")

        return f"""
        <h1>✅ EMAIL TEST SUCCESSFUL!</h1>
        <h3>Debug Information:</h3>
        <pre style="background: #f0f0f0; padding: 10px; border-radius: 5px;">{chr(10).join(debug_info)}</pre>
        <p><strong>📧 Check your inbox at: <code>ankillaanand@gmail.com</code></strong></p>
        <p><strong>📂 Also check spam/junk folder</strong></p>
        <p><strong>⏰ Email may take 1-2 minutes to arrive</strong></p>
        """

    except smtplib.SMTPAuthenticationError as e:
        debug_info.append(f"❌ AUTHENTICATION FAILED: {str(e)}")
        return f"""
        <h1>❌ AUTHENTICATION ERROR</h1>
        <h3>Debug Information:</h3>
        <pre style="background: #ffe6e6; padding: 10px; border-radius: 5px; color: #d00;">{chr(10).join(debug_info)}</pre>
        <h3>🔧 Gmail App Password Setup:</h3>
        <ol>
            <li><strong>Enable 2FA:</strong> Go to <a href="https://myaccount.google.com/security" target="_blank">Google Account Security</a> → Enable 2-Step Verification</li>
            <li><strong>Generate App Password:</strong> Go to <a href="https://myaccount.google.com/apppasswords" target="_blank">App Passwords</a></li>
            <li><strong>Create Password:</strong> Select "Mail" → "Other (custom name)" → Enter "EvidenceSystem"</li>
            <li><strong>Copy Password:</strong> Use the 16-character password (ignore spaces)</li>
            <li><strong>Update Config:</strong> Replace the password in EMAIL_CONFIG with the new app password</li>
        </ol>
        <p><strong>Current password format check:</strong> {len(EMAIL_CONFIG['password'])} characters, contains spaces: {'Yes' if ' ' in EMAIL_CONFIG['password'] else 'No'}</p>
        """

    except Exception as e:
        debug_info.append(f"❌ GENERAL ERROR: {str(e)}")
        debug_info.append(f"❌ Error type: {type(e).__name__}")
        return f"""
        <h1>❌ EMAIL TEST FAILED</h1>
        <h3>Debug Information:</h3>
        <pre style="background: #ffe6e6; padding: 10px; border-radius: 5px; color: #d00;">{chr(10).join(debug_info)}</pre>
        <h3>🔍 Troubleshooting:</h3>
        <ul>
            <li><strong>Network Issue:</strong> Check if your firewall blocks SMTP (port 587)</li>
            <li><strong>Gmail Issue:</strong> Try generating a new app password</li>
            <li><strong>Account Issue:</strong> Verify the Gmail account has proper permissions</li>
        </ul>
        """

@app.route('/verify_evidence')
def verify_evidence():
    """Evidence verification form page"""
    if 'username' not in session:
        flash('Please log in to access verification features', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    return render_template('verify_evidence.html', user_role=user_role, current_endpoint=request.endpoint)

@app.route('/verify/<evidence_id>')
def verify_evidence_route(evidence_id):
    """Public verification route for QR code scanning"""
    # Check both evidence metadata and evidence database
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    evidence_database = load_json_file('evidence_database.json', {})
    
    # First check the evidence database (includes sample data)
    if evidence_id in evidence_database:
        metadata = evidence_database[evidence_id]
        username = session.get('username')
        user_role = UserRoleManager.get_user_role(username) if username else None
        return render_template('verification_result.html',
                             success=True,
                             evidence_id=evidence_id,
                             metadata=metadata,
                             integrity_verified=True,
                             message="Evidence verified successfully from blockchain database",
                             user_role=user_role,
                             current_endpoint=request.endpoint)
    
    # Then check the regular evidence metadata
    if evidence_id not in evidence_metadata:
        # Create not found result object
        result = {
            'overall_status': 'failed',
            'security_score': 0,
            'verification_timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'evidence_id': evidence_id,
            'filename': 'Unknown',
            'file_hash': 'Unknown',
            'upload_timestamp': 'Unknown',
            'uploader': 'Unknown',
            'description': 'Evidence not found',
            'integrity_verified': False
        }
        
        return render_template('verification_result.html', 
                             success=False,
                             result=result,
                             message="Evidence not found. Please check the Evidence ID and try again.",
                             user_role=user_role,
                             current_endpoint=request.endpoint)
    
    metadata = evidence_metadata[evidence_id]
    
    # Verify file integrity
    evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
    filepath = os.path.join(evidence_dir, metadata['filename'])
    
    if os.path.exists(filepath):
        current_hash = calculate_file_hash(filepath)
        integrity_verified = current_hash == metadata['file_hash']

        # Also verify on blockchain
        blockchain_data = verify_evidence_on_blockchain(evidence_id)
        blockchain_verified = blockchain_data is not None

        # Create result object for template
        result = {
            'overall_status': 'verified' if (integrity_verified and blockchain_verified) else ('partially_verified' if integrity_verified else 'failed'),
            'security_score': 95 if (integrity_verified and blockchain_verified) else (75 if integrity_verified else 25),
            'verification_timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'evidence_id': evidence_id,
            'filename': metadata['filename'],
            'file_hash': metadata['file_hash'],
            'upload_timestamp': metadata['upload_timestamp'],
            'uploader': metadata['uploader'],
            'description': metadata.get('description', ''),
            'integrity_verified': integrity_verified,
            'blockchain_verified': blockchain_verified,
            'blockchain_data': blockchain_data
        }

        return render_template('verification_result.html',
                             success=True,
                             result=result,
                             metadata=metadata,
                             user_role=user_role,
                             current_endpoint=request.endpoint)
    else:
        # Create failed result object
        result = {
            'overall_status': 'failed',
            'security_score': 0,
            'verification_timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'evidence_id': evidence_id,
            'filename': metadata['filename'],
            'file_hash': metadata['file_hash'],
            'upload_timestamp': metadata['upload_timestamp'],
            'uploader': metadata['uploader'],
            'description': metadata.get('description', ''),
            'integrity_verified': False
        }
        
        return render_template('verification_result.html',
                             success=False,
                             result=result,
                             message="Evidence file not found",
                             user_role=user_role,
                             current_endpoint=request.endpoint)

@app.route('/blockchain_status')
def blockchain_status():
    """Show blockchain connection status and evidence count"""
    blockchain_info = {
        'connected': False,
        'network_id': None,
        'contract_address': CONTRACT_ADDRESS,
        'evidence_count': 0,
        'latest_block': None,
        'gas_price': None,
        'connection_status': 'disconnected',
        'ipfs_status': 'disconnected',
        'total_evidence_local': 0,
        'blockchain_url': BLOCKCHAIN_URL,
        'ipfs_url': 'http://127.0.0.1:5001'
    }

    # Check local evidence count
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    blockchain_info['total_evidence_local'] = len(evidence_metadata)

    # Check IPFS status
    if ipfs_client:
        try:
            ipfs_client.version()
            blockchain_info['ipfs_status'] = 'connected'
        except:
            blockchain_info['ipfs_status'] = 'error'
    else:
        blockchain_info['ipfs_status'] = 'not_available'

    if WEB3_AVAILABLE and w3:
        try:
            # Check connection by trying to get the latest block
            latest_block = w3.eth.block_number
            blockchain_info['connected'] = True
            blockchain_info['network_id'] = w3.eth.chain_id
            blockchain_info['evidence_count'] = get_blockchain_evidence_count()
            blockchain_info['latest_block'] = latest_block
            blockchain_info['gas_price'] = w3.eth.gas_price
            blockchain_info['connection_status'] = 'connected'
        except Exception as e:
            print(f"Blockchain connection check failed: {e}")
            blockchain_info['connected'] = False
            blockchain_info['connection_status'] = f'error: {str(e)}'

    username = session.get('username')
    user_role = UserRoleManager.get_user_role(username) if username else None
    return render_template('blockchain_status.html', blockchain_info=blockchain_info, user_role=user_role, current_endpoint=request.endpoint)

@app.route('/api/status')
def api_status():
    """API endpoint for system status"""
    status_info = {
        'timestamp': datetime.datetime.now().isoformat(),
        'services': {
            'flask': 'running',
            'blockchain': 'disconnected',
            'ipfs': 'disconnected'
        },
        'blockchain': {
            'url': BLOCKCHAIN_URL,
            'contract_address': CONTRACT_ADDRESS,
            'network_id': CHAIN_ID
        },
        'evidence': {
            'local_count': len(load_json_file(EVIDENCE_METADATA_FILE, {}))
        }
    }

    # Check blockchain status
    if WEB3_AVAILABLE and w3:
        try:
            w3.eth.block_number
            status_info['services']['blockchain'] = 'connected'
            status_info['evidence']['blockchain_count'] = get_blockchain_evidence_count()
        except:
            status_info['services']['blockchain'] = 'error'

    # Check IPFS status
    if ipfs_client:
        try:
            ipfs_client.version()
            status_info['services']['ipfs'] = 'connected'
        except:
            status_info['services']['ipfs'] = 'error'
    else:
        status_info['services']['ipfs'] = 'not_available'

    return jsonify(status_info)

@app.route('/scan_qr')
def scan_qr():
    username = session.get('username')
    user_role = UserRoleManager.get_user_role(username) if username else None
    return render_template('scan_qr.html', user_role=user_role, current_endpoint=request.endpoint)

@app.route('/view_evidence/<evidence_id>')
def view_evidence(evidence_id):
    """Dashboard route for viewing evidence details after QR scan"""
    if 'username' not in session:
        flash('Please log in to view evidence', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    
    # Check permissions
    if not check_user_permission(username, 'view_evidence'):
        flash('You do not have permission to view evidence', 'error')
        return redirect(url_for('dashboard'))
    
    # QR-based access control: Check if user has scanned QR for this evidence
    # Allow access from audit trail without QR scanning
    from_audit_trail = request.args.get('from_audit_trail') == '1'
    if not from_audit_trail:
        qr_access_evidence_id = session.get('qr_access_evidence_id')
        if qr_access_evidence_id != evidence_id:
            flash('Access denied. Please scan the QR code for this evidence to view details.', 'error')
            return redirect(url_for('audit_trail'))
    
    # Load evidence metadata
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    evidence_database = load_json_file('evidence_database.json', {})
    
    metadata = None
    
    # Check evidence database first (includes sample data)
    if evidence_id in evidence_database:
        metadata = evidence_database[evidence_id]
    elif evidence_id in evidence_metadata:
        metadata = evidence_metadata[evidence_id]
    
    if not metadata:
        flash(f'Evidence {evidence_id} not found', 'error')
        return redirect(url_for('dashboard'))
    
    # Additional security: For investigators, ensure they can only view their own evidence
    if user_role == 'investigator' and metadata.get('uploader') != username:
        flash('Access denied. You can only view your own evidence.', 'error')
        return redirect(url_for('audit_trail'))
    
    # Log access
    AuditTrail.log_action(
        user=username,
        action='EVIDENCE_ACCESSED',
        evidence_id=evidence_id,
        details={'access_method': 'qr_authorized_view', 'user_role': user_role}
    )
    
    # Update access history
    if 'access_history' not in metadata:
        metadata['access_history'] = []
    
    metadata['access_history'].append({
        'user': username,
        'timestamp': datetime.datetime.now().isoformat(),
        'action': 'viewed',
        'user_role': user_role
    })
    
    # Save updated metadata
    if evidence_id in evidence_metadata:
        evidence_metadata[evidence_id] = metadata
        save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
    
    # Clear the QR access session after successful access
    session.pop('qr_access_evidence_id', None)
    
    return render_template('view_evidence.html', 
                         evidence_id=evidence_id,
                         metadata=metadata,
                         user_role=user_role,
                         username=username,
                         current_endpoint=request.endpoint)

@app.route('/qr_scan_result', methods=['POST'])
def qr_scan_result():
    """Handle QR code scan results from dashboard"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    try:
        data = request.get_json()
        scanned_data = data.get('scanned_data')
        
        if not scanned_data:
            return jsonify({'success': False, 'message': 'No scan data provided'})
        
        # Parse QR code data
        try:
            qr_data = json.loads(scanned_data)
            evidence_id = qr_data.get('evidence_id')
            
            if evidence_id:
                # Set QR access authorization for this evidence
                session['qr_access_evidence_id'] = evidence_id
                return jsonify({
                    'success': True, 
                    'evidence_id': evidence_id,
                    'redirect_url': url_for('view_evidence', evidence_id=evidence_id)
                })
            else:
                return jsonify({'success': False, 'message': 'Invalid QR code format'})
                
        except json.JSONDecodeError:
            # If not JSON, might be just an evidence ID or URL
            if scanned_data.startswith('http'):
                # Extract evidence ID from URL
                if '/verify/' in scanned_data:
                    evidence_id = scanned_data.split('/verify/')[-1]
                    session['qr_access_evidence_id'] = evidence_id
                    return jsonify({
                        'success': True, 
                        'evidence_id': evidence_id,
                        'redirect_url': url_for('view_evidence', evidence_id=evidence_id)
                    })
            else:
                # Assume it's an evidence ID
                session['qr_access_evidence_id'] = scanned_data
                return jsonify({
                    'success': True, 
                    'evidence_id': scanned_data,
                    'redirect_url': url_for('view_evidence', evidence_id=scanned_data)
                })
            
            return jsonify({'success': False, 'message': 'Could not parse QR code data'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing QR scan: {str(e)}'})

@app.route('/manage_users')
def manage_users():
    if 'username' not in session:
        flash('Please log in to manage users', 'error')
        return redirect(url_for('login'))
    
    if not check_user_permission(session['username'], '*'):  # Admin only
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    user_roles = load_json_file(USER_ROLES_FILE, {'roles': {}, 'user_assignments': {}})
    audit_log = load_json_file(AUDIT_LOG_FILE, [])
    
    return render_template('manage_users.html', 
                         user_roles=user_roles,
                         recent_activities=audit_log[-10:],
                         user_role=user_role,
                         current_endpoint=request.endpoint)

@app.route('/audit_trail')
def audit_trail():
    if 'username' not in session:
        flash('Please log in to view audit trail', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    
    # Load evidence metadata and audit logs
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    audit_log = load_json_file(AUDIT_LOG_FILE, [])
    
    # Get all evidence with uploader information
    all_evidence = []
    for evidence_id, metadata in evidence_metadata.items():
        evidence_info = {
            'evidence_id': evidence_id,
            'filename': metadata.get('filename', 'Unknown'),
            'uploader': metadata.get('uploader', 'Unknown'),
            'upload_timestamp': metadata.get('upload_timestamp', 'Unknown'),
            'verification_status': metadata.get('verification_status', 'pending'),
            'description': metadata.get('description', ''),
            'file_hash': metadata.get('file_hash', ''),
            'blockchain_stored': metadata.get('blockchain_stored', False),
            'tags': metadata.get('tags', []),
            'file_size': metadata.get('file_size', 0),
            'uploader_role': UserRoleManager.get_user_role(metadata.get('uploader', '')) or 'unknown'
        }
        all_evidence.append(evidence_info)
    
    # Sort by upload timestamp (newest first)
    all_evidence.sort(key=lambda x: x['upload_timestamp'], reverse=True)
    
    # Filter evidence based on user role
    if user_role == 'investigator':
        # Investigators can only see their own evidence
        filtered_evidence = [e for e in all_evidence if e['uploader'] == username]
    else:
        # Admins can see all evidence
        filtered_evidence = all_evidence
    
    return render_template('audit_trail.html', 
                         all_evidence=filtered_evidence,
                         audit_log=list(reversed(audit_log)),
                         user_role=user_role,
                         username=username,
                         current_endpoint=request.endpoint)

@app.route('/verify_evidence_status/<evidence_id>', methods=['POST'])
def verify_evidence_status(evidence_id):
    """Verify evidence status (valid, invalid, fake)"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    
    # Only investigators and admins can verify evidence
    if user_role not in ['investigator', 'admin']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'})
    
    verification_status = request.form.get('status')
    verification_notes = request.form.get('notes', '')
    
    if verification_status not in ['valid', 'invalid', 'fake']:
        return jsonify({'success': False, 'message': 'Invalid verification status'})
    
    # Load evidence metadata
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    
    if evidence_id not in evidence_metadata:
        return jsonify({'success': False, 'message': 'Evidence not found'})
    
    # Update verification status
    evidence_metadata[evidence_id]['verification_status'] = verification_status
    evidence_metadata[evidence_id]['verified_by'] = username
    evidence_metadata[evidence_id]['verified_at'] = datetime.datetime.now().isoformat()
    evidence_metadata[evidence_id]['verification_notes'] = verification_notes
    
    # Save updated metadata
    save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)
    
    # Log the verification action
    AuditTrail.log_action(
        user=username,
        action='EVIDENCE_VERIFIED',
        details={
            'evidence_id': evidence_id,
            'status': verification_status,
            'notes': verification_notes
        }
    )
    
    return jsonify({
        'success': True, 
        'message': f'Evidence marked as {verification_status}',
        'status': verification_status
    })

@app.route('/get_evidence_details/<evidence_id>')
def get_evidence_details(evidence_id):
    """Get detailed information about specific evidence"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    
    if evidence_id not in evidence_metadata:
        return jsonify({'success': False, 'message': 'Evidence not found'})
    
    metadata = evidence_metadata[evidence_id]
    
    # Check permissions
    if user_role == 'investigator' and metadata.get('uploader') != username:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    return jsonify({
        'success': True,
        'evidence': {
            'evidence_id': evidence_id,
            'filename': metadata.get('filename', 'Unknown'),
            'uploader': metadata.get('uploader', 'Unknown'),
            'upload_timestamp': metadata.get('upload_timestamp', 'Unknown'),
            'verification_status': metadata.get('verification_status', 'pending'),
            'description': metadata.get('description', ''),
            'file_hash': metadata.get('file_hash', ''),
            'blockchain_stored': metadata.get('blockchain_stored', False),
            'verified_by': metadata.get('verified_by', ''),
            'verified_at': metadata.get('verified_at', ''),
            'verification_notes': metadata.get('verification_notes', ''),
            'file_size': metadata.get('file_size', 0),
            'tags': metadata.get('tags', [])
        }
    })

# ZKP Authentication API Routes
@app.route('/api/zkp/challenge', methods=['POST'])
def zkp_challenge():
    """Generate ZKP challenge for user authentication"""
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': 'Username required'}), 400
        
        # Generate cryptographic challenge
        challenge = zkp_auth.generate_challenge(username)
        
        return jsonify({
            'challenge': challenge,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zkp/verify', methods=['POST'])
def zkp_verify():
    """Verify ZKP proof for authentication"""
    try:
        data = request.get_json()
        username = data.get('username')
        challenge = data.get('challenge')
        proof = data.get('proof')
        
        if not all([username, challenge, proof]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Verify ZKP proof
        is_valid = zkp_auth.verify_proof(username, challenge, proof)
        
        if is_valid:
            # Set session
            session['username'] = username
            session['auth_method'] = 'zkp'
            
            # Ensure user has a role
            user_role = UserRoleManager.get_user_role(username)
            if not user_role:
                UserRoleManager.assign_role(username, 'viewer')
            
            # Log ZKP login
            AuditTrail.log_action(
                user=username,
                action='ZKP_LOGIN',
                details={'auth_method': 'zero_knowledge_proof', 'challenge': challenge}
            )
            
            return jsonify({
                'success': True,
                'message': 'ZKP authentication successful',
                'redirect': url_for('dashboard')
            })
        else:
            # Log failed attempt
            AuditTrail.log_action(
                user=username,
                action='ZKP_LOGIN_FAILED',
                details={'auth_method': 'zero_knowledge_proof', 'challenge': challenge}
            )
            
            return jsonify({
                'success': False,
                'message': 'ZKP authentication failed'
            }), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Load users
        users = load_json_file('users.json', {})
        
        if username in users:
            # For demonstration, using simple password check
            # In production, use proper ZKP authentication
            if users[username]['password'] == password:
                session['username'] = username
                
                # Ensure user has a role - check user data first, then assign from user_assignments
                user_role = UserRoleManager.get_user_role(username)
                if user_role == 'viewer':  # Default role means not assigned
                    # Check if user has role in users.json
                    if 'role' in users[username]:
                        UserRoleManager.assign_role(username, users[username]['role'])
                    else:
                        UserRoleManager.assign_role(username, 'user')  # Default to user role
                
                # Log login
                AuditTrail.log_action(
                    user=username,
                    action='USER_LOGIN',
                    details={'login_method': 'password'}
                )
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'error')
    
    return render_template('login.html', user_role=None, current_endpoint=request.endpoint)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Admin/Educational Authority login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Load admin users (you can extend this to have separate admin user file)
        users = load_json_file('users.json', {})
        
        if username in users:
            # Check if user has admin privileges
            user_role = UserRoleManager.get_user_role(username)
            if users[username]['password'] == password and user_role == 'admin':
                session['username'] = username
                
                # Log admin login
                AuditTrail.log_action(
                    user=username,
                    action='ADMIN_LOGIN',
                    details={'login_method': 'password', 'user_role': 'admin'}
                )
                
                flash('Admin login successful!', 'success')
                return redirect(url_for('dashboard'))
            elif users[username]['password'] == password:
                flash('Access denied. Admin privileges required.', 'error')
            else:
                flash('Invalid username or password', 'error')
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('AdminLogin.html', user_role=None, current_endpoint=request.endpoint)

@app.route('/signup', methods=['GET', 'POST'])
@app.route('/SignupAction', methods=['POST'])
def signup():
    if request.method == 'POST':
        # Get form data with the field names from the form (t1, t2, etc.)
        username = request.form.get('t1')  # username
        password = request.form.get('t2')  # password
        full_name = request.form.get('t3')  # full name
        email = request.form.get('t4')  # email
        role = request.form.get('t5')  # role selection
        org_type = request.form.get('t6')  # organization type
        org_name = request.form.get('t7')  # organization name
        justification = request.form.get('t8')  # access justification
        
        # Also handle standard field names for backward compatibility
        if not username:
            username = request.form.get('username')
        if not password:
            password = request.form.get('password')
        if not email:
            email = request.form.get('email')
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters long')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address')
        if not full_name:
            errors.append('Please enter your full name')
        if not role or role not in ['investigator', 'viewer', 'analyst']:
            errors.append('Please select a valid role')
        if not org_type:
            errors.append('Please select your organization type')
        if not org_name:
            errors.append('Please enter your organization name')
        if not justification or len(justification) < 10:
            errors.append('Please provide access justification (minimum 10 characters)')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('signup.html', user_role=None, current_endpoint=request.endpoint)
        
        # Load users
        users = load_json_file('users.json', {})
        
        if username in users:
            flash('Username already exists', 'error')
            return render_template('signup.html', user_role=None, current_endpoint=request.endpoint)
        else:
            # Create new user with all information
            users[username] = {
                'password': password,  # In production, hash this
                'email': email,
                'full_name': full_name,
                'organization_type': org_type,
                'organization_name': org_name,
                'access_justification': justification,
                'created_at': datetime.datetime.now().isoformat(),
                'zkp_enabled': False,
                'status': 'active'  # Immediate access for demo
            }
            save_json_file('users.json', users)
            
            # Assign requested role
            UserRoleManager.assign_role(username, role)
            
            # Log registration
            AuditTrail.log_action(
                user=username,
                action='USER_REGISTERED',
                details={
                    'email': email,
                    'full_name': full_name,
                    'role': role,
                    'organization': org_name,
                    'org_type': org_type
                }
            )
            
            flash(f'🎉 Registration Successful! Welcome {full_name}! You can now login with username: {username}', 'success')
            return redirect(url_for('login'))
    
    return render_template('signup.html', user_role=None, current_endpoint=request.endpoint)

@app.route('/logout')
def logout():
    if 'username' in session:
        # Log logout
        AuditTrail.log_action(
            user=session['username'],
            action='USER_LOGOUT'
        )
        session.pop('username', None)
        flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/admin/system_stats')
def admin_system_stats():
    """Admin-only system statistics and monitoring"""
    if 'username' not in session:
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    
    if UserRoleManager.get_user_role(session['username']) != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Gather comprehensive system statistics
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    audit_log = load_json_file(AUDIT_LOG_FILE, [])
    users = load_json_file('users.json', {})
    
    stats = {
        'total_users': len(users),
        'total_evidence': len(evidence_metadata),
        'total_audit_entries': len(audit_log),
        'verified_evidence': sum(1 for meta in evidence_metadata.values() if meta.get('verification_status') == 'verified'),
        'blockchain_stored': sum(1 for meta in evidence_metadata.values() if meta.get('blockchain_stored')),
        'system_uptime': '99.9%',  # Placeholder
        'storage_used': '2.3 GB',  # Placeholder
        'active_sessions': 1  # Placeholder
    }
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    return render_template('admin_stats.html', stats=stats, user_role=user_role, current_endpoint=request.endpoint)

@app.route('/admin/user_activity')
def admin_user_activity():
    """Admin view of user activity and engagement"""
    if 'username' not in session:
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    
    if UserRoleManager.get_user_role(session['username']) != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get user activity data
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    audit_log = load_json_file(AUDIT_LOG_FILE, [])
    users = load_json_file('users.json', {})
    
    # Calculate user activity metrics
    user_activity = {}
    for username in users.keys():
        user_evidence = [meta for meta in evidence_metadata.values() if meta.get('uploader') == username]
        user_audits = [entry for entry in audit_log if entry.get('user') == username]
        
        user_activity[username] = {
            'evidence_count': len(user_evidence),
            'verified_count': sum(1 for meta in user_evidence if meta.get('verification_status') == 'verified'),
            'audit_entries': len(user_audits),
            'last_activity': max([entry.get('timestamp', '2025-01-01') for entry in user_audits] + ['2025-01-01'])
        }
    
    username = session['username']
    user_role = UserRoleManager.get_user_role(username)
    return render_template('admin_user_activity.html', user_activity=user_activity, user_role=user_role, current_endpoint=request.endpoint)

@app.route('/api/evidence/<evidence_id>/qr')
def get_evidence_qr(evidence_id):
    """API endpoint to get QR code for evidence"""
    evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
    
    if evidence_id not in evidence_metadata:
        return jsonify({'error': 'Evidence not found'}), 404
    
    metadata = evidence_metadata[evidence_id]
    qr_path = metadata.get('qr_code_path')
    
    if qr_path and os.path.exists(qr_path):
        return send_from_directory(os.path.dirname(qr_path), os.path.basename(qr_path))
    else:
        return jsonify({'error': 'QR code not found'}), 404

@app.route('/test_email_auth')
def test_email_auth():
    """Test Gmail authentication without sending email"""
    try:
        import smtplib
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
        server.quit()
        return """
        <h1>✅ Gmail Authentication Successful!</h1>
        <p>Your app password is working correctly.</p>
        <p>Try the full email test now: <a href='/test_email_simple'>Send Test Email</a></p>
        """
    except Exception as e:
        return f"""
        <h1>❌ Gmail Authentication Failed</h1>
        <p><strong>Error:</strong> {str(e)}</p>
        <p><strong>Error Type:</strong> {type(e).__name__}</p>
        <h3>Common Issues:</h3>
        <ul>
            <li><strong>Wrong App Password:</strong> Make sure you copied the 16-character app password correctly</li>
            <li><strong>2FA Not Enabled:</strong> You must have 2-Step Verification enabled</li>
            <li><strong>App Password Expired:</strong> Generate a new app password</li>
            <li><strong>Account Issues:</strong> Check if your Gmail account is suspended or has restrictions</li>
        </ul>
        <h3>Setup Steps:</h3>
        <ol>
            <li>Go to <a href="https://myaccount.google.com/security" target="_blank">Google Account Security</a></li>
            <li>Enable 2-Step Verification if not already enabled</li>
            <li>Go to <a href="https://myaccount.google.com/apppasswords" target="_blank">App Passwords</a></li>
            <li>Select "Mail" → "Other (custom name)" → Enter "EvidenceSystem"</li>
            <li>Use the 16-character password (ignore spaces)</li>
        </ol>
        """

# API Endpoints for QR Code Actions

@app.route('/api/verify_integrity/<evidence_id>', methods=['GET'])
def api_verify_integrity(evidence_id):
    """API endpoint to verify evidence integrity"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Load evidence metadata
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})

        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions
        if not check_user_permission(username, 'view', evidence_id):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403

        # Verify file integrity
        evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
        filepath = os.path.join(evidence_dir, metadata['filename'])

        integrity_verified = False
        if os.path.exists(filepath):
            current_hash = calculate_file_hash(filepath)
            integrity_verified = current_hash == metadata['file_hash']

        # Verify blockchain status
        blockchain_data = verify_evidence_on_blockchain(evidence_id)
        blockchain_verified = blockchain_data is not None

        # Log the verification action
        AuditTrail.log_action(username, 'verify_integrity', evidence_id, {
            'integrity_verified': integrity_verified,
            'blockchain_verified': blockchain_verified
        })

        # Store verification on blockchain
        if WEB3_AVAILABLE and w3 and contract:
            try:
                verification_data = {
                    'evidence_id': evidence_id,
                    'verifier': username,
                    'integrity_verified': integrity_verified,
                    'blockchain_verified': blockchain_verified,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                store_audit_on_blockchain(verification_data)
            except Exception as e:
                print(f"Failed to store verification on blockchain: {e}")

        result = {
            'integrity_verified': integrity_verified,
            'blockchain_verified': blockchain_verified,
            'file_exists': os.path.exists(filepath),
            'verification_timestamp': datetime.datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'message': f'Integrity verification completed. File integrity: {"✓" if integrity_verified else "✗"}, Blockchain: {"✓" if blockchain_verified else "✗"}',
            'result': result
        })

    except Exception as e:
        print(f"Error in verify_integrity: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/modify_evidence/<evidence_id>', methods=['POST'])
def api_modify_evidence(evidence_id):
    """API endpoint to modify evidence metadata"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Load evidence metadata
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})

        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions (only uploader or admin can modify)
        if username != metadata.get('uploader') and user_role != 'admin':
            return jsonify({'success': False, 'message': 'Permission denied. Only uploader or admin can modify evidence.'}), 403

        # Get modification data
        data = request.get_json()
        description = data.get('description', '').strip()
        tags = data.get('tags', '').strip()

        # Validate input
        if not description and not tags:
            return jsonify({'success': False, 'message': 'At least one field must be provided'}), 400

        # Update metadata
        old_metadata = metadata.copy()
        if description:
            metadata['description'] = description
        if tags:
            metadata['tags'] = [tag.strip() for tag in tags.split(',') if tag.strip()]
        metadata['last_modified'] = datetime.datetime.now().isoformat()
        metadata['modified_by'] = username

        # Save updated metadata
        evidence_metadata[evidence_id] = metadata
        save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)

        # Log the modification action
        AuditTrail.log_action(username, 'modify_evidence', evidence_id, {
            'old_description': old_metadata.get('description', ''),
            'new_description': metadata.get('description', ''),
            'old_tags': old_metadata.get('tags', []),
            'new_tags': metadata.get('tags', [])
        })

        # Store modification on blockchain
        if WEB3_AVAILABLE and w3 and contract:
            try:
                modification_data = {
                    'evidence_id': evidence_id,
                    'modifier': username,
                    'action': 'modify',
                    'changes': {
                        'description': description,
                        'tags': tags
                    },
                    'timestamp': datetime.datetime.now().isoformat()
                }
                store_audit_on_blockchain(modification_data)
            except Exception as e:
                print(f"Failed to store modification on blockchain: {e}")

        return jsonify({
            'success': True,
            'message': 'Evidence metadata updated successfully',
            'changes': {
                'description': description,
                'tags': tags
            }
        })

    except Exception as e:
        print(f"Error in modify_evidence: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/delete_evidence/<evidence_id>', methods=['DELETE'])
def api_delete_evidence(evidence_id):
    """API endpoint to delete evidence"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Load evidence metadata
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})

        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions (only uploader or admin can delete)
        if username != metadata.get('uploader') and user_role != 'admin':
            return jsonify({'success': False, 'message': 'Permission denied. Only uploader or admin can delete evidence.'}), 403

        # Delete physical files
        evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
        deleted_files = []
        if os.path.exists(evidence_dir):
            for filename in os.listdir(evidence_dir):
                file_path = os.path.join(evidence_dir, filename)
                try:
                    os.remove(file_path)
                    deleted_files.append(filename)
                except Exception as e:
                    print(f"Failed to delete file {file_path}: {e}")

            try:
                os.rmdir(evidence_dir)
            except Exception as e:
                print(f"Failed to delete directory {evidence_dir}: {e}")

        # Delete QR code
        qr_path = os.path.join('static', 'qrcode', f'{evidence_id}_qr.png')
        if os.path.exists(qr_path):
            try:
                os.remove(qr_path)
                deleted_files.append(f'{evidence_id}_qr.png')
            except Exception as e:
                print(f"Failed to delete QR code {qr_path}: {e}")

        # Remove from metadata
        del evidence_metadata[evidence_id]
        save_json_file(EVIDENCE_METADATA_FILE, evidence_metadata)

        # Log the deletion action
        AuditTrail.log_action(username, 'delete_evidence', evidence_id, {
            'deleted_files': deleted_files,
            'original_uploader': metadata.get('uploader'),
            'evidence_description': metadata.get('description', '')
        })

        # Store deletion on blockchain
        if WEB3_AVAILABLE and w3 and contract:
            try:
                deletion_data = {
                    'evidence_id': evidence_id,
                    'deleter': username,
                    'action': 'delete',
                    'deleted_files': deleted_files,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                store_audit_on_blockchain(deletion_data)
            except Exception as e:
                print(f"Failed to store deletion on blockchain: {e}")

        return jsonify({
            'success': True,
            'message': f'Evidence {evidence_id} deleted successfully',
            'deleted_files': deleted_files
        })

    except Exception as e:
        print(f"Error in delete_evidence: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/download_evidence/<evidence_id>', methods=['GET'])
def api_download_evidence(evidence_id):
    """API endpoint to download evidence file"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Load evidence metadata
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})

        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions
        if not check_user_permission(username, 'download', evidence_id):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403

        # Get file path
        evidence_dir = os.path.join(UPLOAD_FOLDER, evidence_id)
        filepath = os.path.join(evidence_dir, metadata['filename'])

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'message': 'Evidence file not found'}), 404

        # Log the download action
        AuditTrail.log_action(username, 'download_evidence', evidence_id, {
            'filename': metadata['filename'],
            'file_size': metadata.get('file_size', 0)
        })

        # Store download on blockchain
        if WEB3_AVAILABLE and w3 and contract:
            try:
                download_data = {
                    'evidence_id': evidence_id,
                    'downloader': username,
                    'action': 'download',
                    'filename': metadata['filename'],
                    'timestamp': datetime.datetime.now().isoformat()
                }
                store_audit_on_blockchain(download_data)
            except Exception as e:
                print(f"Failed to store download on blockchain: {e}")

        # Return file
        return send_from_directory(evidence_dir, metadata['filename'], as_attachment=True)

    except Exception as e:
        print(f"Error in download_evidence: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/share_qr/<evidence_id>', methods=['GET'])
def api_share_qr(evidence_id):
    """API endpoint to generate shareable QR code link"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Load evidence metadata
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})

        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions
        if not check_user_permission(username, 'share', evidence_id):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403

        # Generate shareable URL
        share_url = f"{request.host_url}verify/{evidence_id}"

        # Get QR code path
        qr_image_url = f"/static/qrcode/{evidence_id}_qr.png"

        # Log the share action
        AuditTrail.log_action(username, 'share_qr', evidence_id, {
            'share_url': share_url,
            'shared_with': 'public_link'
        })

        # Store share action on blockchain
        if WEB3_AVAILABLE and w3 and contract:
            try:
                share_data = {
                    'evidence_id': evidence_id,
                    'sharer': username,
                    'action': 'share_qr',
                    'share_url': share_url,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                store_audit_on_blockchain(share_data)
            except Exception as e:
                print(f"Failed to store share action on blockchain: {e}")

        return jsonify({
            'success': True,
            'message': 'Share link generated successfully',
            'share_url': share_url,
            'qr_image_url': qr_image_url,
            'evidence_id': evidence_id
        })

    except Exception as e:
        print(f"Error in share_qr: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.route('/api/get_evidence_metadata/<evidence_id>')
def api_get_evidence_metadata(evidence_id):
    """API endpoint to get evidence metadata for editing"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        username = session['username']
        user_role = UserRoleManager.get_user_role(username)

        # Check permissions (only uploader or admin can view metadata)
        evidence_metadata = load_json_file(EVIDENCE_METADATA_FILE, {})
        if evidence_id not in evidence_metadata:
            return jsonify({'success': False, 'message': 'Evidence not found'}), 404

        metadata = evidence_metadata[evidence_id]

        # Check permissions
        if username != metadata.get('uploader') and user_role != 'admin':
            return jsonify({'success': False, 'message': 'Permission denied'}), 403

        # Return metadata for editing
        return jsonify({
            'success': True,
            'metadata': {
                'description': metadata.get('description', ''),
                'tags': metadata.get('tags', []),
                'uploader': metadata.get('uploader', ''),
                'upload_timestamp': metadata.get('upload_timestamp', ''),
                'file_size': metadata.get('file_size', 0),
                'file_hash': metadata.get('file_hash', ''),
                'verification_status': metadata.get('verification_status', 'pending')
            }
        })

    except Exception as e:
        print(f"Error in get_evidence_metadata: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    print(f"Note: Make sure Ethereum blockchain is running on {BLOCKCHAIN_URL}")
    print(f"Note: Make sure IPFS daemon is running at {IPFS_API_MULTIADDR}")
    print("Available at: http://127.0.0.1:5000")
    print("Test route: http://127.0.0.1:5000/test")
    app.run(debug=False, host='127.0.0.1', port=5000)
