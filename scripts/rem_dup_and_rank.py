import sys # <-- ADICIONADO: Necessário para o Kill Switch funcionar
import os
import json
import glob
import time
import google.generativeai as genai
import bibtexparser
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# CONFIGURATION
# ==========================================
GEMINI_API_KEY = "<MY-API-KEY>"
INPUT_DIR = "input_bib_files"
OUTPUT_DIR = "ranked_citations"
PROGRESS_FILE = "progress.jsonl"
BATCH_SIZE = 25

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Ajustado para o nome oficial correto da API do Flash Lite para evitar erro de NotFound
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    generation_config={"response_mime_type": "application/json"}
)

# ==========================================
# PROMPT TEMPLATE
# ==========================================
SYSTEM_PROMPT = """
You are an expert software engineering researcher. I am writing a thesis specifically on "Code merge conflicts in Version Control Systems (like Git)".

I will provide a JSON list of citations (id, title, abstract). You must rank EACH citation based on its relevance to my thesis using the following scale:
5: Yes, definitely. Highly related to code merge conflicts, version control merging, and resolution.
4: Might be related. Includes topics like collaborative coding, CI/CD, or version control, and requires manual checking.
3: Tangentially related. Mentions version control or teamwork, but not directly involved with merge conflicts.
2: Barely related. I probably shouldn't read this, but it's not the most absurd thing.
1: Not acceptable at all. Completely unrelated to the scope.

RETURN ONLY A VALID JSON OBJECT mapping the citation ID to the integer rank. 
Example Output:
{"citation_id_1": 5, "citation_id_2": 1, "citation_id_3": 4}
"""

def setup_folders():
    """Create output directories for the 5 ranks."""
    for i in range(1, 6):
        folder_path = os.path.join(OUTPUT_DIR, f"Rank_{i}")
        os.makedirs(folder_path, exist_ok=True)

def load_and_deduplicate(input_dir):
    """Reads all bib files, extracts entries, and removes duplicates."""
    print("Loading and deduplicating BibTeX files. This might take a minute...")
    all_entries = []
    
    # <-- MODIFICADO: Agora procura em todas as subpastas (recursive=True)
    bib_files = glob.glob(os.path.join(input_dir, "**", "*.bib"), recursive=True)
    
    for file in tqdm(bib_files, desc="Parsing files"):
        with open(file, 'r', encoding='utf-8') as bibtex_file:
            # We use a custom parser to skip errors in badly formatted bib files
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            parser.ignore_nonstandard_types = True
            parser.homogenize_fields = True
            bib_database = bibtexparser.load(bibtex_file, parser=parser)
            all_entries.extend(bib_database.entries)

    # Deduplication logic
    unique_entries = {}
    duplicates_removed = 0
    
    for entry in all_entries:
        # Prefer DOI for uniqueness, fallback to lowercase title
        unique_key = entry.get('doi', '').strip().lower()
        if not unique_key:
            unique_key = entry.get('title', '').strip().lower()
            
        # If we somehow lack both, use the bibtex ID
        if not unique_key:
            unique_key = entry.get('ID')
            
        if unique_key not in unique_entries:
            unique_entries[unique_key] = entry
        else:
            duplicates_removed += 1
            
    print(f"Total citations found: {len(all_entries)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Unique citations to process: {len(unique_entries)}")
    
    return list(unique_entries.values())

def get_processed_ids():
    """Reads the progress file to see which citations have already been ranked."""
    processed = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                processed.update(data)
    return processed

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=60))
def rank_batch_with_gemini(batch):
    """Sends a batch to Gemini and returns the JSON result. Retries on failure."""
    
    # Prepare the payload (only send ID, Title, and Abstract to save tokens)
    payload = []
    for entry in batch:
        payload.append({
            "id": entry.get("ID"),
            "title": entry.get("title", "No Title"),
            "abstract": entry.get("abstract", "No Abstract")
        })
        
    prompt = SYSTEM_PROMPT + "\n\nInput Data:\n" + json.dumps(payload)
    
    response = model.generate_content(prompt)
    
    # The API is configured to return JSON, we parse it here
    result = json.loads(response.text)
    return result

def save_citation_to_folder(entry, rank):
    """Saves a single BibTeX entry into its corresponding rank folder."""
    # Ensure rank is within 1-5 bounds just in case AI hallucinates
    safe_rank = max(1, min(5, int(rank)))
    
    folder_path = os.path.join(OUTPUT_DIR, f"Rank_{safe_rank}")
    
    # Clean the ID to be a safe filename
    safe_filename = "".join([c for c in entry.get("ID") if c.isalnum() or c in "_-"]) + ".bib"
    file_path = os.path.join(folder_path, safe_filename)
    
    # Convert dict back to bibtex string
    db = bibtexparser.bibdatabase.BibDatabase()
    db.entries = [entry]
    bibtex_str = bibtexparser.dumps(db)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(bibtex_str)

def main():
    setup_folders()
    
    # 1. Load and deduplicate
    unique_entries = load_and_deduplicate(INPUT_DIR)
    
    # 2. Check checkpoint/progress
    processed_dict = get_processed_ids()
    print(f"Already processed citations: {len(processed_dict)}")
    
    # Filter out already processed entries (This garantees that old ones are skipped!)
    pending_entries = [e for e in unique_entries if e.get("ID") not in processed_dict]
    print(f"Remaining citations to process: {len(pending_entries)}")
    
    if len(pending_entries) == 0:
        print("All citations have been processed! Nothing new to do.")
        return
    
    # 3. Process in batches
    # Create batches of size BATCH_SIZE
    batches = [pending_entries[i:i + BATCH_SIZE] for i in range(0, len(pending_entries), BATCH_SIZE)]
    
    MAX_SAFE_API_CALLS = 2500  # Hard limit on API requests
    api_call_counter = 0       # Track requests
    
    with open(PROGRESS_FILE, 'a', encoding='utf-8') as progress_file:
        for batch in tqdm(batches, desc="Ranking batches via Gemini"):
            
            # --- KILL SWITCH ---
            if api_call_counter >= MAX_SAFE_API_CALLS:
                print(f"\n[KILL SWITCH ACTIVATED] Reached {MAX_SAFE_API_CALLS} API calls.")
                print("Stopping script to protect your budget!")
                sys.exit(1) # Instantly kills the program
            # -------------------

            try:
                rankings = rank_batch_with_gemini(batch)
                api_call_counter += 1 # Count successful call
                # <-- MODIFICADO: Uma chamada duplicada acidental à API foi removida aqui
                
                # Save progress immediately to prevent data loss
                progress_file.write(json.dumps(rankings) + "\n")
                progress_file.flush() # Force write to disk
                
                # Save actual bibtex files into folders
                for entry in batch:
                    c_id = entry.get("ID")
                    if c_id in rankings:
                        save_citation_to_folder(entry, rankings[c_id])
                    else:
                        # Fallback if AI missed an ID in the batch
                        print(f"\nWarning: AI missed citation ID {c_id}")
                
            except Exception as e:
                api_call_counter += 1 # Count the failed call too!
                print(f"\nError processing batch: {e}. Skipping to next batch...")
                time.sleep(3) # Cooldown before trying next

    print("\nProcessing Complete! Check the 'ranked_citations' folder.")

if __name__ == "__main__":
    main()