import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation

import nltk
from nltk.corpus import stopwords

# CONFIGURATION 
FILE_IN = "tracks_final.json"
FILE_OUT = "tracks_cluster_final.json"

AUDIO_FEATURES = [
    "bpm", "rolloff", "flux", "rms", "flatness",
    "spectral_complexity", "pitch", "loudness",
]

CLUSTER_NAMES = {
    0: "The Pure Tonal",
    1: "The High Energy",
    2: "The Mellow",
    3: "The Complex",
}
TOPIC_NAMES = {
    0: "Trap Gang Life",
    1: "Neapolitan Rap",
    2: "Street Trap Vibes",
    3: "Italian Rap Life",
}

N_TOPICS = 4
RANDOM_STATE = 42
# -------------------------------------------------------------------------
def load_and_scale(file_path: str, feature_cols: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    df = pd.read_json(file_path)
    X = df[feature_cols].to_numpy()
    X = SimpleImputer(strategy="median").fit_transform(X)
    X = StandardScaler().fit_transform(X)
    return df, X

def evaluate_kmeans(X: np.ndarray, k_min: int = 2, k_max: int = 10) -> tuple[list[int], list[float]]:
    ks, wcss = [], []
    print("Silhouette scores:")
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=RANDOM_STATE)
        km.fit(X)
        ks.append(k)
        wcss.append(km.inertia_)
        sil = silhouette_score(X, km.labels_)
        print(f"  k={k}: silhouette={sil:.4f}")
    return ks, wcss

def plot_elbow(ks: list[int], wcss: list[float]) -> None:
    plt.figure(figsize=(9, 5))
    plt.plot(ks, wcss, marker="o", linestyle="--")
    plt.title("Elbow Method (WCSS)")
    plt.xlabel("k"); plt.ylabel("WCSS (Inertia)")
    plt.xticks(ks); plt.grid(True, linestyle=":", alpha=0.7)
    plt.show()

def plot_pca_scatter(X: np.ndarray, labels: np.ndarray) -> None:
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    X2 = pca.fit_transform(X)
    plt.figure(figsize=(9, 6))
    sc = plt.scatter(X2[:, 0], X2[:, 1], c=labels, alpha=0.6, s=30)
    plt.title("K-Means (k=4) – PCA(2D) view")
    plt.xlabel("PC1"); plt.ylabel("PC2")
    plt.legend(*sc.legend_elements(), title="Cluster")
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.show()

