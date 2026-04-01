#!/usr/bin/env python3
"""
CloudPrice - Telecharger les tarifs AWS Paris + Azure France Central
Usage : python3 fetch_prices.py
"""

import json, os, sys, http.client, urllib.parse, gzip, re, subprocess
from datetime import datetime
try:
    from xml.etree import ElementTree as ET
except ImportError:
    ET = None

DATA_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_DIR_AWS  = os.path.join(DATA_DIR, "aws")
DATA_DIR_AZ   = os.path.join(DATA_DIR, "azure")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DATA_DIR_AWS, exist_ok=True)
os.makedirs(DATA_DIR_AZ, exist_ok=True)

CACHE_DAYS = 7

def is_fresh(filepath, days=CACHE_DAYS):
    """Retourne True si le fichier existe et a moins de `days` jours."""
    if not os.path.exists(filepath):
        return False
    age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(filepath))).days
    return age < days

# ── VEILLE FINOPS ──
def fetch_aws_blog():
    print("\nVeille AWS FinOps blog (RSS)...")
    try:
        conn = http.client.HTTPSConnection("aws.amazon.com", timeout=15)
        conn.request("GET", "/blogs/aws-cloud-financial-management/tag/finops/feed/",
                     headers={"User-Agent": "cloudprice/1.0"})
        r = conn.getresponse()
        if r.status != 200: return []
        raw = r.read().decode("utf-8", errors="replace")
        conn.close()
        if ET is None or not raw.strip().startswith('<'): return []
        root = ET.fromstring(raw)
        articles = []
        for entry in root.findall('.//item'):
            title   = (entry.findtext('title') or "").strip()
            url     = (entry.findtext('link') or "").strip()
            date    = (entry.findtext('pubDate') or "").strip()[:16]
            desc    = (entry.findtext('description') or entry.findtext('summary') or "").strip()
            summary = re.sub(r'<[^>]+>', '', desc)[:160].strip()
            if title and url:
                articles.append({"title": title, "url": url, "date": date, "source": "aws", "summary": summary})
            if len(articles) >= 15: break
        log("AWS blog : " + str(len(articles)) + " articles")
        return articles
    except Exception as e:
        log("Erreur AWS blog : " + str(e))
        return []

def fetch_azure_blog():
    print("\nVeille Azure FinOps blog...")
    try:
        conn = http.client.HTTPSConnection("techcommunity.microsoft.com", timeout=15)
        conn.request("GET", "/t5/s/gxcuf89792/rss/board?board.id=FinOpsBlog",
                     headers={"User-Agent": "cloudprice/1.0"})
        r = conn.getresponse()
        if r.status != 200: return []
        raw = r.read().decode("utf-8", errors="replace")
        conn.close()
        if ET is None: return []
        root = ET.fromstring(raw)
        articles = []
        for entry in root.findall('.//item'):
            title   = (entry.findtext('title') or "").strip()
            url     = (entry.findtext('link') or "").strip()
            date    = (entry.findtext('pubDate') or "").strip()[:16]
            desc    = (entry.findtext('description') or entry.findtext('summary') or "").strip()
            summary = re.sub(r'<[^>]+>', '', desc)[:160].strip()
            if title and url:
                articles.append({"title": title, "url": url, "date": date, "source": "azure", "summary": summary})
            if len(articles) >= 15: break
        log("Azure blog : " + str(len(articles)) + " articles")
        return articles
    except Exception as e:
        log("Erreur Azure blog : " + str(e))
        return []

def fetch_finops_foundation():
    print("\nVeille FinOps Foundation...")
    try:
        conn = http.client.HTTPSConnection("www.finops.org", timeout=15)
        conn.request("GET", "/feed/", headers={"User-Agent": "cloudprice/1.0"})
        r = conn.getresponse()
        if r.status not in (200, 301, 302): return []
        raw = r.read().decode("utf-8", errors="replace")
        conn.close()
        if ET is None or not raw.strip().startswith('<'): return []
        root = ET.fromstring(raw)
        articles = []
        for entry in root.findall('.//item'):
            title   = (entry.findtext('title') or "").strip()
            url     = (entry.findtext('link') or "").strip()
            date    = (entry.findtext('pubDate') or "").strip()[:16]
            desc    = (entry.findtext('description') or entry.findtext('summary') or "").strip()
            summary = re.sub(r'<[^>]+>', '', desc)[:160].strip()
            if title and url:
                articles.append({"title": title, "url": url, "date": date, "source": "ff", "summary": summary})
            if len(articles) >= 15: break
        log("FinOps Foundation : " + str(len(articles)) + " articles")
        return articles
    except Exception as e:
        log("Erreur FinOps Foundation : " + str(e))
        return []

def parse_date(date_str):
    """Parse RSS date for sorting — retourne un tuple comparable."""
    if not date_str: return (0,)
    months = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
              'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', date_str)
    if m:
        d, mo, y = int(m.group(1)), months.get(m.group(2), 0), int(m.group(3))
        return (y, mo, d)
    return (0,)

def fetch_veille():
    veille_file = os.path.join(DATA_DIR, "veille.json")
    if is_fresh(veille_file, days=1):
        log("cache frais utilise : " + veille_file)
        with open(veille_file, encoding="utf-8") as f: return json.load(f)
    articles = fetch_aws_blog() + fetch_azure_blog() + fetch_finops_foundation()
    # Trier par date décroissante
    articles.sort(key=lambda a: parse_date(a.get("date","")), reverse=True)
    with open(veille_file, "w", encoding="utf-8") as f: json.dump(articles, f, indent=2, ensure_ascii=False)
    log("veille sauvegardee : " + str(len(articles)) + " articles -> " + veille_file)
    return articles

def log(msg):
    print("  + " + msg)

def get_family_aws(name):
    n = name.lower()
    if n.startswith('t'): return "burstable"
    if n.startswith(('m5','m6','m7','m8')): return "general"
    if n.startswith(('c5','c6','c7','c8')): return "compute"
    if n.startswith(('r5','r6','r7','r8','x1','x2')): return "memory"
    if n.startswith(('i3','i4','d2','d3')): return "storage"
    if n.startswith(('p2','p3','p4','g3','g4','g5','inf')): return "gpu"
    return "other"

def get_family_azure(name):
    n = name.lower().replace('standard_','').replace('_','').replace(' ','')
    if n.startswith('b'): return "burstable"
    if n.startswith(('d2','d4','d8','d16','d32','d48','d64','d96')): return "general"
    if n.startswith('f'): return "compute"
    if n.startswith(('e2','e4','e8','e16','e32','e48','e64','e96','e112','e128','m')): return "memory"
    if n.startswith(('l4','l8','l16','l32','l48','l64','l80')): return "storage"
    if n.startswith(('nc','nd','nv','ng')): return "gpu"
    return "other"


# ── CARBON INTENSITY ──
CARBON_ZONES = {
    "eu-west-3":          {"zone": "FR",           "label": "France"},
    "eu-north-1":         {"zone": "SE",           "label": "Sweden"},
    "eu-south-1":         {"zone": "IT",           "label": "Italy"},
    "eu-south-2":         {"zone": "ES",           "label": "Spain"},
    "eu-central-1":       {"zone": "DE",           "label": "Germany"},
    "eu-west-1":          {"zone": "IE",           "label": "Ireland"},
    "eu-west-2":          {"zone": "GB",           "label": "United Kingdom"},
    "us-east-1":          {"zone": "US-MIDA-PJM",  "label": "US East"},
    "francecentral":      {"zone": "FR",           "label": "France"},
    "northeurope":        {"zone": "IE",           "label": "Ireland"},
    "westeurope":         {"zone": "NL",           "label": "Netherlands"},
    "germanywestcentral": {"zone": "DE",           "label": "Germany"},
    "uksouth":            {"zone": "GB",           "label": "United Kingdom"},
    "swedencentral":      {"zone": "SE",           "label": "Sweden"},
    "italynorth":         {"zone": "IT",           "label": "Italy"},
    "eastus":             {"zone": "US-MIDA-PJM",  "label": "US East"},
}

def fetch_carbon():
    """Récupère les données carbone statiques depuis electricitymaps GitHub."""
    carbon_file = os.path.join(DATA_DIR, "carbon.json")
    if is_fresh(carbon_file, days=30):
        log("cache frais carbon : " + carbon_file)
        with open(carbon_file, encoding="utf-8") as f: return json.load(f)
    print("\nDonnées carbone (Electricity Maps open-source)...")
    # Données annuelles moyennes par pays (gCO2eq/kWh) - source: electricitymaps.com/data-portal
    # Mise à jour annuelle, valeurs 2023
    static_carbon = {
        "FR":          {"co2": 56,  "renew": 91, "mix": "Nuclear + Hydro"},
        "SE":          {"co2": 21,  "renew": 98, "mix": "Hydro + Wind"},
        "DE":          {"co2": 312, "renew": 52, "mix": "Gas + Coal + Wind"},
        "IE":          {"co2": 258, "renew": 58, "mix": "Gas + Wind"},
        "GB":          {"co2": 192, "renew": 64, "mix": "Gas + Wind + Nuclear"},
        "US-MIDA-PJM": {"co2": 358, "renew": 41, "mix": "Gas + Coal + Nuclear"},
        "NL":          {"co2": 278, "renew": 56, "mix": "Gas + Wind"},
    }
    # Construire le dict par région cloud
    result = {}
    for region, meta in CARBON_ZONES.items():
        zone = meta["zone"]
        if zone in static_carbon:
            result[region] = {**static_carbon[zone], "zone": zone, "label": meta["label"]}
    with open(carbon_file, "w", encoding="utf-8") as f: json.dump(result, f, indent=2)
    log("carbon sauvegarde : " + carbon_file)
    return result

FRED_API_KEY = os.environ.get('FRED_API_KEY', '')  # https://fred.stlouisfed.org/docs/api/api_key.html

def fetch_eur_rate():
    """Récupère le taux EUR/USD depuis l'API FRED (cache 1 jour)."""
    rate_file = os.path.join(DATA_DIR, "eur_rate.json")
    if is_fresh(rate_file, days=1):
        with open(rate_file, encoding="utf-8") as f: data = json.load(f)
        log("EUR/USD cache : " + str(data['rate']))
        return data['rate']
    if not FRED_API_KEY:
        log("FRED_API_KEY non definie — taux EUR hardcode 0.92")
        return 0.92
    print("\nTaux EUR/USD (FRED API)...")
    try:
        conn = http.client.HTTPSConnection("api.stlouisfed.org", timeout=10)
        path = "/fred/series/observations?series_id=DEXUSEU&sort_order=desc&limit=1&file_type=json&api_key=" + FRED_API_KEY
        conn.request("GET", path, headers={"User-Agent": "cloudprice/1.0"})
        r = conn.getresponse()
        if r.status != 200: raise Exception("HTTP " + str(r.status))
        data = json.loads(r.read())
        conn.close()
        val = float(data["observations"][0]["value"])
        eur_rate = round(1 / val, 4)  # DEXUSEU = USD par EUR → inverser
        json.dump({"rate": eur_rate, "date": data["observations"][0]["date"]}, open(rate_file, "w", encoding="utf-8"))
        log("EUR/USD = " + str(eur_rate) + " (" + data["observations"][0]["date"] + ")")
        return eur_rate
    except Exception as e:
        log("Erreur FRED : " + str(e) + " — taux hardcode 0.92")
        return 0.92

# ── AZURE ──
AZURE_REGIONS = {
    "francecentral":      {"label": "Paris",       "flag": "&#x1F1EB;&#x1F1F7;", "location": "France Central"},
    "northeurope":        {"label": "Irlande",     "flag": "&#x1F1EE;&#x1F1EA;", "location": "North Europe"},
    "westeurope":         {"label": "Pays-Bas",    "flag": "&#x1F1F3;&#x1F1F1;", "location": "West Europe"},
    "germanywestcentral": {"label": "Francfort",   "flag": "&#x1F1E9;&#x1F1EA;", "location": "Germany West Central"},
    "uksouth":            {"label": "Londres",     "flag": "&#x1F1EC;&#x1F1E7;", "location": "UK South"},
    "swedencentral":      {"label": "Su\u00e8de",  "flag": "&#x1F1F8;&#x1F1EA;", "location": "Sweden Central"},
    "italynorth":         {"label": "Milan",       "flag": "&#x1F1EE;&#x1F1F9;", "location": "Italy North"},
    "eastus":             {"label": "Virginie",    "flag": "&#x1F1FA;&#x1F1F8;", "location": "East US"},
}

SKUS_CACHE_DAYS = 30

