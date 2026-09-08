---
name: 1688-woocommerce-profit-import
description: End-to-end 1688/Alibaba product import workflow for a high-volume WooCommerce store. Use when the user provides one or more 1688/Alibaba product URLs and wants Codex to collect, clean, translate, optimize images, map variations, create/update WooCommerce products, optimize for commercially valuable organic traffic and conversion, and produce auditable results without changing unrelated site structure.
---

# 1688 → WooCommerce Profit-Oriented Import

## Mission

Turn one or more 1688/Alibaba product URLs into commercially useful WooCommerce products with the highest practical chance of gaining relevant organic traffic, clicks, inquiries, add-to-carts and sales.

The priority is **profit and commercially valuable traffic**, not achieving a cosmetic SEO score.

Use existing project scripts and tested components whenever available. Do not rebuild working modules without a reason.

## Highest-priority operating rule: End-to-End Batch Execution

When the user provides one or more 1688/Alibaba links or selects a range of products from an Excel file, the default task is the complete continuous pipeline:

`acquisition → image processing → content/SEO → SKU/pricing → automatic category selection → WooCommerce upload → final acceptance → publish`

This rule governs workflow continuity and has the highest operational priority. The Adaptive Supplier Content Strategy below continues to govern product-content and image decisions.

- Execute the full pipeline in one run. Do not stop after acquisition to wait for a separate request to process, upload, verify, or publish.
- Do not request confirmation between ordinary stages. Existing authorization boundaries still apply; do not expand the user's scope or alter unrelated products or site settings.
- Save durable per-product, per-stage checkpoints after each successful stage. On interruption or restart, inspect the checkpoint and existing artifacts, resume from the first incomplete stage, and do not repeat successful acquisition or processing.
- Isolate failures by product. Record a product-level `FAIL`, block unsafe downstream work and publication for that product, then continue eligible stages for the remaining products.
- Handle existing non-critical `WARNING` conditions according to this Skill, retain them in the audit, and continue the batch without interruption.
- Pause and notify the user only when completion genuinely requires their manual action, such as a 1688 X5 page, login challenge, CAPTCHA, or slider verification. Do not loop or rapidly retry the blocked 1688 request.
- While 1688 acquisition is paused for verification, continue local processing, content work, WooCommerce work, and acceptance for products whose required source data is already complete whenever those stages remain safe and independent.
- After the user completes verification, confirm the persistent session identity, resume the blocked offer from its checkpoint, and continue every remaining stage through publication without requiring a new workflow command.
- Publish every product that passes all critical acceptance gates. Never publish a product with a critical `FAIL`.
- Report once after the entire batch is complete, except for a genuinely required manual-action notice. The final batch report must include successes, warnings, failures, and unresolved items without turning earlier checkpointed work into a new run.

Interpret short requests such as `处理这些链接` and `处理Excel第X-X个` as authorization to execute this complete end-to-end pipeline for exactly the supplied links or selected spreadsheet range. The user does not need to issue separate commands for processing, upload, verification, or publication.

## Highest-priority principle: Adaptive Supplier Content Strategy / 供应商素材自适应策略

Audit the actual supplier evidence before deciding image count, image roles, description modules, specifications, or page depth. This principle overrides any default template, preferred gallery size, preferred featured-image type, or standard long-description outline.

**Optimize only information that truly exists. Never create unsupported product facts merely to complete a template.** Missing information is not permission to infer or invent material, dimensions, specifications, functions, packaging, accessories, benefits, certifications, or selling points. Leave an unsupported field empty or omit the module and record the limitation in the audit.

Adapt the presentation to the evidence:

- Sparse but valid supplier content may produce a concise product page using only the few real, useful images and attributes available.
- Rich, high-quality content should be retained and organized by its real buyer value, including Featured, Gallery, Variation, Product Details, Features, Structure, Dimensions, Materials, Application/Usage, Packaging, Accessories, and Color Options when supported.
- Do not delete valuable images to meet a fixed gallery count, and do not add repetitive or low-value images to make a page appear fuller.
- Description structure and length must follow the product evidence rather than a universal module sequence.
- Image decisions must consider context and whether an asset helps a buyer understand, compare, trust, or purchase the real product. Repair or crop a partly useful image when practical; reject the whole image only when it lacks meaningful purchase value, cannot be repaired reasonably, is severely low quality, or is unrelated.

