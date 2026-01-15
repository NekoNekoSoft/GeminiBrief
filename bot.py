import os
import asyncio
import requests
import time
import re
from datetime import datetime
import pytz
from telegram import Bot
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

# 1. 환경변수 설정
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()

# 텔레그램 속보 채널 (FinancialJuice, WalterBloomberg)
TELEGRAM_CHANNEL_URLS = [
    "https://t.me/s/FinancialJuice",
    "https://t.me/s/WalterBloomberg"
]

# 7개의 API 키 로드
API_KEYS = [
    os.environ.get('GEMINI_API_KEY'),
    os.environ.get('GEMINI_API_KEY_2'),
    os.environ.get('GEMINI_API_KEY_3'),
    os.environ.get('GEMINI_API_KEY_4'),
    os.environ.get('GEMINI_API_KEY_5'),
    os.environ.get('GEMINI_API_KEY_6'),
    os.environ.get('GEMINI_API_KEY_7')
]
# 비어있는 키 제거
API_KEYS = [k.strip() for k in API_KEYS if k]

# 2. 한국 시간 구하기 (로그 및 보고서용)
def get_korea_time_str():
    korea_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(korea_tz)
    return now.strftime("%Y년 %m월 %d일 %H시 %M분")

# 3. 모델 찾기 (첫 번째 키로 헬스 체크)
def get_working_model():
    if not API_KEYS: return "models/gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEYS[0]}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                if 'generateContent' in m['supportedGenerationMethods']:
                    return m['name']
    except:
        pass
    return "models/gemini-1.5-flash"

# 4-1. 뉴스 검색 (VIX 및 레버리지 리스크 감시 강화)
def get_ddg_news():
    results = []
    # ★ 비판적 분석을 위한 검색어 구성 ★
    keywords = [
        "US stock market breaking news impact",   # 전체 시황
        "CBOE VIX index market volatility news",  # ★ 공포지수 (레버리지 투자자 필수)
        "Pure Storage stock latest analysis",     # PSTG
        "SPHD ETF latest dividend news",          # SPHD
        "S&P 500 VOO forecast analysis"           # VOO (SSO/UPRO의 기초자산)
    ]
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    news_gen = ddgs.news(keyword, max_results=1)
                    for r in news_gen:
                        # 출처(WEB) 표기
                        text = f"[WEB] {r['title']} ({r['date']}): {r['body'][:300]}"
                        results.append(text)
                except:
                    continue
    except:
        pass
    return results

# 4-2. 텔레그램 정밀 분석 (속보 채널)
def get_telegram_news():
    collected_list = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in TELEGRAM_CHANNEL_URLS:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                messages = soup.find_all('div', class_='tgme_widget_message_wrap')
                if not messages: continue

                # 최신 메시지 5개 분석
                recent_msgs = messages[-5:] 
                
                channel_name = url.split('/')[-1]
                
                for msg in recent_msgs:
                    text_div = msg.find('div', class_='tgme_widget_message_text')
                    if not text_div: continue
                    text = text_div.get_text(separator=" ", strip=True)
                    
                    time_tag = msg.find('time')
                    msg_time = time_tag['datetime'] if time_tag else ""
                    
                    # 너무 짧은 텍스트 제외
                    if len(text) > 5:
                        full_msg = f"[Telegram:{channel_name}] [{msg_time}] {text}"
                        collected_list.append(full_msg)
        except:
            continue
            
    return collected_list

# 5. 스마트 필터링 (중복 뉴스 제거)
def filter_new_items(current_items):
    log_file = "news_log.txt"
    old_items = set()
    
    # 기존 기록 로드
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                old_items.add(line.strip())
    
    # 새로운 뉴스만 추출 (차집합)
    new_items = []
    for item in current_items:
        clean_item = item.strip()
        if clean_item not in old_items:
            new_items.append(clean_item)
    
    # 현재 상태 저장 (다음 비교를 위해 덮어쓰기)
    with open(log_file, "w", encoding="utf-8") as f:
        for item in current_items:
            f.write(item.strip() + "\n")
            
    return new_items

# 6. 제미나이 요청 (7-Key 로테이션 시스템)
def ask_gemini(model_name, prompt):
    for i, key in enumerate(API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={key}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                # 실패 시 1초 대기 후 다음 키 시도
                time.sleep(1)
                continue
        except:
            continue
    return "❌ 모든 API 키 요청 실패 (서버 혼잡 또는 키 오류)"

# 7. 메인 실행 함수
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    current_time = get_korea_time_str()
    
    # 1) 데이터 수집
    web_list = get_ddg_news()
    telegram_list = get_telegram_news()
    all_current_list = web_list + telegram_list
    
    if not all_current_list:
        print("수집된 데이터가 없습니다.")
        return

    # 2) 필터링 (새로운 뉴스만 골라내기)
    real_new_news = filter_new_items(all_current_list)
    
    # 새로운 뉴스가 하나도 없으면 종료
    if not real_new_news:
        print("🔍 확인 결과: 모든 뉴스가 지난번과 동일합니다. (전송 생략)")
        return 

    # 3) 브리핑 생성 요청
    print(f"✨ 새로운 소식 {len(real_new_news)}건 발견! 분석 시작.")
    combined_data = "\n".join(real_new_news)

    # ★ 비판적 분석 및 레버리지 리스크 경고 프롬프트 ★
    prompt = f"""
    [Role] 월스트리트 수석 매크로 전략가 (냉철한 리스크 관리자)
    [Current Time] {current_time} (KST)
    [User Portfolio]
    - Core: VOO (1x)
    - Satellite: PSTG (Growth), SPHD (Dividend)
    - **Leverage (High Risk): SSO (2x), UPRO (3x)**
    
    [New Input Data]
    {combined_data}
    
    [Instruction]
    위 데이터를 바탕으로 **냉정하고 객관적으로** 브리핑하라.
    특히 레버리지(SSO, UPRO) 보유자에게는 **단순 등락보다 '변동성(Volatility)' 위험**을 경고해야 한다.
    무조건적인 긍정은 지양하고, 하락 가능성과 리스크를 명확히 짚어라.
    
    1. **Breaking Insight**: 텔레그램 속보/웹 뉴스의 핵심과 시장 함의.
    2. **Portfolio Risk Check**:
       - **VOO/SSO/UPRO**: 시장 방향성뿐만 아니라 **VIX(변동성) 확대로 인한 레버리지 손실 위험**이 감지되는가?
       - **PSTG/SPHD**: 개별 호재/악재 체크.
    3. **Cold Reality**: 지금은 '변동성 장세'인가 '추세 상승장'인가? 대응 전략은?
    
    [Output Structure]
    🔔 **New Market Alert** ({current_time})
    
    **1. ⚡ Breaking Insight**
    * (속보 해석 및 시장 분위기)
    
    **2. ⚠️ Leverage & Portfolio Risk**
    * (SSO/UPRO 투자자가 주의해야 할 변동성/금리 이슈 집중 분석)
    * (PSTG/SPHD 관련 특이사항)
    
    **3. 💡 Cold Reality (냉정한 조언)**
    * (희망 회로 배제한 객관적 리스크 진단 및 대응책)
    """
    
    print("브리핑 생성 중...")
    msg = ask_gemini(model_name, prompt)

    # 텔레그램 전송
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    except:
        # 마크다운 에러 시 일반 텍스트로 재시도
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    
    print("전송 성공!")

if __name__ == "__main__":
    asyncio.run(main())
