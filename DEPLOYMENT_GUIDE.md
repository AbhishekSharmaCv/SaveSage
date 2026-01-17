# Deployment Guide: Environment Variables

## How the Code Uses the API Key

The code **still uses the API key** - it just reads it from environment variables instead of hardcoded values. This is the **correct and secure way** to handle secrets.

### Current Code (Secure)
```python
def get_openai_client():
    """Get OpenAI client (API key from environment variable only)."""
    try:
        from openai import OpenAI
        # Get API key from environment variable only
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        return None
    except Exception:
        return None
```

**How it works:**
1. Code calls `os.getenv("OPENAI_API_KEY")`
2. Reads the value from the environment variable
3. Uses it to create the OpenAI client
4. If not set, returns `None` (graceful degradation)

---

## Setting Environment Variables in Different Environments

### 1. Local Development

#### Option A: Export in Terminal
```bash
export OPENAI_API_KEY="sk-proj-your-actual-key-here"
python main.py
```

#### Option B: Create `.env` File (Recommended)
Create a `.env` file in project root:
```
OPENAI_API_KEY=sk-proj-your-actual-key-here
```

Then load it in Python:
```python
# Add to main.py at the top
from dotenv import load_dotenv
load_dotenv()  # Loads .env file
```

Install python-dotenv:
```bash
pip install python-dotenv
```

#### Option C: Set in Shell Profile
Add to `~/.zshrc` or `~/.bashrc`:
```bash
export OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

---

### 2. ChatGPT MCP Server Deployment

When running as an MCP server, set the environment variable before starting:

```bash
# Set the variable
export OPENAI_API_KEY="sk-proj-your-actual-key-here"

# Start the server
python main.py
```

Or use a startup script:
```bash
#!/bin/bash
export OPENAI_API_KEY="sk-proj-your-actual-key-here"
python main.py
```

---

### 3. Docker Deployment

#### Option A: Environment Variable in docker run
```bash
docker run -e OPENAI_API_KEY="sk-proj-your-actual-key-here" your-image
```

#### Option B: Docker Compose
```yaml
version: '3.8'
services:
  savesage:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    # Or use .env file
    env_file:
      - .env
```

#### Option C: Dockerfile ENV (for default, but override in production)
```dockerfile
ENV OPENAI_API_KEY=""
# Override at runtime with -e flag
```

---

### 4. Cloud Platforms

#### Heroku
```bash
heroku config:set OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

Or in Heroku dashboard: Settings → Config Vars

#### AWS (EC2/ECS/Lambda)
```bash
# EC2: Set in user data or systemd service
export OPENAI_API_KEY="sk-proj-your-actual-key-here"

# ECS: Set in task definition environment variables
# Lambda: Set in function configuration → Environment variables
```

#### Google Cloud (Cloud Run/App Engine)
```bash
# Cloud Run
gcloud run deploy savesage \
  --set-env-vars OPENAI_API_KEY="sk-proj-your-actual-key-here"

# App Engine: app.yaml
env_variables:
  OPENAI_API_KEY: "sk-proj-your-actual-key-here"
```

#### Azure (App Service)
```bash
az webapp config appsettings set \
  --name savesage \
  --resource-group myResourceGroup \
  --settings OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

#### Railway
```bash
railway variables set OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

Or in Railway dashboard: Variables tab

#### Render
In Render dashboard: Environment → Add Environment Variable

#### Fly.io
```bash
fly secrets set OPENAI_API_KEY="sk-proj-your-actual-key-here"
```

---

### 5. Systemd Service (Linux Server)

Create `/etc/systemd/system/savesage.service`:
```ini
[Unit]
Description=SaveSage MCP Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/savesage
Environment="OPENAI_API_KEY=sk-proj-your-actual-key-here"
ExecStart=/usr/bin/python3 /path/to/savesage/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable savesage
sudo systemctl start savesage
```

---

### 6. Kubernetes

#### ConfigMap (for non-sensitive)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: savesage-config
data:
  OPENAI_API_KEY: "sk-proj-your-actual-key-here"
```

#### Secret (recommended for sensitive data)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: savesage-secret
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-proj-your-actual-key-here"
```

Then in deployment:
```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: savesage
        envFrom:
        - secretRef:
            name: savesage-secret
```

---

## Verification: Testing the Setup

### Test Locally
```bash
# Set the variable
export OPENAI_API_KEY="sk-proj-your-actual-key-here"

# Test that it's read
python3 -c "import os; print('Key set:', bool(os.getenv('OPENAI_API_KEY')))"
# Should print: Key set: True

# Run the app
python main.py
```

### Test in Code
Add this to `main.py` temporarily:
```python
# At startup, after loading
if os.getenv("OPENAI_API_KEY"):
    print("✅ OpenAI API key loaded from environment")
else:
    print("⚠️  OpenAI API key not set (some features will be disabled)")
```

---

## Security Best Practices

### ✅ DO:
- Use environment variables for all secrets
- Use secret management services (AWS Secrets Manager, Azure Key Vault, etc.)
- Rotate keys regularly
- Use different keys for dev/staging/production
- Never commit keys to git

### ❌ DON'T:
- Hardcode keys in source code
- Commit keys to git (even in private repos)
- Share keys in chat/email
- Use the same key everywhere
- Leave keys in logs or error messages

---

## Troubleshooting

### Issue: "OpenAI API not configured"
**Cause**: Environment variable not set
**Fix**: Set `OPENAI_API_KEY` environment variable

### Issue: Key works locally but not in deployment
**Cause**: Environment variable not set in deployment environment
**Fix**: Set the variable in your deployment platform's configuration

### Issue: Key visible in process list
**Cause**: Environment variables are visible in process list
**Fix**: Use secret management services for production

---

## Summary

**The code works exactly the same** - it just reads the key from the environment instead of hardcoding it. This is:
- ✅ More secure (no keys in code)
- ✅ More flexible (different keys per environment)
- ✅ Industry standard practice
- ✅ Required for production deployments

The key is set **once per environment** (dev, staging, production) and the code reads it automatically when it runs.
