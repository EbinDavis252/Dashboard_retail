import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import hashlib

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Retail Sales Dashboard", layout="wide")

# -------------------- BACKGROUND --------------------
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(to right, #c4fda1, #c2e9fb, #cfa1fd);
            animation: gradient 15s ease infinite;
            background-size: 400% 400%;
        }
        @keyframes gradient {
            0% {background-position: 0% 50%;}
            50% {background-position: 100% 50%;}
            100% {background-position: 0% 50%;}
        }
    </style>
""", unsafe_allow_html=True)

# -------------------- DATABASES --------------------
engine = sqlalchemy.create_engine('sqlite:///sales.db')
user_engine = sqlalchemy.create_engine('sqlite:///users.db')
feedback_engine = sqlalchemy.create_engine('sqlite:///feedback.db')

# ✅ Create users table with role
with user_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """))
    conn.commit()

# ✅ Create feedback table
with feedback_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS feedback (
            username TEXT,
            message TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()

# -------------------- AUTH HELPERS --------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    df = pd.read_sql("SELECT * FROM users WHERE username = ?", user_engine, params=(username,))
    return not df.empty and df['password'][0] == hash_password(password)

def register_user(username, password):
    df = pd.read_sql("SELECT * FROM users WHERE username = ?", user_engine, params=(username,))
    if not df.empty:
        return False
    role = "admin" if username.lower() == "admin" else "user"
    with user_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)"),
            {"u": username, "p": hash_password(password), "r": role}
        )
        conn.commit()
    return True

def save_feedback(username, message):
    with feedback_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO feedback (username, message) VALUES (:u, :m)"),
            {"u": username, "m": message}
        )
        conn.commit()

# -------------------- SALES HELPERS --------------------
def save_to_db(df):
    try:
        df.columns = df.columns.str.strip().str.lower()
        if 'date' not in df.columns:
            st.error("❌ Column 'date' not found in uploaded file.")
            return False
        df['date'] = pd.to_datetime(df['date'])
        df.to_sql('sales', engine, if_exists='append', index=False)
        return True
    except Exception as e:
        st.error(f"Error saving to DB: {e}")
        return False

def load_data():
    try:
        df = pd.read_sql("SELECT * FROM sales", engine)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        return pd.DataFrame()

def clear_db():
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sales"))
        conn.commit()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

# -------------------- SESSION SETUP --------------------
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'user' not in st.session_state:
    st.session_state.user = ""
if 'role' not in st.session_state:
    st.session_state.role = "user"

# -------------------- AUTH UI --------------------
if not st.session_state.auth:
    st.sidebar.title("👤 User Login")
    tab1, tab2 = st.sidebar.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if verify_user(username, password):
                st.session_state.auth = True
                st.session_state.user = username
                user_info = pd.read_sql("SELECT role FROM users WHERE username = ?", user_engine, params=(username,))
                st.session_state.role = user_info['role'][0] if not user_info.empty else "user"
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Register"):
            if register_user(new_user, new_pass):
                st.success("✅ Registration successful! You can now log in.")
            else:
                st.error("❌ Username already exists.")
    st.stop()

# -------------------- HEADER & LOGOUT --------------------
st.sidebar.markdown(f"👋 Welcome, **{st.session_state.user}** ({st.session_state.role})")
if st.sidebar.button("🚪 Logout"):
    st.session_state.auth = False
    st.session_state.user = ""
    st.session_state.role = "user"
    st.rerun()

# -------------------- MAIN MENU --------------------
menu = ["Upload Data", "View Data", "Dashboard", "Feedback"]
if st.session_state.role == "admin":
    menu.append("Admin Panel")

choice = st.sidebar.selectbox("📂 Navigate", menu)

# -------------------- PAGES --------------------
if choice == "Upload Data":
    st.subheader("📤 Upload Sales CSV File")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        try:
            df = pd.read_csv(file, encoding='latin1')
            st.dataframe(df)
            if st.button("✅ Save to Database"):
                if save_to_db(df):
                    st.success("Saved to database!")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    if st.button("🔄 Clear All Data"):
        clear_db()
        st.success("Sales database cleared.")

