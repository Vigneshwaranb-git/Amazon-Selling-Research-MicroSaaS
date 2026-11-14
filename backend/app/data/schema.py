"""SQLite schema and constants shared by the importer and DatasetProductDataProvider."""

from pathlib import Path

DATASET_NAME = "Amazon Reviews 2023"
DATASET_VERSION = "Amazon-Reviews-2023 (McAuley Lab, UCSD)"
SCHEMA_VERSION = "1"

# End of the dataset's coverage ("May 1996 to Sep 2023"). Prices and BSRs are crawl-time
# snapshots taken on or before this date; we label them with it rather than with "now".
DATASET_AS_OF = "2023-09-30"

BASE_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
META_URL = BASE_URL + "/meta_categories/meta_{category}.jsonl.gz"
REVIEWS_URL = BASE_URL + "/review_categories/{category}.jsonl.gz"

DEFAULT_DATASET_PATH = "data/amazon_reviews_2023.sqlite"
# <repo>/backend/app/data/schema.py -> <repo>. Relative dataset paths resolve against it, so the
# importer and the app agree on the file no matter which directory they are started from.
REPO_ROOT = Path(__file__).resolve().parents[3]


def resolve_dataset_path(path: str | Path) -> Path:
    """Absolute paths are kept; relative ones are relative to the repository root."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


ATTRIBUTION = (
    "Product and review data: Amazon Reviews 2023, McAuley Lab, UC San Diego "
    "(Hou et al., 'Bridging Language and Items for Retrieval and Recommendation', "
    "arXiv:2403.03952), https://amazon-reviews-2023.github.io/. Snapshot data ends Sep 2023. "
    "For demonstration and research purposes."
)

LICENCE_NOTICE = (
    "The Amazon Reviews 2023 dataset has no explicit licence: its maintainers state they are "
    "'not in a position to assign a license' and made it available primarily for research. "
    "Review text, titles and images were written by Amazon customers/sellers. Commercial use "
    "is unresolved; obtain written permission from the authors (see the dataset card) before "
    "using it in a paid product. Do not redistribute the downloaded data. This application is "
    "not affiliated with Amazon."
)

SCHEMA_SQL = """
CREATE TABLE products (
    asin TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    category_path TEXT NOT NULL DEFAULT '',
    main_category TEXT NOT NULL DEFAULT '',
    price REAL NOT NULL,
    bsr INTEGER NOT NULL,
    bsr_category TEXT NOT NULL DEFAULT '',
    bsr_sub INTEGER,
    bsr_sub_category TEXT NOT NULL DEFAULT '',
    rating REAL NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    image_url TEXT NOT NULL DEFAULT '',
    reviews_seen INTEGER NOT NULL DEFAULT 0,
    reviews_last12 INTEGER NOT NULL DEFAULT 0,
    reviews_prior12 INTEGER NOT NULL DEFAULT 0,
    rating_last12 REAL,
    rating_prior12 REAL,
    reviews_per_year TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_products_bsr ON products (bsr);
CREATE INDEX idx_products_category ON products (category);
CREATE TABLE reviews (
    id TEXT PRIMARY KEY,
    asin TEXT NOT NULL,
    rating INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    ts INTEGER NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_reviews_asin_ts ON reviews (asin, ts DESC);
CREATE TABLE category_stats (
    category TEXT PRIMARY KEY,
    n_products INTEGER NOT NULL
);
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def import_command(category: str = "Appliances") -> str:
    """The exact command that builds the default dataset file (used in errors and docs)."""
    return f"python -m app.data.import_amazon_2023 --category {category} --max-products 3000"
