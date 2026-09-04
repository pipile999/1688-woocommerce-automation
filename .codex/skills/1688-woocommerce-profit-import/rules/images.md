# Image Rules

## Objective

Use images to increase click-through, product understanding and conversion while keeping pages fast and removing supplier identity.

## Decision order

1. Deduplicate exact images.
2. Reject clearly irrelevant/non-product assets.
3. Detect text/logo/contact information with OCR.
4. Classify visual content.
5. Decide whether information in the image has buyer value.
6. Repair/translate valuable images where practical.
7. Assign roles.
8. Generate natural filename/ALT metadata.
9. Compress after all edits.

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

Prefer a visually strong multi-color collection image for multi-color products. It may show one or two extra colors beyond current SKU availability under the user's business rule. Reject it as featured only when quality/relevance/clarity is materially worse than another candidate or it contains problematic supplier identity/advertising.

Fallback: best representative single-product image.

## Gallery

No hard image-count target. Use enough images to answer buyer questions without repetitive clutter.

## Variations

Match color/pattern visually. Same color across sizes may share an image. Never knowingly bind the wrong color.

## Description images

Use images that explain product structure, dimensions, material, features, details, packaging or application. Place them near the corresponding text rather than dumping every image into the top gallery.

## SEO metadata

Filename: concise descriptive English, lowercase/hyphenated where practical.

ALT: describe what is actually visible. Use relevant product language naturally; do not keyword-stuff and do not force unique keywords merely to make every image different.

## Performance

Optimize final edited assets to WebP where suitable. Use adaptive dimensions/quality based on visual complexity and intended role. Preserve acceptable visual quality and avoid unnecessarily large dimensions/files. Keep WordPress responsive image generation/srcset intact.
