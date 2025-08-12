# Project Structure

## Overview
The Cosy Polyamory project has been refactored to have a clean, modular structure with separated concerns.

## Directory Structure
```
cosypolyamory.org/
├── server.py                    # Main application entry point
├── manage_db.py                 # Database management CLI tool
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (OAuth keys, secrets)
├── .env.example                 # Environment variables template
├── cosypolyamory.db            # SQLite database file
├── cosypolyamory/              # Main application package
│   ├── __init__.py             # Package initialization
│   ├── app.py                  # Flask application and routes
│   ├── database.py             # Database configuration
│   └── models/                 # Database models package
│       ├── __init__.py         # Base model definition
│       └── user.py             # User model
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Base template
│   ├── navbar.html             # Navigation component
│   ├── login.html              # OAuth login page
│   ├── profile.html            # User profile page
│   ├── admin.html              # Admin dashboard
│   ├── index.html              # Home page
│   └── ...                     # Other content pages
└── static/                     # Static assets (CSS, images, PDFs)
    ├── css/
    ├── img/
    └── pdf/
```

## Key Components

### Database Layer
- **`cosypolyamory/database.py`**: Database configuration using Peewee ORM with SQLite
- **`cosypolyamory/models/__init__.py`**: Base model class that all models inherit from
- **`cosypolyamory/models/user.py`**: User model for OAuth authentication

### Application Layer
- **`server.py`**: Main application entry point that imports and runs the Flask app
- **`cosypolyamory/app.py`**: Flask application with OAuth integration and all routes
- **`manage_db.py`**: Command-line tool for database management

### Templates
- **Jinja2 templates** with Bootstrap 5 styling
- **OAuth login integration** with Google and GitHub
- **Admin dashboard** for user management
- **Responsive design** with mobile support

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,           -- "google_123456" or "github_789"
    email VARCHAR UNIQUE,             -- User's email address
    name VARCHAR,                     -- Display name
    avatar_url VARCHAR,               -- Profile picture URL
    provider VARCHAR,                 -- "google" or "github"
    created_at DATETIME,              -- Account creation timestamp
    last_login DATETIME,              -- Last login timestamp
    is_admin BOOLEAN DEFAULT 0        -- Admin status flag
);
```

## Management Commands

### Database Operations
```bash
# Initialize database
python manage_db.py init

# List all users
python manage_db.py list

# Grant admin privileges
python manage_db.py make-admin --email user@example.com

# Remove admin privileges
python manage_db.py remove-admin --email user@example.com
```

### Server Operations
```bash
# Start development server
python server.py

# Server runs on http://localhost:5000
```

## Authentication System

### OAuth Providers
- **Google OAuth 2.0**: Full profile access with avatar
- **GitHub OAuth**: User profile with fallback email handling

### User Flow
1. User visits `/login` page
2. Selects OAuth provider (Google/GitHub)
3. Redirected to provider for authentication
4. Returns to `/callback/<provider>` with authorization code
5. App exchanges code for user information
6. User created/updated in database
7. User logged in with Flask-Login session

### Admin System
- Admin status stored in database (`is_admin` field)
- Admin dashboard accessible at `/admin`
- User management and statistics
- Controlled via CLI management tool

## Security Features
- **Environment-based configuration** for sensitive data
- **CSRF protection** via Flask built-ins
- **Secure session cookies** with proper settings
- **OAuth state validation** to prevent attacks
- **Database input validation** via Peewee ORM

## Future Extensions
The modular package structure supports easy addition of:
- **Event models** (`cosypolyamory/models/event.py`) for Meetup replacement functionality
- **Additional OAuth providers** (Discord, Facebook, etc.) in the auth module
- **User roles and permissions** beyond admin/member
- **Activity logging and audit trails** (`cosypolyamory/models/activity.py`)
- **Email notification system** (`cosypolyamory/notifications.py`)
- **API endpoints** for mobile app integration (`cosypolyamory/api.py`)

## Configuration
- **`.env` file**: Contains OAuth client IDs/secrets and Flask secret key
- **Environment variables**: Support for production deployment
- **Database path**: Configurable via `DATABASE_PATH` environment variable
