"""文档扫描单测（合成图片）。"""

from PIL import Image, ImageDraw

from package.document.scanner import process_image, scan_images


def _make_page(path):
    image = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 80), "Butler scan sample", fill="black")
    draw.rectangle([80, 200, 400, 320], outline="red", width=4)
    image.save(path)
    return path


def test_process_image_modes(tmp_path):
    page = _make_page(tmp_path / "page.png")
    for mode in ("color", "gray", "bw", "pencil", "charcoal"):
        array = process_image(page, mode=mode)
        assert array.ndim == 3 and array.shape[2] == 3


def test_scan_images_creates_pdf(tmp_path):
    pages = [_make_page(tmp_path / f"p{i}.png") for i in range(2)]
    output = tmp_path / "out.pdf"
    result = scan_images(pages, output, mode="color", keep_ink=True)
    assert output.is_file()
    assert result["pages"] == 2
    assert result["size"] > 0
