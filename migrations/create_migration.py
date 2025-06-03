#!/usr/bin/env python
"""
Script to generate a new database migration file
Usage: python create_migration.py name_of_migration
"""
import os
import sys
import shutil
import datetime

def create_migration(name):
    """Create a new migration file based on the template"""
    if not name:
        print("Error: Migration name is required")
        print("Usage: python create_migration.py name_of_migration")
        sys.exit(1)
    
    # Clean the name (replace spaces with underscores, etc.)
    name = name.lower().replace(' ', '_').replace('-', '_')
    
    # Add timestamp to ensure unique ordering
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{name}.py"
    
    # Path to this script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Source template and destination path
    template_path = os.path.join(script_dir, "template_migration.py")
    destination_path = os.path.join(script_dir, filename)
    
    # Check if template exists
    if not os.path.exists(template_path):
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)
    
    # Copy the template to the new file
    shutil.copy2(template_path, destination_path)
    
    # Update the description in the new file
    with open(destination_path, 'r') as file:
        content = file.read()
    
    # Replace the template description with the migration name
    content = content.replace("Migration template - rename this file and update description", 
                             f"Migration to {name.replace('_', ' ')}")
    
    # Write the updated content back to the file
    with open(destination_path, 'w') as file:
        file.write(content)
    
    print(f"Created new migration: {filename}")
    print(f"Please update the migration file with your changes at: {destination_path}")

if __name__ == "__main__":
    migration_name = sys.argv[1] if len(sys.argv) > 1 else ""
    create_migration(migration_name)
