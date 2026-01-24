#!/usr/bin/env python3
"""
Test Script for Advanced Search Mode URLs

Tests all advanced search mode features and reports results.
Run this with the API server running on localhost:8000
"""

import requests
import sys
from typing import Dict, Any


# ANSI color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_error(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def test_url(
    name: str,
    url: str,
    expected_advanced_mode: bool = True,
    check_results: bool = True
) -> Dict[str, Any]:
    """
    Test a single URL and return results.
    
    Args:
        name: Test name
        url: URL to test
        expected_advanced_mode: Expected value of advanced_mode in response
        check_results: Whether to check for results
    
    Returns:
        Dict with test results
    """
    print(f"\n{Colors.BLUE}Testing:{Colors.RESET} {name}")
    print(f"  URL: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        
        # Check status code
        if response.status_code != 200:
            print_error(f"HTTP {response.status_code}")
            return {
                "name": name,
                "success": False,
                "error": f"HTTP {response.status_code}",
                "status_code": response.status_code
            }
        
        data = response.json()
        
        # Validate response structure
        checks = []
        
        # Check advanced_mode field
        if "advanced_mode" in data:
            if data["advanced_mode"] == expected_advanced_mode:
                checks.append(("advanced_mode", True))
                print_success(
                    f"advanced_mode = {data['advanced_mode']} (expected)"
                )
            else:
                checks.append(("advanced_mode", False))
                print_error(
                    f"advanced_mode = {data['advanced_mode']} "
                    f"(expected {expected_advanced_mode})"
                )
        else:
            checks.append(("advanced_mode", False))
            print_error("advanced_mode field missing")
        
        # Check for results (if applicable)
        if check_results:
            if "results" in data:
                result_count = len(data["results"])
                total = data.get("total", 0)
                checks.append(("has_results", True))
                print_success(
                    f"Results: {result_count} returned, {total} total"
                )
            else:
                checks.append(("has_results", False))
                print_error("No results field in response")
        
        # Check query field
        if "query" in data:
            checks.append(("has_query", True))
            print_info(f"Query: {data['query']}")
        else:
            checks.append(("has_query", False))
            print_warning("No query field in response")
        
        all_passed = all(check[1] for check in checks)
        
        if all_passed:
            print_success("All checks passed!")
        else:
            failed = [check[0] for check in checks if not check[1]]
            print_error(f"Failed checks: {', '.join(failed)}")
        
        return {
            "name": name,
            "success": all_passed,
            "status_code": response.status_code,
            "checks": dict(checks),
            "total_results": data.get("total", 0),
            "query": data.get("query", "")
        }
        
    except requests.exceptions.ConnectionError:
        print_error("Connection failed - is the server running?")
        return {
            "name": name,
            "success": False,
            "error": "Connection failed"
        }
    except requests.exceptions.Timeout:
        print_error("Request timeout")
        return {
            "name": name,
            "success": False,
            "error": "Timeout"
        }
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return {
            "name": name,
            "success": False,
            "error": str(e)
        }


def main():
    """Run all tests and report results."""
    
    BASE_URL = "http://localhost:8000"
    
    print(f"\n{'='*70}")
    print(f"{Colors.BLUE}Advanced Search Mode - URL Test Suite{Colors.RESET}")
    print(f"{'='*70}")
    print(f"Testing against: {BASE_URL}")
    print(f"{'='*70}\n")
    
    # Define test cases
    tests = [
        {
            "name": "1. Boolean AND",
            "url": f"{BASE_URL}/api/serps?query=climate%20AND%20change&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "2. Boolean OR",
            "url": f"{BASE_URL}/api/serps?query=solar%20OR%20wind&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "3. Phrase Search",
            "url": f"{BASE_URL}/api/serps?query=%22climate%20change%22&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "4. Wildcard (*)",
            "url": f"{BASE_URL}/api/serps?query=climat*&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "5. Wildcard (?)",
            "url": f"{BASE_URL}/api/serps?query=cl?mate&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "6. Complex Query with Parentheses",
            "url": f"{BASE_URL}/api/serps?query=(renewable%20OR%20solar)%20AND%20energy&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "7. Advanced Mode with Year Filter",
            "url": f"{BASE_URL}/api/serps?query=%22climate%20change%22%20AND%20policy&advanced_mode=true&year=2023",
            "expected_advanced_mode": True
        },
        {
            "name": "8a. Simple Mode (for comparison)",
            "url": f"{BASE_URL}/api/serps?query=climate%20AND%20change&advanced_mode=false",
            "expected_advanced_mode": False
        },
        {
            "name": "8b. Advanced Mode (for comparison)",
            "url": f"{BASE_URL}/api/serps?query=climate%20AND%20change&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "9. Multiple OR",
            "url": f"{BASE_URL}/api/serps?query=solar%20OR%20wind%20OR%20hydro&advanced_mode=true",
            "expected_advanced_mode": True
        },
        {
            "name": "10. Phrase + Wildcard Combined",
            "url": f"{BASE_URL}/api/serps?query=%22renewable%20energy%22%20OR%20climat*&advanced_mode=true",
            "expected_advanced_mode": True
        }
    ]
    
    # Run all tests
    results = []
    for test in tests:
        result = test_url(
            name=test["name"],
            url=test["url"],
            expected_advanced_mode=test["expected_advanced_mode"]
        )
        results.append(result)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"{Colors.BLUE}Summary{Colors.RESET}")
    print(f"{'='*70}\n")
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"Total tests: {len(results)}")
    print_success(f"Passed: {passed}")
    if failed > 0:
        print_error(f"Failed: {failed}")
    
    # List failed tests
    if failed > 0:
        print(f"\n{Colors.RED}Failed tests:{Colors.RESET}")
        for r in results:
            if not r["success"]:
                error_msg = r.get("error", "Unknown error")
                print(f"  - {r['name']}: {error_msg}")
    
    # Connection check
    if any("Connection failed" in r.get("error", "") for r in results):
        print(f"\n{Colors.YELLOW}Note:{Colors.RESET}")
        print("  Make sure the API server is running:")
        print("  uvicorn app.main:main --reload")
    
    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
