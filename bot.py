import os
import asyncio
import requests
import json
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수 가져오기
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 2. 뉴스 검색 함수
def get_latest_news():
    print("뉴스 검색 중...")
    results = []
    with DDGS() as ddgs:
        keywords = ["US stock market news", "PSTG stock", "SPHD ETF", "S&P 500"]
        for keyword in keywords:
            try:
                search_results = ddgs.text(keyword, max_results=2)
                for r in search_results:
                    results.append(f"- {r['title']}: {r['body']}")
            except:
                continue
    return "\n".join(results) if results else "뉴스 검색 실패"

# 3. 제미나이에게 직접 요청 (라이브러리 안 씀!)
def ask_gemini_direct(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"❌ API 오류 ({response.status_code}): {response.text}"

# 4. 메인 실행
async def main():
    news_text = get_latest_news()
    
    prompt = f"""
    [역할] 너는 주식 투자 비서야. 아래 뉴스를 보고 한국어로 브리핑해줘.
    
    [투자 종목] PSTG(성장), SPHD(배당), VOO(지수)
    
    [뉴스 데이터]
    {news_text}
    
    [조건]
    1. 초보자도 알기 쉽게 설명.
    2. 섹션: 📉 시장 분위기, 🚨 핵심 뉴스, 💼 내 종목 체크.
    3. 출처 표기 필수.
    """

    print("제미나이 서버로 직접 전송 중...")
    msg = ask_gemini_direct(prompt)

    # 텔레그램 전송
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    print("전송 완료!")

if __name__ == "__main__":
    asyncio.run(main())
