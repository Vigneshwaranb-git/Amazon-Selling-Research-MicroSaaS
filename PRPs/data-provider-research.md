# Open-data provider research for ProductDataProvider

Date: 2026-11-14. Author: RESEARCH-AGENT. No application files were changed.
Tags: [VERIFIED] = checked against a primary source or a live request from this machine. [UNVERIFIED] = secondary or not checked.

## 1. What the provider must supply (from backend/app/services/providers/base.py and mock.py)

| Method | Returns | Fields |
|---|---|---|
| get_product(asin) | ProductData | asin, title, brand, category, price (Decimal), bsr (int), rating, review_count, monthly_sales_estimate, seller_count, image_url |
| search_products(keyword, category, limit) | list[ProductData] | same |
| get_bsr_history(asin, days) | list[BSRPoint] | day, bsr, price |
| get_reviews(asin, limit) | list[Review] | id, rating (int), title, body, reviewed_at (date) |

`ProductData.bsr`, `price`, `monthly_sales_estimate` and `seller_count` are non-optional, so a dataset provider needs a policy for missing values. See section 4.

## 2. Candidates

### 2.1 Amazon Reviews 2023 (McAuley Lab, UCSD) - best fit
- Sources: https://amazon-reviews-2023.github.io/ and https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023 [VERIFIED].
- Coverage: May 1996 to Sep 2023, 571.5M reviews, 48.2M items, 33 categories [VERIFIED].
- Format: gzipped JSON Lines. The download URLs below returned HTTP 200 from this machine [VERIFIED].
  - Reviews: `https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/<Category>.jsonl.gz`
  - Metadata: `https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/meta_<Category>.jsonl.gz`
  - Hugging Face mirror (uncompressed, with an HTTP 302 to a CDN): `https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/{review,meta}_categories/...jsonl`. The HF copy of Appliances reviews is 929 MB uncompressed [VERIFIED].
  - The HF loader needs `trust_remote_code`. Use the direct `.jsonl.gz` URLs instead.
- Real sizes (Content-Length from HEAD requests, 2026-11-14) [VERIFIED]:

| Category | Items (site table) | Meta .gz | Reviews .gz | Reviews (site table) |
|---|---|---|---|---|
| Subscription_Boxes | 641 | 0.28 MB | 2.7 MB | 16.2K |
| Gift_Cards | 1.1K | 0.32 MB | 12.3 MB | 152K |
| Magazine_Subscriptions | 3.4K | 0.68 MB | 10.0 MB | 71.5K |
| Health_and_Personal_Care | 60.3K | 23.3 MB | 69.5 MB | 494K |
| All_Beauty | 112.6K | 39.9 MB | 94.4 MB | 701K |
| Handmade_Products | 164.7K | 94.4 MB | 77.8 MB | 664K |
| Appliances | 94.3K | 66.4 MB | 270 MB | 2.1M |
| Software | 89.2K | 64.2 MB | 496 MB | 4.9M |
| Industrial_and_Scientific | 427.5K | 282 MB | 676 MB | 5.2M |
| Pet_Supplies | n/a | 400 MB | 2.33 GB | n/a |
| Toys_and_Games | n/a | 659 MB | 1.95 GB | n/a |
| Home_and_Kitchen | n/a | 2.96 GB | 8.31 GB | n/a |

  Item and review counts come from the site table. The sizes are from HEAD requests.
- Review schema [VERIFIED by sampling Subscription_Boxes]: rating (float), title, text, images, asin, parent_asin, user_id, timestamp (Unix time in MILLISECONDS), helpful_vote, verified_purchase. The sample ran 2017-01 to 2023-08.
- Metadata schema [VERIFIED by streaming the first 30 MB of meta_Appliances.jsonl.gz, 38,129 records]: main_category, title, average_rating, rating_number, features, description, price, images (each with thumb, large, hi_res and variant), videos, store, categories (path list), details (dict), parent_asin, bought_together.
  - Field fill rates in that Appliances sample:

