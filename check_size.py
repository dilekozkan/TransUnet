import os
from PIL import Image

# Define the directory containing the images
image_directory = '/userfiles/cgunduz/datasets/retinal_layers/val'

# Desired dimensions
desired_height = 128
desired_width = 1024

# Check each image in the directory
for filename in os.listdir(image_directory):
    if filename.endswith((".png", ".jpg", ".jpeg")):  # Check for common image file extensions
        image_path = os.path.join(image_directory, filename)
        with Image.open(image_path) as img:
            
            if img.size != (desired_width, desired_height):
                print(f"Image {filename} has different dimensions: {img.size}")

"""
dataset_directory ='/userfiles/cgunduz/datasets/retinal_layers/train'
dataset = Data_Binary(dataset_directory, ch=1, anydepth=False, input_size=(128,1024))
unique_sizes = check_image_sizes(dataset)

print("Unique image sizes in the dataset:", unique_sizes)"""
