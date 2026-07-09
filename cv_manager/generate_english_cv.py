"""
generate_english_cv.py
Generates an English version of CV_Crossing_Hurdles_Python_Developer_RemotePythonDev.pdf
starting from the master template (CV_Adatip_v3.pdf).
"""
import fitz
from pathlib import Path

TEMPLATE = str(Path(__file__).parent.parent / "data" / "cvs" / "CV_Adatip_v3.pdf")
OUTPUT   = str(Path(__file__).parent.parent / "data" / "cvs" / "CV_MLEngineer_English.pdf")

ARIAL      = "C:/Windows/Fonts/arial.ttf"
ARIAL_BOLD = "C:/Windows/Fonts/arialbd.ttf"

DARK    = (26/255, 26/255, 46/255)
GRAY_BG = (0.933, 0.933, 0.933)
PAGE_W  = 595.28

# ── Content ────────────────────────────────────────────────────────────────────

ABOUT = (
    "I am a final-year Electrical and Electronics Engineering student, graduating this May. "
    "I am eager to develop strong competencies in both hardware and software. "
    "I conduct my education entirely in English. Throughout my university life, I have been involved in various "
    "areas contributing to my technical and personal development and enabling me to adapt to professional work "
    "environments, including completing an internship. Having been involved in team sports since an early age, "
    "I am a disciplined, team-oriented engineering candidate, eager to learn and continuously improve. "
    "Most importantly, I learn new tasks quickly and always strive to deliver my best."
)

EXPERIENCE = {
    "company": "Ermas Electronics  -  Embedded Systems & Hardware Intern",
    "summary": (
        "I actively participated in team projects and field applications on embedded systems "
        "and microcontroller-based applications at Ermas Electronics."
    ),
    "bullets_label": "Key Responsibilities:",
    "bullets": [
        ("Firmware Development",
         "Coded and debugged embedded firmware for STM32-based applications."),
        ("Circuit Design and Testing",
         "Supported the design phases of microcontroller circuits and conducted prototype tests."),
        ("Hardware Production and Assembly",
         "Carried out manual soldering, cable preparation, and basic hardware assembly on the "
         "production line, gaining technical competency in the structure and practical applications "
         "of electronic components."),
    ],
}

PROJECTS = [
    {
        "name": "Electronic Circuit Design: 555 Timer and AC/DC Adapter",
        "desc": (
            "I designed an AC/DC adapter circuit that efficiently converts alternating current (AC) "
            "to direct current (DC), providing a stable power supply for electronic devices."
        ),
    },
    {
        "name": "Vibration Analysis in Industrial Motors with Machine Learning",
        "desc": (
            "I developed a system to detect bearing failures in industrial motors using vibration data, "
            "distinguishing inner race, outer race, and ball damage. I initially used FFT for frequency "
            "analysis, but found it insufficient for non-stationary signals. Switching to the Hilbert-Huang "
            "Transform significantly improved accuracy. I extracted features from sensor data and applied "
            "classification algorithms for the machine learning model."
        ),
    },
    {
        "name": "Home Energy Consumption Prediction Model",
        "desc": (
            "I analyzed electricity consumption data collected from IoT sensors using Python and Scikit-Learn. "
            "During data preprocessing, model accuracy was low due to missing and outlier values; "
            "I resolved this with normalization and feature engineering. "
            "I deployed the final model as a Flask API to provide real-time energy predictions."
        ),
    },
]

CERTIFICATIONS = [
    ("STM32 Certificate",                        "ST Microelectronics"),
    ("Core Signal Processing Techniques in MATLAB", "MathWorks"),
    ("Simulink Fundamentals",                    "MathWorks"),
    ("Simscape Onramp",                          "MathWorks"),
    ("Simulink Onramp",                          "MathWorks"),
    ("MATLAB Onramp",                            "MathWorks"),
]

SOCIAL = [
    "Yasar University American Football Team — 1x Turkey Championship",
    "Professional American Football — 1x Turkey Championship",
    "Development Projects Community Audit Board Chairmanship",
    "Volleyball Club Founding Member",
]

EDUCATION = [
    "Yasar University (2021 – 2026)",
    "Electrical and Electronics Engineering",
    "(100% English)",
]

LANGUAGES = [
    ("English",   "B2"),
    ("Turkish",   "Native"),
    ("Ukrainian", "Beginner"),
]

