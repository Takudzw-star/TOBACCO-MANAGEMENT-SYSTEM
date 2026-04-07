# HR Management Dashboard

def display_hr_dashboard():
    print("HR Management Dashboard")
    print("1. View Employee Records")
    print("2. Add Employee")
    print("3. Process Payroll")
    choice = input("Enter your choice: ")

    if choice == "1":
        view_employee_records()
    elif choice == "2":
        add_employee()
    elif choice == "3":
        process_payroll()
    else:
        print("Invalid choice")

def view_employee_records():
    print("Displaying employee records...")
    # Logic to fetch and display employee records

def add_employee():
    print("Adding a new employee...")
    # Logic to add a new employee

def process_payroll():
    print("Processing payroll...")
    # Logic to process payroll

if __name__ == "__main__":
    display_hr_dashboard()