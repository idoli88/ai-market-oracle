import argparse
import sys
from oracle import database

def main():
    parser = argparse.ArgumentParser(description="Manage Market Oracle Subscribers")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add or update a subscriber')
    add_parser.add_argument('chat_id', type=int, help='Telegram Chat ID (e.g. 123456789)')
    add_parser.add_argument('--days', type=int, default=30, help='Subscription duration in days')
    add_parser.add_argument('--pref', type=str, default="standard", choices=['standard', 'alerts_only', 'digest_only', '3x_full'], help='Notification preference')

    # List command
    list_parser = subparsers.add_parser('list', help='List all active subscribers')

    # Add Ticker command
    add_ticker_parser = subparsers.add_parser('add-ticker', help='Add a ticker to a user portfolio')
    add_ticker_parser.add_argument('chat_id', type=int, help='Telegram Chat ID')
    add_ticker_parser.add_argument('ticker', type=str, help='Ticker symbol (e.g. NVDA)')

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove/Deactivate a subscriber')
    remove_parser.add_argument('chat_id', type=int, help='Telegram Chat ID to remove')

    args = parser.parse_args()
    
    # Ensure DB is initialized
    database.init_db()

    if args.command == 'add':
        if database.add_subscriber(args.chat_id, args.days, notification_pref=args.pref):
            print(f"Success: Subscriber {args.chat_id} added/updated for {args.days} days. Pref: {args.pref}")
        else:
            print("Error: Failed to add subscriber.")
            
    elif args.command == 'add-ticker':
        success, msg = database.add_ticker_to_user(args.chat_id, args.ticker)
        if success:
            print(f"Success: Added {args.ticker} to {args.chat_id}. ({msg})")
        else:
            print(f"Error: Failed to add ticker. ({msg})")
            
    elif args.command == 'list':
        users = database.get_active_subscribers()
        print(f"Active Subscribers ({len(users)}):")
        for u in users:
            chat_id = u['chat_id']
            pref = u.get('notification_pref', 'standard')
            tickers = database.get_user_tickers(chat_id)
            print(f" - {chat_id} [Plan: {u.get('plan', 'basic')}] [Pref: {pref}] [Tickers: {', '.join(tickers)}]")
            
    elif args.command == 'remove':
        if database.remove_subscriber(args.chat_id):
            print(f"Success: Subscriber {args.chat_id} deactivated.")
        else:
            print("Error: Failed to remove subscriber.")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
