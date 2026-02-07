"""End-to-end test script for the Distill agent."""
from distill.agent import run

SOURCE = "https://arxiv.org/abs/2301.02111"
OUTPUT_DIR = "/Users/lakshyachaudhry/desktop/mind/03_papers"
VAULT_PATH = "/Users/lakshyachaudhry/desktop/mind/02_concepts"

if __name__ == "__main__":
    run(SOURCE, OUTPUT_DIR, vault_path=VAULT_PATH)
