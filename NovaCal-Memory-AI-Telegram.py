import os
import json
import logging
import datetime

# --- Third-Party Libraries ---
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- LangChain & Generative AI Libraries ---
from langchain_google_community import CalendarToolkit
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# --- Custom Application Modules ---
from function import get_id_of_schedules, get_all_schedules

# ==========================================
# ENVIRONMENT VARIABLES & CONFIGURATION
# ==========================================
# Load sensitive credentials from the local .env file securely
load_dotenv()

# Fetch configuration keys from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_Nova_cal_memory")
TELEGRAM_DEVELOPER_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Establish the Database Connection URL.
# PRIMARY: Attempts to fetch the production database URL (e.g., MySQL on Railway) from the environment.
# FALLBACK: If no environment variable is found (e.g., running locally), it safely defaults to a local SQLite database.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///novacal_memory.db")

# ==========================================
# DYNAMIC CREDENTIAL GENERATOR FOR CLOUD DEPLOYMENT (RAILWAY)
# ==========================================
# LangChain's CalendarToolkit strictly requires physical 'credentials.json' and 'token.json' files to function.
# When running locally, these files already exist in your folder, so this code will safely skip execution.
# However, during cloud deployment (like on Railway), these files are typically ignored via .gitignore for security.
# This script dynamically generates the required physical files on the server upon startup by pulling the raw JSON data from Railway's Environment Variables.

# 1. Generate 'credentials.json' on the server if it doesn't exist
creds_env = os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
if creds_env and not os.path.exists("credentials.json"):
    with open("credentials.json", "w") as f:
        f.write(creds_env)

# 2. Generate 'token.json' on the server if it doesn't exist
token_env = os.getenv("GOOGLE_CALENDAR_TOKEN")
if token_env and not os.path.exists("token.json"):
    with open("token.json", "w") as f:
        f.write(token_env)

# ==========================================
# SYSTEM LOGGING SETUP
# ==========================================
# Configure basic logging to monitor bot activity, track routing, and capture errors in the terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# CONVERSATIONAL MEMORY MANAGER (SLIDING WINDOW)
# ==========================================
class WindowedSQLChatMessageHistory(SQLChatMessageHistory):
    """
    A custom wrapper for LangChain's SQLChatMessageHistory that implements a 'Sliding Window' memory mechanism.
    
    Why this is critical for production:
    1. Token Efficiency: Prevents the LLM from processing the entire historical chat log, saving massive API quota.
    2. Contextual Focus: Mitigates 'Contextual Drift' (AI hallucinations) by forcing the AI to only focus on the 
       most recent interactions, ensuring schedule parameters remain highly accurate.
       
    By overriding the `messages` property, the SQL database continues to store 100% of the conversation history 
    securely for auditing, but the AI Agent is strictly fed only the last N messages (e.g., the last 5 chat bubbles).
    """
    @property
    def messages(self):
        # Fetches all records from the SQL database, but slicing limits the output 
        # to the last 5 messages (conversational turns) sent to the LLM agent.
        return super().messages[-5:]

def get_session_history(session_id: str):
    """
    Retrieves or initializes the SQL-backed chat history for a specific user session.
    
    This function acts as the bridge between the AI agent and the database. 
    It ensures that the bot's memory remains stateful by fetching the persistent 
    conversational context (from MySQL on Railway or local SQLite) based on 
    the unique Telegram User ID.
    
    Args:
        session_id (str): The unique identifier for the user (Telegram User ID).
        
    Returns:
        WindowedSQLChatMessageHistory: The sliding-window database connection instance managing the chat array.
    """
    # 1. Bind the specific user's session ID to the active database connection.
    # IMPORTANT: We initialize our custom 'Windowed' class here instead of the default 
    # LangChain class to activate the Token-Saving Sliding Window feature!
    return WindowedSQLChatMessageHistory(
        session_id=session_id,
        connection=DATABASE_URL
    )

