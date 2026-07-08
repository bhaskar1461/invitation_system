# SNIST Guest Invitation Portal

A premium and secure Flask-based web application for managing event invitations, generating dynamic QR-coded entry passes, tracking attendance, and manually adjusting guest scan statuses. Designed for the Sreenidhi University Founder's Day event.

---

## Key Features
* **Guest Management**: Import guest directories from Excel (`.xlsx`) or manually register guests one by one.
* **Email Invites with QR Passes**: Sends personalized HTML invitation emails in background threads. The invitation pass (custom poster with overlaid QR code) is compiled on-the-fly when dispatching. The QR code contains a scan verification link.
* **Direct Database Toggle Controls**: Security admins can view each guest's attendance status in the dashboard and toggle it directly between **Scanned** and **Not Scanned** with a single click.
* **Comprehensive Metrics**: Tracks delivery status (Pending, Sent, Failed), scanned/attendance statistics, and displays recent activities on the admin dashboard.

---

## Database Design

The system runs on **MySQL** (production/development) and falls back to **SQLite** for zero-configuration local runs. Below is the relational database layout:

### 1. Table: `event_qr_codes` (Guests)
Stores the details of invitees, their unique invitation passes, email status, and attendance/check-in logs.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | BIGINT | Primary Key, Auto Increment | Unique guest identifier. |
| `guest_name` | VARCHAR(200) | NOT NULL | Full name of the guest. |
| `rollno` | VARCHAR(20) | NOT NULL | Academic roll number. |
| `mobile` | VARCHAR(20) | NOT NULL | Contact mobile number. |
| `email` | VARCHAR(255) | Unique, NOT NULL, Indexed | Email address used for sending invitation. |
| `qr_code` | VARCHAR(255) | Unique, NOT NULL, Indexed | Unique 6-digit numeric verification code. |
| `qr_image` | VARCHAR(255) | NULL | Filepath to the generated QR pass poster image. |
| `invite_sent` | TINYINT(1) | Default: `0`, NOT NULL | Toggle indicating if the email invite has been sent. |
| `status` | ENUM('ACTIVE', 'INACTIVE') | Default: `'ACTIVE'`, NOT NULL | Invitation status indicator. |
| `is_scanned` | TINYINT(1) | Default: `0`, NOT NULL | **Attendance Flag**: `0` = Not Scanned, `1` = Scanned. |
| `scanned_at` | TIMESTAMP | NULL | Timestamp of the first successful scan/check-in. |
| `device_ip` | VARCHAR(100) | NULL | IP address of the scanning device. |
| `device_id` | VARCHAR(255) | NULL | User-Agent of the checking device. |
| `remarks` | TEXT | NULL | Holds SMTP transmission failure tracebacks (cleared on success). |
| `created_at` | TIMESTAMP | NULL | Timestamp when the record was registered. |
| `updated_at` | TIMESTAMP | NULL | Timestamp of last modification/email dispatch. |
| `last_scanned_at` | TIMESTAMP | NULL | Timestamp of the last scan action. |

### 2. User Account (In-Memory)
Administrators 
* **Admin Role**: `admin@sreenidhi.edu.in` (Password: `Admin@SNIST123`)


---

## Summary of Recent Changes

1. **Production Task Queue (Celery & Redis)**:
   - Replaced thread-based email sending with a robust Celery background queue powered by a Redis broker.
   - Configured SMTP rate throttling limits (`SMTP_RATE_DELAY` and `SMTP_BATCH_LIMIT`) to safely throttle bulk dispatches.
2. **Scan Security & Row Locking**:
   - Implemented database row locking (`SELECT FOR UPDATE`) on the `/scan/<qr_code>` endpoint to atomically lock guest check-in states and prevent concurrent gate scanners from exploiting double-entries.
3. **Database Migrations (Alembic/Flask-Migrate)**:
   - Configured Flask-Migrate database version tracks to automatically sync, migrate, and update production MySQL databases safely.
4. **Dockerization**:
   - Integrated healthcheck scripts to verify web container service status.
   - Configured decoupled container services (`redis`, `web`, `celery_worker`) inside `docker-compose.yml` to manage task lifecycles separately.

---

## Application Setup (Local Development)

Follow these instructions to configure and run the application locally:

### Prerequisites
* **Python 3.9+** installed on your system.
* **Pip** (Python Package Installer).

