# Image Rules

## Objective

Use images to increase click-through, product understanding and conversion while keeping pages fast and removing supplier identity.

## Highest-priority adaptive rule

Audit the actual supplier image set before choosing a featured image, gallery size, image roles, detail-page modules, dimensions, or output count. Never apply one fixed image count, one fixed detail-page layout, or one fixed featured-image type to every product.

Use only real, product-supported information. Three valid product photos may be the complete and correct output when the supplier provides nothing else. Do not manufacture missing dimensions, materials, specifications, functions, packaging, accessories, benefits, or visual modules. Conversely, do not discard independently valuable, high-quality supplier assets merely to satisfy a gallery limit.

Classify useful evidence according to what actually exists: Featured, Gallery, Variation, Product Details, Features, Structure, Dimensions, Materials, Application/Usage, Packaging, Accessories, and Color Options. There is no required count for any role.

## Decision order

1. Inventory main, SKU/color, detail, and adjacent sliced-detail assets with dimensions and source order.
2. Deduplicate exact images.
3. Detect likely continuous sliced-detail groups before translating fragments independently.
4. Detect text/logo/contact information with OCR.
5. Classify visual content.
6. Decide from the whole-image context whether it helps a buyer understand, compare, trust, or purchase the product.
7. Repair, crop, reconstruct, or translate a partly useful image where practical.
8. Reject the entire image only when it has no meaningful purchase value, cannot be repaired reasonably, is severely low quality, or is unrelated.
9. Assign roles from the evidence available.
10. Generate natural filename/ALT metadata.
11. Compress after all edits.

## Delete

Delete images that are primarily:

- supplier/company promotion
- contact information
- QR codes
- factory/company portraits without product value
- certificates unrelated to the buyer decision
- severe watermark/advertising overlays that cannot be cleanly repaired
- duplicates
- very low-quality images
- unrelated products

Do not make deletion decisions from keywords alone. If part of an image contains real buyer value, prefer repairing, masking, cropping, or removing the irrelevant region while retaining the useful product information. Record the context and evidence for every keep/reject decision.

## Repair instead of crop

When a removable logo/watermark/text region does not cover critical product detail:

- detect region
- create mask
- inpaint/reconstruct background
- do not prefer cropping as the default solution

Never remove a mark if the user does not have the right to use the underlying image.

## Valuable Chinese graphics

Keep useful dimensions, structure, material, function, specification and usage graphics. Replace Chinese with natural English while preserving the underlying real product imagery.

## Featured image

Rank viable candidates in this order:

`image quality → resolution → product clarity → composition/click appeal → product relevance → multi-color value`

Multi-color is only an additional merchandising advantage. Never select a low-resolution, blurry, badly composed, poorly proportioned, or product-too-small multi-color image over a sharp, attractive, high-resolution single-product image. When high-quality multi-color and single-product candidates are otherwise close, prefer the multi-color image for its commercial display value.

The featured image must represent the real product and remain clear in WooCommerce product cards and the product page. Do not mistake simple upscaling of a small blurry source for a high-resolution image.

### Quality gate and scoring

Multi-color is a merchandising bonus, not an automatic choice. First reject candidates below a practical minimum for sharpness and resolution. Then score viable candidates using: image quality/sharpness and resolution 30%, product prominence and clarity 20%, composition/click appeal 20%, product relevance 15%, multi-color merchandising value 10%, and clean background 5%.

A sharp, high-resolution single-product image can beat a low-quality multi-color image. When other criteria are close, prefer the high-quality multi-color candidate.

## Featured canvas and aspect-ratio adaptation

When the best source image does not fit the store's product-card aspect ratio, adapt it according to the evidence and visual quality:

- resize proportionally;
- add padding or extend the canvas;
- use background extension when it can be done cleanly;
- keep the product's real proportions and its important details sharp.

Never stretch the product to force a square. Never treat a clearly small or low-resolution image as high quality merely because it was enlarged.

## Continuous sliced-detail reconstruction

