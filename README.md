# 📚 Anonymous Q&A Bot for Learning Centres

A Telegram bot that lets students ask questions **anonymously** and teachers manage & reply to them efficiently. Built for SAT prep, but works for **any learning centre**.

## ✨ Features

### For Students
- 📝 **Compose questions** — send multiple messages (text, photos, docs) as one bundled question
- 🔒 **100% anonymous** — teacher never sees your name or ID
- 🔔 **Get replies** — teacher's answer arrives right in the chat

### For Teachers
- 📩 **Receive questions** with **Reply** / **Done** inline buttons
- 📋 `/queue` — see all pending questions at a glance
- 📊 `/stats` — track total questions, answer rate, student count
- 📢 `/broadcast` — send announcements to all students
- 🗑 **Clear Done** — clean up resolved questions
- ⚙️ `/menu` — management panel with all actions

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/alfasatbot.git
cd alfasatbot

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env with your bot token and teacher ID

# 5. Run
python bot.py
```

## ⚙️ Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Get from [@BotFather](https://t.me/BotFather) on Telegram |
| `TEACHER_ID` | ✅ | Get from [@userinfobot](https://t.me/userinfobot) |
| `CENTRE_NAME` | ❌ | Your learning centre name (default: "SAT ALFA") |

## 🌐 Free Deployment

### Render (Recommended)
1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New** → **Background Worker**
3. Connect your GitHub repo
4. Set environment variables (`BOT_TOKEN`, `TEACHER_ID`, `CENTRE_NAME`)
5. Deploy! ✅

### Railway
1. Go to [railway.app](https://railway.app) → **New Project**
2. Connect your GitHub repo
3. Add environment variables in the dashboard
4. Deploy! ✅

## 📖 How It Works

```
Student                    Bot                     Teacher
  │                         │                        │
  ├─ Tap "Ask a Question" ─►│                        │
  ├─ Send text ────────────►│ (collecting...)        │
  ├─ Send photo ───────────►│                        │
  ├─ Tap "Send Question" ──►│── Question #1 ────────►│
  │                         │   [Reply] [Done]       │
  │                         │◄── Teacher taps Reply ──┤
  │                         │◄── Types answer ────────┤
  │◄── "Reply to #1: ..." ──│                        │
  │                         │── "Reply sent! ✅" ────►│
```

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes
4. Push and open a PR

## 📄 License

MIT — use freely for your own learning centre!
