import kagglehub

# Download directly into your project's raw data folder
path = kagglehub.dataset_download(
    "shudhanshusingh/az-medicine-dataset-of-india",
    output_dir=r"D:\indian-drug-substitute\indian-drug-substitute\output"
)

print("Path to dataset files:", path)