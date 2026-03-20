import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_orig_get = requests.get
def _patched_get(*args, **kwargs):
    kwargs['verify'] = False
    return _orig_get(*args, **kwargs)
requests.get = _patched_get
import os
import sys

# Windows 콘솔에서 이모지 출력 시 발생하는 인코딩 에러 방지용
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ==========================================
# 🛑 아래 4가지 변수를 본인 피그마 정보로 변경하세요!
# ==========================================
FIGMA_TOKEN = "fig"
FILE_KEY = "VdhL71dZBwFoqFeuPCuG1l"

# 추출할 3개 페이지(프레임)의 노드 아이디 (예: "12:345")
PAGE_1_NODE_ID = "1:2"
PAGE_2_NODE_ID = "1:201"
PAGE_3_NODE_ID = "1:620"
# ==========================================

HEADERS = {
    "X-Figma-Token": FIGMA_TOKEN
}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 저장 완료: {filename}")

def download_image(url, filename):
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)
    print(f"🖼️ 이미지 다운로드 완료: {filename}")

def main():
    print("🚀 Figma 데이터 추출을 시작합니다...\n")

    # 1. 전체 파일 JSON 다운로드
    print("1️⃣ 전체 파일 JSON 가져오는 중...")
    res_full = requests.get(f"https://api.figma.com/v1/files/{FILE_KEY}", headers=HEADERS)
    save_json("figma-full-file.json", res_full.json())

    # 전체 JSON에서 폰트 목록 간단히 뽑아내서 저장 (5번 요구사항)
    try:
        fonts_used = res_full.json().get("document", {}).get("usedFonts", [])
        if fonts_used:
             save_json("figma-used-fonts.json", fonts_used)
    except Exception as e:
        print("폰트 정보 추출 실패:", e)

    # 2. 1/2/3 페이지 개별 JSON 다운로드 (geometry=paths 포함)
    page_nodes = {
        "figma-page-1.json": PAGE_1_NODE_ID,
        "figma-page-2.json": PAGE_2_NODE_ID,
        "figma-page-3.json": PAGE_3_NODE_ID,
    }
    
    print("\n2️⃣ 페이지별 개별 노드 JSON 가져오는 중...")
    for filename, node_id in page_nodes.items():
        if node_id:
            res_node = requests.get(f"https://api.figma.com/v1/files/{FILE_KEY}/nodes?ids={node_id}&geometry=paths", headers=HEADERS)
            save_json(filename, res_node.json())

    # 3. 1/2/3 페이지 캡처 이미지 (PNG) 다운로드
    print("\n3️⃣ 페이지 PNG 캡처 이미지 링크 생성 중...")
    node_ids = ",".join([id for id in page_nodes.values() if id])
    res_images = requests.get(f"https://api.figma.com/v1/images/{FILE_KEY}?ids={node_ids}&format=png", headers=HEADERS)
    image_urls = res_images.json().get("images", {})
    
    if image_urls.get(PAGE_1_NODE_ID): download_image(image_urls[PAGE_1_NODE_ID], "figma-page-1.png")
    if image_urls.get(PAGE_2_NODE_ID): download_image(image_urls[PAGE_2_NODE_ID], "figma-page-2.png")
    if image_urls.get(PAGE_3_NODE_ID): download_image(image_urls[PAGE_3_NODE_ID], "figma-page-3.png")

    # 4. 이미지 자산 (Assets) 다운로드
    print("\n4️⃣ 문서 내 사용된 이미지 에셋들 가져오는 중...")
    os.makedirs("assets", exist_ok=True)
    res_assets = requests.get(f"https://api.figma.com/v1/files/{FILE_KEY}/images", headers=HEADERS)
    assets_meta = res_assets.json().get("meta", {}).get("images", {})
    
    for image_ref, url in assets_meta.items():
        download_image(url, f"assets/{image_ref}.png")

    print("\n🎉 모든 데이터 추출이 완료되었습니다! 현재 폴더를 확인해 보세요.")

if __name__ == "__main__":
    main()