# ==========================================
# BOT COMMAND HANDLERS
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the standard Telegram /start command.

    This asynchronous function serves as the primary entry point when a user first 
    interacts with the bot. It welcomes the user and introduces the stateful NovaCal AI.

    Args:
        update (telegram.Update): The payload containing incoming message details.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context object to interact with the bot API.
    """

    # 1. Safely extract the unique ID of the chat session to route the response
    chat_id = update.effective_chat.id

    # 2. Construct the welcoming interface text for a Context-Aware Bot
    welcome_text = (
        "🤖 **Hello! I am NovaCal AI.**\n"
        "I am your highly capable personal calendar assistant. To ensure smooth scheduling, please read my operational guidelines below:\n\n"
        
        "🧠 **1. Conversational Memory (Stateful)**\n"
        "I am equipped with short-term memory! We can converse naturally step-by-step. "
        "*(e.g., You can say 'Schedule a meeting tomorrow', and if I ask 'What time?', you can just reply 'at 4 PM'.)*\n\n"
        
        "⏱️ **2. Provide Details & Follow-ups**\n"
        "While I can ask follow-up questions if details are missing, providing complete info upfront is always faster. If you don't specify an end time, "
        "I might set a **1-hour default**. *(Don't worry, we can always update it!)*\n\n"
        
        "📋 **3. Operation Guide (CRUD)**\n"
        "• ➕ **CREATE:** Tell me the *Event Title, When (Date or Day), Start Time, and End Time*.\n"
        "  *(e.g., 'Book a Team Sync tomorrow from 2 PM to 3:30 PM')*\n"
        "• 📖 **READ:** Tell me the specific *Date or Timeframe* you want to check.\n"
        "  *(e.g., 'What is my schedule for next Monday?')*\n"
        "• ✏️ **UPDATE:** Tell me the *Exact Event Name* and the *New Details*.\n"
        "  *(e.g., 'Change my Dentist appointment tomorrow to 10 AM')*\n"
        "• ❌ **DELETE:** Tell me the *Exact Event Name* you want to remove.\n"
        "  *(e.g., 'Cancel my Team Sync meeting')*\n\n"
        
        "Send me a command whenever you're ready! 🚀"
    )

    # 3. Transmit the welcome message back to the user asynchronously
    await context.bot.send_message(
        chat_id=chat_id, 
        text=welcome_text,
        parse_mode="Markdown"
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the standard Telegram /info command.

    This asynchronous function serves as the "About" page for the bot, 
    displaying its technical specifications, upgraded stateful architecture, 
    and developer credits to the user.
    """
    # 1. Safely extract the unique ID of the chat session to route the response
    chat_id = update.effective_chat.id
    
    # 2. Construct the technical specifications and system architecture payload
    info_text = (
        "🤖 **ABOUT NOVACAL AI**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "NovaCal AI is a streamlined Virtual Assistant built for seamless Google Calendar management.\n\n"
        
        "🛠️ **TECHNICAL SPECIFICATIONS:**\n"
        "• **AI Model:** Google Gemini 2.5 Flash\n"
        "• **Agent Framework:** LangChain (Tool-Calling Agent)\n"
        "• **Integrations:** Google Calendar API v3 (Custom Search & CRUD Tools)\n"
        "• **Architecture:** Stateful (SQL-Backed Conversational Memory)\n"
        "• **Security:** Private Access Control & Activity Logging\n"
        "• **Developers:** Silvio Christian, Joe\n\n"
        
        "⚡ **THE STATEFUL ADVANTAGE:**\n"
        "Powered by a robust SQL database, NovaCal AI securely retains session context for natural, multi-turn conversations. This allows for dynamic follow-ups and complex scheduling adjustments without the need to repeat prior instructions.\n\n"
        
        "Type /howtouse to read the operational guide!"
    )
    
    # 3. Transmit the formatted information text back to the user asynchronously
    await context.bot.send_message(
        chat_id=chat_id, 
        text=info_text, 
        parse_mode="Markdown"
    )

