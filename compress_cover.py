from PIL import Image

# Open the image
img = Image.open('assets/cover.png')

# Resize to 1400x1400 (Spotify/Apple Podcasts recommended size)
img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)

# Convert to RGB if it's RGBA (PNG with transparency)
if img.mode == 'RGBA':
    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
    rgb_img.paste(img, mask=img.split()[3])
    img = rgb_img

# Save as optimized JPEG (much smaller than PNG)
img.save('assets/cover.jpg', 'JPEG', quality=85, optimize=True)

print("✅ Compressed cover saved as cover.jpg")

import os
original_size = os.path.getsize('assets/cover.png') / 1024 / 1024
new_size = os.path.getsize('assets/cover.jpg') / 1024 / 1024
print(f"Original: {original_size:.2f} MB")
print(f"Compressed: {new_size:.2f} MB")
print(f"Saved: {original_size - new_size:.2f} MB ({((original_size - new_size) / original_size * 100):.1f}%)")