SKILLS = [
    "Python",
    "Machine Learning",
    "Signal Processing",
    "Data Preprocessing",
    "Feature Engineering",
    "Model Evaluation",
    "Algorithm Selection",
    "Communication Protocols",
]

HEADER = {
    "name":    "BERK INAN",
    "line2":   "Izmir/Bornova  |  +90 538 074 00 09",
    "line3":   "linkedin.com/in/berk-inan1  |  berkinan974@gmail.com",
}

REFERENCE = {
    "name": "· Asst. Prof. Dr. Mahir Kutay",
    "dept": "Yasar University, Electrical and Electronics Engineering",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _text_w(text: str, size: float) -> float:
    return fitz.get_text_length(text, fontname="helv", fontsize=size)


def _wrap(text: str, max_w: float, size: float) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if _text_w(test, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bar(page, x0, y0, x1, y1, label: str, size: float = 10.0):
    """Draw a gray section bar and write the label."""
    page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=GRAY_BG)
    page.insert_text(
        fitz.Point(x0 + 4, y0 + 12),
        label,
        fontsize=size,
        fontfile=ARIAL_BOLD,
        fontname="ArialBd",
        color=DARK,
    )


def _text(page, x, y, txt, size=8.0, bold=False):
    page.insert_text(
        fitz.Point(x, y),
        txt,
        fontsize=size,
        fontfile=ARIAL_BOLD if bold else ARIAL,
        fontname="ArialBd" if bold else "Arial",
        color=DARK,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def build():
    doc  = fitz.open(TEMPLATE)
    page = doc[0]

    LM   = 38.0   # left margin for text
    RM   = 561.3  # right margin
    BAR_X0 = 34.0
    BAR_X1 = RM
    BODY_W = RM - LM          # ~523 pt
    PROJ_W = 469.0            # project description wrap width

    # ── 1. Redact all variable regions ────────────────────────────────────────
    regions = [
        fitz.Rect(0,      28,    PAGE_W, 170.0),   # header + about text
        fitz.Rect(BAR_X0, 169.7, BAR_X1, 289.0),   # work experience section + bar
        fitz.Rect(BAR_X0, 278.7, BAR_X1, 450.0),   # projects section + bar
        fitz.Rect(BAR_X0, 449.7, BAR_X1, 515.0),   # certifications
        fitz.Rect(BAR_X0, 505.7, BAR_X1, 572.0),   # social
        fitz.Rect(BAR_X0, 570.7, BAR_X1, 720.0),   # edu/lang/skills section
        fitz.Rect(BAR_X0, 720.0, BAR_X1, 841.89),  # references
    ]
    for r in regions:
        page.add_redact_annot(r, fill=(1, 1, 1))
    page.apply_redactions()

    # ── 2. Header ─────────────────────────────────────────────────────────────
    name_w = _text_w(HEADER["name"], 22)
    _text(page, (PAGE_W - name_w) / 2 - 5, 68, HEADER["name"], size=22, bold=True)

    l2_w = _text_w(HEADER["line2"], 7.5)
    _text(page, (PAGE_W - l2_w) / 2, 80, HEADER["line2"], size=7.5)

    l3_w = _text_w(HEADER["line3"], 7.5)
    _text(page, (PAGE_W - l3_w) / 2, 92, HEADER["line3"], size=7.5)

    # ── 3. ABOUT ME ───────────────────────────────────────────────────────────
    _bar(page, BAR_X0, 96.7, BAR_X1, 113.7, "ABOUT ME")
    y = 121.7
    for line in _wrap(ABOUT, BODY_W, 8):
        _text(page, LM, y, line, size=8)
        y += 11

    # ── 4. WORK EXPERIENCE ────────────────────────────────────────────────────
    BAR_EXP_Y = 169.7
    _bar(page, BAR_X0, BAR_EXP_Y, BAR_X1, BAR_EXP_Y + 17, "WORK EXPERIENCE")

    y = BAR_EXP_Y + 26    # ≈ 195.7
    _text(page, LM, y, EXPERIENCE["company"], size=8, bold=True)
    y += 11
    for line in _wrap(EXPERIENCE["summary"], BODY_W, 7.5):
        _text(page, LM, y, line, size=7.5)
        y += 10
    y += 3
    _text(page, LM, y, EXPERIENCE["bullets_label"], size=8, bold=True)
    y += 11
    for label, detail in EXPERIENCE["bullets"]:
        full = f"{label}: {detail}"
        for i, ln in enumerate(_wrap(full, BODY_W, 8)):
            _text(page, LM + (4 if i > 0 else 0), y, ln, size=8)
            y += 11
        y += 1

    # ── 5. PROJECTS ───────────────────────────────────────────────────────────
    BAR_PROJ_Y = 278.7
    _bar(page, BAR_X0, BAR_PROJ_Y, BAR_X1, BAR_PROJ_Y + 17, "PROJECTS")

    y = BAR_PROJ_Y + 26   # ≈ 304.7
    for proj in PROJECTS:
        _text(page, LM, y, proj["name"], size=8, bold=True)
        y += 11
        for ln in _wrap(proj["desc"], PROJ_W, 8):
            if y >= 449.0:
                break
            _text(page, LM, y, ln, size=8)
            y += 11
        y += 4

    # ── 6. CERTIFICATIONS ─────────────────────────────────────────────────────
    BAR_CERT_Y = 449.7
    _bar(page, BAR_X0, BAR_CERT_Y, BAR_X1, BAR_CERT_Y + 17, "CERTIFICATIONS")

    left_certs  = CERTIFICATIONS[0::2]
    right_certs = CERTIFICATIONS[1::2]
    cert_y = BAR_CERT_Y + 27   # ≈ 476.7
    MID_X = 290.0
    for (ln, lo), (rn, ro) in zip(left_certs, right_certs):
        _text(page, LM,    cert_y, f"- {ln} ({lo})", size=8)
        _text(page, MID_X, cert_y, f"- {rn} ({ro})", size=8)
        cert_y += 13

    # ── 7. SOCIAL INVOLVEMENT ─────────────────────────────────────────────────
    BAR_SOC_Y = 505.7
    _bar(page, BAR_X0, BAR_SOC_Y, BAR_X1, BAR_SOC_Y + 17, "SOCIAL INVOLVEMENT")

    y_s = BAR_SOC_Y + 27
    for item in SOCIAL:
        _text(page, LM, y_s, f"- {item}", size=7.5)
        y_s += 12

    # ── 8. EDUCATION / LANGUAGES / SKILLS ─────────────────────────────────────
    BAR_BOTTOM_Y = 570.7
    COL1_X1 = 208.0
    COL2_X0 = 212.0
    COL2_X1 = 386.0
    COL3_X0 = 390.0

    _bar(page, BAR_X0, BAR_BOTTOM_Y, COL1_X1,  BAR_BOTTOM_Y + 17, "EDUCATION", size=10)
    _bar(page, COL2_X0, BAR_BOTTOM_Y, COL2_X1, BAR_BOTTOM_Y + 17, "LANGUAGES", size=10)
    _bar(page, COL3_X0, BAR_BOTTOM_Y, BAR_X1,  BAR_BOTTOM_Y + 17, "SKILLS",    size=10)

    # Education
    y_e = BAR_BOTTOM_Y + 27
    for line in EDUCATION:
        _text(page, LM, y_e, line, size=7.5)
        y_e += 15

    # Languages
    y_l = BAR_BOTTOM_Y + 27
    for lang, level in LANGUAGES:
        _text(page, COL2_X0 + 4, y_l, f"{lang}: {level}", size=8)
        y_l += 15

    # Skills
    y_k = BAR_BOTTOM_Y + 27
    for skill in SKILLS[:9]:
        _text(page, COL3_X0 + 2, y_k, skill, size=7.5)
        y_k += 15

    # ── 9. REFERENCES ─────────────────────────────────────────────────────────
    BAR_REF_Y = 720.0
    _bar(page, BAR_X0, BAR_REF_Y, BAR_X1, BAR_REF_Y + 17, "REFERENCES")

    _text(page, LM, BAR_REF_Y + 29, REFERENCE["name"],  size=9.5, bold=True)
    _text(page, LM, BAR_REF_Y + 41, REFERENCE["dept"],  size=9)

    # ── Save ──────────────────────────────────────────────────────────────────
    doc.save(OUTPUT, deflate=True, garbage=4)
    doc.close()
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    build()
