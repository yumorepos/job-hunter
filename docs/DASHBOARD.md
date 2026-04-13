# Job Hunter Dashboard

Professional job tracking dashboard built with Streamlit and Plotly.

## Features

- **📊 KPI Cards**: Total jobs, new today, sources active
- **📈 Timeline Chart**: Job postings over time (line chart)
- **🎯 Source Breakdown**: Jobs by source (Indeed, RemoteOK, Arbeitnow, HN) - pie chart
- **🔍 Search Filter**: Filter jobs by keyword in title or description
- **📜 Recent Listings**: Last 20 jobs with company, location, source, and links

## Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard
streamlit run dashboard.py
```

Dashboard will open at http://localhost:8501

## Deployment to Streamlit Cloud

1. Ensure `jobs.db` is committed to your repository
2. Go to https://share.streamlit.io/
3. Click "New app"
4. Select repository: `yumorepos/job-hunter`
5. Branch: `main`
6. Main file path: `dashboard.py`
7. Click "Deploy"

**Note:** The `jobs.db` file must be accessible. For a demo dashboard, commit a snapshot of your database. For production, consider:
- Using a hosted database (PostgreSQL, MySQL)
- Implementing a data refresh mechanism
- Setting up automated scraping with cron jobs

## Tech Stack

- **Streamlit**: Web framework
- **Plotly**: Interactive charts
- **Pandas**: Data processing
- **SQLite**: Local database

## Data Sources

- `jobs` table: All scraped job listings with title, company, location, url, source, tags, description, posted_at, scraped_at

## Future Enhancements

- Add application status tracking (Applied, Pending, Rejected)
- Implement email alerts for new jobs matching specific criteria
- Add salary range visualization
- Create weekly digest reports
