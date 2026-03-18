# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : Abdulla Almannaei
# ID      : 20220002297
# Email   : 20220002297@students.cud.ac.ae
# AWS Acc : 978355780049
# -------------------------------------------------------

from flask import Flask, request, jsonify
import boto3
import uuid
from datetime import datetime

app = Flask(__name__)

# Initialize DynamoDB Connection (Target Region: Sydney)
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
table = dynamodb.Table('smartparcel-parcels')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": "smartparcel-server"}), 200

@app.route('/api/parcels', methods=['POST'])
def create_parcel():
    data = request.get_json()
    
    if not data or 'customer_email' not in data or 'destination' not in data:
        return jsonify({"error": "Missing customer_email or destination"}), 400
        
    parcel_id = "PKG-" + str(uuid.uuid4())[:8].upper()
    
    item = {
        'parcel_id': parcel_id,
        'customer_email': data['customer_email'],
        'destination': data['destination'],
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat()
    }
    
    try:
        table.put_item(Item=item)
        return jsonify({"message": "Parcel created successfully", "parcel": item}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels', methods=['GET'])
def get_all_parcels():
    try:
        # Scan the table to get all parcels
        response = table.scan()
        return jsonify({"parcels": response.get('Items', [])}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)