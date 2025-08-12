#!/usr/bin/env python3
"""
OAuth Configuration Test Script
This script tests the basic OAuth setup without starting the full server.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment_variables():
    """Test if required environment variables are set"""
    required_vars = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET', 
        'GITHUB_CLIENT_ID',
        'GITHUB_CLIENT_SECRET',
        'SECRET_KEY'
    ]
    
    print("Checking environment variables...")
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith('your_'):
            missing_vars.append(var)
            print(f"❌ {var}: Not set or using placeholder value")
        else:
            print(f"✅ {var}: Set")
    
    if missing_vars:
        print(f"\n⚠️  Missing or placeholder variables: {', '.join(missing_vars)}")
        print("Please update your .env file with real OAuth credentials.")
        return False
    else:
        print("\n✅ All environment variables are configured!")
        return True

def test_imports():
    """Test if all required packages can be imported"""
    print("\nTesting imports...")
    
    try:
        import flask
        print("✅ flask imported successfully")
        
        import flask_login
        print("✅ flask_login imported successfully")
        
        import authlib
        print("✅ authlib imported successfully")
        
        from authlib.integrations.flask_client import OAuth
        print("✅ OAuth client imported successfully")
        
        import requests
        print("✅ requests imported successfully")
        
        print("\n✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def test_oauth_config():
    """Test OAuth configuration"""
    print("\nTesting OAuth configuration...")
    
    try:
        from flask import Flask
        from authlib.integrations.flask_client import OAuth
        
        app = Flask(__name__)
        app.secret_key = os.getenv('SECRET_KEY', 'test-key')
        
        oauth = OAuth(app)
        
        # Test Google OAuth registration
        google = oauth.register(
            name='google',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            access_token_url='https://oauth2.googleapis.com/token',
            authorize_url='https://accounts.google.com/o/oauth2/auth',
            api_base_url='https://www.googleapis.com/oauth2/v2/',
            client_kwargs={'scope': 'openid email profile'}
        )
        print("✅ Google OAuth configured successfully")
        
        # Test GitHub OAuth registration  
        github = oauth.register(
            name='github',
            client_id=os.getenv('GITHUB_CLIENT_ID'),
            client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            api_base_url='https://api.github.com/',
            client_kwargs={'scope': 'user:email'},
        )
        print("✅ GitHub OAuth configured successfully")
        
        print("\n✅ OAuth configuration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ OAuth configuration error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 OAuth Configuration Test")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    if test_environment_variables():
        tests_passed += 1
    
    if test_imports():
        tests_passed += 1
        
    if test_oauth_config():
        tests_passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your OAuth setup should work correctly.")
        print("\nNext steps:")
        print("1. Start the server: python server.py")
        print("2. Visit http://localhost:5000")
        print("3. Click 'Login' and test OAuth authentication")
    else:
        print("❌ Some tests failed. Please fix the issues above before running the server.")
        sys.exit(1)

if __name__ == '__main__':
    main()
