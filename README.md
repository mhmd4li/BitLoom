# 🧶 Loominar

**Loominar** transforms raw **SonarQube static analysis data** into elegant, audit-ready reports.  
Generate clean **Word**, **Excel**, or **CSV** reports — ideal for audits, management summaries, and CI/CD automation pipelines.

---

### ✨ Features
- 🧭 **Dual Mode:** Run interactively or via CLI (supports both short `-p` and long `--project` flags)
- 📊 **Multi-format Export:** Generate **Word**, **Excel**, or **CSV** reports from SonarQube
- ⚙️ **SonarQube API Integration:** Pulls live metrics, quality gates, and issue data
- 🎨 **Colorized CLI Output:** Clear progress, success, and error messages
- 📁 **Smart Output Path:** Automatically saves reports under your `Documents/Loominar` folder
- 🧩 **Verbosity Control:** Three levels (`-v 1–3`) for silent, normal, or detailed logging
- 🧠 **Modular Design:** Independent modules for CLI, API, input, and reporting
- 🧰 **Extensible Foundation:** Prepared for future PDF/HTML exports, configuration files, and DevOps notifications

---

### 🧰 Stack
- **Language:** Python 3.9 or higher  
- **Libraries:**  
  - `requests` – SonarQube REST API integration  
  - `pandas` – metrics aggregation and data shaping  
  - `python-docx`, `xlsxwriter`, `openpyxl` – document and spreadsheet export  
  - `colorama` – colorized CLI output  
- **Architecture Overview**

```

loominar/
├── api/               # SonarQube data fetchers
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
loominar -u http://localhost:9000 -t squ_abc123 -p A-Star-2 -f excel -v 2
```

#### Example Output

```
🧶 Loominar v0.2.0 — SonarQube Report Exporter
📡 Fetching SonarQube data...
🧾 Generating EXCEL report...
✅ Report successfully saved to: C:\Users\MohamedAli\Documents\Loominar
```

---

### 🧩 Verbosity Levels

| Level                    | Description                      | Output Example                          |
| ------------------------ | -------------------------------- | --------------------------------------- |
| **1 – Minimal**          | Only success and error messages  | ✅ Report saved / ❌ Connection failed    |
| **2 – Normal (default)** | Key steps + summary messages     | 📡 Fetching data / 🧾 Generating report |
| **3 – Detailed**         | Full debug + API pagination logs | `Page 2/10 → 500 issues` etc.           |

---

### 🧠 Roadmap

* 📄 **PDF and HTML Exports** using WeasyPrint + Jinja2 templates
* ⚙️ **Config File Support** (`.loominarrc` or `.env`)
* 🔔 **Slack / Teams Notifications** for report summaries
* 📊 **Trend & Delta Analysis** between runs
* 🧮 **Batch Mode** for multi-project reporting
* 🌐 **CI/CD Integration** (GitHub Actions & Azure Pipelines)

---

### 🧾 License

Licensed under the **MIT License**.
See the [LICENSE](./LICENSE) file for full details.

---

### 💡 Maintainer

**Mohamed Ali**
Software Consultant | DevSecOps & IAM Engineer
[GitHub](https://github.com/mhmd4li) | [LinkedIn](https://linkedin.com/in/mohamed-ali-bmd)

---
