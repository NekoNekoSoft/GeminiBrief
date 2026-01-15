import os
import asyncio
import google.generativeai as genai
from telegram import Bot
from duckduckgo_search import DDGS

# 1. 환경변수 가져오기
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 2. 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 3. 최신 뉴스 검색 함수 (PSTG, SPHD, 미국 증시)
def get_latest_news():
    print("뉴스 검색 중...")
    results = []
    with DDGS() as ddgs:
        # ★ 수정된 부분: SPHD와 배당주 키워드 추가
        keywords = [
            "US stock market news today", 
            "PSTG stock news", 
            "SPHD ETF news", 
            "high dividend ETF analysis"
        ]
        for keyword in keywords:
            try:
                search_results = ddgs.text(keyword, max_results=2) # 키워드 당 2개씩
                for r in search_results:
                    results.append(f"- {r['title']}: {r['body']}")
            except Exception as e:
                print(f"검색 오류 ({keyword}): {e}")
                continue
    return "\n".join(results)

# 4. 제미나이에게 요약 요청 및 전송
async def main():
    # (1) 뉴스 수집
    news_text = get_latest_news()
    
    if not news_text:
        news_text = "뉴스 검색 결과가 없습니다."

    # (2) 프롬프트 작성 (★ 수정됨: SPHD 포함)
    prompt = f"""
    아래는 방금 수집한 미국 증시 관련 최신 뉴스 검색 결과야.
    이 내용을 바탕으로 한국어 브리핑을 작성해줘.
    
    [사용자 포트폴리오]
    1. 성장주: PSTG (퓨어스토리지) - 낸드/AI 관련 뉴스 중요
    2. 배당주: SPHD (고배당 저변동) - 금리, 방어주, 배당 관련 뉴스 중요
    3. 지수: VOO/SSO (S&P 500) - 전체 시장 분위기
    
    [작성 조건]
    1. 위 포트폴리오 종목들에 영향을 줄 만한 내용을 중심으로 요약할 것.
    2. 전문 용어는 주식 초보자도 이해하기 쉽게 비유(트램펄린, 바닥 등)를 섞어서 설명.
    3. 각 섹션 하단에 [출처]를 명시할 것.
    4. 구성: 📉 시장 분위기, 🚨 핵심 뉴스, 💼 내 종목(PSTG, SPHD) 체크.
    
    [검색된 뉴스 데이터]
    {news_text}
    """

    # (3) 제미나이 생성
    print("제미나이 생각 중...")
    try:
        response = model.generate_content(prompt)
        msg = response.text
    except Exception as e:
        msg = f"브리핑 생성 중 오류 발생: {e}"

    # (4) 텔레그램 전송
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
    print("전송 완료!")

if __name__ == "__main__":
    asyncio.run(main())
