# OAuth Configuration Setup Guide

## Prerequisites

1. Python 3.8+
2. Virtual environment (recommended)

## Installation

1. Clone the repository and navigate to the project directory
2. Create and activate a virtual environment:
   ```bash
   python -m venv .ve
   source .ve/bin/activate  # On Windows: .ve\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## OAuth Configuration

### 1. Google OAuth Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Go to "Credentials" and create a new "OAuth 2.0 Client ID"
5. Set the application type to "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:5000/callback/google` (for development)
   - `https://your-domain.com/callback/google` (for production)
7. Copy the Client ID and Client Secret

### 2. GitHub OAuth Setup

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Click "New OAuth App"
3. Fill in the application details:
   - Application name: "Cosy Polyamory Community"
   - Homepage URL: `http://localhost:5000` (for development)
   - Authorization callback URL: `http://localhost:5000/callback/github`
4. Copy the Client ID and Client Secret

### 3. Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your OAuth credentials:
   ```
   GOOGLE_CLIENT_ID=your_google_client_id_here
   GOOGLE_CLIENT_SECRET=your_google_client_secret_here
   GITHUB_CLIENT_ID=your_github_client_id_here
   GITHUB_CLIENT_SECRET=your_github_client_secret_here
   SECRET_KEY=your_random_secret_key_here
   ```
3. Generate a secure secret key for production:
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

## Running the Application

```bash
python server.py
```

The application will be available at `http://localhost:5000`

## Features

### Authentication
- Google OAuth 2.0 integration
- GitHub OAuth integration
- User session management
- Secure logout

### User Management
- User profiles with avatar support
- Admin dashboard (requires admin email configuration)
- User API endpoints

### Security Features
- CSRF protection
- Secure session cookies
- Environment-based configuration
- OAuth state validation

## Admin Access

To grant admin access, modify the `admin_required` decorator in `server.py`:

```python
if current_user.email not in ['admin@example.com', 'your-admin-email@domain.com']:
```

## Production Deployment

### Environment Variables
Set these in your production environment:
- `SECRET_KEY`: Strong random key
- `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`
- `GITHUB_CLIENT_ID` & `GITHUB_CLIENT_SECRET`
- `FLASK_ENV=production`

### Security Considerations
1. Set `SESSION_COOKIE_SECURE = True` for HTTPS
2. Use a proper database instead of in-memory storage
3. Implement proper error logging
4. Add rate limiting for authentication endpoints
5. Configure proper CORS headers

## API Endpoints

- `GET /api/user` - Get current user information (requires authentication)
- `GET /login` - Login page
- `GET /login/<provider>` - Initiate OAuth login
- `GET /callback/<provider>` - OAuth callback handler
- `GET /logout` - Logout user
- `GET /profile` - User profile page
- `GET /admin` - Admin dashboard (requires admin access)

## Database Migration

The current implementation uses in-memory storage. For production, consider:
1. SQLite for small deployments
2. PostgreSQL for larger applications
3. Implement proper user model with SQLAlchemy
4. Add user role management
5. Store session data in Redis

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test thoroughly
4. Submit a pull request

## License

See LICENSE file for details.
