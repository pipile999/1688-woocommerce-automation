# WooCommerce Safety and Verification

## Writes

Prefer WooCommerce REST API over browser form automation.

Before updating an existing product, GET it and verify its identity/model/source metadata.

Never create a replacement product when the task is to update an existing Product ID.

Preserve product status unless instructed otherwise.

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

## Audit integrity

Never let a stale intermediate audit override newer verified REST API results. `final-product-audit.json` must agree with the final variation audit and final WooCommerce GET response.

## Site scope

Do not alter theme, plugins, global permalinks, unrelated categories/products or site-wide settings during a product import unless explicitly authorized.