AI must choose the most suitable presentation from the current supplier assets, image quality, verified attributes, SKU structure, page completeness, SEO value, buyer-decision value, and page-load cost. Truthfulness, image quality, purchase experience, and conversion value take priority over template consistency.

For image-specific execution, including featured-image selection, canvas adaptation, sliced-detail reconstruction, Chinese graphic translation, retention decisions, and performance treatment, read `rules/images.md` before processing images.

## Required input

At minimum:

- One or more 1688/Alibaba product URLs.

Optional:

- Existing WooCommerce Product ID to update.
- User-supplied keyword/category hints.
- Google Ads Keyword Planner credentials/data.

## Non-negotiable business rules

1. Extract the numeric 1688 offer ID from the URL and preserve it as `Model: <offer_id>`.
2. Preserve the original source URL in backend metadata only. Do not expose it on the public product page.
3. Preserve original SKU, variation ID/spec ID, attribute combinations and variation relationships. AI must never rewrite SKU identifiers.
4. Price every variation with the fixed formula:

   `sale_price = 1688_source_price / 0.7 / 6.7`

5. Never invent GTIN, MPN, brand, reviews, ratings, certifications, sales volume or Keyword Planner search volume.
6. Never modify unrelated products, theme files, plugin configuration, permalink structure or site-wide settings unless the user explicitly asks.
7. Prefer WooCommerce REST API for product writes and verification. Do not use browser form automation for routine product updates when REST API access exists.
8. After any WooCommerce write, GET the product and all variations again and verify the stored state before claiming success.
9. For a new product, the default final state is `publish`, but only after every pre-publication critical gate passes. Use `draft` only when the user explicitly asks for a draft.
10. Before every product upload, read the store's current Product Categories through WooCommerce REST and select the most specific truthful existing category. Never create a category automatically or use a broad catch-all merely for convenience.

## Workflow

### 1. Acquire source data

Use the composite acquisition order: `1688-cli` for structured product data, then OpenCLI `1688 assets` for main/SKU/detail media. Use direct 1688 requests only as a low-priority fallback; do not loop-retry X5/CAPTCHA responses. Reserve an interface for the 1688 Open Platform API when it is available.

Collect:

- title
- description
- attributes
- source prices
- all SKUs / variations
- variation IDs; preserve a source SKU ID exactly when it is supplied
- inventory when available
- package dimensions/weight when available
- main images
- variation/color images
- description/detail images

The upload hard gate is: offer ID/Model, title, source URL, source price or tiers, complete SKU combinations, SKU attributes, a price for every SKU, and at least one real product image. A distinct `spec_id`, package dimensions/weight, supplier packaging details, and inventory are optional. Leave unavailable optional fields empty and record an audit WARNING; never invent them. When no distinct source spec ID exists, record `source_spec_id: unavailable` and retain the SKU/variation ID supplied by the source.

If acquisition fails due to login, CAPTCHA or anti-bot controls, diagnose and report the failure. Do not silently fabricate missing fields.

### 2. Preserve raw evidence

Before transformations, save the raw result under:

`output/<offer_id>/original-product.json`

and raw images under:

`output/<offer_id>/raw_images/`

Never overwrite the only raw copy.

### 3. Product text cleanup and English conversion

Create natural English merchandising copy instead of literal machine translation.

Remove or exclude:

- supplier/company names
- factory introductions
- supplier logos
- 1688 shop URLs
- phone/WeChat/WhatsApp/email
- QR codes
- supplier branding
- OEM/ODM promotional copy that is not product information
- exaggerated supplier marketing language

Keep useful buyer-facing information:

- material
- size
- color
- construction
- function
- specifications
- packaging
- usage/application when supported by source evidence

Generate:

- Product Title
- Slug
- Short Description
- Long Description
- Meta Title
- Meta Description
- Focus Keyword when Rank Math is available

Use `rules/seo-and-conversion.md` for keyword and copy decisions.

### 4. Image pipeline

Run the actual image pipeline, not placeholder logic:

1. inventory and audit the supplier's actual main, SKU, detail, and sliced-detail assets
2. exact-content SHA deduplication
3. PaddleOCR text detection
4. OpenCLIP visual classification
5. detect and reconstruct continuous sliced-detail designs when evidence supports it
6. decide keep / delete / repair / translate from image context and buyer value
7. mask unwanted text/logo/watermark
8. LaMa or configured inpainting model for background restoration
9. translate valuable Chinese product-information graphics into natural English
10. assign image role according to the available evidence
11. generate SEO filename/ALT/media title
12. adaptive WebP optimization

