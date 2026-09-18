"""Import UTF-8 CSV orders into an existing database without touching other rows."""
import argparse
import csv
from datetime import datetime
from app import db

parser = argparse.ArgumentParser()
parser.add_argument('csv_file')
args = parser.parse_args()
db.initialize()
with open(args.csv_file, encoding='utf-8-sig', newline='') as handle, db.SessionLocal() as session:
    count = 0
    for row in csv.DictReader(handle):
        customer_id = int(row['customer_id'])
        if not session.get(db.User, customer_id):
            raise ValueError(f'Unknown customer_id {customer_id}')
        if session.query(db.Order).filter_by(order_no=row['order_no']).first():
            continue
        session.add(db.Order(order_no=row['order_no'], customer_id=customer_id, product=row['product'],
                             category=row['category'], amount=float(row['amount']), status=row['status'],
                             created_at=datetime.fromisoformat(row['created_at'])))
        count += 1
    session.commit()
print(f'Imported {count} orders')