async def howtouse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the standard Telegram /howtouse command.

    This asynchronous function serves as the user manual for the bot.
    It delivers a comprehensive guide on the operational rules (Stateful memory)
    and provides specific examples for executing CRUD operations on the calendar.

    Args:
        update (telegram.Update): The payload containing incoming message details.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context object for API interactions.
    """
    # 1. Safely extract the unique ID of the chat session to route the response
    chat_id = update.effective_chat.id
    
    # 2. Construct the comprehensive operational guide and cheat sheet payload
    howtouse_text = (
        "📖 **NOVACAL AI - USER GUIDE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome to your personal calendar command center. Please read the core rules below to ensure flawless execution.\n\n"
        
        "🧠 **1. CONVERSATIONAL MEMORY**\n"
        "I remember our ongoing conversation! You can give me instructions piece by piece or all at once.\n"
        "✅ *Multi-turn Example:*\n"
        "You: 'Schedule a meeting for tomorrow.'\n"
        "Me: 'Sure, what time and what is the title?'\n"
        "You: 'Call it Team Sync, from 2 PM to 3 PM.'\n\n"
        
        "⏱️ **2. PARAMETER SAFETY & FOLLOW-UPS**\n"
        "Always try to define the duration! If you don't specify an end time, I will either **ask you a follow-up question** to confirm, or automatically assume a **1-hour duration** by default. *(Don't worry, we can always update it!)*\n\n"
        
        "⚙️ **3. COMMAND CHEAT SHEET (CRUD)**\n"
        "To perform actions, just talk to me naturally using these formats:\n\n"
        
        "➕ **CREATE (Add an event)**\n"
        "• *Required:* Title, When (Date/Day), Start Time, End Time.\n"
        "• *Prompt:* 'Book a Team Sync tomorrow from 2:00 PM to 3:30 PM.'\n\n"
        
        "📖 **READ (Check your schedule)**\n"
        "• *Required:* Date or Timeframe.\n"
        "• *Prompt:* 'What is my schedule for next Monday?' or 'Do I have any meetings today?'\n\n"
        
        "✏️ **UPDATE (Edit an event)**\n"
        "• *Required:* Exact Event Name, Date, and the New Details.\n"
        "• *Prompt:* 'Change my Dentist appointment tomorrow to start at 10 AM instead.'\n\n"
        
        "❌ **DELETE (Remove an event)**\n"
        "• *Required:* Exact Event Name and Date.\n"
        "• *Prompt:* 'Cancel my Team Sync meeting scheduled for tomorrow.'\n\n"
        
        "Ready? Send me your first command! 🚀"
    )
    
    # 3. Transmit the formatted manual text back to the user asynchronously
    await context.bot.send_message(
        chat_id=chat_id, 
        text=howtouse_text, 
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processes standard text messages sent by the user to the bot.
    
    This handler acts as the core conversational engine. It captures the user's input, 
    forwards it to the Google Gemini LLM for processing, and seamlessly transmits 
    the generated response back to the Telegram chat.
    
    Args:
        update (telegram.Update): The payload containing incoming message details.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context object for API interactions.
    """

    # 1. Extract metadata and user input from the incoming Telegram update
    user_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # --- SECURITY BOUNCER ---
    # Strictly limit access to the designated developer to protect calendar privacy
    if str(user_id) != str(TELEGRAM_DEVELOPER_CHAT_ID):
        # Log the intrusion attempt to the terminal so the developer knows who tried to snoop
        logging.warning(f"🚨 INTRUSION ATTEMPT: Unauthorized access blocked from User ID: {user_id} (Name: {user_name})")

        # 1. Attempt to send a warning to the intruder and kick them out
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="🚨 **Access Denied!** Unauthorized user detected. I am exclusively configured to assist my designated developer.",
                parse_mode="Markdown"
            )
        except Exception as e:
            # Catch errors if the user blocks the bot immediately before receiving the warning
            logging.error(f"Failed to send Access Denied message to intruder (User ID: {user_id}): {e}")

        # 2. Attempt to send a silent security alert to the Developer's DM
        try:
            alert_msg = (
                f"⚠️ **SECURITY ALERT** ⚠️\n\n"
                f"Someone tried to access your Calendar Bot!\n"
                f"👤 **Name:** {user_name}\n"
                f"🆔 **User ID:** `{user_id}`\n"
                f"💬 **They typed:** _{user_text}_"
            )
            await context.bot.send_message(
                chat_id=TELEGRAM_DEVELOPER_CHAT_ID,
                text=alert_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            # Catch errors if the developer's chat ID is invalid or the bot cannot message them
            logging.error(f"Failed to send security alert to Developer: {e}")
            
        # 3. Terminate the function immediately to prevent unauthorized calendar access
        return

    try: 
        # 2. Trigger the 'Typing...' action indicator in the Telegram UI
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

        # 3. Initialize the Google Calendar Toolkit
        toolkit = CalendarToolkit()
        calendar_tools = toolkit.get_tools()

        # Filter out native LangChain search tools (they are buggy/broken for our use case)
        used_tools = [t for t in calendar_tools if "search" not in t.name.lower() and "get" not in t.name.lower()]

        # Inject our custom, highly-optimized tools (The Fetcher & The Sniper)
        tools = used_tools + [get_id_of_schedules, get_all_schedules]

        # Capture the Exact Current System Time for Contextual Accuracy
        current_datetime = datetime.datetime.now().strftime("%A, %d %B %Y %H:%M:%S")
        
        # 4. Construct the Custom Hybrid Tool-Calling Prompt
        # This serves as the core "Brain" of the agent, defining strict Standard Operating Procedures (SOP).
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an elite, highly capable Personal Assistant managing the user's Google Calendar.
            CURRENT SYSTEM TIME: {current_datetime}
            
            CRITICAL RULES:
            1. CALENDAR ID: Whenever a tool requires 'calendar_id', ALWAYS use exactly the string 'primary'.
            2. TIME CONTEXT: Base all date and time calculations strictly on the CURRENT SYSTEM TIME.
            3. LANGUAGE: Always respond naturally in the EXACT SAME language the user typed.
            4. CONVERSATIONAL MEMORY: You have access to the user's previous messages in 'chat_history'. ALWAYS check this history first to find missing details (like event title, date, or time). DO NOT ask the user for information they have already provided in previous messages.
            5. PARAMETER SAFETY:
                - If required parameters are STILL missing after checking chat_history, ask the user for clarification before calling any tool.
                - Never invent dates or times.
                - Do not assume default values unless explicitly provided by the user.
            6. BANNED TOOLS: NEVER use 'CalendarSearchEvents', 'search_events', or 'get_events'. They are broken.
            
            STANDARD OPERATING PROCEDURES (SOP) FOR CALENDAR ACTIONS:
            
            A. CREATING AN EVENT:
            - Use the 'CalendarCreateEvent' tool directly with the details provided.
            
            B. DELETING AN EVENT:
            - Step 1: You MUST FIRST use the 'get_id_of_schedules' tool (search by keyword) or 'get_all_schedules' tool (search by date. ALWAYS provide BOTH 'start_date' and 'end_date' in YYYY-MM-DD) to find the event.
            - Step 2: Extract the 'EVENT_ID' from the tool's response.
            - Step 3: Use the 'CalendarDeleteEvent' tool using that 'EVENT_ID'.
            
            C. EDITING/UPDATING AN EVENT:
            - Step 1: Use 'get_id_of_schedules' or 'get_all_schedules' (ALWAYS provide BOTH 'start_date' and 'end_date' in YYYY-MM-DD) to get the 'EVENT_ID' and the FULL original details.
            - Step 2 (The Priority): Try to use 'CalendarUpdateEvent' using the 'EVENT_ID'. You MUST pass the updated fields AND keep the unchanged fields from Step 1.
            - Step 3 (The Fallback): IF Step 2 fails (due to error or missing data), use the "Swap Method": 
                a. Create a NEW event with 'CalendarCreateEvent'.
                b. Delete the OLD event with 'CalendarDeleteEvent' using the 'EVENT_ID'.
            
            D. READING/DISPLAYING SCHEDULES (e.g., "What is my schedule today?"):
            - Use the 'get_all_schedules' tool.
            - You MUST provide BOTH 'start_date' and 'end_date' in YYYY-MM-DD format (e.g., '{current_datetime[:10]}'). If asking for a single day, use the same date for both.
            - Summarize the results naturally for the user. IMPORTANT: If 'get_all_schedules' returns holidays or all-day events, make sure to mention them clearly to the user.
            
            E. SEARCHING SPECIFIC EVENTS (e.g., "When is my 'Team Sync' meeting?"):
            - Use the 'get_id_of_schedules' tool with the keyword (e.g., "Team Sync").
            """),
            
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 5. Initialize the LLM Engine
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.3
        )

        # 6. Bind the Reasoning Engine (The Brain)
        agent_brain = create_tool_calling_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )

        # 7. Initialize the Base Runtime Executor (The Body)
        agent_executor = AgentExecutor(
            agent=agent_brain,
            tools=tools,
            handle_parsing_errors=True
        )

        # 8. Inject the SQL-Backed Memory Wrapper
        # This dynamically loads the user's past chat history from the database 
        # and seamlessly injects it into the prompt's 'chat_history' placeholder.
        agent_with_memory = RunnableWithMessageHistory(
            agent_executor, 
            get_session_history=get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )

        # 9. Execute the Agent workflow using the User's unique session ID
        response = agent_with_memory.invoke(
            {"input": user_text},
            config={"configurable": {"session_id": str(user_id)}}
        )
        # 10. Safely parse the LLM's output
        if "output" in response and len(response["output"]) > 0:
            final_answer = response.get("output", "Sorry, I am unable to process that scheduling request right now.")

            # Sanitize the output if the LLM returns a complex list structure
            if isinstance(final_answer, list):
                cleaned_text = ""
                for part in final_answer:
                    if isinstance(part, dict) and "text" in part:
                        cleaned_text += part["text"]
                    elif isinstance(part, str):
                        cleaned_text += part
                final_answer = cleaned_text   
        else:
            final_answer = "Sorry, I am unable to process that scheduling request right now."
        
        # 11. Handle Telegram's Message Length Limits
        # Telegram strict limit is 4096. We use 4000 as a safety buffer.
        MAX_LENGTH = 4000
        message_to_send = []

        # Check if the final response exceeds the maximum length constraint
        if len(final_answer) <= MAX_LENGTH:
            message_to_send.append(final_answer)
        else:
            logging.info("⚠️ Message is too long. Splitting into readable chunks...")

            # Split by double newlines to preserve Markdown paragraph structure
            parts = final_answer.split('\n\n')
            current_chunks = ""

            for part in parts:
                # Check if adding the next part exceeds the limit
                if len(current_chunks) + len(part) + 2 < MAX_LENGTH:
                    current_chunks += part + "\n\n"
                else:
                    # If the chunk is full, append to list and start a new one
                    if current_chunks.strip():
                        message_to_send.append(current_chunks)
                    current_chunks = part + "\n\n"

            # Append any remaining text in the buffer
            if current_chunks.strip():
                message_to_send.append(current_chunks)

        # 12. Transmit the formulated chunks back to the user asynchronously
        for i, answer in enumerate(message_to_send):
            await context.bot.send_message(
                chat_id=chat_id,
                text=answer,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        # 13. Prevent silent failures by safely catching, categorizing, and notifying the user
        error_msg = str(e).lower()
        logging.error(f"Failed to generate AI response for User {user_id} ({user_name}): {e}")
        
        # Scenario A: AI Rate Limits or Exhausted Quota (Gemini API)
        if "quota" in error_msg or "429" in error_msg or "exhausted" in error_msg:
            reply_text = "⚠️ **API Limit Reached:** My AI engine is receiving too many requests right now or has reached its daily capacity. Please try again later or tomorrow!"
            
        # Scenario B: Authentication or Billing Issues (Missing/Invalid API Key)
        elif "api_key" in error_msg or "key invalid" in error_msg or "403" in error_msg:
            reply_text = "🛑 **Configuration Error:** My API key seems to be invalid or expired. Please check the system environment settings."
            
        # Scenario C: Google Calendar Access Issues (Token expired or Calendar not found)
        elif "unauthorized" in error_msg or "invalid_grant" in error_msg or "calendar_id" in error_msg:
            reply_text = "📅 **Calendar Sync Error:** I am having trouble accessing your Google Calendar. The authorization token might be expired or the calendar ID is incorrect."
            
        # Scenario D: The Fallback (Catch-all for network drops, timeouts, or unknown bugs)
        else:
            reply_text = "⚠️ **System Error:** My AI engine is currently unreachable or encountering an unexpected issue. Please try again in a moment!"

        # Safely transmit the categorized error message back to the user
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=reply_text, 
                parse_mode="Markdown"
            )
        except Exception as send_error:
            # The absolute last line of defense in case Telegram itself is down
            logging.error(f"CRITICAL: Failed to even send the error message to user! {send_error}")

# ==========================================
# GLOBAL ERROR HANDLING
# ==========================================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for the Telegram bot routing system.
    
    This function acts as the ultimate safety net ("Ambulance"). If any handler 
    encounters an unhandled exception, it logs the error to the terminal and 
    sends a direct emergency message to the developer's Telegram chat.
    
    Args:
        update (telegram.Update): The incoming update that caused the error.
        context (telegram.ext.ContextTypes.DEFAULT_TYPE): The context containing the error object.
    """
    
    # 1. Log the critical error to the system console for debugging
    logging.error(f"Exception while handling an update: {context.error}")

    # 2. Construct the emergency notification payload
    error_message = (
        f"🚨 **SYSTEM ALERT: BOT ENCOUNTERED AN ERROR!** 🚨\n\n"
        f"**Error Details:**\n`{context.error}`"
    )
    
    # 3. Attempt to alert the developer via Telegram DM
    try:
        # Utilize the TELEGRAM_DEVELOPER_CHAT_ID defined in the .env variables
        await context.bot.send_message(
            chat_id=TELEGRAM_DEVELOPER_CHAT_ID, 
            text=error_message, 
            parse_mode="Markdown"
        )
    except Exception as e:
        # Gracefully handle the scenario where the error alert fails to deliver 
        # (e.g., if the developer blocked the bot or the chat ID is invalid)
        logging.error(f"Failed to deliver error alert to Developer: {e}")
        pass

# ==========================================
# MAIN APPLICATION EXECUTOR
# ==========================================
if __name__ == "__main__":
    # 1. Initialize and build the Telegram Bot Application using the secure environment token
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 2. Register Core Command Handlers (/start, /info, /howtouse)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("howtouse", howtouse_command))
    
    # 3. Register the Conversational Message Handler 
    # This captures all regular text prompts intended for the AI while explicitly bypassing commands
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # 4. Register the Global Error Handler (The Ambulance) to safely catch and log unexpected system crashes
    app.add_error_handler(error_handler)

    # 5. Ignite the AI engine and start continuous polling for incoming Telegram updates
    logging.info("🚀 NovaCal AI Telegram Bot is currently online and listening...")
    app.run_polling()