def fetch_azure_skus(region="francecentral", az_available=True):
    """Récupère les specs hardware Azure via l'API Resource SKUs (nécessite az login).
    Retourne un dict { 'D2s v5': {vcpu, ram, storage, network, processor}, ... }
    """
    cache_file = os.path.join(DATA_DIR_AZ, "skus-" + region + ".json")
    if is_fresh(cache_file, days=SKUS_CACHE_DAYS):
        log("cache SKUs frais : " + cache_file)
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    # az CLI non disponible — utiliser le cache existant ou retourner vide
    if not az_available:
        if os.path.exists(cache_file):
            log("utilisation du cache SKUs existant : " + cache_file)
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Récupérer la subscription ID
    try:
        r = subprocess.run(["az", "account", "show", "--query", "id", "-o", "tsv"],
                           capture_output=True, text=True, timeout=15, check=True)
        sub_id = r.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        log("az account show échoué — token expiré ? Relancez az login")
        if os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Appeler l'API Resource SKUs
    url = ("https://management.azure.com/subscriptions/" + sub_id +
           "/providers/Microsoft.Compute/skus?api-version=2021-07-01"
           "&$filter=location eq '" + region + "'")
    try:
        log("appel Azure Resource SKUs pour " + region + "...")
        r = subprocess.run(["az", "rest", "--method", "get", "--url", url],
                           capture_output=True, text=True, timeout=60, check=True)
        data = json.loads(r.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        log("Erreur Resource SKUs : " + str(e))
        if os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Parser les résultats
    skus = {}
    for item in data.get("value", []):
        if item.get("resourceType") != "virtualMachines":
            continue
        name_raw = item.get("name", "")  # ex: Standard_D2s_v5
        caps = {c["name"]: c["value"] for c in item.get("capabilities", [])}

        vcpu = int(caps.get("vCPUs", 0))
        ram  = float(caps.get("MemoryGB", 0))
        temp_disk_mb = int(caps.get("MaxResourceVolumeMB", 0))
        max_disks = int(caps.get("MaxDataDiskCount", 0))
        disk_iops = int(caps.get("UncachedDiskIOPS", 0))
        arch = caps.get("CpuArchitectureType", "")

        # Formater le stockage temp
        storage_str = ""
        if temp_disk_mb > 0:
            temp_gb = temp_disk_mb / 1024
            storage_str = (str(int(temp_gb)) if temp_gb == int(temp_gb) else str(round(temp_gb, 1))) + " GiB temp"

        # Déduire le processeur depuis le nom de la série + architecture
        # Convention Azure : 'a' dans le suffixe = AMD, 'p' = ARM/Ampere, sinon Intel
        key = name_raw.replace("Standard_", "").replace("_", " ").strip()
        key_lower = key.lower().replace(" ", "")
        if arch == "Arm64":
            processor_str = "Arm64 (Ampere)"
        elif "a" in re.sub(r'\d+', '', key_lower.split("v")[0] if "v" in key_lower else key_lower).replace("standard", ""):
            processor_str = "AMD"
        else:
            processor_str = "Intel"

        skus[key] = {
            "vcpu": vcpu,
            "ram": ram,
            "storage": storage_str,
            "network": "",
            "processor": processor_str,
            "max_disks": max_disks,
            "disk_iops": disk_iops
        }

    log("SKUs parsés : " + str(len(skus)) + " VMs")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(skus, f, ensure_ascii=False, indent=2)
    log("sauvegarde SKUs -> " + cache_file)
    return skus


def fetch_azure(region="francecentral", skus=None):
    print("\nAzure " + region + "...")
    if skus is None:
        skus = {}
    filt    = "armRegionName eq '" + region + "' and serviceName eq 'Virtual Machines' and priceType eq 'Consumption'"
    encoded = filt.replace(" ", "%20")
    base_path = "/api/retail/prices?$filter=" + encoded + "&$top=1000"

    all_items = []
    skip = 0
    while True:
        path = base_path + "&$skip=" + str(skip)
        conn = http.client.HTTPSConnection("prices.azure.com", timeout=30)
        conn.request("GET", path, headers={"User-Agent": "cloudprice/1.0"})
        r = conn.getresponse()
        if r.status != 200:
            body = r.read(500).decode("utf-8", errors="replace")
            raise Exception("Azure HTTP " + str(r.status) + ": " + r.reason + "\n" + body)
        data  = json.loads(r.read())
        conn.close()
        items = data.get("Items", [])
        all_items.extend(items)
        log("skip=" + str(skip) + " : " + str(len(items)) + " items (total " + str(len(all_items)) + ")")
        if len(items) < 1000:
            break
        skip += 1000

    result = {}
    for item in all_items:
        sku   = (item.get("skuName") or "").lower()
        price = item.get("retailPrice", 0)
        if price <= 0 or "spot" in sku or "low priority" in sku or "windows" in sku:
            continue
        key = item["skuName"].replace(" Linux","").replace("Linux","").replace("Standard_","").replace("standard_","").strip()
        sku_meta = skus.get(key) or skus.get(key.replace("_", " "), {})
        if sku_meta:
            # Données exactes depuis l'API Resource SKUs
            vcpu = sku_meta.get("vcpu", 0)
            ram  = sku_meta.get("ram", 0)
        else:
            # Fallback : estimation par ratio depuis le nom
            m = re.search(r'^[A-Za-z]+?(\d+)', key.replace('Standard_','').replace('standard_',''))
            vcpu = int(m.group(1)) if m else 0
            kl = key.lower().replace(' ','').replace('_','')
            if kl.startswith('b'):
                ram = vcpu * 4
                if '1ls' in kl: ram = 0.5
                elif '1s' in kl and '1ms' not in kl: ram = 1
                elif '1ms' in kl: ram = 2
                elif '2s' in kl and '2ms' not in kl: ram = 4
                elif '2ms' in kl: ram = 8
            elif kl.startswith('f'): ram = vcpu * 2
            elif kl.startswith(('e','r','m')): ram = vcpu * 8
            elif kl.startswith(('l',)): ram = vcpu * 8
            else: ram = vcpu * 4
        storage    = sku_meta.get("storage", "")
        network    = sku_meta.get("network", "")
        processor  = sku_meta.get("processor", "")
        max_disks  = sku_meta.get("max_disks", 0)
        disk_iops  = sku_meta.get("disk_iops", 0)
        # Déduire le processor depuis le nom si absent
        if not processor:
            kn = key.lower().replace(" ", "").replace("_", "")
            base = re.sub(r'v\d+$', '', kn).rstrip()
            letters = re.sub(r'\d+', '', base)
            if 'p' in letters[1:]:
                processor = "Arm64 (Ampere)"
            elif 'a' in letters[1:]:
                processor = "AMD"
            else:
                processor = "Intel"
        fam = get_family_azure(key)
        if vcpu == 0: continue  # skip instances sans vCPU détecté
        if key not in result or price < result[key]["price"]:
            result[key] = {"name": key, "price": price, "vcpu": vcpu, "ram": ram, "fam": fam,
                           "storage": storage, "network": network, "processor": processor,
                           "max_disks": max_disks, "disk_iops": disk_iops}

    log("instances uniques : " + str(len(result)))

    # ── Prix réservés Azure (1 an + 3 ans) ──
    # retailPrice Azure = prix total de la période (1yr = 8760h, 3yr = 26280h)
    for term_label, term_years, term_hours in [("1 Year", "price_1yr", 8760), ("3 Years", "price_3yr", 26280)]:
        filt_ri  = "armRegionName eq '" + region + "' and serviceName eq 'Virtual Machines' and priceType eq 'Reservation' and reservationTerm eq '" + term_label + "'"
        enc_ri   = filt_ri.replace(" ", "%20").replace("'", "%27")
        path_ri  = "/api/retail/prices?$filter=" + enc_ri + "&$top=1000"
        ri_items = []
        skip2    = 0
        while True:
            try:
                conn2 = http.client.HTTPSConnection("prices.azure.com", timeout=30)
                conn2.request("GET", path_ri + "&$skip=" + str(skip2), headers={"User-Agent": "cloudprice/1.0"})
                r2   = conn2.getresponse()
                if r2.status != 200: conn2.close(); break
                d2   = json.loads(r2.read())
                conn2.close()
                batch = d2.get("Items", [])
                ri_items.extend(batch)
                if len(batch) < 1000: break
                skip2 += 1000
            except Exception as e:
                log("Erreur Reserved Azure " + term_label + " : " + str(e)); break
        log("Reserved " + term_label + " : " + str(len(ri_items)) + " items")
        for item in ri_items:
            sku_raw = (item.get("skuName") or "")
            sku     = sku_raw.lower()
            price   = item.get("retailPrice", 0)
            if price <= 0: continue
            if "windows" in sku or "spot" in sku: continue
            key = sku_raw.replace(" Linux","").replace("Linux","").strip()
            # Convertir prix annuel en prix horaire
            price_h = price / term_hours
            if key in result:
                result[key][term_years] = round(price_h, 6)
    ri1 = sum(1 for v in result.values() if v.get("price_1yr"))
    ri3 = sum(1 for v in result.values() if v.get("price_3yr"))
    log("Azure avec Reserved 1yr : " + str(ri1) + "  3yr : " + str(ri3))
    return result

# ── AZURE BDD ──
def fetch_azure_bdd(region="francecentral"):
    import urllib.parse
    location = AZURE_REGIONS.get(region, {}).get("location", "France Central")
    services = [
        ("Azure Database for PostgreSQL", "postgresql", "armRegionName eq '" + region + "'"),
        ("Azure Database for MySQL",      "mysql",      "armRegionName eq '" + region + "'"),
        ("SQL Database",                  "sqlserver",  "location eq '" + location + "'"),
    ]
    result = {}
    for service_name, engine, region_filter in services:
        print("\nAzure BDD — " + service_name + "...")
        filt      = region_filter + " and serviceName eq '" + service_name + "' and priceType eq 'Consumption'"
        encoded   = urllib.parse.quote(filt, safe="'=&$")
        base_path = "/api/retail/prices?$filter=" + encoded + "&$top=1000"
        all_items = []
        skip = 0
        while True:
            path = base_path + "&$skip=" + str(skip)
            conn = http.client.HTTPSConnection("prices.azure.com", timeout=30)
            conn.request("GET", path, headers={"User-Agent": "cloudprice/1.0"})
            r = conn.getresponse()
            if r.status != 200:
                body = r.read(500).decode("utf-8", errors="replace")
                log("Erreur " + service_name + " HTTP " + str(r.status))
                break
            data  = json.loads(r.read())
            conn.close()
            items = data.get("Items", [])
            all_items.extend(items)
            log("skip=" + str(skip) + " : " + str(len(items)) + " items")
            if len(items) < 1000:
                break
            skip += 1000

        # Debug : afficher les 3 premiers items bruts
        if all_items:
            log("  Exemples items " + service_name + ":")
            for dbg in all_items[:3]:
                log("    skuName=" + str(dbg.get("skuName")) + " price=" + str(dbg.get("retailPrice")))

        for item in all_items:
            sku_raw     = (item.get("skuName") or "")
            sku         = sku_raw.lower()
            product     = (item.get("productName") or "").lower()
            price       = item.get("retailPrice", 0)
            if price <= 0: continue
            # Flexible Server uniquement
            # Exclure stockage, backup, IO, throughput, disk
            if any(x in sku for x in ["storage", "backup", " io", "throughput", "disk", "iops", "log", "redundancy"]): continue

            # Détecter le tier depuis le skuName
            if any(x in sku for x in ["business critical", "memory optimized", "mo ", "m vcore", "_e", "m128", "m64", "m32"]):
                tier = "memory"
                ram_ratio = 8
            elif any(x in sku for x in ["burstable", "_b", "b1ms", "b2ms", "b2s", "b4ms", "b8ms", "b12ms", "b16ms", "b20ms"]):
                tier = "burstable"
                ram_ratio = 4
            else:
                tier = "general"
                ram_ratio = 4

            # Extraire vCores
            m = (re.search(r'(\d+)m?\s*vcore', sku)
              or re.search(r'_(e|b)(\d+)', sku)
              or re.search(r'_(\d+)', sku)
              or re.search(r'^(\d+)', sku))
            if not m: continue
            # Prendre le bon groupe selon le pattern
            try:
                vcpu = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and not m.group(2).isalpha() else int(m.group(1))
            except:
                continue
            if vcpu == 0 or vcpu > 256: continue
            ram = vcpu * ram_ratio

            # Extraire la série pour un nom lisible
            ms  = re.match(r'standard_([a-z]+)(\d+)([a-z]*)_(v\d+)', sku)
            ms2 = re.match(r'standard_([a-z])(\d+)(ms?|s)$', sku) if not ms else None
            ms3 = re.match(r'm(\d+)d(ms?)_(v\d+)', sku) if not ms and not ms2 else None
            if ms:
                display = engine + " " + ms.group(1).upper() + ms.group(2) + ms.group(3) + "s_" + ms.group(4)
            elif ms2:
                display = engine + " " + ms2.group(1).upper() + ms2.group(2) + ms2.group(3)
            elif ms3:
                display = engine + " M" + ms3.group(1) + "d" + ms3.group(2) + "_" + ms3.group(3)
            else:
                display = engine + " " + str(vcpu) + "vCPU"
            key = engine + "||" + sku.strip()
            if key not in result or price < result[key]["price"]:
                result[key] = {"name": display, "price": price, "vcpu": vcpu, "ram": ram, "fam": tier, "engine": engine, "sku": sku_raw}

    log("instances BDD Azure uniques : " + str(len(result)))

    # Prix réservés BDD Azure non disponibles (skuName=vCore sans vcpu, matching impossible)
    return result

# ── AWS ──
AWS_REGIONS = {
    "eu-west-3":    {"label": "Paris",      "flag": "&#x1F1EB;&#x1F1F7;"},
    "eu-west-1":    {"label": "Irlande",    "flag": "&#x1F1EE;&#x1F1EA;"},
    "eu-central-1": {"label": "Francfort",  "flag": "&#x1F1E9;&#x1F1EA;"},
    "eu-west-2":    {"label": "Londres",    "flag": "&#x1F1EC;&#x1F1E7;"},
    "eu-north-1":   {"label": "Su\u00e8de", "flag": "&#x1F1F8;&#x1F1EA;"},
    "eu-south-1":   {"label": "Milan",      "flag": "&#x1F1EE;&#x1F1F9;"},
    "eu-south-2":   {"label": "Espagne",    "flag": "&#x1F1EA;&#x1F1F8;"},
    "us-east-1":    {"label": "Virginie",   "flag": "&#x1F1FA;&#x1F1F8;"},
}

def fetch_aws(region="eu-west-3"):
    print("\nAWS " + region + " (~100MB, patience)...")
    conn = http.client.HTTPSConnection("pricing.us-east-1.amazonaws.com", timeout=120)
    conn.request("GET", "/offers/v1.0/aws/AmazonEC2/current/" + region + "/index.json",
                 headers={"User-Agent": "cloudprice/1.0", "Accept-Encoding": "gzip"})
    r   = conn.getresponse()
    if r.status != 200:
        raise Exception("AWS HTTP " + str(r.status))
    raw = r.read()
    conn.close()
    log("telecharge " + str(round(len(raw)/1024/1024, 1)) + " MB")
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
        log("decompresse " + str(round(len(raw)/1024/1024, 1)) + " MB")
    data     = json.loads(raw)
    products = data.get("products", {})
    terms_od = (data.get("terms") or {}).get("OnDemand", {})
    terms_ri = (data.get("terms") or {}).get("Reserved", {})
    result   = {}

    # Index SKU -> instanceType pour les Reserved
    sku_to_itype = {}
    for sku, prod in products.items():
        attr = prod.get("attributes", {})
        if (attr.get("operatingSystem") != "Linux" or attr.get("tenancy") != "Shared"
                or attr.get("preInstalledSw") != "NA" or attr.get("capacitystatus") != "Used"):
            continue
        itype = attr.get("instanceType","")
        if itype:
            sku_to_itype[sku] = itype

    for sku, itype in sku_to_itype.items():
        # On-Demand
        price = None
        for term in (terms_od.get(sku) or {}).values():
            for pd in term.get("priceDimensions",{}).values():
                p = float((pd.get("pricePerUnit") or {}).get("USD", 0))
                if p > 0 and (price is None or p < price): price = p
        if not price: continue

        # Reserved Standard No Upfront
        price_1yr_no  = None
        price_3yr_no  = None
        price_1yr_all = None
        price_3yr_all = None
        for term in (terms_ri.get(sku) or {}).values():
            ta = term.get("termAttributes", {})
            if ta.get("OfferingClass") != "standard": continue
            purchase = ta.get("PurchaseOption", "")
            if purchase not in ("No Upfront", "All Upfront"): continue
            lease = ta.get("LeaseContractLength","")
            hours = 8760 if lease == "1yr" else 26280  # 3yr
            if purchase == "No Upfront":
                # No Upfront = prix horaire direct
                p_ri = None
                for pd in term.get("priceDimensions",{}).values():
                    p = float((pd.get("pricePerUnit") or {}).get("USD", 0))
                    if p > 0 and (p_ri is None or p < p_ri): p_ri = p
                if p_ri is None: continue
                if lease == "1yr" and (price_1yr_no is None or p_ri < price_1yr_no): price_1yr_no = p_ri
                if lease == "3yr" and (price_3yr_no is None or p_ri < price_3yr_no): price_3yr_no = p_ri
            elif purchase == "All Upfront":
                # All Upfront : dimension "Quantity" = coût upfront total, "Hrs" = $0
                # Prix horaire équivalent = coût upfront / heures du contrat
                upfront_total = 0.0
                for pd in term.get("priceDimensions",{}).values():
                    p = float((pd.get("pricePerUnit") or {}).get("USD", 0))
                    unit = pd.get("unit","").lower()
                    if unit == "quantity":
                        upfront_total += p
                p_ri = round(upfront_total / hours, 6) if upfront_total > 0 else None
                if p_ri is None: continue
                if lease == "1yr" and (price_1yr_all is None or p_ri < price_1yr_all): price_1yr_all = p_ri
                if lease == "3yr" and (price_3yr_all is None or p_ri < price_3yr_all): price_3yr_all = p_ri

        attr    = products[sku].get("attributes", {})
        vcpu    = int(attr.get("vcpu", 0) or 0)
        ram     = float((attr.get("memory") or "0").split()[0].replace(",","") or 0)
        fam     = get_family_aws(itype)
        storage   = attr.get("storage", "")
        processor = attr.get("physicalProcessor", "")
        network   = attr.get("networkPerformance", "")
        entry     = {"name": itype, "price": price, "vcpu": vcpu, "ram": ram, "fam": fam, "storage": storage, "processor": processor, "network": network}
        if price_1yr_no:  entry["price_1yr"]     = price_1yr_no
        if price_3yr_no:  entry["price_3yr"]     = price_3yr_no
        if price_1yr_all: entry["price_1yr_all"] = price_1yr_all
        if price_3yr_all: entry["price_3yr_all"] = price_3yr_all
        if itype not in result or price < result[itype]["price"]:
            result[itype] = entry
    log("instances Linux On-Demand : " + str(len(result)))
    ri_1yr = sum(1 for v in result.values() if v.get("price_1yr"))
    ri_3yr = sum(1 for v in result.values() if v.get("price_3yr"))
    log("avec Reserved 1yr : " + str(ri_1yr) + "  3yr : " + str(ri_3yr))
    return result

def fetch_spot_aws(region="eu-west-3"):
    """Récupère les prix Spot Linux depuis spot-price.s3.amazonaws.com/spot.js (JSONP public)."""
    spot_file = os.path.join(DATA_DIR_AWS, "spot-" + region + ".json")
    if is_fresh(spot_file, days=1):
        log("spot cache : " + spot_file)
        with open(spot_file, encoding="utf-8") as f:
            return json.load(f)
    print("\nSpot prices AWS " + region + "...")
    try:
        conn = http.client.HTTPSConnection("spot-price.s3.amazonaws.com", timeout=30)
        conn.request("GET", "/spot.js", headers={"User-Agent": "cloudprice/1.0", "Accept-Encoding": "gzip"})
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        raw = raw.decode("utf-8").strip()
        # Strip JSONP wrapper: callback({...});
        if raw.startswith("callback("):
            raw = raw[len("callback("):]
            if raw.endswith(");"):
                raw = raw[:-2]
            elif raw.endswith(")"):
                raw = raw[:-1]
        data = json.loads(raw)
        result = {}
        for reg in data.get("config", {}).get("regions", []):
            if reg.get("region") != region:
                continue
            for itype_group in reg.get("instanceTypes", []):
                for size_info in itype_group.get("sizes", []):
                    iname = size_info.get("size", "")
                    for col in size_info.get("valueColumns", []):
                        if col.get("name") == "linux":
                            price_str = (col.get("prices") or {}).get("USD", "")
                            try:
                                price = float(price_str)
                                if price > 0:
                                    result[iname] = price
                            except (ValueError, TypeError):
                                pass
        log("spot prices trouvees : " + str(len(result)))
        with open(spot_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result
    except Exception as e:
        print("  Erreur spot " + region + " : " + str(e))
        if os.path.exists(spot_file):
            with open(spot_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

def fetch_ebs(region="eu-west-3"):
    """Récupère les prix EBS (gp2, gp3, io1, io2, st1, sc1) pour une région AWS."""
    print("\nEBS " + region + "...")
    conn = http.client.HTTPSConnection("pricing.us-east-1.amazonaws.com", timeout=120)
    conn.request("GET", "/offers/v1.0/aws/AmazonEC2/current/" + region + "/index.json",
                 headers={"User-Agent": "cloudprice/1.0", "Accept-Encoding": "gzip"})
    r   = conn.getresponse()
    if r.status != 200:
        raise Exception("AWS HTTP " + str(r.status))
    raw = r.read()
    conn.close()
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    data     = json.loads(raw)
    products = data.get("products", {})
    terms_od = (data.get("terms") or {}).get("OnDemand", {})
    result   = {}

    VOLUME_NAMES = {"General Purpose": "gp2", "General Purpose-gp3": "gp3",
                    "Provisioned IOPS": "io1", "Provisioned IOPS-io2": "io2",
                    "Throughput Optimized HDD": "st1", "Cold HDD": "sc1", "Magnetic": "standard"}

    for sku, prod in products.items():
        if prod.get("productFamily") != "Storage":
            continue
        attr = prod.get("attributes", {})
        # Utiliser volumeApiName si disponible, sinon volumeType
        vol_api  = attr.get("volumeApiName", "")
        vol_type = attr.get("volumeType", "")
        name = vol_api if vol_api else VOLUME_NAMES.get(vol_type, vol_type)
        if not name:
            continue

        # Récupérer toutes les dimensions de prix pour ce SKU
        for term in (terms_od.get(sku) or {}).values():
            for pd in term.get("priceDimensions", {}).values():
                p = float((pd.get("pricePerUnit") or {}).get("USD", 0) or 0)
                if p <= 0:
                    continue
                unit = pd.get("unit", "").lower()
                desc = pd.get("description", "").lower()

                if name not in result:
                    result[name] = {"name": name, "type": vol_type, "storage_media": attr.get("storageMedia", "")}

                if "gb" in unit:
                    if "price_gb" not in result[name] or p < result[name]["price_gb"]:
                        result[name]["price_gb"] = round(p, 6)
                elif "iops" in unit:
                    if "price_iops" not in result[name] or p < result[name]["price_iops"]:
                        result[name]["price_iops"] = round(p, 6)
                elif "mbps" in unit or "throughput" in desc or "mbps" in desc:
                    if "price_throughput" not in result[name] or p < result[name]["price_throughput"]:
                        result[name]["price_throughput"] = round(p, 6)

    # Valeurs incluses gratuitement (baseline gp3)
    if "gp3" in result:
        result["gp3"]["free_iops"]       = 3000
        result["gp3"]["free_throughput"]  = 125
    if "io2" in result:
        result["io2"]["tiered_iops"] = True  # io2 a un tarif dégressif par paliers

    log("types EBS : " + str(list(result.keys())))
    return result

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FinOpsMap — AWS &amp; Azure Cloud Pricing Comparator</title>
<meta name="description" content="FinOpsMap is a free open-source tool to compare AWS EC2, RDS and Azure VM, Database pricing in real time. Instant, visual and actionable cloud cost comparison for FinOps engineers.">
<meta name="keywords" content="cloud pricing, AWS EC2 pricing, Azure VM pricing, FinOps tool, cloud cost comparison, AWS vs Azure, cloud cost optimization, GreenOps, carbon intensity cloud">
<meta property="og:title" content="FinOpsMap — AWS &amp; Azure Cloud Pricing Comparator">
<meta property="og:description" content="Compare AWS and Azure cloud pricing in real time. Free, open-source FinOps tool for engineers and architects.">
<meta property="og:image" content="https://finopsmap.com/cover.jpg">
<meta property="og:type" content="website">
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABwklEQVR4nM1Xq24CQRQ9O2mWh0Ig+IA14+saBKLZL6gkuKYKR8InNMFhWkuQ/QKCqCCtwq/hAxAIFMuuaQWZzey89kLZpUfNi3vOnLlzd/CgwK81ftSxayJNYk/usyrJTRzMNlGVCFY1uSrCuwW5DFa8pFzcXfKj++4ga389vePh4yXrr1ezs2KddQSCWCZJpjFqw4ZzzVUE3HcHWtBkGmdtWYRtvQmkHHAFk+2XsV7Nckd1sQAbuWx9bdjIuXGOCKcA185Vy9U+VcTNr6FVADWJKHC5QHYg4KE2NjpG6C3HGB0jbS6dH0hxCwUEPETAQ2yihUYOAJM6z/UF/H4T6fxQKMRaB+Qdt9odbb63HGfkQsDn46u27vv5LSdKhbUUt9odrFczBDzEfrfVHOjhZP2kzrPdqzkjdu/3m6ecMvAUHsEmWmATLbQcUK2X3RDkfr9p3LUM8sdIdUCQ2m5LEbGA1QFqKaXAdaX/byEC3C6oOWGqE0BxQSN9jm1BAh6i1e4YbwmFHCAegcuJ/W5rHKeW8j+/iNQqWdqLyCQEODkgV8pS34RlgKn/1apEmsQeE41bkAPSLahShMzFbBNVkAPAL4p03KMNldoPAAAAAElFTkSuQmCC">
<link rel="shortcut icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABwklEQVR4nM1Xq24CQRQ9O2mWh0Ig+IA14+saBKLZL6gkuKYKR8InNMFhWkuQ/QKCqCCtwq/hAxAIFMuuaQWZzey89kLZpUfNi3vOnLlzd/CgwK81ftSxayJNYk/usyrJTRzMNlGVCFY1uSrCuwW5DFa8pFzcXfKj++4ga389vePh4yXrr1ezs2KddQSCWCZJpjFqw4ZzzVUE3HcHWtBkGmdtWYRtvQmkHHAFk+2XsV7Nckd1sQAbuWx9bdjIuXGOCKcA185Vy9U+VcTNr6FVADWJKHC5QHYg4KE2NjpG6C3HGB0jbS6dH0hxCwUEPETAQ2yihUYOAJM6z/UF/H4T6fxQKMRaB+Qdt9odbb63HGfkQsDn46u27vv5LSdKhbUUt9odrFczBDzEfrfVHOjhZP2kzrPdqzkjdu/3m6ecMvAUHsEmWmATLbQcUK2X3RDkfr9p3LUM8sdIdUCQ2m5LEbGA1QFqKaXAdaX/byEC3C6oOWGqE0BxQSN9jm1BAh6i1e4YbwmFHCAegcuJ/W5rHKeW8j+/iNQqWdqLyCQEODkgV8pS34RlgKn/1apEmsQeE41bkAPSLahShMzFbBNVkAPAL4p03KMNldoPAAAAAElFTkSuQmCC">
<link rel="apple-touch-icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABwklEQVR4nM1Xq24CQRQ9O2mWh0Ig+IA14+saBKLZL6gkuKYKR8InNMFhWkuQ/QKCqCCtwq/hAxAIFMuuaQWZzey89kLZpUfNi3vOnLlzd/CgwK81ftSxayJNYk/usyrJTRzMNlGVCFY1uSrCuwW5DFa8pFzcXfKj++4ga389vePh4yXrr1ezs2KddQSCWCZJpjFqw4ZzzVUE3HcHWtBkGmdtWYRtvQmkHHAFk+2XsV7Nckd1sQAbuWx9bdjIuXGOCKcA185Vy9U+VcTNr6FVADWJKHC5QHYg4KE2NjpG6C3HGB0jbS6dH0hxCwUEPETAQ2yihUYOAJM6z/UF/H4T6fxQKMRaB+Qdt9odbb63HGfkQsDn46u27vv5LSdKhbUUt9odrFczBDzEfrfVHOjhZP2kzrPdqzkjdu/3m6ecMvAUHsEmWmATLbQcUK2X3RDkfr9p3LUM8sdIdUCQ2m5LEbGA1QFqKaXAdaX/byEC3C6oOWGqE0BxQSN9jm1BAh6i1e4YbwmFHCAegcuJ/W5rHKeW8j+/iNQqWdqLyCQEODkgV8pS34RlgKn/1apEmsQeE41bkAPSLahShMzFbBNVkAPAL4p03KMNldoPAAAAAElFTkSuQmCC">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%23060709'/><circle cx='16' cy='16' r='11' fill='none' stroke='%233a4468' stroke-width='1.2'/><line x1='16' y1='6' x2='16' y2='26' stroke='%233a4468' stroke-width='0.8'/><line x1='6' y1='16' x2='26' y2='16' stroke='%233a4468' stroke-width='0.8'/><polygon points='16,6 13,14 16,12 19,14' fill='%23ff9900'/><polygon points='16,26 13,18 16,20 19,18' fill='%232a3050'/><polygon points='26,16 18,13 20,16 18,19' fill='%2300aaff'/><polygon points='6,16 14,13 12,16 14,19' fill='%232a3050'/><circle cx='16' cy='16' r='2.5' fill='%237bffe0'/><circle cx='16' cy='16' r='1' fill='%23060709'/></svg>">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=DM+Mono:ital,wght@0,400;0,500&family=Syne:wght@400;600;700;800&display=swap" rel="stylesheet">
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<link rel="preload" href="data/agregations/aws_regions.json" as="fetch" crossorigin>
<link rel="preload" href="data/agregations/rds_regions.json" as="fetch" crossorigin>
<link rel="preload" href="data/agregations/azure_regions.json" as="fetch" crossorigin>
<link rel="preload" href="data/agregations/bdd_regions.json" as="fetch" crossorigin>
<link rel="preload" href="data/agregations/regions_meta.json" as="fetch" crossorigin>
<link rel="preload" href="data/carbon.json" as="fetch" crossorigin>
<link rel="preload" href="data/eur_rate.json" as="fetch" crossorigin>
<link rel="stylesheet" href="css/styles.css?v=%%FETCH_DATE%%">
</head>
<body>
<div id="topbar">
  <div id="topbarLeftGroup" style="display:flex;align-items:center;flex:1;min-width:0">
    <div id="topbarLogo" style="display:flex;align-items:center;flex-shrink:0;cursor:pointer" onclick="
      if(heatmapActive){setHeatmap();}
      if(veilleActive){setVeille();}
      if(tcoActive){setTco();}
      const _tn=document.getElementById('topbarNav'); if(_tn){_tn.style.opacity='1';_tn.style.pointerEvents='';}
      setNav('ec2');window.scrollTo(0,0);">
      <svg width="190" height="36" viewBox="0 0 190 36" style="flex-shrink:0">
        <circle cx="15" cy="18" r="11" fill="none" stroke="#3a4468" stroke-width="1.2"/>
        <line x1="15" y1="8" x2="15" y2="28" stroke="#3a4468" stroke-width="0.8"/>
        <line x1="5" y1="18" x2="25" y2="18" stroke="#3a4468" stroke-width="0.8"/>
        <polygon points="15,7 12,16 15,13.5 18,16" fill="#ff9900"/>
        <polygon points="15,29 12,20 15,22.5 18,20" fill="#2a3050"/>
        <polygon points="26,18 17,15 19.5,18 17,21" fill="#00aaff"/>
        <polygon points="4,18 13,15 10.5,18 13,21" fill="#2a3050"/>
        <circle cx="15" cy="18" r="2.5" fill="#7bffe0"/>
        <circle cx="15" cy="18" r="1" fill="#060709"/>
        <text x="33" y="23" font-family="'Syne',sans-serif" font-size="17" font-weight="800" fill="#ffffff" letter-spacing="-0.3">FinOps<tspan fill="#7bffe0">Map</tspan></text>
      </svg>
    </div>
    <div id="topbarLeft" style="display:flex;align-items:center;gap:12px;opacity:0;transition:opacity .2s ease">
      <span id="regionRuler"></span>
      <select class="region-select" id="regionSelect" onchange="onRegionChange(this.value)">
      <option value="eu-west-3">&#x1F1EB;&#x1F1F7; eu-west-3 &mdash; Paris</option>
      <option value="eu-west-1">&#x1F1EE;&#x1F1EA; eu-west-1 &mdash; Irlande</option>
      <option value="eu-central-1">&#x1F1E9;&#x1F1EA; eu-central-1 &mdash; Francfort</option>
      <option value="eu-west-2">&#x1F1EC;&#x1F1E7; eu-west-2 &mdash; Londres</option>
      <option value="eu-north-1">&#x1F1F8;&#x1F1EA; eu-north-1 &mdash; Su&egrave;de</option>
      <option value="eu-south-1">&#x1F1EE;&#x1F1F9; eu-south-1 &mdash; Milan</option>
      <option value="eu-south-2">&#x1F1EA;&#x1F1F8; eu-south-2 &mdash; Espagne</option>
      <option value="us-east-1">&#x1F1FA;&#x1F1F8; us-east-1 &mdash; Virginie</option>
    </select>
  </div>
  </div>
  <div class="nav-outer" id="topbarNav">
    <div class="nav-inline">
      <span class="nav-cloud-label aws">AWS</span>
      <div class="nav-group aws-group">
        <button class="nav-btn active-aws" id="btn-ec2" onclick="setNav(&apos;ec2&apos;)">EC2</button>
        <div class="nav-sep-aws"></div>
        <button class="nav-btn" id="btn-rds" onclick="setNav(&apos;rds&apos;)">RDS</button>
      </div>
    </div>
    <div class="nav-inline">
      <span class="nav-cloud-label az">Azure</span>
      <div class="nav-group az-group">
        <button class="nav-btn" id="btn-vm" onclick="setNav(&apos;azure&apos;)">VM</button>
        <div class="nav-sep-az"></div>
        <button class="nav-btn" id="btn-bdd" onclick="setNav(&apos;psql&apos;)">DB</button>
      </div>
    </div>
  </div>
  <div id="topbarActions" style="display:flex;gap:14px;align-items:center;flex:1;justify-content:flex-end">
    <button id="backBtn" onclick="goBack()" style="display:none;align-items:center;gap:6px;padding:6px 12px;background:transparent;border:1px solid #2a3050;border-radius:6px;color:#c8d0e8;font-family:'IBM Plex Mono',monospace;font-size:.72rem;cursor:pointer;transition:all .15s" onmouseenter="this.style.borderColor='#ff5566';this.style.color='#ff5566'" onmouseleave="this.style.borderColor='#2a3050';this.style.color='#c8d0e8'">&#x2190; Back</button>
    <button class="veille-btn" id="heatmapBtn" onclick="setHeatmap()"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;position:relative;top:-1px"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg><span class="tb-label">Heatmap regions</span></button>
    <button class="veille-btn" id="tcoBtn" onclick="setTco()"><span style="position:relative;top:-1px;margin-right:5px">∑</span><span class="tb-label">TCO</span></button>
    <button class="veille-btn" id="veilleBtn" onclick="setVeille()"><span style="position:relative;top:-1px">&#x25C8;</span><span class="tb-label"> Blog FinOps</span></button>
  </div>
</div>

<main>
<section id="hero">
  <div class="eyebrow" id="heroEyebrow"></div>
  <h1 id="heroTitle"></h1>
  <p class="hero-sub" id="heroSub">Chargement...</p>
</section>



<div id="filters">

  <div class="fgrp" id="famGrp">
    <div style="display:inline-flex;align-items:center;background:var(--s1);border:1px solid var(--b1);border-radius:6px;overflow:hidden;height:36px;flex-shrink:0">
      <span id="famLabel" style="padding:0 10px;background:var(--s2);font-family:'Syne',sans-serif;font-size:.78rem;font-weight:700;color:var(--text);border-right:1px solid var(--b1);height:100%;display:flex;align-items:center;white-space:nowrap">FAMILY</span>
      <select id="famSelect" onchange="setFamSel(this.value)" style="font-family:'Syne',sans-serif;font-size:.78rem;font-weight:700;color:#7bffe0;background:var(--s1);border:none;padding:0 28px 0 10px;height:100%;cursor:pointer;outline:none;appearance:none;-webkit-appearance:none;background-image:url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%237bffe0'/%3E%3C/svg%3E&quot;);background-repeat:no-repeat;background-position:right 8px center">
        <option value="all">All Families</option>
        <option value="general">General</option>
        <option value="burstable">Burstable</option>
        <option value="compute">CPU</option>
        <option value="memory">Memory</option>
        <option value="storage">Storage</option>
        <option value="gpu">GPU</option>
        <option value="other">Other</option>
      </select>
    </div>
  </div>
  <div style="display:inline-flex;align-items:center;background:var(--s1);border:1px solid var(--b1);border-radius:6px;overflow:hidden;height:36px;flex-shrink:0">
    <span style="padding:0 10px;background:var(--s2);font-family:'Syne',sans-serif;font-size:.78rem;font-weight:700;color:var(--text);border-right:1px solid var(--b1);height:100%;display:flex;align-items:center;white-space:nowrap">COST</span>
    <select id="periodSel" onchange="setPeriod(this.value)" style="font-family:'Syne',sans-serif;font-size:.78rem;font-weight:700;color:#7bffe0;background:var(--s1);border:none;border-right:1px solid var(--b1);padding:0 28px 0 10px;height:100%;cursor:pointer;outline:none;appearance:none;-webkit-appearance:none;background-image:url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%237bffe0'/%3E%3C/svg%3E&quot;);background-repeat:no-repeat;background-position:right 8px center">
      <option value="h">/ Hourly</option>
      <option value="d">/ Daily</option>
      <option value="m">/ Monthly</option>
    </select>
    <div style="position:relative;width:140px;height:100%;display:flex;align-items:center;padding:0 12px">
      <div style="position:absolute;left:12px;right:12px;height:4px;background:#2a3050;border-radius:2px"></div>
      <div id="priceSliderFill" style="position:absolute;left:12px;height:4px;background:#2a3050;border-radius:2px;pointer-events:none"></div>
      <div id="priceSliderThumb" style="position:absolute;width:12px;height:12px;background:#7bffe0;border-radius:50%;pointer-events:none;top:50%;transform:translate(-50%,-50%)"></div>
      <input type="range" id="priceSlider" min="0" max="100" step="1" value="100" oninput="onPriceSlider()" style="position:absolute;left:12px;right:12px;width:calc(100% - 24px);margin:0;opacity:0;cursor:pointer;height:36px">
    </div>
    <span id="priceSliderLbl" style="padding:0 12px;font-family:'IBM Plex Mono',monospace;font-size:.75rem;font-weight:700;color:#3a3f55;min-width:52px;border-left:1px solid var(--b1);height:100%;display:flex;align-items:center">any</span>
  </div>

  <div style="display:inline-flex;align-items:center;background:var(--s1);border:1px solid var(--b1);border-radius:6px;overflow:hidden;height:36px" id="riUpfrontToggle">
    <span style="padding:0 10px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;font-weight:700;color:#c8d0e8;border-right:1px solid var(--b1);height:100%;display:flex;align-items:center">RI</span>
    <select id="riSelect" onchange="onRiSelect(this.value)" style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;font-weight:700;color:#7bffe0;background:var(--s1);border:none;padding:0 24px 0 10px;height:100%;cursor:pointer;outline:none;appearance:none;-webkit-appearance:none;background-image:url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%237bffe0'/%3E%3C/svg%3E&quot;);background-repeat:no-repeat;background-position:right 8px center">
      <option value="1yr_no">1Y · No Upfront</option>
      <option value="1yr_all">1Y · All Upfront</option>
      <option value="3yr_no">3Y · No Upfront</option>
      <option value="3yr_all">3Y · All Upfront</option>
    </select>
  </div>
  <div class="curr-toggle">
    <button class="curr-btn on" id="btnUsd" onclick="setCurr(&apos;usd&apos;)">$ USD</button>
    <span style="width:1px;background:var(--b1)"></span>
    <button class="curr-btn" id="btnEur" onclick="setCurr(&apos;eur&apos;)">&#x20AC; EUR</button>
  </div>
  <div id="discountBtn" onclick="toggleDiscount()" onmouseenter="if(!discount){document.getElementById('discountLbl').style.color='var(--accent)'}" onmouseleave="if(!discount){document.getElementById('discountLbl').style.color='#c8d0e8'}" style="display:inline-flex;align-items:center;background:var(--s1);border:1px solid var(--b1);border-radius:6px;overflow:hidden;cursor:pointer;transition:border-color .2s,color .2s">
    <span id="discountLbl" style="padding:8px 15px;color:#c8d0e8;font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700;white-space:nowrap;transition:color .2s;display:flex;align-items:center;gap:7px">Discount EDP</span>
    <div id="discountFieldWrap" style="display:none;align-items:center;border-left:1px solid var(--b1);height:100%">
      <input type="number" id="discountInput" min="0" max="99" placeholder="%" oninput="setDiscountRate(this.value)" onclick="event.stopPropagation()" style="width:58px;padding:8px 10px;background:transparent;border:none;color:#7bffe0;font-family:'IBM Plex Mono',monospace;font-size:.82rem;font-weight:700;outline:none;text-align:center;-moz-appearance:textfield;appearance:textfield">
    </div>
  </div>
  <button class="reset-btn" onclick="resetFiltres()">&#x2715; Reset</button>

  <div style="display:flex;align-items:center;gap:8px;margin-left:auto">
  <div style="width:1px;height:20px;background:var(--b1)"></div>
  <div style="position:relative;flex-shrink:0" id="colPickerWrap">
    <button class="reset-btn" onclick="toggleColPicker()" id="colPickerBtn" style="display:flex;align-items:center;gap:6px">&#x229E; Columns</button>
    <div id="colPicker" style="display:none;position:absolute;top:calc(100% + 6px);right:0;background:var(--s1);border:1px solid var(--b1);border-radius:8px;padding:10px 14px;z-index:200;min-width:180px;box-shadow:0 8px 24px rgba(0,0,0,.6)">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:.65rem;letter-spacing:.12em;color:#6b738f;text-transform:uppercase;margin-bottom:8px">Columns</div>
      <label class="col-pick-row" style="padding-bottom:6px;margin-bottom:2px"><input type="checkbox" id="colSelectAll" checked onchange="toggleAllCols(this.checked)"> All columns</label>
      <label class="col-pick-row" style="border-bottom:1px solid var(--b1);padding-bottom:8px;margin-bottom:4px;cursor:pointer" onclick="setDefaultCols();return false;">&#x229E; Default columns</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-fam" checked onchange="toggleCol('fam',this.checked)"> Family</label>
      <label class="col-pick-row" id="cb-proc-row"><input type="checkbox" id="cb-proc" checked onchange="toggleCol('proc',this.checked)"> Processor</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-vcpu" checked onchange="toggleCol('vcpu',this.checked)"> vCPU</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-ram" checked onchange="toggleCol('ram',this.checked)"> RAM</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-pvcpu" checked onchange="toggleCol('pvcpu',this.checked)"> Cost/vCPU</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-price" checked onchange="toggleCol('price',this.checked)"> On Demand Cost</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-month" checked onchange="toggleCol('month',this.checked)"> Reserved Cost</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-savings" checked onchange="toggleCol('savings',this.checked)"> Savings RI</label>
      <label class="col-pick-row" id="cb-storage-row"><input type="checkbox" id="cb-storage" checked onchange="toggleCol('storage',this.checked)"> Storage</label>
      <label class="col-pick-row" id="cb-network-row"><input type="checkbox" id="cb-network" checked onchange="toggleCol('network',this.checked)"> Network</label>
      <label class="col-pick-row" id="cb-maxdisks-row"><input type="checkbox" id="cb-maxdisks" checked onchange="toggleCol('maxdisks',this.checked)"> Max Disks</label>
      <label class="col-pick-row" id="cb-diskiops-row"><input type="checkbox" id="cb-diskiops" checked onchange="toggleCol('diskiops',this.checked)"> Disk IOPS</label>
      <label class="col-pick-row" id="cb-spot-row"><input type="checkbox" id="cb-spot" checked onchange="toggleCol('spot',this.checked)"> Spot Cost</label>
      <label class="col-pick-row" id="cb-spotsav-row"><input type="checkbox" id="cb-spotsav" checked onchange="toggleCol('spotsav',this.checked)"> Savings Spot</label>
      <label class="col-pick-row"><input type="checkbox" id="cb-score" checked onchange="toggleCol('score',this.checked)"> FinOps Score</label>
    </div>
  </div>
  <button class="cmp-btn" id="cmpBtn" onclick="toggleCmp()">&#x229E; Compare <span class="cmp-count" id="cmpCount"></span></button>
  <button class="reset-btn" onclick="exportCSV()" style="border-color:var(--muted);color:#c8d0e8">&#x2193; Export CSV</button>
  </div>
</div>

<div id="tblwrap">
<div id="tableLoader" style="display:none;justify-content:center;align-items:center;padding:60px;flex-direction:column;gap:16px">
  <div style="width:32px;height:32px;border:2px solid #2a3050;border-top-color:#7bffe0;border-radius:50%;animation:spin .8s linear infinite"></div>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:#3a3f55;letter-spacing:.1em">LOADING PRICES...</span>
</div>
<div id="tblscroll">
  <table id="mainTable" class="view-aws">
    <thead>
    <tr id="sortRow">
      <th id="thCmp" style="width:28px;background:var(--s1);border-bottom:1px solid var(--b1);display:none"></th>
      <th class="col-iname" onclick="qs(&apos;iname&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">NAME <span class="sort-ico" id="si-iname">&#x2195;</span></div></th>
      <th class="col-fam" onclick="qs(&apos;fam&apos;)"><div style="display:flex;align-items:center;justify-content:space-between"><span id="famHeader">FAMILY</span> <span class="sort-ico" id="si-fam">&#x2195;</span></div></th>
      <th class="col-proc" onclick="qs(&apos;proc&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">PROCESSOR <span class="sort-ico" id="si-proc">&#x2195;</span></div></th>
      <th class="col-vcpu" onclick="qs(&apos;vcpu&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">VCPU <span class="sort-ico" id="si-vcpu">&#x2195;</span></div></th>
      <th class="col-ram" onclick="qs(&apos;ram&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">RAM <span class="sort-ico" id="si-ram">&#x2195;</span></div></th>
      <th class="col-storage ec2-only" onclick="qs(&apos;storage&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">STORAGE <span class="sort-ico" id="si-storage">&#x2195;</span></div></th>
      <th class="col-network" onclick="qs(&apos;network&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">NETWORK <span class="sort-ico" id="si-network">&#x2195;</span></div></th>
      <th class="col-maxdisks" onclick="qs(&apos;maxdisks&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">MAX DISKS <span class="sort-ico" id="si-maxdisks">&#x2195;</span></div></th>
      <th class="col-diskiops" onclick="qs(&apos;diskiops&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">DISK IOPS <span class="sort-ico" id="si-diskiops">&#x2195;</span></div></th>
      <th class="col-pvcpu" onclick="qs(&apos;pvcpu&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">COST/VCPU <span class="sort-ico" id="si-pvcpu">&#x2195;</span></div></th>
      <th class="col-price" onclick="qs(&apos;price&apos;)"><div style="display:flex;align-items:center;justify-content:space-between"><span id="thPriceOd" style="letter-spacing:.08em">ON DEMAND COST<span id="periodOdLabel" style="color:#7bffe0;font-size:.65rem;letter-spacing:0">/H</span><span id="discountBadgeHdr" style="display:none" class="discount-badge"></span></span> <span class="sort-ico active-ico" id="si-price">&#x2191;</span></div></th>
      <th class="col-month" onclick="qs(&apos;month&apos;)"><div style="display:flex;align-items:center;justify-content:space-between"><span style="letter-spacing:.08em">RESERVED COST<span id="periodRiLabel" style="color:#7bffe0;font-size:.65rem;letter-spacing:0">/H</span><span id="riYearLabel" style="font-size:.65rem;margin-left:9px;letter-spacing:0;font-family:'Syne',sans-serif;font-weight:700;color:#7bffe0;background:rgba(123,255,224,0.1);border:1px solid rgba(123,255,224,0.3);border-radius:4px;padding:1px 5px">1 YEAR</span></span> <span class="sort-ico" id="si-month">&#x2195;</span></div></th>
      <th class="col-savings" onclick="qs(&apos;savings&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">SAVINGS RI <span class="sort-ico" id="si-savings">&#x2195;</span></div></th>
      <th class="col-spot ec2-only" onclick="qs(&apos;spot&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">SPOT COST<span style="color:#7bffe0;font-size:.65rem;letter-spacing:0">/H</span> <span class="sort-ico" id="si-spot">&#x2195;</span></div></th>
      <th class="col-spotsav ec2-only" onclick="qs(&apos;spotsav&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">SAVINGS SPOT <span class="sort-ico" id="si-spotsav">&#x2195;</span></div></th>
      <th class="col-score" onclick="qs(&apos;score&apos;)"><div style="display:flex;align-items:center;justify-content:space-between">FINOPS SCORE <span class="sort-ico" id="si-score">&#x2195;</span></div></th>
    </tr>
    <tr id="filterRow">
      <th id="thCmpFilter" style="background:var(--s2);border-bottom:1px solid var(--b1);display:none"></th>
      <th class="col-iname"><input class="col-filter" oninput="render()" id="f-iname" placeholder="ex: m6i..."></th>
      <th class="col-fam"><input class="col-filter" oninput="render()" id="f-fam"   placeholder="ex: general..."></th>
      <th class="col-proc"><input class="col-filter" oninput="render()" id="f-proc"  placeholder="ex: Graviton"></th>
      <th class="col-vcpu"><input class="col-filter" oninput="render()" id="f-vcpu"  placeholder="ex: 4"></th>
      <th class="col-ram"><input class="col-filter" oninput="render()" id="f-ram"   placeholder="ex: 32"></th>
      <th class="col-storage ec2-only"><input class="col-filter" oninput="render()" id="f-storage" placeholder="ex: NVMe"></th>
      <th class="col-network"><input class="col-filter" oninput="render()" id="f-network" placeholder="ex: 25 Gbps"></th>
      <th class="col-maxdisks"></th>
      <th class="col-diskiops"></th>
      <th class="col-pvcpu"><input class="col-filter" oninput="render()" id="f-pvcpu" placeholder="ex: &lt;0.1"></th>
      <th class="col-price"><input class="col-filter" oninput="render()" id="f-price" placeholder="ex: &lt;0.5"></th>
      <th class="col-month"><input class="col-filter" oninput="render()" id="f-month" placeholder="ex: &lt;0.5"></th>
      <th class="col-savings"><input class="col-filter" oninput="render()" id="f-savings" placeholder="ex: &gt;30"></th>
      <th class="col-spot ec2-only"><input class="col-filter" oninput="render()" id="f-spot" placeholder="ex: &lt;0.1"></th>
      <th class="col-spotsav ec2-only"><input class="col-filter" oninput="render()" id="f-spotsav" placeholder="ex: &gt;50"></th>
      <th class="col-score"><input class="col-filter" oninput="render()" id="f-score"   placeholder="ex: &gt;7"></th>
    </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
</div>

<div class="cmp-sheet" id="cmpPanel">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:.7rem;letter-spacing:.15em;text-transform:uppercase;color:var(--accent)">&#x229E; Comparaison</span>
    <button onclick="clearCmp()" style="background:transparent;border:1px solid var(--muted);border-radius:4px;color:var(--muted);font-size:.72rem;padding:3px 8px;cursor:pointer;font-family:'Syne',sans-serif">&#x2715; Vider</button>
  </div>
  <div class="cmp-grid" id="cmpGrid"></div>
</div>

<div id="tcoSection" style="display:none;padding:32px 36px 44px;flex:1;min-height:calc(100vh - 64px)">
  <h2 style="font-size:clamp(1.4rem,2.5vw,2rem);font-weight:800;letter-spacing:-.04em;margin-bottom:4px;color:#c8d0e8"><span style="font-size:1.5rem;margin-right:8px;position:relative;top:-4px">∑</span>TCO Calculator</h2>
  <p style="font-family:'IBM Plex Mono',monospace;font-size:.82rem;color:#c8d0e8;margin-bottom:28px">Total Cost of Ownership</p>

  <div class="tco-layout">
    <!-- FORM -->
    <div>
      <div class="tco-panel">
        <div class="tco-panel-title">Workload</div>
        <div class="tco-field-row">
          <div>
            <label class="tco-label">vCPU</label>
            <select id="tcoCpu" class="tco-input" onchange="filterTcoInstances()">
              <option value="">Any</option>
            </select>
          </div>
          <div>
            <label class="tco-label">RAM (GiB)</label>
            <select id="tcoRam" class="tco-input" onchange="filterTcoInstances()">
              <option value="">Any</option>
            </select>
          </div>
        </div>
        <div class="tco-field">
          <label class="tco-label">Instance type</label>
          <select id="tcoInstance" class="tco-input" onchange="updateTcoCommitOptions()"><option value="">&#x2014; loading instances &#x2014;</option></select>
        </div>
        <div class="tco-field-row">
          <div>
            <label class="tco-label">Nb instances</label>
            <input type="number" id="tcoNbInst" class="tco-input" value="5" min="1">
          </div>
          <div>
            <label class="tco-label">Usage / month</label>
            <select id="tcoUsage" class="tco-input">
              <option value="730">730h (24/7)</option>
              <option value="480">480h (16h/day)</option>
              <option value="160">160h (work hrs)</option>
            </select>
          </div>
        </div>
        <div class="tco-field">
          <label class="tco-label">Commitment</label>
          <select id="tcoCommit" class="tco-input">
            <option value="od">On-Demand</option>
            <option value="ri1y" selected>Reserved 1yr No Upfront</option>
            <option value="ri1y_all">Reserved 1yr All Upfront</option>
            <option value="ri3y">Reserved 3yr No Upfront</option>
            <option value="ri3y_all">Reserved 3yr All Upfront</option>
          </select>
        </div>

        <hr class="tco-sep">
        <div class="tco-panel-title">Storage</div>
        <div class="tco-field-row">
          <div>
            <label class="tco-label">EBS / Managed Disk (GB)</label>
            <input type="number" id="tcoStorage" class="tco-input" value="200" min="0">
          </div>
          <div>
            <label class="tco-label">Disk type</label>
            <select id="tcoDiskType" class="tco-input"></select>
          </div>
        </div>


        <hr class="tco-sep">
        <div class="tco-panel-title">Duration</div>
        <div class="tco-dur-toggle">
          <div class="tco-dur-btn" onclick="tcoSetDur(1,this)">1 yr</div>
          <div class="tco-dur-btn on" onclick="tcoSetDur(2,this)">2 yr</div>
          <div class="tco-dur-btn" onclick="tcoSetDur(3,this)">3 yr</div>
        </div>
        <button class="tco-calc-btn" onclick="calcTco()">&#x2192; Calculate TCO</button>
      </div>
    </div>

    <!-- RESULTS -->
    <div class="tco-right" id="tcoResults">
      <div class="tco-empty">Configure your workload and click <strong style="color:#7bffe0">Calculate TCO</strong></div>
    </div>
  </div>
</div>

<div id="heatmapSection" style="display:none;padding:32px 36px 0;min-height:calc(100vh - 64px);display:none;flex-direction:column">
  <div class="veille-title" style="color:#c8d0e8"><svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:12px;position:relative;top:-3px"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Heatmap <em style="color:#c8d0e8">Regions</em></div>
  <div id="heatmapSub" style="margin-bottom:20px;font-family:'IBM Plex Mono',monospace;font-size:.9rem;color:#6b738f">AWS Regions \u2014 Linux On-Demand Cost</div>

  <div id="hmFilters" style="position:sticky;top:0;z-index:20;background:rgba(6,7,9,0.85);backdrop-filter:blur(16px);padding:10px 0 10px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-top:1px solid var(--b1);border-bottom:1px solid var(--b1)">
    <div id="hmFamGrp" style="display:flex;gap:4px;flex-wrap:wrap">
      <button class="fbtn on hm-ec2-fam hm-rds-fam hm-az-fam hm-bdd-fam" onclick="setHmFam('',this)">All</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('general',this)">General</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('compute',this)">CPU</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('memory',this)">Memory</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('burstable',this)">Burstable</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('storage',this)">Storage</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('gpu',this)">GPU</button>
      <button class="fbtn hm-ec2-fam hm-az-fam" onclick="setHmFam('other',this)">Other</button>
      <button class="fbtn hm-rds-fam hm-bdd-fam" style="display:none" onclick="setHmFam('mysql',this)">MySQL</button>
      <button class="fbtn hm-rds-fam hm-bdd-fam" style="display:none" onclick="setHmFam('postgresql',this)">PostgreSQL</button>
      <button class="fbtn hm-rds-fam" style="display:none" onclick="setHmFam('aurora-mysql',this)">Aurora MySQL</button>
      <button class="fbtn hm-rds-fam" style="display:none" onclick="setHmFam('aurora-pg',this)">Aurora PG</button>
      <button class="fbtn hm-rds-fam" style="display:none" onclick="setHmFam('mariadb',this)">MariaDB</button>
      <button class="fbtn hm-rds-fam" style="display:none" onclick="setHmFam('oracle',this)">Oracle</button>
      <button class="fbtn hm-rds-fam" style="display:none" onclick="setHmFam('sqlserver',this)">SQL Server</button>
      <button class="fbtn hm-bdd-only" style="display:none" onclick="setHmEngine('postgresql',this)">PostgreSQL</button>
      <button class="fbtn hm-bdd-only" style="display:none" onclick="setHmEngine('mysql',this)">MySQL</button>
      <button class="fbtn hm-bdd-only" style="display:none" onclick="setHmEngine('sqlserver',this)">SQL Server</button>
    </div>
    <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
      <div class="curr-toggle">
        <button class="curr-btn on" id="hmBtnUsd" onclick="setHmCurr('usd')">$ USD</button>
        <span style="width:1px;background:var(--b1)"></span>
        <button class="curr-btn" id="hmBtnEur" onclick="setHmCurr('eur')">&#x20AC; EUR</button>
      </div>
    </div>
  </div>

  <div style="display:flex;gap:16px;align-items:flex-start;position:relative">
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:16px">
      <div style="position:relative">
        <svg id="worldMapSvg" style="width:100%;display:block;border-radius:10px;border:1px solid var(--b1)"></svg>
        <div id="hmTooltip" style="display:none;position:absolute;background:#10131a;border:1px solid #2a3050;border-radius:8px;padding:10px 14px;font-family:IBM Plex Mono,monospace;font-size:.72rem;color:#ffffff;pointer-events:none;z-index:100;min-width:200px;box-shadow:0 8px 32px rgba(0,0,0,.6)"></div>
      </div>
      <table id="hmRegionTable" style="width:100%;table-layout:fixed;border-collapse:separate;border-spacing:0;border:1px solid var(--b1);border-radius:10px;overflow:hidden;margin-bottom:32px">
        <colgroup>
          <col style="width:11%">
          <col style="width:11%">
          <col style="width:28%">
          <col style="width:15%">
          <col style="width:15%">
          <col style="width:20%">
        </colgroup>
        <thead style="position:static">
          <tr>
            <th onclick="hmSort('label')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">Region Name <span class="sort-ico" id="hsi-label">&#x2195;</span></div></th>
            <th onclick="hmSort('reg')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">Region ID <span class="sort-ico" id="hsi-reg">&#x2195;</span></div></th>
            <th onclick="hmSort('avail')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">Available Instances <span class="sort-ico" id="hsi-avail">&#x2195;</span></div></th>
            <th onclick="hmSort('cost')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">Avg On-Demand /h <span class="sort-ico active-ico" id="hsi-cost">&#x2191;</span></div></th>
            <th onclick="hmSort('maxcost')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">Max Cost /h <span class="sort-ico" id="hsi-maxcost">&#x2195;</span></div></th>
            <th onclick="hmSort('carbon')" style="padding:10px 16px;background:var(--s2);font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;font-weight:700;border-bottom:1px solid var(--b1);position:static;cursor:pointer;user-select:none;text-align:left;overflow:hidden;white-space:nowrap"><div style="display:flex;align-items:center;justify-content:space-between">GREENOPS <span class="sort-ico" id="hsi-carbon">&#x2195;</span></div></th>
          </tr>
        </thead>
        <tbody id="hmRegionTableBody"></tbody>
      </table>
    </div>
    <div id="hmRegionPanel" style="min-width:360px;max-width:400px;display:flex;flex-direction:column;gap:6px;margin-top:24px"></div>
  </div>
</div>

<div id="veilleSection">
  <div class="veille-title" style="color:#c8d0e8"><span style="position:relative;top:-2px;font-size:70%">&#x25C8;</span> Blog <em style="color:#c8d0e8">FinOps</em></div>
  <div class="veille-sub" style="color:#c8d0e8">Latest articles</div>
  <div class="veille-filters" style="margin-top:28px">
    <button class="vsrc-btn on" onclick="veilleFilter('all',this)">ALL</button>
    <button class="vsrc-btn" onclick="veilleFilter('aws',this)">AWS FinOps</button>
    <button class="vsrc-btn" onclick="veilleFilter('azure',this)">Azure FinOps</button>
    <button class="vsrc-btn" onclick="veilleFilter('ff',this)">FinOps Foundation</button>
    <input id="veilleSearch" oninput="renderVeille()" placeholder="Search articles..." style="flex:1;max-width:220px;padding:4px 10px;background:#0d111a;border:1px solid #1e3050;border-radius:4px;color:#c8d0e8;font-size:.72rem;font-family:'IBM Plex Mono',monospace;outline:none">
  </div>
  <div class="v-grid" id="veilleGrid"></div>
</div>
</main>
<footer>
  <span style="font-size:.8rem;color:var(--text)">
    Sources : <a href="https://prices.azure.com/api/retail/prices" target="_blank" style="color:var(--text);text-decoration:none">Azure Retail Prices API</a> &mdash;
    <a href="https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/eu-west-3/index.json" target="_blank" style="color:var(--text);text-decoration:none">AWS Price List API</a>
  </span>
  <span class="fts" style="color:var(--text)"><a href="#" onclick="document.getElementById('aboutModal').style.display='flex';return false;" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--muted)">FinOpsMap · About me</a></span>
  <span class="fts" style="color:var(--text)">Updated %%FETCH_DATE%%</span>
</footer>

<div id="aboutModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9999;align-items:center;justify-content:center" onclick="if(event.target===this)this.style.display='none'">
  <div style="background:var(--s1);border:1px solid #2a3050;border-radius:10px;padding:32px 36px;max-width:480px;width:90%;position:relative">
    <button onclick="document.getElementById('aboutModal').style.display='none'" style="position:absolute;top:14px;right:14px;background:transparent;border:none;color:var(--muted);font-size:1.2rem;cursor:pointer">&#x2715;</button>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:.62rem;letter-spacing:.2em;text-transform:uppercase;color:#7bffe0;margin-bottom:12px">About me</div>
    <div style="font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:#dde3f0;margin-bottom:16px">FinOps<span style="color:#7bffe0">Map</span></div>
    <p style="font-size:.85rem;color:#c8d0e8;line-height:1.7;margin-bottom:12px"><em>I'm a FinOps engineer with hands-on experience optimizing cloud costs across AWS and Azure. I built FinOpsMap because comparing cloud pricing shouldn't require opening a dozen browser tabs — it should be instant, visual, and actionable.</em></p>
    <p style="font-size:.85rem;color:#c8d0e8;line-height:1.7;margin-bottom:12px"><em>This project is free and open-source. If it saves you time or money, consider supporting it.</em></p>
    <p style="font-size:.85rem;color:#c8d0e8;line-height:1.7;margin-bottom:12px"><em>Thank you for your support</em> &#x2665;</p>
    <div style="margin-bottom:16px;font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:var(--muted)">&#x2709; <a href="mailto:contact@finopsmap.com" style="color:#7bffe0;text-decoration:none;border-bottom:1px dotted #7bffe0">contact@finopsmap.com</a></div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
      <a href="https://www.linkedin.com/in/dorian" target="_blank" style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;padding:6px 14px;border:1px solid #3a4468;border-radius:4px;color:#c8d0e8;text-decoration:none">LinkedIn</a>
      <a href="https://github.com/doriancpl/finopsmap" target="_blank" style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;padding:6px 14px;border:1px solid #3a4468;border-radius:4px;color:#c8d0e8;text-decoration:none">GitHub</a>
      <a href="https://buymeacoffee.com/finopsmap" target="_blank" style="font-family:'IBM Plex Mono',monospace;font-size:.72rem;padding:6px 14px;border-radius:4px;color:#000;background:#FFDD00;text-decoration:none;font-weight:700">&#x2615; Buy me a coffee</a>
    </div>
  </div>
</div>

<script>
let AWS_DATA = [], AZURE_DATA = [], RDS_DATA = [], PSQL_DATA = [];
let AWS_ALL_REGIONS = {}, RDS_ALL_REGIONS = {}, AZURE_ALL_REGIONS = {}, BDD_ALL_REGIONS = {};
let REGIONS_META = {}, AZURE_REGIONS_META = {}, CARBON_DATA = {}, VEILLE_DATA = [];
let EUR_RATE = 0.92;
const DISK_REGIONS = %%DISK_REGIONS%%;
let currentRegion      = 'eu-west-3';
let currentAzureRegion = 'francecentral';

const FL_RDS = {'aurora-mysql':'Aurora MySQL','aurora-pg':'Aurora PG','mysql':'MySQL','postgresql':'PostgreSQL','oracle':'Oracle','sqlserver':'SQL Server','mariadb':'MariaDB','other':'Other'};
const FL = {general:'General',compute:'CPU',memory:'Memoire',burstable:'Burst',storage:'Stockage',gpu:'GPU',other:'Other'};
const FC_RDS = {'aurora-mysql':'fam-aurora','aurora-pg':'fam-aurora','mysql':'fam-mysql','postgresql':'fam-pg','oracle':'fam-oracle','sqlserver':'fam-sql','mariadb':'fam-mysql','other':'fam-other'};
const FC = {general:'fam-general',compute:'fam-compute',memory:'fam-memory',burstable:'fam-burstable',storage:'fam-storage',gpu:'fam-gpu',other:'fam-other'};

let view = 'aws';
let currentFam = 'all';
let fam  = 'all';
let discount = false;

const f4  = n => n == null ? '-' : (v => {
  const dec = v < 0.01 ? 4 : v < 1 ? 3 : v < 10 ? 3 : v < 1000 ? 2 : 0;
  return Number(v.toFixed(dec)).toLocaleString('fr-FR').replace(/\u00a0/g,'\u202f');
})((discount ? n * (1 - discountRate()) : n) * currRate());
const fmo = n => n == null ? '-' : Number(((discount ? n * (1 - discountRate()) : n) * 730).toFixed(0)).toLocaleString('fr-FR').replace(/\u00a0/g,'\u202f') + ' ' + currSym();
const ramFmt = r => r < 1 ? (r * 1024) + 'MB' : r + ' GiB';

let _curr = 'usd';
function currRate() { return _curr === 'eur' ? EUR_RATE : 1; }
function currSym()  { return _curr === 'eur' ? '\u20ac' : '$'; }

function setNav(v) {
  const map = { ec2:'btn-ec2', rds:'btn-rds', azure:'btn-vm', psql:'btn-bdd' };
  ['btn-ec2','btn-rds','btn-vm','btn-bdd'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'nav-btn';
  });
  const active = document.getElementById(map[v]);
  if (active) {
    active.className = 'nav-btn ' + (v === 'azure' || v === 'psql' ? 'active-azure' : 'active-aws');
  }
  setView(v === 'ec2' ? 'aws' : v);
  if (tcoActive) { initTcoInstanceSelect(); initTcoDiskSelect(); }
}

const AWS_REGION_OPTIONS = [
  {v:'eu-west-3',   l:'&#x1F1EB;&#x1F1F7; eu-west-3 \u2014 Paris'},
  {v:'eu-west-1',   l:'&#x1F1EE;&#x1F1EA; eu-west-1 \u2014 Irlande'},
  {v:'eu-central-1',l:'&#x1F1E9;&#x1F1EA; eu-central-1 \u2014 Francfort'},
  {v:'eu-west-2',   l:'&#x1F1EC;&#x1F1E7; eu-west-2 \u2014 Londres'},
  {v:'eu-north-1',  l:'&#x1F1F8;&#x1F1EA; eu-north-1 \u2014 Su\u00e8de'},
  {v:'eu-south-1',  l:'&#x1F1EE;&#x1F1F9; eu-south-1 \u2014 Milan'},
  {v:'eu-south-2',  l:'&#x1F1EA;&#x1F1F8; eu-south-2 \u2014 Espagne'},
  {v:'us-east-1',   l:'&#x1F1FA;&#x1F1F8; us-east-1 \u2014 Virginie'},
];
const AZURE_REGION_OPTIONS = [
  {v:'francecentral',      l:'&#x1F1EB;&#x1F1F7; francecentral \u2014 Paris'},
  {v:'northeurope',        l:'&#x1F1EE;&#x1F1EA; northeurope \u2014 Irlande'},
  {v:'westeurope',         l:'&#x1F1F3;&#x1F1F1; westeurope \u2014 Pays-Bas'},
  {v:'germanywestcentral', l:'&#x1F1E9;&#x1F1EA; germanywestcentral \u2014 Francfort'},
  {v:'uksouth',            l:'&#x1F1EC;&#x1F1E7; uksouth \u2014 Londres'},
  {v:'swedencentral',      l:'&#x1F1F8;&#x1F1EA; swedencentral \u2014 Su\u00e8de'},
  {v:'italynorth',         l:'&#x1F1EE;&#x1F1F9; italynorth \u2014 Milan'},
  {v:'eastus',             l:'&#x1F1FA;&#x1F1F8; eastus \u2014 Virginie'},
];

function adjustLayout() {
  var filters = document.getElementById('filters');
  var filtersH = filters ? filters.getBoundingClientRect().height : 0;
  document.documentElement.style.setProperty('--filters-h', filtersH + 'px');
}
window.addEventListener('resize', adjustLayout);

function adaptRegionWidth(sel) {
  const ruler = document.getElementById('regionRuler');
  if (!ruler || !sel) return;
  if (window.matchMedia('(max-width:1300px)').matches) {
    sel.style.width = '';
    return;
  }
  ruler.textContent = sel.options[sel.selectedIndex].text;
  sel.style.width = (ruler.offsetWidth + 48) + 'px';
}

function updateRegionSelector(isAzure) {
  const sel = document.getElementById('regionSelect');
  if (!sel) return;
  const opts = isAzure ? AZURE_REGION_OPTIONS : AWS_REGION_OPTIONS;
  const cur  = isAzure ? currentAzureRegion : currentRegion;
  sel.innerHTML = opts.map(o => '<option value="'+o.v+'"'+(o.v===cur?' selected':'')+'>'+o.l+'</option>').join('');
  adaptRegionWidth(sel);
}

function onRegionChange(val) {
  const sel = document.getElementById('regionSelect');
  adaptRegionWidth(sel);
  const isAzure = (view === 'azure' || view === 'psql');
  if (isAzure) setAzureRegion(val);
  else setRegion(val);
}

function loadRegionData(region) {
  currentRegion = region;
  const regionData = AWS_ALL_REGIONS[region];
  if (!regionData) return;
  AWS_DATA = regionData;
  const rdsData = RDS_ALL_REGIONS[region];
  if (rdsData) RDS_DATA = rdsData;
  window._gensBySerie = null; window._bestInGroup = null; window._recoSet = null; window._resvSet = null;
}

function loadAzureRegionData(region) {
  currentAzureRegion = region;
  const vmData  = AZURE_ALL_REGIONS[region];
  const bddData = BDD_ALL_REGIONS[region];
  if (vmData)  AZURE_DATA = vmData;
  if (bddData) PSQL_DATA  = bddData;
  window._gensBySerie = null; window._bestInGroup = null; window._recoSet = null; window._resvSet = null;
}

function setRegion(region) {
  loadRegionData(region);
  window._isViewChange = false;
  if (tcoActive) { initTcoInstanceSelect(); initTcoDiskSelect(); }
  if (view === 'aws' || view === 'rds') render();
}

function setAzureRegion(region) {
  loadAzureRegionData(region);
  window._isViewChange = false;
  if (tcoActive) { initTcoInstanceSelect(); initTcoDiskSelect(); }
  if (view === 'azure' || view === 'psql') render();
}

function setView(v) {
  window._gensBySerie = null; window._bestInGroup = null; window._recoSet = null; window._resvSet = null;
  view = v;
  window._isViewChange = true;
  window.scrollTo({top: 0, behavior: 'smooth'});
  clearCmp();
  const tb = document.getElementById('tbody');
  if (tb) { tb.style.opacity = '0'; tb.style.transform = 'translateY(6px)'; tb.style.transition = 'none'; }
  resetFiltres();
  const _isAz = v === 'azure' || v === 'psql';
  updateRegionSelector(_isAz);
  // Recharger les données pour la région courante (sans render)
  if (_isAz) { loadAzureRegionData(currentAzureRegion); }
  else       { loadRegionData(currentRegion); }
  const cfg = {
    aws:   {title:'<span style="color:#c8d0e8">Amazon EC2</span>',         color:'aws'},
    azure: {title:'<span style="color:#c8d0e8">Azure Virtual Machines</span>', color:'azure'},
    rds:   {title:'<span style="color:#c8d0e8">Amazon RDS</span>'},
    psql:  {title:'<span style="color:#c8d0e8">Azure Database</span>', color:'azure'},
  };
  document.getElementById('heroTitle').innerHTML     = cfg[v].title;
  updateDiscountLabel();
  const tbl = document.getElementById('mainTable');
  if (tbl) { tbl.classList.remove('view-aws','view-azure','view-rds','view-psql'); tbl.classList.add('view-'+v); }
  const isRds = v === 'rds';
  const famSel = document.getElementById('famSelect');
  const famLbl = document.getElementById('famLabel');
  if (famSel) {
    if (isRds) {
      if(famLbl) famLbl.textContent = 'ENGINE';
      famSel.innerHTML = '<option value="all">All Engines</option><option value="mysql">MySQL</option><option value="postgresql">PostgreSQL</option><option value="aurora-mysql">Aurora MySQL</option><option value="aurora-pg">Aurora PG</option><option value="mariadb">MariaDB</option><option value="oracle">Oracle</option><option value="sqlserver">SQL Server</option>';
    } else {
      if(famLbl) famLbl.textContent = 'FAMILY';
      famSel.innerHTML = '<option value="all">All Families</option><option value="general">General</option><option value="burstable">Burstable</option><option value="compute">CPU</option><option value="memory">Memory</option><option value="storage">Storage</option><option value="gpu">GPU</option><option value="other">Other</option>';
    }
    famSel.value = 'all';
  }
  const fh = document.getElementById('famHeader'); if(fh) fh.textContent = (isRds || view==='psql') ? 'ENGINE' : 'FAMILY';
  const upfrontToggle = document.getElementById('riUpfrontToggle');
  const riSel = document.getElementById('riSelect');
  if (upfrontToggle) upfrontToggle.style.display = 'inline-flex';
  if (riSel) {
    if (v === 'azure' || v === 'psql') {
      riSel.innerHTML = '<option value="1yr_all">1Y · All Upfront</option><option value="3yr_all">3Y · All Upfront</option>';
      riUpfront = 'all';
      riSel.value = riYear + '_all';
    } else {
      riSel.innerHTML = '<option value="1yr_no">1Y · No Upfront</option><option value="1yr_all">1Y · All Upfront</option><option value="3yr_no">3Y · No Upfront</option><option value="3yr_all">3Y · All Upfront</option>';
      riSel.value = riYear + '_' + riUpfront;
    }
  }
  if(fam !== 'all' || currentFam !== 'all'){ fam='all'; currentFam='all'; const fs=document.getElementById('famSelect'); if(fs) fs.value='all'; }
  const cbProcRow = document.getElementById('cb-proc-row');
  if (cbProcRow) cbProcRow.style.display = (v === 'psql') ? 'none' : '';
  const cbStorageRow = document.getElementById('cb-storage-row');
  if (cbStorageRow) cbStorageRow.style.display = (v === 'rds' || v === 'psql') ? 'none' : '';
  const cbNetworkRow = document.getElementById('cb-network-row');
  if (cbNetworkRow) cbNetworkRow.style.display = (v === 'azure' || v === 'psql') ? 'none' : '';
  if (v === 'azure' || v === 'psql') { toggleCol('network', false); const cb = document.getElementById('cb-network'); if (cb) cb.checked = false; }
  const cbMaxdisksRow = document.getElementById('cb-maxdisks-row');
  if (cbMaxdisksRow) cbMaxdisksRow.style.display = v === 'azure' ? '' : 'none';
  const cbDiskiopsRow = document.getElementById('cb-diskiops-row');
  if (cbDiskiopsRow) cbDiskiopsRow.style.display = v === 'azure' ? '' : 'none';
  const cbSpotRow = document.getElementById('cb-spot-row');
  if (cbSpotRow) cbSpotRow.style.display = v === 'aws' ? '' : 'none';
  const cbSpotsavRow = document.getElementById('cb-spotsav-row');
  if (cbSpotsavRow) cbSpotsavRow.style.display = v === 'aws' ? '' : 'none';
  render();
  // S'assurer que le toggle RI reste visible après render
  const ut2 = document.getElementById('riUpfrontToggle');
  if (ut2) ut2.style.display = 'inline-flex';
  if (tb) setTimeout(() => { tb.style.transition = 'opacity .2s, transform .2s'; tb.style.opacity = '1'; tb.style.transform = 'translateY(0)'; }, 30);
}

function getData() { return view === 'aws' ? AWS_DATA : view === 'rds' ? RDS_DATA : view === 'psql' ? PSQL_DATA : AZURE_DATA; }

function getColVal(id) { const el = document.getElementById(id); return el ? el.value.trim().toLowerCase() : ''; }

function matchNum(val, filter) {
  if (!filter) return true;
  const m = filter.match(/^([<>]=?)?([0-9]+[.]?[0-9]*)$/);
  if (!m) return String(val).includes(filter);
  const op = m[1] || '=', n = parseFloat(m[2]);
  if (op === '<')  return val < n;
  if (op === '<=') return val <= n;
  if (op === '>')  return val > n;
  if (op === '>=') return val >= n;
  return val === n;
}

function getFiltered() {
  if (cmpMode && cmpSel.size > 0) {
    return getData().filter(d => cmpSel.has(view==='rds' ? d.iname+'||'+(d.fam||'') : view==='psql' ? (d.fam||'')+'||'+d.iname : d.iname));
  }
  const q      = '';
  const fIname = getColVal('f-iname');
  const fFam   = getColVal('f-fam');
  const fVcpu  = getColVal('f-vcpu');
  const fRam   = getColVal('f-ram');
  const fPvcpu = getColVal('f-pvcpu');
  const fPrice = getColVal('f-price');
  const fMonth   = getColVal('f-month');
  const fSavings = getColVal('f-savings');
  const fProc    = getColVal('f-proc');
  const fStorage = getColVal('f-storage');
  const fNetwork = getColVal('f-network');
  const fSpot    = getColVal('f-spot');
  const fSpotsav = getColVal('f-spotsav');
  const fScore   = getColVal('f-score');
  const sliderPct = parseInt(document.getElementById('priceSlider').value);
  const priceSliderMax = sliderPct < 100 ? (getPricePercentile(sliderPct) / (PRICE_UNIT_MULT[period] || 1)) : null;
  buildSets();
  getData().forEach(d => { d.recoTag = _recoSet.has(d.iname); d.resvTag = _resvSet.has(d.iname); });
  let arr = getData().filter(d =>
    (fam === 'all' || d.fam === fam) &&
    (priceSliderMax === null || d.price <= priceSliderMax) &&
    (!q      || d.iname.toLowerCase().includes(q)) &&
    (!fIname || d.iname.toLowerCase().includes(fIname)) &&
    (!fFam   || d.fam.toLowerCase().includes(fFam) || (FL[d.fam]||'').toLowerCase().includes(fFam)) &&
    (!fProc  || (d.processor||'').toLowerCase().includes(fProc)) &&
    (!fVcpu  || matchNum(d.vcpu, fVcpu)) &&
    (!fRam   || matchNum(d.ram,  fRam)) &&
    (!fPvcpu || matchNum(d.vcpu > 0 ? d.price/d.vcpu : 0, fPvcpu)) &&
    (!fPrice || matchNum(d.price, fPrice)) &&
    (!fMonth || matchNum((d[getRiKey()]||0), fMonth)) &&
    (!fSavings || (() => { const rp = d[getRiKey()]; if (!rp) return false; return matchNum(Math.round((1-rp/d.price)*100), fSavings); })()) &&
    (!fStorage || (d.storage||'').toLowerCase().includes(fStorage)) &&
    (!fNetwork || (d.network||'').toLowerCase().includes(fNetwork)) &&
    (!fSpot    || matchNum((d.spot||0), fSpot)) &&
    (!fSpotsav || matchNum(d.spot ? Math.round((1-d.spot/d.price)*100) : 0, fSpotsav)) &&
    (!fScore   || matchNum(getScore(d).score, fScore))
  );
  return arr;
}

let sortVal = 'price-asc';
let cmpMode = false;
let cmpSel = new Set();

function getSorted(arr) {
  const s = sortVal;
  return [...arr].sort((a,b) => {
    if (s === 'price-asc')  return a.price - b.price;
    if (s === 'price-desc') return b.price - a.price;
    if (s === 'vcpu-asc')   return a.vcpu  - b.vcpu;
    if (s === 'vcpu-desc')  return b.vcpu  - a.vcpu;
    if (s === 'ram-asc')    return a.ram   - b.ram;
    if (s === 'ram-desc')   return b.ram   - a.ram;
    if (s === 'iname-asc')  return a.iname.localeCompare(b.iname);
    if (s === 'iname-desc') return b.iname.localeCompare(a.iname);
    if (s === 'fam-asc')    return (view==='psql'?(a.engine||a.fam):(a.fam)).localeCompare(view==='psql'?(b.engine||b.fam):(b.fam));
    if (s === 'fam-desc')   return (view==='psql'?(b.engine||b.fam):(b.fam)).localeCompare(view==='psql'?(a.engine||a.fam):(a.fam));
    if (s === 'proc-asc')   return (a.processor||'').localeCompare(b.processor||'');
    if (s === 'proc-desc')  return (b.processor||'').localeCompare(a.processor||'');
    if (s === 'pvcpu-asc')  return (a.vcpu > 0 ? a.price/a.vcpu : 0) - (b.vcpu > 0 ? b.price/b.vcpu : 0);
    if (s === 'pvcpu-desc') return (b.vcpu > 0 ? b.price/b.vcpu : 0) - (a.vcpu > 0 ? a.price/a.vcpu : 0);
    if (s === 'score-desc') return (b.score||0) - (a.score||0);
    if (s === 'score-asc')  return (a.score||0) - (b.score||0);
    if (s === 'savings-desc') { const sa = a[getRiKey()]; const sb = b[getRiKey()]; const ra = sa?Math.round((1-sa/a.price)*100):0; const rb = sb?Math.round((1-sb/b.price)*100):0; return rb-ra; }
    if (s === 'savings-asc')  { const sa = a[getRiKey()]; const sb = b[getRiKey()]; const ra = sa?Math.round((1-sa/a.price)*100):0; const rb = sb?Math.round((1-sb/b.price)*100):0; return ra-rb; }
    if (s === 'storage-asc')  return (a.storage||'').localeCompare(b.storage||'');
    if (s === 'storage-desc') return (b.storage||'').localeCompare(a.storage||'');
    if (s === 'network-asc')  return (a.network||'').localeCompare(b.network||'');
    if (s === 'network-desc') return (b.network||'').localeCompare(a.network||'');
    if (s === 'maxdisks-asc')  return (a.max_disks||0) - (b.max_disks||0);
    if (s === 'maxdisks-desc') return (b.max_disks||0) - (a.max_disks||0);
    if (s === 'diskiops-asc')  return (a.disk_iops||0) - (b.disk_iops||0);
    if (s === 'diskiops-desc') return (b.disk_iops||0) - (a.disk_iops||0);
    if (s === 'spot-asc')    return (a.spot||0) - (b.spot||0);
    if (s === 'spot-desc')   return (b.spot||0) - (a.spot||0);
    if (s === 'spotsav-asc')  { const ra = a.spot?Math.round((1-a.spot/a.price)*100):0; const rb = b.spot?Math.round((1-b.spot/b.price)*100):0; return ra-rb; }
    if (s === 'spotsav-desc') { const ra = a.spot?Math.round((1-a.spot/a.price)*100):0; const rb = b.spot?Math.round((1-b.spot/b.price)*100):0; return rb-ra; }
    return 0;
  });
}

function toggleCmp() {
  if (cmpSel.size === 0) return;
  cmpMode = !cmpMode;
  const btn = document.getElementById('cmpBtn');
  btn.classList.toggle('active', cmpMode);
  render();
}

function toggleRow(iname, fam) {
  const key = view==='rds' ? iname+'||'+(fam||'') : view==='psql' ? (fam||'')+'||'+iname : iname;
  if (cmpSel.has(key)) cmpSel.delete(key);
  else cmpSel.add(key);
  updateCmpCount();
  // Mise à jour ciblée : juste toggler la classe sur la ligne cliquée
  const selClass = (view==='azure' || view==='psql') ? 'row-sel-azure' : 'row-sel-aws';
  const tr = document.querySelector('tr[data-iname="'+iname+'"][data-fam="'+(fam||'')+'"]');
  if (tr) {
    if (cmpSel.has(key)) tr.className = selClass;
    else tr.className = '';
  }
  // render() uniquement si mode comparaison actif (filtre le tableau)
  if (cmpMode) render();
}

function updateCmpCount() {
  const el  = document.getElementById('cmpCount');
  const btn = document.getElementById('cmpBtn');
  el.style.display = cmpSel.size > 0 ? 'inline' : 'none';
  el.textContent = cmpSel.size;
  if (btn) btn.style.color = cmpSel.size > 0 ? 'var(--accent)' : '';
}

function updateCmpPanel() {
  const panel = document.getElementById('cmpPanel');
  if (cmpSel.size === 0) { panel.classList.remove('show'); return; }
  panel.classList.add('show');
  const items = getData().filter(d => cmpSel.has(view==='rds' ? d.iname+'||'+(d.fam||'') : view==='psql' ? (d.fam||'')+'||'+d.iname : d.iname));
  buildSets();
  items.forEach(d => { d.recoTag = _recoSet && _recoSet.has(d.iname); d.resvTag = _resvSet && _resvSet.has(d.iname); });
  const minP  = Math.min(...items.map(d => d.price));
  const color = (view === 'aws' || view === 'rds') ? '#ff9900' : '#00aaff';
  const bgC   = (view === 'aws' || view === 'rds') ? 'rgba(255,153,0,0.1)' : 'rgba(0,170,255,0.1)';
  const bdC   = (view === 'aws' || view === 'rds') ? 'rgba(255,153,0,0.3)' : 'rgba(0,170,255,0.3)';
  document.getElementById('cmpGrid').innerHTML = items.map(d => {
    const best = d.price === minP;
    const sc = getScore(d); const dScore = sc ? sc.score : 0;
    return '<div class="cmp-card' + (best ? ' best' : '') + '">'
      + (best ? '<div style="font-size:.58rem;color:var(--accent);letter-spacing:.1em;margin-bottom:6px">&#x2713; MOINS CHER</div>' : '')
      + '<div style="color:' + color + ';font-weight:700;font-size:.92rem;margin-bottom:6px;font-family:IBM Plex Mono,monospace">' + d.iname + '</div>'
      + '<div style="font-size:.8rem;color:#6b738f;margin-bottom:12px">' + ((view==='rds'?FL_RDS:FL)[d.fam]||d.fam) + ' · ' + d.vcpu + ' vCPU · ' + ramFmt(d.ram) + '</div>'
      + '<div style="display:inline-block;padding:5px 12px;background:' + bgC + ';border:1px solid ' + bdC + ';border-radius:6px;font-weight:700;font-size:.92rem;color:' + color + ';font-family:IBM Plex Mono,monospace">' + f4(d.price) + ' ' + currSym() + '/h</div>'
      + '<div style="margin-top:6px"><span style="padding:4px 8px;background:#10131a;border:1px solid #1c2030;border-radius:3px;font-size:.92rem;color:#dde3f0;font-family:IBM Plex Mono,monospace">' + fmo(d.price) + '/mois</span></div>'
      + '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #1c2030;display:flex;align-items:center;gap:8px">'
      + '<span style="font-size:.65rem;color:#6b738f;white-space:nowrap">Score</span>'
      + '<div class="score-bar-sm"><div class="score-fill-sm" style="width:'+(dScore/10*100).toFixed(1)+'%;background:linear-gradient(90deg,'+scoreGrad(dScore)+')"></div></div>'
      + '<span style="font-size:.82rem;font-weight:700;font-family:IBM Plex Mono,monospace;color:'+scoreColor(dScore)+'">'+dScore+'</span>'
      + ''
      + '</div>'
      + '</div>';
  }).join('');

}

function clearCmp() {
  cmpSel.clear(); cmpMode = false;
  const btn = document.getElementById('cmpBtn');
  if (btn) btn.classList.remove('active');
  updateCmpCount();
  const p = document.getElementById('cmpPanel');
  if (p) p.classList.remove('show');
  render();
}

function buildSets() {
  if (window._recoSet && window._resvSet) return;
  const all = getData();
  const byFam = {};
  all.forEach(d => { if(!byFam[d.fam]) byFam[d.fam]=[]; byFam[d.fam].push(d); });
  window._recoSet = new Set();
  Object.values(byFam).forEach(g => {
    const s=[...g].sort((a,b)=>(a.price/Math.max(a.vcpu,1))-(b.price/Math.max(b.vcpu,1)));
    s.slice(0,Math.max(1,Math.ceil(s.length*0.2))).forEach(d=>_recoSet.add(d.iname));
  });
  window._resvSet = new Set();
  Object.values(byFam).forEach(g => {
    const s=[...g].sort((a,b)=>a.price-b.price);
    s.slice(0,Math.max(1,Math.ceil(s.length*0.3))).forEach(d=>_resvSet.add(d.iname));
  });
}

  function getScore(d) {
    // Cache: générations triées par série
    if (!window._gensBySerie) {
      window._gensBySerie = {};
      getData().forEach(x => {
        let s, g;
        if (view === 'azure') {
          const n = x.iname.replace(/^Standard_/i,'');
          const ms = n.match(/^([A-Za-z]+?)(?=\\d)/);
          const mv = x.iname.match(/[\\s_]v(\\d+)/i);
          if (!ms) return;
          s = ms[1].toLowerCase();
          g = mv ? parseInt(mv[1]) : 0;
        } else {
          const m = x.iname.match(/^([a-z]+)(\\d)/);
          if (!m) return;
          s = m[1]; g = parseInt(m[2]);
        }
        if (!_gensBySerie[s]) _gensBySerie[s] = new Set();
        _gensBySerie[s].add(g);
      });
      Object.keys(_gensBySerie).forEach(s => { _gensBySerie[s]=[..._gensBySerie[s]].sort((a,b)=>b-a); });
    }
    // Extraire série et gen
    let serie, gen;
    if (view === 'azure') {
      const n = d.iname.replace(/^Standard_/i,'');
      const ms = n.match(/^([A-Za-z]+?)(?=\\d)/);
      const mv = d.iname.match(/[\\s_]v(\\d+)/i);
      serie = ms ? ms[1].toLowerCase() : '';
      gen   = mv ? parseInt(mv[1]) : 0;
    } else {
      const mp = d.iname.match(/^([a-z]+)(\\d)/);
      serie = mp ? mp[1] : '';
      gen   = mp ? parseInt(mp[2]) : 0;
    }
    const sorted = _gensBySerie[serie] || [gen];
    const rank   = sorted.indexOf(gen);
    const GEN_PTS = [3, 2.5, 1.5, 0.5];
    const genPts  = (view==='azure' && gen===0) ? 0 : (rank < GEN_PTS.length ? GEN_PTS[rank] : 0);
    // Cache bestInGroup
    if (!window._bestInGroup) {
      window._bestInGroup = {};
      const _g={};
      getData().forEach(x=>{const k=x.fam+'-'+x.vcpu+'-'+x.ram;if(!_g[k])_g[k]=[];_g[k].push(x);});
      Object.entries(_g).forEach(([k,g])=>{_bestInGroup[k]=Math.min(...g.map(x=>x.price));});
    }
    const k=d.fam+'-'+d.vcpu+'-'+d.ram;
    const best=_bestInGroup[k]||d.price;
    const prixPts=Math.round(4*(best/d.price)*10)/10;
    // Score RDS spécifique
    if (view === 'rds') {
      const gravPts = d.iname.match(/\\dg\./) ? 0.5 : 0;
      const total    = prixPts + gravPts + genPts;
      const score    = Math.min(10, Math.round(total/7.5*10*10)/10);
      return {score,prixPts,gravPts,genPts,total,gen,maxGen:sorted[0],isRds:true};
    }
    // Score EC2 / Azure
    // AWS Graviton: m7g.large etc. | Azure ARM: Dpsv5, Epsv6 etc. (contient 'p' dans la série)
    const isArm = (view==='azure' || view==='psql')
      ? /(?:\d+p|^[A-Za-z]+p[sbd])/i.test(d.iname.replace(/^Standard_/i,''))
      : !!d.iname.match(/\dg\./);
    const gravPts = isArm ? 1 : 0;
    const total=prixPts+gravPts+genPts;
    const score=Math.min(10,Math.round(total/8*10*10)/10);
    return {score,prixPts,gravPts,genPts,total,gen,maxGen:sorted[0],isRds:false,isArm};
  }
  function scoreGrad(s) { return s>=8?'#00e5a0,#7bffe0':s>=6?'#ff9900,#ffb400':s>=4?'#ff6400,#ff9900':'#ff3355,#ff5566'; }
  function scoreColor(s) { return s>=8?'#7bffe0':s>=6?'#ff9900':s>=4?'#ffb400':'#ff5566'; }

function showTip(e,idx) {
  const d=_tipData[idx]; if(!d) return;
  const sc=d.scoreDet||{};
  const col=scoreColor(d.score);
  const tip=document.getElementById('globalTip');
  const prixPts=sc.prixPts||0, gravPts=sc.gravPts||0, genPts=sc.genPts||0;
  const total=sc.total||0, gen=sc.gen||0;
  tip.innerHTML='<div style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:'+col+';margin-bottom:10px">Score FinOps</div>'
    +'<div class="tip-row"><span class="tip-lbl">Cost</span><span style="font-weight:700;color:#c8d0e8">'+prixPts+' / 4</span></div>'
    +(function(){ const lbl = (view==='azure'||view==='psql') ? 'Ampere (ARM)' : 'Graviton (ARM)'; return '<div class="tip-row"><span class="tip-lbl">'+lbl+'</span><span style="font-weight:700;color:#c8d0e8">'+gravPts+' / '+(sc.isRds?'0.5':'1')+'</span></div>'; })()
    +'<div class="tip-row"><span class="tip-lbl">Generation '+gen+'</span><span style="font-weight:700;color:#c8d0e8">'+genPts+' / 3</span></div>'
    +'<hr class="tip-sep">'
    +'<div class="tip-row"><span class="tip-lbl">Total</span><span style="font-weight:700;color:#dde3f0">'+total.toFixed(1)+' / '+(sc.isRds?'7.5':'8')+'</span></div>'
    +'<div class="tip-row"><span class="tip-lbl">Score final</span><span style="font-weight:700;color:'+col+'">'+d.score+' / 10</span></div>';
  tip.style.display='block'; moveTip(e);
}
function moveTip(e) {
  const tip=document.getElementById('globalTip');
  const w=240,h=230;
  let x=e.clientX+14, y=e.clientY-h-14;
  if(x+w>window.innerWidth) x=e.clientX-w-14;
  if(y<0) y=e.clientY+16;
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
function hideTip(){const t=document.getElementById('globalTip');if(t)t.style.display='none';}

window._tipData = [];

function openSeriesModal(iname, fam) {
  buildSets();
  const all = getData();
  const cur = all.find(d => d.iname === iname && (!fam || d.fam === fam));
  if (!cur) return;
  // Extraire série selon le cloud
  function getSerie(name) {
    if (view === 'azure') {
      const n = name.replace(/^Standard_/i,'');
      const m = n.match(/^([A-Za-z]+?)(?=\\d)/);
      return m ? m[1].toLowerCase() : '';
    } else {
      const m = name.match(/^([a-z]+)\\d/);
      return m ? m[1] : '';
    }
  }
  function getVersion(name) {
    if (view === 'azure') {
      const mv = name.match(/[\\s_]v(\\d+)/i);
      return mv ? parseInt(mv[1]) : 0;
    } else {
      const m = name.match(/[a-z]+(\\d)/);
      return m ? parseInt(m[1]) : 0;
    }
  }
  const serie = getSerie(iname);
  // Filtrer même série, même vcpu, même ram
  const items = all.filter(d => {
    if (view === 'rds') return d.fam === cur.fam && d.vcpu === cur.vcpu && Math.abs(d.ram - cur.ram) < 0.1;
    return getSerie(d.iname) === serie && d.vcpu === cur.vcpu && Math.abs(d.ram - cur.ram) < 0.1;
  }).sort((a,b) => view==='rds' ? a.price-b.price : getVersion(a.iname)-getVersion(b.iname));
  const curPrice = cur.price;
  const color = (view === 'aws' || view === 'rds') ? '#ff9900' : '#00aaff';
  const bgC   = (view === 'aws' || view === 'rds') ? 'rgba(255,153,0,0.1)' : 'rgba(0,170,255,0.1)';
  const bdC   = (view === 'aws' || view === 'rds') ? 'rgba(255,153,0,0.3)' : 'rgba(0,170,255,0.3)';
  document.getElementById('modalTabSerie').textContent = view==='rds' ? ('vs ' + (FL_RDS[cur.fam]||cur.fam) + ' \u2014 ' + cur.vcpu + ' vCPU \u2014 ' + ramFmt(cur.ram)) : view==='psql' ? ('vs ' + (cur.engine||cur.fam) + ' \u2014 ' + cur.vcpu + ' vCPU \u2014 ' + ramFmt(cur.ram)) : ('vs S\u00e9rie ' + serie + ' \u2014 ' + cur.vcpu + ' vCPU \u2014 ' + ramFmt(cur.ram));
  document.getElementById('seriesTable').innerHTML =
    (function(){
      let mSortCol = 'price', mSortDir = 'asc';
      const cols = [{k:'iname',l:'NAME'},{k:'fam',l:(view==='rds'||view==='psql'?'ENGINE':'FAMILY')},{k:'vcpu',l:'VCPU'},{k:'ram',l:'RAM'},{k:'price',l:'ON DEMAND COST'},{k:'month',l:'RESERVED COST'},{k:'score',l:'FINOPS SCORE'}];
      function mHead() {
        return '<thead><tr>' + cols.map(col => {
          const active = col.k === mSortCol || (col.k==='month' && mSortCol==='price');
          const ico = active ? (mSortDir==='asc'?'&#8593;':'&#8595;') : '&#8597;';
          return '<th style="padding:10px 14px;background:var(--bg);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#dde3f0;border-bottom:1px solid var(--b1);font-weight:700;text-align:left;cursor:pointer;user-select:none" onclick="mSort(\\''+col.k+'\\')">' + col.l + '<span style="font-size:.65rem;margin-left:5px;color:'+(active?'var(--accent)':'#3a3f55')+'">'+ico+'</span></th>';
        }).join('') + '</tr></thead>';
      }
      window.mSort = function(col) {
        if (col==='month') col='price';
        if (mSortCol===col) mSortDir=mSortDir==='asc'?'desc':'asc';
        else { mSortCol=col; mSortDir=col==='score'?'desc':'asc'; }
        document.getElementById('seriesTable').innerHTML = mHead() + mBody();
      };
      function mBody() {
        const sorted = [...items].sort((a,b) => {
          let va,vb;
          if(mSortCol==='iname'){va=a.iname;vb=b.iname;}
          else if(mSortCol==='fam'){va=a.fam;vb=b.fam;}
          else if(mSortCol==='score'){va=a._sc||0;vb=b._sc||0;}
          else if(mSortCol==='vcpu'){va=a.vcpu;vb=b.vcpu;}
          else if(mSortCol==='ram'){va=a.ram;vb=b.ram;}
          else{va=a.price;vb=b.price;}
          if(typeof va==='string') return mSortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va);
          return mSortDir==='asc'?va-vb:vb-va;
        });
        return '<tbody>' + sorted.sort((a,b) => {
          const aIsCur = view==='rds' ? (a.iname === iname && a.fam === cur.fam) : a.iname === iname;
          const bIsCur = view==='rds' ? (b.iname === iname && b.fam === cur.fam) : b.iname === iname;
          if (aIsCur) return -1;
          if (bIsCur) return 1;
          return 0;
        }).map((d,i) => {
          const isCur = view==='rds' ? (d.iname === iname && d.fam === cur.fam) : d.iname === iname;
          const diffPct = ((d.price - curPrice) / curPrice * 100);
          const diffHtml = isCur ? '' : (diffPct > 0 ? '<span class="diff-pos">+'+diffPct.toFixed(1)+'%</span>' : '<span class="diff-neg">'+diffPct.toFixed(1)+'%</span>');
          const sc = getScore(d); const dSc = sc ? sc.score : 0; d._sc = dSc;
          return '<tr class="'+(isCur?'current':'')+'" style="background:'+(i%2===0?'var(--bg)':'#0d0f15')+'">' 
            + '<td><div style="display:flex;align-items:center;gap:5px;white-space:nowrap"><span style="color:'+color+';font-weight:600;font-family:IBM Plex Mono,monospace">'+d.iname+'</span>'+'</div></td>'
            + '<td><span style="padding:4px 8px;background:var(--s2);border:1px solid var(--b1);border-radius:3px;font-size:.88rem;color:#dde3f0">'+(view==="psql"?(d.engine||d.fam):((view==="rds"?FL_RDS:FL)[d.fam]||d.fam))+'</span></td>'
            + '<td><span style="padding:3px 7px;background:var(--s2);border:1px solid var(--b1);border-radius:3px;font-size:.88rem;color:#dde3f0;font-family:IBM Plex Mono,monospace">'+d.vcpu+'</span></td>'
            + '<td><span style="padding:3px 7px;background:var(--s2);border:1px solid var(--b1);border-radius:3px;font-size:.88rem;color:#dde3f0;font-family:IBM Plex Mono,monospace">'+ramFmt(d.ram)+'</span></td>'
            + '<td><div style="display:flex;align-items:center;gap:6px;white-space:nowrap"><span style="display:inline-block;padding:4px 10px;background:'+bgC+';border:1px solid '+bdC+';border-radius:6px;font-weight:700;font-size:.88rem;color:'+color+';font-family:IBM Plex Mono,monospace">'+f4(d.price*(periodMult[period]||1))+' ' + currSym() + '</span>'+diffHtml+'</div></td>'
            + '<td>'+(function(){ const rp = d[getRiKey()]; return '<div style="display:flex;align-items:center;gap:6px;white-space:nowrap">' + (rp ? '<span class="ph-mo">'+f4(rp*(periodMult[period]||1))+' '+currSym()+'</span>' : '<span style="color:var(--muted);font-size:.75rem">—</span>') + '</div>'; })()+'</td>'
            + '<td><div style="display:inline-flex;align-items:center;gap:6px"><div class="score-bar-s"><div class="score-fill-s" style="width:'+(dSc/10*100).toFixed(1)+'%;background:linear-gradient(90deg,'+scoreGrad(dSc)+')"></div></div><span style="font-size:.82rem;font-weight:700;color:'+scoreColor(dSc)+';font-family:IBM Plex Mono,monospace">'+dSc+'</span></div></td>'
            + '</tr>';
        }).join('') + '</tbody>';
      }
      return mHead() + mBody();
    })()

  // Identity Card
  const hasProc = (view === 'aws' || view === 'azure') && cur.processor;
  const hasStor = (view === 'aws' || view === 'azure') && cur.storage;
  const famLabel = (view === 'rds' ? FL_RDS : view === 'psql' ? {[cur.fam]: cur.engine || cur.fam} : FL)[cur.fam] || cur.fam;
  function cardRow(label, val, extra) { return '<tr><td class="id-card-label">'+label+'</td><td class="id-card-value">'+val+(extra||'')+'</td></tr>'; }
  let cardHtml = '<table class="id-card">';
  cardHtml += cardRow('Instance Type', '<span style="color:'+color+';font-weight:700">'+cur.iname+'</span>');
  cardHtml += cardRow('Instance Family', famLabel);
  if (hasProc) cardHtml += cardRow('Processor', cur.processor);
  cardHtml += cardRow('vCPUs', cur.vcpu);
  cardHtml += cardRow('Memory', ramFmt(cur.ram));
  if (hasStor) cardHtml += cardRow('Storage', cur.storage);
  if (cur.network) cardHtml += cardRow('Network', cur.network);
  cardHtml += '</table>';
  document.getElementById('modalContentCard').innerHTML = cardHtml;

  // Mettre la bonne couleur sur les tabs selon la vue
  const isAzureView = view === 'azure' || view === 'psql';
  ['modalTabCard','modalTabSerie'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) { el.classList.remove('active-aws','active-az'); }
  });
  switchModalTab('card');
  document.getElementById('seriesModal').classList.add('show');
}
function closeSeriesModal(){document.getElementById('seriesModal').classList.remove('show');}
function switchModalTab(tab) {
  document.querySelectorAll('.modal-tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active-aws','active-az'));
  document.getElementById('modalContent' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add('active');
  const isAz = view === 'azure' || view === 'psql';
  document.getElementById('modalTab' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add(isAz ? 'active-az' : 'active-aws');
}

let riYear = '1yr';
let riUpfront = 'no';
let period = 'h';

function getRiKey() {
  const isAzure = view === 'azure' || view === 'psql';
  if (isAzure) {
    return riYear === '3yr' ? 'price_3yr' : 'price_1yr';
  }
  const suffix = riUpfront === 'all' ? '_all' : '';
  return riYear === '3yr' ? ('price_3yr' + suffix) : ('price_1yr' + suffix);
}

function onRiSelect(val) {
  const parts = val.split('_');
  riYear    = parts[0] === '3yr' ? '3yr' : '1yr';
  riUpfront = parts[1] === 'all' ? 'all' : 'no';
  const lbl = document.getElementById('riYearLabel');
  if (lbl) lbl.textContent = riYear === '3yr' ? '3 YEARS' : '1 YEAR';
  render();
}

function setRiYear(yr) {
  riYear = yr;
  const sel = document.getElementById('riSelect');
  if (sel) sel.value = riYear + '_' + riUpfront;
  const lbl = document.getElementById('riYearLabel');
  if (lbl) lbl.textContent = yr === '3yr' ? '3 YEARS' : '1 YEAR';
  render();
}

function setRiUpfront(u) {
  riUpfront = u;
  const sel = document.getElementById('riSelect');
  if (sel) sel.value = riYear + '_' + riUpfront;
  render();
}
const periodMult   = { h: 1, d: 24, m: 730 };
const periodLabels = { h: '/H', d: '/D', m: '/M' };

function setPeriod(p) {
  period = p;
  const lbl = periodLabels[p];
  const od = document.getElementById('periodOdLabel');
  const ri = document.getElementById('periodRiLabel');
  if (od) od.textContent = lbl;
  if (ri) ri.textContent = lbl;
  onPriceSlider();
}

function render() {
  let arr = getFiltered();
  const tbody = document.getElementById('tbody');
  if (window._isViewChange) { tbody.classList.remove('no-anim'); window._isViewChange = false; }
  else { tbody.classList.add('no-anim'); }
  // Calculer score
  arr = arr.map(d => { const sc=getScore(d); return {...d, score:sc.score, scoreDet:sc}; });
  arr = getSorted(arr);
  // Appliquer badges reco/resv selon boutons actifs

  const cls   = (view === 'aws' || view === 'rds') ? 'iname-aws' : 'iname-azure';
  const phcls = (view === 'aws' || view === 'rds') ? 'ph-aws' : 'ph-azure';

  window._tipData = [];
  document.getElementById('tbody').innerHTML = arr.length === 0
    ? '<tr><td colspan="6" style="text-align:center;padding:48px;color:var(--muted);font-family:IBM Plex Mono,monospace;font-size:.75rem">Aucune instance.</td></tr>'
    : arr.map((d,i) => {
      const _ti = _tipData.push(d) - 1;
      const isSel = cmpSel.has(view==='rds' ? d.iname+'||'+(d.fam||'') : view==='psql' ? (d.fam||'')+'||'+d.iname : d.iname);
      const chkTd = '';
      return '<tr class="' + (isSel?(view==='azure'||view==='psql'?'row-sel-azure':'row-sel-aws'):'') + '" data-iname="' + d.iname + '" data-fam="' + (d.fam||'') + '" style="animation-delay:' + Math.min(i*0.01,0.3) + 's;cursor:pointer" onclick="toggleRow(&apos;' + d.iname + '&apos;,&apos;' + (d.fam||'') + '&apos;)">' + chkTd
        + '<td class="col-iname"><span class="iname iname-clickable '+cls+'" onclick="event.stopPropagation();openSeriesModal(&apos;'+d.iname+'&apos;,&apos;'+(d.fam||'')+'&apos;)">'+d.iname+'</span>'
        + '<td class="col-fam"><span class="fam-badge '+(FC[d.fam]||'fam-other')+'">'+((view==='psql')?(d.engine||d.fam):(view==='rds'?FL_RDS:FL)[d.fam]||d.fam)+'</span></td>'
        + '<td class="col-proc"><span class="tag">'+(d.processor||'—')+'</span></td>'
        + '<td class="col-vcpu"><span class="tag">'+d.vcpu+'</span></td>'
        + '<td class="col-ram"><span class="tag">'+ramFmt(d.ram)+'</span></td>'
        + '<td class="col-storage ec2-only"><span class="tag">'+(d.storage||'—')+'</span></td>'
        + '<td class="col-network"><span class="tag" style="white-space:nowrap">'+(d.network||'—')+'</span></td>'
        + '<td class="col-maxdisks"><span class="tag">'+(d.max_disks ? d.max_disks : '—')+'</span></td>'
        + '<td class="col-diskiops"><span class="tag">'+(d.disk_iops ? d.disk_iops.toLocaleString() : '—')+'</span></td>'
        + '<td class="col-pvcpu"><span class="ph-mo">'+(d.vcpu > 0 ? f4(d.price/d.vcpu)+' '+currSym() : '—')+'</span></td>'
        + '<td class="col-price">'+((view==='aws'||view==='rds') ? '<span style="display:inline-block;padding:5px 12px;background:rgba(255,153,0,0.1);border:1px solid rgba(255,153,0,0.3);border-radius:6px;font-weight:700;font-size:.92rem;color:#ff9900;font-family:IBM Plex Mono,monospace">'+f4(d.price*(periodMult[period]||1))+' ' + currSym() + '</span>' : '<span style="display:inline-block;padding:5px 12px;background:rgba(0,170,255,0.1);border:1px solid rgba(0,170,255,0.3);border-radius:6px;font-weight:700;font-size:.92rem;color:#00aaff;font-family:IBM Plex Mono,monospace">'+f4(d.price*(periodMult[period]||1))+' ' + currSym() + '</span>')+'</td>'
        + '<td class="col-month"><span class="ph-mo">'+(function(){ const rp = d[getRiKey()]; if (!rp) return '<span style="color:var(--muted);font-size:.75rem">—</span>'; return f4(rp*(periodMult[period]||1))+' '+currSym(); })()+'</span></td>'
        + '<td class="col-savings">'+(function(){ const rp = d[getRiKey()]; if (!rp) return '<span style="color:var(--muted);font-size:.75rem">—</span>'; const sav = Math.round((1-rp/d.price)*100); return '<span style="padding:3px 8px;background:rgba(123,255,224,0.1);border:1px solid rgba(123,255,224,0.3);border-radius:4px;color:#7bffe0;font-weight:700;font-family:IBM Plex Mono,monospace;font-size:.82rem">\u2212'+sav+'%</span>'; })()+'</td>'
        + '<td class="col-spot ec2-only"><span class="ph-mo">'+(function(){ if (!d.spot) return '<span style="color:var(--muted);font-size:.75rem">—</span>'; return f4(d.spot*(currRate())*(periodMult[period]||1))+' '+currSym(); })()+'</span></td>'
        + '<td class="col-spotsav ec2-only">'+(function(){ if (!d.spot) return '<span style="color:var(--muted);font-size:.75rem">—</span>'; const sav = Math.round((1-d.spot/d.price)*100); return '<span style="padding:3px 8px;background:rgba(123,255,224,0.1);border:1px solid rgba(123,255,224,0.3);border-radius:4px;color:#7bffe0;font-weight:700;font-family:IBM Plex Mono,monospace;font-size:.82rem">\u2212'+sav+'%</span>'; })()+'</td>'
        + '<td class="col-score" style="padding:10px 16px;border-bottom:1px solid #1c2030;white-space:nowrap">'
        + '<div class="score-wrap" data-ti="'+_ti+'" onmouseenter="showTip(event,+this.dataset.ti)" onmousemove="moveTip(event)" onmouseleave="hideTip()">'
        + '<div style="position:relative;width:100px;height:8px;background:#1c2030;border-radius:4px;overflow:hidden">'
        + '<div style="position:absolute;left:0;top:0;height:100%;width:'+(d.score/10*100).toFixed(1)+'%;background:linear-gradient(90deg,'+scoreGrad(d.score)+');border-radius:4px"></div></div>'
        + '<span class="score-val" style="color:'+scoreColor(d.score)+'">'+d.score+'</span>'
        + ''
        + '</div>'
        + '</div></div></td>'
        + '</tr>';
      }).join('');

  document.getElementById('heroSub').innerHTML = '<span style="font-family:IBM Plex Mono,monospace;font-size:1.05rem;color:#dde3f0;font-weight:700">'+arr.length+'<span style="color:#dde3f0">/</span>'+getData().length+'</span><span style="color:#c8d0e8"> — resources displayed</span>';
  updateURL();
}

function discountRate() {
  const inp = document.getElementById('discountInput');
  return inp && inp.value ? parseFloat(inp.value) / 100 : 0;
}

function setDiscountRate(val) {
  const pct = Math.min(99, Math.max(0, parseFloat(val) || 0));
  discount = pct > 0;
  const btn = document.getElementById('discountBtn');
  const lbl = document.getElementById('discountLbl');
  if (btn) { btn.style.borderColor = discount ? 'var(--accent)' : 'var(--b1)'; }
  if (lbl) lbl.style.color = discount ? 'var(--accent)' : '#c8d0e8';
  const hdr = document.getElementById('discountBadgeHdr');
  if (hdr) { hdr.style.display = discount ? 'inline-block' : 'none'; hdr.textContent = '-'+pct+'%'; }
  render();
}

function toggleDiscount() {
  const wrap  = document.getElementById('discountFieldWrap');
  const btn   = document.getElementById('discountBtn');
  const lbl   = document.getElementById('discountLbl');
  const ico   = document.getElementById('discountIco');
  const input = document.getElementById('discountInput');
  const open  = wrap.style.display === 'flex';
  if (open) {
    wrap.style.display = 'none';
    ico.innerHTML = '&#9658;';
    ico.style.color = '#3a3f55';
    btn.style.borderColor = 'var(--b1)';
    lbl.style.color = '#c8d0e8';
    if (input) input.value = '';
    discount = false;
    render();
  } else {
    wrap.style.display = 'flex';
    ico.innerHTML = '&#9668;';
    ico.style.color = '#7bffe0';
    btn.style.borderColor = 'var(--accent)';
    lbl.style.color = '#7bffe0';
    setTimeout(() => { if (input) input.focus(); }, 30);
  }
}

function updateDiscountLabel() {}


function exportCSV() {
  const arr = getSorted(getFiltered());
  const isRds = view === 'rds' || view === 'psql';
  const disc = discount ? (1 - discountRate()) : 1;
  const rateLabel = riYear === '3yr' ? '3yr' : '1yr';
  const famCol = isRds ? 'Engine' : 'Family';
  const headers = isRds
    ? ['Instance', famCol, 'vCPU', 'RAM (GiB)', 'On-Demand /h ($)', 'On-Demand /mo ($)', 'Reserved '+rateLabel+' /h ($)', 'Reserved '+rateLabel+' /mo ($)', 'Savings RI', 'Discounted /h ($)', 'Discounted /mo ($)']
    : ['Instance', famCol, 'vCPU', 'RAM (GiB)', 'On-Demand /h ($)', 'On-Demand /mo ($)', 'Reserved '+rateLabel+' /h ($)', 'Reserved '+rateLabel+' /mo ($)', 'Savings RI', 'Discounted /h ($)', 'Discounted /mo ($)'];
  const rows = arr.map(d => {
    const fam  = isRds ? (d.engine||'') : (FL[d.fam]||d.fam);
    const rp   = d[getRiKey()];
    const sav  = rp ? Math.round((1 - rp/d.price)*100)+'%' : '';
    const dph  = (d.price * disc).toFixed(4);
    const dmo  = (d.price * disc * 730).toFixed(2);
    return [
      d.iname, fam, d.vcpu, d.ram,
      d.price.toFixed(4), (d.price*730).toFixed(2),
      rp ? rp.toFixed(4) : '', rp ? (rp*730).toFixed(2) : '',
      sav,
      discount ? dph : '', discount ? dmo : ''
    ];
  });
  const csv = [headers, ...rows].map(r => r.map(v => '"'+String(v).replace(/"/g,'""')+'"').join(',')).join(String.fromCharCode(13,10));
  const blob = new Blob(['\uFEFF'+csv], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'finopsmap_'+view+'_'+new Date().toISOString().slice(0,10)+'.csv';
  a.click(); URL.revokeObjectURL(url);
}

function setAzureSub(e, sub) {
  if (e) e.stopPropagation();
  setView(sub === 'psql' ? 'psql' : 'azure');
}

function setCurr(c) {
  _curr = c;
  document.getElementById('btnUsd').className = 'curr-btn' + (c==='usd'?' on':'');
  document.getElementById('btnEur').className = 'curr-btn' + (c==='eur'?' on':'');
  render();
}

function toggleColPicker() {
  const p = document.getElementById('colPicker');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
}
document.addEventListener('click', function(e) {
  const wrap = document.getElementById('colPickerWrap');
  if (wrap && !wrap.contains(e.target)) document.getElementById('colPicker').style.display = 'none';
});
const COL_KEYS = ['fam','proc','vcpu','ram','storage','network','maxdisks','diskiops','pvcpu','price','month','savings','spot','spotsav','score'];
const DEFAULT_HIDDEN_COLS = ['proc','storage','network','maxdisks','diskiops','spot','spotsav'];
function setDefaultCols() {
  const tbl = document.getElementById('mainTable');
  COL_KEYS.forEach(col => {
    const hide = DEFAULT_HIDDEN_COLS.includes(col);
    if (tbl) tbl.classList.toggle('hide-' + col, hide);
    const cb = document.getElementById('cb-' + col);
    if (cb) cb.checked = !hide;
  });
  const sa = document.getElementById('colSelectAll');
  if (sa) sa.checked = false;
  updateURL();
}
function toggleAllCols(visible) {
  COL_KEYS.forEach(col => {
    const tbl = document.getElementById('mainTable');
    if (tbl) tbl.classList.toggle('hide-' + col, !visible);
    const cb = document.getElementById('cb-' + col);
    if (cb) cb.checked = visible;
  });
}
function toggleCol(col, visible) {
  const tbl = document.getElementById('mainTable');
  if (!tbl) return;
  tbl.classList.toggle('hide-' + col, !visible);
  const allChecked = COL_KEYS.every(k => !tbl.classList.contains('hide-' + k));
  const sa = document.getElementById('colSelectAll');
  if (sa) sa.checked = allChecked;
  updateURL();
}
function updateURL() {
  if (!window._dataLoaded) return;
  const params = new URLSearchParams();
  if (view !== 'aws')           params.set('view', view);
  if (currentRegion !== 'eu-west-3') params.set('region', currentRegion);
  if (fam && fam !== 'all')     params.set('fam', fam);
  if (period !== 'h')           params.set('period', period);
  if (_curr !== 'usd')          params.set('curr', _curr);
  const riKey = riYear + '_' + riUpfront;
  if (riKey !== '1yr_no')       params.set('ri', riKey);
  if (sortVal !== 'price-asc')  params.set('sort', sortVal);
  const tbl = document.getElementById('mainTable');
  if (tbl) {
    const hidden = COL_KEYS.filter(k => tbl.classList.contains('hide-' + k));
    if (hidden.length) params.set('cols', hidden.join(','));
  }
  const str = params.toString();
  history.replaceState(null, '', str ? '?' + str : location.pathname);
}
function loadFromURL() {
  const p = new URLSearchParams(location.search);
  const reg = p.get('region');
  if (reg) {
    currentRegion = reg;
    const sel = document.getElementById('regionSelect');
    if (sel) sel.value = reg;
    loadRegionData(reg);
  }
  const ri = p.get('ri'); if (ri) onRiSelect(ri);
  const per = p.get('period'); if (per) { period = per; document.getElementById('periodSel').value = per; }
  const c = p.get('curr'); if (c) setCurr(c);
  const f = p.get('fam'); if (f) { fam = f; const fs = document.getElementById('famSelect'); if(fs) fs.value = f; }
  const s = p.get('sort'); if (s) sortVal = s;
  const cols = p.get('cols');
  if (cols) cols.split(',').forEach(col => {
    if (COL_KEYS.includes(col)) {
      const tbl = document.getElementById('mainTable');
      if (tbl) tbl.classList.add('hide-' + col);
      const cb = document.getElementById('cb-' + col); if (cb) cb.checked = false;
      const sa = document.getElementById('colSelectAll'); if (sa) sa.checked = false;
    }
  });
  setNav(p.get('view') || 'ec2');
}
function resetFiltres() {
  // Reset famille
  fam = 'all'; currentFam = 'all';
  const famSelR = document.getElementById('famSelect'); if(famSelR) famSelR.value = 'all';
  // Reset filtres colonnes
  ['f-iname','f-fam','f-proc','f-vcpu','f-ram','f-price','f-month','f-savings','f-pvcpu','f-score'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  discount = false;
  const discInput = document.getElementById('discountInput');
  const discBtn   = document.getElementById('discountBtn');
  const discLbl   = document.getElementById('discountLbl');
  const discWrap  = document.getElementById('discountFieldWrap');
  const discIco   = document.getElementById('discountIco');
  if (discInput) discInput.value = '';
  if (discBtn)   discBtn.style.borderColor = 'var(--b1)';
  if (discWrap)  discWrap.style.display = 'none';
  if (discIco)   { discIco.innerHTML = '&#9658;'; discIco.style.color = '#3a3f55'; }
  if (discLbl)   discLbl.style.color = '#c8d0e8';
  updateDiscountLabel();
  resetPriceSlider();
  // Désactiver comparaison
  cmpMode = false;
  const cmpBtn = document.getElementById('cmpBtn');
  if (cmpBtn) cmpBtn.classList.remove('active');
  const thCmp = document.getElementById('thCmp');
  if (thCmp) thCmp.style.display = 'none';
  const thCmpFilter = document.getElementById('thCmpFilter');
  if (thCmpFilter) thCmpFilter.style.display = 'none';
  clearCmp();
  render();
}

let priceUnit = 'h';
const PRICE_UNIT_MULT = { h: 1, d: 24, m: 730 };
const PRICE_UNIT_MAX  = { h: 20, d: 200, m: 5000 };

function getPricePercentile(pct) {
  const mult = PRICE_UNIT_MULT[period] || 1;
  const prices = getData().map(d => d.price * mult).filter(p => p > 0).sort((a,b) => a-b);
  if (!prices.length) return 0;
  if (pct >= 100) return prices[prices.length - 1];
  const idx = pct / 100 * (prices.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return prices[lo] + (prices[hi] - prices[lo]) * (idx - lo);
}

function setPriceUnit(u) {
  priceUnit = u;
  onPriceSlider();
}

function onPriceSlider() {
  const v = parseInt(document.getElementById('priceSlider').value);
  const sel = document.getElementById('periodSel');
  const unit = sel ? sel.value : 'h';
  const trackW = 140 - 24;
  const fillW = v / 100 * trackW;
  document.getElementById('priceSliderFill').style.width = fillW + 'px';
  document.getElementById('priceSliderThumb').style.left = 'calc(12px + ' + fillW + 'px)';
  const active = v < 100;
  document.getElementById('priceSliderFill').style.background = active ? '#7bffe0' : '#2a3050';
  const lbl = document.getElementById('priceSliderLbl');
  if (active) {
    const priceVal = getPricePercentile(v);
    lbl.textContent = '$' + priceVal.toFixed(unit === 'h' ? 3 : unit === 'd' ? 1 : 0);
    lbl.style.color = '#7bffe0';
  } else {
    lbl.textContent = 'any';
    lbl.style.color = '#3a3f55';
  }
  render();
}

function resetPriceSlider() {
  document.getElementById('priceSlider').value = 100;
  onPriceSlider();
}

function setFamSel(v) {
  fam = v;
  render();
}

function qs(col) {
  const cur = sortVal;
  const next = {
    score: cur === 'score-desc' ? 'score-asc'  : 'score-desc',
    iname: cur === 'iname-asc' ? 'iname-desc' : 'iname-asc',
    fam:   cur === 'fam-asc'   ? 'fam-desc'   : 'fam-asc',
    proc:  cur === 'proc-asc'  ? 'proc-desc'  : 'proc-asc',
    vcpu:  cur === 'vcpu-asc'  ? 'vcpu-desc'  : 'vcpu-asc',
    ram:   cur === 'ram-asc'   ? 'ram-desc'   : 'ram-asc',
    price: cur === 'price-asc' ? 'price-desc' : 'price-asc',
    pvcpu: cur === 'pvcpu-asc' ? 'pvcpu-desc' : 'pvcpu-asc',
    month:   cur === 'month-asc'   ? 'month-desc'   : 'month-asc',
    savings: cur === 'savings-desc' ? 'savings-asc' : 'savings-desc',
    storage: cur === 'storage-asc' ? 'storage-desc' : 'storage-asc',
    spot:    cur === 'spot-asc'    ? 'spot-desc'    : 'spot-asc',
    spotsav: cur === 'spotsav-desc' ? 'spotsav-asc' : 'spotsav-desc',
    maxdisks: cur === 'maxdisks-asc' ? 'maxdisks-desc' : 'maxdisks-asc',
    diskiops: cur === 'diskiops-asc' ? 'diskiops-desc' : 'diskiops-asc',
  };
  if (next[col]) sortVal = next[col];
  const colMap = {iname:'iname',fam:'fam',proc:'proc',vcpu:'vcpu',ram:'ram',pvcpu:'pvcpu',price:'price',month:'month',savings:'savings',storage:'storage',spot:'spot',spotsav:'spotsav',score:'score',maxdisks:'maxdisks',diskiops:'diskiops'};
  ['iname','fam','proc','vcpu','ram','pvcpu','price','month','savings','storage','spot','spotsav','score','maxdisks','diskiops'].forEach(k => {
    const el = document.getElementById('si-'+k);
    if (!el) return;
    const active = sortVal.startsWith(colMap[k]);
    el.style.color = active ? '#7bffe0' : '#3a3f55';
    el.innerHTML   = active ? (sortVal.endsWith('-asc') ? '&#x2191;' : '&#x2193;') : '&#x2195;';
  });
  render();
}

let veilleActive  = false;
let heatmapActive = false;
let tcoActive     = false;
let tcoDurYears   = 2;
let hmSortCol = 'cost';
let hmSortDir = 'asc';

function hmSort(col) {
  if (hmSortCol === col) { hmSortDir = hmSortDir === 'asc' ? 'desc' : 'asc'; }
  else { hmSortCol = col; hmSortDir = col === 'label' || col === 'reg' ? 'asc' : 'asc'; }
  ['label','reg','avail','cost','maxcost'].forEach(k => {
    const el = document.getElementById('hsi-' + k);
    if (!el) return;
    const active = hmSortCol === k;
    el.style.color = active ? '#7bffe0' : '#3a3f55';
    el.innerHTML   = active ? (hmSortDir === 'asc' ? '&#x2191;' : '&#x2193;') : '&#x2195;';
    el.className   = active ? 'sort-ico active-ico' : 'sort-ico';
  });
  renderHeatmap();
}

function setTco() {
  if (veilleActive) {
    veilleActive = false;
    document.getElementById('veilleBtn').classList.remove('active');
    const vs = document.getElementById('veilleSection');
    if (vs) vs.style.display = 'none';
  }
  if (heatmapActive) {
    heatmapActive = false;
    document.getElementById('heatmapBtn').classList.remove('active');
    const hs = document.getElementById('heatmapSection');
    if (hs) hs.style.display = 'none';
  }
  tcoActive = !tcoActive;
  const btn     = document.getElementById('tcoBtn');
  const main    = document.getElementById('hero');
  const filters = document.getElementById('filters');
  const tblwrap = document.getElementById('tblwrap');
  const statsrow= document.getElementById('statsrow');
  const topLeft = document.getElementById('topbarLeft');
  const topNav  = document.getElementById('topbarNav');
  btn.classList.toggle('active', tcoActive);
  const ts = document.getElementById('tcoSection');
  if (tcoActive) {
    if (main)     main.style.display     = 'none';
    if (filters)  filters.style.display  = 'none';
    if (tblwrap)  tblwrap.style.display  = 'none';
    if (statsrow) statsrow.style.display = 'none';
    if (topLeft)  { topLeft.style.opacity = '1'; topLeft.style.pointerEvents = ''; }
    if (topNav)   { topNav.style.opacity  = '1'; topNav.style.pointerEvents  = ''; }
    if (ts) ts.style.display = 'block';
    initTcoInstanceSelect();
    initTcoDiskSelect();
    showBackBtn(true);
  } else {
    if (main)     main.style.display     = '';
    if (filters)  filters.style.display  = '';
    if (tblwrap)  tblwrap.style.display  = '';
    if (statsrow) statsrow.style.display = '';
    if (topLeft)  { topLeft.style.opacity = '1'; topLeft.style.pointerEvents = ''; }
    if (topNav)   { topNav.style.opacity  = '1'; topNav.style.pointerEvents  = ''; }
    if (ts) ts.style.display = 'none';
    showBackBtn(false);
  }
}

function tcoSetDur(val, el) {
  tcoDurYears = val;
  document.querySelectorAll('.tco-dur-btn').forEach(function(b){ b.classList.remove('on'); });
  el.classList.add('on');
}

function getTcoData() { return view === 'aws' ? AWS_DATA : view === 'rds' ? RDS_DATA : view === 'psql' ? PSQL_DATA : AZURE_DATA; }
function initTcoInstanceSelect() {
  const cpuSel  = document.getElementById('tcoCpu');
  const ramSel  = document.getElementById('tcoRam');
  if (!cpuSel || !ramSel) return;

  const prevCpu = cpuSel.value;
  const prevRam = ramSel.value;

  // CPU uniques triés
  const cpuVals = getTcoData().map(function(d){ return d.vcpu; })
    .filter(function(v,i,a){ return a.indexOf(v)===i; })
    .sort(function(a,b){ return a-b; });
  cpuSel.innerHTML = '<option value="">Any vCPU</option>';
  cpuVals.forEach(function(v){
    const o = document.createElement('option');
    o.value = v; o.textContent = v + ' vCPU';
    if (String(v) === prevCpu) o.selected = true;
    cpuSel.appendChild(o);
  });

  // RAM uniques triés
  const ramVals = getTcoData().map(function(d){ return d.ram; })
    .filter(function(v,i,a){ return a.indexOf(v)===i; })
    .sort(function(a,b){ return a-b; });
  ramSel.innerHTML = '<option value="">Any RAM</option>';
  ramVals.forEach(function(v){
    const o = document.createElement('option');
    o.value = v;
    o.textContent = v >= 1024 ? (v/1024).toFixed(0)+' TiB' : v+' GiB';
    if (String(v) === prevRam) o.selected = true;
    ramSel.appendChild(o);
  });

  filterTcoInstances();
}

// Correspondance Azure par type EBS
const AZ_DISK_MAP = {
  gp3:      { name:'Premium SSD LRS',   price_gb: 0.115 },
  gp2:      { name:'Standard SSD LRS',  price_gb: 0.094 },
  io1:      { name:'Ultra Disk',        price_gb: 0.125 },
  io2:      { name:'Ultra Disk',        price_gb: 0.125 },
  st1:      { name:'Standard HDD LRS',  price_gb: 0.043 },
  sc1:      { name:'Standard HDD LRS',  price_gb: 0.043 },
  standard: { name:'Standard HDD LRS',  price_gb: 0.043 },
};

function initTcoDiskSelect() {
  const sel = document.getElementById('tcoDiskType');
  if (!sel) return;
  const prev = sel.value;
  const diskData = DISK_REGIONS[currentRegion] || DISK_REGIONS['eu-west-3'] || {};
  const order = ['gp3','gp2','io1','io2','st1','sc1','standard'];
  const keys = order.filter(function(k){ return diskData[k]; })
    .concat(Object.keys(diskData).filter(function(k){ return order.indexOf(k)===-1; }));
  sel.innerHTML = '';
  keys.forEach(function(k){
    const d = diskData[k];
    const az = AZ_DISK_MAP[k] || { name:'Standard SSD', price_gb: 0.094 };
    const o = document.createElement('option');
    o.value = k;
    o.textContent = k.toUpperCase() + ' — ' + d.type + ' ($' + d.price_gb.toFixed(4) + '/GB/mo)';
    if (k === prev || (!prev && k === 'gp3')) o.selected = true;
    sel.appendChild(o);
  });
}

function filterTcoInstances() {
  const cpuSel  = document.getElementById('tcoCpu');
  const ramSel  = document.getElementById('tcoRam');
  const instSel = document.getElementById('tcoInstance');
  if (!instSel) return;

  const cpu = cpuSel && cpuSel.value ? parseInt(cpuSel.value)   : null;
  const ram = ramSel && ramSel.value ? parseFloat(ramSel.value) : null;

  // Mettre à jour les RAM dispo selon le CPU sélectionné
  if (cpuSel && ramSel && cpu !== null) {
    const prevRam = ramSel.value;
    const ramVals = getTcoData()
      .filter(function(d){ return d.vcpu === cpu; })
      .map(function(d){ return d.ram; })
      .filter(function(v,i,a){ return a.indexOf(v)===i; })
      .sort(function(a,b){ return a-b; });
    ramSel.innerHTML = '<option value="">Any RAM</option>';
    ramVals.forEach(function(v){
      const o = document.createElement('option');
      o.value = v;
      o.textContent = v >= 1024 ? (v/1024).toFixed(0)+' TiB' : v+' GiB';
      if (String(v) === prevRam) o.selected = true;
      ramSel.appendChild(o);
    });
  }

  const ramFinal = ramSel && ramSel.value ? parseFloat(ramSel.value) : null;

  const filtered = getTcoData().filter(function(d){
    if (cpu !== null && d.vcpu !== cpu) return false;
    if (ramFinal !== null && d.ram !== ramFinal) return false;
    return true;
  }).sort(function(a,b){ return a.iname.localeCompare(b.iname); });

  instSel.innerHTML = '';
  if (filtered.length === 0) {
    const o = document.createElement('option');
    o.value = ''; o.textContent = '— no matching instances —';
    instSel.appendChild(o);
    return;
  }
  filtered.forEach(function(d){
    const o = document.createElement('option');
    o.value = d.iname;
    const ramStr = d.ram >= 1024 ? (d.ram/1024).toFixed(0)+' TiB' : d.ram+' GiB';
    o.textContent = d.iname + '  \u2014  ' + d.vcpu + ' vCPU / ' + ramStr;
    instSel.appendChild(o);
  });
  updateTcoCommitOptions();
}

function updateTcoCommitOptions() {
  const instSel = document.getElementById('tcoInstance');
  const commitSel = document.getElementById('tcoCommit');
  if (!instSel || !commitSel) return;
  const inst = getTcoData().find(function(d){ return d.iname === instSel.value; });
  const prev = commitSel.value;
  const opts = [{ v:'od', l:'On-Demand' }];
  if (inst) {
    if (inst.price_1yr)     opts.push({ v:'ri1y',     l:'Reserved 1yr No Upfront' });
    if (inst.price_1yr_all) opts.push({ v:'ri1y_all', l:'Reserved 1yr All Upfront' });
    if (inst.price_3yr)     opts.push({ v:'ri3y',     l:'Reserved 3yr No Upfront' });
    if (inst.price_3yr_all) opts.push({ v:'ri3y_all', l:'Reserved 3yr All Upfront' });
  }
  commitSel.innerHTML = '';
  opts.forEach(function(o){
    const el = document.createElement('option');
    el.value = o.v; el.textContent = o.l;
    if (o.v === prev) el.selected = true;
    commitSel.appendChild(el);
  });
  // Si la sélection précédente n'existe plus, sélectionner la meilleure option RI dispo ou od
  if (!opts.some(function(o){ return o.v === prev; })) {
    commitSel.value = opts.length > 1 ? opts[1].v : 'od';
  }
}

function tcoFmt(v) {
  if (v >= 1e6) return '$' + (v/1e6).toFixed(2) + 'M';
  if (v >= 100000) return '$' + Math.round(v/1000) + 'k';
  if (v >= 10000)  return '$' + (v/1000).toFixed(1) + 'k';
  return '$' + Math.round(v).toLocaleString();
}

function calcTco() {
  const iname       = document.getElementById('tcoInstance').value;
  const nbInst      = Math.max(1, parseInt(document.getElementById('tcoNbInst').value) || 1);
  const hpm         = parseFloat(document.getElementById('tcoUsage').value) || 730;
  const commit      = document.getElementById('tcoCommit').value;
  const storageGB   = parseFloat(document.getElementById('tcoStorage').value) || 0;
  const diskType    = document.getElementById('tcoDiskType').value;
  const egressGB    = 0;
  const supportType = 'none';
  const months      = tcoDurYears * 12;

  const isAzure = view === 'azure' || view === 'psql';
  const inst = getTcoData().find(function(d){ return d.iname === iname; });
  if (!inst) { alert('Please select an instance'); return; }

  // Hourly rate based on commitment
  let rate = inst.price;
  let commitLabel = 'On-Demand';
  if (commit === 'ri1y')     { rate = inst.price_1yr     || inst.price; commitLabel = 'Reserved 1yr'; }
  if (commit === 'ri1y_all') { rate = inst.price_1yr_all || inst.price_1yr || inst.price; commitLabel = 'Reserved 1yr All Up.'; }
  if (commit === 'ri3y')     { rate = inst.price_3yr     || inst.price; commitLabel = 'Reserved 3yr'; }
  if (commit === 'ri3y_all') { rate = inst.price_3yr_all || inst.price_3yr || inst.price; commitLabel = 'Reserved 3yr All Up.'; }

  // Compute cost
  const compute = rate * hpm * nbInst * months;

  // Storage
  const diskRegData = DISK_REGIONS[currentRegion] || DISK_REGIONS['eu-west-3'] || {};
  const diskInfo    = diskRegData[diskType] || {};
  const diskPrice   = isAzure ? (AZ_DISK_MAP[diskType] || { price_gb: 0.094 }).price_gb : (diskInfo.price_gb || 0.0928);
  const storageCost = diskPrice * storageGB * nbInst * months;

  // Network egress (EU, $/GB)
  const egressRate = isAzure ? 0.087 : 0.09;
  const egressCost = Math.min(egressGB, 10240) * egressRate * months;

  // Support
  const suppPct     = supportType === 'enterprise' ? 0.15 : supportType === 'business' ? 0.10 : 0;
  const supportCost = compute * suppPct;

  const total = compute + storageCost + egressCost + supportCost;

  // On-demand total for comparison (if reserved is selected)
  let odTotal = null;
  if (commit !== 'od') {
    const odCompute = inst.price * hpm * nbInst * months;
    odTotal = odCompute + storageCost + egressCost + (odCompute * suppPct);
  }

  renderTcoResults({
    cloud: isAzure ? 'Azure' : 'AWS',
    cloudColor: isAzure ? 'var(--azure)' : 'var(--aws)',
    total, months, compute, storageCost, egressCost, supportCost,
    rate, nbInst, hpm, storageGB, diskType, egressGB,
    commitLabel, inst, suppPct, odTotal
  });
}

function renderTcoResults(r) {
  const el = document.getElementById('tcoResults');
  if (!el) return;

  const durLbl = tcoDurYears + 'yr';

  // Summary card — single cloud
  const sumHtml =
    '<div class="tco-sum-row">' +
    '<div class="tco-sum-card"><div class="tco-sum-lbl">' + r.cloud + ' Total (' + durLbl + ')</div>' +
      '<div class="tco-sum-val" style="color:' + r.cloudColor + '">' + tcoFmt(r.total) + '</div>' +
      '<div class="tco-sum-sub">' + tcoFmt(r.total/r.months) + ' / month avg</div>' +
      '<div class="tco-sum-badge" style="background:rgba(123,255,224,0.1);border:1px solid var(--accent);color:var(--accent)">' + r.commitLabel + '</div></div>' +
    '<div class="tco-sum-card"><div class="tco-sum-lbl">Instance</div>' +
      '<div class="tco-sum-val" style="color:' + r.cloudColor + ';font-size:1.1rem">' + r.inst.iname + '</div>' +
      '<div class="tco-sum-sub">' + r.inst.vcpu + ' vCPU / ' + (r.inst.ram >= 1024 ? (r.inst.ram/1024).toFixed(0)+' TiB' : r.inst.ram+' GiB') + '</div></div>' +
    '<div class="tco-sum-card"><div class="tco-sum-lbl">Hourly Rate</div>' +
      '<div class="tco-sum-val" style="color:' + r.cloudColor + '">$' + r.rate.toFixed(4) + '/h</div>' +
      '<div class="tco-sum-sub">' + r.nbInst + ' instance' + (r.nbInst>1?'s':'') + ' \u00d7 ' + r.hpm + ' h/mo</div></div>' +
    '</div>';

  // Breakdown rows — single cloud
  const bkRows = [
    { name:'Compute',        sub: r.nbInst + '\u00d7 ' + r.inst.iname + ' \u00b7 ' + r.commitLabel, cost: r.compute },
    { name:'Storage',        sub: r.storageGB + ' GB ' + r.diskType + ' \u00d7 ' + r.nbInst, cost: r.storageCost },
    { name:'Network egress', sub: r.egressGB  + ' GB/mo EU', cost: r.egressCost },
    { name:'Support',        sub: (r.suppPct*100).toFixed(0) + '% of compute', cost: r.supportCost },
  ].filter(function(row){ return row.cost > 0; });

  const bkRowsHtml = bkRows.map(function(row) {
    return '<div class="tco-bk-row"><div><div class="tco-row-name">' + row.name + '</div>'
      + '<div class="tco-row-sub">' + row.sub + '</div></div>'
      + '<div class="tco-row-aws">' + tcoFmt(row.cost) + '</div></div>';
  }).join('');

  const bkHtml =
    '<div class="tco-breakdown">' +
    '<div class="tco-bk-hdr"><span>Cost category</span><span>' + r.cloud + ' (' + durLbl + ')</span></div>' +
    bkRowsHtml +
    '<div class="tco-bk-row total"><div><div class="tco-row-name" style="font-size:.88rem">Total ' + r.months + ' months</div></div>' +
      '<div class="tco-row-aws" style="font-size:.95rem">' + tcoFmt(r.total) + '</div></div>' +
    '</div>';

  // SVG chart (cumulative cost — single cloud, enhanced)
  var svgW=800,svgH=260,pL=70,pR=20,pT=30,pB=36;
  var cW=svgW-pL-pR, cH=svgH-pT-pB;
  var hasOd = r.odTotal && r.odTotal > r.total;
  var chartMax = hasOd ? r.odTotal : r.total;
  var maxV=chartMax*1.12;
  function tx(m){ return pL + (m/r.months)*cW; }
  function ty(v){ return pT + cH - (v/maxV)*cH; }

  var strokeColor = r.cloud === 'Azure' ? '#00aaff' : '#ff9900';
  var odColor     = '#ff4d6a';
  var gridColor   = '#2a3050';
  var labelColor  = '#8890a8';

  // Grid lines + Y-axis labels
  var grid='';
  var gridSteps = [0, 0.25, 0.5, 0.75, 1.0];
  gridSteps.forEach(function(p){
    var y=ty(maxV*p);
    var dash = p === 0 ? '' : ' stroke-dasharray="4,4"';
    grid+='<line x1="'+pL+'" y1="'+y.toFixed(1)+'" x2="'+(svgW-pR)+'" y2="'+y.toFixed(1)+'" stroke="'+gridColor+'" stroke-width="0.7"'+dash+'/>';
    grid+='<text x="'+(pL-8)+'" y="'+(y+4).toFixed(1)+'" fill="'+labelColor+'" font-size="10" font-family="IBM Plex Mono,monospace" text-anchor="end">'+tcoFmt(maxV*p)+'</text>';
  });

  // Build reserved line points
  var pts='';
  for(var m=0;m<=r.months;m++){
    pts += tx(m).toFixed(1)+','+ty(r.total*m/r.months).toFixed(1)+' ';
  }
  var bLine=pT+cH;

  // Build on-demand line points (if reserved selected)
  var odPts='';
  if(hasOd){
    for(var mo=0;mo<=r.months;mo++){
      odPts += tx(mo).toFixed(1)+','+ty(r.odTotal*mo/r.months).toFixed(1)+' ';
    }
  }

  // Gradient definitions
  var ts = Date.now();
  var gradId = 'tcoGrad_' + ts;
  var odGradId = 'tcoOdGrad_' + ts;
  var defs = '<defs><linearGradient id="'+gradId+'" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0%" stop-color="'+strokeColor+'" stop-opacity="0.25"/>'
    +'<stop offset="100%" stop-color="'+strokeColor+'" stop-opacity="0.02"/>'
    +'</linearGradient>';
  if(hasOd){
    defs+='<linearGradient id="'+odGradId+'" x1="0" y1="0" x2="0" y2="1">'
      +'<stop offset="0%" stop-color="'+odColor+'" stop-opacity="0.10"/>'
      +'<stop offset="100%" stop-color="'+odColor+'" stop-opacity="0.01"/>'
      +'</linearGradient>';
  }
  defs+='</defs>';

  // X-axis month labels
  var mLabels='';
  var step=Math.max(1,Math.ceil(r.months/8));
  for(var ml=0;ml<=r.months;ml+=step){
    mLabels+='<text x="'+tx(ml).toFixed(1)+'" y="'+(svgH-6)+'" fill="'+labelColor+'" font-size="10" font-family="IBM Plex Mono,monospace" text-anchor="middle">M'+ml+'</text>';
  }

  // Milestone dots + value labels for reserved line
  var dots='';
  var milestones = [0, Math.round(r.months*0.25), Math.round(r.months*0.5), Math.round(r.months*0.75), r.months];
  milestones = milestones.filter(function(v,i,a){ return a.indexOf(v)===i; });
  milestones.forEach(function(mm){
    var cx=tx(mm), cy=ty(r.total*mm/r.months);
    var val = r.total*mm/r.months;
    dots+='<circle cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="4" fill="'+strokeColor+'" stroke="var(--bg,#060709)" stroke-width="2"/>';
    var labelY = cy - 12;
    if(mm === 0) labelY = cy + 16;
    dots+='<text x="'+cx.toFixed(1)+'" y="'+labelY.toFixed(1)+'" fill="'+strokeColor+'" font-size="11" font-weight="700" font-family="IBM Plex Mono,monospace" text-anchor="middle">'+tcoFmt(val)+'</text>';
  });

  // On-demand dots + labels (only start and end to avoid clutter)
  var odDots='';
  if(hasOd){
    [r.months].forEach(function(mm){
      var cx=tx(mm), cy=ty(r.odTotal*mm/r.months);
      var val = r.odTotal*mm/r.months;
      odDots+='<circle cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="4" fill="'+odColor+'" stroke="var(--bg,#060709)" stroke-width="2"/>';
      odDots+='<text x="'+cx.toFixed(1)+'" y="'+(cy-12).toFixed(1)+'" fill="'+odColor+'" font-size="11" font-weight="700" font-family="IBM Plex Mono,monospace" text-anchor="middle">'+tcoFmt(val)+'</text>';
    });
    // Savings annotation at end
    var savPct = ((r.odTotal - r.total) / r.odTotal * 100).toFixed(0);
    var savAmt = tcoFmt(r.odTotal - r.total);
    var midY = (ty(r.total) + ty(r.odTotal)) / 2;
    odDots+='<text x="'+(svgW-pR-5)+'" y="'+midY.toFixed(1)+'" fill="var(--accent,#7bffe0)" font-size="11" font-weight="700" font-family="IBM Plex Mono,monospace" text-anchor="end">▼ '+savPct+'% ('+savAmt+')</text>';
  }

  // Build SVG
  var chartSvg='<svg viewBox="0 0 '+svgW+' '+svgH+'" style="width:100%;height:auto;max-height:280px" preserveAspectRatio="xMidYMid meet">'
    +defs+grid;
  // On-demand area + line (behind reserved)
  if(hasOd){
    chartSvg+='<polygon points="'+odPts+' '+(svgW-pR)+','+bLine+' '+pL+','+bLine+'" fill="url(#'+odGradId+')"/>';
    chartSvg+='<polyline points="'+odPts+'" fill="none" stroke="'+odColor+'" stroke-width="1.8" stroke-dasharray="6,4" stroke-linejoin="round" opacity="0.8"/>';
    chartSvg+=odDots;
  }
  // Reserved area + line (on top)
  chartSvg+='<polygon points="'+pts+' '+(svgW-pR)+','+bLine+' '+pL+','+bLine+'" fill="url(#'+gradId+')"/>'
    +'<polyline points="'+pts+'" fill="none" stroke="'+strokeColor+'" stroke-width="2.5" stroke-linejoin="round"/>'
    +dots+mLabels
    +'</svg>';

  // Legend
  var legendHtml = '<div class="tco-legend-item"><div class="tco-legend-dot" style="background:'+strokeColor+'"></div>' + r.commitLabel + '</div>';
  if(hasOd){
    legendHtml += '<div class="tco-legend-item"><div class="tco-legend-dot" style="background:'+odColor+';opacity:0.8"></div>On-Demand</div>';
  }

  const chartHtml =
    '<div class="tco-chart-panel">' +
    '<div class="tco-chart-title">Cumulative cost over ' + r.months + ' months</div>' +
    chartSvg +
    '<div class="tco-chart-legend">' + legendHtml + '</div></div>';

  el.innerHTML = sumHtml + bkHtml + chartHtml;
}
let veilleFilterSrc = 'all';
let _cmpRadarChart = null;

function renderComparaison() {
  const items = getData().filter(d => cmpSel.has(view==='rds' ? d.iname+'||'+(d.fam||'') : view==='psql' ? (d.fam||'')+'||'+d.iname : d.iname));
  const grid = document.getElementById('cmpCardsGrid');
  const radarWrap = document.getElementById('cmpRadarWrap');
  const summaryRow = document.getElementById('cmpSummaryRow');
  const subtitle = document.getElementById('cmpSubtitle');
  if (!grid) return;
  if (items.length === 0) {
    grid.innerHTML = '<div style="padding:48px;text-align:center;color:#3a3f55;font-family:IBM Plex Mono,monospace;font-size:.75rem">&#x2190; S\u00e9lectionnez des instances dans le tableau en cliquant sur les lignes</div>';
    if (radarWrap) radarWrap.style.display = 'none';
    if (summaryRow) summaryRow.style.display = 'none';
    if (subtitle) subtitle.style.display = 'none';
    return;
  }
  if (subtitle) subtitle.style.display = 'none';
  buildSets();
  items.forEach(d => { const sc = getScore(d); d.score = sc.score; d.scoreDet = sc; });
  const isAws = view === 'aws' || view === 'rds';
  const minPrice = Math.min(...items.map(d => d.price));
  const maxScore = Math.max(...items.map(d => d.score));
  grid.innerHTML = items.map(d => {
    const isBest = d.price === minPrice;
    const color = isAws ? '#ff9900' : '#00aaff';
    const rp = d[getRiKey()];
    const sav = rp ? Math.round((1-rp/d.price)*100) : null;
    const diff = d.price === minPrice ? null : ((d.price - minPrice)/minPrice*100);
    const scorePct = (d.score/10*100).toFixed(1);
    const scoreColor = d.score>=8?'#7bffe0':d.score>=6?'#ff9900':'#ff5566';
    return '<div class="cmp-card-full'+(isBest?' best':'')+'">'
      +'<div style="height:22px">'+(isBest?'<div class="cmp-best-badge">&#x2713; BEST VALUE</div>':'')+'</div>'
      +'<div style="font-size:14px;font-weight:800;color:'+color+';font-family:IBM Plex Mono,monospace;margin-bottom:2px">'+d.iname+'</div>'
      +'<div style="font-size:11px;color:#6b738f;margin-bottom:14px">'+(isAws?'AWS':'Azure')+' · '+((view==='rds'?FL_RDS:FL)[d.fam]||d.fam)+' · '+d.vcpu+' vCPU · '+ramFmt(d.ram)+'</div>'
      +'<div style="display:flex;flex-direction:column;gap:10px">'
      +'<div><div class="cmp-metric-lbl">On-Demand /h</div><div style="display:flex;align-items:center;gap:5px"><span class="cmp-metric-val" style="color:'+color+'">'+f4(d.price)+'</span>'+(diff!==null?'<span style="font-size:9px;color:'+(diff>0?'#ff5566':'#7bffe0')+'">'+(diff>0?'+':'')+diff.toFixed(1)+'%</span>':'')+'</div></div>'
      +'<div><div class="cmp-metric-lbl">Reserved '+(riYear==='3yr'?'3yr':'1yr')+' /h</div><div class="cmp-metric-val" style="color:#7bffe0">'+(rp?f4(rp)+' <span style="font-size:9px">−'+sav+'%</span>':'<span style="color:#3a3f55">—</span>')+'</div></div>'
      +'<div><div class="cmp-metric-lbl">Cost/vCPU</div><div class="cmp-metric-val" style="color:#c8d0e8">'+(d.vcpu>0?f4(d.price/d.vcpu):'—')+'</div></div>'
      +'<div><div class="cmp-metric-lbl">FinOps Score</div><div style="display:flex;align-items:center;gap:8px;margin-top:2px"><div class="cmp-bar-bg" style="flex:1"><div style="width:'+scorePct+'%;height:100%;background:'+scoreColor+';border-radius:3px"></div></div><span class="cmp-metric-val" style="color:'+scoreColor+'">'+d.score+'</span></div></div>'
      +'</div></div>';
  }).join('');
  if (radarWrap && items.length >= 2) {
    radarWrap.style.display = 'block';
    const legend = document.getElementById('cmpRadarLegend');
    const colors = items.map((d,i) => (view==='azure'||view==='psql') ? (i===0?'#00aaff':'rgba(0,170,255,0.45)') : (i===0?'#ff9900':i===1?'rgba(255,153,0,0.45)':'#7bffe0'));
    if (legend) legend.innerHTML = items.map((d,i) => '<div style="display:flex;align-items:center;gap:5px"><span style="width:8px;height:8px;border-radius:2px;background:'+colors[i]+';display:inline-block"></span><span style="font-family:IBM Plex Mono,monospace;font-size:10px;color:#c8d0e8">'+d.iname+'</span></div>').join('');
    if (_cmpRadarChart) { _cmpRadarChart.destroy(); _cmpRadarChart = null; }
    const maxP = Math.max(...items.map(d=>d.price));
    const datasets = items.map((d,i) => ({
      label: d.iname,
      data: [
        Math.round((1 - d.price/maxP)*100),
        (function(){ const rp=d[getRiKey()]; return rp?Math.round((1-rp/d.price)*100):0; })(),
        Math.round(d.score/10*100),
        Math.round(d.vcpu>0?Math.min(100,(1-(d.price/d.vcpu)/0.5)*100):50),
        Math.round(d.ram>0?Math.min(100,(1-(d.price/d.ram)/0.05)*100):50)
      ],
      borderColor: colors[i], backgroundColor: colors[i].includes('rgba')?colors[i]:colors[i]+'33',
      pointBackgroundColor: colors[i], borderWidth: 1.5, pointRadius: 3
    }));
    const ctx = document.getElementById('cmpRadarChart');
    if (ctx) _cmpRadarChart = new Chart(ctx, {
      type: 'radar',
      data: { labels: ['Prix /h','Reserved','Score','Cost/vCPU','Cost/RAM'], datasets },
      options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}},
        scales:{r:{min:0,max:100,grid:{color:'#1e2535'},ticks:{display:false},pointLabels:{color:'#6b738f',font:{family:'IBM Plex Mono',size:10}},angleLines:{color:'#1e2535'}}}}
    });
  } else if (radarWrap) radarWrap.style.display = 'none';
  if (summaryRow) {
    summaryRow.style.display = 'grid';
    const bestP = items.reduce((a,b)=>a.price<b.price?a:b);
    const bestSavItem = items.reduce((a,b)=>{ const ra=a[getRiKey()]; const rb=b[getRiKey()]; const sa=ra?Math.round((1-ra/a.price)*100):0; const sb=rb?Math.round((1-rb/b.price)*100):0; return sa>sb?a:b; });
    const bestSc = items.reduce((a,b)=>a.score>b.score?a:b);
    const rp2 = bestSavItem[getRiKey()];
    document.getElementById('cmpBestPrice').textContent = f4(bestP.price)+' '+currSym();
    document.getElementById('cmpBestPriceName').textContent = bestP.iname;
    document.getElementById('cmpBestSav').textContent = rp2?'−'+Math.round((1-rp2/bestSavItem.price)*100)+'%':'—';
    document.getElementById('cmpBestSavName').textContent = bestSavItem.iname;
    document.getElementById('cmpBestScore').textContent = bestSc.score;
    document.getElementById('cmpBestScoreName').textContent = bestSc.iname;
  }
}


function setVeille() {
  if (tcoActive) {
    tcoActive = false;
    document.getElementById('tcoBtn').classList.remove('active');
    const ts = document.getElementById('tcoSection');
    if (ts) ts.style.display = 'none';
  }
  if (heatmapActive) {
    heatmapActive = false;
    document.getElementById('heatmapBtn').classList.remove('active');
    const hs = document.getElementById('heatmapSection');
    if (hs) hs.style.display = 'none';
  }
  veilleActive = !veilleActive;
  const btn     = document.getElementById('veilleBtn');
  const vs      = document.getElementById('veilleSection');
  const main    = document.getElementById('hero');
  const filters = document.getElementById('filters');
  const tblwrap = document.getElementById('tblwrap');
  const statsrow= document.getElementById('statsrow');
  const topLeft = document.getElementById('topbarLeft');
  const topNav  = document.getElementById('topbarNav');
  btn.classList.toggle('active', veilleActive);
  if (veilleActive) {
    if (main)     main.style.display     = 'none';
    if (filters)  filters.style.display  = 'none';
    if (tblwrap)  tblwrap.style.display  = 'none';
    if (statsrow) statsrow.style.display = 'none';
    if (topLeft)  { topLeft.style.opacity = '0'; topLeft.style.pointerEvents = 'none'; }
    if (topNav)   { topNav.style.opacity  = '0'; topNav.style.pointerEvents  = 'none'; }
    showBackBtn(true);
    vs.style.display = 'block';
    renderVeille();
  } else {
    if (main)     main.style.display     = '';
    if (filters)  filters.style.display  = '';
    if (tblwrap)  tblwrap.style.display  = '';
    if (statsrow) statsrow.style.display = '';
    if (topLeft)  { topLeft.style.opacity = '1'; topLeft.style.pointerEvents = ''; }
    if (topNav)   { topNav.style.opacity  = '1'; topNav.style.pointerEvents  = ''; }
    showBackBtn(false);
    vs.style.display = 'none';
  }
}

function veilleFilter(src, btn) {
  veilleFilterSrc = src;
  document.querySelectorAll('.vsrc-btn').forEach(b => b.className = 'vsrc-btn');
  btn.classList.add(src === 'aws' ? 'on-aws' : src === 'azure' ? 'on-az' : 'on');
  renderVeille();
}

function renderVeille() {
  const grid = document.getElementById('veilleGrid');
  if (!grid) return;
  const srcLabel = {aws:'AWS FinOps', azure:'Azure FinOps', ff:'FinOps Foundation'};
  const srcIco   = {aws:'AWS', azure:'Az', ff:'FF'};
  const srcCls   = {aws:'src-aws', azure:'src-az', ff:'src-ff'};
  const tagCls   = {aws:'tag-aws', azure:'tag-az', ff:'tag-ff'};
  const q        = ((document.getElementById('veilleSearch')||{}).value||'').toLowerCase().trim();
  const now      = Date.now();
  let filtered   = veilleFilterSrc === 'all' ? VEILLE_DATA : VEILLE_DATA.filter(a => a.source === veilleFilterSrc);
  if (q) filtered = filtered.filter(a => (a.title||'').toLowerCase().includes(q) || (a.summary||'').toLowerCase().includes(q));
  const borderCls = {aws:'v-border-aws', azure:'v-border-az', ff:'v-border-ff'};
  grid.innerHTML = filtered.length === 0
    ? '<div style="grid-column:1/-1;text-align:center;padding:48px;color:#3a3f55;font-family:IBM Plex Mono,monospace;font-size:.75rem">No articles found.</div>'
    : filtered.map((a, idx) => {
        const lbl = srcLabel[a.source] || a.source;
        const tc  = tagCls[a.source]  || 'tag-ff';
        const bc  = borderCls[a.source] || 'v-border-ff';
        const isHero = idx === 0;
        let dFmt  = a.date || '';
        try { const d=new Date(a.date); if(!isNaN(d)) dFmt=d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){}
        let isNew = false;
        try { isNew = (now - new Date(a.date).getTime()) < 8*24*3600*1000; } catch(e){}
        const safeUrl = (a.url||'').replace(/"/g,'&quot;');
        return '<div data-href="'+safeUrl+'" onclick="window.open(this.dataset.href)" class="v-card '+bc+(isHero?' v-hero':'')+'">'
          + '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
          + '<div style="display:flex;align-items:center;gap:7px">'
          + '<span class="veille-tag '+tc+'">'+lbl+'</span>'
          + (isNew ? '<span style="font-size:.58rem;padding:2px 6px;border-radius:3px;background:rgba(123,255,224,.15);color:#7bffe0;border:1px solid rgba(123,255,224,.3)">NEW</span>' : '')
          + '</div>'
          + '<span style="font-size:.7rem;color:#6b738f;font-family:IBM Plex Mono,monospace">'+dFmt+'</span>'
          + '</div>'
          + '<div class="'+(isHero?'v-hero-title':'')+'" style="font-family:Syne,sans-serif;font-size:'+(isHero?'1.15rem':'.9rem')+';font-weight:700;color:#f0f4ff;line-height:1.35;margin-bottom:8px">'+a.title+'</div>'
          + (a.summary ? '<div class="v-summary" style="font-size:.8rem;color:#8b94b0;line-height:1.6;font-family:Syne,sans-serif;margin-bottom:8px">'+a.summary+'…</div>' : '')
          + '<div style="display:flex;align-items:center;justify-content:flex-end">'
          + '<span style="font-size:.68rem;color:#7bffe0;font-family:IBM Plex Mono,monospace">Read ↗</span>'
          + '</div></div>';
      }).join('');
}

let hmCloud = 'aws';
let hmMode  = 'famille';
let hmView  = 'atl';
let hmService = 'ec2';
let hmFam = '';
let hmEngine = '';  // filtre moteur pour Azure BDD

function setHmFam(fam, btn) {
  hmFam = fam;
  if (!fam) hmEngine = '';
  document.querySelectorAll('#hmFamGrp .fbtn').forEach(b => b.classList.remove('on'));
  if (btn) btn.classList.add('on');
  populateHmSizes();
  renderHeatmap();
}

function updateHmFamButtons() {
  const isRds = hmCloud === 'aws' && hmService === 'rds';
  const isBdd = hmCloud === 'azure' && hmService === 'bdd';
  const isDb  = isRds || isBdd;
  document.querySelectorAll('.hm-ec2-fam, .hm-az-fam').forEach(b => {
    if (b.classList.contains('hm-rds-fam') || b.classList.contains('hm-bdd-fam')) return; // All button
    b.style.display = isDb ? 'none' : '';
  });
  document.querySelectorAll('.hm-rds-fam').forEach(b => {
    if (b.textContent.trim() === 'All') { b.style.display = ''; return; }
    b.style.display = isRds ? '' : 'none';
  });
  document.querySelectorAll('.hm-bdd-fam').forEach(b => {
    if (b.textContent.trim() === 'All') { b.style.display = ''; return; }
    if (!b.classList.contains('hm-rds-fam')) b.style.display = isBdd ? '' : 'none';
  });
  document.querySelectorAll('.hm-bdd-only').forEach(b => b.style.display = isBdd ? '' : 'none');
  // Reset hmEngine si on quitte BDD
  if (!isBdd && hmEngine) { hmEngine = ''; }
  // Reset filtre si incompatible
  const RDS_FAMS  = ['mysql','postgresql','aurora-mysql','aurora-pg','mariadb','oracle','sqlserver'];
  const BDD_FAMS  = ['mysql','postgresql','sqlserver'];
  const EC2_FAMS  = ['general','compute','memory','burstable','storage','gpu','other'];
  // Reset hmFam si incompatible avec le service cible
  if (!isDb && RDS_FAMS.includes(hmFam))  { hmFam = ''; }  // RDS/BDD → EC2
  if (isRds && BDD_FAMS.includes(hmFam) && !RDS_FAMS.includes(hmFam)) { hmFam = ''; }  // BDD → RDS
  if (isBdd && !BDD_FAMS.includes(hmFam) && RDS_FAMS.includes(hmFam)) { hmFam = ''; }  // RDS → BDD
  if (isDb  && EC2_FAMS.includes(hmFam))  { hmFam = ''; }  // EC2 → DB
  if (!isBdd) hmEngine = '';
  // Remettre All actif si reset
  document.querySelectorAll('#hmFamGrp .fbtn').forEach(b => {
    const isAll = b.textContent.trim() === 'All';
    const isActive = hmFam === '' ? isAll : (b.getAttribute('onclick')||'').includes("'"+hmFam+"'");
    b.classList.toggle('on', isActive);
  });
}

function setHmEngine(engine, btn) {
  hmEngine = engine;
  document.querySelectorAll('#hmFamGrp .fbtn').forEach(b => b.classList.remove('on'));
  document.querySelectorAll('#hmFamGrp .hm-bdd-fam.All, #hmFamGrp .fbtn:first-child').forEach(b => b.classList.remove('on'));
  if (btn) btn.classList.add('on');
  else document.querySelector('#hmFamGrp .fbtn').classList.add('on');
  renderHeatmap();
}

function setHmCurr(c) {
  _curr = c;
  document.getElementById('hmBtnUsd').className = 'curr-btn' + (c==='usd'?' on':'');
  document.getElementById('hmBtnEur').className = 'curr-btn' + (c==='eur'?' on':'');
  renderHeatmap();
}

function setHmCloudService(cloud, service, btn) {
  hmCloud = cloud;
  hmService = service;
  hmFam = '';  // reset filtre famille à chaque changement de service
  hmEngine = '';
  updateHmFamButtons();
  // Reset tous les boutons heatmap nav
  ['hmCloud_aws_ec2','hmCloud_aws_rds','hmCloud_az_vm','hmCloud_az_bdd'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.className = 'nav-btn'; }
  });
  // Activer le bon
  if (btn) btn.className = 'nav-btn ' + (cloud === 'aws' ? 'active-aws' : 'active-azure');
  populateHmSizes();
  renderHeatmap();
}

function setHmService(v) {
  hmService = v;
  populateHmSizes();
  renderHeatmap();
}

function updateHmServiceSel() {
  // Met à jour les boutons nav heatmap selon hmCloud/hmService courants
  ['hmCloud_aws_ec2','hmCloud_aws_rds','hmCloud_az_vm','hmCloud_az_bdd'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'nav-btn';
  });
  let activeId = null;
  if (hmCloud === 'aws' && hmService === 'ec2') activeId = 'hmCloud_aws_ec2';
  else if (hmCloud === 'aws' && hmService === 'rds') activeId = 'hmCloud_aws_rds';
  else if (hmCloud === 'azure' && hmService !== 'bdd') activeId = 'hmCloud_az_vm';
  else if (hmCloud === 'azure' && hmService === 'bdd') activeId = 'hmCloud_az_bdd';
  if (activeId) {
    const el = document.getElementById(activeId);
    if (el) el.className = 'nav-btn ' + (hmCloud === 'aws' ? 'active-aws' : 'active-azure');
  }
}

const FAM_LABELS = {
  general:'General Purpose', compute:'CPU Optimized', memory:'Memory Optimized',
  burstable:'Burstable', storage:'Storage', gpu:'GPU', other:'Other'
};

function populateHmSizes() {
  const sizeSel = document.getElementById('hmSizeSel');
  if (!sizeSel) return;
  const clouds = hmCloud === 'both' ? ['aws','azure'] : [hmCloud];
  const seen = new Set();
  clouds.forEach(c => {
    const src = c === 'azure' ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS) : AWS_ALL_REGIONS;
    const firstReg = Object.values(src)[0] || [];
    firstReg.filter(d => (!hmFam || d.fam === hmFam) && d.vcpu > 0).forEach(d => seen.add(d.vcpu));
  });
  const cur = parseInt(sizeSel.value);
  const vcpus = [...seen].sort((a,b) => a-b);
  sizeSel.innerHTML = '<option value="">All vCPU</option>'
    + vcpus.map(v => '<option value="'+v+'"'+(v===cur?' selected':'')+'>'+v+' vCPU</option>').join('');
  if (!vcpus.includes(cur)) sizeSel.value = '';
  populateHmRam();
}

function populateHmFamilies() { populateHmSizes(); }

function populateHmVcpu() {
  const sizeSel = document.getElementById('hmSizeSel');
  if (!sizeSel) return;
  const fam    = hmFam;
  const clouds = hmCloud === 'both' ? ['aws','azure'] : [hmCloud];
  const seen   = new Set();
  clouds.forEach(c => {
    const src = c === 'azure'
      ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS)
      : AWS_ALL_REGIONS;
    const firstReg = Object.values(src)[0] || [];
    firstReg.filter(d => (!fam || d.fam === fam) && d.vcpu > 0).forEach(d => seen.add(d.vcpu));
  });
  const cur   = parseInt(sizeSel.value);
  const vcpus = [...seen].sort((a,b) => a-b);
  sizeSel.innerHTML = '<option value="">Tous</option>'
    + vcpus.map(v =>
      '<option value="'+v+'"'+(v===cur?' selected':'')+'>'+v+' vCPU</option>'
    ).join('');
  if (!vcpus.includes(cur)) sizeSel.value = '';
  populateHmRam();
}

