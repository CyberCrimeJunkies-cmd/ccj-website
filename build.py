#!/usr/bin/env python3
"""
Cyber Crime Junkies static site generator.
Runs at Netlify build time (Netlify's servers have network access).
Fetches the Buzzsprout RSS feed fresh on every build and generates:
  - homepage (single clean <title>, canonical, schema)
  - one page per episode (transcript, FAQ block, schema, canonical)
  - about / book-series / resources pages
  - sitemap.xml, robots.txt

No external pip packages required — stdlib only, so it runs on Netlify's
default Python image with zero install step.
"""

import os
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

RSS_URL = "https://feeds.buzzsprout.com/2014652.rss"
SITE_URL = "https://cybercrimejunkies.com"
SITE_NAME = "Cyber Crime Junkies"
OUT_DIR = "dist"

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


TOPIC_HUBS = [
    {
        "slug": "ransomware",
        "label": "Ransomware Players and Stories",
        "description": "Real ransomware attacks, what recovery actually looks like, and how to reduce your risk before it happens to you.",
        "keywords": ["ransomware", "revil", "kaseya", "extortion", "lockbit"],
    },
    {
        "slug": "social-engineering",
        "label": "Social Engineering",
        "description": "Phishing, pretexting, voice cloning, and the human manipulation tactics behind most breaches.",
        "keywords": ["social engineering", "phishing", "swatting", "osint", "deepfake", "voice cloning", "manipulat"],
    },
    {
        "slug": "ai-security",
        "label": "AI Trends and Stories",
        "description": "What AI actually changes about cyber risk — for attackers, defenders, and everyday business decisions.",
        "keywords": ["ai ", " ai", "artificial intelligence", "agentic", "chatgpt", "claude", "truth machine", "creativity"],
    },
    {
        "slug": "cmmc-compliance",
        "label": "Compliance News, HIPAA and CMMC",
        "description": "CMMC, HIPAA, NIST, and the compliance requirements reshaping small business contracts and healthcare data rules.",
        "keywords": ["cmmc", "compliance", "nist", "audit", "regulation", "attestation", "hipaa"],
    },
    {
        "slug": "smb-defense",
        "label": "How To Stay Safe Online",
        "description": "Practical cybersecurity guidance built for small and mid-sized businesses without a dedicated security team.",
        "keywords": ["small business", "smb", "msp", "managed service", "small organizations"],
    },
]


def classify_episode(ep):
    haystack = (ep["title"] + " " + ep["summary_plain"]).lower()
    matched = []
    for hub in TOPIC_HUBS:
        if any(kw in haystack for kw in hub["keywords"]):
            matched.append(hub["slug"])
    return matched


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def strip_html(raw):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text, length):
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "..."


