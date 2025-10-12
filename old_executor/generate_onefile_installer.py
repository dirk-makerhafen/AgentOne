
import os
import textwrap

# Paths to the source files
PRIMITIVES_PATH = 'primitives.py'
MAIN_PATH = 'main.py'
INSTALLER_PATH = 'installer.py'
REQUIREMENTS_PATH = 'requirements.txt'

# Output file name
OUTPUT_FILE = 'onefileinstaller.py'

def read_file_content(filepath):
    """Reads the content of a file, handling potential encoding issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1') as f:
            return f.read()

def escape_triple_quotes(text):
    """Escapes triple single quotes within a string so it can be safely embedded."""
    return text.replace("'''", "\\'\\'\\'")

def generate_installer():
    print(f"Generating {OUTPUT_FILE}...")

    # Read all source file contents
    primitives_content = escape_triple_quotes(read_file_content(PRIMITIVES_PATH))
    main_content = escape_triple_quotes(read_file_content(MAIN_PATH))
    installer_content = escape_triple_quotes(read_file_content(INSTALLER_PATH))
    requirements_content = escape_triple_quotes(read_file_content(REQUIREMENTS_PATH))

    # Construct the content for onefileinstaller.py
    # This script will write the embedded files to a temp directory and then run the installer
    onefile_content = f"""
import os
import sys
import tempfile
import shutil
import subprocess

# Embedded file contents
_EMBEDDED_PRIMITIVES_CONTENT = '''{primitives_content}'''
_EMBEDDED_MAIN_CONTENT = '''{main_content}'''
_EMBEDDED_INSTALLER_CONTENT = '''{installer_content}'''
_EMBEDDED_REQUIREMENTS_CONTENT = '''{requirements_content}'''

EMBEDDED_FILES_MAP = {{
    'primitives.py': _EMBEDDED_PRIMITIVES_CONTENT,
    'main.py': _EMBEDDED_MAIN_CONTENT,
    'installer.py': _EMBEDDED_INSTALLER_CONTENT,
    'requirements.txt': _EMBEDDED_REQUIREMENTS_CONTENT,
}}

def main():
    temp_dir = None
    original_cwd = os.getcwd()
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        print(f"Temporary directory created at: {{temp_dir}}")

        # Write embedded files to the temporary directory
        for filename, content in EMBEDDED_FILES_MAP.items():
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Wrote {{filename}} to {{filepath}}")

        # Change current working directory to the temporary directory
        os.chdir(temp_dir)

        # Execute the installer.py script from the temporary directory
        # Pass all arguments received by onefileinstaller.py to installer.py
        installer_script_path = os.path.join(temp_dir, 'installer.py')
        print(f"Executing installer from: {{installer_script_path}} with arguments: {{sys.argv[1:]}}")
        
        # We need to use the current python executable to run the embedded installer
        command = [sys.executable, installer_script_path] + sys.argv[1:]
        
        # Run the installer process
        process = subprocess.run(command, check=False)
        
        if process.returncode != 0:
            print(f"Installer exited with non-zero status: {{process.returncode}}", file=sys.stderr)
            sys.exit(process.returncode)

    except Exception as e:
        print(f"An error occurred during one-file installer execution: {{e}}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Change back to original working directory
        os.chdir(original_cwd)
        # Clean up the temporary directory
        if temp_dir and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {{temp_dir}}")
            shutil.rmtree(temp_dir)
        else:
            print("No temporary directory to clean up or it was already removed.")

if __name__ == '__main__':
    main()

    """

    # Write the final combined content to the output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(onefile_content)

    print(f"Successfully generated {OUTPUT_FILE}")

if __name__ == '__main__':
    generate_installer()