function populateHmInstances2() {
  const sizeSel = document.getElementById('hmSizeSel');
  const ramSel  = document.getElementById('hmRamSel');
  const instSel = document.getElementById('hmInstSel2');
  if (!sizeSel || !ramSel || !instSel) return;
  const fam        = hmFam;
  const vcpuTarget = parseInt(sizeSel.value);
  const ramTarget  = parseFloat(ramSel.value);
  const clouds     = hmCloud === 'both' ? ['aws','azure'] : [hmCloud];
  const seen = new Set(); const opts = [];
  clouds.forEach(c => {
    const src = c === 'azure'
      ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS)
      : AWS_ALL_REGIONS;
    const firstReg = Object.values(src)[0] || [];
    firstReg.filter(d => (!fam || d.fam === fam) && (!vcpuTarget || d.vcpu === vcpuTarget) && Math.abs((d.ram||0) - ramTarget) < 0.1)
      .forEach(d => { if (!seen.has(d.iname)) { seen.add(d.iname); opts.push(d); } });
  });
  opts.sort((a,b) => a.price - b.price);
  const cur = instSel.value;
  instSel.innerHTML = '<option value="">All</option>'
    + opts.map(o => '<option value="'+o.iname+'"'+(o.iname===cur?' selected':'')+'>'+o.iname+'</option>').join('');
}

