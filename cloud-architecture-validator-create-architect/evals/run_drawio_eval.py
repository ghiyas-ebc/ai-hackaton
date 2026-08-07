#!/usr/bin/env python3
"""
Simple evaluation script for the draw.io emitter feature.
"""

import json
import os
import subprocess
import sys
import tempfile

def run_command(cmd, cwd=None):
    """Run a command and return stdout, stderr, and exit code."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1

def test_drawio_emitter():
    """Test the draw.io emitter functionality."""
    print("Testing draw.io emitter functionality...")

    # Change to the project directory
    project_dir = "/Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-architecture-validator"
    os.chdir(project_dir)

    # Test 1: Generate draw.io without embedded icons
    print("\n1. Testing draw.io generation without embedded icons...")
    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as tmp:
        output_file = tmp.name

    cmd = f"source .venv/bin/activate && python3 scripts/diagram.py --edges 'cloud-run>cloud-sql' --format drawio --output {output_file}"
    stdout, stderr, exit_code = run_command(cmd, project_dir)

    if exit_code != 0:
        print(f"FAIL: Command failed with exit code {exit_code}")
        print(f"stderr: {stderr}")
        return False

    # Check if file was created and has content
    if not os.path.exists(output_file):
        print("FAIL: Output file was not created")
        return False

    with open(output_file, 'r') as f:
        content = f.read()

    if len(content) < 100:
        print("FAIL: Output file is too small")
        return False

    if "mxfile" not in content:
        print("FAIL: Output doesn't contain expected draw.io XML structure")
        return False

    print("PASS: draw.io file generated successfully without embedded icons")
    os.unlink(output_file)

    # Test 2: Generate draw.io with embedded icons (using test icons)
    print("\n2. Testing draw.io generation with embedded icons...")
    # Create test icons directory
    test_icons_dir = "/tmp/test_icons"
    os.makedirs(f"{test_icons_dir}/gcp/Unique Icons/Cloud Run/SVG", exist_ok=True)

    # Create a simple test SVG
    with open(f"{test_icons_dir}/gcp/Unique Icons/Cloud Run/SVG/CloudRun-512-color-rgb.svg", "w") as f:
        f.write('<svg><circle cx="256" cy="256" r="200" fill="blue"/></svg>')

    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False) as tmp:
        output_file = tmp.name

    cmd = f"source .venv/bin/activate && CAV_GCP_ICON_DIR={test_icons_dir}/gcp python3 scripts/diagram.py --edges 'cloud-run>cloud-sql' --format drawio --embed-icons --output {output_file}"
    stdout, stderr, exit_code = run_command(cmd, project_dir)

    if exit_code != 0:
        print(f"FAIL: Command failed with exit code {exit_code}")
        print(f"stderr: {stderr}")
        return False

    # Check if file was created and has content
    if not os.path.exists(output_file):
        print("FAIL: Output file was not created")
        return False

    with open(output_file, 'r') as f:
        content = f.read()

    if len(content) < 100:
        print("FAIL: Output file is too small")
        return False

    if "data:image/svg+xml;base64" not in content:
        print("FAIL: Output doesn't contain embedded SVG icons")
        return False

    print("PASS: draw.io file generated successfully with embedded icons")
    os.unlink(output_file)

    # Test 3: Check CLI help includes new options
    print("\n3. Testing CLI help includes new options...")
    cmd = "source .venv/bin/activate && python3 scripts/diagram.py --help"
    stdout, stderr, exit_code = run_command(cmd, project_dir)

    if exit_code != 0:
        print(f"FAIL: Command failed with exit code {exit_code}")
        print(f"stderr: {stderr}")
        return False

    required_options = ["--format", "--output", "--embed-icons"]
    missing_options = [opt for opt in required_options if opt not in stdout]

    if missing_options:
        print(f"FAIL: Missing CLI options: {missing_options}")
        return False

    print("PASS: All new CLI options are present in help")

    print("\nAll tests passed! draw.io emitter is working correctly.")
    return True

if __name__ == "__main__":
    success = test_drawio_emitter()
    sys.exit(0 if success else 1)