"""Screenshot bounding box blurring utility using Pillow."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageFilter


def blur_bounding_boxes(
    image_bytes: bytes,
    boxes: list[dict[str, float]],
    radius: int = 15,
) -> bytes:
    """Applies Gaussian blur to the specified bounding boxes [x, y, width, height]."""
    if not image_bytes or not boxes:
        return image_bytes

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            img_format = img.format or "PNG"
            work_img = img.copy()
            width, height = work_img.size

            applied_any = False
            for box in boxes:
                raw_x = box.get("x", 0.0)
                raw_y = box.get("y", 0.0)
                raw_w = box.get("width", box.get("w", 0.0))
                raw_h = box.get("height", box.get("h", 0.0))

                x = round(raw_x)
                y = round(raw_y)
                w = round(raw_w)
                h = round(raw_h)

                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(width, x + w)
                y2 = min(height, y + h)

                if x2 <= x1 or y2 <= y1:
                    continue

                crop_box = (x1, y1, x2, y2)
                cropped = work_img.crop(crop_box)
                blurred = cropped.filter(ImageFilter.GaussianBlur(radius=radius))
                work_img.paste(blurred, crop_box)
                applied_any = True

            if not applied_any:
                return image_bytes

            out = BytesIO()
            work_img.save(out, format=img_format)
            return out.getvalue()
    except Exception:
        return image_bytes
