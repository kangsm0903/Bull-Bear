import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from pykrx import stock
import FinanceDataReader as fdr
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv(Path(__file__).with_name(".env"))

DB_PATH = Path(__file__).with_name("identifier.sqlite")


def safe_int(val, default=None):
    try:
        return None if pd.isna(val) else int(val)
    except Exception:
        return default


def safe_float(val, default=None):
    try:
        return None if pd.isna(val) else float(val)
    except Exception:
        return default


def get_target_tickers():
    conn = sqlite3.connect(DB_PATH)
    tickers = pd.read_sql("SELECT ticker FROM companies", conn)['ticker'].tolist()
    conn.close()
    return tickers


def ingest_quant_daily(target_date):
    print(f"[{target_date}] quant_daily 수집 시작...")

    # --- 배치 조회 (시장 전체를 한 번에) ---
    # get_market_ohlcv 반환값에 시가총액이 포함되어 있으므로 get_market_cap_by_ticker 별도 불필요
    df_ohlcv = stock.get_market_ohlcv(target_date, market="KOSPI")
    df_fund = stock.get_market_fundamental(target_date, market="KOSPI")
    df_exhaust = stock.get_exhaustion_rates_of_foreign_investment(target_date, market="KOSPI")

    # 투자자별 순매수 거래량 (외국인 / 기관합계 / 개인)
    try:
        df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(
            target_date, target_date, market="KOSPI", investor="외국인"
        )
    except Exception as e:
        print(f"  외국인 순매수 조회 실패: {e}")
        df_foreign = pd.DataFrame()

    try:
        df_inst = stock.get_market_net_purchases_of_equities_by_ticker(
            target_date, target_date, market="KOSPI", investor="기관합계"
        )
    except Exception as e:
        print(f"  기관 순매수 조회 실패: {e}")
        df_inst = pd.DataFrame()

    try:
        df_indi = stock.get_market_net_purchases_of_equities_by_ticker(
            target_date, target_date, market="KOSPI", investor="개인"
        )
    except Exception as e:
        print(f"  개인 순매수 조회 실패: {e}")
        df_indi = pd.DataFrame()

    # 공매도 거래량 / 잔고 — 단일 date 형식
    try:
        df_short_vol = stock.get_shorting_volume_by_ticker(target_date, market="KOSPI")
    except Exception as e:
        print(f"  공매도 거래량 조회 실패: {e}")
        df_short_vol = pd.DataFrame()

    try:
        df_short_bal = stock.get_shorting_balance_by_ticker(target_date, market="KOSPI")
    except Exception as e:
        print(f"  공매도 잔고 조회 실패: {e}")
        df_short_bal = pd.DataFrame()

    # --- 마스터 DataFrame 병합 ---
    df = df_ohlcv.copy()
    df = df.join(df_fund, how='left')
    if not df_exhaust.empty and '외국인비율' in df_exhaust.columns:
        df = df.join(df_exhaust[['외국인비율']], how='left')

    # --- DB 저장 ---
    target_tickers = get_target_tickers()

    insert_query = """
        INSERT INTO quant_daily (
            ticker, date, open, high, low, close, volume, change_pct,
            foreign_net, inst_net, indi_net,
            foreign_hold_pct, short_volume, short_ratio, short_balance,
            per, pbr, eps, dividend_yield, market_cap
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume,
            change_pct=excluded.change_pct,
            foreign_net=excluded.foreign_net, inst_net=excluded.inst_net,
            indi_net=excluded.indi_net,
            foreign_hold_pct=excluded.foreign_hold_pct,
            short_volume=excluded.short_volume, short_ratio=excluded.short_ratio,
            short_balance=excluded.short_balance,
            per=excluded.per, pbr=excluded.pbr, eps=excluded.eps,
            dividend_yield=excluded.dividend_yield, market_cap=excluded.market_cap
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    success_count = 0

    def _net(df_inv, ticker, col='순매수거래량'):
        if df_inv.empty or ticker not in df_inv.index:
            return None
        return safe_int(df_inv.loc[ticker].get(col))

    def _short_col(df_sv, ticker, *candidates):
        if df_sv.empty or ticker not in df_sv.index:
            return None
        row = df_sv.loc[ticker]
        for c in candidates:
            if c in row.index:
                return row[c]
        return None

    for ticker in target_tickers:
        if ticker not in df.index:
            continue
        row = df.loc[ticker]

        short_volume = safe_int(_short_col(df_short_vol, ticker, '공매도거래량', '공매도'))
        short_ratio  = safe_float(_short_col(df_short_vol, ticker, '비중', '공매도비중'))
        short_balance = safe_int(_short_col(df_short_bal, ticker, '공매도잔고', '잔고'))

        try:
            cursor.execute(insert_query, (
                ticker, target_date,
                safe_int(row.get('시가'),    0),
                safe_int(row.get('고가'),    0),
                safe_int(row.get('저가'),    0),
                safe_int(row.get('종가'),    0),
                safe_int(row.get('거래량'),  0),
                safe_float(row.get('등락률'), 0.0),
                _net(df_foreign, ticker),
                _net(df_inst,    ticker),
                _net(df_indi,    ticker),
                safe_float(row.get('외국인비율')),
                short_volume,
                short_ratio,
                short_balance,
                safe_float(row.get('PER')),
                safe_float(row.get('PBR')),
                safe_int(row.get('EPS')),
                safe_float(row.get('배당수익률')),
                safe_int(row.get('시가총액')),
            ))
            success_count += 1
        except Exception as e:
            print(f"  Error inserting {ticker}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ quant_daily: {success_count}개 종목 업데이트 완료.")


def ingest_macro_daily(target_date):
    """
    target_date: 'YYYYMMDD' 형식
    macro_daily 테이블은 (indicator, date) 복합 PK — narrow format
    """
    print(f"[{target_date}] macro_daily 수집 시작...")

    dt_target = datetime.strptime(target_date, "%Y%m%d")
    fdr_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
    start_date = (dt_target - timedelta(days=7)).strftime("%Y-%m-%d")

    macros = {
        'kospi':   'KS11',
        'kosdaq':  'KQ11',
        'usd_krw': 'USD/KRW',
        'sp500':   'US500',
        'nasdaq':  'IXIC',
        'us_10y':  '^TNX',
        'wti':     'CL=F',
    }

    insert_query = """
        INSERT INTO macro_daily (indicator, date, close, change_pct)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(indicator, date) DO UPDATE SET
            close=excluded.close,
            change_pct=excluded.change_pct
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    success_count = 0

    for indicator, symbol in macros.items():
        try:
            # 7일 치 데이터를 가져옵니다.
            df = fdr.DataReader(symbol, start_date, fdr_date)
            if df.empty:
                print(f"  {symbol}: 데이터 없음")
                continue

            # [핵심 변경] 당일 날짜 강제 검사 로직 삭제!
            # 미국 시장처럼 시차가 있는 경우, 현재 시점에서 확보 가능한 가장 최신 데이터를 오늘(target_date) 데이터로 간주합니다.
            latest_date_in_df = df.index[-1].strftime("%Y%m%d")
            if latest_date_in_df != target_date:
                print(f"  * {symbol}: {target_date} 당일 데이터가 없어 최근 거래일({latest_date_in_df}) 종가를 사용합니다.")

            close = safe_float(df.iloc[-1]['Close'])
            change_pct = None

            # 직접 등락률 계산
            if len(df) >= 2:
                prev_close = safe_float(df.iloc[-2]['Close'])
                if prev_close and prev_close != 0:
                    change_pct = round(((close - prev_close) / prev_close) * 100, 4)

            # DB에는 우리가 스크립트를 실행한 기준일(target_date)로 저장합니다.
            cursor.execute(insert_query, (indicator, target_date, close, change_pct))
            success_count += 1

        except Exception as e:
            print(f"  {symbol} 조회 실패: {e}")

    conn.commit()
    conn.close()
    print(f"✅ macro_daily: {success_count}개 지표 업데이트 완료.")

if __name__ == "__main__":
    target_date = datetime.today().strftime("%Y%m%d")

    ingest_quant_daily(target_date)
    ingest_macro_daily(target_date)
