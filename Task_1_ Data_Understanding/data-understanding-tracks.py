import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import warnings

# Configuration
warnings.filterwarnings('ignore', category=FutureWarning)
sns.set_style("whitegrid")

#1. DATA LOADING
tracks_path = 'tracks.json'
try:
    tracks_df = pd.read_json(tracks_path, orient='records')
except ValueError:
    tracks_df = pd.read_json(tracks_path, lines=True)

print(f"Data Loaded. Shape: {tracks_df.shape}")
print(tracks_df.dtypes)

#2. MISSING VALUES ANALYSIS
print("\n Missing Values Analysis ")
missing_count = tracks_df.isnull().sum()
missing_df = pd.DataFrame({
    'Count': missing_count,
    'Percentage': (missing_count / len(tracks_df)) * 100
})
missing_df = missing_df[missing_df['Count'] > 0].sort_values(by='Percentage', ascending=False)

if not missing_df.empty:
    print(missing_df)
    
    # Heatmap Visualization
    plt.figure(figsize=(12, 8))
    colors = ["#FFA500", "#0c0b00"] 
    cmap = LinearSegmentedColormap.from_list("custom_cmap", colors, N=2)
    sns.heatmap(tracks_df.isnull().T, cbar=True, cmap=cmap, cbar_kws={'ticks': [0, 1]})
    plt.title("Heatmap of Missing Values")
    plt.xlabel("Data Rows")
    plt.xticks([])
    plt.tight_layout()
    plt.show() 
else:
    print("No missing values found.")

#3. EXPLICIT CONTENT
print("\n Explicit Content Analysis ")
tracks_df['explicit'] = tracks_df['explicit'].astype(bool)
explicit_counts = tracks_df['explicit'].value_counts()
num_explicit = explicit_counts.get(True, 0)
num_non = explicit_counts.get(False, 0)
ratio = num_explicit / num_non if num_non > 0 else float('inf')

print(f"Explicit: {num_explicit} | Non-Explicit: {num_non}")
print(f"Ratio (Explicit/Non): {ratio:.2f}")

# 4. DUPLICATES CHECK
print("\n Duplicates Analysis ")
dup_ids = tracks_df.duplicated(subset=['id'], keep=False).sum()
dup_complex = tracks_df.duplicated(subset=['id_artist', 'id', 'title'], keep=False).sum()
print(f"Rows with duplicated IDs: {dup_ids}")
print(f"Rows with duplicated [Artist, ID, Title]: {dup_complex}")

# 5. CORRELATION MATRIX
print("\n Correlation Matrix ")
numerical_cols = tracks_df.select_dtypes(include=[np.number]).columns.tolist()

if len(numerical_cols) > 1:
    corr_matrix = tracks_df[numerical_cols].corr()
    
    # Plotting
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    plt.figure(figsize=(14, 12))
    cmap = LinearSegmentedColormap.from_list("custom", ["black", "white", "#FFA500"], N=100)
    
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap=cmap, 
                mask=mask, vmin=-1, vmax=1, center=0, square=True)
    plt.title('Pearson Correlation Matrix')
    plt.tight_layout()
    plt.show()

