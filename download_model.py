import os
from huggingface_hub import hf_hub_download

# Model configuration
REPO_ID = "mitbersh/car-damage-segmentation"
MODEL_FILENAME = "damage_segmentation.pt"

# Local model directory
MODEL_DIR = "models"

os.makedirs(MODEL_DIR, exist_ok=True)

# Download model only if it doesn't exist
local_model_path = os.path.join(MODEL_DIR, MODEL_FILENAME)

if os.path.exists(local_model_path):
    print("Model already exists locally!")
    print("Path:", local_model_path)

else:
    print("Downloading car damage detection model...")
    
    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=MODEL_FILENAME,
        local_dir=MODEL_DIR
    )

    print("Model downloaded successfully!")
    print("Path:", downloaded_path)