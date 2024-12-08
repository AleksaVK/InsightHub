import sqlite3
import logging
import feedparser
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from transformers import pipeline
import torch
from langdetect import detect
import openai
from dotenv import load_dotenv
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI API
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("API key for OpenAI is not set. Please set the OPENAI_API_KEY environment variable.")
openai.api_key = api_key

# Flask application initialization
app = Flask(__name__, static_folder='static', static_url_path='')

# Limiter for API rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per hour"])

# Redis for caching
cache = redis.StrictRedis(host='localhost', port=6379, db=0)

# Modern UI with Bootstrap
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

# Enhanced logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Translation function with batch processing
def translate_texts(texts, target_language='hu'):
    translated_texts = []
    for text in texts:
        try:
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=f"Translate the following text to {target_language}: {text}",
                max_tokens=100
            )
            translated_texts.append(response.choices[0].text.strip())
        except Exception as e:
            logging.error(f"Translation failed for text: {text}, error: {e}")
            translated_texts.append(text)  # Fallback to original text
    return translated_texts

# BERT sentiment analyzer setup
def setup_sentiment_analyzer():
    device = 0 if torch.cuda.is_available() else -1  # Use GPU if available, otherwise CPU
    return pipeline('sentiment-analysis', model='nlptown/bert-base-multilingual-uncased-sentiment', device=device)

bert_analyzer = setup_sentiment_analyzer()

# Database initialization with indexing
def init_db():
    try:
        with sqlite3.connect('news.db') as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS news
                         (id INTEGER PRIMARY KEY, country TEXT, title TEXT, link TEXT UNIQUE, published TEXT, sentiment TEXT, 
                          political_bias TEXT)''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_country ON news (country)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_published ON news (published)')
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to initialize database: {e}")

# Save news to the database
def save_news(news):
    try:
        with sqlite3.connect('news.db') as conn:
            c = conn.cursor()
            c.execute('''INSERT OR IGNORE INTO news (country, title, link, published, sentiment, political_bias)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (news['country'], news['title'], news['link'], news['published'], news['sentiment'], news['political_bias']))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to save news: {e}")

# Determine political bias
def determine_political_bias(text):
    return 'right' if 'jobboldal' in text.lower() else 'left'

# Fetch and process RSS feeds
def fetch_and_process_feeds():
    for country, feeds in rss_feeds.items():
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                titles = [entry.title for entry in feed.entries]
                translated_titles = translate_texts(titles)

                for entry, translated_title in zip(feed.entries, translated_titles):
                    news = {
                        'country': country,
                        'title': translated_title,
                        'link': entry.link,
                        'published': entry.get('published', 'unknown'),
                        'sentiment': bert_analyzer(translated_title)[0]['label'],
                        'political_bias': determine_political_bias(translated_title),
                    }
                    save_news(news)
            except Exception as e:
                logging.error(f"Failed to fetch/process RSS feed: {feed_url}, error: {e}")

# Visualization with Plotly
def create_interactive_graph():
    import plotly.graph_objects as go
    from collections import Counter

    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('SELECT country, political_bias, sentiment FROM news')
        news_data = c.fetchall()

    if not news_data:
        return None

    bias_counts = Counter([item[1] for item in news_data])
    sentiment_counts = Counter([item[2] for item in news_data])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(bias_counts.keys()), y=list(bias_counts.values()), name='Political Bias'))
    fig.add_trace(go.Bar(x=list(sentiment_counts.keys()), y=list(sentiment_counts.values()), name='Sentiment'))

    fig.update_layout(
        title='News Analysis',
        barmode='group',
        xaxis_title='Category',
        yaxis_title='Count'
    )
    fig.write_html('static/graph.html')
    return 'static/graph.html'

# Initialize the database
init_db()

# Scheduler setup for periodic news fetching
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_process_feeds, 'interval', hours=1)
scheduler.start()

# Flask routes
@app.route("/")
def home():
    return render_template('index.html')

@app.route("/visualization")
def visualization():
    graph_url = create_interactive_graph()
    if graph_url:
        return render_template('visualization.html', graph_url=graph_url)
    else:
        return "No data available for visualization."

@app.route("/api/news", methods=['GET'])
@limiter.limit("10 per minute")
def api_news():
    country = request.args.get('country')
    query = 'SELECT country, title, link, published, sentiment, political_bias FROM news'
    params = ()

    if country:
        query += ' WHERE country = ?'
        params = (country,)

    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute(query, params)
        news_items = c.fetchall()

    return jsonify(news_items)

# Run the Flask application
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5004)))