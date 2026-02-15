import os
import subprocess
import sys
import shutil

def compile_circuit(tex_file):
    """
    Compiles a LaTeX file to PDF using pdflatex.
    """
    if not os.path.exists(tex_file):
        print(f"Error: File {tex_file} not found.")
        return False

    file_dir = os.path.dirname(tex_file)
    file_name = os.path.basename(tex_file)
    base_name = os.path.splitext(file_name)[0]
    
    # Run pdflatex
    try:
        # Run twice to resolve references/labels if needed
        for _ in range(2):
            subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', file_name],
                cwd=file_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        print(f"Successfully compiled {base_name}.pdf")
    except subprocess.CalledProcessError as e:
        print("Error compiling LaTeX:")
        print(e.stdout.decode('utf-8', errors='ignore'))
        return False
    except FileNotFoundError:
        print("Error: pdflatex command not found. Please install a LaTeX distribution (e.g., MiKTeX, TeX Live).")
        return False

    # Try to convert to SVG
    pdf_file = os.path.join(file_dir, f"{base_name}.pdf")
    svg_file = os.path.join(file_dir, f"{base_name}.svg")
    
    if shutil.which('pdf2svg'):
        try:
            subprocess.run(['pdf2svg', pdf_file, svg_file], check=True)
            print(f"Successfully created {base_name}.svg")
        except subprocess.CalledProcessError:
            print("Error converting to SVG.")
    else:
        print("Warning: pdf2svg not found. Skipping SVG generation.")
        print("To generate SVG, please install pdf2svg or use an online converter.")

    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compile_circuit.py <path_to_tex_file>")
        sys.exit(1)
    
    compile_circuit(sys.argv[1])
