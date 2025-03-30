#!/usr/bin/env python3
import os
import re
import sys
import csv
import json
import time
import uuid
import random
import logging
import argparse
import hashlib
import yaml
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent
from cryptography.fernet import Fernet

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scanner.log'),
        logging.StreamHandler()
    ]
)

class SecurityScanner:
    def __init__(self, args):
        self.args = args
        self.config = self._load_config()
        self.session = self._init_session()
        self.ua = UserAgent()
        self.cipher = Fernet(self.config['security']['encryption_key'])
        self.payload_db = self._load_payloads()
        self.scanned_targets = 0

    def _load_config(self):
        config_path = 'config.yaml'
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        required_sections = {
            'security': ['encryption_key'],
            'payloads': [],
            'network': [],
            'endpoints': ['google'],
            'credentials': ['api_key', 'cse_id'],
            'stealth': ['referers', 'time_based_threshold'],
            'detection_patterns': []
        }
        
        for section, keys in required_sections.items():
            if section not in config:
                raise ValueError(f"Missing config section: {section}")
            for key in keys:
                if key not in config[section]:
                    raise ValueError(f"Missing key '{key}' in [{section}]")
        
        config['network'].setdefault('proxies', {})
        config['network'].setdefault('timeout', 10)
        config.setdefault('performance', {'threads': 10})
        
        return config

    def _init_session(self):
        session = requests.Session()
        session.proxies.update(self.config['network']['proxies'])
        session.headers.update({
            'X-Scanner-ID': hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16],
            'Accept-Language': 'en-US,en;q=0.9'
        })
        return session

    def _load_payloads(self):
        payload_db = {}
        for dbms in self.config['payloads']:
            try:
                payload_db[dbms] = [
                    self.cipher.decrypt(p.encode()).decode()
                    for p in self.config['payloads'][dbms]
                    ]
            except Exception as e:
                logging.error(f"Payload decryption failed for {dbms}: {str(e)}")
                raise
        return payload_db

    def _apply_evasion(self):
        if self.args.stealth:
            delay = max(self.args.delay + random.uniform(0, self.args.jitter), 0.1)
            time.sleep(delay)
            
            self.session.headers.update({
                'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                'Referer': random.choice(self.config['stealth']['referers'])
            })
            
            if self.args.random_agent:
                self.session.headers['User-Agent'] = self.ua.random

    def execute_search(self, query_params):
        try:
            processed_query = self._build_query(query_params)
            results = []
            max_pages = 10
            
            for page in range(max_pages):
                params = self._build_api_payload(processed_query, query_params, page+1)
                response = self.session.get(
                    self.config['endpoints']['google'],
                    params=params,
                    timeout=self.config['network']['timeout']
                )
                page_results = self._parse_response(response)
                results.extend(page_results)
                
                if len(page_results) < params['num']:
                    break
                    
            return results
            
        except Exception as e:
            logging.error(f"Search failed: {str(e)}")
            return []

    def _build_query(self, params):
        base = params['dork']
        if params.get('site'):
            base += f" site:{params['site']}"
        if params.get('file_type'):
            base += f" filetype:{params['file_type']}"
        return re.sub(r"([\'\"])", r"\\\1", base)

    def _build_api_payload(self, query, params, start=1):
        return {
            'q': query,
            'key': self.config['credentials']['api_key'],
            'cx': self.config['credentials']['cse_id'],
            'num': min(params['max_results'], 10),
            'start': start,
            'lr': f"lang_{params.get('lang', 'en')}",
            'cr': params.get('region', ''),
            'dateRestrict': params.get('date_range', '')
        }

    def _parse_response(self, response):
        try:
            data = response.json()
            if 'error' in data:
                logging.error(f"API Error: {data['error']['message']}")
                return []
            return [item['link'] for item in data.get('items', [])]
        except json.JSONDecodeError:
            logging.error("Invalid API response format")
            return []

    def perform_scanning(self, targets):
        valid_targets = [url for url in targets if url.startswith(('http://', 'https://'))]
        logging.info(f"Scanning {len(valid_targets)} valid targets")
        
        print(f"\n{' Scan Progress ':=^60}")
        print(f"Total Targets: {len(valid_targets)}")
        print(f"Thread Workers: {self.config['performance']['threads']}")
        print(f"Stealth Mode: {'Enabled' if self.args.stealth else 'Disabled'}")
        print("-" * 60)
        
        with ThreadPoolExecutor(max_workers=self.config['performance']['threads']) as executor:
            futures = {executor.submit(self._scan_target, url): url for url in valid_targets}
            return self._process_futures(futures, len(valid_targets))

    def _scan_target(self, url):
        try:
            self.scanned_targets += 1
            logging.info(f"Scanning: {url}")
            results = []
            
            for dbms in self.payload_db:
                for payload in self.payload_db[dbms]:
                    self._apply_evasion()
                    result = self._test_injection(url, payload, dbms)
                    if result['vulnerable']:
                        results.append(result)
                        
            return url, results
            
        except Exception as e:
            logging.error(f"Error scanning {url}: {str(e)}")
            return url, []

    def _test_injection(self, url, payload, dbms):
        try:
            separator = '&' if '?' in url else '?'
            target_url = f"{url}{separator}{payload}"
            start_time = time.time()
            
            response = self.session.get(
                target_url,
                timeout=self.config['network']['timeout'],
                allow_redirects=False
            )
            
            return self._analyze_response(response, payload, dbms, time.time() - start_time)
            
        except requests.exceptions.RequestException as e:
            return self._error_result(url, payload, f"Request failed: {str(e)}")
        except Exception as e:
            return self._error_result(url, payload, f"Unexpected error: {str(e)}")

    def _analyze_response(self, response, payload, dbms, resp_time):
        content = response.text.lower()
        indicators = [
            pattern for pattern in self.config['detection_patterns']
            if re.search(pattern, content, re.IGNORECASE)
        ]
        return {
            'vulnerable': any([
                response.status_code >= 500,
                resp_time > self.config['stealth']['time_based_threshold'],
                len(indicators) > 0
            ]),
            'url': response.url,
            'payload': self.cipher.encrypt(payload.encode()).decode(),
            'dbms': dbms,
            'indicators': indicators,
            'response_time': resp_time,
            'timestamp': datetime.now().isoformat()
        }

    def _process_futures(self, futures, total_targets):
        results = []
        completed = 0
        start_time = time.time()
        
        for future in as_completed(futures):
            completed += 1
            url, target_results = future.result()
            results.extend(target_results)
            self._update_progress(completed, total_targets, start_time, url)
            
        return results

    def _update_progress(self, completed, total, start_time, current_url):
        elapsed = time.time() - start_time
        avg_time = elapsed / completed if completed > 0 else 0
        remaining = avg_time * (total - completed)
        
        progress = (
            f"Scanned: {completed}/{total} ({completed/total:.0%}) | "
            f"Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s\n"
            f"Current Target: {current_url[:70]}{'...' if len(current_url) > 70 else ''}"
        )
        
        sys.stdout.write("\033[F\033[K" * 2)
        print(f"{progress}\n{'=' * 60}")

    def generate_report(self, results, format):
        if format == 'json':
            self._write_json(results)
        elif format == 'csv':
            self._write_csv(results)
        else:
            self._console_output(results)

    def _error_result(self, url, payload, error_msg):
        return {
            'vulnerable': False,
            'url': url,
            'payload': self.cipher.encrypt(payload.encode()).decode(),
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }

    def _write_json(self, results):
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        logging.info(f"JSON report generated: {filename}")

    def _write_csv(self, results):
        filename = f"report_{datetime.now().strftime('%Y%m%d%H%M')}.csv"
        fieldnames = ['timestamp', 'url', 'dbms', 'payload', 'response_time', 'indicators']
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow({
                    'timestamp': result['timestamp'],
                    'url': result['url'],
                    'dbms': result['dbms'],
                    'payload': self.cipher.decrypt(result['payload'].encode()).decode(),
                    'response_time': f"{result['response_time']:.2f}",
                    'indicators': "; ".join(result['indicators'])
                })
        logging.info(f"CSV report generated: {filename}")

    def _console_output(self, results):
        print("\n" + " Scan Results ".center(60, '='))
        for idx, result in enumerate(results, 1):
            status = "VULNERABLE" if result['vulnerable'] else "SAFE"
            color_code = "\033[91m" if result['vulnerable'] else "\033[92m"
            
            print(f"\n{color_code}Result #{idx} ({status})\033[0m")
            print(f"URL: {result['url']}")
            print(f"DBMS Type: {result['dbms']}")
            print(f"Injected Payload: {self.cipher.decrypt(result['payload'].encode()).decode()}")
            print(f"Response Time: {result['response_time']:.2f}s")
            if result['indicators']:
                print(f"Detection Patterns: {', '.join(result['indicators'])}")
            print("-" * 60)

