#!/usr/bin/env python3
"""
Standalone health check server for Kubernetes/OpenShift probes.
Runs independently from the Streamlit app on port 8081.
"""

import os
import sys
from flask import Flask, jsonify

app = Flask(__name__)
health_status = {"status": "healthy", "checks": {}}

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check - always returns healthy."""
    print("🏥 Health check called", flush=True)
    return jsonify(health_status), 200

@app.route('/ready', methods=['GET'])  
def readiness_check():
    """Readiness check - verifies the app can handle requests."""
    print("🔍 Readiness check called", flush=True)
    # For now, always return ready. Could add llama stack connectivity check later.
    return jsonify({"status": "ready", "checks": {}}), 200

if __name__ == "__main__":
    port = int(os.environ.get("HEALTH_PORT", "8081"))
    print(f"🚀 Starting health server on port {port}...", flush=True)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

