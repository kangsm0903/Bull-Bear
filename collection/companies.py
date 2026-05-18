import sqlite3
import os
import requests
import zipfile
import io
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pykrx import stock

# .env 파일 로드
load_dotenv(Path(__file__).with_name(".env"))

def get_dart_corp_codes():
    """DART API에서 corp_code 딕셔너리를 가져오는 함수"""
    print("DART API에서 기업 고유번호(corp_code)를 불러오는 중...")
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        print("경고: .env 파일에 DART_API_KEY가 설정되지 않았습니다.")
        return {}

    url = 'https://opendart.fss.or.kr/api/corpCode.xml'
    res = requests.get(url, params={'crtfc_key': api_key})
    
    corp_dict = {}
    if res.status_code == 200:
        # ZIP 파일 메모리 압축 해제 및 XML 파싱
        zip_file = zipfile.ZipFile(io.BytesIO(res.content))
        with zip_file.open('CORPCODE.xml') as xml_file:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            for list_element in root.findall('list'):
                corp_code = list_element.find('corp_code').text
                stock_code = list_element.find('stock_code').text
                
                # 상장사(stock_code가 있는 경우)만 딕셔너리에 저장
                if stock_code and stock_code.strip():
                    corp_dict[stock_code.strip()] = corp_code.strip()
        print(f"성공: 총 {len(corp_dict)}개의 상장사 corp_code 맵핑 완료.")
    else:
        print(f"DART API 호출 실패 (상태코드: {res.status_code})")
        
    return corp_dict

def init_kospi_top_200_companies():
    # 1. DART corp_code 사전 가져오기
    dart_corp_map = get_dart_corp_codes()

    # 2. 데이터베이스 연결
    db_path = Path(__file__).with_name("identifier.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 3. KOSPI 시가총액 데이터 가져오기
    today = datetime.today().strftime("%Y%m%d")
    print(f"\n[{today}] KOSPI 시가총액 데이터를 pykrx에서 불러옵니다...")
    
    df_cap = stock.get_market_cap_by_ticker(
        today,
        market="KOSPI",
        alternative=True,
    )
    
    if df_cap.empty:
        print("데이터를 불러오지 못했습니다. 주말이나 휴일일 경우 평일 날짜로 세팅해보세요.")
        conn.close()
        return

    # 4. 상위 200개 추출 및 업종 데이터 병합
    top_200 = df_cap.sort_values(by='시가총액', ascending=False).head(200)

    print("KOSPI 업종 분류 데이터를 pykrx에서 불러옵니다...")
    try:
        df_sector = stock.get_market_sector_classifications(today, market="KOSPI")
        if "종목코드" in df_sector.columns:
            sector_map = df_sector.set_index("종목코드")["업종명"].to_dict()
        else:
            sector_map = df_sector["업종명"].to_dict()
    except Exception as e:
        print(f"업종 분류 데이터를 불러오지 못했습니다. sector 없이 저장합니다: {e}")
        sector_map = {}
    
    # 5. INSERT 쿼리 준비 (corp_code 컬럼 추가)
    insert_query = """
        INSERT INTO companies (ticker, corp_name, market, sector, market_cap, corp_code, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            corp_name = excluded.corp_name,
            market = excluded.market,
            sector = excluded.sector,
            market_cap = excluded.market_cap,
            corp_code = excluded.corp_code,
            updated_at = excluded.updated_at
    """
    
    updated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
    success_count = 0

    print("DB에 저장을 시작합니다...")
    
    # 6. 순회하며 데이터 넣기
    for ticker, row in top_200.iterrows():
        corp_name = stock.get_market_ticker_name(ticker)
        sector = sector_map.get(ticker)
        market_cap = int(row['시가총액'])
        
        # [수정된 부분] 우선주 DART 코드 매핑 로직
        corp_code = dart_corp_map.get(ticker) 
        
        # 만약 DART 맵에서 못 찾았다면? (우선주일 확률이 높음)
        if not corp_code:
            # 종목코드의 마지막 자리를 '0'으로 바꿔서 보통주 코드로 변환해 봅니다.
            base_ticker = ticker[:-1] + '0'
            corp_code = dart_corp_map.get(base_ticker)
            
            if corp_code:
                print(f"[{ticker}] {corp_name} (우선주 추정) -> 보통주({base_ticker})의 DART 코드로 연결 성공")
            else:
                print(f"[{ticker}] {corp_name} -> DART 코드를 끝내 찾지 못했습니다.")
        
        try:
            cursor.execute(insert_query, (ticker, corp_name, "KOSPI", sector, market_cap, corp_code, updated_at))
            success_count += 1
        except Exception as e:
            print(f"Error inserting {ticker} ({corp_name}): {e}")

    # 7. 커밋 및 종료
    conn.commit()
    conn.close()
    
    print(f"\n완료! 총 {success_count}개의 상위 종목이 'companies' 테이블에 저장되었습니다.")

if __name__ == "__main__":
    init_kospi_top_200_companies()