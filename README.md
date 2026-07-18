# Bluesky Engine

Terminal-style web app for growing Bluesky followers. Automates following, liking, and unfollowing across multiple accounts.

## Features

- **Dashboard** — live follower stats, growth chart, bot status
- **Like Bot** — like posts from non-followers to trigger notifications
- **Follow Bot** — copy followers from target accounts (coming soon)
- **Unfollow Bot** — clean up non-followers (coming soon)

## Quick Start

### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file path to `app.py`
5. Deploy

## Tech Stack

- **Python** + **Streamlit** — web app
- **atproto** — Bluesky API
- **Streamlit Cloud** — hosting

## How It Works

1. Add your Bluesky accounts in Settings
2. Configure batch size, delays
3. Click Run — bot runs on the server
4. Watch live log output in the terminal-style UI

## License

MIT
