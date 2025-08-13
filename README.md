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
2. Configure OAuth credentials (see `OAUTH_SETUP.md`)
3. Configure Google Maps API key (see `GOOGLE_MAPS_SETUP.md`)

### Running

```bash
flask --app server --debug run
```

## Documentation

- [OAuth Setup Guide](OAUTH_SETUP.md) - Configure Google and GitHub authentication
- [Google Maps Setup](GOOGLE_MAPS_SETUP.md) - Configure embedded maps for events
