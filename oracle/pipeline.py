
import logging
from datetime import datetime
from oracle import database
from oracle.data_source import MarketData
from oracle.analysis import AnalysisGate, LLMClient
from oracle.telegram_bot import broadcast_report
from oracle.message_formatter import format_report

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
            html_report = format_report(ticker, technicals, analysis_result, diff_str=diff_str)
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