elif choice == "View Data":
    st.subheader("📑 View Stored Sales Data")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data found.")
    else:
        st.dataframe(data)
        st.download_button("📥 Download All Data", data=convert_df(data), file_name='sales_data.csv', mime='text/csv')

elif choice == "Dashboard":
    st.subheader("📊 Sales Dashboard")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data found.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            region = st.selectbox("🌍 Select Region", ["All"] + sorted(data['region'].dropna().unique()))
        with col2:
            product = st.selectbox("📦 Select Product", ["All"] + sorted(data['product'].dropna().unique()))

        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("📅 Start Date", data['date'].min())
        with col4:
            end_date = st.date_input("📅 End Date", data['date'].max())

        data = data[(data['date'] >= pd.to_datetime(start_date)) & (data['date'] <= pd.to_datetime(end_date))]
        if region != "All":
            data = data[data['region'] == region]
        if product != "All":
            data = data[data['product'] == product]

        st.markdown("### 📈 KPIs")
        c1, c2 = st.columns(2)
        c1.metric("Total Revenue", f"${data['revenue'].sum():,.2f}")
        c2.metric("Units Sold", f"{data['units_sold'].sum():,.0f}")

        st.markdown("### 📅 Revenue Over Time")
        st.plotly_chart(px.line(data.groupby('date')['revenue'].sum().reset_index(), x='date', y='revenue'))

        st.markdown("### 📦 Top Selling Products")
        st.plotly_chart(px.bar(data.groupby('product')['revenue'].sum().reset_index().sort_values(by="revenue", ascending=False), x='product', y='revenue'))

        st.markdown("### 🌍 Region vs Product Heatmap")
        fig, ax = plt.subplots()
        sns.heatmap(data.pivot_table(index='region', columns='product', values='revenue', aggfunc='sum', fill_value=0), annot=True, fmt=".0f", cmap="YlGnBu", ax=ax)
        st.pyplot(fig)

        st.markdown("### 🗓️ Monthly Trend")
        data['month'] = data['date'].dt.to_period('M')
        st.bar_chart(data.groupby('month')[['revenue', 'units_sold']].sum())

        st.markdown("### 📤 Download Filtered Data")
        st.download_button("Download CSV", data=convert_df(data), file_name="filtered_sales.csv", mime='text/csv')

elif choice == "Feedback":
    st.subheader("⭐ Rate Your Experience")
    st.markdown("We’d love to hear how your experience was using the app!")
    if 'star_rating' not in st.session_state:
        st.session_state.star_rating = 0

    st.markdown("### Select Star Rating:")
    stars = st.columns(5)
    for i in range(5):
        if stars[i].button("⭐" if st.session_state.star_rating > i else "☆", key=f"star{i}"):
            st.session_state.star_rating = i + 1

    st.markdown(f"**Your Rating: {st.session_state.star_rating} star{'s' if st.session_state.star_rating > 1 else ''}**")
    comment = st.text_area("💬 Any comments? (optional)", max_chars=300)

    if st.button("Submit Feedback"):
        if st.session_state.star_rating == 0:
            st.warning("⚠ Please select a star rating before submitting.")
        else:
            save_feedback(st.session_state.user, f"Rating: {st.session_state.star_rating} stars | Comment: {comment.strip() or 'No comment'}")
            st.success("✅ Thanks for your feedback!")
            st.session_state.star_rating = 0

elif choice == "Admin Panel":
    st.subheader("🛠️ Admin Panel - Feedback Review")
    if st.session_state.role != "admin":
        st.warning("⛔ You are not authorized to view this page.")
    else:
        feedback_df = pd.read_sql("SELECT * FROM feedback ORDER BY submitted_at DESC", feedback_engine)
        if feedback_df.empty:
            st.info("No feedback submitted yet.")
        else:
            st.dataframe(feedback_df, use_container_width=True)
