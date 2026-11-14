from pathlib import Path
import requests
from pypdf import PdfReader

RAW_DIR = Path(__file__).parent/ "data" / "raw"
pdf_path = RAW_DIR / "round_02.pdf"

url = "https://resources.premierleague.pulselive.com/premierleague/document/2026/09/08/fb9baf79-2494-4e7a-b413-cdb8afb950ae/2026-27-KMI-Match-Round-2-decisions.pdf"

response = requests.get(url, timeout=30)
response.raise_for_status()  # Raise an exception for HTTP errors


with open(pdf_path, "wb") as f:
    f.write(response.content)

print("Saved", len(response.content), "bytes")


reader = PdfReader(pdf_path)
print(len(reader.pages), "pages")
for i, page in enumerate(reader.pages, start=1):
    text = page.extract_text()
    print(f"Page {i} has {len(text)} characters")
    print(text)