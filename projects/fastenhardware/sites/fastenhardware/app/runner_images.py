"""Offer-isolated local image adapter; no remote vision/generation API."""
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .image_pipeline import OCRAdapter, VisionClassifierAdapter, RembgAdapter, adaptive_quality_webp
from .runner_state import ReviewRequired, file_hash, read, save, digest
from .strict_cache import StrictCache, cache_key, specification_hash


def png(image):
    out = BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def contained(root, relative):
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("FAIL_CROSS_OFFER_PATH")
    return path


def phash(path):
    with Image.open(path) as source:
        gray = ImageOps.exif_transpose(source).convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    coeff = cv2.dct(np.asarray(gray, dtype=np.float32))[:8, :8].flatten()[1:]
    return tuple(bool(x > np.median(coeff)) for x in coeff)


def near(a, b):
    return sum(x != y for x, y in zip(a, b)) <= 4


def inventory(source, folder):
    result = []
    for item in source["raw_images"]:
        path = contained(folder / "raw_images", item["filename"])
        url = item.get("source_url") or item.get("url")
        if not url or url not in source["images"]:
            raise ValueError("FAIL_IMAGE_SOURCE_PROVENANCE")
        if str(item.get("source_offer_id", source["offer_id"])) != str(source["offer_id"]):
            raise ValueError("FAIL_IMAGE_OFFER_MISMATCH")
        with Image.open(path) as im:
            width, height = im.size
        result.append(dict(filename=item["filename"], path=str(path), raw_sha256=file_hash(path),
                           source_offer_id=str(source["offer_id"]), source_url=source["source_url"],
                           source_image_url=url, width=width, height=height,
                           main_pool=url in source.get("main_images", [])))
    return result


def validate_roles(records):
    top = [r for r in records if r["image_role"] in ("featured", "gallery")]
    details = [r for r in records if r["image_role"] == "description"]
    if not top or len(top) > 5:
        raise ReviewRequired("FEATURED_GALLERY_COUNT_INVALID")
    for r in top:
        if not r["main_pool"] or r["width"] != r["height"] or r["width"] < 600:
            raise ReviewRequired("FEATURED_NOT_NATIVE_QUALIFIED_MAIN_SQUARE")
    for a in top:
        for b in details:
            if near(a["phash"], b["phash"]):
                raise ReviewRequired("TOP_DESCRIPTION_PERCEPTUAL_DUPLICATE")
    return records


def confirmed_parameters(analysis, source):
    """OCR parameters must independently agree with source facts; no bare numbers."""
    result = {}
    source_text = re.sub(r"\s+", "", str(source)).casefold().replace("×", "*")
    labels = {"材质": "Material", "material": "Material", "尺寸": "Dimensions", "dimensions": "Dimensions",
              "重量": "Weight", "weight": "Weight", "装箱数量": "Packaging Quantity"}
    materials = {"塑料": "Plastic", "锌合金": "Zinc alloy", "铝合金": "Aluminum alloy", "不锈钢": "Stainless steel"}
    for detection in analysis["detections"]:
        if detection["score"] < .95:
            continue
        for label, name in labels.items():
            match = re.fullmatch(re.escape(label) + r"\s*[:：]\s*(.+)", detection["text"], re.I)
            if not match:
                continue
            value = match.group(1).strip()
            normalized = re.sub(r"\s+", "", value).casefold().replace("×", "*")
            if normalized not in source_text:
                continue
            if value in materials:
                result[name] = materials[value]
            elif re.fullmatch(r"\d+(?:\.\d+)?(?:\s*[*×x]\s*\d+(?:\.\d+)?){0,2}\s*(?:mm|cm|g|kg|pcs)", value, re.I):
                result[name] = value.replace("*", " × ")
    return result


def replay_existing(source, processed, folder, destination):
    """Offline test of saved bytes/lineage, not a new model or HTTP QA PASS."""
    raw = {r["filename"]: r for r in inventory(source, folder)}
    lineage = {}
    for path in sorted(folder.glob("quality-audit-*.json")):
        for row in read(path, {}).get("records", []):
            for key in ("relative", "replacement"):
                if row.get(key):
                    lineage[row[key]] = row
    records = []
    top = processed.get("images", [])
    detail = processed.get("description_images", [])
    for index, relative in enumerate(list(dict.fromkeys(top + detail))):
        evidence = lineage.get(relative, {})
        r = raw.get(evidence.get("source_filename"))
        path = contained(folder, relative)
        if not r or evidence.get("raw_sha256") != r["raw_sha256"] or evidence.get("final_sha256") != file_hash(path):
            raise ReviewRequired("EXISTING_IMAGE_HASH_LINEAGE_UNPROVEN")
        if str(evidence.get("source_offer_id")) != str(source["offer_id"]):
            raise ValueError("FAIL_IMAGE_OFFER_MISMATCH")
        with Image.open(path) as im:
            if im.format != "WEBP":
                raise ReviewRequired("FINAL_IMAGE_NOT_WEBP")
            width, height = im.size
        role = "featured" if relative == top[0] else "gallery" if relative in top else "description"
        records.append(dict(r, final_path=str(path), final_sha256=file_hash(path), width=width, height=height,
                            image_role=role, phash=phash(path), previous_visual_qa=evidence.get("visual_qa"),
                            qa_this_run="OFFLINE_BYTES_AND_GEOMETRY_ONLY", index=index))
    validate_roles(records)
    result = dict(records=records, mode="DRY_RUN_REPLAY", publication_qa="NOT_EXECUTED",
                  raw_count=len(raw), local_models_executed=False, warnings=[])
    save(destination / "image-audit.json", result)
    return dict(result, artifacts=[str(destination / "image-audit.json")] + [r["final_path"] for r in records])


