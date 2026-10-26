"""평가 결과를 README용 막대그래프(SVG)로 그린다. 외부 라이브러리 없이 SVG 문자열을 만든다.

SVG는 이미지로 임베드되므로 페이지 테마와 무관하게 읽히도록 불투명한 밝은 카드 배경을 쓴다.
색은 dataviz 기본 팔레트 slot 1~3(밝은 모드)이며 validate_palette.js(CVD ΔE 9.2, 일반 시야 ΔE 27.6)를 통과했다.
aqua는 배경 대비가 3:1 미만이므로 모든 막대 끝에 값 라벨을 붙이고, README에는 같은 값을 표로도 싣는다.
"""
from html import escape
from pathlib import Path

from scripts.chat_eval.report import MAIN_METRICS, METRIC_LABELS, group_scores

SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
FONT = "system-ui, -apple-system, 'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif"

GROUP_NAMES = {
    "category": "질문 카테고리",
    "prompt_style": "프롬프트 스타일",
    "traveler_type": "여행자 유형",
    "persona": "페르소나",
    "language": "언어",
}

WIDTH, LABEL_W, RIGHT_PAD = 760, 214, 64
BAR_H, BAR_GAP, GROUP_GAP, TOP = 16, 2, 14, 86


def _bar_path(x0: float, y: float, x1: float, h: float, radius: float = 4) -> str:
    """기준선 쪽은 직각, 값 끝은 4px 둥글게."""
    r = min(radius, (x1 - x0) / 2, h / 2)
    return (
        f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} A{r},{r} 0 0 1 {x1:.1f},{y + r:.1f} "
        f"V{y + h - r:.1f} A{r},{r} 0 0 1 {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z"
    )


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def render_svg(title: str, subtitle: str, groups: list[tuple[str, list[float | None]]], series_names: list[str]) -> str:
    """groups: [(라벨, [시리즈별 0~1 값 또는 None])]"""
    n_series = len(series_names)
    plot_x0, plot_x1 = LABEL_W, WIDTH - RIGHT_PAD
    group_h = n_series * BAR_H + (n_series - 1) * BAR_GAP
    height = TOP + len(groups) * (group_h + GROUP_GAP) + 22

    def scale(value: float) -> float:
        return plot_x0 + (plot_x1 - plot_x0) * value

    summary = " / ".join(
        f"{label}: " + ", ".join(f"{name} {_percent(value)}" for name, value in zip(series_names, values))
        for label, values in groups
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'role="img" aria-labelledby="t d" font-family="{FONT}">',
        f'<title id="t">{escape(title)}</title>',
        f'<desc id="d">{escape(summary)}</desc>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" fill="{SURFACE}" stroke="{GRID}"/>',
        f'<text x="24" y="34" font-size="16" font-weight="600" fill="{INK}">{escape(title)}</text>',
        f'<text x="24" y="54" font-size="12" fill="{INK_2}">{escape(subtitle)}</text>',
    ]

    if n_series > 1:  # 범례는 시리즈가 둘 이상일 때만 둔다.
        x = 24
        for color, name in zip(SERIES_COLORS, series_names):
            parts.append(f'<rect x="{x}" y="64" width="10" height="10" rx="2" fill="{color}"/>')
            parts.append(f'<text x="{x + 16}" y="73" font-size="12" fill="{INK_2}">{escape(name)}</text>')
            x += 16 + 8 * len(name) + 26

    for tick in (0, 25, 50, 75, 100):
        x = scale(tick / 100)
        stroke = AXIS if tick == 0 else GRID
        parts.append(f'<line x1="{x:.1f}" y1="{TOP - 8}" x2="{x:.1f}" y2="{height - 22}" stroke="{stroke}" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 6}" font-size="11" text-anchor="middle" fill="{INK_2}">{tick}%</text>')

    for index, (label, values) in enumerate(groups):
        y0 = TOP + index * (group_h + GROUP_GAP)
        parts.append(
            f'<text x="{LABEL_W - 12}" y="{y0 + group_h / 2 + 4:.1f}" font-size="13" text-anchor="end" fill="{INK}">{escape(label)}</text>'
        )
        for s, (color, value) in enumerate(zip(SERIES_COLORS, values)):
            y = y0 + s * (BAR_H + BAR_GAP)
            if value is None:
                parts.append(f'<text x="{plot_x0 + 8}" y="{y + BAR_H - 4}" font-size="12" fill="{INK_2}">-</text>')
                continue
            x1 = scale(value)
            if x1 - plot_x0 >= 1:
                parts.append(f'<path d="{_bar_path(plot_x0, y, x1, BAR_H)}" fill="{color}"/>')
            parts.append(f'<text x="{x1 + 6:.1f}" y="{y + BAR_H - 4}" font-size="12" fill="{INK}">{value * 100:.1f}%</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def build_chart(results: list[dict], by: str, metrics: list[str] | None, title: str | None, out: Path) -> Path:
    """results: report.load_result() 결과 1~2개. 2개면 앞이 before, 뒤가 after."""
    runs = [(result["meta"].get("tag") or result["meta"].get("experiment"), result["rows"]) for result in results]
    meta = results[-1]["meta"]
    subtitle = " · ".join([f"{meta.get('split')} {len(runs[-1][1])}문항", f"챗봇 {meta.get('chat_model')}", f"채점 {meta.get('judge')}"])

    if by == "overall":
        groups = []
        for metric in metrics or list(MAIN_METRICS):
            scored = [group_scores(rows, "overall", metric)["전체"] for _, rows in runs]
            if any(value is not None for value, _ in scored):
                groups.append((f"{METRIC_LABELS[metric]} (n={scored[-1][1]})", [value for value, _ in scored]))
        series_names = [name for name, _ in runs]
        default_title = "챗봇 평가 지표"
    elif len(runs) == 2:  # 전후 비교: 지표 하나를 그룹별로 비교한다.
        metric = (metrics or ["answer_correctness"])[0]
        before, after = (group_scores(rows, by, metric) for _, rows in runs)
        groups = [(f"{label} (n={after[label][1]})", [before[label][0], after[label][0]]) for label in after]
        series_names = [name for name, _ in runs]
        default_title = f"{METRIC_LABELS[metric]} · {GROUP_NAMES[by]}별"
    else:  # 한 번의 실행: 지표 여러 개를 그룹별로 보여준다.
        chosen = (metrics or ["source_condition_rate", "answer_correctness", "faithfulness"])[: len(SERIES_COLORS)]
        rows = runs[0][1]
        per_metric = [group_scores(rows, by, metric) for metric in chosen]
        groups = [
            (f"{label} (n={sum(row[by] == label for row in rows)})", [scores[label][0] for scores in per_metric])
            for label in per_metric[0]
        ]
        series_names = [METRIC_LABELS[metric] for metric in chosen]
        default_title = f"{GROUP_NAMES[by]}별 지표"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(title or default_title, subtitle, groups, series_names) + "\n", encoding="utf-8")
    return out
