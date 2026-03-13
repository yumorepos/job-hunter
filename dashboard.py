"""
Job Hunter Dashboard
Built with Streamlit + Plotly
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Job Hunter Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Database connection
DB_PATH = Path(__file__).parent / "jobs.db"

@st.cache_data(ttl=300)
def load_jobs():
    """Load all jobs from database"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT 
            id, title, company, location, url, source, 
            tags, description, posted_at, scraped_at
        FROM jobs
        ORDER BY scraped_at DESC
    """, conn)
    conn.close()
    
    # Parse dates
    df['scraped_at'] = pd.to_datetime(df['scraped_at'], format='mixed', utc=True)
    df['posted_at'] = pd.to_datetime(df['posted_at'], format='mixed', utc=True, errors='coerce')
    
    return df

def main():
    st.title("🔍 Job Hunter Dashboard")
    st.markdown("**Automated job scraper tracking Python, data, and automation roles**")
    
    # Load data
    jobs_df = load_jobs()
    
    if jobs_df.empty:
        st.warning("No jobs found in database. Run `python job_hunter.py scrape` to collect jobs.")
        return
    
    # Calculate metrics
    total_jobs = len(jobs_df)
    today = datetime.now().date()
    new_today = len(jobs_df[jobs_df['scraped_at'].dt.date == today])
    sources_active = jobs_df['source'].nunique()
    
    # KPI Cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Total Jobs", f"{total_jobs:,}")
    
    with col2:
        st.metric("✨ New Today", new_today)
    
    with col3:
        st.metric("🌐 Sources Active", sources_active)
    
    st.markdown("---")
    
    # Timeline Chart
    st.subheader("📈 Job Postings Timeline")
    
    # Group by date
    timeline_data = jobs_df.groupby(jobs_df['scraped_at'].dt.date).size().reset_index()
    timeline_data.columns = ['date', 'count']
    
    fig_timeline = go.Figure()
    fig_timeline.add_trace(go.Scatter(
        x=timeline_data['date'],
        y=timeline_data['count'],
        mode='lines+markers',
        name='Jobs Scraped',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6)
    ))
    
    fig_timeline.update_layout(
        xaxis_title="Date",
        yaxis_title="Number of Jobs",
        hovermode='x unified',
        height=350,
        template='plotly_dark'
    )
    
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    # Source Breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 Source Breakdown")
        
        source_counts = jobs_df['source'].value_counts()
        
        # Create pie chart
        fig_pie = px.pie(
            values=source_counts.values,
            names=source_counts.index,
            hole=0.4,
            template='plotly_dark'
        )
        
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(height=350, showlegend=False)
        
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📊 Status Tracker")
        
        # Since no status column exists, show total jobs as a simple metric
        st.metric("Total Jobs Found", f"{total_jobs:,}")
        st.info("💡 Status tracking not yet implemented. All jobs are currently tracked as 'Found'.")
    
    st.markdown("---")
    
    # Search & Filter
    st.subheader("🔍 Recent Listings")
    
    search_query = st.text_input("Search by keyword (title or description)", "")
    
    # Filter by search
    filtered_df = jobs_df.copy()
    if search_query:
        mask = (
            filtered_df['title'].str.contains(search_query, case=False, na=False) |
            filtered_df['description'].str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    # Display results
    st.markdown(f"**Showing {len(filtered_df)} jobs** (limited to 20 most recent)")
    
    # Recent listings table
    display_df = filtered_df.head(20)[['title', 'company', 'location', 'source', 'scraped_at', 'url']]
    display_df['scraped_at'] = display_df['scraped_at'].dt.strftime('%Y-%m-%d %H:%M')
    
    for _, row in display_df.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{row['title']}**")
                if pd.notna(row['company']):
                    st.caption(f"🏢 {row['company']}")
            
            with col2:
                if pd.notna(row['location']):
                    st.caption(f"📍 {row['location']}")
                st.caption(f"🗓️ {row['scraped_at']}")
            
            with col3:
                st.caption(f"**{row['source'].upper()}**")
                st.markdown(f"[View Job]({row['url']})")
            
            st.markdown("---")

if __name__ == "__main__":
    main()
