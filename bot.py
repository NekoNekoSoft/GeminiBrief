import os
import asyncio
import requests
import time
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
CHAT_ID = os.environ['TELEGRAM_CHAT_ID'].strip()
GEMINI_API_KEY = os.environ['GEMINI_API_KEY'].strip()

# 2. 모델 자동 찾기
def get_working_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
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

# 3. 뉴스 수집
def get_latest_news():
    print("뉴스 수집 중...")
    results = []
    
    keywords = [
        "Pure Storage AI data center trend", # PSTG
        "SPHD ETF dividend analysis",        # SPHD
        "S&P 500 market forecast today",     # VOO
        "US stock market breaking news today", # 시장 전체
        "Trending stocks US market today"    # 급등락
    ]
    
    try:
        with DDGS() as ddgs:
            for keyword in keywords:
                try:
                    news_gen = ddgs.news(keyword, max_results=2)
                    for r in news_gen:
                        full_text = f"[{keyword}] {r['title']} ({r['date']}): {r['body']}"
                        results.append(full_text)
                except:
                    continue
    except Exception as e:
        print(f"DDGS 접속 오류: {e}")
        return ""
    return "\n".join(results)

# 4. 제미나이 요청 (★ 재시도 기능 추가됨 ★)
def ask_gemini(model_name, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # 최대 3번까지 재시도
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=data)
            
            # 성공(200)하면 바로 결과 반환
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # 서버 과부하(503)면 잠시 대기 후 재시도
            elif response.status_code == 503:
                print(f"서버 혼잡... {attempt+1}번째 재시도 중...")
                time.sleep(5) # 5초 휴식
                continue
                
            else:
                return f"❌ 분석 실패: {response.text}"
                
        except Exception as e:
            print(f"연결 오류: {e}")
            time.sleep(5)
            continue
            
    return "❌ 서버가 너무 바빠서 3번 시도했지만 실패했습니다. 잠시 후 다시 시도해주세요."

# 5. 메인 실행
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    model_name = get_working_model()
    news_text = get_latest_news()
    
    if not news_text:
        news_text = "뉴스 수집 실패. 시황 브리핑 바람."

    prompt = f"""
    [Role] 월스트리트 수석 애널리스트
    [Portfolio] PSTG, SPHD, VOO
    [Input] {news_text}
    [Instruction]
    1. 🚨 메인 이슈 (Macro)
    2. 💼 내 포트폴리오 점검 (PSTG, SPHD)
    3. 🌍 그 외 놓치면 안 될 소식 (Trending)
    4. 💡 제미나이의 투자 한마디
    위 4단계로 브리핑해줘. 맥락(Context)과 영향(Impact) 위주로. 출처 필수.
    """
    
    print("보고서 작성 중...")
    msg = ask_gemini(model_name, prompt)

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        print("전송 성공!")
    except Exception as e:
        print(f"전송 실패: {e}")

if __name__ == "__main__":
    asyncio.run(main())
