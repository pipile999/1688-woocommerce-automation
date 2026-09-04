---
name: 1688-woocommerce-profit-import
description: End-to-end 1688/Alibaba product import workflow for a high-volume WooCommerce store. Use when the user provides one or more 1688/Alibaba product URLs and wants Codex to collect, clean, translate, optimize images, map variations, create/update WooCommerce products, optimize for commercially valuable organic traffic and conversion, and produce auditable results without changing unrelated site structure.
---

# 1688 → WooCommerce Profit-Oriented Import

## Mission

Turn one or more 1688/Alibaba product URLs into commercially useful WooCommerce products with the highest practical chance of gaining relevant organic traffic, clicks, inquiries, add-to-carts and sales.

The priority is **profit and commercially valuable traffic**, not achieving a cosmetic SEO score.

Use existing project scripts and tested components whenever available. Do not rebuild working modules without a reason.

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

## Workflow

### 1. Acquire source data

Try the existing direct 1688 acquisition path first.

Collect:

- title
- description
- attributes
- source prices
- all SKUs / variations
- variation IDs / spec IDs
- inventory when available
- package dimensions/weight when available
- main images
- variation/color images
- description/detail images

If direct acquisition fails due to login, CAPTCHA or anti-bot controls, diagnose and report the failure. Do not silently fabricate missing fields.

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

1. exact-content SHA deduplication
2. PaddleOCR text detection
3. OpenCLIP visual classification
4. decide keep / delete / repair / translate
5. mask unwanted text/logo/watermark
6. LaMa or configured inpainting model for background restoration
7. translate valuable Chinese product-information graphics into natural English
8. assign image role
9. generate SEO filename/ALT/media title
10. adaptive WebP optimization

Use `rules/images.md` for the detailed rules.

### 5. Image role assignment

Classify every final image as one or more of:

- `featured`
- `gallery`
- `variation`
- `description`
- `reject`

Featured image rule:

- **Prefer a strong multi-color product collection image** when one exists.
- It may remain the featured image even if it visually shows one or two more colors than the currently available SKU list.
- It must still be clear, relevant to the same product, visually strong, reasonably clean, free of supplier identity/contact details and suitable for attracting clicks.
- If no strong multi-color image exists, choose the best representative single-product image.

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

Build the description as a sales page, not a block of SEO text.

Use available evidence flexibly. Typical order:

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

### 11. WooCommerce write strategy

If creating a new product:

- default to Draft unless the user explicitly requests publication.

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

### 12. Verification gates

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
- no supplier/company/contact information remains in public copy/images where detectable
- final images are optimized formats
- WordPress/WooCommerce API GET confirms saved values

Warnings are allowed when evidence is genuinely unavailable; do not convert uncertainty into false PASS.

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
