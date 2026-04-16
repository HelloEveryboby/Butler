import io
import numpy as np
import cv2
from PIL import Image
from .lazy_import import lazy_import

# 延迟导入可选包
np = lazy_import("numpy")
try:
    cv2 = lazy_import("cv2")
except Exception:
    cv2 = None  # 修复协作错误
PIL = lazy_import("PIL")
pytesseract = lazy_import("pytesseract")


def pytesseract_get_text(img):
    # 列出pytesseract的属性，这将触发它的延迟加载
    attributes = dir(pytesseract)
    if pytesseract == None:
        raise ImportError("pytesseract模块无法导入.")

    result = pytesseract.image_to_string(img)
    return result


def pytesseract_get_text_bounding_boxes(img):
    # 转换PIL图像到NumPy数组
    img_array = np.array(img)

    # 将图像转换为灰度
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

    # 使用pytesseract从图像中获取数据
    d = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

    # 创建一个空列表来保存每个边界框的字典
    boxes = []

    # 根据其中一个属性列表的长度遍历检测到的框的数量
    for i in range(len(d["text"])):
        # 对于每个框，用您感兴趣的属性创建一个字典
        box = {
            "text": d["text"][i],
            "top": d["top"][i],
            "left": d["left"][i],
            "width": d["width"][i],
            "height": d["height"][i],
        }
        # 把这个方框字典添加到列表中
        boxes.append(box)

    return boxes


def find_text_in_image(img, text, debug=False):
    # Convert PIL Image to NumPy array
    img_array = np.array(img)

    # Convert the image to grayscale
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

    # Use pytesseract to get the data from the image
    d = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

    # Initialize an empty list to store the centers of the bounding boxes
    centers = []

    # Get the number of detected boxes
    n_boxes = len(d["level"])

    # Create a copy of the grayscale image to draw on
    img_draw = np.array(gray.copy())

    # Convert the img_draw grayscale image to RGB
    img_draw = cv2.cvtColor(img_draw, cv2.COLOR_GRAY2RGB)

    id = 0

    # Loop through each box
    for i in range(n_boxes):
        if debug:
            # (DEBUGGING) Draw each box on the grayscale image
            cv2.rectangle(
                img_draw,
                (d["left"][i], d["top"][i]),
                (d["left"][i] + d["width"][i], d["top"][i] + d["height"][i]),
                (0, 255, 0),
                2,
            )
            # Draw the detected text in the rectangle in small font
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            font_color = (0, 0, 255)
            line_type = 2

            cv2.putText(
                img_draw,
                d["text"][i],
                (d["left"][i], d["top"][i] - 10),
                font,
                font_scale,
                font_color,
                line_type,
            )

        
        if text.lower() in d["text"][i].lower():
        
            start_index = d["text"][i].lower().find(text.lower())
            start_percentage = start_index / len(d["text"][i])
            d["left"][i] = d["left"][i] + int(d["width"][i] * start_percentage)

            text_width_percentage = len(text) / len(d["text"][i])
            d["width"][i] = int(d["width"][i] * text_width_percentage)
            center = (
                d["left"][i] + d["width"][i] / 2,
                d["top"][i] + d["height"][i] / 2,
            )

            # Add the center to the list
            centers.append(center)

            # Draw the bounding box on the image in red and make it slightly larger
            larger = 10
            cv2.rectangle(
                img_draw,
                (d["left"][i] - larger, d["top"][i] - larger),
                (
                    d["left"][i] + d["width"][i] + larger,
                    d["top"][i] + d["height"][i] + larger,
                ),
                (255, 0, 0),
                7,
            )

            # Create a small black square background for the ID
            cv2.rectangle(
                img_draw,
                (
                    d["left"][i] + d["width"][i] // 2 - larger * 2,
                    d["top"][i] + d["height"][i] // 2 - larger * 2,
                ),
                (
                    d["left"][i] + d["width"][i] // 2 + larger * 2,
                    d["top"][i] + d["height"][i] // 2 + larger * 2,
                ),
                (0, 0, 0),
                -1,
            )

            # Put the ID in the center of the bounding box in red
            cv2.putText(
                img_draw,
                str(id),
                (
                    d["left"][i] + d["width"][i] // 2 - larger,
                    d["top"][i] + d["height"][i] // 2 + larger,
                ),
                cv2.FONT_HERSHEY_DUPLEX,
                1,
                (255, 155, 155),
                4,
            )

            # Increment id
            id += 1

    if not centers:
        word_centers = []
        for word in text.split():
            for i in range(n_boxes):
                if word.lower() in d["text"][i].lower():
                    center = (
                        d["left"][i] + d["width"][i] / 2,
                        d["top"][i] + d["height"][i] / 2,
                    )
                    center = (center[0] / 2, center[1] / 2)
                    word_centers.append(center)

        for center1 in word_centers:
            for center2 in word_centers:
                if (
                    center1 != center2
                    and (
                        (center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2
                    )
                    ** 0.5
                    <= 400
                ):
                    centers.append(
                        ((center1[0] + center2[0]) / 2, (center1[1] + center2[1]) / 2)
                    )
                    break
            if centers:
                break

    bounding_box_image = PIL.Image.fromarray(img_draw)
    bounding_box_image.format = img.format

    # Convert centers to relative
    img_width, img_height = img.size
    centers = [(x / img_width, y / img_height) for x, y in centers]

    # Debug by showing bounding boxes:
    # bounding_box_image.show()

    return centers
