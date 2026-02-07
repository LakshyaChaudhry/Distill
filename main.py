"""End-to-end test script for the Distill agent."""
from distill.agent import run

SOURCE = "https://arxiv.org/abs/2301.02111"
OUTPUT_DIR = "./test_output"
VAULT_PATH = "/Users/lakshyachaudhry/desktop/mind/02_concepts"  # Set to your Obsidian vault path, e.g. "/Users/you/ObsidianVault"

if __name__ == "__main__":
    run(SOURCE, OUTPUT_DIR, vault_path=VAULT_PATH)