| Field | Fill rate |
|---|---|
| average_rating, rating_number, parent_asin | 100% |
| title | 99.97% |
| images | 99.99% |
| categories | 96.6% |
| details | 99.7% |
| price | 54.6% |
| `details["Best Sellers Rank"]` | 65.6% (25,026) |
| `details["Brand"]` | 46% (17,691) |

  - `details["Best Sellers Rank"]` is a dict of `{category or subcategory name: rank}`. Example: `{"Tools & Home Improvement": 246177, "Refrigerator Egg Trays": 288}`. `details` also has Manufacturer, Date First Available and Item Weight.
  - For brand, use `details.Brand`, then `store`, then Manufacturer.
  - There is no seller count and no offers list.
  - The price and BSR values are single snapshots taken at crawl time (the site says "price at crawl time") [VERIFIED].
- License and terms [VERIFIED, but ambiguous]:
  - The GitHub repo https://github.com/hyp1231/AmazonReviews2023 contains an MIT LICENSE ("Copyright (c) 2024 Yupeng Hou"). That covers the repo's code and scripts. The HF dataset card YAML shows no license field.
  - A maintainer wrote in https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1 (hyp1231, 8 Mar 2024): "we are not in a position to assign a license to this dataset", "We have made the dataset available primarily for research purposes", and use "comes with a responsibility to adhere to ethical guidelines and any applicable legal standards."
  - The underlying content (review text, titles, descriptions and images) was written by Amazon customers and sellers, and Amazon owns the image URLs (m.media-amazon.com). The dataset authors cannot grant rights to that content.
  - Citation is requested: Hou et al., "Bridging Language and Items for Retrieval and Recommendation", arXiv:2403.03952.
  - Verdict: it is NOT an open license for commercial use. It is research-intended, unlicensed, and carries third-party content rights. Whether commercial use is allowed is unresolved and needs counsel or a written answer from the authors (contact: yphou AT ucsd.edu, from the HF card).
  - A "MIT" claim for the data appears only on third-party derivative pages [UNVERIFIED]. Do not rely on it.
- Missing: any BSR or price time series, seller count, sales volume, and current data (ends Sep 2023). Review timestamps are real and can be bucketed by day.