def fetch_feed():
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0 (Netlify build)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_episodes(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    episodes = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        summary = item.findtext("itunes:summary", default="", namespaces=NS)
        description = item.findtext("description", default="", namespaces=NS)
        content_encoded = item.findtext("content:encoded", default="", namespaces=NS)
        duration = item.findtext("itunes:duration", default="", namespaces=NS)
        season = item.findtext("itunes:season", default="", namespaces=NS)
        episode_num = item.findtext("itunes:episode", default="", namespaces=NS)
        image_el = item.find("itunes:image", NS)
        image = image_el.get("href") if image_el is not None else ""
        enclosure_el = item.find("enclosure")
        audio_url = enclosure_el.get("url") if enclosure_el is not None else ""
        transcript_el = item.find("podcast:transcript", NS)
        transcript_url = transcript_el.get("url") if transcript_el is not None else ""
        chapters = []
        for ch in item.findall(".//{http://podlove.org/simple-chapters}chapter"):
            chapters.append({"start": ch.get("start"), "title": ch.get("title")})

        try:
            pub_date = datetime.strptime(pub_date_raw[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            pub_date = None

        slug = slugify(title) or slugify(guid)

        episodes.append({
            "title": title.strip(),
            "slug": slug,
            "guid": guid,
            "pub_date": pub_date,
            "pub_date_display": pub_date.strftime("%B %d, %Y") if pub_date else "",
            "pub_date_iso": pub_date.isoformat() if pub_date else "",
            "summary_plain": strip_html(summary),
            "description_html": content_encoded or description,
            "duration": duration,
            "season": season,
            "episode_num": episode_num,
            "image": image,
            "audio_url": audio_url,
            "transcript_url": transcript_url,
            "chapters": chapters,
        })
    episodes.sort(key=lambda e: e["pub_date"] or datetime.min, reverse=True)
    return episodes


def base_head(title, description, canonical_path, extra_schema=""):
    canonical = f"{SITE_URL}{canonical_path}"
    return f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@cybercrimejunky">
<link rel="stylesheet" href="/style.css">
{extra_schema}"""


def nav():
    return """<header class="site-header">
  <div class="banner"><a href="/contact">Complimentary Cyber Awareness &amp; AI Workshops Now Available &mdash; Reach Out Today</a></div>
  <nav class="nav">
    <a class="brand" href="/"><img src="/images/logo.png" alt="Cyber Crime Junkies logo" class="logo-img"> Cyber Crime Junkies</a>
    <a href="/">Home</a>
    <a href="/book-series">Book Series</a>
    <a href="/chaos-brief-newsletter">Chaos Brief Newsletter</a>
    <a href="/resources">Resources</a>
    <a href="/episodes">Episodes</a>
    <a href="/about">About</a>
    <a href="/contact">Contact Us</a>
  </nav>
</header>"""


def footer():
    return f"""<footer class="site-footer">
  <p>&copy; 2026 David Dean Mauro &mdash; Cyber Crime Junkies Media</p>
</footer>"""


def episode_schema(ep):
    parts = [f'"name": {json_str(ep["title"])}', f'"description": {json_str(ep["summary_plain"][:300])}']
    if ep["pub_date_iso"]:
        parts.append(f'"datePublished": {json_str(ep["pub_date_iso"])}')
    if ep["duration"]:
        parts.append(f'"duration": {json_str("PT" + ep["duration"] + "S")}')
    if ep["audio_url"]:
        parts.append(f'"associatedMedia": {{"@type": "MediaObject", "contentUrl": {json_str(ep["audio_url"])}}}')
    return f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  {", ".join(parts)},
  "partOfSeries": {{"@type": "PodcastSeries", "name": "Cyber Crime Junkies", "url": "{SITE_URL}"}}
}}
</script>"""


def json_str(s):
    return html.unescape(s).replace('"', '\\"').replace("\n", " ")


def json_str(s):  # noqa: F811 - simple escaper, redefined intentionally
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    return f'"{s}"'


def render_episode_page(ep):
    title = f"{ep['title']} | Cyber Crime Junkies"
    desc = truncate(ep["summary_plain"], 155) if ep["summary_plain"] else f"{ep['title']} on Cyber Crime Junkies."
    answer_block = truncate(ep["summary_plain"], 300) if ep["summary_plain"] else ""

    chapters_html = ""
    if ep["chapters"]:
        rows = "\n".join(f"<li><span class='ts'>{html.escape(c['start'] or '')}</span> {html.escape(c['title'] or '')}</li>" for c in ep["chapters"])
        chapters_html = f"<section class='chapters'><h2>Chapters</h2><ul>{rows}</ul></section>"

    transcript_html = ""
    if ep["transcript_url"]:
        transcript_html = f"<p class='transcript-link'><a href='{ep['transcript_url']}'>Read the full transcript</a></p>"

    meta = " &middot; ".join(filter(None, [
        f"Season {ep['season']}" if ep["season"] else "",
        f"Episode {ep['episode_num']}" if ep["episode_num"] else "",
        ep["pub_date_display"],
    ]))

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
{base_head(title, desc, f"/episode/{ep['slug']}", episode_schema(ep))}
</head>
<body>
{nav()}
<main class="episode-page">
  <article>
    <h1>{html.escape(ep['title'])}</h1>
    <p class="episode-meta">{meta}</p>
    {f'<p class="answer-block">{html.escape(answer_block)}</p>' if answer_block else ''}
    {f'<audio controls src="{ep["audio_url"]}"></audio>' if ep["audio_url"] else ''}
    <div class="episode-description">{ep['description_html']}</div>
    {chapters_html}
    {transcript_html}
  </article>
</main>
{footer()}
</body>
</html>"""
    return body


def render_homepage(episodes):
    title = "Cyber Crime Junkies | True Crime Stories & AI Security Podcast"
    desc = "True crime stories and expert interviews on cybersecurity and AI. Hosted by Dean Mauro. New episodes and the Chaos Brief newsletter every week."

    cards = ""
    for ep in episodes[:12]:
        cards += f"""<a class="episode-card" href="/episode/{ep['slug']}">
  <h3>{html.escape(ep['title'])}</h3>
  <p class="episode-meta">{ep['pub_date_display']}</p>
  <p>{html.escape(truncate(ep['summary_plain'], 140))}</p>
</a>"""

    schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "PodcastSeries",
  "name": "Cyber Crime Junkies",
  "url": "{SITE_URL}",
  "description": {json_str(desc)},
  "author": {{"@type": "Person", "name": "Dean Mauro"}}
}}
</script>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{base_head(title, desc, "/", schema)}
</head>
<body>
{nav()}
<main class="homepage">
  <section class="hero">
    <img src="/images/dean-closeup.jpg" alt="Dean Mauro, host of Cyber Crime Junkies" class="hero-img-home">
    <div>
      <h1>Cybersecurity and AI True Crime for Business Leaders</h1>
      <p>Real cybercrime stories, expert interviews, and AI security explained in plain language. Hosted by Dean Mauro.</p>
    </div>
  </section>

  <section class="buzzsprout-player">
    <div id="buzzsprout-large-player"></div>
    <script type="text/javascript" charset="utf-8" src="https://www.buzzsprout.com/2014652.js?container_id=buzzsprout-large-player&amp;player=large"></script>
  </section>

  <section class="trailer-section">
    <div class="video-embed">
      <iframe src="https://www.youtube.com/embed/B_SoawySWQA" title="Cyber Crime Junkies Trailer" frameborder="0" allowfullscreen loading="lazy"></iframe>
    </div>
    <a class="watch-youtube-link" href="https://youtu.be/B_SoawySWQA">Watch on YouTube</a>
  </section>

  <section class="home-studio-row">
    <img src="/images/home-hacking-hacker.jpg" alt="Cyber Crime Junkies studio shelf with Hacking the Hacker">
    <img src="/images/home-monitors.jpg" alt="Cyber Crime Junkies studio multi-monitor setup">
  </section>
  <section class="spotlight">
    <h2>Latest Episodes</h2>
    <div class="episode-grid">
      {cards}
    </div>
    <a class="see-all" href="/episodes">See all episodes</a>
  </section>
</main>
{footer()}
</body>
</html>"""


def render_episodes_index(episodes):
    title = "All Episodes | Cyber Crime Junkies"
    desc = "Every Cyber Crime Junkies episode organized by topic: ransomware, social engineering, AI security, CMMC, and small business defense."

    for ep in episodes:
        ep["_hubs"] = classify_episode(ep)

    hub_sections = ""
    for hub in TOPIC_HUBS:
        matches = [ep for ep in episodes if hub["slug"] in ep["_hubs"]][:6]
        if not matches:
            continue
        cards = "\n".join(
            f"""<a class="episode-card" href="/episode/{ep['slug']}">
  <h3>{html.escape(ep['title'])}</h3>
  <p class="episode-meta">{ep['pub_date_display']}</p>
</a>""" for ep in matches
        )
        hub_sections += f"""<section class="hub-section" id="{hub['slug']}">
  <h2>{hub['label']}</h2>
  <p class="hub-desc">{hub['description']}</p>
  <div class="episode-grid">{cards}</div>
</section>"""

    rows = "\n".join(
        f"""<li><a href="/episode/{ep['slug']}">{html.escape(ep['title'])}</a> <span class="episode-meta">{ep['pub_date_display']}</span></li>"""
        for ep in episodes
    )

    hub_nav = " &middot; ".join(f'<a href="#{h["slug"]}">{h["label"]}</a>' for h in TOPIC_HUBS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{base_head(title, desc, "/episodes")}
</head>
<body>
{nav()}
<main class="episodes-index">
  <section class="episodes-hero">
    <img src="/images/dean-studio.jpg" alt="Dean Mauro recording Cyber Crime Junkies in studio" class="hero-img">
    <div class="episodes-hero-text">
      <h1>All Episodes</h1>
      <p>True crime stories, cybersecurity, and AI &mdash; organized by topic below, or browse everything newest first.</p>
      <p class="hub-jump">{hub_nav}</p>
    </div>
  </section>

  <section class="hack-or-hype-feature">
    <img src="/images/hack-or-hype.png" alt="Hack or Hype segment on Cyber Crime Junkies">
    <div>
      <h2>Segment: Hack or Hype</h2>
      <p>A recurring bit where guests call out real threats versus overhyped headlines &mdash; watch for it across recent episodes.</p>
    </div>
  </section>

  {hub_sections}

  <section class="team-strip">
    <img src="/images/team-graphic.png" alt="Cyber Crime Junkies team: Dean Mauro, Kylie Jaimeson, Dr. Sergio Sanchez, Mike Acerra" class="team-graphic-img">
  </section>

  <section class="behind-scenes">
    <img src="/images/riverside-session.png" alt="Recording a Cyber Crime Junkies interview">
    <p class="hub-desc">Behind the scenes recording an episode.</p>
  </section>

  <section class="all-episodes">
    <h2>All Episodes, Newest First</h2>
    <ul class="episode-list">{rows}</ul>
  </section>
</main>
{footer()}
</body>
</html>"""


def render_static_page(slug, title_tag, desc, h1, content_html):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{base_head(title_tag, desc, f"/{slug}" if slug else "/")}
</head>
<body>
{nav()}
<main class="static-page">
  <h1>{h1}</h1>
  {content_html}
</main>
{footer()}
</body>
</html>"""


ABOUT_CONTENT = """
<div class="about-hero">
  <img src="/images/dean-noir.jpg" alt="Dean Mauro, author and host" class="about-hero-img">
  <div>
    <p>Cyber Crime Junkies is a true crime podcast about cybersecurity and AI &mdash; real breach stories, hacker interviews,
    and plain-language explanations of the threats facing small and mid-sized businesses.</p>
    <p>Hosted by <strong>Dean Mauro</strong> &mdash; VP of Growth at NetGain Technologies, a Top 250 Managed Security Service
    Provider (SOC 2 Type II certified, operating since 1984), FBI InfraGard member, former trial lawyer, and author of the
    Moving Target Trilogy.</p>
  </div>
</div>

<h2>The team</h2>
<img src="/images/team-graphic.png" alt="Cyber Crime Junkies team: Dean Mauro, Kylie Jaimeson, Dr. Sergio Sanchez, Mike Acerra" class="about-wide-img">

<h2>On the road</h2>
<img src="/images/dean-speaking.png" alt="Dean Mauro speaking at industry conferences" class="about-wide-img">
<p>Dean speaks regularly at industry conferences and community workshops on cybersecurity, AI governance, and business risk.</p>

<div class="about-shelf-row">
  <img src="/images/about-shelf-1.jpg" alt="Cyber Crime Junkies studio shelf">
  <img src="/images/about-shelf-2.jpg" alt="Cyber Crime Junkies studio shelf, FDNY and NYPD">
</div>

<h2>Editorial note on names</h2>
<p>The host publishes as <strong>Dean Mauro</strong>. "David Dean Mauro" appears as a legal-name variant on some
podcast directories and older episode credits.</p>
"""

RESOURCES_CONTENT = """
<p>Free guides and tools for small business leaders navigating cybersecurity and AI risk. Enter your email to unlock each download.</p>
<div class="resource-grid">
  <div class="resource-card">
    <h3>AI Prompt Guide</h3>
    <p>Five ready-to-use prompts: personalize any AI to sound like you, verify outputs before you trust them, build an
    executive briefing agent, and manage tool and vendor decisions.</p>
    <form name="ai-prompt-guide" method="POST" data-netlify="true" action="/resources/ai-prompt-guide-thank-you/">
      <input type="hidden" name="form-name" value="ai-prompt-guide">
      <input type="email" name="email" placeholder="Your email" required>
      <button type="submit" class="buy-now-btn">Get the Guide</button>
    </form>
  </div>
  <div class="resource-card">
    <h3>AI Governance &amp; Personal Set Up Guide</h3>
    <p>What to do and not do with AI at work, how to set up AI to teach you anything, the most common governance gaps,
    and a full governance checklist for leadership teams.</p>
    <form name="ai-governance-guide" method="POST" data-netlify="true" action="/resources/ai-governance-guide-thank-you/">
      <input type="hidden" name="form-name" value="ai-governance-guide">
      <input type="email" name="email" placeholder="Your email" required>
      <button type="submit" class="buy-now-btn">Get the Guide</button>
    </form>
  </div>
  <div class="resource-card">
    <h3>Moving Target Camouflage Checklist</h3>
    <p>The full checklist from the book on one page &mdash; password managers, LinkedIn exposure, people-search
    removal, verifying vendors, and the family code word. Ten actions, no jargon.</p>
    <form name="camouflage-checklist" method="POST" data-netlify="true" action="/resources/camouflage-checklist-thank-you/">
      <input type="hidden" name="form-name" value="camouflage-checklist">
      <input type="email" name="email" placeholder="Your email" required>
      <button type="submit" class="buy-now-btn">Get the Checklist</button>
    </form>
  </div>
  <div class="resource-card">
    <h3>Ransomware Response Plan Template</h3>
    <p>The first 24 hours: who to call, what to preserve, what not to do.</p>
    <a href="/contact">Get the guide</a>
  </div>
</div>
<p><em>Editorial note: replace the Ransomware Response Plan Template placeholder with the real guide, same gated-email
pattern as the others, before launch.</em></p>
"""

THANK_YOU_PAGES = {
    "ai-prompt-guide-thank-you": {
        "title": "Thanks — Your AI Prompt Guide Is Ready | Cyber Crime Junkies",
        "h1": "Thanks — here's your guide",
        "file": "/files/ai-prompt-guide.pdf",
        "label": "AI Prompt Guide",
    },
    "ai-governance-guide-thank-you": {
        "title": "Thanks — Your AI Governance Guide Is Ready | Cyber Crime Junkies",
        "h1": "Thanks — here's your guide",
        "file": "/files/ai-governance-guide.pdf",
        "label": "AI Governance &amp; Personal Set Up Guide",
    },
    "camouflage-checklist-thank-you": {
        "title": "Thanks — Your Camouflage Checklist Is Ready | Cyber Crime Junkies",
        "h1": "Thanks — here's your checklist",
        "file": "/files/camouflage-checklist.pdf",
        "label": "Moving Target Camouflage Checklist",
    },
}

BOOK_SERIES_CONTENT = """
<img src="/images/book-collage.png" alt="Moving Target Trilogy by Dean Mauro, #1 Amazon Hot New Release" class="book-hero-img">
<p>The Moving Target Trilogy &mdash; nonfiction cybercrime thrillers based on 400+ interviews over four years.</p>
<div class="book-shelf-row">
  <img src="/images/book-shelf-wide.jpg" alt="Moving Target books on studio shelf">
  <img src="/images/book-shelf-closeup.jpg" alt="Moving Target: Art of Online Camouflage and The Obedient Machine">
</div>
<div class="book-grid">
  <div class="book-card">
    <img src="/images/book1-cover.png" alt="Book 1: Art of Online Camouflage cover" class="book-cover-img">
    <h3>Book 1: Art of Online Camouflage</h3>
    <a class="buy-now-btn" href="https://www.audible.com/pd/B0GXGS1ZHC/?source_code=AUDFPWS0223189MWT-BK-ACX0-506376&amp;ref=acx_bty_BK_ACX0_506376_rh_us">Buy Now</a>
  </div>
  <div class="book-card">
    <img src="/images/book2-cover.png" alt="Book 2: Obedient Machine cover" class="book-cover-img">
    <h3>Book 2: Obedient Machine</h3>
    <a class="buy-now-btn" href="https://shop.ingramspark.com/b/084?params=S3F9zWWMC2y2eYiTmUGP91Owy9AUVG4zbLa6NwuX3cl">Buy Now</a>
  </div>
  <div class="book-card">
    <img src="/images/book3-cover.png" alt="Book 3: The Ghost and the Machine cover" class="book-cover-img">
    <h3>Book 3: The Ghost and the Machine</h3>
    <p>Releases September 22, 2026.</p>
    <a class="buy-now-btn" href="https://a.co/0gG92uN0">Presale Offer &mdash; Live 9/22</a>
  </div>
</div>
<p><em>Editorial note: add reader reviews and a first-chapter excerpt before launch &mdash; these were flagged as missing in
the site audit.</em></p>
<p><a class="buy-now-btn" href="/files/moving-target-media-flyer.pdf" download>Download Media Flyer (PDF)</a></p>
"""

CONTACT_CONTENT = """
<p>Reach out about workshops, speaking, podcast guesting, or press.</p>
<p>Email: <a href="mailto:cybercrimejunkies@gmail.com">cybercrimejunkies@gmail.com</a></p>
"""
PRIVACY_CONTENT = """
<h2>Privacy Policy</h2>
<p>Last updated: 2026</p>
<p>Cyber Crime Junkies ("we," "us," or "our") operates cybercrimejunkies.com. This policy explains what information we collect, how we use it, and what rights you have over it.</p>
<h2>Information We Collect</h2>
<p>When you contact us through our website form, we collect your name and email address. If you subscribe to the Chaos Brief newsletter, we collect your email address. We do not sell this information to anyone.</p>
<h2>Third-Party Services</h2>
<p>Our site uses the following third-party services, each with their own privacy practices: Buzzsprout hosts our podcast audio. Netlify hosts our website, with the site built from a GitHub repository. YouTube hosts our video content. Substack and LinkedIn host our newsletter. Each of these services may collect usage data independently.</p>
<h2>Analytics</h2>
<p>We may collect basic, anonymized traffic data to understand how visitors use the site. This data does not identify you personally.</p>
<h2>Cookies</h2>
<p>Our website may use cookies to function properly. You can disable cookies in your browser settings, though some site features may not work as a result.</p>
<h2>Your Rights</h2>
<p>You may request to see, correct, or delete any personal information we hold about you. To do so, contact us at the email address listed on our Contact page.</p>
<h2>Children's Privacy</h2>
<p>This site is not directed at children under 13. We do not knowingly collect information from children.</p>
<h2>Changes to This Policy</h2>
<p>We may update this policy as our site evolves. Changes will be posted on this page with an updated date.</p>
<h2>Contact</h2>
<p>For privacy-related questions, contact us at cybercrimejunkies@gmail.com</p>
"""

GUEST_POLICY_CONTENT = """
<p>Effective Date: June 2026 | cybercrimejunkies.com</p>
<p>Thank you for appearing on Cyber Crime Junkies. Before we record, please read this policy. It is short, plain, and fair. If you have questions, email us before your session.</p>
<h2>What You're Agreeing To</h2>
<p>By participating in a Cyber Crime Junkies recording session, you grant Cyber Crime Junkies and its host Dean Mauro a perpetual, royalty-free, worldwide license to use your name, voice, likeness, and the content of your interview. That license covers all current and future media formats including audio, video, short-form clips, transcripts, and written summaries.</p>
<h2>How Your Appearance May Be Used</h2>
<p>Your interview may be published as a full podcast episode, a short-form clip, a YouTube video, a social media post, a newsletter feature, or a written recap. We may edit for length, clarity, and pacing. We will not misrepresent your words or take statements out of context in a way that changes their meaning.</p>
<h2>What You Own</h2>
<p>You retain all rights to your own intellectual property, including any proprietary frameworks, methodologies, or published works you discuss. Appearing on CCJ does not transfer ownership of your ideas or content to us. All video, audio and imagery used for the podcast, newsletter and future discussion created by us are owned exclusively by us.</p>
<h2>Promotion and Sharing</h2>
<p>We encourage you to share your episode. We will provide you with a shareable link, cover art, and clip assets when available. You may promote your appearance on any channel.</p>
<h2>Content Standards</h2>
<p>Cyber Crime Junkies covers cybersecurity, AI risk, and organized cybercrime for business audiences. Guests are expected to present information in good faith, disclose any material conflicts of interest, and avoid making false or defamatory claims about individuals or organizations. We reserve the right to decline to publish any recording, in whole or in part, if it does not meet our editorial standards or creates legal exposure.</p>
<h2>No Compensation</h2>
<p>Guest appearances are unpaid unless otherwise agreed in writing before the session.</p>
<h2>No Endorsement</h2>
<p>Appearing on Cyber Crime Junkies does not constitute an endorsement by David Dean Mauro, Cyber Crime Junkies or NetGain Technologies of your products, services, or organization, unless explicitly stated on air or in writing.</p>
<h2>Questions</h2>
<p>Contact us at: cybercrimejunkies@gmail.com</p>
<p>Cyber Crime Junkies is produced by <strong>David Dean Mauro | Cyber Crime Junkies</strong></p>
"""

def render_sitemap(episodes):
    urls = ["", "/about", "/book-series", "/resources", "/episodes", "/contact", "/chaos-brief-newsletter", "/privacy-policy", "/guest-policy"]
    entries = "\n".join(f"  <url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    ep_entries = "\n".join(f"  <url><loc>{SITE_URL}/episode/{e['slug']}</loc></url>" for e in episodes)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
{ep_entries}
</urlset>"""


ROBOTS = f"""User-agent: *
Allow: /
Disallow: /*?v=
Sitemap: {SITE_URL}/sitemap.xml
"""

STYLE_CSS = """
:root { --navy:#12233d; --blue:#3f6fa3; --bg:#0d1420; --text:#e8edf3; --muted:#9fb0c3; }
* { box-sizing: border-box; }
body { margin:0; font-family: 'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--text); line-height:1.6; }
a { color:#7eb2d0; text-decoration:none; }
a:hover { text-decoration:underline; }
.banner { background:var(--navy); color:#fff; text-align:center; padding:10px; font-size:14px; }
.nav { display:flex; align-items:center; gap:20px; padding:16px 24px; background:var(--navy); flex-wrap:wrap; }
.nav .brand { font-weight:bold; font-size:20px; color:#fff; margin-right:auto; }
main { max-width:1000px; margin:0 auto; padding:32px 20px; }
.hero h1 { font-size:2.2rem; }
.episode-grid, .resource-grid, .book-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:20px; margin:24px 0; }
.episode-card, .resource-card, .book-card { background:#16233a; padding:16px; border-radius:8px; }
.episode-meta { color:var(--muted); font-size:0.85rem; }
.answer-block { background:#16233a; padding:16px; border-left:4px solid var(--blue); border-radius:4px; }
.chapters ul { list-style:none; padding:0; }
.chapters .ts { color:var(--muted); display:inline-block; width:60px; }
.episode-list { list-style:none; padding:0; }
.episode-list li { padding:10px 0; border-bottom:1px solid #223349; display:flex; justify-content:space-between; }
.site-footer { text-align:center; padding:24px; color:var(--muted); font-size:0.85rem; }
audio { width:100%; margin:16px 0; }
.logo-img { height:32px; width:32px; object-fit:cover; border-radius:6px; vertical-align:middle; margin-right:8px; }
.episodes-hero { display:flex; gap:24px; align-items:center; background:#16233a; border-radius:10px; padding:24px; margin-bottom:32px; flex-wrap:wrap; }
.episodes-hero .hero-img { width:220px; height:220px; object-fit:cover; border-radius:10px; }
.episodes-hero-text h1 { margin-top:0; }
.hub-jump a { margin-right:4px; }
.hub-section { margin:40px 0; }
.hub-section h2 { border-bottom:2px solid var(--blue); padding-bottom:8px; }
.hub-desc { color:var(--muted); max-width:700px; }
.team-strip { display:flex; gap:24px; margin:40px 0; flex-wrap:wrap; }
.team-member { text-align:center; }
.team-member img { width:120px; height:120px; object-fit:cover; border-radius:50%; }
.team-member p { color:var(--muted); font-size:0.9rem; margin-top:8px; }
.all-episodes { margin-top:40px; }
.hero-img-home { width:200px; height:200px; object-fit:cover; border-radius:10px; float:left; margin-right:24px; }
.hero { overflow:auto; }
.about-hero { display:flex; gap:24px; align-items:flex-start; flex-wrap:wrap; margin-bottom:32px; }
.about-hero-img { width:240px; height:240px; object-fit:cover; border-radius:10px; }
.about-wide-img { width:100%; max-width:800px; border-radius:10px; margin:16px 0; display:block; }
.about-team-row { display:flex; align-items:center; gap:20px; margin:24px 0; }
.about-team-img { width:100px; height:100px; object-fit:cover; border-radius:50%; }
.book-hero-img { width:100%; max-width:900px; border-radius:10px; margin-bottom:16px; display:block; }
.hack-or-hype-feature { display:flex; gap:20px; align-items:center; background:#16233a; border-radius:10px; padding:16px; margin:24px 0; flex-wrap:wrap; }
.hack-or-hype-feature img { width:280px; border-radius:8px; }
.hack-or-hype-feature h2 { margin-top:0; }
.behind-scenes { margin:40px 0; }
.behind-scenes img { max-width:500px; width:100%; border-radius:10px; display:block; }
.book-cover-img { width:100%; max-width:220px; border-radius:6px; margin-bottom:12px; }
.buy-now-btn { display:inline-block; margin-top:10px; padding:10px 18px; background:var(--blue); color:#fff; border-radius:6px; font-weight:bold; }
.buy-now-btn:hover { background:#5487bb; text-decoration:none; }
.trailer-section { margin:32px 0; }
.video-embed { position:relative; width:100%; max-width:700px; padding-bottom:39.375%; height:0; overflow:hidden; border-radius:10px; }
.video-embed iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; border-radius:10px; }
.watch-youtube-link { display:inline-block; margin-top:10px; color:var(--muted); font-size:0.9rem; }
.resource-card form { margin-top:12px; display:flex; flex-direction:column; gap:8px; }
.resource-card input[type=email] { padding:10px; border-radius:6px; border:1px solid #2a3b56; background:#0d1420; color:var(--text); }
.resource-card button.buy-now-btn { border:none; cursor:pointer; font-size:1rem; }
.about-shelf-row { display:flex; gap:16px; margin:24px 0; flex-wrap:wrap; }
.about-shelf-row img { width:100%; max-width:380px; border-radius:10px; flex:1; min-width:280px; }
.team-graphic-img { width:100%; max-width:900px; border-radius:10px; display:block; margin:0 auto; }
.home-studio-row { display:flex; gap:16px; margin:24px 0; flex-wrap:wrap; }
.home-studio-row img { width:100%; max-width:340px; border-radius:10px; flex:1; min-width:260px; }
.book-shelf-row { display:flex; gap:16px; margin:24px 0 32px; flex-wrap:wrap; }
.book-shelf-row img { width:100%; max-width:420px; border-radius:10px; flex:1; min-width:280px; }
.buzzsprout-player { max-width:700px; margin:24px 0; }
"""


def copy_images():
    import shutil
    src = "static/images"
    dst = f"{OUT_DIR}/images"
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for fname in os.listdir(src):
            shutil.copyfile(f"{src}/{fname}", f"{dst}/{fname}")

    fsrc = "static/files"
    fdst = f"{OUT_DIR}/files"
    if os.path.isdir(fsrc):
        os.makedirs(fdst, exist_ok=True)
        for fname in os.listdir(fsrc):
            shutil.copyfile(f"{fsrc}/{fname}", f"{fdst}/{fname}")


def render_thank_you_page(slug, info):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{base_head(info['title'], f"Download your {info['label']}.", f"/resources/{slug}")}
</head>
<body>
{nav()}
<main class="static-page">
  <h1>{info['h1']}</h1>
  <p>Your download is ready.</p>
  <a class="buy-now-btn" href="{info['file']}" download>Download {info['label']}</a>
</main>
{footer()}
</body>
</html>"""


def main():
    os.makedirs(f"{OUT_DIR}/episode", exist_ok=True)
    copy_images()

    print("Fetching RSS feed...")
    xml_bytes = fetch_feed()
    episodes = parse_episodes(xml_bytes)
    print(f"Parsed {len(episodes)} episodes.")

    with open(f"{OUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(render_homepage(episodes))

    with open(f"{OUT_DIR}/episodes.html", "w", encoding="utf-8") as f:
        f.write(render_episodes_index(episodes))
    os.makedirs(f"{OUT_DIR}/episodes", exist_ok=True)
    with open(f"{OUT_DIR}/episodes/index.html", "w", encoding="utf-8") as f:
        f.write(render_episodes_index(episodes))

    for ep in episodes:
        path = f"{OUT_DIR}/episode/{ep['slug']}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_episode_page(ep))
        # also write as directory/index.html so /episode/<slug> works without .html
        d = f"{OUT_DIR}/episode/{ep['slug']}"
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/index.html", "w", encoding="utf-8") as f:
            f.write(render_episode_page(ep))

    os.makedirs(f"{OUT_DIR}/about", exist_ok=True)
    with open(f"{OUT_DIR}/about/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("about", "About | Cyber Crime Junkies",
                                    "Host Dean Mauro and the story behind Cyber Crime Junkies.",
                                    "About Cyber Crime Junkies", ABOUT_CONTENT))

    os.makedirs(f"{OUT_DIR}/resources", exist_ok=True)
    with open(f"{OUT_DIR}/resources/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("resources", "Free Cybersecurity & AI Resources | Cyber Crime Junkies",
                                    "Free guides on cybersecurity basics, AI governance, and ransomware response for small business.",
                                    "Resources", RESOURCES_CONTENT))

    for slug, info in THANK_YOU_PAGES.items():
        os.makedirs(f"{OUT_DIR}/resources/{slug}", exist_ok=True)
        with open(f"{OUT_DIR}/resources/{slug}/index.html", "w", encoding="utf-8") as f:
            f.write(render_thank_you_page(slug, info))

    os.makedirs(f"{OUT_DIR}/book-series", exist_ok=True)
    with open(f"{OUT_DIR}/book-series/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("book-series", "The Moving Target Trilogy | Cyber Crime Junkies",
                                    "Nonfiction cybercrime thrillers by Dean Mauro, based on 400+ interviews.",
                                    "The Moving Target Trilogy", BOOK_SERIES_CONTENT))

    os.makedirs(f"{OUT_DIR}/contact", exist_ok=True)
    with open(f"{OUT_DIR}/contact/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("contact", "Contact | Cyber Crime Junkies",
                                    "Get in touch about workshops, speaking, or the show.",
                                    "Contact Us", CONTACT_CONTENT))
    os.makedirs(f"{OUT_DIR}/privacy-policy", exist_ok=True)
    with open(f"{OUT_DIR}/privacy-policy/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("privacy-policy", "Privacy Policy | Cyber Crime Junkies",
                                     "Privacy Policy for Cyber Crime Junkies and cybercrimejunkies.com.",
                                     "Privacy Policy", PRIVACY_CONTENT))

    os.makedirs(f"{OUT_DIR}/guest-policy", exist_ok=True)
    with open(f"{OUT_DIR}/guest-policy/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("guest-policy", "Podcast Guest Policy | Cyber Crime Junkies",
                                     "Podcast Guest Policy for Cyber Crime Junkies. What guests agree to before recording.",
                                     "Podcast Guest Policy", GUEST_POLICY_CONTENT))
    os.makedirs(f"{OUT_DIR}/chaos-brief-newsletter", exist_ok=True)
    with open(f"{OUT_DIR}/chaos-brief-newsletter/index.html", "w", encoding="utf-8") as f:
        f.write(render_static_page("chaos-brief-newsletter", "The Chaos Brief Newsletter | Cyber Crime Junkies",
                                    "Weekly cybersecurity and AI true crime stories, straight to your inbox.",
                                    "The Chaos Brief Newsletter",
                                    "<p>Subscribe on <a href='https://www.linkedin.com/newsletters/the-chaos-brief-6941459114879311872/'>LinkedIn</a> or <a href='https://chaosbrief.substack.com/'>Substack</a>.</p>"))

    with open(f"{OUT_DIR}/sitemap.xml", "w", encoding="utf-8") as f:
        f.write(render_sitemap(episodes))

    with open(f"{OUT_DIR}/robots.txt", "w", encoding="utf-8") as f:
        f.write(ROBOTS)

    with open(f"{OUT_DIR}/style.css", "w", encoding="utf-8") as f:
        f.write(STYLE_CSS)

    print(f"Build complete: {len(episodes)} episode pages + homepage + core pages written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
