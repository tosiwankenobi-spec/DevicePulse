#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "DevicePulse device-health app. Verify all REAL (non-simulated) functionality works end-to-end, especially the newly added AI Health Coach (daily card + Pro chat with memory). Simulated scan/clean numbers are by design due to mobile OS sandboxing."

backend:
  - task: "AI Health Coach - daily card"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/coach/daily generates a personalized daily coaching card via Claude Sonnet 5, cached per user per day in coach_daily collection. Auth required (Bearer). Falls back gracefully if LLM unavailable."
        -working: true
        -agent: "testing"
        -comment: "PASS with real Claude Sonnet 5. Daily card returns valid fields, per-user per-day cache confirmed. 16/16 coach tests passed (iteration_6.json)."
  - task: "AI Health Coach - chat with memory"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/coach/chat persists user+assistant messages in coach_messages, builds memory context from cleanup history + recent conversation, uses Claude Sonnet 5. Rate-limited per user (10/min). GET /api/coach/history returns messages, DELETE /api/coach/history clears. All IDOR-safe (identity from token)."
        -working: true
        -agent: "testing"
        -comment: "PASS. Contextual replies with real LLM, memory continuity verified (2nd reply references prior context), history GET ordered, DELETE clears, 429 after 10 rapid calls, 401 without token on all coach endpoints. IDOR-safe, no _id leakage."
  - task: "Core endpoints regression (scan/clean/history/streak/forecast/ai recommendations/auth)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: true
        -agent: "main"
        -comment: "Existing endpoints previously working. Re-verify no regression after Coach additions."

frontend:
  - task: "AI Health Coach tab (daily card + chat UI)"
    implemented: true
    working: "NA"
    file: "frontend/app/(tabs)/coach.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "New Coach tab with daily coaching card (free), quick-prompt chips, chat bubbles with memory. Chat Pro-gated on native (isSubscribed) but unlocked on web for preview/testing. Not yet tested."

metadata:
  created_by: "main_agent"
  version: "1.1"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus:
    - "AI Health Coach - daily card"
    - "AI Health Coach - chat with memory"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: "Added AI Health Coach (backend + Coach tab). Please test backend Coach endpoints end-to-end using a seeded Mongo session token (see test_credentials.md for how to insert user + session). Verify: (1) GET /api/coach/daily returns a valid card with real LLM content, (2) POST /api/coach/chat returns a contextual reply and persists messages, (3) memory works (send 2 messages, second reply should reflect awareness), (4) GET /api/coach/history returns both turns, (5) DELETE /api/coach/history clears them, (6) rate limit returns 429 after 10 rapid calls, (7) auth required (401 without token). Also quickly re-verify core endpoints (scan, clean, ai/recommendations) still work. Backend only."