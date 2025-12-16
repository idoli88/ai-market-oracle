import logging
from datetime import datetime
from oracle import database
from oracle.data_source import MarketData
from oracle.analysis import AnalysisGate, LLMClient
from oracle.telegram_bot import broadcast_report
from oracle.message_formatter import format_report
from oracle.news import get_provider_for_ticker
from oracle.fundamentals import SecEdgarProvider
from oracle.config import settings

logger = logging.getLogger(__name__)

async def run_pipeline(dry_run: bool = False, run_type: str = "normal"):
    """
    run_type: 'normal' | 'digest'
    """
    logger.info(f"🚀 Starting pipeline run... (Dry Run: {dry_run}, Type: {run_type})")

    # 1. Get all unique tickers from all active users
    active_users = database.get_active_subscribers()
    if not active_users and not dry_run:
        logger.info("No active subscribers. Skipping run.")
        return

    unique_tickers = database.get_all_unique_tickers()
    if not unique_tickers:
        logger.info("No unique tickers found.")
        return

    logger.info(f"Checking {len(unique_tickers)} unique tickers for {len(active_users)} users.")

    reports = {} # ticker -> {'html': str, 'significant': bool}
    llm_client = LLMClient()

    for ticker in unique_tickers:
        try:
            logger.info(f"Processing {ticker}...")

            # Fetch Data
            df = MarketData.fetch_price_history(ticker)
            if df.empty:
                logger.warning(f"No data for {ticker}")
                continue

            technicals = MarketData.calculate_technicals(df)
            if not technicals:
                logger.warning(f"Could not calculate technicals for {ticker}")
                continue

            snapshot = database.get_snapshot(ticker)

            # 1.1 Fetch News (MVP)
            news_items = database.get_cached_news(ticker, ttl_minutes=settings.NEWS_TTL_MINUTES)
            if not news_items:
                provider = get_provider_for_ticker(ticker)
                fresh_news = provider.fetch(ticker)
                if fresh_news:
                    database.update_news_cache(ticker, fresh_news)
                    news_items = fresh_news

            # 1.2 Fetch Fundamentals (US only)
            fundamentals = None
            is_us_ticker = not ticker.endswith('.TA')  # Simple heuristic for US tickers

            if is_us_ticker:
                # Check cache
                fundamentals = database.get_fundamentals(ticker, ttl_days=settings.FUNDAMENTALS_TTL_DAYS)

                # Check if we need to refresh (new filing or cache miss)
                edgar_provider = SecEdgarProvider()
                needs_refresh = False

                if not fundamentals:
                    needs_refresh = True
                else:
                    # Check for new filing
                    checkpoint = database.get_filing_checkpoint(ticker)
                    fresh_data = edgar_provider.get_fundamentals(ticker)

                    if fresh_data and fresh_data.get('latest_filing'):
                        latest_filing = fresh_data['latest_filing']
                        last_accession = checkpoint.get('last_accession_or_id') if checkpoint else None

                        if latest_filing['accession_number'] != last_accession:
                            logger.info(f"New filing detected for {ticker}: {latest_filing['accession_number']}")
                            needs_refresh = True

                if needs_refresh:
                    fresh_data = edgar_provider.get_fundamentals(ticker)
                    if fresh_data:
                        database.update_fundamentals(ticker, fresh_data['kpis'])
                        if fresh_data.get('latest_filing'):
                            database.update_filing_checkpoint(
                                ticker,
                                fresh_data['latest_filing']['accession_number'],
                                fresh_data['latest_filing']['filing_date']
                            )
                        fundamentals = fresh_data

            # Calculate Snapshot Diff
            diff_str = ""
            if snapshot and snapshot.get("last_price"):
                last_p = snapshot.get("last_price")
                last_r = snapshot.get("last_rsi", 50)
                curr_p = technicals.get("current_price")
                curr_r = technicals.get("rsi")

                d_p = ((curr_p - last_p) / last_p) * 100
                d_r = curr_r - last_r
                diff_str = f"Since last: Price {d_p:+.2f}%, RSI {d_r:+.1f}"

            # The Gate
            should_run_llm, trigger_reason = AnalysisGate.should_trigger_llm(ticker, technicals, snapshot)

            analysis_result = None
            is_significant = False
            trigger_at = None

            if should_run_llm:
                logger.info(f"invoking LLM for {ticker} (Reason: {trigger_reason})")

                # Determine Plan for Routing
                max_plan = database.get_max_plan_for_ticker(ticker)

                # Build context
                context = f"Previous action: {snapshot.get('last_action') if snapshot else 'None'}. Trigger: {trigger_reason}"
                analysis_result = llm_client.analyze_ticker(ticker, technicals, context, diff_context=diff_str, plan=max_plan)
                analysis_result['trigger_reason'] = trigger_reason
                is_significant = True
                trigger_at = datetime.now()
            else:
                # Reuse old snapshot summary or create simple technical update
                logger.info(f"Skipping LLM for {ticker}, using fallback/cache")
                analysis_result = {
                    "ticker": ticker,
                    "action": "HOLD", # Default if no change
                    "confidence": 1.0,
                    "summary_he": "אין שינוי מהותי במדדים הטכניים.",
                    "key_points_he": [f"RSI: {technicals.get('rsi')}", f"Price: {technicals.get('current_price')}"],
                    "invalidation_he": "-",
                    "risk_note_he": "-"
                }
                is_significant = False

            # Save Snapshot ONLY if not dry_run
            if not dry_run:
                database.update_snapshot(
                    ticker,
                    technicals.get('current_price'),
                    technicals.get('rsi'),
                    technicals.get('ema_short'),
                    technicals.get('ema_long'),
                    analysis_result.get('action'),
                    analysis_result,
                    trigger_type=trigger_reason if is_significant else None,
                    trigger_at=trigger_at
                )
            else:
                logger.info(f"[DRY RUN] Would update snapshot for {ticker}: {analysis_result.get('action')} (Trigger: {trigger_reason})")

            # Format Report for Telegram
            html_report = format_report(
                ticker,
                technicals,
                analysis_result,
                diff_str=diff_str,
                news_items=news_items,
                fundamentals=fundamentals
            )
            reports[ticker] = {
                'html': html_report,
                'significant': is_significant
            }

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")

    # Broadcast
    if reports:
        if not dry_run:
            logger.info("Broadcasting updates...")
            await broadcast_report(active_users, reports, run_type=run_type)
            logger.info("Broadcast complete.")
        else:
            logger.info("[DRY RUN] Would broadcast the following reports:")
            for t, data in reports.items():
                logger.info(f"--- Report for {t} ({'Significant' if data['significant'] else 'Quiet'}) ---\n{data['html']}\n----------------")
    else:
        logger.info("No reports generated.")
