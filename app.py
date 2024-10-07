import json
import feedparser
from googletrans import Translator
import time
from googlesearch import search
import logging
import requests
import os
import sqlite3
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from transformers import pipeline  # NLP modell importálása

# Flask alkalmazás inicializálása
app = Flask(__name__, static_folder='static', static_url_path='')

# Környezeti változók betöltése
load_dotenv()

# Naplózás beállítása
logging.basicConfig(filename='rss_feed_log.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Országok és kulcsszavak az RSS feed kereséséhez
countries = {
    "Hungary": "Magyarország híroldal RSS feed",
    "Serbia": "Szerbia híroldal RSS feed",
    "Slovenia": "Szlovénia híroldal RSS feed",
    "Slovakia": "Szlovákia híroldal RSS feed",
    "Romania": "Románia híroldal RSS feed",
    "Czech Republic": "Csehország híroldal API",
    "Poland": "Lengyelország híroldal API",
    "Austria": "Ausztria híroldal API"
}

rss_feeds = {
    "Hungary": ["https://index.hu/24ora/rss", "https://hvg.hu/rss/rss.html"],
    "Serbia": ["https://www.rts.rs/page/stories/sr/rss.html"],
    "Slovenia": ["https://www.rtvslo.si/rss"],  # Szlovénia: RSS feedek
    "Slovakia": ["https://www.aktuality.sk/rss"],
    "Romania": ["https://www.digi24.ro/rss"],
    "Czech Republic": [],  # Csehország esetén API-t fogunk használni
    "Poland": [],  # Lengyelország esetén API-t fogunk használni
    "Austria": []  # Ausztria esetén API-t fogunk használni
}

translator = Translator()
translation_cache = {}

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# NLP sentiment analysis modell inicializálása
sentiment_analysis = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")


# Adatbázis inicializálása
def init_db():
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news
                     (id INTEGER PRIMARY KEY, country TEXT, title TEXT, link TEXT, published TEXT, sentiment TEXT)''')
        conn.commit()


# Hírek mentése az adatbázisba
def save_news(country, title, link, published, sentiment):
    try:
        with sqlite3.connect('news.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO news (country, title, link, published, sentiment) VALUES (?, ?, ?, ?, ?)",
                      (country, title, link, published, sentiment))
    except sqlite3.Error as e:
        logging.error(f"Hiba történt az adatbázis mentése közben: {e}")


def translate_text(text, target_language="hu"):
    if text in translation_cache:
        return translation_cache[text]
    try:
        translated = translator.translate(text, dest=target_language)
        translation_cache[text] = translated.text
        return translated.text
    except Exception as e:
        logging.error(f"Hiba történt a fordítás közben: {e}")
        return text


# API hívások a Csehország, Lengyelország és Ausztria esetében
def fetch_news_from_api(country):
    url = ""
    if country == "Czech Republic":
        url = f"https://newsapi.org/v2/top-headlines?country=cz&apiKey={NEWS_API_KEY}"
    elif country == "Austria":
        url = f"https://newsapi.org/v2/top-headlines?country=at&apiKey={NEWS_API_KEY}"
    elif country == "Poland":
        url = f"https://newsapi.org/v2/top-headlines?country=pl&apiKey={NEWS_API_KEY}"

    try:
        response = requests.get(url)
        data = response.json()
        for article in data.get("articles", []):
            title = article['title']
            link = article['url']
            published = article.get('publishedAt', 'Nincs megadva')
            translated_title = translate_text(title)
            sentiment = analyze_sentiment(translated_title)
            save_news(country, translated_title, link, published, sentiment)
    except Exception as e:
        logging.error(f"Hiba történt az API hívás közben {country} esetén: {e}")


def analyze_sentiment(text):
    try:
        result = sentiment_analysis(text)
        return result[0]['label']  # Ez adja meg a hangvétel osztályát (pl. positive, negative)
    except Exception as e:
        logging.error(f"Hiba történt a hangvétel elemzés közben: {e}")
        return "Unknown"


# RSS feedek begyűjtése és az API-hívások integrálása
def fetch_and_translate_news():
    """RSS feedek begyűjtése és a hírek fordítása"""
    for country, feeds in rss_feeds.items():
        if country in ["Czech Republic", "Austria", "Poland"]:  # API-t használunk ezekhez az országokhoz
            fetch_news_from_api(country)
        else:
            for feed in feeds:
                try:
                    d = feedparser.parse(feed)
                    if 'entries' in d and d.entries:
                        for entry in d.entries:
                            try:
                                translated_title = translate_text(entry.title)
                                sentiment = analyze_sentiment(translated_title)
                                save_news(country, translated_title, entry.link,
                                          entry.published if 'published' in entry else 'Nincs megadva', sentiment)
                            except Exception as e:
                                logging.error(f"Hiba történt a bejegyzés feldolgozása közben: {e}")
                    else:
                        logging.warning(f"Nem találhatóak bejegyzések ebben a feedben: {feed}")
                except Exception as e:
                    logging.error(f"Hiba történt a feed betöltése közben: {e}")


# Hírek megjelenítése, időrendi sorrendben és ország szerint szűrve
@app.route('/')
def show_news():
    selected_country = request.args.get('country')
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        if selected_country:
            c.execute(
                "SELECT country, title, link, published, sentiment FROM news WHERE country = ? ORDER BY published DESC",
                (selected_country,))
        else:
            c.execute("SELECT country, title, link, published, sentiment FROM news ORDER BY published DESC")
        news = [{'country': row[0], 'title': row[1], 'link': row[2], 'published': row[3], 'sentiment': row[4]} for row
                in c.fetchall()]
    return render_template('google_news.html', news=news, countries=countries, selected_country=selected_country)


# Hírek frissítése 10 percenként
def scheduled_news_update():
    try:
        fetch_and_translate_news()
    except Exception as e:
        logging.error(f"Hiba történt a hírek frissítése közben: {e}")


# Ütemezett feladatkezelő inicializálása
scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_news_update, trigger="interval", minutes=10)
scheduler.start()

if __name__ == "__main__":
    init_db()
    fetch_and_translate_news()
    app.run(debug=True, port=5001, use_reloader=False)
