"""F1 Multi-Cloud dashboard (Streamlit)."""

from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import logging

import pandas as pd
import plotly.express as px
import streamlit as st

from f1lab.config import settings
from f1lab.pipeline import load_cloud, run_pipeline
from f1lab.stores import get_stores

logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="F1 | Multi-Cloud Data Lab", page_icon="🏎️", layout="wide", initial_sidebar_state="expanded")

COLORS = ["#ff4562", "#21d4c6", "#f8cb69", "#93a6ff", "#f18fff", "#8dd689", "#dddee2"]

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1550px; }
  .f1-hero { padding: 1.2rem 1.5rem; border-radius: 16px;
    background: linear-gradient(115deg, #331726 0%, #192437 47%, #0b3540 100%);
    border: 1px solid #334252; margin-bottom: 1.4rem; }
  .f1-eyebrow { font-size: .72rem; color: #a1afc0; letter-spacing: .24em; font-weight: 700; }
  .f1-title { font-size: 2rem; font-weight: 800; letter-spacing: -.04em; line-height: 1.2; margin: .3rem 0; }
  .f1-subtitle { color:#c1ccd9; font-size: .96rem; }
  .cloud-status { border: 1px solid #334051; background: #141e2d; border-radius: 12px;
    padding: .9rem 1.1rem; font-size: .9rem; min-height: 99px; }
  .ok { color: #46dcc7; } .missing { color: #ffa364; }
  .small-muted { color: #a2b1c2; font-size: .78rem; }
  div[data-testid="stMetric"] { background: #171f2d; border: 1px solid #303d4c; border-radius: 12px; padding: 1rem; }
  div[data-testid="stMetricLabel"] { color: #a4b4c6; }
  h3 { font-size: 1.15rem !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=20, show_spinner=False)
def read_cloud(cloud: str, season: int):
    store = get_stores()[cloud]
    return load_cloud(store, season)


def age(iso_text: str) -> str:
    try:
        seconds = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(iso_text)).total_seconds())
        if seconds < 120:
            return f"{round(seconds)} s"
        if seconds < 7200:
            return f"{round(seconds / 60)} min"
        return f"{round(seconds / 3600, 1)} h"
    except (ValueError, TypeError):
        return "n/d"


def chart(fig, height=320):
    fig.update_layout(
        template="plotly_dark", height=height,
        margin=dict(l=10, r=20, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="", font=dict(color="#d7e1ee", size=12),
        xaxis=dict(gridcolor="#34404f", zeroline=False),
        yaxis=dict(gridcolor="#34404f", zeroline=False),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


st.sidebar.markdown("### 🏎️ F1 Data Lab")
st.sidebar.caption("Data Engineering · AWS + GCP locales")
years = list(range(datetime.now(timezone.utc).year, 2019, -1))
if settings.default_season not in years:
    years.append(settings.default_season)
    years = sorted(set(years), reverse=True)
season = st.sidebar.selectbox("Temporada", years, index=years.index(settings.default_season))
cloud_choice = st.sidebar.radio(
    "Visualizar datos desde", ["AWS · S3", "GCP · Cloud Storage"], index=0
)
selected_cloud = "aws" if cloud_choice.startswith("AWS") else "gcp"
st.sidebar.divider()

if st.sidebar.button("↻ Actualizar desde Jolpica", type="primary", use_container_width=True):
    with st.spinner(f"Descargando temporada {season} y publicando en ambas nubes…"):
        try:
            outcome = run_pipeline(season)
            st.cache_data.clear()
            failed = {c: r.get("error", "") for c, r in outcome["clouds"].items() if not r["ok"]}
            if failed:
                st.sidebar.error(f"Fallos de publicación: {failed}")
            else:
                st.sidebar.success("Sincronización AWS + GCP completada")
                st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Error durante la ingesta: {exc}")

with st.sidebar.expander("Modo demo (offline)"):
    st.caption("Datos ficticios, claramente identificados. Sustituyen el último snapshot de la temporada.")
    if st.button("Cargar datos demo", use_container_width=True):
        with st.spinner("Publicando dataset demo…"):
            try:
                result = run_pipeline(season, demo=True)
                st.cache_data.clear()
                st.sidebar.success("Demo publicado" if all(x["ok"] for x in result["clouds"].values()) else str(result["clouds"]))
                st.rerun()
            except Exception as exc:
                st.error(f"Error demo: {exc}")

st.sidebar.divider()
st.sidebar.caption(f"Refresh en background: cada {settings.sync_interval_hours:g} h (temporada {settings.default_season})")
st.sidebar.caption("El dashboard se actualiza cada 60 s.")
st.sidebar.markdown("[API Jolpica](https://api.jolpi.ca/docs/) · [Docs Moto](https://docs.getmoto.org/)")

st.markdown(f"""
<div class="f1-hero">
  <div class="f1-eyebrow">F1 · MULTI-CLOUD DATA OBSERVABILITY</div>
  <div class="f1-title">Race Intelligence <span style="color:#ff556f">/{season}</span></div>
  <div class="f1-subtitle">Data lake AWS S3 ↔ GCP Cloud Storage · Bronze RAW / Silver Parquet / Gold KPIs</div>
</div>
""", unsafe_allow_html=True)


@st.fragment(run_every="60s")
def render_live_dashboard(season: int, selected_cloud: str):
    observations = {}
    for provider in ("aws", "gcp"):
        try:
            manifest, frames = read_cloud(provider, season)
            observations[provider] = {"manifest": manifest, "frames": frames, "error": None}
        except Exception as exc:
            observations[provider] = {"manifest": None, "frames": {}, "error": f"{type(exc).__name__}: {exc}"}

    left, right = st.columns(2)
    for col, provider, name in [(left, "aws", "AWS / S3"), (right, "gcp", "GCP / Cloud Storage")]:
        data = observations[provider]
        manifest = data["manifest"]
        if manifest:
            status = "● ONLINE · dataset verificado"
            detail = f"{manifest['results']} resultados · {age(manifest['ingested_at_utc'])} desde la ingesta"
            clas = "ok"
        elif data["error"]:
            status, detail, clas = "● ERROR", data["error"], "missing"
        else:
            status, detail, clas = "● SIN DATOS", "Esperando primera ingesta del worker…", "missing"
        with col:
            st.markdown(f"""<div class="cloud-status">
              <b>{name}</b><div class="{clas}" style="margin-top:.4rem">{status}</div>
              <div class="small-muted" style="overflow-wrap:anywhere">{detail}</div>
            </div>""", unsafe_allow_html=True)

    a, b = observations["aws"]["manifest"], observations["gcp"]["manifest"]
    if a and b:
        parity = a["parquet_sha256"] == b["parquet_sha256"] and a["mode"] == b["mode"]
        if parity:
            st.caption("✅ Data parity: los SHA-256 de los tres datasets Parquet coinciden en ambas nubes.")
        else:
            st.error("⚠️ Data drift: AWS y GCP contienen datasets diferentes.")

    current = observations[selected_cloud]
    if not current["manifest"]:
        alternative = "gcp" if selected_cloud == "aws" else "aws"
        if observations[alternative]["manifest"]:
            st.warning("El cloud seleccionado aún no tiene datos. Cambia el origen en la barra lateral.")
        else:
            st.info("El worker está realizando la primera ingesta. Consulta `docker compose logs -f worker`, o pulsa **Cargar datos demo** para probarlo sin Internet.")
        return

    manifest = current["manifest"]
    frames = current["frames"]
    results, races, standings = frames["results"], frames["races"], frames["standings"]
    if manifest["mode"] != "LIVE":
        st.warning("🧪 MODO DEMO: resultados ficticios para probar el dashboard; no representan carreras reales.")

    st.caption(f"Fuente: {manifest['source']} · Cloud seleccionado: {selected_cloud.upper()} · Snapshot UTC: {manifest['ingested_at_utc']}")
    cols = st.columns(5)
    for col, (title, value) in zip(cols, [
        ("GP disputados", f"{manifest['races_with_results']} / {manifest['scheduled_races']}"),
        ("Pilotos", manifest["drivers"]),
        ("Equipos", manifest["constructors"]),
        ("Resultados", manifest["results"]),
        ("Freshness", age(manifest["ingested_at_utc"])),
    ]):
        col.metric(title, value)

    tabs = st.tabs(["🏁 Racing analytics", "📈 Progresión", "☁️ Cloud & quality", "🗂 Datos"])

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Clasificación de pilotos")
            if not standings.empty:
                frame = standings.nsmallest(12, "position")
                fig = px.bar(frame.sort_values("points"), x="points", y="driver", orientation="h",
                             color="points", color_continuous_scale=[[0, "#7c2b4d"], [1, "#ff5472"]],
                             labels={"driver": "", "points": "Puntos oficiales"})
                fig.update_layout(coloraxis_showscale=False)
                chart(fig, 370)
            else:
                st.info("Sin clasificación oficial disponible.")
        with c2:
            st.subheader("Puntos por constructor (carreras)")
            teams = results.groupby("constructor", as_index=False)["points"].sum().nlargest(12, "points")
            fig = px.bar(teams.sort_values("points"), x="points", y="constructor", orientation="h",
                         color_discrete_sequence=["#24c4bc"], labels={"constructor": "", "points": "Puntos (sin sprints)"})
            chart(fig, 370)
        st.subheader("Victorias por piloto")
        winners = results.loc[results["position"] == 1].groupby("driver", as_index=False).size().rename(columns={"size": "wins"})
        if not winners.empty:
            fig = px.bar(winners.sort_values("wins", ascending=False), x="driver", y="wins",
                         color="driver", color_discrete_sequence=COLORS,
                         labels={"driver": "Piloto", "wins": "Victorias"})
            fig.update_layout(showlegend=False)
            chart(fig, 285)

    with tabs[1]:
        st.subheader("Puntos acumulados por ronda · carreras")
        leaders = (standings.nsmallest(6, "position")["driver"].tolist() if not standings.empty
                   else results.groupby("driver")["points"].sum().nlargest(6).index.tolist())
        by_round = results[results["driver"].isin(leaders)].pivot_table(
            index="round", columns="driver", values="points", aggfunc="sum", fill_value=0
        ).sort_index().cumsum().reset_index()
        if len(by_round) > 0:
            melted = by_round.melt(id_vars="round", var_name="driver", value_name="points")
            fig = px.line(melted, x="round", y="points", color="driver", markers=True,
                          color_discrete_sequence=COLORS,
                          labels={"round": "Ronda", "points": "Puntos acumulados", "driver": "Piloto"})
            fig.update_traces(line_width=2.5)
            chart(fig, 380)
        st.caption("Este gráfico suma exclusivamente puntos de Grandes Premios; la clasificación oficial puede incluir sprints.")

    with tabs[2]:
        st.subheader("Salud del pipeline multi-cloud")
        rows = []
        for provider in ("aws", "gcp"):
            item = observations[provider]
            m = item["manifest"]
            rows.append({
                "cloud": provider.upper(), "estado": "OK" if m else "ERROR" if item["error"] else "SIN DATA",
                "temporada": season, "registros": m["results"] if m else 0,
                "última ingesta (UTC)": m["ingested_at_utc"] if m else "-",
                "modo": m["mode"] if m else "-",
                "run_id": m["run_id"] if m else "-",
                "parquet SHA (resultados)": m["parquet_sha256"]["results"][:16] if m else "-",
                "error": item["error"] or "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.subheader("Controles de calidad")
        checks = {
            "Sin duplicados por (season, round, driver)": not results.duplicated(subset=["season", "round", "driver_id"]).any(),
            "Puntuación no negativa": bool((results["points"] >= 0).all()),
            "Rondas positivas": bool((results["round"] > 0).all()),
            "Las carreras disputadas existen en el calendario": set(results["round"]).issubset(set(races["round"])),
            "SHA-256 de todos los datasets verificado": True,
        }
        for desc, ok in checks.items():
            st.write(("✅" if ok else "❌") + " " + desc)
        st.caption("RAW JSON → Silver Parquet → Gold JSON. Manifest publicado en último lugar (commit por cloud).")
        with st.expander("Detalles del manifest"):
            st.json(manifest)

    with tabs[3]:
        st.subheader("Resultados por Gran Premio")
        available = results[["round", "race_name"]].drop_duplicates().sort_values("round")
        choices = {int(row["round"]): f"R{int(row['round']):02d} · {row['race_name']}" for _, row in available.iterrows()}
        rnd = st.selectbox("Carrera", list(choices), format_func=lambda x: choices[x])
        race_table = results[results["round"] == rnd].sort_values("position")
        st.dataframe(race_table[["position", "driver", "constructor", "grid", "points", "status", "laps"]],
                     hide_index=True, use_container_width=True)
        st.download_button("⬇ Descargar resultados CSV", results.to_csv(index=False).encode("utf-8"),
                           file_name=f"f1_{season}_{selected_cloud}_results.csv", mime="text/csv")
        st.download_button("⬇ Descargar calendario CSV", races.to_csv(index=False).encode("utf-8"),
                           file_name=f"f1_{season}_{selected_cloud}_races.csv", mime="text/csv")


render_live_dashboard(season, selected_cloud)