function populateHmRam() {
  const sizeSel = document.getElementById('hmSizeSel');
  const ramSel  = document.getElementById('hmRamSel');
  if (!sizeSel || !ramSel) return;
  const fam         = hmFam;
  const vcpuTarget  = parseInt(sizeSel.value);
  const clouds      = hmCloud === 'both' ? ['aws','azure'] : [hmCloud];
  const seen        = new Set();
  clouds.forEach(c => {
    const src = c === 'azure' ? AZURE_ALL_REGIONS : AWS_ALL_REGIONS;
    const firstReg = Object.values(src)[0] || [];
    firstReg.filter(d => (!fam || d.fam === fam) && (!vcpuTarget || d.vcpu === vcpuTarget)).forEach(d => {
      if (d.ram) seen.add(d.ram);
    });
    if (!seen.size) {
      const close = firstReg.filter(d => (!fam || d.fam === fam))
        .sort((a,b) => Math.abs(a.vcpu-(vcpuTarget||0))-Math.abs(b.vcpu-(vcpuTarget||0)));
      if (close.length) seen.add(close[0].ram);
    }
  });
  const cur = parseFloat(ramSel.value);
  const rams = [...seen].sort((a,b) => a-b);
  ramSel.innerHTML = '<option value="">All RAM</option>'
    + rams.map(r =>
    '<option value="'+r+'"'+(r===cur?' selected':'')+'>'+(r < 1 ? (r*1024)+'MB' : r+' GiB')+'</option>'
  ).join('');
  if (!rams.includes(cur) && rams.length) ramSel.value = rams[0];
  populateHmInstances2();
}