# 6. RELATIONSHIP PLOTTING FUNCTION
def plot_aggregated_relation(df, group_col, value_col, agg_func='sum', top_n=30, 
                             chart_type='bar', sort_by_value=True, palette='viridis'):
    """
    Generic function to group, aggregate, and plot data.
    
    Args:
        agg_func: 'sum' for totals, 'mean' for averages.
        chart_type: 'bar' or 'line'.
        sort_by_value: True to sort by the metric (e.g., top artists), 
                       False to sort by the index (e.g., timeline by Year).
    """
    if group_col not in df.columns or value_col not in df.columns:
        print(f"Skipping plot: Columns {group_col} or {value_col} not found.")
        return
        
    clean_df = df.dropna(subset=[group_col]).copy()

    if group_col in ['year', 'month']:
        clean_df[group_col] = clean_df[group_col].astype(int)

    # Group and Aggregate
    agg_df = clean_df.groupby(group_col)[value_col].agg(agg_func).reset_index()
    
    # Sorting
    if sort_by_value:
        agg_df = agg_df.sort_values(by=value_col, ascending=False).head(top_n)
    else:
        # For time series, we usually want chronological order
        agg_df = agg_df.sort_values(by=group_col, ascending=True)

    # Plotting
    plt.figure(figsize=(15, 7))
    title = f"{agg_func.title()} of {value_col} by {group_col}"
    
    if chart_type == 'bar':
        ax = sns.barplot(x=group_col, y=value_col, data=agg_df, palette=palette)
        plt.xticks(rotation=90 if len(agg_df) > 15 else 45)
    elif chart_type == 'line':
        ax = sns.lineplot(x=group_col, y=value_col, data=agg_df, marker='o', color='purple')
        plt.grid(True, linestyle='--')

    # Formatting Y-axis with commas
    if ax.get_yaxis():
        ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    plt.title(title, fontsize=16)
    plt.xlabel(group_col, fontsize=12)
    plt.ylabel(value_col, fontsize=12)
    plt.tight_layout()
    plt.show()
    print(f"Plot generated: {title}")

# EXECUTE RELATIONSHIP PLOTS
print("\n Generating Aggregated Plots")
# 1. Albums Analysis
plot_aggregated_relation(tracks_df, 'id_album', 'streams@1month', 'sum', palette='viridis')
plot_aggregated_relation(tracks_df, 'id_album', 'popularity', 'mean', palette='plasma')
# 2. Artists Analysis
plot_aggregated_relation(tracks_df, 'primary_artist', 'streams@1month', 'sum', palette='viridis')
plot_aggregated_relation(tracks_df, 'primary_artist', 'popularity', 'mean', palette='plasma')
# 3. Languages Analysis
plot_aggregated_relation(tracks_df, 'language', 'streams@1month', 'sum', palette='viridis')
plot_aggregated_relation(tracks_df, 'language', 'popularity', 'mean', palette='plasma')
# 4. Temporal Analysis (Year) - Sort by Value=False to keep chronological order
plot_aggregated_relation(tracks_df, 'year', 'streams@1month', 'sum', sort_by_value=False, chart_type='bar')
plot_aggregated_relation(tracks_df, 'year', 'popularity', 'mean', sort_by_value=False, chart_type='line')
# 5. Temporal Analysis (Month)
# Pre-process Month Names for better display
if 'month' in tracks_df.columns:
    month_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    tracks_df['month_name'] = tracks_df['month'].map(month_map)
    # Define categorical order for months so sorting works by logic, not alphabetically
    month_order = list(month_map.values())
    tracks_df['month_name'] = pd.Categorical(tracks_df['month_name'], categories=month_order, ordered=True)
    
    plot_aggregated_relation(tracks_df, 'month_name', 'streams@1month', 'sum', sort_by_value=False, chart_type='bar')
    plot_aggregated_relation(tracks_df, 'month_name', 'popularity', 'mean', sort_by_value=False, chart_type='bar')

# 7. FEATURE DISTRIBUTIONS 
print("\n Audio Feature Distributions")
audio_features = ['bpm', 'rolloff', 'flux', 'rms', 'flatness', 'spectral_complexity', 'pitch', 'loudness']

for feature in audio_features:
    if feature in tracks_df.columns and tracks_df[feature].notnull().any():
        plt.figure(figsize=(8, 4))
        data = tracks_df[feature].dropna()
        sns.histplot(data, kde=True, bins=30)
        
        plt.axvline(data.mean(), color='red', linestyle='--', label=f'Mean: {data.mean():.2f}')
        plt.axvline(data.median(), color='green', linestyle='-', label=f'Median: {data.median():.2f}')
        
        plt.title(f'Distribution: {feature}')
        plt.legend()
        plt.tight_layout()
        plt.show()

print("\n Analysis Complete ")