# Explainable Book Recommender System on Goodreads 100K

## 1. Problem and Setup

**Research question.**  
Can SHAP-based explanations provide meaningful, stable, and human-understandable justifications for recommendations in a book recommender system?

**Formulation.**  
Because the available Goodreads 100K dataset contains only book-level metadata, not user–book interaction logs, the problem is framed as:

- Predicting a book’s average rating from interpretable features such as popularity, genre, book format, and length.
- Using the predicted ratings as a basis for global (non-personalised) recommendations.
- Applying SHAP to understand which features drive these predicted ratings.

## 2. Data, Features, and Model

**Data.**  
- Source: Kaggle `mdhamani/goodreads-books-100k`.  
- Single table with ~100k books and columns including `rating`, `totalratings`, `reviews`, `pages`, `genre`, `bookformat`, and textual metadata.

**Key engineered features.**
- `ratings_count`: numeric popularity signal derived from `totalratings`.
- `log_ratings_count`: `log1p(ratings_count)` to compress the heavy tail.
- `pages`: imputed median-by-primary-genre (with a global median fallback) and hard-capped at 2000.
- `reviews`: number of text reviews.
- Multi-hot genre indicators for the 50 most frequent genres, derived from the comma-separated `genre` field.
- One-hot book format indicators (e.g., `format_Hardcover`, `format_Paperback`).

**Model.**  
- Tree-based regressor: XGBoost with lightweight hyperparameter tuning over depth, learning rate, and number of estimators.
- Train/validation/test split over books (70/15/15).

**Performance (test set).**
- Baseline (global mean): RMSE ≈ 0.633, MAE ≈ 0.364, R² ≈ 0.
- Tuned XGBoost:
  - RMSE ≈ **0.356**
  - MAE ≈ **0.256**
  - R² ≈ **0.655**

The model explains roughly two thirds of the variance in average book ratings and reduces RMSE by ~44% relative to the baseline.

## 3. Recommendation Behaviour

Predicted ratings are used to produce both a **global top-N list** and **personalised lists for synthetic user profiles**.

**General behaviour (global list).**
- Correlation between predicted and true ratings: **≈ 0.83**, indicating that top-predicted books tend to be highly rated in the data.
- Correlation between predicted rating and `totalratings`: **≈ 0.03**, suggesting that the model does not simply recommend the most popular books.

**Diversity (global list).**
- Among the top-20 recommended books, primary genres include Religion, Unknown, History, Fantasy, European Literature, Christianity, Young Adult, Humanities, Sequential Art, Reference, Mystery, and Occult.
- The most frequent primary genre (Religion) accounts for only ~20% of the list, so recommendations are not dominated by a single genre.

**Synthetic user profiles.**
- Five hand-crafted “users” are defined (e.g., `fantasy_fan`, `romance_reader`, `literary_reader`) with genre preference weights and a coarse length preference (short/medium/long books).
- For each profile, the system adjusts the model’s predicted rating by a weighted genre match score and a length penalty/bonus, then ranks books to obtain personalised top-N lists.
- Example: the `fantasy_fan` profile upweights Fantasy and related genres and mildly prefers longer books; its top recommendations are dominated by Fantasy and Young Adult Fantasy titles, whereas the `romance_reader` list focuses on Romance and Contemporary Romance.

## 4. SHAP-Based Explanations

### 4.1 Global Insights

The SHAP global bar plot shows the following top features by mean absolute SHAP value:

1. `ratings_count`
2. `reviews`
3. `pages`
4. `genre_Fiction`
5. `log_ratings_count`
6. `genre_Romance`
7. `genre_Christian`
8. `genre_Religion`
9. `genre_Art`
10. `genre_European_Literature`
… (other genre and format indicators follow).

**Interpretation.**

- **Popularity and engagement matter.**  
  `ratings_count`, `log_ratings_count`, and `reviews` are the strongest drivers. Books with many ratings and reviews receive higher predicted scores, but the low correlation between predictions and `totalratings` indicates that popularity is informative rather than overwhelming.

