"""
LinkedIn Job Tracker — Dashboard
"""

import sqlite3
import json
import re
from pathlib import Path

import streamlit as st
import pandas as pd

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import DB_PATH

# ─── Sayfa Ayarları ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LinkedIn Job Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Genel */
[data-testid="stAppViewContainer"] { background: #0f0f17; }
[data-testid="stSidebar"]          { background: #1a1a2e; border-right: 1px solid #2a2a3e; }
.block-container { padding-top: 1.5rem; }

/* Metrik kartlar */
[data-testid="stMetric"] {
    background: #1a1a2e;
    border: 1px solid #2a2a3e;
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; }

/* Durum badge */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.badge-new      { background:#2a2a3e; color:#9999cc; }
.badge-analyzed { background:#1e2d3e; color:#6ab0de; }
.badge-cv       { background:#1e3a2e; color:#6dd5a0; }
.badge-cl       { background:#2e2a1e; color:#d5b06d; }
.badge-applied  { background:#1e3e1e; color:#5dbb63; border:1px solid #3d8b40; }
.badge-skipped  { background:#3e1e1e; color:#dd6666; }

/* İlan kartı */
.job-card {
    background: #1a1a2e;
    border: 1px solid #2a2a3e;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: border-color .2s;
}
.job-card:hover { border-color: #4a4a6e; }

/* Pipeline bar */
.pipeline-step {
    text-align: center;
    padding: 10px;
    border-radius: 8px;
    font-size: 0.85rem;
}

/* Cevap satırı */
.answer-row {
    background: #1a1a2e;
    border-left: 3px solid #3a3a5e;
    padding: 8px 12px;
    margin-bottom: 6px;
    border-radius: 0 6px 6px 0;
}
.answer-rule { border-left-color: #4a7ab5; }
.answer-user { border-left-color: #5dbb63; }
.answer-ai   { border-left-color: #d5b06d; }
.answer-none { border-left-color: #dd6666; }

/* Expander */
details summary { font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ─── Yardımcılar ──────────────────────────────────────────────────────────────

STATUS_META = {
    "new":                 ("⚪", "Yeni",         "badge-new"),
    "analyzed":            ("🔍", "Analiz",        "badge-analyzed"),
    "cv_ready":            ("📄", "CV Hazır",      "badge-cv"),
    "cover_letter_ready":  ("✉️",  "Ön Yazı Hazır","badge-cl"),
    "applied":             ("✅", "Başvuruldu",    "badge-applied"),
    "skipped":             ("⛔", "Atlandı",       "badge-skipped"),
}

def badge(status: str) -> str:
    icon, label, cls = STATUS_META.get(status, ("❓", status, "badge-new"))
    return f'<span class="badge {cls}">{icon} {label}</span>'

def score_color(score: int) -> str:
    if score >= 70: return "#5dbb63"
    if score >= 50: return "#d5b06d"
    if score > 0:   return "#de6b6b"
    return "#666"

def find_cv(company: str, title: str) -> Path | None:
    raw  = f"{company}_{title}"
    safe = re.sub(r'[^\w\-]', '_', raw.replace('\n', ''))
    safe = re.sub(r'_+', '_', safe).strip('_')[:50]
    p    = Path(f"data/cvs/CV_{safe}.pdf")
    if p.exists():
        return p
    slug    = re.sub(r'[^\w\-]', '_', company)[:20].strip('_')
    matches = list(Path("data/cvs").glob(f"CV_{slug}*.pdf"))
    return matches[0] if matches else None

def find_cl(company: str) -> Path | None:
    slug    = re.sub(r'[^\w\-]', '_', company)[:20].strip('_')
    matches = list(Path("data/cover_letters").glob(f"CL_{slug}*.txt"))
    return matches[0] if matches else None


# ─── Veri Fonksiyonları ───────────────────────────────────────────────────────

@st.cache_data(ttl=20)
def load_data() -> pd.DataFrame:
    if not Path(DB_PATH).exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, title, company, location, work_type,
               match_score, required_skills, status, applied_at, url, scraped_at
        FROM jobs
        ORDER BY match_score DESC NULLS LAST, scraped_at DESC
    """, conn)
    conn.close()

    def parse_skills(s):
        try:    return json.loads(s) if s else []
        except: return []

    df["skills_list"] = df["required_skills"].apply(parse_skills)
    df["skills_str"]  = df["skills_list"].apply(lambda lst: ", ".join(lst) if lst else "—")
    df["match_score"] = df["match_score"].fillna(0).astype(int)
    return df


def update_status(job_id: int, new_status: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
    conn.commit(); conn.close()
    st.cache_data.clear()


@st.cache_data(ttl=10)
def load_questions() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("""
            SELECT id, question_text, question_type, options,
                   ai_answer, user_answer, times_seen, times_answered, last_seen_at
            FROM question_bank
            ORDER BY
                CASE WHEN user_answer IS NULL OR user_answer='' THEN 0 ELSE 1 END,
                times_seen DESC
        """, conn)
    except: df = pd.DataFrame()
    conn.close()
    return df


def save_user_answer(qid: int, answer: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE question_bank SET user_answer=? WHERE id=?", (answer.strip(), qid))
    conn.commit(); conn.close()
    st.cache_data.clear()


FEEDBACK_META = {
    "waiting":   ("⏳", "Bekleniyor",      "#4a4a6e"),
    "interview": ("🎯", "Mülakat",         "#d5b06d"),
    "offer":     ("🎉", "Teklif Geldi",    "#5dbb63"),
    "rejected":  ("❌", "Reddedildi",      "#de6b6b"),
    "ghosted":   ("👻", "Yanıt Yok",       "#666688"),
}

def update_feedback(job_id: int, status: str, note: str = "", interview_date: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE jobs SET feedback_status=?, feedback_note=?, interview_date=?
        WHERE id=?
    """, (status, note, interview_date or None, job_id))
    conn.commit(); conn.close()
    st.cache_data.clear()


@st.cache_data(ttl=15)
def load_tracking() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("""
            SELECT id, title, company, location, url, match_score,
                   applied_at, feedback_status, feedback_note, interview_date
            FROM jobs WHERE status='applied'
            ORDER BY applied_at DESC
        """, conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=15)
def load_applications() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("""
            SELECT id, title, company, location, url,
                   match_score, applied_at, required_skills
            FROM jobs WHERE status='applied'
            ORDER BY applied_at DESC, match_score DESC
        """, conn)
    except: df = pd.DataFrame()
    conn.close()
    return df


@st.cache_data(ttl=15)
def load_app_answers(job_id: int) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("""
            SELECT question_text, answer_given, source
            FROM application_log WHERE job_id=?
            ORDER BY logged_at
        """, conn, params=(job_id,))
    except: df = pd.DataFrame()
    conn.close()
    return df


# ─── Başlık + Sekmeler ────────────────────────────────────────────────────────

st.markdown("## 💼 LinkedIn Job Tracker")
tab_ilanlar, tab_basvurular, tab_takip, tab_sorular = st.tabs(
    ["📌  İlanlar", "✅  Başvurular", "📊  Takip", "❓  Soru Bankası"]
)


# ══════════════════════════════════════════════════════════════════════════════
# SEKME 1 — İLANLAR
# ══════════════════════════════════════════════════════════════════════════════

with tab_ilanlar:
    df = load_data()
    if df.empty:
        st.warning("Henüz veri yok. Önce: `py scraper/linkedin_scraper.py`")
        st.stop()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Filtreler")
        status_opts  = sorted(df["status"].unique().tolist())
        status_filter = st.multiselect("Durum", status_opts, default=status_opts)

        min_score = st.slider("Min. Eşleşme Skoru", 0, 100, 0)

        wt_opts   = df["work_type"].dropna().unique().tolist()
        wt_filter = st.multiselect("Çalışma Şekli", wt_opts, default=wt_opts)

        st.divider()
        st.markdown("### Pipeline Komutları")
        st.code("py analyzer/job_analyzer.py --skip-fetch\npy cv_manager/cv_manager.py\npy cover_letter/cover_letter_generator.py\npy applicator/linkedin_applicator.py --dry-run", language="bash")

    filtered = df[
        df["status"].isin(status_filter) &
        (df["match_score"] >= min_score) &
        df["work_type"].isin(wt_filter)
    ]

    # ── Metrikler ─────────────────────────────────────────────────────────────
    pipeline = [
        ("Toplam",      len(df),                               "#4a4a6e"),
        ("Yeni",        len(df[df["status"]=="new"]),           "#9999cc"),
        ("Analiz",      len(df[df["status"]=="analyzed"]),      "#6ab0de"),
        ("CV Hazır",    len(df[df["status"]=="cv_ready"]),      "#6dd5a0"),
        ("Ön Yazı",     len(df[df["status"]=="cover_letter_ready"]), "#d5b06d"),
        ("Başvuruldu",  len(df[df["status"]=="applied"]),       "#5dbb63"),
    ]
    cols = st.columns(len(pipeline))
    for col, (label, val, color) in zip(cols, pipeline):
        col.metric(label, val)

    # ── Pipeline Hunisi ───────────────────────────────────────────────────────
    st.divider()
    col_chart, col_stat = st.columns([3, 1])

    with col_chart:
        st.markdown("**Skor Dağılımı**")
        scored = df[df["match_score"] > 0]["match_score"]
        if not scored.empty:
            hist = scored.value_counts().sort_index()
            st.bar_chart(hist, height=180, color="#4a7ab5")
        else:
            st.info("Henüz analiz yok.")

    with col_stat:
        st.markdown("**Durum Dağılımı**")
        status_df = df["status"].value_counts().reset_index()
        status_df.columns = ["Durum", "Adet"]
        status_df["Durum"] = status_df["Durum"].map(
            lambda s: STATUS_META.get(s, ("","",s))[1]
        )
        st.dataframe(status_df, hide_index=True, use_container_width=True, height=200)

    st.divider()

    # ── İlan Listesi ──────────────────────────────────────────────────────────
    sort_by = st.selectbox(
        "Sırala:",
        ["Eşleşme Skoru ↓", "Şirket A-Z", "Tarih (yeni)"],
        label_visibility="collapsed",
    )
    if sort_by == "Şirket A-Z":
        filtered = filtered.sort_values("company")
    elif sort_by == "Tarih (yeni)":
        filtered = filtered.sort_values("scraped_at", ascending=False)

    st.markdown(f"**{len(filtered)} ilan** gösteriliyor")

    for _, row in filtered.iterrows():
        score = row["match_score"]
        sc    = score_color(score)

        with st.expander(
            f"{STATUS_META.get(row['status'],('❓','',''))[0]}  "
            f"**{row['title']}**  —  {row['company']}  "
            f"| {row['location'] or '—'}  |  Skor: {score}"
        ):
            c_left, c_right = st.columns([2, 1])

            with c_left:
                st.markdown(
                    badge(row["status"]),
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Çalışma:** {row['work_type'] or '—'} &nbsp;|&nbsp; "
                            f"**Eklendi:** {str(row['scraped_at'])[:10] if row['scraped_at'] else '—'}",
                            unsafe_allow_html=True)
                if row["skills_str"] != "—":
                    skills = row["skills_list"][:8]
                    pills  = " ".join(
                        f'<span style="background:#2a2a4e;padding:2px 8px;'
                        f'border-radius:12px;font-size:0.78rem;margin:2px;display:inline-block">{s}</span>'
                        for s in skills
                    )
                    st.markdown(pills, unsafe_allow_html=True)
                if row["url"]:
                    st.markdown(f"[LinkedIn'de Görüntüle]({row['url']})")

            with c_right:
                st.markdown(
                    f'<div style="text-align:center;font-size:2.5rem;'
                    f'font-weight:700;color:{sc}">{score}</div>'
                    f'<div style="text-align:center;color:#888;font-size:0.8rem">eşleşme</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            st.markdown("**Durumu Güncelle:**")
            btn_cols = st.columns(5)
            statuses = ["new", "analyzed", "cv_ready", "cover_letter_ready", "applied"]
            labels   = ["⚪ Yeni", "🔍 Analiz", "📄 CV", "✉️ Ön Yazı", "✅ Başvuruldu"]
            for i, (s, l) in enumerate(zip(statuses, labels)):
                is_current = row["status"] == s
                if btn_cols[i].button(
                    l, key=f"{row['id']}_{s}",
                    type="primary" if is_current else "secondary",
                ):
                    update_status(int(row["id"]), s)
                    st.rerun()

    st.caption("F5 ile yenile veya sidebar filtrelerini değiştir.")


# ══════════════════════════════════════════════════════════════════════════════
# SEKME 2 — BAŞVURULAR
# ══════════════════════════════════════════════════════════════════════════════

with tab_basvurular:
    apps = load_applications()

    if apps.empty:
        st.info("Henüz başvurulan ilan yok. Applicator çalıştırıldığında burası dolacak.")
    else:
        # Özet banner
        st.markdown(
            f'<div style="background:#1a3e1a;border:1px solid #3d8b40;border-radius:10px;'
            f'padding:16px 24px;margin-bottom:16px">'
            f'<span style="font-size:2rem;font-weight:700;color:#5dbb63">{len(apps)}</span>'
            f'<span style="color:#aaa;margin-left:8px">başvuru tamamlandı</span></div>',
            unsafe_allow_html=True,
        )

        for _, app in apps.iterrows():
            applied_date = str(app["applied_at"])[:16] if app["applied_at"] else "—"
            score  = int(app["match_score"]) if app["match_score"] else 0
            sc     = score_color(score)

            with st.expander(
                f"✅  **{app['title']}**  —  {app['company']}  "
                f"|  Skor: {score}  |  {applied_date}"
            ):
                col_info, col_ans = st.columns([1, 1])

                # ── Sol: Detaylar ──────────────────────────────────────────
                with col_info:
                    st.markdown(f"**Şirket:** {app['company']}")
                    st.markdown(f"**Konum:** {app['location'] or '—'}")
                    st.markdown(f"**Başvuru:** {applied_date}")
                    st.markdown(
                        f'<span style="font-size:1.6rem;font-weight:700;color:{sc}">{score}</span>'
                        f'<span style="color:#888"> / 100</span>',
                        unsafe_allow_html=True,
                    )
                    if app["url"]:
                        st.markdown(f"[LinkedIn İlanı]({app['url']})")

                    # Beceriler
                    try:
                        skills = json.loads(app["required_skills"] or "[]")
                        if skills:
                            pills = " ".join(
                                f'<span style="background:#1e3a2e;padding:2px 8px;'
                                f'border-radius:12px;font-size:0.75rem;margin:2px;'
                                f'display:inline-block;color:#6dd5a0">{s}</span>'
                                for s in skills[:8]
                            )
                            st.markdown("**Aranan Beceriler:**")
                            st.markdown(pills, unsafe_allow_html=True)
                    except Exception:
                        pass

                    st.divider()

                    # CV
                    cv_path = find_cv(str(app["company"]), str(app["title"]))
                    if cv_path:
                        st.markdown(f"📄 **CV:** `{cv_path.name}`")
                        with open(cv_path, "rb") as f:
                            st.download_button(
                                "CV'yi İndir (PDF)",
                                data=f,
                                file_name=cv_path.name,
                                mime="application/pdf",
                                key=f"dl_cv_{app['id']}",
                                use_container_width=True,
                            )
                    else:
                        st.markdown("📄 **CV:** bulunamadı")

                    # Cover letter
                    cl_path = find_cl(str(app["company"]))
                    if cl_path:
                        st.markdown(f"✉️ **Ön Yazı:** `{cl_path.name}`")
                        with st.expander("Ön yazıyı oku"):
                            st.markdown(
                                cl_path.read_text(encoding="utf-8", errors="ignore")
                            )

                # ── Sağ: Başvuruda verilen cevaplar ───────────────────────
                with col_ans:
                    st.markdown("**Başvuruda Verilen Cevaplar**")
                    ans_df = load_app_answers(int(app["id"]))

                    if ans_df.empty:
                        st.info("Bu başvuru için cevap kaydı yok.")
                    else:
                        source_cls = {
                            "rule": ("answer-rule", "🔵 Kural"),
                            "user": ("answer-user", "🟢 Kullanıcı"),
                            "ai":   ("answer-ai",   "🟡 AI"),
                            "none": ("answer-none", "🔴 Cevapsız"),
                        }
                        for _, ans in ans_df.iterrows():
                            cls, src_label = source_cls.get(
                                str(ans["source"]), ("answer-row", "⚪")
                            )
                            q = str(ans["question_text"])
                            a = str(ans["answer_given"]) if ans["answer_given"] else "—"
                            st.markdown(
                                f'<div class="answer-row {cls}">'
                                f'<div style="font-size:0.78rem;color:#aaa">{src_label}</div>'
                                f'<div style="font-weight:600;margin:2px 0">{q[:70]}</div>'
                                f'<div style="color:#5dbb63;font-family:monospace">{a}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        st.caption("🔵 Kural  🟢 Senin cevabın  🟡 AI  🔴 Cevaplanamadı")


# ══════════════════════════════════════════════════════════════════════════════
# SEKME 3 — TAKİP
# ══════════════════════════════════════════════════════════════════════════════

with tab_takip:
    track_df = load_tracking()

    if track_df.empty:
        st.info("Henüz başvurulan ilan yok.")
    else:
        # Özet metrikler
        fb = track_df["feedback_status"].value_counts().to_dict()
        cols = st.columns(len(FEEDBACK_META))
        for col, (key, (icon, label, color)) in zip(cols, FEEDBACK_META.items()):
            col.markdown(
                f'<div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:10px;'
                f'padding:12px;text-align:center">'
                f'<div style="font-size:1.6rem">{icon}</div>'
                f'<div style="font-size:1.4rem;font-weight:700;color:{color}">{fb.get(key,0)}</div>'
                f'<div style="color:#888;font-size:0.8rem">{label}</div></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # Filtre
        fb_filtre = st.selectbox(
            "Filtrele:",
            ["Tümü"] + [v[1] for v in FEEDBACK_META.values()],
            label_visibility="collapsed",
        )

        label_to_key = {v[1]: k for k, v in FEEDBACK_META.items()}
        if fb_filtre != "Tümü":
            fk = label_to_key[fb_filtre]
            track_df = track_df[track_df["feedback_status"] == fk]

        st.markdown(f"**{len(track_df)} başvuru**")

        for _, row in track_df.iterrows():
            fstatus  = str(row.get("feedback_status") or "waiting")
            icon, label, color = FEEDBACK_META.get(fstatus, ("⏳","Bekleniyor","#666"))
            score    = int(row["match_score"]) if row["match_score"] else 0
            date_str = str(row["applied_at"])[:10] if row["applied_at"] else "—"

            with st.expander(
                f"{icon}  **{row['title']}**  —  {row['company']}  "
                f"|  {label}  |  Başvuru: {date_str}"
            ):
                left, right = st.columns([1, 1])

                with left:
                    st.markdown(f"**Şirket:** {row['company']}")
                    st.markdown(f"**Konum:** {row['location'] or '—'}")
                    st.markdown(f"**Eşleşme:** {score} / 100")
                    st.markdown(f"**Başvuru Tarihi:** {date_str}")
                    if row["url"]:
                        st.markdown(f"[LinkedIn İlanı]({row['url']})")
                    if row["interview_date"]:
                        st.markdown(
                            f'<div style="background:#2e2a1e;border-left:3px solid #d5b06d;'
                            f'padding:8px 12px;border-radius:0 6px 6px 0">'
                            f'🎯 Mülakat: <b>{row["interview_date"]}</b></div>',
                            unsafe_allow_html=True,
                        )

                with right:
                    st.markdown("**Durumu Güncelle:**")
                    new_status = st.selectbox(
                        "Durum:",
                        list(FEEDBACK_META.keys()),
                        index=list(FEEDBACK_META.keys()).index(fstatus),
                        format_func=lambda k: f"{FEEDBACK_META[k][0]} {FEEDBACK_META[k][1]}",
                        key=f"fb_{row['id']}",
                        label_visibility="collapsed",
                    )
                    note = st.text_area(
                        "Not:",
                        value=str(row["feedback_note"] or ""),
                        key=f"note_{row['id']}",
                        placeholder="Geri bildirim, recruiter adı, mülakat detayı...",
                        height=80,
                    )
                    interview_date = ""
                    if new_status == "interview":
                        interview_date = st.text_input(
                            "Mülakat Tarihi:",
                            value=str(row["interview_date"] or ""),
                            key=f"idate_{row['id']}",
                            placeholder="ör. 2026-05-10 14:00",
                        )
                    if st.button("Kaydet", key=f"save_fb_{row['id']}", use_container_width=True):
                        update_feedback(int(row["id"]), new_status, note, interview_date)
                        st.success("Güncellendi.")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SEKME 4 — SORU BANKASI
# ══════════════════════════════════════════════════════════════════════════════

with tab_sorular:
    q_df = load_questions()

    if q_df.empty:
        st.info("Henüz soru yok. Applicator çalışınca sorular buraya birikir.")
    else:
        total    = len(q_df)
        answered = len(q_df[q_df["user_answer"].notna() & (q_df["user_answer"] != "")])

        # Üst bilgi
        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Soru", total)
        c2.metric("Cevapladın", answered)
        c3.metric("Bekleyen", total - answered)

        # İlerleme çubuğu
        if total > 0:
            pct = answered / total
            st.progress(pct, text=f"Tamamlanma: %{pct*100:.0f}")

        st.divider()
        st.caption(
            "Kendi cevabını gir — sistem bir sonraki başvuruda bunu kullanır. "
            "Cevap vermezsen AI dener, o da yapamıyorsa ilan atlanır."
        )

        filtre = st.radio(
            "Filtre:",
            ["Tümü", "Bekleyen", "Cevaplandı"],
            horizontal=True,
        )
        if filtre == "Bekleyen":
            q_df = q_df[q_df["user_answer"].isna() | (q_df["user_answer"] == "")]
        elif filtre == "Cevaplandı":
            q_df = q_df[q_df["user_answer"].notna() & (q_df["user_answer"] != "")]

        st.markdown(f"**{len(q_df)} soru**")

        for _, q in q_df.iterrows():
            has_user = bool(q["user_answer"] and str(q["user_answer"]).strip())
            preview  = str(q["question_text"])
            icon     = "✅" if has_user else "❓"

            with st.expander(
                f"{icon}  {preview[:80]}{'...' if len(preview)>80 else ''}  "
                f"— {q['times_seen']}x görüldü"
            ):
                left, right = st.columns([1, 1])

                with left:
                    st.markdown(f"**Tip:** `{q['question_type'] or '—'}`")

                    if q["options"]:
                        try:
                            opts = json.loads(q["options"])
                            st.markdown("**Seçenekler:**")
                            for o in opts:
                                st.markdown(
                                    f'<span style="background:#2a2a4e;padding:2px 10px;'
                                    f'border-radius:12px;font-size:0.8rem;margin:2px;'
                                    f'display:inline-block">{o}</span>',
                                    unsafe_allow_html=True,
                                )
                        except Exception:
                            pass

                    if q["ai_answer"]:
                        st.markdown(
                            f'<div style="background:#2e2a1e;border-left:3px solid #d5b06d;'
                            f'padding:6px 10px;border-radius:0 6px 6px 0;margin-top:8px">'
                            f'🟡 AI önerisi: <code>{q["ai_answer"]}</code></div>',
                            unsafe_allow_html=True,
                        )

                with right:
                    current    = str(q["user_answer"]) if has_user else ""
                    new_answer = st.text_input(
                        "Senin cevabın:",
                        value=current,
                        key=f"q_{q['id']}",
                        placeholder="Cevabı buraya yaz...",
                    )
                    if st.button("💾 Kaydet", key=f"save_{q['id']}", use_container_width=True):
                        save_user_answer(int(q["id"]), new_answer)
                        st.success("Kaydedildi.")
                        st.rerun()