class ScannerCLI:
    def __init__(self):
        self.parser = self._create_parser()
        self.args = self.parser.parse_args()
        self._validate_args()

    def _create_parser(self):
        parser = argparse.ArgumentParser(description="Advanced Web Vulnerability Scanner")
        parser.add_argument('--dork', required=True, help="Google dork search query")
        parser.add_argument('--site', help="Limit search to specific domain")
        parser.add_argument('--file-type', help="Filter by file extension")
        parser.add_argument('--lang', default='en', help="Search language code")
        parser.add_argument('--region', help="Country code for regional results")
        parser.add_argument('--date-range', help="Date range filter (e.g., 'm1')")
        parser.add_argument('--output', choices=['console','json','csv'], default='console', help="Report output format")
        parser.add_argument('--max-results', type=int, default=50, help="Maximum results to process")
        parser.add_argument('--stealth', action='store_true', help="Enable anti-detection measures")
        parser.add_argument('--jitter', type=float, default=0.5, help="Random delay variation")
        parser.add_argument('--delay', type=float, default=1.0, help="Base delay between requests")
        parser.add_argument('--random-agent', action='store_true', help="Randomize user agents")
        return parser

    def _validate_args(self):
        if self.args.max_results < 1 or self.args.max_results > 100:
            self.parser.error("--max-results must be 1-100")
        if self.args.delay < 0 or self.args.jitter < 0:
            self.parser.error("Delay values must be positive")

    def execute_scan(self):
        try:
            scanner = SecurityScanner(self.args)
            logging.info("Starting target discovery phase...")
            
            targets = scanner.execute_search({
                'dork': self.args.dork,
                'site': self.args.site,
                'file_type': self.args.file_type,
                'lang': self.args.lang,
                'region': self.args.region,
                'date_range': self.args.date_range,
                'max_results': self.args.max_results
            })
            
            if not targets:
                logging.warning("No targets discovered - exiting")
                sys.exit(0)
                
            print("\n[Discovered Targets]")
            for idx, url in enumerate(targets[:5], 1):
                print(f"{idx}. {url}")
            if len(targets) > 5:
                print(f"Displaying 5 of {len(targets)} targets...")
            print("-" * 60)
            
            logging.info("Initiating vulnerability assessment...")
            results = scanner.perform_scanning(targets)
            
            if not results:
                logging.warning("No vulnerabilities detected")
                sys.exit(1)
                
            scanner.generate_report(results, self.args.output)
            logging.info("Operation completed successfully")

        except Exception as e:
            logging.error(f"Critical failure: {str(e)}", exc_info=True)
            sys.exit(2)

if __name__ == '__main__':
    try:
        ScannerCLI().execute_scan()
    except KeyboardInterrupt:
        print("\n\033[91mScan aborted by user\033[0m")
        sys.exit(130)