Use `rules/images.md` for the detailed rules.

### 5. Image role assignment

Classify every final image as one or more of:

- `featured`
- `gallery`
- `variation`
- `description`
- `reject`

Featured image rule:

- Rank candidates in this order: **image quality → resolution → product clarity → composition/click appeal → product relevance → multi-color value**.
- Multi-color is an optional merchandising advantage, never the first criterion.
- A sharp, high-resolution, attractive single-product image must beat a blurry, low-resolution, poorly composed, undersized, or badly proportioned multi-color image.
- When a high-quality multi-color candidate and a high-quality single-product candidate are otherwise close, prefer the multi-color candidate for its commercial display value.
- A featured candidate must be relevant to the real product, clean of supplier identity/contact details, and suitable for the store's product-card and product-page presentation.

Do not select the featured image merely because it is first in the source list.

Gallery size is not a fixed SEO number. Keep images only when they add meaningful information for the buyer.

### 6. Chinese text inside useful product images

Do **not** delete a useful product-information image just because it contains substantial Chinese text.

If the Chinese text explains:

- dimensions
- structure
- materials
- functions
- specifications
- product advantages
- usage

then:

1. OCR the Chinese text.
2. Translate it into natural buyer-facing English.
3. Remove the original Chinese text with mask + inpainting/background reconstruction.
4. Place readable English text in an appropriate layout.
5. Preserve the real product image as much as possible.

If text is supplier identity, company promotion, phone, URL, contact information or unrelated advertising, remove it rather than translate it.

### 7. Variation image mapping

Map variation images by actual visual match.

Preferred logic:

- Color/pattern image mapping has priority.
- Different sizes of the same color may share one accurate color image when no size-specific image exists.
- Never knowingly attach the wrong color image.
- If no dedicated reliable image exists, leaving a fallback/multi-color image or no dedicated image is preferable to a false mapping.

Validate every variation after write.

### 8. Commercial keyword cluster

Build a keyword cluster around the product rather than forcing one unique keyword per image.

Prioritize:

- true product relevance
- buyer/commercial intent
- search demand when real data is available
- fit with the store's main product direction
- achievable competition
- wholesale/B2B intent where appropriate
- margin/commercial value

Organize into:

- primary commercial keyword
- secondary keywords
- attribute keywords
- long-tail transactional keywords
- wholesale/B2B keywords

If Google Ads Keyword Planner is configured, use real data. Otherwise mark it as unavailable and never invent search volume.

Image filename/ALT should match the real image content and may reuse closely related terms naturally. Do not force N images to use N unique keywords.

### 9. Long Description layout

Build the description as a sales page, not a block of SEO text. Choose its structure dynamically from the available evidence. A product with three useful images and few verified attributes may need only a concise, coherent description. A product with many strong images, dimensions, structure, packaging, and usage evidence may justify a richer page. Products with sliced detail designs require reconstruction and content organization before layout.

Use only evidence-supported modules; examples include:

- Product Overview
- strong product image
- Key Features
- detail/structure image
- Color Options when useful
- Material & Details
- Sizes / Specifications
- Application / Packaging when source evidence exists
- Specifications table
- Model number
- clear purchase/inquiry CTA consistent with the existing site

Do not invent sections merely to fill a template.

### 10. Image performance

Optimize after all editing/inpainting/text replacement is complete.

Prefer WebP and adaptive compression.

Goals:

- visually good product quality
- minimal practical payload
- no unnecessary huge source dimensions
- retain WordPress responsive-image behavior/srcset

Do not use one hardcoded quality value as the only rule. Compare output quality/size and choose a sensible result.

Record original and final dimensions/KB when feasible.

### 11. Mandatory category selection

Before uploading each product, retrieve the current WooCommerce Product Categories through REST, including parent relationships. Select the most specific truthful existing child category from the product's verified type, title, attributes, function/use case, and the store's existing merchandising structure.

