# WooCommerce Safety and Verification

## Strict identity/update gate — revision 2026-09-16

Audit input_1688_url -> canonical_offer_id -> source_url -> product fingerprint -> woocommerce_product_id. Fingerprint canonical Offer ID, original source URL, raw title/attributes, immutable SKU/variation/spec combinations and image SHA lineage. A fuzzy title/Model search is not sufficient evidence.

Enumerate all candidates from canonical backend source URLs and Offer/Model metadata, including conflicting records. Before writing verify Model, source URL Offer ID, source/processed/live title and attributes, complete immutable SKU IDs, and visual image/product provenance. If multiple IDs match, inspect each; update only a uniquely proven target. Otherwise STOP THIS PRODUCT + WARNING_DUPLICATE_MAPPING, record candidate evidence, and continue other products. Never create replacements to bypass ambiguity.

Every image payload needs source_offer_id, source_url, source_image_url, woocommerce_product_id and image_role in its local audit. Same-offer original SHA lineage and directories are mandatory; cross-offer image is FAIL. Global hash-only media/content caches cannot authorize reuse.

Retrospective writes require explicit scope and patch failed content/images only. Snapshot parent/variation IDs, SKUs, source IDs, prices, Model, backend URL, correct categories and status; re-fetch before writing to detect concurrent changes. Afterwards fresh GET parent and all variations: protected values unchanged, expected images/HTML stored, correct bindings, main-pool square top <=5, perceptually disjoint Description, total distinct images including variation-only assets <=10 or documented variant exception, evidenced local image QA/selective Vision and HTTP 200/image Content-Type. Ordinary warnings continue the batch; ambiguity stops only its product. Unresolved hard failures stay FAIL; preserve existing publish state. A Skill-only update does not authorize product reads, scans or writes.

## Writes

Prefer WooCommerce REST API over browser form automation.

Before updating an existing product, GET it and verify its identity/model/source metadata.

Compare intended mutable fields with the stored product: unchanged means SKIP, not a redundant write. Save successful stage checkpoints immediately with product_id, offer_id, stage/status and timestamp. Within the same batch/task, completed verified checkpoints are skipped on resume; cached image decisions do not replace fresh publication REST/HTTP acceptance. Do not rescan prior batches merely because a new batch starts.

Never create a replacement product when the task is to update an existing Product ID.

For a new product, the default final state is `publish` after every critical acceptance gate passes. A safe implementation may create a temporary Draft for verification and then publish it. Leave a new product as Draft only when the user explicitly requests Draft or a publication-blocking failure exists.

For an existing product, preserve its status unless the user explicitly requests a status change.

Any `FAIL` blocks publication. Non-critical warnings such as unavailable source `spec_id`, package dimensions, package weight, or absence of a dedicated variation image may publish when no wrong image is assigned; retain every warning in the final audit.

## Mandatory category selection

Before each upload, retrieve the current WooCommerce Product Categories through REST, including parent relationships. Select the most specific truthful existing category from the verified product type, title, attributes, function/use case, and the store's existing merchandising structure.

- Prefer the most specific suitable child category.
- Retain both parent and child only when appropriate for the existing store structure.
- Do not use a broad default category for convenience or classify from noisy 1688 title keywords alone.
- Never create categories automatically.
- If no truthful category exists, record `WARNING: category_unresolved`, assign no misleading substitute, and block publication until category assignment is resolved.

Record `selected_category_ids`, `selected_category_names`, `category_path`, and `category_selection_reason` in the final audit. Re-read the stored product after write and verify those category IDs through WooCommerce REST.

## Secrets

WooCommerce URL/consumer key/consumer secret and other credentials belong in local environment configuration. Never commit credentials to GitHub.

## SKU integrity

SKU and source variation identifiers are immutable unless the user explicitly changes the business rule.

Before/after variation counts must match unless source data itself intentionally changes.

## Price integrity

Use the fixed business formula `source_price / 0.7 / 6.7`. Verify calculated prices and do not overwrite them during unrelated SEO/image updates.

## Product identity

Public product content must preserve `Model: <1688_offer_id>`. Preserve source URL in backend metadata only.

## Variation images

After image updates, GET every variation and compare actual image assignment against the expected color/pattern mapping. Produce PASS/WARNING/FAIL records.

A missing dedicated SKU/color image is WARNING, not permission to bind another color or invent an image. Source_offer_id differing from the current canonical Offer ID is FAIL and must never enter an upload payload.

## Audit integrity

Never let a stale intermediate audit override newer verified REST API results. `final-product-audit.json` must agree with the final variation audit and final WooCommerce GET response.

## Publication gate

Before setting a new product to `publish`, verify all of the following:

- Model is correct and visible where required.
- The original source URL is saved in backend metadata and not exposed publicly.
- SKU count matches the source and every SKU/source identifier is unchanged.
- Every price matches `source_price / 0.7 / 6.7`.
- Featured and Gallery assignments match the approved final assets.
- Every Gallery and Long Description image returns HTTP 200 with an image Content-Type; any broken image is `FAIL`.
- Variation images contain no false mapping and no Variation-image `FAIL`.
- Category selection is correct and verified against the current REST category tree.
- Every final image was produced from the highest-resolution saved original, not a thumbnail or previously compressed WebP, and records dimensions, bytes, compression ratio, selected quality, and sharpness/quality PASS.
- Real local final OCR, contrast-enhanced watermark detection and quality checks (or valid identical QA cache) found no supplier/Chinese/contact/URL/QR/unauthorized-logo residue, smear, broken edge, fake repair, deformation, unreadable text, or excessive compression loss. Only important locally unresolved images require Vision escalation; uncertainty is not PASS.
- Long Description uses accessible Media Library full/large images with responsive sizing; thumbnail/small URLs, visibly undersized assets, or zero images despite usable distinct supplier detail material are FAIL. Do not duplicate top images when no distinct detail asset exists; record the documented sparse-material warning.

After publication, GET the parent product and all variations once more and confirm the final `publish` state and stored values.

For a post-publication quality repair, GET and snapshot identity, status, categories, SKU set, prices, source variation/spec identifiers, Model, source URL, and variation-image relationships before writing. Update only failed image/content/SEO fields, preserve the original publication status, then GET parent and variations again and prove every immutable value is unchanged. Every final Featured, Gallery, Description, and changed Variation attachment URL must return HTTP 200 with an image Content-Type.

## Site scope

Do not alter theme, plugins, global permalinks, unrelated categories/products or site-wide settings during a product import unless explicitly authorized.
