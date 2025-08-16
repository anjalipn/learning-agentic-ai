import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader

# Load environment variables
load_dotenv(override=True)

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

def record_user_details(email, name="Name not provided", notes="not provided"):
    """Record user contact details"""
    push(f"User details: {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    """Record questions that couldn't be answered"""
    push(f"Unknown question: {question}")
    return {"recorded": "ok"}

# Tool definitions for OpenAI function calling
tools = [
    {
        "type": "function",
        "function": {
            "name": "record_user_details",
            "description": "Record user contact details",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "name": {"type": "string", "description": "User's name"},
                    "notes": {"type": "string", "description": "Additional context"}
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_unknown_question",
            "description": "Record questions that couldn't be answered",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The unanswered question"}
                },
                "required": ["question"]
            }
        }
    }
]

class Me:
    """Personal information and document processing"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.openai = OpenAI(api_key=api_key)
        self.name = "Anjali Nair"
        
        # Load LinkedIn content
        self.linkedin = self._load_linkedin()
        
        # Load personal summary
        self.summary = self._load_summary()

    def _load_linkedin(self):
        """Load LinkedIn PDF content"""
        try:
            if os.path.exists("me/linkedin.pdf"):
                reader = PdfReader("me/linkedin.pdf")
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                print("LinkedIn PDF loaded successfully")
                return text
            else:
                print("LinkedIn PDF not found")
                return "LinkedIn profile not available"
        except Exception as e:
            print(f"Error reading LinkedIn PDF: {e}")
            return "LinkedIn profile could not be loaded"

    def _load_summary(self):
        """Load personal summary"""
        try:
            if os.path.exists("me/summary.txt"):
                with open("me/summary.txt", "r", encoding="utf-8") as f:
                    summary = f.read()
                print("Personal summary loaded successfully")
                return summary
            else:
                print("Summary file not found")
                return "Personal summary not available"
        except Exception as e:
            print(f"Error reading summary: {e}")
            return "Personal summary could not be loaded"

    def handle_tool_call(self, tool_calls):
        """Handle OpenAI function calls"""
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name} with args: {arguments}")
            
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            
            results.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tool_call.id
            })
        return results

    def chat(self, message, history):
        """Main chat function"""
        try:
            # Create system message
            system_message = f"""You are {self.name}, a personal AI assistant.

Personal Summary: {self.summary}
LinkedIn Profile: {self.linkedin}

You have access to tools to record user interactions and track unanswered questions.
Always be helpful, professional, and use the available tools when appropriate.
If someone asks for contact information or wants to get in touch, use the record_user_details tool.
If you can't answer a question, use the record_unknown_question tool to track it."""
            
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": system_message}]
            
            # Add conversation history
            for msg in history:
                if msg["role"] in ["user", "assistant"]:
                    messages.append(msg)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Call OpenAI API
            response = self.openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7
            )
            
            # Handle tool calls if any
            if response.choices[0].message.tool_calls:
                tool_results = self.handle_tool_call(response.choices[0].message.tool_calls)
                messages.append(response.choices[0].message)
                messages.extend(tool_results)
                
                # Get final response
                final_response = self.openai.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.7
                )
                return final_response.choices[0].message.content
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            print(f"Error in chat: {e}")
            return f"I'm sorry, I encountered an error: {str(e)}"

# Initialize the assistant
try:
    assistant = Me()
    print("AI Anjali assistant initialized successfully!")
except Exception as e:
    print(f"Failed to initialize assistant: {e}")
    assistant = None

# Create Gradio interface
with gr.Blocks(title="AI Anjali - Personal Assistant", theme=gr.themes.Soft(), css="""
    .chatbot-avatar img {
        width: 40px !important;
        height: 40px !important;
        border-radius: 50% !important;
        object-fit: cover !important;
    }
""") as demo:
    
    gr.Markdown("""
    # 🤖 AI Anjali - Personal AI Assistant
    
    Hello! I'm Anjali's AI assistant. I can help you with information about Anjali, 
    answer any questions regarding Anjali's resume, career experience, and professional background. 
    Feel free to ask me anything about Anjali's career journey!
    
    ---
    """)
    
    if assistant:
        chatbot = gr.Chatbot(
            show_label=False, 
            container=True, 
            type="messages",
            avatar_images=["avatar/user.png", "avatar/anjali.jpg"],  # User avatar, AI avatar
            # Or use image files: avatar_images=["path/to/user.jpg", "path/to/ai.jpg"]
        )
        
        def respond(message, chat_history):
            if not message.strip():
                return "", chat_history
            
            # Add user message immediately and yield to show it
            chat_history.append({"role": "user", "content": message})
            yield "", chat_history
            
            # Get AI response
            bot_message = assistant.chat(message, chat_history[:-1])
            
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
        
    else:
        gr.Markdown("""
        ## ❌ Initialization Error
        
        The assistant failed to initialize. Please check:
        - Environment variables are properly set
        - Required files exist in the `me/` directory
        - OpenAI API key is valid
        
        Check the console logs for more details.
        """)

# Launch the app
if __name__ == "__main__":
    demo.launch(show_error=True)