- **Content signals via genre are important.**  
  Multiple genre indicators (`genre_Fiction`, `genre_Romance`, `genre_Christian`, `genre_Religion`, `genre_Art`, `genre_European_Literature`, etc.) appear among the most influential features. This suggests that genre carries systematic information about typical rating levels.

- **Book length has a moderate effect.**  
  `pages` is a strong feature: for some genres (e.g., long reference works, omnibus editions) very large books tend to garner higher or lower ratings than average. The hard cap at 2000 pages prevents a few extreme values from dominating.

Overall, the model combines **popularity/engagement features** with **genre and format** to explain ratings.

### 4.2 Local Example Explanations

Two types of local SHAP explanations were generated: (1) for highly rated books in the test set, and (2) for top-ranked books under specific synthetic user profiles (e.g., “why this book for the fantasy fan?”).

- For highly rated, well-known titles (global perspective):
  - Large positive contributions from `ratings_count`, `log_ratings_count`, and `reviews`.
  - Positive contributions from genres like `genre_Fiction`, `genre_Fantasy`, or `genre_Romance` when they historically correlate with higher ratings.
  - Slight negative adjustments if the book is extremely long (`pages`) or belongs to genres with more variable quality.

- For niche but well-received books:
  - Smaller but still positive `ratings_count` and `reviews` contributions.
  - Strong positive contributions from specific genres (e.g., `genre_Religion`, `genre_Art`, `genre_European_Literature`) indicating that certain specialised domains tend to receive high evaluations from their audiences.

- For synthetic user recommendations:
  - The underlying SHAP attributions remain book-level (the model does not change per user), but the books surfaced for each profile align with that profile’s genre and length preferences.
  - Explanations can therefore be phrased in a user-centric way, e.g., “this book is recommended for the fantasy fan because it is a highly rated Fantasy/Young Adult Fantasy title with many ratings and reviews.”

In all inspected examples, the top contributing features are **intuitively plausible** (popularity, reviews, and relevant genres), which makes the explanations easy to read and justify.

### 4.3 Overview of Generated SHAP Plots

To support the qualitative analysis above, several SHAP visualisations were generated and are attached to the project:

- **Global summary beeswarm (`results/shap/global/shap_summary_beeswarm.png`).**  
  Shows the distribution of SHAP values for the most important features across a random subset of books. Each point is a book; colour encodes feature value (e.g., high vs low `ratings_count`). This plot reveals how high vs low values of a feature tend to push predictions up or down.

- **Global summary bar plot (`results/shap/global/shap_summary_bar.png`).**  
  Ranks features by mean absolute SHAP value, providing a compact view of global importance (used to produce the ordered list in Section 4.1).

- **Local waterfall plots for high-prediction books (e.g., `results/shap/local/waterfall_example_2864.png`, `..._9942.png`).**  
  For selected highly rated books in the test set, these plots decompose the prediction into the base value plus successive feature contributions, highlighting which features most increase or decrease the prediction for that specific book.

- **Local waterfall plots for synthetic user recommendations (e.g., `results/shap/local/user_fantasy_fan_rank2_book_15121.png`, `user_fantasy_fan_rank4_book_10822.png`).**  
  For books that appear near the top of a synthetic user’s personalised list, these plots explain why the underlying model assigns them high predicted ratings. When read together with the user profile definition (e.g., strong Fantasy preference), they provide user-centric narratives such as “this book is recommended for the fantasy fan because it is a highly rated Fantasy title with many ratings and reviews.”

## 5. Evaluation Against the Research Question

### 5.1 Genre–Preference Alignment

The original project framing referred to user–genre alignment. The available dataset does not include user identifiers, so **true user preference profiles cannot be estimated**. Instead, we interpret “preference” at the aggregate level:

- Genre indicators appear prominently among the most important features, which shows that the model recognises that certain genres (e.g., Fiction, Romance, Christian/Religion, European Literature) are typically associated with higher or lower average ratings.
- Local SHAP explanations for top-predicted books highlight their genres among the main positive contributors, indicating that “this book is highly rated partly because it belongs to a genre that tends to receive high ratings.”

