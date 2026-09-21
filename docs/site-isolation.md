# Separate production sites

Packaging project: SITE.md, 自动上架/skills/mypakg-1688-product-import, sites/mypakg/runner.py.
Fastener project: projects/fastenhardware/SITE.md, its 03_products/skills/fastenhardware-1688-product-import and sites/fastenhardware/runner.py.

Each runner hardcodes its single domain and derives site data paths from its own location. Site/profile/root overrides, environment domain mismatch, cross-site data paths, redirects and non-product endpoints fail closed. Separate code copies preserve independent business rules. Shared Python packages are code only at D:/codex/tools/site-runner-libs.

Both .env files are NEW EMPTY credential templates (not copied from history); configure each locally for future production. No secret values were read. Historical raw data, caches and checkpoints remain untouched, are not auto-migrated and are never automatically resumed. Local model packages/weights retain the original provisioning requirements; this refactor validates guards and isolation, not collection, image inference or live acceptance.

Run `runner.py --dry-run` WITHOUT product input to inspect only fixed identity and paths. Test both runtimes with `python tests/test_site_isolation.py <mypakg-runtime> <fastenhardware-runtime>`. Tests forbid real network and credentials; no products are supplied or processed.

Legacy Skill is retained as LEGACY / DO NOT USE FOR PRODUCTION. Old generic root Runner, desktop resume/start scripts and legacy REST client are disabled. Dedicated desktop names: mypakg自动上品 and fastenhardware自动上品. Original ambiguous shortcuts are archived locally, not reused for target selection.

Fastener rules preserve supplier SKU order/source_sku_position, technical data, parent Featured fallback, max five main-pool images, independent fastener categories/keywords and full-quality description images with display width limits. Publication still requires all acceptance gates, including real backend source-link visibility; no global template edits are permitted.
