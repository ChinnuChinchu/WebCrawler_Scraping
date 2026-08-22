"""Streamlit UI for the Wikipedia crawler."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from wikipedia_crawler import crawl

OUTPUT = Path("outputs")
st.set_page_config(page_title="Wikipedia Crawler", page_icon="🕷️", layout="wide")
st.title("Wikipedia crawler")
st.caption("Collect a small, rate-limited set of public Wikipedia articles using its official API.")

with st.sidebar:
    st.header("Crawl settings")
    url = st.text_input("Starting article", "https://en.wikipedia.org/wiki/Kerala")
    limit = st.slider("Maximum pages", 1, 25, 5)
    delay = st.slider("Wait between requests (seconds)", 0.5, 5.0, 1.0, 0.5)
    run = st.button("Start crawl", type="primary", use_container_width=True)

st.info("This version uses Wikipedia's official API. Direct HTML crawling can be rejected by its robots rules.")
if run:
    try:
        with st.spinner("Collecting articles…"):
            count = crawl(url, limit, delay, OUTPUT)
        st.session_state.records = json.loads((OUTPUT / "wikipedia_pages.json").read_text(encoding="utf-8"))
        st.success(f"Collected {count} page(s).")
    except Exception as error:
        st.error(f"Unable to crawl: {error}")

records = st.session_state.get("records", [])
if records:
    table = pd.DataFrame(records)
    table["headings"] = table["headings"].apply(" | ".join)
    a, b = st.columns(2)
    a.metric("Pages collected", len(table))
    b.metric("Characters extracted", int(table.text.str.len().sum()))
    st.dataframe(table[["title", "url", "headings"]], use_container_width=True, hide_index=True)
    title = st.selectbox("Preview an article", table.title)
    selected = table.loc[table.title == title].iloc[0]
    st.markdown(f"### [{selected.title}]({selected.url})")
    st.write(selected.text)
    left, right = st.columns(2)
    left.download_button("Download CSV", table.to_csv(index=False).encode(), "wikipedia_pages.csv", "text/csv", use_container_width=True)
    right.download_button("Download JSON", json.dumps(records, ensure_ascii=False, indent=2).encode(), "wikipedia_pages.json", "application/json", use_container_width=True)
else:
    st.write("Choose a Wikipedia article and click **Start crawl**.")
