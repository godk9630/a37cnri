# ARK Admin Contact Bot 🤖

A Telegram bot where users send messages and the admin receives them with full button-based controls.

---

## ⚙️ Setup Steps

### 1. Get your Bot Token
- Open Telegram → search `@BotFather`
- Send `/newbot` and follow steps
- Copy the token

### 2. Get your Telegram Admin ID
- Search `@userinfobot` on Telegram
- Send `/start` — it will show your ID

### 3. Set Environment Variables on Render
| Key | Value |
|---|---|
| `BOT_TOKEN` | Your bot token from BotFather |
| `ADMIN_ID` | Your Telegram numeric ID |
| `PORT` | `8080` |

### 4. Deploy on Render
1. Push these files to a GitHub repo
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Add the env vars above
6. Click **Deploy**

---

## 🔘 Admin Button Commands

| Button | Function |
|---|---|
| 📋 All Users | List all users with status |
| 📢 Broadcast | Send message to all users |
| 🚫 Ban User | Ban a user by ID |
| ✅ Unban User | Unban a user by ID |
| 📊 Bot Stats | Total / active / banned count |
| 🔔 Toggle Notify | Turn message forwarding on/off |
| ❓ Help | Show help guide |

---

## 💬 How It Works

- **User** sends any message → forwarded to admin with a **Reply** button
- **Admin** clicks Reply button → types reply → sent back to user
- **Admin** uses `/panel` anytime to open the control panel

---

## 📁 Files
```
ark_contact_bot/
├── bot.py           # Main bot
├── requirements.txt # Dependencies
├── render.yaml      # Render config
└── README.md        # This file
```
