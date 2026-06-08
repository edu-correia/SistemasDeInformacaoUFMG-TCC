file_path = "export_a1762d8f-fe64-4d48-a332-e88550ae5f1f_2026-06-07T193707.087360617.bib"  # Replace with your actual file name

count = 0
with open(file_path, 'r', encoding='utf-8') as file:
    for line in file:
        line = line.strip().lower()
        # Count lines starting with '@' but ignore standard BibTeX variables
        if line.startswith('@') and not line.startswith(('@string', '@comment', '@preamble')):
            count += 1

print(f"Total citations in the file: {count}")