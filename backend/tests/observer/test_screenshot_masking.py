"""Unit tests for screenshot bounding box blurring with Pillow."""

from io import BytesIO

from PIL import Image, ImageDraw

from app.observer.masking import blur_bounding_boxes


def _create_test_image(width: int = 120, height: int = 120) -> bytes:
    """Create a test PNG image with a solid white background and a contrasting high-contrast rectangle."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw a solid black rectangle from (30, 30) to (70, 70)
    draw.rectangle([30, 30, 70, 70], fill=(0, 0, 0))
    # Draw high-contrast alternating lines inside the box
    draw.line([30, 30, 70, 70], fill=(255, 0, 0), width=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_blur_bounding_box_mutates_inside_and_preserves_outside() -> None:
    original_bytes = _create_test_image(120, 120)
    orig_img = Image.open(BytesIO(original_bytes)).convert("RGB")

    box = {"x": 30.0, "y": 30.0, "width": 40.0, "height": 40.0}
    blurred_bytes = blur_bounding_boxes(original_bytes, [box], radius=15)
    blurred_img = Image.open(BytesIO(blurred_bytes)).convert("RGB")

    assert orig_img.size == blurred_img.size

    # Pixels far outside the bounding box must remain identical
    outside_coords = [(5, 5), (10, 10), (100, 100), (110, 5), (5, 110)]
    for ox, oy in outside_coords:
        assert orig_img.getpixel((ox, oy)) == blurred_img.getpixel((ox, oy))

    # Pixels inside the blurred region (especially along contrasting borders) must be mutated
    mutated_pixels = 0
    for x in range(30, 71):
        for y in range(30, 71):
            if orig_img.getpixel((x, y)) != blurred_img.getpixel((x, y)):
                mutated_pixels += 1

    # Overwhelming majority of pixels inside the bounding box should be altered by the Gaussian blur
    assert mutated_pixels > 100


def test_blur_bounding_boxes_multiple() -> None:
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 50, 50], fill=(0, 0, 0))
    draw.rectangle([120, 10, 160, 50], fill=(0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    orig_bytes = buf.getvalue()

    boxes: list[dict[str, float]] = [
        {"x": 10.0, "y": 10.0, "width": 40.0, "height": 40.0},
        {"x": 120.0, "y": 10.0, "width": 40.0, "height": 40.0},
    ]
    result_bytes = blur_bounding_boxes(orig_bytes, boxes, radius=10)
    result_img = Image.open(BytesIO(result_bytes))

    # Center pixel between boxes should be untouched
    assert result_img.getpixel((85, 25)) == (255, 255, 255)


def test_blur_bounding_boxes_edge_cases() -> None:
    orig_bytes = _create_test_image(80, 80)

    # Empty inputs
    assert blur_bounding_boxes(b"", [{"x": 10.0, "y": 10.0, "width": 20.0, "height": 20.0}]) == b""
    assert blur_bounding_boxes(orig_bytes, []) == orig_bytes

    # Keys 'w' and 'h' supported alongside 'width' and 'height'
    res_wh = blur_bounding_boxes(orig_bytes, [{"x": 30.0, "y": 30.0, "w": 30.0, "h": 30.0}])
    assert res_wh != orig_bytes

    # Clamping out-of-bounds coordinates safely
    res_oob = blur_bounding_boxes(orig_bytes, [{"x": -10.0, "y": -10.0, "width": 200.0, "height": 200.0}])
    assert len(res_oob) > 0

    # Completely outside image bounds safely ignored
    res_far = blur_bounding_boxes(orig_bytes, [{"x": 500.0, "y": 500.0, "width": 100.0, "height": 100.0}])
    assert res_far == orig_bytes

    # Zero or negative dimensions ignored safely
    res_zero = blur_bounding_boxes(orig_bytes, [{"x": 10.0, "y": 10.0, "width": 0.0, "height": 0.0}])
    assert res_zero == orig_bytes

    # Invalid image bytes returned gracefully without unhandled exception
    assert (
        blur_bounding_boxes(b"not an image", [{"x": 0.0, "y": 0.0, "width": 10.0, "height": 10.0}])
        == b"not an image"
    )
