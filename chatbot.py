import streamlit as st
import openai

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales Assistant Chatbot", page_icon="🤖")
openai.api_key = "YOUR_OPENAI_API_KEY"  # Replace with your OpenAI key

# ---------------- INITIAL STATE ----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "username" not in st.session_state:
    st.session_state.username = "Guest"

# ---------------- TITLE ----------------
st.title("🤖 Sales Assistant Chatbot")
st.caption("Ask me anything about sales, revenue predictions, or product insights.")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("🔐 User Info")
    name = st.text_input("Enter your name", value=st.session_state.username)
    if name:
        st.session_state.username = name
        st.success(f"Welcome, {name}!")

# ---------------- CHAT FUNCTION ----------------
def generate_response(messages):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.5,
    )
    return response["choices"][0]["message"]["content"]

# ---------------- CHAT HISTORY DISPLAY ----------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------- USER INPUT ----------------
user_prompt = st.chat_input("Ask about products, sales, or predictions...")

if user_prompt:
    user_name = st.session_state.username
    user_msg = f"{user_name} asked: {user_prompt}"

    # Display user message
    st.chat_message("user").markdown(user_prompt)
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})

    # System instruction for GPT
    system_prompt = {
        "role": "system",
        "content": (
            f"You are a helpful and friendly sales assistant chatbot for a retail dashboard. "
            f"Explain data clearly, summarize predictions, help with navigation questions, "
            f"and use {user_name}'s name to keep it personalized."
        )
    }

    messages = [system_prompt] + st.session_state.chat_history

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = generate_response(messages)
            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})

    # ---------------- FEEDBACK ----------------
    with st.expander("💬 Was this helpful?", expanded=False):
        feedback = st.radio("Your feedback:", ["👍 Yes", "👎 No"], horizontal=True)
        if feedback:
            st.success("Thanks for your feedback!")

