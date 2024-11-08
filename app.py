import logging
import os
import random
import sqlite3

import feedparser
import matplotlib.pyplot as plt
import networkx as nx
import nltk
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, render_template
from googletrans import Translator
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Flask application initialization
app = Flask(__name__, static_folder='static', static_url_path='')

# Load environment variables
load_dotenv(override=True)

# Setup logging
logging.basicConfig(filename='rss_feed_log.log', level=logging.INFO,  # Reduced log level to INFO
                    format='%(asctime)s - %(levelname)s - %(message)s')

# RSS feeds dictionary
rss_feeds = {
    "Hungary": [
        "https://index.hu/24ora/rss", "https://hvg.hu/rss/rss.html", "https://444.hu/feed",
        "https://24.hu/feed/", "https://nepszava.hu/rss", "https://magyarnemzet.hu/rss",
        "https://telex.hu/rss"
    ],
    "Serbia": [
        "https://www.rts.rs/page/stories/sr/rss.html", "https://www.b92.net/info/rss.php",
        "https://www.danas.rs/feed/", "https://www.novosti.rs/rss", "https://rs.n1info.com/feed/",
        "https://nova.rs/feed/", "https://www.alo.rs/rss"
    ],
    "Slovakia": [
        "https://www.aktuality.sk/rss", "https://www.sme.sk/rss", "https://dennikn.sk/feed/",
        "https://www.pravda.sk/rss", "https://www.hnonline.sk/rss", "https://www.teraz.sk/rss",
        "https://www.ta3.com/rss"
    ],
    "Romania": [
        "https://www.digi24.ro/rss", "https://www.hotnews.ro/rss", "https://www.mediafax.ro/rss",
        "https://www.agerpres.ro/rss", "https://www.euractiv.ro/rss", "https://www.realitatea.net/rss",
        "https://www.zf.ro/rss"
    ],
    "Czech Republic": [
        "https://www.idnes.cz/rss", "https://www.novinky.cz/rss", "https://www.ceskenoviny.cz/rss",
        "https://www.ceskatelevize.cz/rss", "https://www.lidovky.cz/rss", "https://www.aktualne.cz/rss",
        "https://www.reflex.cz/rss"
    ],
    "Poland": [
        "https://www.tvn24.pl/najnowsze.xml", "https://www.gazeta.pl/rss", "https://www.onet.pl/rss",
        "https://www.rmf24.pl/rss", "https://www.pap.pl/rss", "https://www.wprost.pl/rss",
        "https://www.dziennik.pl/rss"
    ],
    "Austria": [
        "https://www.diepresse.com/rss", "https://www.derstandard.at/rss", "https://www.kleinezeitung.at/rss",
        "https://www.krone.at/rss", "https://www.kurier.at/rss", "https://orf.at/rss",
        "https://www.salzburg24.at/rss"
    ]
}

# Source political bias mapping
political_bias = {
    "index.hu": "centrist",
    "hvg.hu": "left",
    "444.hu": "left",
    "24.hu": "left",
    "nepszava.hu": "left",
    "magyarnemzet.hu": "right",
    "telex.hu": "centrist",
    "origo.hu": "right",
    "rts.rs": "state",
    "b92.net": "right",
    "danas.rs": "left",
    "novosti.rs": "right",
    "n1info.com": "centrist",
    "nova.rs": "centrist",
    "alo.rs": "tabloid",
    "aktuality.sk": "centrist",
    "sme.sk": "left",
    "dennikn.sk": "left",
    "pravda.sk": "centrist",
    "hnonline.sk": "right",
    "teraz.sk": "state",
    "ta3.com": "right",
    "digi24.ro": "centrist",
    "hotnews.ro": "left",
    "mediafax.ro": "right",
    "agerpres.ro": "state",
    "euractiv.ro": "centrist",
    "realitatea.net": "right",
    "zf.ro": "business",
    "idnes.cz": "right",
    "novinky.cz": "left",
    "ceskenoviny.cz": "state",
    "ceskatelevize.cz": "public",
    "lidovky.cz": "right",
    "aktualne.cz": "left",
    "reflex.cz": "centrist",
    "tvn24.pl": "left",
    "gazeta.pl": "left",
    "onet.pl": "centrist",
    "rmf24.pl": "right",
    "pap.pl": "state",
    "wprost.pl": "right",
    "dziennik.pl": "right",
    "diepresse.com": "right",
    "derstandard.at": "left",
    "kleinezeitung.at": "centrist",
    "krone.at": "right",
    "kurier.at": "centrist",
    "orf.at": "public",
    "salzburg24.at": "centrist"
}

