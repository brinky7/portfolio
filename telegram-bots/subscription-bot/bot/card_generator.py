from PIL import Image, ImageDraw, ImageFont
import io

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO    = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

W, H = 800, 460

BG        = "#0F1923"
CARD_BG   = "#151F2E"
GREEN     = "#00C853"
RED       = "#FF1744"
YELLOW    = "#FFD600"
NEUTRAL   = "#607D8B"
TEXT      = "#E8EAF6"
MUTED     = "#78909C"
ACCENT    = "#1E88E5"
BORDER    = "#1E2D3D"


def _color(direction: str) -> str:
    d = direction.upper()
    if "BULL" in d or d == "LONG":
        return GREEN
    if "BEAR" in d or d == "SHORT":
        return RED
    return YELLOW


def _arrow(direction: str) -> str:
    d = direction.upper()
    if "BULL" in d or d == "LONG":
        return "▲"
    if "BEAR" in d or d == "SHORT":
        return "▼"
    return "◆"


def _fmt_price(price: float) -> str:
    if price >= 1000:
        return f"${price:,.2f}"
    if price >= 1:
        return f"${price:.4f}"
    return f"${price:.6f}"


def generate_signal_card(result: dict) -> bytes:
    symbol  = result["symbol"]
    price   = result["price"]
    st      = result["short_term"]["primary"]
    mt      = result["mid_term"]["primary"]

    st_dir  = st.get("direction", "NEUTRAL")
    st_conf = st.get("confidence", 0)
    mt_dir  = mt.get("direction", "NEUTRAL")
    mt_conf = mt.get("confidence", 0)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # card background
    draw.rounded_rectangle([20, 20, W - 20, H - 20], radius=18, fill=CARD_BG, outline=BORDER, width=1)

    # top accent line
    dir_color = _color(st_dir)
    draw.rounded_rectangle([20, 20, W - 20, 24], radius=4, fill=dir_color)

    # fonts
    f_logo   = ImageFont.truetype(FONT_BOLD,    18)
    f_symbol = ImageFont.truetype(FONT_BOLD,    54)
    f_price  = ImageFont.truetype(FONT_REGULAR, 26)
    f_badge  = ImageFont.truetype(FONT_BOLD,    22)
    f_label  = ImageFont.truetype(FONT_REGULAR, 14)
    f_value  = ImageFont.truetype(FONT_BOLD,    16)
    f_foot   = ImageFont.truetype(FONT_REGULAR, 13)

    # logo
    draw.text((44, 40), "BRINKY", font=f_logo, fill=ACCENT)
    draw.text((44, 60), "Signal Analysis", font=ImageFont.truetype(FONT_REGULAR, 12), fill=MUTED)

    # watermark right
    wm = "t.me/BrinkyAnalysisBot"
    wm_w = draw.textlength(wm, font=f_foot)
    draw.text((W - 44 - wm_w, 48), wm, font=f_foot, fill=MUTED)

    # divider
    draw.line([(44, 90), (W - 44, 90)], fill=BORDER, width=1)

    # symbol
    draw.text((44, 108), symbol.replace("USDT", ""), font=f_symbol, fill=TEXT)
    sym_w = draw.textlength(symbol.replace("USDT", ""), font=f_symbol)
    draw.text((44 + sym_w + 10, 138), "/USDT", font=f_price, fill=MUTED)

    # price
    price_str = _fmt_price(price)
    draw.text((44, 172), price_str, font=f_price, fill=TEXT)

    # short-term badge
    badge_x = 44
    badge_y = 220
    badge_text = f"{_arrow(st_dir)} {st_dir}  {st_conf:.0f}%"
    badge_w = draw.textlength(badge_text, font=f_badge) + 24
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + 38],
        radius=8,
        fill=dir_color + "33",
        outline=dir_color,
        width=1,
    )
    draw.text((badge_x + 12, badge_y + 8), badge_text, font=f_badge, fill=dir_color)

    # confidence bar
    bar_x, bar_y = 44, 275
    bar_w = W - 88
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 6], radius=3, fill=BORDER)
    fill_w = int(bar_w * st_conf / 100)
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 6], radius=3, fill=dir_color)

    # divider
    draw.line([(44, 300), (W - 44, 300)], fill=BORDER, width=1)

    # short / mid columns
    col1_x, col2_x = 44, W // 2 + 20
    row_y = 314

    draw.text((col1_x, row_y), "SHORT-TERM", font=f_label, fill=MUTED)
    draw.text((col2_x, row_y), "MID-TERM", font=f_label, fill=MUTED)

    st_text = f"{_arrow(st_dir)} {st_dir}"
    mt_text = f"{_arrow(mt_dir)} {mt_dir}"
    draw.text((col1_x, row_y + 20), st_text, font=f_value, fill=_color(st_dir))
    draw.text((col2_x, row_y + 20), mt_text, font=f_value, fill=_color(mt_dir))

    draw.text((col1_x, row_y + 42), f"{st['tf']} · {st_conf:.0f}% conf", font=f_label, fill=MUTED)
    draw.text((col2_x, row_y + 42), f"{mt['tf']} · {mt_conf:.0f}% conf", font=f_label, fill=MUTED)

    # footer
    draw.line([(44, H - 64), (W - 44, H - 64)], fill=BORDER, width=1)
    draw.text((44, H - 50), "Full multi-timeframe analysis  →  @BrinkyAnalysisBot", font=f_foot, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
