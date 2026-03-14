# Recommendation Quality Checks

## Correlations

- Correlation between predicted rating and true rating: 0.8311
- Correlation between predicted rating and popularity (`totalratings`): 0.0271

## Genre diversity in top-N list

Primary-genre distribution among top-N recommendations:

- Religion: 4
- Unknown: 3
- Fantasy: 2
- History: 2
- European Literature: 2
- Christianity: 1
- Young Adult: 1
- Humanities: 1
- Mystery: 1
- Reference: 1
- Sequential Art: 1
- Occult: 1

Most frequent primary genre in top-N: Religion (20.0% of top-N)

## Popularity bias

Comparison of mean `totalratings` (a proxy for popularity) for all books vs. only the top-N recommended books:

- Mean `totalratings` for all books: 2990.79
- Mean `totalratings` for top-N books: 1809.60
