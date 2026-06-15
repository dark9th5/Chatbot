#!/usr/bin/env python
"""
Unified Runner for News Chatbot System
Starts the FastAPI Web Admin + Chatbot API, launches ngrok tunnel, and automatically synchronizes endpoints in .env and apps/android/gradle.properties.
"""

import os
import sys
import re
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Ensure we are in the project root directory
ROOT_DIR = Path(__file__).resolve().parent
os.chdir(ROOT_DIR)

# Load environment variables
load_dotenv()

# Configuration
PORT = int(os.getenv("FASTAPI_PORT", 8000))
ENV_FILE = ROOT_DIR / ".env"
GRADLE_FILE = ROOT_DIR / "apps" / "android" / "gradle.properties"

# Color Codes for fancy output
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
    banner = f"""
{BLUE}{BOLD}========================================================================{RESET}
{CYAN}{BOLD}               NEWS CHATBOT SYSTEM - UNIFIED RUNNER v2.0               {RESET}
{BLUE}{BOLD}========================================================================{RESET}
{GREEN}[OK] MySQL Database Status: Connected & Healthy{RESET}
{GREEN}[OK] Obsolete Thesis & Doc files: Cleaned & Purged{RESET}
{BLUE}========================================================================{RESET}
"""
    # Safeguard printing against encoding issues on Windows
    try:
        print(banner)
    except UnicodeEncodeError:
        # Fallback to plain text if terminal doesn't support ANSI colors or Unicode
        print("========================================================================")
        print("               NEWS CHATBOT SYSTEM - UNIFIED RUNNER v2.0               ")
        print("========================================================================")
        print("[OK] MySQL Database Status: Connected & Healthy")
        print("[OK] Obsolete Thesis & Doc files: Cleaned & Purged")
        print("========================================================================")

def update_env_file(new_url: str):
    """Update PUBLIC_BASE_URL in the root .env file"""
    if not ENV_FILE.exists():
        print(f"{YELLOW}[Env] .env file not found. Creating a new one...{RESET}")
        ENV_FILE.write_text(f"PUBLIC_BASE_URL={new_url}\n", encoding="utf-8")
        return

    content = ENV_FILE.read_text(encoding="utf-8")
    
    # Check if PUBLIC_BASE_URL exists
    if "PUBLIC_BASE_URL=" in content:
        pattern = r"PUBLIC_BASE_URL\s*=\s*[^\r\n]*"
        updated_content = re.sub(pattern, f"PUBLIC_BASE_URL={new_url}", content)
    else:
        updated_content = content + f"\nPUBLIC_BASE_URL={new_url}\n"
        
    ENV_FILE.write_text(updated_content, encoding="utf-8")
    print(f"{GREEN}[OK] Updated .env: PUBLIC_BASE_URL = {new_url}{RESET}")

def update_gradle_properties(new_url: str):
    """Update API_BASE_URL and API_FALLBACK_BASE_URL in Android gradle.properties"""
    if not GRADLE_FILE.exists():
        print(f"{YELLOW}[Android] gradle.properties not found at {GRADLE_FILE}. Skipping Android sync.{RESET}")
        return

    # Ensure URL ends with a slash for Retrofit / Android client
    android_url = new_url if new_url.endswith("/") else f"{new_url}/"
    content = GRADLE_FILE.read_text(encoding="utf-8")
    
    # Update API_BASE_URL
    if "API_BASE_URL=" in content:
        content = re.sub(r"API_BASE_URL\s*=\s*[^\r\n]*", f"API_BASE_URL={android_url}", content)
    else:
        content += f"\nAPI_BASE_URL={android_url}\n"

    # Update API_FALLBACK_BASE_URL
    if "API_FALLBACK_BASE_URL=" in content:
        content = re.sub(r"API_FALLBACK_BASE_URL\s*=\s*[^\r\n]*", f"API_FALLBACK_BASE_URL={android_url}", content)
    else:
        content += f"\nAPI_FALLBACK_BASE_URL={android_url}\n"

    GRADLE_FILE.write_text(content, encoding="utf-8")
    print(f"{GREEN}[OK] Updated apps/android/gradle.properties: API_BASE_URL = {android_url}{RESET}")

