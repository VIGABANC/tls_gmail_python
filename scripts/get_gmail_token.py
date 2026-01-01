import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Scopes required for the application
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_PATH = '.token'

def main():
    load_dotenv()
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print('❌ Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env')
        print('')
        print('Steps:')
        print('1. Go to https://console.cloud.google.com/')
        print('2. Create a project and enable Gmail API')
        print('3. Create OAuth 2.0 credentials (Desktop app)')
        print('4. Copy client ID and secret to .env')
        return

    # Create client config from env vars
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"]
        }
    }

    # Run flow
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    print('')
    print('🔐 Gmail OAuth2 Token Generator (Python)')
    print('========================================')
    print('')
    
    # Run local server to obtain credentials
    creds = flow.run_local_server(port=0)

    print('')
    print('✅ Success! Tokens obtained:')
    print('')
    print(f"Refresh Token: {'✓ Present' if creds.refresh_token else '✗ Missing'}")
    print(f"Expiry: {creds.expiry}")
    print('')

    if not creds.refresh_token:
        print('⚠️  WARNING: No refresh_token returned!')
        print('   This can happen if you already authorized this app.')
        print('   Go to: https://myaccount.google.com/permissions to revoke access and try again.')
    else:
        print('📋 Add this to your .env file:')
        print('')
        print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
        print('')

        # Save tokens
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }
        
        with open(TOKEN_PATH, 'w') as f:
            json.dump(token_data, f, indent=2)
            print(f"💾 Tokens saved to {TOKEN_PATH}")

    print('')
    print('✅ Setup complete!')

if __name__ == "__main__":
    main()
