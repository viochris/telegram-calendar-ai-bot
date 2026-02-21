# 📅 NovaCal AI: Stateful Google Calendar Assistant (Telegram Bot Edition)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?logo=telegram&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-Agent-blueviolet?logo=langchain&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini%202.5%20Flash-8E75B2?logo=google&logoColor=white)
![Google Calendar](https://img.shields.io/badge/Google%20Calendar-API-4285F4?logo=googlecalendar&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-005C84?logo=mysql&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active-success)

> 🛑 **CRITICAL NOTICE: PLEASE READ UNTIL THE END!**
> Before cloning or deploying this repository, **you MUST read the "Limitations & Disclaimers" section at the bottom of this page.** There are significant architectural trade-offs, high API quota consumption risks, and important developer recommendations regarding this SQL-backed memory version that you need to be aware of.

## 📌 Overview
**NovaCal AI** is an enterprise-grade, highly capable Virtual Assistant built for seamless Google Calendar management directly from Telegram.

Powered by a **LangChain Tool-Calling Agent** and **Google Gemini 2.5 Flash**, this upgraded bot operates on a **Stateful (Conversational Memory)** architecture. By utilizing an SQL-backed memory buffer (MySQL/SQLite), it securely retains session context for natural, multi-turn conversations. It features custom-built scheduling tools (The Sniper & The Fetcher) to securely Create, Read, Update, and Delete (CRUD) your calendar events without the need to repeat prior instructions.

> **🌐 EXPLORE OTHER VERSIONS OF NOVACAL AI:**
> * **[Streamlit Dashboard Edition](https://github.com/viochris/NovaCal-AI-Streamlit.git):** If you are looking for the Visual Web UI version of NovaCal AI.
> * **[Stateless Telegram Edition (No Memory)](https://github.com/viochris/NovaCal-AI-Telegram.git):** If you are looking for the ultra-fast, zero-memory version built purely for One-Shot execution.

## ⚠️ IMPORTANT: Why This Bot Is Locked To A Single User?
> This bot is authenticated using your personal Google Calendar credentials. If it were open to the public, anyone on Telegram could read your private schedules, add fake events, or delete your important meetings!
>
> To prevent this massive security risk, the bot is strictly locked to YOU (the developer). By matching the user's ID with the `TELEGRAM_DEVELOPER_CHAT_ID` stored in your environment variables, the system ensures that only your specific Telegram account can give commands or read your Google Calendar. 
>
> If any stranger attempts to chat with the bot, it will instantly block them and send an intrusion alert directly to your DM.

## ✨ Key Features

### 🧠 Tool-Calling Agent Architecture
Using `create_tool_calling_agent`, the system navigates a strict Standard Operating Procedure (SOP):
1.  **Analyze Intent:** Understands complex time-based requests relative to the current system time.
2.  **Execute Tools:** Uses custom-built, highly optimized tools like `get_id_of_schedules` (The Sniper) and `get_all_schedules` to reliably fetch data.
3.  **Self-Correction (Swap Method):** If an event update fails, the Agent seamlessly falls back to creating a new event and deleting the old one.

### 💾 Conversational Memory Engine (Stateful)
Equipped with `SQLChatMessageHistory` and `RunnableWithMessageHistory`, NovaCal remembers your ongoing conversation. You can give instructions piece by piece (e.g., "Schedule a meeting tomorrow" -> *Bot asks what time* -> "At 4 PM") allowing for dynamic follow-ups and complex scheduling adjustments.

### 🛡️ Private Security Bouncer
The bot is hard-locked to a specific `TELEGRAM_DEVELOPER_CHAT_ID`. Any unauthorized attempts to interact with the bot are immediately blocked, logged, and silently reported to the developer's DM.

### ☁️ Cloud Deployment Ready (Railway)
Features a dynamic credential generator that automatically builds physical `credentials.json` and `token.json` files on the server directly from cloud environment variables upon startup. The database architecture dynamically adapts: using MySQL in production (Railway) or falling back to local SQLite for development.

## 🛠️ Tech Stack
* **LLM:** Google Gemini 2.5 Flash (via `ChatGoogleGenerativeAI`).
* **Bot Framework:** `python-telegram-bot`
* **Orchestration:** LangChain (Tool-Calling Agent).
* **Memory Backend:** SQLAlchemy, PyMySQL (for MySQL Railway), SQLite (Fallback).
* **Calendar Integration:** Google Calendar API (`google-api-python-client` & `CalendarToolkit`).

## ⚠️ Limitations & Disclaimers
### 1. Database Requirement
For cloud deployment, an active SQL database (like MySQL on Railway) is recommended via the `DATABASE_URL` variable. If left blank, it defaults to a local SQLite file which may be wiped on ephemeral cloud instances upon restart.
### 2. Timezone Hardcoding
The time boundary extraction in the custom fetcher tools currently uses a fixed `+07:00` (WIB/Jakarta) timezone offset for daily queries.
### 3. Native Tool Bypassing
Native LangChain search tools (`CalendarSearchEvents`) are intentionally disabled/banned in the system prompt due to instability, replaced entirely by custom-built extraction functions for maximum reliability.
### 4. Occasional Contextual Amnesia (Over-Caution)
While equipped with an SQL-backed conversational memory, generative models like Gemini 2.5 Flash can occasionally struggle with multi-turn context correlation. Even with explicit system instructions to check the chat history first, the AI might become overly cautious and ask to re-verify a detail (such as the event time or title) that you provided earlier. If this looping behavior occurs, you can explicitly command it to *"just create it with the provided details"*, or simply bypass the loop by providing all event parameters in a single comprehensive message (treating it temporarily like a zero-memory bot).
### 5. High Token & API Quota Consumption
Because the bot is stateful, every new message you send also re-transmits the entire conversational history back to the LLM. As the chat grows longer, this consumes a massive amount of tokens per request, which can rapidly exhaust your Google Gemini API daily free tier quota.
### 6. Contextual Drift & Accuracy Degradation
As the SQL memory buffer accumulates days or weeks of conversation, the AI can become "distracted" by older, irrelevant scheduling details. This overload of past context can lead to AI hallucinations, confusion, or executing calendar tools with incorrect parameters.

---

> 💡 **DEVELOPER'S VERDICT & RECOMMENDATION**
> 
> **For Educational Purposes:** This repository serves as an excellent **learning resource** for developers looking to understand how to implement persistent, **SQL-backed conversational memory** in LangChain. It demonstrates how to maintain stateful context across sessions using a robust database architecture, as opposed to ephemeral in-memory buffers (like `ConversationBufferMemory`) or temporary local files.
> 
> **For Daily Practical Use:** Despite the theoretical convenience of multi-turn memory, the most reliable and error-free way to interact with an AI scheduling agent is to provide all parameters upfront. Because of the memory limitations (high token usage and contextual drift) mentioned above, **it is highly recommended to use the [NovaCal AI (Stateless Telegram)](https://github.com/viochris/NovaCal-AI-Telegram.git) version for actual daily use.** The stateless edition is lightning-fast, highly token-efficient, and completely immune to memory-based hallucinations.

## 📦 Installation & Deployment

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/viochris/telegram-calendar-ai-bot.git
    cd telegram-calendar-ai-bot
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Local Environment Setup (`.env`)**
    Create a `.env` file for local testing:
    ```env
    TELEGRAM_TOKEN_Nova_cal_memory=your_telegram_bot_token
    TELEGRAM_CHAT_ID=your_personal_telegram_id
    GOOGLE_API_KEY=your_gemini_api_key
    # DATABASE_URL=mysql+pymysql://user:pass@host:port/db # (Optional for local, defaults to SQLite)
    ```

4.  **Run Locally**
    ```bash
    python NovaCal-Memory-AI-Telegram.py
    ```

### 🖥️ Expected Terminal Output
You will see the bot initialize the LangChain Agent, establish the SQL connection, and start polling in real-time:
```text
2026-02-21 08:30:15,123 - root - INFO - 🚀 NovaCal AI Telegram Bot is currently online and listening...
2026-02-21 08:35:10,001 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot1234...:98.../getUpdates "HTTP/1.1 200 OK"
2026-02-21 08:40:45,432 - root - WARNING - 🚨 INTRUSION ATTEMPT: Unauthorized access blocked from User ID: 9876...
```

### 🚀 Cloud Deployment (Railway)
This script is designed to be **Always On** via continuous polling. We highly recommend **Railway (PaaS)** for seamless GitHub integration, Docker deployment, and attached MySQL databases.

**Strict Instructions for Railway Deployment:**  
Do **NOT** upload your physical `credentials.json` or `token.json` files to the cloud. Instead, add these directly into your Railway Variables:
* `GOOGLE_CALENDAR_CREDENTIALS`: Paste the raw JSON content of your `credentials.json`.
* `GOOGLE_CALENDAR_TOKEN`: Paste the raw JSON content of your `token.json`.
* `TELEGRAM_TOKEN_Nova_cal_memory`: Your bot token.
* `TELEGRAM_CHAT_ID`: Your exact developer chat ID.
* `GOOGLE_API_KEY`: Your Gemini API Key.
* `DATABASE_URL`: Your Railway MySQL connection string (Ensure you add `+pymysql` after `mysql`, e.g., `mysql+pymysql://...`).

## 🚀 Usage Guide
Once the bot is running, start a chat on Telegram:
* `/start` - Initializes the bot and shows the welcome guidelines.
* `/info` - Displays technical specifications and architecture details.
* `/howtouse` - Provides the full CRUD operation cheat sheet.
* **Natural Multi-Turn Chat:** Talk directly to perform actions piece by piece.
  * *You:* "Schedule a meeting for tomorrow."
  * *Bot:* "Sure, what time and what is the title?"
  * *You:* "Call it Team Sync, from 2 PM to 3 PM."

---

**Authors:** Silvio Christian, Joe
*"Automate your schedule. Experience intelligent time management."*