function setHeatmap() {
  if (veilleActive)      { veilleActive = false;      document.getElementById('veilleBtn').classList.remove('active');      document.getElementById('veilleSection').style.display = 'none'; }
  if (tcoActive) {
    tcoActive = false;
    document.getElementById('tcoBtn').classList.remove('active');
    const ts = document.getElementById('tcoSection');
    if (ts) ts.style.display = 'none';
  }
  heatmapActive = !heatmapActive;
  const btn     = document.getElementById('heatmapBtn');
  const hs      = document.getElementById('heatmapSection');
  const main    = document.getElementById('hero');
  const filters = document.getElementById('filters');
  const tblwrap = document.getElementById('tblwrap');
  const statsrow= document.getElementById('statsrow');
  const topLeft = document.getElementById('topbarLeft');
  const topNav  = document.getElementById('topbarNav');
  btn.classList.toggle('active', heatmapActive);
  const show = heatmapActive;
  if (main)     main.style.display     = show ? 'none' : '';
  if (filters)  filters.style.display  = show ? 'none' : '';
  if (tblwrap)  tblwrap.style.display  = show ? 'none' : '';
  if (statsrow) statsrow.style.display = show ? 'none' : '';
  if (topLeft)  { topLeft.style.opacity = show ? '0' : '1'; topLeft.style.pointerEvents = show ? 'none' : ''; }
  if (topNav) {
    topNav.style.opacity = '1';
    topNav.style.pointerEvents = '';
    if (show) {
      // Ne sauvegarder que si ce n'est pas déjà les boutons heatmap
      if (!topNav.innerHTML.includes('hmCloud_aws_ec2')) topNav.dataset.orig = topNav.innerHTML;
      topNav.innerHTML = `
        <div class="nav-inline">
          <span class="nav-cloud-label aws">AWS</span>
          <div class="nav-group aws-group">
            <button class="nav-btn active-aws" id="hmCloud_aws_ec2" onclick="setHmCloudService('aws','ec2',this)">EC2</button>
            <div class="nav-sep-aws"></div>
            <button class="nav-btn" id="hmCloud_aws_rds" onclick="setHmCloudService('aws','rds',this)">RDS</button>
          </div>
        </div>
        <div class="nav-inline">
          <span class="nav-cloud-label az">Azure</span>
          <div class="nav-group az-group">
            <button class="nav-btn" id="hmCloud_az_vm" onclick="setHmCloudService('azure','ec2',this)">VM</button>
            <div class="nav-sep-az"></div>
            <button class="nav-btn" id="hmCloud_az_bdd" onclick="setHmCloudService('azure','bdd',this)">DB</button>
          </div>
        </div>`;
      updateHmServiceSel();
    } else {
      if (topNav.dataset.orig) topNav.innerHTML = topNav.dataset.orig;
    }
  }
  showBackBtn(show);
  hs.style.display = show ? 'flex' : 'none';
  if (show) {
    // Synchroniser avec la vue principale courante
    if (view === 'rds')   { hmCloud = 'aws';   hmService = 'rds'; }
    else if (view === 'azure') { hmCloud = 'azure'; hmService = 'ec2'; }
    else if (view === 'psql')  { hmCloud = 'azure'; hmService = 'bdd'; }
    else                       { hmCloud = 'aws';   hmService = 'ec2'; }
    updateHmServiceSel();
    updateHmFamButtons();
    populateHmSizes();
    renderHeatmap();
  }
}

