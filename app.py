import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import hashlib
from prophet import Prophet

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

# Create users table
with user_engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """))
    conn.commit()

# Create feedback table
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
    with user_engine.connect() as conn:
        conn.execute(
            text("INSERT INTO users (username, password) VALUES (:u, :p)"),
            {"u": username, "p": hash_password(password)}
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

# -------------------- APP HEADER & LOGOUT --------------------
st.sidebar.markdown(f"👋 Welcome, **{st.session_state.user}**!")
if st.sidebar.button("🚪 Logout"):
    st.session_state.auth = False
    st.session_state.user = ""
    st.rerun()

# -------------------- MAIN MENU --------------------
menu = ["Upload Data", "View Data", "Dashboard", "Feedback", "Predictions", "Admin Panel"]
choice = st.sidebar.selectbox("📂 Navigate", menu)

# -------------------- UPLOAD --------------------
if choice == "Upload Data":
    st.subheader("📤 Upload Sales CSV File")
    with st.expander("📌 CSV Format Example"):
        st.markdown("""
        | date       | product     | region  | units_sold | revenue |
        |------------|-------------|---------|------------|---------|
        | 2024-06-01 | Widget A    | East    | 10         | 100     |
        """)

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

# -------------------- VIEW --------------------
elif choice == "View Data":
    st.subheader("📑 View Stored Sales Data")
    data = load_data()
    if data.empty:
        st.warning("⚠ No data found.")
    else:
        st.dataframe(data)
        st.download_button("📥 Download All Data", data=convert_df(data), file_name='sales_data.csv', mime='text/csv')

# -------------------- DASHBOARD --------------------
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

        st.markdown("### 📈 Key Performance Indicators")
        c1, c2 = st.columns(2)
        c1.metric("Total Revenue", f"${data['revenue'].sum():,.2f}")
        c2.metric("Units Sold", f"{data['units_sold'].sum():,.0f}")

        st.markdown("### 📅 Revenue Over Time")
        daily = data.groupby('date').agg({'revenue': 'sum'}).reset_index()
        st.plotly_chart(px.line(daily, x='date', y='revenue', markers=True), use_container_width=True)

        st.markdown("### 📦 Top Selling Products")
        top_products = data.groupby('product')['revenue'].sum().sort_values(ascending=False).reset_index()
        st.plotly_chart(px.bar(top_products, x='product', y='revenue', text_auto=True), use_container_width=True)

        st.markdown("### 🌍 Region vs Product Heatmap")
        pivot = data.pivot_table(values='revenue', index='region', columns='product', aggfunc='sum', fill_value=0)
        fig, ax = plt.subplots()
        sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlGnBu", ax=ax)
        st.pyplot(fig)

        st.markdown("### 🗓️ Monthly Trend")
        data['month'] = data['date'].dt.to_period('M')
        monthly = data.groupby('month')[['revenue', 'units_sold']].sum().reset_index()
        st.bar_chart(monthly.set_index('month'))

        st.markdown("### 📤 Download Filtered Data")
        st.download_button("Download CSV", data=convert_df(data), file_name="filtered_sales.csv", mime='text/csv')

        st.markdown("### 📌 Dynamic Chart")
        colx1, colx2 = st.columns(2)
        xcol = colx1.selectbox("X-axis", options=data.select_dtypes(include=['object', 'datetime64']).columns)
        ycol = colx2.selectbox("Y-axis", options=data.select_dtypes(include='number').columns)
        st.plotly_chart(px.bar(data, x=xcol, y=ycol), use_container_width=True)

        st.markdown("### 🔬 Correlation Matrix")
        st.dataframe(data.corr(numeric_only=True).round(2))

# -------------------- FEEDBACK --------------------
elif choice == "Feedback":
    st.subheader("⭐ Rate Your Experience")
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
            save_feedback(
                st.session_state.user,
                f"Rating: {st.session_state.star_rating} stars | Comment: {comment.strip() or 'No comment'}"
            )
            st.success("✅ Thanks for your feedback!")
            st.session_state.star_rating = 0

# -------------------- ADMIN PANEL --------------------
elif choice == "Admin Panel":
    st.subheader("🛠️ Admin Panel")

    if st.session_state.user != "admin":
        st.warning("⛔ You are not authorized to view this page.")
    else:
        feedback_df = pd.read_sql("SELECT * FROM feedback ORDER BY submitted_at DESC", feedback_engine)

        st.markdown("### 🗣️ All Feedback")
        if feedback_df.empty:
            st.info("No feedback submitted yet.")
        else:
            st.dataframe(feedback_df)

            st.markdown("### 📊 Feedback Analytics")
            # ✅ FIXED: Proper regex to extract numeric rating
            feedback_df['rating'] = feedback_df['message'].str.extract(r'Rating:\s*(\d+)').astype(float)
            avg_rating = feedback_df['rating'].mean()
            st.metric("Average Rating", f"{avg_rating:.2f} ⭐")

            rating_counts = feedback_df['rating'].value_counts().sort_index()
            chart = pd.DataFrame({ "Rating": rating_counts.index, "Count": rating_counts.values })
            st.bar_chart(chart.set_index("Rating"))

            with st.expander("💬 View Sample Comments"):
                comments = feedback_df[['username', 'message', 'submitted_at']].copy()
                comments['Comment'] = comments['message'].str.extract(r'Comment:\s*(.*)')
                st.dataframe(comments[['username', 'submitted_at', 'Comment']])

        st.markdown("### 👥 Registered Users")
        users_df = pd.read_sql("SELECT username FROM users", user_engine)
        st.success(f"**Total Users Registered:** {users_df.shape[0]}")
        st.dataframe(users_df)
# -------------------- PREDICTIONS --------------------
elif choice == "Predictions":
    st.subheader("🔮 Predictive Insights")

    prediction_option = st.selectbox("Select Prediction Type", [
        "Sales Forecast (Time Series)",
        "Revenue Prediction Model",
        "Seasonality Analysis"
    ])

    if prediction_option == "Sales Forecast (Time Series)":
        st.markdown("""
        ### 📈 Sales Forecast (Time Series)
        This uses historical sales data to forecast future sales using time series models (like ARIMA or Prophet).
        """)
        data = load_data()
        if data.empty:
            st.warning("⚠ Not enough data to forecast.")
        else:
            df = data.groupby('date').agg({'revenue': 'sum'}).reset_index()
            df = df.rename(columns={"date": "ds", "revenue": "y"})

            from prophet import Prophet
            model = Prophet()
            model.fit(df)

            future = model.make_future_dataframe(periods=30)
            forecast = model.predict(future)

            st.markdown("### 📉 Forecasted Revenue")
            st.plotly_chart(px.line(forecast, x='ds', y='yhat'), use_container_width=True)

    elif prediction_option == "Revenue Prediction Model":
        st.markdown("### 💰 Revenue Prediction Model")
        st.info("🚧 Revenue prediction model is under development.")

    elif prediction_option == "Seasonality Analysis":
        st.markdown("### 📆 Seasonality Analysis")
        st.info("🚧 Seasonality analysis logic is under development.")
