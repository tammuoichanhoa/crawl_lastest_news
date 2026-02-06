import requests
from bs4 import BeautifulSoup

url = "https://baolangson.vn/hanh-trinh-hoi-nhap-bat-dau-tu-ren-luyen-5071654.html"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "vi,en;q=0.8",
}

resp = requests.get(url, headers=headers, timeout=30)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

# Lấy div nội dung chính
content_div = soup.find("div", id="content-detail")

if not content_div:
    print("Không tìm thấy div#content-detail")
else:
    paragraphs = content_div.find_all("p")
    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    print(text)
