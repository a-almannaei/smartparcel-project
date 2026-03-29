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
import json
from datetime import datetime

app = Flask(__name__)

# Initialize AWS Connections (Target Region: Sydney)
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
table = dynamodb.Table('smartparcel-parcels')

sqs = boto3.client('sqs', region_name='ap-southeast-2')
# Your exact SQS Queue URL
SQS_QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/978355780049/smartparcel-notifications-20220002297'

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
        response = table.scan()
        return jsonify({"parcels": response.get('Items', [])}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>', methods=['GET'])
def get_parcel(parcel_id):
    try:
        response = table.get_item(Key={'parcel_id': parcel_id})
        if 'Item' in response:
            return jsonify({"parcel": response['Item']}), 200
        else:
            return jsonify({"error": "Parcel not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>/status', methods=['PUT'])
def update_status(parcel_id):
    data = request.get_json()
    
    if not data or 'status' not in data:
        return jsonify({"error": "Missing new status"}), 400
        
    new_status = data['status'].lower()
    
    try:
        # Update DynamoDB and get the whole updated item back
        response = table.update_item(
            Key={'parcel_id': parcel_id},
            UpdateExpression="set #s = :stat",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':stat': new_status},
            ReturnValues="ALL_NEW"
        )
        updated_item = response['Attributes']
        
        # Send async notification message to SQS
        message_body = {
            'parcel_id': parcel_id,
            'new_status': new_status,
            'customer_email': updated_item.get('customer_email', 'unknown')
        }
        
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message_body)
        )
        
        return jsonify({
            "message": "Status updated & notification queued", 
            "updated_status": new_status
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>', methods=['DELETE'])
def delete_parcel(parcel_id):
    try:
        response = table.get_item(Key={'parcel_id': parcel_id})
        if 'Item' not in response:
            return jsonify({"error": "Parcel not found"}), 404
            
        table.delete_item(Key={'parcel_id': parcel_id})
        return jsonify({"message": f"Parcel {parcel_id} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)