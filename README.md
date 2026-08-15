# 🧶 Loominar

[![PyPI](https://img.shields.io/pypi/v/loominar.svg)](https://pypi.org/project/loominar/)
[![Python](https://img.shields.io/pypi/pyversions/loominar.svg)](https://pypi.org/project/loominar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE.txt)

**Loominar** transforms raw **SonarQube static analysis data** into elegant, audit-ready reports.  
Generate clean **Word**, **Excel**, or **CSV** reports — ideal for audits, management summaries, and CI/CD automation pipelines.

Unlike a plain API script, Loominar retrieves **complete** issue sets: it works around
SonarQube's hard 10,000-result limit, so a 200,000-issue project exports as reliably as
a 200-issue one.

---

### ✨ Features
- 🧭 **Dual Mode:** Run interactively or via CLI (supports both short `-p` and long `--project` flags)
- 📊 **Multi-format Export:** Generate **Word**, **Excel**, or **CSV** reports from SonarQube
- ⚙️ **SonarQube API Integration:** Pulls live metrics, quality gates, and issue data
- 🚀 **No 10,000-issue ceiling:** Retrieves complete issue sets of any size (see below)
- 💾 **Flat memory usage:** Large projects stream to disk instead of loading into RAM
- 🎨 **Colorized CLI Output:** Auto-disabled when not a terminal, so CI logs stay clean
- 🔁 **Pipeline-ready:** Logs on stderr, report path on stdout, distinct exit codes, env-var credentials
- 📁 **Smart Output Path:** Automatically saves reports under your `Documents/Loominar` folder
- 🧩 **Verbosity Control:** Three levels (`-v 1–3`) from quiet to full HTTP debug
- 🧠 **Modular Design:** Independent modules for CLI, API, input, and reporting
- 🧰 **Extensible Foundation:** Prepared for future PDF/HTML exports, configuration files, and DevOps notifications

---

### 🚀 Getting past SonarQube's 10,000-result limit

`/api/issues/search` refuses any request where `page * pageSize > 10000`, so a plain
pagination loop dies partway through a large project. Loominar works around it in two
layers:

1. **Filter splitting.** Projects over the threshold are split by **severity**, then
   **type**, then **creation-date** windows, until each bucket fits inside the window.
   Severity and type partition the result set exactly — no gaps, no double counting.
2. **Creation-date cursor.** If a bucket is *still* too large, issues are sorted by
   creation date and, once the 10k window is exhausted, `createdAfter` is re-anchored to
   the last issue seen and paging restarts. Every issue is deduplicated by key, so the
   inclusive boundary between windows never produces duplicates.

Buckets are streamed to per-bucket CSVs under `<output>/.loominar_temp/` and merged into
the final workbook, so peak memory stays flat no matter how large the project is. The
temp directory is removed once the report is written (`--keep-temp` preserves it).

| Issue count | Behaviour |
| ----------- | --------- |
| ≤ `--inline-limit` (10,000 by default) | Fetched in memory; any format |
| Above the limit, Excel or CSV | Split → streamed to disk → merged |
| Above the limit, Word | Falls back to Excel (Word cannot render that volume) |

---

### 🧰 Stack
- **Language:** Python 3.9 or higher  
- **Libraries:**  
  - `requests` – SonarQube REST API integration  
  - `xlsxwriter` – streaming Excel export (constant-memory mode)  
  - `python-docx` – Word export  
  - `matplotlib` – severity charts for Word reports  
  - `colorama` – colorized CLI output  
- **Architecture Overview**

```

loominar/
├── api/
│   ├── base_client.py     # Pooled HTTP session, retries, backoff
│   ├── issues_client.py   # Orchestrates fetch strategy
│   ├── metrics_client.py  # Measures + quality gate
│   └── issues/
│       ├── pagination.py  # Paging + creation-date cursor (10k workaround)
│       ├── splitter.py    # severity → type → date bucketing
│       ├── stream.py      # Per-bucket CSV streaming + canonical row schema
│       ├── components.py  # Component tree listing
│       └── date_utils.py  # Calendar-month windows, midpoints
├── report/            # Report generators (Word, Excel, CSV)
├── cli_handler.py     # CLI argument parsing
├── input_handler.py   # Interactive input prompts
├── main.py            # Unified entrypoint (CLI + interactive)
└── console.py         # Colorized console utilities

````

---

### 🚀 Quick Start

#### Installation
```bash
pip install loominar
````

#### Interactive Mode

Run Loominar with no arguments and follow the prompts:

```bash
loominar
```

#### CLI Mode

Run headless with full control (perfect for pipelines):

```bash
loominar -u http://localhost:9000 -t squ_abc123 -p A-Star-2 -f excel -v 2 --no-confirm
```

In a pipeline, prefer environment variables — a token passed as `--token` is visible in
process listings and CI logs:

```bash
export SONAR_URL=http://localhost:9000
export SONAR_TOKEN=squ_abc123
export SONAR_PROJECT=A-Star-2
loominar -f excel --no-confirm
```

With `--no-confirm` (or no TTY) Loominar never prompts: a missing required value exits
immediately with exit code 3 rather than blocking the job.

**Exit codes:** `0` success · `1` error · `2` cancelled · `3` missing/invalid input

#### Example Output

```
Loominar v1.0.0 - SonarQube Report Exporter
[INFO ] Connecting to http://localhost:9000
[INFO ] Project 'A-Star-2': 42,000 open issues reported.
[WARN ] 42,000 issues exceed the 10,000-issue limit for WORD output.
        Falling back to Excel, which can render this volume reliably.
[INFO ] 42,000 issues exceed the 10,000-issue inline limit. Splitting by severity then type then date and streaming to disk.
[INFO ] Streaming BLOCKER in A-Star-2: 8,400/8,400 (100%) at 612/s, 13.7s total
[INFO ] Streaming CRITICAL in A-Star-2: 8,400/8,400 (100%) at 655/s, 12.8s total
[OK   ] Retrieved 42,000 unique issues across 5 buckets.
[INFO ] Merging 5 streamed bucket(s) into A-Star-2_ERROR_2026-08-15_2216.xlsx
[OK   ] Excel report written: ...\A-Star-2_ERROR_2026-08-15_2216.xlsx (42,000 issues)
```

Everything above is on **stderr**. The report path is the only thing on **stdout**.

---

### 🧩 Logging

Log records are written to **stderr** as `[LEVEL] message`; the finished report
path is written to **stdout**. Continuation lines are indented under the message,
so multi-line warnings stay readable in CI output.

| Level | Flag | Shows |
| ----- | ---- | ----- |
| **1 – Quiet** | `-v 1` / `-q` | Results, warnings, errors |
| **2 – Normal** (default) | `-v 2` | Adds progress: counts, splitting, streaming throughput |
| **3 – Debug** | `-v 3` / `--debug` | Adds HTTP requests, response sizes and timings, paging and cursor decisions |

| Flag | Default | Purpose |
| ---- | ------- | ------- |
| `--color` / `--no-color` | auto | Color is on only when stderr is a terminal; `NO_COLOR` and `TERM=dumb` are honoured |
| `--timestamps` / `--no-timestamps` | auto | Timestamps appear automatically when stderr is redirected to a file or CI log |

API tokens are never logged, and any credential-shaped request parameter is
redacted before it reaches a log line.

---

### ⚙️ Options for large projects

| Flag | Default | Purpose |
| ---- | ------- | ------- |
| `--inline-limit N` | `10000` | Above `N` issues, stream to disk and fall back to Excel |
| `--split-by DIMS` | `severity,type,date` | Split dimensions; `component` is also available |
| `--keep-temp` | off | Keep the intermediate `.loominar_temp` CSVs |
| `--no-confirm` | off | Never prompt — required for pipelines |

---

### 🧠 Roadmap

* 📄 **PDF and HTML Exports** using WeasyPrint + Jinja2 templates
* ⚙️ **Config File Support** (`.loominarrc` or `.env`)
* 🔔 **Slack / Teams Notifications** for report summaries
* 📊 **Trend & Delta Analysis** between runs
* 🧮 **Batch Mode** for multi-project reporting
* 🌐 **CI/CD Integration** (GitHub Actions & Azure Pipelines)

---

### 📜 Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the full history.

#### Upgrading from 0.2.x

1.0.0 is the first release that retrieves complete issue sets. It carries a few
breaking changes worth checking before you upgrade a pipeline:

| Change | What to do |
| ------ | ---------- |
| Logs moved to **stderr**; only the report path is on **stdout** | Anything parsing stdout for progress should read stderr. `REPORT=$(loominar ...)` now yields just the path. |
| Exit codes split into `0/1/2/3` | Cancellation is now `2` and bad input is `3`; both used to be `1`. |
| CSV columns expanded to the 12-column canonical schema | Update any downstream parser that assumed `Severity, Type, Message, File, Line`. |
| `pandas` and `openpyxl` are no longer required | Nothing to do; they can be dropped from pinned environments. |
| Headless runs never prompt | Supply `-u/-t/-p` (or `SONAR_URL`/`SONAR_TOKEN`/`SONAR_PROJECT`), or the run exits `3` instead of hanging. |

If you install from a wheel, note that 0.2.x wheels were missing the
`loominar.api.issues` subpackage entirely — a fresh `pip install` of those
versions fails at import. Upgrade rather than pinning them.

---

### 🧾 License

Licensed under the **MIT License**.
See the [LICENSE](./LICENSE.txt) file for full details.

---

### 💡 Maintainer

**Mohamed Ali**
Software Consultant | DevSecOps & IAM Engineer
[GitHub](https://github.com/mhmd4li) | [LinkedIn](https://linkedin.com/in/mohamed-ali-bmd)

---