function setHmView(v, btn) {
  hmView = v;
  document.querySelectorAll('#hmViewAtl').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  renderHeatmap();
}

function renderHeatmap() {
  const clouds  = hmCloud === 'both' ? ['aws','azure'] : [hmCloud];
  const sizeSel    = document.getElementById('hmSizeSel');
  const ramSel     = document.getElementById('hmRamSel');
  const instSel2   = document.getElementById('hmInstSel2');
  const fam        = hmFam;
  console.log('renderHeatmap hmCloud='+hmCloud+' hmService='+hmService+' hmFam='+hmFam+' hmEngine='+hmEngine);
  const vcpuTarget = sizeSel && sizeSel.value ? parseInt(sizeSel.value) : null;
  const ramTarget  = ramSel  && ramSel.value  ? parseFloat(ramSel.value) : null;
  const instTarget = instSel2 ? instSel2.value : '';

  const HM_VIEWS = {
    eu:    { center:[10,54],  scale:900 },
    atl:   { center:[-20,45], scale:250, ratio:0.32 },
    world: { center:[10,45], scale:155 },
  };

  const CITY_COORDS = {
    'eu-west-3':          { lon:2.3522, lat:48.8566, label:'Paris',     cloud:'aws'   },
    'eu-west-1':          { lon:-6.2603,lat:53.3498, label:'Irlande',   cloud:'aws'   },
    'eu-central-1':       { lon:8.6821, lat:50.1109, label:'Francfort', cloud:'aws'   },
    'eu-west-2':          { lon:-0.1276,lat:51.5074, label:'Londres',   cloud:'aws'   },
    'eu-north-1':         { lon:17.9139,lat:59.3293, label:'Stockholm', cloud:'aws'   },
    'eu-south-1':         { lon:9.1900, lat:45.4654, label:'Milan',     cloud:'aws'   },
    'eu-south-2':         { lon:-3.7038,lat:40.4168, label:'Madrid',    cloud:'aws'   },
    'us-east-1':          { lon:-77.47, lat:38.99,   label:'Virginie',  cloud:'aws'   },
    'francecentral':      { lon:2.3522, lat:48.8566, label:'Paris',     cloud:'azure' },
    'northeurope':        { lon:-6.2603,lat:53.3498, label:'Irlande',   cloud:'azure' },
    'westeurope':         { lon:4.9041, lat:52.3676, label:'Amsterdam', cloud:'azure' },
    'germanywestcentral': { lon:8.6821, lat:50.1109, label:'Francfort', cloud:'azure' },
    'uksouth':            { lon:-0.1276,lat:51.5074, label:'Londres',   cloud:'azure' },
    'swedencentral':      { lon:16.3458,lat:60.1282, label:'Gävle',     cloud:'azure' },
    'italynorth':         { lon:9.1900, lat:45.4654, label:'Milan',     cloud:'azure' },
    'eastus':             { lon:-77.47, lat:38.99,   label:'Virginie',  cloud:'azure' },
  };
  const ISO_MAP = {
    'eu-west-1':'372','northeurope':'372',
    'eu-west-2':'826','uksouth':'826',
    'eu-west-3':'250','francecentral':'250',
    'westeurope':'528',
    'eu-central-1':'276','germanywestcentral':'276',
    'swedencentral':'752','eu-north-1':'752',
    'eu-south-1':'380',
    'italynorth':'380',
    'eu-south-2':'724',
    'us-east-1':'840','eastus':'840',
  };

  function median(arr) {
    if (!arr || !arr.length) return null;
    const p = arr.map(d => d.price).filter(p => p > 0).sort((a,b) => a-b);
    if (!p.length) return null;
    const m = Math.floor(p.length/2);
    return p.length%2 ? p[m] : (p[m-1]+p[m])/2;
  }

  // Calcul prix par région selon filtres famille/taille
  const regionMedians = {};
  const regionReserved = {};
  const regionMinMax = {};  // min/max panier commun filtré

  let _commonCount = 0;  // nb instances panier commun
  clouds.forEach(c => {
    const allRegs = c === 'azure'
      ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS)
      : (hmService === 'rds' ? RDS_ALL_REGIONS : AWS_ALL_REGIONS);

    // Étape 1 : instances filtrées par région
    const regFiltered = {};
    Object.entries(allRegs).forEach(([reg, data]) => {
      if (!CITY_COORDS[reg] || CITY_COORDS[reg].cloud !== c) return;
      const isBdd2 = c === 'azure' && hmService === 'bdd';
      regFiltered[reg] = data.filter(d =>
        (!fam        || d.fam === fam)
        && (!vcpuTarget || d.vcpu === vcpuTarget)
        && (!ramTarget  || Math.abs(d.ram - ramTarget) < 0.1)
        && (!instTarget || d.iname === instTarget)
        && (!isBdd2 || !hmEngine || d.engine === hmEngine)
      );
    });

    // Étape 2 : intersection
    // Pour EC2/VM : intersection sur iname (instances communes)
    // Pour RDS/BDD : intersection sur fam (moteurs communs)
    const regKeys = Object.keys(regFiltered);
    const isDbService = (c === 'aws' && hmService === 'rds') || (c === 'azure' && hmService === 'bdd');
    if (regKeys.length > 0) {
      let common_keys, getCommon;
      // Intersection toujours sur iname — le filtre fam est déjà appliqué dans regFiltered
      const inameSets = regKeys.map(r => new Set(regFiltered[r].map(d => d.iname)));
      const commonInames = inameSets.length > 0 ? [...inameSets[0]].filter(n => inameSets.every(s => s.has(n))) : [];
      _commonCount = commonInames.length || (inameSets[0] ? inameSets[0].size : 0);
      common_keys = commonInames;
      getCommon = (reg) => commonInames.length > 0
        ? regFiltered[reg].filter(d => commonInames.includes(d.iname))
        : regFiltered[reg];

      // Étape 3 : moyenne sur le panier commun pour chaque région
      regKeys.forEach(reg => {
        const common = getCommon(reg);
        if (!common.length) return;
        const price = common.reduce((s,d) => s+d.price, 0) / common.length;
        regionMedians[reg] = price;
        const prices = common.map(d => d.price);
        const maxCommonObj = [...common].sort((a,b) => b.price-a.price)[0];
        regionMinMax[reg] = { min: Math.min(...prices), max: Math.max(...prices), maxInst: maxCommonObj ? maxCommonObj.iname : '' };
        const ri = common.filter(d => d[getRiKey()]);
        if (ri.length) regionReserved[reg] = Math.min(...ri.map(d => d[getRiKey()]||d.price_1yr||0));
      });
    }
  });
  // regionMediansTable = alias de regionMinMax (intersection du panier commun)
  const regionMediansTable = regionMinMax;

  const refKey = clouds.includes('azure') ? 'francecentral' : 'eu-west-3';
  const refVal = regionMedians[refKey] || Math.min(...Object.values(regionMedians).filter(Boolean)) || 1;

  const cheapestReg = Object.entries(regionMedians).filter(([r]) => CITY_COORDS[r]).sort((a,b) => a[1]-b[1])[0];
  const cheapestVal = cheapestReg ? cheapestReg[1] : 1;

  // Gradient dynamique basé sur les valeurs réelles des régions présentes
  const allVals = Object.values(regionMedians).filter(Boolean);
  const minVal  = Math.min(...allVals);
  const maxVal  = Math.max(...allVals);
  const range   = maxVal - minVal || 1;

  function diffColor(val) {
    const t = (val - minVal) / range;
    if (t < 0.33) {
      const tt = t / 0.33;
      const r = Math.round(74  + (163-74)*tt);
      const g = Math.round(222 + (230-222)*tt);
      const b = Math.round(128 + (53-128)*tt);
      return 'rgb('+r+','+g+','+b+')';
    } else if (t < 0.66) {
      const tt = (t-0.33) / 0.33;
      const r = Math.round(163 + (250-163)*tt);
      const g = Math.round(230 + (204-230)*tt);
      const b = Math.round(53  + (21-53)*tt);
      return 'rgb('+r+','+g+','+b+')';
    } else {
      const tt = (t-0.66) / 0.34;
      const r = Math.round(250 + (248-250)*tt);
      const g = Math.round(204 + (113-204)*tt);
      const b = Math.round(21  + (113-21)*tt);
      return 'rgb('+r+','+g+','+b+')';
    }
  }

  const activeRegs = Object.keys(regionMedians).filter(r => CITY_COORDS[r]);
  const cloudName = hmCloud === 'azure' ? 'Azure' : 'AWS';
  const totalRegs = Object.keys(hmCloud === 'azure' ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS) : (hmService === 'rds' ? RDS_ALL_REGIONS : AWS_ALL_REGIONS)).length;
  const famLabel2 = hmEngine ? hmEngine.charAt(0).toUpperCase()+hmEngine.slice(1) : (fam ? fam.charAt(0).toUpperCase()+fam.slice(1) : 'All');
  const commonUnit = 'instances';
  const svcLabel = hmService === 'rds' ? 'RDS' : hmService === 'bdd' ? 'DB' : hmService.toUpperCase();
  document.getElementById('heatmapSub').innerHTML =
    '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8">Comparing </span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.92rem;color:#7bffe0;font-weight:700">'+activeRegs.length+'</span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8"> '+cloudName+' '+svcLabel+' regions</span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8"> · </span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.92rem;color:#7bffe0;font-weight:700">'+_commonCount+'</span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8"> common instances</span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8"> · </span>'
    + '<span style="font-family:IBM Plex Mono,monospace;font-size:.82rem;color:#c8d0e8">'+(famLabel2==='All' ? 'All families' : famLabel2+' family')+'</span>';
  const cFill = {};
  activeRegs.forEach(reg => {
    const val = regionMedians[reg];
    const iso = ISO_MAP[reg];
    if (iso && !cFill[iso]) cFill[iso] = diffColor(val);
  });

  const svgEl = document.getElementById('worldMapSvg');
  if (!window.d3 || !window.topojson) {
    svgEl.innerHTML = '<text x="50%" y="50%" text-anchor="middle" font-family="IBM Plex Mono,monospace" font-size="13" fill="#ff5566">Libs manquantes \u2014 relancez fetch_prices.py</text>';
    return;
  }

  const svg = d3.select('#worldMapSvg');
  svg.selectAll('*').remove();
  const W = 900;
  const v = HM_VIEWS[hmView] || HM_VIEWS.atl;
  const H = Math.round(W * (v.ratio || 0.38));
  svg.attr('viewBox', '0 0 '+W+' '+H)
     .attr('preserveAspectRatio', 'xMidYMid meet')
     .style('height', 'auto');

  const proj = d3.geoMercator().center(v.center).scale(v.scale).translate([W/2, H/2]);
  const path = d3.geoPath(proj);

  // Reverse map : iso -> reg
  const isoToReg = {};
  activeRegs.forEach(reg => {
    const iso = ISO_MAP[reg];
    if (iso) isoToReg[iso] = reg;
  });

  const tooltip = document.getElementById('hmTooltip');
  const svgContainer = svgEl.parentElement;

  function draw(world) {
    const countries = topojson.feature(world, world.objects.countries);
    svg.append('rect').attr('width',W).attr('height',H).attr('rx',8).attr('fill','#07111f');
    svg.selectAll('path.land').data(countries.features).join('path').attr('class','land')
      .attr('d', path)
      .attr('fill', d => cFill[String(d.id)] || '#1a2035')
      .attr('stroke','#0c1220')
      .attr('stroke-width', hmView==='eu' ? .6 : .35)
      .style('cursor', d => isoToReg[String(d.id)] ? 'pointer' : 'default')
      .on('click', function(event, d) {
        const reg = isoToReg[String(d.id)];
        if (!reg) return;
        heatmapActive = false;
        document.getElementById('heatmapBtn').classList.remove('active');
        document.getElementById('heatmapSection').style.display = 'none';
        ['hero','filters','tblwrap','statsrow'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = ''; });
        const topLeft = document.getElementById('topbarLeft');
        const topNav  = document.getElementById('topbarNav');
        if (topLeft) { topLeft.style.opacity='1'; topLeft.style.pointerEvents=''; }
        if (topNav)  { topNav.style.opacity='1';  topNav.style.pointerEvents=''; }
        const isAz = CITY_COORDS[reg].cloud === 'azure';
        setNav(hmService === 'bdd' ? 'psql' : hmService === 'rds' ? 'rds' : isAz ? 'azure' : 'ec2');
        if (isAz) setAzureRegion(reg); else setRegion(reg);
        const sel = document.getElementById('regionSelect');
        if (sel) { sel.value = reg; adaptRegionWidth(sel); }
      });

    // Marqueurs — cercle plein + anneau blanc, tooltip uniquement sur les ronds
    activeRegs.forEach(reg => {
      const c   = CITY_COORDS[reg];
      const val = regionMedians[reg];
      const ri1 = regionReserved[reg];
      const eco = val ? (val - cheapestVal) * 730 : 0;
      const cloudColor = hmCloud === 'aws' ? '#ff9900' : '#00aaff';
      const cloudLbl = hmCloud === 'aws'
        ? '<span style="color:#ff9900">AWS '+hmService.toUpperCase()+'</span>'
        : '<span style="color:#00aaff">Azure '+hmService.toUpperCase()+'</span>';
      const cheapestLabel = cheapestReg ? (CITY_COORDS[cheapestReg[0]] ? CITY_COORDS[cheapestReg[0]].label : '') : '';
      const vcpuTarget2 = sizeSel && sizeSel.value ? parseInt(sizeSel.value) : null;
      const pvcpu = (val && vcpuTarget2 > 0) ? (val / vcpuTarget2) : null;

      const pt  = proj([c.lon, c.lat]);
      if (!pt) return;
      const [px, py] = pt;
      if (px<-10||px>W+10||py<-10||py>H+10) return;

      // Anneau
      const ring = svg.append('circle').attr('cx', px).attr('cy', py).attr('r', 6)
        .attr('fill', 'none').attr('stroke', 'white').attr('stroke-width', 0.8)
        .attr('opacity', 0.25).attr('pointer-events', 'none');
      // Point
      svg.append('circle').attr('cx', px).attr('cy', py).attr('r', 2.5)
        .attr('fill', 'white').attr('opacity', 0.85).attr('pointer-events', 'none');
      // Zone de hit invisible
      svg.append('circle').attr('cx', px).attr('cy', py).attr('r', 10)
        .attr('fill', 'transparent').attr('stroke', 'none').style('cursor', 'pointer')
        .on('mouseenter', function() {
          ring.attr('fill', 'white').attr('opacity', 0.15).attr('stroke', 'none');
        })
        .on('mouseleave', function() {
          ring.attr('fill', 'none').attr('opacity', 0.25).attr('stroke', 'white').attr('stroke-width', 0.8);
          tooltip.style.display = 'none';
        })
        .on('mousemove', function(event) {
          const tipHtml =
            '<div style="margin-bottom:7px;display:flex;justify-content:space-between;align-items:flex-start;gap:16px">'
            +'<div><span style="font-weight:700;color:'+cloudColor+'">'+c.label+'</span><br><span style="color:#c8d0e8;font-size:.68rem">'+reg+'</span></div>'
            +'<div style="padding-top:1px">'+cloudLbl+'</div>'
            +'</div>'
            +'<div style="border-top:1px solid #2a3050;margin-bottom:8px"></div>'
            +'<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
            +'<span style="color:var(--text2)">Avg On-Demand</span>'
            +'<span style="color:#c8d0e8;font-weight:700">'+(val ? (val*currRate()).toFixed(4) : '\u2014')+' '+currSym()+'/h</span></div>'
            +(pvcpu !== null ? '<div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="color:var(--text2)">Prix / vCPU</span><span style="color:#c8d0e8">'+(pvcpu*currRate()).toFixed(4)+' '+currSym()+'/h</span></div>' : '')
            +(function(){ const mm = regionMinMax[reg]; if(!mm) return ''; return '<div style="border-top:1px solid #1c2030;margin-top:5px;padding-top:5px">'+'<div style="display:flex;justify-content:space-between;margin-bottom:2px">'+'<span style="color:var(--text2);font-size:.68rem">Min</span>'+'<span style="color:#c8d0e8;font-size:.68rem">'+f4(mm.min)+' '+currSym()+'</span></div>'+'<div style="display:flex;justify-content:space-between">'+'<span style="color:var(--text2);font-size:.68rem">Max</span>'+'<span style="color:#c8d0e8;font-size:.68rem">'+f4(mm.max)+' '+currSym()+'</span></div>'+'</div>'; })()
            +(function(){ const cd = CARBON_DATA[reg]; if(!cd) return '';
              const co2=cd.co2; const col=co2<100?'#1D9E75':co2<300?'#BA7517':'#E24B4A';
              return '<div style="border-top:1px solid #1c2030;margin-top:5px;padding-top:5px">'
                +'<div style="display:flex;justify-content:space-between;margin-bottom:2px">'
                +'<span style="color:var(--text2);font-size:.68rem">Carbon</span>'
                +'<span style="font-size:.68rem;font-weight:700;color:#c8d0e8">'+co2+' gCO2/kWh</span></div>'
                +'<div style="display:flex;justify-content:space-between">'
                +'<span style="color:var(--text2);font-size:.68rem">Mix</span>'
                +'<span style="color:#c8d0e8;font-size:.68rem">'+cd.mix+'</span></div>'
                +'</div>'; })()
            +'<div style="border-top:1px solid #1c2030;margin-top:6px;padding-top:6px;display:flex;justify-content:space-between">'
            +(eco <= 0.1
              ? '<span style="color:var(--accent);font-weight:700;letter-spacing:.08em;font-size:.68rem">&#x2713; CHEAPEST</span><span></span>'
              : '<span style="color:var(--text2)">vs '+cheapestLabel+'</span><span style="color:#c8d0e8">+'+((val/cheapestVal-1)*100).toFixed(1)+'%</span>')
            +'</div>';
          tooltip.innerHTML = tipHtml;
          const rect = svgContainer.getBoundingClientRect();
          let tx = event.clientX - rect.left + 14;
          let ty = event.clientY - rect.top - 10;
          if (tx + 220 > svgContainer.offsetWidth) tx = event.clientX - rect.left - 224;
          tooltip.style.left = tx + 'px';
          tooltip.style.top  = ty + 'px';
          tooltip.style.display = 'block';
        })
        .on('click', function() {
          heatmapActive = false;
          document.getElementById('heatmapBtn').classList.remove('active');
          document.getElementById('heatmapSection').style.display = 'none';
          ['hero','filters','tblwrap','statsrow'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = ''; });
          const topLeft = document.getElementById('topbarLeft');
          const topNav  = document.getElementById('topbarNav');
          if (topLeft) { topLeft.style.opacity='1'; topLeft.style.pointerEvents=''; }
          if (topNav)  { topNav.style.opacity='1';  topNav.style.pointerEvents=''; }
          const isAz = c.cloud === 'azure';
          setNav(hmService === 'bdd' ? 'psql' : hmService === 'rds' ? 'rds' : isAz ? 'azure' : 'ec2');
          if (isAz) setAzureRegion(reg); else setRegion(reg);
          const sel = document.getElementById('regionSelect');
          if (sel) { sel.value = reg; adaptRegionWidth(sel); }
        });
    });
  }

  if (!window._topoWorld) {
    window._topoWorld = %%WORLD_TOPO%%;
  }
  if (window._topoWorld) { draw(window._topoWorld); }

  // Panneau variations à droite
  const sortedRegs = [...activeRegs].sort((a,b) => (regionMedians[a]||0) - (regionMedians[b]||0));

  const panel = document.getElementById('hmRegionPanel');
  const famLabel  = fam  ? (FAM_LABELS[fam]  || fam)  : 'All families';
  const vcpuLabel = vcpuTarget ? vcpuTarget+' vCPU' : 'All vCPU';
  const ramLabel  = ramTarget  ? ramTarget+' GiB RAM' : 'Toute RAM';
  const instLabel = instTarget ? ' · '+instTarget : '';
  const contextLabel = famLabel+' · '+vcpuLabel+' · '+ramLabel+instLabel;
  const serviceLabel = (hmCloud === 'aws' ? 'AWS ' : 'Azure ') + hmService.toUpperCase();

  panel.innerHTML = '<div style="font-family:IBM Plex Mono,monospace;font-size:.82rem;font-weight:700;color:#7bffe0;letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px">Top 5 Cheapest Regions</div>'

  sortedRegs.slice(0, 5).forEach((reg, idx) => {
    const m        = CITY_COORDS[reg];
    const val      = regionMedians[reg];
    const ri1      = regionReserved[reg];
    const isCheap  = idx === 0;
    const d        = val ? (val/cheapestVal)-1 : 0;
    const col      = isCheap ? '#7bffe0' : diffColor(val);
    const pct      = (d*100).toFixed(1);
    const lbl      = isCheap ? '0.0%' : '+'+pct+'%';
    const surcoût  = isCheap ? 0 : (val - cheapestVal) * 730;
    const card     = document.createElement('div');
    card.style.cssText = 'background:var(--s1);border:1px solid var(--b1);border-left:3px solid '+(isCheap?'#7bffe0':col)+';border-radius:0 6px 6px 0;padding:10px 14px';
    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">'
      +'<span style="font-family:IBM Plex Mono,monospace;font-size:.95rem;font-weight:700;color:#c8d0e8">'+m.label+' <span style="color:#c8d0e8;font-size:.95rem">('+reg+')</span></span>'
      +'<span style="font-family:IBM Plex Mono,monospace;font-size:.95rem;font-weight:700;color:#c8d0e8">'+lbl+'</span>'
      +'</div>'
      +'<div style="display:flex;justify-content:space-between;font-family:IBM Plex Mono,monospace;font-size:.82rem;color:var(--muted);margin-bottom:2px">'
      +'<span style="color:#c8d0e8">Avg On-Demand</span>'
      +'<span style="color:#c8d0e8">'+(val ? (val*currRate()).toFixed(4) : '\u2014')+' '+currSym()+'/h</span>'
      +'</div>';
    panel.appendChild(card);
  });

  // Légende couleurs
  const hmLeg = document.getElementById('hmLegend');
  if (hmLeg) hmLeg.innerHTML =
    '<span style="font-family:IBM Plex Mono,monospace;font-size:.6rem;color:#7bffe0">Moins cher</span>'
    +'<div style="width:120px;height:6px;border-radius:3px;background:linear-gradient(90deg,#7bffe0,#ffb400,#ff3355)"></div>'
    +'<span style="font-family:IBM Plex Mono,monospace;font-size:.6rem;color:#ff3355">Plus cher</span>';

  // Tableau régions
  const tbody2 = document.getElementById('hmRegionTableBody');
  if (tbody2) {
    const cloudColor = hmCloud === 'azure' ? '#00aaff' : '#ff9900';
    const allRegsData = hmCloud === 'azure'
      ? (hmService === 'bdd' ? BDD_ALL_REGIONS : AZURE_ALL_REGIONS)
      : (hmService === 'rds' ? RDS_ALL_REGIONS : AWS_ALL_REGIONS);
    const CITY_COORDS_ref = typeof CITY_COORDS !== 'undefined' ? CITY_COORDS : {};
    // Tableau : toutes régions connues, sans filtre, tri stable par colonne
    const allTableRegs = Object.keys(allRegsData).filter(r => CITY_COORDS[r] && regionMedians[r]);
    const sortedForTable = [...allTableRegs].sort((a, b) => {
      const ca = CITY_COORDS_ref[a] || {}, cb = CITY_COORDS_ref[b] || {};
      let va, vb;
      if (hmSortCol === 'label') { va=(ca.label||a).toLowerCase(); vb=(cb.label||b).toLowerCase(); return hmSortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va); }
      if (hmSortCol === 'reg')   { va=a.toLowerCase(); vb=b.toLowerCase(); return hmSortDir==='asc'?va.localeCompare(vb):vb.localeCompare(va); }
      if (hmSortCol === 'avail') { va=(allRegsData[a]||[]).filter(d => !fam||d.fam===fam).length; vb=(allRegsData[b]||[]).filter(d => !fam||d.fam===fam).length; }
      else if (hmSortCol === 'maxcost') { va=(regionMinMax[a]&&regionMinMax[a].max)||0; vb=(regionMinMax[b]&&regionMinMax[b].max)||0; }
      else if (hmSortCol === 'carbon')  { va=(CARBON_DATA[a]&&CARBON_DATA[a].co2)||999; vb=(CARBON_DATA[b]&&CARBON_DATA[b].co2)||999; }
      else                       { va=regionMedians[a]||0; vb=regionMedians[b]||0; }
      return hmSortDir==='asc'?va-vb:vb-va;
    });
    const cheapestVal2 = allTableRegs.reduce((m,r) => Math.min(m, regionMedians[r]||Infinity), Infinity) || 1;

    // Calculer le max d'instances sur toutes les régions (sans filtre)
    const counts = {};
    sortedForTable.forEach(reg => {
      counts[reg] = (allRegsData[reg] || []).filter(d => !fam || d.fam === fam).length;
    });
    const maxCount = Math.max(...Object.values(counts), 1);

    tbody2.innerHTML = sortedForTable.map((reg, i) => {
      const c = CITY_COORDS[reg];
      const tbl = regionMediansTable[reg];
      const val = regionMedians[reg] || null;
      const avail = counts[reg];
      const pct = Math.round(avail / maxCount * 100);
      const isCheap = val === cheapestVal2;
      return '<tr style="background:'+(i%2?'#0d0f15':'var(--bg)')+'">'
        + '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;font-family:IBM Plex Mono,monospace;font-size:.85rem">'
        + '<span style="color:#c8d0e8">'+c.label+'</span>'

        + '</td>'
        + '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;font-family:IBM Plex Mono,monospace;font-size:.75rem;color:#c8d0e8">'+reg+'</td>'
        + '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;font-family:IBM Plex Mono,monospace;font-size:.85rem">'
        + '<div style="display:flex;align-items:center;gap:10px">'
        + '<span style="color:#c8d0e8;font-weight:700;min-width:28px;text-align:right">'+avail+'</span>'
        + '<div style="flex:1;max-width:70%;background:#1e2535;border-radius:3px;height:4px"><div style="width:'+pct+'%;height:100%;background:linear-gradient(90deg,rgba('+( hmCloud==='azure'?'0,170,255':'255,153,0')+',0.1),'+cloudColor+');border-radius:3px"></div></div>'
        + '<span style="color:#c8d0e8;font-size:.72rem;min-width:34px">'+pct+'%</span>'
        + '</div>'
        + '</td>'
        + '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;text-align:left;font-family:IBM Plex Mono,monospace;font-size:.85rem">'
        + (val ? '<span style="color:'+cloudColor+';font-weight:700">'+f4(val*(periodMult[period]||1))+' '+currSym()+'</span>' : '<span style="color:#3a3f55">—</span>')
        + '</td>'
        + '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;text-align:left;font-family:IBM Plex Mono,monospace;font-size:.85rem">'
        + (function(){ const mm = regionMinMax[reg]; return mm && mm.max ? '<span style="color:#c8d0e8;font-weight:700">'+f4(mm.max*(periodMult[period]||1))+' '+currSym()+'</span>'+(mm.maxInst?'<span style="color:#c8d0e8;font-size:.72rem;margin-left:4px">('+mm.maxInst+')</span>':'') : '<span style="color:#3a3f55">—</span>'; })()
        + '</td>'
        + (function(){
            const cd = CARBON_DATA[reg];
            if (!cd) return '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;font-family:IBM Plex Mono,monospace;font-size:.85rem"><span style="color:#3a3f55">—</span></td>';
            const co2 = cd.co2;
            const col = co2 < 100 ? '#1D9E75' : co2 < 300 ? '#BA7517' : '#E24B4A';
            const pct = Math.min(100, Math.round(co2/5));
            return '<td style="padding:10px 16px;border-bottom:1px solid #1c2030;font-family:IBM Plex Mono,monospace;font-size:.85rem">'
              + '<div style="display:flex;align-items:center;gap:6px">'
              + '<div style="flex:1;max-width:70%;background:#1e2535;border-radius:3px;height:6px"><div style="width:'+pct+'%;height:100%;background:linear-gradient(90deg,'+(co2<100?'rgba(29,158,117,0.15)':co2<300?'rgba(186,117,23,0.15)':'rgba(226,75,74,0.15)')+','+col+');border-radius:3px"></div></div>'
              + '<span style="color:#c8d0e8;font-weight:700;min-width:36px;text-align:right">'+co2+' <span style="font-size:.65rem;color:#c8d0e8">gCO2/kWh</span></span>'
              + '</div></td>';
          })()
        + '</tr>';
    }).join('');
  // Mettre à jour les icônes de tri du tableau heatmap
  ;['label','reg','avail','cost','maxcost','carbon'].forEach(k => {
    const el = document.getElementById('hsi-' + k);
    if (!el) return;
    const active = hmSortCol === k;
    el.style.color = active ? '#7bffe0' : '#3a3f55';
    el.innerHTML   = active ? (hmSortDir === 'asc' ? '&#x2191;' : '&#x2193;') : '&#x2195;';
    el.className   = active ? 'sort-ico active-ico' : 'sort-ico';
  });
  }

}