class LocalImages:
    def __init__(self, root, cache_dir, rules_version):
        self.root, self.version = Path(root), rules_version
        self.cache = StrictCache(Path(cache_dir) / "image-ocr.sqlite", Path(cache_dir) / "image-cache-events.jsonl")
        self.ocr = self.clip = self.rembg = None

    def analyze(self, path, source):
        args = dict(offer_id=str(source["offer_id"]), source_url=source["source_url"], image_hash=file_hash(path),
                    spec_hash=specification_hash(source), rules_ver=self.version)
        key = cache_key(**args)
        cached = self.cache.lookup(key=key, offer_id=args["offer_id"])
        if cached:
            return dict(cached, cache_event="CACHE_HIT")
        if self.ocr is None:
            # Models must already be provisioned. No hidden model downloads in a batch.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            self.ocr, self.clip = OCRAdapter(), VisionClassifierAdapter()
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
        enhanced = Image.fromarray(cv2.createCLAHE(clipLimit=3, tileGridSize=(8, 8)).apply(gray)).convert("RGB")
        detections = []
        for view, im in (("original", image), ("clahe", enhanced)):
            analysis = self.ocr.analyze(png(im))
            detections.extend(dict(text=d.text, score=d.score, polygon=d.polygon, view=view) for d in analysis.detections)
        classified = self.clip.classify(png(image))
        _, qr, _ = cv2.QRCodeDetector().detectAndDecode(np.asarray(image))
        result = dict(detections=detections, text=list(dict.fromkeys(d["text"] for d in detections)),
                      classification=dict(label=classified.label, confidence=classified.confidence), qr_detected=qr is not None,
                      sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                      paddleocr_executed=True, openclip_executed=True, clahe_executed=True,
                      remote_vision_calls=0, image_sha256=args["image_hash"])
        self.cache.store(key=key, **args, result=result)
        return dict(result, cache_event="CACHE_MISS")

    def segmentation(self):
        if self.rembg is None:
            home = self.root / "models/rembg"
            if not list(home.rglob("isnet-general-use.onnx")):
                raise ReviewRequired("REMBG_MODEL_NOT_INSTALLED")
            self.rembg = RembgAdapter(home)
        return self.rembg

    def process(self, source, folder, destination, queue):
        destination.mkdir(parents=True, exist_ok=True)
        records, seen = [], {}
        specs = {}
        prior_records = read(destination / "image-audit.json", {}).get("records", [])
        for raw in inventory(source, folder):
            processing_identity = digest([source["offer_id"], source["source_url"], raw["raw_sha256"], specification_hash(source), self.version])
            prior = next((p for p in prior_records if p.get("processing_identity") == processing_identity), None)
            r = dict(raw, decision="reject", inpainting_executed=False, rembg_executed=False, processing_identity=processing_identity)
            if r["raw_sha256"] in seen:
                r.update(reason="SHA_DUPLICATE", duplicate_of=seen[r["raw_sha256"]])
                records.append(r)
                continue
            seen[r["raw_sha256"]] = r["filename"]
            if prior and prior.get("decision") == "keep" and Path(prior.get("final_path", "")).is_file() and file_hash(prior["final_path"]) == prior.get("final_sha256"):
                records.append(dict(prior, artifact_cache="CACHE_HIT"))
                specs.update(prior.get("confirmed_specs", {}))
                continue
            try:
                analysis = self.analyze(r["path"], source)
                r["source_analysis"] = analysis
                protected = re.compile(r"DIN|ISO|ANSI|ANS\b|M\d|\d+(?:[.,]\d+)?\s*(?:mm|cm|inch)|螺距|直径|长度|材质|等级|标准|thread|steel|grade|diameter|pitch|finish|coating|\b(?:8[.]8|10[.]9|12[.]9|A2|A4)\b", re.I)
                if any(protected.search(text) for text in analysis["text"]):
                    raise ReviewRequired("PROTECTED_PRODUCT_DATA: preserve original technical diagram; reviewed description treatment required")
                r["confirmed_specs"] = confirmed_parameters(analysis, source)
                specs.update(r["confirmed_specs"])
                with Image.open(r["path"]) as opened:
                    master = ImageOps.exif_transpose(opened).convert("RGB")
                if analysis["qr_detected"]:
                    raise ReviewRequired("QR_OR_CONTACT_GRAPHIC")
                label = analysis["classification"]["label"]
                if label != "product_photo" or analysis["classification"]["confidence"] < .70:
                    # Never call low-confidence local classification a visual PASS.
                    raise ReviewRequired("COMPLEX_GRAPHIC_OR_UNCERTAIN_PRODUCT_CLASS")
                if analysis["sharpness"] < 15 or min(master.size) < 600:
                    raise ReviewRequired("NATIVE_RESOLUTION_OR_SHARPNESS_TOO_LOW")
                if analysis["text"]:
                    # Unknown text may be a brand/specification: keep evidence for review.
                    pollution = re.compile(r"1688|https?[:/]|www\.|\.com|公司|店铺|微信|联系|工厂|shop|wechat|supplier", re.I)
                    if any(not pollution.search(t) for t in analysis["text"]):
                        raise ReviewRequired("TEXT_MEANING_OR_TRANSLATION_UNCERTAIN")
                    mask = Image.new("L", master.size, 0)
                    draw = ImageDraw.Draw(mask)
                    for d in analysis["detections"]:
                        draw.polygon([tuple(p) for p in d["polygon"]], fill=255)
                    mask = Image.fromarray(cv2.dilate(np.asarray(mask), np.ones((9, 9), np.uint8)))
                    cutout = self.segmentation().cutout(png(master))
                    core = cv2.erode((np.asarray(cutout.getchannel("A")) > 96).astype(np.uint8), np.ones((11, 11), np.uint8))
                    marked = np.asarray(mask) > 0
                    if np.count_nonzero(core & marked) / max(1, np.count_nonzero(marked)) > .05:
                        raise ReviewRequired("CONTAMINATION_COVERS_PRODUCT_CORE")
                    mask_path = destination / (r["raw_sha256"] + "-mask.png")
                    mask.save(mask_path)
                    r["mask_path"] = str(mask_path)
                    if np.mean(marked) < .025:
                        master = Image.fromarray(cv2.inpaint(np.asarray(master), np.asarray(mask), 3, cv2.INPAINT_TELEA))
                        r.update(inpainting_executed=True, inpainting_model="OpenCV TELEA; non-generative")
                    else:
                        master, cutout_qa = self.segmentation().on_neutral_square(png(master), background=(255, 255, 255))
                        r.update(rembg_executed=True, rembg_model="isnet-general-use", cutout_qa=cutout_qa)
                payload, quality = adaptive_quality_webp(master, source_dimensions=(r["width"], r["height"]),
                                                         source_filesize=Path(r["path"]).stat().st_size)
                final = destination / (r["raw_sha256"] + ".webp")
                final.write_bytes(payload)
                qa = self.analyze(final, source)
                if qa["text"] or qa["qr_detected"] or qa["classification"]["label"] != "product_photo" or qa["classification"]["confidence"] < .70:
                    raise ReviewRequired("FINAL_LOCAL_QA_UNCERTAIN")
                r.update(decision="keep", final_path=str(final), final_sha256=file_hash(final),
                         width=master.width, height=master.height, phash=phash(final),
                         quality=quality, final_analysis=qa, qa_method="local OCR+CLAHE+QR+OpenCLIP+OpenCV, no remote Vision")
            except ReviewRequired as exc:
                r["reason"] = str(exc)
                queue.add(source["offer_id"], "image", str(exc), {"filename": r["filename"], "sha256": r["raw_sha256"]})
            records.append(r)
            save(destination / "image-audit.json", dict(records=records, complete=False))
        candidates = sorted([r for r in records if r["decision"] == "keep"],
                            key=lambda r: (r["source_analysis"]["classification"]["confidence"],
                                           r["source_analysis"]["sharpness"], r["width"] * r["height"]), reverse=True)
        unique = []
        for r in candidates:
            if any(near(r["phash"], x["phash"]) for x in unique):
                r.update(decision="reject", reason="PERCEPTUAL_DUPLICATE")
            else:
                unique.append(r)
        top = [r for r in unique if r["main_pool"] and r["width"] == r["height"] and r["width"] >= 600][:5]
        rest = [r for r in unique if r not in top][:10 - len(top)]
        selected = top + rest
        for r in unique:
            r["image_role"] = "featured" if top and r is top[0] else "gallery" if r in top else "description" if r in rest else "reject"
        result = dict(records=records, selected=selected, specs=specs, complete=True, mode="LOCAL_MODELS",
                      publication_qa="PASS" if top else "FAIL", warnings=[] if rest else ["insufficient_distinct_detail_material"])
        save(destination / "image-audit.json", result)
        validate_roles(selected)
        if source.get("detail_images") and not rest:
            raise ReviewRequired("DETAIL_MATERIAL_NEEDS_REVIEW; no usable distinct detail yet")
        return dict(result, records=selected, artifacts=[str(destination / "image-audit.json")] + [r["final_path"] for r in selected])
