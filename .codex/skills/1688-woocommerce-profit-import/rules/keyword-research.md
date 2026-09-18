# Evidence-driven keyword and title decisions

Default market: United States / English / Google Search. Never substitute global volume. Retain keyword, country, language, query/source timestamp, historical period, source/evidence reference, average monthly searches (exact number or reported range), advertiser competition and available bid/commercial metrics. Missing values remain null/DATA_UNAVAILABLE; 0–10 is a reported range, not a proven positive number.

Workflow: true product type/material/size/structure/features/use and genuine B2B proposition → a small relevant seed set → Google Keyword Planner → Google-returned Keyword Ideas and historical metrics → Trends relative comparison → a few top-candidate real SERPs → local ranking → keyword roles → natural English title.

Distinguish a submitted seed from a Google-generated idea. Preserve filters or access limitations that restrict returned ideas. Do not borrow product facts, certifications or capabilities from SERP competitors.

## Exact-market cache and source adapters

Use `data/keyword-cache.json`. Normalize case/whitespace only; cache exact keyword+country+language with source and TTL. Deduplicate a batch before paid queries and check all equivalent configured Planner sources before querying. Cache returned related ideas as well as requested seeds. Repeated missing terms should not be hammered within a run. Do not use similar words as evidence for an unqueried keyword.

The standalone Runner supports recorded Planner UI/export evidence and an optional official Google Ads SDK adapter. Browser login alone is not API authorization. API configuration belongs in a local private Google Ads SDK config file plus Customer ID, never a chat or Git commit. No configured credentials/access: use valid cache; otherwise DATA_UNAVAILABLE and KEEP CURRENT TITLE. Do not revive the Ahrefs route.

Trends and SERP evidence may be imported/cached with query, market, date and actual source. Missing or stale evidence must remain unavailable; do not simulate live queries. Trends 0–100 is relative within its comparison, never monthly volume; sparse series do not prove rising/falling demand. Uncertain important SERP intent goes into `ai-review-queue.json` while other products continue.

## Selection and title gate

Rank `Product Relevance × Commercial Intent × Search Demand × Competition Opportunity × SERP Match`, with product truth and search-intent match as hard prerequisites. Ads Competition describes advertisers, not organic SEO difficulty; do not claim LOW means easy organic rankings. Without organic competitive evidence, label that aspect unavailable and use Ads metrics only as a disclosed weak commercial signal.

Classify Core, Long-tail Opportunity, Commercial/B2B, and Reject. B2B wording requires both real procurement demand/SERP match and an actual supported purchase proposition. Reject wrong product/intent, unauthorized brands and unsupported modifiers regardless of volume. A 0–10 range or missing competition does not establish a low-competition opportunity.

Check `data/keyword-map.json` for existing ownership before choosing a Primary. Do not mechanically assign the same Primary to similar products, but never choose an irrelevant substitute to avoid a collision. Store product_id/offer_id/current title/primary/secondary/long-tail/search intent and source evidence. Recommendations are not live store changes; update live ownership only after confirmed REST acceptance.

If there is no sufficiently supported improvement, KEEP CURRENT TITLE. A local numeric score alone is not proof of relevance or a license to rewrite. Unknown English facts/translations require review. For a genuinely new product, a minimal confirmed factual English name may be used without claiming verified SEO demand.

Normally use one naturally leading Primary plus one valuable true modifier in the Product Title. Put other terms in Meta/Description/Specifications/ALT/FAQ/internal linking only when those sections/images actually support them; never create unsupported FAQ facts or rename existing live image URLs just for a keyword. Existing slugs stay unchanged unless explicitly authorized.