### 1. Clone the Project & Setup Virtual Environment
Navigate to your project folder in your command-line interface:
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
Install all package requirements listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory. Copy the contents of `.env.example` and set up the configuration values:
```env
# Flask Settings
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=snist-guest-invitation-super-secret-key-12345
BASE_URL=http://localhost:5000

# Database Connection
# Leave blank to fall back automatically to local SQLite database (sqlite:///guest_invitation.db)
DATABASE_URL=mysql+pymysql://username:password@hostname:3306/database_name

# SMTP Configuration
# Set to 'simulation' to log emails to logs/email_simulation.log instead of triggering SMTP
SMTP_HOST=simulation
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USER=
SMTP_PASSWORD=
SMTP_SENDER=invitations@sreenidhi.edu.in
```

### 4. Run Redis Server
Ensure you have Redis running locally (defaulting to `redis://127.0.0.1:6379/0`).

### 5. Run Database Migrations
Initialize and sync database migrations using Alembic:
```bash
# Sync local database with the latest schema version
flask db upgrade
```

### 6. Launch Celery Worker
Start the Celery worker process to run background dispatches in a separate terminal:
```bash
celery -A app.celery worker --loglevel=info
```

### 7. Launch the Server
Execute the Flask server:
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser. Log in using `admin@sreenidhi.edu.in` and `Admin@SNIST123`.

---

## VPS Deployment Guide (Any Cloud Provider)

Here are the step-by-step instructions to deploy this application to any VPS (Ubuntu 22.04 LTS recommended) using either **Docker Compose** (recommended) or a **Manual Systemd + Nginx** setup.

### Option A: Docker Compose Deployment (Recommended)

This is the simplest way to deploy the app with all dependencies.

#### 1. Setup Docker on the VPS
Connect to your VPS via SSH and install Docker:
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable --now docker
```

#### 2. Clone the Repository & Configure Env
```bash
git clone https://github.com/bhaskar1461/invitation_system.git
cd invitation_system
```
Create a `.env` file or modify the environment values directly in `docker-compose.yml` to set your credentials, `SECRET_KEY`, and `DATABASE_URL` (connecting to your VPS database or external database).

#### 3. Spin up the Containers
Run Docker Compose in detached mode. This builds the web image and starts it:
```bash
sudo docker-compose up -d --build
```
This starts the application listening on host port `8888` (as defined in `docker-compose.yml`). The container will automatically initialize the database structure on startup.

---

### Option B: Manual Setup (Systemd + Gunicorn + Nginx)

Use this method if you want to run the application natively on the VPS.

#### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git nginx mysql-server build-essential
```

#### 2. Configure MySQL Database
Secure your MySQL installation and create the database:
```bash
sudo mysql_secure_installation
sudo mysql -u root -p

# Inside the MySQL Prompt:
CREATE DATABASE founder_day;
CREATE USER 'admin_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON founder_day.* TO 'admin_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### 3. Clone and Setup Virtual Environment
```bash
git clone https://github.com/bhaskar1461/invitation_system.git /var/www/invitation_system
cd /var/www/invitation_system

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure Production Environment Variables
Create the production environment file:
```bash
sudo nano .env
```
Add the following content:
```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=generate-a-random-hex-string
BASE_URL=https://yourdomain.com
DATABASE_URL=mysql+pymysql://admin_user:secure_password@localhost:3306/founder_day
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USER=Invitation@suh.edu.in
SMTP_PASSWORD=your_app_password
SMTP_SENDER=Invitation@suh.edu.in
```

#### 5. Initialize the Database
```bash
python db_init.py
```

#### 6. Configure Systemd Service
Create a systemd unit file for Gunicorn to run the application in the background:
```bash
sudo nano /etc/systemd/system/invitation.service
```
Add the following:
```ini
[Unit]
Description=Gunicorn instance to serve SNIST Guest Invitation Portal
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/invitation_system
Environment="PATH=/var/www/invitation_system/venv/bin"
ExecStart=/var/www/invitation_system/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 gunicorn.conf:app

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start invitation
sudo systemctl enable invitation
```

#### 7. Configure Nginx Reverse Proxy
Create an Nginx configuration file:
```bash
sudo nano /etc/nginx/sites-available/invitation
```
Add the following configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/invitation_system/static/;
    }

    location /uploads/ {
        alias /var/www/invitation_system/uploads/;
    }
}
```
Link and enable the site, then restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/invitation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 8. Install SSL Certificate (Let's Encrypt)
To secure the connections, install SSL using Certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```
Follow the prompts to enable HTTPS redirect.

---

## How to Push Code to GitHub

Follow these steps to push updates to GitHub:

```bash
# Add all files to staging
git add .

# Create a commit
git commit -m "docs: update database design, recent changes, and add VPS deployment guide"

# Push to GitHub
git push origin main
```