### 2.2 Older UCSD data (2014 and 2018)
- 2014 (http://jmcauley.ucsd.edu/data/amazon/ ; the cseweb mirror has a TLS certificate problem): metadata has `salesRank` as `{category: rank}` plus price. Reviews are 1996-2014. The page asks for citation. A third-party catalog calls the data non-commercial research only [UNVERIFIED]. The per-category files sit behind a request form [VERIFIED from page text].
- 2018 (https://nijianmo.github.io/amazon/index.html): metadata includes rank, price and brand. Coverage is 1996-Oct 2018. Terms are not stated beyond citation (Ni, Li, McAuley, EMNLP 2019). Per-category files are also behind a form [VERIFIED from page text].
- Verdict: the same ambiguity as 2023, but staler and more awkward to get. Rejected in favour of 2023.

### 2.3 Amazon Berkeley Objects (ABO)
- Source: https://amazon-berkeley-objects.s3.amazonaws.com/index.html [VERIFIED].
- License: CC BY 4.0, which allows commercial use with attribution, a license link and a change notice. This is the only candidate with a clean, explicit open license.
- Contents: 147,702 products. `abo-listings.tar` is 83 MB (HEAD returned 87,480,320 bytes [VERIFIED]). The fields are item_id, item_name, brand, bullet_point, product_description, product_type, color, material, node (category), main_image_id and others.
- Missing: no price, no BSR, no ratings, no reviews. It is only useful for product attributes, so it cannot power this provider on its own.
- Possible role: catalog titles, brands and images (licensed under CC BY 4.0).

### 2.4 Kaggle, HF and OpenML Amazon datasets
- Most are scrapes of Amazon, so their provenance and ToS standing is poor. Examples are aaronfriasr "Amazon Products Dataset", asaniczka "Amazon UK Products 2023", and kanchana1990 "best sellers".
- Search results showed no confirmed open license for any dataset that includes rank, price and rating [UNVERIFIED]. Each license field would have to be checked on the dataset page.
- Verdict: rejected. Scrape-derived data with an unclear license is worse than the UCSD data. HF re-uploads of Amazon Reviews 2023 inherit its ambiguity.

### 2.5 Genuinely open-source Amazon-like data without scraping
- None found that has BSR, price and reviews. ABO is the nearest, and it only has attributes. Commercial datasets (Bright Data, Grepsr, DataForSEO) are paid and out of scope.

### 2.6 Rejected: scraping Amazon directly
- Violates the Amazon Conditions of Use and risks IP blocks and legal exposure. Not acceptable.

## 3. Deriving app fields honestly

| App field | Source and honesty note |
|---|---|
| asin | `parent_asin` (the variation-family ID). Make the label clear: the app's 10-character ASIN is a parent ASIN. |
| title, image_url | `title` and `images[0].large` (fall back to `hi_res`). These are hotlinks to Amazon's CDN. Hotlinking may be fragile and may breach terms. The provider could return "" and have the UI show a placeholder. |
| category | `categories` path joined with " > ", or `main_category`. |
| brand | `details.Brand`, then `store`, then `details.Manufacturer`, else "". |
| price | `price`, which is a snapshot at crawl time and null for about 45% of items. Options: filter to priced items at import time (keep only items with price and BSR), or return an `Optional`. The dataclass requires a value, so filtering at import is the least invasive. |
| bsr | `details["Best Sellers Rank"]`. Use the entry for the top-level category (the first key, which matches `main_category`) as the headline BSR. Also keep the sub-category rank. This is a real value, but as of about 2023 and not current. |
| rating, review_count | `average_rating` and `rating_number`. Both are real and always present. |
| monthly_sales_estimate | NOT in the data. It is a heuristic: units/day ≈ C / rank^E. |
| seller_count | NOT in the data. Use `0` or None and hide it in the UI. Do not fabricate it. |
| reviews | `rating`, `title`, `text`, `timestamp` (ms, divide by 1000), `user_id`-derived id. All real. Join on `parent_asin`. |
| BSR history | NO real time series exists in this data (see below). |

### BSR to sales heuristic (must be labelled "estimate")
- Published, open basis: John Mount (Win-Vector blog, 18 Apr 2014, https://www.r-bloggers.com/old-tails-a-crude-power-law-fit-on-ebook-sales) fitted Kindle eBook data from Hugh Howey's "50k Report": daily units ≈ 99,340 / rank^0.93. It is a crude fit, valid for roughly ranks 200 to 150,000, and based on one snapshot of Kindle eBooks [VERIFIED].
- Other sources I did not read in full [UNVERIFIED]:
  - A vendor page (RIDGE) claims category exponents of 0.7 to 0.9.
  - Brynjolfsson, Hu and Smith (2003) used a log-linear rank-sales relationship for books.
  - He and Hollenbeck (2020) report that the double-log relationship is concave.
- No open, published, category-specific BSR-to-sales table was found. The exponent and constant differ by category and by year.
- Proposal: `monthly = 30 * K_cat / rank^E` with `E=0.9`. Make K and E per-category settings with generic defaults. Mark every value `estimated=true` and show "Estimate" in the UI. As a cross-check, prefer a review-based signal such as the recent review velocity from real timestamps, which is a real number.

### History snapshots (no real series)
- The dataset has one snapshot per item. Do not synthesise a series as if it were real.
- Approach A (recommended): `get_bsr_history` returns the single real dataset snapshot, dated by the dataset release (2023-09), labelled "dataset snapshot". The app's worker then appends its own real snapshot each time it runs. That series is only real from the moment the worker starts, and its values come from the same static dataset, so they will not change unless a different source is added later. State this plainly in the UI.
- Approach B (real, review-derived): build a monthly series from review timestamps. For each month, report the review count that month, the cumulative review count and the running average rating. These are real. Show them as "Review activity" and "Rating trend", not as BSR.
- Do not interpolate or randomise BSR (the mock does this). If the UI needs a BSR chart, show one point and the label above.

### Trend and saturation scores from real fields
- Trend score: the ratio of reviews in the last 90 days of data to the preceding 90 days. If the dataset ends in 2023, measure relative to the item's last review date.
- Competition and saturation: `rating_number` percentiles within a category, BSR percentiles within a category, and the count of items in the same leaf category with `rating_number > N`.
- Quality gaps: the share of 1 and 2 star reviews, and the verified-purchase share. All of these come from real fields.

## 4. Recommendation: Amazon Reviews 2023, 2-3 small categories, local SQLite store

Because the license is ambiguous, ship the dataset provider as opt-in. Default stays `mock`. Do not redistribute the data, and have each developer or operator download it themselves. Get a written answer from the authors before using it in a paid product.

### Categories for a demo
- Start with Health_and_Personal_Care (meta 23 MB and reviews 70 MB, about 60K items) and All_Beauty (meta 40 MB and reviews 94 MB, about 113K items). Combined, that is about 230 MB to download.
- Appliances is a good third category and the best BSR coverage I measured (66%), but its reviews file is 270 MB.
- For a very small smoke test use Subscription_Boxes (3 MB).
- Per-category BSR and price fill rates were measured on Appliances only. Re-measure after import. The importer should print the fill rates.

### Implementation plan
1. Script `backend/scripts/build_dataset.py` (CLI, new file). Arguments: `--categories Health_and_Personal_Care,All_Beauty --out data/amzn2023.sqlite --max-reviews-per-item 200`.
2. Download with `httpx` or `urllib` streaming to `data/raw/` (use `Range` and resume), then verify the size against Content-Length. The base URL is the mcauleylab.ucsd.edu pattern in section 2.1.
3. Stream with `gzip.open(..., 'rt')` and `json.loads` per line. Never load a whole file. Memory stays O(1) apart from the SQLite page cache, which is fine for multi-hundred-MB files.
4. Pass 1 over meta: keep an item only if `price` is non-null and BSR is present. Compute `bsr` and `price`. Write `products(parent_asin PK, title, brand, category, main_category, price, bsr, bsr_sub, rating, review_count, image_url, est_monthly_sales)`. Add an FTS5 table over title, brand and category for `search_products`.
5. Pass 2 over reviews: keep only rows whose `parent_asin` is in the product set. Cap at N reviews per item (newest first). Write `reviews(id, parent_asin, rating, title, body, ts)` with an index on `(parent_asin, ts)`. Also write a `review_monthly(parent_asin, month, n, rating_sum)` aggregation so history and trend queries stay cheap.
6. Write a `meta` table with the dataset name, source URLs, download date, category list and the heuristic constants.
7. Add `data/` to `.gitignore` (it is not currently listed) and add `data/` to `.dockerignore`. In Docker, mount it as a volume. Never `COPY` it into an image.
8. Add `DatasetProductDataProvider` in `backend/app/services/providers/dataset.py`. It uses read-only `sqlite3` (via `asyncio.to_thread`) and implements the 4 methods. Wire it through `get_product_data_provider()`.
9. Config in `app/config.py`: `DATA_PROVIDER: Literal["mock","dataset"] = "mock"` and `DATASET_PATH: str = "data/amzn2023.sqlite"`. If `dataset` is chosen but the file is missing, raise a clear startup error and log a warning (`logging`, not `print`).
10. Optional extra field on `ProductData`: `estimated: bool` or `data_as_of: date`, so the API and UI can label estimates and the snapshot date. This is a backend decision, not made here.

### Attribution and notices the app must show
- A footer or "Data sources" page: "Product and review data: Amazon Reviews 2023, McAuley Lab, UC San Diego (Hou et al., 'Bridging Language and Items for Retrieval and Recommendation', arXiv:2403.03952), https://amazon-reviews-2023.github.io/. Snapshot data ends Sep 2023. For demonstration and research purposes."
- Label sales figures "Estimated (heuristic)". Label BSR and price "as of dataset snapshot (2023)". Label the review-derived trend as based on review dates.
- Add a "not affiliated with Amazon" notice. Amazon and the ASIN-linked content belong to their owners.

### Provider config
`DATA_PROVIDER=mock|dataset` and `DATASET_PATH=...` (as above). Keep `AMAZON_DATA_API_KEY` for a future paid provider.

## 5. Summary of gaps
- Licence: unresolved for commercial SaaS use. It is not OK to assume it is, and counsel or the authors should confirm it.
- Data is a 2023 snapshot. There is no BSR or price time series, no seller counts and no sales numbers.
- BSR is present for only some items (65.6% in the Appliances sample), price for about 55%, and brand for about 46% (with fallbacks).
- `monthly_sales_estimate` is a heuristic derived from a crude published fit, not from sales data.
- Image URLs are Amazon hotlinks.

## 6. Unverified items
- Third-party claims that the 2023 data is MIT-licensed (derivative pages only).
- The 2014 "non-commercial" tag (third-party catalog).
- The RIDGE exponent range, the Brynjolfsson et al. (2003) approach, and the He and Hollenbeck (2020) finding.
- Kaggle dataset licenses (not checked individually).
- Fill rates for categories other than Appliances.
- The 2014 and 2018 file sizes and the exact terms for them.
