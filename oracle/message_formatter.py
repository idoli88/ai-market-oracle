import html
from typing import List, Dict, Optional

def safe_html(text: str) -> str:
    """Escape special characters for HTML parsing."""
    if not text:
        return ""
    return html.escape(str(text))

def format_report(ticker: str, technicals: Dict, analysis: Dict, diff_str: str = "", news_items: List[Dict] = None, fundamentals: Dict = None) -> str:
    """
    Format a single ticker report using HTML.
    """
    action = safe_html(analysis.get('action', 'UNKNOWN'))
    emoji = safe_html(analysis.get('emoji', ''))

    price = technicals.get('current_price', 0)
    pct_change = technicals.get('price_change_pct', 0)
    rsi = technicals.get('rsi', 0)

    summary = safe_html(analysis.get('summary_he', ''))
    risk = safe_html(analysis.get('risk_note_he', ''))

    # Construct HTML
    diff_html = f"<i>{safe_html(diff_str)}</i>\n" if diff_str else ""

    news_html = ""
    if news_items:
        news_html = "📰 <b>News:</b>\n"
        for item in news_items[:2]:
            title = safe_html(item.get('title'))
            source = safe_html(item.get('source'))
            url = item.get('url')
            news_html += f"• <a href='{url}'>{title}</a> ({source})\n"
        news_html += "---\n"

    fundamentals_html = ""
    if fundamentals and fundamentals.get('kpis'):
        kpis = fundamentals['kpis']
        fundamentals_html = "💼 <b>Fundamentals:</b>\n"

        # Format numbers with B/M suffix
        parts = []
        if 'revenue' in kpis:
            parts.append(f"Revenue: ${kpis['revenue']:.2f}B")
        if 'net_income' in kpis:
            parts.append(f"Net Income: ${kpis['net_income']:.1f}M")
        if 'eps' in kpis:
            parts.append(f"EPS: ${kpis['eps']:.2f}")
        if 'debt' in kpis:
            parts.append(f"Debt: ${kpis['debt']:.2f}B")

        if parts:
            # Split into two lines if needed
            if len(parts) > 2:
                fundamentals_html += " | ".join(parts[:2]) + "\n"
                fundamentals_html += " | ".join(parts[2:]) + "\n"
            else:
                fundamentals_html += " | ".join(parts) + "\n"
        else:
            fundamentals_html += "N/A\n"

        fundamentals_html += "---\n"

    # Note: <b> is supported by Telegram HTML parse mode.
    return (
        f"<b>{safe_html(ticker)}</b>: {action} {emoji}\n"
        f"מחיר: {price} ({pct_change}%)\n"
        f"RSI: {rsi}\n"
        f"{diff_html}"
        f"---\n"
        f"{news_html}"
        f"{fundamentals_html}"
        f"{summary}\n"
        f"⚠️ {risk}"
    ).strip()

def split_message(text: str, max_length: int = 4000) -> List[str]:
    """
    Split a long message into chunks, respecting newlines where possible.
    Telegram limit is 4096. We default to 4000 to be safe.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Find nearest newline before max_length
        split_at = text.rfind('\n', 0, max_length)
        if split_at == -1:
            # No newline, force split at max_length
            split_at = max_length

        chunk = text[:split_at]
        chunks.append(chunk)

        # Advance text (skip newline if we split on it)
        text = text[split_at:].lstrip()

    return chunks
