# Bluesky Engine

A terminal-style web app for growing your Bluesky audience. Automates following, liking, and unfollowing across multiple accounts.

## Features

### Dashboard
- Success metrics: Followers, Growth Rate, Follow Ratio, Engagement Rate
- Key drivers: Posts/Day, Follow-back Rate, Reply Rate, Repost Rate
- Real-time stats from Bluesky API

### Bots
- **Engage** — Like posts from non-followers randomly to get their attention
- **Grow** — Build your audience by following relevant accounts from target profiles
- **Clean Up** — Unfollow accounts that don't follow you back after X days

### Other
- Terminal-style dark UI with JetBrains Mono font
- Background threading — bots run without freezing the UI
- Live log output with progress tracking
- Browser notifications when bots complete
- Session-based settings persistence

## Quick Start

### Run locally

```bash
pip install atproto streamlit
streamlit run app.py
```

### Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file path to `app.py`
5. Deploy

## Usage

1. Sign in with your Bluesky handle and [App Password](https://bsky.app/settings/app-passwords)
2. Navigate to a bot tab (Engage, Grow, or Clean Up)
3. Configure settings (batch size, delays, etc.)
4. Click RUN to start the bot
5. Watch live progress in the log panel

## Tech Stack

- **Python** + **Streamlit** — web app framework
- **atproto** — Bluesky AT Protocol SDK
- **Threading** — background bot execution
- **Streamlit Cloud** — hosting

## Project Structure

```
bluesky-engine/
├── app.py              # Main Streamlit app
├── bots/
│   ├── like_bot.py     # Like bot logic
│   ├── follow_bot.py   # Follow bot logic
│   └── unfollow_bot.py # Unfollow bot logic
├── utils/
│   ├── stats.py        # Dashboard statistics
│   └── tracker.py      # Follower history tracking
└── data/               # Local data storage
```

## Rate Limits

Bluesky API rate limits apply. The bots are configured with conservative defaults:
- 5-15 second delays between actions
- Daily caps to avoid hitting limits
- Automatic pause on rate limit errors

## License

MIT