- Prefer the most specific suitable child category; include its parent as well only when the store structure or navigation benefits from both.
- Do not bulk-place unrelated products into a broad default category.
- Do not classify from noisy 1688 title keywords alone.
- Do not create categories automatically.
- If no truthful existing category fits, record `WARNING: category_unresolved`; do not assign a misleading category. Because correct category assignment is a critical publication gate, also record a publication-blocking failure until the category is resolved.

The final audit must record:

- `selected_category_ids`
- `selected_category_names`
- `category_path`
- `category_selection_reason`

### 12. WooCommerce write and default publication strategy

If creating a new product:

- Default to `publish` after acquisition, image processing, SEO, SKU/variation mapping, price calculation, category selection, image HTTP checks, and WooCommerce REST verification all pass.
- A safe two-phase implementation may create an internal draft, verify it, then switch it to `publish`; do not leave a verified new product in Draft unless the user explicitly requested Draft.
- Any `FAIL` blocks publication.
- Non-critical `WARNING` records may still publish, including unavailable `spec_id`, packaging dimensions, package weight, or a variation without a dedicated image when it is not mapped to an incorrect image.
- Every warning must remain in the final audit.

If updating an existing Product ID:

- update that ID only
- preserve current publish/draft status unless explicitly instructed otherwise
- never create a duplicate

Prefer REST API calls for:

- product body
- slug
- attributes
- images/gallery
- metadata
- variation updates

Rank Math SEO fields may be written through the existing tested mechanism/API when supported.

### 13. Pre-publication verification gates

Do not report success until all applicable gates pass.

Verify:

- correct offer ID / Model
- source URL preserved in backend
- title/slug saved
- short description saved
- long description saved with intended images
- featured image correct
- gallery useful and not blindly bloated
- SKU count before = SKU count after
- every SKU identifier unchanged
- every calculated price matches the fixed formula
- variation attributes remain correct
- variation image mapping checked
- selected category IDs, names, hierarchy path, and selection reason verified against the current REST category tree
- no supplier/company/contact information remains in public copy/images where detectable
- final images are optimized formats
- WordPress/WooCommerce API GET confirms saved values

Publication requires correct Model, backend source URL, unchanged SKU count and identifiers, exact price formula, correct Featured image, accessible Gallery, HTTP 200 Long Description images with no broken images, no Variation-image FAIL, and correct category assignment. A critical failure keeps the product unpublished. Non-critical warnings may publish but must remain explicit in the audit; do not convert uncertainty into false PASS.

### 14. Final image-access acceptance gate

After every WooCommerce write, retrieve the stored product again and inspect every `<img src>` in the Long Description. Each URL must return HTTP 200 and an image Content-Type. A broken image is a **FAIL**, not a warning: do not report the import complete until every description image is accessible. Also verify that the Featured Image is the final selected high-quality image, every Gallery image is accessible, variation-image mappings are correct, SKU count and prices remain intact, and Model/source URL metadata are present.

If a final processed image is not yet in the WordPress Media Library, upload it there and use the real attachment URL in the description. Never use local paths, `file://` URLs, temporary paths, or an external source hotlink as the final description image URL.

### 15. Default interpretation

When the user says only `处理并上传这些1688链接` or an equivalent request, interpret it as:

`complete processing → automatic category selection → full acceptance → publish`

Use `draft` only when the user explicitly requests a draft or when a publication-blocking failure prevents release.

## Audit outputs

For each product, maintain auditable outputs under:

`output/<offer_id>/`

Recommended files:

- `original-product.json`
- `processed-product.json`
- `image_audit/image-audit.json`
- `image_audit/sha-deduplication.json`
- `image-seo-map.json`
- `variation-image-audit.json`
- `final-product-audit.json`

`final-product-audit.json` must reflect the final verified state, not stale intermediate script results.

## Completion report

Keep the user-facing completion report concise. Include:

- offer/model ID
- WooCommerce Product ID
- final status
- final title + slug
- SKU/variation count
- price range
- image counts: raw → unique → final
- variation image PASS/WARNING/FAIL
- main unresolved warnings
- front-end product URL when available

Do not claim success if verification is incomplete.

## Failure handling

If a stage fails:

- stop unsafe downstream writes
- preserve current good state
- state exactly which stage failed
- fix the failing script/module rather than repeatedly retrying browser UI automation
- never modify unrelated products to work around a failure

## Supporting rules

Read these only when the task reaches that stage:

- `rules/images.md`
- `rules/seo-and-conversion.md`
- `rules/woocommerce-safety.md`
