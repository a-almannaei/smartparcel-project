# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : Abdulla Almannaei
# ID      : 20220002297
# Email   : 20220002297@students.cud.ac.ae
# AWS Acc : 978355780049
# -------------------------------------------------------

from flask import Flask, request, jsonify
from functools import wraps
import boto3
import uuid
import json
from datetime import datetime

app = Flask(__name__)

# --- AWS Connections (Target Region: Sydney) ---
REGION = 'ap-southeast-2'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table('smartparcel-parcels')

sqs = boto3.client('sqs', region_name=REGION)
SQS_QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/978355780049/smartparcel-notifications-20220002297'

s3 = boto3.client('s3', region_name=REGION)
S3_BUCKET_NAME = 'smartparcel-photos-20220002297'

# --- Simple Role-Based Authentication ---
API_KEYS = {
    "key-admin-001": "admin",
    "key-driver-001": "driver",
    "key-customer-001": "customer"
}

def require_auth(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if not api_key or api_key not in API_KEYS:
                return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 401
            
            user_role = API_KEYS[api_key]
            if user_role not in allowed_roles:
                return jsonify({"error": f"Forbidden. Role '{user_role}' cannot access this endpoint."}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- API Endpoints ---

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": "smartparcel-server"}), 200

@app.route('/api/parcels', methods=['POST'])
@require_auth(['admin', 'driver'])
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
@require_auth(['admin'])
def get_all_parcels():
    status_filter = request.args.get('status')
    try:
        if status_filter:
            # Requires the GSI 'status-index' you created in AWS
            response = table.query(
                IndexName='status-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('status').eq(status_filter.lower())
            )
        else:
            response = table.scan()
        return jsonify({"parcels": response.get('Items', [])}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>', methods=['GET'])
@require_auth(['admin', 'driver', 'customer'])
def get_parcel(parcel_id):
    try:
        response = table.get_item(Key={'parcel_id': parcel_id})
        if 'Item' in response:
            return jsonify({"parcel": response['Item']}), 200
        return jsonify({"error": "Parcel not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>/status', methods=['PUT'])
@require_auth(['driver'])
def update_status(parcel_id):
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({"error": "Missing new status"}), 400
        
    new_status = data['status'].lower()
    
    try:
        # First check if cancelled
        current = table.get_item(Key={'parcel_id': parcel_id})
        if 'Item' not in current:
            return jsonify({"error": "Parcel not found"}), 404
        if current['Item'].get('status') == 'cancelled':
            return jsonify({"error": "Cannot update a cancelled parcel"}), 409

        response = table.update_item(
            Key={'parcel_id': parcel_id},
            UpdateExpression="set #s = :stat",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':stat': new_status},
            ReturnValues="ALL_NEW"
        )
        updated_item = response['Attributes']
        
        # Send SQS Message
        message_body = {
            'parcel_id': parcel_id,
            'new_status': new_status,
            'customer_email': updated_item.get('customer_email', 'unknown')
        }
        sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(message_body))
        
        return jsonify({"message": "Status updated & notification queued", "updated_status": new_status}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>/photo', methods=['POST'])
@require_auth(['driver'])
def upload_photo(parcel_id):
    if 'photo' not in request.files:
        return jsonify({"error": "No photo file provided"}), 400
        
    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    s3_key = f"{parcel_id}/{photo.filename}"
    
    try:
        s3.upload_fileobj(photo, S3_BUCKET_NAME, s3_key)
        photo_url = f"s3://{S3_BUCKET_NAME}/{s3_key}"
        return jsonify({"parcel_id": parcel_id, "photo_url": photo_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcels/<parcel_id>', methods=['DELETE'])
@require_auth(['admin'])
def delete_parcel(parcel_id):
    try:
        response = table.get_item(Key={'parcel_id': parcel_id})
        if 'Item' not in response:
            return jsonify({"error": "Parcel not found"}), 404
            
        current_status = response['Item'].get('status', 'pending')
        if current_status != 'pending':
            return jsonify({"error": f"Conflict: Cannot cancel parcel in '{current_status}' state"}), 409
            
        # Soft delete (change status to cancelled)
        table.update_item(
            Key={'parcel_id': parcel_id},
            UpdateExpression="set #s = :stat",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':stat': 'cancelled'}
        )
        return jsonify({"message": f"Parcel {parcel_id} cancelled successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)