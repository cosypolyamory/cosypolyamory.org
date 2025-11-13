cosy polyamory web page
=======================

Web page for Barcelona's new english speaking polyamory group, complete with Meetup replacement.

## Features

- **Event Management**: Create, edit, and manage community events
- **RSVP System**: Full RSVP functionality with Yes/No/Maybe/Cancel options
- **User Applications**: 7-question application system with admin review
- **Google Maps Integration**: Embedded interactive maps for event locations
- **OAuth Authentication**: Login with Google or GitHub
- **Role-Based Access**: Admin, organizer, and member roles
- **Public Access**: Events visible to all, details to approved members
- **Responsive Design**: Mobile-friendly Bootstrap 5 interface

## Setup

### Basic Installation

```bash
    python -m venv .ve
    source .ve/bin/activate
    pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env`
2. Configure OAuth credentials (see `DOCS/OAUTH_SETUP.md`)
3. Configure Google Maps API key (see `GOOGLE_MAPS_SETUP.md`) # TO IMPLEMENT
4. Make admins by running `python manage_db.py make-admin user@email.xxx`
5. Generate sample data by running `python generate_sample_data.py`

### Running

```bash
    python server.py
```

## Documentation

- [OAuth Setup Guide](docs/OAUTH_SETUP.md) - Configure Google and GitHub authentication
- [Google Maps Setup](GOOGLE_MAPS_SETUP.md) - Configure embedded maps for events # TO IMPLEMENT

### minor issues
#### CSS/SASS
- workaround if sass support for css doesn't work:
`pip install Flask-Assets libsass`

- how to compile the css after you modify it:
```bash
export FLASK_APP=cosypolyamory/app.py
python3 -m flask assets build
```
