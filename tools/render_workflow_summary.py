from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "workflow_summary.jpg"

W, H = 2400, 3400
img = Image.new("RGB", (W, H), "#f6f8fb")
d = ImageDraw.Draw(img)

FONT_REGULAR = "C:/Windows/Fonts/malgun.ttf"
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
F_TITLE = ImageFont.truetype(FONT_BOLD, 62)
F_SUB = ImageFont.truetype(FONT_BOLD, 38)
F_BOX = ImageFont.truetype(FONT_BOLD, 29)
F_SMALL = ImageFont.truetype(FONT_REGULAR, 25)
F_TINY = ImageFont.truetype(FONT_REGULAR, 22)

COLORS = {
    "ink": "#152033",
    "muted": "#5d6678",
    "line": "#61708a",
    "blue": "#dceeff",
    "blue_border": "#3b82f6",
    "green": "#ddf7e6",
    "green_border": "#22a06b",
    "orange": "#fff1d7",
    "orange_border": "#f59e0b",
    "purple": "#eee7ff",
    "purple_border": "#8b5cf6",
    "red": "#ffe1e1",
    "red_border": "#ef4444",
    "gray": "#eef2f7",
    "gray_border": "#94a3b8",
    "white": "#ffffff",
}


def text_size(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = d.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if len(words) == 1:
        line = ""
        lines = []
        for ch in text:
            if text_size(line + ch, font)[0] <= max_width:
                line += ch
            else:
                if line:
                    lines.append(line)
                line = ch
        if line:
            lines.append(line)
        return lines

    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if text_size(candidate, font)[0] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def center_text(x: int, y: int, w: int, text: str, font: ImageFont.FreeTypeFont, fill: str = COLORS["ink"]):
    tw, _ = text_size(text, font)
    d.text((x + (w - tw) / 2, y), text, font=font, fill=fill)


def draw_panel(x: int, y: int, w: int, h: int, title: str, accent: str):
    d.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=COLORS["white"], outline="#d6dde8", width=3)
    d.rounded_rectangle((x, y, x + 12, y + h), radius=8, fill=accent)
    d.text((x + 34, y + 24), title, font=F_SUB, fill=COLORS["ink"])


def draw_box(
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    fill: str,
    outline: str,
    font: ImageFont.FreeTypeFont = F_BOX,
    radius: int = 18,
    align: str = "center",
):
    d.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill, outline=outline, width=3)
    lines: list[str] = []
    for part in text.split("\n"):
        lines.extend(wrap_text(part, font, w - 28))

    line_h = text_size("가", font)[1] + 9
    total_h = line_h * len(lines)
    ty = y + (h - total_h) / 2
    for line in lines:
        tw, _ = text_size(line, font)
        tx = x + 16 if align == "left" else x + (w - tw) / 2
        d.text((tx, ty), line, font=font, fill=COLORS["ink"])
        ty += line_h


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = COLORS["line"], width: int = 4):
    d.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 14
    p1 = (x2, y2)
    p2 = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
    p3 = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
    d.polygon([p1, p2, p3], fill=color)


center_text(0, 56, W, "청년 정책 추천/상담 시스템 수정 사항 전체 도식", F_TITLE)
center_text(0, 132, W, "DB 통합부터 추천 로직, UI, 정책별 챗봇, 예외 처리, 신청 방법 상담까지", F_SMALL, COLORS["muted"])

draw_panel(90, 210, 2220, 410, "1. 전체 수정 흐름", "#3b82f6")
steps = ["기존 추천\n시스템", "정책 DB\n확장", "통합 검색\n테이블", "조건 추출\n고도화", "검색/추천\n개선", "UI/챗봇\n강화"]
box_w, box_h, start_x, gap, cy = 300, 110, 170, 60, 380
for i, step in enumerate(steps):
    x = start_x + i * (box_w + gap)
    fill, border = (COLORS["blue"], COLORS["blue_border"]) if i < 3 else (COLORS["green"], COLORS["green_border"])
    draw_box(x, cy, box_w, box_h, step, fill, border)
    if i < len(steps) - 1:
        arrow(x + box_w + 6, cy + box_h / 2, x + box_w + gap - 8, cy + box_h / 2)

draw_panel(90, 670, 2220, 610, "2. DB / 통합 검색 구조", "#22a06b")
sources = ["policies_processed", "hrd_trainings", "kstartup_notices", "smallloan_youth", "myhome_notices", "rental_houses"]
source_x, source_y = 160, 780
for i, src in enumerate(sources):
    y = source_y + i * 72
    draw_box(source_x, y, 360, 54, src, COLORS["gray"], COLORS["gray_border"], font=F_SMALL, radius=12)
    arrow(source_x + 360, y + 27, 840, 1000, width=3)

