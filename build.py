import io
import os
from pathlib import Path
import zipfile

import requests

FIRA_CODE_VERSION = "6.2"
PRETENDARD_VERSION = "1.3.6"

CACHE_DIR = Path(os.path.dirname(os.path.realpath(__file__))) / ".cache"
FIRA_CODE_CACHE = CACHE_DIR / "fira"
PRETENDARD_CACHE = CACHE_DIR / "pretendard"

if not FIRA_CODE_CACHE.exists():
    print("Downloading Fira Code")
    os.makedirs(FIRA_CODE_CACHE)
    url = f"https://github.com/tonsky/FiraCode/releases/download/{FIRA_CODE_VERSION}/Fira_Code_v{FIRA_CODE_VERSION}.zip"
    response = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(FIRA_CODE_CACHE)

if not PRETENDARD_CACHE.exists():
    print("Downloading Pretendard")
    os.makedirs(PRETENDARD_CACHE)
    url = f"https://github.com/orioncactus/pretendard/releases/download/v{PRETENDARD_VERSION}/Pretendard-{PRETENDARD_VERSION}.zip"
    response = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(PRETENDARD_CACHE)

