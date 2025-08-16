import gradio as gr
import json
import os
import requests
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from theme import Seafoam
from agents import Agent, Runner, trace, Tool, function_tool

name= "Anjali Nair"
summary = ""
linkedin = ""

load_dotenv(override=True)

def read_pdf(file_path: str) -> str:
    """Tool to read and extract text from a PDF file"""
    try:
        if os.path.exists(file_path):
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return f"PDF content extracted successfully from {file_path}:\n\n{text}"
        else:
            return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading PDF {file_path}: {str(e)}"

def read_summary_file(file_path: str) -> str:
    """Tool to read and extract text from a summary file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                return f"Summary file content extracted successfully from {file_path}:\n\n{text}"
        else:
            return f"File not found: {file_path}"
    except Exception as e:
        return f"Error reading summary file {file_path}: {str(e)}"

def push(text):
    """Send push notification via Pushover"""
    try:
        token = os.getenv("PUSHOVER_APP_TOKEN")
        user_key = os.getenv("PUSHOVER_USER_KEY")
        
        if token and user_key:
            requests.post(
                "https://api.pushover.net/1/messages.json",
                data={"token": token, "user": user_key, "message": text}
            )
            print(f"Push notification sent: {text}")
        else:
            print("Pushover credentials not configured")
    except Exception as e:
        print(f"Push notification failed: {e}")

@function_tool       
def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided") -> dict:
    """Record user contact details"""
    push(f"User details: {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

@function_tool
def record_unknown_question(question: str) -> dict:
    """Record questions that couldn't be answered"""
    push(f"Unknown question: {question}")
    return {"recorded": "ok"}

summary = read_summary_file("me/summary.txt")
linkedin = read_pdf("me/linkedin.pdf")

# Create the agent with tools
career_agent = Agent(
    name="Career Agent", 
    instructions=f"""You are acting as {name}. You are answering questions on {name}'s website, \
        particularly questions related to {name}'s career, background, skills and experience. \
        Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
        You are given a summary of {name}'s background and LinkedIn profile which you can use to answer questions. \
        Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
        If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
        If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        system_message += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
        system_message += f"With this context, please chat with the user, always staying in character as {name}.""",
    model="gpt-4o-mini",
    tools=[record_user_details, record_unknown_question]
)

async def process_user_message(message: str, chat_history: list[dict]) -> str:
    with trace("Resume query"):
        # Build a comprehensive prompt that includes chat history
        full_prompt = "Chat History ="
        for msg in chat_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        
        full_prompt += f"\nCurrent User Message: {message}\n\nPlease respond to the current message while considering the conversation history above."
        
        result = await Runner.run(career_agent, full_prompt)
        print(result)
        return str(result.final_output)

seafoam = Seafoam()
# Create Gradio interface
with gr.Blocks(theme=seafoam, title="AI Anjali - Personal Assistant") as demo:
    
    gr.Markdown("""
    # <span class="header-title">🤖 AI Anjali - Personal AI Assistant</span>
    
    Hello! I'm Anjali's AI assistant. I can help you with information about Anjali, 
    answer any questions regarding Anjali's resume, career experience, and professional background. 
    Feel free to ask me anything about Anjali's career journey!
    
    ---
    """)
    
    chatbot = gr.Chatbot(
        show_label=False, 
        container=True, 
        type="messages",
        avatar_images=["avatar/user.png", "avatar/anjali.jpg"]
    )
    
    def respond(message, chat_history):
        if not message.strip():
            return "", chat_history
        
        # Add user message immediately and yield to show it
        chat_history.append({"role": "user", "content": message})
        yield "", chat_history
        
        # Get AI response using your linkedInAgent
        bot_message = asyncio.run(process_user_message(message, chat_history))
        
        # Update with AI response and yield again
        chat_history[-1] = {"role": "user", "content": message}
        chat_history.append({"role": "assistant", "content": bot_message})
        yield "", chat_history
    
    with gr.Row():
        msg = gr.Textbox(
            placeholder="Ask me anything about Anjali or any other topic!",
            lines=1,
            max_lines=1,
            show_label=False,
            scale=4,
            container=False
        )
        submit_btn = gr.Button("Send", variant="primary", scale=1)
    
    with gr.Row():
        clear = gr.Button("🗑️ Clear Chat", variant="secondary")
    
    # Event handlers
    msg.submit(respond, [msg, chatbot], [msg, chatbot], show_progress=True)
    submit_btn.click(respond, [msg, chatbot], [msg, chatbot], show_progress=True)
    
    clear.click(lambda: None, None, chatbot, queue=False)
    
    gr.Markdown("""
    ---
    **Note**: This assistant can record user interactions and track questions for continuous improvement.
    """)

# Launch the app
if __name__ == "__main__":
    demo.launch(show_error=True)
