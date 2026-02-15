#!/usr/bin/env python3
"""Test if the base.html template compiles correctly"""
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
import os

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader('templates'))

try:
    # Try to load the template
    template = env.get_template('base.html')
    print("✅ Template compiled successfully!")
    
    # Check for duplicate blocks
    print("\nChecking for duplicate blocks...")
    template_code = open('templates/base.html').read()
    
    # Count block occurrences
    blocks = {}
    lines = template_code.split('\n')
    for i, line in enumerate(lines, 1):
        if '{% block' in line:
            # Extract block name
            import re
            match = re.search(r'{% block (\w+)', line)
            if match:
                block_name = match.group(1)
                blocks.setdefault(block_name, []).append(i)
    
    print(f"Found {len(blocks)} unique blocks:")
    for block_name, line_numbers in blocks.items():
        if len(line_numbers) > 1:
            print(f"❌ Block '{block_name}' defined multiple times at lines: {line_numbers}")
        else:
            print(f"✅ Block '{block_name}' defined once at line: {line_numbers[0]}")
            
except TemplateSyntaxError as e:
    print(f"❌ Template syntax error: {e}")
    print(f"Error at line: {e.lineno}")
except Exception as e:
    print(f"❌ Error: {e}")