"""Print-ready monochrome charts from report results, without recalculation."""

from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def result_chart(rows: list[tuple[str, Decimal]], *, line: bool = False) -> BytesIO:
    """Render values with ASCII axis labels; localized captions live in Word."""
    image = Image.new("RGB", (1500, 650), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    left, top, right, bottom = 140, 60, 1450, 555
    values = [float(value) for _, value in rows]
    maximum = max(values, default=0) or 1
    minimum = min(0, min(values, default=0))
    span = (maximum - minimum) * 1.15

    def y(value: float) -> float:
        return bottom - (value - minimum) / span * (bottom - top)

    for tick in range(6):
        value = minimum + span * tick / 5
        yy = y(value)
        draw.line((left, yy, right, yy), fill="#dddddd", width=2)
        draw.text((left - 15, yy), f"{value:.2f}", font=font, fill="black", anchor="rm")
    draw.text((left, 15), "tCO2e", font=font, fill="black")
    draw.line((left, top, left, bottom), fill="black", width=2)
    draw.line((left, y(0), right, y(0)), fill="black", width=2)
    step = (right - left) / max(1, len(rows))
    points = []
    for index, ((label, _), value) in enumerate(zip(rows, values, strict=True)):
        x = left + step * (index + 0.5)
        yy = y(value)
        points.append((x, yy))
        if not line:
            draw.rectangle((x - step * 0.28, min(yy, y(0)), x + step * 0.28, max(yy, y(0))), fill="#666666")
        draw.text((x, bottom + 25), label, font=font, fill="black", anchor="mt")
        draw.text((x, yy - 15), f"{value:.4f}", font=font, fill="black", anchor="mb")
    if line and points:
        if len(points) > 1:
            draw.line(points, fill="black", width=4)
        for x, yy in points:
            draw.ellipse((x - 6, yy - 6, x + 6, yy + 6), fill="black")
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


def contribution_bar(value: Decimal, maximum: Decimal, *, signed: bool = False) -> BytesIO:
    """Render a bar; Word supplies the adjacent Chinese label and exact value."""
    image = Image.new("RGB", (480, 48), "white")
    draw = ImageDraw.Draw(image)
    zero = 240 if signed else 2
    draw.line((zero, 2, zero, 46), fill="#999999", width=2)
    if maximum and value:
        end = zero + float(value / maximum) * (235 if signed else 473)
        draw.rectangle((min(zero, end), 8, max(zero, end), 40), fill="#555555")
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
