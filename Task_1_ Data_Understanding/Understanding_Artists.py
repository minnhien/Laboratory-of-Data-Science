import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import CountVectorizer
import os

df = pd.read_xml("artists.xml")

df.info()
# Replace empty/None values once
df = df.replace(['', 'None', None], pd.NA)

# Calculate Missing Percentage
total_rows = len(df)
missing_report = pd.DataFrame({
    'Missing Count': df.isnull().sum(),
    'Percentage (%)': (df.isnull().sum() / total_rows * 100).round(2)
}).sort_values(by='Percentage (%)', ascending=False)

# Convert date columns
date_cols = ["birth_date", "active_start", "active_end"]
for col in date_cols:
    df[col] = pd.to_datetime(df[col], errors="coerce")

# Derived Columns (Age based on 2025)
df['age'] = 2025 - df['birth_date'].dt.year
df['active_year'] = df['active_start'].dt.year


# Frequency Counts
counts = {
    "gender": df['gender'].value_counts(dropna=False),
    "region": df['region'].dropna().value_counts(),
    "country": df['country'].dropna().value_counts(),
    "nationality": df['nationality'].dropna().value_counts(),
    "birth_place": df['birth_place'].value_counts().head(20)
}

# Text Analysis
descriptions = df["description"].fillna("").astype(str)
vectorizer = CountVectorizer(lowercase=True)
X = vectorizer.fit_transform(descriptions)
word_counts = pd.Series(X.toarray().sum(axis=0), index=vectorizer.get_feature_names_out()).sort_values(ascending=False)

# VISUALIZATIONS

def create_plots(df, counts):
    # Figure 1: Missing Data Heatmap
    plt.figure(figsize=(12, 5))
    sns.heatmap(df.isnull(), yticklabels=False, cbar=False, cmap='magma')
    plt.title('Data Completeness Map (Bright = Missing)')
    plt.tight_layout(); plt.savefig('missing_data_heatmap.png'); plt.show()

    # Figure 2:  Gender Distribution
    plt.figure(figsize=(8, 6))
    sns.barplot(x=counts["gender"].index, y=counts["gender"].values, palette="pastel")
    plt.title('Gender Distribution', fontsize=14)
    plt.xlabel('Gender'); plt.ylabel('Count')
    plt.tight_layout(); plt.savefig('gender_distribution.png'); plt.show()

    # Figure 3:  Region Distribution
    plt.figure(figsize=(12, 8))
    sns.barplot(x=counts["region"].values, y=counts["region"].index, palette="viridis")
    plt.title('Distribution of Artists by Region', fontsize=16)
    plt.xlabel('Count'); plt.ylabel('Region')
    plt.tight_layout(); plt.savefig('region_distribution.png'); plt.show()

    # Figure 4: Country & Nationality Distributions 
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    sns.barplot(x=counts["country"].index, y=counts["country"].values, ax=axes[0], color="orange")
    axes[0].set_title("Artists by Country")
    
    sns.barplot(x=counts["nationality"].index, y=counts["nationality"].values, ax=axes[1], color="plum")
    axes[1].set_title("Artists by Nationality")
    plt.tight_layout(); plt.savefig('country_nationality.png'); plt.show()

    # Figure 5: Age Analysis
    plt.figure(figsize=(12, 6))
    plot_df = df.dropna(subset=['age', 'region'])
    sns.stripplot(data=plot_df, x='age', y='region', hue='gender', jitter=True, size=7, alpha=0.6)
    sns.pointplot(data=plot_df, x='age', y='region', estimator=np.mean, join=False, color='black', markers='D', scale=0.5)
    plt.title('Age Distribution by Region (with Means)')
    plt.tight_layout(); plt.savefig('age_region_scatter.png'); plt.show()



create_plots(df, counts)

print(f"\nMissing Data Report:\n{missing_report}")
print(f"Total Artists: {len(df)}")
print(f"Average Age: {df['age'].mean():.1f} years")
print(f"Artists with full timeline data: {df.dropna(subset=['age', 'active_year']).shape[0]}")
print("\nTop 10 Description Keywords:")
print(word_counts.head(20))