function showBackBtn(show) {
  const btn = document.getElementById('backBtn');
  if (btn) btn.style.display = show ? 'inline-flex' : 'none';
}

function goBack() {
  if (heatmapActive)          { setHeatmap(); }
  else if (veilleActive)      { setVeille(); }
  else if (tcoActive)         { setTco(); }
  // Garantir que topNav est toujours interactif après retour
  const topNav = document.getElementById('topbarNav');
  if (topNav) { topNav.style.opacity = '1'; topNav.style.pointerEvents = ''; }
}


// Info-bulles colonnes
document.addEventListener('mousemove', function(e) {
  const tip = document.getElementById('colInfoTooltip');
  if (!tip) return;
  const el = e.target.closest('.col-info');
  if (!el) { tip.style.display = 'none'; return; }
  tip.innerHTML = (el.dataset.tip||'').replace(/\|/g,'<br>');
  tip.style.top  = (e.clientY + 14) + 'px';
  tip.style.left = Math.min(e.clientX, window.innerWidth - 296) + 'px';
  tip.style.display = 'block';
});

// Diagnostic disponibilité instances de référence
window.checkRefInstances = function() {
  const REF_AWS   = ['t3.medium','t3.large','m5.xlarge','m5.2xlarge','m6i.xlarge','m6i.2xlarge','c5.xlarge','r5.xlarge','m5.4xlarge','c6i.2xlarge'];
  const REF_AZURE = ['B2ms','B4ms','D2s v3','D4s v3','D2s v5','D4s v5','F2s v2','E2s v3','D8s v3','F4s v2'];
  const results = [];
  // AWS
  const _checkSrc = hmService === 'rds' ? RDS_ALL_REGIONS : AWS_ALL_REGIONS;
  Object.entries(_checkSrc).forEach(([reg, data]) => {
    const found = REF_AWS.filter(ref => data.some(d => d.iname === ref));
    const missing = REF_AWS.filter(ref => !data.some(d => d.iname === ref));
    results.push({cloud:'AWS', region:reg, found:found.length, missing});
  });
  // Azure
  Object.entries(AZURE_ALL_REGIONS).forEach(([reg, data]) => {
    const found = REF_AZURE.filter(ref => data.some(d => d.iname && d.iname.toLowerCase().replace('standard_','') === ref.toLowerCase()));
    const missing = REF_AZURE.filter(ref => !data.some(d => d.iname && d.iname.toLowerCase().replace('standard_','') === ref.toLowerCase()));
    results.push({cloud:'Azure', region:reg, found:found.length, missing});
  });
  console.table(results.map(r => ({
    Cloud: r.cloud, Region: r.region,
    'Found': r.found+'/10',
    'Missing': r.missing.join(', ') || '—'
  })));
  return results;
};
console.log('%c[CloudPrice] Run checkRefInstances() to verify reference instance availability', 'color:#7bffe0');

