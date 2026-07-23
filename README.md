# Cyber Crime Junkies — Netlify Site

Static site generator. Pulls all episodes from your Buzzsprout RSS feed
(`https://feeds.buzzsprout.com/2014652.rss`) fresh on every build — no manual
episode entry, no database.

## What this fixes from the Beamly audit
- Single clean `<title>` tag per page (no duplication)
- Correct canonical URL per page (no `?v=` params)
- Hand-written meta descriptions under 160 characters
- `301` redirect for `/chaos-brief` → `/chaos-brief-newsletter`
- `301` redirects collapsing `/video/*` and `/blog/*` into `/episode/*`
- PodcastSeries / PodcastEpisode schema (JSON-LD) on every page
- Direct-answer block at the top of every episode page (AEO)
- Chapter timestamps rendered as real text, not just audio markers
- Transcript link surfaced on every episode page that has one
- `sitemap.xml` and `robots.txt` generated automatically, `?v=` disallowed

## Deploy steps (15 minutes, no code required after setup)

1. **Create a GitHub repo** (or use any git host Netlify supports) and push
   this folder to it. If you don't use git day-to-day, ask anyone with basic
   GitHub familiarity to do this one-time step — it's five commands.
2. **Go to netlify.com → Add new site → Import an existing project.**
3. Connect the repo. Netlify will auto-detect `netlify.toml` — build command
   and publish directory are already set, don't change them.
4. Click **Deploy**. The first build fetches all current episodes from your
   RSS feed and generates the full site — homepage, every episode page,
   About, Book Series, Resources, Contact, Chaos Brief.
5. Once it's live on a `*.netlify.app` URL and you've checked it, go to
   **Domain settings → Add custom domain** and point `cybercrimejunkies.com`
   at it. Netlify gives you the DNS records to add at your registrar.
6. **Set up auto-rebuild** so new episodes appear automatically: Netlify →
   Site settings → Build & deploy → Build hooks → create a hook, then either
   trigger it manually after publishing a new episode, or use a free
   scheduling service (e.g. cron-job.org) to hit the hook URL nightly.

## Before going fully live — content to review

The generator writes real episode data automatically, but three pages have
placeholder copy marked with an editorial note — replace before launch:

- `/about` — name variant note; confirm host bio details
- `/resources` — replace placeholder guide titles/descriptions with your
  actual resource names and content
- `/book-series` — add reader reviews, a first-chapter excerpt, and an email
  capture for Book 3, as flagged in the original audit

## Running it locally to preview (optional)

```
pip install --break-system-packages -r requirements.txt  # none needed, stdlib only
python3 build.py
```

Output lands in `dist/`. Open `dist/index.html` in a browser to preview
before pushing.