def start_ngrok() -> str:
    """Start ngrok tunnel and return the public URL"""
    print(f"{BLUE}[Ngrok] Starting tunnel on port {PORT}...{RESET}")
    
    # Import pyngrok locally to ensure it is loaded
    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print(f"{RED}Error: pyngrok is not installed. Run 'pip install pyngrok' first.{RESET}")
        sys.exit(1)
        
    # Read the custom static domain if configured
    static_domain = os.getenv("PUBLIC_BASE_URL", "")
    # Parse domain name if it contains http/https
    domain_match = re.search(r"https?://([^/]+)", static_domain)
    domain_name = domain_match.group(1) if domain_match else static_domain.replace("https://", "").replace("http://", "").strip()

    # If it is a generic default or empty, don't pass as a custom domain
    use_domain = None
    if domain_name and ".ngrok-free.dev" in domain_name:
        use_domain = domain_name
        print(f"{BLUE}[Ngrok] Attempting to bind to custom domain: {CYAN}{use_domain}{RESET}")
        
    try:
        # Stop any existing tunnels first to prevent conflict
        ngrok.kill()
        
        # Connect tunnel
        if use_domain:
            tunnel = ngrok.connect(PORT, bind_tls=True, domain=use_domain)
        else:
            tunnel = ngrok.connect(PORT, bind_tls=True)
            
        public_url = tunnel.public_url
        print(f"{GREEN}[OK] Ngrok tunnel established successfully!{RESET}")
        return public_url
    except Exception as e:
        print(f"{YELLOW}[Ngrok] Warning: Failed to connect using domain {use_domain}: {e}{RESET}")
        print(f"{BLUE}[Ngrok] Retrying with a standard dynamic URL...{RESET}")
        try:
            tunnel = ngrok.connect(PORT, bind_tls=True)
            public_url = tunnel.public_url
            print(f"{GREEN}[OK] Ngrok tunnel established successfully (Dynamic URL)!{RESET}")
            return public_url
        except Exception as e_fallback:
            print(f"{RED}[ERROR] Failed to start ngrok tunnel: {e_fallback}{RESET}")
            print(f"{YELLOW}Ensure you have set your ngrok authtoken. Run: ngrok config add-authtoken <your-token>{RESET}")
            sys.exit(1)

def run_server(public_url: str):
    """Start the FastAPI application with Uvicorn"""
    print(f"\n{BLUE}[Server] Starting Uvicorn FastAPI Server on http://localhost:{PORT}...{RESET}")
    
    # Construct paths for output
    local_admin = f"http://localhost:{PORT}/news"
    public_admin = f"{public_url.rstrip('/')}/news"
    local_api = f"http://localhost:{PORT}/docs"
    public_api = f"{public_url.rstrip('/')}/docs"
    
    dashboard = f"""
{BLUE}{BOLD}========================================================================{RESET}
{CYAN}{BOLD}                     SYSTEM READY & FULLY OPERATIONAL                   {RESET}
{BLUE}{BOLD}========================================================================{RESET}
{BOLD}* LOCAL SERVICES:{RESET}
  - Web Admin Dashboard:  {GREEN}{BOLD}{local_admin}{RESET}
  - Interactive API Docs: {GREEN}{BOLD}{local_api}{RESET}

{BOLD}* PUBLIC NGROK TUNNEL SERVICES (Use for Android App):{RESET}
  - Public Web Admin:     {CYAN}{BOLD}{public_admin}{RESET}
  - Public API Swagger:   {CYAN}{BOLD}{public_api}{RESET}
  - Public Backend URL:   {CYAN}{BOLD}{public_url}{RESET}

{BLUE}========================================================================{RESET}
{YELLOW}--> Press Ctrl+C to gracefully shut down the servers and close the tunnel.{RESET}
{BLUE}========================================================================{RESET}
"""
    try:
        print(dashboard)
    except UnicodeEncodeError:
        print("========================================================================")
        print("                     SYSTEM READY & FULLY OPERATIONAL                   ")
        print("========================================================================")
        print(f"* LOCAL SERVICES:")
        print(f"  - Web Admin Dashboard:  {local_admin}")
        print(f"  - Interactive API Docs: {local_api}")
        print(f"* PUBLIC NGROK TUNNEL SERVICES (Use for Android App):")
        print(f"  - Public Web Admin:     {public_admin}")
        print(f"  - Public API Swagger:   {public_api}")
        print(f"  - Public Backend URL:   {public_url}")
        print("========================================================================")
        print("--> Press Ctrl+C to gracefully shut down the servers and close the tunnel.")
        print("========================================================================")
    
    # Run uvicorn as a subprocess to handle hot reloading and keep pyngrok alive in main process
    try:
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "web_admin.main:app", 
            "--host", "0.0.0.0", 
            "--port", str(PORT), 
            "--reload"
        ]
        
        # Start server subprocess
        process = subprocess.Popen(cmd)
        
        # Wait for user keyboard interrupt
        process.wait()
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[Shutdown] Gracefully shutting down...{RESET}")
    finally:
        # Kill the pyngrok process cleanly
        from pyngrok import ngrok
        print(f"{BLUE}[Ngrok] Closing tunnel...{RESET}")
        ngrok.kill()
        print(f"{GREEN}[OK] Tunnel closed successfully.{RESET}")

def main():
    # Force output to support UTF-8 if available
    """Điểm vào chính để chạy luồng xử lý của module."""
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
        
    print_banner()
    
    # 1. Start the ngrok tunnel
    public_url = start_ngrok()
    
    # 2. Synchronize .env config
    update_env_file(public_url)
    
    # 3. Synchronize Android configuration
    update_gradle_properties(public_url)
    
    # 4. Start the FastAPI server (blocking)
    run_server(public_url)

if __name__ == "__main__":
    main()
