# Accounts Dashboard

def display_accounts_dashboard():
    print("Accounts Dashboard")
    print("1. View Transactions")
    print("2. Add Transaction")
    choice = input("Enter your choice: ")

    if choice == "1":
        view_transactions()
    elif choice == "2":
        add_transaction()
    else:
        print("Invalid choice")

def view_transactions():
    print("Displaying transactions...")
    # Logic to fetch and display transactions

def add_transaction():
    print("Adding a new transaction...")
    # Logic to add a new transaction

if __name__ == "__main__":
    display_accounts_dashboard()