# Function to determine political bias from URL
def get_political_bias(source_url):
    return next((bias for source, bias in political_bias.items() if source in source_url), "unknown")

# Translator setup
translator = Translator()
translation_cache = {}

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
if not NEWS_API_KEY:
    raise ValueError("The NEWS_API_KEY environment variable is missing. Please check your .env file.")

# NLTK initialization and download
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)
analyzer = SentimentIntensityAnalyzer()

# Database initialization
def init_db():
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news
                     (id INTEGER PRIMARY KEY, country TEXT, title TEXT, link TEXT, published TEXT, sentiment TEXT, 
                      political_bias TEXT)''')
        conn.commit()

# Save news to database
def save_news(country, title, link, published, sentiment, political_bias=None):
    try:
        with sqlite3.connect('news.db') as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO news (country, title, link, published, sentiment, political_bias)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (country, title, link, published, sentiment, political_bias))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to save news: {e}")

# Fetch and process feeds
def fetch_and_process_feeds():
    for country, feeds in rss_feeds.items():
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title
                    link = entry.link
                    published = entry.get('published', 'unknown')
                    sentiment = analyzer.polarity_scores(title)['compound']
                    sentiment_category = 'positive' if sentiment > 0 else 'negative' if sentiment < 0 else 'neutral'
                    political_bias = get_political_bias(link)

                    # Save to database
                    save_news(country, title, link, published, sentiment_category, political_bias=political_bias)

            except Exception as e:
                logging.error(f"Failed to fetch/process feed {feed_url}: {e}")

# Initialize database
init_db()

# Set up background scheduler to periodically fetch news
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_process_feeds, 'interval', hours=1)
scheduler.start()

# Network visualization for political bias and sentiment
def plot_sentiment_political_bias_network():
    G = nx.Graph()

    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('SELECT country, title, political_bias, sentiment FROM news')
        news_data = c.fetchall()

    for _, title, bias, sentiment in news_data:
        sentiment_node = f"{sentiment}_sentiment"
        bias_node = bias
        title_node = title

        G.add_node(sentiment_node, type='sentiment')
        G.add_node(bias_node, type='bias')
        G.add_node(title_node, type='news')

        G.add_edge(title_node, sentiment_node)
        G.add_edge(title_node, bias_node)

    plt.figure(figsize=(15, 15))
    pos = nx.spring_layout(G, seed=42)
    node_colors = []
    for node in G.nodes:
        if G.nodes[node]['type'] == 'sentiment':
            node_colors.append('orange')
        elif G.nodes[node]['type'] == 'bias':
            node_colors.append('cyan')
        else:
            node_colors.append('gray')

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=100, alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=0.5, alpha=0.5, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold', font_color='black')

    plt.title("Political Bias and Sentiment Relationship in News Articles")
    plt.axis('off')
    plt.show()

# Sentiment Analysis Explanation
def explain_sentiment_analysis():
    explanation = (
        "The sentiment analysis used in this project is based on the NLTK library's VADER (Valence Aware Dictionary and sEntiment Reasoner) model. "
        "VADER is a lexicon and rule-based sentiment analysis tool that is specifically designed to identify sentiment expressed in text. "
        "It calculates a compound score, which is used to categorize news titles into positive, negative, or neutral sentiment. "
        "This compound score is calculated based on the intensity of words and phrases that carry sentiment. "
        "The categorization helps visualize the relationship between news articles, their sentiment, and the political bias of the sources."
    )
    return explanation

# Flask routes
@app.route("/")
def home():
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM news ORDER BY published DESC LIMIT 20')
        news_items = c.fetchall()
    sentiment_explanation = explain_sentiment_analysis()
    return render_template('index.html', news=news_items, sentiment_explanation=sentiment_explanation)

# Run Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", random.randint(5000, 6000)))
    app.run(debug=True, port=port)
