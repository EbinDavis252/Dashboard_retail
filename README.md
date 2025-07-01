# 🛍️ Retail Sales Dashboard (Streamlit App)

This is a full-featured **Retail Sales Dashboard** built using **Python, Streamlit, and SQLite**. It allows users to upload sales data, visualize key metrics, and interactively explore performance trends over time — all inside a browser.

🔐 Includes **user login and registration** for secure access.

---

## 🚀 Features

- 📤 Upload retail sales CSV data
- 💾 Stores data in a local SQLite database
- 📊 View dashboards with filters (Region, Product, Date)
- 📈 Line charts, bar graphs, heatmaps, correlation matrix
- 🔍 Dynamic charting by selecting any X/Y axis
- 🧹 Clear/reset data option
- 📥 Export filtered data as CSV
- 👤 User login and registration system

---

## 🗂 Sample Data Format

Upload a CSV with these columns:

| date       | product   | region | units_sold | revenue |
|------------|-----------|--------|------------|---------|
| 2024-06-01 | Widget A  | East   | 10         | 100     |
| 2024-06-02 | Widget B  | West   | 5          | 50      |

📝 `date` should be in `YYYY-MM-DD` format.

---

## 🔧 How to Run Locally

### 1. Clone the repo:
```bash
git clone https://github.com/yourusername/Retail-Sales-Dashboard.git
cd Retail-Sales-Dashboard
