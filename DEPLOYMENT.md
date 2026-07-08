# Azure Deployment Guide

This guide explains how to deploy the **SNIST Guest Invitation Management System** to **Azure App Service (Linux)** and connect it to **Azure Database for MySQL**.

## Step 1: Database Setup on Azure

1. Create an **Azure Database for MySQL flexible server** in the Azure portal.
2. Configure the server Firewall rules to **Allow public access from any Azure service within Azure** (so the Web App can connect to it).
3. Obtain the connection string. It should look like this:
   ```text
   mysql+pymysql://<admin-user>:<admin-password>@<server-name>.mysql.database.azure.com:3306/<database-name>?ssl_ca=DigiCertGlobalRootG2.crt.pem
   ```
   *(Note: Secure connections might require downloading the DigiCert SSL root certificate. Save the certificate file in the project folder and append `?ssl_ca=DigiCertGlobalRootG2.crt.pem` to your connection string).*

## Step 2: Configure Azure App Service

1. Create a new **App Service Web App** in Azure:
   * **Runtime stack:** Python 3.11 or Python 3.12
   * **Operating System:** Linux
2. Under the Web App's **Settings > Configuration > Application Settings**, define the following environment variables:
   * `SECRET_KEY`: A secure random secret string (e.g. generated via `openssl rand -hex 32`).
   * `DATABASE_URL`: Your Azure MySQL connection string (e.g. `mysql+pymysql://user:pass@host:3306/db`).
   * `MAIL_SERVER`: SMTP server hostname (e.g. `smtp.gmail.com` or `smtp.sendgrid.net`). Set to `simulation` to mock email delivery in development logs.
   * `MAIL_PORT`: SMTP port (usually `587` or `465`).
   * `MAIL_USE_TLS`: Set to `True`.
   * `MAIL_USERNAME`: SMTP authorization username.
   * `MAIL_PASSWORD`: SMTP authorization password.
   * `MAIL_DEFAULT_SENDER`: Email address to display in the "From" header (e.g., `invitations@sreenidhi.edu.in`).
3. Set the **Startup Command** under the Web App's **Configuration > General settings**:
   ```bash
   gunicorn --config gunicorn.conf.py app:app
   ```

## Step 3: Deployment via GitHub Actions (or Local Git)

You can deploy by linking your GitHub repository to Azure Web App Deployment Center:
1. Go to your App Service **Deployment Center**.
2. Select **GitHub** as the source, log in, and select your repository.
3. Azure will generate a GitHub Actions workflow file that builds and deploys your code automatically whenever you push to your branch.

## Step 4: Initialize the Production Database

Once the app is deployed:
1. Navigate to the App Service console in Azure Portal (under **Development Tools > SSH**).
2. Connect to the container and run:
   ```bash
   python db_init.py
   ```
3. This creates all MySQL tables and seeds the default administrator:
   * **Email:** `admin@sreenidhi.edu.in`
   * **Password:** `Admin@SNIST123`
4. Log in immediately and update your password or setup customized administrator accounts.
