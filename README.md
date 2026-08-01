# OppConnect

OppConnect is a Django web app for futsal teams to build profiles, find opponents,
manage availability, message other captains, and track match history and player stats.
The UI uses the dark sidebar / red accent theme from the dashboard reference.

## Features
- **Accounts**: custom user model with signup/login, avatar, city, phone, position, and bio.
- **Player profiles**: public player pages plus a self-service edit profile screen.
- **Team profiles**: name, logo, bio, home ground, city, level, and playstyle.
- **Find teams**: search and filter by level, playstyle, and city.
- **Match requests**: send a request to a specific team or create an open request.
- **Join requests**: players can request to join a team; captains can accept or decline.
- **Match reporting**: captains can submit final score, scorers, and player ratings.
- **Availability calendar**: mark days available, maybe, or unavailable from the dashboard.
- **Messaging**: encrypted 1:1 conversations between team captains.
- **Notifications**: team and user notifications for requests, acceptances, and replies.
- **Stats**: win rate, goals scored/conceded, clean sheets, reliability, and recent results.

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Then visit http://127.0.0.1:8000/accounts/signup/ to create an account. After signup,
you will be taken to the team onboarding flow.

## Project Layout
- `accounts/` - custom user model, profile views/forms, and auth routes.
- `core/` - teams, match requests, join requests, matches, notifications, encryption helpers,
  and the main app views/urls.
- `templates/` - server-rendered Django templates for the public app pages.
- `static/css/styles.css` - the dashboard and profile styling.

## Deployment

The project is configured for Render with `whitenoise`, `dj-database-url`, `build.sh`,
and `render.yaml`.

### Render Blueprint
1. Push the project to GitHub.
2. In Render, choose **New +** -> **Blueprint** and connect the repo.
3. Render reads `render.yaml`, creates the web service and PostgreSQL database, and
   sets `DATABASE_URL` automatically.

### Manual Render Setup
1. Push the project to GitHub.
2. Create a free PostgreSQL database in Render and copy the internal database URL.
3. Create a new web service connected to the repo.
4. Use these commands:
   - Build: `./build.sh`
   - Start: `gunicorn oppconnect.wsgi:application`
5. Add environment variables:
   - `SECRET_KEY`
   - `DEBUG=False`
   - `DATABASE_URL`
   - `MESSAGE_ENCRYPTION_KEY` for stable encrypted message storage in production
6. Deploy, then create a superuser from the shell if needed.

## Notes
- SQLite is fine for local development; Postgres is recommended in production.
- The encrypted message field uses `cryptography` and a stable
  `MESSAGE_ENCRYPTION_KEY` in production.
- Team captains can review join requests from the team management area.
