#!/usr/bin/env python3

"""
Security testing script for the Euro AIP Airport Explorer.
Run this script to test various security measures.
"""

import requests
import time
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_cors_headers():
    """Test CORS headers are properly set."""
    print("🔒 Testing CORS headers...")
    
    # Make a request with Origin header to trigger CORS
    headers = {"Origin": "https://maps.flyfun.aero"}
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    
    # Check for CORS headers
    cors_headers = [
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers"
    ]
    
    for header in cors_headers:
        if header in response.headers:
            print(f"  ✅ {header}: {response.headers[header]}")
        else:
            print(f"  ❌ {header} not found")
    
    # Also test with a disallowed origin
    headers = {"Origin": "https://malicious-site.com"}
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    
    if "Access-Control-Allow-Origin" in response.headers:
        origin = response.headers["Access-Control-Allow-Origin"]
        if origin == "https://malicious-site.com":
            print(f"  ❌ CORS allows malicious origin: {origin}")
        else:
            print(f"  ✅ CORS properly restricts origin: {origin}")
    else:
        print(f"  ✅ CORS headers not present for disallowed origin")
    
    return response

def test_security_headers():
    """Test security headers are properly set."""
    print("\n🛡️ Testing security headers...")
    
    response = requests.get(f"{BASE_URL}/health")
    
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    for header, expected_value in security_headers.items():
        if header in response.headers:
            actual_value = response.headers[header]
            if actual_value == expected_value:
                print(f"  ✅ {header}: {actual_value}")
            else:
                print(f"  ⚠️ {header}: {actual_value} (expected: {expected_value})")
        else:
            print(f"  ❌ {header} not found")
    
    return response

def test_input_validation():
    """Test input validation on API endpoints."""
    print("\n🔍 Testing input validation...")
    
    # Test invalid ICAO code
    response = requests.get(f"{BASE_URL}/api/airports/INVALID")
    if response.status_code == 422:
        print("  ✅ Invalid ICAO code properly rejected")
    else:
        print(f"  ❌ Invalid ICAO code not rejected: {response.status_code}")
    
    # Test excessive limit
    response = requests.get(f"{BASE_URL}/api/airports/?limit=999999")
    if response.status_code == 422:
        print("  ✅ Excessive limit properly rejected")
    else:
        print(f"  ❌ Excessive limit not rejected: {response.status_code}")
    
    # Test negative offset
    response = requests.get(f"{BASE_URL}/api/airports/?offset=-1")
    if response.status_code == 422:
        print("  ✅ Negative offset properly rejected")
    else:
        print(f"  ❌ Negative offset not rejected: {response.status_code}")
    
    # Test invalid distance
    response = requests.get(f"{BASE_URL}/api/airports/EGLL/procedure-lines?distance_nm=-1")
    if response.status_code == 422:
        print("  ✅ Invalid distance properly rejected")
    else:
        print(f"  ❌ Invalid distance not rejected: {response.status_code}")

def test_rate_limiting():
    """Test rate limiting functionality."""
    print("\n⏱️ Testing rate limiting...")
    
    # Make multiple requests quickly
    responses = []
    for i in range(105):  # Exceed the 100 request limit
        try:
            response = requests.get(f"{BASE_URL}/health")
            responses.append(response.status_code)
        except Exception as e:
            print(f"  ❌ Request {i+1} failed: {e}")
            break
    
    # Check if rate limiting kicked in
    if 429 in responses:
        print("  ✅ Rate limiting working (429 status code found)")
    else:
        print("  ❌ Rate limiting not working (no 429 status codes)")
    
    print(f"  📊 Made {len(responses)} requests, status codes: {set(responses)}")

def test_trusted_hosts():
    """Test trusted hosts middleware."""
    print("\n🏠 Testing trusted hosts...")
    
    # Test with valid host
    headers = {"Host": "localhost:8000"}
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    if response.status_code == 200:
        print("  ✅ Valid host accepted")
    else:
        print(f"  ❌ Valid host rejected: {response.status_code}")
    
    # Test with invalid host
    headers = {"Host": "malicious-site.com"}
    try:
        response = requests.get(f"{BASE_URL}/health", headers=headers)
        if response.status_code == 400:
            print("  ✅ Invalid host properly rejected")
        else:
            print(f"  ❌ Invalid host not rejected: {response.status_code}")
    except requests.exceptions.RequestException:
        print("  ✅ Invalid host properly rejected (connection refused)")

def test_health_endpoint():
    """Test health endpoint doesn't expose sensitive information."""
    print("\n🏥 Testing health endpoint...")
    
    # Wait for rate limiting to reset
    time.sleep(2)
    
    response = requests.get(f"{BASE_URL}/health")
    data = response.json()
    
    # Check that sensitive information is not exposed
    sensitive_fields = ["airports_count", "database_path", "model", "airports"]
    
    for field in sensitive_fields:
        if field in data:
            print(f"  ❌ Sensitive field '{field}' exposed in health endpoint")
        else:
            print(f"  ✅ Sensitive field '{field}' not exposed")
    
    # Check that only safe information is exposed
    safe_fields = ["status", "timestamp"]
    for field in safe_fields:
        if field in data:
            print(f"  ✅ Safe field '{field}' present")
        else:
            print(f"  ⚠️ Safe field '{field}' missing")
    
    # Print actual response for debugging
    print(f"  📄 Actual response: {data}")

def test_api_endpoints():
    """Test API endpoints return proper responses."""
    print("\n🔌 Testing API endpoints...")
    
    # Wait for rate limiting to reset
    time.sleep(2)
    
    endpoints = [
        "/api/airports/",
        "/api/filters/countries",
        "/api/statistics/overview"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            if response.status_code == 200:
                print(f"  ✅ {endpoint}: OK")
            else:
                print(f"  ❌ {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")

def main():
    """Run all security tests."""
    print("🚀 Starting security tests for Euro AIP Airport Explorer")
    print("=" * 60)
    
    try:
        # Test if server is running
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not responding properly: {response.status_code}")
            return
    except requests.exceptions.RequestException:
        print("❌ Server not running. Please start the server first.")
        return
    
    # Run all tests
    test_cors_headers()
    test_security_headers()
    test_input_validation()
    test_rate_limiting()
    test_trusted_hosts()
    test_health_endpoint()
    test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("✅ Security tests completed!")

if __name__ == "__main__":
    main() 