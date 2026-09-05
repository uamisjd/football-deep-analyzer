# data/

- `raw/`     risposte grezze delle fonti (JSON/CSV) — **non versionate**, rigenerabili.
- `cache/`   cache HTTP — non versionata.
- `processed/` tabelle Parquet e database DuckDB prodotti dalla pipeline — versionati
  (è il "git scraping": ogni run aggiorna i file e li committa).
