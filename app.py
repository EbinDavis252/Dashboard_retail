import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import hashlib
from prophet import Prophet
from prophet.plot import plot_plotly

st.set_page_config(page_title="Retail Sales Dashboard", layout="wide")

# ---------- Background ----------
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(to right, #d3cce3, #e9e4f0);
        }
    </style>
""", unsafe_allow_html=True)

# ---------- Databases ----------
engine = sqlalchemy.create_engine('sqlite:///sales.db')
user_engine = sqlalchemy.create_engine('sqlite:///users.db')

# Create tables if not exist
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
            comments TEXT
        )
    """))
    conn.commit()

# ---------- Helpers ----------
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

def load_data():
    try:
        df = pd.read_sql("SELECT * FROM sales", engine)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

# ---------- Session ----------
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'user' not in st.session_state:
    st.session_state.user = ''

# ---------- Login/Register ----------
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
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")
    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Register"):
            if register_user(new_user, new_pass):
                st.success("✅ Registered! You can now log in.")
            else:
                st.error("❌ Username already exists.")
    st.stop()

# ---------- Sidebar ----------
st.sidebar.markdown(f"👋 Welcome, **{st.session_state.user}**")
if st.sidebar.button("🚪 Logout"):
    st.session_state.auth = False
    st.session_state.user = ""
    st.rerun()

menu = ["Upload Data", "View Data", "Dashboard", "Feedback", "Predictions", "Admin Panel"]
choice = st.sidebar.selectbox("📂 Navigate", menu)

# ---------- Upload ----------
if choice == "Upload Data":
    st.subheader("📤 Upload Sales CSV")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        try:
            df = pd.read_csv(file)
            df.columns = df.columns.str.strip().str.lower()
            df['date'] = pd.to_datetime(df['date'])
            st.dataframe(df)
            if st.button("✅ Save to DB"):
                df.to_sql('sales', engine, if_exists='append', index=False)
                st.success("Saved to database!")
        except Exception as e:
            st.error(f"Error: {e}")

# ---------- View ----------
elif choice == "View Data":
    st.subheader("📑 Stored Sales Data")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data found.")
    else:
        st.dataframe(data)
        st.download_button("📥 Download CSV", convert_df(data), file_name="sales_data.csv")

# ---------- Dashboard ----------
elif choice == "Dashboard":
    st.subheader("📊 Sales Dashboard")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data available.")
    else:
        col1, col2 = st.columns(2)
        region = col1.selectbox("Select Region", ["All"] + list(data['region'].dropna().unique()))
        product = col2.selectbox("Select Product", ["All"] + list(data['product'].dropna().unique()))

        col3, col4 = st.columns(2)
        start = col3.date_input("Start Date", data['date'].min())
        end = col4.date_input("End Date", data['date'].max())

        df = data[(data['date'] >= pd.to_datetime(start)) & (data['date'] <= pd.to_datetime(end))]
        if region != "All":
            df = df[df['region'] == region]
        if product != "All":
            df = df[df['product'] == product]

        st.metric("Total Revenue", f"${df['revenue'].sum():,.2f}")
        st.metric("Units Sold", f"{df['units_sold'].sum()}")

        st.plotly_chart(px.line(df.groupby('date')['revenue'].sum().reset_index(), x='date', y='revenue'), use_container_width=True)

# ---------- Feedback ----------
elif choice == "Feedback":
    st.subheader("⭐ Give Your Feedback")
    st.markdown("### Rate Your Experience:")
    stars = st.columns(5)
    if 'star_rating' not in st.session_state:
        st.session_state.star_rating = 0
    for i in range(5):
        if stars[i].button("⭐" if st.session_state.star_rating > i else "☆", key=f"star{i}"):
            st.session_state.star_rating = i + 1
    comment = st.text_area("💬 Comments (optional)")
    if st.button("Submit Feedback"):
        if st.session_state.star_rating == 0:
            st.warning("⚠ Please rate before submitting.")
        else:
            with user_engine.connect() as conn:
                conn.execute(text("INSERT INTO feedback (username, rating, comments) VALUES (:u, :r, :c)"),
                             {"u": st.session_state.user, "r": st.session_state.star_rating, "c": comment})
                conn.commit()
            st.success("✅ Thanks for your feedback!")
            st.session_state.star_rating = 0

# ---------- Predictions ----------
elif choice == "Predictions":
    st.subheader("🔮 Predictive Analytics")
    pred_option = st.selectbox("Choose Prediction Type", [
        "Sales Forecast (Time Series)",
        "Revenue Prediction Model",
        "Seasonality Analysis"
    ])

    if pred_option == "Sales Forecast (Time Series)":
        st.markdown("Using Prophet to forecast future sales.")
        df = load_data()
        if df.empty:
            st.warning("No data available.")
        else:
            ts_data = df.groupby('date').agg({'revenue': 'sum'}).reset_index()
            ts_data.rename(columns={'date': 'ds', 'revenue': 'y'}, inplace=True)
            model = Prophet()
            model.fit(ts_data)
            future = model.make_future_dataframe(periods=30)
            forecast = model.predict(future)

            st.plotly_chart(plot_plotly(model, forecast), use_container_width=True)
            st.write(model.plot_components(forecast))

    elif pred_option == "Revenue Prediction Model":
        st.markdown("🚧 Will implement regression model soon...")

    elif pred_option == "Seasonality Analysis":
        st.markdown("🚧 Will add seasonal decomposition and analysis...")

# ---------- Admin Panel ----------
elif choice == "Admin Panel":
    st.subheader("🛠️ Admin Panel")
    if st.session_state.user != "admin":
        st.warning("⛔ Access Denied. Only Admin allowed.")
    else:
        st.markdown("### 👥 Registered Users")
        users_df = pd.read_sql("SELECT username FROM users", user_engine)
        st.write(users_df)
        st.success(f"Total Users: {len(users_df)}")

        st.markdown("### 🗣️ All Feedback")
        fb_df = pd.read_sql("SELECT * FROM feedback", user_engine)
        if fb_df.empty:
            st.info("No feedback yet.")
        else:
            st.dataframe(fb_df)
            st.metric("Average Rating", f"{fb_df['rating'].mean():.2f} ⭐")
            st.bar_chart(fb_df['rating'].value_counts().sort_index())