Thus, genre information is clearly aligned with the model’s notion of “preference”, albeit at the level of the overall readership rather than individual users.

### 5.2 Influence of Popularity and Average Ratings

- SHAP shows `ratings_count`, `reviews`, and `log_ratings_count` as the most important features.
- However:
  - The correlation between predicted rating and popularity (`totalratings`) is low (~0.03).
  - Global and local explanations also emphasise genre and, to a lesser extent, format and length.

This indicates that **popularity is influential but not dominant**. The model tends to favour books that are both:

- well-received (high `rating`), and
- reasonably popular (`ratings_count`, `reviews`),  

but popularity alone is not sufficient to generate a high predicted rating.

### 5.3 Behaviour Patterns and Stability

Because user identifiers are absent, we cannot directly study lenient vs strict raters. Instead we examine stability from two angles:

1. **Consistency across similar books.**  
   Books sharing similar genres and popularity profiles tend to have similar SHAP profiles. For example, multiple highly rated religious reference works show:
   - strong positive contributions from `genre_Christian` / `genre_Religion`,
   - strong positive contributions from `ratings_count` and `reviews`,
   - small contributions from format indicators.

2. **Robustness of explanations.**  
   Across different random subsets of the test data (beeswarm plots inspected qualitatively), the ordering of the top features is stable: the same small set of features dominates global importance.

This supports the view that SHAP explanations are reasonably stable for this model and dataset, though no formal numeric stability metric was computed.

### 5.4 Explanation Quality: Meaningfulness and Human-Understandability

- **Meaningfulness.**  
  The top SHAP features—popularity measures, genre indicators, and pages—are all readily interpretable and have clear, literature-based justifications for why they should affect ratings.

- **Human-understandability.**  
  Waterfall plots tell simple stories such as:
  > “This book is predicted to have a high rating because it has many ratings and reviews, belongs to a genre that tends to be well-liked, and has a typical page count.”

  This style of explanation is accessible to non-technical stakeholders (e.g., librarians, editors) and can be directly embedded into recommendation interfaces.

- **Limitations.**
  - Explanations are at the **book level only**; personalisation is approximated via synthetic user profiles rather than learned from real user histories.
  - Genre indicators derived from a single `genre` string are imperfect and may omit nuanced subgenres.
  - SHAP currently relies on a small compatibility workaround for XGBoost 3.x (parsing the model’s `base_score` correctly); this does not affect qualitative conclusions but is a reminder that tooling versions matter.

## 6. Conclusions and Future Work

**Answer to the research question.**  
Within the constraints of the available data, SHAP-based explanations **do provide meaningful, stable, and human-understandable justifications** for book recommendations:

- They consistently highlight interpretable drivers: popularity/engagement and genre.
- They remain stable across different subsets of the data.
- They can be summarised in simple narratives for each recommended book.

**Key takeaways.**

1. A tree-based model trained on interpretable book features can predict average ratings with good accuracy (RMSE ≈ 0.36, R² ≈ 0.65).
2. SHAP reveals that both **popularity signals** and **genre information** are central to these predictions.
3. Recommendations derived from the model are diverse and not solely driven by popularity.
4. Simple synthetic user profiles allow book-level SHAP explanations to be reused as user-facing narratives (e.g., “why this book fits the fantasy fan”), even without true user interaction data.

**Future work.**

- Incorporate **user–book interaction data** to build truly personalised recommendations and user-level explanations (e.g., “because you like X and Y, and often rate Z highly”).
- Extend features with richer text-derived signals (embeddings or keyword-based themes) while keeping explanations interpretable.
- Compute quantitative stability metrics for SHAP explanations (e.g., cosine similarity of SHAP vectors for near-duplicate books) and compare to alternative explanation methods.
- Compare different model families (LightGBM, CatBoost, linear models) to assess whether explanation quality or stability changes even when accuracy is similar).

﻿