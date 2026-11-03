# Image Rules — MyPakg
Revision: 2026-11-03. Sole image-policy source for this site's Skill and publication checks. Apply only to MyPakg; do not copy other sites' caches or business data.

## Selection and retention
Prefer existing clear, complete, truthful supplier images before editing. Pure-background photos, usage scenes, English explanation graphics, dimension graphics and real multi-color group photos are eligible. Do not reject images merely for having a scene, text, a name or a small logo. Ordinary names and unobtrusive marks may remain under the user's selection standard; this does not establish brand affiliation. Remove distracting small logos/edge decorations when practical. Contacts, QR codes and unrelated advertising are not useful product content: crop or repair them rather than reject the product. Concrete serious safety or rights concerns require specific evidence and representative user review, not blanket speculative holds.

Choose sharpness, product clarity, truthful relevance and attractive composition first; favor useful scene/dimension/color coverage among equally good candidates. A group image must not imply that one unit includes every displayed color or accessory.

Featured + Gallery: normally 3–5 distinct useful images, maximum five. Work toward this using all credible same-offer assets; never fabricate views or repeat crops to fill a quota. If fewer distinct useful images genuinely exist, retain the product in the repair queue and report the limitation rather than silently discard it. Supplier-main images are preferred, not the only eligible source. A clear same-offer detail crop or accurate English dimension card can qualify after square adaptation and visual review. Long, dense, unreadable panels belong in Description, not the top gallery. Preserve original source order when the user selects numbered images.
Keep the existing ordinary total cap of ten distinct final images across roles; document genuine SKU/color exceptions. Do not duplicate top images in Description merely to fill space. Preserve all raw evidence.

## User examples, not a closed allowlist
- 1044116644935: user accepts all supplier-main images, including scenes, plain backgrounds, English explanation and names.
- 787675642935: user accepts all supplier-main images.
- 1050883680899: prefer the last two clean supplier-main images, after verifying source order; do not struggle to retain dense Chinese promotional panels.
These examples define selection behavior for the authorized batch, not permission to add offers to a queue. User statements are recorded as user evidence; do not claim independent image inspection without actually viewing the images.

## Repair ladder
1. Use an already suitable same-offer image unchanged.
2. Crop a small edge decoration if the subject and useful information remain complete; otherwise use precise local cleanup or masked inpainting. Do not mechanically prefer repair over a harmless crop.
3. For valuable dimensions/parameters, verify text and measurements, translate to natural English and reconstruct a coherent layout. Preserve true units, arrows and geometry. No patchwork rectangles, residual Chinese, gibberish, smears or obvious repair seams. Use confirmed HTML facts as a fallback when a graphic cannot be relaid out faithfully, not as an automatic reason to prohibit dimension images.
4. For cluttered backgrounds, extract the real complete product using a suitable cutout tool, refine alpha edges and place it on an 800×800 white/light neutral canvas. Aim for approximately 80–90% occupancy where product shape and real source detail permit; retain breathing room and all important parts. Never stretch or invent hidden detail. Do not present ordinary enlargement as recovered resolution.
5. When a result fails visual review, return to the original, change the mask/method or select another source image. Exhaust credible source alternatives and cutout before declaring more material necessary.

Reuse installed tested tools first. Candidate tools include rembg (https://github.com/danielgatis/rembg) for cutout, OpenCV for precise cleanup and layout, and a compatible local inpainting tool such as IOPaint (https://github.com/Sanster/IOPaint). IOPaint is archived: assess compatibility before installing; do not blindly upgrade a working environment. Verify repository, license, dependencies and actual output before integration. Prefer sequential processing on limited-memory machines; do not launch competing model workers. Record the tool/model actually executed. A mask alone is not inpainting and tool exit success is not visual approval.

## Provenance and fidelity
Bind input URL, canonical Offer ID, source image URL, raw SHA256, transformation lineage, final SHA256, role and target WooCommerce product ID. Never reuse cross-offer images or recommendations. Preserve originals and before snapshots; edit from the highest-resolution original, not thumbnails or a prior lossy output. Never invent SKU colors, geometry, material, accessories, certifications or dimensions.
Map variation images by verified color/pattern; same color across sizes may share an accurate image. Missing dedicated imagery is a warning, not permission to invent it or assign a different color.

## Detail reconstruction and layout
Join sliced designs only with evidence from order, matching edges, continuity and layout; matching width alone is insufficient. Remove captured UI and irrelevant regions, reconstruct before translating and record seams/crops. Split long designs into readable coherent modules when useful. Retain true scene, structure, use, packaging and dimension content. Center Description images with responsive max-width:100%; height:auto and use Media Library full/large assets, never thumbnail URLs. Keep supported native detail, usually 1000–1600 px effective width where the source supports it; do not force detail panels square. If no distinct useful detail exists, record that limitation rather than duplicate a gallery image.

## Final visual acceptance
Actually view each new or changed final image at normal display size and inspect repaired edges/text at full resolution. Local OCR and contrast-enhanced checks identify candidates for review; names, text or logos alone are not automatic FAIL. Do not claim OCR proves visual quality. Reuse identical valid QA rather than repeat inspection of unchanged bytes.
Reject the OUTPUT for visible patches, blotches, halos, jagged/missing edges, residual text from failed edits, distorted products, unreadable English/measurements, false colors, severe blur or compression loss. Rework it; do not treat a rejected image as a permanently rejected product.
Remove distracting large Chinese promotional overlays and contact/QR advertising; retain permitted names and useful English content. Preserve the source product's real appearance. Only genuinely ambiguous representative cases require user input; apply the resulting decision consistently to analogous cases.

## Exact caching, encoding and audit
Use exact keys including Offer ID, original URL, raw/final SHA256, specification hash and relevant rules version. Record CACHE_HIT/MISS. Re-evaluate old image rejections that depended on the superseded blanket rules; reuse unchanged source/OCR evidence where valid. Never promote prior failures automatically to PASS.
After edits, encode once from the finished master to quality-first WebP (lossless if needed). Keep responsive image behavior. Record source/final dimensions and bytes, quality setting, upscaling status, source/final hashes, tool, review method, decisions and reasons. Fresh media HTTP/image Content-Type checks and target binding remain required for publication; cache approval is not publication acceptance.

## Queue completion
Every valid input link remains an obligation until published and read back, or explicitly resolved as unavailable/serious-risk. Image difficulty, repair failure and missing optional information are not permanent skip reasons.
Use per-item pending repair/source/review states, continue other eligible products and revisit pending items with a materially different repair or additional evidence; do not hot-loop failures. Never reset retry counters or clear holds without resolving their actual causes.
Treat a single 404 observation as evidence, not proof of permanent delisting. Login/CAPTCHA and tool failures are distinct from unavailable products. Confirm unavailable sources as far as permitted and record evidence.
Missing essential SKU/price/source facts must be completed, never fabricated. Critical unresolved issues keep that item unpublished and visible as unfinished; they do not erase it from the queue or imply batch completion. Ask the user only for necessary representative decisions or actions the agent cannot perform.
This image policy does not lift tool stops, source access restrictions, provenance checks, SKU/price integrity or site isolation. Do independent local repair/API reconciliation only where authorized. A Skill edit alone does not prove runtime guards were updated: inspect their actual predicates before claiming production adoption.
