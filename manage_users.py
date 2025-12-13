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
            
    elif args.command == 'list':
        users = database.get_active_subscribers()
        print(f"Active Subscribers ({len(users)}):")
        for u in users:
            print(f" - {u}")
            
    elif args.command == 'remove':
        if database.remove_subscriber(args.phone):
            print(f"Success: Subscriber {args.phone} deactivated.")
        else:
            print("Error: Failed to remove subscriber.")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
