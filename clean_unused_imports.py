#!/usr/bin/env python
"""
Clean Unused Imports Script

This script automatically removes unused imports flagged by flake8 F401.
It should be run before committing code to ensure clean imports.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Set

def run_flake8() -> List[str]:
    """Run flake8 to find unused imports and return the output lines"""
    cmd = [
        "flake8",
        "app", 
        "migrations",
        "--select=F401",
        "--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return result.stdout.splitlines()
        return []
    except Exception as e:
        print(f"Error running flake8: {e}")
        return []

def parse_flake8_output(lines: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """Parse flake8 output and organize by file"""
    files_to_fix = {}
    pattern = r"^(.*?):(\d+):(\d+):F401:(.*?) imported but unused$"
    
    for line in lines:
        match = re.match(pattern, line)
        if match:
            filepath, line_num, _, import_desc = match.groups()
            line_num = int(line_num)
            
            # Extract the import name
            import_name = import_desc.strip()
            
            if filepath not in files_to_fix:
                files_to_fix[filepath] = []
                
            files_to_fix[filepath].append((line_num, import_name))
            
    return files_to_fix

def clean_import_line(line: str, imports_to_remove: Set[str]) -> str:
    """Clean a single import line by removing unused imports"""
    # Handle 'from x import y' style imports
    if line.strip().startswith("from ") and " import " in line:
        prefix, imports = line.split(" import ", 1)
        
        # Split imports by comma, clean up whitespace
        import_items = [item.strip() for item in imports.split(",")]
        
        # Filter out unused imports
        cleaned_imports = [item for item in import_items if item not in imports_to_remove and item]
        
        # If no imports remain, remove the whole line
        if not cleaned_imports:
            return ""
            
        # Reconstruct the line
        return f"{prefix} import {', '.join(cleaned_imports)}"
        
    # Handle direct 'import x' style
    elif line.strip().startswith("import "):
        imports = line[7:].strip()  # Remove 'import ' prefix
        
        # Split imports by comma
        import_items = [item.strip() for item in imports.split(",")]
        
        # Filter out unused imports
        cleaned_imports = [item for item in import_items if item not in imports_to_remove and item]
        
        # If no imports remain, remove the whole line
        if not cleaned_imports:
            return ""
            
        # Reconstruct the line
        return f"import {', '.join(cleaned_imports)}"
        
    # Return unchanged if not an import line
    return line

def fix_file(filepath: str, unused_imports: List[Tuple[int, str]]) -> bool:
    """Fix a single file by removing unused imports"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Group by line number to handle multiple imports on the same line
        line_map = {}
        for line_num, import_name in unused_imports:
            if line_num not in line_map:
                line_map[line_num] = set()
            line_map[line_num].add(import_name)
            
        # Fix each line
        for line_num, imports_to_remove in line_map.items():
            if line_num <= len(lines):
                original_line = lines[line_num - 1]
                fixed_line = clean_import_line(original_line, imports_to_remove)
                lines[line_num - 1] = fixed_line + '\n' if fixed_line else ''
        
        # Remove empty lines (but preserve one newline)
        i = 0
        while i < len(lines) - 1:
            if lines[i].strip() == '' and lines[i+1].strip() == '':
                lines.pop(i)
            else:
                i += 1
                
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        return True
    except Exception as e:
        print(f"Error fixing file {filepath}: {e}")
        return False

def main() -> int:
    """Main function"""
    print("Running flake8 to find unused imports...")
    flake8_output = run_flake8()
    
    if not flake8_output:
        print("No unused imports found!")
        return 0
        
    print(f"Found {len(flake8_output)} unused import issues")
    
    # Parse flake8 output
    files_to_fix = parse_flake8_output(flake8_output)
    
    # Fix each file
    success_count = 0
    for filepath, unused_imports in files_to_fix.items():
        print(f"Cleaning {filepath}... ({len(unused_imports)} unused imports)")
        if fix_file(filepath, unused_imports):
            success_count += 1
            
    print(f"Successfully cleaned {success_count}/{len(files_to_fix)} files")
    
    # Run flake8 again to verify
    remaining_issues = run_flake8()
    if remaining_issues:
        print(f"Warning: {len(remaining_issues)} unused import issues still remain")
        print("Some complex cases might need manual fixing")
    else:
        print("All unused imports have been successfully cleaned!")
        
    return 0 if not remaining_issues else 1

if __name__ == "__main__":
    sys.exit(main())
