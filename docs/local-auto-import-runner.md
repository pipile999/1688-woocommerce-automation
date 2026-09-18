# Local auto import Runner

## Entry points

```powershell
.venv-ai/Scripts/python.exe auto_import_runner.py "https://detail.1688.com/offer/123456789.html"
.venv-ai/Scripts/python.exe auto_import_runner.py products.xlsx --start 21 --end 40
.venv-ai/Scripts/python.exe auto_import_runner.py tasks.json --dry-run
.venv-ai/Scripts/python.exe scripts/test_auto_import_three.py
.venv-ai/Scripts/python.exe -m unittest tests.test_auto_import_runner tests.test_keyword_research -v
```

Running without `--dry-run` authorizes the supplied input only. Eligible **new** products use draft → REST/HTTP acceptance → publish; `--draft` keeps a draft. Existing store products outside this Runner's own upload checkpoint are not modified or duplicated. An unresolved product enters the review queue; other products continue.

Excel uses sequence column A and a URL cell/hyperlink in the first worksheet. `--start/--end` select sequence numbers, not header-inclusive physical row numbers. URL and JSON task list inputs also work.

## Reused components

- Existing conservative OpenCLI/1688-cli adapter and persistent browser verification functions; serial acquisition, retained session, whoami confirmation.
- Existing PaddleOCR, OpenCLIP and rembg adapters and adaptive final WebP encoder. OpenCLIP is a **local** model, not a remote Vision API call.
- Existing exact SQLite cache primitives and price calculation.
- Existing WooCommerce REST and WordPress Media transport. No old offer-specific image mapping or bulk script `main()` is invoked.

Python environment needs project requirements plus the already-provisioned image stack (`numpy`, Pillow, OpenCV, PaddleOCR/Paddle, OpenCLIP/torch, rembg/ONNX). Model weights must be installed locally. Missing models fail explicitly; a successful offline artifact replay does not prove fresh model inference. No default Codex/chat/LLM service is used.

## English facts and review boundary

Supported literal product types/options have a small controlled glossary in `runner_content.py`. Unknown types, ambiguous English/SKU translations and complex graphics require a source-bound `output/<offer>/runner-evidence.json` pack, not guesses. Test evidence is derived only from the three previously reviewed products; it is not a blanket approval for new products.

An evidence pack contains the SHA-based `source_fingerprint`, facts and source tokens for every fact, approved translated SKUs (or exact `processed_fingerprint`), current English title, exact keyword relevance evidence, candidate title options with fact evidence, and appropriate existing category names. The optional `category_snapshot` is only for offline tests; live execution always fetches real categories. A saved keyword map cannot replace product/source verification.

Complex sliced graphics/English layout, uncertain product/logo/semantic match and ambiguous SERP intent go to `ai-review-queue.json`. This is an honest remaining review dependency, not an automatic AI caller. Straightforward eligible photos are locally OCR/CLAHE/QR/classification checked, repaired where reliable, rechecked and encoded. Dense or uncertain text is not smeared into a fake clean image. Source-confirmed OCR parameters may become HTML; unsupported fragments are omitted. Unresolved valuable detail material blocks that product rather than creating an empty fake-complete detail page.

## Google data, access and costs

`data/keyword-cache.json` is reused with exact keyword + market + language and source TTL. Actual previously collected UI/export results are valid sources; similar terms are not substitutes. Missing data keeps the current title. No Ahrefs route is used by the Runner.

For optional direct Keyword Ideas calls install the official `google-ads` SDK, configure `GOOGLE_ADS_CONFIGURATION_FILE_PATH` to a **private** SDK YAML file and `GOOGLE_ADS_CUSTOMER_ID` in local environment/ignored `.env`. The SDK file contains Google Ads developer token and OAuth configuration; do not put credentials in chat or Git. Browser login alone does not grant API access. See [Google's official sample](https://developers.google.com/google-ads/api/samples/generate-keyword-ideas). Requests explicitly use US location 2840, English 1000 and Google Search. The adapter records exact returned values, not fabricated volumes. Other markets require explicit API constant configuration.

Normalized Planner evidence can also be imported using `GoogleKeywordPlanner.import_evidence(path)` with keyword, country, language, timestamp, evidence_source and actual metrics/ranges. Trends and SERP currently consume dated real cached evidence; automated new Trends/SERP acquisition is **not implemented or claimed**. Missing/uncertain SERP evidence cannot approve a title change. Advertiser competition is not organic KD.

Per-offer audit records local_processing, keyword_api_queries, llm_calls, vision_calls, paid_api_cost and elapsed seconds. With no external calls cost is zero; an actual API query without invoice data has unknown cost, not an estimate. CPU/electricity and prior research costs are not attributed to the current run.

## Checkpoints and safety

Artifacts are isolated under `output/auto-runner/{dry-run|live}/<offer>/`. Atomic checkpoints validate input and output hashes, rules and implementation version. Existing complete raw sources are never reacquired. Content results are copied out of cache to prevent a later proposal mutating saved input. Identifiers/prices and file bytes/dimensions are re-read independently.

The OS lock prevents concurrent Runner processes. Already-collected products drain first; only new acquisition pauses for manual X5/login. A fixed project browser session stays alive. Ordinary review/failure is product-local. Upload checkpoints record each media/parent/variation operation. If a write times out with unknown outcome, do not repeat it; reconcile its server outcome before clearing/resolving the checkpoint. This safe exception prevents duplicates.

## What the three-product test proves

Exactly offers 972743663599, 991366391366 and 977271484514: real saved source data, immutable SKU/price checks, current saved title snapshot, real Google cache, local scoring, saved final image SHA/provenance/geometry/pHash, category snapshot, full parent/variation payload construction, resume cache hits and unchanged existing artifacts.

Network is blocked and WooCommerce construction is mocked to fail if attempted. The test does **not** collect 1688, call live Keyword Planner, rerun OCR/rembg, upload or prove current HTTP/publication state. Those stages are explicitly NOT_EXECUTED. Transport tests use labeled synthetic fixtures to exercise acceptance-before-publish, broken-image blocking, duplicate mapping and unknown-write safeguards without changing a store.