1688 detail pages often split one long design into adjacent image slices. Detect candidate groups using source order, matching width, edge continuity, background continuity, connected patterns or lines, continuing typography/layout, and semantic continuation between lower and upper edges.

When the evidence confirms one continuous design, reconstruct it before translation or final layout:

1. Remove captured 1688 UI, navigation, tabs, and unrelated page areas.
2. Remove supplier logos, contact information, QR codes, and unrelated promotion while retaining real product information.
3. If both slices are wholly useful, preserve both and join them without a visible seam.
4. If only part of a slice is useful, crop the irrelevant region and then join the remaining content when continuity is still valid.
5. Record the source filenames, seam evidence, crops, reconstruction output, and confidence in the audit.

Do not join images solely because their widths match. Do not independently translate fragments first when they belong to one design; otherwise typography, spacing, and context can become inconsistent.

## Reconstructed detail-image web adaptation

Do not mechanically keep an extremely long or heavy reconstructed image. Based on content boundaries, reading flow, mobile/desktop legibility, and page weight, either keep one reasonably sized continuous image or divide it into 2–N coherent modules such as Product Structure, Features, Specifications, or Application. The number of modules must follow the content, never a fixed target.

Preserve resolution sufficient for readable detail while optimizing load performance. Avoid duplicate use of the same reconstructed content across Gallery and Description unless each placement adds clear buyer value.

## Chinese text in sliced designs

For valuable Chinese text inside a confirmed sliced design, first reconstruct the complete structure and then run:

`OCR → translation → mask → inpainting/background reconstruction → English layout`

Translate only real product information. Remove rather than translate supplier identity, logos, contact details, QR codes, and unrelated promotion. Keep English typography, spacing, hierarchy, and terminology consistent across the completed design.

## Retention-first selection

Optimize for retaining real, high-quality, sales-relevant product information rather than deleting aggressively. Keep a product display, multi-angle, application, detail, feature, structure/disassembly, dimensions, material, specification, color/SKU, packaging, or accessory image when it is real, relevant, and independently useful to a buyer. Text alone is never a deletion reason.

Delete only exact/near duplicates, unrelated images, severely blurry images, low-quality images with no useful product information, company/factory promotion, contact information, QR codes, supplier identity, or advertising/watermarks too extensive to repair reasonably. Do not delete an independently useful high-quality image merely because the Gallery already has many images.

## Chinese buyer-information graphics

For a Chinese graphic with purchase value, use OCR, translate to natural English, mask the original Chinese, inpaint/reconstruct the background, relayout the English, and retain the image. Remove rather than translate company names, logos, contact details, QR codes, supplier identity, and supplier advertising.

## Role separation and audit trail

Assign each source image one or more of `featured`, `gallery`, `variation`, `description`, or `reject`. Gallery supports rapid browsing; Long Description supports explanation, persuasion, and conversion. A high-quality structural or specification image that is unsuitable for Gallery can still be retained for Description.

For every original image, record dimensions, resolution, sharpness_score, information_value, detected_text, role, keep/reject decision, and rejection_reason when rejected. Never discard an image without an explicit reason.


## Gallery

No hard image-count target. Use enough images to answer buyer questions without repetitive clutter. A sparse supplier set may legitimately produce a very small gallery. A rich supplier set may justify more images when each adds distinct buyer value.

## Variations

Match color/pattern visually. Same color across sizes may share an image. Never knowingly bind the wrong color.

## Description images

Use images that explain product structure, dimensions, material, features, details, packaging or application. Place them near the corresponding text rather than dumping every image into the top gallery.

## SEO metadata

Filename: concise descriptive English, lowercase/hyphenated where practical.

ALT: describe what is actually visible. Use relevant product language naturally; do not keyword-stuff and do not force unique keywords merely to make every image different.

## Performance

Optimize final edited assets to WebP where suitable. Use adaptive dimensions/quality based on visual complexity and intended role. Preserve acceptable visual quality and avoid unnecessarily large dimensions/files. Keep WordPress responsive image generation/srcset intact.