def plot_tsne_scatter(X: np.ndarray, labels: np.ndarray) -> None:
    n = X.shape[0]
    # keep perplexity valid & stable
    perplexity = min(30, max(5, (n - 1) // 3))
    tsne = TSNE(
        n_components=2,
        random_state=RANDOM_STATE,
        init="pca",
        learning_rate="auto",
        perplexity=perplexity,
    )
    X2 = tsne.fit_transform(X)
    plt.figure(figsize=(9, 6))
    sc = plt.scatter(X2[:, 0], X2[:, 1], c=labels, alpha=0.6, s=30)
    plt.title(f"K-Means (k=4) – t-SNE(2D) view (perplexity={perplexity})")
    plt.xlabel("t-SNE 1"); plt.ylabel("t-SNE 2")
    plt.legend(*sc.legend_elements(), title="Cluster")
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.show()

def plot_centroids(feature_names: list[str], centers: np.ndarray) -> None:
    n_features = centers.shape[1]
    plt.figure(figsize=(16, 5))
    for i in range(len(centers)):
        plt.plot(range(n_features), centers[i], marker="o", linewidth=2, label=f"Cluster {i}")
    plt.xticks(range(n_features), feature_names)
    # z-score baseline
    plt.axhline(0.0, color="black", linestyle="--", linewidth=1, alpha=0.5)
    plt.title("Cluster Centroids (standardized features)")
    plt.ylabel("Z-Score")
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    plt.legend()
    plt.show()

def build_multilingual_stopwords() -> list[str]:
    nltk.download("stopwords", quiet=True)
    langs = ["english", "italian", "french", "german", "spanish", "portuguese", "dutch"]
    words = set()
    for lang in langs:
        try:
            words.update(stopwords.words(lang))
        except OSError:
            # missing language pack -> skip
            pass
    words.update([
        "yeah", "oh", "ooh", "ah", "uh", "na", "la", "da", "baby",
        "got", "wanna", "gonna", "hey", "whoa", "chorus", "verse", "intro", "outro",
    ])
    return sorted(words)

def print_top_words(model: LatentDirichletAllocation, vocab: np.ndarray, n: int) -> None:
    print("-" * 60)
    print(f"Top {n} words for each of the {len(model.components_)} topics:")
    print("-" * 60)
    for i, topic in enumerate(model.components_):
        top_idx = topic.argsort()[:-n - 1:-1]
        print(f"Topic #{i + 1}: " + ", ".join(vocab[top_idx]))
    print("-" * 60)

def main() -> None:
    print("Loading & preprocessing audio features...")
    df, X = load_and_scale(FILE_IN, AUDIO_FEATURES)
    print(f"Data shape: {df.shape}; features used: {len(AUDIO_FEATURES)}")

    #  Melodic profiling
    ks, wcss = evaluate_kmeans(X, 2, 10)
    plot_elbow(ks, wcss)

    print("Fitting final KMeans with k=4 (fixed mapping)...")
    kmeans = KMeans(n_clusters=4, init="k-means++", n_init=10, random_state=RANDOM_STATE).fit(X)
    labels = kmeans.labels_
    plot_pca_scatter(X, labels)
    plot_tsne_scatter(X, labels)
    plot_centroids(AUDIO_FEATURES, kmeans.cluster_centers_)

    df["melodic_type"] = pd.Series(labels).map(CLUSTER_NAMES)
    print("Melodic type distribution:")
    print(df["melodic_type"].value_counts())

    # Lyrics profiling
    print("\nVectorizing multilingual lyrics with TF-IDF...")
    stop_words = build_multilingual_stopwords()
    valid_lyrics = df["lyrics"].apply(lambda t: isinstance(t, str) and len(t) > 10)
    x_train = df.loc[valid_lyrics, "lyrics"].tolist()

    tfidf_vectorizer = TfidfVectorizer(
        stop_words=stop_words,
        max_df=0.90,
        min_df=2,
        max_features=5000,
        ngram_range=(1, 2),
    )
    tfidf = tfidf_vectorizer.fit_transform(x_train)
    print(f"TF-IDF shape (songs x tokens): {tfidf.shape}")

    lda_tfidf = LatentDirichletAllocation(
        n_components=N_TOPICS,
        max_iter=20,
        learning_method="batch",
        n_jobs=-1,
        verbose=1,
        random_state=RANDOM_STATE,
    ).fit(tfidf)

    try:
        tfidf_feature_names = tfidf_vectorizer.get_feature_names_out()
    except AttributeError:
        tfidf_feature_names = tfidf_vectorizer.get_feature_names()

    print_top_words(lda_tfidf, tfidf_feature_names, 15)
    print_top_words(lda_tfidf, tfidf_feature_names, 50)

    topic_probs = lda_tfidf.transform(tfidf)
    topic_idx = topic_probs.argmax(axis=1)

    df["lyrics_topic"] = "Unknown/No Lyrics"
    df.loc[valid_lyrics, "lyrics_topic"] = pd.Series(topic_idx, index=df.index[valid_lyrics]).map(TOPIC_NAMES)

    print("-" * 40)
    print("Lyrics topic assignment complete! (TF-IDF + LDA)")
    print(f"Total songs: {len(df)} | Classified: {valid_lyrics.sum()}")
    print("-" * 40)

    cols = [c for c in ["id", "melodic_type", "lyrics_topic"] if c in df.columns]
    print("First 5 rows:")
    print(df[cols].head())

    df.to_json(FILE_OUT, orient="records", indent=4, force_ascii=False)
    print(f"SUCCESS: saved final file → {FILE_OUT}")


if __name__ == "__main__":
    main()
