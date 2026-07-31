# OppConnect

A Django web app for futsal teams to build profiles, find opponents, send/accept match
requests, manage availability, message other captains, and track match history & stats —
styled after the provided dashboard reference (dark sidebar, red accent).

## Features
- **Accounts**: custom user model, signup/login, each user creates/captains one team.
- **Team profiles**: name, logo, bio, home ground, city, level (Casual/Intermediate/
  Competitive), playstyle (Possession/Counter Attack/High Press/Defensive/Balanced).
- **Find Teams**: search + filter by level, playstyle and city.
- **Matchmaking**: send a match request to a specific team (date/time/venue/message),
  or post an open "Create Request" that other teams can see. Accept/Decline flow —
  accepting auto-creates a scheduled Match.
- **Availability calendar**: mark days Available / Maybe / Not Available (mini month
  calendar on the dashboard, like the reference UI).
- **Messaging**: 1:1 conversations between team captains, separate per team pairing.
- **Notifications**: created on new requests / accept / decline.
- **Stats**: win rate, goals scored/conceded, clean sheets, reliability %, recent match
  results — computed from completed Match records.

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Then visit http://127.0.0.1:8000/accounts/signup/ to create an account — you'll be asked
to set up your team profile right after signing up.

## Project layout
- `accounts/` — custom `User` model, signup/login views & forms.
- `core/` — `Team`, `TeamMembership`, `Availability`, `MatchRequest`, `Match`,
  `Conversation`, `Message`, `Notification` models, plus all app views/urls.
- `templates/` — server-rendered Django templates (base layout + per-page templates).
- `static/css/styles.css` — the dark-sidebar / red-accent theme matching your reference.

## Deploying for free (Render)

Heroku is discontinued and Railway/Fly.io no longer offer real free tiers as of 2026.
**Render** is currently the best free option: a free web service + free PostgreSQL,
no credit card required. (The free Postgres instance is deleted 90 days after creation,
and the free web service spins down after ~15 min idle — expect a ~30-50s cold start on
the first request after a while. Fine for a portfolio/internship project, not for
production traffic.)

The project is already configured for this: `whitenoise` serves static files,
`dj-database-url` reads `DATABASE_URL` if present (falls back to SQLite locally),
and `build.sh` / `render.yaml` are included.

**Option A — one-click via Blueprint:**
1. Push this project to a GitHub repo.
2. On https://dashboard.render.com → **New +** → **Blueprint** → connect the repo.
   Render reads `render.yaml` and creates both the web service and the free Postgres
   database automatically, wiring `DATABASE_URL` for you.
3. Wait for the build to finish, then open the assigned `*.onrender.com` URL.

**Option B — manual setup:**
1. Push to GitHub.
2. Dashboard → **New +** → **PostgreSQL** → free plan → create. Copy the "Internal
   Database URL".
3. Dashboard → **New +** → **Web Service** → connect the repo.
   - Build command: `./build.sh`
   - Start command: `gunicorn oppconnect.wsgi:application`
   - Add environment variables: `SECRET_KEY` (generate any random string),
     `DEBUG=False`, `DATABASE_URL` (paste the internal DB URL from step 2).
4. Deploy. First deploy runs migrations automatically via `build.sh`.
5. Create an admin user from the Render shell tab: `python manage.py createsuperuser`.

**Custom domain:** free on Render, add it under the web service's Settings → Custom Domains.

**If you outgrow the free tier:** Render's paid web service ($7/mo) removes the spin-down,
or move to a small VPS (Hetzner ~€4/mo) with Appliku's free-tier managed deploy tool on top.

- Currently one team per user (as captain). `TeamMembership` already supports multiple
  players per team if you want to add a "join team" flow for teammates.
- Match results are entered directly in Django admin (`/admin/`) on the `Match` model
  (`home_score` / `away_score`, set `status=completed`) — a captain-facing "report score"
  form would be a natural next addition.
- Open match requests currently just get listed under "Your Open Requests"; wiring them
  into `find_teams`/dashboard as challengeable public posts is a good next step.
- Swap SQLite for Postgres in `settings.py` `DATABASES` for production.
