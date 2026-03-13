# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : Abdulla Almannaei
# ID      : 20220002297
# Email   : 20220002297@students.cud.ac.ae
# AWS Acc : 978355780049
# -------------------------------------------------------

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": "smartparcel-server"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)