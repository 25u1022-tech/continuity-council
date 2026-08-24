"""ADK Smoke Test — Verifies Agent Development Kit (google-adk) integration.

Tests:
  - ADK Agent initialization
  - ADK FunctionTool wrapping an async Python function
  - ADK InMemorySessionService for session management
  - ADK Runner message dispatch and tool call event loop
"""
import asyncio
import os
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

# Search for .env in backend/.env or parent .env
for env_path in (
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(".env"),
):
    if env_path.exists():
        load_dotenv(env_path)
        break

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types


# 1. Define async weather tool
async def get_weather(city: str) -> str:
    """Get the current weather forecast for a given city."""
    return f"Weather in {city} is sunny, 72F."


async def run_smoke_test():
    print("=" * 60)
    print("ADK SMOKE TEST: Running Agent Development Kit Verification")
    print("=" * 60)

    # 2. Wrap tool in ADK FunctionTool
    weather_tool = FunctionTool(get_weather)

    # 3. Create ADK Agent
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    agent = Agent(
        name="smoke_test_agent",
        model=model_name,
        instruction="You are a helpful weather assistant. Use the provided tool to get the weather.",
        tools=[weather_tool],
    )
    print(f"[1] Agent created: {agent.name} (model: {model_name})")

    # 4. Initialize Session Service & Runner
    session_service = InMemorySessionService()
    app_name = "smoke_test_app"
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
    )
    print(f"[2] Runner initialized with {session_service.__class__.__name__}")

    # 5. Create session
    user_id = "smoke_test_user"
    session_id = "smoke_test_session_001"
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    print(f"[3] Session created: id={session.id}, user={user_id}")

    # 6. Dispatch user query
    user_query = "What is the weather in Tokyo?"
    print(f"[4] Sending user query: '{user_query}'")
    print("-" * 60)

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=user_query)],
    )

    final_text_response = ""
    tool_calls_detected = []
    tool_responses_detected = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    fc = part.function_call
                    tool_calls_detected.append((fc.name, fc.args))
                    print(f"--> [TOOL CALL] {fc.name}(args={dict(fc.args or {})})")
                if part.function_response:
                    fr = part.function_response
                    tool_responses_detected.append((fr.name, fr.response))
                    print(f"<-- [TOOL RESPONSE] {fr.name} -> {fr.response}")
                if part.text:
                    final_text_response += part.text

    print("-" * 60)
    print(f"[FINAL AGENT RESPONSE]:\n{final_text_response.strip()}")
    print("=" * 60)

    assert len(tool_calls_detected) > 0, "Expected at least 1 tool call"
    assert tool_calls_detected[0][0] == "get_weather", "Expected tool call to get_weather"
    assert "Tokyo" in str(tool_calls_detected[0][1]), "Expected Tokyo in tool arguments"
    assert len(final_text_response) > 0, "Expected non-empty final response text"
    print("ADK SMOKE TEST: PASSED SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
