# Field Officer Dashboard

from models import Farmer, Contract

def display_field_officer_dashboard():
    print("Field Officer Dashboard")
    print("1. View Farmers")
    print("2. Create Contract")
    print("3. View Contracts")
    choice = input("Enter your choice: ")

    if choice == "1":
        view_farmers()
    elif choice == "2":
        create_contract()
    elif choice == "3":
        view_contracts()
    else:
        print("Invalid choice")

def view_farmers():
    farmers = Farmer.get_all()
    for farmer in farmers:
        print(f"ID: {farmer.id}, Name: {farmer.name}, Contact: {farmer.contact_info}")

def create_contract():
    farmer_id = input("Enter Farmer ID: ")
    details = input("Enter Contract Details: ")
    Contract.create(farmer_id=farmer_id, details=details)
    print("Contract created successfully")

def view_contracts():
    contracts = Contract.get_all()
    for contract in contracts:
        print(f"ID: {contract.id}, Farmer ID: {contract.farmer_id}, Details: {contract.details}")

if __name__ == "__main__":
    display_field_officer_dashboard()