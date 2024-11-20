import json
import feedparser
import time
import random
import logging
import requests
import os
import sqlite3
from dotenv import load_dotenv
from flask import Flask, render_template, request
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import plotly.graph_objs as go
from deep_translator import GoogleTranslator
import matplotlib.pyplot as plt
from matplotlib import cm
from sklearn.metrics.pairwise import cosine_similarity
import plotly
import networkx as nx

# Flask alkalmazás inicializálása
app = Flask(__name__, static_folder='static', static_url_path='')

# Környezeti változók betöltése
load_dotenv(override=True)

# Naplózás beállítása
logging.basicConfig(filename='rss_feed_log.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Klaszterezés színei
CLUSTER_COLORS = [
    'rgb(244, 67, 54)', 'rgb(33, 150, 243)', 'rgb(76, 175, 80)', 'rgb(255, 152, 0)',
    'rgb(156, 39, 176)', 'rgb(0, 188, 212)', 'rgb(255, 87, 34)', 'rgb(63, 81, 181)'
]

translator = GoogleTranslator(source='auto', target='hu')

# Adatbázis inicializálása
def init_db():
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news
                     (id INTEGER PRIMARY KEY, country TEXT, title TEXT, link TEXT, published TEXT, sentiment TEXT, topic TEXT, region TEXT, political_bias TEXT, entities TEXT)''')
        conn.commit()

# K-means klaszterezési függvény
def perform_kmeans_clustering(titles, num_clusters=3):
    # A szöveget TF-IDF jellemzőkké alakítjuk
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(titles)

    # K-means klaszterezés alkalmazása
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    kmeans.fit(X)

    # Visszaadjuk a címkéket és a centroidokat
    return kmeans.labels_, kmeans.cluster_centers_, X

# Vizualizációs függvény Plotly segítségével
def create_kmeans_visualization(titles, labels, num_clusters):
    traces = []

    for i in range(num_clusters):
        cluster_points = [title for idx, title in enumerate(titles) if labels[idx] == i]
        traces.append(go.Scatter(
            x=list(range(len(cluster_points))),
            y=[i] * len(cluster_points),  # Az y tengelyen a klaszter azonosítója van beállítva
            mode='markers+text',
            name=f'Klaszter {i}',
            text=cluster_points,
            marker=dict(
                color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                size=10,
                line=dict(width=1)
            )
        ))

    layout = go.Layout(
        title='Hírcikkek K-means Klaszterezése',
        xaxis=dict(title='Dokumentum Index'),
        yaxis=dict(title='Klaszter'),
        hovermode='closest'
    )

    fig = go.Figure(data=traces, layout=layout)
    return fig

# Szociogram készítése NetworkX segítségével
def create_social_network_graph(X, labels):
    G = nx.Graph()
    num_nodes = X.shape[0]

    # Csomópontok hozzáadása a gráfhoz
    for i in range(num_nodes):
        G.add_node(i, label=f"Cím {i}: {labels[i]}")

    # Élek hozzáadása a gráfhoz, a kapcsolatok erősségének ábrázolása érdekében
    similarity_matrix = cosine_similarity(X)
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if similarity_matrix[i, j] > 0.1:  # Csak a jelentős kapcsolatok hozzáadása
                G.add_edge(i, j, weight=similarity_matrix[i, j])

    # Szociogram rajzolása
    pos = nx.spring_layout(G)
    plt.figure(figsize=(12, 12))
    edges = G.edges(data=True)
    weights = [edge[2]['weight'] for edge in edges]
    nx.draw_networkx_nodes(G, pos, node_size=500, cmap=cm.get_cmap('viridis'))
    nx.draw_networkx_edges(G, pos, edgelist=edges, width=[weight * 5 for weight in weights], alpha=0.5)
    nx.draw_networkx_labels(G, pos, labels=nx.get_node_attributes(G, 'label'))
    plt.title('Hírek Szociogramja Klaszterekkel')
    plt.show()

@app.route('/visualize')
def visualize():
    # Az összes cím lekérdezése az adatbázisból
    with sqlite3.connect('news.db') as conn:
        c = conn.cursor()
        c.execute("SELECT title FROM news")
        titles = [row[0] for row in c.fetchall()]

    # Klaszterezés végrehajtása
    if titles:
        labels, centroids, X = perform_kmeans_clustering(titles, num_clusters=3)

        # Vizualizáció létrehozása
        fig = create_kmeans_visualization(titles, labels, num_clusters=3)
        div = plotly.offline.plot(fig, include_plotlyjs=False, output_type='div')

        # Szociogram készítése
        create_social_network_graph(X, labels)

        return render_template('visualization.html', plot_div=div)
    else:
        return "<h3>Nincs elérhető hír a vizualizációhoz.</h3>"

# HTML sablon a vizualizációhoz (templates/visualization.html)
# Ezt a HTML fájlt a templates könyvtárban kell létrehozni
"""
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <title>K-means Klaszterezés Vizualizáció</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <h1>Hírcikkek K-means Klaszterezése</h1>
    <div id="plotly-div">{{ plot_div|safe }}</div>
</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001, use_reloader=False)
