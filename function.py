from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.tools import tool

# ==========================================
# AI TOOL: EVENT ID SEARCHER (THE SNIPER)
# ==========================================
@tool
def get_id_of_schedules(keyword: str) -> str:
    """
    USE THIS TOOL TO FIND THE 'EVENT_ID' BEFORE DELETING OR EDITING AN EVENT. 
    Provide a specific keyword or the name of the event (e.g., 'Meeting' or 'Dentist').
    It searches the primary calendar and returns a list of matching events with their dates, times, and unique IDs.
    """
    try:
        # 1. Authenticate with the Google Calendar API using the predefined scopes.
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/calendar'])
        service = build('calendar', 'v3', credentials=creds)

        # 2. Execute a free-text search query ('q') against the primary calendar
        result = service.events().list(
            calendarId="primary",
            q=keyword,          # The search keyword provided by the AI
            maxResults=10,      # Limit the results to prevent token overflow
            singleEvents=True,  # Expand recurring events into single instances
            orderBy='startTime'
        ).execute()

        # 3. Extract the array of events from the API payload
        events = result.get("items", [])
        
        # 4. Handle the edge case where no events match the search query
        if not events:
            return f"No events found matching the keyword: '{keyword}'."

        # 5. Format the output string so the LLM can easily read the Date, Title, Time, and ID
        response = f"Matching Events Found for '{keyword}':\n"
        
        for e in events:
            title = e.get('summary', 'Untitled Event')
            event_id = e.get('id', 'NO_ID_FOUND')
            
            # Extract raw date/time strings from the API payload
            start_raw = e['start'].get('dateTime', e['start'].get('date'))
            end_raw = e['end'].get('dateTime', e['end'].get('date'))

            # Extract just the 'YYYY-MM-DD' portion for AI context
            event_date = start_raw[:10]

            # Determine if the event is time-bound or an all-day occurrence
            if "T" in start_raw:
                start_time = start_raw[11:16] # Extract HH:MM
                end_time = end_raw[11:16]
                time_str = f"{start_time} - {end_time}"
            else:
                time_str = "All-day"

            # Append the fully formatted event entry (Date, Title, Time, and ID in one single line)
            response += f"- [{event_date}] '{title}' ({time_str}) | EVENT_ID: {event_id}\n"
            
        return response

    except Exception as e:
        # 6. Return a graceful error message back to the AI agent if the API call fails
        return f"Error executing search tool: {str(e)}"

# ==========================================
# AI TOOL: DATE RANGE SCHEDULE FETCHER
# ==========================================
@tool
def get_all_schedules(start_date: str, end_date: str) -> str:
    """
    USE THIS TOOL TO RETRIEVE ALL SCHEDULED EVENTS AND HOLIDAYS WITHIN A SPECIFIC DATE RANGE.
    The 'start_date' and 'end_date' inputs MUST be strictly in 'YYYY-MM-DD' format.
    If the user asks for a single day's schedule (e.g., "today"), provide the exact same date for both inputs.
    """
    try:
        # 1. Authenticate with the Google Calendar API using the predefined scopes.
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/calendar'])
        service = build('calendar', 'v3', credentials=creds)
        
        # 2. Format the time boundaries (Appending +07:00 for WIB/Jakarta Timezone)
        timeMin = f"{start_date}T00:00:00+07:00"
        timeMax = f"{end_date}T23:59:59+07:00"

        # 3. Define the list of target calendars (Primary user calendar & Indonesian Holidays)
        target_calendars = ['primary', 'id.indonesian#holiday@group.v.calendar.google.com']
        all_events = []

        # 4. Iterate through each calendar and aggregate the matching events
        for calendar_id in target_calendars:
            try: 
                result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=timeMin,
                    timeMax=timeMax,
                    maxResults=50,      # Increased limit to accommodate multi-day ranges
                    singleEvents=True,  # Expand recurring events into single instances
                    orderBy='startTime'
                ).execute()
                all_events.extend(result.get("items", []))
            except:
                # Silently skip if a specific calendar is inaccessible or fails
                continue

        # 5. Handle the edge case where no events are found in the given timeframe
        if not all_events:
            return f"No events scheduled from {start_date} to {end_date}."

        # 6. Format the aggregated events into a clean, readable string for both UI and AI context
        response = f"Schedule from {start_date} to {end_date}:\n"
        
        for e in all_events:
            title = e.get('summary', 'Untitled Event')
            
            # Extract raw date/time strings from the API payload
            start_raw = e['start'].get('dateTime', e['start'].get('date'))
            end_raw = e['end'].get('dateTime', e['end'].get('date'))

            # Extract just the 'YYYY-MM-DD' portion for clear visual grouping
            event_date = start_raw[:10]

            # Determine if the event is time-bound or an all-day occurrence
            if "T" in start_raw:
                start_time = start_raw[11:16] # Extract HH:MM
                end_time = end_raw[11:16]
                time_str = f"{start_time} - {end_time}"
            else:
                time_str = "All-day"

            # Append the formatted event entry (Notice: NO EVENT_ID here to keep UI clean)
            response += f"- [{event_date}] {title} ({time_str})\n"
            
        return response

    except Exception as e:
        # 7. Gracefully return the error back to the AI agent
        return f"Error executing schedule fetcher: {str(e)}"