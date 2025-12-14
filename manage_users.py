import argparse
import sys
from oracle import database

def main():
    parser = argparse.ArgumentParser(description="Manage Market Oracle Subscribers")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add or update a subscriber')
    add_parser.add_argument('phone', type=str, help='Phone number (e.g., +972501234567)')
    add_parser.add_argument('--days', type=int, default=30, help='Subscription duration in days')

    # List command
    list_parser = subparsers.add_parser('list', help='List all active subscribers')

    # Add Ticker command
    add_ticker_parser = subparsers.add_parser('add-ticker', help='Add a ticker to a user portfolio')
    add_ticker_parser.add_argument('phone', type=str, help='Phone number')
    add_ticker_parser.add_argument('ticker', type=str, help='Ticker symbol (e.g. NVDA)')

    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove/Deactivate a subscriber')
    remove_parser.add_argument('phone', type=str, help='Phone number to remove')

    args = parser.parse_args()
    
    # Ensure DB is initialized
    database.init_db()

    if args.command == 'add':
        if database.add_subscriber(args.phone, args.days):
            print(f"Success: Subscriber {args.phone} added/updated for {args.days} days.")
        else:
            print("Error: Failed to add subscriber.")
            
    elif args.command == 'add-ticker':
        if database.add_ticker_to_user(args.phone, args.ticker):
            print(f"Success: Added {args.ticker} to {args.phone}.")
        else:
            print(f"Error: Failed to add ticker.")
            
    elif args.command == 'list':
        users = database.get_active_subscribers()
        print(f"Active Subscribers ({len(users)}):")
        for u in users:
            tickers = database.get_user_tickers(u)
            print(f" - {u} [Tickers: {', '.join(tickers)}]")
            
    elif args.command == 'remove':
        if database.remove_subscriber(args.phone):
            print(f"Success: Subscriber {args.phone} deactivated.")
        else:
            print("Error: Failed to remove subscriber.")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
