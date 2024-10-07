import feedparser
from googletrans import Translator
import time
from googlesearch import search
import logging
import json

# Naplózás beállítása
logging.basicConfig(filename='rss_feed_log.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Országok és kulcsszavak az RSS feed kereséséhez
countries = {
    "Hungary": "Magyarország híroldal RSS feed",
    "Serbia": "Szerbia híroldal RSS feed",
    "Slovenia": "Szlovénia híroldal RSS feed",
    "Slovakia": "Szlovákia híroldal RSS feed",
    "Romania": "Románia híroldal RSS feed",
    "Czech Republic": "Csehország híroldal RSS feed",
    "Poland": "Lengyelország híroldal RSS feed",
    "Austria": "Ausztria híroldal RSS feed"
}

# Friss RSS feedek országonként
rss_feeds = {
    "Hungary": ["https://index.hu/24ora/rss", "https://hvg.hu/rss/rss.html"],
    "Serbia": ["https://www.rts.rs/page/stories/sr/rss.html"],
    "Slovenia": ["https://www.rtvslo.si/rss"],
    "Slovakia": ["https://www.aktuality.sk/rss"],
    "Romania": ["https://www.digi24.ro/rss"],
    "Czech Republic": ["https://www.ceskatelevize.cz/rss/"],
    "Poland": ["https://www.tvn24.pl/najnowsze.xml"],
    "Austria": ["https://www.diepresse.com/rss"]
}

# API javaslatok, ahol nincs működő RSS feed
api_suggestions = {
    "Slovenia": "News API (https://newsapi.org/)",
    "Slovakia": "GDELT API (https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/)"
}

translator = Translator()
translation_cache = {}
rss_results = {}


def translate_text(text, target_language="hu"):
    """Fordítja a szöveget a megadott nyelvre, cache-eli az eredményt"""
    if text in translation_cache:
        return translation_cache[text]
    try:
        translated = translator.translate(text, dest=target_language)
        translation_cache[text] = translated.text
        return translated.text
    except Exception as e:
        logging.error(f"Hiba történt a fordítás közben: {e}")
        return text  # Ha hiba van, visszaadjuk az eredeti szöveget


def fetch_and_translate_news():
    """RSS feedek begyűjtése és a hírek fordítása"""
    for country, feeds in rss_feeds.items():
        print(f"\nOrszág: {country}")
        for feed in feeds:
            try:
                # RSS feed feldolgozása
                d = feedparser.parse(feed)
                if 'entries' in d and d.entries:
                    for entry in d.entries:
                        try:
                            translated_title = translate_text(entry.title)
                            print(f"Fordított cím: {translated_title}")
                            print(f"Eredeti link: {entry.link}")
                            print(f"Megjelenés: {entry.published if 'published' in entry else 'Nincs megadva'}")
                            print("-" * 40)
                        except Exception as e:
                            logging.error(f"Hiba történt a bejegyzés feldolgozása közben: {e}")
                else:
                    print(f"Nem találhatóak bejegyzések ebben a feedben: {feed}")
            except Exception as e:
                logging.error(f"Hiba történt a feed betöltése közben: {e}")


def search_rss_feeds():
    """RSS feedek keresése a megadott országok számára"""
    rss_results = {}
    for country, query in countries.items():
        print(f"Keresés {country} híroldalakra...")
        rss_results[country] = []
        try:
            for result in search(query, num_results=10):
                rss_results[country].append(result)
        except Exception as e:
            logging.error(f"Hiba történt a keresés közben {country} esetén: {e}")

    # Eredmények mentése JSON fájlba
    with open('rss_search_results.json', 'w') as f:
        json.dump(rss_results, f, indent=4)


if __name__ == "__main__":
    # Első lépés: keresés RSS feedekre (ha szükséges)
    search_rss_feeds()

    # Második lépés: hírek begyűjtése és fordítása
    try:
        while True:
            fetch_and_translate_news()
            time.sleep(600)  # 10 percenként frissíti a híreket
    except KeyboardInterrupt:
        print("A program leállt.")