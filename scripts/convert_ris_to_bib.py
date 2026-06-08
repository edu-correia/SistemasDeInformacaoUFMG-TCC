import rispy
import re

# File paths
ris_file_path = "wos2.ris"
bib_file_path = "webofscience2.bib"

# Dictionary to translate RIS reference types to BibTeX types
type_mapping = {
    'JOUR': 'article',
    'BOOK': 'book',
    'CHAP': 'incollection',
    'CONF': 'inproceedings',
    'THES': 'phdthesis',
    'RPRT': 'techreport',
    'PAT':  'misc'
}

# Open and parse the RIS file
with open(ris_file_path, 'r', encoding='utf-8') as ris_file:
    entries = rispy.load(ris_file)

# Open the new BIB file to write
with open(bib_file_path, 'w', encoding='utf-8') as bib_file:
    
    for index, entry in enumerate(entries):
        # 1. Determine the BibTeX type (default to 'misc' if unknown)
        ris_type = entry.get('type_of_reference', 'MISC')
        bib_type = type_mapping.get(ris_type, 'misc')
        
        # 2. Generate a Citation Key (e.g., "Smith2020_1")
        authors = entry.get('authors', ['Unknown'])
        first_author_last_name = authors[0].split(',')[0]
        # Remove any special characters/spaces from the author's name for the key
        clean_author = re.sub(r'\W+', '', first_author_last_name)
        year = entry.get('year', 'XXXX')
        
        cite_key = f"{clean_author}{year}_{index}"
        
        # 3. Write the entry to the .bib file
        bib_file.write(f"@{bib_type}{{{cite_key},\n")
        
        if 'title' in entry:
            bib_file.write(f"  title = {{{entry['title']}}},\n")
            
        if 'authors' in entry:
            # Bibtex expects authors separated by ' and '
            author_string = " and ".join(entry['authors'])
            bib_file.write(f"  author = {{{author_string}}},\n")
            
        if 'journal_name' in entry:
            bib_file.write(f"  journal = {{{entry['journal_name']}}},\n")
            
        if 'year' in entry:
            bib_file.write(f"  year = {{{entry['year']}}},\n")
            
        if 'volume' in entry:
            bib_file.write(f"  volume = {{{entry['volume']}}},\n")
            
        if 'number' in entry: # Issue number
            bib_file.write(f"  number = {{{entry['number']}}},\n")
            
        # Combine start and end pages
        if 'start_page' in entry:
            pages = entry['start_page']
            if 'end_page' in entry:
                pages += f"--{entry['end_page']}"
            bib_file.write(f"  pages = {{{pages}}},\n")
            
        if 'doi' in entry:
            bib_file.write(f"  doi = {{{entry['doi']}}},\n")
            
        if 'publisher' in entry:
            bib_file.write(f"  publisher = {{{entry['publisher']}}},\n")
            
        if 'url' in entry:
            bib_file.write(f"  url = {{{entry['url']}}},\n")
            
        if 'abstract' in entry:
            bib_file.write(f"  abstract = {{{entry['abstract']}}},\n")

        # Close the BibTeX entry
        bib_file.write("}\n\n")

print(f"Success! Converted {len(entries)} citations to {bib_file_path}")