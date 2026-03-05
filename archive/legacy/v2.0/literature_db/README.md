# Literature Reference Database

## Purpose

This folder contains reference data for validating discovered outcome factors against known quality-of-life constructs in development economics literature.

## Structure

### Known Constructs (from master instructions)

The literature database should define these 10+ canonical constructs:

1. **Health Outcomes**
   - Keywords: mortality, morbidity, life expectancy, disease
   - Typical indicators: infant_mortality, life_expectancy, u5_mortality
   - Canonical papers: Preston (1975), Bloom et al. (2004), Deaton (2003)

2. **Education Outcomes**
   - Keywords: schooling, literacy, enrollment, attainment
   - Typical indicators: years_schooling, completion_rates, test_scores
   - Canonical papers: Barro (1991), Hanushek & Woessmann (2012), Psacharopoulos & Patrinos (2018)

3. **Economic Prosperity**
   - Keywords: GDP, income, consumption, wealth
   - Typical indicators: gdp_per_capita, gni, household_consumption
   - Canonical papers: Solow (1956), Acemoglu & Robinson (2012)

4. **Security & Safety**
   - Keywords: violence, crime, conflict, homicide
   - Typical indicators: homicide_rate, conflict_deaths, crime_index
   - Canonical papers: Collier & Hoeffler (2004)

5. **Social Equity**
   - Keywords: inequality, Gini, poverty, distribution
   - Typical indicators: gini_index, poverty_headcount, income_share
   - Canonical papers: Piketty (2014), Deaton (2013)

6. **Infrastructure**
   - Keywords: roads, electricity, water, sanitation
   - Typical indicators: paved_roads_pct, electricity_access, improved_water
   - Canonical papers: Calderón & Servén (2010)

7. **Environment**
   - Keywords: emissions, pollution, deforestation, climate
   - Typical indicators: co2_emissions, pm25, forest_coverage
   - Canonical papers: Stern (2004)

8. **Governance Quality**
   - Keywords: democracy, corruption, rule of law, institutions
   - Typical indicators: polity_score, corruption_index, voice_accountability
   - Canonical papers: North (1990), Kaufmann et al. (2011)

9. **Nutrition**
   - Keywords: stunting, wasting, food security, malnutrition
   - Typical indicators: stunting_prevalence, dietary_energy, nutrition_index
   - Canonical papers: Black et al. (2013)

10. **Connectivity & Technology**
    - Keywords: internet, mobile, telecommunications, digital
    - Typical indicators: internet_penetration, mobile_subscriptions, broadband_access
    - Canonical papers: Jensen (2007)

## Usage in Pipeline

### B1: Outcome Discovery (Step B1)

The literature database is used in `find_best_matching_construct()`:

```python
def find_best_matching_construct(top_variables, known_constructs, literature_db):
    """
    Uses TF-IDF similarity between variable descriptions and construct keywords.
    Returns: {'label': 'health_outcomes', 'confidence': 0.87}
    """
    # 1. Extract variable descriptions
    descriptions = [get_variable_full_description(var) for var in top_variables]

    # 2. Compute TF-IDF similarity to each construct's keywords
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer()

    similarities = {}
    for construct, metadata in literature_db.items():
        construct_text = ' '.join(metadata['keywords'])
        corpus = descriptions + [construct_text]
        tfidf_matrix = vectorizer.fit_transform(corpus)

        # Cosine similarity between variables and construct
        from sklearn.metrics.pairwise import cosine_similarity
        sim = cosine_similarity(tfidf_matrix[:-1], tfidf_matrix[-1:]).mean()
        similarities[construct] = sim

    best_match = max(similarities, key=similarities.get)
    confidence = similarities[best_match]

    return {'label': best_match, 'confidence': confidence}
```

### Factor Validation Criteria

**ACCEPT** if:
- TF-IDF similarity > 0.60 to known construct
- Domain coherence (≤3 unique domains)
- Predictive R² > 0.40 (random forest cross-validation)

**CAUTION** if:
- 0.40 < TF-IDF similarity < 0.60 (novel factor, needs expert validation)

**REJECT** if:
- TF-IDF similarity < 0.40
- Or domain too scattered (>3 domains)
- Or unpredictable (R² < 0.40)

## File Format

Recommended format: `literature_constructs.json`

```json
{
  "health_outcomes": {
    "keywords": ["mortality", "morbidity", "life expectancy", "disease", "health", "longevity"],
    "typical_indicators": [
      "life_expectancy",
      "infant_mortality_rate",
      "under5_mortality_rate",
      "maternal_mortality_ratio",
      "disease_burden"
    ],
    "canonical_papers": [
      "Preston, S. H. (1975). The changing relation between mortality and level of economic development. Population Studies, 29(2), 231-248.",
      "Bloom, D. E., Canning, D., & Sevilla, J. (2004). The effect of health on economic growth: a production function approach. World Development, 32(1), 1-13.",
      "Deaton, A. (2003). Health, inequality, and economic development. Journal of Economic Literature, 41(1), 113-158."
    ],
    "domain": "Health"
  },
  "education_outcomes": {
    "keywords": ["schooling", "literacy", "enrollment", "attainment", "education", "learning"],
    "typical_indicators": [
      "mean_years_schooling",
      "primary_completion_rate",
      "secondary_enrollment",
      "tertiary_enrollment",
      "literacy_rate",
      "test_scores"
    ],
    "canonical_papers": [
      "Barro, R. J. (1991). Economic growth in a cross section of countries. The Quarterly Journal of Economics, 106(2), 407-443.",
      "Hanushek, E. A., & Woessmann, L. (2012). Do better schools lead to more growth? Cognitive skills, economic outcomes, and causation. Journal of Economic Growth, 17(4), 267-321.",
      "Psacharopoulos, G., & Patrinos, H. A. (2018). Returns to investment in education: a decennial review of the global literature. Education Economics, 26(5), 445-458."
    ],
    "domain": "Education"
  }
  // ... 8 more constructs
}
```

## Maintenance

- **Update**: When new development economics papers establish new canonical relationships
- **Versioning**: Track changes in `literature_db_changelog.md`
- **Validation**: Cross-reference with recent World Development reports and UNDP HDR

## V1 Validated Outcomes

These 8 outcomes from V1 should be **anchors** (must be reproduced in V2):

1. life_expectancy
2. years_schooling
3. gdp_per_capita
4. infant_mortality
5. gini_index
6. homicide_rate
7. nutrition_index
8. internet_access

Assert: `v1_reproduced >= 6 out of 8` in validation (see `v2_master_instructions.md` line 618).
