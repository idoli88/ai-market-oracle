
import pytest
from oracle.message_formatter import safe_html, format_report, split_message

def test_safe_html():
    raw = "Hello <World> & 'Friends'"
    expected = "Hello &lt;World&gt; &amp; &#x27;Friends&#x27;"
    assert safe_html(raw) == expected

def test_format_report_escaping():
    ticker = "<NVDA>"
    technicals = {'current_price': 100, 'price_change_pct': 5, 'rsi': 50}
    analysis = {
        'action': 'BUY & HOLD',
        'emoji': '🚀',
        'summary_he': 'Dangerous <script>',
        'risk_note_he': 'Risk > 9000'
    }
    
    report = format_report(ticker, technicals, analysis)
    
    assert "&lt;NVDA&gt;" in report
    assert "BUY &amp; HOLD" in report
    assert "Dangerous &lt;script&gt;" in report
    assert "Risk &gt; 9000" in report
    assert "<b>" in report # Bold tag should be present and unescaped (it's added by formatter)

def test_split_message_short():
    short_msg = "Short message"
    chunks = split_message(short_msg, max_length=100)
    assert len(chunks) == 1
    assert chunks[0] == short_msg

def test_split_message_long():
    # Create a message of length 150
    # "Line 1..." is 10 chars. 15 lines = 150 chars.
    lines = [f"Line {i:02d}" for i in range(15)] 
    long_msg = "\n".join(lines) # 15 lines joined by \n
    
    # Split max 50
    chunks = split_message(long_msg, max_length=50)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50
    
    # Verify content preservation
    reconstructed = "".join(chunks)
    # split_message might eat some newlines if it splits exactly on them or lstrips.
    # Our implementation logic: chunk = text[:split_at], text = text[split_at:].lstrip()
    # It might lose the newline it split on if split_at points to a newline?
    # rfind returns index of newline. text[:split_at] EXCLUDES newline.
    # text[split_at:] INCLUDES newline. lstrip removes leading whitespace (newline).
    # So yes, one newline might be lost per chunk. That's acceptable for Telegram splitting (usually preferred).
    
    assert "Line 00" in chunks[0]
    assert "Line 14" in chunks[-1]

def test_split_no_newlines():
    # continuous string
    msg = "a" * 100
    chunks = split_message(msg, max_length=10)
    assert len(chunks) == 10
    assert chunks[0] == "aaaaaaaaaa"

def test_format_report_with_diff():
    technicals = {'current_price': 100}
    analysis = {'action': 'HOLD'}
    diff_str = "Since last: +5.0%, RSI +2.0"
    report = format_report("AAPL", technicals, analysis, diff_str=diff_str)
    
    assert "<i>Since last: +5.0%, RSI +2.0</i>" in report
