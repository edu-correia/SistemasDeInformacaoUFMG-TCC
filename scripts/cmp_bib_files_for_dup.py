import bibtexparser

# Replace these with your actual file names
file1_path = "acm23.bib"
file2_path = "acm2024.bib"

# Load the first file
with open(file1_path, 'r', encoding='utf-8') as f1:
    bib1 = bibtexparser.load(f1)

# Load the second file
with open(file2_path, 'r', encoding='utf-8') as f2:
    bib2 = bibtexparser.load(f2)

# Helper function to clean titles (removes {} and makes lowercase)
def clean_title(title):
    return title.replace('{', '').replace('}', '').replace('\n', ' ').strip().lower()

# Extract all cleaned titles into sets
titles1 = set()
for entry in bib1.entries:
    if 'title' in entry:
        titles1.add(clean_title(entry['title']))

titles2 = set()
for entry in bib2.entries:
    if 'title' in entry:
        titles2.add(clean_title(entry['title']))

# Find the overlap (intersection) between the two sets of titles
duplicates = titles1.intersection(titles2)

# Print the counts
print(f"File 1 contains: {len(titles1)} valid titles")
print(f"File 2 contains: {len(titles2)} valid titles")
print(f"--> Found {len(duplicates)} repeated article(s) between them!\n")

# Optional: Print the names of the repeated articles
if duplicates:
    print("List of repeated articles:")
    for title in duplicates:
        print(f"- {title.title()}") # .title() capitalizes it nicely for reading