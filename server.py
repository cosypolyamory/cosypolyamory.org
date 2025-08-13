#!/usr/bin/env python3
"""
Main server entry point for Cosy Polyamory website
"""

if __name__ == '__main__':
    print("🚀 Starting Cosy Polyamory server...")
    from cosypolyamory.app import app
    print("✅ App imported successfully")
    print("🌐 Server starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
