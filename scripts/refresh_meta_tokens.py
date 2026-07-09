#!/usr/bin/env python3
import sys
import os
import requests
from pathlib import Path

# Load config
sys.path.insert(0, str(Path(__file__).parent.parent))
from api import config

def print_banner(title):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)

def main():
    print_banner("Meta API Token Refresh & Validation Tool")
    
    app_id = config.META_APP_ID
    app_secret = config.META_APP_SECRET
    
    if not app_id or not app_secret:
        print("❌ Error: META_APP_ID or META_APP_SECRET is not set in .env")
        sys.exit(1)
        
    print(f"🔑 Using Meta App ID: {app_id}")
    print(f"🔑 Using Meta App Secret: {app_secret[:6]}...{app_secret[-6:]}")
    
    print("\nStep 1: Get a short-lived User Access Token")
    print("1. Open Graph API Explorer: https://developers.facebook.com/tools/explorer/")
    print(f"2. Select your App '{app_id}' in the top right dropdown.")
    print("3. Add the following permissions in the User/Page permissions sidebar:")
    print("   - pages_show_list")
    print("   - pages_read_engagement")
    print("   - pages_manage_posts")
    print("   - instagram_basic")
    print("   - instagram_content_publish")
    print("4. Click 'Generate Access Token' and authorize the app.")
    
    try:
        short_token = input("\n👉 Paste the generated User Access Token here: ").strip()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
        
    if not short_token:
        print("❌ Token cannot be empty.")
        sys.exit(1)

    print("\nStep 2: Exchanging for a Long-Lived User Access Token...")
    exchange_url = "https://graph.facebook.com/v20.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }
    
    resp = requests.get(exchange_url, params=params)
    if resp.status_code != 200:
        print(f"❌ Failed to exchange token: {resp.status_code} - {resp.text}")
        sys.exit(1)
        
    long_user_token = resp.json().get("access_token")
    print("✅ Successfully generated Long-Lived User Access Token!")
    
    print("\nStep 3: Fetching your Pages & Page Access Tokens...")
    accounts_url = "https://graph.facebook.com/v20.0/me/accounts"
    accounts_resp = requests.get(accounts_url, params={"access_token": long_user_token})
    if accounts_resp.status_code != 200:
        print(f"❌ Failed to fetch accounts: {accounts_resp.status_code} - {accounts_resp.text}")
        sys.exit(1)
        
    pages_data = accounts_resp.json().get("data", [])
    if not pages_data:
        print("❌ No pages found associated with this user account.")
        sys.exit(1)
        
    print(f"\nFound {len(pages_data)} page(s):")
    selected_page = None
    for i, page in enumerate(pages_data):
        print(f" [{i+1}] {page['name']} (ID: {page['id']})")
    
    if len(pages_data) == 1:
        selected_page = pages_data[0]
    else:
        try:
            choice = int(input("\n👉 Select the page number to configure: ")) - 1
            if 0 <= choice < len(pages_data):
                selected_page = pages_data[choice]
            else:
                print("❌ Invalid selection.")
                sys.exit(1)
        except ValueError:
            print("❌ Invalid selection.")
            sys.exit(1)
            
    page_id = selected_page["id"]
    page_name = selected_page["name"]
    page_token = selected_page["access_token"]
    
    print(f"\n✅ Selected Page: {page_name}")
    print(f"👉 Page Access Token: {page_token}")
    
    # Check if there is an Instagram Business Account linked to this page
    print("\nChecking for linked Instagram Business Account...")
    page_info_url = f"https://graph.facebook.com/v20.0/{page_id}"
    ig_resp = requests.get(page_info_url, params={"fields": "instagram_business_account", "access_token": page_token})
    ig_id = None
    if ig_resp.status_code == 200:
        ig_data = ig_resp.json().get("instagram_business_account")
        if ig_data:
            ig_id = ig_data.get("id")
            print(f"✅ Found linked Instagram Business Account ID: {ig_id}")
        else:
            print("⚠️ No Instagram Business Account linked to this Page.")
    else:
        print(f"⚠️ Could not fetch Instagram account details: {ig_resp.text}")
        
    # Write to local .env
    print_banner("Updating Environment Configuration")
    env_path = Path(__file__).parent.parent / ".env"
    env_content = env_path.read_text()
    
    # Helper to replace or append env vars
    def update_env_var(content, key, val):
        lines = content.splitlines()
        replaced = False
        for idx, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[idx] = f"{key}={val}"
                replaced = True
        if not replaced:
            lines.append(f"{key}={val}")
        return "\n".join(lines) + "\n"
        
    new_content = update_env_var(env_content, "META_ACCESS_TOKEN", page_token)
    new_content = update_env_var(new_content, "FB_PAGE_ACCESS_TOKEN", page_token)
    new_content = update_env_var(new_content, "FB_PAGE_ID", page_id)
    if ig_id:
        new_content = update_env_var(new_content, "IG_USER_ID", ig_id)
        
    env_path.write_text(new_content)
    print("✅ Local .env file updated with new Meta Credentials!")
    
    # Offer to push to DO Droplet
    print("\nWould you like to deploy this updated .env file to your DigitalOcean droplet?")
    try:
        confirm = input("👉 Type 'yes' to deploy: ").strip().lower()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
        
    if confirm == "yes":
        print("\nDeploying to DigitalOcean droplet...")
        import subprocess
        # 1. SCP the new .env file
        try:
            subprocess.run([
                "scp", "-o", "StrictHostKeyChecking=no",
                str(env_path), "root@159.203.131.240:/root/smartshop/.env"
            ], check=True)
            print("✅ Copied .env to remote server.")
            
            # 2. Restart Docker containers to pick up new env
            print("🔄 Restarting remote containers to apply changes...")
            subprocess.run([
                "ssh", "-o", "StrictHostKeyChecking=no", "root@159.203.131.240",
                "cd /root/smartshop && docker compose -f infra/docker-compose.yml up -d --force-recreate"
            ], check=True)
            print("🎉 Remote deployment successfully restarted with the new tokens!")
        except Exception as e:
            print(f"❌ Remote deployment failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