draw_box(850, 915, 420, 170, "search_documents\n통합 검색 테이블", COLORS["green"], COLORS["green_border"])
cols = ["domain", "source_table / source_id", "doc_id", "region_sido / region_sigungu", "employment_status", "title / summary / search_text"]
for i, col in enumerate(cols):
    y = 775 + i * 72
    draw_box(1530, y, 560, 54, col, "#f7fbff", COLORS["blue_border"], font=F_SMALL, radius=12, align="left")
    arrow(1275, 1000, 1520, y + 27, width=3)

draw_panel(90, 1330, 2220, 690, "3. 추천 Workflow", "#f59e0b")
x0, y0 = 160, 1450
nodes = [
    ("사용자 입력", COLORS["blue"], COLORS["blue_border"]),
    ("조건 신호 검사", COLORS["orange"], COLORS["orange_border"]),
    ("조건 추출\n나이/지역/관심/재직", COLORS["orange"], COLORS["orange_border"]),
    ("domain 힌트\n선필터/분산 top-k", COLORS["purple"], COLORS["purple_border"]),
]
for i, (txt, fill, border) in enumerate(nodes):
    x = x0 + i * 500
    draw_box(x, y0, 380, 105, txt, fill, border)
    if i < len(nodes) - 1:
        arrow(x + 380, y0 + 52, x0 + (i + 1) * 500 - 8, y0 + 52)
arrow(x0 + 380, y0 + 52, x0 + 520, y0 + 210)
draw_box(x0 + 450, y0 + 210, 500, 92, "조건 부족 / 이상 프롬프트\n추천 중단 + 안내 메시지", COLORS["red"], COLORS["red_border"], font=F_SMALL)
bottom = [
    ("지역 필터/정렬\n시도·시군구 우선", COLORS["green"], COLORS["green_border"]),
    ("전국 단위 정책\n다른 시도보다 우선", COLORS["green"], COLORS["green_border"]),
    ("FAISS 또는\n키워드 fallback", COLORS["blue"], COLORS["blue_border"]),
    ("추천 카드\n근거/점수/출처 표시", COLORS["blue"], COLORS["blue_border"]),
]
yb = 1750
for i, (txt, fill, border) in enumerate(bottom):
    x = x0 + i * 500
    draw_box(x, yb, 380, 105, txt, fill, border)
    if i < len(bottom) - 1:
        arrow(x + 380, yb + 52, x0 + (i + 1) * 500 - 8, yb + 52)
arrow(x0 + 3 * 500 + 190, y0 + 105, x0 + 190, yb - 8)

draw_panel(90, 2070, 2220, 800, "4. 정책별 챗봇 Workflow", "#8b5cf6")
chat_nodes = ["정책 카드에서\n상담 시작", "/chat 호출", "통합 문서 조회", "원본 테이블 row\n재조회", "policy_profile\n구조화"]
for i, txt in enumerate(chat_nodes):
    x = 150 + i * 420
    draw_box(x, 2195, 320, 100, txt, COLORS["purple"], COLORS["purple_border"], font=F_SMALL)
    if i < len(chat_nodes) - 1:
        arrow(x + 320, 2245, 150 + (i + 1) * 420 - 8, 2245)
draw_box(320, 2395, 560, 145, "사용자 조건과 정책 조건 비교\n나이 / 지역 / 재직 여부 / 관심분야 / 소득·주거", COLORS["green"], COLORS["green_border"], font=F_SMALL)
arrow(1830, 2295, 880, 2467)
draw_box(1030, 2380, 350, 95, "질문 의도 분기", COLORS["orange"], COLORS["orange_border"])
arrow(880, 2467, 1022, 2428)
branches = [
    ("조건/필요한 것", "서류·조건·지원내용\n신청방법까지 구조화"),
    ("신청 방법", "신청 경로·기간·링크\n서류·문의처 리스트업"),
    ("기타 질문", "정책 DB 안에서\n대화형 답변"),
]
for i, (head, body) in enumerate(branches):
    y = 2500 + i * 105
    draw_box(1560, y, 480, 78, f"{head}\n{body}", COLORS["blue"], COLORS["blue_border"], font=F_TINY)
    arrow(1380, 2428, 1552, y + 39)

draw_panel(90, 2920, 2220, 370, "5. 최종 결과", "#ef4444")
finals = ["지역/domain 기반 추천 정확도 개선", "추천 근거·점수·출처 시각화", "정책별 맞춤 챗봇 상담", "조건 부족/이상 입력 방어", "신청 방법 상세 리스트업"]
for i, item in enumerate(finals):
    x = 160 + i * 425
    draw_box(x, 3040, 350, 120, item, "#ffffff", COLORS["red_border"], font=F_SMALL)
    if i < len(finals) - 1:
        arrow(x + 350, 3100, 160 + (i + 1) * 425 - 8, 3100, color="#ef4444")
center_text(0, 3330, W, "생성일: 2026-06-03 · 청년 정책 추천/상담 AI 프로젝트", F_TINY, COLORS["muted"])

img.save(OUT, quality=95, subsampling=0)
print(str(OUT.resolve()))