(async function() {
  const loader = document.getElementById('tableLoader');
  if (loader) loader.style.display = 'flex';
  try {
    const [awsAll, rdsAll, azureAll, bddAll, meta, carbon, eurData, veille] = await Promise.all([
      fetch('data/agregations/aws_regions.json').then(r => r.json()),
      fetch('data/agregations/rds_regions.json').then(r => r.json()),
      fetch('data/agregations/azure_regions.json').then(r => r.json()),
      fetch('data/agregations/bdd_regions.json').then(r => r.json()),
      fetch('data/agregations/regions_meta.json').then(r => r.json()),
      fetch('data/carbon.json').then(r => r.json()),
      fetch('data/eur_rate.json').then(r => r.json()),
      fetch('data/veille.json').then(r => r.json()),
    ]);
    AWS_ALL_REGIONS   = awsAll;
    RDS_ALL_REGIONS   = rdsAll;
    AZURE_ALL_REGIONS = azureAll;
    BDD_ALL_REGIONS   = bddAll;
    REGIONS_META       = meta.aws;
    AZURE_REGIONS_META = meta.azure;
    CARBON_DATA        = carbon;
    EUR_RATE           = eurData.rate || 0.92;
    VEILLE_DATA        = veille;
    AWS_DATA   = awsAll[currentRegion]        || [];
    AZURE_DATA = azureAll[currentAzureRegion] || [];
    RDS_DATA   = rdsAll[currentRegion]        || [];
    PSQL_DATA  = bddAll[currentAzureRegion]   || [];
  } catch(e) {
    console.error('[FinOpsMap] Erreur chargement données:', e);
    const tb = document.getElementById('tbody');
    if (tb) tb.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:40px;color:#ff5566">Erreur de chargement des données</td></tr>';
    return;
  } finally {
    if (loader) loader.style.display = 'none';
  }
  updateHmFamButtons();
  window._dataLoaded = true;
  setDefaultCols();
  loadFromURL();
  const tl = document.getElementById('topbarLeft'); if(tl) tl.style.opacity='1';
  (function(){ const tn = document.getElementById('topbarNav'); if(tn) tn.dataset.orig = tn.innerHTML; })();
  onPriceSlider();
  adjustLayout();
  (function() {
    function fixStickyRows() {
      const sortRow    = document.getElementById('sortRow');
      const filterRow  = document.getElementById('filterRow');
      const filtersBar = document.getElementById('filters');
      if (!sortRow || !filterRow) return;
      const filtersH = filtersBar ? filtersBar.getBoundingClientRect().height : 0;
      const sortH    = sortRow.getBoundingClientRect().height;
      sortRow.querySelectorAll('th').forEach(th => th.style.top = filtersH + 'px');
      filterRow.querySelectorAll('th').forEach(th => th.style.top = (filtersH + sortH) + 'px');
    }
    fixStickyRows();
    window.addEventListener('resize', fixStickyRows);
  })();
  document.getElementById('tbody').addEventListener('click', function(e) {
    if (!cmpMode) return;
    const tr = e.target.closest('tr[data-iname]');
    if (tr) toggleRow(tr.dataset.iname, tr.dataset.fam);
  });
})();
</script>
<div id="globalTip" class="score-tip"></div>
<div class="modal-overlay" id="seriesModal" onclick="if(event.target===this)closeSeriesModal()">
  <div class="modal-box">
    <div class="modal-hdr">
      <div class="modal-tabs">
        <button class="modal-tab active-aws" id="modalTabCard" onclick="switchModalTab('card')">Identity Card</button>
        <button class="modal-tab" id="modalTabSerie" onclick="switchModalTab('serie')">vs Série</button>
      </div>
      <button class="modal-close" onclick="closeSeriesModal()">&#x2715; Fermer</button>
    </div>
    <div class="modal-tab-content active" id="modalContentCard"></div>
    <div class="modal-tab-content" id="modalContentSerie">
      <table class="st" id="seriesTable"></table>
    </div>
  </div>
</div>
<div id="colInfoTooltip"></div>
</body>
</html>
"""

def get_family_rds(engine):
    e = engine.lower()
    if 'aurora' in e and 'mysql' in e:    return 'aurora-mysql'
    if 'aurora' in e and 'postgres' in e: return 'aurora-pg'
    if 'mysql' in e:    return 'mysql'
    if 'postgres' in e: return 'postgresql'
    if 'oracle' in e:   return 'oracle'
    if 'sql server' in e or 'sqlserver' in e: return 'sqlserver'
    if 'mariadb' in e:  return 'mariadb'
    return 'other'

def fetch_rds(region="eu-west-3"):
    print("\nRDS " + region + " (~50MB, patience)...")
    conn = http.client.HTTPSConnection("pricing.us-east-1.amazonaws.com", timeout=120)
    conn.request("GET", "/offers/v1.0/aws/AmazonRDS/current/" + region + "/index.json",
                 headers={"User-Agent": "cloudprice/1.0", "Accept-Encoding": "gzip"})
    r = conn.getresponse()
    if r.status != 200:
        raise Exception("RDS HTTP " + str(r.status))
    raw = r.read()
    conn.close()
    log("telecharge " + str(round(len(raw)/1024/1024, 1)) + " MB")
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
        log("decompresse " + str(round(len(raw)/1024/1024, 1)) + " MB")
    data     = json.loads(raw)
    products = data.get("products", {})
    terms_od = (data.get("terms") or {}).get("OnDemand", {})
    terms_ri = (data.get("terms") or {}).get("Reserved", {})

    # Index SKU -> attributs pour les Reserved
    sku_to_attr = {}
    for sku, prod in products.items():
        attr = prod.get("attributes", {})
        if attr.get("databaseEngine","").strip() == "": continue
        if "windows" in attr.get("databaseEngine","").lower(): continue
        if attr.get("deploymentOption","") != "Single-AZ": continue
        itype = attr.get("instanceType","")
        if not itype or not itype.startswith("db."): continue
        sku_to_attr[sku] = attr

    result = {}
    for sku, attr in sku_to_attr.items():
        itype  = attr.get("instanceType","")
        engine = attr.get("databaseEngine","")
        deploy = attr.get("deploymentOption","")
        # On-Demand
        price = None
        for term in terms_od.get(sku, {}).values():
            for pd in term.get("priceDimensions", {}).values():
                try:
                    p = float(pd["pricePerUnit"]["USD"])
                    if p > 0: price = p; break
                except: pass
            if price: break
        if not price: continue
        # Reserved Standard No Upfront + All Upfront
        price_1yr_no = None; price_3yr_no = None
        price_1yr_all = None; price_3yr_all = None
        for term in (terms_ri.get(sku) or {}).values():
            ta = term.get("termAttributes", {})
            if ta.get("OfferingClass") != "standard": continue
            purchase = ta.get("PurchaseOption", "")
            if purchase not in ("No Upfront", "All Upfront"): continue
            lease = ta.get("LeaseContractLength","")
            hours = 8760 if lease == "1yr" else 26280
            if purchase == "No Upfront":
                p_ri = None
                for pd in term.get("priceDimensions",{}).values():
                    try:
                        p = float(pd["pricePerUnit"]["USD"])
                        if p > 0: p_ri = p; break
                    except: pass
                if p_ri is None: continue
                if lease == "1yr" and (price_1yr_no is None or p_ri < price_1yr_no): price_1yr_no = p_ri
                if lease == "3yr" and (price_3yr_no is None or p_ri < price_3yr_no): price_3yr_no = p_ri
            elif purchase == "All Upfront":
                upfront_total = 0.0
                for pd in term.get("priceDimensions",{}).values():
                    try:
                        p = float(pd["pricePerUnit"]["USD"])
                        unit = pd.get("unit","").lower()
                        if unit == "quantity":
                            upfront_total += p
                    except: pass
                p_ri = round(upfront_total / hours, 6) if upfront_total > 0 else None
                if p_ri is None: continue
                if lease == "1yr" and (price_1yr_all is None or p_ri < price_1yr_all): price_1yr_all = p_ri
                if lease == "3yr" and (price_3yr_all is None or p_ri < price_3yr_all): price_3yr_all = p_ri
        try:
            vcpu = int(attr.get("vcpu",0) or 0)
            ram  = float((attr.get("memory") or "0").split()[0].replace(",","") or 0)
        except: continue
        fam   = get_family_rds(engine)
        key   = itype + "||" + deploy + "||" + fam  # normaliser sur fam, pas engine brut
        processor = attr.get("physicalProcessor", "")
        network   = attr.get("networkPerformance", "")
        entry     = {"name": itype, "price": price, "vcpu": vcpu, "ram": ram,
                 "fam": fam, "engine": engine, "deploy": deploy, "processor": processor, "network": network}
        if price_1yr_no:  entry["price_1yr"]     = price_1yr_no
        if price_3yr_no:  entry["price_3yr"]     = price_3yr_no
        if price_1yr_all: entry["price_1yr_all"] = price_1yr_all
        if price_3yr_all: entry["price_3yr_all"] = price_3yr_all
        if key not in result or price < result[key]["price"]:
            result[key] = entry
    # Déduplication finale par (name, fam) — garder le moins cher
    dedup = {}
    for k, v in result.items():
        dk = v['name'] + '||' + v['fam']
        if dk not in dedup or v['price'] < dedup[dk]['price']:
            dedup[dk] = v
    result = dedup
    log(str(len(result)) + ' instances RDS trouvees')
    ri_1yr = sum(1 for v in result.values() if v.get("price_1yr"))
    ri_3yr = sum(1 for v in result.values() if v.get("price_3yr"))
    log("RDS Reserved 1yr : " + str(ri_1yr) + "  3yr : " + str(ri_3yr))
    return result


def generate_html(aws_data, azure_data, rds_data, fetch_date, psql_data=None, aws_regions_data=None, azure_regions_data=None, bdd_regions_data=None, veille_data=None, rds_regions_data=None, carbon_data=None, eur_rate=0.92):
    def ri3(v):
        d = {}
        if v.get("price_1yr"):     d["price_1yr"]     = v["price_1yr"]
        if v.get("price_3yr"):     d["price_3yr"]     = v["price_3yr"]
        if v.get("price_1yr_all"): d["price_1yr_all"] = v["price_1yr_all"]
        if v.get("price_3yr_all"): d["price_3yr_all"] = v["price_3yr_all"]
        return d
    def spot3(v):
        d = {}
        if v.get("spot"): d["spot"] = v["spot"]
        return d
    aws_list   = [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "storage": v.get("storage",""), "processor": v.get("processor",""), "network": v.get("network",""), **ri3(v), **spot3(v)} for v in sorted(aws_data.values(),   key=lambda x: x["price"])]
    azure_list = [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "storage": v.get("storage",""), "processor": v.get("processor",""), "network": v.get("network",""), "max_disks": v.get("max_disks",0), "disk_iops": v.get("disk_iops",0), **ri3(v)} for v in sorted(azure_data.values(), key=lambda x: x["price"])]
    rds_list   = [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "engine": v.get("engine",""), "deploy": v.get("deploy",""), "processor": v.get("processor",""), "network": v.get("network",""), **ri3(v)} for v in sorted(rds_data.values(), key=lambda x: x["price"])]
    psql_data  = psql_data or {}
    psql_list  = [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "engine": v.get("engine",""), "sku": v.get("sku",""), **ri3(v)} for v in sorted(psql_data.values(), key=lambda x: x["price"])]

    def to_list(d):     return [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "storage": v.get("storage",""), "processor": v.get("processor",""), "network": v.get("network",""), "max_disks": v.get("max_disks",0), "disk_iops": v.get("disk_iops",0), **ri3(v), **spot3(v)} for v in sorted(d.values(), key=lambda x: x["price"])]
    def to_list_bdd(d): return [{"iname": v["name"], "price": v["price"], "vcpu": v["vcpu"], "ram": v["ram"], "fam": v["fam"], "engine": v.get("engine",""), "sku": v.get("sku",""), **ri3(v)} for v in sorted(d.values(), key=lambda x: x["price"])]

    aws_regions_data   = aws_regions_data   or {}
    azure_regions_data = azure_regions_data or {}
    bdd_regions_data   = bdd_regions_data   or {}

    aws_all_regions   = {r: to_list(d)     for r, d in aws_regions_data.items()}
    rds_regions_data  = rds_regions_data or {}
    rds_all_regions   = {r: to_list(d)     for r, d in rds_regions_data.items()}
    azure_all_regions = {r: to_list(d)     for r, d in azure_regions_data.items()}
    bdd_all_regions   = {r: to_list_bdd(d) for r, d in bdd_regions_data.items()}

    aws_regions_meta   = {k: {"label": v["label"], "flag": v["flag"]} for k, v in AWS_REGIONS.items()}
    azure_regions_meta = {k: {"label": v["label"], "flag": v["flag"]} for k, v in AZURE_REGIONS.items()}

    # Écrire les fichiers JSON agrégés pour chargement côté client
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    with open(os.path.join(data_dir, "agregations", "aws_regions.json"), "w", encoding="utf-8") as f:
        json.dump(aws_all_regions, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "agregations", "rds_regions.json"), "w", encoding="utf-8") as f:
        json.dump(rds_all_regions, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "agregations", "azure_regions.json"), "w", encoding="utf-8") as f:
        json.dump(azure_all_regions, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "agregations", "bdd_regions.json"), "w", encoding="utf-8") as f:
        json.dump(bdd_all_regions, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "agregations", "regions_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"aws": aws_regions_meta, "azure": azure_regions_meta}, f, ensure_ascii=False)

    veille_data = veille_data or []
    carbon_data = carbon_data or {}

    # Lire les libs embarquées
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
    def read_lib(fname, is_json=False):
        p = os.path.join(lib_dir, fname)
        if not os.path.exists(p):
            log("ATTENTION lib manquante : " + fname + " — relancez le script avec connexion internet")
            return "null" if is_json else "/* lib manquante */"
        with open(p, "rb") as f:
            raw = f.read()
        return raw.decode("utf-8", errors="replace")

    world_topo   = read_lib("countries-110m.json", is_json=True)

    # Agrège les données disques par région
    disk_regions = {}
    for reg in AWS_REGIONS:
        fp = os.path.join(DATA_DIR_AWS, "disk-" + reg + ".json")
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                disk_regions[reg] = json.load(f)

    html = HTML_TEMPLATE
    html = html.replace("%%FETCH_DATE%%",          fetch_date)
    html = html.replace("%%WORLD_TOPO%%",          world_topo)
    html = html.replace("%%DISK_REGIONS%%",        json.dumps(disk_regions))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8", errors="surrogatepass") as f:
        f.write(html)
    return out

def fetch_libs():
    """Télécharge topojson.min.js et countries-110m.json dans ./lib/ si absent."""
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
    os.makedirs(lib_dir, exist_ok=True)

    files = [
        ("cdnjs.cloudflare.com", "/ajax/libs/topojson/3.0.2/topojson.min.js",  "topojson.min.js"),
        ("cdnjs.cloudflare.com", "/ajax/libs/d3/7.8.5/d3.min.js",             "d3.min.js"),
        ("cdn.jsdelivr.net",     "/npm/world-atlas@2/countries-110m.json",     "countries-110m.json"),
    ]
    for host, path, fname in files:
        dest = os.path.join(lib_dir, fname)
        if os.path.exists(dest):
            log("lib deja presente : " + fname)
            continue
        print("  Telechargement " + fname + "...")
        try:
            conn = http.client.HTTPSConnection(host, timeout=30)
            conn.request("GET", path, headers={"User-Agent": "cloudprice/1.0"})
            r = conn.getresponse()
            if r.status != 200:
                raise Exception("HTTP " + str(r.status))
            data = r.read()
            conn.close()
            with open(dest, "wb") as f:
                f.write(data)
            log("sauvegarde -> " + dest + " (" + str(round(len(data)/1024)) + " KB)")
        except Exception as e:
            log("Erreur telechargement " + fname + " : " + str(e))


def main():
    now = datetime.now()
    fetch_date = "{}/{}/{} · {}:{:02d} {}".format(
        now.month, now.day, now.year,
        now.hour % 12 or 12, now.minute,
        "AM" if now.hour < 12 else "PM"
    )
    print("=" * 42)
    print("  CloudPrice - Telechargeur de tarifs")
    print("=" * 42)

    print("\nTelechargement libs cartographie...")
    fetch_libs()

    # ── RDS : toutes les régions ──
    rds_regions_data = {}
    for region in AWS_REGIONS:
        rds_file = os.path.join(DATA_DIR_AWS, "rds-" + region + ".json")
        if is_fresh(rds_file):
            log("cache frais utilise : " + rds_file)
            with open(rds_file, encoding="utf-8") as f: rds_regions_data[region] = json.load(f)
            continue
        try:
            data = fetch_rds(region)
            with open(rds_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            log("sauvegarde -> " + rds_file)
            rds_regions_data[region] = data
        except Exception as e:
            print("  Erreur RDS " + region + " : " + str(e))
            if os.path.exists(rds_file):
                log("cache utilise : " + rds_file)
                with open(rds_file, encoding="utf-8") as f: rds_regions_data[region] = json.load(f)
            else:
                rds_regions_data[region] = {}
    rds_data = rds_regions_data.get("eu-west-3", {})

    # ── Azure SKUs (specs hardware) — un appel par région, cache 30j ──
    azure_skus_by_region = {}
    # Vérifier si au moins une région a besoin de rafraîchir les SKUs
    _need_skus_refresh = any(
        not is_fresh(os.path.join(DATA_DIR_AZ, "skus-" + r + ".json"), days=SKUS_CACHE_DAYS)
        for r in AZURE_REGIONS
    )
    _az_available = True
    if _need_skus_refresh:
        try:
            subprocess.run(["az", "account", "show", "--query", "id", "-o", "tsv"],
                           capture_output=True, text=True, timeout=15, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            _az_available = False
            log("az CLI non disponible ou token expiré — les specs Azure (RAM, network, processor) utiliseront le cache ou les estimations. Lancez 'az login' pour rafraîchir.")
    for region in AZURE_REGIONS:
        azure_skus_by_region[region] = fetch_azure_skus(region, az_available=_az_available)

    # ── Azure VM : toutes les régions ──
    azure_regions_data = {}
    for region in AZURE_REGIONS:
        skus = azure_skus_by_region.get(region, {})
        az_file = os.path.join(DATA_DIR_AZ, "vm-" + region + ".json")
        if is_fresh(az_file):
            log("cache frais utilise : " + az_file)
            with open(az_file, encoding="utf-8") as f: cached = json.load(f)
            # Enrichir les données en cache avec les SKUs si disponibles
            for key, vm in cached.items():
                meta = skus.get(key) or skus.get(key.replace("_", " "), {}) if skus else {}
                if meta:
                    vm["vcpu"]      = meta.get("vcpu", vm.get("vcpu", 0))
                    vm["ram"]       = meta.get("ram", vm.get("ram", 0))
                    vm["storage"]   = meta.get("storage", "")
                    vm["network"]   = meta.get("network", "")
                    vm["processor"] = meta.get("processor", "")
                    vm["max_disks"] = meta.get("max_disks", 0)
                    vm["disk_iops"] = meta.get("disk_iops", 0)
                # Déduire le processor si toujours absent
                if not vm.get("processor"):
                    kn = key.lower().replace(" ", "").replace("_", "")
                    base = re.sub(r'v\d+$', '', kn).rstrip()
                    letters = re.sub(r'\d+', '', base)
                    if 'p' in letters[1:]:
                        vm["processor"] = "Arm64 (Ampere)"
                    elif 'a' in letters[1:]:
                        vm["processor"] = "AMD"
                    else:
                        vm["processor"] = "Intel"
            azure_regions_data[region] = cached
            continue
        try:
            data = fetch_azure(region, skus=skus)
            with open(az_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            log("sauvegarde -> " + az_file)
            azure_regions_data[region] = data
        except Exception as e:
            print("  Erreur Azure VM " + region + " : " + str(e))
            if os.path.exists(az_file):
                log("cache utilise : " + az_file)
                with open(az_file, encoding="utf-8") as f: azure_regions_data[region] = json.load(f)
            else:
                azure_regions_data[region] = {}
    azure_data = azure_regions_data.get("francecentral", {})

    # ── Azure BDD : toutes les régions ──
    bdd_regions_data = {}
    for region in AZURE_REGIONS:
        bdd_file = os.path.join(DATA_DIR_AZ, "bdd-" + region + ".json")
        if is_fresh(bdd_file):
            log("cache frais utilise : " + bdd_file)
            with open(bdd_file, encoding="utf-8") as f: bdd_regions_data[region] = json.load(f)
            continue
        try:
            data = fetch_azure_bdd(region)
            with open(bdd_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            log("sauvegarde -> " + bdd_file)
            bdd_regions_data[region] = data
        except Exception as e:
            print("  Erreur Azure BDD " + region + " : " + str(e))
            if os.path.exists(bdd_file):
                log("cache utilise : " + bdd_file)
                with open(bdd_file, encoding="utf-8") as f: bdd_regions_data[region] = json.load(f)
            else:
                bdd_regions_data[region] = {}
    psql_data = bdd_regions_data.get("francecentral", {})

    # ── AWS EC2 : toutes les régions ──
    aws_regions_data = {}
    for region in AWS_REGIONS:
        aws_file = os.path.join(DATA_DIR_AWS, "ec2-" + region + ".json")
        if is_fresh(aws_file):
            log("cache frais utilise : " + aws_file)
            with open(aws_file, encoding="utf-8") as f: aws_regions_data[region] = json.load(f)
            continue
        try:
            data = fetch_aws(region)
            with open(aws_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            log("sauvegarde -> " + aws_file)
            aws_regions_data[region] = data
        except Exception as e:
            print("  Erreur AWS " + region + " : " + str(e))
            if os.path.exists(aws_file):
                log("cache utilise : " + aws_file)
                with open(aws_file, encoding="utf-8") as f: aws_regions_data[region] = json.load(f)
            else:
                aws_regions_data[region] = {}
    aws_data = aws_regions_data.get("eu-west-3", {})

    # ── AWS Spot : toutes les régions ──
    for region in AWS_REGIONS:
        spot_prices = fetch_spot_aws(region)
        for iname, sp in spot_prices.items():
            if iname in aws_regions_data.get(region, {}):
                aws_regions_data[region][iname]["spot"] = sp
    # Refresh aws_data after spot enrichment
    aws_data = aws_regions_data.get("eu-west-3", {})

    # ── AWS EBS : toutes les régions ──
    for region in AWS_REGIONS:
        disk_file = os.path.join(DATA_DIR_AWS, "disk-" + region + ".json")
        if is_fresh(disk_file):
            log("cache frais utilise : " + disk_file)
            continue
        try:
            data = fetch_ebs(region)
            with open(disk_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            log("sauvegarde -> " + disk_file)
        except Exception as e:
            print("  Erreur EBS " + region + " : " + str(e))
            if os.path.exists(disk_file):
                log("cache utilise : " + disk_file)

    print("\nGeneration index.html...")
    veille_data  = fetch_veille()
    carbon_data  = fetch_carbon()
    eur_rate     = fetch_eur_rate()
    html_path = generate_html(aws_data, azure_data, rds_data, fetch_date, psql_data, aws_regions_data, azure_regions_data, bdd_regions_data, veille_data, rds_regions_data, carbon_data, eur_rate)
    log("genere -> " + html_path)
    print("\nTermine ! Ouvrez : " + html_path + "\n")

if __name__ == "__main__":
    main()
