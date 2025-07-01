import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import plotly.express as px
import hashlib

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Retail Sales Dashboard", layout="wide")

# -------------------- BACKGROUND --------------------
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(to right, #d7effb, #ecd2f7);
            animation: gradient 15s ease infinite;
            background-size: 400% 400%;
        }
    </style>
""", unsafe_allow_html=True)

# -------------------- DATABASE SETUP --------------------
engine = sqlalchemy.create_engine('sqlite:///sales.db')
user_engine = sqlalchemy.create_engine('sqlite:///users.db')

with user_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS feedback (
            username TEXT,
            rating INTEGER,
            comment TEXT
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
    with user_engine.connect() as conn:
        conn.execute(text("INSERT INTO users (username, password) VALUES (:u, :p)"),
                     {"u": username, "p": hash_password(password)})
        conn.commit()
    return True

# -------------------- SALES DATA HELPERS --------------------
def save_to_db(df):
    try:
        df.columns = df.columns.str.strip().str.lower()
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

# -------------------- AUTH UI --------------------
if 'auth' not in st.session_state:
    st.session_state.auth = False
    st.session_state.username = ""

if not st.session_state.auth:
    st.sidebar.title("👤 User Login")
    tab1, tab2 = st.sidebar.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if verify_user(username, password):
                st.session_state.auth = True
                st.session_state.username = username
                st.success("✅ Login successful!")
                st.experimental_rerun()
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

# -------------------- MAIN MENU --------------------
menu = ["Upload Data", "View Data", "Dashboard", "Feedback", "Predictions", "Admin Panel"]
choice = st.sidebar.selectbox("📂 Navigate", menu)

st.sidebar.write(f"👋 Welcome, `{st.session_state.username}`")
if st.sidebar.button("🔓 Logout"):
    st.session_state.auth = False
    st.session_state.username = ""
    st.experimental_rerun()

# -------------------- PAGES --------------------
if choice == "Upload Data":
    st.subheader("📤 Upload Sales CSV File")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        df = pd.read_csv(file)
        st.dataframe(df)
        if st.button("✅ Save to Database"):
            if save_to_db(df):
                st.success("Saved to database!")
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
        st.download_button("📥 Download All Data", data=convert_df(data), file_name='sales_data.csv')

elif choice == "Dashboard":
    st.subheader("📊 Sales Dashboard")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data found.")
    else:
        region = st.selectbox("🌍 Region", ["All"] + sorted(data['region'].dropna().unique()))
        product = st.selectbox("📦 Product", ["All"] + sorted(data['product'].dropna().unique()))
        start_date = st.date_input("📅 Start Date", data['date'].min())
        end_date = st.date_input("📅 End Date", data['date'].max())

        data = data[(data['date'] >= pd.to_datetime(start_date)) & (data['date'] <= pd.to_datetime(end_date))]
        if region != "All": data = data[data['region'] == region]
        if product != "All": data = data[data['product'] == product]

        st.metric("💰 Total Revenue", f"${data['revenue'].sum():,.2f}")
        st.metric("📦 Units Sold", f"{data['units_sold'].sum():,.0f}")

        st.plotly_chart(px.line(data.groupby('date').revenue.sum().reset_index(), x='date', y='revenue'), use_container_width=True)

elif choice == "Feedback":
    st.subheader("📝 Submit Feedback")
    with st.form("feedback_form"):
        rating = st.slider("Rate the App", 1, 5)
        comment = st.text_area("Additional Comments (optional)")
        if st.form_submit_button("Submit"):
            with user_engine.connect() as conn:
                conn.execute(text("INSERT INTO feedback (username, rating, comment) VALUES (:u, :r, :c)"),
                             {"u": st.session_state.username, "r": rating, "c": comment})
                conn.commit()
            st.success("Feedback submitted!")

elif choice == "Predictions":
    st.subheader("🔮 Predictive Analytics")
    prediction_option = st.selectbox("Select Prediction Type", [
        "Sales Forecast (Time Series)",
        "Revenue Prediction Model",
        "Seasonality Analysis"
    ])

    if prediction_option == "Sales Forecast (Time Series)":
        st.markdown("""
        ### 📈 Sales Forecast (Time Series)
        This module analyzes historical sales data to forecast future sales trends using models like ARIMA or Prophet.
        Useful for inventory planning and demand estimation.
        """)
        st.info("🚧 Forecast logic will be implemented here...")

    elif prediction_option == "Revenue Prediction Model":
        st.markdown("""
        ### 💰 Revenue Prediction Model
        Predict revenue using regression models based on product, region, and historical performance.
        This helps in budgeting and sales target setting.
        """)
        st.info("🚧 Revenue prediction logic goes here...")

    elif prediction_option == "Seasonality Analysis":
        st.markdown("""
        ### 📅 Seasonality Analysis
        Identify patterns such as monthly or weekly seasonality in sales to improve marketing and stock planning.
        """)
        st.info("🚧 Seasonality charts to be added...")

elif choice == "Admin Panel" and st.session_state.username == "admin":
    st.subheader("🛠️ Admin Panel")
    users_df = pd.read_sql("SELECT username FROM users", user_engine)
    feedback_df = pd.read_sql("SELECT * FROM feedback", user_engine)

    st.markdown("### 👥 Registered Users")
    st.write(f"Total Users: {len(users_df)}")
    st.dataframe(users_df)

    st.markdown("### 💬 Submitted Feedback")
    if feedback_df.empty:
        st.info("No feedback yet.")
    else:
        st.dataframe(feedback_df)
        avg_rating = feedback_df['rating'].mean()
        st.metric("📊 Average Rating", f"{avg_rating:.2f} ⭐")
        st.bar_chart(feedback_df['rating'].value_counts().sort_index())

elif choice == "Admin Panel":
    st.warning("⚠ Only admin can access this panel.")
