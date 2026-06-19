# Rule-based blocklist — fast first pass
DISALLOWED_PATTERNS = [
    # Gender
    r"\bmale\b", r"\bfemale\b", r"\bhe/him\b", r"\bshe/her\b",
    r"\bgentlemen\b", r"\bwomen only\b", r"\bmen only\b",
    # Age
    r"\bunder \d{2}\b", r"\bover \d{2}\b", r"\bage limit\b",
    r"\byoung\b", r"\bfresh graduate\b.*\bonly\b", r"\b\d{2}-\d{2} years old\b",
    # Religion
    r"\bchristian\b", r"\bmuslim\b", r"\bhindu\b", r"\bjewish\b",
    r"\bcatholic\b", r"\bbuddhist\b",
    # Ethnicity / Race
    r"\bwhite\b.*\bpreferred\b", r"\basian\b.*\bonly\b",
    r"\brethnicity\b.*\bpreferred\b",
    # Marital / Family
    r"\bmarried\b.*\bpreferred\b", r"\bsingle\b.*\bpreferred\b",
    r"\bno children\b",
    # Nationality
    r"\blocal candidates only\b", r"\bcitizens only\b",
]

SHORTLIST_N = 10

INDEX_DIMENSION = 384
TOP_K_RETRIEVE = 50       # initial retrieval pool
TOP_K_RERANK = 20         # after re-ranking
IVFFLAT_LISTS   = 50

INDEX_NAME = "recruitment_profiles"

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "candidate_id": {"type": "keyword"},
            "name": {"type": "text"},
            "email": {"type": "keyword"},
            "location": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "skills": {"type": "text", "analyzer": "standard"},
            "skills_keyword": {"type": "keyword"},
            "experience_years": {"type": "float"},
            "summary": {"type": "text"},
            "employment_text": {"type": "text"},
            "education_text": {"type": "text"},
            "sources": {"type": "keyword"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}
